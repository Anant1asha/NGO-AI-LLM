# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this repository is

A collection of **five independent projects** serving one mission: converting Indian K-12 textbook PDFs (NCERT and other boards) into interactive, gamified, offline HTML5 learning modules.

> [!IMPORTANT]
> **Ecosystem Identity Invariant (Autonomous AI Agent System vs. Building LLM)**:
> Despite the nominal directory name `NGO AI LLM` and remote URL `https://github.com/Anant1asha/NGO-AI-LLM.git`, this ecosystem **DOES NOT BUILD, PRE-TRAIN, OR FINE-TUNE LLMs**. It is an **Autonomous AI Agent Ecosystem (AASHA AIOS)** featuring multi-agent orchestration (`agents.json`), multi-tier memory (Serena MCP, Mem0, SQLite, AST graph), multi-tools & simulation engines (F01–F20 catalog, PyMuPDF, LaTeX math insulator, Headless Chrome CDP automation), curated resources, and procedural skills. External LLMs are consumed strictly as swappable reasoning engines via an anti-bleed router (`packages/llm-router/openrouter_client.ts`). Any assumption that this project builds or trains an LLM is an anti-pattern hallucination.

There is **no single root orchestrator binary**. `scripts/aasha_root_orchestrator.js` exists and root `package.json:7-21` fans out to each sub-project via `npm --prefix`, but each project is separately runnable and separately testable.

Authoritative context documents (read these before large changes):
- `GEMINI.md` — the normative invariant document. Persona, evidence protocol, scope-locked 20 MB rule, resource-first reuse hierarchy.
- `Aasha-AI/CLAUDE.md` — the operating persona (evidence > confidence, no fabrication).
- `PROJECT.md` — per-chapter architecture spec (currently the Class 8 Square & Cube Roots chapter).
- `Aasha-AI/ECOSYSTEM_MAP.md`, `ARCHITECTURE_GRAPH.md`, `docs/specs/`.

## Layout

| Path | Role | Entry point |
|---|---|---|
| `Aasha-AI/aasha-pipeline-with-master-json/` | **The core engine.** 6-agent Python pipeline (Ingest, Analysis, Design, Assessment, LLE, QA) orchestrating 9 stages. | `src/aasha/cli.py`; orchestration in `src/aasha/pipeline/orchestrator.py` |
| `Aasha-AI/server/` | Fastify + SQLite sync/evidence API | `server/server.js` |
| `Aasha-AI/packages/` | Reusable subsystems: `aios/` (capability broker, version manager), `iec/` (registry, provenance, providers), `v6-engine/`, `memory-engine/`, `llm-router/`, `aasha-rules/` | per-package `src/index.ts` |
| `Aasha-AI/experience_registry/` | **The live resource registry** — written at runtime by ingestion. | `registry.json` |
| `multi-agent-tui/` | Teacher-facing TUI. Spawns the Python pipeline. | `src/cli.ts` |
| `aasha-studio/` | Clean AGPL-3.0 repackaging. npm workspaces. | `apps/cli/bin/aasha.js` |
| `gemini-web2api/` | Go OpenAI-compatible Gemini web bridge | `main.go` |
| `AASHA_Visual_Mass_Harvest_Phase3/` | Harvested visual resource library (static manifests + HTML) | `catalogue/` |

## Build and test

Run these **per sub-project** — there is no unified test command.

```bash
# multi-agent-tui (TypeScript)
npm --prefix multi-agent-tui install
npm --prefix multi-agent-tui run build     # tsc -> dist/
npm exec -- tsc --noEmit -p multi-agent-tui/tsconfig.json   # typecheck only
npm --prefix multi-agent-tui test

# aasha-studio (npm workspaces)
npm --prefix aasha-studio install
npm --prefix aasha-studio run studio

# Aasha-AI (Node)
npm --prefix Aasha-AI install
npm --prefix Aasha-AI test                 # runs index.html checks

# gemini-web2api (Go)
cd gemini-web2api && go test ./...

# Python pipeline
cd Aasha-AI/aasha-pipeline-with-master-json && python -m aasha.cli --help
```

Install and test are **separate steps**. A test claim requires output showing tests actually executed — exit code 0 alone proves nothing (a filter matching nothing exits 0).

## Dual Execution Topology (Heavy CLI vs. VS Code Extension)

To avoid token bleed, command parsing errors, and interrupted background tasks, adhere to this environment split:

- **Scenario A: Standalone Claude Code CLI Terminal (Direct `ANTHROPIC_API_KEY`)**
  - Reserved for heavy multi-agent workflows (`Workflow({ name: "deep-research" })`, `/deep-research`), multi-agent reviews, and full codebase AST indexing.
  - Native TUI commands (such as the interactive `/workflows` progress panel) run exclusively in this environment.
- **Scenario B: VS Code Extension (via 9Router Proxy & Local Scripts)**
  - Use for routine development, coding, bug fixing, and continuous pipeline orchestration.
  - Pipeline control, stage execution, and test certifications are driven via the Unified Root Orchestrator:
    - Interactive Hub: `npm run orchestrator` / `npm start`
    - Laya Zero-Token Audit: `npm run laya:test`
    - Teacher Console: `npm run tui`
    - Chapter V6 Build: `npm run chapter:compile`
    - All Tests: `npm run test:all`
    - Gateway Check: `npm run audit:gateway`
  - Do not type CLI-specific TUI slash commands (like `/workflows`) in the extension chat.

## Invariants you must not violate

**Scope-locked 20 MB ceiling** (`GEMINI.md:312-315`). `CHILD_HTML5_BUNDLE_MAX_BYTES = 20971520` applies **ONLY** to the child-facing standalone offline HTML5 bundle. It explicitly does **not** apply to source PDFs, contracts, Hatchable storage, telemetry databases, evidence ledgers, server-side artifacts, **resource libraries**, global vocabulary, QA reports, or **version history**. Resource libraries may exceed 20 MB. On violation: `CERTIFICATION = FAIL`, `RELEASE = BLOCKED` — and never delete educational functionality to pass it; optimize deterministically first.

Do not conflate this with the other, unrelated budgets: LLM `max_tokens` (completion length), provider daily token budget (spend throttle), bounded diff budget (≤ 2000 lines), mobile sync payload (< 50 KB).

**Resource-first reuse** (`GEMINI.md:317-324`). Resolution order is `EXACT_REUSE → PARAMETRIC_ADAPT → COMPOSE → LOCAL_ADAPTATION → CERTIFIED_GENERATION → SAFE_FALLBACK`. Code generation is a LAST RESORT. Local precedence: `LOCAL RESOURCE > LOCAL REGISTRY > LOCAL VOCABULARY > LOCAL EXPERIENCE > LOCAL AST/GRAPH > EXISTING CACHE > REMOTE MODEL`. Never invoke an LLM to recreate information available locally; never re-download an identical resource.

**Zero-spoiler assessment.** Misconception text in the `m` attribute must never leak the answer.

**Math insulation.** Shield expressions as `__AASHA_MATH_X__` before any LLE translation pass.

**Offline integrity.** Child bundles: zero external CDN/font/network calls, 44px minimum touch targets.

**Zero-secret staging** (`GEMINI.md:40-45`). All ecosystem repos are treated as 100% public. Never stage API keys, tokens, or private keys.

## Working conventions

- **Read and evaluate before mutating.** Inspect source, contracts, and textbook context first; then propose; then await review for anything architectural.
- **Verify fixes empirically.** This repo has a history of plausible-looking defects that were already correct. Resolve the path, run the command, check the file — before changing it.
- **Empty search results prove nothing.** Confirm absence with an explicit directory listing.
- **Prefer targeted patches** over whole-file rewrites.
- Do not force-push, `reset --hard`, amend published commits, or delete branches.
- Do not commit unless asked.

## Known rough edges

These are real and observed — do not "fix" them reflexively:

- `aasha-studio/apps/cli/bin/aasha.js` — `ingest`, `match`, and `verify` print success strings without performing the work. The `studio` command is fully functional.
- `aasha-studio/packages/core/tsconfig.json:11` sets `"strict": false` while the two consuming projects set `true`.
- `@aasha/engine` is linked both as a workspace and via a `file:` dependency, producing a hoisted duplicate under `node_modules`.
- No `package-lock.json` at the repo root despite root scripts delegating across three projects.
- Several directories under `src/aasha/` (`exercise/`, `profiles/`) contain only `__init__.py`.
- Agent workflow scratch output accumulates under `.agents/teamwork_preview_*` and `.agents/worker_*`.
