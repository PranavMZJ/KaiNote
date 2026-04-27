"use client";

import React, { useCallback, useState } from "react";
import { useAuth } from "@/auth/useAuth";

/**
 * ExportControls — "Copy to Clipboard" and "Download JSON" buttons
 * for exporting meeting minutes.
 *
 * Requirements: 11.1, 11.2, 11.3
 */

interface ExportControlsProps {
  meetingId: string;
  /** The formatted text content to copy to clipboard. */
  formattedText: string;
}

type ToastType = "success" | "error";

export function ExportControls({
  meetingId,
  formattedText,
}: ExportControlsProps) {
  const { getToken } = useAuth();
  const [toast, setToast] = useState<{
    message: string;
    type: ToastType;
  } | null>(null);

  const showToast = useCallback(
    (message: string, type: ToastType = "success") => {
      setToast({ message, type });
      setTimeout(() => setToast(null), 3000);
    },
    []
  );

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(formattedText);
      showToast("Copied!");
    } catch {
      showToast("Failed to copy to clipboard.", "error");
    }
  }, [formattedText, showToast]);

  const handleDownload = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) {
        showToast("Authentication required.", "error");
        return;
      }

      const apiUrl = process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? "";
      const response = await fetch(
        `${apiUrl}/meetings/${meetingId}/report/download`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error("Download request failed");
      }

      const data = (await response.json()) as { url?: string };
      if (data.url) {
        // Trigger download via pre-signed URL
        const link = document.createElement("a");
        link.href = data.url;
        link.download = `meeting-${meetingId}-minutes.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch {
      showToast("Failed to download. Please try again.", "error");
    }
  }, [meetingId, getToken, showToast]);

  return (
    <div style={{ position: "relative" }}>
      {/* Toast notification */}
      {toast && (
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
            borderColor:
              toast.type === "success" ? "var(--success)" : "var(--error)",
            borderWidth: 1,
            borderStyle: "solid",
            color:
              toast.type === "success" ? "var(--success)" : "var(--error)",
            fontSize: "var(--text-small)",
            animation: "fade-in-up var(--duration-normal) var(--ease-out)",
          }}
        >
          {toast.message}
        </div>
      )}

      {/* Export buttons */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-3)",
          alignItems: "center",
        }}
      >
        <button
          className="btn-secondary"
          onClick={handleCopy}
          aria-label="Copy to clipboard"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <rect
              x="5"
              y="5"
              width="9"
              height="9"
              rx="1.5"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path
              d="M11 5V3.5A1.5 1.5 0 009.5 2h-6A1.5 1.5 0 002 3.5v6A1.5 1.5 0 003.5 11H5"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
          Copy to Clipboard
        </button>

        <button
          className="btn-secondary"
          onClick={handleDownload}
          aria-label="Download JSON"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M8 2v8m0 0l-3-3m3 3l3-3"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M2 11v1.5A1.5 1.5 0 003.5 14h9a1.5 1.5 0 001.5-1.5V11"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          Download JSON
        </button>
      </div>
    </div>
  );
}
