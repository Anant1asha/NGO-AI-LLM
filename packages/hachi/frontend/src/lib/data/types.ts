// ============================================================
// Hachi Web App — data types
// Source: logic class state (Hachi Web App.dc.html lines 1476–1722)
// ============================================================

export type SafetyLevel = "guarded" | "standard" | "open";
export type ScreenKey =
  | "home"
  | "chat"
  | "work"
  | "approvals"
  | "memory"
  | "skills"
  | "og"
  | "authoring"
  | "integrations"
  | "settings"
  | "run";

// ----- approvals -----
export interface Approval {
  id: number;
  icon: string;
  request: string;
  why: string;
  action: string;
  op: string;
  policy: string;
  touches: string[];
  risk: "low" | "medium" | "high";
  scope: string;
  expiresAt: number;
  totalMs: number;
}

export type ApprovalDecision =
  | "allowed once"
  | "always allowed"
  | "declined"
  | "timed out — Hachi stayed put";

export interface HistoryItem {
  id: number;
  icon: string;
  request: string;
  decision: ApprovalDecision | string;
  /** Pre-formatted display label ("just now", fixture strings). Use ts when available. */
  when: string;
  /** Unix-ms timestamp of the decision event — set by store actions, absent in fixture data. */
  ts?: number;
  color: string;
}

export interface AuditEntry {
  ts: string;
  op: string;
  target: string;
  policy: string;
  decision: "allowed" | "allowed once" | "declined" | "automatic" | string;
}

// ----- runs / routines / work -----
export interface RunStep {
  label: string;
  state: "done" | "working" | "pending" | "failed";
}

export interface Run {
  id: number;
  title: string;
  status: "working" | "on-watch" | "done" | "blocked";
  progress: number;
  spent: number;
  budget: number;
  meta?: string;
  owner?: string;
  when?: string;
  steps?: RunStep[];
}

export interface RoutineRun {
  when: string;
  cost: number;
  ok: boolean;
}

export interface Routine {
  id: number;
  title: string;
  schedule: string;
  next: string;
  last?: string;
  cost: number;
  paused: boolean;
  steps?: RunStep[];
  runHistory?: RoutineRun[];
}

export interface FinishedTask {
  id: number;
  title: string;
  note: string;
  when: string;
  cost: number;
  result?: string;
  steps?: RunStep[];
}

export interface FailedTask {
  id: number;
  title: string;
  status: string;
  owner?: string;
  when: string;
  cost: number;
  error?: string;
  waitingOn?: string;
  steps?: RunStep[];
}

// ----- memory -----
export interface Fact {
  id: string;
  text: string;
  source: string;
}

export interface MemGroup {
  id: string;
  title: string;
  facts: Fact[];
}

export interface BlockedItem {
  id: string;
  text: string;
  reason: string;
}

export interface ProposedChange {
  from: string;
  to: string;
}

// ----- skills / kennel -----
export interface Skill {
  id: string;
  icon: string;
  name: string;
  desc: string;
  uses: string;
  lastUsed: string;
  stale: boolean;
}

export interface KennelItem {
  id: string;
  icon: string;
  name: string;
  desc: string;
}

// ----- integrations / MCP -----
export interface Integration {
  id: string;
  icon: string;
  name: string;
  can: string;
  status: "connected" | "degraded" | "none";
  risky: boolean;
}

export interface McpServer {
  name: string;
  /**
   * "loading" is a transient state while the gateway is initialising the server.
   * "pending" means the server is registered but not connected in this session
   * yet (e.g. a TOML-persisted server before the first conversation boots) — it
   * is NOT actively starting, so it must render distinctly from "starting".
   */
  status: "connected" | "starting" | "blocked" | "loading" | "pending";
  tools: number;
  transport: string;
  uptime: string;
  err?: string;
}

export interface McpTool {
  name: string;
  server: string;
  args: [string, string][];
}

// ----- OG explorer -----
export interface OgNode {
  id: string;
  name: string;
  kind: "root" | "skill" | "leaf";
  index: number;
  dense: number;
  full: number;
  deps: string[];
}

// ----- authoring -----
export interface AuthTarget {
  name: string;
  path: string;
  kind: "brain" | "skill" | "config";
  dirty: boolean;
}

export type DiffLine = ["" | "add" | "del", string];

// ----- spend -----
export interface SpendTurn {
  n: number;
  inT: number;
  out: number;
  cost: number;
}

export interface SpendTidy {
  ts: string;
  before: number;
  after: number;
}

export interface SpendModel {
  name: string;
  tokens: number;
  cost: number;
  color: string;
}

// ----- pack (sub-agents) -----
export interface PackMember {
  role: string;
  task: string;
  status: "working" | "done" | "pending";
  outcome: string;
  tokens: number;
}

// ----- activity (operator) -----
export interface ActivityEvent {
  t: string;
  type: string;
  d: string;
  lvl: "ok" | "info" | "warn" | "error" | "muted";
}

export interface ToolCall {
  tool: string;
  inp: string;
  out: string;
  dur: string;
  ts: string;
}

// ----- memory recall + sessions + skill usage -----
export interface RecallHit {
  fact: string;
  score: string;
  src: string;
}

export interface Session {
  id: string;
  title: string;
  turns: number;
  model: string;
  date: string;
  active: boolean;
}

export interface SkillUsage {
  name: string;
  calls: number;
  tokens: string;
  saved: string;
}

export interface AskRule {
  id: string;
  label: string;
  on: boolean;
}

export interface OpTool {
  id: string;
  label: string;
  scope: string;
  on: boolean;
}

// ----- toast -----
export interface Toast {
  message: string;
  tone?: "success" | "working" | "blocked" | "info";
  /** Optional single action (e.g. "Undo"). Presence extends auto-dismiss to 6s. */
  action?: { label: string; onAction: () => void };
}

/** Toast with a store-assigned id for targeted dismissal. */
export interface ToastItem extends Toast {
  id: string;
}

// ----- chat message + action cards -----
export interface ActionCard {
  key: string;
  icon: string;
  title: string;
  status: "done" | "working" | "pending" | "blocked";
  cost: number;
  tool?: string;
  detail?: string;
  expanded: boolean;
}

export interface RoutineProposal {
  title?: string;
  trigger?: string;
  steps?: string[];
  needs?: string[];
  costPerRun?: number;
  dryRunDone?: boolean;
  created?: boolean;
}

export interface ChatMessage {
  id: number;
  role: "you" | "hachi";
  text: string;
  cards: ActionCard[];
  routine?: RoutineProposal | null;
  attachments?: Pick<PendingAttachment, "name" | "mediaType" | "size">[];
  /** Unix-ms when the message was created; absent for historical messages with no server timestamp. */
  ts?: number;
  /** Structural error flag — true when the hachi bubble represents a failed turn. */
  error?: boolean;
}

// ----- run pack (live run) -----
export interface RunPackMember {
  id: string;
  name: string;
  role: string;
  task: string;
  status: "working" | "done" | "pending";
  tokens: number;
}

// ----- in-context leash -----
export interface InContextLeash {
  msgId: number;
  request: string;
  action: string;
  why: string;
}

// ----- provider -----
export interface Provider {
  name: string;
  model: string;
  key: string;
}

// ----- eval loop / interactions -----
export interface AgentInteraction {
  id: string;
  sessionId: string;
  turnId: string | null;
  ts: string;
  /** Human-readable relative timestamp (e.g. "5m ago"). */
  tsHuman: string;
  userInput: string;
  agentOutput: string;
  /** Tool call names — string[], never objects. */
  toolCalls: string[];
  /** Memory hit descriptions — string[], never objects. */
  memoryHits: string[];
  modelUsed: string;
  tokenCost: number | null;
  tokens: number | null;
  rating: "up" | "down" | null;
  notes: string | null;
}

// ----- file attachments (Phase 4 — Initiative E wiring) -----
export interface PendingAttachment {
  /** Stable local key used before the server responds. Replaced by real SHA-256 file_id on upload success. */
  fileId: string;
  name: string;
  mediaType: string;
  size: number;
  /** Object URL for local image preview; undefined for non-image files. */
  localUrl?: string;
  /** True while the upload is in flight. */
  uploading?: boolean;
  /** Set when upload failed; chip shows an error state. */
  error?: string;
}
