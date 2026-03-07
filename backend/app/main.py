from pathlib import Path
from typing import Optional
from uuid import uuid4

from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Body, Depends, FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, ensure_schema_compat, get_db
from app.export_service import generate_exports
from app.pdd_template import render_standard_pdd_markdown
from app.provider_health import check_providers_health
from app.retention import run_retention_sweep_once, start_retention_scheduler
from app.repository import create_job as repo_create_job
from app.repository import get_job as repo_get_job
from app.repository import update_job_metadata, update_job_status
from app.schemas import ApiEnvelope, JobCreateResponseData, JobStatus, PDDDocumentModel, ProcessingProfile, Provider, SIPOCRowModel
from app.upload_validation import ValidationError, validate_and_persist_inputs
from app.worker import process_job_async

settings = get_settings()
uploads_root = Path(settings.uploads_dir)
exports_root = Path(settings.exports_dir)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compat()
    uploads_root.mkdir(parents=True, exist_ok=True)
    exports_root.mkdir(parents=True, exist_ok=True)
    start_retention_scheduler()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _success_response(data: dict, status_code: int = 200) -> JSONResponse:
    payload = ApiEnvelope(success=True, data=data, error=None)
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _error_response(code: str, message: str, details: Optional[dict] = None, status_code: int = 400) -> JSONResponse:
    payload = ApiEnvelope(success=False, data=None, error={"code": code, "message": message, "details": details or {}})
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return _error_response(
        code="ERR_VALIDATION",
        message="Request validation failed.",
        details={"errors": exc.errors()},
        status_code=422,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "env": settings.env,
        "default_provider": settings.default_provider,
        "openai_key_configured": "yes" if settings.openai_api_key else "no",
        "google_key_configured": "yes" if settings.google_api_key else "no",
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
    }


@app.get("/api/providers/health")
def providers_health(timeout_seconds: float = 10.0) -> ApiEnvelope:
    results = check_providers_health(timeout_seconds=timeout_seconds)
    data = {
        "all_ok": all(item.ok for item in results),
        "results": [
            {
                "provider": item.provider,
                "ok": item.ok,
                "latency_ms": item.latency_ms,
                "status_code": item.status_code,
                "message": item.message,
            }
            for item in results
        ],
    }
    return ApiEnvelope(success=True, data=data, error=None)


@app.post("/api/system/retention/sweep")
def trigger_retention_sweep() -> JSONResponse:
    result = run_retention_sweep_once()
    return _success_response(data=result)


@app.post("/api/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    provider: Provider = Form(default=Provider.google.value),
    processing_profile: ProcessingProfile = Form(default=ProcessingProfile.balanced.value),
    context_notes: Optional[str] = Form(default=None, max_length=2000),
    video_file: Optional[UploadFile] = File(default=None),
    audio_file: Optional[UploadFile] = File(default=None),
    transcript_file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    job_id = str(uuid4())
    try:
        input_manifest = await validate_and_persist_inputs(
            job_id=job_id,
            uploads_dir=uploads_root,
            video_file=video_file,
            audio_file=audio_file,
            transcript_file=transcript_file,
        )
    except ValidationError as exc:
        status_code = 413 if exc.code == "ERR_FILE_TOO_LARGE" else 415 if exc.code == "ERR_UNSUPPORTED_MIME" else 400
        return _error_response(code=exc.code, message=exc.message, details=exc.details, status_code=status_code)

    limits_applied = {
        "max_file_size_mb": 500,
        "max_job_duration_seconds": settings.max_job_duration_seconds,
        "max_provider_tokens": settings.max_provider_tokens,
        "cost_target_band_usd_per_media_hour": {"min": settings.cost_band_min_usd, "max": settings.cost_band_max_usd},
    }

    job = repo_create_job(
        db,
        job_id=job_id,
        provider=provider.value,
        processing_profile=processing_profile.value,
        context_notes=context_notes,
        input_manifest=input_manifest,
        limits_applied=limits_applied,
        retention_days=settings.retention_days,
    )

    data = JobCreateResponseData(
        job_id=job.id,
        status=JobStatus(job.status),
        provider=Provider(job.provider),
        processing_profile=ProcessingProfile(job.processing_profile),
        created_at=job.created_at,
    )
    background_tasks.add_task(process_job_async, job.id)
    return _success_response(data=data.model_dump(mode="json"), status_code=202)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    job = repo_get_job(db, job_id)
    if not job:
        return _error_response(
            code="ERR_JOB_NOT_FOUND",
            message="Job not found.",
            details={"job_id": job_id},
            status_code=404,
        )
    return _success_response(
        data={
            "id": job.id,
            "status": job.status,
            "provider": job.provider,
            "processing_profile": job.processing_profile,
            "model_plan": job.model_plan,
            "input_manifest": job.input_manifest,
            "limits_applied": job.limits_applied,
            "usage_cost_estimate": job.usage_cost_estimate,
            "progress": job.progress,
            "artifacts": job.artifacts,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "expires_at": job.expires_at,
        },
    )


@app.get("/api/jobs/{job_id}/draft")
def get_draft(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    job = repo_get_job(db, job_id)
    if not job:
        return _error_response(
            code="ERR_JOB_NOT_FOUND",
            message="Job not found.",
            details={"job_id": job_id},
            status_code=404,
        )
    return _success_response(
        data={
            "job_id": job.id,
            "provider": job.provider,
            "model_plan": job.model_plan,
            "pdd": job.draft_pdd,
            "sipoc": job.draft_sipoc,
            "pdd_markdown": render_standard_pdd_markdown(job.draft_pdd, job.draft_sipoc),
            "review_notes": job.review_notes,
            "updated_at": job.updated_at,
        }
    )


@app.put("/api/jobs/{job_id}/draft")
def update_draft(job_id: str, payload: dict = Body(...), db: Session = Depends(get_db)) -> JSONResponse:
    job = repo_get_job(db, job_id)
    if not job:
        return _error_response(
            code="ERR_JOB_NOT_FOUND",
            message="Job not found.",
            details={"job_id": job_id},
            status_code=404,
        )

    pdd = payload.get("pdd")
    sipoc = payload.get("sipoc")
    if not isinstance(pdd, dict) or not isinstance(sipoc, list):
        return _error_response(
            code="ERR_INVALID_DRAFT_PAYLOAD",
            message="Draft payload must include pdd object and sipoc array.",
            status_code=400,
        )
    try:
        PDDDocumentModel(**pdd)
        [SIPOCRowModel(**row) for row in sipoc]
    except Exception as exc:
        return _error_response(
            code="ERR_INVALID_DRAFT_PAYLOAD",
            message="Draft payload does not match required schema.",
            details={"reason": str(exc)},
            status_code=400,
        )

    job = update_job_metadata(db, job, draft_pdd=pdd, draft_sipoc=sipoc)
    return _success_response(data={"job_id": job_id, "saved": True, "updated_at": job.updated_at})


@app.post("/api/jobs/{job_id}/finalize")
def finalize_job(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    job = repo_get_job(db, job_id)
    if not job:
        return _error_response(
            code="ERR_JOB_NOT_FOUND",
            message="Job not found.",
            details={"job_id": job_id},
            status_code=404,
        )
    if job.status == JobStatus.completed.value:
        return _success_response(
            data={"job_id": job_id, "status": JobStatus.completed.value, "next_stage": "done", "idempotent": True},
            status_code=200,
        )
    if job.status != JobStatus.needs_review.value:
        return _error_response(
            code="ERR_INVALID_STATUS_TRANSITION",
            message=f"Finalize is allowed only from {JobStatus.needs_review.value} status.",
            details={"job_id": job_id, "status": job.status},
            status_code=409,
        )
    if not isinstance(job.draft_pdd, dict) or not isinstance(job.draft_sipoc, list) or not job.draft_sipoc:
        return _error_response(
            code="ERR_NOT_FINALIZED",
            message="Draft is incomplete; cannot finalize.",
            details={"job_id": job_id},
            status_code=409,
        )

    ok, msg = update_job_status(db, job, JobStatus.processing.value)
    if not ok:
        return _error_response(
            code="ERR_INVALID_STATUS_TRANSITION",
            message=msg,
            details={"job_id": job_id},
            status_code=409,
        )
    try:
        artifacts = generate_exports(job_id=job.id, pdd=job.draft_pdd, sipoc=job.draft_sipoc, exports_root=exports_root)
        job = update_job_metadata(
            db,
            job,
            artifacts=artifacts,
            progress={"stage": "export_generation", "percent": 100},
        )
    except Exception as exc:
        update_job_metadata(
            db,
            job,
            error_code="ERR_EXPORT_GENERATION_FAILED",
            error_message=str(exc)[:2000],
        )
        update_job_status(db, job, JobStatus.failed.value)
        return _error_response(
            code="ERR_EXPORT_GENERATION_FAILED",
            message="Failed to generate export artifacts.",
            status_code=500,
        )

    ok, msg = update_job_status(db, job, JobStatus.completed.value)
    if not ok:
        return _error_response(
            code="ERR_INVALID_STATUS_TRANSITION",
            message=msg,
            details={"job_id": job_id},
            status_code=409,
        )
    return _success_response(
        data={"job_id": job_id, "status": JobStatus.completed.value, "next_stage": "done"},
        status_code=202,
    )


@app.get("/api/jobs/{job_id}/exports/{fmt}")
def get_export(job_id: str, fmt: str, db: Session = Depends(get_db)):
    job = repo_get_job(db, job_id)
    if not job:
        return _error_response(
            code="ERR_JOB_NOT_FOUND",
            message="Job not found.",
            details={"job_id": job_id},
            status_code=404,
        )
    if job.status != JobStatus.completed.value:
        return _error_response(
            code="ERR_NOT_FINALIZED",
            message="Export is available only after finalization.",
            details={"job_id": job_id, "status": job.status},
            status_code=409,
        )
    if fmt not in {"md", "json", "pdf", "docx"}:
        return _error_response(
            code="ERR_INVALID_EXPORT_FORMAT",
            message="Invalid export format.",
            details={"format": fmt},
            status_code=400,
        )
    path = job.artifacts.get(fmt)
    if not path or not Path(path).exists():
        return _error_response(
            code="ERR_EXPORT_NOT_FOUND",
            message="Requested export artifact not found.",
            details={"format": fmt},
            status_code=404,
        )
    media_type = {
        "md": "text/markdown",
        "json": "application/json",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[fmt]
    filename = Path(path).name
    return FileResponse(path=path, media_type=media_type, filename=filename)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> ApiEnvelope:
    return ApiEnvelope(success=True, data={"job_id": job_id, "deleted": True}, error=None)
