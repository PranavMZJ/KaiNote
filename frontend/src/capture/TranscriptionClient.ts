"use client";

/**
 * TranscriptionClient — WebSocket client for the Fargate transcription service.
 *
 * Connects to the ALB-backed WebSocket endpoint and handles:
 * - Sending binary PCM audio chunks (not base64) for efficiency
 * - Receiving real-time transcript segments
 * - Session lifecycle (start → stream → stop)
 */

export interface TranscriptSegment {
  type: "transcript_segment";
  text: string;
  speaker: string;
  isPartial: boolean;
  timestamp: string;
}

export interface CaptureStoppedMessage {
  type: "capture_stopped";
  meetingId: string;
  status: string;
}

export interface TranscriptionErrorMessage {
  type: "error";
  message: string;
  code: string;
}

export type TranscriptionServerMessage =
  | TranscriptSegment
  | CaptureStoppedMessage
  | TranscriptionErrorMessage;

export interface TranscriptionClientOptions {
  /** Called when a transcript segment is received. */
  onSegment: (segment: TranscriptSegment) => void;
  /** Called when capture is stopped and processing begins. */
  onStopped: (meetingId: string) => void;
  /** Called when an error occurs. */
  onError: (error: string) => void;
  /** Called when the WebSocket connection opens. */
  onConnected?: () => void;
  /** Called when the WebSocket connection closes. */
  onDisconnected?: () => void;
}

const RECONNECT_ATTEMPTS = 3;
const BASE_BACKOFF_MS = 1000;

export class TranscriptionClient {
  private ws: WebSocket | null = null;
  private options: TranscriptionClientOptions;
  private _isConnected = false;
  private _meetingId: string | null = null;
  private _audioLanguage: string = "en-US";
  private _displayLanguage: string | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

  constructor(options: TranscriptionClientOptions) {
    this.options = options;
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  get meetingId(): string | null {
    return this._meetingId;
  }

  /**
   * Connect to the transcription service and start a session.
   *
   * @param meetingId - Unique meeting identifier
   * @param userId - Cognito user sub
   * @param token - JWT token for authentication
   * @param audioLanguage - Language of the audio (e.g., "en-US", "ja-JP")
   * @param displayLanguage - Language to display transcription in (for translation)
   */
  connect(meetingId: string, userId: string, token: string, audioLanguage?: string, displayLanguage?: string): void {
    this.intentionalClose = false;
    this.reconnectAttempts = 0;
    this._meetingId = meetingId;
    this._audioLanguage = audioLanguage || "en-US";
    this._displayLanguage = displayLanguage || null;

    const wsUrl = this.getWebSocketUrl();
    if (!wsUrl) {
      this.options.onError("NEXT_PUBLIC_TRANSCRIPTION_WS_URL is not configured");
      return;
    }

    this.createConnection(wsUrl, meetingId, userId, token);
  }

  /**
   * Send raw PCM audio data as a binary WebSocket message.
   * More efficient than base64 encoding — reduces bandwidth by ~33%.
   *
   * @param pcmData - Raw PCM 16-bit 16kHz audio buffer
   */
  sendAudio(pcmData: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(pcmData);
  }

  /**
   * Signal the server to stop transcription and begin post-processing.
   */
  stop(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type: "stop" }));
  }

  /**
   * Change the display language mid-session (triggers server-side translation).
   * Pass null or undefined to disable translation.
   */
  setDisplayLanguage(language: string | null): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this._displayLanguage = language;
    this.ws.send(JSON.stringify({
      type: "set_display_language",
      language: language,
    }));
  }

  /**
   * Close the WebSocket connection without triggering reconnection.
   */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._isConnected = false;
    this._meetingId = null;
  }

  // ---------------------------------------------------------------------------
  // Private
  // ---------------------------------------------------------------------------

  private getWebSocketUrl(): string | null {
    const baseUrl =
      typeof window !== "undefined"
        ? (process.env.NEXT_PUBLIC_TRANSCRIPTION_WS_URL ?? null)
        : null;

    if (!baseUrl) return null;

    // Ensure the URL ends with /ws
    const url = baseUrl.endsWith("/ws") ? baseUrl : `${baseUrl}/ws`;
    return url;
  }

  private createConnection(
    wsUrl: string,
    meetingId: string,
    userId: string,
    token: string
  ): void {
    this.ws = new WebSocket(wsUrl);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      this._isConnected = true;
      this.reconnectAttempts = 0;

      // Send start message to initiate transcription session
      const startMessage: Record<string, unknown> = {
        type: "start",
        meetingId,
        userId,
        token,
        audioLanguage: this._audioLanguage,
      };
      if (this._displayLanguage) {
        startMessage.displayLanguage = this._displayLanguage;
      }
      this.ws!.send(JSON.stringify(startMessage));

      this.options.onConnected?.();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;

      try {
        const message = JSON.parse(event.data) as TranscriptionServerMessage;
        this.handleMessage(message);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onerror = () => {
      this.options.onError("WebSocket connection error");
    };

    this.ws.onclose = () => {
      this._isConnected = false;
      this.options.onDisconnected?.();

      if (!this.intentionalClose) {
        this.attemptReconnect(meetingId, userId, token);
      }
    };
  }

  private handleMessage(message: TranscriptionServerMessage): void {
    switch (message.type) {
      case "transcript_segment":
        this.options.onSegment(message);
        break;

      case "capture_stopped":
        this.options.onStopped(message.meetingId);
        break;

      case "error":
        this.options.onError(`[${message.code}] ${message.message}`);
        break;
    }
  }

  private attemptReconnect(
    meetingId: string,
    userId: string,
    token: string
  ): void {
    if (this.reconnectAttempts >= RECONNECT_ATTEMPTS) {
      this.options.onError("Reconnection failed after maximum attempts");
      return;
    }

    const delay = BASE_BACKOFF_MS * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      const wsUrl = this.getWebSocketUrl();
      if (wsUrl) {
        this.createConnection(wsUrl, meetingId, userId, token);
      }
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
