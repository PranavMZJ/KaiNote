"use client";

import React from "react";
import type { AgentReport } from "@/api/client";

interface AgentActionsPanelProps {
  agentReport: AgentReport | null;
  isLoading?: boolean;
}

export function AgentActionsPanel({ agentReport, isLoading }: AgentActionsPanelProps) {
  if (isLoading) {
    return (
      <div className="glass-panel" style={{ padding: "var(--space-4)", marginTop: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <div className="spinner" style={{ width: 16, height: 16, borderTopColor: "var(--accent-primary)" }} />
          <span style={{ color: "var(--text-tertiary)", fontSize: "var(--text-small)" }}>Loading agent actions...</span>
        </div>
      </div>
    );
  }

  if (!agentReport) return null;

  const { notifications_sent, overdue_items, follow_up_suggestion } = agentReport;
  const hasContent = notifications_sent.length > 0 || overdue_items.length > 0 || follow_up_suggestion;

  if (!hasContent) return null;

  return (
    <div className="glass-panel" style={{ padding: "var(--space-6)", marginTop: "var(--space-6)" }}>
      {/* Header */}
      <h3 style={{
        fontSize: "var(--text-h3)",
        fontWeight: 600,
        color: "var(--text-primary)",
        marginBottom: "var(--space-4)",
        display: "flex",
        alignItems: "center",
        gap: "var(--space-2)",
      }}>
        🤖 Automated Actions
      </h3>

      <p style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginBottom: "var(--space-4)" }}>
        Executed at {new Date(agentReport.agent_execution_timestamp).toLocaleString()}
      </p>

      {/* Notifications Sent */}
      {notifications_sent.length > 0 && (
        <div style={{ marginBottom: "var(--space-5)" }}>
          <h4 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-3)" }}>
            📧 Notifications Sent ({notifications_sent.length})
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {notifications_sent.map((notif, i) => (
              <div
                key={i}
                style={{
                  background: "var(--bg-elevated)",
                  borderRadius: "var(--radius-sm)",
                  padding: "var(--space-3)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
                  <span style={{ fontSize: "var(--text-small)", fontWeight: 500, color: "var(--text-primary)" }}>
                    {notif.recipient}
                  </span>
                  <span style={{
                    fontSize: "var(--text-xs)",
                    padding: "1px var(--space-2)",
                    borderRadius: "999px",
                    background: notif.priority === "high" ? "rgba(255,69,58,0.15)" : "rgba(108,92,231,0.15)",
                    color: notif.priority === "high" ? "var(--error)" : "var(--accent-primary)",
                    fontWeight: 500,
                  }}>
                    {notif.priority}
                  </span>
                </div>
                <p style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginTop: "2px" }}>
                  {notif.task}
                </p>
                {notif.due_date && (
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginTop: "2px" }}>
                    Due: {notif.due_date}
                  </p>
                )}
                {notif.error && (
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--error)", marginTop: "2px" }}>
                    ⚠️ {notif.error}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Overdue Items */}
      {overdue_items.length > 0 && (
        <div style={{ marginBottom: "var(--space-5)" }}>
          <h4 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--warning, #f0a500)", marginBottom: "var(--space-3)" }}>
            ⚠️ Overdue Items ({overdue_items.length})
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {overdue_items.map((item, i) => (
              <div
                key={i}
                style={{
                  background: "var(--bg-elevated)",
                  borderRadius: "var(--radius-sm)",
                  padding: "var(--space-3)",
                  border: "1px solid rgba(255,159,10,0.3)",
                  borderLeft: "3px solid rgba(255,159,10,0.8)",
                }}
              >
                <p style={{ fontSize: "var(--text-small)", fontWeight: 500, color: "var(--text-primary)" }}>
                  {item.original_task}
                </p>
                <div style={{ display: "flex", gap: "var(--space-4)", marginTop: "4px", flexWrap: "wrap" }}>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
                    Owner: {item.original_owner}
                  </span>
                  {item.original_due_date && (
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--error)" }}>
                      Due: {item.original_due_date}
                    </span>
                  )}
                  <span style={{
                    fontSize: "var(--text-xs)",
                    padding: "0 var(--space-1)",
                    borderRadius: "var(--radius-sm)",
                    background: item.status === "overdue" ? "rgba(255,69,58,0.15)" : "rgba(255,159,10,0.15)",
                    color: item.status === "overdue" ? "var(--error)" : "rgba(255,159,10,1)",
                  }}>
                    {item.status}
                  </span>
                </div>
                {item.current_meeting_reference && (
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginTop: "4px", fontStyle: "italic" }}>
                    Referenced: {item.current_meeting_reference}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Follow-Up Suggestion */}
      {follow_up_suggestion && follow_up_suggestion.recommended && (
        <div>
          <h4 style={{ fontSize: "var(--text-body)", fontWeight: 600, color: "var(--accent-primary)", marginBottom: "var(--space-3)" }}>
            📅 Follow-Up Meeting Suggested
          </h4>
          <div style={{
            background: "var(--bg-elevated)",
            borderRadius: "var(--radius-sm)",
            padding: "var(--space-4)",
            border: "1px solid rgba(108,92,231,0.3)",
            borderLeft: "3px solid var(--accent-primary)",
          }}>
            <p style={{ fontSize: "var(--text-small)", color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>
              {follow_up_suggestion.reason}
            </p>
            {follow_up_suggestion.suggested_topics.length > 0 && (
              <div style={{ marginBottom: "var(--space-2)" }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", fontWeight: 500 }}>Topics: </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)" }}>
                  {follow_up_suggestion.suggested_topics.join(", ")}
                </span>
              </div>
            )}
            {follow_up_suggestion.suggested_participants.length > 0 && (
              <div style={{ marginBottom: "var(--space-2)" }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", fontWeight: 500 }}>Participants: </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)" }}>
                  {follow_up_suggestion.suggested_participants.join(", ")}
                </span>
              </div>
            )}
            <div>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", fontWeight: 500 }}>Timeframe: </span>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--accent-primary)", fontWeight: 500 }}>
                {follow_up_suggestion.recommended_timeframe}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
