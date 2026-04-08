# PFCD Project Replication Guide (Baseline: Azure v1)

This document is the complete operational reference to rebuild this project and replicate the same pattern for a new project.

## 1. Scope and Baseline

- Product: Process Documentation Agent (PFCD MVP)
- Baseline commit: `abcfdf4` (`Baseline Azure v1: auth flow fixes, Azure SQL deployment, and ops docs`)
- Stack:
  - Frontend: Next.js
  - Backend: FastAPI + SQLAlchemy
  - Containers: Docker
  - Cloud target: Azure App Service (Linux Web App for Containers) + Azure Container Registry (ACR)
  - Database: Azure SQL (SQL Server) via `mssql+pyodbc`

## 2. Functional Overview

The app accepts process evidence (`video`, `audio`, `transcript`) and generates:
- PDD draft
- SIPOC draft

Workflow:
1. User creates a job (uploaded files or demo inputs).
2. Job moves through async stages (`queued`, `processing`, `needs_review`, `completed`, `failed`, `expired`).
3. User reviews/edits draft.
4. User finalizes and exports (`md`, `json`, `pdf`, `docx`).

## 3. Repository Structure

- `frontend/` Next.js UI
- `backend/` FastAPI API + orchestration
- `infra/docker-compose.yml` local container orchestration
- `infra/azure/deploy_webapp.sh` Azure build/deploy automation
- `infra/azure/README.md` Azure deployment notes
- `infra/azure/AUTH_REFERENCE.md` auth toggle runbook
- `AGENTS.md` architecture and internal contracts
- `PRD.md` product requirements

## 4. API Surface (Current)

- `GET /health`
- `POST /api/auth/session`
- `GET /api/auth/session`
- `DELETE /api/auth/session`
- `GET /api/providers/health`
- `POST /api/system/retention/sweep`
- `POST /api/jobs`
- `POST /api/jobs/demo`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/draft`
- `PUT /api/jobs/{job_id}/draft`
- `POST /api/jobs/{job_id}/finalize`
- `GET /api/jobs/{job_id}/exports/{format}`
- `DELETE /api/jobs/{job_id}`

## 5. Configuration Matrix

## 5.1 Backend environment variables

Defined in `backend/.env.example` and `backend/app/config.py`.

Core:
- `ENV`
- `DATABASE_URL`
- `UPLOADS_DIR`
- `EXPORTS_DIR`
- `ALLOWED_ORIGINS`

Auth:
- `AUTH_ENABLED`
- `ACCESS_SESSION_SECRET`
- `OWNER_ACCESS_CODE`
- `GUEST_ACCESS_CODE`
- `GUEST_ACCESS_TIMEOUT_MINUTES`
- `ACCESS_COOKIE_NAME`
- `ACCESS_COOKIE_SECURE`
- `ACCESS_COOKIE_SAMESITE` (`lax|strict|none`)

Providers:
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_CHAT_DEPLOYMENT`
- `AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

Limits:
- `RETENTION_DAYS`
- `RETENTION_SWEEP_SECONDS`
- `MAX_JOB_DURATION_SECONDS`
- `MAX_PROVIDER_TOKENS`
- `COST_BAND_MIN_USD`
- `COST_BAND_MAX_USD`

## 5.2 Frontend environment variables

Defined in `frontend/.env.example`.

- `NEXT_PUBLIC_API_URL`
- `INTERNAL_API_URL`
- `NEXT_PUBLIC_DEFAULT_PROVIDER`
- `NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE`
- `NEXT_PUBLIC_GUEST_ACCESS_TIMEOUT_MINUTES`
- `NEXT_PUBLIC_AUTH_ENABLED`

Important:
- `NEXT_PUBLIC_AUTH_ENABLED` is build-time in Next.js (must rebuild image when changed).

## 6. Local Development

## 6.1 Native run

1. Backend:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2. Frontend:
```bash
cd frontend
npm install
npm run dev
```

## 6.2 Docker compose

```bash
docker compose -f infra/docker-compose.yml up --build
```

Persistent local mounts:
- `infra/data/uploads` -> `/app/uploads`
- `infra/data/exports` -> `/app/exports`

## 7. Azure Deployment Architecture

Two Web Apps:
- Backend Web App container (FastAPI, port 8000)
- Frontend Web App container (Next.js, port 3000)

ACR hosts both images:
- `pfcd-backend:<tag>`
- `pfcd-frontend:<tag>`

Frontend to backend API path:
- Browser calls `/api/*` on frontend domain
- Next.js rewrite forwards to `INTERNAL_API_URL`

## 8. One-Command Azure Deployment

Script:
- `infra/azure/deploy_webapp.sh`

Required env vars:
- `RESOURCE_GROUP`
- `LOCATION`
- `APP_SERVICE_PLAN`
- `ACR_NAME`
- `BACKEND_APP_NAME`
- `FRONTEND_APP_NAME`

Common optional vars:
- `TAG`
- `BACKEND_PUBLIC_URL`
- `FRONTEND_PUBLIC_URL`
- `NEXT_PUBLIC_API_URL` (default `/api`)
- `NEXT_PUBLIC_AUTH_ENABLED` (default `false`)
- `DATABASE_URL` (default `sqlite:////home/pfcd.db`)

Run:
```bash
./infra/azure/deploy_webapp.sh
```

## 9. Azure SQL Setup (Recommended Baseline)

Use Azure SQL instead of SQLite for stable cloud persistence.

## 9.1 Backend container support

Already included in baseline:
- `pyodbc` in `backend/requirements.txt`
- ODBC driver install in `backend/Dockerfile` (`msodbcsql18`)

## 9.2 Connection string format

Use:
```text
mssql+pyodbc://<user>:<password>@<server>.database.windows.net:1433/<db>?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
```

Set in backend app settings as `DATABASE_URL`.

## 9.3 Schema note (critical)

`ensure_schema_compat()` currently applies only to SQLite. For SQL Server:
- Prefer a fresh dedicated DB for this app
- Or implement/execute proper migrations before switching to an existing DB

If you point to an old shared DB missing columns, startup/retention queries can fail with SQL errors (example: missing `expires_at`).

## 10. Auth Modes and Switching

Reference file: `infra/azure/AUTH_REFERENCE.md`

## 10.1 Demo mode (no auth)

- Backend: `AUTH_ENABLED=false`
- Frontend: `NEXT_PUBLIC_AUTH_ENABLED=false`
- Rebuild frontend if changing this value

## 10.2 Access-code mode (auth on)

Backend settings:
- `AUTH_ENABLED=true`
- `ACCESS_SESSION_SECRET=<strong-random-secret>`
- `OWNER_ACCESS_CODE=<owner-code>`
- `GUEST_ACCESS_CODE=<guest-code>`
- `GUEST_ACCESS_TIMEOUT_MINUTES=30`
- `ACCESS_COOKIE_SECURE=true`
- `ACCESS_COOKIE_SAMESITE=none` (required for split frontend/backend domains)
- `ALLOWED_ORIGINS` includes frontend domain and local dev origins

Frontend settings:
- `NEXT_PUBLIC_AUTH_ENABLED=true`
- `NEXT_PUBLIC_API_URL=/api`

Then restart both apps.

Important:
- UI gate behavior depends on build-time `NEXT_PUBLIC_AUTH_ENABLED`. If backend auth is true but frontend was built with false, app opens directly and later API calls fail with `ERR_AUTH_REQUIRED`.

## 11. Validation Checklist (Post Deploy)

## 11.1 Infra health

- Backend health:
```bash
curl -sS -i https://<backend-domain>/health
```
Expect `200`.

- Frontend reachability:
```bash
curl -sS -i https://<frontend-domain>/
```

## 11.2 Auth behavior

Unauthenticated:
```bash
curl -sS -i https://<frontend-domain>/api/auth/session
```
- Auth enabled: expect `401 ERR_AUTH_REQUIRED`
- Auth disabled: expect `200` authenticated payload

## 11.3 Demo endpoint

```bash
curl -sS -i -X POST https://<frontend-domain>/api/jobs/demo
```
Expect `202` + `job_id`.

## 12. Troubleshooting Runbook

## 12.1 App started but API times out/hangs

- Check Web App logs:
```bash
az webapp log download --resource-group <rg> --name <app> --log-file /tmp/<app>.zip
```
- Inspect `LogFiles/*docker.log` for startup errors.

## 12.2 Backend startup fails with SQLite open error

Symptom:
- `sqlite3.OperationalError: unable to open database file`

Actions:
1. Prefer switching to Azure SQL (`DATABASE_URL` mssql).
2. If staying on SQLite, use a writable absolute path and ensure directory exists.

## 12.3 Auth appears off but backend says auth required

Root cause:
- Frontend built with `NEXT_PUBLIC_AUTH_ENABLED=false`

Fix:
1. Rebuild frontend image with build arg `NEXT_PUBLIC_AUTH_ENABLED=true`
2. Update frontend container image
3. Restart frontend
4. Hard refresh/incognito

## 12.4 Intermittent App Service startup issues

Possible causes:
- VNET transient startup failures
- Delayed warmup probe

Action:
- Restart app and wait 2-5 minutes before judging health.

## 12.5 Existing session masks auth gate

If auth is on but page bypasses gate:
- Use incognito
- Clear site cookies
- Optional logout call:
```bash
curl -X DELETE https://<frontend-domain>/api/auth/session
```

## 13. Security and Secrets

- Never commit real keys/passwords.
- Keep provider secrets in Azure App Settings or Key Vault references.
- Rotate secrets if they were exposed during troubleshooting.
- Use strong `ACCESS_SESSION_SECRET` in production-like environments.

## 14. Replicate for a New Project (Template Procedure)

1. Copy this repo baseline commit and rename app/repo.
2. Create new Azure resources (or new names in existing RG):
- New backend app name
- New frontend app name
- New ACR repositories/tags
- New dedicated SQL database
3. Update deployment env vars for new names.
4. Deploy via `infra/azure/deploy_webapp.sh`.
5. Apply backend secrets and DB connection.
6. Decide auth mode and rebuild frontend accordingly.
7. Run validation checklist in section 11.
8. Save final working settings in a project-specific runbook.

## 15. Recommended Next Hardening

- Add database migrations for SQL Server/Postgres (instead of SQLite-only compat helper).
- Externalize uploads/exports to durable object storage.
- Add CI pipeline for image build + deploy + smoke tests.
- Add explicit startup diagnostics endpoint and readiness checks.

## 16. Related Docs

- `README.md`
- `PRD.md`
- `AGENTS.md`
- `infra/azure/README.md`
- `infra/azure/AUTH_REFERENCE.md`
