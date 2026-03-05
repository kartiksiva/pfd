# Release Checklist

## 1. Branch and Version Readiness
- [ ] PR merged to `main`
- [ ] Release notes drafted (features, fixes, known issues)
- [ ] Required docs updated (`README.md`, `PRD.md`, `TASKS.md` as applicable)

## 2. Configuration and Secrets
- [ ] `backend/.env.example` and `frontend/.env.example` reflect current required settings
- [ ] Production secrets configured (not in repo)
- [ ] `LLM_ENABLED` set appropriately for target environment
- [ ] `DEFAULT_PROVIDER` and `DEFAULT_PROCESSING_PROFILE` verified

## 3. Backend Validation
- [ ] Tests pass: `cd backend && .venv/bin/pytest -q`
- [ ] Health endpoint passes: `/health`
- [ ] Provider health endpoint passes: `/api/providers/health`
- [ ] End-to-end flow validated:
  - [ ] Create job
  - [ ] Reach `needs_review`
  - [ ] Save draft
  - [ ] Finalize
  - [ ] Download `md`, `json`, `pdf`, `docx`

## 4. Frontend Validation
- [ ] Build succeeds (`next build`)
- [ ] Submit/review/finalize/export flows work in browser
- [ ] Error states render cleanly (network/API failures)
- [ ] Finalize button only enabled in `needs_review`

## 5. Export Quality Gate
- [ ] Markdown output follows `STANDARD_PDD_TEMPLATE.md`
- [ ] Word export uses native formatting (real headings/lists/tables)
- [ ] SIPOC present and readable in markdown/pdf/docx
- [ ] No leaked transcript noise in final PDD sections (timestamps/speaker tags minimized)

## 6. Data and Retention
- [ ] Retention settings validated (`RETENTION_DAYS`, sweep schedule)
- [ ] Upload/export storage paths writable and monitored
- [ ] No sensitive sample outputs accidentally committed

## 7. Deployment and Post-Deploy
- [ ] Containers rebuilt with latest dependencies
- [ ] Deployment succeeded and services are healthy
- [ ] Smoke test run in deployed environment
- [ ] Rollback plan confirmed
