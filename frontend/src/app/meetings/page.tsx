"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/auth/useAuth";
import { ReportRenderer, type MinutesReport } from "@/components/ReportRenderer";
import { ExportControls } from "@/components/ExportControls";

interface Meeting {
  meetingId: string;
  meeting_title?: string;
  status: "pending" | "processing" | "completed" | "failed";
  createdAt: string;
  updatedAt?: string;
}

const STATUS_STYLES: Record<
  Meeting["status"],
  { bg: string; color: string; label: string; icon: string }
> = {
  pending: { bg: "rgba(142,142,147,0.15)", color: "var(--text-secondary)", label: "Pending", icon: "⏳" },
  processing: { bg: "rgba(108,92,231,0.15)", color: "var(--accent-primary)", label: "Processing", icon: "⚙️" },
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
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);
  const [report, setReport] = useState<MinutesReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

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
    } catch { setError("Failed to load meetings."); }
    finally { setLoading(false); }
  }, [getToken]);

  useEffect(() => { fetchMeetings(); }, [fetchMeetings]);

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
    try {
      const token = await getToken();
      if (!token) { setReportError("Authentication required."); setReportLoading(false); return; }
      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(`${apiUrl}/meetings/${meeting.meetingId}/report`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) { setReportError(response.status === 404 ? "Report not found." : "Failed to load report."); setReportLoading(false); return; }
      const data = await response.json();
      setReport(data.report || null);
    } catch { setReportError("Failed to load report."); }
    finally { setReportLoading(false); }
  }, [getToken]);

  const formatReportAsText = (r: MinutesReport): string => {
    const lines: string[] = [`# ${r.meeting_title}`, `Date: ${r.meeting_datetime}`, `Participants: ${r.participants.join(", ")}`, "", "## Summary", r.summary];
    if (r.decisions.length > 0) { lines.push("", "## Decisions"); r.decisions.forEach((d, i) => lines.push(`${i + 1}. ${d.decision}`)); }
    if (r.action_items.length > 0) { lines.push("", "## Action Items"); r.action_items.forEach((a, i) => lines.push(`${i + 1}. ${a.task} [${a.priority}] Owner: ${a.owner || "TBD"}`)); }
    return lines.join("\n");
  };

  if (loading) {
    return (
      <main style={{ background: "var(--bg-primary)", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" style={{ width: 32, height: 32, borderTopColor: "var(--accent-primary)" }} />
      </main>
    );
  }

  const hasSelection = selectedMeetingId !== null;

  return (
    <main style={{ background: "var(--bg-primary)", minHeight: "100vh", paddingTop: "var(--space-12)", paddingLeft: "var(--space-6)", paddingRight: "var(--space-6)", paddingBottom: "var(--space-12)" }}>

      {/* Header */}
      <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "var(--text-h1)", fontWeight: 700, letterSpacing: "var(--letter-spacing-tight)", color: "var(--text-primary)" }}>
          Your Meetings
        </h1>
        <a href="/capture" className="btn-primary" style={{ textDecoration: "none", padding: "var(--space-2) var(--space-6)", fontSize: "var(--text-small)" }}>
          + New Capture
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
          <p style={{ fontSize: "var(--text-h3)", color: "var(--text-secondary)", fontWeight: 500 }}>No meetings yet</p>
          <p style={{ fontSize: "var(--text-small)", color: "var(--text-tertiary)", textAlign: "center", maxWidth: 320 }}>
            Start your first meeting capture to generate AI-powered minutes.
          </p>
          <a href="/capture" className="btn-primary" style={{ marginTop: "var(--space-4)", padding: "var(--space-3) var(--space-8)", fontWeight: 600, textDecoration: "none" }}>
            Start Meeting Capture
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
          }}>
            {meetings.map((meeting, i) => {
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
                        <span style={{ fontSize: "10px" }}>{style.icon}</span> {style.label}
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
                  onClick={() => { setSelectedMeetingId(null); setReport(null); setReportError(null); }}
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
                <ReportRenderer meetingId={selectedMeetingId} report={report} isLoading={reportLoading} />
              )}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
