import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.pipelines.document_generation import generate_document_from_extraction, generate_sipoc_rows
from app.pipelines.media_understanding import build_media_understanding_payload
from app.pipelines.process_extraction import extract_process_structure
from app.pipelines.transcript_media_consistency import verify_transcript_media_consistency
from app.pipelines.quality_checks import run_quality_checks
from app.providers.factory import get_fallback_provider, get_provider_adapter
from app.repository import get_job, update_job_metadata, update_job_status
from app.schemas import JobStatus

logger = logging.getLogger(__name__)


def _set_failure(db: Session, job_id: str, code: str, message: str) -> None:
    job = get_job(db, job_id)
    if not job:
        logger.warning("_set_failure called for unknown job_id=%s (code=%s)", job_id, code)
        return
    if job.status in {JobStatus.queued.value, JobStatus.processing.value, JobStatus.needs_review.value}:
        update_job_metadata(
            db,
            job,
            error_code=code,
            error_message=message[:2000],
            progress={"stage": "failed", "percent": 100},
        )
        update_job_status(db, job, JobStatus.failed.value)


def _is_timeout(job, started_at: float) -> bool:
    limit = int(job.limits_applied.get("max_job_duration_seconds", 0) or 0)
    if limit <= 0:
        return False
    return (time.monotonic() - started_at) > limit


def _violates_cost_guardrail(job, usage: dict) -> bool:
    band = job.limits_applied.get("cost_target_band_usd_per_media_hour", {})
    max_allowed = float(band.get("max", 0) or 0)
    current = float(usage.get("estimated_per_media_hour", 0) or 0)
    return max_allowed > 0 and current > max_allowed


def _apply_consistency_confidence_penalty(confidence: float, consistency_result: dict) -> float:
    verdict = str((consistency_result or {}).get("verdict", "")).strip().lower()
    penalty = 0.0
    if verdict == "inconclusive":
        penalty = 0.10
    elif verdict == "suspected_mismatch":
        penalty = 0.30
    return max(round(float(confidence or 0.0) - penalty, 2), 0.05)


def process_job_async(job_id: str) -> None:
    db = SessionLocal()
    started_at = time.monotonic()
    try:
        job = get_job(db, job_id)
        if not job:
            logger.error("process_job_async: job_id=%s not found in DB; cannot process", job_id)
            return

        ok, msg = update_job_status(db, job, JobStatus.processing.value)
        if not ok:
            _set_failure(db, job_id, "ERR_INVALID_STATUS_TRANSITION", msg)
            return
        if _is_timeout(job, started_at):
            _set_failure(db, job_id, "ERR_JOB_TIMEOUT", "Job exceeded max processing duration.")
            return

        requested_provider = job.provider
        adapter = get_provider_adapter(requested_provider)
        result = None
        fallback_used = False
        primary_error: Optional[str] = None
        execution_provider = requested_provider
        try:
            result = adapter.run(
                job.input_manifest,
                processing_profile=job.processing_profile,
                document_template=job.document_template,
                context_notes=job.context_notes,
            )
            execution_provider = result.evidence.provider or requested_provider
        except Exception as primary_exc:
            fallback_used = True
            primary_error = str(primary_exc)[:300]
            update_job_metadata(
                db,
                job,
                progress={
                    "stage": "provider_fallback",
                    "percent": 20,
                    "fallback_attempted": True,
                    "primary_provider": requested_provider,
                    "primary_error": primary_error,
                },
            )
            fallback_name = get_fallback_provider(requested_provider)
            fallback = get_provider_adapter(fallback_name)
            try:
                result = fallback.run(
                    job.input_manifest,
                    processing_profile=job.processing_profile,
                    document_template=job.document_template,
                    context_notes=job.context_notes,
                )
                execution_provider = result.evidence.provider or fallback_name
            except Exception as fallback_exc:
                _set_failure(
                    db,
                    job_id,
                    "ERR_FALLBACK_TRANSCRIPTION_FAILED",
                    f"Primary and fallback providers failed: {fallback_exc}",
                )
                return

        # NOTE: Cost guardrail is evaluated after the provider adapter has already run.
        # This catches future jobs once the operator adjusts cost_band_max_usd, but does
        # not prevent the current job from being billed. Acceptable MVP limitation.
        if _violates_cost_guardrail(job, result.usage_cost_estimate):
            _set_failure(
                db,
                job_id,
                "ERR_PROVIDER_CAP_EXCEEDED",
                "Estimated provider run-cost exceeds configured budget band.",
            )
            return

        evidence_dict = {
            "provider": result.evidence.provider,
            "transcript_text": result.evidence.transcript_text,
            "transcript_format": getattr(result.evidence, "transcript_format", None),
            "visual_events": result.evidence.visual_events,
            "frame_images": getattr(result.evidence, "frame_images", []),
            "process_candidates": result.evidence.process_candidates,
            "confidence": result.evidence.confidence,
            "structured_extraction": result.evidence.structured_extraction,
            "structured_extraction_error": getattr(result.evidence, "structured_extraction_error", None),
            "structured_extraction_raw_preview": getattr(result.evidence, "structured_extraction_raw_preview", None),
        }
        consistency_result = verify_transcript_media_consistency(
            provider=execution_provider,
            input_manifest=job.input_manifest,
            transcript_text=result.evidence.transcript_text,
        )
        evidence_dict["transcript_media_consistency"] = consistency_result
        evidence_dict["confidence"] = _apply_consistency_confidence_penalty(
            evidence_dict.get("confidence", 0.0), consistency_result
        )
        provider_execution = {
            "requested_provider": requested_provider,
            "executed_provider": execution_provider,
            "fallback_used": fallback_used,
            "primary_error": primary_error,
        }
        model_plan = dict(result.model_plan or {})
        model_plan["requested_provider"] = requested_provider
        model_plan["provider"] = execution_provider
        model_plan["fallback_used"] = fallback_used
        if primary_error:
            model_plan["primary_error"] = primary_error
        update_job_metadata(
            db,
            job,
            model_plan=model_plan,
            usage_cost_estimate=result.usage_cost_estimate,
            progress={
                "stage": "provider_routing",
                "percent": 25,
                "evidence": evidence_dict,
                "provider_execution": provider_execution,
            },
        )
        if _is_timeout(job, started_at):
            _set_failure(db, job_id, "ERR_JOB_TIMEOUT", "Job exceeded max processing duration.")
            return

        media_payload = build_media_understanding_payload(evidence_dict, input_manifest=job.input_manifest)
        update_job_metadata(
            db,
            job,
            progress={
                "stage": "media_understanding",
                "percent": 55,
                "evidence": evidence_dict,
                "media": media_payload,
                "provider_execution": provider_execution,
            },
        )

        extraction = extract_process_structure(media_payload)
        extraction["confidence"] = min(
            float(extraction.get("confidence", evidence_dict.get("confidence", 0.0)) or 0.0),
            float(evidence_dict.get("confidence", 0.0) or 0.0),
        )
        evidence_dict["confidence"] = extraction.get("confidence", evidence_dict.get("confidence", 0.0))

        update_job_metadata(
            db,
            job,
            progress={
                "stage": "process_extraction",
                "percent": 80,
                "evidence": evidence_dict,
                "media": media_payload,
                "extraction": extraction,
                "provider_execution": provider_execution,
            },
        )
        if _is_timeout(job, started_at):
            _set_failure(db, job_id, "ERR_JOB_TIMEOUT", "Job exceeded max processing duration.")
            return

        document_type = str(getattr(job, "document_template", "pdd") or "pdd")
        document = generate_document_from_extraction(
            extraction,
            document_type=document_type,
            frame_images=media_payload.get("frame_images", []),
        )
        sipoc = generate_sipoc_rows(extraction)
        review_notes = run_quality_checks(
            pdd=document,
            sipoc=sipoc,
            confidence=extraction.get("confidence", 0.0),
            document_type=document_type,
            source_facts={
                **(extraction.get("operational_facts", {}) if isinstance(extraction.get("operational_facts"), dict) else {}),
                "effort_data": extraction.get("effort_data", []),
                "pain_points": extraction.get("pain_points", []),
            },
        )
        if fallback_used:
            review_notes.setdefault("flags", []).append(
                {
                    "type": "provider_fallback_used",
                    "path": "provider_execution",
                    "message": (
                        f"Selected provider '{requested_provider}' failed during processing. "
                        f"Output was generated using fallback provider '{execution_provider}'."
                    ),
                }
            )
            review_notes.setdefault("assumptions", []).append(
                "Primary provider failed. Re-run with your desired provider if provider-specific output is required."
            )
        structured_error = evidence_dict.get("structured_extraction_error")
        if structured_error and not evidence_dict.get("structured_extraction"):
            review_notes.setdefault("flags", []).append(
                {
                    "type": "structured_extraction_failed",
                    "path": "provider_execution.structured_extraction",
                    "message": structured_error,
                }
            )
            review_notes.setdefault("assumptions", []).append(
                "Structured extraction failed. Draft content may reflect safe fallback behavior and requires manual review."
            )
        consistency_verdict = str((consistency_result or {}).get("verdict", "")).strip().lower()
        if consistency_verdict == "inconclusive":
            review_notes.setdefault("flags", []).append(
                {
                    "type": "transcript_media_inconclusive",
                    "path": "provider_execution.transcript_media_consistency",
                    "message": "Uploaded transcript could not be confidently matched to uploaded media.",
                }
            )
            review_notes.setdefault("assumptions", []).append(
                "Transcript and media alignment is inconclusive. Manually verify the uploaded pair before finalization."
            )
        elif consistency_verdict == "suspected_mismatch":
            review_notes.setdefault("flags", []).append(
                {
                    "type": "transcript_media_mismatch_suspected",
                    "path": "provider_execution.transcript_media_consistency",
                    "message": "Uploaded transcript appears to differ materially from uploaded media.",
                }
            )
            review_notes.setdefault("assumptions", []).append(
                "Transcript and media may not belong together. Confirm the correct transcript before finalization."
            )

        update_job_metadata(
            db,
            job,
            draft_pdd=document,
            draft_sipoc=sipoc,
            review_notes=review_notes,
            progress={
                "stage": "quality_checks",
                "percent": 95,
                "evidence": evidence_dict,
                "media": media_payload,
                "extraction": extraction,
                "review_notes": review_notes,
                "provider_execution": provider_execution,
            },
        )

        ok, msg = update_job_status(db, job, JobStatus.needs_review.value)
        if not ok:
            _set_failure(db, job_id, "ERR_INVALID_STATUS_TRANSITION", msg)
            return

        update_job_metadata(
            db,
            job,
            progress={
                "stage": "ready_for_review",
                "percent": 100,
                "evidence": evidence_dict,
                "media": media_payload,
                "extraction": extraction,
                "review_notes": review_notes,
                "provider_execution": provider_execution,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive branch for worker reliability.
        _set_failure(db, job_id, "ERR_JOB_PROCESSING_FAILED", str(exc))
    finally:
        db.close()
