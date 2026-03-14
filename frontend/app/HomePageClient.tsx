"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiBase, apiFetch } from "./api";

const defaultProvider = process.env.NEXT_PUBLIC_DEFAULT_PROVIDER ?? "google";
const defaultProfile = process.env.NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE ?? "balanced";
const defaultTemplate = process.env.NEXT_PUBLIC_DEFAULT_DOCUMENT_TEMPLATE ?? "pdd";

type JobStatus = "queued" | "processing" | "needs_review" | "completed" | "failed" | "expired";

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
  const [draftJson, setDraftJson] = useState("");
  const [draftMarkdown, setDraftMarkdown] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState("");

  const canSubmit = useMemo(() => Boolean(transcriptFile || audioFile || videoFile), [transcriptFile, audioFile, videoFile]);
  const canReview = job?.status === "needs_review" || job?.status === "completed";
  const canFinalize = job?.status === "needs_review";
  const isWorking = Boolean(jobId) && (!job || job?.status === "queued" || job?.status === "processing");
  const providerExecution = job?.progress?.provider_execution;
  const requestedProvider = providerExecution?.requested_provider ?? job?.provider ?? "-";
  const executedProvider = providerExecution?.executed_provider ?? job?.model_plan?.provider ?? job?.provider ?? "-";
  const fallbackUsed = Boolean(providerExecution?.fallback_used ?? job?.model_plan?.fallback_used);
  const primaryProviderError = providerExecution?.primary_error ?? job?.model_plan?.primary_error ?? "";
  const mediaMode = job?.model_plan?.media_processing?.mode ?? "-";
  const mediaModeNote = job?.model_plan?.media_processing?.note ?? "";

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
        setDraftJson(
          JSON.stringify(
            {
              document_type: payload.data.document_type ?? payload.data.document_template ?? "pdd",
              document: payload.data.document ?? {},
              sipoc: payload.data.sipoc ?? []
            },
            null,
            2
          )
        );
        setDraftMarkdown(payload.data.document_markdown ?? "");
      }
    } catch {
      setError(`Cannot reach API at ${apiBase || "/api"}.`);
    }
  }

  async function saveDraft() {
    setError("");
    if (!jobId || !draftJson) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(draftJson);
    } catch {
      setError("Draft JSON is invalid.");
      return;
    }
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/draft`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed)
      });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to save draft.");
        return;
      }
      setStatusMsg("Draft saved.");
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
    <main>
      <h1>Process Documentation Agent</h1>
      <p className="muted">Upload evidence, review generated PDD/SIPOC, finalize, and export.</p>
      <p>
        <Link href="/history">View Job History</Link>
      </p>

      <section className="card">
        <h2>Submit Job</h2>
        <div className="row">
          <div>
            <label>Provider</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="google">google</option>
              <option value="openai">openai</option>
              <option value="azure_openai">azure_openai</option>
              <option value="ollama">ollama</option>
            </select>
          </div>
          <div>
            <label>Processing Profile</label>
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              <option value="balanced">balanced</option>
              <option value="quality">quality</option>
              <option value="low_cost">low_cost</option>
            </select>
            <p className="muted">`quality` may process full media and incur higher cost. Prefer transcript upload from team recordings.</p>
          </div>
          <div>
            <label>Document Template</label>
            <select value={documentTemplate} onChange={(e) => setDocumentTemplate(e.target.value)}>
              <option value="pdd">pdd</option>
              <option value="sop">sop</option>
              <option value="custom_sop">custom_sop</option>
            </select>
          </div>
        </div>
        <div className="row">
          <div>
            <label>Transcript</label>
            <input type="file" accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf" onChange={(e) => setTranscriptFile(e.target.files?.[0] ?? null)} />
          </div>
          <div>
            <label>Audio</label>
            <input type="file" accept="audio/*" onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)} />
          </div>
        </div>
        <div>
          <label>Video</label>
          <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)} />
        </div>
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
          <textarea rows={3} value={contextNotes} onChange={(e) => setContextNotes(e.target.value)} />
        </div>
        <button onClick={submitJob} disabled={!canSubmit}>Submit</button>
      </section>

      <section className="card">
        <h2>Status</h2>
        {isWorking ? (
          <div className="processingBanner" aria-live="polite" role="status">
            <div className="processingHeader">
              <span className="spinner" aria-hidden="true" />
              <strong>Processing in progress</strong>
            </div>
            <p className="muted">Your files are being analyzed. Stage: {job?.progress?.stage || "queued"}</p>
            <div className="progressRail" aria-hidden="true">
              <span className="progressGlow" />
            </div>
          </div>
        ) : null}
        <p className="muted">Job ID: {jobId || "-"}</p>
        <p className="muted">Status: {(job?.status as JobStatus) || "-"}</p>
        <p className="muted">Stage: {job?.progress?.stage || "-"}</p>
        <p className="muted">Requested Provider: {requestedProvider}</p>
        <p className="muted">Executed Provider: {executedProvider}</p>
        <p className="muted">Document Template: {job?.document_template ?? "-"}</p>
        <p className="muted">Media Mode: {mediaMode}</p>
        {mediaModeNote ? <p className="muted">Media Note: {mediaModeNote}</p> : null}
        <p className="muted">Fallback Used: {fallbackUsed ? "yes" : "no"}</p>
        {fallbackUsed ? (
          <p style={{ color: "#92400e" }}>
            Selected provider failed. Output was generated with fallback provider "{executedProvider}". Re-run if you need the
            originally selected provider.
          </p>
        ) : null}
        {primaryProviderError ? <p className="muted">Primary Provider Error: {primaryProviderError}</p> : null}
        <p className="muted">Message: {statusMsg || "-"}</p>
        {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
      </section>

      <section className="card">
        <h2>Template Draft</h2>
        <textarea rows={18} value={draftMarkdown} readOnly />
      </section>

      <section className="card">
        <h2>Review Draft</h2>
        <textarea rows={18} value={draftJson} onChange={(e) => setDraftJson(e.target.value)} />
        <div className="row">
          <button onClick={saveDraft} disabled={!canReview || !draftJson}>Save Draft</button>
          <button onClick={finalizeJob} disabled={!canFinalize}>Finalize & Generate Exports</button>
        </div>
      </section>

      <section className="card">
        <h2>Exports</h2>
        <div className="row">
          <a href={jobId ? `${apiBase}/api/jobs/${jobId}/exports/md` : "#"} target="_blank" rel="noreferrer">Download Markdown</a>
          <a href={jobId ? `${apiBase}/api/jobs/${jobId}/exports/json` : "#"} target="_blank" rel="noreferrer">Download JSON</a>
        </div>
        <div className="row">
          <a href={jobId ? `${apiBase}/api/jobs/${jobId}/exports/pdf` : "#"} target="_blank" rel="noreferrer">Download PDF</a>
          <a href={jobId ? `${apiBase}/api/jobs/${jobId}/exports/docx` : "#"} target="_blank" rel="noreferrer">Download Word (.docx)</a>
        </div>
        <div className="row">
          <span className="muted">Available after status = completed.</span>
        </div>
      </section>
    </main>
  );
}
