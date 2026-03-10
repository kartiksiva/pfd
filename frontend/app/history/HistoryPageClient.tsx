"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type JobItem = {
  id: string;
  status: string;
  provider: string;
  processing_profile: string;
  process_name: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string;
  error_code: string | null;
  artifacts: Record<string, string | null>;
};

export default function HistoryPageClient() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory() {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ limit: "100" });
      if (statusFilter) query.set("status", statusFilter);
      const res = await fetch(`${apiBase}/api/jobs?${query.toString()}`);
      const payload = await res.json();
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? "Failed to load job history.");
        setJobs([]);
      } else {
        setJobs(payload.data.jobs ?? []);
      }
    } catch {
      setError("Cannot reach API.");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }

  async function finalizeFromHistory(jobId: string) {
    setError("");
    try {
      const res = await fetch(`${apiBase}/api/jobs/${jobId}/finalize`, { method: "POST" });
      const payload = await res.json();
      if (!res.ok || !payload?.success) {
        setError(payload?.error?.message ?? `Failed to finalize ${jobId}.`);
        return;
      }
      await loadHistory();
    } catch {
      setError(`Cannot reach API to finalize ${jobId}.`);
    }
  }

  useEffect(() => {
    loadHistory();
  }, [statusFilter]);

  return (
    <main>
      <h1>Job History</h1>
      <p className="muted">Review previously submitted jobs and download exports for completed jobs.</p>
      <div className="row">
        <div>
          <label>Status Filter</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">all</option>
            <option value="queued">queued</option>
            <option value="processing">processing</option>
            <option value="needs_review">needs_review</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="expired">expired</option>
          </select>
        </div>
        <div>
          <label>Navigation</label>
          <Link href="/">Back to Submit Page</Link>
        </div>
      </div>
      {loading ? <p className="muted">Loading jobs...</p> : null}
      {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
      <section className="card">
        <h2>Recent Jobs</h2>
        {jobs.length === 0 ? <p className="muted">No jobs found.</p> : null}
        {jobs.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table className="historyTable">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Provider</th>
                  <th>Profile</th>
                  <th>Process</th>
                  <th>Created</th>
                  <th>Error</th>
                  <th>Exports</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{job.id}</td>
                    <td>{job.status}</td>
                    <td>{job.provider}</td>
                    <td>{job.processing_profile}</td>
                    <td>{job.process_name ?? "-"}</td>
                    <td>{new Date(job.created_at).toLocaleString()}</td>
                    <td>{job.error_code ?? "-"}</td>
                    <td>
                      {job.status === "completed" ? (
                        <span className="historyLinks">
                          <a href={`${apiBase}/api/jobs/${job.id}/exports/md`} target="_blank" rel="noreferrer">
                            md
                          </a>
                          <a href={`${apiBase}/api/jobs/${job.id}/exports/json`} target="_blank" rel="noreferrer">
                            json
                          </a>
                          <a href={`${apiBase}/api/jobs/${job.id}/exports/pdf`} target="_blank" rel="noreferrer">
                            pdf
                          </a>
                          <a href={`${apiBase}/api/jobs/${job.id}/exports/docx`} target="_blank" rel="noreferrer">
                            docx
                          </a>
                        </span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td>
                      {job.status === "needs_review" ? (
                        <span className="historyLinks">
                          <Link href={`/?job_id=${job.id}`}>view</Link>
                          <button type="button" onClick={() => finalizeFromHistory(job.id)}>
                            finalize
                          </button>
                        </span>
                      ) : job.status === "completed" ? (
                        <Link href={`/?job_id=${job.id}`}>view</Link>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </main>
  );
}
