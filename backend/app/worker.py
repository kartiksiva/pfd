import time

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.pipelines.document_generation import generate_pdd_document, generate_sipoc_rows
from app.pipelines.media_understanding import build_media_understanding_payload
from app.pipelines.process_extraction import extract_process_structure
from app.pipelines.quality_checks import run_quality_checks
from app.providers.factory import get_provider_adapter
from app.repository import get_job, update_job_metadata, update_job_status
from app.schemas import JobStatus


def _fallback_provider(primary: str) -> str:
    if primary == "google":
        return "openai"
    if primary == "openai":
        return "google"
    return "google"


def _set_failure(db: Session, job_id: str, code: str, message: str) -> None:
    job = get_job(db, job_id)
    if not job:
        return
    if job.status in {JobStatus.queued.value, JobStatus.processing.value, JobStatus.needs_review.value}:
        ok, _ = update_job_status(db, job, JobStatus.failed.value)
        if ok:
            update_job_metadata(
                db,
                job,
                error_code=code,
                error_message=message[:2000],
                progress={"stage": "failed", "percent": 100},
            )


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


def process_job_async(job_id: str) -> None:
    db = SessionLocal()
    started_at = time.monotonic()
    try:
        job = get_job(db, job_id)
        if not job:
            return

        ok, msg = update_job_status(db, job, JobStatus.processing.value)
        if not ok:
            _set_failure(db, job_id, "ERR_INVALID_STATUS_TRANSITION", msg)
            return
        if _is_timeout(job, started_at):
            _set_failure(db, job_id, "ERR_JOB_TIMEOUT", "Job exceeded max processing duration.")
            return

        adapter = get_provider_adapter(job.provider)
        result = None
        try:
            result = adapter.run(job.input_manifest)
        except Exception as primary_exc:
            update_job_metadata(
                db,
                job,
                progress={
                    "stage": "provider_fallback",
                    "percent": 20,
                    "fallback_attempted": True,
                    "primary_provider": job.provider,
                    "primary_error": str(primary_exc)[:300],
                },
            )
            fallback = get_provider_adapter(_fallback_provider(job.provider))
            try:
                result = fallback.run(job.input_manifest)
            except Exception as fallback_exc:
                _set_failure(
                    db,
                    job_id,
                    "ERR_FALLBACK_TRANSCRIPTION_FAILED",
                    f"Primary and fallback providers failed: {fallback_exc}",
                )
                return

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
            "visual_events": result.evidence.visual_events,
            "process_candidates": result.evidence.process_candidates,
            "confidence": result.evidence.confidence,
            "structured_extraction": result.evidence.structured_extraction,
        }
        update_job_metadata(
            db,
            job,
            model_plan=result.model_plan,
            usage_cost_estimate=result.usage_cost_estimate,
            progress={"stage": "provider_routing", "percent": 25, "evidence": evidence_dict},
        )
        if _is_timeout(job, started_at):
            _set_failure(db, job_id, "ERR_JOB_TIMEOUT", "Job exceeded max processing duration.")
            return

        media_payload = build_media_understanding_payload(evidence_dict)
        update_job_metadata(
            db,
            job,
            progress={"stage": "media_understanding", "percent": 55, "evidence": evidence_dict, "media": media_payload},
        )

        extraction = extract_process_structure(media_payload)
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
            },
        )
        if _is_timeout(job, started_at):
            _set_failure(db, job_id, "ERR_JOB_TIMEOUT", "Job exceeded max processing duration.")
            return

        pdd = generate_pdd_document(extraction)
        sipoc = generate_sipoc_rows(extraction)
        review_notes = run_quality_checks(pdd=pdd, sipoc=sipoc, confidence=extraction.get("confidence", 0.0))

        update_job_metadata(
            db,
            job,
            draft_pdd=pdd,
            draft_sipoc=sipoc,
            review_notes=review_notes,
            progress={
                "stage": "quality_checks",
                "percent": 95,
                "evidence": evidence_dict,
                "media": media_payload,
                "extraction": extraction,
                "review_notes": review_notes,
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
            },
        )
    except Exception as exc:  # pragma: no cover - defensive branch for worker reliability.
        _set_failure(db, job_id, "ERR_JOB_PROCESSING_FAILED", str(exc))
    finally:
        db.close()
