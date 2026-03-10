from datetime import datetime, timedelta
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
            input_manifest={"video": None, "audio": None, "transcript": None},
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
        def run(self, _input_manifest, processing_profile="balanced"):
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
        def run(self, _input_manifest, processing_profile="balanced"):
            raise RuntimeError("provider down")

    monkeypatch.setattr("app.worker.get_provider_adapter", lambda _provider: CrashAdapter())
    process_job_async(job_id)
    row = _load_job(job_id)
    assert row.status == "failed"
    assert row.error_code == "ERR_FALLBACK_TRANSCRIPTION_FAILED"


def test_fallback_success_is_visible_in_review_notes(monkeypatch):
    job_id = _seed_job(provider="openai")

    class CrashAdapter:
        def run(self, _input_manifest, processing_profile="balanced"):
            raise RuntimeError("openai unavailable")

    class SuccessAdapter:
        def run(self, _input_manifest, processing_profile="balanced"):
            class Evidence:
                provider = "google"
                transcript_text = "Step one\nStep two"
                visual_events = []
                process_candidates = [{"source": "transcript", "action": "extract_steps", "summary": "Step one"}]
                confidence = 0.85
                structured_extraction = None

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
