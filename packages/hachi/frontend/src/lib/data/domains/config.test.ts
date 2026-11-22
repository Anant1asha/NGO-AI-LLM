// Regression tests for BB-15 — the permission/safety tier must NOT revert to
// "standard" when the (slow, external) /models call fails. /config is the source
// of truth for safety and is fetched independently of /models.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Mock the HTTP client so we control /config and /models independently ──────
const apiGetMock = vi.fn();
const apiSendMock = vi.fn();
vi.mock("../client", () => ({
  USE_MOCKS: false,
  apiGet: (path: string, params?: unknown, signal?: unknown) =>
    apiGetMock(path, params, signal),
  apiSend: (...args: unknown[]) => apiSendMock(...args),
  // store.ts calls this at module-load to wire the reconnecting flag.
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: "/api",
  authHeaders: () => ({}),
  ApiError: class ApiError extends Error {},
}));

// loadConfig calls loadDailySpend() — stub it so no real network happens.
vi.mock("./spend", () => ({ loadDailySpend: vi.fn().mockResolvedValue(undefined) }));

import { loadConfig, getAvailableModels, removeFolderLive, removeCommandLive, toggleOpToolLive } from "./config";
import { useStore } from "../../store/store";

const CONFIG_OPEN = {
  permissions: { tier: "unrestricted", ask_before: {} },
  provider: { kind: "anthropic", model: "claude-haiku-4-5" },
};

const MODELS_OK = [
  { id: "claude-haiku-4-5", label: "Haiku", provider: "anthropic", recommended: true },
];

beforeEach(() => {
  apiGetMock.mockReset();
  // Start from a known store state.
  useStore.getState().hydrate({ safety: "standard", configLoaded: false });
});

afterEach(() => {
  vi.clearAllMocks();
});

// NOTE: loadConfig keeps a module-level `_hasEverSucceeded` flag that gates the
// first-load fallback. The "config fails" case must run BEFORE any success case,
// so it is declared first (vitest preserves declaration order within a file).
describe("loadConfig — safety tier resilience (BB-15)", () => {
  it("falls back to standard only when /config itself fails on first load", async () => {
    apiGetMock.mockImplementation(() => Promise.reject(new Error("gateway down")));

    await loadConfig();

    // /config never succeeded → safe default is acceptable here.
    expect(useStore.getState().safety).toBe("standard");
    expect(useStore.getState().configLoaded).toBe(true);
  });

  it("keeps the /config tier when /models REJECTS (no revert to standard)", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/config") return Promise.resolve(CONFIG_OPEN);
      if (path === "/models") return Promise.reject(new Error("provider 503"));
      return Promise.resolve(undefined);
    });

    await loadConfig();

    // The whole point: a failed /models must not wipe the permission tier.
    expect(useStore.getState().safety).toBe("open");
    expect(useStore.getState().configLoaded).toBe(true);
  });

  it("hydrates models when both succeed", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/config") return Promise.resolve(CONFIG_OPEN);
      if (path === "/models") return Promise.resolve(MODELS_OK);
      return Promise.resolve(undefined);
    });

    await loadConfig();

    expect(useStore.getState().safety).toBe("open");
    expect(getAvailableModels()).toHaveLength(1);
  });
});

// ---- T2 / BB-78: permission removals must persist to the gateway (BB-78) ----

describe("removeFolderLive — persist to gateway (BB-78)", () => {
  beforeEach(() => {
    apiSendMock.mockReset();
    useStore.getState().hydrate({ allowedFolders: ["/home/user/projects", "/tmp"] });
  });

  it("removes folder from store on 200", async () => {
    apiSendMock.mockResolvedValue({ ok: true });
    await removeFolderLive("/home/user/projects");
    expect(useStore.getState().allowedFolders).not.toContain("/home/user/projects");
  });

  it("keeps folder in store on failure", async () => {
    apiSendMock.mockRejectedValue(new Error("server error"));
    await removeFolderLive("/home/user/projects");
    expect(useStore.getState().allowedFolders).toContain("/home/user/projects");
  });
});

describe("removeCommandLive — persist to gateway (BB-78)", () => {
  beforeEach(() => {
    apiSendMock.mockReset();
    useStore.getState().hydrate({ allowedCommands: ["npm", "git"] });
  });

  it("removes command from store on 200", async () => {
    apiSendMock.mockResolvedValue({ ok: true });
    await removeCommandLive("npm");
    expect(useStore.getState().allowedCommands).not.toContain("npm");
  });

  it("keeps command in store on failure", async () => {
    apiSendMock.mockRejectedValue(new Error("server error"));
    await removeCommandLive("npm");
    expect(useStore.getState().allowedCommands).toContain("npm");
  });
});

describe("toggleOpToolLive — persist to gateway (BB-78)", () => {
  beforeEach(() => {
    apiSendMock.mockReset();
    useStore.getState().hydrate({
      opTools: [{ id: "shell", label: "Shell", scope: "approved folders", on: true }],
    });
  });

  it("flips op tool in store on 200", async () => {
    apiSendMock.mockResolvedValue({ ok: true });
    await toggleOpToolLive("shell");
    expect(useStore.getState().opTools.find((t) => t.id === "shell")?.on).toBe(false);
  });

  it("keeps op tool unchanged on failure", async () => {
    apiSendMock.mockRejectedValue(new Error("server error"));
    await toggleOpToolLive("shell");
    expect(useStore.getState().opTools.find((t) => t.id === "shell")?.on).toBe(true);
  });
});
