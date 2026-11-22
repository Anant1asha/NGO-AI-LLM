# Hachi Web App — Implementation Contract (BINDING)

This is the single source of truth for the `frontend/` build. Every agent MUST follow it
exactly so independently-built files compose without conflict. The design we are porting is a
Claude Design HTML/CSS/JS prototype. We are recreating it **faithfully** as a real
TanStack + React + TypeScript app. Match the visual output pixel-for-pixel; do not copy the
prototype's template-engine internals.

## 0. Source of truth files (read these; do not modify them)
- Prototype (all screens + logic): `.design-bundle/project/Hachi Web App.dc.html` (2546 lines).
  - Template/markup: lines 30–1469. Logic class (state + methods + computed `renderVals`): 1471–2544.
- Mascot sprite component: `.design-bundle/project/HachiMascot.dc.html`
- Mascot states reference: `.design-bundle/project/Hachi Mascot States.dc.html`
- Icon path data: `.design-bundle/project/hachi-icons.js`
- Design tokens (real CSS, copy these): `design-system/tokens/*.css`
- Design-system component sources (for exact look/props): `design-system/components/`
- Design-system guide: `design-system/readme.md`

## 1. Stack, layout, commands
- **Vite + React 18 + TypeScript (strict)** with **TanStack Router file-based routing**
  (`@tanstack/react-router` + `@tanstack/router-plugin/vite`). Prefer TanStack **Start**
  (`@tanstack/react-start`) if it scaffolds cleanly; if Start's SSR blocks a clean build on
  Windows, fall back to TanStack Router SPA with the same `src/routes/` structure and record the
  choice in §8 of this file. Either way routing is file-based and routes live in `src/routes/`.
- **State:** `zustand` (single store, see §6). Persist `operator` + `theme` to localStorage.
- All app code under `frontend/`. Commands (run from `frontend/`):
  - install: `npm install`
  - dev: `npm run dev`  (must boot clean)
  - typecheck: `npm run typecheck` (alias for `tsc --noEmit`)
  - build: `npm run build` (must succeed)
- **Only the Scaffold agent and the Verify agent run npm.** Module/screen agents ONLY write files.

### File layout
```
frontend/
  index.html                 # links token CSS @imports via styles/index.css; sets <html data-theme>
  package.json  vite.config.ts  tsconfig.json
  src/
    main.tsx  routeTree.gen.ts (generated)
    styles/
      tokens/{colors,typography,spacing,motion,fonts,base}.css   # copied verbatim from DS
      index.css       # @imports the 6 token files + global.css
      global.css      # keyframes + .hachi-scroll + resets from the prototype <style> (lines 14–29)
    routes/
      __root.tsx      # app shell: <Sidebar/> + <Outlet/> + <GlobalOverlays/>
      index.tsx       # Home ("Today")            path "/"
      conversation.tsx  work.tsx  approvals.tsx  memory.tsx  skills.tsx
      og.tsx  authoring.tsx  integrations.tsx  settings.tsx  run.tsx
    components/
      icons/Icon.tsx              # <Icon name size/> ; registry ported from hachi-icons.js
      ui/{Button,StatusPill,Input,Switch,Badge,Card,Toast,LoyalLoop,RunCard,Terminal}.tsx
      brand/{HachiMark,HachiMascot,LeashPrompt}.tsx
      shell/{Sidebar,NavItem,BudgetWidget}.tsx
      overlays/{index,CommandPalette,SetupWizard,KennelConsent,ReconnectingBanner,ToastHost}.tsx
    lib/
      data/{types,fixtures,api}.ts
      store/store.ts
      hooks/useCountdown.ts
```
Routes map: `/`→Home, `/conversation`, `/work`, `/approvals`, `/memory`, `/skills`, `/og`,
`/authoring`, `/integrations`, `/settings`, `/run`.

## 2. Visual rules (from the DS guide — non-negotiable)
- Use the **token CSS variables** for every color/font/space/radius/duration. Never hardcode hex
  except where the prototype uses a one-off (e.g. scrollbar `#d3c8b4`, mascot pixels).
- Tokens available: colors `--hachi-brand|brand-hover|brand-tint|ink|muted|line|canvas|surface|cream|trust|working|success|danger` and their `-tint` variants; semantic aliases `--text-default|muted|link|on-brand`, `--surface-page|card|cream`, `--border-hairline`, `--accent`, `--focus-ring`. Fonts `--font-display|body|mono`. Type `--text-display|heading|body|small|mono`, `--weight-regular|medium`. Space `--space-1..8`. Radius `--radius-sm(6)|md(10)|lg(16)|pill(999)` (define lg/pill in spacing.css if missing). Motion `--dur-fast|dur|dur-slow|ease|transition`.
- Cards: `--hachi-surface` on `--hachi-canvas`, **0.5px hairline** `--hachi-line` border, radius 16, **no shadow**. Friendly rounded radii everywhere.
- **Torii red is rare** — mark + the single primary action per view only. Navy `--hachi-trust` is the workhorse secondary. Status families: working=amber, done=green, blocked/danger=their own reds.
- **Voice:** sentence case everywhere (never ALL CAPS), **no emoji**, address user as "you", Hachi speaks of itself in third person ("Hachi is resting"). Always show exact cost ("spent $0.02 of $1.00"). Status words lowercase: working · on watch · done · blocked.
- Motion: durations 120/200/320ms, ease `cubic-bezier(.2,.7,.3,1)`. Calm fades/short slides; no bounce. Hover darkens fill (brand→brand-hover) or tints bg. **Avoid CSS entrance animations on list items / frequently re-rendered nodes** (the prototype hit opacity-stuck bugs there — render them at full opacity).

## 3. Faithful porting technique
- The prototype styles with **inline styles**. You MAY keep inline `style={{}}` objects that
  reference `var(--token)` — this is the fastest way to match it pixel-for-pixel and keeps each
  screen self-contained (good for parallel work). Convert the prototype's `{{ x }}` holes to React
  expressions, `sc-if`→conditional render, `sc-for`→`.map()`, `onClick={{ f }}`→`onClick={f}`,
  `style-hover="..."`→a hover handler or a CSS class (small `.hover-*` utilities in global.css are OK).
- Replace `<hachi-icon name="x" size="n">` → `<Icon name="x" size={n}/>`.
- Replace DS `<x-import ...HachiDesignSystem_46e488.Button ...>` / `<dc-import name="HachiMascot">`
  → the corresponding React component from `components/ui` or `components/brand`.
- Keep the exact copy text, spacing, and structure of the prototype.

## 4. Icon component (`components/icons/Icon.tsx`)
- Port the FULL registry from `.design-bundle/project/hachi-icons.js` (a map of name→inner SVG path
  string). Render `<svg viewBox="0 0 24 24" width=size height=size fill="none" stroke="currentColor"
  stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" dangerouslySetInnerHTML>`.
- Props: `{ name: string; size?: number (default 18); style?; className? }`. Icons inherit
  `currentColor`; never Torii red unless it's the brand mark.
- Available names (port all): alert, arrow-right, arrow-up, bell, brain, calendar, chat, check,
  chevron-down, chevron-left, chevron-right, circle-alert, circle-check, clock, command, cpu,
  dollar, dots, enter, external, eye, file, file-code, folder, git-branch, globe, hash, home, key,
  leash, lightbulb, mail, memory, minus, moon, network, paw, pencil, play, plug, plus, refresh,
  repeat, search, send, settings, shield, skills, sparkles, stop, sun, terminal, trash, user, work, zap, pause.

## 5. Component APIs (implement EXACTLY; consumers rely on these signatures)
All components are typed `.tsx`, default or named export of the component (named exports preferred,
e.g. `export function Button(...)`). Props are TypeScript interfaces.

- `ui/Button({ variant?: 'primary'|'secondary'|'ghost' = 'primary', size?: 'sm'|'md' = 'md', type?, onClick?, disabled?, children, style? })`
  primary = Torii-red fill, cream text; secondary = navy outline; ghost = transparent. Radius md. Hover darkens.
- `ui/StatusPill({ status: 'working'|'on-watch'|'done'|'blocked', children? })` tinted bg + same-family text + a leading dot; lowercase label from status (on-watch → "on watch").
- `ui/Input({ value, onChange:(v)=>void, placeholder?, label?, mono?, type?, style? })` surface fill, hairline border, brand focus ring.
- `ui/Switch({ checked, onChange:(v)=>void, label?, disabled? })` on-state fills Torii red; 40×24.
- `ui/Badge({ tone?: 'default'|'brand'|'muted', children })` small inline chip.
- `ui/Card({ children, padding?, style?, onClick? })` the base surface container (surface, hairline, radius 16, no shadow).
- `ui/Toast({ message, tone?: 'success'|'blocked'|'info' = 'success' })` transient pill in Hachi voice.
- `ui/LoyalLoop({ size?: number = 48 })` the figure-8/infinity spinner tracing in Torii red (animate stroke-dashoffset; respect prefers-reduced-motion).
- `ui/RunCard({ title, status, progress: 0..1, spent: number, budget: number, meta?, onClick? })` status pill + thin Torii-red progress bar + always-visible "spent $x of $y".
- `ui/Terminal({ lines?: string[], prompt?: string, children?, style? })` dark mono surface (#16151A), JetBrains Mono, red `hachi ▸` prompt with blinking caret. Used by Live run output + CLI blocks.
- `brand/HachiMark({ size?: number = 24, variant?: 'default'|'knockout', style? })` the two-tone dog mark as inline SVG (port from DS `components/hachi/HachiMark` source or `docs/brand/hachi.svg`). knockout = single-color currentColor.
- `brand/HachiMascot({ state: 'on-watch'|'working'|'done'|'blocked'|'resting', scale?: number = 3, decor?: boolean = false, reduceMotion?: boolean = false, style? })` the pixel-grid morphing sprite. Port the sprite rows + per-state morph + the loyal-loop overlay (working) + "z" float (resting) + breathe/blink from `HachiMascot.dc.html`. Body uses `var(--hachi-brand)`, face `var(--hachi-cream)`/cream, eyes `var(--hachi-ink)`.
- `brand/LeashPrompt({ request, why, action?, risk?, onAllowOnce, onAlwaysAllow, onDecline, countdown? })` the signature calm permission card (port from DS `components/hachi/LeashPrompt`). Never looks like an error.

## 6. Data layer + store (Phase: Data agent owns these; screens CONSUME, never edit)
### `lib/data/types.ts`
Define TS interfaces/types for every fixture shape used in the prototype state (read the logic class
constructor, lines 1476–1723). Notably: `Approval, ApprovalDecision, HistoryItem, Run, RunStep,
Routine, RoutineRun, FinishedTask, FailedTask, MemGroup, Fact, BlockedItem, ProposedChange, Skill,
KennelItem, Integration, McpServer, McpTool, OgNode, AuthTarget, DiffLine, SpendTurn, SpendTidy,
SpendModel, PackMember, ActivityEvent, ToolCall, AuditEntry, RecallHit, Session, SkillUsage,
AskRule, OpTool, Toast, ScreenKey, SafetyLevel`. Export them all.

### `lib/data/fixtures.ts`
Export the initial data, copied verbatim from the prototype state object (lines 1476–1722):
`approvals, history, runs, routines, finished, failed, memGroups, blocked, proposed, skills, kennel,
integrations, mcpServers, mcpTools, ogNodes, authTargets, authSource, spendTurns, spendTidies,
spendModels, packRoster, events, toolCalls, auditLog, recall, sessions, skillUsage, askRules,
allowedFolders, allowedCommands, opTools`, plus scalars `initialSpent=0.41, initialBudget=5.0,
initialTaskSpent=0.03`. Approvals' `expiresAt`/`totalMs`: compute `expiresAt = Date.now()+totalMs`
inside an init function so the countdown is live.

### `lib/data/api.ts`
A thin async layer **shaped to the gateway OpenAPI** so real wiring is later a one-module change.
Export a `USE_MOCKS = true` flag and functions that currently resolve fixtures, e.g.:
`getApprovals(): Promise<Approval[]>`, `decideApproval(id, decision, reason?)`,
`getSchedules()` (routines), `getJobs()` (active/failed), `getSessions()`, `getCapabilities()`
(skills), `getConfig()/updateConfig()`, `getProviderModels()`, `getMcpInventory()`,
`getSubagentReports()` (pack), `getPermissionsAudit()`, `getSetup()/applySetup()`. Keep a single
`request()` helper guarded by `USE_MOCKS` (mock → fixtures; else `fetch('/api'+path)`). Screens do
NOT need to call api.ts directly — the store seeds from fixtures — but it must exist and typecheck.

### `lib/store/store.ts`  — `export const useStore = create<State & Actions>(...)`
Single zustand store. Persist only `operator` and `theme`. Seed all domain arrays from fixtures.
**State** (mirror the prototype state, names verbatim where listed): `operator, theme,
spent, budget, taskSpent, approvals, history, runs, routines, finished, failed, memGroups, blocked,
proposed, skills, kennel, integrations, mcpServers, mcpTools, ogNodes, authTargets, authSource,
authSel, authMode, authApplied, ogSel, ogView, spendTurns, spendTidies, spendModels, packRoster,
events, toolCalls, auditLog, recall, sessions, skillUsage, safety, askRules, allowedFolders,
allowedCommands, opTools, provider({name,model,key}), reconnecting`.
Plus ephemeral UI state used across screens/overlays: `toast, palette{open,query},
setup{open,step,key,safety,routine,google,channel}, kennelConsent, slashOpen, streaming,
inContext, messages, composer, homeInput, selectedWork, runView, runLines, runStreaming, runDone,
runLeash, runSpent, runPack, runSteps, editingFactId, editingText`.
**Actions** (implement faithfully from the logic methods; read them in the .dc.html logic section):
`setOperator(b), setTheme(t), toggleTheme(), showToast(message,tone?), dismissToast(),
openPalette()/closePalette()/setPaletteQuery(q),
openSetup()/closeSetup()/setSetupStep(n)/setSetupField(k,v),
allowApproval(id, scope?)/declineApproval(id, reason?) (also append to history + auditLog),
pauseRoutine(id)/runRoutineNow(id), cancelRun(id), retryFailed(id), duplicateRoutine(id),
openWork(id)/closeWork(), setWorkFilter(f),
addFact(groupId,text)/editFact(id,text)/deleteFact(id)/startEditFact(id)/approveProposed()/rejectProposed(),
addSkill(kennelId) (-> opens kennelConsent)/confirmKennel()/cancelKennel()/removeSkill(id),
setOgSel(id)/setOgView(v), selectAuthTarget(name)/setAuthMode(m)/applyPatch()/revertPatch(),
connectIntegration(id)/disconnectIntegration(id),
setSafety(level)/toggleAskRule(id)/removeFolder(f)/removeCommand(c)/toggleOpTool(id)/setProvider(p),
startTask(text) (Home/Conversation: pushes a user msg, streams a Hachi reply with action cards,
raises an in-context leash), sendMessage(text), stopStreaming(),
openRun(runId)/watchLive(runId)/closeRun(), simulateReconnect()`.
Keep screen-LOCAL view state (expanded card, active sub-tab, hover) in component `useState`; only
shared domain mutations go through store actions. If you truly need a new shared action, add it here.

### `lib/hooks/useCountdown.ts`
`useCountdown(expiresAt: number): { ms, label }` — ticks every 1s, formats `1m 19s` / `45s`,
clamps at 0. Used by approval cards. (A single `setInterval` in the store or this hook drives the
"auto-declines in …" countdown; expired approvals auto-decline → "Hachi stayed put".)

## 7. Routing & shell conventions
- `routes/__root.tsx` renders `<div data-theme={theme} style="display:flex;height:100vh">` with
  `<Sidebar/>` + `<main style="flex:1;min-width:0">` `<Outlet/>` + `<GlobalOverlays/>`. Apply
  `data-theme` from the store to `document.documentElement` in an effect.
- `Sidebar` (port lines 34–81): centered `<HachiMascot state=… scale=3/>` at top, the ⌘K search
  button (opens palette), the nav list (the 10 nav items below + correct active highlight from the
  current route), the **operator view** `<Switch/>`, and the clickable **today's budget** widget
  (→ navigates to `/work` Spend, or `/work`). Active nav item: brand-tinted bg + medium weight.
- Nav (key→route→label→icon): home `/` "Today" home · chat `/conversation` "Conversation" chat ·
  work `/work` "Work" work · approvals `/approvals` "The leash" leash · memory `/memory` "Memory"
  memory · skills `/skills` "The library" skills · og `/og` "OG explorer" network · authoring
  `/authoring` "Authoring" file-code · integrations `/integrations` "Integrations" plug · settings
  `/settings` "Settings" settings. (The leash nav shows a badge = pending approvals count.)
- `overlays/index.tsx` exports `GlobalOverlays` rendering CommandPalette, SetupWizard, KennelConsent,
  ReconnectingBanner, ToastHost — each reads the store and self-gates on its open flag.
- Live run (`/run`) is reachable via "watch live" / "doing now" cards / palette; not in the sidebar nav.

## 8. Routing setup actually used (Verify/Scaffold fills this in)
- (to be completed by the Scaffold agent with the concrete route file syntax used, e.g.
  `export const Route = createFileRoute('/conversation')({ component: Conversation })`.)

## 9. Definition of done
- `npm run build` succeeds; `npm run typecheck` clean; `npm run dev` boots with no console errors.
- All 11 screens render and are navigable; overlays open/close; the signature flows work
  (start task → streaming → in-context leash → allow → toast; approve/decline with live countdown;
  operator toggle reveals operator-only surfaces). No emoji, sentence case, cost always visible.
