# Phase 5 — The Personal AI OS: Agents, Google Workspace, NL Automation, Marketplace

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Inputs:** Phases 0–4. New verified fact this phase: `PermissionGate` enforces filesystem/terminal/MCP
rules only — **no integration-scope rules exist** despite CLAUDE.md's claim ▶ permissions.py (grep:
no scope model) → logged as discrepancy **D9**.
**Voices:** §1 = What I found · §2–§8 = What I propose.

---

## 1. What already exists to build on (observation)

The repo is unusually close to "platform" already — the design below is mostly *composition*:

| Primitive | Evidence |
|---|---|
| All 8 Workspace services implemented (Gmail, Calendar, Tasks, Docs, Drive, Sheets, Meet, Contacts + planning) | ✅ src/hachi/integrations/google/* (Phase 0 listing); real OAuth/PKCE + vault storage Ⓐ oauth.py |
| Lazy "google" tool group; graceful stubs when unconfigured | ✅ orchestrator.py:234, 1366–1369 |
| Role sub-agents with scoped tools + skill views | ✅ sub_agent.py, delegation_tools rebinding (orchestrator.py:1411–1427) |
| Parallel delegation | ✅ delegation_tools.py:622 `delegate_parallel_tasks` |
| Scheduler (cron/interval/once) firing `session.chat`; full CLI (add/pause/resume/trigger/export) | ✅ orchestrator.py:1568–1578, Ⓐ CLI map |
| Suspend/resume workflow primitive | ✅ loop.py:57–62 `SuspendWorkflow`, `core_suspend_workflow` tool |
| Skills that carry REST tools (`::api`) with vault-injected, SSRF-guarded calls | ✅ Phase 2 §4.2 |
| Pack infrastructure: manifest-driven core/optional installs; community-pack fetcher (no packs shipped) | ✅ skill_packs.py, Ⓐ community_packs.py |
| Per-skill semver + `::changelog` + `min_agent_version` field | ✅ parser.py:101, engine.py:705–747 |
| Agent-persona packs already sketched | ✅ default_skills/google/{inbox_sentinel,meeting_copilot,morning_briefing,receipt_sweeper,travel_organizer}.og, notion/, slack/ |
| Marketplace threat model documented from the field | 🌐 Phase 3 (ClawHavoc: 800+ malicious skills) |

**The one-line consequence:** Hachi should ship agents as **packs over one kernel**, not as new
runtimes — the delegation/roles machinery already works exactly that way.

## 2. The OS framing (proposal)

```
┌─ Surfaces ──────────────────────────────────────────────────────────────┐
│  TUI · Web · Telegram/WhatsApp/Slack/Discord · OpenAI-compatible API    │
├─ Kernel ────────────────────────────────────────────────────────────────┤
│  ExecutionLoop + TurnContext (scheduler = cron; sub-agents = processes) │
│  Syscall layer: ToolRegistry → PermissionGate (every call gated)        │
├─ Filesystem ────────────────────────────────────────────────────────────┤
│  skills/*.og · memory/*.og (Phase 4) · device-permissions.og            │
├─ Drivers ───────────────────────────────────────────────────────────────┤
│  Google Workspace · Notion · Slack · ::api REST adapter · MCP servers   │
├─ Package manager ───────────────────────────────────────────────────────┤
│  Agent Packs (.ogpack): install · scope-consent · update · yank         │
└─────────────────────────────────────────────────────────────────────────┘
```

**An "Agent" = an installable pack**: `brain-<agent>.og` (persona/rules, sub-agent-loadable ✅
PromptBuilder, sub_agent.py:216–268) + `skills/*.og` (procedures, with `::api` tools) +
`workflows/*.og` (NL-authored, §5) + suggested `schedules.json` + a scoped manifest (§6). Running an
agent = the existing delegation path with the pack's role; *resident* agents = schedules firing
scoped sessions. No new process model.

## 3. The seven agents — composition + gaps (proposal)

| Agent | Composes (exists ✅) | Missing (build) |
|---|---|---|
| **Email** | gmail tools; `inbox_sentinel.og`; messaging channels for alerts; emailer role | Triage memory (sender→importance as `person` nodes, Phase 4); draft-approval UX (TUI/Telegram inline approve — InteractivePermissionGate pattern ✅); send-scope consent (§6) |
| **Meeting** | calendar + meet + contacts; `meeting_copilot.og`; voice transcribe ✅ voice_tools | Pre-brief workflow (calendar→people/*.og lookup→pack); post-meeting episode node write (Phase 4 M1) |
| **Research** | researcher role; browse_web + browser group; vault/memory; delegate_parallel_tasks | Source-tracking nodes (`artifact`+`evidence` edges, Phase 4); long-run jobs on durable queue (Phase 1 R5); report templates as skills |
| **CRM** | contacts API; Phase 4 `people/*.og` + `involves` edges; episode log | Interaction-capture extractor rules; "catch me up on X" resume packs (Phase 4 Stage C) |
| **Finance** | `receipt_sweeper.og`; sheets tools; finance.og quotes; drive | Statement-parsing skills; monthly rollup workflow; **hard rule: read/categorize only — never move money** (gate-enforced, §6) |
| **Career** | docs tools; journal episodes (Phase 4); save_skill loop | Weekly-reflection workflow; achievement nodes feeding review docs |
| **Learning** | save_skill self-improvement ✅; wiki/dictionary skills; scheduler | Spaced-repetition workflow (schedule + journal query); progress nodes |

Each is **S–M effort (2–6 d) once the platform pieces below exist** (medium confidence); Email and
Meeting first — their `.og` seeds already ship.

## 4. Google Workspace as a *native* capability (proposal)

Modules exist; what blocks "native" is **first-touch friction and scope granularity**:

1. **OAuth without a GCP console visit.** Today requires user-supplied `GOOGLE_CLIENT_ID` Ⓐ
   (creating a Google Cloud project is the single biggest non-dev filter). Proposal: project-owned
   OAuth client using the **device-code flow** (TUI/Telegram show a code + URL; no localhost
   redirect, works headless), minimal incremental scopes; BYO-client stays for sovereignty users.
   ⚠️ **Org decision required**: a hosted client id means Google verification + an Anthropic-style
   brand trust burden + quota ownership — flag to user; effort 2–4 d eng + verification lead time
   (low confidence on the review timeline).
2. **Incremental, per-agent scopes.** Install Email-agent → request `gmail.readonly` only; the first
   *send* triggers an interactive scope upgrade through the existing approval-handler path ✅
   InteractivePermissionGate (orchestrator.py:1089–1094). Requires §6's scope model (D9 gap).
3. **Triggers: poll-first, push later.** Briefings/sentinels run on the scheduler (exists). Gmail
   `watch`/Calendar push need a public HTTPS endpoint — defer; the webhook route ✅
   fastapi_app.py:482 is ready when users opt into exposure (with the Phase 1 R16 posture).
4. **Rate/cost hygiene**: Google client already does backoff Ⓐ google/client.py:77; per-pack
   schedule budgets come from the existing per-turn caps ✅ loop.py:340–360.

## 5. Natural-language workflow creation — no YAML, ever (proposal)

**Thesis:** users speak; the system compiles to artifacts that *already exist* — a workflow skill
(`.og` with `::steps`/`::assertions`) plus a `Schedule` whose `task` invokes it. No new DSL; the
".og as workflow IR" is internal and inspectable, never required reading.

**The compile conversation** (the only new machinery — "Workflow Composer"):

```
User (Telegram): every weekday at 8 send me a briefing of my calendar and important emails
Agent:           Here's what I'll set up:
                 ⏰ Mon–Fri 08:00 (Asia/Kolkata)
                 1. Read today's calendar (calendar.readonly)
                 2. Scan inbox for important unread (gmail.readonly)
                 3. Compose briefing → send here (Telegram)
                 Scopes already granted ✓ · est. ~$0.02/run
                 [Approve] [Edit] [Dry-run]
```

- **Approve** → `save_skill(workflow_morning_briefing, steps=…, assertions=["calendar reachable"])`
  ✅ existing tool + `create_schedule(cron="0 8 * * 1-5", task="run workflow_morning_briefing")` ✅
  existing tool. Both artifacts versioned/diffable like everything else.
- **Dry-run** = run the workflow as a sub-agent whose registry is wrapped in a **read-only gate**
  (the gate already distinguishes read/write/delete ✅ permissions.py:484–508 — sandbox-tier wrap =
  free dry-run; outbound sends stubbed to "would send: …"). Effort ~1–2 d, high confidence.
- **Triggers beyond time** via a small trigger registry: `time` (exists) · `webhook` (exists) ·
  `condition` (new: scheduled cheap evaluation of a condition skill, e.g. "new email from
  landlord" → fire workflow; haiku-class check, budget-capped). Effort 3–5 d (medium).
- **NL lifecycle**: "stop the morning thing" → semantic match over schedules → `pause` (CLI/tooling
  exists Ⓐ schedule pause/resume) with confirmation; "make it 9" → update (exists).
- **Failure UX**: workflow errors land as failed jobs (read-models ✅) and a channel message with
  one-tap [Retry] [Pause] — depends on Phase 1 R4/R5.

Composer effort total: **4–7 d** (medium-high) — it is a prompt-pattern + preview renderer + two
existing tool calls, not an engine.

## 6. Permission & security model for the platform (proposal)

Five layers — three exist, two are new:

1. **Device tier** (exists ✅): sandbox/guided/unrestricted; blocked-paths-always-win; interpreter
   blocking (Phase 1 S5).
2. **Pack manifest scopes** (NEW — closes D9): each `.ogpack` declares
   `tools: [gmail.read, calendar.read, telegram.send]`, fs paths, schedule budget
   (`max_runs/day`, `max_cost/run`). Install renders a mobile-style consent sheet; **updates that
   widen scopes re-prompt with a diff** (the ClawHavoc-class control). Enforced by stamping the
   pack's sub-agent registry (rebinding machinery exists ✅) + a scope check in the gate.
3. **Runtime gate** (exists ✅): every call re-checked; InteractivePermissionGate escalates
   first-use of sensitive scopes.
4. **Data plane** (exists ✅): vault-only secrets interpolated at call time (never in pack files)
   rest_adapter.py Ⓐ; outbound secret redaction; SSRF guard; MemoryGuard/quarantine for what packs
   write to memory.
5. **Hard floors** (policy, gate-enforced): finance = read/categorize only, never transact;
   contacts/email bulk-send caps; no pack may grant itself `unrestricted`.

**Why `.og` packs are structurally safer than the field:** a skill is *data* — its `::code` blocks
are reference text and its `::api` calls run through the guarded adapter; there is **no
install-time or import-time code execution path** (vs. ClawHub's npm-style payloads that shipped
AMOS 🌐). Execution always crosses the syscall layer. This claim is checkable in code today ✅ and
should be the marketplace's headline.

## 7. Marketplace: packaging, distribution, versioning (proposal)

**Package format `.ogpack`** = tar of the pack dir + `pack.toml`
(`id`, `semver`, `min_agent_version` — field already parsed ✅ parser.py:101, `scopes[]`,
`sha256s`, `signature`). Per-skill `::meta.version` + `::changelog` (exist ✅) give sub-pack deltas;
`skill_changelog` tool (exists ✅) lets agents delta-check after updates.

**Distribution in three stages:**
- **Stage 1 (now):** git/URL installs via the existing community_packs fetcher Ⓐ + a curated
  `hachi-packs` index repo (Homebrew-tap model). Signing optional but verified when present.
- **Stage 2:** registry service with publish gates: `lint_og_file` must pass with 0 errors ✅
  engine.py:104–208 · static scan (reuse secret_scanner + memory_guard patterns ✅) · scope manifest
  required · namespace ownership · provenance signature (sigstore keyless or minisign).
- **Stage 3:** install telemetry-free trust tiers — `official` / `verified publisher` /
  `community (unreviewed)` with default-install warning on the last; report + yank + version-pin.

**ClawHavoc → control mapping** (each verified attack vector 🌐 answered):

| ClawHub failure | Hachi control |
|---|---|
| Malicious skills executed code on install | No execution path in pack format (§6) |
| 20% of registry poisoned, discovered late | Publish-time lint+scan gate; yank; signed index |
| Skills exfiltrated creds | Secrets never in packs; vault interpolation + outbound redaction ✅ |
| Updates silently changed behavior | Scope-diff re-consent + per-skill changelog surfaced on update |
| No provenance | Signature + namespace ownership |

**Versioning policy:** packs semver; engine compatibility via `min_agent_version`; skills inside a
pack may `supersede` (Phase 4 edge) for migration notes; registry rejects version reuse.

## 8. Sequencing & effort (feeds Phase 8)

| Step | Depends on | Effort (conf.) |
|---|---|---|
| Pack format + installer + consent sheet (closes D9) | Phase 2 qualified IDs | 4–6 d (med-high) |
| Workflow Composer + dry-run + condition triggers | R1/R4/R5 (Phase 1) | 5–8 d (medium) |
| Google device-flow onboarding | org decision ⚠️ | 2–4 d eng + review lead time (low conf. on timeline) |
| Email + Meeting agents as packs | pack format | 4–8 d combined (medium) |
| Curated index repo (Stage 1 distribution) | pack format | 1–2 d (high) |
| Registry service (Stage 2) | traction signal | 3–6 wk (low conf.; defer past Phase 8's 90-day line) |

**Decisions needed from the user:** (1) hosted Google OAuth client — yes/no; (2) marketplace Stage 2
build-vs-defer threshold (e.g., ≥20 community packs in the index repo).
