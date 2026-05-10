"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/auth/useAuth";
import { ReportRenderer, type MinutesReport } from "@/components/ReportRenderer";
import { ExportControls } from "@/components/ExportControls";
import { AgentActionsPanel } from "@/components/AgentActionsPanel";
import { Navbar } from "@/components/Navbar";
import { useI18n } from "@/i18n";
import type { AgentReport } from "@/api/client";

interface Meeting {
  meetingId: string;
  meeting_title?: string;
  status: "pending" | "processing" | "completed" | "failed";
  createdAt: string;
  updatedAt?: string;
}

const STATUS_STYLES: Record<
  Meeting["status"],
  { bg: string; color: string; label: string; icon: string; spin?: boolean }
> = {
  pending: { bg: "rgba(142,142,147,0.15)", color: "var(--text-secondary)", label: "Pending", icon: "⏳" },
  processing: { bg: "rgba(108,92,231,0.15)", color: "var(--accent-primary)", label: "Processing", icon: "⚙️", spin: true },
  completed: { bg: "rgba(52,199,89,0.15)", color: "var(--success)", label: "Completed", icon: "✓" },
  failed: { bg: "rgba(255,69,58,0.15)", color: "var(--error)", label: "Failed", icon: "✗" },
};

function formatMeetingLabel(meeting: Meeting, index: number): string {
  const date = new Date(meeting.createdAt);
  const timeStr = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const dateStr = date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return meeting.meeting_title || `Meeting #${index + 1} — ${dateStr} ${timeStr}`;
}

export default function MeetingsPage() {
  const { getToken } = useAuth();
  const { t } = useI18n();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);
  const [report, setReport] = useState<MinutesReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [agentReport, setAgentReport] = useState<AgentReport | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; right: number } | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | Meeting["status"]>("all");
  const [sortNewest, setSortNewest] = useState(true);
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchMeetings = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) { setError("Authentication required."); setLoading(false); return; }
      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(`${apiUrl}/meetings`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Failed");
      const data = (await response.json()) as { meetings?: Meeting[] };
      const sorted = (data.meetings ?? []).sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
      setMeetings(sorted);
      setError(null);
    } catch { setError("Failed to load meetings."); }
    finally { setLoading(false); }
  }, [getToken]);

  useEffect(() => { fetchMeetings(); }, [fetchMeetings]);

  // Auto-poll every 5 seconds while any meeting is processing/pending
  useEffect(() => {
    const hasProcessing = meetings.some(
      (m) => m.status === "processing" || m.status === "pending"
    );
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      fetchMeetings();
    }, 5000);

    return () => clearInterval(interval);
  }, [meetings, fetchMeetings]);

  const handleRetry = useCallback(async (meetingId: string) => {
    setRetrying(meetingId);
    try {
      const token = await getToken();
      if (!token) return;
      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      await fetch(`${apiUrl}/meetings/${meetingId}/retry`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      await fetchMeetings();
    } catch { /* retry silently */ }
    finally { setRetrying(null); }
  }, [getToken, fetchMeetings]);

  const handleCardClick = useCallback(async (meeting: Meeting) => {
    if (meeting.status !== "completed") return;
    setSelectedMeetingId(meeting.meetingId);
    setReport(null);
    setReportError(null);
    setReportLoading(true);
    setAgentReport(null);
    setAgentLoading(true);
    try {
      const token = await getToken();
      if (!token) { setReportError("Authentication required."); setReportLoading(false); setAgentLoading(false); return; }
      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(`${apiUrl}/meetings/${meeting.meetingId}/report`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) { setReportError(response.status === 404 ? "Report not found." : "Failed to load report."); setReportLoading(false); setAgentLoading(false); return; }
      const data = await response.json();
      setReport(data.report || null);

      // Fetch agent report (non-blocking)
      try {
        const agentResponse = await fetch(`${apiUrl}/meetings/${meeting.meetingId}/agent-report`, { headers: { Authorization: `Bearer ${token}` } });
        if (agentResponse.ok) {
          const agentData = await agentResponse.json();
          setAgentReport(agentData.agentReport || null);
        }
      } catch { /* agent report is optional */ }
    } catch { setReportError("Failed to load report."); }
    finally { setReportLoading(false); setAgentLoading(false); }
  }, [getToken]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    };
    if (menuOpenId) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpenId]);

  const handleDelete = useCallback(async (meetingId: string) => {
    setDeleting(meetingId);
    setConfirmDeleteId(null);
    setMenuOpenId(null);
    try {
      const token = await getToken();
      if (!token) return;
      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(`${apiUrl}/meetings/${meetingId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        // If the deleted meeting was selected, clear the selection
        if (selectedMeetingId === meetingId) {
          setSelectedMeetingId(null);
          setReport(null);
          setReportError(null);
          setAgentReport(null);
        }
        await fetchMeetings();
      }
    } catch { /* delete silently */ }
    finally { setDeleting(null); }
  }, [getToken, fetchMeetings, selectedMeetingId]);

  const handleDownloadReport = useCallback(async (meetingId: string) => {
    setMenuOpenId(null);
    try {
      const token = await getToken();
      if (!token) return;
      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(`${apiUrl}/meetings/${meetingId}/report`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json();
      if (!data.report) return;
      const blob = new Blob([JSON.stringify(data.report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `meeting-${meetingId.slice(0, 8)}-report.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch { /* download silently */ }
  }, [getToken]);

  const handleShare = useCallback(async (meeting: Meeting) => {
    setMenuOpenId(null);
    const title = meeting.meeting_title || `Meeting — ${new Date(meeting.createdAt).toLocaleDateString()}`;
    const text = `KaiNote Meeting: ${title}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: "KaiNote", text });
      } catch { /* user cancelled */ }
    } else {
      // Fallback: copy meeting info to clipboard
      try {
        await navigator.clipboard.writeText(text);
      } catch { /* clipboard failed */ }
    }
  }, []);

  const formatReportAsText = (r: MinutesReport): string => {
    const lines: string[] = [`# ${r.meeting_title}`, `Date: ${r.meeting_datetime}`, `Participants: ${r.participants.join(", ")}`, "", "## Summary", r.summary];
    if (r.decisions.length > 0) { lines.push("", "## Decisions"); r.decisions.forEach((d, i) => lines.push(`${i + 1}. ${d.decision}`)); }
    if (r.action_items.length > 0) { lines.push("", "## Action Items"); r.action_items.forEach((a, i) => lines.push(`${i + 1}. ${a.task} [${a.priority}] Owner: ${a.owner || "TBD"}`)); }
    return lines.join("\n");
  };

  // Filter and sort meetings
  const filteredMeetings = meetings.filter((m, idx) => {
    // Status filter
    if (statusFilter !== "all" && m.status !== statusFilter) return false;
    // Text search (matches against displayed label, date, or meeting ID)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const label = formatMeetingLabel(m, idx).toLowerCase();
      const date = new Date(m.createdAt).toLocaleDateString().toLowerCase();
      const fullDate = new Date(m.createdAt).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }).toLowerCase();
      if (!label.includes(q) && !date.includes(q) && !fullDate.includes(q) && !m.meetingId.toLowerCase().includes(q)) return false;
    }
    return true;
  }).sort((a, b) => {
    const diff = new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    return sortNewest ? diff : -diff;
  });

  if (loading) {
    return (
      <>
      <Navbar />
      <main style={{ background: "var(--bg-primary)", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" style={{ width: 32, height: 32, borderTopColor: "var(--accent-primary)" }} />
      </main>
      </>
    );
  }

  const hasSelection = selectedMeetingId !== null;

  return (
    <>
    <Navbar />
    <main style={{ background: "var(--bg-primary)", minHeight: "100vh", paddingTop: "var(--space-12)", paddingLeft: "var(--space-6)", paddingRight: "var(--space-6)", paddingBottom: "var(--space-12)" }}>

      {/* Header */}
      <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "var(--text-h1)", fontWeight: 700, letterSpacing: "var(--letter-spacing-tight)", color: "var(--text-primary)" }}>
          {t("meetings.title")}
        </h1>
        <a href="/capture" className="btn-primary" style={{ textDecoration: "none", padding: "var(--space-2) var(--space-6)", fontSize: "var(--text-small)" }}>
          {t("meetings.newCapture")}
        </a>
      </div>

      {error && (
        <div className="elevated-card" role="alert" style={{ maxWidth: 1400, margin: "0 auto var(--space-6)", borderColor: "var(--error)", color: "var(--error)", textAlign: "center" }}>
          {error}
        </div>
      )}

      {/* Empty state */}
      {meetings.length === 0 && !error && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "var(--space-24) var(--space-8)", gap: "var(--space-4)" }}>
          <p style={{ fontSize: "var(--text-h3)", color: "var(--text-secondary)", fontWeight: 500 }}>{t("meetings.empty.title")}</p>
          <p style={{ fontSize: "var(--text-small)", color: "var(--text-tertiary)", textAlign: "center", maxWidth: 320 }}>
            {t("meetings.empty.desc")}
          </p>
          <a href="/capture" className="btn-primary" style={{ marginTop: "var(--space-4)", padding: "var(--space-3) var(--space-8)", fontWeight: 600, textDecoration: "none" }}>
            {t("meetings.empty.cta")}
          </a>
        </div>
      )}

      {/* Split layout: list left, report right */}
      {meetings.length > 0 && (
        <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", gap: "var(--space-6)", alignItems: "flex-start" }}>

          {/* Left panel: meeting list */}
          <div style={{
            width: hasSelection ? "320px" : "100%",
            maxWidth: hasSelection ? "320px" : "720px",
            margin: hasSelection ? "0" : "0 auto",
            flexShrink: 0,
            transition: "width var(--duration-normal) var(--ease-out), max-width var(--duration-normal) var(--ease-out)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-3)",
            maxHeight: hasSelection ? "calc(100vh - 140px)" : "none",
            overflowY: hasSelection ? "auto" : "visible",
            position: "relative",
          }}>

            {/* Search and filter bar */}
            <div style={{
              display: "flex", gap: "var(--space-2)", flexWrap: "wrap", marginBottom: "var(--space-2)",
            }}>
              <input
                type="text"
                placeholder={t("meetings.search")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  flex: 1, minWidth: "140px",
                  background: "var(--bg-elevated)", color: "var(--text-primary)",
                  border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-2) var(--space-3)", fontSize: "var(--text-small)",
                  outline: "none",
                }}
              />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as "all" | Meeting["status"])}
                style={{
                  background: "var(--bg-elevated)", color: "var(--text-primary)",
                  border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-2) var(--space-2)", fontSize: "var(--text-xs)",
                  cursor: "pointer",
                }}
              >
                <option value="all">{t("meetings.all")}</option>
                <option value="completed">{t("meetings.completed")}</option>
                <option value="processing">{t("meetings.processing")}</option>
                <option value="failed">{t("meetings.failed")}</option>
                <option value="pending">{t("meetings.pending")}</option>
              </select>
              <button
                onClick={() => setSortNewest(!sortNewest)}
                title={sortNewest ? "Showing newest first" : "Showing oldest first"}
                style={{
                  background: "var(--bg-elevated)", color: "var(--text-tertiary)",
                  border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-2) var(--space-2)", fontSize: "var(--text-xs)",
                  cursor: "pointer", transition: "color var(--duration-fast)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-tertiary)")}
              >
                {sortNewest ? t("meetings.newest") : t("meetings.oldest")}
              </button>
            </div>

            {/* No results */}
            {filteredMeetings.length === 0 && (
              <p style={{ textAlign: "center", color: "var(--text-tertiary)", fontSize: "var(--text-small)", padding: "var(--space-4)" }}>
                {t("meetings.noResults")}
              </p>
            )}

            {filteredMeetings.map((meeting, i) => {
              const style = STATUS_STYLES[meeting.status];
              const isSelected = meeting.meetingId === selectedMeetingId;
              const isClickable = meeting.status === "completed";

              return (
                <div
                  key={meeting.meetingId}
                  className="fade-in-up"
                  role={isClickable ? "button" : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                  onClick={() => handleCardClick(meeting)}
                  onKeyDown={(e) => { if (isClickable && (e.key === "Enter" || e.key === " ")) handleCardClick(meeting); }}
                  style={{
                    background: isSelected ? "var(--bg-elevated)" : "var(--bg-secondary)",
                    border: isSelected ? "1px solid var(--accent-primary)" : "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: hasSelection ? "var(--space-3) var(--space-4)" : "var(--space-4) var(--space-6)",
                    cursor: isClickable ? "pointer" : "default",
                    transition: "all var(--duration-fast) var(--ease-out)",
                    animationDelay: `${i * 60}ms`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{
                        fontSize: hasSelection ? "var(--text-small)" : "var(--text-body)",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        marginBottom: "2px",
                      }}>
                        {formatMeetingLabel(meeting, i)}
                      </p>
                      <p style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
                        {new Date(meeting.createdAt).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </p>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexShrink: 0 }}>
                      <span style={{
                        display: "inline-flex", alignItems: "center", gap: "4px",
                        padding: "2px var(--space-2)", fontSize: "var(--text-xs)", fontWeight: 500,
                        borderRadius: "999px", background: style.bg, color: style.color, lineHeight: 1,
                      }}>
                        <span style={{
                          fontSize: "10px",
                          display: "inline-block",
                          animation: style.spin ? "spin 1.5s linear infinite" : "none",
                        }}>{style.icon}</span> {style.label}
                      </span>

                      {meeting.status === "failed" && (
                        <button
                          className="btn-secondary"
                          onClick={(e) => { e.stopPropagation(); handleRetry(meeting.meetingId); }}
                          disabled={retrying === meeting.meetingId}
                          style={{ padding: "2px var(--space-2)", fontSize: "var(--text-xs)", opacity: retrying === meeting.meetingId ? 0.6 : 1 }}
                        >
                          {retrying === meeting.meetingId ? "…" : "Retry"}
                        </button>
                      )}

                      {/* Three-dot menu */}
                      <div style={{ position: "relative" }} ref={menuOpenId === meeting.meetingId ? menuRef : undefined}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (menuOpenId === meeting.meetingId) {
                              setMenuOpenId(null);
                              setMenuPosition(null);
                            } else {
                              const rect = e.currentTarget.getBoundingClientRect();
                              setMenuPosition({ top: rect.top, right: window.innerWidth - rect.right });
                              setMenuOpenId(meeting.meetingId);
                            }
                          }}
                          style={{
                            background: "none", border: "none", cursor: "pointer",
                            padding: "2px 6px", borderRadius: "var(--radius-sm)",
                            color: "var(--text-tertiary)", fontSize: "16px", lineHeight: 1,
                            transition: "color var(--duration-fast) var(--ease-out)",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-tertiary)")}
                          aria-label="Meeting options"
                        >
                          ⋮
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right panel: report */}
          {hasSelection && (
            <div style={{
              flex: 1,
              minWidth: 0,
              maxHeight: "calc(100vh - 140px)",
              overflowY: "auto",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-lg)",
              padding: "var(--space-6)",
            }}>
              {/* Report header */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-6)", flexWrap: "wrap", gap: "var(--space-3)" }}>
                <button
                  className="btn-secondary"
                  onClick={() => { setSelectedMeetingId(null); setReport(null); setReportError(null); setAgentReport(null); }}
                  style={{ fontSize: "var(--text-small)", padding: "var(--space-1) var(--space-3)" }}
                >
                  ✕ Close
                </button>

                {report && (
                  <ExportControls meetingId={selectedMeetingId} formattedText={formatReportAsText(report)} />
                )}
              </div>

              {reportError ? (
                <div className="elevated-card" style={{ textAlign: "center", color: "var(--error)", borderColor: "var(--error)" }}>
                  <p>{reportError}</p>
                </div>
              ) : (
                <>
                  <ReportRenderer meetingId={selectedMeetingId} report={report} isLoading={reportLoading} />
                  <AgentActionsPanel agentReport={agentReport} isLoading={agentLoading} />
                </>
              )}
            </div>
          )}
        </div>
      )}
      {/* Fixed-position dropdown menu (rendered outside scroll container) */}
      {menuOpenId && menuPosition && (() => {
        const meeting = meetings.find((m) => m.meetingId === menuOpenId);
        if (!meeting) return null;
        return (
          <div
            ref={menuRef}
            style={{
              position: "fixed",
              top: menuPosition.top - 4,
              right: menuPosition.right,
              transform: "translateY(-100%)",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "var(--space-1) 0",
              boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
              zIndex: 1000,
              minWidth: "160px",
              animation: "fadeIn var(--duration-fast) var(--ease-out)",
            }}
          >
            {meeting.status === "completed" && (
              <button
                onClick={(e) => { e.stopPropagation(); handleDownloadReport(meeting.meetingId); }}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: "none", border: "none", cursor: "pointer",
                  padding: "var(--space-2) var(--space-3)", fontSize: "var(--text-small)",
                  color: "var(--text-primary)", transition: "background var(--duration-fast)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-secondary)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
              >
                📥 Download Report
              </button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); handleShare(meeting); }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: "none", border: "none", cursor: "pointer",
                padding: "var(--space-2) var(--space-3)", fontSize: "var(--text-small)",
                color: "var(--text-primary)", transition: "background var(--duration-fast)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-secondary)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
            >
              🔗 Share
            </button>
            <div style={{ height: "1px", background: "var(--border-subtle)", margin: "var(--space-1) 0" }} />
            <button
              onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(meeting.meetingId); setMenuOpenId(null); setMenuPosition(null); }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: "none", border: "none", cursor: "pointer",
                padding: "var(--space-2) var(--space-3)", fontSize: "var(--text-small)",
                color: "var(--error)", transition: "background var(--duration-fast)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,69,58,0.1)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
            >
              🗑️ Delete
            </button>
          </div>
        );
      })()}

      {/* Delete confirmation modal */}
      {confirmDeleteId && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 100,
            background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
            display: "flex", alignItems: "center", justifyContent: "center",
            animation: "fadeIn var(--duration-fast) var(--ease-out)",
          }}
          onClick={() => setConfirmDeleteId(null)}
        >
          <div
            className="elevated-card"
            onClick={(e) => e.stopPropagation()}
            style={{
              maxWidth: 400, width: "90%", padding: "var(--space-6)",
              background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)",
            }}
          >
            <h3 style={{ fontSize: "var(--text-h3)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-3)" }}>
              Delete Meeting?
            </h3>
            <p style={{ fontSize: "var(--text-small)", color: "var(--text-secondary)", marginBottom: "var(--space-6)", lineHeight: 1.5 }}>
              This will permanently delete the meeting, its transcript, report, and all associated data. This action cannot be undone.
            </p>
            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
              <button
                className="btn-secondary"
                onClick={() => setConfirmDeleteId(null)}
                style={{ padding: "var(--space-2) var(--space-4)", fontSize: "var(--text-small)" }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDeleteId)}
                disabled={deleting === confirmDeleteId}
                style={{
                  padding: "var(--space-2) var(--space-4)", fontSize: "var(--text-small)",
                  background: "var(--error)", color: "white", border: "none",
                  borderRadius: "var(--radius-md)", cursor: "pointer", fontWeight: 500,
                  opacity: deleting === confirmDeleteId ? 0.6 : 1,
                }}
              >
                {deleting === confirmDeleteId ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
    </>
  );
}
