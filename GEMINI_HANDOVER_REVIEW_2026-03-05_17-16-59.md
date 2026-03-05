# Gemini Re-Review Handover

## Purpose
This document is for re-review after fixing findings from:
- `GEMINI_REVIEW_2026-03-05_17-45-00.md`

## Fixed Findings (from Gemini NO-GO report)

### 1) Contract mismatch for `JobRecord` fields
Status: Fixed

Changes:
- Added DB fields in `backend/app/models.py`:
  - `model_plan` (JSON)
  - `limits_applied` (JSON)
  - `usage_cost_estimate` (JSON)
  - `context_notes` (TEXT)
- Initialized defaults in `backend/app/repository.py:create_job`.
- Added fields to `GET /api/jobs/{id}` response in `backend/app/main.py`.
- Added SQLite compatibility migration for new columns in `backend/app/database.py:ensure_schema_compat`.

### 2) Unsafe filename handling (path traversal risk)
Status: Fixed

Changes:
- Sanitized uploaded filenames via `Path(raw_name).name` in `backend/app/upload_validation.py` (`_safe_filename`).
- Persisted sanitized names only.

### 3) No cleanup on partial upload failure
Status: Fixed

Changes:
- Wrapped upload flow in `try/except` and added recursive cleanup:
  - `shutil.rmtree(job_dir, ignore_errors=True)` on `ValidationError`.
- Ensured file handles close even on failure via `finally` in `_save_file`.

### 4) Inconsistent API envelope behavior
Status: Fixed

Changes:
- Added unified response helpers in `backend/app/main.py`:
  - `_success_response(...)`
  - `_error_response(...)`
- Added global FastAPI validation exception handler returning envelope format:
  - `ERR_VALIDATION` with `422`.
- Standardized key error responses for `POST /api/jobs`, `GET /api/jobs/{id}`, and `POST /api/jobs/{id}/finalize`.

### 5) Unbounded `context_notes`
Status: Fixed

Changes:
- Enforced max length at API layer:
  - `context_notes: Form(..., max_length=2000)` in `POST /api/jobs`.
- Updated contract docs:
  - `openapi.yaml` (`maxLength: 2000`)
  - `schemas.md` mention added.

## Additional Contract Alignment
- `POST /api/jobs/{id}/finalize` now returns `202` with:
  - `status`
  - `next_stage`
- Added `422` response for `POST /api/jobs` in `openapi.yaml`.

## Verification Evidence (live checks)
1. `POST /api/jobs` with transcript:
- returns `202` envelope with `job_id`.
2. `GET /api/jobs/{id}`:
- returns `model_plan`, `limits_applied`, `usage_cost_estimate`.
3. Path traversal attempt (`filename=../../escape.txt`):
- stored filename sanitized as `escape.txt` inside job upload directory.
4. Partial failure rollback:
- upload dir count unchanged before/after failed mixed upload.
5. Overlong `context_notes` (>2000):
- returns envelope error `ERR_VALIDATION` with 422.
6. Missing job:
- returns `404` with envelope error `ERR_JOB_NOT_FOUND`.

## Files Changed For This Re-Review
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/repository.py`
- `backend/app/upload_validation.py`
- `backend/app/database.py`
- `backend/app/config.py`
- `backend/.env.example`
- `openapi.yaml`
- `schemas.md`

## Re-Review Request
Please validate:
1. No remaining critical/high issues for T1.2 + T2.1.
2. Contract compatibility against `openapi.yaml` JobRecord requirements.
3. Upload safety and atomic cleanup behavior.
4. Approval or blockers for proceeding to T2.2.
