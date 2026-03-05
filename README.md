# Process Documentation Agent (MVP)

Initial scaffold for:
- `frontend/` Next.js UI
- `backend/` FastAPI service
- `infra/` local Docker compose

## Defaults Chosen
- Default provider: `google`
- Default processing profile: `balanced`
- Database: SQLite (adapter-ready for Postgres/SQL Server)
- Background jobs: in-process (adapter-ready for Celery/Redis)

## Quick Start (Local)
1. Create env files:
   - `cp frontend/.env.example frontend/.env.local`
   - `cp backend/.env.example backend/.env`
2. Fill values in `frontend/.env.local` and `backend/.env`.
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
