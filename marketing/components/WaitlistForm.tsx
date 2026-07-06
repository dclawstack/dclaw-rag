"use client";

import { useState } from "react";

type Status = "idle" | "loading" | "success" | "error";

export function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("error");
        setMessage(data.error ?? "Something went wrong. Please try again.");
        return;
      }
      setStatus("success");
      setMessage(
        data.alreadyJoined
          ? "You're already on the list — we'll email you at launch."
          : "You're on the list! We'll email you when the desktop app ships."
      );
    } catch {
      setStatus("error");
      setMessage("Network error. Please try again.");
    }
  }

  if (status === "success") {
    return (
      <p className="rounded-xl border border-brand-500/40 bg-brand-500/10 px-4 py-3 text-sm text-brand-300">
        {message}
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
      <label htmlFor="waitlist-email" className="sr-only">
        Email address
      </label>
      <input
        id="waitlist-email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        className="w-full rounded-pill border border-white/15 bg-white/[0.05] px-5 py-3 text-sm text-white placeholder:text-meta focus:border-brand-500"
      />
      <button
        type="submit"
        disabled={status === "loading"}
        className="rounded-pill bg-brand-500 px-6 py-3 text-sm font-semibold text-ink transition hover:bg-brand-400 disabled:opacity-60"
      >
        {status === "loading" ? "Saving…" : "Notify me at launch"}
      </button>
      {status === "error" && (
        <p className="text-sm text-red-400 sm:absolute sm:mt-14">{message}</p>
      )}
    </form>
  );
}
