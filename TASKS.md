# TASKS.md

## Goal
Implement the Process Documentation Agent MVP from `PRD.md` using the operating model in `AGENTS.md`.

## Milestone 1: Foundation and Job Lifecycle

### T1.1 Repo bootstrap
- Initialize monorepo/workspace layout:
  - `frontend/` (Next.js)
  - `backend/` (FastAPI)
  - `infra/` (Docker + local orchestration)
- Add base README with local run steps.
- Add `.env.example` files for frontend/backend.
- Add shared formatting/lint configs.
- Acceptance:
  - Both apps start locally.
  - Health endpoint responds.

### T1.2 Core job model and status state machine
- Implement backend models:
  - `JobRecord`
  - `InputManifest`
  - `ArtifactManifest`
- Implement valid status transitions:
  - `queued -> processing -> needs_review -> completed`
  - `queued|processing -> failed`
  - `* -> expired` (retention flow)
- Acceptance:
  - Invalid state transitions are rejected.
  - Status lifecycle is queryable via API.

### T1.3 API skeleton (v1 endpoints)
- Implement endpoint stubs:
  - `POST /api/jobs`
  - `GET /api/jobs/{job_id}`
  - `GET /api/jobs/{job_id}/draft`
  - `PUT /api/jobs/{job_id}/draft`
  - `POST /api/jobs/{job_id}/finalize`
  - `GET /api/jobs/{job_id}/exports/{format}`
  - `DELETE /api/jobs/{job_id}`
- Acceptance:
  - OpenAPI docs show all routes.
  - Routes return stable contract envelopes.
  - Create job contract includes `provider` field (`openai|google`).

### T1.4 Provider abstraction contract
- Add provider interface for:
  - transcription
  - multimodal analysis
  - structured PDD/SIPOC generation
- Add provider registry and runtime resolver.
- Acceptance:
  - Orchestrator calls provider-agnostic interface only.

## Milestone 2: Ingestion and Processing Pipeline

### T2.1 Multipart ingestion validation
- Support optional `video`, `audio`, `transcript` uploads.
- Enforce at least one input present.
- Enforce max 500 MB per file.
- Enforce MIME/type allowlist.
- Persist upload metadata into `input_manifest`.
- Acceptance:
  - Missing all inputs returns validation error.
  - Oversize and invalid type are rejected with clear codes.

### T2.2 Async job execution framework
- Integrate background worker queue.
- Trigger pipeline from `POST /api/jobs`.
- Update progress stages within `processing`.
- Add retry policy for transient provider failures.
- Acceptance:
  - Create-job API returns quickly while work continues async.
  - Job status updates are visible via polling.
  - Job metadata persists provider and resolved model plan.

### T2.2a OpenAI provider adapter
- Implement OpenAI adapter for transcription + multimodal extraction + structured generation.
- Wire adapter to provider interface.
- Acceptance:
  - End-to-end processing works with `provider=openai`.

### T2.2b Google provider adapter
- Implement Google adapter for transcription + multimodal extraction + structured generation.
- Wire adapter to provider interface.
- Acceptance:
  - End-to-end processing works with `provider=google`.

### T2.3 Media understanding pipeline
- Video path: extract audio + visual context frames/segments.
- Audio path: transcription + chunking.
- Transcript path: normalization and segmentation.
- Emit normalized evidence schema for downstream extraction.
- Acceptance:
  - Transcript-only, audio-only, and video+transcript all produce normalized evidence.

### T2.4 Process extraction pipeline
- Extract candidate process steps, roles, systems, handoffs, rules, exceptions, outputs, metrics, risks.
- Merge evidence from multi-input jobs.
- Track confidence flags per section/row.
- Acceptance:
  - Structured extraction object produced for all supported input modes.

## Milestone 3: PDD and SIPOC Generation

### T3.1 Fixed-template PDD generator
- Generate required sections:
  - `purpose`, `scope`, `triggers`, `preconditions`, `steps`, `roles`,
    `systems`, `business_rules`, `exceptions`, `outputs`, `metrics`, `risks`
- Add deterministic section ordering.
- Acceptance:
  - Missing section keys are blocked by schema validation.

### T3.2 SIPOC generator
- Generate single consolidated SIPOC row set:
  - `supplier`, `input`, `process_step`, `output`, `customer`
- Add minimal row normalization and deduping.
- Acceptance:
  - At least one valid SIPOC row required for review readiness.

### T3.3 Quality gate checks
- Validate PDD completeness.
- Validate SIPOC row schema.
- Mark weak/uncertain outputs with review notes.
- Route to `needs_review` state.
- Acceptance:
  - Jobs enter `needs_review` with draft payload and quality notes.

## Milestone 4: Frontend UX

### T4.1 Upload and submission UI
- Build single flow upload screen with file pickers for video/audio/transcript.
- Client-side validation for required input rule and size/type checks.
- Submit to `POST /api/jobs`.
- Acceptance:
  - User can submit any one of three file types successfully.

### T4.2 Status tracking UI
- Job status page with polling.
- Show explicit statuses:
  - `queued`, `processing`, `needs_review`, `completed`, `failed`, `expired`
- Show clear error messages for failed jobs.
- Acceptance:
  - Long-running jobs show progress without page errors.

### T4.3 Review/edit UI
- Render editable PDD sections and SIPOC table.
- Save edits through `PUT /api/jobs/{job_id}/draft`.
- Finalize via `POST /api/jobs/{job_id}/finalize`.
- Acceptance:
  - User edits persist and survive refresh.

### T4.4 Export UI
- Download actions for `md`, `json`, `pdf`.
- Disable export until finalized/completed.
- Acceptance:
  - All three formats downloadable for completed jobs.

## Milestone 5: Export, Retention, and Controls

### T5.1 Export service implementation
- Generate Markdown artifact from finalized model.
- Generate JSON artifact from validated schema.
- Generate PDF artifact from finalized markdown/document render.
- Acceptance:
  - Export endpoints return valid files for completed jobs.

### T5.2 Retention scheduler
- Scheduled cleanup for artifacts/uploads older than 7 days.
- Mark job as `expired`.
- Acceptance:
  - TTL cleanup verified with forced-expiry test fixture.

### T5.3 Cost and runtime guardrails
- Enforce per-job duration cap.
- Enforce provider token/usage cap.
- Standardize failure codes on cap breach/timeouts.
- Acceptance:
  - Cap breaches fail gracefully with actionable error messages.
  - Report per-job cost estimate and keep run-cost in `$2-$8` per media hour target band.

### T5.4 Provider fallback behavior
- Implement fallback transcription path when primary provider transcription fails.
- Keep hard failure only after fallback exhaustion.
- Acceptance:
  - Fallback attempt is visible in job diagnostics and failure codes.

## Milestone 6: Testing and Release Readiness

### T6.1 Unit tests
- Validation rules (input presence, type, size).
- Status transition logic.
- PDD/SIPOC schema validators.
- Retention and cap logic.
- Acceptance:
  - Core units pass in CI.

### T6.2 Integration tests
- End-to-end for:
  - transcript-only
  - audio-only
  - video+transcript
- Include review edit + finalize + export path.
- Include invalid upload and cap breach failures.
- Acceptance:
  - PRD acceptance criteria are fully covered.
  - Each scenario passes once with `openai` and once with `google`.

### T6.2a Provider benchmark suite
- Build benchmark dataset (20-30 representative jobs).
- Add scoring script for:
  - PDD completeness
  - SIPOC coverage/correctness
  - latency to draft
  - cost per media hour
  - human edit effort
- Acceptance:
  - Default provider recommendation can be derived from measured results.

### T6.3 Local Docker demo packaging
- Dockerfiles for frontend/backend.
- Compose setup for local full-stack run.
- One-command startup script.
- Acceptance:
  - Internal demo can be launched from clean environment.

## Definition of Done (MVP)
- All PRD section 10 acceptance criteria pass.
- End-to-end flow works: upload -> process -> review/edit -> finalize -> export.
- 7-day retention and per-job caps enforced.
- No-auth internal demo warning visible in UI.
- Basic operational logs and error diagnostics available for debugging.

## Suggested Execution Order
1. Milestone 1
2. Milestone 2
3. Milestone 3
4. Milestone 4
5. Milestone 5
6. Milestone 6
