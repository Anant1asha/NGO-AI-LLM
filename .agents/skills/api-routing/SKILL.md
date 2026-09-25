---
name: api-routing
description: >-
  Multi-API Routing Setup & Operational Runbook for the AASHA ecosystem.
  Covers Claude Code VS Code extension setup, OpenRouter free pool configuration,
  Gemini API as strict reserve, 3-tier cascade rules, and the multi-agent
  architecture that best utilizes each model tier without paid API bleed.
version: 1.0.0
layer: layer-4-extensions
compatibility:
  runtimes: [antigravity, claude-code, nodejs]
  models: [meta-llama/llama-3.1-8b-instruct:free, nvidia/nemotron-3.5-lightning:free, google/gemini-2.0-flash-exp:free, claude-3-5-sonnet, gemini-2.0-flash]
tools_required:
  - run_command
  - view_file
  - write_to_file
---

# AASHA Multi-API Routing Runbook

## Quick Reference: What Goes Where

| Task Type | Tier | API / Tool |
|---|---|---|
| Chat reply, clarification | 1 | OpenRouter free (`llama-3.1-8b:free`) |
| File read, grep, dir list | 1 | OpenRouter free |
| Registry queries, graphify | 1 | OpenRouter free (`nemotron:free`) |
| Simple code edit <200 lines | 1 | OpenRouter free |
| Multi-file refactor / chapter HTML | 2 | Claude Code (sonnet) |
| TypeScript synthesis, benchmarks | 2 | Claude Code (sonnet/haiku) |
| MCP / VS Code plugin dev | 2 | Claude Code (sonnet) |
| CDP automation scripts | 2 | Claude Code (sonnet) |
| Textbook PDF vision ingestion | 3 | Gemini 2.0 Flash (authorized) |
| Final QA certification (L-Truth + CDP) | 3 | Gemini 1.5 Pro (authorized) |
| `/boost` session | 3 | Gemini Pro (user-authorized) |

---

## Setup: Claude Code (Tier 2)

### A. VS Code Extension (Interactive Dev — Recommended)
```
1. Open VS Code → Extensions (Ctrl+Shift+X)
2. Search: "Claude Code" by Anthropic
3. Install → Sign in with Anthropic account
4. Usage: Open any file → Ctrl+Shift+P → "Claude: Edit File"
         Or use inline chat: Ctrl+K
```

### B. Claude CLI (Headless / Antigravity Subagent)
```bash
# Install globally
npm install -g @anthropic-ai/claude-code

# Verify
claude --version

# Use in Antigravity run_command (headless coding task):
claude --model claude-3-5-sonnet-20241022 --print "Generate TypeScript for..."

# Set API key in Aasha-AI/.env:
ANTHROPIC_API_KEY=sk-ant-...
```

### C. Antigravity Subagent Delegation to Claude Code
When the orchestrator (Antigravity) needs to delegate a coding task:
```
invoke_subagent:
  TypeName: self
  Model: inherit   ← uses current session model (Claude Sonnet 4.x)
  Role: "TypeScript Synthesizer"
  Prompt: "Generate packages/llm-router/openrouter_client.ts..."
```
Or via `run_command` for headless:
```bash
claude --model claude-haiku-20241022 --print "Fix TypeScript error in..."
```

---

## Setup: OpenRouter Free Pool (Tier 1)

### 1. Get API Key
- Sign up at https://openrouter.ai → Dashboard → API Keys → Create Key
- Free-tier models have `$0.00` cost — no billing needed for approved free models

### 2. Add to `Aasha-AI/.env`
```env
OPENROUTER_API_KEY=sk-or-v1-...
ALLOW_PAID_GEMINI_FALLBACK=false
DEFAULT_LLM_PROVIDER=openrouter
DEFAULT_FREE_MODEL=meta-llama/llama-3.1-8b-instruct:free
FALLBACK_FREE_MODEL_1=nvidia/nemotron-3.5-lightning:free
FALLBACK_FREE_MODEL_2=google/gemini-2.0-flash-exp:free
BATCH_RATE_LIMIT_BACKOFF_MS=3000
MAX_RETRIES_BEFORE_TIER2_ESCALATE=3
```

### 3. Verify Connection
```bash
node packages/llm-router/openrouter_client.ts --test
# Expected: ✅ Tier 1 OpenRouter free pool: CONNECTED (llama-3.1-8b:free)
```

### 4. Free Model Rotation Logic
The client rotates through the pool on 429:
```
Attempt 1 → llama-3.1-8b:free
Attempt 2 (3s wait) → nemotron-3.5-lightning:free  
Attempt 3 (3s wait) → gemini-2.0-flash-exp:free
Attempt 4 → throw → ESCALATE to Tier 2 (Claude Code), NOT Gemini paid
```

---

## Setup: Gemini API as Reserve (Tier 3)

### 1. Add to `Aasha-AI/.env`
```env
GEMINI_API_KEY=AIzaSy...
ALLOW_PAID_GEMINI_FALLBACK=false
GEMINI_RESERVE_TASKS=pdf_ingestion,final_qa_certification,super_admin_boost
GEMINI_DEFAULT_RESERVE_MODEL=gemini-2.0-flash
GEMINI_PRO_RESERVE_MODEL=gemini-1.5-pro
```

### 2. Guard Check (Mandatory in All Pipeline Scripts)
```typescript
// packages/llm-router/gemini_guard.ts
export function assertGeminiAuthorized(taskType: string): void {
  const allowed = (process.env.GEMINI_RESERVE_TASKS ?? '').split(',').map(t => t.trim());
  if (process.env.ALLOW_PAID_GEMINI_FALLBACK === 'true') return; // only when user explicitly enables
  if (!allowed.includes(taskType)) {
    throw new Error(
      `[ANTI-BLEED GUARD] ❌ Gemini API BLOCKED for: "${taskType}".\n` +
      `Allowed tasks: ${allowed.join(', ')}.\n` +
      `Route to Tier 1 (OpenRouter) or Tier 2 (Claude Code) instead.`
    );
  }
  console.warn(`[TIER 3] ⚠️  Gemini paid API authorized for: "${taskType}". Logging usage.`);
}
```

---

## Multi-Agent Architecture (Optimal Utilization)

```
┌──────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR                                                     │
│  Antigravity (Claude Sonnet 4.x — current session)               │
│  • Receives user request                                          │
│  • Applies 3-tier routing decision tree                           │
│  • Delegates to specialized subagents                             │
│  • Never makes paid Gemini calls for routine orchestration        │
└────────┬─────────────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────────┐
│  TIER 1: OpenRouter Free Pool Subagents                          │
│  (All routine work — zero cost)                                  │
│  ├── RoutineChatAgent      → llama-3.1-8b:free                  │
│  ├── RegistryMatchAgent    → nemotron-3.5-lightning:free         │
│  ├── GraphifyQueryAgent    → gemini-2.0-flash-exp:free           │
│  ├── AdminStatusAgent      → llama-3.1-8b:free                  │
│  └── MathInsulationAgent   → nemotron-3.5-lightning:free         │
└────────┬────────────────────────────────────────────────────────┘
         │  (escalate on: code task | 3x 429 | edit >200 lines)
┌────────▼────────────────────────────────────────────────────────┐
│  TIER 2: Claude Code Subagents                                   │
│  (All coding synthesis — Anthropic API, cheaper than Gemini Pro) │
│  ├── ChapterHTMLGenerator  → claude-3-5-sonnet-20241022          │
│  ├── TypeScriptSynthesizer → claude-3-haiku-20241022             │
│  ├── BenchmarkScriptAgent  → claude-3-haiku-20241022             │
│  ├── MCPPluginDeveloper    → claude-3-5-sonnet-20241022          │
│  └── CDPAutomationWriter   → claude-3-5-sonnet-20241022          │
└────────┬────────────────────────────────────────────────────────┘
         │  (ONLY on: /boost | PDF ingestion | final QA cert)
┌────────▼────────────────────────────────────────────────────────┐
│  TIER 3: Gemini API Reserve                                      │
│  (High-end tasks only — explicit authorization required)         │
│  ├── PDFIngestionAgent     → gemini-2.0-flash (vision)           │
│  └── FinalQACertifier      → gemini-1.5-pro (long context)       │
└─────────────────────────────────────────────────────────────────┘
```

### Subagent Spawn Patterns

**Tier 1 task (routine chat/research)**:
```
invoke_subagent → TypeName: research, Model: flash_lite
```

**Tier 2 task (code synthesis)**:
```
invoke_subagent → TypeName: self, Model: inherit (Claude Sonnet)
```

**Tier 3 task (PDF ingestion — explicit)**:
```
run_command → node scripts/ingest_pdf.ts --model gemini-2.0-flash --authorize pdf_ingestion
```

---

## MCP Servers via OpenRouter (Tier 1 Tools)

For MCP tools that require LLM calls, route through OpenRouter free pool:

```json
// .agents/mcp_config.json
{
  "servers": {
    "openrouter-llm": {
      "command": "node",
      "args": [".agents/mcp/openrouter_mcp_server.js"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}",
        "DEFAULT_MODEL": "meta-llama/llama-3.1-8b-instruct:free"
      }
    }
  }
}
```

---

## System Instructions & Structured JSON Protocol

To eliminate model hallucinations and ensure clean, parseable responses across all 3 tiers:

1. **Explicit System Instructions**: Every API call via `llm_router.ts` or `openrouter_client.ts` must pass a structured `systemPrompt` defining:
   - Specific role and output schema requirements (e.g. `content_map`, `chapter_spec`).
   - Truth-seeking protocol: `ANSWER WITHOUT GUESSING`, `CHECK YOUR WORK`, `CONFIDENCE SCORE (0.0-1.0)`.
   - Hard output boundaries (e.g., "Respond ONLY with valid JSON").

2. **Schema Validation & Gatekeeper Auto-Repair**:
   ```typescript
   // Validate LLM output with ContextBus
   const audit = contextBus.validateOutput(llmResponse.content, role);
   if (!audit.passed && audit.repairPrompt) {
     // Autonomous self-repair loop
     const repaired = await route({ prompt: audit.repairPrompt, systemPrompt, taskType });
   }
   ```

---

## Mem0 & Graphify Local AGI Agentic Memory Pipeline

To maximize multi-agent performance while avoiding external API token overhead:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MULTI-AGENT CONTEXT BUS                             │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│  GRAPHIFY AST KNOWLEDGE GRAPH │               │  MEM0 LOCAL EPISODIC MEMORY   │
│  `graphify-out/graph.json`    │               │  `.scratch/mem0_store.json`   │
│  - Codebase AST relationships │               │  - Pedagogical preferences    │
│  - Foundation mappings (F01-20)│               │  - Section 24 contract state  │
└────────┬──────────────────────┘               └────────┬──────────────────────┘
         │                                               │
         └───────────────────────┬───────────────────────┘
                                 │ Zero-Token Local Context Injection
                                 ▼
         ┌───────────────────────────────────────────────┐
         │  Agent System Prompt Context Enrichment       │
         │  (ContextBus.buildAgentContext())             │
         └───────────────────────────────────────────────┘
```

1. **Pre-Call Context Enrichment**: Before generating prompts for subagents, `agent_orchestrator.ts` automatically queries local Graphify subgraphs and Mem0 episodic store.
2. **Zero-Token Memory Snapshot**: Agent state and domain rules are loaded directly from local JSON files without spending API tokens.

---

## Anti-Bleed Health Check

Run this to verify no paid Gemini calls are leaking:
```bash
# Check current env config
node -e "require('dotenv').config({path:'Aasha-AI/.env'}); console.log('ALLOW_PAID_GEMINI_FALLBACK:', process.env.ALLOW_PAID_GEMINI_FALLBACK)"
# Expected: ALLOW_PAID_GEMINI_FALLBACK: false

# Test OpenRouter connection
node packages/llm-router/openrouter_client.ts --test

# Test Gemini guard
node -e "import('./packages/llm-router/gemini_guard.ts').then(m => m.assertGeminiAuthorized('chat')).catch(e => console.log(e.message))"
# Expected: [ANTI-BLEED GUARD] ❌ Gemini API BLOCKED for: "chat"
```
