# schemas.md

## Purpose
Canonical API and data schemas for the MVP described in `PRD.md`, `AGENTS.md`, and `TASKS.md`.

## Conventions
- Date-time format: ISO-8601 UTC string.
- IDs: UUID string.
- All API responses use envelope:
  - `success: boolean`
  - `data: object | null`
  - `error: object | null`

## Enums

### JobStatus
```json
["queued", "processing", "needs_review", "completed", "failed", "expired"]
```

### Provider
```json
["openai", "azure_openai", "google", "ollama"]
```

### ProcessingProfile
```json
["quality", "balanced", "low_cost"]
```

### ExportFormat
```json
["md", "json", "pdf", "docx"]
```

## Core Objects

### ErrorObject
```json
{
  "code": "string",
  "message": "string",
  "details": {}
}
```

### InputFileMeta
```json
{
  "filename": "string",
  "content_type": "string",
  "size_bytes": 0,
  "storage_key": "string"
}
```

### InputManifest
```json
{
  "video": {
    "filename": "walkthrough.mp4",
    "content_type": "video/mp4",
    "size_bytes": 123456,
    "storage_key": "uploads/job_id/video.mp4"
  },
  "audio": null,
  "transcript": {
    "filename": "notes.txt",
    "content_type": "text/plain",
    "size_bytes": 9876,
    "storage_key": "uploads/job_id/transcript.txt"
  }
}
```

### LimitsApplied
```json
{
  "max_file_size_mb": 500,
  "max_job_duration_seconds": 7200,
  "max_provider_tokens": 1500000,
  "cost_target_band_usd_per_media_hour": {
    "min": 2,
    "max": 8
  }
}
```

### ModelPlan
```json
{
  "provider": "openai",
  "transcription_model": "string",
  "multimodal_model": "string",
  "generation_model": "string",
  "fallback_transcription": {
    "provider": "google",
    "model": "string"
  }
}
```

### UsageCostEstimate
```json
{
  "currency": "USD",
  "estimated_total": 3.84,
  "estimated_per_media_hour": 5.12,
  "input_tokens": 12345,
  "output_tokens": 2345,
  "audio_seconds_processed": 1800,
  "video_seconds_processed": 1200
}
```

### SIPOCRow
```json
{
  "supplier": "Sales Team",
  "input": "Customer Requirement",
  "process_step": "Validate request and create ticket",
  "output": "Verified service ticket",
  "customer": "Operations Team"
}
```

### PDDDocument
```json
{
  "purpose": "string",
  "scope": "string",
  "triggers": ["string"],
  "preconditions": ["string"],
  "steps": [
    {
      "step_no": 1,
      "title": "string",
      "actor": "string",
      "system": "string",
      "description": "string",
      "input": "string",
      "output": "string",
      "exception": "string"
    }
  ],
  "roles": ["string"],
  "systems": ["string"],
  "business_rules": ["string"],
  "exceptions": ["string"],
  "outputs": ["string"],
  "metrics": ["string"],
  "risks": ["string"]
}
```

### ReviewNotes
```json
{
  "quality_score": 0.82,
  "flags": [
    {
      "type": "low_confidence",
      "path": "pdd.steps[3].description",
      "message": "Weak evidence from source."
    }
  ],
  "assumptions": ["string"]
}
```

### DraftPayload
```json
{
  "job_id": "uuid",
  "provider": "openai",
  "model_plan": {
    "provider": "openai",
    "transcription_model": "string",
    "multimodal_model": "string",
    "generation_model": "string",
    "fallback_transcription": {
      "provider": "google",
      "model": "string"
    }
  },
  "pdd": {},
  "sipoc": [],
  "review_notes": {
    "quality_score": 0.82,
    "flags": [],
    "assumptions": []
  },
  "updated_at": "2026-03-05T12:34:56Z"
}
```

### JobRecord
```json
{
  "id": "uuid",
  "status": "processing",
  "provider": "openai",
  "processing_profile": "balanced",
  "model_plan": {},
  "input_manifest": {},
  "limits_applied": {},
  "usage_cost_estimate": {},
  "artifacts": {
    "md": null,
    "json": null,
    "pdf": null,
    "docx": null
  },
  "error_code": null,
  "error_message": null,
  "created_at": "2026-03-05T12:00:00Z",
  "updated_at": "2026-03-05T12:02:00Z",
  "expires_at": "2026-03-12T12:00:00Z"
}
```

## Endpoint Schemas

### 0) `GET /api/providers/health`
Optional query:
- `timeout_seconds` (default `10`, max suggested `60`)

Success `200`:
```json
{
  "success": true,
  "data": {
    "all_ok": true,
    "results": [
      {
        "provider": "openai",
        "ok": true,
        "latency_ms": 311,
        "status_code": 200,
        "message": "OpenAI API reachable."
      },
      {
        "provider": "google",
        "ok": true,
        "latency_ms": 287,
        "status_code": 200,
        "message": "Google API reachable."
      }
    ]
  },
  "error": null
}
```

### 0b) `POST /api/system/retention/sweep`
Success `200`:
```json
{
  "success": true,
  "data": {
    "scanned": 3,
    "expired": 2
  },
  "error": null
}
```

### 1) `POST /api/jobs`
`multipart/form-data`

Fields:
- `provider` (required): `openai | azure_openai | google | ollama`
- `processing_profile` (optional): `quality | balanced | low_cost` (default: `balanced`)
- `context_notes` (optional): string (max 2000 chars)
- `video_file` (optional): binary
- `audio_file` (optional): binary
- `transcript_file` (optional): binary

Validation:
- At least one of `video_file`, `audio_file`, `transcript_file` must be present.
- Max file size 500 MB per file.
- MIME allowlist must pass.

Success response `202`:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "provider": "openai",
    "processing_profile": "balanced",
    "created_at": "2026-03-05T12:00:00Z"
  },
  "error": null
}
```

Error response `400/413/415`:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERR_INVALID_INPUT",
    "message": "At least one input file is required.",
    "details": {}
  }
}
```

### 2) `GET /api/jobs/{job_id}`
Success `200`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "processing",
    "provider": "openai",
    "processing_profile": "balanced",
    "model_plan": {
      "provider": "openai",
      "transcription_model": "string",
      "multimodal_model": "string",
      "generation_model": "string",
      "fallback_transcription": {
        "provider": "google",
        "model": "string"
      }
    },
    "progress": {
      "stage": "media_understanding",
      "percent": 47
    },
    "usage_cost_estimate": {
      "currency": "USD",
      "estimated_total": 2.31,
      "estimated_per_media_hour": 4.62
    },
    "artifacts": {
      "md": null,
      "json": null,
      "pdf": null,
      "docx": null
    },
    "error_code": null,
    "error_message": null,
    "created_at": "2026-03-05T12:00:00Z",
    "updated_at": "2026-03-05T12:10:00Z",
    "expires_at": "2026-03-12T12:00:00Z"
  },
  "error": null
}
```

### 3) `GET /api/jobs/{job_id}/draft`
Success `200`:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "provider": "google",
    "model_plan": {},
    "pdd": {},
    "sipoc": [],
    "review_notes": {
      "quality_score": 0.86,
      "flags": [],
      "assumptions": []
    },
    "updated_at": "2026-03-05T12:22:00Z"
  },
  "error": null
}
```

### 4) `PUT /api/jobs/{job_id}/draft`
Request body:
```json
{
  "pdd": {},
  "sipoc": [],
  "editor_notes": "Adjusted step ordering and clarified exceptions."
}
```

Success `200`:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "saved": true,
    "updated_at": "2026-03-05T12:25:00Z"
  },
  "error": null
}
```

### 5) `POST /api/jobs/{job_id}/finalize`
Request body:
```json
{
  "finalize_note": "Approved by analyst."
}
```

Success `202`:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "processing",
    "next_stage": "export_generation"
  },
  "error": null
}
```

### 6) `GET /api/jobs/{job_id}/exports/{format}`
- `{format}` must be one of: `md | json | pdf | docx`

Success `200`:
- Binary stream for `pdf`
- Text for `md`
- JSON object for `json`

Error `409` when not finalized:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERR_NOT_FINALIZED",
    "message": "Export is available only after finalization.",
    "details": {}
  }
}
```

### 7) `DELETE /api/jobs/{job_id}`
Success `200`:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "deleted": true
  },
  "error": null
}
```

## Error Code Catalog
- `ERR_INVALID_INPUT`
- `ERR_VALIDATION`
- `ERR_FILE_TOO_LARGE`
- `ERR_UNSUPPORTED_MIME`
- `ERR_JOB_NOT_FOUND`
- `ERR_INVALID_STATUS_TRANSITION`
- `ERR_PROVIDER_TIMEOUT`
- `ERR_PROVIDER_RATE_LIMIT`
- `ERR_PROVIDER_CAP_EXCEEDED`
- `ERR_TRANSCRIPTION_FAILED`
- `ERR_FALLBACK_TRANSCRIPTION_FAILED`
- `ERR_JOB_TIMEOUT`
- `ERR_EXPORT_GENERATION_FAILED`
- `ERR_INVALID_EXPORT_FORMAT`
- `ERR_EXPORT_NOT_FOUND`
- `ERR_NOT_FINALIZED`
- `ERR_JOB_EXPIRED`

## State Transition Rules
- `queued -> processing`
- `processing -> needs_review`
- `needs_review -> processing` (after user save/finalize pipeline continuation)
- `processing -> completed`
- `queued|processing|needs_review -> failed`
- `queued|processing|needs_review|completed|failed -> expired`

## Minimal JSON Schema Constraints (Implementation Notes)
- `pdd` must include all required top-level keys.
- `sipoc` must be array with at least one valid `SIPOCRow`.
- `provider` is required at job creation.
- `processing_profile` defaults to `balanced`.
- `model_plan` and `usage_cost_estimate` are required by `completed` status.
