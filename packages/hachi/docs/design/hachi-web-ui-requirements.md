# Hachi — Web UI Requirements & Design Brief

> **What this is.** A build-ready brief for a UI/UX designer to prototype Hachi's **web app in Claude Design**.
> It covers *product context, audiences, the screens and flows to design, behaviours, and content* — the
> "what" and "why." It deliberately does **not** specify visual style (colour, type, spacing, components):
> that is owned by the existing **Hachi Design System**. Add that system to your Claude Design project and
> apply it; this brief is what you apply it *to*.
>
> **Scope (v1):** single-user · local-first · **desktop**. One product serving **two audiences**: a
> non-technical *companion* user and a technical *operator*.
> **Out of scope for v1:** teams / multi-user, multiple workspaces, mobile, billing, a full skill
> marketplace/publishing, and any API/technical implementation detail.

---

## 1. What Hachi is — the mental model to design around

Hachi is a **personal AI agent that does autonomous, long-running work on the user's own machine** — and
asks permission before it does anything risky. Named after the loyal Akita: capable, patient, waits at the
door.

Design for this truth, not for a chatbot:

- **It's a control surface, not a chat window.** A lot of work runs in the background, on a schedule, or
  delegated to helper agents, and keeps running when the user isn't watching. Conversation is just *one way
  to start work*.
- **Its reason to exist is trust through control.** The promise is *"you hold the leash."* Every screen must
  help answer: *what is Hachi doing, what did it touch, what does it cost, what is it waiting on, and how do
  I approve or stop it?* If a screen hides any of those, it's wrong.
- **Tone is calm, plain, honest, never hype.** "A good dog." It shows real status and real errors; it never
  alarms; it never buries cost.

---

## 2. Who it's for — design for both, in one product

| | **Companion** (non-technical) | **Operator** (technical) |
|---|---|---|
| Who | The person whose life the agent touches | Developer / power user / "supervisor" |
| Wants | Approve or decline what Hachi proposes; see today's plan; never see jargon | Delegate, watch tool calls, automate, inspect, tune, investigate failures |
| Mindset | "Hachi asks before it acts — I just say yes or no." | "I'm supervising a worker I'm responsible for." |
| Needs | Plain language, approvals front-and-centre, reassurance | Density, depth, keyboard control, transparency |

**Core design principle: one adaptive product — calm and plain by default, operator depth on demand.**
Do *not* build two apps or force a mode at sign-in. Default everything to the simplest, plainest version
that satisfies the companion; let operators reveal depth contextually (expand a card, open advanced
settings, use the command palette). Offer an optional **"operator view"** toggle that surfaces power
surfaces (skill authoring, raw activity log, full permission editor). When in doubt, choose the more
legible, more honest, less technical option.

---

## 3. The product vocabulary — use these exact words in the UI

Hachi has a deliberate in-product language. Use it; don't invent synonyms.

| Concept | Word to use |
|---|---|
| Permissions | **the leash** — *you hold it* |
| Background / long-running work | **on watch** |
| A finished task | **Hachi is resting** |
| Helper sub-agents | **the pack** |
| Skill library / marketplace | **the kennel** |
| Live status words | **working · on watch · done · blocked** |
| Recurring automated tasks | **routines** |
| Spend limits | **limits / budget** |

**Voice:** sentence case everywhere; never ALL CAPS; **no emoji**. Address the user as "you." **Hachi
refers to itself in the third person** ("Hachi is working," "Hachi is resting") — a companion, not a chatbot
saying "I." One plain line beats a paragraph; always explain *why* in one clause (e.g. *"why: install the
dependencies for your build"*). Show real errors plainly, each with a next action. Never round cost into
vagueness — always exact (*"spent $0.02 of $1.00"*).

---

## 4. Cross-cutting requirements — apply to every screen

1. **Always visible:** Hachi's current state, **spend vs. budget**, and **pending approvals**. Cost and
   permissions are features, not settings to hide.
2. **Responses stream live and are interruptible** — text appears as it's generated; the user can always
   stop the current task.
3. **Every action Hachi takes is shown as an expandable card** — collapsed = one plain line (what + status
   + cost); expanded = the details. Transparency is the product.
4. **Approvals appear two ways:** *in context* (a focused prompt during a task the user is watching) and as
   an *inbox* (a queue when work runs in the background). Each shows the action, a one-line *why*, the risk,
   and **a visible countdown** (requests expire and auto-decline — never let that be a surprise). Choices:
   **Allow once · Always allow · Decline** (declining can take an optional reason).
5. **Command palette + global search** (keyboard-launched) to jump anywhere or do anything; the product is
   keyboard-friendly throughout (mouse optional).
6. **Design every state, not just the happy path:** empty (teach the next action) · loading · **error**
   (real message + next action) · **streaming** (live work) · reconnecting (the agent runs locally and the
   connection can drop) · busy (a task is already running) · **approval-timed-out** · done/success (a calm
   confirmation in the leash voice, not a modal).

---

## 5. Screens to design

For each: **Goal · Audience · On screen · Key actions · States.** Layout *intent* is noted where it helps;
visual styling comes from the design system.

### 5.0 Setup (first-run wizard)
- **Goal:** get a brand-new user to their first useful task in under five minutes.
- **Audience:** both (must be friendly enough for the companion).
- **On screen:** a short, resumable stepper — welcome → choose an AI provider + enter a key (**validated on
  the spot**, with a clear ✓/⚠) → choose a safety level (with plain-language consequences, not jargon) →
  optional connect Google / a chat channel → a "first routine" suggestion ("set up a morning briefing").
- **Key actions:** back / next / skip / finish; validate key; finish into Home.
- **States:** invalid key (inline, before proceeding), skipped steps, resume-after-interruption.

### 5.1 Home ("Today")
- **Goal:** the five-second answer to "what's happening, and does anything need me?" The calm landing page.
- **Audience:** both. This is the companion's home; the operator's pulse.
- **On screen:** **what needs you** (pending approvals — the loudest thing), **what Hachi is doing now**,
  **what's on watch** (scheduled/background routines + next run), **what finished recently** (plain
  language), today's spend vs. budget, and a prominent **"start something"** action (new conversation /
  describe a task).
- **Key actions:** approve/decline inline; open any item; start a new task; jump to a routine.
- **States:** nothing-needs-you ("Hachi is on watch"), first-run empty (suggest starter tasks), error.

### 5.2 Conversation (Chat)
- **Goal:** work *with* Hachi live — talk, delegate, watch it act, approve in the moment.
- **Audience:** both (companion stays in plain chat; operator expands the detail).
- **On screen:** the transcript (clearly distinct **you** vs **Hachi** messages); **action cards**
  (collapsible tool/helper-agent steps with status and cost); a **"what Hachi will do next" plan** when one
  exists; the live spend/state for this task; an **in-context approval** when one is raised; a composer with
  a slash-command menu, input history, and a clear send/stop.
- **Key actions:** send, stop/interrupt, expand a card, copy a reply, approve in place, run a slash command.
- **States:** welcome/empty (a friendly prompt + a few starter suggestions), streaming, awaiting approval,
  busy/queued, error card, reconnecting.

### 5.3 Tasks & Automations ("Work")
- **Goal:** one place for all work — what's running, what's scheduled (routines), what finished, what
  failed.
- **Audience:** both (companion sees "your routines" plainly; operator sees the full queue + traces).
- **On screen:** filter tabs (**active · routines · history · needs attention**); each item shows a plain
  title, status, owner (a conversation, a helper agent, or a routine), when it ran / next run, and cost.
  A **detail panel** for any item; for a blocked item, *what it's waiting on*; for a failed one, the real
  error + a retry. Routines show their schedule, steps, and run history with cost per run.
- **Key actions:** pause/resume a routine, cancel, retry, duplicate, open detail, "watch live."
- **States:** empty (no work yet — suggest creating a routine), failed (error + retry), blocked
  (waiting-on), loading.

### 5.4 Approvals ("the leash")
- **Goal:** where the user exercises authority — the trust crux. Critical for the companion.
- **Audience:** both; designed to be effortless for a non-technical user.
- **On screen:** a queue of pending requests, each in **plain language** — *"Hachi wants to send an email to
  Priya"* — with a one-line *why*, what exactly it will do, the risk, and a **visible countdown**. A history
  of past decisions. Flag any action that currently runs **without** a leash check (be honest about it).
- **Key actions:** **Allow once · Always allow (this kind/contact/site) · Decline (+ optional reason);** bulk
  approve/decline; open detail.
- **States:** nothing pending (calm), one urgent (focused), timed-out → auto-declined ("Hachi stayed put"),
  many pending (triage).

### 5.5 Memory
- **Goal:** answer "what does Hachi know about me?" — never a black box. Inspect, correct, and approve what
  it remembers.
- **Audience:** both (companion: simple editable cards; operator: search, categories, advanced).
- **On screen:** search; remembered facts grouped sensibly (about you, your work, the agent's own notes),
  each card showing the fact and where it came from; **proposed changes to review** (Hachi suggests an
  update → you approve or reject — it never silently overwrites); a list of **blocked/quarantined** items it
  refused to store.
- **Key actions:** search, edit, delete, add a fact, approve/reject a proposed change, review blocked items.
- **States:** empty ("Hachi hasn't learned anything yet"), search-no-results, a pending change to review.

### 5.6 Skills ("the Library / kennel")
- **Goal:** see and manage what Hachi *can do*, and (lightly) discover more.
- **Audience:** operator-leaning; companion sees a simple "what Hachi can do" list.
- **On screen:** installed capabilities with a plain description, how often each is used, and when last used;
  a simple **browse/add from the kennel** entry; for operators, a way to see a capability's details and
  **author/edit** one (advanced, behind "operator view"). Surface stale/unused ones gently ("not used in 90
  days — remove?").
- **Key actions:** view, add, remove; (operator) author/edit, view versions.
- **States:** empty, adding/installing (with a clear "what it will be allowed to do" consent step), error.

### 5.7 Integrations
- **Goal:** connect the accounts and tools Hachi can reach (Google, Slack, Notion, chat channels, and
  developer "MCP" tools).
- **Audience:** both (companion: "connect your Google"; operator: add custom tools, see health).
- **On screen:** connected accounts/tools with **health/status**, what each can do, and the access it was
  granted; a clear connect / re-authorise / disconnect; honest flags on anything with risky access.
- **Key actions:** connect, test, re-authorise, disconnect, (operator) add a custom tool server.
- **States:** none connected (guide the first connection), connecting, connected, failed/expired, degraded.

### 5.8 Settings (incl. the leash, provider, and limits)
- **Goal:** configure Hachi safely — the place the operator tunes and the companion adjusts a few basics.
- **Audience:** both, with progressive disclosure.
- **On screen, grouped:**
  - **Permissions & safety (the leash):** safety level; which folders/commands/tools Hachi may use; "ask
    before…" rules (before spending over $X, before sending anything out, before deleting). Plain-language;
    operator can go deeper. Be honest when a change "applies next time Hachi starts."
  - **Spend & limits:** budget caps (per task and overall) shown against current spend; what's costing money.
  - **AI provider & model:** which provider/model, with a validate action; keys are entered masked and never
    shown back.
  - **Memory & routines:** toggles for what Hachi remembers; manage routines.
  - **Appearance & account:** theme, the (re-run) setup wizard, keyboard shortcuts.
- **Key actions:** edit (validated), change safety level (with a clear warning for the most permissive),
  validate provider, set a limit.
- **States:** unsaved changes, validation error, "applies next launch" notice, save success.

### 5.9 Command palette / global search (overlay, on every screen)
- **Goal:** jump anywhere or do anything from the keyboard.
- **On screen:** one search field → grouped results (go to a place · do an action · open a recent
  conversation/skill/memory). Shows the keyboard shortcut beside each item.

---

## 6. Key flows to prototype (build these as cohesive journeys, not isolated screens)

1. **First five minutes** — Setup → validate key → pick safety level → suggested "morning briefing" → see it
   confirmed and "on watch" on Home. *(The make-or-break flow.)*
2. **Do a task, approve in the moment** — start a task in Conversation → watch action cards stream → an
   approval appears → Allow once → result completes.
3. **Create a routine in plain language** — type *"every weekday at 8, summarise my inbox and message me the
   urgent ones"* → Hachi shows a preview (trigger, steps, what it needs, cost per run) → **try it once
   safely (dry run)** → approve → it appears under routines.
4. **Triage what needs you** — open Approvals with several pending → understand each in plain language →
   decide quickly (including a timed-out one).
5. **Check spend and tighten a limit** — see today's cost on Home → open Spend & limits → lower a cap.
6. **See and fix what Hachi remembers** — open Memory → find a wrong fact → correct it → approve a proposed
   change.
7. **Connect an account** — Integrations → connect Google → grant access → it becomes usable.
8. *(Operator)* **Investigate a failure** — Work → a failed task → read the real error → fix the cause →
   retry.

---

## 7. Open scope decisions — recommendations (adjust as you like)

These aren't settled in the product yet; here's the recommended v1 stance so the prototype stays focused.

- **Projects / grouping:** *Recommend defer.* Keep the IA flat for v1; if grouping is needed, use simple
  optional tags on conversations and routines — not a separate "Projects" hub. (A richer project model can
  come later.)
- **The kennel (marketplace):** *Recommend light.* Include browsing and adding skills with a clear consent
  step; defer the full publish/economy experience.
- **Companion vs operator:** *Recommend one adaptive UI* (§2), not two apps or a hard mode switch.
- **Explicitly out for v1:** teams/multi-user, multiple workspaces, mobile, billing/subscriptions. Don't
  design these now, but don't build anything that would block adding them later (e.g. leave room near the
  account area).

---

## 8. How to drive Claude Design with this brief

Based on how Claude Design works best (it inherits your design system, and rewards specific, iterative,
flow-based prompting):

1. **Set up the project first.** Create a Claude Design project and **add the Hachi Design System** (and any
   reference screenshots). Projects automatically inherit brand colours, fonts, and components — so you
   won't have to restate visuals, and every screen stays consistent.
2. **Prompt screen-by-screen, in this brief's order**, and *start simple, then layer*. For each screen give
   four things: **goal · audience · content (what's on screen) · layout intent**, then add **interactions**
   and ask it to **show the states** (empty / loading / error / streaming). This brief already contains all
   of that per screen — paste the screen's section and let it generate.
3. **Build the flows in §6 as journeys**, not loose screens — walk Claude through the steps so it generates
   each screen *in context* and keeps them consistent ("now the next step in this flow is…").
4. **Name components by the design system's names** so they carry through; reference patterns ("use the same
   card pattern as the action cards in Conversation").
5. **Ask for variations** on the highest-stakes screens (Home, Conversation, Approvals) — "show me three
   layouts so I can compare" — then keep the best.
6. **Ask Claude for feedback** on accessibility and usability before you settle a screen.
7. **Iterate with inline comments for small edits and chat for structural changes.** For a real pivot, tell
   it *"save what we have and try a completely different approach."*
8. **Optional high-leverage move:** name a reference vibe for personality only (calm, precise developer
   tools) — but the Hachi Design System remains the source of truth; don't let a reference override it.

---

*Prepared as a product/UX brief only. Visual design = the Hachi Design System. Implementation/data details
intentionally omitted — they aren't needed to design the prototype.*
