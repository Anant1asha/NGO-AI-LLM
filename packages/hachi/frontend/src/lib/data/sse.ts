// ============================================================
// Hachi Web App — Server-Sent Events reader (foundation)
//
// We use fetch + ReadableStream rather than the native EventSource because
// EventSource cannot set an Authorization header. The gateway streams runtime
// events at GET /sessions/{id}/stream with frames shaped:
//
//   id: <sequence>
//   event: <event_type>      (e.g. text.stream.delta, tool.call.started)
//   data: <json>             (the full event envelope)
//
// Lines starting with ":" are comments/keepalives and are ignored.
// ============================================================

import { API_BASE, authHeaders } from "./client";

export interface SSEMessage {
  /** Last-Event-ID (gateway sequence number) if present. */
  id?: string;
  /** SSE event name; defaults to "message" when omitted. */
  event: string;
  /** Raw data payload (usually JSON text). */
  data: string;
}

export interface SSEHandlers {
  onMessage: (msg: SSEMessage) => void;
  onOpen?: () => void;
  onError?: (err: unknown) => void;
  onClose?: () => void;
}

export interface SSEOptions {
  params?: Record<string, unknown>;
  signal?: AbortSignal;
  /** Max ms to wait between chunks before aborting the stream. Default 3 minutes. */
  idleTimeoutMs?: number;
}

function buildSseUrl(path: string, params?: Record<string, unknown>): string {
  const base = path.startsWith("/") ? API_BASE + path : `${API_BASE}/${path}`;
  if (!params) return base;
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    usp.append(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `${base}?${qs}` : base;
}

/**
 * Open an SSE stream and dispatch parsed frames to `handlers.onMessage`.
 * Resolves when the stream ends (server close or aborted via `opts.signal`).
 * Does NOT auto-reconnect — callers own retry/backoff policy.
 */
export async function streamSSE(
  path: string,
  handlers: SSEHandlers,
  opts?: SSEOptions
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(buildSseUrl(path, opts?.params), {
      method: "GET",
      headers: authHeaders({ Accept: "text/event-stream" }),
      signal: opts?.signal,
    });
  } catch (err) {
    handlers.onError?.(err);
    return;
  }

  if (!res.ok || !res.body) {
    handlers.onError?.(new Error(`SSE ${path} → ${res.status}`));
    return;
  }

  handlers.onOpen?.();

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // Idle timeout: if no chunk arrives within idleTimeoutMs, cancel the stream.
  // Default 3 minutes — long enough for slow tasks but prevents zombie streams.
  const idleMs = opts?.idleTimeoutMs ?? 3 * 60 * 1000;
  let idleTimer: ReturnType<typeof setTimeout> | null = null;
  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      // ReadableStreamDefaultReader.read() has no AbortSignal overload. Cancel
      // the reader directly so the pending read resolves without retaining one
      // abort listener per received chunk.
      void reader.cancel("SSE idle timeout").catch(() => { /* already closed */ });
    }, idleMs);
  }

  function clearIdleTimer() {
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  }

  // Accumulators for the in-flight event frame.
  let evId: string | undefined;
  let evName = "message";
  let evData: string[] = [];

  const dispatch = () => {
    if (evData.length === 0 && evName === "message" && evId === undefined) return;
    handlers.onMessage({ id: evId, event: evName, data: evData.join("\n") });
    evId = undefined;
    evName = "message";
    evData = [];
  };

  // If the caller aborts, we also want to cancel the reader (not just the
  // fetch) so the loop exits cleanly without waiting for the next chunk.
  const callerSignal = opts?.signal;
  const onCallerAbort = () => {
    void reader.cancel("SSE caller aborted").catch(() => { /* already closed */ });
  };
  callerSignal?.addEventListener("abort", onCallerAbort);

  try {
    resetIdleTimer();
    for (;;) {
      const { value, done } = await reader.read();

      resetIdleTimer(); // chunk arrived — reset the idle window
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines; keep the trailing partial in `buffer`.
      let nl: number;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        let line = buffer.slice(0, nl);
        buffer = buffer.slice(nl + 1);
        if (line.endsWith("\r")) line = line.slice(0, -1);

        if (line === "") {
          dispatch(); // blank line terminates an event
          continue;
        }
        if (line.startsWith(":")) continue; // comment / keepalive

        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        let val = colon === -1 ? "" : line.slice(colon + 1);
        if (val.startsWith(" ")) val = val.slice(1);

        switch (field) {
          case "id":
            evId = val;
            break;
          case "event":
            evName = val;
            break;
          case "data":
            evData.push(val);
            break;
          default:
            break; // ignore unknown fields (e.g. retry)
        }
      }
    }
    dispatch(); // flush any trailing frame
  } catch (err) {
    // AbortError covers: caller cancelled (opts.signal), idle timeout,
    // and the race's own reject path. None of these are real stream errors.
    if (!(err instanceof DOMException && err.name === "AbortError")) {
      handlers.onError?.(err);
    }
  } finally {
    clearIdleTimer();
    callerSignal?.removeEventListener("abort", onCallerAbort);
    handlers.onClose?.();
    try {
      reader.cancel().catch(() => { /* ignore cancel errors */ });
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}
