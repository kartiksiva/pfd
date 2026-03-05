# GEMINI.md - Process Documentation Agent (MVP)

## Project Overview
The **Process Documentation Agent** is an internal MVP designed to convert process evidence (video, audio, or transcripts) into structured documentation. It leverages multimodal AI to generate:
- **Process Definition Documents (PDD):** Detailed steps, roles, systems, and rules.
- **SIPOC Maps:** High-level view of Suppliers, Inputs, Process, Outputs, and Customers.

The system uses a **multi-agent orchestration** model to handle ingestion, media analysis, extraction, and quality control.

## Agent Roles & Interaction Model
- **Reviewer (Gemini CLI):** Responsible for technical oversight, architectural validation, schema compliance, and code quality audits. All implementations must pass the Reviewer's evaluation against the project's mandates.
- **Developer (Codex):** Responsible for implementation, repository bootstrapping, and executing the milestones defined in `TASKS.md`.

### Core Technologies
- **Frontend:** Next.js (TypeScript)
- **Backend:** FastAPI (Python)
- **AI Providers:** OpenAI & Google (runtime selectable)
- **Job Management:** Async worker queue
- **Deployment:** Local Docker

## Building and Running
*Note: This project is currently in the initialization phase. Refer to `TASKS.md` for the implementation roadmap.*

### Prerequisites
- Docker & Docker Compose
- API Keys for OpenAI and/or Google (Gemini)

### Local Development
1. **Backend:**
   - TODO: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload`
2. **Frontend:**
   - TODO: `cd frontend && npm install && npm run dev`
3. **Full Stack:**
   - TODO: `docker-compose up --build`

## Development Conventions & Mandates

### 1. Data Contracts & API
- **Strict Schema Adherence:** All API responses MUST follow the envelope defined in `schemas.md` and `openapi.yaml`:
  ```json
  {
    "success": boolean,
    "data": object | null,
    "error": object | null
  }
  ```
- **IDs & Timestamps:** Use UUIDs for job IDs and ISO-8601 UTC strings for dates.
- **MIME/Size Limits:** Enforce 500 MB max file size and strict MIME allowlists at the ingestion layer.

### 2. Multi-Agent Topology
Logic should be partitioned into the following agents:
- `ui-agent`: Frontend UX and client-side validation.
- `ingestion-agent`: Server-side validation and storage.
- `media-understanding-agent`: Transcription and visual context extraction.
- `process-extraction-agent`: Merging signals into structured steps.
- `document-agent`: Generating PDD and SIPOC drafts.
- `quality-agent`: Confidence scoring and completeness checks.
- `provider-routing-agent`: Handling OpenAI/Google abstraction and fallbacks.
- `export-agent`: Generating `.md`, `.json`, and `.pdf` artifacts.
- `retention-agent`: Enforcing the 7-day TTL cleanup.

### 3. State Management
Jobs follow a strict state machine:
`queued` -> `processing` -> `needs_review` -> `completed`
- Finalization is required before artifacts are generated.
- Failures must include a diagnostic `error_code`.

### 4. Quality & Cost
- **Human-in-the-loop:** Always route to `needs_review` with `ReviewNotes` identifying low-confidence sections.
- **Cost Band:** Aim for `$2–$8` per source media hour.

## Key Files
- `PRD.md`: Functional and non-functional requirements.
- `AGENTS.md`: Multi-agent operating model and topology.
- `schemas.md`: Canonical data structures and API envelopes.
- `openapi.yaml`: Full REST API specification.
- `TASKS.md`: Execution roadmap and milestones.
