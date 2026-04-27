"use client";

import React, { useCallback, useState } from "react";
import { useAuth } from "@/auth/useAuth";

/**
 * ReportRenderer — displays structured meeting minutes with inline editing,
 * human review highlights, confidence badges, and save functionality.
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4
 */

/* ---------- Data types ---------- */

export interface Decision {
  decision: string;
  rationale: string;
  owner: string | null;
  evidence: string;
  timestamp: string | null;
}

export interface ActionItem {
  task: string;
  owner: string | null;
  due_date: string | null;
  priority: "low" | "medium" | "high";
  evidence: string;
  timestamp: string | null;
  confidence: number;
  needs_human_review: boolean;
}

export interface MinutesReport {
  schema_version: string;
  meeting_title: string;
  meeting_datetime: string;
  participants: string[];
  summary: string;
  agenda_items: string[];
  key_discussion_points: string[];
  decisions: Decision[];
  action_items: ActionItem[];
  risks_blockers: string[];
  open_questions: string[];
  follow_up_needed: boolean;
}

interface ReportRendererProps {
  meetingId: string;
  report: MinutesReport | null;
  isLoading?: boolean;
}

/* ---------- Inline editable field ---------- */

function EditableField({
  value,
  onChange,
  multiline = false,
  placeholder = "",
  style,
}: {
  value: string;
  onChange: (val: string) => void;
  multiline?: boolean;
  placeholder?: string;
  style?: React.CSSProperties;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const handleClick = () => {
    setDraft(value);
    setEditing(true);
  };

  const handleBlur = () => {
    setEditing(false);
    if (draft !== value) {
      onChange(draft);
    }
  };

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    if (e.key === "Enter" && !multiline) {
      e.currentTarget.blur();
    }
    if (e.key === "Escape") {
      setDraft(value);
      setEditing(false);
    }
  };

  if (editing) {
    const commonStyle: React.CSSProperties = {
      width: "100%",
      background: "var(--bg-elevated)",
      border: "1px solid var(--border-focus)",
      borderRadius: "var(--radius-sm)",
      color: "var(--text-primary)",
      fontFamily: "inherit",
      fontSize: "inherit",
      padding: "var(--space-1) var(--space-2)",
      outline: "none",
      ...style,
    };

    if (multiline) {
      return (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          autoFocus
          rows={3}
          style={{ ...commonStyle, resize: "vertical" }}
        />
      );
    }

    return (
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        autoFocus
        style={commonStyle}
      />
    );
  }

  return (
    <span
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") handleClick();
      }}
      title="Click to edit"
      style={{
        cursor: "text",
        borderRadius: "var(--radius-sm)",
        padding: "var(--space-1) var(--space-2)",
        transition: "background var(--duration-fast) var(--ease-out)",
        display: "inline-block",
        minWidth: 40,
        ...style,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background =
          "var(--bg-elevated)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = "transparent";
      }}
    >
      {value || (
        <span style={{ color: "var(--text-tertiary)" }}>
          {placeholder || "Click to edit"}
        </span>
      )}
    </span>
  );
}

/* ---------- Confidence badge ---------- */

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const isHigh = confidence >= 0.7;
  return (
    <span
      className={isHigh ? "badge-success" : "badge-warning"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "var(--space-1) var(--space-2)",
        fontSize: "var(--text-xs)",
        fontWeight: 500,
        borderRadius: "var(--radius-sm)",
        lineHeight: 1,
        background: isHigh
          ? "rgba(52, 199, 89, 0.15)"
          : "rgba(255, 159, 10, 0.15)",
        color: isHigh ? "var(--success)" : "var(--warning)",
      }}
    >
      {(confidence * 100).toFixed(0)}%
    </span>
  );
}

/* ---------- Warning icon ---------- */

function WarningIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <path
        d="M8 1L15 14H1L8 1Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M8 6v3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="8" cy="12" r="0.75" fill="currentColor" />
    </svg>
  );
}

/* ---------- Section heading ---------- */

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2
      style={{
        fontSize: "var(--text-h2)",
        fontWeight: 600,
        color: "var(--text-primary)",
        letterSpacing: "var(--letter-spacing-tight)",
        marginBottom: "var(--space-4)",
      }}
    >
      {children}
    </h2>
  );
}

/* ---------- Section divider ---------- */

function SectionDivider() {
  return (
    <hr
      style={{
        border: "none",
        borderTop: "1px solid var(--border-subtle)",
        margin: 0,
      }}
    />
  );
}

/* ---------- Main component ---------- */

export function ReportRenderer({
  meetingId,
  report,
  isLoading,
}: ReportRendererProps) {
  const { getToken } = useAuth();
  const [editedReport, setEditedReport] = useState<MinutesReport | null>(null);
  const [hasEdits, setHasEdits] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveToast, setSaveToast] = useState<string | null>(null);

  // Use edited version if available, otherwise original
  const displayReport = editedReport ?? report;

  const updateReport = useCallback(
    (updater: (prev: MinutesReport) => MinutesReport) => {
      const base = editedReport ?? report;
      if (!base) return;
      const updated = updater({ ...base });
      setEditedReport(updated);
      setHasEdits(true);
    },
    [editedReport, report]
  );

  const handleSave = useCallback(async () => {
    if (!editedReport) return;
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");

      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(
        `${apiUrl}/meetings/${meetingId}/report`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(editedReport),
        }
      );

      if (!response.ok) throw new Error("Save failed");

      setHasEdits(false);
      setSaveToast("Changes saved successfully");
      setTimeout(() => setSaveToast(null), 3000);
    } catch {
      setSaveToast("Failed to save changes. Please try again.");
      setTimeout(() => setSaveToast(null), 3000);
    } finally {
      setSaving(false);
    }
  }, [editedReport, meetingId, getToken]);

  // Loading state
  if (isLoading) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-24)",
          gap: "var(--space-4)",
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
        <p
          style={{
            color: "var(--text-secondary)",
            fontSize: "var(--text-body)",
          }}
        >
          Loading report…
        </p>
      </div>
    );
  }

  if (!displayReport) {
    return (
      <div
        style={{
          textAlign: "center",
          padding: "var(--space-16)",
          color: "var(--text-secondary)",
        }}
      >
        No report available.
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-12)",
      }}
    >
      {/* Save toast */}
      {saveToast && (
        <div
          className="glass-panel"
          role="status"
          style={{
            position: "fixed",
            top: "var(--space-4)",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 100,
            padding: "var(--space-2) var(--space-6)",
            borderColor: saveToast.includes("Failed")
              ? "var(--error)"
              : "var(--success)",
            borderWidth: 1,
            borderStyle: "solid",
            color: saveToast.includes("Failed")
              ? "var(--error)"
              : "var(--success)",
            fontSize: "var(--text-small)",
            animation: "fade-in-up var(--duration-normal) var(--ease-out)",
          }}
        >
          {saveToast}
        </div>
      )}

      {/* Header */}
      <div>
        <h1
          style={{
            fontSize: "var(--text-h1)",
            fontWeight: 700,
            letterSpacing: "var(--letter-spacing-tight)",
            color: "var(--text-primary)",
            marginBottom: "var(--space-2)",
          }}
        >
          <EditableField
            value={displayReport.meeting_title}
            onChange={(val) =>
              updateReport((r) => ({ ...r, meeting_title: val }))
            }
          />
        </h1>
        <p
          style={{
            fontSize: "var(--text-small)",
            color: "var(--text-secondary)",
          }}
        >
          {new Date(displayReport.meeting_datetime).toLocaleString()}
        </p>
        {displayReport.participants.length > 0 && (
          <p
            style={{
              fontSize: "var(--text-small)",
              color: "var(--text-tertiary)",
              marginTop: "var(--space-1)",
            }}
          >
            Participants: {displayReport.participants.join(", ")}
          </p>
        )}
      </div>

      <SectionDivider />

      {/* Summary */}
      <section>
        <SectionHeading>Summary</SectionHeading>
        <EditableField
          value={displayReport.summary}
          onChange={(val) => updateReport((r) => ({ ...r, summary: val }))}
          multiline
          style={{ fontSize: "var(--text-body)", lineHeight: "1.6" }}
        />
      </section>

      <SectionDivider />

      {/* Key Discussion Points */}
      {displayReport.key_discussion_points.length > 0 && (
        <>
          <section>
            <SectionHeading>Key Discussion Points</SectionHeading>
            <ul
              style={{
                listStyle: "disc",
                paddingLeft: "var(--space-6)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              {displayReport.key_discussion_points.map((point, i) => (
                <li
                  key={i}
                  className="fade-in-up"
                  style={{
                    color: "var(--text-primary)",
                    animationDelay: `${i * 80}ms`,
                  }}
                >
                  <EditableField
                    value={point}
                    onChange={(val) =>
                      updateReport((r) => {
                        const pts = [...r.key_discussion_points];
                        pts[i] = val;
                        return { ...r, key_discussion_points: pts };
                      })
                    }
                  />
                </li>
              ))}
            </ul>
          </section>
          <SectionDivider />
        </>
      )}

      {/* Decisions */}
      {displayReport.decisions.length > 0 && (
        <>
          <section>
            <SectionHeading>Decisions</SectionHeading>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-4)",
              }}
            >
              {displayReport.decisions.map((decision, i) => (
                <div
                  key={i}
                  className="elevated-card fade-in-up"
                  style={{
                    borderLeft: "3px solid var(--accent-primary)",
                    animationDelay: `${i * 100}ms`,
                  }}
                >
                  <div style={{ marginBottom: "var(--space-2)" }}>
                    <EditableField
                      value={decision.decision}
                      onChange={(val) =>
                        updateReport((r) => {
                          const decs = [...r.decisions];
                          decs[i] = { ...decs[i], decision: val };
                          return { ...r, decisions: decs };
                        })
                      }
                      style={{
                        fontWeight: 600,
                        fontSize: "var(--text-body)",
                      }}
                    />
                  </div>
                  <p
                    style={{
                      fontSize: "var(--text-small)",
                      color: "var(--text-secondary)",
                      marginBottom: "var(--space-2)",
                    }}
                  >
                    <strong>Rationale:</strong>{" "}
                    <EditableField
                      value={decision.rationale}
                      onChange={(val) =>
                        updateReport((r) => {
                          const decs = [...r.decisions];
                          decs[i] = { ...decs[i], rationale: val };
                          return { ...r, decisions: decs };
                        })
                      }
                    />
                  </p>
                  {decision.owner && (
                    <p
                      style={{
                        fontSize: "var(--text-small)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      Owner:{" "}
                      <EditableField
                        value={decision.owner}
                        onChange={(val) =>
                          updateReport((r) => {
                            const decs = [...r.decisions];
                            decs[i] = { ...decs[i], owner: val || null };
                            return { ...r, decisions: decs };
                          })
                        }
                      />
                    </p>
                  )}
                  {/* Evidence snippet */}
                  <div
                    style={{
                      marginTop: "var(--space-2)",
                      background: "var(--bg-elevated)",
                      borderRadius: "var(--radius-sm)",
                      padding: "var(--space-2) var(--space-3)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-small)",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    {decision.evidence}
                  </div>
                </div>
              ))}
            </div>
          </section>
          <SectionDivider />
        </>
      )}

      {/* Action Items */}
      {displayReport.action_items.length > 0 && (
        <>
          <section>
            <SectionHeading>Action Items</SectionHeading>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-4)",
              }}
            >
              {displayReport.action_items.map((item, i) => {
                const hasMissing =
                  item.owner === null || item.due_date === null;
                const needsReview = item.needs_human_review;

                return (
                  <div
                    key={i}
                    className="elevated-card fade-in-up"
                    style={{
                      borderLeft: needsReview
                        ? "3px solid var(--warning)"
                        : "3px solid var(--border-subtle)",
                      border: hasMissing
                        ? "1px dashed var(--border-subtle)"
                        : undefined,
                      borderLeftWidth: 3,
                      borderLeftStyle: "solid",
                      borderLeftColor: needsReview
                        ? "var(--warning)"
                        : "var(--border-subtle)",
                      animationDelay: `${i * 100}ms`,
                    }}
                  >
                    {/* Header row */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--space-2)",
                        marginBottom: "var(--space-2)",
                        flexWrap: "wrap",
                      }}
                    >
                      {needsReview && (
                        <span
                          style={{
                            color: "var(--warning)",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "var(--space-1)",
                          }}
                          title="Needs human review"
                        >
                          <WarningIcon />
                        </span>
                      )}
                      <EditableField
                        value={item.task}
                        onChange={(val) =>
                          updateReport((r) => {
                            const items = [...r.action_items];
                            items[i] = { ...items[i], task: val };
                            return { ...r, action_items: items };
                          })
                        }
                        style={{
                          fontWeight: 600,
                          fontSize: "var(--text-body)",
                          flex: 1,
                        }}
                      />
                      <ConfidenceBadge confidence={item.confidence} />
                    </div>

                    {/* Details */}
                    <div
                      style={{
                        display: "flex",
                        gap: "var(--space-4)",
                        flexWrap: "wrap",
                        fontSize: "var(--text-small)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      <span>
                        Priority:{" "}
                        <span
                          style={{
                            fontWeight: 500,
                            color:
                              item.priority === "high"
                                ? "var(--error)"
                                : item.priority === "medium"
                                  ? "var(--warning)"
                                  : "var(--text-secondary)",
                          }}
                        >
                          {item.priority}
                        </span>
                      </span>

                      <span>
                        Owner:{" "}
                        {item.owner !== null ? (
                          <EditableField
                            value={item.owner}
                            onChange={(val) =>
                              updateReport((r) => {
                                const items = [...r.action_items];
                                items[i] = {
                                  ...items[i],
                                  owner: val || null,
                                };
                                return { ...r, action_items: items };
                              })
                            }
                          />
                        ) : (
                          <span
                            style={{
                              color: "var(--text-tertiary)",
                              fontStyle: "italic",
                            }}
                          >
                            Missing
                            <EditableField
                              value=""
                              placeholder="Set owner"
                              onChange={(val) =>
                                updateReport((r) => {
                                  const items = [...r.action_items];
                                  items[i] = {
                                    ...items[i],
                                    owner: val || null,
                                  };
                                  return { ...r, action_items: items };
                                })
                              }
                            />
                          </span>
                        )}
                      </span>

                      <span>
                        Due:{" "}
                        {item.due_date !== null ? (
                          <EditableField
                            value={item.due_date}
                            onChange={(val) =>
                              updateReport((r) => {
                                const items = [...r.action_items];
                                items[i] = {
                                  ...items[i],
                                  due_date: val || null,
                                };
                                return { ...r, action_items: items };
                              })
                            }
                          />
                        ) : (
                          <span
                            style={{
                              color: "var(--text-tertiary)",
                              fontStyle: "italic",
                            }}
                          >
                            Missing
                            <EditableField
                              value=""
                              placeholder="Set due date"
                              onChange={(val) =>
                                updateReport((r) => {
                                  const items = [...r.action_items];
                                  items[i] = {
                                    ...items[i],
                                    due_date: val || null,
                                  };
                                  return { ...r, action_items: items };
                                })
                              }
                            />
                          </span>
                        )}
                      </span>
                    </div>

                    {/* Evidence */}
                    <div
                      style={{
                        marginTop: "var(--space-2)",
                        background: "var(--bg-elevated)",
                        borderRadius: "var(--radius-sm)",
                        padding: "var(--space-2) var(--space-3)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--text-small)",
                        color: "var(--text-tertiary)",
                      }}
                    >
                      {item.evidence}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
          <SectionDivider />
        </>
      )}

      {/* Risks & Blockers */}
      {displayReport.risks_blockers.length > 0 && (
        <>
          <section>
            <SectionHeading>Risks &amp; Blockers</SectionHeading>
            <ul
              style={{
                listStyle: "disc",
                paddingLeft: "var(--space-6)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              {displayReport.risks_blockers.map((risk, i) => (
                <li
                  key={i}
                  className="fade-in-up"
                  style={{
                    color: "var(--text-primary)",
                    animationDelay: `${i * 80}ms`,
                  }}
                >
                  <EditableField
                    value={risk}
                    onChange={(val) =>
                      updateReport((r) => {
                        const risks = [...r.risks_blockers];
                        risks[i] = val;
                        return { ...r, risks_blockers: risks };
                      })
                    }
                  />
                </li>
              ))}
            </ul>
          </section>
          <SectionDivider />
        </>
      )}

      {/* Open Questions */}
      {displayReport.open_questions.length > 0 && (
        <>
          <section>
            <SectionHeading>Open Questions</SectionHeading>
            <ul
              style={{
                listStyle: "disc",
                paddingLeft: "var(--space-6)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              {displayReport.open_questions.map((q, i) => (
                <li
                  key={i}
                  className="fade-in-up"
                  style={{
                    color: "var(--text-primary)",
                    animationDelay: `${i * 80}ms`,
                  }}
                >
                  <EditableField
                    value={q}
                    onChange={(val) =>
                      updateReport((r) => {
                        const qs = [...r.open_questions];
                        qs[i] = val;
                        return { ...r, open_questions: qs };
                      })
                    }
                  />
                </li>
              ))}
            </ul>
          </section>
          <SectionDivider />
        </>
      )}

      {/* Save button — only when edits are pending */}
      {hasEdits && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: "var(--space-3) var(--space-8)",
              fontWeight: 600,
              opacity: saving ? 0.7 : 1,
            }}
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      )}
    </div>
  );
}
