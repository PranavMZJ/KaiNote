"use client";

/**
 * AudioCapture — captures PCM 16-bit, 16kHz audio from the microphone
 * and encodes chunks as base64 for WebSocket transmission.
 *
 * Requirements: 2.2, 2.3, 2.6
 */

export type AudioChunkCallback = (base64Chunk: string) => void;

export interface AudioCaptureOptions {
  /** Called with each base64-encoded PCM chunk. */
  onChunk: AudioChunkCallback;
  /** Called when an error occurs (e.g. mic denied). */
  onError?: (error: Error) => void;
  /** Interval in ms between audio chunk emissions. Default: 250ms. */
  chunkIntervalMs?: number;
}

const TARGET_SAMPLE_RATE = 16000;

export class AudioCapture {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private options: AudioCaptureOptions;
  private _isCapturing = false;

  constructor(options: AudioCaptureOptions) {
    this.options = options;
  }

  get isCapturing(): boolean {
    return this._isCapturing;
  }

  /**
   * Request microphone access and start capturing PCM 16-bit 16kHz audio.
   * Each chunk is base64-encoded and delivered via the onChunk callback.
   */
  async start(): Promise<void> {
    if (this._isCapturing) return;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: TARGET_SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch (err) {
      const error =
        err instanceof Error
          ? err
          : new Error("Microphone access denied");
      this.options.onError?.(error);
      throw error;
    }

    this.audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
    this.source = this.audioContext.createMediaStreamSource(this.stream);

    // Use ScriptProcessorNode for broad compatibility.
    // Buffer size of 4096 at 16kHz ≈ 256ms per chunk.
    const bufferSize = 4096;
    this.processor = this.audioContext.createScriptProcessor(
      bufferSize,
      1,
      1
    );

    this.processor.onaudioprocess = (event: AudioProcessingEvent) => {
      if (!this._isCapturing) return;

      const inputData = event.inputBuffer.getChannelData(0);
      // Convert Float32 [-1, 1] to Int16 PCM
      const pcm16 = float32ToInt16(inputData);
      const base64 = arrayBufferToBase64(pcm16.buffer as ArrayBuffer);
      this.options.onChunk(base64);
    };

    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);
    this._isCapturing = true;
  }

  /**
   * Stop capturing audio and release all resources.
   */
  stop(): void {
    this._isCapturing = false;

    if (this.processor) {
      this.processor.disconnect();
      this.processor.onaudioprocess = null;
      this.processor = null;
    }

    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }

    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }
}

/**
 * Convert Float32Array audio samples to Int16Array (PCM 16-bit).
 */
function float32ToInt16(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16;
}

/**
 * Convert an ArrayBuffer to a base64 string.
 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
