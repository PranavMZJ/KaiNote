"use client";

import Link from "next/link";
import { useAuth } from "@/auth/useAuth";
import { useI18n } from "@/i18n";
import { useEffect, useState } from "react";

export function Navbar() {
  const { isAuthenticated, signOut } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("kainote-theme") as "dark" | "light" | null;
    if (saved) {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    }
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("kainote-theme", next);
  };

  return (
    <nav style={{
      position: "sticky", top: 0, zIndex: 100,
      background: theme === "dark" ? "rgba(13,13,15,0.85)" : "rgba(255,255,255,0.85)",
      backdropFilter: "blur(12px)",
      borderBottom: "1px solid var(--border-subtle)",
      padding: "var(--space-3) var(--space-6)",
      display: "flex", alignItems: "center", justifyContent: "space-between",
    }}>
      {/* Logo */}
      <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        {/* Waveform icon */}
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" style={{ flexShrink: 0 }}>
          <rect width="28" height="28" rx="6" fill="var(--accent-primary)" fillOpacity="0.15" />
          <rect x="5" y="10" width="2.5" height="8" rx="1.25" fill="var(--accent-primary)" />
          <rect x="9" y="7" width="2.5" height="14" rx="1.25" fill="var(--accent-primary)" />
          <rect x="13" y="4" width="2.5" height="20" rx="1.25" fill="var(--accent-primary)" />
          <rect x="17" y="8" width="2.5" height="12" rx="1.25" fill="var(--accent-primary)" />
          <rect x="21" y="11" width="2.5" height="6" rx="1.25" fill="var(--accent-primary)" />
        </svg>
        <span style={{ fontSize: "var(--text-h3)", fontWeight: 700, letterSpacing: "-0.03em" }}>
          <span style={{ color: "var(--text-primary)" }}>Kai</span>
          <span style={{ color: "var(--accent-primary)" }}>Note</span>
        </span>
      </Link>

      {/* Nav links */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
        {isAuthenticated && (
          <>
            <Link href="/capture" style={{
              color: "var(--text-secondary)", textDecoration: "none",
              fontSize: "var(--text-small)", fontWeight: 500,
              transition: "color var(--duration-fast)",
            }}>
              {t("nav.capture")}
            </Link>
            <Link href="/meetings" style={{
              color: "var(--text-secondary)", textDecoration: "none",
              fontSize: "var(--text-small)", fontWeight: 500,
              transition: "color var(--duration-fast)",
            }}>
              {t("nav.meetings")}
            </Link>
          </>
        )}

        {/* Language toggle */}
        <button
          onClick={() => setLocale(locale === "en" ? "ja" : "en")}
          title={locale === "en" ? "日本語に切り替え" : "Switch to English"}
          style={{
            background: "none", border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)", padding: "var(--space-1) var(--space-2)",
            cursor: "pointer", fontSize: "var(--text-xs)", fontWeight: 500,
            color: "var(--text-secondary)", lineHeight: 1.4,
            transition: "border-color var(--duration-fast)",
          }}
        >
          {locale === "en" ? "🇯🇵 日本語" : "🇺🇸 EN"}
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          style={{
            background: "none", border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)", padding: "var(--space-1) var(--space-2)",
            cursor: "pointer", fontSize: "16px", lineHeight: 1,
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "border-color var(--duration-fast)",
          }}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>

        {isAuthenticated && (
          <button
            onClick={() => signOut()}
            style={{
              background: "none", border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)", padding: "var(--space-1) var(--space-3)",
              color: "var(--text-tertiary)", fontSize: "var(--text-xs)",
              cursor: "pointer", transition: "color var(--duration-fast), border-color var(--duration-fast)",
            }}
          >
            {t("nav.signOut")}
          </button>
        )}
        {!isAuthenticated && (
          <>
            <Link href="/login" style={{
              color: "var(--text-secondary)", textDecoration: "none",
              fontSize: "var(--text-small)", fontWeight: 500,
            }}>
              {t("nav.signIn")}
            </Link>
            <Link href="/register" className="btn-primary" style={{
              textDecoration: "none", padding: "var(--space-1) var(--space-4)",
              fontSize: "var(--text-small)",
            }}>
              {t("nav.getStarted")}
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
