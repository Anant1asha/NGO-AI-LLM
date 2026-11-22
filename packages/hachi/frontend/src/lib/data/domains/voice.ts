// ============================================================
// Hachi Web App — voice domain adapter
//
// Wires: POST /voice/transcribe, POST /voice/speak,
//        GET /voice/config, PUT /voice/config
//
// All calls go through the standard gateway base + bearer pattern
// (Vite proxy in dev, VITE_HACHI_GATEWAY_URL in prod).
// ============================================================

import { API_BASE, authHeaders, ApiError } from "../client";

// ---- Types ----

export interface VoiceConfig {
  stt_provider: string;
  tts_provider: string;
  tts_voice: string;
  stt_model: string | null;
  tts_model: string | null;
  elevenlabs_voice_id: string | null;
  available: {
    tts_providers: string[];
    voices: string[];
  };
  configured: boolean;
}

export interface VoiceConfigPatch {
  stt_provider?: string;
  tts_provider?: string;
  tts_voice?: string;
  stt_model?: string;
  tts_model?: string;
  stt_base_url?: string;
  tts_base_url?: string;
  stt_api_key_env?: string;
  tts_api_key_env?: string;
  elevenlabs_api_key_env?: string;
  elevenlabs_voice_id?: string;
}

export interface TranscribeResult {
  text: string;
  language?: string;
}

export interface SpeakOptions {
  voice?: string;
  model?: string;
  format?: "mp3" | "opus" | "aac" | "flac" | "wav";
  provider?: string;
}

// ---- Adapters ----

/**
 * Upload a recorded audio Blob and receive the transcript text.
 *
 * Sends a multipart/form-data POST to POST /voice/transcribe.
 * The file field is named "audio"; filename is derived from the MIME type.
 *
 * @param blob - Raw audio Blob from MediaRecorder (webm, wav, etc.)
 * @returns The transcript result including the `text` field.
 * @throws ApiError on gateway/network errors.
 */
export async function transcribeAudio(blob: Blob): Promise<TranscribeResult> {
  const ext = _blobExt(blob.type);
  const form = new FormData();
  form.append("audio", blob, `recording.${ext}`);

  const url = `${API_BASE}/voice/transcribe`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(msg, 0, "network_error");
  }

  if (!res.ok) {
    let message = `POST /voice/transcribe → ${res.status}`;
    try {
      const body = await res.json() as Record<string, unknown>;
      if (typeof body.message === "string") message = body.message;
    } catch { /* ignore */ }
    throw new ApiError(message, res.status);
  }

  return res.json() as Promise<TranscribeResult>;
}

/**
 * Synthesize text to speech and return a temporary object URL for playback.
 *
 * P1 streaming path: pipes `res.body` (ReadableStream) into a `MediaSource` +
 * `SourceBuffer` so audio starts as bytes arrive — no full-blob wait.  Falls
 * back to the blob path when MediaSource is unavailable or the codec is not
 * supported by the browser.
 *
 * The caller must revoke the returned URL with `URL.revokeObjectURL(url)` after
 * playback finishes.
 *
 * @param text - The text to synthesize.
 * @param opts - Optional overrides for voice, model, format, and provider.
 * @returns A temporary object URL that resolves to the audio (streaming or blob).
 * @throws ApiError on gateway/network errors.
 */
export async function speakText(text: string, opts: SpeakOptions = {}): Promise<string> {
  const fmt = opts.format ?? "mp3";
  const url = `${API_BASE}/voice/speak`;
  const body = {
    text,
    voice: opts.voice,
    model: opts.model,
    format: fmt,
    provider: opts.provider,
  };

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(msg, 0, "network_error");
  }

  if (!res.ok) {
    let message = `POST /voice/speak → ${res.status}`;
    try {
      const errBody = await res.json() as Record<string, unknown>;
      if (typeof errBody.message === "string") message = errBody.message;
    } catch { /* ignore */ }
    throw new ApiError(message, res.status);
  }

  const contentType = res.headers.get("Content-Type") ?? "audio/mpeg";

  // --- P1: Try MediaSource streaming path first ---
  const mediaSourceUrl = _tryStreamViaMediaSource(res, contentType);
  if (mediaSourceUrl !== null) {
    return mediaSourceUrl;
  }

  // --- Fallback: buffer the full blob (original behaviour) ---
  const audioBlob = await res.blob();
  const typedBlob = new Blob([audioBlob], { type: contentType });
  return URL.createObjectURL(typedBlob);
}

/**
 * Attempt to pipe the fetch response stream into a MediaSource so playback
 * starts as bytes arrive.  Returns the MediaSource object URL on success,
 * or `null` when MediaSource / the codec is unsupported (caller falls back
 * to blob path).
 *
 * @internal
 */
function _tryStreamViaMediaSource(res: Response, contentType: string): string | null {
  // Guard: MediaSource must exist and the response must have a readable body.
  if (
    typeof MediaSource === "undefined" ||
    !res.body ||
    typeof MediaSource.isTypeSupported !== "function"
  ) {
    return null;
  }

  // Map gateway content-type to a MediaSource-compatible MIME string.
  // MediaSource needs a codec hint for some formats.
  const mimeMap: Record<string, string> = {
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
    "audio/ogg": "audio/ogg; codecs=opus",
    "audio/ogg; codecs=opus": "audio/ogg; codecs=opus",
    "audio/aac": "audio/aac",
    "audio/flac": "audio/flac",
    "audio/wav": "audio/wav",
  };
  const baseType = contentType.split(";")[0].trim().toLowerCase();
  const mimeType = mimeMap[baseType] ?? mimeMap[contentType.toLowerCase()] ?? contentType;

  if (!MediaSource.isTypeSupported(mimeType)) {
    return null;
  }

  try {
    const ms = new MediaSource();
    const objectUrl = URL.createObjectURL(ms);

    // Pipe the stream asynchronously; the caller gets the URL immediately.
    ms.addEventListener(
      "sourceopen",
      () => {
        let sb: SourceBuffer;
        try {
          sb = ms.addSourceBuffer(mimeType);
        } catch {
          // If addSourceBuffer fails (e.g. quota / codec mismatch) abandon the MS.
          try {
            ms.endOfStream("decode");
          } catch { /* ignore */ }
          return;
        }

        const reader = res.body!.getReader();
        const appendQueue: Uint8Array[] = [];
        let appending = false;
        let streamDone = false;

        function maybeEndStream() {
          if (streamDone && appendQueue.length === 0 && !appending) {
            try {
              if (ms.readyState === "open") ms.endOfStream();
            } catch { /* ignore */ }
          }
        }

        function drainQueue() {
          if (appending || appendQueue.length === 0) return;
          const chunk = appendQueue.shift()!;
          appending = true;
          try {
            // Cast: a Uint8Array is a valid BufferSource at runtime; the TS 5.7
            // lib.dom types over-narrow to ArrayBuffer-backed views only.
            sb.appendBuffer(chunk as unknown as BufferSource);
          } catch {
            // Buffer full or decode error — skip this chunk.
            appending = false;
            drainQueue();
          }
        }

        sb.addEventListener("updateend", () => {
          appending = false;
          drainQueue();
          maybeEndStream();
        });

        function pump(): void {
          reader
            .read()
            .then(({ done, value }) => {
              if (done) {
                streamDone = true;
                maybeEndStream();
                return;
              }
              if (value) appendQueue.push(value);
              drainQueue();
              pump();
            })
            .catch(() => {
              streamDone = true;
              try {
                if (ms.readyState === "open") ms.endOfStream("network");
              } catch { /* ignore */ }
            });
        }

        pump();
      },
      { once: true },
    );

    return objectUrl;
  } catch {
    return null;
  }
}

/**
 * Fetch the current voice configuration from the gateway.
 *
 * @returns The gateway voice config summary.
 * @throws ApiError on network/gateway errors.
 */
export async function getVoiceConfig(): Promise<VoiceConfig> {
  const url = `${API_BASE}/voice/config`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "GET",
      headers: authHeaders(),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(msg, 0, "network_error");
  }
  if (!res.ok) throw new ApiError(`GET /voice/config → ${res.status}`, res.status);
  return res.json() as Promise<VoiceConfig>;
}

/**
 * Persist voice config fields via the gateway and return the updated config.
 *
 * @param patch - Partial voice settings to persist.
 * @returns The updated voice config summary.
 * @throws ApiError on network/gateway errors.
 */
export async function setVoiceConfig(patch: VoiceConfigPatch): Promise<VoiceConfig> {
  const url = `${API_BASE}/voice/config`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(patch),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(msg, 0, "network_error");
  }
  if (!res.ok) throw new ApiError(`PUT /voice/config → ${res.status}`, res.status);
  return res.json() as Promise<VoiceConfig>;
}

// ---- Helpers ----

function _blobExt(mimeType: string): string {
  const map: Record<string, string> = {
    "audio/webm": "webm",
    "audio/webm;codecs=opus": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/flac": "flac",
  };
  const base = mimeType.split(";")[0].trim().toLowerCase();
  return map[base] ?? "webm";
}
