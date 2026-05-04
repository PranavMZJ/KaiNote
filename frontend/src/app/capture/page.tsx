"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/auth/useAuth";
import { AudioCapture } from "@/capture/AudioCapture";
import {
  WebSocketManager,
  type ServerMessage,
  type TranscriptSegment,
} from "@/capture/WebSocketManager";
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

  const [captureState, setCaptureState] = useState<CaptureState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<string>("");

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
  const wsManagerRef = useRef<WebSocketManager | null>(null);
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

  const handleMessage = useCallback((message: ServerMessage) => {
    switch (message.type) {
      case "transcript":
        setSegments((prev) => {
          const segment = message as TranscriptSegment;
          // Replace partial segment from same speaker or append
          if (segment.isPartial) {
            const lastIdx = prev.length - 1;
            if (
              lastIdx >= 0 &&
              prev[lastIdx].isPartial &&
              prev[lastIdx].speaker === segment.speaker
            ) {
              const updated = [...prev];
              updated[lastIdx] = segment;
              return updated;
            }
          }
          return [...prev, segment];
        });
        break;
      case "capture_stopped":
        setCaptureState("processing");
        setMeetingId(message.meetingId);
        // Start polling for completion since Step Functions doesn't send WebSocket messages
        pollForCompletion(message.meetingId);
        break;
      case "processing_complete":
        setMeetingId(message.meetingId);
        // Navigate to report view
        window.location.href = `/meetings/${message.meetingId}`;
        break;
      case "error":
        setMicError(message.message);
        break;
      case "connection_warning":
        setConnectionLost(true);
        setTimeout(() => setConnectionLost(false), 5000);
        break;
    }
  }, []);

  const handleStart = useCallback(async () => {
    setMicError(null);
    setConnectionLost(false);
    setSegments([]);

    const token = await auth.getToken();
    if (!token) {
      setMicError("Authentication required. Please sign in.");
      return;
    }

    const wsUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL ?? "";
    if (!wsUrl) {
      setMicError("WebSocket URL not configured.");
      return;
    }

    // Set up WebSocket
    const wsManager = new WebSocketManager({
      url: wsUrl,
      token,
      onMessage: handleMessage,
      onOpen: () => {
        setConnectionLost(false);
      },
      onClose: () => {
        // Only show warning if still capturing
      },
      onError: () => {
        setConnectionLost(true);
      },
      onReconnectFailed: () => {
        setConnectionLost(true);
      },
    });

    wsManagerRef.current = wsManager;
    wsManager.connect();

    // Set up audio capture
    const audioCapture = new AudioCapture({
      onChunk: (base64Chunk: string) => {
        wsManager.sendAudioChunk(base64Chunk);
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
  }, [auth.getToken, handleMessage]);

  const handleStop = useCallback(() => {
    setCaptureState("stopping");

    // Send stop signal via WebSocket FIRST (before closing audio)
    if (wsManagerRef.current) {
      wsManagerRef.current.sendStopCapture();
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
      wsManagerRef.current?.disconnect();
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const isActive =
    captureState === "capturing" || captureState === "stopping";

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
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-body)",
              color: "var(--text-primary)",
            }}
          >
            {formatTime(elapsedSeconds)}
          </span>
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
            Meeting Capture
          </h1>
          <p
            style={{
              fontSize: "var(--text-body)",
              color: "var(--text-secondary)",
            }}
          >
            Capture your meeting audio for AI-powered transcription and minutes
            generation.
          </p>
        </div>

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
              Start Meeting Capture
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
              Stop and Generate Minutes
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
        {segments.length > 0 && <TranscriptPanel segments={segments} />}

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
  );
}
