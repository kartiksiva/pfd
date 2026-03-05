# Gemini Handover: Post-Review Hardening (T5.2 + T5.3/T5.4 Slice)

## Context
This handover follows guidance from:
- `GEMINI_REVIEW_2026-03-05_19-25-00.md`

Targeted progression implemented:
- `T5.2 Retention Scheduler`
- `T5.3/T5.4 Guardrails & fallback robustness`

## What Was Implemented

### 1) Retention scheduler and sweep endpoint (`T5.2`)
Added:
- `backend/app/retention.py`

Implemented:
- periodic retention loop (daemon thread) started at app startup
- one-shot sweep function: `run_retention_sweep_once()`
  - finds expired jobs (`expires_at <= now` and not yet expired)
  - removes upload/export directories per job
  - updates artifacts/progress
  - transitions status to `expired`
- operational endpoint:
  - `POST /api/system/retention/sweep`

Config additions:
- `RETENTION_SWEEP_SECONDS` in `config.py` and `.env.example`

### 2) Worker guardrails (`T5.3/T5.4`)
Updated:
- `backend/app/worker.py`

Implemented:
- duration guardrail with `max_job_duration_seconds`
  - failure code: `ERR_JOB_TIMEOUT`
- cost-band guardrail with `cost_target_band_usd_per_media_hour.max`
  - failure code: `ERR_PROVIDER_CAP_EXCEEDED`
- fallback diagnostics hardening:
  - explicit `provider_fallback` progress stage
  - fallback failure code: `ERR_FALLBACK_TRANSCRIPTION_FAILED`

### 3) Export/finalize resilience retained
- finalize/export flow still operational and validated after hardening changes

### 4) Contract docs updated
Updated:
- `openapi.yaml`
  - added `POST /api/system/retention/sweep`
  - added `RetentionSweepResponse` schema
- `schemas.md`
  - added retention sweep response sample
  - added new error code coverage

## Files Changed
- `backend/app/retention.py` (new)
- `backend/app/worker.py`
- `backend/app/main.py`
- `backend/app/repository.py`
- `backend/app/config.py`
- `backend/.env.example`
- `openapi.yaml`
- `schemas.md`

## Live Verification Evidence
Smoke checks executed:
1. `POST /api/system/retention/sweep` -> `200` with `{scanned, expired}`
2. create job -> worker execution -> finalize -> completed
3. export endpoint still serves markdown successfully (`200`)

## Notes
- Retention loop runs in-process (MVP-appropriate) and can be migrated to scheduler/queue later.
- Guardrail paths are now explicit in worker failure semantics.

## Re-Review Request for Gemini
Please validate:
1. retention sweep behavior and status/cleanup semantics
2. guardrail enforcement approach (timeout/cost/fallback failure paths)
3. readiness to begin Milestone 6 test suite implementation
