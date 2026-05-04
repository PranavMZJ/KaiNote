"use client";

import React, { FormEvent, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/auth/useAuth";

export default function LoginPage() {
  const { signIn, isAuthenticated, user, isLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [justSignedIn, setJustSignedIn] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await signIn(email, password);
      setJustSignedIn(true);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Sign in failed. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  // Show loading state while checking session
  if (isLoading) {
    return (
      <main style={pageStyle}>
        <div className="glass-panel" style={cardStyle}>
          <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
            <div className="spinner" style={{ width: 32, height: 32, margin: "0 auto var(--space-4)" }} />
            <p style={{ color: "var(--text-secondary)" }}>Loading...</p>
          </div>
        </div>
      </main>
    );
  }

  // Show success state after sign-in or if already authenticated
  if (isAuthenticated || justSignedIn) {
    return (
      <main style={pageStyle}>
        <div className="glass-panel fade-in-up" style={cardStyle}>
          <h1 style={headingStyle}>Welcome!</h1>
          <p style={subtextStyle}>
            Signed in as <strong style={{ color: "var(--text-primary)" }}>{user?.email || email}</strong>
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-4)" }}>
            <a
              href="/capture"
              className="btn-primary"
              style={{ width: "100%", textAlign: "center", textDecoration: "none", padding: "var(--space-3) var(--space-6)" }}
            >
              Start Meeting Capture
            </a>
            <a
              href="/meetings"
              className="btn-secondary"
              style={{ width: "100%", textAlign: "center", textDecoration: "none", padding: "var(--space-3) var(--space-6)" }}
            >
              View Meetings
            </a>
          </div>
        </div>
      </main>
    );
  }

  // Show login form
  return (
    <main style={pageStyle}>
      <div className="glass-panel fade-in-up" style={cardStyle}>
        <h1 style={headingStyle}>Sign In</h1>
        <p style={subtextStyle}>Welcome back to KaiNote</p>

        <form onSubmit={handleSubmit} style={formStyle}>
          <label htmlFor="login-email" style={labelStyle}>
            Email
          </label>
          <input
            id="login-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            style={inputStyle}
          />

          <label htmlFor="login-password" style={labelStyle}>
            Password
          </label>
          <input
            id="login-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            style={inputStyle}
          />

          {error && (
            <p role="alert" style={errorStyle}>
              {error}
            </p>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={isSubmitting}
            style={{ width: "100%", marginTop: "var(--space-2)" }}
          >
            {isSubmitting ? (
              <span style={spinnerWrapStyle}>
                <span style={spinnerStyle} aria-hidden="true" />
                Signing in…
              </span>
            ) : (
              "Sign In"
            )}
          </button>
        </form>

        <p style={footerStyle}>
          Don&apos;t have an account?{" "}
          <Link href="/register" style={linkStyle}>
            Create Account
          </Link>
        </p>
      </div>
    </main>
  );
}

/* ---------- Inline styles using design tokens ---------- */

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--bg-primary)",
  padding: "var(--space-4)",
};

const cardStyle: React.CSSProperties = {
  width: "100%",
  maxWidth: "420px",
  padding: "var(--space-8)",
};

const headingStyle: React.CSSProperties = {
  fontSize: "var(--text-h1)",
  fontWeight: 700,
  color: "var(--text-primary)",
  letterSpacing: "var(--letter-spacing-tight)",
  marginBottom: "var(--space-2)",
};

const subtextStyle: React.CSSProperties = {
  fontSize: "var(--text-small)",
  color: "var(--text-secondary)",
  marginBottom: "var(--space-6)",
};

const formStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "var(--space-3)",
};

const labelStyle: React.CSSProperties = {
  fontSize: "var(--text-small)",
  fontWeight: 500,
  color: "var(--text-secondary)",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "var(--space-3) var(--space-4)",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-subtle)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  fontSize: "var(--text-body)",
  fontFamily: "var(--font-body)",
  outline: "none",
  transition: "border-color var(--duration-fast) var(--ease-out)",
};

const errorStyle: React.CSSProperties = {
  color: "var(--error)",
  fontSize: "var(--text-small)",
  margin: 0,
};

const spinnerWrapStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "var(--space-2)",
};

const spinnerStyle: React.CSSProperties = {
  display: "inline-block",
  width: "16px",
  height: "16px",
  border: "2px solid rgba(255,255,255,0.3)",
  borderTopColor: "var(--accent-primary)",
  borderRadius: "50%",
  animation: "spin 0.6s linear infinite",
};

const footerStyle: React.CSSProperties = {
  textAlign: "center",
  marginTop: "var(--space-6)",
  fontSize: "var(--text-small)",
  color: "var(--text-secondary)",
};

const linkStyle: React.CSSProperties = {
  color: "var(--accent-primary)",
  fontWeight: 500,
};
