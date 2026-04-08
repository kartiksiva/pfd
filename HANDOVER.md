# HANDOVER

## Project
Process Documentation Agent (PFCD)

Repository: https://github.com/kartiksiva/pfd.git

## Azure Deployment Snapshot (April 2026)
- Frontend URL: `https://pfcd-frontend-karthick-20260408.azurewebsites.net`
- Backend URL: `https://pfcd-backend-karthick-20260408.azurewebsites.net`
- Resource Group: `app-pfcd-v2`
- App Service Plan: `pfcd-dev-asp` (Linux)
- ACR: `acrpfcdkarthick20260408`
- Frontend image: `acrpfcdkarthick20260408.azurecr.io/pfcd-frontend:v3`
- Backend image: `acrpfcdkarthick20260408.azurecr.io/pfcd-backend:v1`

### Azure-Specific Current State
- Frontend lock screen issue fixed in `frontend/app/AccessGate.tsx`.
- Owner session stability fixed: owner is not force-logged-out on transient API errors.
- Backend startup fixed by using writable runtime paths:
  - `DATABASE_URL=sqlite:////tmp/pfcd.db`
  - `UPLOADS_DIR=/tmp/uploads`
  - `EXPORTS_DIR=/tmp/exports`
- Important limitation: `/tmp` storage is ephemeral across restarts/redeploys.
- Full migration notes/runbook: `azure.md` and `infra/azure/README.md`.

## Current Scope
- Inputs: transcript, audio, video (any one required)
- Providers: `google`, `openai`, `ollama`
- Processing: async background job pipeline
- Outputs: `md`, `json`, `docx`, `pdf`
- PDF generation source: **DOCX** (not markdown)

## Architecture (High Level)
- `frontend/` (Next.js): upload, status polling, draft review/edit, finalize, export links
- `backend/` (FastAPI): jobs API, provider adapters, extraction pipeline, exports, retention
- `infra/docker-compose.yml`: local runtime (backend + frontend)
- `data/`: persisted uploads/exports (docker mount)

## Core Backend Flow
1. `POST /api/jobs` creates job (`queued`) and stores files
2. Worker sets `processing`
3. Provider adapter builds evidence
4. LLM structured extraction attempted (provider-specific)
5. Fallback deterministic extraction if LLM fails
6. Draft PDD + SIPOC generated and quality checks applied
7. Job moves to `needs_review`
8. `POST /api/jobs/{id}/finalize` generates artifacts
9. Job moves to `completed`

## Provider Notes
- `google`: Gemini-backed extraction path
- `openai`: OpenAI-backed extraction path
- `ollama`: local Ollama `/api/generate` extraction path
- Health endpoint: `GET /api/providers/health`

## Environment Keys
Backend (`backend/.env`):
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default `qwen3-vl:8b`)
- `LLM_ENABLED=true`
- `DEFAULT_PROVIDER=google`

Frontend (`frontend/.env.local`):
- `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`
- `NEXT_PUBLIC_DEFAULT_PROVIDER=google`

## Runbook
- Start/rebuild:
  - `docker compose -f infra/docker-compose.yml up -d --build`
- Backend health:
  - `curl http://127.0.0.1:8000/health`
- Providers health:
  - `curl http://127.0.0.1:8000/api/providers/health`
- Frontend:
  - `http://127.0.0.1:3000`

## Test Checklist (Gemini Video Upload)
1. Open UI and set provider to `google`
2. Upload a real video file (optionally with transcript for benchmark)
3. Submit job and monitor status transitions:
   - `queued -> processing -> needs_review`
4. Verify draft quality:
   - meaningful process name
   - business rules captured
   - exceptions captured
   - SIPOC rows present
5. Finalize job
6. Download all exports (`md`, `json`, `docx`, `pdf`)
7. Validate DOCX formatting:
   - native headings/lists/tables
   - no markdown markers
8. Validate PDF reflects DOCX structure

## Recent Successes (March 2026)
- **Azure OpenAI Integration:** Fixed URL pathing, headers (`api-key`), and API versioning.
- **Template Consolidation:** Moved all `.md` templates to `backend/app/templates/` for Docker-safe pathing.
- **`custom_sop` Hardening:** 
  - UI now renders the full document using robust fallback strings.
  - Export spacing fixed via explicit "Compact Meta" paragraph styling in `export_service.py`.
- **Docker Alignment:** Fixed `docker-compose.yml` volume mounts to match the new template directory.

## Known Limitations
- Native audio/video transcription is still scaffolded in adapters for some flows.
- Best quality currently achieved with transcript input present.
- Ollama health may fail if local daemon/model is not running.

## Important Files
- API entry: `backend/app/main.py`
- Worker: `backend/app/worker.py`
- Providers: `backend/app/providers/`
- Structured extraction: `backend/app/providers/structured_extraction.py`
- Export service: `backend/app/export_service.py`
- Templates: `backend/app/templates/STANDARD_PDD_TEMPLATE.md`, `backend/app/templates/Custom_SOP_Template.md`
- Docs: `PRD.md`, `AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_CHECKLIST.md`
