import React, { useState } from "react";

export function AccountPanel({
  authEnabled,
  authReady,
  authUser,
  authStatus,
  cloudStatus,
  onSignIn,
  onSignUp,
  onSignOut,
}) {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const statusText = String(authUser ? cloudStatus : authStatus || "").trim();
  const statusLower = statusText.toLowerCase();
  const statusTone = statusLower.includes("error") || statusLower.includes("failed")
    ? "error"
    : statusLower.includes("saved") || statusLower.includes("loaded") || statusLower.includes("enabled") || statusLower.includes("signed in")
      ? "ok"
      : "";

  async function handleSubmit(event) {
    event.preventDefault();
    if (!authEnabled || !authReady || submitting) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) return;

    setSubmitting(true);
    try {
      if (mode === "signup") {
        await onSignUp(normalizedEmail, normalizedPassword);
      } else {
        await onSignIn(normalizedEmail, normalizedPassword);
      }
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onSignOut();
    } finally {
      setSubmitting(false);
    }
  }

  if (!authEnabled) {
    return (
      <section className="account-card" aria-live="polite">
        <div className="account-head">
          <h3>Account Sync</h3>
        </div>
        <p className="account-note">
          Account login is currently disabled for this deployment. Configure Supabase to enable saved cross-device settings.
        </p>
      </section>
    );
  }

  return (
    <section className="account-card" aria-live="polite">
      <div className="account-head">
        <h3>Account Sync</h3>
        {authUser && <span className="account-user">{authUser.email || "Signed in"}</span>}
      </div>

      {!authReady && (
        <p className="account-note">Checking existing session...</p>
      )}

      {authReady && !authUser && (
        <form className="account-form" onSubmit={handleSubmit}>
          <label className="account-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={event => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label className="account-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              minLength={8}
              required
            />
          </label>
          <div className="account-actions">
            <button type="submit" className="inline-btn" disabled={submitting}>
              {submitting ? "Working..." : mode === "signup" ? "Create Account" : "Sign In"}
            </button>
            <button
              type="button"
              className="inline-btn"
              onClick={() => setMode(current => (current === "signup" ? "signin" : "signup"))}
              disabled={submitting}
            >
              {mode === "signup" ? "Use Existing Login" : "Create New Login"}
            </button>
          </div>
        </form>
      )}

      {authReady && authUser && (
        <div className="account-actions">
          <button type="button" className="inline-btn" onClick={handleSignOut} disabled={submitting}>
            {submitting ? "Signing Out..." : "Sign Out"}
          </button>
        </div>
      )}

      {statusText && (
        <p className={`account-status ${statusTone}`.trim()}>{statusText}</p>
      )}
    </section>
  );
}
