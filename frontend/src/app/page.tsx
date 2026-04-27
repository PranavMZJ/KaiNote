import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "var(--space-24) var(--space-8)",
        gap: "var(--space-6)",
      }}
    >
      <h1
        style={{
          fontSize: "var(--text-hero)",
          fontWeight: 700,
          letterSpacing: "var(--letter-spacing-tight)",
          color: "var(--text-primary)",
        }}
      >
        Meeting Minutes
      </h1>
      <p
        style={{
          fontSize: "var(--text-h3)",
          color: "var(--text-secondary)",
          maxWidth: "480px",
          textAlign: "center",
        }}
      >
        AI-powered meeting capture, transcription, and structured report
        generation.
      </p>
      <div
        style={{
          display: "flex",
          gap: "var(--space-4)",
          marginTop: "var(--space-8)",
        }}
      >
        <Link
          href="/login"
          className="btn-primary"
          style={{
            padding: "var(--space-3) var(--space-8)",
            fontWeight: 600,
            textDecoration: "none",
            fontSize: "var(--text-body)",
          }}
        >
          Sign In
        </Link>
        <Link
          href="/register"
          className="btn-secondary"
          style={{
            padding: "var(--space-3) var(--space-8)",
            fontWeight: 500,
            textDecoration: "none",
            fontSize: "var(--text-body)",
          }}
        >
          Create Account
        </Link>
      </div>
    </main>
  );
}
