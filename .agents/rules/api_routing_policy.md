---
description: >-
  Universal 3-Tier API Routing Policy. Governs ALL model API calls across
  interactive chat, VS Code coding tasks, plugin calls, MCP tool invocations,
  and automated pipelines. Gemini paid API is RESERVE-only — not a default,
  not a convenience fallback. Cascade path: Tier 1 (OpenRouter free) →
  Tier 2 (Claude Code) → Tier 3 (Gemini, authorized only).
globs: ["**/*"]
---

# Universal 3-Tier API Routing Policy

## Decision Tree (Apply Before EVERY API Call)

```
Is this task in the explicit Tier 3 authorized list below?
  YES → Use Gemini API (paid). Log usage. Require explicit user authorization.
  NO  ↓
Is this a multi-file code synthesis, chapter HTML generation, TS scripting,
  VS Code / MCP plugin dev, or file edit >200 lines?
  YES → Use Claude Code (Tier 2). Prefer claude-3-5-sonnet or claude-haiku.
  NO  ↓
Route to OpenRouter Free Pool (Tier 1).
  → Rotate: llama-3.1-8b:free → nemotron-3.5:free → gemini-2.0-flash-exp:free
  → 3s mandatory backoff on 429. Max 3 retries.
  → After 3 failures → escalate to Tier 2 (Claude Code). NEVER to Tier 3.
```

---

## Tier 1 — OpenRouter Free Pool (Default for ALL Routine Work)

Route here first for:
- All interactive chat replies and clarifications
- File reading, grepping, listing directories, status checks
- Simple code edits or patches under 200 lines
- Registry queries (`registry.json`, `graphify-out/`)
- Admin commands (`npm run admin:status`, `npm run admin:match`)
- Plugin and MCP tool result summarization
- Math insulation runs (`math_insulator.ts`) and small JSON transforms
- LaTeX rendering checks, YAML contract validation

**Approved free models** (rotate in order on failure):
```
meta-llama/llama-3.1-8b-instruct:free
nvidia/nemotron-3.5-lightning:free
google/gemini-2.0-flash-exp:free
```

**Rate limit handling**: 3-second backoff on 429, max 3 retries, then escalate to Tier 2.

---

## Tier 2 — OpenRouter Free Coding Pool / Claude Code (Coding Agent Tasks)

Route here for:
- Any file creation or multi-file refactoring
- Chapter HTML generation (simulation + assessment content)
- TypeScript / Node.js script generation and debugging
- `packages/`, `benchmarks/`, `scripts/` development in Aasha-AI
- VS Code extension, MCP server, OpenRouter adapter development
- CDP browser automation scripts
- Any Tier 1 task that has failed 3x on 429

**Default Model Pool (0 Cost via OpenRouter)**:
```
qwen/qwen-2.5-coder-32b-instruct:free
nvidia/nemotron-3.5-lightning:free
google/gemini-2.0-flash-exp:free
meta-llama/llama-3.1-8b-instruct:free
```
*Note*: No paid Anthropic key is required. Uses 3-key OpenRouter rotation (`OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2`, `OPENROUTER_API_KEY_3`) for 3x rate limit capacity.

---

## Tier 3 — Gemini API Reserve (Explicit Authorization Required)

**This is STRICTLY reserved for the following tasks ONLY:**

1. Textbook PDF multimodal vision ingestion (>10 pages, structured JSON extraction)
2. Full-chapter long-context synthesis requiring >100K token context window
3. Final Dual-Benchmark L-Truth + CDP certification run (authorized by Super Admin)
4. Tasks explicitly authorized by user with the `/boost` slash command

**NEVER use Gemini paid API for:**
- Routine chat, file reads, grep, status checks
- Simple code edits under 200 lines
- Registry lookups, foundation match reports
- Plugin/MCP status checks, admin commands
- Any task covered by Tier 1 or Tier 2

`ALLOW_PAID_GEMINI_FALLBACK=false` must remain set in `Aasha-AI/.env` at ALL times.

---

## System Instructions & Structured JSON Protocol

All model requests (across Tier 1, Tier 2, and Tier 3) MUST:
1. **Pass Explicit System Instructions**: Include system prompts defining strict role boundaries, truth-seeking reasoning constraints, and output format requirements to eliminate hallucinations.
2. **Enforce JSON Schema Verification**: Validate generated JSON outputs (`ContextBus.validateOutput()`) before persisting to codebase files.

---

## Serena, Graphify & Local Memory Protocol (Default Local Memory)

1. **Serena Default Local Memory First**: Subagents and agents MUST query Serena MCP memories (`.serena/memories/` via `read_memory`) and local Graphify AST subgraphs (`graphify-out/graph.json`) before making external model context queries.
2. **Zero-Bleed Memory Sharing**: Share state, rules, and memory across agent turns using persistent local Serena memories (`.serena/memories/`) and local episodic stores (`.scratch/mem0_store.json`, `aasha_operational.db`) to eliminate redundant API token overhead.

---

## Cascade Rules (Strict — No Exceptions)

| From | To | Trigger |
|---|---|---|
| Tier 1 → Tier 2 | OpenRouter Free Coding Pool | Code task, 3x 429 retries, or edit >200 lines |
| Tier 2 → Tier 3 | Gemini (authorized) | `/boost` command OR explicit PDF ingestion task ONLY |
| Tier 1 → Tier 3 | **PROHIBITED** | Never skip directly to paid Gemini |
| Any → Tier 3 (auto) | **PROHIBITED** | Never automatic fallback to Gemini paid on any error |

---

## Enforcement

This rule applies to:
- The Antigravity orchestrator agent
- All subagents spawned via `invoke_subagent`
- All `run_command` calls invoking LLM APIs
- All pipeline scripts in `Aasha-AI/` and `packages/`
- All MCP tool calls that hit external LLM endpoints
