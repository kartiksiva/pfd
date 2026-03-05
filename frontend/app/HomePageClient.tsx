"use client";

import { useEffect, useMemo, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const defaultProvider = process.env.NEXT_PUBLIC_DEFAULT_PROVIDER ?? "google";
const defaultProfile = process.env.NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE ?? "balanced";

type JobStatus = "queued" | "processing" | "needs_review" | "completed" | "failed" | "expired";

export default function HomePage() {
  const [provider, setProvider] = useState(defaultProvider);
  const [profile, setProfile] = useState(defaultProfile);
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
    if (contextNotes) fd.append("context_notes", contextNotes);
    if (transcriptFile) fd.append("transcript_file", transcriptFile);
    if (audioFile) fd.append("audio_file", audioFile);
    if (videoFile) fd.append("video_file", videoFile);

    try {
      const res = await fetch(`${apiBase}/api/jobs`, { method: "POST", body: fd });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to create job.");
        return;
      }
      setJobId(payload.data.job_id);
      setStatusMsg("Job submitted.");
    } catch {
      setError(`Cannot reach API at ${apiBase}. Check backend and CORS settings.`);
    }
  }

  async function refreshJob(id: string) {
    try {
      const res = await fetch(`${apiBase}/api/jobs/${id}`);
      const payload = await toJsonSafe(res);
      if (res.ok && payload?.success) {
        setJob(payload.data);
      }
    } catch {
      setError(`Cannot reach API at ${apiBase}.`);
    }
  }

  async function loadDraft(id: string) {
    try {
      const res = await fetch(`${apiBase}/api/jobs/${id}/draft`);
      const payload = await toJsonSafe(res);
      if (res.ok && payload?.success) {
        setDraftJson(JSON.stringify({ pdd: payload.data.pdd, sipoc: payload.data.sipoc }, null, 2));
        setDraftMarkdown(payload.data.pdd_markdown ?? "");
      }
    } catch {
      setError(`Cannot reach API at ${apiBase}.`);
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
      const res = await fetch(`${apiBase}/api/jobs/${jobId}/draft`, {
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
      setError(`Cannot reach API at ${apiBase}.`);
    }
  }

  async function finalizeJob() {
    setError("");
    if (!jobId) return;
    try {
      const res = await fetch(`${apiBase}/api/jobs/${jobId}/finalize`, { method: "POST" });
      const payload = await toJsonSafe(res);
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to finalize.");
        return;
      }
      setStatusMsg("Finalize accepted.");
      await refreshJob(jobId);
    } catch {
      setError(`Cannot reach API at ${apiBase}.`);
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

  return (
    <main>
      <h1>Process Documentation Agent</h1>
      <p className="muted">Upload evidence, review generated PDD/SIPOC, finalize, and export.</p>

      <section className="card">
        <h2>Submit Job</h2>
        <div className="row">
          <div>
            <label>Provider</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="google">google</option>
              <option value="openai">openai</option>
            </select>
          </div>
          <div>
            <label>Processing Profile</label>
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              <option value="balanced">balanced</option>
              <option value="quality">quality</option>
              <option value="low_cost">low_cost</option>
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
          <label>Context Notes (max 2000)</label>
          <textarea rows={3} value={contextNotes} onChange={(e) => setContextNotes(e.target.value)} />
        </div>
        <button onClick={submitJob} disabled={!canSubmit}>Submit</button>
      </section>

      <section className="card">
        <h2>Status</h2>
        <p className="muted">Job ID: {jobId || "-"}</p>
        <p className="muted">Status: {(job?.status as JobStatus) || "-"}</p>
        <p className="muted">Stage: {job?.progress?.stage || "-"}</p>
        <p className="muted">Message: {statusMsg || "-"}</p>
        {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
      </section>

      <section className="card">
        <h2>Template Draft (STANDARD_PDD_TEMPLATE)</h2>
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
