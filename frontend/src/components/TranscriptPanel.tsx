"use client";

import React, { useEffect, useRef } from "react";

/**
 * TranscriptPanel — displays live transcript segments with speaker labels,
 * partial/final styling, slide-in animation, and auto-scroll.
 *
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */

export interface TranscriptSegmentData {
  text: string;
  speaker: string;
  isPartial: boolean;
  timestamp: string;
}

interface TranscriptPanelProps {
  segments: TranscriptSegmentData[];
}

function formatSpeakerLabel(speaker: string): string {
  // Handle various formats: "spk_0", "0", "spk_1", "Speaker 1", etc.
  const num = speaker.replace(/[^0-9]/g, "");
  if (num !== "") {
    return `Speaker ${parseInt(num, 10) + 1}`;
  }
  return speaker || "Speaker";
}

export function TranscriptPanel({ segments }: TranscriptPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to most recent segment
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [segments]);

  return (
    <div
      ref={containerRef}
      role="log"
      aria-live="polite"
      aria-label="Live transcript"
      style={{
        background: "var(--bg-primary)",
        borderLeft: "2px solid var(--accent-primary)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-6)",
        maxHeight: 400,
        overflowY: "auto",
        scrollBehavior: "smooth",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
      }}
    >
      {segments.length === 0 && (
        <p
          style={{
            color: "var(--text-tertiary)",
            fontSize: "var(--text-small)",
            textAlign: "center",
          }}
        >
          Waiting for transcript…
        </p>
      )}

      {segments.map((segment, index) => (
        <div
          key={`seg-${index}`}
          className={segment.isPartial ? "" : "fade-in-up"}
          style={{
            animationDelay: segment.isPartial ? "0ms" : `${Math.min(index * 50, 200)}ms`,
            transition: "opacity var(--duration-fast) var(--ease-out)",
          }}
        >
          {/* Speaker label */}
          <span
            style={{
              display: "block",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "var(--letter-spacing-wide)",
              color: "var(--accent-primary)",
              marginBottom: "var(--space-1)",
            }}
          >
            {formatSpeakerLabel(segment.speaker)}
          </span>

          {/* Segment text */}
          <p
            style={{
              fontSize: "var(--text-body)",
              lineHeight: 1.6,
              color: segment.isPartial
                ? "var(--text-tertiary)"
                : "var(--text-primary)",
              fontStyle: segment.isPartial ? "italic" : "normal",
              fontWeight: segment.isPartial ? 400 : 400,
            }}
          >
            {segment.text}
          </p>
        </div>
      ))}
    </div>
  );
}
