# Azure Deployment Notes (PFCD MVP)

This document captures everything done to move PFCD to Azure Web App for Containers, including code changes, Azure resource setup, troubleshooting, and the current operational runbook.

## 1. Target Azure Architecture

PFCD is deployed as two Linux Web Apps backed by Docker images in Azure Container Registry (ACR):

- Frontend Web App (Next.js)
  - App: `pfcd-frontend-karthick-20260408`
  - URL: `https://pfcd-frontend-karthick-20260408.azurewebsites.net`
  - Container image: `acrpfcdkarthick20260408.azurecr.io/pfcd-frontend:v3`

- Backend Web App (FastAPI)
  - App: `pfcd-backend-karthick-20260408`
  - URL: `https://pfcd-backend-karthick-20260408.azurewebsites.net`
  - Container image: `acrpfcdkarthick20260408.azurecr.io/pfcd-backend:v1`

- Azure resources used
  - Resource group: `app-pfcd-v2`
  - App Service plan (existing): `pfcd-dev-asp` (Linux, South India)
  - ACR: `acrpfcdkarthick20260408`

## 2. Repo Changes Made

### 2.1 Docker/runtime changes

1. `backend/Dockerfile`
- Changed startup command to honor Azure-provided `PORT`:
  - from fixed `--port 8000`
  - to `--port ${PORT:-8000}`
- Added worker count env support:
  - `--workers ${UVICORN_WORKERS:-2}`

2. `frontend/Dockerfile`
- Converted to multi-stage production build:
  - `deps` (npm ci)
  - `builder` (next build)
  - `runner` (next start)
- Added build args for API base:
  - `NEXT_PUBLIC_API_URL`
  - `INTERNAL_API_URL`
- Runtime starts with:
  - `npm run start -- --hostname 0.0.0.0 --port ${PORT:-3000}`

3. Docker ignore files
- Added root `.dockerignore`
- Added `frontend/.dockerignore`

### 2.2 Azure deployment automation/docs

4. Added deploy script:
- `infra/azure/deploy_webapp.sh`
- Creates/uses RG, ACR, plan, web apps
- Builds images in ACR
- Configures container + app settings
- Restarts apps

5. Added Azure runbook:
- `infra/azure/README.md`

6. Updated root `README.md`
- Added section linking Azure deploy script and guide.

### 2.3 Frontend gate UX fix

7. `frontend/app/AccessGate.tsx`
- Fixed blank lock-screen behavior when backend session check stalls.
- Added 8s timeout to session check.
- Shows explicit error (`Cannot reach API...`) instead of blank gradient page.
- Kept lock form visible consistently.
- Added owner-session stability fix:
  - guest sessions are polled for expiry
  - owner sessions are not force-logged-out on transient API/network failures
  - logout only on explicit auth failure (`401/403`)

## 3. Azure Provisioning + Deployment Sequence Executed

## 3.1 Initial deployment attempt

- Tried to deploy with new RG + new plan in `eastus`.
- Hit quota issue:
  - `Operation cannot be completed without additional quota`
  - Basic VMs quota was `0` in that region/subscription path.

### 3.2 Pivot to existing plan

- Reused existing Linux App Service plan:
  - `pfcd-dev-asp` in `app-pfcd-v2`

### 3.3 Registry issue encountered

- Initial ACR target (`acrpfcddemo20260408`) was not available in active subscription context.
- Created new ACR in active RG:
  - `acrpfcdkarthick20260408` in `app-pfcd-v2`

### 3.4 Image builds completed

- Built/pushed backend:
  - `acrpfcdkarthick20260408.azurecr.io/pfcd-backend:v1`
- Built/pushed frontend:
  - `acrpfcdkarthick20260408.azurecr.io/pfcd-frontend:v1`
- Later built/pushed frontend fix:
  - `acrpfcdkarthick20260408.azurecr.io/pfcd-frontend:v2`
- Later built/pushed owner-session fix:
  - `acrpfcdkarthick20260408.azurecr.io/pfcd-frontend:v3`

### 3.5 Web app container binding

- Backend bound to:
  - `DOCKER|acrpfcdkarthick20260408.azurecr.io/pfcd-backend:v1`
- Frontend bound to:
  - first `v1`, then updated to `v2`, then `v3`

## 4. Production Issues Encountered and Fixes

## 4.1 Frontend visible but blank/lock content missing

Symptom:
- Background loaded, but lock card/UI was not clearly visible (or appeared blank).

Fix:
- `AccessGate.tsx` updated (timeout + explicit error + non-blank rendering path).
- Redeployed frontend as `v2`.

## 4.2 Frontend lock card showed “Cannot reach API”

Symptom:
- Lock form displayed and reported backend unreachable.

Root cause:
- Backend container startup failed:
  - `sqlite3.OperationalError: unable to open database file`

Fix:
- Updated backend app settings to writable paths and restarted:
  - `DATABASE_URL=sqlite:////tmp/pfcd.db`
  - `UPLOADS_DIR=/tmp/uploads`
  - `EXPORTS_DIR=/tmp/exports`

Validation:
- `GET /api/auth/session` now responds (401 when unauthenticated), confirming backend API reachable.

## 4.3 Additional runtime hardening

- Frontend:
  - `alwaysOn=true`
  - `httpsOnly=true`
- Backend:
  - `ACCESS_COOKIE_SECURE=true`
  - `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true` (kept enabled, though backend currently uses `/tmp` paths)

## 4.4 Owner login re-prompting too often

Symptom:
- Owner code login appeared to expire in Azure more frequently than expected.

Root cause:
- Frontend gate polling logic treated transient API/network failures like auth expiry and forced logout.

Fix:
- Updated `frontend/app/AccessGate.tsx` and redeployed frontend `v3`.

Result:
- Owner sessions remain active unless backend explicitly returns auth failure.

## 5. Current Effective App Settings

## 5.1 Frontend app settings (`pfcd-frontend-karthick-20260408`)

- `WEBSITES_PORT=3000`
- `PORT=3000`
- `NEXT_PUBLIC_API_URL=https://pfcd-backend-karthick-20260408.azurewebsites.net/api`
- `INTERNAL_API_URL=https://pfcd-backend-karthick-20260408.azurewebsites.net/api`
- `alwaysOn=true`
- `httpsOnly=true`

## 5.2 Backend app settings (`pfcd-backend-karthick-20260408`)

- `WEBSITES_PORT=8000`
- `PORT=8000`
- `ALLOWED_ORIGINS=https://pfcd-frontend-karthick-20260408.azurewebsites.net,http://localhost:3000,http://127.0.0.1:3000`
- `DATABASE_URL=sqlite:////tmp/pfcd.db`
- `UPLOADS_DIR=/tmp/uploads`
- `EXPORTS_DIR=/tmp/exports`
- `ACCESS_COOKIE_SECURE=true`
- `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`

## 6. Remaining Manual Step: API Keys

Add provider keys on backend app (`pfcd-backend-karthick-20260408`) via Portal or CLI.

Minimum required (based on provider path you use):
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- Azure OpenAI path (if used):
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_CHAT_DEPLOYMENT`
  - `AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT`

After setting, restart backend app.

Note:
- Provider keys were added in Azure App Settings during migration validation.
- Rotate keys if any were exposed in terminal output/history during troubleshooting.

## 7. Redeploy Procedure (Current)

1. Build and push backend image to ACR.
2. Build and push frontend image to ACR with backend URL build args.
3. Update backend webapp container image + restart.
4. Update frontend webapp container image + restart.
5. Validate:
   - Backend: `/api/auth/session` returns `401` (without cookie)
   - Frontend loads lock screen and accepts access code.

You can use:
- `infra/azure/deploy_webapp.sh` (with env vars adjusted to this environment), or
- direct `az` commands as done during this migration.

## 8. Known Limitation (Important)

Backend currently uses `/tmp` for DB/uploads/exports to guarantee startup in App Service container sandbox.

Impact:
- Data is ephemeral across restarts/redeploys.

Recommended next step:
- Move backend persistence to durable storage:
  - Azure SQL / Postgres for DB
  - Azure Blob Storage for uploads/exports
  - or App Service mounted persistent storage path validated end-to-end.

## 9. Files Added/Changed for Azure Work

Changed:
- `README.md`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/app/AccessGate.tsx`

Added:
- `.dockerignore`
- `frontend/.dockerignore`
- `infra/azure/README.md`
- `infra/azure/deploy_webapp.sh`

## 10. Commit Checklist

Use this to commit only Azure migration changes:

```bash
git add \
  README.md \
  backend/Dockerfile \
  frontend/Dockerfile \
  frontend/app/AccessGate.tsx \
  .dockerignore \
  frontend/.dockerignore \
  infra/azure/README.md \
  infra/azure/deploy_webapp.sh \
  azure.md
```

Optional pre-check:

```bash
git status --short
git diff --name-only --cached
```

Suggested commit message:

```bash
git commit -m "Add Azure Web App container deployment setup and fix access-gate/API startup issues"
```
