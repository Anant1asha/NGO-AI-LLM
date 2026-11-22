// ============================================================
// Hachi Web App — Zustand store
// Single store; persist only operator + theme.
// Actions mirror prototype logic methods (dc.html 1800–2160).
// ============================================================

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { USE_MOCKS, registerReconnectCallback } from "../data/client";
import {
  allowLeashLive,
  denyLeashLive,
  newSessionLive,
  startTaskLive,
  stopStreamingLive,
  switchSessionLive,
} from "../data/domains/chat";
import {
  initApprovals,
  history,
  runs,
  routines,
  finished,
  failed,
  memGroups,
  blocked,
  proposed,
  skills,
  kennel,
  integrations,
  mcpServers,
  mcpTools,
  ogNodes,
  authTargets,
  authSource,
  spendTurns,
  spendTidies,
  spendModels,
  packRoster,
  events,
  toolCalls,
  auditLog,
  recall,
  sessions,
  skillUsage,
  askRules,
  allowedFolders,
  allowedCommands,
  opTools,
  initialSpent,
  initialBudget,
  initialTaskSpent,
} from "../data/fixtures";
import { apiSend } from "../data/client";
import type {
  Approval,
  HistoryItem,
  Run,
  Routine,
  FinishedTask,
  FailedTask,
  MemGroup,
  BlockedItem,
  ProposedChange,
  Skill,
  KennelItem,
  Integration,
  McpServer,
  McpTool,
  OgNode,
  AuthTarget,
  DiffLine,
  SpendTurn,
  SpendTidy,
  SpendModel,
  PackMember,
  ActivityEvent,
  ToolCall,
  AuditEntry,
  RecallHit,
  Session,
  SkillUsage,
  AskRule,
  OpTool,
  Toast,
  ToastItem,
  ChatMessage,
  ActionCard,
  RunPackMember,
  InContextLeash,
  Provider,
  SafetyLevel,
  PendingAttachment,
  AgentInteraction,
} from "../data/types";

// Alias used in consent overlay state
type KennelConsentItem = KennelItem;

// ---- run-queue item type (internal) ----
interface RunQueueItem {
  line?: { text: string; tone?: string };
  steps?: { i: number; state: string }[];
  pack?: { id: string; status: string; task?: string };
  spend?: number;
  leash?: { request: string; action: string; why: string };
}

// ============================================================
// State shape
// ============================================================
interface State {
  // persisted
  operator: boolean;
  theme: "light" | "dark" | "auto";
  // data source: "live" calls the gateway; "mock" keeps seeded fixtures.
  dataMode: "mock" | "live";
  // budget
  spent: number;
  budget: number;
  taskSpent: number;
  // domain arrays
  approvals: Approval[];
  history: HistoryItem[];
  runs: Run[];
  routines: Routine[];
  finished: FinishedTask[];
  failed: FailedTask[];
  memGroups: MemGroup[];
  blocked: BlockedItem[];
  proposed: ProposedChange | null;
  skills: Skill[];
  kennel: KennelItem[];
  integrations: Integration[];
  mcpServers: McpServer[];
  mcpTools: McpTool[];
  ogNodes: OgNode[];
  authTargets: AuthTarget[];
  authSource: DiffLine[];
  authSel: string;
  authMode: "diff" | "source";
  authAppliedTarget: string | null;
  ogSel: string;
  ogView: "graph" | "tree";
  spendTurns: SpendTurn[];
  spendTidies: SpendTidy[];
  spendModels: SpendModel[];
  packRoster: PackMember[];
  events: ActivityEvent[];
  toolCalls: ToolCall[];
  auditLog: AuditEntry[];
  recall: RecallHit[];
  sessions: Session[];
  skillUsage: SkillUsage[];
  safety: SafetyLevel;
  askRules: AskRule[];
  allowedFolders: string[];
  allowedCommands: string[];
  opTools: OpTool[];
  provider: Provider;
  /** True once loadConfig has received a real response (success or error-with-defaults). */
  configLoaded: boolean;
  /** Per-domain settled flags — true once the first load completes (success or error). */
  loaded: { approvals: boolean; work: boolean; review: boolean; memory: boolean; integrations: boolean };
  reconnecting: boolean;
  // toast
  toasts: ToastItem[];
  // palette
  palette: { open: boolean; query: string };
  // setup
  setup: {
    open: boolean;
    step: number;
    key: string;
    safety: SafetyLevel;
    routine: boolean;
    google: boolean;
    channel: boolean;
    /** 'onboard' = full wizard; 'edit-provider' = provider/key step only */
    mode: 'onboard' | 'edit-provider';
    /** True when the backend reports an API key is already configured in the environment */
    keyAlreadySet: boolean;
    /** Onboarding wizard tier; gates which setup steps + integrations appear. Distinct from `safety`. */
    tier: 'lightning' | 'recommended' | 'enhanced' | 'power';
    /** True once the wizard has been completed end-to-end; openSetup resets to step 0 when true. */
    completed: boolean;
  };
  // kennel consent overlay
  kennelConsent: KennelConsentItem | null;
  // kennel browse mode (true = list mode, no specific item selected)
  kennelBrowseOpen: boolean;
  // spend caps (editable)
  taskCap: number;
  dailyCap: number;
  // chat
  slashOpen: boolean;
  streaming: boolean;
  inContext: InContextLeash | null;
  messages: ChatMessage[];
  composer: string;
  pendingAttachments: PendingAttachment[];
  // home
  homeInput: string;
  selectedWork: unknown | null;
  workFilter: string;
  // live run
  runView: Run | null;
  runLines: { text: string; tone?: string }[];
  runStreaming: boolean;
  runDone: boolean;
  runLeash: { request: string; action: string; why: string } | null;
  runSpent: number;
  runPack: RunPackMember[];
  runSteps: { label: string; state: string }[];
  // memory
  editingFactId: string | null;
  editingText: string;
  // FIX 4: last model id seen in a usage/turn-complete SSE event
  lastUsedModel: string | null;
  // eval loop
  interactions: AgentInteraction[];
}

// ============================================================
// Actions shape
// ============================================================
interface Actions {
  // live-data hydration (foundation)
  // Shallow-merge a slice of gateway-derived state into the store. Domain
  // loaders call this after mapping a gateway response to UI types.
  hydrate: (patch: Partial<State>) => void;
  setLoaded: (domain: keyof State['loaded']) => void;
  setReconnecting: (v: boolean) => void;
  // operator / theme
  setOperator: (v: boolean) => void;
  setTheme: (t: "light" | "dark" | "auto") => void;
  toggleTheme: () => void;
  toggleOperator: () => void;
  // toast
  showToast: (message: string, tone?: Toast["tone"], action?: Toast["action"]) => void;
  dismissToast: (id: string) => void;
  // palette
  openPalette: () => void;
  closePalette: () => void;
  setPaletteQuery: (q: string) => void;
  // setup
  openSetup: () => void;
  openSetupEditProvider: () => void;
  closeSetup: () => void;
  setSetupStep: (n: number) => void;
  setSetupField: (k: string, v: unknown) => void;
  setupBack: () => void;
  setupNext: () => void;
  toggleSetupRoutine: () => void;
  toggleSetupGoogle: () => void;
  toggleSetupChannel: () => void;
  setSetupKey: (v: string) => void;
  // approvals
  allowApproval: (id: number, scope?: string) => void;
  alwaysApproval: (id: number) => void;
  declineApproval: (id: number, reason?: string) => void;
  declineAll: () => void;
  // auto-tick (called by interval)
  tickApprovals: () => void;
  // routines / work
  pauseRoutine: (id: number) => void;
  runRoutineNow: (id?: number) => void;
  cancelRun: (id: number) => void;
  retryFailed: (id: number) => void;
  duplicateRoutine: (id: number) => void;
  openWork: (item: unknown) => void;
  closeWork: () => void;
  setWorkFilter: (f: string) => void;
  // memory
  addFact: (groupId?: string, text?: string) => void;
  editFact: (id: string, text: string) => void;
  deleteFact: (id: string) => void;
  startEditFact: (id: string) => void;
  cancelEdit: () => void;
  saveFact: (groupId: string, factId: string) => void;
  delFact: (groupId: string, factId: string) => void;
  setEditText: (v: string) => void;
  approveProposed: () => void;
  rejectProposed: () => void;
  // skills / kennel
  addSkill: (kennelId: string) => void;
  confirmKennel: () => void;
  cancelKennel: () => void;
  removeSkill: (id: string) => void;
  askKennel: (item: KennelConsentItem) => void;
  // OG
  setOgSel: (id: string) => void;
  setOgView: (v: "graph" | "tree") => void;
  setOgHover: (id: string | null) => void;
  // authoring
  selectAuthTarget: (name: string) => void;
  setAuthMode: (m: "diff" | "source") => void;
  applyPatch: (reindexed_ms?: number) => void;
  revertPatch: () => void;
  rejectPatch: () => void;
  // integrations
  connectIntegration: (id: string) => void;
  disconnectIntegration: (id: string) => void;
  // settings
  setSafety: (level: SafetyLevel) => void;
  toggleAskRule: (id: string) => void;
  removeFolder: (f: string) => void;
  removeCommand: (c: string) => void;
  addFolder: () => void;
  addCommand: () => void;
  toggleOpTool: (id: string) => void;
  setProvider: (p: Partial<Provider>) => void;
  // chat / streaming
  startTask: (text: string) => void;
  /** Retry the last failed turn IN PLACE — re-sends the last prompt and reuses the
   *  failed assistant bubble instead of appending a duplicate "you" message. */
  retryLastMessage: () => void;
  sendMessage: (text: string) => void;
  stopStreaming: () => void;
  setComposer: (v: string) => void;
  addPendingAttachment: (a: PendingAttachment) => void;
  updatePendingAttachment: (localId: string, patch: Partial<PendingAttachment>) => void;
  removePendingAttachment: (fileId: string) => void;
  clearPendingAttachments: () => void;
  setHomeInput: (v: string) => void;
  icAllow: () => void;
  icAlwaysAllow: () => void;
  icDeny: () => void;
  toggleCard: (mid: number, key: string) => void;
  dryRunRoutine: (msgId: number) => void;
  createRoutine: (msgId: number) => void;
  // live run
  openRun: (runId?: number, from?: string) => void;
  watchLive: (runId: number) => void;
  closeRun: () => void;
  runAllowLeash: () => void;
  runAlwaysAllow: () => void;
  runDenyLeash: () => void;
  stopRun: () => void;
  // kennel browse
  openKennelBrowse: () => void;
  // settings helpers
  addFolderWithPath: (path: string) => void;
  addCommandWithText: (cmd: string) => void;
  setTaskCap: (v: number) => void;
  setDailyCap: (v: number) => void;
  // session switching (M8 MED-020)
  switchSession: (sessionId: string) => void;
  newSession: () => void;
  // reconnect
  simulateReconnect: () => void;
}

// ============================================================
// Internal id counter (module-level, not in state)
// ============================================================
let _id = 100;
function nextId() { return ++_id; }

// ============================================================
// Streaming helpers (module-level timers)
// ============================================================
let _iv: ReturnType<typeof setInterval> | null = null;
let _rc: ReturnType<typeof setTimeout> | null = null;
let _runIv: ReturnType<typeof setInterval> | null = null;
let _runQueue: RunQueueItem[] = [];
let _runFrom = "home";
let _runStart = 0;

const CHAT_MESSAGES_MAX = 400;

function capMessages(messages: ChatMessage[]): ChatMessage[] {
  if (messages.length <= CHAT_MESSAGES_MAX) return messages;
  return messages.slice(-CHAT_MESSAGES_MAX);
}

function clearIv() { if (_iv) { clearInterval(_iv); _iv = null; } }
function clearRunIv() { if (_runIv) { clearInterval(_runIv); _runIv = null; } }

// ============================================================
// Store
// ============================================================
const domainDefaults = (): Omit<State, "operator" | "theme"> => ({
  dataMode: USE_MOCKS ? "mock" : "live",
  spent: USE_MOCKS ? initialSpent : 0,
  budget: USE_MOCKS ? initialBudget : 5.0,
  taskSpent: USE_MOCKS ? initialTaskSpent : 0,
  approvals: USE_MOCKS ? initApprovals() : [],
  history: USE_MOCKS ? history : [],
  runs: USE_MOCKS ? runs : [],
  routines: USE_MOCKS ? routines : [],
  finished: USE_MOCKS ? finished : [],
  failed: USE_MOCKS ? failed : [],
  memGroups: USE_MOCKS ? memGroups : [],
  blocked: USE_MOCKS ? blocked : [],
  proposed: USE_MOCKS ? proposed : null,
  skills: USE_MOCKS ? skills : [],
  kennel: USE_MOCKS ? kennel : [],
  integrations: USE_MOCKS ? integrations : [],
  mcpServers: USE_MOCKS ? mcpServers : [],
  mcpTools: USE_MOCKS ? mcpTools : [],
  ogNodes: USE_MOCKS ? ogNodes : [],
  authTargets: USE_MOCKS ? authTargets : [],
  authSource: USE_MOCKS ? authSource : [],
  authSel: "deep_research.og",
  authMode: "diff",
  authAppliedTarget: null,
  ogSel: "brain",
  ogView: "graph",
  spendTurns: USE_MOCKS ? spendTurns : [],
  spendTidies: USE_MOCKS ? spendTidies : [],
  spendModels: USE_MOCKS ? spendModels : [],
  packRoster: USE_MOCKS ? packRoster : [],
  events: USE_MOCKS ? events : [],
  toolCalls: USE_MOCKS ? toolCalls : [],
  auditLog: USE_MOCKS ? auditLog : [],
  recall: USE_MOCKS ? recall : [],
  sessions: USE_MOCKS ? sessions : [],
  skillUsage: USE_MOCKS ? skillUsage : [],
  safety: "standard",
  askRules: USE_MOCKS ? askRules : [],
  allowedFolders: USE_MOCKS ? allowedFolders : [],
  allowedCommands: USE_MOCKS ? allowedCommands : [],
  opTools: USE_MOCKS ? opTools : [],
  provider: { name: "anthropic", model: "claude-sonnet-4-5", key: "" },
  configLoaded: false,
  loaded: { approvals: false, work: false, review: false, memory: false, integrations: false },
  reconnecting: false,
  toasts: [],
  palette: { open: false, query: "" },
  setup: { open: false, step: 0, key: "", safety: "standard", routine: true, google: false, channel: false, mode: 'onboard' as const, keyAlreadySet: false, tier: 'lightning', completed: false },
  kennelConsent: null,
  kennelBrowseOpen: false,
  taskCap: 1.0,
  dailyCap: USE_MOCKS ? initialBudget : 5.0,
  slashOpen: false,
  streaming: false,
  inContext: null,
  messages: [],
  composer: "",
  pendingAttachments: [],
  homeInput: "",
  selectedWork: null,
  workFilter: "active",
  runView: null,
  runLines: [],
  runStreaming: false,
  runDone: false,
  runLeash: null,
  runSpent: 0,
  runPack: [],
  runSteps: [],
  editingFactId: null,
  editingText: "",
  lastUsedModel: null,
  interactions: [],
});

export const useStore = create<State & Actions>()(
  persist(
    (set, get) => {
      // ---- helpers ----
      // Auto-dismiss timing lives in ToastHost (not here) so it can pause while
      // the toast is hovered and use a longer duration for error/"blocked" tones.
      const toast = (message: string, tone?: Toast["tone"], action?: Toast["action"]) => {
        const id = String(nextId());
        set((s) => {
          const next = [...s.toasts, { id, message, tone, action }];
          return { toasts: next.length > 3 ? next.slice(-3) : next };
        });
      };;

      const getText = (id: number): string => {
        const m = get().messages.find((x) => x.id === id);
        return m ? m.text : "";
      };

      const setText = (id: number, t: string) => {
        set((s) => ({
          messages: capMessages(s.messages.map((m) => (m.id === id ? { ...m, text: t } : m))),
        }));
      };

      const stream = (id: number, str: string, done?: () => void) => {
        const base = getText(id);
        let i = 0;
        clearIv();
        _iv = setInterval(() => {
          i += 2;
          setText(id, base + str.slice(0, i));
          if (i >= str.length) {
            clearIv();
            if (done) setTimeout(done, 380);
          }
        }, 16);
      };

      const addCard = (id: number, card: ActionCard) => {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === id ? { ...m, cards: [...m.cards, card] } : m
          ),
        }));
      };

      const setCard = (id: number, key: string, patch: Partial<ActionCard>) => {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === id
              ? { ...m, cards: m.cards.map((c) => (c.key === key ? { ...c, ...patch } : c)) }
              : m
          ),
        }));
      };

      const setRoutine = (id: number, patch: Record<string, unknown>) => {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === id
              ? { ...m, routine: { ...(m.routine || {}), ...patch } }
              : m
          ),
        }));
      };

      const resolveApproval = (
        id: number,
        decision: string,
        color: string
      ) => {
        const a = get().approvals.find((x) => x.id === id);
        const historyEntry: HistoryItem | undefined = a
          ? {
              id,
              icon:
                color === "var(--hachi-danger)" ? "x" : "circle-check",
              request: a.request,
              decision,
              when: "just now",
              ts: Date.now(),
              color,
            }
          : undefined;
        const auditEntry: AuditEntry = {
          ts: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          op: a?.op ?? "unknown",
          target: a?.action ?? "",
          policy: a?.policy ?? "",
          decision:
            decision === "allowed once"
              ? "allowed once"
              : decision === "always allowed"
              ? "allowed"
              : "declined",
        };
        set((s) => ({
          approvals: s.approvals.filter((x) => x.id !== id),
          history: historyEntry
            ? [historyEntry, ...s.history]
            : s.history,
          auditLog: [auditEntry, ...s.auditLog],
        }));
      };

      // ---- run helpers ----
      const applyRunSteps = (arr: { i: number; state: string }[]) => {
        set((s) => ({
          runSteps: s.runSteps.map((st, i) => {
            const u = arr.find((a) => a.i === i);
            return u ? { ...st, state: u.state } : st;
          }),
        }));
      };

      const archiveRun = (): Partial<State> => {
        const s = get();
        const rv = s.runView;
        if (!rv) return {};
        const finItem: FinishedTask = {
          id: rv.id,
          title: rv.title,
          note: "Hachi is resting",
          when: "just now",
          cost: s.runSpent,
          result: "Summarised 6 PRs — 2 need review. Posted to #eng.",
          steps: s.runSteps.map((st) => ({
            label: st.label,
            state: (st.state === "working" ? "done" : st.state) as "done" | "working" | "pending" | "failed",
          })),
        };
        return {
          runs: s.runs.filter((r) => r.id !== rv.id),
          finished: [finItem, ...s.finished],
          spent:
            Math.round(
              (s.spent + Math.max(0, s.runSpent - (rv.spent || 0))) * 100
            ) / 100,
        };
      };

      const finishRun = () => {
        clearRunIv();
        const s = get();
        if (s.runDone || !s.runView) return;
        const elapsed = _runStart
          ? Math.ceil((Date.now() - _runStart) / 1000)
          : 0;
        const elStr = elapsed ? " · " + (elapsed < 60 ? elapsed + "s" : Math.floor(elapsed / 60) + "m " + (elapsed % 60) + "s") : "";
        set({
          ...archiveRun(),
          runStreaming: false,
          runDone: true,
          runLines: [
            ...s.runLines,
            { text: "done — Hachi is resting" + elStr, tone: "success" },
          ],
          runSteps: s.runSteps.map((st) => ({ ...st, state: "done" })),
          runPack: s.runPack.map((p) => ({ ...p, status: "done" as const })),
        });
        toast("Task complete — Hachi is resting", "success");
      };

      const runTick = () => {
        const s = get();
        if (s.runDone || !s.runView) { clearRunIv(); return; }
        if (!_runQueue || _runQueue.length === 0) { finishRun(); return; }
        const item = _runQueue.shift()!;
        if (item.steps) applyRunSteps(item.steps);
        if (item.leash) {
          clearRunIv();
          set({ runLeash: item.leash, runStreaming: false });
          return;
        }
        set((prev) => {
          let pack = prev.runPack;
          if (item.pack) {
            pack = pack.map((p) =>
              p.id === item.pack!.id ? { ...p, ...item.pack } : p
            ) as RunPackMember[];
          }
          return {
            runLines: item.line ? [...prev.runLines, item.line] : prev.runLines,
            runPack: pack,
            runSpent: item.spend
              ? Math.round((prev.runSpent + item.spend) * 100) / 100
              : prev.runSpent,
          };
        });
      };

      const slug = (t: string) =>
        String(t || "task")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "")
          .slice(0, 28) || "task";

      // ---- actions ----
      return {
        // seed domain state
        ...domainDefaults(),
        // persisted defaults (will be overridden by storage)
        operator: false,
        theme: "auto",

        // live-data hydration (foundation)
        hydrate: (patch) => {
          if (Array.isArray(patch.messages)) {
            set({
              ...(patch as Partial<State & Actions>),
              messages: capMessages(patch.messages),
            });
            return;
          }
          set(patch as Partial<State & Actions>);
        },
        setLoaded: (domain) => set((s) => ({ loaded: { ...s.loaded, [domain]: true } })),
        setReconnecting: (v) => set({ reconnecting: v }),

        // operator / theme
        setOperator: (v) => set({ operator: v }),
        setTheme: (t) => {
          if (t === 'auto') {
            document.documentElement.removeAttribute('data-theme');
          } else {
            document.documentElement.setAttribute('data-theme', t);
          }
          set({ theme: t });
        },
        toggleTheme: () => {
          const current = get().theme;
          const systemDark = typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
          const effectiveDark = current === 'dark' || (current === 'auto' && systemDark);
          const t = effectiveDark ? 'light' : 'dark';
          document.documentElement.setAttribute('data-theme', t);
          set({ theme: t });
        },
        toggleOperator: () => set((s) => ({ operator: !s.operator })),

        // toast
        showToast: (message, tone, action) => toast(message, tone, action),
        dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

        // palette
        openPalette: () => set({ palette: { open: true, query: "" } }),
        closePalette: () => set((s) => ({ palette: { ...s.palette, open: false } })),
        setPaletteQuery: (q) => set((s) => ({ palette: { ...s.palette, query: q } })),

        // setup
        openSetup: () =>
          set((s) => ({
            setup: {
              ...s.setup,
              open: true,
              // Preserve partial progress so the user resumes where they left off.
              // Reset to step 0 only when starting fresh or after completing the wizard.
              step: s.setup.step > 0 && !s.setup.completed ? s.setup.step : 0,
              mode: 'onboard' as const,
            },
          })),
        openSetupEditProvider: () =>
          set((s) => ({ setup: { ...s.setup, open: true, step: 1, mode: 'edit-provider' as const } })),
        closeSetup: () =>
          set((s) => ({ setup: { ...s.setup, open: false } })),
        setSetupStep: (n) =>
          set((s) => ({ setup: { ...s.setup, step: n } })),
        setSetupField: (k, v) =>
          set((s) => ({ setup: { ...s.setup, [k]: v } })),
        setSetupKey: (v) =>
          set((s) => ({ setup: { ...s.setup, key: v } })),
        toggleSetupRoutine: () =>
          set((s) => ({ setup: { ...s.setup, routine: !s.setup.routine } })),
        toggleSetupGoogle: () =>
          set((s) => ({ setup: { ...s.setup, google: !s.setup.google } })),
        toggleSetupChannel: () =>
          set((s) => ({ setup: { ...s.setup, channel: !s.setup.channel } })),
        setupBack: () =>
          set((s) => ({
            setup: { ...s.setup, step: Math.max(0, s.setup.step - 1) },
          })),
        setupNext: () => {
          const su = get().setup;
          // edit-provider mode: step 1 is the only step; Save closes the wizard.
          if (su.mode === 'edit-provider') {
            set((s) => ({ setup: { ...s.setup, open: false } }));
            toast("Provider updated — Hachi will use it on next restart", "success");
            return;
          }
          const step = su.step;
          if (step >= 4) {
            set((s) => {
              const hasBriefing = s.routines.some((r) => r.title === "Morning briefing");
              const newRoutines =
                su.routine && !hasBriefing
                  ? [
                      {
                        id: nextId(),
                        title: "Morning briefing",
                        schedule: "weekdays 8:00",
                        next: "tomorrow 8:00",
                        cost: 0.04,
                        paused: false,
                      },
                      ...s.routines,
                    ]
                  : s.routines;
              return {
                setup: { ...s.setup, open: false, completed: true },
                safety: su.safety,
                routines: newRoutines,
              };
            });
            toast("All set — Hachi is on watch", "success");
          } else {
            set((s) => ({ setup: { ...s.setup, step: s.setup.step + 1 } }));
          }
        },

        // approvals
        allowApproval: (id) => {
          resolveApproval(id, "allowed once", "var(--hachi-success)");
          toast("On it — Hachi is working", "working");
        },
        alwaysApproval: (id) => {
          resolveApproval(id, "always allowed", "var(--hachi-success)");
          toast("Saved — Hachi won't ask again for this", "success");
        },
        declineApproval: (id) => {
          resolveApproval(id, "declined", "var(--hachi-danger)");
          toast("Stayed put — Hachi is resting", "success");
        },
        declineAll: () => {
          const ids = get().approvals.map((a) => a.id);
          ids.forEach((id) =>
            resolveApproval(id, "declined", "var(--hachi-danger)")
          );
          toast("Stayed put — Hachi is resting", "success");
        },
        tickApprovals: () => {
          // Live approvals have no server-sent expiry (expiresAt=0). Only mock
          // data uses countdowns, so skip the expiry pass entirely in live mode.
          if (get().dataMode === "live") return;
          const now = Date.now();
          // expiresAt=0 is the sentinel for "no expiry" — never treat it as expired.
          const expired = get().approvals.filter(
            (a) => a.expiresAt > 0 && a.expiresAt <= now
          );
          if (expired.length) {
            set((s) => ({
              approvals: s.approvals.filter(
                (a) => a.expiresAt <= 0 || a.expiresAt > now
              ),
              history: [
                ...expired.map((a) => ({
                  id: a.id,
                  icon: "clock",
                  request: a.request,
                  decision: "timed out — Hachi stayed put",
                  when: "just now",
                  ts: Date.now(),
                  color: "var(--hachi-muted)",
                })),
                ...s.history,
              ],
            }));
          }
        },

        // routines / work
        pauseRoutine: (id) =>
          set((s) => ({
            routines: s.routines.map((r) =>
              r.id === id ? { ...r, paused: !r.paused } : r
            ),
          })),
        runRoutineNow: () => {
          set({ selectedWork: null });
          toast("Running now — Hachi is working", "working");
        },
        cancelRun: (id) =>
          set((s) => ({ runs: s.runs.filter((r) => r.id !== id) })),
        retryFailed: (id) => {
          const f = get().failed.find((x) => x.id === id);
          set((s) => ({
            failed: s.failed.filter((x) => x.id !== id),
            runs: f
              ? [
                  {
                    id: nextId(),
                    title: f.title,
                    status: "working" as const,
                    progress: 0.12,
                    spent: 0.0,
                    budget: 1.0,
                    meta: "Retrying",
                    owner: f.owner,
                    when: "retrying now",
                    steps: (f.steps || []).map((stp) => ({
                      label: stp.label,
                      state: "done" as const,
                    })),
                  },
                  ...s.runs,
                ]
              : s.runs,
            selectedWork: null,
            workFilter: "active",
          }));
          toast("Retrying — Hachi is working", "working");
        },
        duplicateRoutine: (id) => {
          const r = get().routines.find((x) => x.id === id);
          if (!r) return;
          set((s) => ({
            routines: [
              { ...r, id: nextId(), title: r.title + " (copy)" },
              ...s.routines,
            ],
          }));
        },
        openWork: (item) => set({ selectedWork: item }),
        closeWork: () => set({ selectedWork: null }),
        setWorkFilter: (f) => set({ workFilter: f }),

        // memory
        addFact: (groupId = "you") => {
          const fid = "fn" + nextId();
          set((s) => ({
            memGroups: s.memGroups.map((g) =>
              g.id === groupId
                ? {
                    ...g,
                    facts: [
                      { id: fid, text: "", source: "added by you" },
                      ...g.facts,
                    ],
                  }
                : g
            ),
            editingFactId: fid,
            editingText: "",
          }));
        },
        editFact: (id, text) =>
          set((s) => ({
            memGroups: s.memGroups.map((g) => ({
              ...g,
              facts: g.facts.map((f) =>
                f.id === id ? { ...f, text } : f
              ),
            })),
          })),
        deleteFact: (id) =>
          set((s) => ({
            memGroups: s.memGroups.map((g) => ({
              ...g,
              facts: g.facts.filter((f) => f.id !== id),
            })),
          })),
        startEditFact: (id) => {
          const all = get().memGroups.flatMap((g) => g.facts);
          const f = all.find((x) => x.id === id);
          set({ editingFactId: id, editingText: f?.text ?? "" });
        },
        cancelEdit: () => set({ editingFactId: null, editingText: "" }),
        setEditText: (v) => set({ editingText: v }),
        saveFact: (groupId, factId) => {
          const t = get().editingText.trim();
          set((s) => ({
            editingFactId: null,
            editingText: "",
            memGroups: s.memGroups.map((g) =>
              g.id === groupId
                ? {
                    ...g,
                    facts: g.facts.map((f) =>
                      f.id === factId ? { ...f, text: t || f.text } : f
                    ),
                  }
                : g
            ),
          }));
          toast("Saved — Hachi remembers it", "success");
        },
        delFact: (groupId, factId) => {
          set((s) => ({
            memGroups: s.memGroups.map((g) =>
              g.id === groupId
                ? { ...g, facts: g.facts.filter((f) => f.id !== factId) }
                : g
            ),
          }));
          toast("Forgotten — Hachi removed that fact", "success");
        },
        approveProposed: () => {
          set({ proposed: null });
          toast("Updated — Hachi remembers the new version", "success");
        },
        rejectProposed: () => {
          set({ proposed: null });
          toast("Kept as-is — Hachi won't change it", "success");
        },

        // skills / kennel
        addSkill: (kennelId) => {
          const k = get().kennel.find((x) => x.id === kennelId);
          if (k) set({ kennelConsent: k });
        },
        askKennel: (item) => set({ kennelConsent: item, kennelBrowseOpen: false }),
        confirmKennel: () => {
          const k = get().kennelConsent;
          if (!k) return;

          if (!USE_MOCKS) {
            // Live mode: delegate to the domain function which POSTs /skills/add,
            // refreshes from gateway, and shows the success/error toast.
            void import("../data/domains/skills").then(({ addSkillLive }) => {
              void addSkillLive(k.id);
            });
            return;
          }

          // Mock mode: local-only add
          set((s) => ({
            kennelConsent: null,
            skills: [
              ...s.skills,
              {
                id: "kn" + nextId(),
                icon: k.icon,
                name: k.name,
                desc: k.desc,
                uses: "0 times",
                lastUsed: "just added",
                stale: false,
              },
            ],
          }));
          toast("Added " + k.name + " — it's ready to use", "success");
        },
        cancelKennel: () => set({ kennelConsent: null, kennelBrowseOpen: false }),
        openKennelBrowse: () => set({ kennelBrowseOpen: true, kennelConsent: null }),
        removeSkill: (id) => {
          set((s) => ({ skills: s.skills.filter((k) => k.id !== id) }));
          toast("Removed — one fewer thing on Hachi's plate", "success");
        },

        // OG explorer
        setOgSel: (id) => set({ ogSel: id }),
        setOgView: (v) => set({ ogView: v }),
        setOgHover: (_id) => {
          // local-only hover not stored in global state per contract guidance
          // screens should use local useState for hover; this is a no-op shim
        },

        // authoring
        selectAuthTarget: (name) => set({ authSel: name }),
        setAuthMode: (m) => set({ authMode: m }),
        applyPatch: (reindexed_ms?: number) => {
          const sel = get().authSel;
          set((s) => ({
            authAppliedTarget: sel,
            authTargets: s.authTargets.map((t) =>
              t.name === sel ? { ...t, dirty: false } : t
            ),
          }));
          const reindexStr =
            reindexed_ms !== undefined
              ? `re-indexed in ${(reindexed_ms / 1000).toFixed(1)}s`
              : "re-indexed";
          toast(`Patch applied — ${reindexStr}`, "success");
        },
        revertPatch: () => {
          const sel = get().authSel;
          set((s) => ({
            authAppliedTarget: null,
            authTargets: s.authTargets.map((t) =>
              t.name === sel ? { ...t, dirty: true } : t
            ),
          }));
        },
        rejectPatch: () => {
          toast("Rejected — nothing was written", "success");
        },

        // integrations
        connectIntegration: (id) => {
          set((s) => ({
            integrations: s.integrations.map((i) => {
              if (i.id !== id) return i;
              if (i.status === "connected") return i;
              if (i.status === "degraded")
                return {
                  ...i,
                  status: "connected" as const,
                  risky: false,
                  can: i.can.replace(" — broad access", ""),
                };
              return {
                ...i,
                status: "connected" as const,
                can:
                  i.name === "Notion" ? "read & update pages" : i.can,
              };
            }),
          }));
          toast("Connected — Hachi can reach it now", "success");
        },
        disconnectIntegration: (id) => {
          set((s) => ({
            integrations: s.integrations.map((i) =>
              i.id === id
                ? { ...i, status: "none" as const, can: "not connected", risky: false }
                : i
            ),
          }));
          toast("Disconnected", "success");
        },

        // settings
        setSafety: (level) => set({ safety: level }),
        toggleAskRule: (id) =>
          set((s) => ({
            askRules: s.askRules.map((r) =>
              r.id === id ? { ...r, on: !r.on } : r
            ),
          })),
        removeFolder: (f) =>
          set((s) => ({
            allowedFolders: s.allowedFolders.filter((x) => x !== f),
          })),
        removeCommand: (c) =>
          set((s) => ({
            allowedCommands: s.allowedCommands.filter((x) => x !== c),
          })),
        addFolder: () => {
          // Legacy no-arg path: kept for back-compat with tests / other callers.
          // Settings UI now uses addFolderWithPath instead.
          set((s) => ({ allowedFolders: [...s.allowedFolders, "~/new-folder"] }));
          toast("Added — edit the path in your config", "success");
        },
        addFolderWithPath: (path) => {
          const trimmed = path.trim();
          if (!trimmed) {
            toast("Enter a folder path first", "blocked");
            return;
          }
          set((s) => ({ allowedFolders: [...s.allowedFolders, trimmed] }));
          toast("Folder added", "success");
        },
        addCommand: () => {
          // Legacy no-arg path: kept for back-compat with tests / other callers.
          set((s) => ({ allowedCommands: [...s.allowedCommands, "cmd"] }));
        },
        addCommandWithText: (cmd) => {
          const trimmed = cmd.trim();
          if (!trimmed) {
            toast("Enter a command first", "blocked");
            return;
          }
          set((s) => ({ allowedCommands: [...s.allowedCommands, trimmed] }));
          toast("Command added", "success");
        },
        setTaskCap: (v) => set({ taskCap: v }),
        setDailyCap: (v) => {
          set({ dailyCap: v, budget: v });
        },
        toggleOpTool: (id) =>
          set((s) => ({
            opTools: s.opTools.map((t) =>
              t.id === id ? { ...t, on: !t.on } : t
            ),
          })),
        setProvider: (p) =>
          set((s) => ({ provider: { ...s.provider, ...p } })),

        // chat
        setComposer: (v) =>
          set({ composer: v, slashOpen: v.trim().startsWith("/") }),
        setHomeInput: (v) => set({ homeInput: v }),
        addPendingAttachment: (a) =>
          set((s) => ({ pendingAttachments: [...s.pendingAttachments, a] })),
        updatePendingAttachment: (localId, patch) =>
          set((s) => ({
            pendingAttachments: s.pendingAttachments.map((a) =>
              a.fileId === localId ? { ...a, ...patch } : a
            ),
          })),
        removePendingAttachment: (fileId) =>
          set((s) => ({
            pendingAttachments: s.pendingAttachments.filter((a) => a.fileId !== fileId),
          })),
        clearPendingAttachments: () => set({ pendingAttachments: [] }),

        startTask: (text) => {
          const trimmed = text.trim();
          const pending = get().pendingAttachments;
          if (!trimmed && pending.length === 0) return;
          if (get().streaming) return;
          const youId = nextId();
          const hachiId = nextId();
          const attachmentSnapshot = [...pending];
          // Only include attachments that finished uploading successfully.
          const attachmentIds = attachmentSnapshot
            .filter((a) => !a.uploading && !a.error)
            .map((a) => a.fileId);

          // Shared state update: always append messages and set streaming=true
          // regardless of mode.  The live/mock divergence happens AFTER this.
          set((s) => ({
            composer: "",
            slashOpen: false,
            streaming: true,
            inContext: null,
            homeInput: "",
            pendingAttachments: [],
            messages: capMessages([
              ...s.messages,
              {
                id: youId,
                role: "you" as const,
                text: trimmed,
                cards: [],
                routine: null,
                ts: Date.now(),
                attachments: attachmentSnapshot.map((a) => ({
                  name: a.name,
                  mediaType: a.mediaType,
                  size: a.size,
                })),
              },
              {
                id: hachiId,
                role: "hachi" as const,
                text: "",
                cards: [],
                routine: null,
                ts: Date.now(),
              },
            ]),
          }));

          // Live mode: delegate to chat.ts via dynamic import to avoid a
          // static circular dependency (store → chat → store).
          if (get().dataMode === "live") {
            startTaskLive(trimmed, hachiId, attachmentIds).catch(() => {
              // Catch errors from the live send path: reset streaming and surface an error.
              set((s) => ({
                streaming: false,
                messages: s.messages.map((m) =>
                  m.id === hachiId
                    ? { ...m, text: m.text || "Something went wrong — please try again.", error: true }
                    : m
                ),
              }));
              toast("Send failed — please try again", "blocked");
            });
            return;
          }

          // ── Mock mode: keep existing simulated implementation ──────────────
          const isRoutine =
            /\b(every|each|daily|weekday|weekly|at \d|schedule|routine)\b/i.test(
              trimmed
            );
          if (isRoutine) {
            // routine script
            stream(
              hachiId,
              "Here's what I'd set up. Take a look before it goes on watch — nothing runs until you say so.",
              () => {
                setRoutine(hachiId, {
                  title: "Morning inbox triage",
                  trigger: "Every weekday at 8:00",
                  steps: [
                    "Read your inbox",
                    "Pick out anything urgent",
                    "Message you the urgent ones",
                  ],
                  needs: ["read your inbox", "message you"],
                  costPerRun: 0.04,
                  dryRunDone: false,
                  created: false,
                });
                set({ streaming: false });
              }
            );
          } else {
            // standard script
            stream(
              hachiId,
              "On it. Let me take a quick look at your inbox first.",
              () => {
                addCard(hachiId, {
                  key: "inbox",
                  icon: "mail",
                  title: "Searched your inbox",
                  status: "done",
                  cost: 0.01,
                  tool: "gmail.search(query='is:unread', max=20)",
                  detail:
                    "12 unread · 3 look urgent.\nTop: Priya — \"Q3 deck feedback?\" (2 days ago)",
                  expanded: false,
                });
                setTimeout(() => {
                  stream(
                    hachiId,
                    " Three look urgent — the clearest is Priya waiting on the Q3 deck. I can send her a short reply. Want me to?",
                    () => {
                      set({
                        inContext: {
                          msgId: hachiId,
                          request: "Hachi wants to send an email to Priya",
                          action:
                            "gmail.send to: priya@studio.co · Re: Q3 deck feedback",
                          why: "she's been waiting two days for your reply",
                        },
                      });
                    }
                  );
                }, 450);
              }
            );
          }
        },

        retryLastMessage: () => {
          // Find the last user prompt and the trailing (failed) assistant bubble.
          const msgs = get().messages;
          let youText: string | null = null;
          let hachiId: number | null = null;
          for (let i = msgs.length - 1; i >= 0; i -= 1) {
            if (hachiId === null && msgs[i].role === "hachi") hachiId = msgs[i].id;
            if (msgs[i].role === "you") {
              youText = msgs[i].text;
              break;
            }
          }
          if (!youText || hachiId === null) return;
          const retryHachiId = hachiId;
          // Reset the failed assistant bubble IN PLACE — appending a new you/hachi pair
          // was the source of the duplicated user message on retry.
          set((s) => ({
            streaming: true,
            inContext: null,
            messages: s.messages.map((m) =>
              m.id === retryHachiId ? { ...m, text: "", cards: [] } : m
            ),
          }));
          if (get().dataMode === "live") {
            startTaskLive(youText, retryHachiId).catch(() => {
              set((s) => ({
                streaming: false,
                messages: s.messages.map((m) =>
                  m.id === retryHachiId
                    ? { ...m, text: m.text || "Something went wrong — please try again.", error: true }
                    : m
                ),
              }));
              toast("Send failed — please try again", "blocked");
            });
          } else {
            // Mock mode has no live gateway to resend against — just clear the error.
            set({ streaming: false });
          }
        },

        sendMessage: (text) => get().startTask(text),

        stopStreaming: () => {
          // Live mode: abort the SSE stream via chat.ts
          if (get().dataMode === "live") {
            stopStreamingLive();
            set({ streaming: false, inContext: null });
            toast("Stopped — Hachi is resting", "success");
            return;
          }

          // ── Mock mode: keep existing simulated implementation ──────────────
          clearIv();
          const last = [...get().messages].reverse().find((m) => m.role === "hachi");
          set({ streaming: false, inContext: null });
          if (last) setText(last.id, getText(last.id) + " …stopped.");
          toast("Stopped — Hachi is resting", "success");
        },

        icAllow: () => {
          // Live mode: clear leash and let the SSE stream continue
          if (get().dataMode === "live") {
            void allowLeashLive();
            return;
          }

          // ── Mock mode: keep existing simulated implementation ──────────────
          const ic = get().inContext;
          if (!ic) return;
          const id = ic.msgId;
          set({ inContext: null });
          addCard(id, {
            key: "send",
            icon: "send",
            title: "Sending email to Priya",
            status: "working",
            cost: 0.0,
            tool: "gmail.send(to='priya@studio.co')",
            detail:
              "To: priya@studio.co\nRe: Q3 deck feedback\n\"Here's the latest — your notes are folded in. Happy to walk through it tomorrow.\"",
            expanded: false,
          });
          setTimeout(() => {
            setCard(id, "send", { status: "done", title: "Sent email to Priya", cost: 0.02 });
            stream(
              id,
              " Done — your reply is on its way. Anything else?",
              () => {
                set((s) => ({
                  streaming: false,
                  taskSpent:
                    Math.round((s.taskSpent + 0.02) * 100) / 100,
                  spent:
                    Math.round((s.spent + 0.02) * 100) / 100,
                }));
                toast("Sent — Hachi is resting", "success");
              }
            );
          }, 1500);
        },

        icAlwaysAllow: () => {
          // Always-allow: persist to gateway via POST /sessions/{id}/permissions/always-allow
          // then fall through to the same optimistic path as icAllow.
          const _ic = get().inContext;
          if (!_ic) return;

          if (get().dataMode === "live") {
            // Persist always-allow rule to the gateway; surface failure honestly.
            void (async () => {
              try {
                await apiSend("POST", `/sessions/current/permissions/always-allow`, {
                  request: _ic.request,
                  action: _ic.action,
                });
                // On success, let the live stream continue as "allow once" would
                void allowLeashLive();
                toast("Always allowed — Hachi won't ask again for this", "success");
              } catch {
                // Endpoint returned an error — tell the user, don't silently proceed
                toast("Could not save always-allow rule — please try again", "blocked");
              }
            })();
            return;
          }

          // Mock mode: same visual path as icAllow + show a different toast
          get().icAllow();
          toast("Always allowed — Hachi won't ask again for this", "success");
        },

        icDeny: () => {
          // Live mode: abort stream (user declined permission)
          if (get().dataMode === "live") {
            void denyLeashLive();
            toast("Stayed put — Hachi is resting", "success");
            return;
          }

          // ── Mock mode: keep existing simulated implementation ──────────────
          const ic = get().inContext;
          if (!ic) return;
          const id = ic.msgId;
          set({ inContext: null });
          stream(
            id,
            " No problem — I'll leave it. What else can I do?",
            () => set({ streaming: false })
          );
          toast("Stayed put — Hachi is resting", "success");
        },

        toggleCard: (mid, key) => {
          set((s) => ({
            messages: s.messages.map((m) =>
              m.id === mid
                ? {
                    ...m,
                    cards: m.cards.map((c) =>
                      c.key === key ? { ...c, expanded: !c.expanded } : c
                    ),
                  }
                : m
            ),
          }));
        },

        dryRunRoutine: (msgId) => {
          if (get().streaming) return;
          set({ streaming: true });
          addCard(msgId, {
            key: "dry",
            icon: "play",
            title: "Dry run — nothing sent",
            status: "working",
            cost: 0.0,
            tool: "scheduler.dry_run(routine='inbox_triage')",
            detail:
              "Ran the routine once against today's inbox, in a safe sandbox. Nothing left your machine.",
            expanded: false,
          });
          setTimeout(() => {
            setCard(msgId, "dry", { status: "done", cost: 0.03 });
            setRoutine(msgId, { dryRunDone: true });
            stream(
              msgId,
              " Dry run looks good — it found 3 urgent emails and drafted the briefing. Ready to set it live?",
              () =>
                set((s) => ({
                  streaming: false,
                  taskSpent:
                    Math.round((s.taskSpent + 0.03) * 100) / 100,
                  spent:
                    Math.round((s.spent + 0.03) * 100) / 100,
                }))
            );
          }, 1600);
        },

        createRoutine: (msgId) => {
          if (get().streaming) return;
          const m = get().messages.find((x) => x.id === msgId);
          const ro = m?.routine ?? {};
          set((s) => ({
            streaming: true,
            routines: [
              {
                id: nextId(),
                title: (ro as Record<string,unknown>).title as string || "New routine",
                schedule: "weekdays 8:00",
                next: "tomorrow 8:00",
                cost: ((ro as Record<string,unknown>).costPerRun as number) || 0.04,
                paused: false,
                steps: ((ro as Record<string,unknown>).steps as string[] || []).map((l: string) => ({
                  label: l,
                  state: "done" as const,
                })),
                runHistory: [],
              },
              ...s.routines,
            ],
            messages: s.messages.map((msg) =>
              msg.id === msgId
                ? { ...msg, routine: { ...(msg.routine || {}), created: true } }
                : msg
            ),
          }));
          stream(
            msgId,
            " Done — it's on watch under your routines. I'll run it tomorrow at 8:00.",
            () => set({ streaming: false })
          );
          toast("Added — the routine is on watch", "success");
        },

        // live run
        openRun: (runId, from = "home") => {
          _runFrom = from;

          // Live mode: don't seed mock data or start the mock interval.
          if (get().dataMode === "live") {
            const rv = get().runView;
            if (!rv) {
              toast("Nothing live right now — start a task in the conversation", "success");
            }
            // If runView exists it was already seeded by startTaskLive — leave it.
            return;
          }

          // ── Mock mode: existing simulation ──────────────────────────────────
          clearRunIv();
          const s = get();
          const r =
            (runId != null && s.runs.find((x) => x.id === runId)) ||
            s.runs[0];
          if (!r) {
            toast("Nothing live right now — Hachi is on watch", "success");
            return;
          }
          set({
            runView: r,
            runLines: [
              { text: "hachi ▸ run " + slug(r.title) + " --watch" },
              { text: "→ starting on your machine", tone: "muted" },
            ],
            runStreaming: true,
            runDone: false,
            runLeash: null,
            runSpent: r.spent || 0,
            runPack: [
              { id: "p1", name: "reader-1", role: "reader", task: "reading PR #482 · auth refactor", status: "working", tokens: 6240 },
              { id: "p2", name: "reader-2", role: "reader", task: "reading PR #485 · vitest migration", status: "working", tokens: 5180 },
              { id: "p3", name: "writer", role: "writer", task: "waiting for the readers", status: "pending", tokens: 0 },
            ],
            runSteps: (
              r.steps && r.steps.length
                ? r.steps
                : [
                    { label: "Read the source", state: "working" },
                    { label: "Do the work", state: "pending" },
                    { label: "Report back to you", state: "pending" },
                  ]
            ).map((step) => ({ ...step })),
          });
          _runQueue = [
            { line: { text: "✓ cloned repo index · 1,204 files", tone: "success" }, steps: [{ i: 0, state: "done" }] },
            { line: { text: "→ spawning the pack · 3 sub-agents", tone: "muted" }, steps: [{ i: 1, state: "working" }] },
            { line: { text: "· reader-1 → PR #482 auth refactor", tone: "muted" } },
            { line: { text: "· reader-2 → PR #485 vitest migration", tone: "muted" } },
            { line: { text: "✓ reader-1 done — 2 risks noted", tone: "success" }, pack: { id: "p1", status: "done", task: "PR #482 · 2 risks noted" }, spend: 0.01 },
            { line: { text: "✓ reader-2 done — looks clean", tone: "success" }, pack: { id: "p2", status: "done", task: "PR #485 · looks clean" }, spend: 0.01 },
            { line: { text: "→ writer drafting the summary", tone: "muted" }, pack: { id: "p3", status: "working", task: "drafting the summary" }, steps: [{ i: 1, state: "done" }, { i: 2, state: "working" }] },
            { line: { text: "✓ summary ready — 6 PRs · 2 need review", tone: "success" }, pack: { id: "p3", status: "done", task: "summary drafted" }, steps: [{ i: 2, state: "done" }], spend: 0.01 },
            { leash: { request: "Hachi wants to post the summary", action: "slack.post #eng · \"This week: 6 PRs, 2 need review\"", why: "share the weekly PR summary with your team" }, steps: [{ i: 3, state: "working" }] },
            { line: { text: "✓ posted to #eng", tone: "success" } },
          ];
          _runStart = Date.now();
          _runIv = setInterval(() => runTick(), 1100);
        },

        watchLive: (runId) => get().openRun(runId, "work"),

        closeRun: () => {
          clearRunIv();
          _runQueue = [];
          set({ runView: null, runLeash: null });
        },

        runAllowLeash: () => {
          // Live mode: route approval through the gateway
          if (get().dataMode === "live") {
            set((s) => ({
              runLeash: null,
              runStreaming: true,
              runLines: [...s.runLines, { text: "✓ allowed — continuing", tone: "success" }],
            }));
            void allowLeashLive();
            toast("On it — Hachi is working", "working");
            return;
          }

          // ── Mock mode ─────────────────────────────────────────────────────
          set((s) => ({
            runLeash: null,
            runStreaming: true,
            runLines: [...s.runLines, { text: "✓ allowed — posting now", tone: "success" }],
          }));
          clearRunIv();
          _runIv = setInterval(() => runTick(), 1100);
          toast("On it — Hachi is working", "working");
        },

        runAlwaysAllow: () => {
          const rl = get().runLeash;
          if (get().dataMode === "live") {
            if (rl) {
              // Persist the always-allow rule; surface failure honestly
              void (async () => {
                try {
                  await apiSend("POST", `/sessions/current/permissions/always-allow`, {
                    request: rl.request,
                    action: rl.action,
                  });
                  set((s) => ({
                    runLeash: null,
                    runStreaming: true,
                    runLines: [...s.runLines, { text: "✓ always allowed — continuing", tone: "success" }],
                  }));
                    void allowLeashLive();
                  toast("Saved — Hachi won't ask again for this", "success");
                } catch {
                  // Endpoint returned an error — tell the user
                  toast("Could not save always-allow rule — please try again", "blocked");
                }
              })();
            } else {
              // No leash context — just allow
              set((s) => ({
                runLeash: null,
                runStreaming: true,
                runLines: [...s.runLines, { text: "✓ always allowed — continuing", tone: "success" }],
              }));
              void allowLeashLive();
              toast("Saved — Hachi won't ask again for this", "success");
            }
            return;
          }

          // ── Mock mode ─────────────────────────────────────────────────────
          // Then proceed exactly like runAllowLeash
          set((s) => ({
            runLeash: null,
            runStreaming: true,
            runLines: [...s.runLines, { text: "✓ always allowed — posting now", tone: "success" }],
          }));
          clearRunIv();
          _runIv = setInterval(() => runTick(), 1100);
          toast("Saved — Hachi won't ask again for this", "success");
        },

        runDenyLeash: () => {
          // Live mode: abort the stream and mark done
          if (get().dataMode === "live") {
            const s = get();
            set({
              runLeash: null,
              runStreaming: false,
              runDone: true,
              runLines: [
                ...s.runLines,
                { text: "✗ denied — Hachi is resting", tone: "danger" },
              ],
              runPack: s.runPack.map((p) => ({
                ...p,
                status: p.status === "working" ? "done" as const : p.status,
              })),
            });
              void denyLeashLive();
            toast("Stayed put — Hachi is resting", "success");
            return;
          }

          // ── Mock mode ─────────────────────────────────────────────────────
          clearRunIv();
          _runQueue = [];
          const s = get();
          set({
            ...archiveRun(),
            runLeash: null,
            runStreaming: false,
            runDone: true,
            runLines: [
              ...s.runLines,
              { text: "✗ denied — Hachi is resting", tone: "danger" },
            ],
            runPack: s.runPack.map((p) => ({
              ...p,
              status: p.status === "working" ? "done" as const : p.status,
            })),
          });
          toast("Stayed put — Hachi is resting", "success");
        },

        stopRun: () => {
          // Live mode: abort the SSE stream and mark done
          if (get().dataMode === "live") {
            const s = get();
            set({
              runStreaming: false,
              runDone: true,
              runLeash: null,
              runLines: [
                ...s.runLines,
                { text: "■ stopped — Hachi is resting", tone: "muted" },
              ],
              runPack: s.runPack.map((p) => ({
                ...p,
                status: p.status === "working" ? "done" as const : p.status,
              })),
            });
              stopStreamingLive();
            toast("Stopped — Hachi is resting", "success");
            return;
          }

          // ── Mock mode ─────────────────────────────────────────────────────
          clearRunIv();
          _runQueue = [];
          const s = get();
          set({
            ...archiveRun(),
            runStreaming: false,
            runDone: true,
            runLeash: null,
            runLines: [
              ...s.runLines,
              { text: "■ stopped — Hachi is resting", tone: "muted" },
            ],
            runPack: s.runPack.map((p) => ({
              ...p,
              status: p.status === "working" ? "done" as const : p.status,
            })),
          });
          toast("Stopped — Hachi is resting", "success");
        },

        // session switching (M8 MED-020)
        switchSession: (sessionId) => {
          if (get().dataMode === "live") {
            void switchSessionLive(sessionId);
            return;
          }
          // Mock mode: just flip the active flag
          set((s) => ({
            messages: [],
            sessions: s.sessions.map((sess) =>
              sess.id === sessionId
                ? { ...sess, active: true }
                : { ...sess, active: false }
            ),
          }));
        },

        newSession: () => {
          if (get().dataMode === "live") {
            newSessionLive();
            return;
          }
          // Mock mode: clear messages and deactivate all sessions
          set((s) => ({
            messages: [],
            sessions: s.sessions.map((sess) => ({ ...sess, active: false })),
          }));
        },

        simulateReconnect: () => {
          set({ reconnecting: true, palette: { open: false, query: "" } });
          if (_rc) clearTimeout(_rc);
          _rc = setTimeout(() => {
            set({ reconnecting: false });
            toast("Reconnected — Hachi is back", "success");
          }, 3800);
        },
      };
    },
    {
      name: "hachi-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        operator: state.operator,
        theme: state.theme,
      }),
    }
  )
);

// Wire the client's reconnect callback to the store's setReconnecting action.
// This runs once when the store module loads (module scope), avoiding a circular
// import (client.ts ← store.ts ← client.ts) by using a callback injection pattern.
registerReconnectCallback((v) => useStore.getState().setReconnecting(v));
