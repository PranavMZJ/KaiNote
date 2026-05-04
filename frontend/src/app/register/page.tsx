"use client";

import React, { FormEvent, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/auth/useAuth";

type Step = "register" | "verify";

export default function RegisterPage() {
  const { signUp, confirmSignUp } = useAuth();

  const [step, setStep] = useState<Step>("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await signUp(email, password, name);
      setStep("verify");
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Registration failed. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleVerify(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await confirmSignUp(email, code);
      window.location.href = "/login";
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Verification failed. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-primary)",
        padding: "var(--space-4)",
      }}
    >
      <div className="glass-panel fade-in-up" style={cardStyle}>
        {step === "register" ? (
          <>
            <h1 style={headingStyle}>Create Account</h1>
            <p style={subtextStyle}>
              Get started with KaiNote
            </p>

            <form onSubmit={handleRegister} style={formStyle}>
              <label htmlFor="register-name" style={labelStyle}>
                Name
              </label>
              <input
                id="register-name"
                type="text"
                required
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                style={inputStyle}
              />

              <label htmlFor="register-email" style={labelStyle}>
                Email
              </label>
              <input
                id="register-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                style={inputStyle}
              />

              <label htmlFor="register-password" style={labelStyle}>
                Password
              </label>
              <input
                id="register-password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={inputStyle}
              />
              <p style={hintStyle}>
                Min 8 characters, uppercase, lowercase, number, and symbol
              </p>

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
                    Creating account…
                  </span>
                ) : (
                  "Create Account"
                )}
              </button>
            </form>

            <p style={footerStyle}>
              Already have an account?{" "}
              <Link href="/login" style={linkStyle}>
                Back to Login
              </Link>
            </p>
          </>
        ) : (
          <>
            <h1 style={headingStyle}>Verify Email</h1>
            <p style={subtextStyle}>
              We sent a verification code to{" "}
              <strong style={{ color: "var(--text-primary)" }}>{email}</strong>
            </p>

            <form onSubmit={handleVerify} style={formStyle}>
              <label htmlFor="verify-code" style={labelStyle}>
                Verification Code
              </label>
              <input
                id="verify-code"
                type="text"
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="123456"
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
                    Verifying…
                  </span>
                ) : (
                  "Verify Email"
                )}
              </button>
            </form>

            <p style={footerStyle}>
              <Link href="/login" style={linkStyle}>
                Back to Login
              </Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}

/* ---------- Inline styles using design tokens ---------- */

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

const hintStyle: React.CSSProperties = {
  fontSize: "var(--text-xs)",
  color: "var(--text-tertiary)",
  margin: 0,
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
