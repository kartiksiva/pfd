from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from app.database import Base, SessionLocal, engine, ensure_schema_compat
from app.models import JobRecord
from app.worker import process_job_async


def _seed_job(
    *,
    status: str = "queued",
    provider: str = "google",
    max_duration: int = 7200,
    max_cost: float = 8.0,
    input_manifest: Optional[dict] = None,
) -> str:
    Base.metadata.create_all(bind=engine)
    ensure_schema_compat()
    db = SessionLocal()
    try:
        job_id = str(uuid4())
        now = datetime.utcnow()
        row = JobRecord(
            id=job_id,
            status=status,
            provider=provider,
            processing_profile="balanced",
            context_notes=None,
            model_plan={},
            input_manifest=input_manifest or {"video": None, "audio": None, "transcript": None},
            limits_applied={
                "max_file_size_mb": 500,
                "max_job_duration_seconds": max_duration,
                "max_provider_tokens": 1500000,
                "cost_target_band_usd_per_media_hour": {"min": 2.0, "max": max_cost},
            },
            usage_cost_estimate={},
            progress={"stage": "queued", "percent": 0},
            draft_pdd={},
            draft_sipoc=[],
            review_notes={"quality_score": 0.0, "flags": [], "assumptions": []},
            artifacts={"md": None, "json": None, "pdf": None},
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=7),
        )
        db.add(row)
        db.commit()
        return job_id
    finally:
        db.close()


def _load_job(job_id: str) -> JobRecord:
    db = SessionLocal()
    try:
        row = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        assert row is not None
        return row
    finally:
        db.close()


def test_timeout_guardrail_triggers_failure(monkeypatch):
    job_id = _seed_job(max_duration=1)

    # Force timeout path immediately.
    monkeypatch.setattr("app.worker._is_timeout", lambda *_args, **_kwargs: True)

    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "failed"
    assert row.error_code == "ERR_JOB_TIMEOUT"


def test_cost_guardrail_triggers_failure(monkeypatch):
    job_id = _seed_job(max_cost=1.0)

    class HighCostAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            class Evidence:
                provider = "google"
                transcript_text = "x"
                visual_events = []
                process_candidates = []
                confidence = 0.9

            class Result:
                model_plan = {"provider": "google"}
                usage_cost_estimate = {"currency": "USD", "estimated_total": 2.0, "estimated_per_media_hour": 99.0}
                evidence = Evidence()

            return Result()

    monkeypatch.setattr("app.worker.get_provider_adapter", lambda _provider: HighCostAdapter())
    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "failed"
    assert row.error_code == "ERR_PROVIDER_CAP_EXCEEDED"


def test_fallback_failure_sets_specific_error(monkeypatch):
    job_id = _seed_job()

    class CrashAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            raise RuntimeError("provider down")

    monkeypatch.setattr("app.worker.get_provider_adapter", lambda _provider: CrashAdapter())
    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "failed"
    assert row.error_code == "ERR_FALLBACK_TRANSCRIPTION_FAILED"


def test_fallback_success_is_visible_in_review_notes(monkeypatch):
    job_id = _seed_job(provider="openai")

    class CrashAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            raise RuntimeError("openai unavailable")

    class SuccessAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            class Evidence:
                provider = "google"
                transcript_text = "Step one\nStep two"
                visual_events = []
                process_candidates = [{"source": "transcript", "action": "extract_steps", "summary": "Step one"}]
                confidence = 0.85
                structured_extraction = None
                structured_extraction_error = None
                structured_extraction_raw_preview = None

            class Result:
                model_plan = {"provider": "google", "transcription_model": "gemini-2.5-flash"}
                usage_cost_estimate = {"currency": "USD", "estimated_total": 1.0, "estimated_per_media_hour": 3.0}
                evidence = Evidence()

            return Result()

    def adapter_factory(provider):
        if provider == "openai":
            return CrashAdapter()
        return SuccessAdapter()

    monkeypatch.setattr("app.worker.get_provider_adapter", adapter_factory)
    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "needs_review"
    assert row.model_plan.get("requested_provider") == "openai"
    assert row.model_plan.get("provider") == "google"
    assert row.model_plan.get("fallback_used") is True
    flags = row.review_notes.get("flags", [])
    assert any(flag.get("type") == "provider_fallback_used" for flag in flags)


def test_structured_extraction_failure_is_visible_in_review_notes(monkeypatch):
    job_id = _seed_job(provider="google")

    class SuccessAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            class Evidence:
                provider = "google"
                transcript_text = "# Process Discovery Session Transcript"
                visual_events = []
                process_candidates = [{"source": "transcript", "action": "extract_steps", "summary": "Transcript uploaded"}]
                confidence = 0.7
                structured_extraction = None
                structured_extraction_error = "Structured extraction returned no valid JSON. Raw preview: response body"
                structured_extraction_raw_preview = "response body"

            class Result:
                model_plan = {"provider": "google", "transcription_model": "gemini-2.5-flash"}
                usage_cost_estimate = {"currency": "USD", "estimated_total": 1.0, "estimated_per_media_hour": 3.0}
                evidence = Evidence()

            return Result()

    monkeypatch.setattr("app.worker.get_provider_adapter", lambda _provider: SuccessAdapter())
    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "needs_review"
    flags = row.review_notes.get("flags", [])
    assert any(flag.get("type") == "structured_extraction_failed" for flag in flags)
    assert any("Raw preview: response body" in flag.get("message", "") for flag in flags)
    assert any(
        "Structured extraction failed." in assumption
        for assumption in row.review_notes.get("assumptions", [])
    )
    assert row.progress.get("evidence", {}).get("structured_extraction_error") == "Structured extraction returned no valid JSON. Raw preview: response body"
    assert row.progress.get("evidence", {}).get("structured_extraction_raw_preview") == "response body"


def test_transcript_media_mismatch_adds_review_flag_and_reduces_confidence(monkeypatch):
    job_id = _seed_job(
        provider="google",
        input_manifest={
            "video": {"storage_key": "/tmp/demo.mov"},
            "audio": None,
            "transcript": {"storage_key": "/tmp/demo.vtt"},
        },
    )

    class SuccessAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            class Evidence:
                provider = "google"
                transcript_text = "Customer complaint is received and assigned."
                visual_events = []
                process_candidates = [{"source": "transcript", "action": "extract_steps", "summary": "Receive complaint"}]
                confidence = 0.9
                structured_extraction = None
                structured_extraction_error = None
                structured_extraction_raw_preview = None

            class Result:
                model_plan = {"provider": "google"}
                usage_cost_estimate = {"currency": "USD", "estimated_total": 1.0, "estimated_per_media_hour": 3.0}
                evidence = Evidence()

            return Result()

    monkeypatch.setattr("app.worker.get_provider_adapter", lambda _provider: SuccessAdapter())
    monkeypatch.setattr(
        "app.worker.verify_transcript_media_consistency",
        lambda **kwargs: {
            "checked": True,
            "provider": "google",
            "sample_source": "full_media_transcription_truncated_for_comparison",
            "sample_window_seconds": 60,
            "uploaded_transcript_chars_compared": 80,
            "verification_transcript_chars_compared": 75,
            "similarity_score": 0.12,
            "verdict": "suspected_mismatch",
            "reasons": ["media_transcript_similarity_below_mismatch_threshold"],
        },
    )

    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "needs_review"
    flags = row.review_notes.get("flags", [])
    assert any(flag.get("type") == "transcript_media_mismatch_suspected" for flag in flags)
    evidence = row.progress.get("evidence", {})
    assert evidence.get("transcript_media_consistency", {}).get("verdict") == "suspected_mismatch"
    assert evidence.get("confidence") <= 0.6


def test_transcript_media_inconclusive_adds_review_note(monkeypatch):
    job_id = _seed_job(
        provider="openai",
        input_manifest={
            "video": {"storage_key": "/tmp/demo.mov"},
            "audio": None,
            "transcript": {"storage_key": "/tmp/demo.vtt"},
        },
    )

    class SuccessAdapter:
        def run(self, _input_manifest, processing_profile="balanced", document_template="pdd", context_notes=None):
            class Evidence:
                provider = "openai"
                transcript_text = "Customer complaint is received and assigned." * 5
                visual_events = []
                process_candidates = [{"source": "transcript", "action": "extract_steps", "summary": "Receive complaint"}]
                confidence = 0.8
                structured_extraction = None
                structured_extraction_error = None
                structured_extraction_raw_preview = None

            class Result:
                model_plan = {"provider": "openai"}
                usage_cost_estimate = {"currency": "USD", "estimated_total": 1.0, "estimated_per_media_hour": 3.0}
                evidence = Evidence()

            return Result()

    monkeypatch.setattr("app.worker.get_provider_adapter", lambda _provider: SuccessAdapter())
    monkeypatch.setattr(
        "app.worker.verify_transcript_media_consistency",
        lambda **kwargs: {
            "checked": True,
            "provider": "openai",
            "sample_source": "verification_transcription_failed",
            "sample_window_seconds": 60,
            "uploaded_transcript_chars_compared": 200,
            "verification_transcript_chars_compared": 0,
            "similarity_score": None,
            "verdict": "inconclusive",
            "reasons": ["verification_transcription_failed:RuntimeError"],
        },
    )

    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "needs_review"
    assert any(flag.get("type") == "transcript_media_inconclusive" for flag in row.review_notes.get("flags", []))
