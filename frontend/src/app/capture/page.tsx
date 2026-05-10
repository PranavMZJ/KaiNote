"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/auth/useAuth";
import { AudioCapture } from "@/capture/AudioCapture";
import { Navbar } from "@/components/Navbar";
import { useI18n } from "@/i18n";
import {
  TranscriptionClient,
  type TranscriptSegment,
} from "@/capture/TranscriptionClient";
import { TranscriptPanel } from "@/components/TranscriptPanel";

/**
 * Meeting Capture Page
 *
 * Provides "Start Meeting Capture" and "Stop and Generate Minutes" buttons,
 * a live recording indicator with elapsed timer, connection-lost warnings,
 * and microphone-denied error display.
 *
 * Requirements: 2.1, 2.4, 2.7, 5.1
 */

type CaptureState = "idle" | "capturing" | "stopping" | "processing";

export default function CapturePage() {
  const auth = useAuth();
  const { t } = useI18n();

  const [captureState, setCaptureState] = useState<CaptureState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<string>("");
  const [audioLanguage, setAudioLanguage] = useState<string>("en-US");
  const [displayLanguage, setDisplayLanguage] = useState<string>("same");

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll the REST API for meeting status (completed/failed)
  const pollForCompletion = useCallback(async (mid: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
    if (!apiUrl) return;

    // Clear any existing poll
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const token = await auth.getToken();
        if (!token) return;

        const response = await fetch(`${apiUrl}/meetings/${mid}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) return;

        const data = await response.json();
        const status = data.status;

        if (status === "completed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          window.location.href = `/meetings`;
        } else if (status === "failed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setMicError(`Minutes generation failed: ${data.error || "Unknown error"}`);
          setCaptureState("idle");
        }
      } catch {
        // Silently retry on next interval
      }
    }, 5000); // Poll every 5 seconds
  }, [auth]);

  // Poll the REST API for the latest meeting (used when meetingId is unknown)
  const pollForLatestMeeting = useCallback(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
    if (!apiUrl) return;

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const token = await auth.getToken();
        if (!token) return;

        const response = await fetch(`${apiUrl}/meetings`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) return;

        const data = await response.json();
        const meetings = data.meetings || [];

        const completed = meetings.find((m: { status: string }) => m.status === "completed");
        const failed = meetings.find((m: { status: string }) => m.status === "failed");

        if (completed) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          window.location.href = `/meetings`;
        } else if (failed) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setMicError(`Minutes generation failed: ${failed.error || "Unknown error"}`);
          setCaptureState("idle");
        }
      } catch {
        // Silently retry
      }
    }, 5000);
  }, [auth]);

  const audioCaptureRef = useRef<AudioCapture | null>(null);
  const transcriptionRef = useRef<TranscriptionClient | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Debug: show auth state
  useEffect(() => {
    setDebugInfo(`Auth: loading=${auth.isLoading}, authenticated=${auth.isAuthenticated}, user=${auth.user?.email || "none"}`);
  }, [auth.isLoading, auth.isAuthenticated, auth.user]);

  // Elapsed timer
  useEffect(() => {
    if (captureState === "capturing") {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [captureState]);

  const formatTime = (totalSeconds: number): string => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const handleStart = useCallback(async () => {
    setMicError(null);
    setConnectionLost(false);
    setSegments([]);

    const token = await auth.getToken();
    if (!token) {
      setMicError("Authentication required. Please sign in.");
      return;
    }

    // Generate a meeting ID for this session
    const newMeetingId = crypto.randomUUID();
    setMeetingId(newMeetingId);

    // Get user info
    const userId = auth.user?.sub || "";

    // Set up TranscriptionClient (connects to Fargate ALB)
    const client = new TranscriptionClient({
      onSegment: (segment: TranscriptSegment) => {
        setSegments((prev) => {
          const lastIdx = prev.length - 1;

          // If the last segment was partial, replace it with the new one
          // (whether the new one is partial or final)
          if (lastIdx >= 0 && prev[lastIdx].isPartial) {
            const updated = [...prev];
            updated[lastIdx] = segment;
            return updated;
          }

          // Otherwise append as a new segment
          return [...prev, segment];
        });
      },
      onStopped: (stoppedMeetingId: string) => {
        setCaptureState("processing");
        setMeetingId(stoppedMeetingId);
        pollForLatestMeeting();
      },
      onError: (error: string) => {
        setMicError(error);
        setConnectionLost(true);
      },
      onConnected: () => {
        setConnectionLost(false);
      },
      onDisconnected: () => {
        setConnectionLost(true);
      },
    });

    transcriptionRef.current = client;
    const translationTarget = displayLanguage === "same" ? undefined : displayLanguage;
    client.connect(newMeetingId, userId, token, audioLanguage, translationTarget);

    // Set up audio capture — send raw PCM (not base64) to Fargate
    const audioCapture = new AudioCapture({
      onChunk: (_base64Chunk: string) => {
        // The AudioCapture gives us base64, but TranscriptionClient needs ArrayBuffer
        // Decode base64 to binary and send
        const binaryStr = atob(_base64Chunk);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        client.sendAudio(bytes.buffer);
      },
      onError: (error: Error) => {
        setMicError(error.message || "Microphone access denied.");
        setCaptureState("idle");
      },
    });

    audioCaptureRef.current = audioCapture;

    try {
      await audioCapture.start();
      setCaptureState("capturing");
    } catch {
      setCaptureState("idle");
    }
  }, [auth, pollForLatestMeeting, audioLanguage, displayLanguage]);

  const handleStop = useCallback(() => {
    setCaptureState("stopping");

    // Send stop signal to Fargate service FIRST
    if (transcriptionRef.current) {
      transcriptionRef.current.stop();
    }

    // Then stop audio capture
    if (audioCaptureRef.current) {
      audioCaptureRef.current.stop();
      audioCaptureRef.current = null;
    }

    // Transition to processing state and start polling after a short delay
    // (give the backend time to store the transcript and start the workflow)
    setTimeout(() => {
      setCaptureState("processing");
      pollForLatestMeeting();
    }, 3000);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      audioCaptureRef.current?.stop();
      transcriptionRef.current?.disconnect();
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const isActive =
    captureState === "capturing" || captureState === "stopping";

  return (
    <>
    <Navbar />
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
      {/* Sticky recording header */}
      {isActive && (
        <div
          className="glass-panel"
          style={{
            position: "sticky",
            top: 0,
            zIndex: 50,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--space-3)",
            padding: "var(--space-3) var(--space-6)",
            marginBottom: "var(--space-8)",
          }}
        >
          <span
            className="recording-pulse"
            style={{
              display: "inline-block",
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: "var(--recording)",
            }}
            aria-label="Recording"
          />
          <span
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--text-tertiary)",
              background: "var(--bg-elevated)",
              padding: "1px var(--space-2)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            🎤 {audioLanguage}
          </span>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-body)",
              color: "var(--text-primary)",
            }}
          >
            {formatTime(elapsedSeconds)}
          </span>

          {/* Live language switcher */}
          <select
            value={displayLanguage}
            onChange={(e) => {
              const newLang = e.target.value;
              setDisplayLanguage(newLang);
              const target = newLang === "same" ? null : newLang;
              if (transcriptionRef.current) {
                transcriptionRef.current.setDisplayLanguage(target);
              }
            }}
            style={{
              background: "var(--bg-elevated)", color: "var(--text-primary)",
              border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)",
              padding: "2px var(--space-2)", fontSize: "var(--text-xs)",
              cursor: "pointer", marginLeft: "var(--space-2)",
            }}
            title="Display language"
          >
            <option value="same">Original</option>
            <option value="en">English</option>
            <option value="ja">日本語</option>
            <option value="ko">한국어</option>
            <option value="zh">中文</option>
            <option value="fr">Français</option>
            <option value="de">Deutsch</option>
            <option value="es">Español</option>
          </select>
          {captureState === "stopping" && (
            <span
              style={{
                fontSize: "var(--text-small)",
                color: "var(--text-secondary)",
              }}
            >
              Stopping…
            </span>
          )}
        </div>
      )}

      {/* Connection lost warning toast */}
      {connectionLost && (
        <div
          className="glass-panel"
          role="alert"
          style={{
            position: "fixed",
            top: "var(--space-4)",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 100,
            padding: "var(--space-3) var(--space-6)",
            borderColor: "var(--warning)",
            borderWidth: 1,
            borderStyle: "solid",
            borderRadius: "var(--radius-lg)",
            color: "var(--warning)",
            fontSize: "var(--text-small)",
            animation: "fade-in-up var(--duration-normal) var(--ease-out)",
          }}
        >
          Connection lost. Attempting to reconnect…
        </div>
      )}

      {/* Microphone error */}
      {micError && (
        <div
          className="elevated-card"
          role="alert"
          style={{
            maxWidth: 480,
            margin: "0 auto var(--space-8)",
            borderColor: "var(--error)",
            color: "var(--error)",
            textAlign: "center",
          }}
        >
          <p style={{ fontSize: "var(--text-body)", fontWeight: 500 }}>
            {micError}
          </p>
          <p
            style={{
              fontSize: "var(--text-small)",
              color: "var(--text-secondary)",
              marginTop: "var(--space-2)",
            }}
          >
            Please allow microphone access in your browser settings.
          </p>
        </div>
      )}

      {/* Main content */}
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-8)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <h1
            style={{
              fontSize: "var(--text-h1)",
              fontWeight: 700,
              letterSpacing: "var(--letter-spacing-tight)",
              color: "var(--text-primary)",
              marginBottom: "var(--space-3)",
            }}
          >
            {t("capture.title")}
          </h1>
          <p
            style={{
              fontSize: "var(--text-body)",
              color: "var(--text-secondary)",
            }}
          >
            {t("capture.subtitle")}
          </p>
        </div>

        {/* Language settings (only shown when idle) */}
        {captureState === "idle" && (
          <div style={{
            display: "flex", justifyContent: "center", gap: "var(--space-6)", flexWrap: "wrap",
          }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {t("capture.audioLanguage")}
              </label>
              <select
                value={audioLanguage}
                onChange={(e) => setAudioLanguage(e.target.value)}
                style={{
                  background: "var(--bg-elevated)", color: "var(--text-primary)",
                  border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-2) var(--space-3)", fontSize: "var(--text-small)",
                  cursor: "pointer", minWidth: "140px",
                }}
              >
                <option value="en-US">English (US)</option>
                <option value="ja-JP">日本語</option>
                <option value="ko-KR">한국어</option>
                <option value="zh-CN">中文</option>
                <option value="fr-FR">Français</option>
                <option value="de-DE">Deutsch</option>
                <option value="es-ES">Español</option>
              </select>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {t("capture.displayLanguage")}
              </label>
              <select
                value={displayLanguage}
                onChange={(e) => setDisplayLanguage(e.target.value)}
                style={{
                  background: "var(--bg-elevated)", color: "var(--text-primary)",
                  border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-2) var(--space-3)", fontSize: "var(--text-small)",
                  cursor: "pointer", minWidth: "140px",
                }}
              >
                <option value="same">Same as audio</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
                <option value="zh">中文</option>
                <option value="fr">Français</option>
                <option value="de">Deutsch</option>
                <option value="es">Español</option>
              </select>
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "var(--space-4)",
          }}
        >
          {captureState === "idle" && (
            <button
              className="btn-primary"
              onClick={handleStart}
              style={{
                fontWeight: 700,
                padding: "var(--space-4) var(--space-8)",
                fontSize: "var(--text-h3)",
              }}
            >
              {t("capture.start")}
            </button>
          )}

          {captureState === "capturing" && (
            <button
              className="btn-danger"
              onClick={handleStop}
              style={{
                padding: "var(--space-3) var(--space-6)",
                fontSize: "var(--text-body)",
                fontWeight: 600,
              }}
            >
              {t("capture.stop")}
            </button>
          )}

          {captureState === "processing" && (
            <div style={{ textAlign: "center" }}>
              <div
                className="spinner"
                style={{
                  width: 32,
                  height: 32,
                  margin: "0 auto var(--space-3)",
                }}
              />
              <p
                style={{
                  color: "var(--text-secondary)",
                  fontSize: "var(--text-small)",
                }}
              >
                Generating meeting minutes…
                {meetingId && (
                  <span
                    style={{
                      display: "block",
                      marginTop: "var(--space-1)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-xs)",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    Meeting ID: {meetingId}
                  </span>
                )}
              </p>
            </div>
          )}
        </div>

        {/* Live transcript panel */}
        {segments.length > 0 && (
          <div style={{ position: "relative" }}>
            <TranscriptPanel segments={segments} />
            <button
              onClick={() => {
                const text = segments
                  .filter((s) => !s.isPartial)
                  .map((s) => `${s.speaker}: ${s.text}`)
                  .join("\n");
                navigator.clipboard.writeText(text).catch(() => {});
              }}
              style={{
                position: "absolute", top: "var(--space-2)", right: "var(--space-2)",
                background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)", padding: "var(--space-1) var(--space-2)",
                fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
                cursor: "pointer", transition: "color var(--duration-fast)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-tertiary)")}
              title="Copy transcription"
            >
              📋 Copy
            </button>
          </div>
        )}

        {/* Debug info - remove after testing */}
        {debugInfo && (
          <div style={{
            position: "fixed",
            bottom: "var(--space-4)",
            left: "var(--space-4)",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "var(--space-2) var(--space-3)",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--text-xs)",
            color: "var(--text-tertiary)",
            zIndex: 200,
          }}>
            {debugInfo}
          </div>
        )}
      </div>
    </main>
    </>
  );
}
