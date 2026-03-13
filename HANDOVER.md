# HANDOVER

## Project
Process Documentation Agent (PFCD)

Repository: https://github.com/kartiksiva/pfd.git

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

## Known Limitations
- Native audio/video transcription is still scaffolded in adapters for some flows.
- Best quality currently achieved with transcript input present.
- Ollama health may fail if local daemon/model is not running.

## Active Issue: `custom_sop` Export Spacing
- Feature status:
  - `document_template=custom_sop` is implemented.
  - Markdown rendering uses root template: `Custom_SOP_Template.md`.
  - `custom_sop` finalization validates against SOP contract.
- Current user-facing issue:
  - Exported `docx/pdf` for `custom_sop` still shows excessive vertical spacing around the top header/meta block (e.g., between title/process name/function/sub-function/date).
  - This persists even after removing explicit blank-line paragraph inserts in markdown->DOCX conversion.
- Relevant code paths:
  - Template rendering: `backend/app/pdd_template.py` (`render_custom_sop_markdown`)
  - Export orchestration: `backend/app/export_service.py` (`generate_exports`)
  - Markdown->DOCX converter: `backend/app/export_service.py` (`_render_docx_from_markdown`)
  - PDF is generated from DOCX (`_render_pdf_from_docx`), so DOCX layout propagates to PDF.
- Changes already made:
  - Added `custom_sop` template option across API/UI and generation paths.
  - Added `custom_sop` markdown renderer with placeholder hardening and section population.
  - Routed `custom_sop` exports through markdown->DOCX path.
  - Suppressed explicit empty paragraph creation on blank lines and `---` in markdown->DOCX conversion.
  - Added/updated tests; backend test suite in scope currently passes.
- Likely root cause for next fix:
  - DOCX paragraph style defaults (space-before/space-after/line spacing) for generated paragraphs are still too large.
  - Potential heading/list style inheritance from `python-docx` defaults for markdown-converted blocks.
- Recommended next action:
  - In `_render_docx_from_markdown`, set paragraph formatting explicitly for generated paragraphs/headings/lists:
    - `space_before = 0`
    - `space_after = 0` (or small controlled values)
    - controlled `line_spacing`
  - Re-export a fresh `custom_sop` job and verify both `.docx` and `.pdf`.

## Important Files
- API entry: `backend/app/main.py`
- Worker: `backend/app/worker.py`
- Providers: `backend/app/providers/`
- Structured extraction: `backend/app/providers/structured_extraction.py`
- Export service: `backend/app/export_service.py`
- Templates: `backend/app/templates/STANDARD_PDD_TEMPLATE.md`, `backend/app/templates/Custom_SOP_Template.md`
- Docs: `PRD.md`, `AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_CHECKLIST.md`
