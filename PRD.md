# Product Requirements Document (PRD)
## Product
Process Documentation Agent (MVP)

## Implementation Status Note
- The original MVP requirement is no-auth internal demo mode.
- Current implementation also supports optional access-code auth (`AUTH_ENABLED` in backend and `NEXT_PUBLIC_AUTH_ENABLED` in frontend) for controlled demos.

## 1. Objective
Build an internal demo web app that accepts process evidence (`video`, `audio`, and/or `transcript`) and generates:
1. Process Definition Document (PDD)
2. SIPOC map

Outputs must be reviewable/editable in-app and exportable as Markdown, JSON, PDF, and DOCX.

## 2. Users
- Internal business/process teams
- Process analysts
- Operations stakeholders validating current-state workflows

## 3. Scope (MVP)
### In Scope
- No-auth internal demo
- Upload any one or more:
  - Video file
  - Audio file
  - Transcript file
- Async processing with job status tracking
- Runtime model provider selection per job
- Supported providers in MVP: OpenAI, Azure OpenAI, Google, and Ollama
- English-only generation
- Fixed-template PDD
- Single consolidated SIPOC map
- In-app review/edit before finalization
- Export as `.md`, `.json`, `.pdf`, `.docx`
- Retention: auto-delete uploads/artifacts after 7 days
- Per-job processing/token caps
- Target AI run-cost band: `$2-$8` per source media hour

### Out of Scope
- SSO/auth roles
- Multi-language generation
- Multi-SIPOC decomposition by subprocess
- Advanced domain-specific templates
- Production-scale cloud architecture

## 4. Success Criteria
- User can submit at least one input type and receive a draft PDD + SIPOC.
- End-to-end completion for common jobs without manual backend intervention.
- User can edit draft and export final outputs.
- System clearly reports status/failures for long jobs.
- Expired jobs/artifacts are removed automatically at 7-day TTL.

## 5. Functional Requirements
### FR-1 Submission
- System shall accept multipart upload with optional `video`, `audio`, `transcript`.
- System shall reject if all three are missing.
- Max file size: 500 MB per file.
- System shall validate file MIME/type.

### FR-2 Processing Pipeline
- System shall run asynchronous job orchestration.
- System shall extract/process:
  - Video: audio + visual cues
  - Audio: transcription + step extraction
  - Transcript: structure extraction
- System shall merge signals when multiple inputs exist.
- System shall route processing through selected provider (`openai`, `azure_openai`, `google`, or `ollama`).
- System shall attempt transcription fallback before marking provider-stage failure.

### FR-3 Generation
- System shall generate fixed-template PDD sections:
  - purpose, scope, triggers, preconditions, steps, roles, systems,
    business_rules, exceptions, outputs, metrics, risks
- System shall generate one SIPOC table with rows:
  - supplier, input, process_step, output, customer

### FR-4 Review & Finalization
- System shall expose generated draft for in-app edits.
- System shall persist edits.
- System shall support explicit finalize action to lock final version.

### FR-5 Export
- System shall export finalized outputs in Markdown, JSON, PDF, and DOCX.

### FR-6 Job Tracking
- System shall provide status values:
  - `queued`, `processing`, `needs_review`, `completed`, `failed`, `expired`
- System shall provide meaningful error codes/messages for failed jobs.

### FR-7 Retention & Limits
- System shall auto-delete files/results after 7 days.
- System shall enforce per-job duration/token limits and fail gracefully.

### FR-8 Provider Selection
- System shall allow provider selection at job creation time.
- System shall persist selected provider in job metadata.
- System shall expose provider and model plan in job status response.

### FR-9 Model Evaluation and Defaulting
- System shall support benchmark runs across OpenAI, Azure OpenAI, and Google paths.
- System shall report quality, latency, and cost metrics per provider.
- System shall allow a configurable default provider while retaining per-job override.

## 6. Non-Functional Requirements
- Reliable handling of long-running jobs without request timeout.
- Clear user-facing status updates.
- Deterministic output schema for JSON artifacts.
- Internal-demo security baseline (no public exposure by default).
- Local Docker deployment for MVP validation.
- Provider abstraction to avoid vendor lock-in in orchestration logic.

## 7. API Requirements (v1)
- `POST /api/jobs` (multipart create job; includes `provider=openai|azure_openai|google|ollama`)
- `GET /api/jobs/{job_id}` (status/progress)
- `GET /api/jobs/{job_id}/draft` (draft PDD + SIPOC)
- `PUT /api/jobs/{job_id}/draft` (save edits)
- `POST /api/jobs/{job_id}/finalize` (finalize artifacts)
- `GET /api/jobs/{job_id}/exports/{format}` (`md|json|pdf|docx`)
- `DELETE /api/jobs/{job_id}` (manual cleanup)

## 8. UX Requirements
- Single flow: upload -> submit -> track -> review/edit -> export
- Validation messaging for missing/invalid files
- Progress and state visibility for async jobs
- Warning banner indicating internal no-auth demo mode

## 9. Risks & Mitigations
- AI variability in extraction quality
  - Mitigation: fixed template + human review/edit step
- Provider output drift across model updates
  - Mitigation: benchmark suite and pinned production model versions
- Cost overruns on long media
  - Mitigation: per-job caps
- Large file processing instability
  - Mitigation: async queue + status and retries
- No-auth internal mode risk
  - Mitigation: local/private deployment only in MVP

## 10. Acceptance Criteria
1. Transcript-only upload produces draft PDD + SIPOC and can be finalized/exported.
2. Audio-only upload produces draft and exports successfully.
3. Video + transcript upload processes asynchronously and reaches review stage.
4. Invalid file type or >500 MB file is rejected with clear error.
5. Finalized job exports all four formats (`md`, `json`, `pdf`, `docx`).
6. Job artifacts expire and are deleted after 7 days.
7. User can choose `openai`, `azure_openai`, `google`, or `ollama` per job and view provider in status.
8. Fallback transcription path is attempted before hard provider-stage failure.

## 11. Implementation Stack (MVP)
- Frontend: Next.js
- Backend: FastAPI
- Processing: async worker queue
- AI: managed/local multimodal APIs (OpenAI + Azure OpenAI + Google + Ollama, runtime selectable)
- Deployment: local Docker
