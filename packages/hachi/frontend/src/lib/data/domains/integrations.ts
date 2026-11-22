// ============================================================
// Hachi Web App — integrations + MCP inventory domain
// Wires:
//   GET /capabilities  → Integration[] (native integrations only)
//   GET /runtime/mcp/inventory → McpServer[] + McpTool[]
//   PUT /capabilities/{id}/enabled → connect/disconnect toggle (apikey/"none" connectors)
//   POST /integrations/{id}/oauth/start → { authorization_url } (OAuth2 connectors)
//   POST /integrations/{id}/disconnect → disconnect OAuth token
//   POST /runtime/mcp/register → register new MCP server (stdio/sse/http)
//   POST /runtime/mcp/{name}/enable  → enable an MCP server
//   POST /runtime/mcp/{name}/disable → disable an MCP server
//   DELETE /runtime/mcp/{name}       → remove an MCP server
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { Integration, McpServer, McpTool } from "../types";

// ============================================================
// 1. Raw gateway shapes (mirror Python dicts exactly)
// ============================================================

/**
 * A single credential field descriptor from the connector registry.
 * Returned by GET /integrations so the UI can render the correct form.
 */
export interface CredentialFieldSpec {
  /** Storage key used in the vault (e.g. "telegram_bot_token"). */
  key: string;
  /** Human-readable label for the form field. */
  label: string;
  /** When true the UI should use a password input. */
  secret: boolean;
  /** Example value shown as placeholder text. */
  placeholder: string;
  /** When true the field is not required for configured=true status. */
  optional: boolean;
  /** Short description shown below the field. */
  help_text?: string;
}

/** Raw capability entry from GET /capabilities */
interface GatewayCapability {
  id: string;
  kind?: string;           // always "native_integration", but tolerate omission
  enabled?: boolean;
  configured?: boolean;
  connected?: boolean;     // real OAuth token present
  auth_type?: "oauth2" | "apikey" | "none";
  secret_ref?: string | null;
}

/** Raw connector status entry from GET /integrations */
interface GatewayIntegrationStatus {
  id: string;
  name?: string;
  category?: string;
  auth_type?: "oauth2" | "apikey" | "none";
  configured?: boolean;
  connected?: boolean;
  status?: string;
  credential_fields?: CredentialFieldSpec[];
  /** Where the credential was loaded from (C-CREDSOURCE). */
  source?: "vault" | "env" | null;
  /**
   * When true, web search is falling back to Playwright because Tavily is
   * not configured or unreachable (C-SEARCHFALLBACK).
   */
  fallback_active?: boolean;
}

/** Raw MCP server entry inside GET /runtime/mcp/inventory */
interface GatewayMcpServer {
  name?: string;
  status?: string;
  tool_count?: number;
  tools?: string[];
  transport?: string;      // "stdio" | "sse" | "http"
  uptime?: string;
  err?: string;
  /** Whether the server is enabled (new field from backend contract). */
  enabled?: boolean;
}

/** Raw response from GET /runtime/mcp/inventory */
interface GatewayMcpInventory {
  server_count?: number;
  total_tool_count?: number;
  servers?: GatewayMcpServer[];
}

/**
 * McpServer extended with the `enabled` field from the backend inventory contract.
 * The base McpServer type (types.ts) does not carry this field; keep the extension
 * here so types.ts remains a pure UI-shape and this domain owns the transport contract.
 */
export interface McpServerExtended extends McpServer {
  /** Whether the server is currently enabled. Defaults to true when absent. */
  enabled: boolean;
}

/** Response from POST /integrations/{id}/oauth/start */
interface GatewayOAuthStartResponse {
  authorization_url: string;
  message?: string;
}

/** Response from POST /integrations/{id}/disconnect */
interface GatewayDisconnectResponse {
  id: string;
  connected: boolean;
  message?: string;
}

/** Response from POST/DELETE /integrations/{id}/credentials */
interface GatewayCredentialResponse extends GatewayIntegrationStatus {
  id: string;
}

// ============================================================
// 2. Extended Integration type with OAuth fields
// ============================================================

/**
 * Integration shape extended with OAuth/auth fields.
 * These are inline types (not touching schema.d.ts).
 */
export interface IntegrationExtended extends Integration {
  auth_type: "oauth2" | "apikey" | "none";
  /** True when a real token is stored for this connector. */
  connected: boolean;
  /** True when the admin has configured client credentials for OAuth, or when
   * all required apikey credential fields are present in the vault / env. */
  configured: boolean;
  /**
   * Field descriptors for apikey connectors.  Empty array for OAuth2 / none connectors.
   * Returned by GET /integrations so the UI can render a dynamic credential form.
   */
  credential_fields: CredentialFieldSpec[];
  /**
   * Where the credential was loaded from (C-CREDSOURCE).
   * "vault" = user saved via credential dialog, "env" = set in env vars,
   * null = not yet configured.
   */
  source?: "vault" | "env" | null;
  /**
   * When true, this integration (Tavily/web-search) is falling back to
   * Playwright because Tavily is not reachable (C-SEARCHFALLBACK).
   */
  fallback_active?: boolean;
}

// ============================================================
// 3. Pure adapters: gateway shape → UI types
// ============================================================

/**
 * Derive a human-readable name from a capability id (e.g. "google" → "Google").
 * Handles common compound ids like "google_calendar" → "Google Calendar".
 */
function prettyName(id: string): string {
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

/**
 * Map capability id → short description of what it can do.
 * Falls back to a generic string for unknown ids — adapter must never throw.
 */
function capabilityDescription(id: string): string {
  const descriptions: Record<string, string> = {
    google: "Read Gmail, Calendar, Drive",
    gmail: "Read and send email",
    google_calendar: "Read and create calendar events",
    google_drive: "Read and write Drive files",
    slack: "Send messages, read channels",
    notion: "Read and write Notion pages",
    github: "Read repos, open issues and PRs",
    linear: "Create and update issues",
    telegram: "Send Telegram messages",
    discord: "Send Discord messages",
    whatsapp: "Send WhatsApp messages",
    tavily: "Web search via Tavily",
  };
  return descriptions[id.toLowerCase()] ?? "Access external service";
}

/**
 * Heuristic: mark a capability as risky when it includes broad or destructive scopes.
 * Keeps it simple — this is a UI hint, not a security gate.
 */
function isRisky(id: string): boolean {
  const riskyIds = new Set(["github", "google_drive", "google"]);
  return riskyIds.has(id.toLowerCase());
}

/**
 * Derive an icon name from the capability id.
 * Falls back to "plug" so the UI always has something to render.
 */
function iconFromId(id: string): string {
  const icons: Record<string, string> = {
    google: "google",
    gmail: "mail",
    google_calendar: "calendar",
    google_drive: "folder",
    slack: "slack",
    notion: "notion",
    github: "github",
    linear: "linear",
    telegram: "telegram",
    discord: "discord",
    whatsapp: "whatsapp",
    tavily: "globe",
  };
  return icons[id.toLowerCase()] ?? "plug";
}

/**
 * Adapt a raw GatewayCapability → UI IntegrationExtended.
 *
 * Status mapping:
 *   If auth_type === "oauth2": use `connected` field for real token presence.
 *   If auth_type === "apikey": use `configured` field (vault/env creds present).
 *   Otherwise: configured && enabled → "connected", configured && !enabled → "degraded".
 */
function adaptCapability(raw: GatewayCapability): IntegrationExtended {
  const enabled = Boolean(raw.enabled);
  const configured = Boolean(raw.configured);
  const connected = Boolean(raw.connected);
  const authType: IntegrationExtended["auth_type"] = raw.auth_type ?? "none";

  let status: Integration["status"];
  if (authType === "oauth2") {
    status = connected ? "connected" : "none";
  } else if (authType === "apikey") {
    // For apikey connectors, configured = all required creds present.
    status = configured ? "connected" : "none";
  } else {
    status = configured && enabled
      ? "connected"
      : configured && !enabled
      ? "degraded"
      : "none";
  }

  return {
    id: raw.id ?? "unknown",
    icon: iconFromId(raw.id ?? ""),
    name: prettyName(raw.id ?? "unknown"),
    can: capabilityDescription(raw.id ?? ""),
    status,
    risky: isRisky(raw.id ?? ""),
    auth_type: authType,
    connected,
    configured,
    credential_fields: [],  // capabilities endpoint doesn't return these
  };
}

/**
 * Adapt a raw GatewayIntegrationStatus → UI IntegrationExtended.
 *
 * Used for the GET /integrations response which includes credential_fields.
 */
function adaptIntegrationStatus(raw: GatewayIntegrationStatus): IntegrationExtended {
  const configured = Boolean(raw.configured);
  const connected = Boolean(raw.connected);
  const authType: IntegrationExtended["auth_type"] = raw.auth_type ?? "none";

  let status: Integration["status"];
  if (authType === "oauth2") {
    status = connected ? "connected" : "none";
  } else if (authType === "apikey") {
    status = configured ? "connected" : "none";
  } else {
    status = "none";
  }

  return {
    id: raw.id ?? "unknown",
    icon: iconFromId(raw.id ?? ""),
    name: raw.name ? (prettyName(raw.id ?? raw.name)) : prettyName(raw.id ?? "unknown"),
    can: capabilityDescription(raw.id ?? ""),
    status,
    risky: isRisky(raw.id ?? ""),
    auth_type: authType,
    connected,
    configured,
    credential_fields: Array.isArray(raw.credential_fields) ? raw.credential_fields : [],
    source: raw.source ?? null,
    fallback_active: raw.fallback_active ?? false,
  };
}

/**
 * Adapt a raw GatewayMcpServer → UI McpServer.
 * Gateway status values ("connected", "starting", "blocked", etc.) are mapped
 * to the UI's allowed literal union; unknown values fall back to "starting".
 */
export function adaptMcpServer(raw: GatewayMcpServer): McpServerExtended {
  const rawStatus = (raw.status ?? "").toLowerCase();
  const statusMap: Record<string, McpServer["status"]> = {
    connected: "connected",
    ready: "connected",
    running: "connected",
    starting: "starting",
    loading: "loading",
    initialising: "loading",
    initializing: "loading",
    // BB-16: backend statuses that mean "registered but not running this
    // session". These must NOT fall through to the "starting" default (a
    // misleading orange "starting…" that never resolves) — they're idle, not
    // booting. "pending" renders as "needs restart".
    pending_restart: "pending",
    stopped: "pending",
    pending: "pending",
    blocked: "blocked",
    failed: "blocked",
    error: "blocked",
  };
  const status: McpServer["status"] = statusMap[rawStatus] ?? "starting";

  return {
    name: raw.name ?? "unknown",
    status,
    tools: raw.tool_count ?? 0,
    transport: raw.transport ?? "—",
    uptime: raw.uptime ?? "—",
    err: raw.err,
    enabled: raw.enabled ?? true,
  };
}

/** Response from POST /integrations/{id}/credentials/test (C-CREDTEST). */
export interface CredentialTestResult {
  ok: boolean;
  message: string;
}

/**
 * Test stored credentials for an apikey connector without saving them.
 *
 * Contract (C-CREDTEST):
 *   POST /integrations/{id}/credentials/test → { ok: boolean, message: string }
 *
 * Degrades gracefully on 404 (endpoint not yet deployed) — returns null so the
 * caller can hide/disable the test button.
 *
 * @throws ApiError on other network/server errors (caller should show the message).
 */
export async function testCredentials(
  id: string,
): Promise<CredentialTestResult | null> {
  if (USE_MOCKS) return { ok: true, message: "Mock: credentials look good" };
  try {
    return await apiSend<CredentialTestResult>(
      "POST",
      `/integrations/${id}/credentials/test`,
    );
  } catch (err) {
    // 404 → endpoint not deployed yet → signal "not available"
    if (
      typeof err === "object" &&
      err !== null &&
      "status" in err &&
      (err as { status: number }).status === 404
    ) {
      return null;
    }
    throw err;
  }
}

/**
 * Expand a single GatewayMcpServer's tools array → UI McpTool[].
 * The gateway provides tool names only (no argument schemas), so args is always [].
 */
function adaptMcpTools(raw: GatewayMcpServer): McpTool[] {
  const serverName = raw.name ?? "unknown";
  return (raw.tools ?? []).map((toolName) => ({
    name: toolName,
    server: serverName,
    args: [] as [string, string][],
  }));
}

// ============================================================
// 4. Loader: fetch → adapt → hydrate (NEVER throws)
// ============================================================

// Tracks whether this domain has ever received real data from the gateway.
let _hasEverSucceeded = false;

/**
 * Load native integrations and MCP inventory, then hydrate the store.
 *
 * Strategy:
 *   1. Try GET /integrations (connector registry — includes credential_fields).
 *      Falls back to GET /capabilities (legacy — no credential_fields) if that
 *      endpoint is unavailable (older gateway versions).
 *   2. GET /runtime/mcp/inventory for MCP server list.
 */
export async function loadIntegrations(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures

  const { hydrate } = useStore.getState();

  try {
    const [integrationStatuses, mcpInventory] = await Promise.all([
      // Prefer /integrations (has credential_fields); fall back to /capabilities.
      apiGet<GatewayIntegrationStatus[]>("/integrations").catch(() =>
        apiGet<GatewayCapability[]>("/capabilities").then((caps) =>
          (Array.isArray(caps) ? caps : []) as GatewayIntegrationStatus[]
        )
      ),
      apiGet<GatewayMcpInventory>("/runtime/mcp/inventory"),
    ]);

    const rawStatuses = Array.isArray(integrationStatuses) ? integrationStatuses : [];
    // Prefer adaptIntegrationStatus (has credential_fields awareness).
    const integrations: Integration[] = rawStatuses.map((raw) =>
      "credential_fields" in raw
        ? adaptIntegrationStatus(raw as GatewayIntegrationStatus)
        : adaptCapability(raw as GatewayCapability)
    );

    const rawServers: GatewayMcpServer[] = mcpInventory?.servers ?? [];
    const mcpServers: McpServer[] = rawServers.map(adaptMcpServer);
    const mcpTools: McpTool[] = rawServers.flatMap(adaptMcpTools);

    hydrate({ integrations, mcpServers, mcpTools });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      hydrate({ integrations: [], mcpServers: [], mcpTools: [] });
    }
  } finally {
    useStore.getState().setLoaded("integrations");
  }
}

// Self-register so bootstrapLiveData() picks this loader up automatically.
registerLoader("integrations", loadIntegrations);

// ============================================================
// 5. Mutation wrappers — OAuth connect / disconnect
// ============================================================

/** Status tracked per-integration to prevent double-submission. */
export type ActionStatus = "idle" | "loading" | "error";

const _connectStatus = new Map<string, ActionStatus>();
const _disconnectStatus = new Map<string, ActionStatus>();
const _statusListeners = new Set<() => void>();

/** Subscribe to status change notifications (used by the UI for re-render). */
export function subscribeActionStatus(cb: () => void): () => void {
  _statusListeners.add(cb);
  return () => _statusListeners.delete(cb);
}

function _notifyListeners() {
  _statusListeners.forEach((cb) => cb());
}

/** Get the current connect status for an integration id. */
export function getConnectStatus(id: string): ActionStatus {
  return _connectStatus.get(id) ?? "idle";
}

/** Get the current disconnect status for an integration id. */
export function getDisconnectStatus(id: string): ActionStatus {
  return _disconnectStatus.get(id) ?? "idle";
}

/**
 * Start an OAuth2 flow for the given connector.
 *
 * Contract (CONTRACT-OAUTH):
 *   POST /integrations/{id}/oauth/start → { authorization_url: string }
 *   May return 400/409 with { message } if client credentials aren't configured.
 *
 * Opens `authorization_url` in a popup window, waits for the popup to signal
 * completion (via a postMessage from the callback page, or popup close), then
 * re-runs the integrations loader to refresh real status from the gateway.
 *
 * @throws Error if the backend returns 400/409 (not configured) or on network error.
 */
export async function startIntegrationOAuth(id: string): Promise<void> {
  if (USE_MOCKS) return;

  const { authorization_url } = await apiSend<GatewayOAuthStartResponse>(
    "POST",
    `/integrations/${id}/oauth/start`,
  );

  await new Promise<void>((resolve, reject) => {
    // Open the OAuth provider page in a 600×700 popup.
    const width = 600;
    const height = 700;
    const left = Math.round(window.screenX + (window.outerWidth - width) / 2);
    const top = Math.round(window.screenY + (window.outerHeight - height) / 2);
    const popup = window.open(
      authorization_url,
      `hachi_oauth_${id}`,
      `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`,
    );

    if (!popup) {
      reject(new Error("Popup was blocked. Allow popups for this site and try again."));
      return;
    }

    // Capture as non-null reference so closures below can use it safely.
    const openedPopup: Window = popup;

    // Listen for a postMessage from the callback page (backend renders a tiny
    // HTML page that calls window.opener.postMessage({ type: "hachi_oauth_done" }, ...)).
    // SECURITY: reject any message whose origin differs from this app's own origin
    // so a malicious third-party popup cannot spoof the "hachi_oauth_done" signal.
    function onMessage(ev: MessageEvent) {
      if (
        ev.origin !== window.location.origin ||
        ev.source !== openedPopup ||
        !ev.data ||
        typeof ev.data !== "object" ||
        (ev.data as Record<string, unknown>).type !== "hachi_oauth_done"
      ) {
        return;
      }
      cleanup();
      openedPopup.close();
      resolve();
    }

    // Fallback: poll for popup close (handles cases where the callback page
    // doesn't postMessage back, e.g. same-origin redirects).
    let pollInterval: ReturnType<typeof setInterval> | null = null;
    pollInterval = setInterval(() => {
      if (openedPopup.closed) {
        cleanup();
        resolve();
      }
    }, 500);

    function cleanup() {
      window.removeEventListener("message", onMessage);
      if (pollInterval !== null) clearInterval(pollInterval);
    }

    window.addEventListener("message", onMessage);
  });

  // Refresh the integrations list so the new connected=true status shows.
  await loadIntegrations();
}

/**
 * Submit apikey credentials for a connector.
 *
 * Contract (CONTRACT-APIKEY-CREDS):
 *   POST /integrations/{id}/credentials
 *   Body: { fields: { [key]: value } }
 *   Response: updated connector status with configured/connected flags.
 *
 * On success, reloads the integrations list.
 *
 * @throws ApiError on network failure or backend validation error.
 */
export async function submitCredentials(
  id: string,
  fields: Record<string, string>,
): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayCredentialResponse>("POST", `/integrations/${id}/credentials`, { fields });
  await loadIntegrations();
}

/**
 * Clear stored apikey credentials for a connector.
 *
 * Contract (CONTRACT-APIKEY-CREDS):
 *   DELETE /integrations/{id}/credentials
 *   Response: updated connector status with configured=false.
 *
 * On success, reloads the integrations list.
 *
 * @throws ApiError on network failure or backend error.
 */
export async function clearCredentials(id: string): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayCredentialResponse>("DELETE", `/integrations/${id}/credentials`);
  await loadIntegrations();
}

/**
 * "Connect" an integration.
 *
 * - For oauth2 connectors: calls startIntegrationOAuth().
 * - For apikey connectors WITH credential_fields: caller should open a CredentialDialog
 *   (this function signals that by returning "needs_credentials"). The integration list
 *   item in the store carries the credential_fields schema.
 * - For apikey/"none" connectors without credential_fields: calls PUT /capabilities/{id}/enabled
 *   with { enabled: true } (optimistic update).
 *
 * Returns false if already in-flight (prevents double-click duplicates).
 * Returns "needs_credentials" when the connector needs a credential dialog.
 */
export async function connectIntegration(
  id: string,
  authType?: "oauth2" | "apikey" | "none",
  credentialFields?: CredentialFieldSpec[],
): Promise<boolean | "needs_credentials"> {
  if (_connectStatus.get(id) === "loading") return false;

  if (USE_MOCKS) {
    useStore.getState().connectIntegration(id);
    return true;
  }

  // Apikey connectors with declared credential fields need a credential dialog.
  // Signal the caller to open the dialog instead of making a network call here.
  if (authType === "apikey" && credentialFields && credentialFields.length > 0) {
    return "needs_credentials";
  }

  _connectStatus.set(id, "loading");
  _notifyListeners();

  try {
    if (authType === "oauth2") {
      await startIntegrationOAuth(id);
    } else {
      useStore.getState().connectIntegration(id);
      await apiSend<{ id: string; enabled: boolean; configured: boolean }>(
        "PUT",
        `/capabilities/${id}/enabled`,
        { enabled: true },
      );
      await loadIntegrations();
    }
    _connectStatus.set(id, "idle");
    _notifyListeners();
    return true;
  } catch {
    _connectStatus.set(id, "error");
    _notifyListeners();
    return false;
  }
}

/**
 * "Disconnect" an integration.
 *
 * - For oauth2 connectors: calls POST /integrations/{id}/disconnect to remove the token.
 * - For apikey connectors WITH credential_fields: calls DELETE /integrations/{id}/credentials.
 * - For apikey/"none" connectors without credential_fields: calls
 *   PUT /capabilities/{id}/enabled with { enabled: false }.
 *
 * Returns false if already in-flight.
 */
export async function disconnectIntegration(
  id: string,
  authType?: "oauth2" | "apikey" | "none",
  credentialFields?: CredentialFieldSpec[],
): Promise<boolean> {
  if (_disconnectStatus.get(id) === "loading") return false;

  if (USE_MOCKS) {
    useStore.getState().disconnectIntegration(id);
    return true;
  }

  _disconnectStatus.set(id, "loading");
  _notifyListeners();

  try {
    if (authType === "oauth2") {
      await apiSend<GatewayDisconnectResponse>(
        "POST",
        `/integrations/${id}/disconnect`,
      );
      await loadIntegrations();
    } else if (authType === "apikey" && credentialFields && credentialFields.length > 0) {
      await clearCredentials(id);  // calls DELETE /integrations/{id}/credentials + reload
    } else {
      useStore.getState().disconnectIntegration(id);
      await apiSend<{ id: string; enabled: boolean; configured: boolean }>(
        "PUT",
        `/capabilities/${id}/enabled`,
        { enabled: false },
      );
      await loadIntegrations();
    }
    _disconnectStatus.set(id, "idle");
    _notifyListeners();
    return true;
  } catch {
    _disconnectStatus.set(id, "error");
    _notifyListeners();
    return false;
  }
}

// ============================================================
// 6. MCP server registration — stdio + sse + http transports
// ============================================================

/** Allowed launcher commands for stdio transport (mirrors Python ALLOWED_MCP_COMMANDS). */
export const ALLOWED_MCP_COMMANDS = ["npx", "uvx", "python", "python3", "node", "uv"] as const;
export type McpCommand = (typeof ALLOWED_MCP_COMMANDS)[number];

/** MCP transport types supported by the register endpoint. */
export type McpTransport = "stdio" | "sse" | "http";

/**
 * Input shape for adding a new MCP server.
 * Transport determines which fields are required:
 *   - stdio: command + args (env_vars optional)
 *   - sse / http: url (headers optional)
 */
export interface AddMcpServerInput {
  /** Slug identifier, e.g. "github". Letters, digits, hyphens, underscores only. */
  name: string;
  /** Transport type. Defaults to "stdio". */
  transport: McpTransport;
  // --- stdio fields ---
  /** Launcher command. Required when transport === "stdio". */
  command?: McpCommand;
  /** Package / script arguments. Required when transport === "stdio". */
  args?: string;
  /** Optional plain (non-secret) env vars. Keys must not look like secrets. */
  envVars?: Record<string, string>;
  // --- sse / http fields ---
  /** Endpoint URL. Required when transport === "sse" or "http". */
  url?: string;
  /** Optional request headers (key → value). */
  headers?: Record<string, string>;
}

/** Validation result returned before hitting the network. */
export type McpValidationResult =
  | { ok: true }
  | { ok: false; field: keyof AddMcpServerInput | "envVars"; message: string }

/** Client-side validation mirroring Python backend constraints. */
export function validateMcpServerInput(input: AddMcpServerInput): McpValidationResult {
  if (!input.name.trim()) {
    return { ok: false, field: "name", message: "Name is required." };
  }
  if (!/^[\w-]+$/.test(input.name)) {
    return {
      ok: false,
      field: "name",
      message: "Use letters, digits, hyphens, and underscores only.",
    };
  }

  if (input.transport === "stdio") {
    if (!input.command || !ALLOWED_MCP_COMMANDS.includes(input.command)) {
      return {
        ok: false,
        field: "command",
        message: `Command must be one of: ${ALLOWED_MCP_COMMANDS.join(", ")}.`,
      };
    }
    if (!input.args?.trim()) {
      return { ok: false, field: "args", message: "Args are required for stdio transport." };
    }
    if (/[;&|><`]|\$[({]|&&|\|\|/.test(input.args)) {
      return {
        ok: false,
        field: "args",
        message: "Args must not contain shell metacharacters (; & | > < ` ${ $(  && ||).",
      };
    }
    // BB-18: secret-looking env keys are NO LONGER rejected here. addMcpServer
    // transparently stores their values via POST /runtime/secrets and references
    // them as secret:<name>, so the raw value never reaches settings.toml. (The
    // old hard rejection made it impossible to register a server that needs an
    // API key from this dialog.)
  } else {
    // sse or http
    if (!input.url?.trim()) {
      return { ok: false, field: "url", message: "URL is required for SSE / HTTP transport." };
    }
    try {
      new URL(input.url.trim());
    } catch {
      return { ok: false, field: "url", message: "Enter a valid URL (e.g. https://example.com/mcp)." };
    }
  }

  return { ok: true };
}

/** Raw response from POST /runtime/mcp/register */
interface GatewayMcpRegisterResponse {
  name: string;
  message?: string;
}

// ============================================================
// BB-18: transparent secret handling for MCP registration
//
// The backend rejects raw secret-looking env/header values (they would land in
// settings.toml) and instead wants the value stored via POST /runtime/secrets
// and referenced as secret:<name>. Rather than make the user do that two-step
// dance, addMcpServer detects secret-looking keys, stores their values first,
// and rewrites the register payload to use secret:<name> refs.
// ============================================================

/** Keys whose values are treated as secrets. Mirrors the gateway's _SECRET_PATTERNS. */
const MCP_SECRET_KEY_PATTERNS = [
  "key", "token", "secret", "password", "passwd", "credential",
  "private", "auth", "bearer", "apikey", "api_key",
];

/** True when an env/header key name looks like it carries a secret value. */
export function looksLikeMcpSecretKey(key: string): boolean {
  const lower = key.toLowerCase();
  return MCP_SECRET_KEY_PATTERNS.some((p) => lower.includes(p));
}

/** Coerce an arbitrary string into the gateway's secret-name charset (^[\w.\-]+$). */
function sanitizeSecretName(raw: string): string {
  return raw.replace(/[^\w.\-]/g, "_");
}

/**
 * Store a single user-managed secret via POST /runtime/secrets (stored under the
 * reserved cred:<name> namespace server-side; the value is never returned).
 */
export async function storeSecret(name: string, value: string): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<{ ok: boolean; name: string }>("POST", "/runtime/secrets", { name, value });
}

/**
 * Split an env/header map into the payload-safe map (secret-looking raw values
 * replaced with secret:<name> refs) and the list of secrets to store first.
 *
 * Values already in `secret:<name>` form pass through untouched (the user is
 * referencing an existing credential). Non-secret keys pass through as-is.
 *
 * Pure + exported for unit testing.
 */
export function extractMcpSecrets(
  serverName: string,
  scope: "env" | "header",
  pairs: Record<string, string>,
): {
  sanitized: Record<string, string>;
  secrets: { name: string; value: string }[];
} {
  const sanitized: Record<string, string> = {};
  const secrets: { name: string; value: string }[] = [];
  for (const [k, v] of Object.entries(pairs)) {
    if (typeof v === "string" && v.startsWith("secret:")) {
      sanitized[k] = v; // already a reference — leave it
    } else if (v && looksLikeMcpSecretKey(k)) {
      const name = sanitizeSecretName(`mcp_${serverName}_${scope}_${k}`);
      secrets.push({ name, value: v });
      sanitized[k] = `secret:${name}`;
    } else {
      sanitized[k] = v;
    }
  }
  return { sanitized, secrets };
}

/**
 * Register a new MCP server via POST /runtime/mcp/register.
 *
 * Payload (CONTRACT-MCP):
 * {
 *   name, transport: "stdio"|"sse"|"http",
 *   command?, args?, env_vars?,   // stdio only
 *   url?, headers?                // sse/http only
 * }
 *
 * On success, reloads the MCP inventory so the new server appears in the list
 * immediately (the backend hot-reloads on register).
 *
 * @throws ApiError on network failure or backend error.
 */
export async function addMcpServer(input: AddMcpServerInput): Promise<void> {
  if (USE_MOCKS) return;

  const payload: Record<string, unknown> = {
    name: input.name,
    transport: input.transport,
  };

  // BB-18: transparently store secret-looking env/header values and reference
  // them as secret:<name> so registration succeeds without the user manually
  // pre-storing the credential (the raw value never lands in settings.toml).
  const pendingSecrets: { name: string; value: string }[] = [];

  if (input.transport === "stdio") {
    payload.command = input.command;
    payload.args = input.args;
    const { sanitized, secrets } = extractMcpSecrets(input.name, "env", input.envVars ?? {});
    pendingSecrets.push(...secrets);
    payload.env_vars = sanitized;
  } else {
    payload.url = input.url;
    if (input.headers && Object.keys(input.headers).length > 0) {
      const { sanitized, secrets } = extractMcpSecrets(input.name, "header", input.headers);
      pendingSecrets.push(...secrets);
      payload.headers = sanitized;
    }
  }

  // Store every detected secret BEFORE registering so the secret:<name> refs in
  // the payload resolve server-side (the backend verifies cred:<name> exists).
  for (const s of pendingSecrets) {
    await storeSecret(s.name, s.value);
  }

  await apiSend<GatewayMcpRegisterResponse>("POST", "/runtime/mcp/register", payload);

  // Reload inventory so the newly registered server appears (backend hot-reloads).
  await loadIntegrations();
}

// ============================================================
// 7. MCP server lifecycle controls — enable / disable / delete
// ============================================================

/** Shared response shape for enable / disable / delete endpoints. */
interface GatewayMcpOkResponse {
  ok: boolean;
}

/**
 * Enable a registered MCP server.
 *
 * Contract: POST /runtime/mcp/{name}/enable → { "ok": true }
 * On success, reloads the MCP inventory.
 *
 * @throws ApiError on network failure or 404 (unknown server).
 */
export async function enableMcpServer(name: string): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayMcpOkResponse>(
    "POST",
    `/runtime/mcp/${encodeURIComponent(name)}/enable`,
  );
  await loadIntegrations();
}

/**
 * Disable a registered MCP server (keeps its registration, just stops routing calls to it).
 *
 * Contract: POST /runtime/mcp/{name}/disable → { "ok": true }
 * On success, reloads the MCP inventory.
 *
 * @throws ApiError on network failure or 404 (unknown server).
 */
export async function disableMcpServer(name: string): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayMcpOkResponse>(
    "POST",
    `/runtime/mcp/${encodeURIComponent(name)}/disable`,
  );
  await loadIntegrations();
}

/**
 * Permanently delete a registered MCP server.
 *
 * Contract: DELETE /runtime/mcp/{name} → { "ok": true }
 * On success, reloads the MCP inventory so the row disappears.
 *
 * @throws ApiError on network failure or 404 (unknown server).
 */
export async function deleteMcpServer(name: string): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayMcpOkResponse>(
    "DELETE",
    `/runtime/mcp/${encodeURIComponent(name)}`,
  );
  await loadIntegrations();
}
