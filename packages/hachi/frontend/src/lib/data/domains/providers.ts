// ============================================================
// Hachi Web App — multi-provider admin domain
//
// Wires:
//   GET  /config/providers
//   POST /config/providers             (add provider)
//   PUT  /config/providers/{name}      (update named provider)
//   DELETE /config/providers/{name}    (remove named provider)
//   POST /config/providers/{name}/test-connection
//   GET  /config/routing
//   PUT  /config/routing
//   POST /config/routing/validate
//   POST /config/routing/rollback
//   GET  /config/routing/audit
//   GET  /config/models/all
// ============================================================

import { apiGet, apiSend } from "../client";

// ---- Types ----

export interface ProviderEntry {
  name: string;
  kind: string;
  model: string;
  base_url: string | null;
  allowed_models: string[];
  headers: Record<string, string>;
  configured: boolean;
}

export interface ProvidersResponse {
  providers: ProviderEntry[];
}

export interface ProviderSpec {
  kind: string;
  model?: string;
  base_url?: string | null;
  allowed_models?: string[];
  headers?: Record<string, string>;
  api_key?: string;
}

export interface CapabilityRow {
  name: string;
  label: string;
  models: string[];
}

export interface RoutingResponse {
  default_model: string;
  capabilities: CapabilityRow[];
}

export interface ConnectionTestResult {
  ok: boolean;
  detail: string;
}

export interface ProbeResult {
  ok: boolean;
  detail: string;
  models: string[];
}

export type AllModelsResponse = Record<string, string[]>;

// ---- API adapters ----

/**
 * Fetch all configured providers (secrets masked).
 */
export async function getProviders(): Promise<ProvidersResponse> {
  return apiGet<ProvidersResponse>("/config/providers");
}

/**
 * Add a new provider.
 */
export async function addProvider(
  name: string,
  spec: ProviderSpec
): Promise<ProviderEntry> {
  return apiSend<ProviderEntry>("POST", "/config/providers", { name, ...spec });
}

/**
 * Update an existing named provider.
 */
export async function updateProvider(
  name: string,
  spec: ProviderSpec
): Promise<ProviderEntry> {
  return apiSend<ProviderEntry>("PUT", `/config/providers/${encodeURIComponent(name)}`, spec);
}

/**
 * Remove a named provider.
 */
export async function removeProvider(name: string): Promise<{ ok: boolean; name: string }> {
  return apiSend<{ ok: boolean; name: string }>(
    "DELETE",
    `/config/providers/${encodeURIComponent(name)}`
  );
}

/**
 * Test connectivity for a provider.
 */
export async function testConnection(name: string): Promise<ConnectionTestResult> {
  try {
    return await apiSend<ConnectionTestResult>(
      "POST",
      `/config/providers/${encodeURIComponent(name)}/test-connection`
    );
  } catch {
    return { ok: false, detail: "Could not reach gateway" };
  }
}

/**
 * Probe an unsaved provider spec: test connectivity and list available models.
 *
 * The browser can't call providers directly (CORS + keys stay server-side), so
 * the gateway does the round-trip. `name` lets edit-mode reuse a stored key
 * without re-typing it. Never throws — returns a failed-safe result.
 */
export async function probeProvider(
  spec: ProviderSpec & { name?: string }
): Promise<ProbeResult> {
  try {
    return await apiSend<ProbeResult>("POST", "/config/providers/probe", spec);
  } catch (e) {
    return {
      ok: false,
      detail: e instanceof Error ? e.message : "Could not reach gateway",
      models: [],
    };
  }
}

/**
 * Fetch the capability routing matrix.
 */
export async function getRouting(): Promise<RoutingResponse> {
  return apiGet<RoutingResponse>("/config/routing");
}

/**
 * Persist the capability routing matrix.
 */
export async function setRouting(
  defaultModel: string,
  capabilities: Record<string, string[]>
): Promise<RoutingResponse> {
  return apiSend<RoutingResponse>("PUT", "/config/routing", {
    default_model: defaultModel,
    capabilities,
  });
}

export interface RoutingValidationResult {
  ok: boolean;
  issues: string[];
  warnings: string[];
}

export interface RoutingRollbackResult {
  ok: boolean;
  detail: string;
  routing: RoutingResponse | null;
}

/**
 * Validate a routing config without persisting it.
 * Always resolves (HTTP 200); check `ok` in the result.
 */
export async function validateRouting(
  defaultModel: string,
  capabilities: Record<string, string[]>
): Promise<RoutingValidationResult> {
  return apiSend<RoutingValidationResult>("POST", "/config/routing/validate", {
    default_model: defaultModel,
    capabilities,
  });
}

/**
 * Restore the last-known-good routing snapshot.
 */
export async function rollbackRouting(): Promise<RoutingRollbackResult> {
  return apiSend<RoutingRollbackResult>("POST", "/config/routing/rollback", {});
}

/**
 * Fetch recent routing-change audit records (newest first).
 */
export async function getRoutingAudit(
  limit = 50
): Promise<Record<string, unknown>[]> {
  return apiGet<Record<string, unknown>[]>(`/config/routing/audit?limit=${limit}`);
}

/**
 * Fetch model ids available per provider.
 */
export async function listAllModels(): Promise<AllModelsResponse> {
  return apiGet<AllModelsResponse>("/config/models/all");
}
