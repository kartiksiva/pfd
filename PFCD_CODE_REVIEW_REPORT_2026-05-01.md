# PFCD Full-Codebase Code Review — 2026-05-01

Scope: backend (`backend/app/`), frontend (`frontend/app/`), infra (`infra/`).
Method: prior `PFCD_CODE_REVIEW_REPORT.md` (2026-04-23) findings re-verified at HEAD `b16f911` + new pass.
Subagent dispatch unavailable (org monthly limit) — review done inline.

Confidence rubric (0-100): 0 false positive · 25 unverified · 50 verified-but-minor · 75 high-impact · 100 certain. Items below are scored ≥80.

---

## CRITICAL

### C1. `DELETE /api/jobs/{job_id}` is a silent no-op — NEW (95)
- File: `backend/app/main.py:637-639`
- Endpoint returns `{"deleted": true}` without touching DB, uploads, or exports. Clients believe job deleted; nothing happens. Job continues to occupy storage and remain visible until retention sweep.
```python
@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, _=Depends(require_authenticated_access)) -> ApiEnvelope:
    return ApiEnvelope(success=True, data={"job_id": job_id, "deleted": True}, error=None)
```
- Not in `openapi.yaml`/`schemas.md` audit trail. Either remove the route or implement repo deletion + filesystem cleanup. CLAUDE.md: "Status transitions only via `repository.update_job_status`" — a delete must also go through repo.

### C2. Default secrets / access codes still in repo — STILL PRESENT (95)
- File: `backend/app/config.py:50-53`
```python
owner_access_code: str = Field(default="PFCD-OWNER-7429", ...)
guest_access_code: str = Field(default="PFCD-GUEST-3184", ...)
access_session_secret: str = Field(default="change-this-demo-secret", ...)
```
- HMAC cookie (`auth.py:38-40`) signed with `access_session_secret`. Default known publicly via repo → cookie forgery trivial when `AUTH_ENABLED=true` and operator forgot override.
- Fix: drop defaults or `model_validator(mode='after')` raising when `auth_enabled` and any value still default.

### C3. `repository.commit()` no rollback — STILL PRESENT (90)
- File: `backend/app/repository.py:77, 105, 147`
- Three commits, none wrapped. SQLAlchemy 2.x deactivates the session after a failed commit. Worker holds **one** `SessionLocal()` for the entire pipeline (`worker.py:66, 328`) → first failed commit corrupts every subsequent `update_job_metadata` / `update_job_status` silently.
- Fix:
```python
try:
    db.commit()
except Exception:
    db.rollback()
    raise
```

### C4. `_set_failure` and `process_job_async` silently return when job missing — STILL PRESENT (85)
- File: `backend/app/worker.py:27-28, 70-71`
- No logger. Job vanishing mid-pipeline → no diagnostic record. Worsened by C5 (no structured logging anywhere).

---

## MAJOR

### M1. Duplicated provider-fallback logic — STILL PRESENT (85)
- Files: `backend/app/worker.py:17-22` and `backend/app/repository.py:39-44`
- Two independent copies of the same map (`google ↔ openai`, others → `google`). Repository version handles `ollama` explicitly; worker version drops it into the default branch. Functionally same today, but adding a real Ollama fallback (e.g. `ollama → google` only when GOOGLE_API_KEY set) will require touching two sites.
- Fix: single function in `providers/factory.py`.

### M2. Frontend `apiFetch` has no timeout / abort — STILL PRESENT (85)
- File: `frontend/app/api.ts:11-16`
- Bare `fetch` wrapper. Job-status polling on a stalled backend hangs indefinitely. `AccessGate.tsx:30-31` rolls its own 8s `AbortController`; that pattern is not shared.
- Fix: add `AbortController` + default 30s timeout in `apiFetch`.

### M3. `AccessGate` is client-only — STILL PRESENT (mitigated) (80)
- File: `frontend/app/AccessGate.tsx:1`
- `"use client"` gate. JS-disabled / DevTools bypass possible. Backend `require_authenticated_access` (`main.py:117-120`) is the actual line of defence — **but** `AUTH_ENABLED=false` returns synthetic owner role unconditionally. So bypass risk lives entirely in deploy-config: any prod deploy that ships with `AUTH_ENABLED=false` is wide open.
- Fix: move check to Next.js `middleware.ts`; for backend, fail-closed if `AUTH_ENABLED` unset rather than defaulting `False` (`config.py:57`).

### M4. No rate limiting on `POST /api/jobs` — STILL PRESENT (80)
- File: `backend/app/main.py:233-289`
- Job creation triggers expensive multimodal pipeline. Authenticated guest can spam jobs and exhaust budget within minutes. Cost guardrail trips per-job, not aggregate.
- Fix: `slowapi` middleware on jobs endpoints; or daily-cap counter in repo.

### M5. Retention sweep wipes artifacts even if status transition fails — REAL (80)
- File: `backend/app/retention.py:29-37`
```python
update_job_metadata(db, job, artifacts={"md": None, ...}, progress={"stage": "expired", ...})
ok, _ = update_job_status(db, job, JobStatus.expired.value)
if ok:
    expired += 1
```
- Order is wipe-then-transition. If the transition fails (e.g. status already `expired` from another sweep, since `ALLOWED_TRANSITIONS[expired]=set()`), the row is left with empty artifacts and `progress.stage='expired'` but its prior status — observable as a stuck partial-expire.
- `list_expired_jobs` does filter `status != expired`, so today the failure path is unreachable. Future status-machine changes will resurface this. Move the artifact wipe **after** the status transition succeeds.

### M6. `_set_failure` calls `update_job_status` then `update_job_metadata` — REAL but minor (80)
- File: `backend/app/worker.py:30-38`
- Same problem as M5 in reverse: status flips to `failed` first, error_code/message stamped second. Brief window where a `GET /api/jobs/{id}` returns `failed` with no `error_code`. Frontend reads `error_code` from `progress.stage`/top-level — UI may render "Failed (no reason)" then refresh into the real reason. Order-swap: stamp metadata first, transition last.

---

## MEDIUM

### Med1. `print()` in retention loop, no structured logging — STILL PRESENT (75)
- `backend/app/retention.py:51`. Prior report flagged "no structured logging" across backend; still 0 modules use `logging.getLogger(__name__)`.

### Med2. Path traversal hardening still missing at `generate_exports` boundary — STILL PRESENT (70)
- Mitigated in practice by DB lookup. Boundary still trusts caller. Add `UUID(job_id)` parse at function entry.

### Med3. `auth_enabled` defaults to `False` — REAL (75)
- `backend/app/config.py:57`
- Combined with M3: a prod deployment that forgets to set `AUTH_ENABLED=true` silently runs open. Default should be `True`, or startup must assert env explicitly set when `ENV != "development"`.

### Med4. Cost guardrail evaluated only after primary/fallback adapter `run()` — REAL (70)
- `backend/app/worker.py:128`
- By the time we know cost exceeds the band, both providers have already been billed. Guardrail catches future jobs (after operator tuning) but not the current one. Acceptable for MVP — flag for production.

---

## LOWER (≥80 confidence not met — listed for completeness, not for immediate action)

- Long-lived `db` session across pipeline (worker.py:66/328) — pairs with C3.
- Magic confidence-penalty constants 0.10 / 0.30 (worker.py:59, 61).
- `frontend/app/HomePageClient.tsx` — `any` typing on job state (per prior report).

---

## Verified-fixed since 2026-04-23 review

- `/health` endpoint exists (`main.py:142`).
- `datetime.utcnow()` fully replaced with `datetime.now(timezone.utc)` (grep confirms 0 hits in `backend/app/`).
- Retention thread `_thread_started` flag guarded by `threading.Lock()` (`retention.py:13, 57`).
- `LLM_ENABLED=false` set in `tests/conftest.py:8`.
- No `.env*` or `pfcd*.db` files tracked by git (verified `git ls-files`).
- `openapi.yaml` and `schemas.md` enums updated per `b16f911`.

---

## Recommended priority

| Item | Why now |
|------|---------|
| C1 (DELETE no-op) | Silent data-integrity bug; trivial to fix or remove route. |
| C2 (default secrets) | Pre-deploy blocker — single `model_validator` solves it. |
| C3 (commit rollback) | Worker reuses session; one transient DB hiccup poisons whole pipeline. |
| C4 (silent missing-job return) | Operability black hole; needs `logging` module wired. |
| Med3 (`auth_enabled` default False) | Pairs with M3; flip default + startup assertion. |
