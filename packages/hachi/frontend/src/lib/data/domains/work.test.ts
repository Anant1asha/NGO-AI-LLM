// Regression tests for audit finding L1/gap 1 (BB-36) — the Work screen's
// "Run now" action on a routine must actually call the gateway
// (POST /schedules/{id}/run-now), not just optimistically clear the panel.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Mock the HTTP client so we control the gateway response ───────────────
const apiGetMock = vi.fn();
const apiSendMock = vi.fn();
vi.mock("../client", () => ({
  USE_MOCKS: false,
  apiGet: (path: string, params?: unknown, signal?: unknown) =>
    apiGetMock(path, params, signal),
  apiSend: (method: string, path: string, body?: unknown) =>
    apiSendMock(method, path, body),
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: "/api",
  authHeaders: () => ({}),
  ApiError: class ApiError extends Error {},
}));

import { loadWork, runRoutineNowLive } from "./work";
import { useStore } from "../../store/store";

const SCHEDULE_A = {
  schedule_id: "sched-aaa",
  name: "daily-summary",
  task: "summarize",
  kind: "cron" as const,
  cron: "0 9 * * *",
  timezone: "utc",
  enabled: true,
  created_at: "2026-07-01T00:00:00Z",
  last_run: null,
  next_run: "2026-07-05T09:00:00Z",
};

beforeEach(() => {
  apiGetMock.mockReset();
  apiSendMock.mockReset();
  useStore.getState().hydrate({ routines: [], selectedWork: null });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("runRoutineNowLive — POST /schedules/{id}/run-now (BB-36)", () => {
  it("calls the gateway run-now route for a routine loaded from GET /schedules", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/jobs/active") return Promise.resolve([]);
      if (path === "/jobs/failed") return Promise.resolve([]);
      if (path === "/schedules") return Promise.resolve({ schedules: [SCHEDULE_A] });
      if (path === "/runs") return Promise.resolve({ runs: [] });
      return Promise.resolve(undefined);
    });

    await loadWork();
    const routine = useStore.getState().routines.find((r) => r.title === "daily-summary");
    expect(routine).toBeDefined();

    apiSendMock.mockResolvedValueOnce({ ok: true, schedule_id: "sched-aaa" });

    const dispatched = await runRoutineNowLive(routine!.id);

    expect(dispatched).toBe(true);
    expect(apiSendMock).toHaveBeenCalledWith(
      "POST",
      "/schedules/sched-aaa/run-now",
      undefined
    );
  });

  it("applies the optimistic store update (closes panel) regardless of gateway result", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/schedules") return Promise.resolve({ schedules: [SCHEDULE_A] });
      return Promise.resolve(path === "/runs" ? { runs: [] } : []);
    });
    await loadWork();
    const routine = useStore.getState().routines.find((r) => r.title === "daily-summary")!;

    useStore.getState().hydrate({ selectedWork: { id: routine.id } as never });
    apiSendMock.mockRejectedValueOnce(new Error("gateway down"));

    const dispatched = await runRoutineNowLive(routine.id);

    expect(dispatched).toBe(false);
    // Optimistic action (store.runRoutineNow) always clears selectedWork.
    expect(useStore.getState().selectedWork).toBeNull();
  });

  it("returns false and skips the network call for an id with no known schedule mapping (fixture)", async () => {
    // No loadWork() call — _scheduleIdMap has no entry for an arbitrary id.
    const dispatched = await runRoutineNowLive(999999);
    expect(dispatched).toBe(false);
    expect(apiSendMock).not.toHaveBeenCalled();
  });
});
