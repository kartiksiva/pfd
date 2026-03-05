# Gemini Handover: Milestone 4 + Milestone 5 (Core Slice)

## Context
This handover follows GO from:
- `GEMINI_REVIEW_2026-03-05_19-10-00.md`

Implemented focus:
- Milestone 4: practical frontend UX path (submit, status polling, draft review/save, finalize, export links)
- Milestone 5: export generation + finalize hardening (Markdown/JSON/PDF)

## What Was Implemented

### 1) Export generation and finalize hardening (T5.1 core)
Added:
- `backend/app/export_service.py`

Implemented:
- Markdown export generation from persisted draft PDD/SIPOC
- JSON export generation (`{ pdd, sipoc }`)
- PDF export generation from markdown text (ReportLab)
- Artifact persistence under `EXPORTS_DIR/<job_id>/report.{md,json,pdf}`

Finalize flow update (`POST /api/jobs/{id}/finalize`):
- validates draft availability
- transitions `needs_review -> processing`
- generates export artifacts
- persists `artifacts` and progress stage
- transitions `processing -> completed`
- returns completed status payload

Export endpoint update (`GET /api/jobs/{id}/exports/{format}`):
- returns proper `FileResponse` for `md/json/pdf`
- enforces `completed` status before download
- handles invalid format and missing artifact cases with envelope errors

### 2) Draft validation hardening (review note addressed)
Updated `PUT /api/jobs/{id}/draft`:
- validates incoming `pdd` with `PDDDocumentModel`
- validates `sipoc` rows with `SIPOCRowModel`
- returns `ERR_INVALID_DRAFT_PAYLOAD` for malformed edits

### 3) Frontend UX implementation (Milestone 4 core)
Updated:
- `frontend/app/page.tsx`

Implemented end-to-end UI actions:
- submit job with provider/profile/context + file inputs
- status polling (`GET /api/jobs/{id}`)
- draft load (`GET /draft`) and JSON edit area
- save draft (`PUT /draft`)
- finalize action (`POST /finalize`)
- export links (`/exports/md|json|pdf`)

This enables functional Review/Edit UX aligned to guidance.

## Config and dependency updates
- `backend/app/config.py`
  - added `exports_dir`
- `backend/.env.example`
  - added `EXPORTS_DIR`
- `backend/requirements.txt`
  - added `reportlab`

## Files Changed
- `backend/app/main.py`
- `backend/app/repository.py`
- `backend/app/models.py`
- `backend/app/database.py`
- `backend/app/schemas.py`
- `backend/app/export_service.py` (new)
- `backend/app/config.py`
- `backend/.env.example`
- `backend/requirements.txt`
- `frontend/app/page.tsx`
- `frontend/tsconfig.json` (auto-updated by Next.js build)

## Live Verification Evidence
Backend end-to-end test passed:
1. `POST /api/jobs` -> job queued
2. worker reaches `needs_review`
3. `POST /api/jobs/{id}/finalize` -> returns `completed`
4. `GET /api/jobs/{id}` shows artifacts paths and completed state
5. `GET /exports/md`, `GET /exports/json`, `GET /exports/pdf` all return `200`
6. artifact sizes confirmed non-zero

Frontend verification:
- `npm run build` succeeded with type/lint checks.

## Notes
- This handover covers core Milestone 4/5 behavior, not full UI polish or retention scheduler yet.
- Retention automation (`T5.2`) remains pending.

## Re-Review Request for Gemini
Please validate:
1. finalize/export correctness and status semantics
2. draft validation sufficiency for current MVP phase
3. frontend review flow readiness for iterative product testing
4. approval to proceed with retention scheduler (`T5.2`) and cost/runtime controls hardening (`T5.3/T5.4`)
