"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import { apiFetch } from "./api";

const guestTimeoutMinutes = Number(process.env.NEXT_PUBLIC_GUEST_ACCESS_TIMEOUT_MINUTES ?? "30");
const safeGuestTimeoutMinutes = Number.isFinite(guestTimeoutMinutes) && guestTimeoutMinutes > 0 ? guestTimeoutMinutes : 30;

export default function AccessGate({ children }: { children: ReactNode }) {
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [enteredCode, setEnteredCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      try {
        const res = await apiFetch("/api/auth/session");
        if (!cancelled) {
          setIsAuthorized(res.ok);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setIsAuthorized(false);
          setError("Cannot reach API.");
        }
      } finally {
        if (!cancelled) {
          setIsInitialized(true);
        }
      }
    }

    loadSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isAuthorized) return;

    const intervalId = window.setInterval(() => {
      apiFetch("/api/auth/session")
        .then((res) => {
          if (!res.ok) {
            setIsAuthorized(false);
            setEnteredCode("");
            setError("Session expired. Enter the code again.");
          }
        })
        .catch(() => {
          setIsAuthorized(false);
          setError("Cannot reach API.");
        });
    }, 30000);

    return () => window.clearInterval(intervalId);
  }, [isAuthorized]);

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
      setIsAuthorized(true);
      setEnteredCode("");
    } catch {
      setError("Cannot reach API.");
    }
  }

  if (!isInitialized) {
    return <main className="gateShell" />;
  }

  if (isAuthorized) {
    return <>{children}</>;
  }

  return (
    <main className="gateShell">
      <section className="gateCard">
        <p className="gateEyebrow">Restricted Access</p>
        <h1>Enter Access Code</h1>
        <p className="muted">Owner access stays unlocked for the current browser session. Guest access expires after {safeGuestTimeoutMinutes} minutes.</p>
        <form className="gateForm" onSubmit={handleSubmit}>
          <label htmlFor="access-code">Access Code</label>
          <input
            id="access-code"
            type="password"
            value={enteredCode}
            onChange={(event) => setEnteredCode(event.target.value)}
            autoComplete="off"
            autoFocus
          />
          <button type="submit">Enter</button>
        </form>
        {error ? <p className="gateError">{error}</p> : null}
      </section>
    </main>
  );
}
