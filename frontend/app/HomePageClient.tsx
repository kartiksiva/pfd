"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiBase, apiFetch, joinApiPath } from "./api";

const defaultProvider = process.env.NEXT_PUBLIC_DEFAULT_PROVIDER ?? "google";
const defaultProfile = process.env.NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE ?? "balanced";
const defaultTemplate = process.env.NEXT_PUBLIC_DEFAULT_DOCUMENT_TEMPLATE ?? "pdd";

type JobStatus = "queued" | "processing" | "needs_review" | "completed" | "failed" | "expired";

const stageOrder = [
  "queued",
  "provider_routing",
  "media_understanding",
  "process_extraction",
  "quality_checks",
  "ready_for_review",
  "export_generation"
] as const;

const stageLabels: Record<(typeof stageOrder)[number], string> = {
  queued: "Queued",
  provider_routing: "Resolving provider plan",
  media_understanding: "Processing media evidence",
  process_extraction: "Extracting process structure",
  quality_checks: "Running quality checks",
  ready_for_review: "Ready for review",
  export_generation: "Generating export artifacts"
};

const templatePreviews: Record<string, string> = {
  pdd: `# [Process Name] - Process Definition Document (PDD)

## 1. Document Control
| Version | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| 1.0 | [Date] | [Author Name] | Initial Draft |

## 2. Process Overview
* **Process Name:** [Name]
* **Objective:** [Short description of why the process exists]

## 5. Detailed Process Steps (As-Is)
| Step # | Action | Role | System | Input | Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1.1 | [Action] | [Role] | [System] | [Input] | [Output] |`,
  sop: `# Standard Operating Procedure (SOP) Template

## <Process Name>
**Function:** <Function Name>
**Sub-Function:** <Sub-function Name>
**Document Version:** <vX.X>
**Document Status:** Draft / Final
**Effective Date:** <DD-MMM-YYYY>

---

## 1. Document Control
### 1.1 Key Stakeholders
| # | Name | Position / Designation | Email ID |
|---|------|------------------------|----------|
| 1 | <Name> | <Role> | <email@domain> |
| 2 | <Name> | <Role> | <email@domain> |

### 1.2 Version History
| Version | Date | Status | Author | Reviewed By | Comments / Changes |
|---------|------|--------|--------|-------------|-------------------|
| 0.1 | <DD-MMM-YYYY> | Draft | <Name> | <Name> | Initial draft |
| 1.0 | <DD-MMM-YYYY> | Final | <Name> | <Name> | Approved version |

---

## 2. Introduction
### 2.1 Process Overview
<Brief description of the process>

### 2.2 Process Objective
- <Objective 1>
- <Objective 2>

### 2.3 Frequency
<Daily / Weekly / Monthly / Ad-hoc>

### 2.4 SLA
- <Turnaround time / SLA details>

---

## 3. Process Steps
### Step 1: <Step Name>
- Description
- Tools / Systems
- Inputs

### Step 2: <Step Name>
- Description
- Validation / Checks
- Outputs

---

## 4. Process Exceptions
| Exception Scenario | Description | Action Required | Owner |
|--------------------|-------------|-----------------|-------|
| <Exception 1> | <Details> | <Resolution> | <Role> |`,
  custom_sop: `# Standard Operating Procedure (SOP) Template

## <Process Name>
**Function:** <Function Name>
**Sub-Function:** <Sub-function Name>
**Document Version:** <vX.X>
**Document Status:** Draft / Final
**Effective Date:** <DD-MMM-YYYY>

---

## 1. Document Control
### 1.1 Key Stakeholders
| # | Name | Position / Designation | Email ID |
|---|------|------------------------|----------|
| 1 | <Name> | <Role> | <email@domain> |
| 2 | <Name> | <Role> | <email@domain> |
| 3 | <Name> | <Role> | <email@domain> |

### 1.2 Version History
| Version | Date | Status (Draft/Final) | Author | Reviewed By | Comments / Changes |
|---------|------|----------------------|--------|-------------|-------------------|
| 0.1 | <DD-MMM-YYYY> | Draft | <Name> | <Name> | Initial draft |
| 1.0 | <DD-MMM-YYYY> | Final | <Name> | <Name> | Approved version |

---

## Index
1. Document Control
2. Introduction
3. Process Steps
4. Process Exceptions
5. Process Controls
6. Approval Matrix
7. Appendix

---

## 2. Introduction
### 2.1 Process Overview
<Brief description of the process>

### 2.2 Process Objective
- <Objective 1>
- <Objective 2>
- <Objective 3>

### 2.3 Frequency
<Daily / Weekly / Monthly / Ad-hoc>

### 2.4 SLA
- <Turnaround time / SLA details>

### 2.5 RACI
| Task / Stakeholders | Role 1 | Role 2 | Role 3 |
|---------------------|--------|--------|--------|
| <Task 1> | R | I | A |
| <Task 2> | I | R | A |

### 2.6 SIPOC
**Supplier**
- <Supplier>

**Input**
- <Inputs>

**Process**
- <High-level steps>

**Output**
- <Outputs>

**Customer**
- <Customers>

---

## 3. Process Steps
### Step 1: <Step Name>
- Description
- Tools / Systems
- Inputs

### Step 2: <Step Name>
- Description
- Validation / Checks
- Outputs

---

## 4. Process Exceptions
| Exception Scenario | Description | Action Required | Owner |
|--------------------|-------------|-----------------|-------|
| <Exception 1> | <Details> | <Resolution> | <Role> |

---

## 5. Process Controls
| Control # | Process Step | Control Description | Manual / System | Preventive / Detective |
|-----------|-------------|---------------------|-----------------|------------------------|
| C1 | <Step Name> | <Control Description> | Manual | Preventive |

---

## 6. Approval Matrix
| Role | Responsibility |
|------|----------------|
| <Role 1> | Review |
| <Role 2> | Approval |`
};

function formatProviderLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatStatusLabel(value?: string) {
  if (!value) return "Idle";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTemplateLabel(value: string) {
  switch (value) {
    case "pdd":
      return "PDD - Transcript";
    case "sop":
      return "SOP - Standard";
    case "custom_sop":
      return "SOP - Custom";
    default:
      return value;
  }
}

type UploadPanelProps = {
  accept: string;
  file: File | null;
  hint: string;
  title: string;
  onChange: (file: File | null) => void;
};

function UploadPanel({ accept, file, hint, title, onChange }: UploadPanelProps) {
  return (
    <label className="uploadPanel">
      <span className="uploadLabel">{title}</span>
      <input className="srOnlyInput" type="file" accept={accept} onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
      <span className="uploadPanelInner">
        <span className="uploadGlyph" aria-hidden="true">
          ^
        </span>
        <span className="uploadTitle">{file ? file.name : "Drop file here or browse"}</span>
        <span className="uploadHint">{file ? "Click to replace the selected file." : hint}</span>
      </span>
    </label>
  );
}

export default function HomePage() {
  const [provider, setProvider] = useState(defaultProvider);
  const [profile, setProfile] = useState(defaultProfile);
  const [documentTemplate, setDocumentTemplate] = useState(defaultTemplate);
  const [processName, setProcessName] = useState("");
  const [contextNotes, setContextNotes] = useState("");
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<any>(null);
  const [draftMarkdown, setDraftMarkdown] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState("");
  const [isReviewOpen, setIsReviewOpen] = useState(false);

  const canSubmit = useMemo(() => Boolean(transcriptFile || audioFile || videoFile), [transcriptFile, audioFile, videoFile]);
  const canReview = job?.status === "needs_review" || job?.status === "completed";
  const canFinalize = job?.status === "needs_review";
  const isWorking = Boolean(jobId) && (!job || job?.status === "queued" || job?.status === "processing");
  const providerExecution = job?.progress?.provider_execution;
  const requestedProvider = providerExecution?.requested_provider ?? job?.provider ?? "";
  const executedProvider = providerExecution?.executed_provider ?? job?.model_plan?.provider ?? job?.provider ?? "";
  const fallbackUsed = Boolean(providerExecution?.fallback_used ?? job?.model_plan?.fallback_used);
  const primaryProviderError = providerExecution?.primary_error ?? job?.model_plan?.primary_error ?? "";
  const mediaMode = job?.model_plan?.media_processing?.mode ?? "";
  const mediaModeNote = job?.model_plan?.media_processing?.note ?? "";
  const isCompleted = job?.status === "completed";
  const progressStage = (job?.progress?.stage as (typeof stageOrder)[number] | undefined) ?? (jobId ? "queued" : undefined);
  const progressPercent = typeof job?.progress?.percent === "number" ? job.progress.percent : jobId ? 0 : 0;
  const currentStageIndex = progressStage ? stageOrder.indexOf(progressStage) : -1;
  const statusLabel = job?.status ? formatStatusLabel(job.status) : "Idle";
  const reviewButtonLabel = canReview ? "View Template and Output" : "Template and Output";
  const progressSteps = stageOrder.map((stage, index) => {
    const baseLabel = stageLabels[stage];
    const label = isCompleted && stage === "export_generation" ? "Exports generated" : baseLabel;
    const done = isCompleted ? true : currentStageIndex > index || (stage === "ready_for_review" && job?.status === "needs_review");
    const active = !isCompleted && progressStage === stage;
    return { stage, label, done, active };
  });
  const statusMessage =
    statusMsg ||
    (isCompleted
      ? "All exports generated and ready for download."
        : jobId
          ? "Job loaded. Monitor status here and open the review modal when draft generation completes."
          : "No active job. Submit a new job to get started.");
  const canDownloadDraftMarkdown = Boolean(jobId && draftMarkdown);
  const selectedTemplatePreview = templatePreviews[job?.document_template ?? documentTemplate] ?? templatePreviews.pdd;

  async function toJsonSafe(res: Response): Promise<any> {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }

  async function submitJob() {
    setError("");
    if (!canSubmit) {
      setError("Upload at least one file.");
      return;
    }
    const fd = new FormData();
    fd.append("provider", provider);
    fd.append("processing_profile", profile);
    fd.append("document_template", documentTemplate);
    if (processName.trim()) fd.append("process_name", processName.trim());
    if (contextNotes) fd.append("context_notes", contextNotes);
    if (transcriptFile) fd.append("transcript_file", transcriptFile);
    if (audioFile) fd.append("audio_file", audioFile);
    if (videoFile) fd.append("video_file", videoFile);

    try {
      const res = await apiFetch("/api/jobs", { method: "POST", body: fd });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to create job.");
        return;
      }
      setJobId(payload.data.job_id);
      setJob(null);
      setDraftMarkdown("");
      setIsReviewOpen(false);
      setStatusMsg("Job submitted.");
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}. Check backend and CORS settings.`);
    }
  }

  async function refreshJob(id: string) {
    try {
      const res = await apiFetch(`/api/jobs/${id}`);
      const payload = await toJsonSafe(res);
      if (res.ok && payload?.success) {
        setJob(payload.data);
      }
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}.`);
    }
  }

  async function loadDraft(id: string) {
    try {
      const res = await apiFetch(`/api/jobs/${id}/draft`);
      const payload = await toJsonSafe(res);
      if (res.ok && payload?.success) {
        setDraftMarkdown(payload.data.document_markdown ?? "");
      }
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}.`);
    }
  }

  async function finalizeJob() {
    setError("");
    if (!jobId) return;
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/finalize`, { method: "POST" });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to finalize.");
        return;
      }
      setStatusMsg("Finalize accepted.");
      await refreshJob(jobId);
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}.`);
    }
  }

  function openReview() {
    if (!canReview) return;
    setIsReviewOpen(true);
  }

  function downloadDraftMarkdown() {
    if (!draftMarkdown) return;
    const filenameBase = (job?.process_name || processName || "process-document")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "process-document";
    const filename = `${filenameBase}-${jobId || "draft"}.md`;
    const blob = new Blob([draftMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    if (!jobId) return;
    refreshJob(jobId);
    const t = setInterval(() => {
      refreshJob(jobId);
    }, 2000);
    return () => clearInterval(t);
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    if (canReview) loadDraft(jobId);
  }, [jobId, canReview]);

  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("job_id");
    if (fromUrl && !jobId) {
      setJobId(fromUrl);
      setStatusMsg(`Loaded job ${fromUrl} from history.`);
    }
  }, [jobId]);

  return (
    <>
      <main className="dashboardMain">
        <div className="pageHeader">
          <div className="pageBrand">
            <span className="brandMark" aria-hidden="true">
              *
            </span>
            <div>
              <h1>Process Documentation Agent</h1>
              <p className="muted">Upload evidence, review generated PDD/SIPOC, finalize, and export.</p>
            </div>
          </div>
          <p>
            <Link href="/history">View Job History</Link>
          </p>
        </div>

        <div className="dashboardGrid">
          <div className="leftColumn">
            <section className="card configCard">
              <div className="cardHeader">
                <div>
                  <p className="sectionEyebrow">Job Configuration</p>
                  <h2>Configure your documentation generation settings</h2>
                </div>
              </div>

              <div className="formSection">
                <p className="groupHeading">Processing Settings</p>
                <div className="row rowThree">
                  <div>
                    <label>Provider</label>
                    <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                      <option value="google">Google</option>
                      <option value="openai">OpenAI</option>
                      <option value="azure_openai">Azure OpenAI</option>
                      <option value="ollama">Ollama</option>
                    </select>
                  </div>
                  <div>
                    <label>Processing Profile</label>
                    <select value={profile} onChange={(e) => setProfile(e.target.value)}>
                      <option value="balanced">Balanced</option>
                      <option value="quality">Quality</option>
                      <option value="low_cost">Low Cost</option>
                    </select>
                    <p className="fieldNote">
                      `quality` may process full media and incur higher cost. Prefer transcript upload from team recordings.
                    </p>
                  </div>
                  <div className="rowSpanFull">
                    <label>Document Template</label>
                    <select value={documentTemplate} onChange={(e) => setDocumentTemplate(e.target.value)}>
                      <option value="pdd">PDD - Transcript</option>
                      <option value="sop">SOP - Standard</option>
                      <option value="custom_sop">SOP - Custom</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="formSection">
                <p className="groupHeading">Media Upload</p>
                <div className="uploadGrid">
                  <UploadPanel
                    title="Transcript"
                    accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
                    file={transcriptFile}
                    hint="TXT, PDF, DOC, DOCX"
                    onChange={setTranscriptFile}
                  />
                  <UploadPanel title="Audio" accept="audio/*" file={audioFile} hint="MP3, WAV, M4A, OGG" onChange={setAudioFile} />
                  <div className="uploadSpanFull">
                    <UploadPanel title="Video" accept="video/*" file={videoFile} hint="MP4, MOV, AVI, WEBM" onChange={setVideoFile} />
                  </div>
                </div>
              </div>

              <div className="formSection">
                <p className="groupHeading">Process Details</p>
                <div className="fieldStack">
                  <div>
                    <label>Process Name</label>
                    <input
                      type="text"
                      placeholder="e.g., invoice_reconciliation"
                      value={processName}
                      onChange={(e) => setProcessName(e.target.value)}
                    />
                  </div>
                  <div>
                    <label>Context Notes (max 2000)</label>
                    <textarea
                      rows={4}
                      maxLength={2000}
                      placeholder="Add any additional context or requirements..."
                      value={contextNotes}
                      onChange={(e) => setContextNotes(e.target.value)}
                    />
                    <div className="fieldCounter">{contextNotes.length}/2000</div>
                  </div>
                </div>
              </div>

              {error ? <p className="formError">{error}</p> : null}

              <div className="primaryActionRow">
                <button onClick={submitJob} disabled={!canSubmit}>
                  Generate Documentation
                </button>
              </div>
            </section>

            <section className="card draftEntryCard">
              <div className="cardHeader compactHeader">
                <div>
                  <p className="sectionEyebrow">Document Drafts</p>
                  <h2>Review and edit generated documentation</h2>
                </div>
              </div>
              <div className="draftEntryBody">
                <div className="draftEntryMeta">
                  <div>
                    <span className="draftPill">Template Draft</span>
                    <p className="muted">Generated markdown preview from the selected template.</p>
                  </div>
                  <div>
                    <span className="draftPill">Review Draft</span>
                    <p className="muted">Markdown draft available now. PDF and DOCX are generated after finalization.</p>
                  </div>
                </div>
                <div className="draftPreviewBox">
                  <p className="draftPreviewText">
                    {draftMarkdown
                      ? `${draftMarkdown.slice(0, 280)}${draftMarkdown.length > 280 ? "..." : ""}`
                      : "Generated template and output will appear here after the job reaches review or completed state."}
                  </p>
                </div>
                <div className="draftEntryActions">
                  <button className="secondaryButton" type="button" onClick={openReview} disabled={!canReview}>
                    Open Review Popup
                  </button>
                  {isCompleted ? (
                    <button type="button" disabled>
                      Exports Ready
                    </button>
                  ) : canDownloadDraftMarkdown ? (
                    <button type="button" onClick={downloadDraftMarkdown}>
                      Download Markdown Draft
                    </button>
                  ) : (
                    <button type="button" onClick={finalizeJob} disabled={!canFinalize}>
                      Finalize and Generate Exports
                    </button>
                  )}
                </div>
              </div>
            </section>
          </div>

          <aside className="card statusCard">
            <div className="statusHeader">
              <h2>Job Status</h2>
              <span className={`statusBadge status-${job?.status ?? "idle"}`}>{statusLabel}</span>
            </div>

            {jobId ? (
              <div className="progressPanel" aria-live="polite" role="status">
                <div className="progressSummary">
                  <span className="progressLabel">Progress</span>
                  <strong>{isCompleted ? 100 : progressPercent}%</strong>
                </div>
                <div className="progressRail" aria-hidden="true">
                  <span className="progressFill" style={{ width: `${isCompleted ? 100 : progressPercent}%` }} />
                </div>
                <ul className="progressChecklist">
                  {progressSteps.map((step) => (
                    <li key={step.stage} className={step.done ? "isDone" : step.active ? "isActive" : ""}>
                      <span className="progressDot" aria-hidden="true" />
                      <span>{step.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <dl className="statusList">
              <div>
                <dt>Job ID</dt>
                <dd>{jobId || "-"}</dd>
              </div>
              <div>
                <dt>Provider</dt>
                <dd>{requestedProvider ? formatProviderLabel(requestedProvider) : "-"}</dd>
              </div>
              <div>
                <dt>Template</dt>
                <dd>{job?.document_template ? formatTemplateLabel(job.document_template) : formatTemplateLabel(documentTemplate)}</dd>
              </div>
              <div>
                <dt>Media Mode</dt>
                <dd>{mediaMode ? formatStatusLabel(mediaMode) : "-"}</dd>
              </div>
              <div>
                <dt>Fallback Used</dt>
                <dd>{fallbackUsed ? "Yes" : "No"}</dd>
              </div>
            </dl>

            <div className="statusMessageCard">
              <p className="statusMessageTitle">Status Message</p>
              <p className="muted">{statusMessage}</p>
            </div>

            {mediaModeNote ? <p className="fieldNote">Media note: {mediaModeNote}</p> : null}
            {fallbackUsed ? (
              <p className="statusWarning">
                Selected provider failed. Output was generated with fallback provider "{formatProviderLabel(executedProvider)}".
              </p>
            ) : null}
            {primaryProviderError ? <p className="fieldNote">Primary provider error: {primaryProviderError}</p> : null}

            <div className="statusActions">
              <button className="secondaryButton" type="button" onClick={openReview} disabled={!canReview}>
                {reviewButtonLabel}
              </button>
              <div className={`exportLinks ${isCompleted ? "exportLinksCompleted" : ""}`}>
                {canDownloadDraftMarkdown ? (
                  <button className={isCompleted ? "exportLinkPrimary exportLinkButton" : "exportLinkButton"} type="button" onClick={downloadDraftMarkdown}>
                    Markdown Draft
                  </button>
                ) : null}
                {isCompleted ? (
                  <>
                    <a
                      className="exportLinkPrimary"
                      href={jobId ? joinApiPath(`/api/jobs/${jobId}/exports/pdf`) : "#"}
                      target="_blank"
                      rel="noreferrer"
                      aria-disabled={!jobId}
                    >
                      PDF
                    </a>
                    <a
                      className="exportLinkPrimary"
                      href={jobId ? joinApiPath(`/api/jobs/${jobId}/exports/docx`) : "#"}
                      target="_blank"
                      rel="noreferrer"
                      aria-disabled={!jobId}
                    >
                      DOCX
                    </a>
                  </>
                ) : null}
              </div>
            </div>
          </aside>
        </div>
      </main>

      {isReviewOpen ? (
        <div className="modalBackdrop" role="dialog" aria-modal="true" aria-labelledby="review-modal-title">
          <div className="modalCard">
            <div className="modalHeader">
              <div>
                <p className="sectionEyebrow">Draft Review</p>
                <h2 id="review-modal-title">Template and Output</h2>
              </div>
              <button className="modalCloseButton" type="button" onClick={() => setIsReviewOpen(false)}>
                Close
              </button>
            </div>

            <div className="modalGrid">
              <section className="modalPane">
                <div className="modalPaneHeader">
                  <h3>Template</h3>
                  <p className="muted">Reference template structure for the selected document type.</p>
                </div>
                <textarea className="reviewTextarea reviewReadonly" rows={22} value={selectedTemplatePreview} readOnly />
              </section>

              <section className="modalPane">
                <div className="modalPaneHeader">
                  <h3>Markdown Output</h3>
                  <p className="muted">Generated Markdown draft for review before finalization.</p>
                </div>
                <textarea className="reviewTextarea reviewReadonly" rows={22} value={draftMarkdown} readOnly />
              </section>
            </div>

            <div className="modalFooter">
              <button className="secondaryButton" type="button" onClick={downloadDraftMarkdown} disabled={!canDownloadDraftMarkdown}>
                Download Markdown Draft
              </button>
              <button type="button" onClick={finalizeJob} disabled={!canFinalize}>
                Finalize and Generate Exports
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
