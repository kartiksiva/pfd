from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import JobRecord
from app.schemas import JobStatus

ALLOWED_TRANSITIONS = {
    JobStatus.queued.value: {JobStatus.processing.value, JobStatus.failed.value, JobStatus.expired.value},
    JobStatus.processing.value: {
        JobStatus.needs_review.value,
        JobStatus.completed.value,
        JobStatus.failed.value,
        JobStatus.expired.value,
    },
    JobStatus.needs_review.value: {JobStatus.processing.value, JobStatus.failed.value, JobStatus.expired.value},
    JobStatus.completed.value: {JobStatus.expired.value},
    JobStatus.failed.value: {JobStatus.expired.value},
    JobStatus.expired.value: set(),
}


def create_job(
    db: Session,
    *,
    job_id: Optional[str] = None,
    provider: str,
    processing_profile: str,
    document_template: str,
    process_name: Optional[str],
    context_notes: Optional[str],
    input_manifest: dict,
    limits_applied: dict,
    retention_days: int = 7,
) -> JobRecord:
    now = datetime.utcnow()
    if provider == "google":
        fallback_provider = "openai"
    elif provider in {"openai", "azure_openai", "ollama"}:
        fallback_provider = "google"
    else:
        fallback_provider = "google"
    payload = {
        "status": JobStatus.queued.value,
        "provider": provider,
        "processing_profile": processing_profile,
        "document_template": document_template,
        "process_name": process_name,
        "context_notes": context_notes,
        "model_plan": {
            "provider": provider,
            "transcription_model": "",
            "multimodal_model": "",
            "generation_model": "",
            "fallback_transcription": {"provider": fallback_provider, "model": ""},
        },
        "input_manifest": input_manifest,
        "limits_applied": limits_applied,
        "usage_cost_estimate": {"currency": "USD", "estimated_total": 0.0, "estimated_per_media_hour": 0.0},
        "progress": {"stage": "queued", "percent": 0},
        "draft_pdd": {},
        "draft_sipoc": [],
        "review_notes": {"quality_score": 0.0, "flags": [], "assumptions": []},
        "artifacts": {"md": None, "json": None, "pdf": None, "docx": None},
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(days=retention_days),
    }
    if job_id:
        payload["id"] = job_id
    job = JobRecord(**payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> Optional[JobRecord]:
    return db.query(JobRecord).filter(JobRecord.id == job_id).first()


def list_jobs(db: Session, *, limit: int = 50, status: Optional[str] = None) -> list[JobRecord]:
    q = db.query(JobRecord)
    if status:
        q = q.filter(JobRecord.status == status)
    return q.order_by(desc(JobRecord.created_at)).limit(limit).all()


def list_expired_jobs(db: Session, now: Optional[datetime] = None) -> list[JobRecord]:
    now = now or datetime.utcnow()
    return db.query(JobRecord).filter(JobRecord.expires_at <= now, JobRecord.status != JobStatus.expired.value).all()


def update_job_status(db: Session, job: JobRecord, target_status: str) -> tuple[bool, str]:
    allowed = ALLOWED_TRANSITIONS.get(job.status, set())
    if target_status not in allowed:
        return False, f"Invalid status transition: {job.status} -> {target_status}"
    job.status = target_status
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return True, "ok"


def update_job_metadata(
    db: Session,
    job: JobRecord,
    *,
    model_plan: Optional[dict] = None,
    usage_cost_estimate: Optional[dict] = None,
    progress: Optional[dict] = None,
    draft_pdd: Optional[dict] = None,
    draft_sipoc: Optional[list] = None,
    review_notes: Optional[dict] = None,
    artifacts: Optional[dict] = None,
    expires_at: Optional[datetime] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> JobRecord:
    if model_plan is not None:
        job.model_plan = model_plan
    if usage_cost_estimate is not None:
        job.usage_cost_estimate = usage_cost_estimate
    if progress is not None:
        job.progress = progress
    if draft_pdd is not None:
        job.draft_pdd = draft_pdd
    if draft_sipoc is not None:
        job.draft_sipoc = draft_sipoc
    if review_notes is not None:
        job.review_notes = review_notes
    if artifacts is not None:
        job.artifacts = artifacts
    if expires_at is not None:
        job.expires_at = expires_at
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
