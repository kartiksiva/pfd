# Contributing

## Scope
This repository contains the PFCD MVP agent:
- `backend/`: FastAPI API, job orchestration, LLM extraction, export generation
- `frontend/`: Next.js UI for submit/review/finalize/export
- `infra/`: Docker Compose for local runtime

## Local Setup
1. Copy env templates:
- `cp backend/.env.example backend/.env`
- `cp frontend/.env.example frontend/.env.local`
2. Add API keys to `backend/.env` (`GOOGLE_API_KEY`, optional `OPENAI_API_KEY`).
3. Start services:
- `docker compose -f infra/docker-compose.yml up --build`

## Development Rules
- Keep secrets out of git. Never commit `.env` files or API keys.
- Preserve API envelope contract (`success`, `data`, `error`) across endpoints.
- For extraction/generation changes, keep deterministic fallback path in place.
- Validate all user edits to draft payload against schema before saving.
- Keep docs and tests updated with behavior changes.

## Testing
Backend tests:
- `cd backend && .venv/bin/pytest -q`

Smoke checks:
- `GET /health`
- `GET /api/providers/health`
- Create job -> wait `needs_review` -> finalize -> download `md/json/pdf/docx`

## Pull Request Expectations
Each PR should include:
- What changed
- Why it changed
- How it was tested
- Any env/config changes required
- Screenshots for UI changes

## Commit Guidance
- Use focused commits with clear messages.
- Avoid mixing refactors with functional changes unless required.
- Keep generated/runtime artifacts out of commits.
