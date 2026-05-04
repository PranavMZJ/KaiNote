import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-primary)",
        padding: "var(--space-8)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background glow effects */}
      <div
        style={{
          position: "absolute",
          top: "-20%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "600px",
          height: "600px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(108,92,231,0.08) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "-30%",
          right: "-10%",
          width: "400px",
          height: "400px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(1,168,141,0.06) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      {/* App name — typography-only, no logo */}
      <h1
        style={{
          fontSize: "clamp(3rem, 8vw, 5rem)",
          fontWeight: 700,
          letterSpacing: "-0.04em",
          color: "var(--text-primary)",
          marginBottom: "var(--space-4)",
          textAlign: "center",
        }}
      >
        Kai<span style={{ color: "var(--accent-primary)" }}>Note</span>
      </h1>

      {/* Tagline */}
      <p
        style={{
          fontSize: "var(--text-h3)",
          color: "var(--text-secondary)",
          maxWidth: "520px",
          textAlign: "center",
          lineHeight: 1.6,
          marginBottom: "var(--space-3)",
        }}
      >
        Turn conversations into structured meeting minutes — powered by AI.
      </p>

      {/* Feature pills */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          flexWrap: "wrap",
          justifyContent: "center",
          marginBottom: "var(--space-8)",
        }}
      >
        {["Live Capture", "Real-Time Transcription", "AI Summaries", "Action Items"].map((feature) => (
          <span
            key={feature}
            style={{
              padding: "var(--space-1) var(--space-3)",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
              color: "var(--text-tertiary)",
              background: "var(--bg-glass)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "999px",
            }}
          >
            {feature}
          </span>
        ))}
      </div>

      {/* CTA buttons */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-4)",
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

      {/* Built with badge */}
      <p
        style={{
          marginTop: "var(--space-16)",
          fontSize: "var(--text-xs)",
          color: "var(--text-tertiary)",
          letterSpacing: "var(--letter-spacing-wide)",
          textTransform: "uppercase",
        }}
      >
        Built on AWS · Serverless · Secure
      </p>
    </main>
  );
}
