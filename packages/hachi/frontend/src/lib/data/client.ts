// ============================================================
// Hachi Web App — HTTP client (foundation)
// Single entry point for all gateway calls. Shaped to the gateway
// OpenAPI (openapi/hachi-openapi.json).
//
// Connectivity model
// ------------------
// In dev, requests go to `/api/...` and Vite proxies them to the gateway
// (default http://127.0.0.1:8787), injecting `Authorization: Bearer <token>`
// from the HACHI_GATEWAY_TOKEN env var. This sidesteps CORS and keeps the
// token out of client JS. See vite.config.ts.
//
// In prod / direct mode, set VITE_HACHI_GATEWAY_URL to the gateway origin and
// optionally VITE_HACHI_TOKEN to attach the bearer header from the browser.
//
// Mocks
// -----
// VITE_HACHI_USE_MOCKS=true forces every wired domain to keep its seeded
// fixtures instead of hitting the network (offline UI work). Gap domains
// (Memory, OG, Authoring, Spend, .og skill list) have no endpoint yet and
// always behave as mock regardless of this flag — see DATA_GAPS below.
// ============================================================

const env = import.meta.env as Record<string, string | undefined>;

/** Base path/origin for every gateway call. Defaults to the proxied `/api`. */
export const API_BASE: string = (env.VITE_HACHI_GATEWAY_URL || "/api").replace(/\/$/, "");

/** When true, wired domains keep fixtures instead of calling the gateway. */
export const USE_MOCKS: boolean = String(env.VITE_HACHI_USE_MOCKS).toLowerCase() === "true";

/** Optional bearer token for direct (non-proxied) mode. Dev proxy injects its own. */
const DIRECT_TOKEN: string | undefined = env.VITE_HACHI_TOKEN || undefined;

/**
 * Domains the UI renders but the gateway does not yet expose. These screens
 * stay on mock data behind a visible flag. Keep this list in sync with the
 * "preview" badges in the routes so the gap is honest, not hidden.
 */
// All formerly-listed gaps are now wired to real gateway endpoints
// (see docs/web/backend-api-gaps.md §1–6). Kept as an (empty) export so
// any `DATA_GAPS.includes(...)` call sites and the `DataGap` type stay valid.
export const DATA_GAPS = [] as const;
export type DataGap = (typeof DATA_GAPS)[number] | string;

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * Returns true when the error is a genuine network failure or a gateway-down
 * proxy error.
 *
 * Two cases:
 *  1. fetch() itself rejected (status 0, code "network_error") — connection
 *     refused, DNS failure, offline, or CORS preflight rejection.
 *  2. In dev the Vite proxy sits between the browser and the gateway. When
 *     the gateway process is DOWN the proxy returns 502/503/504 — the server
 *     was technically reachable (the proxy) but the real backend is absent.
 *     We treat these proxy error codes as connectivity loss so the reconnecting
 *     indicator fires correctly. A 500 from a live gateway with a JSON error
 *     body is NOT caught here (it has a readable ApiError message instead).
 */
export function isNetworkError(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === 0 && err.code === "network_error") return true;
  // Vite-proxy-down heuristic: 502 Bad Gateway, 503 Service Unavailable,
  // 504 Gateway Timeout all indicate the upstream gateway is unreachable.
  if (err.status === 502 || err.status === 503 || err.status === 504) return true;
  return false;
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
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

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {};
  if (extra) Object.assign(headers, extra as Record<string, string>);
  // Direct mode only — the dev proxy injects auth server-side.
  if (DIRECT_TOKEN && !("Authorization" in headers)) {
    headers.Authorization = `Bearer ${DIRECT_TOKEN}`;
  }
  return headers;
}

async function parseError(res: Response, method: string, path: string): Promise<ApiError> {
  let code: string | undefined;
  let message = `API ${method} ${path} → ${res.status}`;
  let details: unknown;
  try {
    const body = await res.json();
    // Gateway ErrorResponse: { code, message, details }
    if (body && typeof body === "object") {
      code = (body as Record<string, unknown>).code as string | undefined;
      const m = (body as Record<string, unknown>).message;
      if (typeof m === "string" && m) message = m;
      details = (body as Record<string, unknown>).details;
    }
  } catch {
    /* non-JSON error body — keep the generic message */
  }
  return new ApiError(message, res.status, code, details);
}

// Module-level callback registered by the store to avoid a circular import.
// client.ts → store.ts → client.ts would be a cycle; instead the store
// calls registerReconnectCallback() at startup to inject setReconnecting.
type ReconnectCallback = (v: boolean) => void;
let _setReconnecting: ReconnectCallback | null = null;

/**
 * Register the store's setReconnecting action so the HTTP client can flip the
 * reconnecting flag centrally. Called once at app startup (from bootstrap or
 * __root.tsx). If never called, the flag is simply not updated from here.
 */
export function registerReconnectCallback(cb: ReconnectCallback): void {
  _setReconnecting = cb;
}

async function request<T>(
  method: string,
  path: string,
  opts?: { body?: unknown; params?: Record<string, unknown>; signal?: AbortSignal }
): Promise<T> {
  const headers = authHeaders(
    opts?.body !== undefined ? { "Content-Type": "application/json" } : undefined
  );

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts?.params), {
      method,
      headers,
      body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts?.signal,
    });
  } catch (fetchErr) {
    // fetch() rejected — server is genuinely unreachable (connection refused,
    // DNS failure, offline, CORS preflight rejection). Signal reconnecting.
    _setReconnecting?.(true);
    const msg = fetchErr instanceof Error ? fetchErr.message : "Network error";
    throw new ApiError(msg, 0, "network_error");
  }

  // We reached the server (any HTTP response, including 5xx) — clear reconnecting.
  _setReconnecting?.(false);

  if (!res.ok) throw await parseError(res, method, path);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function apiGet<T>(
  path: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal
): Promise<T> {
  return request<T>("GET", path, { params, signal });
}

export function apiSend<T>(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  signal?: AbortSignal
): Promise<T> {
  return request<T>(method, path, { body, signal });
}
