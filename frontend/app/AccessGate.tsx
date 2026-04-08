"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { apiFetch } from "./api";

const authEnabled = (process.env.NEXT_PUBLIC_AUTH_ENABLED ?? "false").toLowerCase() === "true";
const guestTimeoutMinutes = Number(process.env.NEXT_PUBLIC_GUEST_ACCESS_TIMEOUT_MINUTES ?? "30");
const safeGuestTimeoutMinutes = Number.isFinite(guestTimeoutMinutes) && guestTimeoutMinutes > 0 ? guestTimeoutMinutes : 30;
const publicPaths = new Set(["/privacy"]);
type SessionRole = "owner" | "guest" | null;

export default function AccessGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [sessionRole, setSessionRole] = useState<SessionRole>(null);
  const [enteredCode, setEnteredCode] = useState("");
  const [error, setError] = useState("");
  const isPublicPath = pathname ? publicPaths.has(pathname) : false;

  useEffect(() => {
    if (!authEnabled) {
      setIsAuthorized(true);
      setIsCheckingSession(false);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 8000);

    async function loadSession() {
      try {
        const res = await apiFetch("/api/auth/session", { signal: controller.signal });
        if (!cancelled) {
          if (res.ok) {
            const payload = await res.json().catch(() => null);
            const role = payload?.data?.session?.role;
            setSessionRole(role === "owner" || role === "guest" ? role : null);
            setIsAuthorized(true);
          } else {
            setSessionRole(null);
            setIsAuthorized(false);
            setError("");
          }
        }
      } catch {
        if (!cancelled) {
          setIsAuthorized(false);
          setError("Cannot reach API. You can still enter access code once backend is reachable.");
        }
      } finally {
        if (!cancelled) {
          setIsCheckingSession(false);
        }
        window.clearTimeout(timeoutId);
      }
    }

    loadSession();
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, []);

  useEffect(() => {
    if (!authEnabled) return;
    if (!isAuthorized || sessionRole !== "guest") return;

    const intervalId = window.setInterval(() => {
      apiFetch("/api/auth/session")
        .then((res) => {
          if (res.status === 401 || res.status === 403) {
            setIsAuthorized(false);
            setSessionRole(null);
            setEnteredCode("");
            setError("Session expired. Enter the code again.");
          }
        })
        .catch(() => {
          // Keep the current session on transient network issues.
          setError("Cannot reach API right now. Retrying...");
        });
    }, 30000);

    return () => window.clearInterval(intervalId);
  }, [isAuthorized, sessionRole]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const res = await apiFetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: enteredCode }),
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        setError(payload?.error?.message ?? "Incorrect code.");
        return;
      }
      const role = payload?.data?.session?.role;
      setSessionRole(role === "owner" || role === "guest" ? role : null);
      setIsAuthorized(true);
      setEnteredCode("");
    } catch {
      setError("Cannot reach API.");
    }
  }

  if (!authEnabled || isAuthorized || isPublicPath) {
    return <>{children}</>;
  }

  return (
    <main className="gateShell">
      <section className="gateCard">
        <p className="gateEyebrow">Restricted Access</p>
        <h1>Enter Access Code</h1>
        <p className="muted">Owner access stays unlocked for the current browser session. Guest access expires after {safeGuestTimeoutMinutes} minutes.</p>
        {isCheckingSession ? <p className="muted">Checking active session...</p> : null}
        <form className="gateForm" onSubmit={handleSubmit}>
          <label htmlFor="access-code">Access Code</label>
          <input
            id="access-code"
            type="password"
            value={enteredCode}
            onChange={(event) => setEnteredCode(event.target.value)}
            autoComplete="off"
            autoFocus
            disabled={isCheckingSession}
          />
          <button type="submit" disabled={isCheckingSession}>
            Enter
          </button>
        </form>
        {error ? <p className="gateError">{error}</p> : null}
      </section>
    </main>
  );
}
