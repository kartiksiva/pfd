# AGENTS.md

## Purpose
This file defines the agent operating model for the Process Documentation Agent MVP described in `PRD.md`.

## Implementation Status Note
- Product constraint remains internal demo no-auth mode.
- Runtime now also supports optional access-code auth for hosted demos, controlled by:
  - backend `AUTH_ENABLED`
  - frontend `NEXT_PUBLIC_AUTH_ENABLED`

The system accepts `video`, `audio`, and/or `transcript` inputs, then generates:
- Process Definition Document (PDD)
- SIPOC map

Outputs are reviewed in-app and exported as `Markdown`, `JSON`, `PDF`, and `DOCX`.

## Product Constraints (Must Follow)
- MVP mode is internal demo with no authentication.
- Accept at least one input file per job.
- Max upload size is 500 MB per file.
- Provider must be selectable per job: `openai`, `google`, or `ollama`.
- Language support is English only.
- SIPOC output is a single consolidated map.
- Processing is asynchronous with job status tracking.
- Retention TTL is 7 days for uploads and artifacts.
- Per-job duration/token caps must be enforced.
- Target AI processing cost band is `$2-$8` per source media hour.

## Agent Topology
Use a multi-agent pipeline orchestrated by a Job Orchestrator.

1. `ui-agent`
- Owns upload, status view, review/edit, finalize, and export UX.
- Shows statuses: `queued`, `processing`, `needs_review`, `completed`, `failed`, `expired`.
- Enforces client-side file validation before submission.

2. `ingestion-agent`
- Validates server-side input presence, size, and MIME/type.
- Stores input metadata in `input_manifest`.
- Normalizes transcript text payloads for downstream parsing.

3. `media-understanding-agent`
- For video: extracts audio and relevant visual context.
- For audio: transcribes and timestamps key content.
- Produces normalized evidence chunks and confidence markers.

4. `process-extraction-agent`
- Converts evidence into structured process steps.
- Extracts actors, systems, handoffs, business rules, exceptions, outputs, and metrics when available.
- Merges signals from multi-input submissions.

5. `document-agent`
- Generates fixed-template PDD draft using required sections:
  - `purpose`, `scope`, `triggers`, `preconditions`, `steps`, `roles`,
    `systems`, `business_rules`, `exceptions`, `outputs`, `metrics`, `risks`
- Generates a single SIPOC row set:
  - `supplier`, `input`, `process_step`, `output`, `customer`

6. `quality-agent`
- Runs schema and completeness checks on PDD and SIPOC.
- Flags low-confidence or missing critical sections.
- Routes job to `needs_review` with review notes when checks are not strong enough.

7. `export-agent`
- Builds finalized artifacts: `.md`, `.json`, `.pdf`, `.docx`.
- Exports only from finalized or accepted draft state.

8. `retention-agent`
- Deletes files and generated artifacts older than 7 days.
- Marks job status as `expired`.

9. `provider-routing-agent`
- Resolves selected provider at job start.
- Maps provider-specific model plan for transcription, multimodal analysis, and structured generation.
- Applies provider fallback strategy for transcription before hard failure.

## Data Contracts
Minimum internal contracts for handoffs:

1. `JobRecord`
- `id`
- `status`
- `provider` (`openai|google|ollama`)
- `model_plan`
- `input_manifest`
- `limits_applied`
- `usage_cost_estimate`
- `artifacts`
- `error_code` (nullable)
- `created_at`
- `expires_at`

2. `PDDDocument`
- Required keys: `purpose`, `scope`, `triggers`, `preconditions`, `steps`,
  `roles`, `systems`, `business_rules`, `exceptions`, `outputs`, `metrics`, `risks`

3. `SIPOCRow`
- `supplier`
- `input`
- `process_step`
- `output`
- `customer`

## API Ownership Mapping
1. `POST /api/jobs`
- Owners: `ui-agent` + `ingestion-agent`
- Result: create job in `queued` status after validation, with selected provider.

2. `GET /api/jobs/{job_id}`
- Owners: `ui-agent` + `orchestrator`
- Result: live status, selected provider, and error visibility.

3. `GET /api/jobs/{job_id}/draft`
- Owners: `document-agent`
- Result: draft PDD + SIPOC for review.

4. `PUT /api/jobs/{job_id}/draft`
- Owners: `ui-agent` + `document-agent`
- Result: persist human edits.

5. `POST /api/jobs/{job_id}/finalize`
- Owners: `quality-agent` + `export-agent`
- Result: lock reviewed content and generate artifacts.

6. `GET /api/jobs/{job_id}/exports/{format}`
- Owner: `export-agent`
- Result: return `md|json|pdf|docx`.

7. `DELETE /api/jobs/{job_id}`
- Owners: `retention-agent` + API layer
- Result: manual cleanup for demo operations.

## Orchestration Flow
1. Upload submission accepted -> status `queued`.
2. Ingestion validation passes -> status `processing`.
3. Provider-routing resolves model plan.
4. Media understanding + extraction complete.
5. PDD + SIPOC draft generated.
6. Quality checks run:
- if pass threshold: status `needs_review` with clean draft.
- if weak confidence: status `needs_review` with flagged notes.
7. User edits and saves draft.
8. Finalize endpoint locks draft and triggers export generation.
9. Status becomes `completed` when artifacts are ready.
10. Scheduled retention task marks and purges expired jobs -> `expired`.

## Error Handling Rules
- Reject missing all-input submissions with explicit validation error.
- Reject unsupported MIME/type and size >500 MB with explicit reason.
- On AI/provider timeout or cap breach:
  - attempt configured transcription fallback path first
  - if fallback fails, continue failure handling below
  - set `failed`
  - preserve diagnostic `error_code`
  - return actionable message to UI
- Keep partial internals hidden from end-user; expose stable error contract only.

## Quality Gates
- PDD must include all required sections.
- SIPOC must include at least one valid row.
- JSON exports must validate against output schema.
- PDF export must originate from finalized content only.
- Provider, model plan, and cost estimate must be present in completed job metadata.
- Acceptance scenarios in `PRD.md` section 10 are required release gates.

## Provider Benchmark Policy
- Keep all provider paths operational in MVP.
- Run periodic benchmark set across providers and compare:
  - PDD completeness
  - SIPOC correctness and coverage
  - latency to draft
  - cost per media hour

## Prompt and Generation Guardrails
- Use deterministic template-first generation for PDD.
- Do not invent unsupported systems or role names without evidence.
- When evidence is weak, include explicit "Assumption/Needs Review" markers.
- Prefer concise, operational language over narrative prose.

## Delivery Sequence
1. Backend skeleton: job model, status model, ingestion validation, queue wiring.
2. Media and extraction pipeline with normalized intermediate schema.
3. PDD/SIPOC generation and quality checks.
4. Review/edit and finalize flow in UI.
5. Export stack for Markdown/JSON/PDF.
6. Retention scheduler and cleanup jobs.
7. End-to-end acceptance tests for transcript-only, audio-only, and video+transcript.


<claude-mem-context>
# Memory Context

# [PFCD] recent context, 2026-05-07 9:22am GMT+5:30

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 14 obs (5,911t read) | 627,563t work | 99% savings

### May 1, 2026
434 12:40p 🔵 PFCD-V2 Code Review Session Kickoff — Project Structure and Git State Mapped
436 12:41p 🔵 PFCD-V2 Full Backend Architecture — Deep Code Review Mapping Complete
437 " 🔵 PFCD-V2 Structured Extraction + Process Pipeline — LLM Prompt Schema and Normalization Logic Mapped
438 " 🔵 PFCD-V2 Security Issues Found in Code Review — Stubs, Secrets, and Hardcoded Logic
439 " 🔵 PFCD-V2 Frontend Architecture — Next.js 15 Single-Page App with Job Polling and Review Modal
444 12:43p 🔵 PFCD-V2 Test Suite — 6 Integration Tests Fail Locally Due to Hardcoded /app/uploads Path
445 " 🔵 PFCD-V2 .env File Contains Live API Keys Committed to Repo
446 " 🔵 PFCD-V2 Ollama Adapter — Transcription is Placeholder, Media Not Actually Processed
447 " 🔵 PFCD-V2 Quality Checks Pipeline — Score Calculation and Operational Fact Validation Logic Mapped
### May 7, 2026
501 9:21a 🔵 PFCD Git State — code-review-remediation Branch with Unstaged Changes
502 " 🔵 PFCD Git Index Write Permission Denied — Blocking All Staging Operations
504 " ✅ PFCD Git — Stash/Switch Workaround Succeeded, Files Restored onto Main
506 9:22a ✅ PFCD Main Branch — Agent Guidance and Review Artifacts Committed
508 " 🔵 PFCD Sandbox — No Network Access to GitHub, Push Blocked

Access 628k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>