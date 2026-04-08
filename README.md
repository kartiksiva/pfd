# Process Documentation Agent (MVP)

Initial scaffold for:
- `frontend/` Next.js UI
- `backend/` FastAPI service
- `infra/` local Docker compose

## Defaults Chosen
- Default provider: `google`
- Available providers: `google`, `openai`, `ollama`
- Default processing profile: `balanced`
- Database: SQLite (adapter-ready for Postgres/SQL Server)
- Background jobs: in-process (adapter-ready for Celery/Redis)

## Quick Start (Local)
1. Create env files:
   - `cp frontend/.env.example frontend/.env.local`
   - `cp backend/.env.example backend/.env`
2. Fill values in `frontend/.env.local` and `backend/.env`.
   - For internal demo mode (no login prompt), keep `AUTH_ENABLED=false` in `backend/.env` and `NEXT_PUBLIC_AUTH_ENABLED=false` in `frontend/.env.local`.
   - If frontend and backend run on different domains with auth enabled, set `ACCESS_COOKIE_SECURE=true` and `ACCESS_COOKIE_SAMESITE=none` in `backend/.env`.
3. Run backend:
   - `cd backend && python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
4. Run frontend:
   - `cd frontend && npm install`
   - `npm run dev`

## Quick Start (Docker)
- `docker compose -f infra/docker-compose.yml up --build`

### Persistent Storage (Docker)
- Uploads persist at `data/uploads`
- Exports persist at `data/exports`
- These are mounted to backend paths:
  - `/app/uploads`
  - `/app/exports`

## Current Status
- Health endpoint: `GET /health`
- API scaffold for jobs/drafts/finalize/export routes
- Typed config, provider defaults, and response envelopes

## Tests
- Backend tests:
  - `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q`

## Deploy to Azure Web App (Docker)
- Deployment guide: `infra/azure/README.md`
- One-command script: `./infra/azure/deploy_webapp.sh`
- Deploys two Linux Web Apps (frontend + backend) with images built in ACR.

## Replication Documentation
- Full replication runbook: `PROJECT_REPLICATION_GUIDE.md`
