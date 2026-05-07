# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Process Documentation Agent (PFCD). Internal MVP that ingests `video`, `audio`, and/or `transcript` evidence and generates a Process Definition Document (PDD) or SOP plus a SIPOC map. Reviewed in-app, exported as `md`, `json`, `pdf`, `docx`.

Stack: FastAPI backend (`backend/app`) + Next.js 15 / React 19 frontend (`frontend/app`) + Docker. Cloud target is Azure Web Apps (two containers) with Azure SQL via `mssql+pyodbc`.

## Common Commands

Backend (Python 3.12, venv expected at `backend/.venv`):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend tests (use the venv pytest so `conftest.py` env shims load):

```bash
cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
# single test:
.venv/bin/pytest -q tests/test_api_integration_flow.py::test_demo_flow
```

Frontend:

```bash
cd frontend
npm install
npm run dev      # next dev
npm run build && npm run start
npm run lint
```

Full stack via Docker:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Azure deploy (one-shot, builds in ACR, updates two Web Apps):

```bash
./infra/azure/deploy_webapp.sh   # see infra/azure/README.md for required env vars
```

## Architecture

### Job pipeline

`POST /api/jobs` (or `/api/jobs/demo`) creates a `JobRecord`, persists uploads, then schedules `worker.process_job_async` via FastAPI `BackgroundTasks`. The worker is a single function that drives the full pipeline and writes intermediate state via `repository.update_job_metadata` so `GET /api/jobs/{id}` reflects live progress.

Pipeline stages (in `backend/app/worker.py`, calling into `backend/app/pipelines/*`):

1. `provider_routing` — `providers/factory.get_provider_adapter` returns one of `OpenAIAdapter`, `AzureOpenAIAdapter`, `GoogleAdapter`, `OllamaAdapter`. Each adapter implements `ProviderAdapter.run` (see `providers/base.py`) which produces an `AdapterResult { model_plan, usage_cost_estimate, evidence }`.
2. Provider failure → automatic fallback to a sibling provider (`google ↔ openai`, see `_fallback_provider`). If both fail: `ERR_FALLBACK_TRANSCRIPTION_FAILED`.
3. `transcript_media_consistency` — penalises confidence when uploaded transcript doesn't match uploaded media (`inconclusive` -0.10, `suspected_mismatch` -0.30).
4. `media_understanding` → `process_extraction` → `document_generation` (PDD or SOP based on `document_template`) → `quality_checks` produces `review_notes` with `flags` and `assumptions`.
5. Job lands in `needs_review`. User edits via `PUT /api/jobs/{id}/draft` (validated against `PDDDocumentModel` / `SOPDocumentModel` / `SIPOCRowModel` in `schemas.py`).
6. `POST /api/jobs/{id}/finalize` re-validates, runs `export_service.generate_exports` to produce all four artifacts, sets `expires_at = now + RETENTION_DAYS`, transitions to `completed`.
7. `retention.start_retention_scheduler` runs every `RETENTION_SWEEP_SECONDS` and marks expired jobs.

Job state machine (`schemas.JobStatus`): `queued → processing → needs_review → completed`, plus terminal `failed` / `expired`. Finalize is only valid from `needs_review`; a second call from `completed` returns the idempotent success response.

Cost guardrail: if `usage_cost_estimate.estimated_per_media_hour` exceeds `cost_target_band_usd_per_media_hour.max` from `limits_applied`, worker fails with `ERR_PROVIDER_CAP_EXCEEDED`. Duration guardrail uses `MAX_JOB_DURATION_SECONDS`.

### API contract

Every response uses the envelope `{ success, data, error }` (`schemas.ApiEnvelope`). `_success_response` and `_error_response` in `main.py` are the only sanctioned producers. Error objects include a stable `code` (e.g. `ERR_VALIDATION`, `ERR_JOB_NOT_FOUND`, `ERR_INVALID_STATUS_TRANSITION`, `ERR_NOT_FINALIZED`, `ERR_EXPORT_GENERATION_FAILED`). `openapi.yaml` and `schemas.md` are the canonical specs — keep them in sync when changing endpoints.

### Frontend ↔ backend wiring

Browser always calls same-origin `/api/*`. `frontend/next.config.mjs` rewrites `/api/:path*` → `${INTERNAL_API_URL}/:path*` (defaults to `http://localhost:8000/api` in dev). `frontend/app/api.ts` `apiFetch` always sends `credentials: "include"` so the access-code cookie flows.

### Auth

Two modes, controlled by `AUTH_ENABLED` (backend) and `NEXT_PUBLIC_AUTH_ENABLED` (frontend). When disabled, `require_authenticated_access` returns a synthetic `owner` session and all endpoints are open. When enabled, `auth.validate_access_code` matches against `OWNER_ACCESS_CODE` / `GUEST_ACCESS_CODE` and issues an HMAC-signed cookie (`ACCESS_COOKIE_NAME`) bound by `ACCESS_SESSION_SECRET`.

**Critical:** `NEXT_PUBLIC_AUTH_ENABLED` is baked at Next.js build time. Changing the App Service setting alone leaves the UI gate stuck at the old value — you must rebuild and redeploy the frontend image. See `infra/azure/AUTH_REFERENCE.md`.

For split frontend/backend domains with auth on, set `ACCESS_COOKIE_SECURE=true` and `ACCESS_COOKIE_SAMESITE=none`, and add the frontend origin to `ALLOWED_ORIGINS`.

### Database

`backend/app/database.py` builds the SQLAlchemy engine from `DATABASE_URL`. SQLite is the default and dev baseline; Azure SQL via `mssql+pyodbc` (driver `ODBC Driver 18 for SQL Server`) is the cloud baseline.

`ensure_schema_compat()` is a SQLite-only ALTER-TABLE shim that backfills new columns added during MVP iteration. **It is a no-op on SQL Server.** When pointing at Azure SQL, use a fresh dedicated database — reusing an older shared DB will fail at startup or during retention sweeps with missing-column errors. There are no Alembic-style migrations yet.

### Providers

Each provider adapter owns transcription, evidence building, model plan, and cost estimation. `should_use_full_media` returns `True` only when `processing_profile == "quality"` — otherwise the adapter operates in frame-only mode and prefers any uploaded transcript over re-transcribing media. Tests cover this in `tests/test_provider_transcription_adapters.py` and `tests/test_azure_media_transcription_modes.py`.

`provider_health.check_providers_health` powers `GET /api/providers/health` and is the right entry point when adding a new provider.

## Coding Guidelines (Karpathy Principles)

Apply these on every task:

1. **Think before coding** — state assumptions explicitly; if multiple interpretations exist, surface them rather than picking silently; ask when unclear.
2. **Simplicity first** — minimum code that solves the problem; no speculative features, abstractions for single use, or error handling for impossible scenarios.
3. **Surgical changes** — touch only what the task requires; don't improve adjacent code; match existing style; remove only imports/variables made unused by *your* changes.
4. **Goal-driven execution** — define verifiable success criteria before acting; for multi-step tasks, state a brief plan with a per-step verification check.

## Conventions

- Preserve the `{ success, data, error }` envelope on every endpoint — clients depend on it.
- Validate any draft mutation against `PDDDocumentModel` / `SOPDocumentModel` / `SIPOCRowModel` before persisting.
- Keep the deterministic fallback path in extraction/generation working — provider outages must still produce a draft (with `flags`).
- Status transitions only via `repository.update_job_status` (it enforces the legal transitions).
- Tests must keep `LLM_ENABLED=false` (set in `tests/conftest.py`) — never call real providers from pytest.
- Don't commit `.env*`, real provider keys, or the local SQLite DB files (`pfcd.db`, `backend/pfcd*.db`).

## Key reference docs

- `PROJECT_REPLICATION_GUIDE.md` — full operational runbook (env vars, Azure deploy, validation checklist, troubleshooting).
- `infra/azure/README.md` — Azure deployment script details and required app settings.
- `infra/azure/AUTH_REFERENCE.md` — auth toggle commands for the live Azure apps.
- `AGENTS.md` — multi-agent topology and ownership map per endpoint.
- `PRD.md` — product requirements and acceptance scenarios.
- `openapi.yaml` + `schemas.md` — canonical API and data contracts.
