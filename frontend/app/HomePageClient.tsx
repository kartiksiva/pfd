"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiBase, apiFetch, joinApiPath } from "./api";

const defaultProvider = process.env.NEXT_PUBLIC_DEFAULT_PROVIDER ?? "google";
const defaultProfile = process.env.NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE ?? "balanced";
const defaultTemplate = process.env.NEXT_PUBLIC_DEFAULT_DOCUMENT_TEMPLATE ?? "pdd";
const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024;
const ALLOWED_TRANSCRIPT_MIMES = new Set(["text/plain", "text/markdown", "application/pdf", "text/vtt"]);
const ALLOWED_AUDIO_MIMES = /^audio\//;
const ALLOWED_VIDEO_MIMES = /^video\//;

type JobStatus = "queued" | "processing" | "needs_review" | "completed" | "failed" | "expired";
type SaveStatus = "idle" | "saving" | "saved" | "error";

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
| 1.0 | [Date] | [Author Name] | Initial Draft (As-Is Process) |

## 2. Process Overview
* **Process Name:** [e.g., Invoice Validation]
* **Objective:** [Short description of why the process exists]
* **Frequency:** [e.g., Daily / On-demand]
* **Estimated Volume:** [e.g., 50 cases/day]
* **Manual Effort:** [e.g., 15 mins per case]

## 3. Scope
### 3.1 In-Scope
* [Primary process activities covered]
* [Systems / channels covered]

### 3.2 Out-of-Scope
* [Explicit exclusions]
* [Future-state redesign]

## 4. Prerequisites & Systems
### 4.1 Prerequisites
* [Required access, approvals, or source material]

### 4.2 Application Inventory
| Application | Version | Access Method |
| :--- | :--- | :--- |
| [System Name] | [Version] | [Web/Desktop/etc.] |

---

## 5. Detailed Process Steps (As-Is)
| Step # | Action | Role | System | Input | Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1.1 | [Action] | [Role] | [System] | [Input] | [Output] |
| 1.2 | [Action] | [Role] | [System] | [Input] | [Output] |

### Step Details
1. Follow the sequence listed in the table above.
2. Apply business rules and exception handling where applicable.

## 6. Business Rules & Logic
* **Rule 1:** [Business rule]
* **Rule 2:** [Business rule]

## 7. Exceptions Handling
### 7.1 Business Exceptions
* **Scenario:** [Exception]
* **Action:** [Resolution]

### 7.2 Technical Exceptions
* **Scenario:** [System/API issue]
* **Action:** [Retry / escalate path]

## 8. Inputs & Outputs
* **Primary Input:** [Input]
* **Primary Output:** [Output]

## 9. Metrics & Risks
* **Success Metric:** [Metric]
* **Risk:** [Risk]
* **Mitigation:** [Mitigation]

## 10. SIPOC
| Supplier | Input | Process | Output | Customer |
| :--- | :--- | :--- | :--- | :--- |
| [Supplier] | [Input] | [Process Step] | [Output] | [Customer] |`,
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

const PDD_EDITABLE_FIELDS: { key: string; label: string }[] = [
  { key: "purpose", label: "Purpose" },
  { key: "scope", label: "Scope" },
  { key: "triggers", label: "Triggers (one per line)" },
  { key: "preconditions", label: "Preconditions (one per line)" },
  { key: "roles", label: "Roles (one per line)" },
  { key: "systems", label: "Systems (one per line)" },
  { key: "business_rules", label: "Business Rules (one per line)" },
  { key: "exceptions", label: "Exceptions (one per line)" },
  { key: "outputs", label: "Outputs (one per line)" },
  { key: "metrics", label: "Metrics (one per line)" },
  { key: "risks", label: "Risks (one per line)" },
];

function initEditableFields(doc: Record<string, any>): Record<string, string> {
  const result: Record<string, string> = {};
  for (const { key } of PDD_EDITABLE_FIELDS) {
    const val = doc[key];
    if (typeof val === "string") {
      result[key] = val;
    } else if (Array.isArray(val)) {
      result[key] = (val as string[]).filter(Boolean).join("\n");
    } else {
      result[key] = "";
    }
  }
  return result;
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
  const [editedDraftMarkdown, setEditedDraftMarkdown] = useState("");
  const [draftDocument, setDraftDocument] = useState<Record<string, any> | null>(null);
  const [draftSipoc, setDraftSipoc] = useState<any[]>([]);
  const [editableFields, setEditableFields] = useState<Record<string, string>>({});
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [displayStageIndex, setDisplayStageIndex] = useState(-1);

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
  const visibleStageIndex = isCompleted ? stageOrder.length - 1 : Math.max(displayStageIndex, currentStageIndex);
  const statusLabel = job?.status ? formatStatusLabel(job.status) : "Idle";
  const reviewButtonLabel = canReview ? "View Template and Output" : "Template and Output";
  const progressSteps = stageOrder.map((stage, index) => {
    const baseLabel = stageLabels[stage];
    const label = isCompleted && stage === "export_generation" ? "Exports generated" : baseLabel;
    const done = isCompleted ? true : visibleStageIndex > index || (stage === "ready_for_review" && job?.status === "needs_review");
    const active = !isCompleted && visibleStageIndex === index;
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
  const showTranscriptionWarning = Boolean((audioFile || videoFile) && !transcriptFile && profile !== "quality");
  const isPdd = (job?.document_template ?? documentTemplate) === "pdd";

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
    const filesToCheck = [
      {
        file: transcriptFile,
        label: "Transcript",
        mimeCheck: (type: string) => ALLOWED_TRANSCRIPT_MIMES.has(type) || type.startsWith("text/"),
      },
      { file: audioFile, label: "Audio", mimeCheck: (type: string) => ALLOWED_AUDIO_MIMES.test(type) },
      { file: videoFile, label: "Video", mimeCheck: (type: string) => ALLOWED_VIDEO_MIMES.test(type) },
    ];
    for (const { file, label, mimeCheck } of filesToCheck) {
      if (!file) continue;
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setError(`${label} file exceeds the 500 MB limit (${(file.size / 1024 / 1024).toFixed(0)} MB).`);
        return;
      }
      if (!mimeCheck(file.type)) {
        setError(`${label} file type "${file.type || "unknown"}" is not supported.`);
        return;
      }
    }
    setIsSubmitting(true);
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
      setEditedDraftMarkdown("");
      setDraftDocument(null);
      setDraftSipoc([]);
      setSaveStatus("idle");
      setIsReviewOpen(false);
      setStatusMsg("Job submitted.");
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}. Check backend and CORS settings.`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitDemoJob() {
    setError("");
    setIsSubmitting(true);
    const fd = new FormData();
    fd.append("provider", provider);
    fd.append("processing_profile", profile);
    fd.append("document_template", documentTemplate);
    if (processName.trim()) fd.append("process_name", processName.trim());
    if (contextNotes) fd.append("context_notes", contextNotes);

    try {
      const res = await apiFetch("/api/jobs/demo", { method: "POST", body: fd });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to create demo job.");
        return;
      }
      setJobId(payload.data.job_id);
      setJob(null);
      setDraftMarkdown("");
      setEditedDraftMarkdown("");
      setDraftDocument(null);
      setDraftSipoc([]);
      setSaveStatus("idle");
      setIsReviewOpen(false);
      setStatusMsg("Demo job submitted.");
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}. Check backend and CORS settings.`);
    } finally {
      setIsSubmitting(false);
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
        const markdown = payload.data.document_markdown ?? "";
        setDraftMarkdown(markdown);
        setEditedDraftMarkdown(markdown);
        setDraftDocument(payload.data.document ?? null);
        setDraftSipoc(Array.isArray(payload.data.sipoc) ? payload.data.sipoc : []);
        if (payload.data.document && typeof payload.data.document === "object") {
          setEditableFields(initEditableFields(payload.data.document));
        }
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
    setEditedDraftMarkdown(draftMarkdown);
    if (draftDocument) {
      setEditableFields(initEditableFields(draftDocument));
    }
    setSaveStatus("idle");
    setIsReviewOpen(true);
  }

  async function saveDraftChanges() {
    if (!jobId || !draftDocument || !Array.isArray(draftSipoc)) return;
    setError("");
    setSaveStatus("saving");
    const docType = job?.document_template ?? documentTemplate;
    let updatedDoc: Record<string, any>;
    if (docType === "pdd") {
      updatedDoc = { ...draftDocument };
      for (const { key } of PDD_EDITABLE_FIELDS) {
        const displayVal = editableFields[key] ?? "";
        const original = draftDocument[key];
        if (Array.isArray(original)) {
          updatedDoc[key] = displayVal.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
        } else {
          updatedDoc[key] = displayVal;
        }
      }
    } else {
      updatedDoc = draftDocument;
    }
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/draft`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_type: docType,
          draft_pdd: updatedDoc,
          draft_sipoc: draftSipoc,
        }),
      });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setSaveStatus("error");
        setError(payload?.error?.message ?? "Failed to save draft.");
        return;
      }
      setSaveStatus("saved");
      await loadDraft(jobId);
    } catch {
      setSaveStatus("error");
      setError(`Cannot reach API at ${apiBase || "/api"}.`);
    }
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
    }, 750);
    return () => clearInterval(t);
  }, [jobId]);

  useEffect(() => {
    if (!jobId) {
      setDisplayStageIndex(-1);
      return;
    }
    if (currentStageIndex < 0) return;
    if (displayStageIndex < 0) {
      setDisplayStageIndex(currentStageIndex);
      return;
    }
    if (currentStageIndex <= displayStageIndex) return;

    const timer = window.setTimeout(() => {
      setDisplayStageIndex((prev) => {
        if (prev < 0) return currentStageIndex;
        return Math.min(prev + 1, currentStageIndex);
      });
    }, 280);

    return () => window.clearTimeout(timer);
  }, [jobId, currentStageIndex, displayStageIndex]);

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
                    accept=".txt,.md,.pdf,.vtt,text/plain,text/markdown,text/vtt,application/pdf"
                    file={transcriptFile}
                    hint="TXT, MD, PDF, VTT (Teams/WebVTT)"
                    onChange={setTranscriptFile}
                  />
                  <UploadPanel title="Audio" accept="audio/*" file={audioFile} hint="MP3, WAV, M4A, OGG" onChange={setAudioFile} />
                  <div className="uploadSpanFull">
                    <UploadPanel title="Video" accept="video/*" file={videoFile} hint="MP4, MOV, AVI, WEBM" onChange={setVideoFile} />
                  </div>
                </div>
                {showTranscriptionWarning ? (
                  <p className="warningNote">
                    <strong>Heads up:</strong> In Balanced / Low Cost mode, audio and video are not transcribed. Only metadata is used.
                    For best results, upload a transcript alongside your media, or switch to the <strong>Quality</strong> profile.
                  </p>
                ) : null}
                <p className="fieldNote">
                  Or skip uploads and run the bundled demo media from the server with the current processing settings.
                </p>
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
                <button onClick={submitJob} disabled={!canSubmit || isSubmitting}>
                  Generate Documentation
                </button>
                <button className="secondaryButton" onClick={submitDemoJob} disabled={isSubmitting}>
                  Run Demo Files
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
                  <h3>{isPdd ? "Document Fields" : "Markdown Output"}</h3>
                  <p className="muted">
                    {isPdd
                      ? "Edit each section below. Steps are read-only — download the draft to edit them."
                      : "Read-only preview — download the draft to edit manually."}
                  </p>
                </div>
                {isPdd ? (
                  <div className="reviewFieldList">
                    {PDD_EDITABLE_FIELDS.map(({ key, label }) => (
                      <div key={key} className="reviewField">
                        <label className="reviewFieldLabel">{label}</label>
                        <textarea
                          className="reviewTextarea reviewFieldTextarea"
                          rows={3}
                          value={editableFields[key] ?? ""}
                          disabled={saveStatus === "saving"}
                          onChange={(e) => {
                            setEditableFields((prev) => ({ ...prev, [key]: e.target.value }));
                            setSaveStatus("idle");
                          }}
                        />
                      </div>
                    ))}
                    {draftDocument?.steps ? (
                      <p className="reviewStepsNote muted">
                        Steps ({Array.isArray(draftDocument.steps) ? draftDocument.steps.length : 0} extracted) — edit after export via the downloaded document.
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <textarea className="reviewTextarea reviewReadonly" rows={22} value={editedDraftMarkdown} readOnly />
                )}
                {saveStatus === "saved" ? <p className="saveStatus">Saved.</p> : null}
                {saveStatus === "error" ? <p className="saveStatus saveStatusError">Draft save failed.</p> : null}
              </section>
            </div>

            <div className="modalFooter">
              <button className="secondaryButton" type="button" onClick={downloadDraftMarkdown} disabled={!canDownloadDraftMarkdown}>
                Download Markdown Draft
              </button>
              <button className="secondaryButton" type="button" onClick={saveDraftChanges} disabled={!canFinalize || saveStatus === "saving"}>
                {saveStatus === "saving" ? "Saving..." : "Save Changes"}
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
