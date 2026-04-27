"use client";

/**
 * WebSocketManager — manages WebSocket connection lifecycle for audio streaming.
 *
 * Connects to the WebSocket API with JWT auth, sends audio chunks,
 * handles incoming transcript/status messages, and implements
 * reconnection with exponential backoff.
 *
 * Requirements: 2.5, 2.6, 3.3, 12.1, 12.2
 */

export interface TranscriptSegment {
  type: "transcript";
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

export interface ProcessingCompleteMessage {
  type: "processing_complete";
  meetingId: string;
  reportUrl: string;
}

export interface ErrorMessage {
  type: "error";
  message: string;
  code: string;
}

export interface ConnectionWarningMessage {
  type: "connection_warning";
  message: string;
}

export type ServerMessage =
  | TranscriptSegment
  | CaptureStoppedMessage
  | ProcessingCompleteMessage
  | ErrorMessage
  | ConnectionWarningMessage;

export interface WebSocketManagerOptions {
  /** WebSocket API URL (from env). */
  url: string;
  /** JWT token for authentication. */
  token: string;
  /** Called when a server message is received. */
  onMessage: (message: ServerMessage) => void;
  /** Called when the connection is established. */
  onOpen?: () => void;
  /** Called when the connection is closed. */
  onClose?: () => void;
  /** Called when a connection error occurs. */
  onError?: (error: Event) => void;
  /** Called when reconnection attempts are exhausted. */
  onReconnectFailed?: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 3;
const BASE_BACKOFF_MS = 1000;

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private options: WebSocketManagerOptions;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _isConnected = false;
  private _intentionalClose = false;

  constructor(options: WebSocketManagerOptions) {
    this.options = options;
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  /**
   * Open the WebSocket connection with JWT in query parameter.
   */
  connect(): void {
    this._intentionalClose = false;
    this.reconnectAttempts = 0;
    this.createConnection();
  }

  /**
   * Send an audio_chunk message with base64-encoded PCM data.
   */
  sendAudioChunk(base64Data: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(
      JSON.stringify({
        action: "audio_chunk",
        data: base64Data,
      })
    );
  }

  /**
   * Send stop_capture message to signal end of recording.
   */
  sendStopCapture(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(
      JSON.stringify({
        action: "stop_capture",
      })
    );
  }

  /**
   * Close the connection intentionally (no reconnect).
   */
  disconnect(): void {
    this._intentionalClose = true;
    this.clearReconnectTimer();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._isConnected = false;
  }

  private createConnection(): void {
    const separator = this.options.url.includes("?") ? "&" : "?";
    const wsUrl = `${this.options.url}${separator}token=${encodeURIComponent(this.options.token)}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this._isConnected = true;
      this.reconnectAttempts = 0;
      this.options.onOpen?.();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string) as ServerMessage;
        this.options.onMessage(message);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onerror = (event: Event) => {
      this.options.onError?.(event);
    };

    this.ws.onclose = () => {
      this._isConnected = false;
      this.options.onClose?.();

      if (!this._intentionalClose) {
        this.attemptReconnect();
      }
    };
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.options.onReconnectFailed?.();
      return;
    }

    // Exponential backoff: 1s, 2s, 4s
    const delay = BASE_BACKOFF_MS * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.createConnection();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
