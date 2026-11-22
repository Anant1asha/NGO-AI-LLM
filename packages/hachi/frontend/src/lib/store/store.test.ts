// Regression lock for audit finding L1/gap 2 investigation — the scripted demo
// run queue (store.ts's _runQueue/runTick/finishRun, which produces the
// hardcoded "Summarised 6 PRs — 2 need review. Posted to #eng." result) must
// NEVER fire when dataMode === 'live'. It is confined to mock/demo mode.
//
// This was investigated as part of BB-36 (Work screen live-wiring audit) and
// found to already be correctly gated — every entry point into the scripted
// queue (openRun, runAllowLeash, runAlwaysAllow, runDenyLeash, stopRun) has an
// explicit `dataMode === 'live'` early-return that fully replaces the mock
// behaviour before the scripted queue could ever be seeded. No code change
// was needed; this test pins the invariant so a future edit can't silently
// reintroduce fake data into a real run.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Approval } from "../data/types";

vi.mock("../data/client", () => ({
  USE_MOCKS: false,
  apiGet: vi.fn().mockResolvedValue(undefined),
  apiSend: vi.fn().mockResolvedValue(undefined),
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: "/api",
  authHeaders: () => ({}),
  ApiError: class ApiError extends Error {},
}));

vi.mock("../data/sse", () => ({
  streamSSE: vi.fn(),
}));

vi.mock("../notifications", () => ({
  ensureNotificationPermission: vi.fn(),
  notifyApprovalPending: vi.fn(),
}));

import { useStore } from "./store";

const FAKE_RESULT = "Summarised 6 PRs — 2 need review. Posted to #eng.";

beforeEach(() => {
  useStore.getState().hydrate({
    dataMode: "live",
    runView: { id: 1, title: "Weekly PR summary", status: "working", progress: 0.5, spent: 0, budget: 1 },
    runLines: [{ text: "hachi ▸ run weekly-pr-summary --watch" }],
    runDone: false,
    runStreaming: true,
    runLeash: null,
    runSpent: 0,
    finished: [],
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("live run — scripted demo queue must never fire (BB-36 gap-2 investigation)", () => {
  it("openRun() in live mode does not seed the mock queue or touch runView", () => {
    const before = useStore.getState().runView;
    useStore.getState().openRun(1, "work");
    // Live branch just early-returns (runView untouched, no mock seeding).
    expect(useStore.getState().runView).toBe(before);
    expect(useStore.getState().finished.some((f) => f.result === FAKE_RESULT)).toBe(false);
  });

  it("runDenyLeash() in live mode marks done WITHOUT the hardcoded demo result", () => {
    useStore.getState().runDenyLeash();
    const state = useStore.getState();
    expect(state.runDone).toBe(true);
    // archiveRun() (which produces the fake result) must NOT have run in live mode —
    // the live branch does not push into `finished` at all.
    expect(state.finished.some((f) => f.result === FAKE_RESULT)).toBe(false);
  });

  it("stopRun() in live mode marks done WITHOUT the hardcoded demo result", () => {
    useStore.getState().stopRun();
    const state = useStore.getState();
    expect(state.runDone).toBe(true);
    expect(state.finished.some((f) => f.result === FAKE_RESULT)).toBe(false);
  });

  it("runAllowLeash() in live mode does not start the scripted mock interval", () => {
    useStore.getState().hydrate({ runLeash: { request: "x", action: "y", why: "z" } });
    useStore.getState().runAllowLeash();
    // Live branch clears the leash + resumes streaming without scheduling runTick.
    const state = useStore.getState();
    expect(state.runLeash).toBeNull();
    expect(state.finished.some((f) => f.result === FAKE_RESULT)).toBe(false);
  });
});

// ---- T5 / BB-81: authApplied must be per-target, not a global boolean ----

describe("applyPatch — per-target applied state (BB-81)", () => {
  it("records the applied target name, not a bare boolean", () => {
    useStore.setState({ authSel: "brain.og", authAppliedTarget: null } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().applyPatch();
    expect((useStore.getState() as unknown as Record<string, unknown>).authAppliedTarget).toBe("brain.og");
  });

  it("applied state for a different target reads false", () => {
    useStore.setState({ authSel: "brain.og", authAppliedTarget: null } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().applyPatch();
    const state = useStore.getState() as unknown as Record<string, unknown>;
    // When authSel is settings.toml, the derivation should differ
    expect(state.authAppliedTarget !== "settings.toml").toBe(true);
  });

  it("revertPatch clears authAppliedTarget to null", () => {
    useStore.setState({ authSel: "brain.og", authAppliedTarget: "brain.og" } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().revertPatch();
    expect((useStore.getState() as unknown as Record<string, unknown>).authAppliedTarget).toBeNull();
  });
});

// ---- T1 / BB-77: tickApprovals must not auto-decline live approvals with expiresAt=0 ----

function approvalWith(overrides: Partial<Approval>): Approval {
  return {
    id: 1,
    icon: "mail",
    request: "test request",
    why: "test why",
    action: "test action",
    op: "test-op",
    policy: "asks first",
    touches: [],
    risk: "low",
    scope: "test",
    expiresAt: Date.now() + 60000,
    totalMs: 60000,
    ...overrides,
  };
}

describe("tickApprovals — live sentinel and mock expiry (BB-77)", () => {
  it("live approval with expiresAt=0 survives ticking", () => {
    useStore.setState({
      dataMode: "live",
      approvals: [approvalWith({ expiresAt: 0 })],
      history: [],
    });
    useStore.getState().tickApprovals();
    expect(useStore.getState().approvals).toHaveLength(1);
    expect(useStore.getState().history).toHaveLength(0);
  });

  it("mock past-expiry approval is auto-declined", () => {
    useStore.setState({
      dataMode: "mock",
      approvals: [approvalWith({ expiresAt: Date.now() - 1000 })],
      history: [],
    });
    useStore.getState().tickApprovals();
    expect(useStore.getState().approvals).toHaveLength(0);
    expect(useStore.getState().history[0].decision).toMatch(/timed out/);
  });
});

// ---- T8a / BB-83: toast queue (append/cap/dismiss) ----

describe('toast queue — append / cap / dismiss (BB-83)', () => {
  beforeEach(() => {
    useStore.setState({ toasts: [] });
  });

  it('showToast appends a toast with a unique id', () => {
    useStore.getState().showToast('hello', 'success');
    const { toasts } = useStore.getState();
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe('hello');
    expect(toasts[0].id).toBeTruthy();
  });

  it('a fourth toast drops the oldest (cap=3)', () => {
    useStore.getState().showToast('a', 'success');
    useStore.getState().showToast('b', 'success');
    useStore.getState().showToast('c', 'success');
    useStore.getState().showToast('d', 'success');
    const { toasts } = useStore.getState();
    expect(toasts).toHaveLength(3);
    expect(toasts.map((t) => t.message)).toEqual(['b', 'c', 'd']);
  });

  it('dismissToast removes the targeted toast by id', () => {
    useStore.getState().showToast('x', 'success');
    useStore.getState().showToast('y', 'success');
    const { toasts: before } = useStore.getState();
    useStore.getState().dismissToast(before[0].id);
    const { toasts: after } = useStore.getState();
    expect(after).toHaveLength(1);
    expect(after[0].message).toBe('y');
  });

  it('showToast preserves the action callback', () => {
    const onAction = vi.fn();
    useStore.getState().showToast('Fact forgotten', 'success', { label: 'Undo', onAction });
    const { toasts } = useStore.getState();
    expect(toasts[0].action?.label).toBe('Undo');
    toasts[0].action?.onAction();
    expect(onAction).toHaveBeenCalledOnce();
  });
});
