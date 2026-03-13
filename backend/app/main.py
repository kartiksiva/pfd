from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Body, Depends, FastAPI, File, Form, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, ensure_schema_compat, get_db
from app.export_service import generate_exports
from app.pdd_template import render_document_markdown
from app.provider_health import check_providers_health
from app.retention import run_retention_sweep_once, start_retention_scheduler
from app.repository import create_job as repo_create_job
from app.repository import get_job as repo_get_job
from app.repository import list_jobs as repo_list_jobs
from app.repository import update_job_metadata, update_job_status
from app.schemas import (
    ApiEnvelope,
    DocumentTemplate,
    JobCreateResponseData,
    JobStatus,
    PDDDocumentModel,
    ProcessingProfile,
    Provider,
    SIPOCRowModel,
    SOPDocumentModel,
)
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


def _validate_sop_complete(document: dict) -> tuple[bool, str]:
    required_non_empty = [
        ("purpose", document.get("purpose")),
        ("steps", document.get("steps")),
        ("document_control", document.get("document_control")),
        ("quality_checks", document.get("quality_checks")),
        ("exception_handling", document.get("exception_handling")),
        ("controls_and_compliance", document.get("controls_and_compliance")),
    ]
    for key, value in required_non_empty:
        if value in (None, "", [], {}):
            return False, f"Missing required SOP field: {key}"
    return True, "ok"


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
    document_template: DocumentTemplate = Form(default=DocumentTemplate.pdd.value),
    process_name: Optional[str] = Form(default=None, max_length=255),
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
        document_template=document_template.value,
        process_name=process_name,
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
        document_template=DocumentTemplate((job.document_template or DocumentTemplate.pdd.value)),
        created_at=job.created_at,
    )
    background_tasks.add_task(process_job_async, job.id)
    return _success_response(data=data.model_dump(mode="json"), status_code=202)


@app.get("/api/jobs")
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[JobStatus] = Query(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    rows = repo_list_jobs(db, limit=limit, status=(status.value if status else None))
    return _success_response(
        data={
            "jobs": [
                {
                    "id": row.id,
                    "status": row.status,
                    "provider": row.provider,
                    "processing_profile": row.processing_profile,
                    "process_name": row.process_name,
                    "document_template": row.document_template or DocumentTemplate.pdd.value,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "expires_at": row.expires_at,
                    "error_code": row.error_code,
                    "artifacts": row.artifacts,
                }
                for row in rows
            ],
            "count": len(rows),
            "limit": limit,
            "status_filter": status.value if status else None,
        }
    )


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
            "process_name": job.process_name,
            "document_template": job.document_template or DocumentTemplate.pdd.value,
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
            "document_template": job.document_template or DocumentTemplate.pdd.value,
            "model_plan": job.model_plan,
            "document_type": job.document_template or DocumentTemplate.pdd.value,
            "document": job.draft_pdd,
            "sipoc": job.draft_sipoc,
            "document_markdown": render_document_markdown(
                job.draft_pdd,
                job.draft_sipoc,
                job.document_template or DocumentTemplate.pdd.value,
            ),
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

    document_type = payload.get("document_type") or job.document_template or DocumentTemplate.pdd.value
    document = payload.get("document")
    sipoc = payload.get("sipoc")
    if not isinstance(document, dict) or not isinstance(sipoc, list):
        return _error_response(
            code="ERR_INVALID_DRAFT_PAYLOAD",
            message="Draft payload must include document object and sipoc array.",
            status_code=400,
        )
    if str(document_type) != str(job.document_template or DocumentTemplate.pdd.value):
        return _error_response(
            code="ERR_INVALID_DRAFT_PAYLOAD",
            message="document_type must match job document_template.",
            details={"job_document_template": (job.document_template or DocumentTemplate.pdd.value), "document_type": document_type},
            status_code=400,
        )
    try:
        if job.document_template == DocumentTemplate.pdd.value:
            PDDDocumentModel(**document)
        else:
            SOPDocumentModel(**document)
        [SIPOCRowModel(**row) for row in sipoc]
    except Exception as exc:
        return _error_response(
            code="ERR_INVALID_DRAFT_PAYLOAD",
            message="Draft payload does not match required schema.",
            details={"reason": str(exc)},
            status_code=400,
        )

    job = update_job_metadata(db, job, draft_pdd=document, draft_sipoc=sipoc)
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
    try:
        if (job.document_template or DocumentTemplate.pdd.value) in {DocumentTemplate.sop.value, DocumentTemplate.custom_sop.value}:
            SOPDocumentModel(**job.draft_pdd)
            ok, msg = _validate_sop_complete(job.draft_pdd)
            if not ok:
                return _error_response(
                    code="ERR_NOT_FINALIZED",
                    message=msg,
                    details={"job_id": job_id, "document_template": job.document_template or DocumentTemplate.pdd.value},
                    status_code=409,
                )
        else:
            PDDDocumentModel(**job.draft_pdd)
        [SIPOCRowModel(**row) for row in job.draft_sipoc]
    except Exception as exc:
        return _error_response(
            code="ERR_NOT_FINALIZED",
            message="Draft does not satisfy required schema for finalization.",
            details={"reason": str(exc), "document_template": job.document_template or DocumentTemplate.pdd.value},
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
        processed_at = datetime.utcnow()
        artifacts = generate_exports(
            job_id=job.id,
            document=job.draft_pdd,
            sipoc=job.draft_sipoc,
            exports_root=exports_root,
            document_type=job.document_template or DocumentTemplate.pdd.value,
            process_name=job.process_name,
            llm_provider=(job.model_plan or {}).get("provider", job.provider),
            processed_at=processed_at,
        )
        job = update_job_metadata(
            db,
            job,
            artifacts=artifacts,
            expires_at=processed_at + timedelta(days=settings.retention_days),
            progress={"stage": "export_generation", "percent": 100},
        )
    except Exception as exc:
        err_text = str(exc).strip() or f"{exc.__class__.__name__}: {repr(exc)}"
        update_job_metadata(
            db,
            job,
            error_code="ERR_EXPORT_GENERATION_FAILED",
            error_message=err_text[:2000],
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
