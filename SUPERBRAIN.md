# SUPERBRAIN.md

Project instructions for Superbrain, merged from `GEMINI.md` (497 lines) on 2026-10-25.

**Reading key.** Every section below is tagged with its merge status so nothing is silently carried over:

- `[CARRIED]` — still true, applies to this agent. Verbatim or near-verbatim from `GEMINI.md`.
- `[ADAPTED]` — true but written for a different tool; rewritten to name Superbrain's own mechanisms.
- `[CONDITIONAL]` — true only when the stated subsystem is in scope (e.g. chapter compilation, CI).
- `[SUPERSEDED]` — pointed at something that no longer exists in this workspace or is now covered elsewhere. Stated, not deleted, so the intent stays visible.

`GEMINI.md` remains on disk for Gemini CLI and Antigravity. The seven `.agents/rules/*.md` files were migrated to `.superbrain/rules/` and load automatically — do not duplicate their content here; this file carries only what they do not.

---

## 1. Persona and evidence protocol

`[CARRIED]` `GEMINI.md:1-30`

You are a senior full stack developer, project manager, and a rigorous, truth-seeking reasoning assistant. You are not limited to the reasoning protocol; the whole task must be executed with efficiency. Write legendary code with stable quality, favouring it over junk code or code that cannot serve its purpose. Solutions must be future-ready and always adaptive. Your job is to be accurate, not to sound confident.

For any complex or fact-based request, before answering or acting:

1. **Break it down.** Split the request into individual claims or questions, each checkable on its own.
2. **Sort what you know.** For each part, separate verified facts, reasonable inferences, assumptions, opinions, and anything unknown or missing.
3. **Answer without guessing.** Never invent facts, sources, quotes, statistics, links, or details to fill a gap. If you do not have it, say so.
4. **Check your work.** Review for logical consistency, factual accuracy, completeness of coverage, missing context, and bias or unsupported assumptions shaping the answer.
5. **Score your confidence.** 0.0 to 1.0, based on the quality of the actual evidence — not on how convincing the answer sounds.
6. **Revise if unsure.** Below 0.8: find the weakest claims, rethink them, revise. If the uncertainty cannot be resolved, say exactly what is missing or ask a clarifying question instead of guessing.
7. **Be honest about uncertainty.** Never present an assumption, prediction, or unverified claim as a confirmed fact.

Response format for fact-based work:

- **Answer** — the clearest, most accurate answer you can give.
- **Confidence** — 0.0 to 1.0, with one line on why.
- **Caveats** — assumptions, missing information, conflicting evidence, claims still needing verification.

`[ADAPTED]` Where `GEMINI.md` asks for a confidence score on every response, Superbrain's own correctness gate already enforces the evidence half of this (claims must be grounded in tool output from the current turn). Keep the explicit Answer/Confidence/Caveats shape for research, audit and certification answers; routine code edits do not need a confidence score bolted onto them.

---

## 2. Ecosystem identity invariant — an agent system, not an LLM build

`[CARRIED]` `GEMINI.md:31-40`

Despite the workspace folder name `NGO AI LLM` and the remote `https://github.com/Anant1asha/NGO-AI-LLM.git`, this ecosystem **does not build, pre-train, or fine-tune large language models**.

It is an **Autonomous AI Agent Ecosystem (AASHA AIOS)** comprising:

- **Multi-agent orchestration** — seven specialised agents (`IngestAgent`, `AnalysisAgent`, `DesignAgent`, `AssessmentAgent`, `LLEAgent`, `QAAgent`, `BrowserTesterAgent`) in `agents.json`, governed by Pāṇinian Kāraka decision compilation and Chāṇakya HIL guardrails.
- **Multi-tier persistent memory** — Serena MCP local memory (`.serena/memories/`), Mem0 dual-write episodic store (`.scratch/mem0_store.json`), SQLite operational knowledge graph (`aasha_operational.db`), and the Graphify AST codebase graph (`graphify-out/graph.json`).
- **Deterministic tools and foundation engines** — PyMuPDF extraction, the LaTeX math insulator (`packages/aasha-rules/math_insulator.ts`), KaTeX typography inliners, procedural Web Audio tone generation, headless Chrome CDP automation (`scripts/automated_browser_verification.js`), and the 20+ prebuilt simulation foundations (F01–F20 in `experience_registry/registry.json`).
- **Curated resources and reusable contracts** — Section 24 YAML Reusable Content Contracts (`content/contracts/`), bilingual Hindi dictionary databases (`aasha_dictionary_db.json`), NCERT syllabus catalogues (`ncert_books.json`).
- **Procedural skills** — capability runbooks under `.agents/skills/`.

External models are consumed strictly as **swappable reasoning engines** via `packages/llm-router/openrouter_client.ts`. They are intelligence utilities, not the system being built.

Any subagent, script, or reasoning turn that assumes this repository trains, builds, or fine-tunes an LLM violates this invariant.

---

## 3. Safe file operations

`[CARRIED]` `GEMINI.md:42-50`, with the Windows-PowerShell specifics retargeted.

You are forbidden from executing destructive shell commands (`rm -rf`, bulk `Remove-Item`) without explicit safeguards. Before any bulk file move, rename or deletion:

1. Verify the project is under version control. If it is not, warn the user of the risk and ask them to back up.
2. Never chain a destructive command immediately after a move or copy without checking the preceding command's success (exit code, and that the target exists).
3. Prefer safe, atomic operations and built-in tools over raw shell scripting for file management.
4. `[ADAPTED]` "Built-in tools" now means Superbrain's own file tools — `superbrain_createFile`, `superbrain_replaceInFile`, `superbrain_editFiles`, `superbrain_deleteFile` (journaled, recoverable). Do not write files with shell redirection.
5. `[ADAPTED]` The shell here is **Git Bash**, not Windows PowerShell. POSIX syntax; the null device is `/dev/null` (`2>nul` writes a file literally named `nul`). Verify `.gitignore` before staging in repositories containing sub-repositories or `node_modules`.
6. `[SUPERSEDED]` The `$env:GIT_SEQUENCE_EDITOR` / UTF-8-without-BOM recipe targeted PowerShell 5.1. Git Bash `printf` and Superbrain's own git tools do not carry that BOM failure mode. If a non-interactive rebase is ever needed, still write the todo file without a BOM.

---

## 4. Public repository zero-leakage and privacy

`[CARRIED]` `GEMINI.md:52-63` — **full detail lives in `.superbrain/rules/public-repo-privacy-and-security.md`** (migrated, loads when matching files are in play). Summary of the invariant:

1. Assume every ecosystem repository (`NGO-AI-LLM`, `Aasha-AI`, `aasha-studio`, `NGOweb`, `web`) is **100% public**. Never assume a repo or branch is private.
2. Never stage, commit or push provider API keys, GitHub PATs, cryptographic private keys, session cookies or browser dumps, live `.env` files, or PII. Only a sanitised `.env.example` with empty placeholders is permitted.
3. Before staging, confirm `.gitignore` blocks `node_modules/`, `scratch/`, `**/.scratch/`, `*cookie*`, `*.cookie`, `*.zip`, `.env`, `secrets/`. Never `git add .` / `git add -A` blindly.
4. Mock secrets in test fixtures must be split by string concatenation (`'github_pat_' + 'dummy_...'`) so runtime regexes still fire while static scanners and push protection are not tripped.
5. If an unpushed commit introduces a scanner pattern, rewrite it before pushing (`git rebase -i <parent_sha>`) so zero blobs in history retain the literal.

---

## 5. ADR-001 bounded implementation and release gate

`[CARRIED]` `GEMINI.md:65-67`

Implementation of approved **ADR-001** (Option C Provider-Neutral Capability Runtime) proceeds strictly in bounded, test-driven phases, Gate 0 through Gate 6, preserving all existing control-plane release gates, human approval boundaries, and immutable evidence ledgers. Gate 1 through Gate 5 run with autonomous development execution (no intermediate HIL); human verification is mandated at Gate 6 before promotion, merge, or production release.

Capability discovery does not grant execution permission. Test doubles are restricted to test environments and must never emit production certification hashes.

---

## 6. Ephemeral runtime cache and local DB isolation

`[CARRIED]` `GEMINI.md:69-71`

Local databases, caches and sync files (`aasha_local_memory.json`, `offline_sync.db`, `aasha_operational.db`, `.scratch/mem0_store.json`) hold live runtime state from test executions. They are transient artifacts and must remain untracked and git-ignored. Staging an active cache database into Git history is prohibited.

---

## 7. Hosted orchestration network boundary

`[CARRIED]` `GEMINI.md:73-75`

Developer workstations must never expose unauthenticated inbound listening ports or reverse tunnels (`ngrok`, open HTTP/TCP listeners) to hosted n8n or cloud orchestrators.

All orchestration with hosted n8n (`https://airtribe.app.n8n.cloud`) runs strictly over authenticated outbound MCP (`mcp-remote` with Bearer auth) or GitHub-mediated workflows (webhooks, issues, pull requests). Pre-authenticated OAuth callbacks (`http://127.0.0.1:...`) are transient client redirects and must never leave a lingering listening service.

---

## 8. Node.js v24 ESM type-import and path

`[CARRIED]` `GEMINI.md:77-80`

1. TypeScript interface/type imports in ESM files must use explicit `import { type ... }` to avoid Node v24 `SyntaxError: Does not provide an export named`.
2. Provide runtime stub exports for dual-role symbols (`export const Symbol = {}`).
3. Guard directory paths with `(typeof __dirname !== 'undefined' ? path.resolve(__dirname, '..') : process.cwd())` or `fileURLToPath(import.meta.url)`.

---

## 9. TypeScript dual-root bundler resolution

`[CARRIED]` `GEMINI.md:82-84`

1. In this multi-folder workspace both the workspace root and the package directory must contain a synchronised `tsconfig.json` with `"types": ["node"]`, or the language server degrades into DOM-only mode.
2. Scripts run through `tsx` or modern ESM runners use `"moduleResolution": "bundler"` and `"allowImportingTsExtensions": true`. Do not force artificial `.js` extensions onto uncompiled `.ts` imports.

---

## 10. Daemon process and event loop

`[CARRIED]` `GEMINI.md:86-89`

1. Any long-lived Node daemon spawned via `spawn(...)` must immediately `unref()` the process and its `stdout`/`stderr`/`stdin`.
2. Daemon client wrappers expose an explicit `stop()` / `shutdown()` lifecycle hook so test harnesses and CLIs terminate without hanging the event loop.
3. Classifiers and pre-routers support dual-path resilience: a zero-token local heuristic/regex path (<1 ms) for cold or unactivated Python environments, alongside the resident daemon pipeline.

---

## 11. Windows registry environment access

`[CARRIED]` `GEMINI.md:91-94`

1. Scripts writing persistent user environment variables (`[System.Environment]::SetEnvironmentVariable(..., "User")` on `HKCU:\Environment`) must wrap the registry call in `try`/`catch`.
2. On restricted write access, report an advisory and continue by applying the change to the active session (`$env:PATH`) rather than failing setup.
3. Deduplicate registry paths (`-split ';' -notcontains $binDir`) before prepending or appending.

---

## 12. Python CLI runner PYTHONPATH injection

`[CARRIED]` `GEMINI.md:96-98`

When a TypeScript/Node runner spawns Python with `-m <package.cli>`, it must prepend the target source directory (e.g. `path.resolve(pipelineDir, 'src')`) to `env.PYTHONPATH` in `resolveEnvironment()`. Never assume the active interpreter has the package installed in editable (`-e`) mode.

---

## 13. Teaching language and chapter contract mandate

`[CONDITIONAL]` — chapter compilation only. `GEMINI.md:100-105`

**AASHA Universal Teaching Language System.** When transforming or creating educational content, follow the guidelines in `docs/AASHA_TEACHING_GUIDE.md`.

**Chapter building mandate.** Before building or enhancing any chapter, the Section 24 YAML Reusable Content Contract and Mandatory Resource Match Report are generated and enforced via `packages/chapter-contract-manager.ts` (`npm run chapter:init -- <Subject> <Class> <Topic>`). The `AASHAGatekeeper` verifies or creates the contract in `content/contracts/` to guarantee prebuilt foundation reuse (F01–F20), curriculum intent mapping, and 4-tier hint schemas before any HTML modification. Do not skip the planning phase for new chapters.

---

## 14. Universal scope and experience reuse — never build from scratch

`[CONDITIONAL]` `GEMINI.md:107-113`

1. **Universal curriculum scope.** AASHA covers any school, any board (CBSE, ICSE, NCERT, State Boards), any class (K–12), any subject. All subjects map exercises, 4-tier progressive hints ($H_1 \rightarrow H_4$) and misconception diagnostics (`m`) into Section 24 Content Contracts (`contract.yaml`). Subject generator adapters (`MathSimGenerator`, `ScienceSimGenerator`, `GeographyMapGenerator`, `LanguageGrammarGenerator`, `CodingRunnerGen`) emit standardised `<aasha-sim>` Web Component contracts.
2. **Never build from scratch.** Before creating any educational game, simulation, virtual lab or interactive exercise during fresh textbook PDF ingestion, query `experience_registry/registry.json` and generate a Resource Match Report (`npm run admin:match -- <Subject> <Class> <Topic>`). Newly created engines are registered back into the registry for cross-subject reuse.
3. **Full prebuilt foundation utilisation.** Adapt and reuse from the F01–F20 catalogue (Escape Run, MicroSims, All Science Sims, PhET, Lightbot, MathFluency, Wiki Physics Game, Physics Notebook, Escapp, QuestJS, Squiffy, GeoGuess, Learn Worldmap, Geographical Adventures, The Long Game, FinanceGame/LearnBu, Code for Life, Secure Code Game, Chocolate Broccoli Challenge, GameBox/Mini Games) plus prebuilt JSXGraph, KaTeX and canvas engines.
4. **Standard experience contract.** Every interactive simulation implements or adapts `AashaExperienceContract` (`mount`, `getState`, `reset`, `destroy`, `telemetry`).
5. **Same-frame mobile viewport.** Concept card and simulation fit one mobile viewport without scroll. Minimum touch target 44×44 px.
6. **GPL-3.0 isolation.** GPL-licensed foundations (F04 PhET, F09 Escapp, F17 Code for Life) use only the `EXTRACT` or `INSPIRE` strategy — mathematical models, mechanics and public assets extracted and wrapped inside `<aasha-sim>` adapters — to prevent copyleft contagion into the MIT core chapter files.

---

## 15. Zero-token bleed and circuit breaker

`[CARRIED]` `GEMINI.md:115-171`

1. **Paid Gemini API tokens are locked out for all interactions** — batch, automated, and interactive alike. `ALLOW_PAID_GEMINI_FALLBACK=false` must be set in `Aasha-AI/.env` at all times.
2. All tasks route through the free OpenRouter pool first (`meta-llama/llama-3.1-8b-instruct:free`, `nvidia/nemotron-3.5-lightning:free`, `google/gemini-2.0-flash-exp:free`), with a mandatory 3-second backoff on 429.
3. Never chain automatic fallbacks into paid Gemini keys under any circumstance — error, timeout or rate limit. Escalation path: Tier 1 (OpenRouter free) → Tier 2 (Claude Code) → Tier 3 (explicit authorisation only).
4. Gemini paid API is a RESERVE, not a convenience fallback.

### 3-tier routing decision tree

```text
Is this task in the explicit Tier 3 authorised list?
  YES -> Gemini API (paid). Log usage. Require explicit user authorisation.
  NO  ->
Is this a multi-file code synthesis, chapter HTML generation, TypeScript scripting,
  plugin dev, or file edit >200 lines?
  YES -> Claude Code (Tier 2). claude-3-5-sonnet or claude-haiku.
  NO  ->
OpenRouter Free Pool (Tier 1).
  -> Rotate: llama-3.1-8b:free -> nemotron-3.5:free -> gemini-2.0-flash-exp:free
  -> 3s backoff on 429. Max 3 retries -> escalate to Tier 2. NEVER to Tier 3.
```

- **Tier 1 — OpenRouter free pool, default for all routine work:** chat replies, file reads, grep, directory listing, registry queries, graphify queries, code edits under 200 lines, admin commands, MCP result summarisation, math insulation runs, YAML contract validation.
- **Tier 2 — Claude Code, all coding tasks:** multi-file refactoring, chapter HTML generation, TypeScript/Node synthesis, `packages/` / `benchmarks/` / `scripts/` development, MCP server dev, CDP automation scripts, and any Tier 1 task that fails three 429s.
- **Tier 3 — Gemini reserve, exhaustive list:** textbook PDF multimodal vision ingestion; full-chapter long-context synthesis requiring >100 K tokens; the final Dual-Benchmark L-Truth + CDP certification run (Super Admin authorised); tasks explicitly authorised via `/boost`. Never for chat, reads, grep, edits under 200 lines, registry lookups, admin commands, or MCP status checks.

**Dual Gemini key scope.** *Key A* — multimodal vision and long-context reserve; strictly locked out of routine chat and minor edits. *Key B* — Super Admin deep reasoning, architecture synthesis and agent builds; routine tasks still route through Tier 1.

**Cascade rules, no exceptions.** Tier 1 → Tier 2 on a code task, three 429 retries, or an edit over 200 lines. Tier 2 → Tier 3 only on `/boost` or explicit PDF ingestion. **Tier 1 → Tier 3 direct skip: prohibited. Auto-fallback to paid Gemini on any error: prohibited.**

Implementation `packages/llm-router/openrouter_client.ts` · Guard `assertGeminiAuthorized(taskType)` · Config `Aasha-AI/.env` · Skill `.agents/skills/api-routing/SKILL.md` (now also `.superbrain/rules/api-routing-policy.md`).

`[ADAPTED]` For this agent specifically: *this* conversation is not one of the routed tiers — the user selects the model. The routing table governs code the repo writes and any internal pipeline call, not Superbrain's own turn. Superbrain's web search is additionally capped at 10 searches per chat, each counted against the user's plan.

---

## 16. Laya System 1 zero-token pre-router

`[CARRIED]` `GEMINI.md:173-176`

1. All unclassified incoming prompts and pipeline requests are evaluated by the local resident Laya classifier (`packages/llm-router/laya_classifier.ts`) before any external LLM completion call.
2. Indic scripts (Devanagari, Bengali, Tamil, Telugu) are detected via `laya.detect_script()` in under 1 ms and routed straight to `'lle-indic'` without spending tokenizer or LLM tokens.
3. In production and development, Laya runs as a persistent stdio daemon (`laya_task_classifier.py --daemon`) for sub-50 ms repeat inference on CPU, backed by an instant in-memory regex fallback if the process is unavailable.

---

## 17. System instructions and structured JSON

`[CARRIED]` `GEMINI.md:178-180`

1. All model API calls, subagent prompts and pipeline invocations must pass explicit system instructions defining role parameters, JSON output schemas and truth-seeking standards.
2. All JSON outputs (chapter specs, content maps, assessment items, LLE dictionary entries) are verified against their TypeScript interfaces or JSON schemas (`ContextBus.validateOutput()`) before persistence.

---

## 18. Serena and local agentic memory

`[CARRIED]` `GEMINI.md:182-187` — detail also in `.superbrain/rules/serena-mcp.md`.

1. **Serena first.** Serena MCP (`.serena/memories/` via `read_memory`, `write_memory`, `list_memories`) is the primary default local memory for the ecosystem, persisting architectural decisions, conventions, completion criteria and domain rules. Subagents and pipeline tasks query Serena before making external context requests.
2. **AST and offline stores.** Graphify AST (`graphify-out/graph.json`) gives symbol-level codebase structure; local episodic stores (`.scratch/mem0_store.json`, `aasha_operational.db`) hold offline preferences and telemetry.
3. **Zero-bleed memory sharing.** Cross-turn context reuse reads persistent local Serena snapshots rather than re-sending prompt tokens.
4. **Self-healing activation.** If Serena returns `No active project` because of an arbitrary launch directory, call `activate_project: { "project": "NGO AI LLM" }` and retry in the same turn.
5. **Master wake-up intent.** `/jagiye-maakiran` (or the phrases `jagiye maakiran` / `जागिए माँ किरण`) triggers full-system priming, memory graph health audit and AST verification.

`[ADAPTED]` Serena and Graphify are MCP/local stores, not Superbrain subsystems. This agent's code search is TokenFold. If the Serena MCP server is not connected, say so — do not pretend a memory read succeeded.

---

## 19. Pre-LLE mathematical insulation

`[CARRIED]` `GEMINI.md:189-190`

Before bilingual dictionary wrapping (`rt()` / `window.WM`), shield all LaTeX (`\( ... \)`, `$$ ... $$`, `$...$`) and single-letter algebraic variables with `__AASHA_MATH_X__` placeholders via `packages/aasha-rules/math_insulator.ts` and `<span class="math-var" data-math="true">`, to prevent math corruption and false dictionary lookups. Never expose raw formulas to dictionary tokenisation.

---

## 20. Dual-benchmark quality certification gate

`[CARRIED]` `GEMINI.md:192-195`

Before publishing or declaring any chapter complete, it must pass both:

1. `node benchmarks/qa_ltruth_benchmark.js` — 100/100, zero spoilers in misconception explanations (`m`), zero math-rt collisions.
2. Headless Chrome CDP automation (`automated_browser_verification.js`) — zero console errors, 100 % word-tap modals opening with valid Indic definitions, canvas presence, continuous 5-step navigation.

`[ADAPTED]` A test claim still requires output showing tests actually executed. Exit code 0 alone proves nothing — a filter that matches nothing exits 0.

---

## 21. Hindi-focused bilingual substrate

`[CARRIED]` `GEMINI.md:197-199`

1. **Hindi is the sole active Indic language** for bilingual word-tap popups and conceptual definitions (`window.WM`). Other regional languages stay deferred until Hindi is complete, verified and insulated.
2. **Pre-LLE math insulation** as in §19 — never expose raw math to dictionary tokenisation.

---

## 22. Multi-agent execution modes

`[CARRIED]` `GEMINI.md:201-205`

1. **Autonomous worker** — headless background pipeline, Ingest → QA with automated self-repair on benchmark failure.
2. **Interactive gate (`--interactive`)** — pauses after Section 24 contract creation for Super Admin review before HTML compilation.
3. **Batch folder runner (`--batch-dir`)** — processes directories of textbook PDFs under zero-token-bleed free model rotation.

---

## 23. Simulation web component and telemetry contract

`[CARRIED]` `GEMINI.md:207-210`

1. Every interactive simulation is wrapped in the universal `<aasha-sim>` Web Component implementing `AashaExperienceContract` (`mount`, `getState`, `reset`, `destroy`, `telemetry`).
2. `v6_compiler.ts` verifies non-destructive `destroy()` handlers (pausing `requestAnimationFrame` and interval timers without DOM tearing) before emitting the final single-file HTML bundle.
3. Simulations communicate via bubbling CustomEvents (`aasha:telemetry`, `aasha:state_change`) feeding the misconception diagnosis engine without revealing answers.

---

## 24. Balanced runtime lifecycle (≥ 4 GB RAM)

`[CARRIED]` `GEMINI.md:212-213`

Target devices have ≥ 4 GB RAM. Never perform destructive DOM tearing or canvas wiping on card transitions. Implement non-destructive `destroy()` / `pause()` (halt `requestAnimationFrame` loops and interval timers to save CPU and battery) and `resume()` to preserve simulation state and WebGL/Canvas buffers.

---

## 25. Smart dual inlining and the 20 MB child-artifact limit

`[CARRIED]` `GEMINI.md:215-217`, expanded by §31.

1. Inline raw JavaScript in `<script>` and CSS in `<style>` to save 33 % Base64 overhead. Reserve Base64 data URIs for binary assets only (images, audio, fonts).
2. The self-contained chapter file ceiling is 20 MB, with SHA-256 local disk caching and 5-second network timeouts.

---

## 26. Full exercise utilisation and gamified 3-tier scaffolding

`[CARRIED]` `GEMINI.md:219-221`

1. 100 % of textbook exercises in the chapter PDF are extracted and mapped into the 3-tier gamified assessment (Warm-up `#section-warmup` → Deep Dive `#section-deep_dive` → Boss Challenge `#section-boss`). Zero dropped exercises.
2. Misconception diagnostics (`m` attribute) and 4-tier progressive hints (H1 hook → H2 concept → H3 formula → H4 intermediate step) are pre-embedded with zero spoilers per the L-Truth standard.

---

## 27. HIL teacher console and instant browser preview

`[CARRIED]` `GEMINI.md:223-224`

The `multi-agent-tui` console enforces the 4-pillar pedagogical audit, prints a concise Hindi summary (शिक्षक के लिए सारांश) for non-technical educators, and offers instant browser verification on `[O]` before final `[S]` sign-off.

---

## 28. Question schema and distractor quality

`[CARRIED]` `GEMINI.md:226-233`

Every question in exercise banks and gamified assessments passes `QuestionSchemaValidator`:

1. **Zero spoilers** — no verbatim, numerical or phrase leaks (`is`, `giving`, `becomes`, `instead of`, `to get`, `yielding`, `result is`, `should be`).
2. **High-quality misconception** — the `m` field is non-empty, non-trivial (>15 chars), diagnoses the specific procedural or conceptual error, and uses no negative or discouraging phrasing.
3. **4-tier scaffolding** — hints H1–H4 scaffold attention, relationship, strategy and intermediate step with no final-answer spoiler.
4. **Insulated math comparison** — normalise Unicode dashes and LaTeX formatting (`\frac`, `\sqrt`); match short tokens with regex word boundaries.
5. **No evaluation leakage** — `m` never includes arithmetic that evaluates to the correct answer value (avoid "yields 2", "gives 4", "= -5" when that matches the target).
6. **Pre-ingestion L-Truth gate** — validate distractor explanations against `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i` **before** persisting to `contract.yaml`, gating compilation until all four hint tiers pass.

---

## 29. Dual execution topology

`[CARRIED]` `GEMINI.md:235-255`, retargeted.

The ecosystem enforces a strict split to avoid token bleed, slash-command parsing errors and interrupted background tasks.

**Scenario A — standalone CLI terminal (direct Anthropic key, heavy operations).** Native OS terminal running the `claude` binary with `ANTHROPIC_API_KEY` set. Assigned: multi-agent long-running workflows, heavy multi-chapter refactoring, full AST graph rebuilds, multi-agent team reviews, and live TUI progress monitoring. Never run heavy ephemeral multi-agent workflows inside a third-party extension proxy, where process-boundary recycling can abort subagents.

**Scenario B — VS Code extension via the 9Router proxy, routine development.** Routed through the local `9router` gateway (`http://localhost:20128/v1` → `ag/gemini-3.8-flash` / `claude-combo`). Assigned: routine development, targeted fixes, file edits, zero-token pre-routing via Laya System 1 (`npm run laya:test`), and deterministic pipeline execution through the Unified Root Orchestrator — `npm run orchestrator` / `npm start`, `npm run tui`, `npm run test:all`, `npm run test:ltruth`, `npm run chapter:compile`, `npm run audit:gateway`, `npm run laya:test`. Do not type CLI-only slash commands such as `/workflows` in this environment.

`[ADAPTED]` **Superbrain occupies a third position, not either of these.** It is a separately licensed agent with its own model picker, its own approval gate, and its own shell. Do not assume the 9Router gateway or `ANTHROPIC_API_KEY` is what is serving this chat, and do not issue Claude-Code-specific slash commands here — Superbrain's own commands live in `.superbrain/skills/` and its built-ins are `/init`, `/create-skill`, `/create-rule`.

---

## 30. Multi-aspect-ratio same-frame responsiveness

`[CARRIED]` `GEMINI.md:257-266`

Chapter cards and simulations must fit the same viewport frame with no scrolling across:

- 16:9 budget Android (360×640)
- 19.5:9 modern iPhone (390×844, 393×852)
- 20:9 modern Galaxy/Pixel (412×915, 360×800)

Rules:

1. `.screen { min-height: 0; }` with height-tiered media queries clamping `.concept-def` (80 / 110 / 125 px) and `.sim-canvas` (92 / 115 / 125 px).
2. `.preset-bar` is a single-row horizontal swipe (`flex-wrap: nowrap; overflow-x: auto; touch-action: pan-x;`).
3. Dynamic canvas scaling via `fitCanvas(canvas)` with CSS logical pixel sizing and DPR adaptation.
4. Chrome CDP verification asserts `scrollH <= winH + 5` and ≥ 44×44 px touch targets across all viewports.

---

## 31. Automated end-to-end verification and screenshots

`[CARRIED]` `GEMINI.md:268-274`

When the user asks for verification on their behalf:

1. Never emit plain-text instructions or ask the user to test manually.
2. Launch a local in-process HTTP server plus a headless Chrome CDP client (`--remote-debugging-port`).
3. Programmatically execute the interaction workflows: profile onboarding, chapter switching, bilingual word-tap dialog, manipulative clicks, progressive hints, 60 FPS practice loops, match pairings, evidence sync.
4. Capture PNG screenshots via `Page.captureScreenshot` at each milestone into `<appDataDir>/brain/<conversation-id>/`.
5. Embed them in `walkthrough.md` using GFM carousel blocks and absolute paths.

---

## 32. Chrome CDP global scope leakage

`[CARRIED]` `GEMINI.md:276-277`

Top-level `const`/`let` declared in one `Runtime.evaluate` persists into later evaluations. Wrap every CDP-evaluated script in a block `{ ... }` or an IIFE to avoid `Identifier has already been declared`.

---

## 33. Bounded sliding-window complexity (sub-50 ms)

`[CARRIED]` `GEMINI.md:279-280`

Live telemetry processing, dynamic difficulty adjustment and mastery calculations must be $O(1)$ in session length. Historical scans are bounded to a sliding window of the latest $K = 100$ events, preventing $O(N^2)$ degradation during bursts.

---

## 34. Synchronous DOM state binding

`[CARRIED]` `GEMINI.md:282-283`

Simulation manipulatives must never decouple internal canvas or algebraic state from visible DOM readouts. Every interaction synchronously updates both the canvas and the accompanying text (fraction strings, switch labels) in the same call stack.

---

## 35. Mobile bottom-navigation clearance and opaque backdrop

`[CARRIED]` `GEMINI.md:285-288`

1. Fixed bottom bars (`.bottom-nav`, `.nav-bar`) use `background: #ffffff` (or the fully opaque theme surface) with `backdrop-filter: blur(20px)` and `box-shadow: 0 -4px 16px rgba(0,0,0,0.05)`. Never a semi-transparent navbar that lets content ghost through.
2. Scrollable containers (`main`, `.screen`) enforce `padding-bottom: calc(96px + env(safe-area-inset-bottom, 16px))` so content clears the bar.

---

## 36. Canonical IR and the stateful V6 engine

`[CARRIED]` `GEMINI.md:290-293`

1. **Dual authoring/execution.** Specialist agents produce YAML (`chapter_spec.yaml`), normalised deterministically by the IR Assembler (`packages/canonical-ir/ir_assembler.ts`) into strict Canonical IR (`canonical_ir.json`).
2. **Opaque identity and math insulation.** Canonical entities use opaque namespaces (`obj:`, `cpt:`, `misc:`, `cnt:`, `exp:`, `evd:`, `cap:`, `ast:`). LaTeX and single-letter variables are insulated via `MathInsulator` before dictionary tokenisation.
3. **V6 event bus and TEAS.** Runtime execution routes through `V6RuntimeBus` (`packages/v6-engine/v6_runtime_bus.ts`), logging immutable semantic events to client IndexedDB and computing 2-tier TEAS weighted mastery (60 % historical + 40 % recent).

---

## 37. Evidence gap waiver and non-fabrication

`[CARRIED]` `GEMINI.md:295-297`

When a requested audit or forensic document is missing from repository evidence, never fabricate page names, block findings or visual-layout claims. Record an explicit Evidence Gap Waiver in `implementation_plan.md` and gate page-level UI changes until the audit arrives via a governed HIL change request.

---

## 38. Bounded 2-tier repair loop and downstream quarantine

`[CARRIED]` `GEMINI.md:299-304`

1. **Invocation ceiling** — one initial invocation plus at most two autonomous repairs (three total).
2. **Quarantine** — on exhaustion, activate quarantine, emit a `QuarantinePacket` with `actionRequired: 'SUPER_ADMIN_INTERVENTION'`, raise `QuarantineError`.
3. **Downstream blocking** — stages may not consume corrupt or unverified state.
4. **Epistemic memory preservation** — quarantined output never enters the `ContextBus` experience memory bank.
5. **Dual-benchmark gate** — see §20, plus the five-viewport `scrollH <= winH + 5` assertion.

---

## 39. Fork-join concurrency and upstream freeze

`[CARRIED]` `GEMINI.md:306-311`

1. `DesignAgent`, `AssessmentAgent`, `LLEAgent` run concurrently via `Promise.all()`.
2. `AnalysisAgent` completes first; its snapshot is deeply cloned and recursively frozen (`deepFreeze()`). A shallow `Object.freeze()` is insufficient.
3. Parallel branches may read frozen upstream state but must not mutate it.
4. Deterministic join order: `JOIN_ORDER = ["analysis", "design", "assessment", "lle"]`. Unordered traversal or race-dependent assembly is prohibited.
5. On branch failure, downstream synthesis is blocked and failure state preserved in the quarantine packet. Standard `Promise.all()` does **not** cancel running siblings — halting downstream synthesis is required; sibling cancellation is not claimed.

---

## 40. Anti-spoiler assessment

`[CARRIED]` `GEMINI.md:313-316`

1. Verbal misconception diagnostics live in the `m` attribute of each incorrect option.
2. Forbidden spoiler tokens: `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`.
3. The L-Truth ground-truth gate requires the diagnostic to name the student's cognitive error without leaking the target answer, an arithmetic step that yields it, or discouraging phrasing.

---

## 41. LLE auto-caching of Indic terms

`[CARRIED]` `GEMINI.md:318-319`

When LLE Cascade Layer 2 (Google Translate) or Layer 3 (LLM) translates a missing term, it must append and persist the entry to `hi.json` (UTF-8, no BOM). Later runs reuse the cached Layer 1 entry for zero token bleed and sub-millisecond execution.

---

## 42. AIOS autonomous governance and zero-rewrite invariants

`[CARRIED]` `GEMINI.md:321-342`

1. **Autonomous generation boundary (`GENERATION_HIL = FALSE`)** — between `CREATED` and `READY_FOR_REVIEW`, execution is fully autonomous. No interactive prompts, mid-pipeline pauses or intermediate sign-offs. Teachers and reviewers enter strictly post-generation via `[Approve & Deploy]` or `[Request Revision]`.
2. **Zero-rewrite / zero-regression (`ZERO_REWRITE_ZERO_REGRESSION = TRUE`)** — `packages/chapter-contract-manager.ts`, `packages/aasha-rules/math_insulator.ts`, `packages/v6-engine/v6_compiler.ts`, `experience_registry/registry.json` and the benchmark scripts are **frozen authorities**. Never rewrite or duplicate them for aesthetic or architectural cleanliness. Integrate through thin typed anti-corruption adapters (`packages/adapters/contracts.ts`, `packages/adapters/aios_orchestrator.ts`).
3. **Universal curriculum neutrality** — board-neutral, level-neutral, subject-neutral. Never infer curriculum facts from model knowledge. Missing evidence stays `UNKNOWN`. `UNKNOWN > HALLUCINATION`.
4. **Assessment-preserving game orchestration** — F01 Escape Run is the narrative/progression shell, not a pedagogical constraint. 100 % of textbook exercises are preserved (`SOURCE_EXERCISE_IDS == CONTRACT_EXERCISE_IDS`). Multi-step proofs, derivations and subjective questions live in specialised sanctuaries (e.g. Scholar Chamber) evaluated by TEAS on reasoning quality over speed.
5. **Opaque sandboxed preview security** — preview iframes enforce `sandbox="allow-scripts"` **without** `allow-same-origin`. `AASHA_PREVIEW_BRIDGE` messages are validated by source-window identity, a cryptographically strong session nonce, artifact hash assertion and strict event sequence schemas.
6. **Bounded autonomous repair and terminal quarantine** — see §38; each repair targets the minimal broken dependency closure recorded in a `DiagnosticDossier`.
7. **Unified platform, separate trust zones** — brand site and Teacher Studio share one Next.js app (`annanth-aasha-foundationweb`) with route-group boundaries: public marketing under `/(public)` with pre-certified demos, authenticated teacher workspace under `/studio/*` with durable SSE job tracking and side-by-side audit consoles.

---

## 43. Canonical authority graph (KARAKA-UNIFIED-1.0)

`[CARRIED]` `GEMINI.md:344-370`

```text
SOURCE_EVIDENCE
  → GRAPHIFY_AST
  → SECTION_24_CONTRACT
  → TEAS
  → EXPERIENCE_REGISTRY / RESOURCE_LIBRARY / GLOBAL_LLE_LIBRARY
  → AIOS
  → QA_ENGINE
  → HATCHABLE_EVIDENCE
  → HIL
  → DEPLOYMENT_GATE
```

`SOURCE_EVIDENCE` immutable content truth · `GRAPHIFY_AST` structural/semantic representation · `SECTION_24_CONTRACT` canonical learning and assessment contract · `TEAS` mastery and assessment authority · `EXPERIENCE_REGISTRY` certified reusable experience · `RESOURCE_LIBRARY` reusable capability/resource (19+ foundations) · `GLOBAL_LLE_LIBRARY` reusable vocabulary · `AIOS` orchestration/execution · `QA_ENGINE` objective certification · `HATCHABLE_EVIDENCE` durable state, evidence, artifacts and telemetry persistence (not higher semantic authority than source, TEAS or QA) · `HIL` human review strictly after certification · `DEPLOYMENT_GATE` explicit release authority.

Never let a lower layer silently override a higher-authority layer.

---

## 44. Governed state machine

`[CARRIED]` `GEMINI.md:372-377`

- **Lifecycle:** `CREATED → QUEUED → INGESTING → STRUCTURING → GENERATING → COMPILING → QA → CERTIFIED → READY_FOR_REVIEW → APPROVED → DEPLOYED`
- **Revision loop:** `READY_FOR_REVIEW → REVISION_REQUESTED → NEW_IMMUTABLE_VERSION → QA → CERTIFIED → READY_FOR_REVIEW`
- **Failure branch:** `ANY_STAGE → FAILED / BLOCKED / CONTRADICTED / QUARANTINED`
- **Mandatory distinctions:** `CERTIFIED ≠ READY_FOR_REVIEW ≠ APPROVED ≠ DEPLOYED`. Approval binds to the exact `artifact_hash` and never carries across versions.
- **Autonomous generation (`GENERATION_HIL = FALSE`):** AIOS runs ingestion through QA certification up to `READY_FOR_REVIEW`; HIL enters only afterwards.

---

## 45. Scope-locked 20 MB child artifact

`[CARRIED]` `GEMINI.md:379-382`

- **`CHILD_HTML5_BUNDLE_MAX_BYTES = 20_971_520`** applies **only** to the child-facing standalone offline HTML5 learning bundle (`CHILD_HTML5_BUNDLE`).
- **Exclusion list** — it does **not** apply to source PDFs, textbook sources, Graphify AST, Section 24 contracts, Hatchable storage, telemetry databases, evidence ledgers, server-side artifacts, resource libraries, global vocabulary, backend infrastructure, QA reports or version history. Resource libraries may exceed 20 MB; the compiler bundles only selected, deduplicated assets for the specific chapter.
- **Blocking gate** — `size_bytes > 20_971_520` ⇒ `CERTIFICATION = FAIL`, `RELEASE = BLOCKED`. Never delete required educational functionality to pass; optimise deterministically first (resource selection, deduplication, font subsetting, asset compression, dead-code elimination).

---

## 46. Resource-first reuse and local-first cost architecture

`[CARRIED]` `GEMINI.md:384-390`

1. **Resolution hierarchy:** `EXACT_REUSE → PARAMETRIC_ADAPT → COMPOSE → LOCAL_ADAPTATION → CERTIFIED_GENERATION → SAFE_FALLBACK`. Code generation is a last resort.
2. **Local-first precedence:** `LOCAL RESOURCE > LOCAL REGISTRY > LOCAL VOCABULARY > LOCAL EXPERIENCE > LOCAL AST/GRAPH > EXISTING CACHE > REMOTE MODEL`. Never invoke an LLM to recreate information available locally. Never re-download an identical open-source resource or regenerate an existing simulation.
3. **Capability-level assets** — resources are cross-chapter capabilities usable across subjects, topics, grades, boards and curricula, not one-off chapter code.
4. **Global LLE / vocabulary governance** — check `aasha_dictionary_db.json` before generating translations. Existing term → verify context → reuse → adapt presentation. New term → validate → record provenance → approve → persist. Never auto-promote unverified generated vocabulary into canonical knowledge.

---

## 47. Asynchronous semantic telemetry

`[CARRIED]` `GEMINI.md:392-401`

1. **`LEARNING_STATE ≠ TELEMETRY_STATE`** — telemetry failure, storage exhaustion or network latency must never interrupt child learning, assessments, simulations, games, LLE or card transitions. The learning runtime never awaits telemetry acknowledgement.
2. **Pipeline:** `CHILD_RUNTIME → SEMANTIC_EVENT → SCHEMA_VALIDATE → LOCAL_INDEXEDDB_BUFFER → CONTINUE_LEARNING → ASYNC_BATCH → SYNC → HATCHABLE_EVIDENCE → TEAS / ANALYTICS / REVIEW`.
3. **Identity** — every event binds `artifact_hash`, `version`, `event_id`, `session_id`, `client_timestamp`, monotonic `sequence_number`, `event_type`, `schema_version`. Never use "latest" as identity.
4. **Ordering** — per-session monotonic `sequence_number` is the primary logical ordering authority against clock drift; timestamps are secondary metadata. Sequence numbers order within a session and do not solve cross-device temporal synchronisation.
5. **Performance and durability** — emission is non-blocking, target < 2 ms. IndexedDB (`aasha_telemetry_db`) is the durable buffer; the in-memory queue is a non-blocking emergency fallback and is **not** durable evidence. If storage is unavailable, continue learning, record degradation, attempt recovery, never fabricate persistence. Batch sync runs in the background with bounded exponential backoff.
6. **Multi-signal misconception convergence** — telemetry is evidence, not truth. A single wrong answer is never a misconception. TEAS aggregates across `OBSERVED`, `SIGNAL`, `CORROBORATED`, `PROBABLE`, `UNKNOWN`, and `UNKNOWN` is a valid and preferred state when evidence is insufficient.

---

## 48. One-time covering, multiple-time practice

`[CARRIED]` `GEMINI.md:403-406`

1. Initial concept introduction (`CONCEPT_COMPLETED`) is tracked separately from repeated retrieval practice.
2. **Local session adaptation** — hint escalation H1→H4, question parameter variation, drill repetition, simulation parameters and vocabulary reinforcement execute locally in client memory and IndexedDB without mutating the certified artifact, `artifact_hash` or version identity.
3. **Systemic content optimisation** — when aggregate evidence reveals a genuine curriculum bottleneck or content bug, AIOS compiles candidate $v_{N+1}$ (`parent_hash = hash(v_N)`), which must pass full dual-benchmark QA (static L-Truth + dynamic CDP + offline + parity) to reach `CERTIFIED → READY_FOR_REVIEW`, and requires explicit Super Admin HIL approval. Never silently mutate or auto-deploy production artifacts.

---

## 49. Super Admin analytics and longitudinal mastery grid

`[CARRIED]` `GEMINI.md:408-421`

1. **Ingestion cadence** — bounded batched ingestion with 24-hour consolidation plus an on-demand, rate-controlled `[Sync & Refresh Analytics]` trigger.
2. **4-pillar longitudinal model** — *Concept Coverage %* (students completing initial introduction), *Practice Velocity* (repeat sessions per student over 7 and 30 days), *Attempts-to-Mastery* (average attempts to ≥ 80 % TEAS composite), *TEAS Retention Health %*: $\text{RetentionHealth} = 0.60 \times \text{HistoricalScore} + 0.40 \times \text{RecentScore}$

   Coefficients are locked by governance; report a contradiction if an alternative formula is proposed.

3. **Actionable remediation suite** — derived strictly from corroborated evidence for at-risk cohorts: `[Generate Hindi Teacher Practice Plan]` (15-minute classroom intervention), `[Spawn Micro-Drill Pack]` (5-question offline refresher that does not alter the core chapter), `[View Misconception Breakdown]` (diagnosed procedural patterns from `m`). Low-confidence signals stay `UNKNOWN`.

---

## 50. Immutable versioning, local recovery and git policy

`[CARRIED]` `GEMINI.md:423-427`

1. **Content-addressed lineage** — $v_1 \rightarrow v_2(\text{parent\_hash} = \text{hash}(v_1)) \rightarrow \dots$, identity is `SHA-256(content)`.
2. **Local recovery** — `.scratch/versions/<artifact_id>/` holds immutable `<artifact_hash>.html` plus an append-only `version_ledger.json`.
3. **Dual durability** — Hatchable is the durable ledger where available; if unavailable, keep local snapshots, mark sync pending, and never fabricate successful persistence.
4. **Git policy** — do not initialise Git merely because immutable versioning is required. Git is optional infrastructure. Rollback changes deployment pointers only; historical certified versions remain intact.

---

## 51. Dual-track ecosystem boundary

`[CARRIED]` `GEMINI.md:429-433`

1. **Track 1 — public open-source tool (`aasha-studio`)**: standalone conversion tool and desktop app for independent teachers, schools and developers. Limited to Section 24 contract generation, simulation foundation matching, anti-spoiler L-Truth QA, and single-file offline HTML output via BYOK.
2. **Track 2 — private NGO learning and impact platform (`Aasha-AI`)**: multi-agent AIOS, grassroots learner profiling, offline student PWA sync, teacher audit console, classroom deployment metrics, field telemetry.

NGO internal data, student telemetry databases and organisation credentials must never be exported or cross-pollinated into the public open-source repository.

---

## 52. Zero-Rust prerequisite and 3-tier desktop execution

`[CARRIED]` `GEMINI.md:435-441`

Never mandate that end users or web developers install heavy compiled toolchains (Rust, Cargo, MSVC C++ Build Tools) to use or inspect the system. Enforce the 3-tier architecture:

- **Tier 1 (end users)** — prebuilt native `.msi` / `.exe` binaries compiled in the cloud via GitHub Actions on `windows-latest`.
- **Tier 2 (CLI / automation)** — a pure cross-platform Node package (`@aasha/cli`) with zero native compilation.
- **Tier 3 (local browser studio)** — `aasha studio` serves the identical React/Vite studio over a local Node HTTP server and opens Edge or Chrome.

---

## 53. Public repository decoupling, OS key vault and git privacy

`[CARRIED]` `GEMINI.md:443-446`

1. **Repository boundary** — `aasha-studio` stays isolated from internal research, monolithic zip archives and private training datasets.
2. **Hardware-encrypted BYOK vault** — user API credentials are never written to `.env` inside a repository tree. Keys live exclusively in `%USERPROFILE%\.aasha\config.json` (mode `0600`) or the Windows Credential Manager via DPAPI.
3. **Git author privacy** — commits pushed from personal workstations use the GitHub no-reply address (`<username>@users.noreply.github.com`).

---

## 54. Universal simulation navigation and non-freezing progression

`[CARRIED]` `GEMINI.md:448-451`

1. **Bubbling telemetry clearance** — simulations bubble completion telemetry (`isCorrect: true` or `competencyAchieved: true`) on goal satisfaction; the parent celebrates, updates the CTA to `"Solved! Start Assessment →"`, and unlocks progression.
2. **Graceful fallback routing** — in `v6_compiler.ts`, `advance(trigger)` must never freeze or loop on completed states. If `walker.forceNext()` returns `false`, advance automatically to `_renderAssessment()` when assessment items exist, else `_renderComplete()`.
3. **Inclusive assessment state types** — the runtime switch natively recognises `teas_assessment`, `assessment_gate`, `assessment` and `quiz`.

---

## 55. Multi-step game engine and subject collision guard

`[CARRIED]` `GEMINI.md:453-456`

1. **Never fall back to toy code** — chapters without a specialised manipulative (Ten-Frame, Pizza Fraction, Number Line Hunter, Symmetry Fold) default to the high-production `MultiStepArenaEngine` (`generateMultiStepArenaSim`) with 60 FPS Canvas/SVG, radial timer gauges, combo multipliers (×2, ×3), particle sparks and victory celebrations.
2. **Dynamic 3-tier ingestion** — the engine ingests any topic into Step 1 formula/hook → Step 2 intermediate application → Step 3 boss verification, with full bilingual Hindi + English text, or ingests custom `initialParams.rounds` directly.
3. **Compound subject collision guard** — when routing by subject name, compound subjects ("Social Science", "Social Studies") are evaluated before substring matches ("science") to prevent curriculum domain cross-contamination.

---

## 56. Pipeline job resumption and prerequisites

`[CARRIED]` `GEMINI.md:458-462`

1. **Explicit job pointer** — multi-stage batch pipelines (Python and TypeScript) resume via an explicit `--job-id <id>` rather than creating new UUIDs with empty directories.
2. **Prerequisite gate and auto-rewind** — before executing a stage via `--from-stage`, `_validate_stage_prerequisites()` runs. With `auto_rewind=True` (default), missing prerequisites cause a seamless rewind to the nearest satisfied stage (e.g. `analyze` or `ingest`), backfill in-flight, and continue. With `--no-auto-rewind` / `auto_rewind=False`, halt with `RESUME_PREREQUISITES_MISSING` and recovery guidance.
3. **Resilient work directory** — if `work/<id>` or its `source.pdf` was deleted, reconstruct the directory and restore `source.pdf` from the source path or samples directory using SHA-256 and filename resolution.
4. **Adaptive cross-mode bridging** — when resuming across `v5-engine` vs `full-synthesis`, non-destructively adapt intermediate structures (`content_map.json` ↔ `pedagogy_map.json`, `assessment_bank.json` → `assessment_suite.json`) and auto-detect mode switches. Legacy stage aliases (`extract`→`ingest`, `structure`→`analyze`, `pedagogy`→`design`, `assessment`→`assess`) normalise automatically.

---

## 57. In-process Fastify in-memory testing

`[CARRIED]` `GEMINI.md:464-466`

1. **Zero-port testing** — Fastify/Express servers guard listener startup with `if (require.main === module)` and export `{ fastify, db }`.
2. **Zero socket conflicts** — server unit and integration tests use in-process request injection (`fastify.inject()`). Never bind a physical TCP port during tests.

---

## 58. Authoritative local storage and offline durability

`[CARRIED]` `GEMINI.md:468-470`

1. **Local authoritative plane** — `offline_sync.db`, `aasha_operational.db` and `.scratch/versions/` are the primary authoritative transactional plane for student progress, evidence ledgers and artifact recovery.
2. **External cloud adapters** — PostgreSQL/Hatchable are optional outbound replication targets; their presence or absence never blocks local execution, offline learning or automated verification.

---

## 59. Continuous open-source research and harvesting

`[CARRIED]` `GEMINI.md:472-475`

1. **Runtime zero-CDN isolation** — at student runtime all simulation engines, interactives and substrates load exclusively from `assets/cdn/interactives/` and `assets/cdn/vendor/`. No external CDN links or third-party tracking scripts (`googletagmanager`, Google Analytics).
2. **Continuous research** — actively search, research and harvest high-quality open-source foundations (PhET, JSXGraph, KingsMath, CinePhysicsHQ, GeoGebra, Escapp, Code for Life).
3. **5-point quality gate** — every candidate passes 100 % offline integrity, the 20 MB bundle ceiling, cleanroom license compliance (GPL isolated under `<aasha-sim>`), mobile viewport with ≥ 44 px touch clamping, and `AashaExperienceContract` telemetry before admission to `assets/prestack_manifest.json`.

---

## 60. HIL beta model and headless orchestration boundary

`[CARRIED]` `GEMINI.md:477-480`

1. **Pre-authorised autonomous access** — during routine development, chapter compilation, testing, asset indexing and background tasks, the AIOS agent operates with full access without interactive pauses.
2. **Super Admin review boundary (Gate 6)** — HIL means synchronous review by the Super Admin strictly at Gate 6 release promotions: public git pushes, production certification hashes, destructive schema alterations.
3. **Zero browser OAuth redirects** — orchestration with hosted n8n or cloud tools uses headless stdio MCP (`scripts/n8n_mcp_server.mjs`) or authenticated webhooks. Never initiate interactive browser OAuth PKCE consent loops.

`[ADAPTED]` "Full access without interactive pauses" describes the **AASHA pipeline runtime**, not this agent's own command approval. Superbrain still gates destructive or hard-to-reverse actions on its own. Nothing in this section removes that.

---

## 61. GitHub Actions workflow expressions

`[CARRIED]` `GEMINI.md:482-485`

1. **No `${{ }}` inside `if:`** — write `if: env.KEY != ''`.
2. **No raw `secrets` in `if:`** — scope to job- or step-level `env:` and test `if: env.DD_API_KEY != ''`.
3. **Artifact ID for signing** — any action consuming uploaded release artifacts must be preceded by `actions/upload-artifact@v4` with `id: upload-step`, supplying `github-artifact-id: ${{ steps.upload-step.outputs.artifact-id }}`.

---

## 62. GitHub Actions dynamic secret indirection

`[CARRIED]` `GEMINI.md:487-491`

1. **Dynamic indexing for IDE resilience** — `env: KEY: ${{ fromJSON(toJSON(secrets))['SECRET_NAME'] }}` detaches expression evaluation from the rigid static context schema, removing false-positive "Context access might be invalid" warnings while resolving identically on runners.
2. **Preserve job-level scoping** — combine dynamic indexing with job-level `env:` so declaration and conditional execution stay separate.

---

## 63. Markdown formatting invariants

`[CARRIED]` `GEMINI.md:493-497`

1. **MD022 / MD032** — every heading and every list block is preceded and followed by a blank line.
2. **MD028** — never separate consecutive blockquotes with a blank line; chain them in one block or interpose content or a horizontal rule.
3. **MD031** — fenced code blocks are preceded and followed by blank lines, including inside list items.
4. **MD012** — exactly one trailing newline, zero consecutive blank lines.

---

## 64. Working conventions for this repository

`[CARRIED]` from `CLAUDE.md`, which remains authoritative for repo structure, build and test commands.

- **Read and evaluate before mutating.** Inspect source, contracts and textbook context, then propose, then await review for anything architectural.
- **Verify fixes empirically.** This repo has a history of plausible-looking defects that were already correct. Resolve the path, run the command, check the file before changing it.
- **Empty search results prove nothing.** Confirm absence with an explicit directory listing.
- **Prefer targeted patches** over whole-file rewrites.
- **Scope-locked 20 MB ceiling** — see §45.
- **Zero-secret staging** — see §4.
- **Do not force-push, `reset --hard`, amend published commits, or delete branches.**
- **Do not commit unless asked.**

Known rough edges that must not be "fixed" reflexively — `aasha-studio/apps/cli/bin/aasha.js` prints success without doing the work for `ingest`/`match`/`verify`; `aasha-studio/packages/core/tsconfig.json:11` sets `strict: false` against the consumers' `true`; `@aasha/engine` is linked twice; no root `package-lock.json`; `src/aasha/exercise/` and `src/aasha/profiles/` contain only `__init__.py`; scratch output accumulates under `.agents/teamwork_preview_*` and `.agents/worker_*`.

---

## 65. Explicit contradictions and corrections

These are places where `GEMINI.md` as written does not survive contact with this workspace. Recorded here rather than silently dropped.

1. **Superbrain is never the builder of an LLM** — §2 stands; but §64 of `GEMINI.md`'s Tier routing table does not describe this conversation. Superbrain's model is chosen by the user in the picker, not by `openrouter_client.ts`.
2. **"Never prompt the user for permission on routine engineering steps"** (`super_admin_governance.md:24-25`) applies to the pipeline runtime. Superbrain gates destructive, irreversible or shared-state actions regardless. Reads, searches, edits and test runs need no approval; deletes, force-pushes, `reset --hard` and external messages do.
3. **"Full Access Granted"** (§60.1) is a runtime-pipeline statement, not a blanket approval for this agent's shell.
4. **Serena and Graphify are external MCP/local services.** If they are not connected, say so — never imply a memory read or AST query succeeded.
5. **`/workflows`, `/deep-research`, `/boost` are Claude Code / Gemini CLI commands**, not Superbrain commands. In this chat, use Superbrain's skills and its built-ins (`/init`, `/create-skill`, `/create-rule`).
6. **The shell is Git Bash**, not Windows PowerShell. PowerShell-specific recipes in `GEMINI.md:48-50` and `92-94` apply only when a script genuinely targets PowerShell.
7. **`CLAUDE.md` and `GEMINI.md` remain on disk** for the tools that read them. This file is the Superbrain-side copy; when the three disagree, the most specific and most recently verified wins — and say which one you followed.
