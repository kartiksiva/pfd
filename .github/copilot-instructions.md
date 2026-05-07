# Copilot Instructions — Process Documentation Agent (PFCD)

## Project Overview

Internal MVP that ingests `video`, `audio`, and/or `transcript` files and produces a Process Definition Document (PDD) or SOP plus a SIPOC map. Review happens in-app; exports are `md`, `json`, `pdf`, `docx`.

**Stack:** FastAPI (Python 3.12) backend + Next.js 15 / React 19 frontend, containerized via Docker Compose.

---

## Build, Test, and Lint Commands

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run all tests (always use the venv pytest — `conftest.py` sets env shims before imports):

```bash
cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
```

Run a single test:

```bash
cd backend && .venv/bin/pytest -q tests/test_api_integration_flow.py::test_demo_flow
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # dev server
npm run build && npm run start
npm run lint
```

### Full stack

```bash
docker compose -f infra/docker-compose.yml up --build
```

---

## Architecture

### Job pipeline (async, driven by `backend/app/worker.py`)

`POST /api/jobs` creates a `JobRecord` in `queued` state and schedules `process_job_async` via FastAPI `BackgroundTasks`. The worker drives each stage synchronously and writes progress via `repository.update_job_metadata`.

Pipeline stages in order:

1. **Provider routing** — `providers/factory.get_provider_adapter` returns one of `OpenAIAdapter`, `AzureOpenAIAdapter`, `GoogleAdapter`, `OllamaAdapter`. Each implements `ProviderAdapter.run` → `AdapterResult { model_plan, usage_cost_estimate, evidence }`.
2. **Automatic fallback** — if the primary provider raises, `_fallback_provider()` maps `google ↔ openai/azure_openai` and retries once. Both failing → `ERR_FALLBACK_TRANSCRIPTION_FAILED`.
3. **Transcript–media consistency check** (`pipelines/transcript_media_consistency.py`) — penalises `evidence.confidence` (`inconclusive`: −0.10, `suspected_mismatch`: −0.30).
4. **Media understanding** → **Process extraction** → **Document generation** (PDD/SOP based on `document_template`) → **Quality checks** → `review_notes { flags, assumptions }`.
5. Job transitions to `needs_review`. User edits via `PUT /api/jobs/{id}/draft`.
6. `POST /api/jobs/{id}/finalize` re-validates, generates artifacts, sets `expires_at`, transitions to `completed`.
7. `retention.start_retention_scheduler` sweeps expired jobs on a configurable interval.

### State machine (`schemas.JobStatus`)

```
queued → processing → needs_review → completed
                  ↘ failed / expired (any stage)
```

Legal transitions are defined in `repository.ALLOWED_TRANSITIONS`. **All status changes must go through `repository.update_job_status`**; it enforces the transition table and refuses invalid moves.

### Provider adapters (`backend/app/providers/`)

All extend `ProviderAdapter` in `providers/base.py`. Key behaviour: `should_use_full_media()` returns `True` only when `processing_profile == "quality"`; otherwise the adapter prefers any uploaded transcript over re-transcribing media.

### API response contract

Every response uses the envelope `{ success, data, error }` (`schemas.ApiEnvelope`). **Use only `_success_response` and `_error_response` in `main.py`** to produce responses — never return raw dicts. Error objects always include a stable `code` string (e.g. `ERR_VALIDATION`, `ERR_JOB_NOT_FOUND`, `ERR_INVALID_STATUS_TRANSITION`).

### Frontend ↔ backend wiring

The browser calls same-origin `/api/*`. `next.config.mjs` rewrites `/api/:path*` → `${INTERNAL_API_URL}/:path*` (defaults to `http://localhost:8000/api` in dev). `frontend/app/api.ts` `apiFetch` always sends `credentials: "include"` for cookie auth.

### Auth

Controlled by `AUTH_ENABLED` (backend env) and `NEXT_PUBLIC_AUTH_ENABLED` (frontend build-time env). When `AUTH_ENABLED=false`, `require_authenticated_access` returns a synthetic `owner` session and all endpoints are open. When `true`, an HMAC-signed cookie is used. **`NEXT_PUBLIC_AUTH_ENABLED` is baked at Next.js build time**; toggling it requires a frontend image rebuild.

### Database

Default (dev): SQLite (`sqlite:///./pfcd.db`). Cloud: Azure SQL via `mssql+pyodbc`. `ensure_schema_compat()` is a **SQLite-only** ALTER TABLE shim; it is a no-op on SQL Server. There are no Alembic migrations — on Azure SQL, always use a fresh dedicated database.

---

## Coding Guidelines (Karpathy Principles)

Apply these on every task:

1. **Think before coding** — state assumptions explicitly; if multiple interpretations exist, surface them rather than picking silently; ask when unclear.
2. **Simplicity first** — minimum code that solves the problem; no speculative features, abstractions for single use, or error handling for impossible scenarios.
3. **Surgical changes** — touch only what the task requires; don't improve adjacent code; match existing style; remove only imports/variables made unused by *your* changes.
4. **Goal-driven execution** — define verifiable success criteria before acting; for multi-step tasks, state a brief plan with a per-step verification check.

---

## Key Conventions

- **Tests must never call real providers.** `conftest.py` sets `LLM_ENABLED=false`. Do not remove or override this.
- **Document template validation.** Any draft mutation (via `PUT /api/jobs/{id}/draft`) must be validated against `PDDDocumentModel`, `SOPDocumentModel`, or `SIPOCRowModel` (all in `schemas.py`) before persisting.
- **PDD required sections** (enforced by `pipelines/quality_checks.py` and `PDDDocumentModel`): `purpose`, `scope`, `triggers`, `preconditions`, `steps`, `roles`, `systems`, `business_rules`, `exceptions`, `outputs`, `metrics`, `risks`.
- **Export only from finalized content.** `export_service.generate_exports` is called only after `POST /api/jobs/{id}/finalize` succeeds (status `completed`).
- **`get_settings()` is an `lru_cache` singleton.** In tests, patch settings before the first import or use `importlib.reload`.
- **Deterministic fallback in extraction/generation must be preserved.** When LLM evidence is weak or absent, the pipeline must still produce a draft (with `flags` and `assumptions` in `review_notes`) rather than fail.
- **Never invent unsupported system/role names without evidence.** Use `"Assumption/Needs Review"` markers when evidence is weak.
- **Canonical API and data contract references:** `openapi.yaml` and `schemas.md`. Keep them in sync when changing endpoints or data shapes.
- **Do not commit** `.env*` files, provider API keys, or local SQLite DB files (`pfcd.db`, `pfcd_test.db`, `test_review.db`).
- **PDF artifacts are generated from DOCX**, not from markdown. `export_service.py` renders DOCX first, then converts to PDF via `reportlab`. Never change this generation order.
- **Structured extraction prompt** lives in `backend/app/providers/structured_extraction.py` (`SYSTEM_PROMPT`). Extraction policy: return valid JSON only, current-state process only, no invented roles/systems, confidence ≤ 0.55 for sparse evidence, ≤ 0.85 unless steps/roles/systems are all explicitly named.
- **Export DOCX quality gates** (from `RELEASE_CHECKLIST.md`): use native Word headings/lists/tables (no markdown markers in output), SIPOC must be present and readable, no leaked transcript noise (timestamps/speaker tags) in final PDD sections.
- **Processing profiles** affect media handling: `quality` → full media transcription (higher cost); `balanced`/`low_cost` → frame-only, prefers uploaded transcript. Best quality is currently achieved when a transcript file is included alongside audio/video.

---

## Full API Surface

All endpoints (see `PROJECT_REPLICATION_GUIDE.md` §4 and `openapi.yaml`):

```
GET  /health
POST /api/auth/session
GET  /api/auth/session
DELETE /api/auth/session
GET  /api/providers/health          # optional ?timeout_seconds=10
POST /api/system/retention/sweep    # manual retention trigger
GET  /api/jobs
POST /api/jobs                      # multipart/form-data, returns 202
POST /api/jobs/demo                 # creates job from built-in demo inputs
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/draft
PUT  /api/jobs/{job_id}/draft
POST /api/jobs/{job_id}/finalize
GET  /api/jobs/{job_id}/exports/{format}   # format: md|json|pdf|docx
DELETE /api/jobs/{job_id}
```

### `POST /api/jobs` — input validation rules

- At least one of `video_file`, `audio_file`, `transcript_file` must be present; otherwise → `ERR_INVALID_INPUT`.
- Max 500 MB per file → `ERR_FILE_TOO_LARGE`.
- MIME/type must pass allowlist → `ERR_UNSUPPORTED_MIME`.
- `provider` is required: `openai | azure_openai | google | ollama`.
- `processing_profile` defaults to `balanced` (`quality | balanced | low_cost`).
- `context_notes` optional string (max 2000 chars).

---

## Schema Shapes

### PDDDocument step object

```json
{
  "step_no": 1,
  "title": "string",
  "actor": "string",
  "system": "string",
  "description": "string",
  "input": "string",
  "output": "string",
  "exception": "string"
}
```

### ReviewNotes

```json
{
  "quality_score": 0.82,
  "flags": [
    { "type": "low_confidence", "path": "pdd.steps[3].description", "message": "Weak evidence." }
  ],
  "assumptions": ["string"]
}
```

### LimitsApplied (stored in `job.limits_applied`)

```json
{
  "max_file_size_mb": 500,
  "max_job_duration_seconds": 7200,
  "max_provider_tokens": 1500000,
  "cost_target_band_usd_per_media_hour": { "min": 2, "max": 8 }
}
```

---

## Error Code Catalog

Full stable error codes (from `schemas.md`):

| Code | Trigger |
|---|---|
| `ERR_INVALID_INPUT` | Missing all input files |
| `ERR_VALIDATION` | Request schema validation failure |
| `ERR_FILE_TOO_LARGE` | File > 500 MB |
| `ERR_UNSUPPORTED_MIME` | MIME type not in allowlist |
| `ERR_JOB_NOT_FOUND` | Unknown job_id |
| `ERR_INVALID_STATUS_TRANSITION` | Illegal state change attempt |
| `ERR_PROVIDER_TIMEOUT` | Provider API timed out |
| `ERR_PROVIDER_RATE_LIMIT` | Provider rate limit hit |
| `ERR_PROVIDER_CAP_EXCEEDED` | Cost estimate exceeds `cost_band_max_usd` |
| `ERR_TRANSCRIPTION_FAILED` | Transcription step failed |
| `ERR_FALLBACK_TRANSCRIPTION_FAILED` | Both primary and fallback provider failed |
| `ERR_JOB_TIMEOUT` | Job exceeded `MAX_JOB_DURATION_SECONDS` |
| `ERR_EXPORT_GENERATION_FAILED` | Export artifact build failed |
| `ERR_INVALID_EXPORT_FORMAT` | Unknown format requested |
| `ERR_EXPORT_NOT_FOUND` | Export file missing on disk |
| `ERR_NOT_FINALIZED` | Export requested before finalize |
| `ERR_JOB_EXPIRED` | Job TTL elapsed |
| `ERR_AUTH_REQUIRED` | Unauthenticated request with `AUTH_ENABLED=true` |

---

## Environment Variables

All vars resolved via `backend/app/config.py` (Pydantic `BaseSettings`). See `backend/.env.example` and `frontend/.env.example` for templates.

### Backend (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./pfcd.db` | Use Azure SQL string for cloud |
| `UPLOADS_DIR` | `./uploads` | Use `/home/uploads` on Azure App Service |
| `EXPORTS_DIR` | `./exports` | Use `/home/exports` on Azure App Service |
| `LLM_ENABLED` | `true` | Set `false` in tests (enforced by `conftest.py`) |
| `DEFAULT_PROVIDER` | `google` | |
| `DEFAULT_PROCESSING_PROFILE` | `balanced` | |
| `GOOGLE_API_KEY` | — | Required for Google provider |
| `OPENAI_API_KEY` | — | Required for OpenAI provider |
| `AZURE_OPENAI_API_KEY` | — | Required for Azure OpenAI provider |
| `AZURE_OPENAI_ENDPOINT` | — | |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | — | |
| `AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT` | — | |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | |
| `OLLAMA_MODEL` | `qwen3-vl:8b` | |
| `RETENTION_DAYS` | `7` | |
| `RETENTION_SWEEP_SECONDS` | `300` | |
| `MAX_JOB_DURATION_SECONDS` | `7200` | |
| `MAX_PROVIDER_TOKENS` | `1500000` | |
| `COST_BAND_MIN_USD` | `2.0` | |
| `COST_BAND_MAX_USD` | `8.0` | |
| `AUTH_ENABLED` | `false` | |
| `ACCESS_SESSION_SECRET` | `change-this-demo-secret` | **Must override in any non-dev deployment** |
| `OWNER_ACCESS_CODE` | `PFCD-OWNER-7429` | **Must override in production** |
| `GUEST_ACCESS_CODE` | `PFCD-GUEST-3184` | **Must override in production** |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:3000,...` | Add frontend domain when split |
| `ACCESS_COOKIE_SECURE` | `false` | Set `true` for HTTPS / split-domain |
| `ACCESS_COOKIE_SAMESITE` | `lax` | Set `none` for split-domain with auth |

### Frontend (`frontend/.env.local`)

| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | Default `/api`; browser uses same-origin rewrite |
| `INTERNAL_API_URL` | Server-side rewrite target; default `http://localhost:8000/api` |
| `NEXT_PUBLIC_DEFAULT_PROVIDER` | Pre-selected provider in UI |
| `NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE` | Pre-selected profile in UI |
| `NEXT_PUBLIC_AUTH_ENABLED` | **Build-time baked** — rebuilding frontend image required when changed |

---

## Document Templates

Three `document_template` values are supported:

| Value | Schema | Template file |
|---|---|---|
| `pdd` | `PDDDocumentModel` | `backend/app/templates/STANDARD_PDD_TEMPLATE.md` |
| `sop` | `SOPDocumentModel` | `backend/app/templates/Custom_SOP_Template.md` |
| `custom_sop` | `SOPDocumentModel` | `backend/app/templates/Custom_SOP_Template.md` |

SOP required fields differ from PDD: `purpose`, `steps`, `document_control`, `quality_checks`, `exception_handling`, `controls_and_compliance`. Validation is done in `_validate_sop_complete()` in `main.py`.

All template `.md` files live in `backend/app/templates/` for Docker-safe path resolution.

---

## Azure Deployment

One-command deploy script: `./infra/azure/deploy_webapp.sh`. Full guide: `infra/azure/README.md`. Auth toggle runbook: `infra/azure/AUTH_REFERENCE.md`.

**Azure SQL connection string format:**

```
mssql+pyodbc://<user>:<password>@<server>.database.windows.net:1433/<db>?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
```

Set as `DATABASE_URL` in backend app settings. ODBC driver `msodbcsql18` is pre-installed in the backend `Dockerfile`.

**Critical Azure notes:**
- Use `/home/uploads` and `/home/exports` (persistent), not `/tmp` (ephemeral across restarts).
- SQLite on App Service containers has path/permissions issues — always use Azure SQL in cloud.
- Use a fresh dedicated SQL database per deployment; reusing an old shared DB missing columns causes startup failures.
- After `NEXT_PUBLIC_AUTH_ENABLED` change: rebuild frontend image, update container, restart app.

**Quick health checks:**

```bash
curl -sS -i https://<backend-domain>/health
curl -sS -i https://<frontend-domain>/api/auth/session
curl -sS -i -X POST https://<frontend-domain>/api/jobs/demo
```

---

## Important Files Reference

| File | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app, all endpoints, `_success_response`/`_error_response` |
| `backend/app/worker.py` | Async job pipeline driver |
| `backend/app/repository.py` | All DB operations; enforces status transitions via `ALLOWED_TRANSITIONS` |
| `backend/app/schemas.py` | All Pydantic models, enums, `ApiEnvelope` |
| `backend/app/config.py` | `Settings` (Pydantic BaseSettings), `get_settings()` singleton |
| `backend/app/providers/base.py` | `ProviderAdapter`, `AdapterResult`, `EvidencePayload` contracts |
| `backend/app/providers/factory.py` | Provider registry and runtime resolver |
| `backend/app/providers/structured_extraction.py` | LLM extraction prompt and retry logic |
| `backend/app/export_service.py` | Artifact generation (`md`, `json`, `docx`, `pdf`) |
| `backend/app/pipelines/quality_checks.py` | PDD/SIPOC completeness validation, review notes |
| `backend/app/database.py` | SQLAlchemy engine, `ensure_schema_compat()` (SQLite-only shim) |
| `backend/app/retention.py` | Scheduled TTL sweep |
| `backend/tests/conftest.py` | Test env setup (`LLM_ENABLED=false`, in-memory DB) |
| `frontend/app/api.ts` | `apiFetch` wrapper; always sends `credentials: "include"` |
| `frontend/next.config.mjs` | `/api/*` rewrite to backend |
| `openapi.yaml` | Canonical REST API spec |
| `schemas.md` | Canonical data contracts |
| `PRD.md` | Product requirements and acceptance criteria |
| `AGENTS.md` | Multi-agent topology and endpoint ownership map |
| `PROJECT_REPLICATION_GUIDE.md` | Full operational runbook (env vars, Azure deploy, troubleshooting) |

---

## PRD Acceptance Criteria (Release Gates)

All eight must pass before release (from `PRD.md` §10):

1. Transcript-only upload produces draft PDD + SIPOC and can be finalized/exported.
2. Audio-only upload produces draft and exports successfully.
3. Video + transcript upload processes asynchronously and reaches review stage.
4. Invalid file type or >500 MB file is rejected with clear error.
5. Finalized job exports all four formats (`md`, `json`, `pdf`, `docx`).
6. Job artifacts expire and are deleted after 7 days.
7. User can choose `openai`, `google`, or `ollama` per job and view provider in status.
8. Fallback transcription path is attempted before hard provider-stage failure.

---

## Known Limitations

- Native audio/video transcription is scaffolded in some adapter flows; best extraction quality is achieved when a transcript file is uploaded alongside media.
- Ollama health check fails if local daemon or model (`qwen3-vl:8b`) is not running.
- No Alembic migrations exist — schema evolution is SQLite-only via `ensure_schema_compat()`.
- No rate limiting on API endpoints — high-volume job creation can exhaust provider budgets.
