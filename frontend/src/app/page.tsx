"use client";

import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { useI18n } from "@/i18n";

export default function Home() {
  const { t } = useI18n();

  return (
    <div style={{ background: "var(--bg-primary)", minHeight: "100vh" }}>
      <Navbar />

      <main style={{ overflow: "hidden", position: "relative" }}>
        {/* Background glow effects */}
        <div style={{
          position: "absolute", top: "-10%", left: "50%", transform: "translateX(-50%)",
          width: "800px", height: "800px", borderRadius: "50%",
          background: "radial-gradient(circle, rgba(108,92,231,0.1) 0%, transparent 60%)",
          pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", bottom: "10%", right: "-5%",
          width: "500px", height: "500px", borderRadius: "50%",
          background: "radial-gradient(circle, rgba(1,168,141,0.07) 0%, transparent 60%)",
          pointerEvents: "none",
        }} />

        {/* ============ HERO SECTION ============ */}
        <section style={{
          padding: "var(--space-24) var(--space-8) var(--space-16)",
          display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
          position: "relative",
        }}>
          {/* Animated waveform graphic */}
          <div style={{ marginBottom: "var(--space-8)", position: "relative" }}>
            <svg width="280" height="80" viewBox="0 0 280 80" fill="none" style={{ opacity: 0.9 }}>
              {/* Waveform bars with staggered animation */}
              {[
                { x: 10, h: 30 }, { x: 22, h: 50 }, { x: 34, h: 70 }, { x: 46, h: 45 },
                { x: 58, h: 60 }, { x: 70, h: 35 }, { x: 82, h: 55 }, { x: 94, h: 75 },
                { x: 106, h: 40 }, { x: 118, h: 65 }, { x: 130, h: 50 }, { x: 142, h: 30 },
                { x: 154, h: 55 }, { x: 166, h: 70 }, { x: 178, h: 45 }, { x: 190, h: 60 },
                { x: 202, h: 35 }, { x: 214, h: 50 }, { x: 226, h: 65 }, { x: 238, h: 40 },
                { x: 250, h: 55 }, { x: 262, h: 30 },
              ].map((bar, i) => (
                <rect
                  key={i}
                  x={bar.x}
                  y={40 - bar.h / 2}
                  width="8"
                  height={bar.h}
                  rx="4"
                  fill={i < 11 ? "var(--accent-primary)" : "rgba(108,92,231,0.3)"}
                />
              ))}
              {/* Arrow indicating transformation */}
              <path d="M135 78 L145 78 L140 84 Z" fill="var(--accent-primary)" opacity="0.6" />
            </svg>
            {/* Document icon below waveform */}
            <div style={{
              marginTop: "var(--space-2)", display: "flex", justifyContent: "center",
            }}>
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <rect x="8" y="4" width="24" height="32" rx="3" stroke="var(--accent-primary)" strokeWidth="2" fill="rgba(108,92,231,0.08)" />
                <line x1="13" y1="14" x2="27" y2="14" stroke="var(--accent-primary)" strokeWidth="1.5" strokeLinecap="round" opacity="0.7" />
                <line x1="13" y1="19" x2="24" y2="19" stroke="var(--accent-primary)" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
                <line x1="13" y1="24" x2="22" y2="24" stroke="var(--accent-primary)" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
                <line x1="13" y1="29" x2="20" y2="29" stroke="var(--accent-primary)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
              </svg>
            </div>
          </div>

          <h1 style={{
            fontSize: "clamp(2.5rem, 7vw, 4rem)", fontWeight: 700,
            letterSpacing: "-0.04em", color: "var(--text-primary)",
            marginBottom: "var(--space-4)", lineHeight: 1.1,
          }}>
            {t("home.hero.title1")}<br />
            <span style={{ color: "var(--accent-primary)" }}>{t("home.hero.title2")}</span>
          </h1>

          <p style={{
            fontSize: "var(--text-h3)", color: "var(--text-secondary)",
            maxWidth: "560px", lineHeight: 1.6, marginBottom: "var(--space-8)",
          }}>
            {t("home.hero.subtitle")}
          </p>

          <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap", justifyContent: "center" }}>
            <Link href="/register" className="btn-primary" style={{
              padding: "var(--space-3) var(--space-8)", fontWeight: 600,
              textDecoration: "none", fontSize: "var(--text-body)",
            }}>
              {t("home.cta.start")}
            </Link>
            <Link href="/login" className="btn-secondary" style={{
              padding: "var(--space-3) var(--space-8)", fontWeight: 500,
              textDecoration: "none", fontSize: "var(--text-body)",
            }}>
              {t("home.cta.signIn")}
            </Link>
          </div>
        </section>

        {/* ============ FEATURES SECTION ============ */}
        <section style={{
          padding: "var(--space-16) var(--space-8)",
          maxWidth: "1100px", margin: "0 auto",
        }}>
          <h2 style={{
            fontSize: "var(--text-h2)", fontWeight: 600, color: "var(--text-primary)",
            textAlign: "center", marginBottom: "var(--space-12)",
            letterSpacing: "var(--letter-spacing-tight)",
          }}>
            {t("home.features.title")}
          </h2>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "var(--space-6)",
          }}>
            {/* Feature 1 */}
            <div className="glass-panel" style={{ padding: "var(--space-6)" }}>
              <div style={{ fontSize: "28px", marginBottom: "var(--space-3)" }}>🎙️</div>
              <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
                {t("home.features.transcription.title")}
              </h3>
              <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {t("home.features.transcription.desc")}
              </p>
            </div>

            {/* Feature 2 */}
            <div className="glass-panel" style={{ padding: "var(--space-6)" }}>
              <div style={{ fontSize: "28px", marginBottom: "var(--space-3)" }}>🌐</div>
              <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
                {t("home.features.translation.title")}
              </h3>
              <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {t("home.features.translation.desc")}
              </p>
            </div>

            {/* Feature 3 */}
            <div className="glass-panel" style={{ padding: "var(--space-6)" }}>
              <div style={{ fontSize: "28px", marginBottom: "var(--space-3)" }}>🤖</div>
              <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
                {t("home.features.reports.title")}
              </h3>
              <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {t("home.features.reports.desc")}
              </p>
            </div>

            {/* Feature 4 */}
            <div className="glass-panel" style={{ padding: "var(--space-6)" }}>
              <div style={{ fontSize: "28px", marginBottom: "var(--space-3)" }}>📋</div>
              <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
                {t("home.features.followups.title")}
              </h3>
              <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {t("home.features.followups.desc")}
              </p>
            </div>

            {/* Feature 5 */}
            <div className="glass-panel" style={{ padding: "var(--space-6)" }}>
              <div style={{ fontSize: "28px", marginBottom: "var(--space-3)" }}>🔗</div>
              <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
                {t("home.features.rag.title")}
              </h3>
              <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {t("home.features.rag.desc")}
              </p>
            </div>

            {/* Feature 6 */}
            <div className="glass-panel" style={{ padding: "var(--space-6)" }}>
              <div style={{ fontSize: "28px", marginBottom: "var(--space-3)" }}>📧</div>
              <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
                {t("home.features.notifications.title")}
              </h3>
              <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {t("home.features.notifications.desc")}
              </p>
            </div>
          </div>
        </section>

        {/* ============ HOW IT WORKS ============ */}
        <section style={{
          padding: "var(--space-16) var(--space-8)",
          maxWidth: "900px", margin: "0 auto",
        }}>
          <h2 style={{
            fontSize: "var(--text-h2)", fontWeight: 600, color: "var(--text-primary)",
            textAlign: "center", marginBottom: "var(--space-12)",
            letterSpacing: "var(--letter-spacing-tight)",
          }}>
            {t("home.howItWorks.title")}
          </h2>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-8)" }}>
            {([
              { step: "1", title: t("home.howItWorks.step1.title"), desc: t("home.howItWorks.step1.desc") },
              { step: "2", title: t("home.howItWorks.step2.title"), desc: t("home.howItWorks.step2.desc") },
              { step: "3", title: t("home.howItWorks.step3.title"), desc: t("home.howItWorks.step3.desc") },
              { step: "4", title: t("home.howItWorks.step4.title"), desc: t("home.howItWorks.step4.desc") },
            ]).map((item) => (
              <div key={item.step} style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
                <div style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  background: "rgba(108,92,231,0.15)", border: "1px solid var(--accent-primary)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "var(--text-small)", fontWeight: 700, color: "var(--accent-primary)",
                  flexShrink: 0,
                }}>
                  {item.step}
                </div>
                <div>
                  <h3 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "4px" }}>
                    {item.title}
                  </h3>
                  <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                    {item.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ============ TECH STACK SECTION ============ */}
        <section style={{
          padding: "var(--space-12) var(--space-8) var(--space-16)",
          textAlign: "center",
        }}>
          <p style={{
            fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
            textTransform: "uppercase", letterSpacing: "var(--letter-spacing-wide)",
            marginBottom: "var(--space-4)",
          }}>
            {t("home.poweredBy")}
          </p>
          <div style={{
            display: "flex", gap: "var(--space-4)", flexWrap: "wrap", justifyContent: "center",
            maxWidth: "700px", margin: "0 auto",
          }}>
            {[
              "Amazon Transcribe", "Amazon Bedrock", "Amazon Translate",
              "AWS Step Functions", "ECS", "CloudFront", "Cognito", "DynamoDB",
            ].map((service) => (
              <span key={service} style={{
                padding: "var(--space-1) var(--space-3)",
                fontSize: "var(--text-xs)", fontWeight: 500,
                color: "var(--text-tertiary)",
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "999px",
              }}>
                {service}
              </span>
            ))}
          </div>
        </section>

        {/* ============ FOOTER ============ */}
        <footer style={{
          padding: "var(--space-6) var(--space-8)",
          borderTop: "1px solid var(--border-subtle)",
          textAlign: "center",
        }}>
          <p style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
            {t("home.footer")}
          </p>
        </footer>
      </main>
    </div>
  );
}
