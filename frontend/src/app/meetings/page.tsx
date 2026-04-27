"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/auth/useAuth";

/**
 * Meetings List Page — lists user's meetings as elevated-card items
 * with status badges, hover effects, retry for failed, and empty state.
 *
 * Requirements: 9.1, 12.4, 14.5
 */

interface Meeting {
  meetingId: string;
  meeting_title?: string;
  status: "pending" | "processing" | "completed" | "failed";
  createdAt: string;
  updatedAt?: string;
}

const STATUS_STYLES: Record<
  Meeting["status"],
  { background: string; color: string; label: string }
> = {
  pending: {
    background: "rgba(142, 142, 147, 0.15)",
    color: "var(--text-secondary)",
    label: "Pending",
  },
  processing: {
    background: "rgba(108, 92, 231, 0.15)",
    color: "var(--accent-primary)",
    label: "Processing",
  },
  completed: {
    background: "rgba(52, 199, 89, 0.15)",
    color: "var(--success)",
    label: "Completed",
  },
  failed: {
    background: "rgba(255, 69, 58, 0.15)",
    color: "var(--error)",
    label: "Failed",
  },
};

export default function MeetingsPage() {
  const { getToken } = useAuth();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const fetchMeetings = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) {
        setError("Authentication required.");
        setLoading(false);
        return;
      }

      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(`${apiUrl}/meetings`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error("Failed to load meetings");

      const data = (await response.json()) as { meetings?: Meeting[] };
      setMeetings(data.meetings ?? []);
    } catch {
      setError("Failed to load meetings. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  const handleRetry = useCallback(
    async (meetingId: string) => {
      setRetrying(meetingId);
      try {
        const token = await getToken();
        if (!token) return;

        const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
        const response = await fetch(
          `${apiUrl}/meetings/${meetingId}/retry`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!response.ok) throw new Error("Retry failed");

        // Refresh the list
        await fetchMeetings();
      } catch {
        // Error handled silently — user can try again
      } finally {
        setRetrying(null);
      }
    },
    [getToken, fetchMeetings]
  );

  const handleCardClick = (meeting: Meeting) => {
    if (meeting.status === "completed") {
      window.location.href = `/meetings/${meeting.meetingId}`;
    }
  };

  if (loading) {
    return (
      <main
        style={{
          background: "var(--bg-primary)",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          className="spinner"
          style={{
            width: 32,
            height: 32,
            borderTopColor: "var(--accent-primary)",
          }}
        />
      </main>
    );
  }

  return (
    <main
      style={{
        background: "var(--bg-primary)",
        minHeight: "100vh",
        paddingTop: "var(--space-24)",
        paddingLeft: "var(--space-8)",
        paddingRight: "var(--space-8)",
        paddingBottom: "var(--space-12)",
      }}
    >
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <h1
          style={{
            fontSize: "var(--text-h1)",
            fontWeight: 700,
            letterSpacing: "var(--letter-spacing-tight)",
            color: "var(--text-primary)",
            marginBottom: "var(--space-8)",
          }}
        >
          Your Meetings
        </h1>

        {error && (
          <div
            className="elevated-card"
            role="alert"
            style={{
              borderColor: "var(--error)",
              color: "var(--error)",
              textAlign: "center",
              marginBottom: "var(--space-6)",
            }}
          >
            {error}
          </div>
        )}

        {/* Empty state */}
        {meetings.length === 0 && !error && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "var(--space-24) var(--space-8)",
              gap: "var(--space-4)",
            }}
          >
            <svg
              width="64"
              height="64"
              viewBox="0 0 64 64"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <rect
                x="8"
                y="12"
                width="48"
                height="40"
                rx="4"
                stroke="var(--text-tertiary)"
                strokeWidth="2"
              />
              <path
                d="M8 24h48"
                stroke="var(--text-tertiary)"
                strokeWidth="2"
              />
              <circle
                cx="16"
                cy="18"
                r="2"
                fill="var(--text-tertiary)"
              />
              <circle
                cx="24"
                cy="18"
                r="2"
                fill="var(--text-tertiary)"
              />
              <circle
                cx="32"
                cy="18"
                r="2"
                fill="var(--text-tertiary)"
              />
              <path
                d="M20 34h24M20 42h16"
                stroke="var(--text-tertiary)"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            <p
              style={{
                fontSize: "var(--text-h3)",
                color: "var(--text-secondary)",
                fontWeight: 500,
              }}
            >
              No meetings yet
            </p>
            <p
              style={{
                fontSize: "var(--text-small)",
                color: "var(--text-tertiary)",
                textAlign: "center",
                maxWidth: 320,
              }}
            >
              Start your first meeting capture to generate AI-powered minutes.
            </p>
            <a
              href="/capture"
              className="btn-primary"
              style={{
                marginTop: "var(--space-4)",
                padding: "var(--space-3) var(--space-8)",
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Start Meeting Capture
            </a>
          </div>
        )}

        {/* Meeting cards */}
        {meetings.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-4)",
            }}
          >
            {meetings.map((meeting, i) => {
              const statusStyle = STATUS_STYLES[meeting.status];
              const isClickable = meeting.status === "completed";

              return (
                <div
                  key={meeting.meetingId}
                  className="elevated-card fade-in-up"
                  role={isClickable ? "link" : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                  onClick={() => handleCardClick(meeting)}
                  onKeyDown={(e) => {
                    if (
                      isClickable &&
                      (e.key === "Enter" || e.key === " ")
                    ) {
                      handleCardClick(meeting);
                    }
                  }}
                  style={{
                    cursor: isClickable ? "pointer" : "default",
                    animationDelay: `${i * 80}ms`,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "var(--space-4)",
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h3
                        style={{
                          fontSize: "var(--text-h3)",
                          fontWeight: 600,
                          color: "var(--text-primary)",
                          marginBottom: "var(--space-1)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {meeting.meeting_title || `Meeting ${meeting.meetingId.slice(0, 8)}`}
                      </h3>
                      <p
                        style={{
                          fontSize: "var(--text-small)",
                          color: "var(--text-tertiary)",
                        }}
                      >
                        {new Date(meeting.createdAt).toLocaleDateString(
                          undefined,
                          {
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          }
                        )}
                      </p>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--space-3)",
                      }}
                    >
                      {/* Status badge */}
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          padding: "var(--space-1) var(--space-3)",
                          fontSize: "var(--text-xs)",
                          fontWeight: 500,
                          borderRadius: "999px",
                          background: statusStyle.background,
                          color: statusStyle.color,
                          lineHeight: 1,
                        }}
                      >
                        {statusStyle.label}
                      </span>

                      {/* Retry button for failed meetings */}
                      {meeting.status === "failed" && (
                        <button
                          className="btn-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRetry(meeting.meetingId);
                          }}
                          disabled={retrying === meeting.meetingId}
                          style={{
                            padding: "var(--space-1) var(--space-3)",
                            fontSize: "var(--text-xs)",
                            opacity:
                              retrying === meeting.meetingId ? 0.6 : 1,
                          }}
                        >
                          {retrying === meeting.meetingId
                            ? "Retrying…"
                            : "Retry"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
