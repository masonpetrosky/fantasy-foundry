import React, { useCallback, useState } from "react";
import { trackEvent } from "./analytics.js";

export function NewsletterSignup({ apiBase }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | success | error
  const [message, setMessage] = useState("");

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;

    setStatus("loading");
    setMessage("");
    try {
      const resp = await fetch(`${apiBase}/api/newsletter/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "Subscription failed.");
      }
      setStatus("success");
      setMessage("You're subscribed!");
      setEmail("");
      trackEvent("ff_newsletter_subscribe", { source: "footer" });
    } catch (err) {
      setStatus("error");
      setMessage(String(err.message || "Something went wrong."));
    }
  }, [apiBase, email]);

  if (status === "success") {
    return (
      <div className="newsletter-label">
        <p className="newsletter-status ok">{message}</p>
      </div>
    );
  }

  return (
    <div>
      <p className="newsletter-label">Get dynasty insights in your inbox</p>
      <form className="newsletter-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="newsletter-email">Email address</label>
        <input
          id="newsletter-email"
          type="email"
          placeholder="your@email.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          autoComplete="email"
        />
        <button type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Subscribing..." : "Subscribe"}
        </button>
      </form>
      {status === "error" && <p className="newsletter-status error">{message}</p>}
    </div>
  );
}
