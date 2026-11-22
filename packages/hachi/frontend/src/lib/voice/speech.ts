// ============================================================
// Hachi Web App — speech helpers
//
// Two engines power the composer's voice features:
//   1. Browser Web Speech API  — live dictation streamed into the
//      textarea + single-utterance capture for push-to-talk. Needs no
//      backend; available in Chromium browsers.
//   2. Gateway STT (/voice/transcribe) — MediaRecorder → server Whisper.
//      Used as a fallback when Web Speech is unavailable, and as the
//      preferred engine for continuous mode when configured.
//
// TTS likewise falls back from gateway /voice/speak to the browser's
// SpeechSynthesis when no gateway voice is configured.
// ============================================================

import { transcribeAudio } from "../data/domains/voice";

/* eslint-disable @typescript-eslint/no-explicit-any */

// ---- Web Speech availability ----

function getSpeechRecognition(): any | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function browserSpeechSupported(): boolean {
  return getSpeechRecognition() != null;
}

export function browserTtsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

// ---- Web Speech recognition ----

export interface RecognizerHandle {
  /** Stop gracefully — onFinal fires with the accumulated transcript. */
  stop: () => void;
  /** Abort immediately — no onFinal. */
  abort: () => void;
}

export interface RecognitionOptions {
  /** Keep listening across pauses (dictation). Default false. */
  continuous?: boolean;
  lang?: string;
  /** Running transcript (committed finals + current interim). */
  onPartial?: (text: string) => void;
  /** Accumulated final transcript, delivered when recognition ends. */
  onFinal?: (text: string) => void;
  onError?: (err: string) => void;
  onEnd?: () => void;
}

/**
 * Start a Web Speech recognition session.
 *
 * @returns a handle to stop/abort, or null when Web Speech is unavailable.
 */
export function startRecognition(opts: RecognitionOptions): RecognizerHandle | null {
  const SR = getSpeechRecognition();
  if (!SR) return null;

  const rec = new SR();
  rec.lang = opts.lang ?? "en-US";
  rec.continuous = opts.continuous ?? false;
  rec.interimResults = true;

  let finalText = "";
  let closed = false;

  rec.onresult = (event: any) => {
    let interim = "";
    let committed = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const r = event.results[i];
      if (r.isFinal) committed += r[0].transcript;
      else interim += r[0].transcript;
    }
    if (committed) finalText += committed;
    opts.onPartial?.((finalText + interim).replace(/\s+/g, " ").trim());
  };
  rec.onerror = (e: any) => {
    opts.onError?.(typeof e?.error === "string" ? e.error : "speech-error");
  };
  rec.onend = () => {
    opts.onFinal?.(finalText.trim());
    opts.onEnd?.();
  };

  try {
    rec.start();
  } catch {
    return null;
  }

  return {
    stop: () => {
      if (closed) return;
      closed = true;
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    },
    abort: () => {
      if (closed) return;
      closed = true;
      try {
        rec.abort();
      } catch {
        /* ignore */
      }
    },
  };
}

// ---- Browser TTS ----

/**
 * Speak text via the browser SpeechSynthesis engine.
 * Resolves when playback finishes (or fails). Markdown is stripped first.
 */
export function browserSpeak(text: string): Promise<void> {
  return new Promise((resolve) => {
    const plain = stripMarkdown(text);
    if (!browserTtsSupported() || !plain) {
      resolve();
      return;
    }
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* ignore */
    }
    const utter = new SpeechSynthesisUtterance(plain);
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    try {
      window.speechSynthesis.speak(utter);
    } catch {
      resolve();
    }
  });
}

export function cancelBrowserSpeak(): void {
  if (!browserTtsSupported()) return;
  try {
    window.speechSynthesis.cancel();
  } catch {
    /* ignore */
  }
}

export function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!?\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[*_~#>]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// ---- Gateway record-and-transcribe (MediaRecorder → /voice/transcribe) ----

export interface RecordController {
  /** Finish recording; resolves `done` with the transcript. */
  stop: () => void;
  /** Discard the recording; resolves `done` with "". */
  cancel: () => void;
  /** Resolves with the transcript text, or "" on failure / too-short audio. */
  done: Promise<string>;
}

/**
 * Capture a single audio clip via MediaRecorder and transcribe it through the
 * gateway. Caller controls clip length via `stop()`.
 *
 * @throws if microphone access is denied (getUserMedia rejects).
 */
export async function recordAndTranscribe(): Promise<RecordController> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mimeType = pickAudioMime();
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: Blob[] = [];
  let cancelled = false;

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  const done = new Promise<string>((resolve) => {
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      if (cancelled) {
        resolve("");
        return;
      }
      const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
      if (blob.size < 1200) {
        resolve("");
        return;
      }
      try {
        const res = await transcribeAudio(blob);
        resolve(res.text.trim());
      } catch {
        resolve("");
      }
    };
  });

  recorder.start();

  return {
    stop: () => {
      if (recorder.state !== "inactive") recorder.stop();
    },
    cancel: () => {
      cancelled = true;
      if (recorder.state !== "inactive") recorder.stop();
    },
    done,
  };
}

export function pickAudioMime(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"];
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported?.(c)) return c;
  }
  return null;
}
