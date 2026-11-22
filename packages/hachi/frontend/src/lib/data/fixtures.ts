// ============================================================
// Hachi Web App — initial state fixtures
// Copied verbatim from logic class (lines 1476–1722)
// expiresAt is computed at init time so countdowns are live.
// ============================================================

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
} from "./types";

// Scalars
export const initialSpent = 0.41;
export const initialBudget = 5.0;
export const initialTaskSpent = 0.03;

// ---- approvals ----
// expiresAt seeded in initFixtures() below
export function initApprovals(): Approval[] {
  const now = Date.now();
  return [
    {
      id: 1,
      icon: "mail",
      request: "Hachi wants to send an email to Priya",
      why: "reply to her question about the Q3 deck",
      action: "gmail.send to: priya@studio.co · subject: Re: Q3 deck feedback",
      op: "send an email",
      policy: "asks before anything leaves your machine",
      touches: ["Re: Q3 deck feedback", "priya@studio.co"],
      risk: "medium",
      scope: "this contact",
      expiresAt: now + 95000,
      totalMs: 95000,
    },
    {
      id: 2,
      icon: "trash",
      request: "Hachi wants to delete 142 files",
      why: "clear ~/Downloads/old as you asked last week",
      action: "rm -rf ~/Downloads/old/*",
      op: "delete files",
      policy: "asks before deleting anything",
      touches: ["~/Downloads/old/", "142 files · 0 outside it"],
      risk: "high",
      scope: "this folder",
      expiresAt: now + 180000,
      totalMs: 180000,
    },
  ];
}

export const history: HistoryItem[] = [
  { id: 90, icon: "circle-check", request: "Ran npm install", decision: "allowed once", when: "12 min ago", color: "var(--hachi-success)" },
  { id: 91, icon: "circle-check", request: "Read your project folder", decision: "always allowed", when: "1 hr ago", color: "var(--hachi-success)" },
  { id: 92, icon: "clock", request: "Post to #deploys", decision: "timed out — Hachi stayed put", when: "2 hrs ago", color: "var(--hachi-muted)" },
  { id: 93, icon: "x", request: "Push to main", decision: "declined", when: "yesterday", color: "var(--hachi-danger)" },
];

export const runs: Run[] = [
  {
    id: 10,
    title: "Summarise this week's pull requests",
    status: "working",
    progress: 0.42,
    spent: 0.03,
    budget: 1.0,
    meta: "Reading 8 PRs",
    owner: "this conversation",
    when: "started 4 min ago",
    steps: [
      { label: "Cloned the repo index", state: "done" },
      { label: "Reading 8 open pull requests", state: "working" },
      { label: "Drafting the summary", state: "pending" },
      { label: "Posting it to you", state: "pending" },
    ],
  },
];

export const routines: Routine[] = [
  {
    id: 20,
    title: "Morning briefing",
    schedule: "weekdays 8:00",
    next: "tomorrow 8:00",
    cost: 0.04,
    paused: false,
    steps: [
      { label: "Read your inbox", state: "done" },
      { label: "Read your calendar", state: "done" },
      { label: "Summarise and flag what's urgent", state: "done" },
      { label: "Message you the briefing", state: "done" },
    ],
    runHistory: [
      { when: "today 8:00", cost: 0.04, ok: true },
      { when: "Fri 8:00", cost: 0.03, ok: true },
      { when: "Thu 8:00", cost: 0.05, ok: true },
    ],
  },
  {
    id: 21,
    title: "Watch the deploy channel",
    schedule: "always on",
    next: "live",
    cost: 0.0,
    paused: false,
    steps: [
      { label: "Watch #deploys", state: "working" },
      { label: "Flag failures to you", state: "pending" },
    ],
    runHistory: [{ when: "continuous", cost: 0.0, ok: true }],
  },
];

export const finished: FinishedTask[] = [
  {
    id: 30,
    title: "Drafted reply to Priya",
    note: "Hachi is resting",
    when: "20 min ago",
    cost: 0.02,
    result: "Sent a 3-line reply with the latest deck attached.",
    steps: [
      { label: "Read the thread", state: "done" },
      { label: "Drafted the reply", state: "done" },
      { label: "Sent it (you allowed)", state: "done" },
    ],
  },
  {
    id: 31,
    title: "Updated 6 dependencies",
    note: "Hachi is resting",
    when: "1 hr ago",
    cost: 0.09,
    result: "6 packages bumped, the test suite passes.",
    steps: [
      { label: "Checked for updates", state: "done" },
      { label: "Bumped 6 packages", state: "done" },
      { label: "Ran the test suite", state: "done" },
    ],
  },
  {
    id: 32,
    title: "Backed up your notes",
    note: "Hachi is resting",
    when: "this morning",
    cost: 0.01,
    result: "412 notes backed up to your Drive.",
    steps: [
      { label: "Collected 412 notes", state: "done" },
      { label: "Uploaded to Drive", state: "done" },
    ],
  },
];

export const failed: FailedTask[] = [
  {
    id: 40,
    title: "Deploy preview to staging",
    status: "blocked",
    owner: "a routine",
    when: "failed 30 min ago",
    cost: 0.05,
    error: "exit 1: missing env var STRIPE_KEY\n  at deploy.sh:12 → vercel deploy --prebuilt",
    waitingOn: "the STRIPE_KEY secret — add it in Integrations, then retry",
    steps: [
      { label: "Built the preview bundle", state: "done" },
      { label: "Uploaded assets", state: "done" },
      { label: "Ran deploy.sh", state: "failed" },
    ],
  },
];

export const memGroups: MemGroup[] = [
  {
    id: "you",
    title: "About you",
    facts: [
      { id: "f1", text: "Your name is Sam. You go by Sam in messages.", source: "from setup" },
      { id: "f2", text: "You're based in Lisbon (UTC+0).", source: "learned from your calendar" },
    ],
  },
  {
    id: "work",
    title: "Your work",
    facts: [
      { id: "f3", text: "You're shipping Hachi v1 — desktop, local-first.", source: "from a conversation" },
      { id: "f4", text: "Priya is your design lead. Reply to her quickly.", source: "from a conversation" },
    ],
  },
  {
    id: "notes",
    title: "Hachi's own notes",
    facts: [
      { id: "f5", text: "Prefers terse summaries with the action up top.", source: "Hachi noted this" },
    ],
  },
];

export const blocked: BlockedItem[] = [
  { id: "b1", text: "A password that appeared in a pasted log", reason: "looked like a secret — quarantined, not stored" },
  { id: "b2", text: "A credit card number from an email", reason: "looked like a secret — quarantined, not stored" },
];

export const proposed: ProposedChange = {
  from: "You prefer meetings in the morning",
  to: "You prefer meetings before 11am, and no meetings on Fridays",
};

export const skills: Skill[] = [
  { id: "s1", icon: "mail", name: "Email", desc: "Read, draft, and send through your connected inbox.", uses: "42 times", lastUsed: "today", stale: false },
  { id: "s2", icon: "calendar", name: "Calendar", desc: "Read your schedule and propose meeting times.", uses: "18 times", lastUsed: "yesterday", stale: false },
  { id: "s3", icon: "terminal", name: "Shell", desc: "Run commands on your machine, within the leash.", uses: "9 times", lastUsed: "1 hr ago", stale: false },
  { id: "s4", icon: "globe", name: "Web research", desc: "Search and read pages to answer questions.", uses: "2 times", lastUsed: "94 days ago", stale: true },
];

export const kennel: KennelItem[] = [
  { id: "k1", icon: "git-branch", name: "GitHub", desc: "Triage issues, open PRs, summarise diffs." },
  { id: "k2", icon: "file", name: "Notion", desc: "Read and update your workspace pages." },
  { id: "k3", icon: "hash", name: "Slack", desc: "Watch channels and post on your behalf." },
];

export const integrations: Integration[] = [
  { id: "i1", icon: "mail", name: "Google", can: "Gmail · Calendar · Drive", status: "connected", risky: false },
  { id: "i2", icon: "hash", name: "Slack", can: "read & post in 3 channels", status: "connected", risky: false },
  { id: "i3", icon: "file", name: "Notion", can: "not connected", status: "none", risky: false },
  { id: "i4", icon: "terminal", name: "Local MCP tools", can: "filesystem · shell — broad access", status: "degraded", risky: true },
];

export const mcpServers: McpServer[] = [
  { name: "filesystem", status: "connected", tools: 11, transport: "stdio", uptime: "2h 14m" },
  { name: "git", status: "connected", tools: 9, transport: "stdio", uptime: "2h 14m" },
  { name: "search", status: "connected", tools: 7, transport: "sse", uptime: "1h 02m" },
  { name: "browser", status: "starting", tools: 0, transport: "stdio", uptime: "—" },
  { name: "postgres", status: "blocked", tools: 0, transport: "stdio", uptime: "—", err: "can't reach 127.0.0.1:5432" },
];

export const mcpTools: McpTool[] = [
  { name: "read_file", server: "filesystem", args: [["path", "text"], ["range", "numbers?"]] },
  { name: "write_file", server: "filesystem", args: [["path", "text"], ["content", "text"]] },
  { name: "grep", server: "filesystem", args: [["pattern", "text"], ["path", "text?"]] },
  { name: "git_log", server: "git", args: [["max", "number?"]] },
  { name: "web_search", server: "search", args: [["query", "text"], ["k", "number?"]] },
];

export const ogNodes: OgNode[] = [
  { id: "brain", name: "brain.og", kind: "root", index: 42, dense: 380, full: 2140, deps: ["deep_research", "code_review", "git_sync"] },
  { id: "deep_research", name: "deep_research.og", kind: "skill", index: 38, dense: 410, full: 1980, deps: ["web_search", "summarize"] },
  { id: "code_review", name: "code_review.og", kind: "skill", index: 34, dense: 360, full: 1720, deps: ["git_diff"] },
  { id: "git_sync", name: "git_sync.og", kind: "skill", index: 30, dense: 290, full: 1340, deps: ["git_diff"] },
  { id: "web_search", name: "web_search.og", kind: "leaf", index: 22, dense: 180, full: 760, deps: [] },
  { id: "summarize", name: "summarize.og", kind: "leaf", index: 20, dense: 160, full: 690, deps: [] },
  { id: "git_diff", name: "git_diff.og", kind: "leaf", index: 24, dense: 210, full: 880, deps: [] },
];

export const authTargets: AuthTarget[] = [
  { name: "brain.og", path: "~/.hachi/brain.og", kind: "brain", dirty: false },
  { name: "deep_research.og", path: "~/.hachi/skills/deep_research.og", kind: "skill", dirty: true },
  { name: "code_review.og", path: "~/.hachi/skills/code_review.og", kind: "skill", dirty: false },
  { name: "git_sync.og", path: "~/.hachi/skills/git_sync.og", kind: "skill", dirty: false },
  { name: "hachi.json", path: "~/.hachi/hachi.json", kind: "config", dirty: false },
];

export const authSource: DiffLine[] = [
  ["", "node deep_research {"],
  ["", "  @index \"Multi-source research with citation tracking.\""],
  ["", "  pass dense {"],
  ["del", "    budget: 1800"],
  ["add", "    budget: 2400"],
  ["", "    tools: [web_search, summarize, fetch]"],
  ["del", "    strategy: \"breadth-first\""],
  ["add", "    strategy: \"adaptive\""],
  ["add", "    max_subagents: 3"],
  ["", "  }"],
  ["", "  pass full {"],
  ["", "    cite: required"],
  ["", "  }"],
  ["", "}"],
];

export const spendTurns: SpendTurn[] = [
  { n: 1, inT: 2140, out: 880, cost: 0.041 },
  { n: 2, inT: 3010, out: 1240, cost: 0.058 },
  { n: 3, inT: 1820, out: 640, cost: 0.032 },
  { n: 4, inT: 4200, out: 2100, cost: 0.092 },
  { n: 5, inT: 2600, out: 1180, cost: 0.054 },
  { n: 6, inT: 3400, out: 1620, cost: 0.075 },
  { n: 7, inT: 1280, out: 760, cost: 0.028 },
];

export const spendTidies: SpendTidy[] = [
  { ts: "13:48", before: 142000, after: 38000 },
  { ts: "14:02", before: 96000, after: 31000 },
  { ts: "14:18", before: 88000, after: 31200 },
];

export const spendModels: SpendModel[] = [
  { name: "Claude Sonnet", tokens: 142000, cost: 2.84, color: "var(--hachi-trust)" },
  { name: "Claude Opus", tokens: 38000, cost: 1.71, color: "var(--hachi-working)" },
  { name: "Llama 3.3 (local)", tokens: 96000, cost: 0, color: "var(--hachi-success)" },
];

export const packRoster: PackMember[] = [
  { role: "researcher", task: "survey this week's pull requests", status: "working", outcome: "—", tokens: 12480 },
  { role: "planner", task: "decompose the summary into steps", status: "done", outcome: "3-step plan", tokens: 2140 },
  { role: "critic", task: "check the draft reads clearly", status: "done", outcome: "clear · approved", tokens: 1860 },
];

export const events: ActivityEvent[] = [
  { t: "14:22:06", type: "finished a tool call", d: "read 8 pull requests", lvl: "ok" },
  { t: "14:22:05", type: "started a tool call", d: "reading pull requests", lvl: "info" },
  { t: "14:22:04", type: "wrote to you", d: "+128 words", lvl: "muted" },
  { t: "14:21:40", type: "you allowed", d: "write notes.md", lvl: "ok" },
  { t: "14:21:38", type: "asked you", d: "write notes.md", lvl: "warn" },
  { t: "14:20:11", type: "a job failed", d: "fetch — rate limited", lvl: "error" },
  { t: "14:19:02", type: "a server came online", d: "filesystem · 11 tools", lvl: "ok" },
];

export const toolCalls: ToolCall[] = [
  { tool: "read_pull_requests", inp: '{"repo":"hachi"}', out: "8 PRs", dur: "1.8s", ts: "14:22" },
  { tool: "list_tools", inp: '{"servers":["*"]}', out: "27 tools", dur: "0.4s", ts: "14:22" },
  { tool: "memory.search", inp: '{"q":"repo root"}', out: "2 hits", dur: "0.2s", ts: "14:21" },
  { tool: "write_file", inp: '{"path":"notes.md"}', out: "ok", dur: "0.1s", ts: "14:21" },
];

export const auditLog: AuditEntry[] = [
  { ts: "14:21:40", op: "write a file", target: "patches/notes.md", policy: "asks first", decision: "allowed" },
  { ts: "13:58:02", op: "fetch a url", target: "api.github.com", policy: "asks first", decision: "allowed once" },
  { ts: "13:41:55", op: "run a command", target: "rm -rf ./build", policy: "asks first", decision: "declined" },
  { ts: "13:30:10", op: "read a file", target: "src/og/parser.py", policy: "sandboxed", decision: "automatic" },
];

export const recall: RecallHit[] = [
  { fact: "Repo root is ~/code/hachi; you prefer read-only scans first.", score: "0.94", src: "a session · 2d ago" },
  { fact: "Default model is Claude Sonnet; opus only for deep research.", score: "0.91", src: "settings · 5d ago" },
  { fact: "Never run a destructive command without asking you.", score: "0.89", src: "your leash · 12d ago" },
];

export const sessions: Session[] = [
  { id: "now", title: "Summarise this week's PRs", turns: 7, model: "sonnet", date: "today · 14:22", active: true },
  { id: "s2", title: "Reply to Priya about Q3", turns: 22, model: "opus", date: "yesterday", active: false },
  { id: "s3", title: "Tidy up the Downloads folder", turns: 14, model: "sonnet", date: "Jun 12", active: false },
  { id: "s4", title: "Set up the morning briefing", turns: 9, model: "llama", date: "Jun 11", active: false },
];

export const skillUsage: SkillUsage[] = [
  { name: "deep_research.og", calls: 142, tokens: "1.2K", saved: "84%" },
  { name: "code_review.og", calls: 98, tokens: "0.9K", saved: "79%" },
  { name: "git_sync.og", calls: 61, tokens: "0.6K", saved: "88%" },
  { name: "memoir.og", calls: 40, tokens: "0.7K", saved: "82%" },
];

export const askRules: AskRule[] = [
  { id: "r1", label: "Before spending over $0.50 on one task", on: true },
  { id: "r2", label: "Before sending anything outside your machine", on: true },
  { id: "r3", label: "Before deleting files", on: true },
];

export const allowedFolders: string[] = ["~/projects", "~/Downloads", "~/Documents/notes"];

export const allowedCommands: string[] = ["npm", "git", "ls", "cat", "grep"];

export const opTools: OpTool[] = [
  { id: "t1", label: "Filesystem", scope: "read + write in allowed folders", on: true },
  { id: "t2", label: "Shell", scope: "allowed commands only", on: true },
  { id: "t3", label: "Network", scope: "fetch + outbound HTTP", on: false },
];
