# Hachi TUI — Product Design Specification

> The terminal cockpit for a governed personal AI assistant.
> Designed to be implemented directly against Hachi's existing runtime (Textual UI,
> `RuntimeReadModelStore`, the gateway control plane, and `device-permissions.og`).

This document specifies information architecture, navigation, screens, flows, and
interaction patterns. It does **not** specify color, typography, or brand. Where a
visual encoding is required (e.g. "running" vs "blocked"), it is specified as a
*semantic glyph + optional color*, with a no-color fallback, because that is
information design, not styling.

Every screen lists its **Data source** — the real read model, event, or gateway
route it binds to — so engineers can wire it without guessing. These names were
taken from the current codebase (`runtime_events.py`, `runtime_read_models.py`,
`fastapi_app.py`, `memory_vault.py`, `sub_agent.py`, `permissions.py`,
`jobs/queue.py`, `jobs/scheduler.py`).

---

## 0. The one-sentence design thesis

> **Hachi is not a chatbot with extra screens; it is a supervisor's console for a
> team of AI workers, where the conversation is one altitude and the fleet is
> another — and a single Trust Bar answers "can I trust what's happening right
> now?" at every altitude.**

Most agent UIs optimize for *autonomy* (let it run) or *chat* (talk to it). Hachi's
differentiator is **trust**, and trust is a UI property before it is a backend one:
it is the continuous, glanceable answer to *what is running, what is waiting, what
is blocked, what needs me, what is it spending, who is responsible.* The entire
design is organized around keeping those answers on screen, always, cheaply.

---

## 1. The eight questions (the acceptance test)

The brief's litmus test: opening the TUI must answer these within 5 seconds.

| # | Question | Where it is answered, always |
|---|----------|------------------------------|
| 1 | What is running? | Trust Bar `▶N running` + Dashboard *The Pack* / *Work Queue* |
| 2 | What is waiting? | Trust Bar `⧖N queued` + Tasks (queued) |
| 3 | What is blocked? | Trust Bar `⛔N blocked` + Tasks (suspended) |
| 4 | What needs my approval? | Trust Bar `⚠N approval` (the loudest signal) + Approvals |
| 5 | What is costing money? | Trust Bar `$X/$Y today` + Resources |
| 6 | What is consuming resources? | Trust Bar gauge + Resources (tokens/queue/agents) |
| 7 | Which agent is responsible? | Every action row/card carries an **owner** (turn / role / schedule) |
| 8 | Can I trust what is happening? | Trust Bar tier badge + ungated-tool flags + Audit being one key away |

**Design rule:** anything an agent does that spends money, touches the outside world,
or mutates state must be *attributable to a named owner* and *visible in the Trust
Bar's counters*. If it isn't, it is invisible, and invisible is the opposite of trust.

---

## 2. Personas → what they need the TUI to do

| Persona | Primary altitude | The TUI must let them… |
|---------|------------------|------------------------|
| **Power user / developer** | Focus (chat) | delegate work, watch tool calls inline, interrupt, retry, keep flow without leaving the keyboard |
| **AI enthusiast / tinkerer** | Cockpit | run several agents at once, switch models, compare cost, author skills, inspect traces |
| **Operator / "supervisor" mood** | Cockpit | triage approvals fast, pause/cancel runaway tasks, watch spend, investigate failures |
| **Future enterprise** | Cockpit + Audit | immutable audit, policy-as-code, attribution, export, role visibility |

These are not separate apps. They are the **same person on different days**. The
altitude model (below) lets one interface serve all four without modes that trap you.

---

## 3. Global architecture

### 3.1 The altitude model (the core idea)

Two ways of *being* in the same app, sharing one frame:

```
        FOCUS  ─────────────────  ⌃O  ─────────────────►  COCKPIT
   one conversation, full-screen      the whole system, gridded
   "I am working WITH hachi"          "I am supervising hachi"
        ◄───────────────  ↵ on a session / ⌃O  ──────────────
```

- **Focus altitude** = the Chat Workspace fills the frame. This is the default and
  where casual use lives. It feels like Claude Code: transcript, composer, inline
  tool/agent cards, a slim context inspector. Single conversation.
- **Cockpit altitude** = you "zoom out" to the operator console: Dashboard and the
  data views (Agents, Tasks, Approvals, Governance, Memory, Skills, Audit, Resources,
  Connections). This feels like k9s/btop: dense tables, gauges, hotkey navigation.

The **Trust Bar** and the **Command Palette** are constant at both altitudes, so you
never lose situational awareness or navigation when you change altitude. `⌃O` toggles;
`↵` on a conversation in the cockpit drops you into Focus on that session.

> Why this matters: it resolves the chat-vs-console tension that breaks most agent
> UIs. You don't choose a paradigm at install time; you change altitude per moment.

### 3.2 Frame anatomy

Every screen, both altitudes, is the same four bands plus an overlay layer:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ TRUST BAR        always-visible governance + state (2 lines)               │  band A
├──────────────────────────────────────────────┬───────────────────────────┤
│ MAIN VIEW                                      │ INSPECTOR (optional)      │  band B + C
│ chat / dashboard grid / data table             │ drill-down of selection   │
│                                                │ (collapses < 90 cols)     │
├──────────────────────────────────────────────┴───────────────────────────┤
│ FOOTER          command hint · context keybinds · breadcrumb               │  band D
└──────────────────────────────────────────────────────────────────────────┘
   OVERLAY LAYER (floats above everything): palette · approval modal · toasts · help
```

- **Band A — Trust Bar** (§3.3): persistent. Never scrolls. Highest priority pixels.
- **Band B — Main View**: the active screen.
- **Band C — Inspector**: right-hand drill-down of the selected row/card. Toggle `i`
  or `↵`. Auto-hides below 90 cols (content re-routes into the main view as a sub-page).
- **Band D — Footer**: left = global hint (`:cmd  /filter  ?help`); right = the keys
  that work *right here* (LazyGit-style context keys). Plus breadcrumb of where you are.
- **Overlay layer**: modal approvals, the command palette, notification toasts, the
  help cheat-sheet. Drawn above; dimming the frame behind.

### 3.3 The Trust Bar (specification)

Two lines. This is the single most important component in the product. It is the
answer to question 8. It must be legible at 80 cols and richer at 120+.

```
Line 1 (identity + state):
┌ hachi ▸ guided ───────────────────────────────── ◐ working · turn 3 · 14:22 ┐
   │        │                                        │        │
   wordmark tier badge (sandbox/guided/unrestricted) activity glyph + label

Line 2 (the eight answers, dense):
│ ▶2 running ⏸1 paused ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00 ▓▓▓░░ haiku │
   └running └paused  └queued    └blocked    └APPROVAL(loud) └spend/budget bar └model
```

**Field rules**

| Field | Source | Behavior |
|-------|--------|----------|
| tier badge | `PermissionGate.tier` / `GET /config` | `sandbox` / `guided` / `unrestricted`; unrestricted is visually loud (it's the risky one) |
| activity glyph + label | `RuntimeReadModelStore.activity()` → `ActivitySnapshot.{state,label}` | states `idle/running/pending/failed`; animated glyph reuses existing `HachiGlyph` eye frames |
| `▶ running` | `active_jobs()` count (job_type running) | hidden when 0 |
| `⏸ paused` | schedules with `enabled=False` + paused tasks | hidden when 0 |
| `⧖ queued` | `SessionStateSnapshot.pending_job_count` | hidden when 0 |
| `⛔ blocked` | suspended workflows (`core_suspend_workflow`) awaiting event | hidden when 0 |
| `⚠ approval` | `len(PendingApprovalRegistry.list_pending())` | **never hidden when >0; this is the loudest element**; blinks once on increment + bell |
| `$ spend/budget` | `activity().estimated_cost_usd` vs `max_cost_usd` | bar fills; turns "hot" at ≥80% of cap |
| model | `SessionStateSnapshot.model_name` | click/`m` to switch |

**No-color fallback:** every state also has a distinct glyph (`◐ ▶ ⏸ ⧖ ⛔ ⚠ ✓ ✗`), so
the bar is fully readable in a monochrome terminal. Color is redundant encoding, never
the sole carrier of meaning.

### 3.4 Navigation & focus model

The hard problem in a chat-first TUI: the composer wants every keystroke, but an
operator console wants single-key hotkeys. Solution — **focus determines the keymap**:

- **When a text input is focused** (chat composer, a filter box, an edit field):
  printable keys type. Navigation happens via **chords** (`⌃`/`Alt`), **slash
  commands** (`/…`), and the **palette** (`⌃K`). `Esc` interrupts the turn / blurs.
- **When no text input is focused** (any cockpit data view): **single-key hotkeys**
  are live (k9s/LazyGit style) — `j/k` move, `↵` inspect, `/` filter, `:` command,
  letters do context actions. `Esc` goes up the breadcrumb.

Three always-available ways to get anywhere (redundancy = discoverability):

1. **Command Palette** `⌃K` (or `:` when not in a text field) — fuzzy over **views**,
   **actions**, **sessions**, **skills**, **settings**. The universal spine. (Today's
   `Ctrl+P` binding is reused/relabeled for this.)
2. **Go-to mnemonics** — `g` then a letter (vim "goto"): `gc` chat, `gd` dashboard,
   `ga` agents, `gt` tasks, `gp` approvals, `gg` governance, `gm` memory, `gk` skills,
   `gl` ledger/audit, `gr` resources, `gn` connections, `gs` settings. Mnemonic, not
   positional — survives reordering, unlike `Ctrl+1..9`.
3. **The Dashboard** — every panel on it is a portal: `↵` a panel drills into its view.

> Migration note: the current TUI uses `Ctrl+1..9`/`F1..9`. Keep those as hidden
> aliases for one release, surface the `g<letter>` scheme in the footer + help, and
> let muscle memory transfer.

### 3.5 The view map (twelve views, four groups)

The palette and `g`-prefix expose twelve views. They are grouped for the mental model
(the groups appear as headers in the palette and the help sheet), but every view is one
keystroke away — you don't navigate the hierarchy, it's just for comprehension.

```
TALK
  Chat            gc   the conversation workspace (Focus altitude home)
WATCH (observability)
  Dashboard       gd   command center / pulse — the cockpit home
  Agents          ga   "the pack": live delegations + scheduled agents
  Tasks           gt   work queue: jobs + schedules + suspended workflows
  Audit           gl   immutable timeline / ledger / event log
  Resources       gr   meters: tokens, cost, calls, queue, memory
GOVERN (trust)
  Approvals       gp   approvals inbox (also interrupts as a modal)
  Governance      gg   permissions · budgets · approval rules · safety
KNOW (knowledge)
  Memory          gm   3-layer memory explorer (active · sessions · vault)
  Skills          gk   capabilities + OG 3-pass inspector + authoring
CONNECT / CONFIG
  Connections     gn   MCP servers + integrations + scopes + health
  Settings        gs   provider/model · memory · prefs · setup wizard
```

---

## 4. Screens

Each screen below gives: **purpose**, **wireframe**, **interactions** (the context
keys shown in the footer), **Data source**, and **empty/edge states**.

Conventions in wireframes: `◐` working, `▶` running, `⏸` paused, `⧖` queued,
`⛔` blocked/suspended, `⚠` needs-attention, `✓` ok/done, `✗` failed, `⏰`/`⏱` scheduled,
`▸` selected row, `▓░` gauge.

---

### 4.1 Chat Workspace (`gc`) — Focus altitude home

**Purpose.** The human-AI collaboration surface. Talk, delegate, watch work happen
inline, see the *plan* (what it intends to do next), interrupt, and approve in context.
This is the evolution of today's `SessionScreen`.

```
┌ hachi ▸ guided ─────────────────────────────────────────── ◐ working · turn 3 ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                │
├──────────────────────────────────────────────────────┬─────────────────────────┤
│  you ▸ research the latest AI funding rounds and       │ PLAN  (what's next)     │
│        draft a one-pager                                │ ☑ search sources        │
│                                                         │ ◐ read top 5 articles   │
│  hachi ▸ On it — gathering sources, then drafting.      │ ☐ extract figures       │
│          Delegating the research.                       │ ☐ draft one-pager       │
│                                                         │ ☐ save to Drive         │
│  ┌ ⛓ delegate ▸ researcher ─────────────────  18s ◐ ┐  ├─────────────────────────┤
│  │ task: gather funding rounds, last 30 days       │  │ CONTEXT                 │
│  │ ◐ browse_web   news.ycombinator.com        ⚠    │  │ model    haiku-4.5      │
│  │ ✓ google_search_drive  "AI funding" → 4 hits    │  │ tokens   184k (61% cache)│
│  └──────────────────────────────────────[↵ trace]──┘  │ spend    $0.42          │
│                                                         │ session  0xA31F · t3    │
│  ┌ ✓ read_file  notes/funding.md ──────── 1.2k · ok ┐  │ skill    research-proto │
│  └────────────────────────────────────────────[↵]──┘  ├─────────────────────────┤
│                                                         │ ⚠ 1 APPROVAL WAITING    │
│  hachi ▸ Found 6 rounds. Drafting now…                  │   browse_web (researcher)│
│  ▌                                                      │   [a] review now        │
├─────────────────────────────────────────────────────────┴─────────────────────┤
│ ▸ ask hachi…  (↵ send · ⇧↵ newline · / commands · ⎋ interrupt)                  │
└────────────────────────────────────────────────────────────────────────────────┘
 / commands   ⌃K palette   ⌃O cockpit   ⎋ interrupt turn   ↵ on a card = inspect
```

**Interactions.**
- Composer: `↵` send, `⇧↵` newline, `↑/↓` history recall (when slash menu hidden),
  `/` opens slash palette (the existing 20 commands), `⎋` graceful interrupt of the
  running turn.
- Cards: tool calls and delegations render as **collapsible inline cards** (reuse
  `ToolCard`). `↵` on a card opens the **Inspector** with full request/result, or the
  full agent trace for a delegation card. Cards stream status live.
- **PLAN panel**: renders the agent's current todo/plan when one exists (from a plan
  step or `/plan`). This is the literal answer to "what will it do next," kept on
  screen. Checkboxes advance as steps complete.
- In-context approval: when this session raises an approval, the Inspector shows a
  compact prompt and `a` jumps to the modal — you don't have to leave chat.
- Streaming: `text.stream.delta` accumulates into the live bubble; auto-follow scroll
  unless the user scrolled up (preserve existing behavior).

**Data source.** transcript = `SessionStore.get_session_messages` + live
`text.stream.delta`; cards = `tool.call.started/completed`, `subagent.started/completed`;
context = `SessionStateSnapshot` + `usage.updated`; plan = plan/todo events or the
active skill's `::steps`; approval = `PendingApprovalRegistry`.

**Empty state.** First run shows the splash (`HachiSplash`) + 3–4 `StarterPrompt`
chips ("Research a company", "Triage my inbox", "Watch a repo for releases") that
double as teaching the delegation/scheduling capabilities.

---

### 4.2 Dashboard (`gd`) — Cockpit home / "Pulse"

**Purpose.** The five-second answer to all eight questions. A btop/k9s-style grid of
live panels, each a portal into its view. This is what `⌃O` lands on.

```
┌ hachi ▸ guided ───────────────────────────────────────────── ◐ working · 14:22 ┐
│ ▶2 running ⏸1 paused ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00 ▓▓▓░░ haiku │
├──────────────────────────────┬─────────────────────────────────────────────────┤
│ ACTIVITY                      │ NEEDS YOU   (1)                          [p] open│
│ ◐ Working — browse_web        │ ⚠ researcher wants  browse_web                  │
│   turn 3 · iter 5/10          │   → https://news.ycombinator.com                │
│   ▓▓▓▓▓▓░░░░ 5 tools / turn   │   why: sources for "AI funding" one-pager       │
│                               │   [↵ review]   [y approve]   [n deny]           │
├──────────────────────────────┼─────────────────────────────────────────────────┤
│ THE PACK  (2 live · 1 sched)  │ SPEND TODAY                          $0.42 / $5 │
│ ◐ researcher  browse_web  18s │  tokens 184k ▓▓▓▓▓▓▓▓░░░░░░░░░░  cache hit 61%   │
│ ◐ coder       write_file   4s │  opus  $0.31 ████████████                       │
│ ⏰ inbox-triage   in 38m      │  haiku $0.08 ███                                 │
│                         [a]   │  calls 47 · tools 31 · web 6            [r] more │
├──────────────────────────────┼─────────────────────────────────────────────────┤
│ WORK QUEUE             [t]    │ RECENT  (audit tail)                  [l] ledger │
│ ▶ research "AI funding"   42s │ 14:22:01 tool.completed   read_file ok          │
│ ▶ summarize inbox          8s │ 14:21:54 subagent.started researcher            │
│ ⧖ build slides (queued)       │ 14:21:50 permission.requested browse_web   ⚠    │
│ ⛔ deploy (awaiting approval) │ 14:21:33 memory.compaction  skill→research      │
│ ✗ fetch prices (failed)  [x]  │ 14:21:20 tool.completed   google_list_emails ok │
└──────────────────────────────┴─────────────────────────────────────────────────┘
 :cmd  ?help   ↵ on a panel drills in    gc chat · ga agents · gt tasks · gp approvals
```

**Interactions.** `↵`/`Tab` cycles panel focus; `↵` on a focused panel jumps to its
full view. Panel hotkeys in brackets (`[p] [a] [t] [r] [l]`) jump directly. The *Needs
You* panel supports inline `y/n` for the top approval without leaving the dashboard.
`x` on a failed work item opens its failure in Tasks.

**Layout responsiveness.** 6 panels at ≥120 cols (2×3); collapses to a single column
stack at <100 cols, ordered by priority: **Needs You → Activity → Pack → Queue →
Spend → Recent** (approvals always first).

**Data source.** Activity `activity()`; Needs You `PendingApprovalRegistry.list_pending`
/ `GET /approvals`; Pack `subagent_reports()` + `active_jobs()` filtered to
`job_type=="delegate"` + `GET /schedules`; Spend `usage.updated` + per-model split from
`CostTracker`; Queue `active_jobs()` + `failed_jobs()` + suspended workflows; Recent
`read_events_since(seq)` tail.

---

### 4.3 Agents (`ga`) — "The Pack"

**Purpose.** Fleet visibility. Today the "fleet" is (a) **ephemeral sub-agents** spawned
within a turn (`delegate_task`, ≤3 parallel), (b) their **recent history**
(`delegation_log`), and (c) **scheduled agents** (recurring schedules). The view treats
all three as one roster and is built to scale to persistent/remote agents later.

```
┌ hachi ▸ guided ──────────────────── agents ───────────── ◐ working · 3 active ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku               │
├────────────────────────────────────────────────────────┬───────────────────────┤
│  STATUS  ROLE         TASK                  ITER  TIME TOK│ TRACE ▸ researcher    │
│ ▸◐ run   researcher   AI funding rounds      5/10  18s 22k│ task: gather funding  │
│  ◐ run   coder        write one-pager.md     2/10   4s  6k│ rounds last 30 days   │
│  ⏰ sched inbox-triage every day 08:00         —    —   — │ leased: reports/*.md  │
│  ✓ done  emailer      send digest            3     12s  9k│ ─────────────────────│
│  ✗ fail  analyst      parse CSV (timeout)   10    120s 41k│ ◐ browse_web          │
│  ✓ done  researcher   competitor scan        6     31s 18k│   news.ycombinator ⚠  │
│                                                          │ ✓ google_search_drive │
│  [/] filter: all · running · done · failed · scheduled   │   "AI funding" → 4    │
│                                                          │ ✓ read_file notes.md  │
│                                                          │ ◷ thinking… (iter 5)  │
│                                                          ├───────────────────────┤
│                                                          │ parent  turn 3 (chat) │
│                                                          │ model   haiku-4.5     │
│                                                          │ cost    ~$0.04        │
│  [↵] trace  [w] watch live  [x] cancel  [r] retry        │ status  RUNNING       │
│  [d] delegate new   [s] new schedule   [/] filter        │ [w] follow  [y] copy  │
└──────────────────────────────────────────────────────────┴───────────────────────┘
 :cmd  ?help   ga agents · gt tasks · gl ledger
```

**Interactions.** `j/k` select; `↵`/`i` open **Trace inspector** (the agent's tool
calls + reasoning, streamed); `w` follow-live (auto-scroll the trace as it runs);
`x` cancel a running delegation; `r` retry a failed one (re-delegate same role+task);
`d` open the **delegate dialog** (role picker: analyst·coder·devops·emailer·researcher,
task field, optional write-targets); `s` create a scheduled agent. `/` filters by
status/role.

**Honest scaling note (engineers).** A *live* delegation today has no first-class
"agent" record — it surfaces via `subagent.started/completed` + `active_jobs()` of
`job_type=="delegate"`. To make this view solid, add a thin **AgentRegistry** read
model keyed by a run-id that holds `{role, task, status, iter, started_at, parent_turn,
model, leased_targets, token_estimate}` while running, then flush to `delegation_log`
on completion. The table binds to that; the inspector tails the child loop's events.

**Data source.** live = proposed `AgentRegistry` + `subagent.started/completed`,
`active_jobs()`; history = `query_subagent_reports()` / `GET /subagents/reports` +
`delegation_log` collection; scheduled = `GET /schedules`; trace = child
`ExecutionLoop` events (`thinking.step`, `tool.call.*`).

---

### 4.4 Tasks (`gt`) — Work Queue

**Purpose.** One queue view over three backend concepts that the user shouldn't have to
distinguish: **jobs** (`jobs/queue.py`), **schedules** (`jobs/scheduler.py`), and
**suspended workflows** (`core_suspend_workflow`). Tabs filter by lifecycle.

```
┌ hachi ▸ guided ───────────────────── tasks ──── 2 running · 1 blocked · 1 failed ┐
│ ▶2 running ⏸1 paused ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku       │
├──────────────────────────────────────────────────────────┬─────────────────────┤
│ [ active ] scheduled  completed  failed  paused  blocked   │ DETAIL ▸ deploy app │
│  STATE  KIND      LABEL                  OWNER     AGE  RTRY│ kind   workflow      │
│ ▸▶ run  delegate  research "AI funding"  turn 3    42s   — │ state  ⛔ suspended   │
│  ▶ run  job       summarize inbox        turn 3     8s   — │ since  0:31           │
│  ⧖ wait job       build slides           turn 3     —    — │ waiting on:          │
│  ⛔ susp workflow  deploy app             turn 2   0:31  — │  human approval       │
│  ⏰ sched schedule inbox-triage 08:00      system  —    — │  (deploy to prod)     │
│  ✗ fail job       fetch prices           turn 1   2m    3/3│ ─────────────────── │
│                                                            │ resume when approved │
│                                                            │ checkpoint saved ✓   │
│  bulk: [space] select  [P] pause  [X] cancel  [R] retry    │ ─────────────────── │
│                                                            │ [a] approve & resume │
│  [↵] detail  [P]ause  [Re]sume  [X] cancel  [D]uplicate    │ [X] cancel workflow  │
│  [R] retry   [/] filter   [f] follow                       │ [y] copy job_id      │
└──────────────────────────────────────────────────────────┴─────────────────────┘
 :cmd  ?help   gt tasks · ga agents · gp approvals · gl ledger
```

**Interactions.** Tab bar switches lifecycle filter (active/scheduled/completed/failed/
paused/blocked). Row actions (footer): `↵` detail, `P` pause (schedule → `enabled=False`),
`Re` resume, `X` cancel, `D` duplicate (re-enqueue same payload), `R` retry (failed job),
`f` follow. `space` multi-selects for bulk pause/cancel/retry. **Blocked** tab is special:
these are suspended workflows; their detail shows *what they're waiting on* and offers
`a` (approve & resume) when the blocker is an approval.

**Data source.** active/queued/failed = `active_jobs()`, `failed_jobs()`, job states
`PENDING/RUNNING/COMPLETED/FAILED/CANCELLED`; scheduled = `GET /schedules` (kinds
`ONCE/INTERVAL/CRON`, `next_run`, `run_count`); paused = schedules `enabled=False`;
blocked = suspended-workflow registry. Controls map to `DELETE /schedules/{id}`,
`PUT /schedules/{id}/enabled`, and job enqueue/cancel.

**Edge.** A failed job at max retries (`3/3`) shows the error inline and a one-key
`R` that re-enqueues a fresh attempt; `↵` opens the failure in Audit at that sequence.

---

### 4.5 Approvals (`gp`) — the trust crux

**Purpose.** Where human authority is exercised. Hachi has two real approval delivery
paths and this view unifies them:
- **Foreground modal** (`HandlerApprover`): for the session you're actively in — a
  blocking modal interrupts you. Right when you're focused on one task.
- **Background inbox** (`RegistryApprover` + `PendingApprovalRegistry`): for everything
  else — queued, non-blocking, triaged here. Right when you're supervising many agents.

**The modal** (floats over any screen when the *foreground* session needs you):

```
        ┌─ ⛓ approval needed ───────────────────────────────────────┐
        │ researcher wants to   browse the web                        │
        │                                                             │
        │    ▸ https://news.ycombinator.com                           │
        │    why:    gather sources for the "AI funding" one-pager    │
        │    risk:   outbound network · untrusted content returned    │
        │    policy: guided tier · web allowed · this host is new     │
        │                                                             │
        │    rationale (optional) ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁    │
        │                                                             │
        │    [n] deny     [y] allow once     [A] always allow host    │
        │                                  ⎋ deny · you hold the leash │
        └─────────────────────────────────────────────────────────────┘
```

**The inbox** (when supervising; `gp`):

```
┌ hachi ▸ guided ─────────────── approvals ──── ⚠ 3 pending · oldest 0:42 ago ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠3 approval  $0.42/$5.00  haiku            │
├─────────────────────────────────────────────────────┬──────────────────────┤
│  AGE   AGENT        ACTION             TARGET     RISK│ DETAIL ▸ browse_web  │
│ ▸0:42  researcher   browse_web         news.yc..  net │ researcher wants to  │
│  0:31  coder        write_file         src/app.py fs  │ browse the web       │
│  0:08  emailer      google_send_email  3 recip.   send│  ▸ news.ycombinator  │
│                                                       │  why: gather sources │
│                                                       │  for AI funding report│
│  bulk: [space] select  [Y] approve all  [N] deny all  │  risk: net+untrusted │
│                                                       │  policy: host is new │
│  countdown: ⧖ approvals expire in 180s (auto-deny)    │ ──────────────────── │
│                                                       │ [y] allow once       │
│                                                       │ [A] always this host │
│                                                       │ [n] deny + rationale │
└─────────────────────────────────────────────────────┴──────────────────────┘
 ⚠ google_send_email currently runs WITHOUT a gate — [G] add it to the policy
```

**Interactions.** `j/k` select; `y` allow-once, `A` always-allow (adds a durable rule:
host for network, path for fs, "remember" → session via the existing `approve` action),
`n` deny (focuses the rationale field), `↵` expand detail. `space`+`Y/N` for bulk.
A **countdown** shows the real 180s `RegistryApprover` timeout so the auto-deny is never
a surprise (today it is — UAT flagged it).

**Honest grounding (engineers).** Two real gaps this view must address, not hide:
1. **Ungated integration tools** — `google_send_email`, `google_delete_event`,
   `google_share_file`, `google_trash_file`, `google_delete_task`,
   `google_delete_contact` bypass the gate entirely. The inbox footer **flags** any
   such tool and offers `[G]` to add an approval requirement (writes an approval rule).
   The real fix is backend (route these through `require_action`), but the UI makes the
   risk *visible* meanwhile — which is the whole point of Hachi.
2. **Gateway path can't escalate** — non-TUI sessions get a bare gate and auto-deny.
   When the TUI is running it *is* the approver for those sessions via the inbox, so
   wiring `RegistryApprover` to this inbox closes the gap for TUI-supervised runs.

**Data source.** `GET /approvals` / `PendingApprovalRegistry.list_pending()`;
resolve via `POST /approvals/{request_id}` (`approve`/`deny`/`allow_once` + rationale);
history via `permission_audit()` / `GET /permissions/audit`. Events
`permission.requested` (raises the toast + increments the bar) and `permission.decided`.

---

### 4.6 Governance (`gg`) — policy as code

**Purpose.** Edit the rules that constrain the agent: permissions, budgets, approval
rules, safety. The product's headline feature. It is a **structured editor over
`device-permissions.og`** plus budget caps — *policies are enforced in code, not
prompts*, and this screen is where that code is authored without hand-editing `.og`.

```
┌ hachi ▸ guided ───────────────── governance ────────────────── you hold the leash ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                  │
├──────────────────┬─────────────────────────────────────────────────────────────────┤
│ ▸ Permissions    │ PERMISSIONS — tier: guided           [e] edit   [T] change tier   │
│   Budgets        │                                                                   │
│   Approval Rules │ filesystem    write ✓   delete ✗    max 50 MB                     │
│   Safety         │   allowed    ~/Desktop   ~/Downloads   ~/Documents       [+ add]  │
│   Integrations   │   blocked    ~/.ssh   ~/.hachi   ~/Library            (always on)  │
│                  │ terminal      enabled ✓   timeout 120s                             │
│                  │   allowed    git  npm  pip  ls  cd  cat  …                [+ add]  │
│                  │   blocked    rm -rf   shutdown   format   reg delete   (always on) │
│                  │ mcp fs        enabled ✓                                            │
│                  │ ───────────────────────────────────────────────────────────────  │
│                  │ ⚠ 6 integration tools run WITHOUT an approval gate:                │
│                  │   google_send_email · google_delete_event · google_share_file ·   │
│                  │   google_trash_file · google_delete_task · google_delete_contact  │
│                  │   [G] require approval for all of these   (recommended)           │
│                  │ ───────────────────────────────────────────────────────────────  │
│                  │ ⓘ edits write ~/.hachi/device-permissions.og                       │
│                  │ ⚠ the gate is immutable mid-session — changes apply next launch    │
│                  │   [H] hot-reload now (rebuild gate; see backend note)             │
└──────────────────┴─────────────────────────────────────────────────────────────────┘
 :cmd  ?help   [e]dit  [T]ier  [G] gate integrations  [H] hot-reload   gg · gp · gl
```

**Sub-pages (left rail).**
- **Permissions** — the above; filesystem roots, terminal allow/block, mcp toggle.
- **Budgets** — `max_cost_usd` / `max_tokens` (per session), `max_cost_per_turn` /
  `max_tokens_per_turn`, and proposed **daily/monthly** caps. Shows current spend vs
  each cap as a bar; editing writes config; warns that *no dedicated `budget.exceeded`
  event exists yet* (recommend adding one — see §13).
- **Approval Rules** — declarative "ask before…" rules: ask before spending > $X,
  before delete, before external send, before a new host. Maps onto `require_action`
  call sites and the always-allow rules accreted from the inbox.
- **Safety** — read-mostly status of the hard guards already in code: SSRF/net_guard
  (blocked private ranges + metadata IPs), secret_scanner (redaction on/off via
  `HACHI_ALLOW_OUTBOUND_SECRETS`), dangerous-command list, interpreter blocking in
  guided/sandbox, UNC rejection. Each is a row with on/off + "why".
- **Integrations** — per-integration scope grants (Google scopes, Slack, etc.).

**Interactions.** `e` edit the focused field (inline, with validation — e.g. a path
must resolve, a command can't collide with the always-block list); `T` tier switcher
(with a clear "unrestricted = full filesystem + terminal" warning); `+` add a
path/command; `G` bulk-gate the ungated tools; `H` hot-reload (requires the backend
change below).

**Honest grounding (engineers).** `PermissionGate` is intentionally immutable after
boot (fail-safe). For a usable "tighten the leash *now*" experience, add a guarded
`rebuild_gate(new_og)` that swaps the gate atomically between turns (never mid-tool).
Until then, the screen is honest: it says "applies next launch" and offers a restart.
Tightening (emergency revoke) should be prioritized over loosening.

**Data source.** `GET /config`; writes `PUT /config/permissions`, `PUT /config/memory`,
and `device-permissions.og` via the workspace writer; budgets map to `ExecutionLoop`
caps; safety status from `net_guard` / `secret_scanner` / `permissions.py` constants.

---

### 4.7 Memory (`gm`) — 3-layer explorer

**Purpose.** Inspect, search, edit, and delete what Hachi remembers — across all three
layers — and **audit what was blocked** (the quarantine). Trust requires that memory is
not a black box.

```
┌ hachi ▸ guided ──────────────────── memory ──────────────────────────────────────┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                  │
├──────────────────┬─────────────────────────────────────────────────────────────────┤
│ LAYERS           │ search ▸ "funding"                              42 hits   [/]    │
│ ▸ Active (ctx)   │ ─────────────────────────────────────────────────────────────── │
│   Sessions       │  SCORE COLLECTION    FACT                              CATEGORY  │
│   Vault          │ ▸ 0.91 core_memory   "Acme raised $40M Series B…"   workspace    │
│     core (218)   │   0.88 core_memory   "Funding tracked in notes/…"   workspace    │
│     user (12/25) │   0.74 user_profile  "User follows AI funding news" preference   │
│     agent (8/25) │   0.39 delegation    researcher · competitor scan   delegation   │
│     delegation   │ ─────────────────────────────────────────────────────────────── │
│   ⚠ Quarantine(3)│ INSPECT ▸ core_memory · id 7f3a…                                 │
│                  │   "Acme raised $40M Series B led by Sequoia (2026-05)."          │
│                  │   category workspace_state · trust accepted · 2026-05-30          │
│                  │   [e] edit   [x] delete   [y] copy   [→] show related (graph)     │
│                  │ ─────────────────────────────────────────────────────────────── │
│                  │ ⚠ QUARANTINE: 3 writes blocked by MemoryGuard — [↵] review       │
└──────────────────┴─────────────────────────────────────────────────────────────────┘
 :cmd  ?help   [/] search  [e]dit  [x] delete  [a] add fact   gm · gk · gl
```

**Layers (left rail).**
- **Active (ctx)** — the live in-context window: message count vs `max_active_messages`,
  the last compaction events (skill-switch / sliding-window / stale-tool-clear), and a
  `compact now` action. Read-mostly; this is "what's in its head right now."
- **Sessions** — SQLite transcript search (`search_sessions`), recent sessions list,
  open a transcript, resume (`hachi -r`), delete a session.
- **Vault** — the five ChromaDB collections with counts and caps:
  `core_memory` (unbounded), `user_profile` (n/25), `agent_profile` (n/25),
  `delegation_log`, and **`memory_quarantine`** (blocked writes — a first-class trust
  feature, surfaced loudly).

**Interactions.** `/` semantic search (scopes to the focused collection or all); `↵`/`i`
inspect a fact in the Inspector; `e` edit (re-upsert), `x` delete, `a` add a fact (pick
collection + category), `y` copy. `→` shows graph-related facts (RRF/FTS5 edges).
Quarantine rows show the threat reason; `release`/`purge` actions for review.

**Data source.** Active = `MemoryManager` state + `memory.compaction` events;
Sessions = `SessionStore.search_sessions` / `get_session_messages`; Vault =
`semantic_search`, `search_user_profile`, `search_delegations`, `get_*_snapshot`,
`get_*_stats`, `get_quarantine_entries`; edits = `upsert_fact`/`delete_fact` family
(also the `core_save_memory`/`core_delete_memory` tool paths).

---

### 4.8 Skills (`gk`) — capabilities + OG inspector

**Purpose.** Manage what Hachi *can do*: installed `.og` skills, their usage, their
required scopes, the **3-pass (search→peek→load) token-efficiency inspector** (the
moat made visible), authoring, and a marketplace placeholder.

```
┌ hachi ▸ guided ───────────────────── skills ─────────────────── 41 installed ───┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                 │
├──────────────────────────────────┬───────────────────────────────────────────────┤
│  USE  SKILL               STALE  │ OG INSPECTOR ▸ deploy-to-prod                   │
│ ▸ 142 research-protocol          │ Pass 1 · index    keywords: deploy, prod, ci    │
│   118 inbox-triage               │   routing hit, ~28 tok                          │
│    97 deploy-to-prod             │ Pass 2 · dense    "Zero-downtime deploy via…"   │
│    61 slides-from-outline   30d⚠ │   warning: requires approval · ~30 tok          │
│    44 competitor-scan            │   blocks: full(120) steps(85) code(200) table   │
│     3 csv-cleanup           90d⚠ │ Pass 3 · load     [↵ load full]  est 405 tok    │
│     0 legacy-export      never⚠  │ ─────────────────────────────────────────────── │
│                                  │ requires: ssh-helper → secrets-vault            │
│  [/] filter   sort: use · stale  │ scopes:  terminal(git,ssh) · network(deploy host)│
│                                  │ source:  ~/.hachi/skills/deploy-to-prod.og      │
│  tabs: [installed] marketplace   │ used 97× · last 2026-06-14                      │
│  authored                        │ [↵] load  [E] edit  [v] versions  [x] uninstall │
└──────────────────────────────────┴───────────────────────────────────────────────┘
 :cmd  ?help   [/] filter  [E]dit  [n] new skill  [x] uninstall   gk · gm · gn
```

**Interactions.** `j/k` select; `↵` runs the **3-pass inspector** showing exactly what
each pass costs in tokens (the differentiator, made legible); `E` edit (opens authoring,
which is today's `AuthoringScreen` for `.og`); `n` new skill (`save_skill`, hot-loaded
with lint feedback); `v` version history (changelog/delta); `x` uninstall; `/` filter.
Stale badges (`30d/90d/never`) drive a "prune unused skills" workflow. Tabs:
**installed**, **marketplace** (future registry — same card shape, adds Install +
scope-grant), **authored** (learned/ skills).

**Data source.** list/usage = `og_engine` `get_skill_inventory()` / `skill_usage.json`
/ `get_stale_skills()`; 3-pass = `search()`/`peek()`/`resolve_node()` with token
counts; deps = `get_dependency_chain()`; authoring = `upsert_skill()` + lint;
scopes = skill `::meta tools` + declared scopes.

---

### 4.9 Audit (`gl`) — immutable ledger / timeline

**Purpose.** The who/what/when/why. A single chronological, **append-only**, filterable
stream of every runtime event, with full payloads on drill-down. This is the logs +
timeline + audit trio merged; it is where you investigate and where compliance reads.

```
┌ hachi ▸ guided ───────────────────── audit ───────── following ⏵ · 1,284 events ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                 │
├────────────────────────────────────────────────────────┬─────────────────────────┤
│  SEQ   TIME       EVENT                  OWNER     DETAIL │ EVENT ▸ #1281            │
│ 1284 14:22:01 tool.call.completed   researcher read_file │ permission.requested    │
│ 1283 14:21:58 thinking.step         researcher iter 5    │ seq      1281            │
│ 1282 14:21:55 tool.call.started     researcher browse_web│ time     14:21:50.114Z  │
│▸1281 14:21:50 permission.requested  researcher browse ⚠  │ owner    researcher      │
│ 1280 14:21:48 subagent.started      turn 3     researcher│ session  0xA31F · turn 3 │
│ 1279 14:21:33 memory.compaction     system    skill→res  │ ─────────────────────── │
│ 1278 14:21:20 tool.call.completed   turn 3    gmail ok   │ payload                 │
│ 1277 14:21:02 usage.updated         turn 3    +4.1k tok  │  operation network      │
│                                                          │  tool      browse_web   │
│  filter ▸ [domain: all] [owner: all] [⚠ only] [/text]    │  target    news.yc…     │
│  range  ▸ session · today · all                          │ ─────────────────────── │
│                                                          │ [→] jump to in chat     │
│  [f] follow  [/] filter  [w] watch ⚠  [E] export         │ [y] copy json           │
└──────────────────────────────────────────────────────────┴─────────────────────────┘
 :cmd  ?help   [f] follow  [/] filter  [E] export   gl · gp · gt
```

**Interactions.** `f` toggle follow (live tail, k9s/`tail -f` style); `/` text filter;
domain/owner filter chips (`session · tool · subagent · permission · job · memory ·
mcp · usage`); `⚠ only` shows just attention events; `↵`/`i` expand full JSON payload in
the Inspector; `→` jump to that event's spot in the originating chat; `E` export
(JSONL/markdown) for compliance; `y` copy. Sequence numbers are the stable cursor.

**Data source.** `read_events_since(after, limit)` / `GET /runtime/events` /
`GET /sessions/{id}/events` + SSE `…/stream`; `permission_audit()`; immutable —
events are append-only with monotonic `sequence`.

---

### 4.10 Resources (`gr`) — meters

**Purpose.** btop for the agent. Where the money and compute go, attributable.

```
┌ hachi ▸ guided ──────────────────── resources ──────────────── session 0xA31F ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku               │
├──────────────────────────────────────────┬─────────────────────────────────────┤
│ TOKENS (session)                          │ COST                     $0.42 / $5 │
│  input    142k ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░       │  by model                           │
│  output    18k ▓▓                         │   opus   $0.31 ████████████  74%    │
│  cache rd 142k ▓▓▓▓▓▓▓▓▓▓▓▓▓  (61% hit)   │   haiku  $0.08 ███           19%    │
│  cache wr   9k ▓                          │   gemini $0.03 █              7%    │
│  total    311k                            │  calls 47 · avg $0.009/call         │
├──────────────────────────────────────────┼─────────────────────────────────────┤
│ THROUGHPUT                                │ FOOTPRINT (local-first)             │
│  active agents   2      queue depth   4   │  vault   core 218 · user 12 · agent 8│
│  running tasks   2      failed (24h)  1   │  sessions.db   1,284 msgs · 4.2 MB   │
│  tools (turn)    5      web calls     6   │  jobs.db   12 pending · 0 stuck      │
│  iters (turn)    5/10                      │  runs LOCAL ✓   remote calls: LLM only│
└──────────────────────────────────────────┴─────────────────────────────────────┘
 :cmd  ?help   [r] refresh  scope: [session] today · all     gr · gl · gt
```

**Interactions.** Scope toggle (session / today / all); `r` refresh; `↵` on a model row
filters Audit to that model's calls. The **Footprint** panel makes the *local-first*
promise legible: what's on disk locally vs what leaves the machine ("remote calls: LLM
only") — directly answering the brief's "what runs locally vs remotely."

**Data source.** `CostSnapshot` (`input/output/cache_read/cache_creation/total_tokens`,
`estimated_cost_usd`, `call_count`) via `usage.updated` / `GET /sessions/{id}/usage`;
per-model split from `CostTracker`; throughput from `active_jobs()`/`tool_calls()`/
`failed_jobs()`/`pending_job_count`; footprint from vault `count()`s + db file sizes.

---

### 4.11 Connections (`gn`) — MCP + integrations

**Purpose.** External capability surface: MCP servers and their tools, integration
accounts (Google, Slack, …), health, and per-connection scopes.

```
┌ hachi ▸ guided ─────────────────── connections ──────────── 3 servers · 2 accts ┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                │
├──────────────────────────────────┬───────────────────────────────────────────────┤
│  HEALTH  CONNECTION       TOOLS   │ DETAIL ▸ google (workspace)                    │
│ ▸ ● ok   google           44      │ status   connected · token valid 2026-07       │
│   ● ok   filesystem-mcp     6      │ scopes   gmail.send ⚠ · calendar · drive       │
│   ◐ slow weather-mcp        2      │ tools    gmail(10) calendar(10) drive(7) …     │
│   ✗ down notion-mcp         0  [r] │ ⚠ gmail.send + drive.share are UNGATED         │
│                                   │   [G] require approval (governance)            │
│  [+ add server]  [/] filter       │ ─────────────────────────────────────────────│
│                                   │ [t] test  [d] disconnect  [s] re-auth          │
└──────────────────────────────────┴───────────────────────────────────────────────┘
 :cmd  ?help   [+] add  [t] test  [r] retry  [d] disconnect    gn · gk · gg
```

**Interactions.** `+` add MCP server (`add_mcp_server`, with command validation + secret
guard); `t` test/ping; `r` retry a down server; `d` disconnect; `s` re-auth an account;
`/` filter. Ungated destructive tools are flagged here too, with a jump to Governance.

**Data source.** `GET /runtime/mcp/inventory`; `add_mcp_server`/`remove_mcp_server`/
`list_mcp_servers`; `mcp.server.starting/ready/failed/shutdown` events; integration
account status.

---

### 4.12 Settings (`gs`) — config + setup

**Purpose.** Provider/model, memory behavior, general prefs, and the onboarding wizard.
Reuses today's `SettingsScreen` + `SetupScreen` flow.

```
┌ hachi ▸ guided ───────────────────── settings ──────────────────────────────────┐
│ ▶2 running ⧖4 queued ⛔1 blocked ⚠1 approval  $0.42/$5.00  haiku                 │
├──────────────────┬─────────────────────────────────────────────────────────────────┤
│ ▸ Provider       │ PROVIDER & MODEL                                  [e] edit        │
│   Memory         │  provider  anthropic            [change]                          │
│   Sub-agents     │  model     claude-haiku-4-5     [m] switch   [✓ validate]         │
│   Appearance     │  allowed   haiku · sonnet · opus           (guardrail)            │
│   Setup wizard   │  fallback  gemini (free tier)                                     │
│                  │ ─────────────────────────────────────────────────────────────── │
│                  │  providers: anthropic · openai-compatible · openrouter · groq ·   │
│                  │             together · deepseek · gemini · ollama                 │
│                  │ ─────────────────────────────────────────────────────────────── │
│                  │ SUB-AGENTS                                                        │
│                  │  default model   claude-haiku-4-5  (cost-aware)                   │
│                  │  per-role model  researcher→haiku · coder→sonnet   [e]            │
└──────────────────┴─────────────────────────────────────────────────────────────────┘
 :cmd  ?help   [e]dit  [m] switch model  [✓] validate    gs · gg · gn
```

**Sub-pages.** Provider (switch/validate, the 8 real providers), Memory (session-history
+ semantic toggles), **Sub-agents** (default + per-role model — exposes the pending
per-sub-agent model selection as a first-class control), Appearance (density, glyphs,
follow-mode defaults — *not* brand), Setup wizard (the existing tiered onboarding).

**Data source.** `GET /config`, `PUT /config/provider`, `POST /config/provider/validate`,
`PUT /config/memory`, `GET /models`; setup via `GET /setup`, `POST /setup/apply`.

---

## 5. Overlays (the floating layer)

### 5.1 Command Palette (`⌃K` / `:`)
Fuzzy launcher and the navigation spine. Sections: **Go to** (the 12 views), **Do**
(context actions — delegate, schedule, switch model, compact memory, export audit,
add permission…), **Open** (recent sessions, skills, memory facts), **Settings**.
Type-ahead; `↑/↓`+`↵`; shows the keybind next to each item (teaches shortcuts).

```
        ┌─ ⌃K ─────────────────────────────────────────────┐
        │ > appro|                                          │
        │ ─────────────────────────────────────────────────│
        │ GO TO    Approvals                            gp  │
        │ DO       Approve all pending                      │
        │ DO       Require approval for ungated tools    G  │
        │ OPEN     Audit: permission events             gl  │
        └───────────────────────────────────────────────────┘
```

### 5.2 Approval modal — §4.5. The only *blocking* overlay, and only for the
foreground session. Everything else is non-blocking.

### 5.3 Notification toasts (bottom-right, transient, stacking)
Terminal-native, non-stealing. Fire on: approval requested, budget threshold crossed,
policy/safety block, task completed/failed, agent failed, skill installed, memory
quarantine. Each toast: glyph + one line + a hotkey to act (`[a] review`, `[t] tasks`).
Auto-dismiss after N seconds; `⌃W`/history keeps the last ones (reuses today's
`WarningsModal` as the history view). Optional terminal bell on `⚠`.

```
                                            ┌ ⚠ approval needed ───────────┐
                                            │ researcher → browse_web  [a]  │
                                            └───────────────────────────────┘
                                            ┌ ✗ task failed ────────────────┐
                                            │ fetch prices (3/3)       [t]  │
                                            └───────────────────────────────┘
```

### 5.4 Help cheat-sheet (`?`)
Full keymap, grouped by the four view-groups + global + context. Reuses `HelpModal`.
Lists the `g<letter>` mnemonics, palette, and the current screen's context keys.

### 5.5 Quick session switcher (`⌃J`)
A small overlay listing active + recent sessions to jump between conversations (multi-
session supervision), each with its state glyph and spend.

---

## 6. User flows (keystroke-level)

**A. Create a task (delegate + schedule).**
1. Chat: type *"every morning at 8, triage my inbox and DM me the urgent ones."*
2. Hachi proposes a plan in the PLAN panel + a **schedule preview** card (CRON `0 8 * * *`,
   deliver→chat). Inline `[↵ confirm]`.
3. On confirm → appears in **Tasks ▸ scheduled** and **Agents ▸ scheduled**; Trust Bar
   `⏰` reflects it. *Or* explicitly: `ga` → `s` (new schedule) → fill the form.

**B. Manage permissions.**
1. `gg` → Permissions. `T` → choose `guided`. `e` on *allowed paths* → `+` add
   `~/projects`. Validation confirms it resolves and isn't in the always-block set.
2. Banner: "applies next launch" → `H` hot-reload (if backend supports) or restart.
3. `G` to gate the 6 ungated integration tools in one action.

**C. Review an agent's actions.**
1. `ga` → `j/k` to the agent → `↵` trace. `w` to follow live as tools execute.
2. See `browse_web` paused on `⚠` → `a` jumps to the approval → decide → trace resumes.

**D. Approve a request.**
1. Toast `⚠ researcher → browse_web [a]` → `a` (or `gp`).
2. Read why/risk/policy → `y` allow once (or `A` always-allow host, or `n` deny + reason).
3. Trust Bar `⚠` decrements; Audit logs `permission.decided`.

**E. Install a skill.**
1. `gk` → tab **marketplace** → `/` find → `↵` preview (3-pass cost + required scopes).
2. `Install` → **scope grant** dialog ("this skill wants terminal:git, network:deploy
   host") → grant → it appears in **installed**, hot-loaded.

**F. Search memory.**
1. `gm` → `/` *"funding"* → ranked hits across collections.
2. `↵` inspect a fact → `e` edit / `x` delete. `→` to walk related facts.
3. Check **Quarantine** for anything MemoryGuard blocked.

**G. Monitor execution.**
1. `⌃O` → Dashboard. Watch Activity + Pack + Queue live.
2. `gl` → `f` follow the audit tail; `⚠ only` to watch just attention events.

**H. Investigate a failure.**
1. Dashboard *Work Queue* shows `✗ fetch prices [x]` → `x` opens **Tasks ▸ failed**.
2. `↵` detail → error + attempt `3/3`. `↵` on the error → **Audit** at that sequence
   for the full trace. Fix cause (e.g., `gg` add the host) → `R` retry.

---

## 7. Information hierarchy

| Tier | What | Always on screen? |
|------|------|-------------------|
| 0 | **Trust Bar** (state + 8 answers) | yes, never scrolls |
| 1 | **Active view** (chat or a data view) | yes |
| 1 | **Approval signal** (`⚠` + toast + modal for foreground) | yes when pending |
| 2 | **Footer** context keys + breadcrumb | yes |
| 3 | **Inspector** drill-down of selection | on demand (`↵`/`i`), auto-hides narrow |
| 3 | **Expandable detail** (card bodies, event JSON, traces) | collapsed by default |
| 4 | **Overlays** (palette, help, toasts history) | summoned |

First glance = Trust Bar (trust) + the view's headline counts. Sustained attention =
the main view. Deliberate drill = Inspector / expanded cards. Rare = overlays.

---

## 8. Terminal UX pattern library

| Pattern | Binding | Behavior |
|---------|---------|----------|
| Command palette | `⌃K` / `:` | fuzzy go-to / do / open |
| Go-to view | `g`+letter | jump to any of 12 views |
| Altitude toggle | `⌃O` | Focus ↔ Cockpit |
| Filter-in-place | `/` | live-filter the focused list |
| Global search | palette → Open | across sessions/memory/audit |
| Drill-down | `↵` / `i` | open Inspector for selection |
| Up / back | `⎋` | close inspector / up breadcrumb / blur input |
| Vim move | `j k g G ⌃d ⌃u` | list navigation (operator focus) |
| Follow / tail | `f` / `w` | live auto-scroll (audit, trace) |
| Multi-select | `space` | mark rows; then bulk action |
| Bulk action | `Shift`+key | apply to selection (`P/X/R`, `Y/N`) |
| Quick action | context letters | shown in footer per screen |
| Copy / yank | `y` | copy id / content / json |
| Interrupt | `⎋` (chat) / `⌃C` | stop turn / cancel in-flight |
| Refresh | `⌃R` | re-pull snapshot |
| Help | `?` | cheat-sheet |
| Session switch | `⌃J` | jump between conversations |

**Discoverability principles.** (1) The footer always shows the keys that work *here*.
(2) The palette lists every action with its shortcut, so you learn by using. (3) `?`
is a complete map. (4) Mnemonic (`g`+letter, action-initials) over positional. (5)
Nothing is *only* reachable by a hotkey — the palette reaches everything.

---

## 9. Master keybinding table

```
GLOBAL (any focus)
  ⌃K            command palette            ⌃O   altitude toggle (focus/cockpit)
  ⌃J            session switcher           ⌃R   refresh snapshot
  ⌃W            notifications history      ?    help / keymap
  ⌃C            interrupt / cancel         ⌃Q   quit

GO TO (operator focus, or after g)
  gc chat   gd dashboard   ga agents   gt tasks   gp approvals   gg governance
  gm memory gk skills      gl audit    gr resources  gn connections  gs settings

OPERATOR FOCUS (data views; no text input active)
  j/k ↑/↓   move          ⌃d/⌃u  half-page      g/G  top/bottom
  ↵ / i     inspect       ⎋      back/up        /    filter
  space     select        f      follow         y    copy
  (context letters per screen, e.g. P pause · X cancel · R retry · e edit · x delete)

CHAT FOCUS (composer active)
  ↵ send    ⇧↵ newline    ↑/↓ history    / slash commands    ⎋ interrupt turn
  ⌃Y copy last response   (chords + palette for navigation)
```

> Today's `Ctrl+1..9` / `F1..9` remain as deprecated aliases mapped to the new `g`
> targets for one release.

---

## 10. Component inventory (Textual mapping)

**Reuse (exists today):** `HachiGlyph` (→ Trust Bar state glyph), `StatusStrip`
(→ evolves into the two-line **TrustBar**), `SidebarPanel` (→ **Inspector** base),
`ToolCard` (inline cards), `PermissionApprovalModal` (approval modal), `HelpModal`,
`WarningsModal` (→ notifications history), `SnapshotScreen` (base for data views),
`SetupScreen`, `AuthoringScreen` (→ Skills edit), `Composer`/`SlashMenu`.

**New components:**
- `TrustBar` — the two-line band A; subscribes to `activity()` + counters.
- `CockpitScreen` / `DashboardGrid` — the altitude-2 host + portal panels.
- `DataTable+` views — `AgentTable`, `TaskTable`, `ApprovalInbox`, `AuditStream`
  (with follow), `ConnectionList`, `SkillList`, `MemoryResults` (all on a shared
  filterable/selectable table widget).
- `Inspector` — right pane; per-view content adapters (trace, task detail, fact,
  event JSON, approval detail).
- `CommandPalette` — fuzzy overlay (go/do/open).
- `ToastHost` — stacking transient notifications.
- `MeterPanel` — gauges for Resources.
- `OGInspector` — the 3-pass token-cost viewer (also satisfies the stubbed OG Explorer).
- `PlanPanel` — the chat-side todo/plan.
- `BudgetEditor` / `PermissionEditor` — structured `device-permissions.og` + caps editor.

**Layout primitive.** A `FrameShell` that lays out band A/B/C/D + overlay layer and
owns focus routing (chat-focus vs operator-focus keymaps) so every screen inherits the
navigation model uniformly.

---

## 11. Event / read-model → UI binding (implementation bridge)

| UI element | Read model / event | Route (gateway) |
|------------|--------------------|--------------------|
| Trust Bar state | `activity()` → `ActivitySnapshot` | (in-proc) |
| Trust Bar `⚠ approval` | `PendingApprovalRegistry.list_pending()` | `GET /approvals` |
| Trust Bar spend | `usage.updated` / `activity().estimated_cost_usd` | `GET /sessions/{id}/usage` |
| Chat stream | `text.stream.delta` | SSE `…/stream` |
| Tool/delegation cards | `tool.call.*`, `subagent.*` | `GET /sessions/{id}/events` |
| Dashboard Pack | `subagent_reports()` + `active_jobs(delegate)` | `GET /subagents/reports`, `/jobs/active` |
| Tasks | `active_jobs()`,`failed_jobs()`,schedules,suspended | `/jobs/*`, `/schedules` |
| Approvals | `permission.requested/decided`, registry | `GET/POST /approvals`, `/permissions/audit` |
| Governance | `PermissionGate`, config, og writer | `GET/PUT /config`, og file |
| Memory | vault search/stats/quarantine, `MemoryManager` | (in-proc + tools) |
| Skills | `og_engine` inventory/usage/3-pass | (in-proc + tools) |
| Audit | `read_events_since(seq)` (append-only) | `/runtime/events`, `/sessions/{id}/events` |
| Resources | `CostSnapshot`, read-model counters, db sizes | `/sessions/{id}/usage` |
| Connections | mcp inventory, `mcp.server.*` | `GET /runtime/mcp/inventory` |
| Settings | provider/model/memory config, models list | `/config*`, `/models`, `/setup*` |

All live updates ride the existing **monotonic `sequence` cursor** — every view that
tails events keeps a last-seen sequence and pulls `read_events_since`. No new transport
needed; the SSE `…/stream` already exists for the gateway/remote case.

---

## 12. Accessibility & responsiveness

- **No-color mode.** Every state carries a distinct glyph; color is redundant. Honors
  `NO_COLOR`. Borders/dividers use box-drawing that degrades to ASCII (`+ - |`).
- **Width breakpoints.** ≥120: full (main + inspector + 2-col dashboard). 90–119:
  inspector becomes a toggled sub-page; dashboard 1-col. <90: Trust Bar compresses
  counters into `⚠1 ▶2 ⧖4 $0.42`, sidebar hidden, single column (mirrors today's
  `NARROW_WIDTH=90` behavior).
- **Height.** Below ~24 rows, the Trust Bar drops to one line and the footer to keys-only.
- **Screen-reader / plain output.** A `--plain` event log and `hachi audit --follow`
  CLI mirror the Audit view for non-TUI/assistive consumption. All data views back onto
  the gateway JSON, so nothing is TUI-only.
- **Motion.** Animated glyphs and spinners are decorative; a "reduce motion" pref swaps
  them for static state glyphs.

---

## 13. Future-proofing

The architecture is deliberately built so these are additive, not rewrites:

- **Voice agents.** Add a `🎙` indicator to the Trust Bar (listening/speaking), a
  push-to-talk binding, and a "voice" surface that reuses the existing `transcribe_audio`
  / `speak_text` tools and the same event stream. Transcripts flow into the normal chat
  transcript; nothing else changes.
- **Mobile companion.** Every view already reads the gateway's REST/SSE. A mobile app is
  a second *surface* over the same read models — sessions are already `surface`-tagged at
  creation. Approvals especially map to push notifications → the same `POST /approvals/{id}`.
- **Remote agents.** Sessions carry `client_id`/`surface`. Add a **location column**
  (local/remote/host) to Agents and a Trust Bar `local·remote` split so the local-first
  promise stays legible when some agents run elsewhere. Channels inbound webhooks already
  model remote-triggered sessions.
- **Agent & skill marketplace.** Skills already has a marketplace tab shape; agent
  *roles* (`brain-<role>.og`) use the same install + scope-grant pattern. A registry
  endpoint slots behind the existing card UI.
- **Team collaboration.** Audit and sessions are multi-client already. Add an **actor/
  owner** column (who triggered) — the "owner" field is in every row by design — and the
  same screens scale to "whose agent did what."
- **Enterprise governance.** `device-permissions.og` *is* policy-as-code; org policy is
  the same model at a higher scope. Audit is append-only with a stable cursor → compliant
  export (`E` in Audit). Budgets become org budgets. No new paradigm, just scope.

---

## 14. Honest grounding — recommended backend changes

The TUI surfaces trust; some trust guarantees need small backend additions. These are
called out so the spec isn't selling vapor. (They align with the project's "make the
claims true" phase.)

1. **Gate destructive integration tools.** Route `google_send_email`,
   `google_delete_event`, `google_share_file`, `google_trash_file`,
   `google_delete_task`, `google_delete_contact` through `require_action` so the
   Approvals inbox actually intercepts them. *Until done, the UI flags them as ungated
   (it does not pretend they're safe).*
2. **Wire the gateway approval path.** Connect `RegistryApprover` +
   `PendingApprovalRegistry` to the Approvals inbox so API/channel sessions can escalate
   to a human (today they auto-deny). The TUI inbox becomes the human for those sessions.
3. **Hot-reloadable permissions.** Add a guarded `rebuild_gate()` that swaps the
   `PermissionGate` atomically *between turns* so "tighten the leash now" works without a
   restart. Prioritize tightening (emergency revoke) over loosening.
4. **First-class governance events.** Emit `budget.warned` / `budget.exceeded` and
   `policy.blocked` events (today budget caps only return a reason string). The
   Dashboard/Audit/Toasts bind to them cleanly instead of parsing chat output.
5. **Live AgentRegistry read model.** A small in-flight registry keyed by run-id (role,
   task, status, iter, parent_turn, model, leased_targets, tokens) so Agents shows live
   delegations as first-class rows, then flushes to `delegation_log` on completion.
6. **Per-sub-agent model selection** surfaced in Settings ▸ Sub-agents (the design slot
   exists; honor `model` per role even when a client is injected — the known
   `sub_agent.py` gap).

None of these block the TUI build; the views degrade gracefully and *honestly* without
them, which is itself on-brand for a trust-first product.

---

## 15. Phased implementation plan

**Phase 1 — the spine (highest trust ROI).**
`FrameShell` + focus routing · **TrustBar** (the 8 answers) · **Command Palette** ·
**Approvals** (modal + inbox, ungated-tool flags) · keep Chat working inside the new
frame. *Outcome: the 5-second test passes; approvals are first-class.*

**Phase 2 — the cockpit.**
Altitude toggle + **Dashboard** · **Agents** (with the AgentRegistry read model) ·
**Tasks** (jobs+schedules+suspended unified) · **Audit** (follow + filter). *Outcome:
supervise a fleet.*

**Phase 3 — knowledge & control.**
**Governance** editor (permissions/budgets/rules/safety) · **Memory** explorer (incl.
quarantine) · **Skills** + OG 3-pass inspector. *Outcome: full control + the moat made
visible.*

**Phase 4 — meters & connections + polish.**
**Resources** · **Connections** · **Settings** sub-pages (per-role models) ·
notifications/toasts polish · responsive/no-color hardening.

**Phase 5 — future surfaces.**
Voice indicator · remote/location column · marketplace tabs · compliance export ·
team actor column.

---

*End of specification. Wireframes are layout-accurate, not pixel-accurate; all data
bindings reference real symbols in the current codebase so this can be implemented
without re-deriving the contract.*
