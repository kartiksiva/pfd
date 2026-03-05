# Gemini Review Handover

## Context
This handover is for Gemini acting as technical reviewer for the Process Documentation Agent MVP.

Primary references:
- `PRD.md`
- `AGENTS.md`
- `TASKS.md`
- `schemas.md`
- `openapi.yaml`

## Current Build Snapshot
Implemented so far:
- Project scaffold:
  - `frontend/` (Next.js shell)
  - `backend/` (FastAPI)
  - `infra/` (docker compose)
- Provider setup:
  - Runtime provider enum supports `openai|google`
  - `/api/providers/health` verifies OpenAI + Google connectivity
- T1.2/T2.1 core backend progress:
  - SQLite-backed `jobs` table (`JobRecord`) via SQLAlchemy
  - Startup auto-creates DB tables
  - `POST /api/jobs` supports multipart uploads
  - Validation implemented:
    - at least one input required
    - MIME allowlist per file category
    - 500MB max file size per file
  - Files are persisted to `UPLOADS_DIR/<job_id>/...`
  - `input_manifest` persisted in DB
  - `GET /api/jobs/{job_id}` returns persisted metadata
  - Status transition guard added in repository (`ALLOWED_TRANSITIONS`)

## Files To Review First
- `backend/app/main.py`
- `backend/app/upload_validation.py`
- `backend/app/models.py`
- `backend/app/repository.py`
- `backend/app/database.py`
- `backend/app/provider_health.py`
- `openapi.yaml` (provider health + job contracts)

## Review Objectives
1. Contract compliance
- API responses must follow envelope shape:
  - `success`, `data`, `error`
- Ensure `POST /api/jobs` and `GET /api/jobs/{id}` align with `schemas.md` and `openapi.yaml`.

2. Data integrity
- Check SQLAlchemy model correctness for `JobRecord`.
- Validate JSON fields (`input_manifest`, `artifacts`) are safe and consistently shaped.

3. Validation correctness
- Verify MIME and size checks are robust and not bypassable.
- Confirm upload handling does not allow path traversal or unsafe filenames.

4. State machine correctness
- Verify transition map in `repository.py` matches required lifecycle.
- Confirm invalid transitions return deterministic error contract.

5. Reliability and maintainability
- Confirm seams for future migration:
  - DB: SQLite -> Postgres/SQL Server
  - Task runner: in-process -> Celery/Redis
- Identify code paths that should move from endpoint layer to services.

6. Security and operational risks
- Check for any secrets leakage in responses/logs.
- Check cleanup behavior for partially uploaded files on validation failure.

## Known Gaps (Expected At This Stage)
- Async processing orchestration (`T2.2`) not implemented.
- OpenAI/Google generation adapters (`T2.2a`, `T2.2b`) not implemented.
- PDD/SIPOC generation pipelines (`T3.x`) not implemented.
- Frontend workflows (`T4.x`) mostly scaffold only.
- Tests (`T6.x`) not implemented yet.

## Quick Validation Commands
From `backend/`:
```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:
```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/providers/health
curl -sS -X POST http://127.0.0.1:8000/api/jobs -F provider=google -F transcript_file=@/tmp/pfcd_transcript.txt
curl -sS -X POST http://127.0.0.1:8000/api/jobs -F provider=google
```

## Review Output Requested From Gemini
Please provide:
1. Severity-ordered findings (`critical`, `high`, `medium`, `low`)
2. File and line references for each finding
3. Proposed fix direction per finding
4. Go/No-Go recommendation for moving to `T2.2`

## Acceptance For This Review Stage
Approve progression to `T2.2` only if:
- Upload validation behavior is correct and deterministic.
- DB persistence shape is stable and contract-safe.
- No critical security issues in upload/path handling.
- State transitions are enforced as intended for current endpoints.

