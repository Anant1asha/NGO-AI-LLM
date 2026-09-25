# Tech Stack

- **Runtime & Environment**: Node.js, TypeScript (ESNext / CommonJS / ESM dual build), Windows OS (`PowerShell`).
- **Core Orchestrator**: AASHA AIOS, Canonical IR Assembler (`packages/canonical-ir`), V6 Event Bus (`packages/v6-engine`).
- **Front-end / Interactive**: HTML5 Web Components (`<aasha-sim>`), KaTeX, JSXGraph, Canvas 2D / WebGL.
- **LLM API & Routing**: 3-Tier anti-bleed router (`packages/llm-router/openrouter_client.ts`). Tier 1: OpenRouter free models; Tier 2: Claude Code; Tier 3: Gemini paid (strict reserve). `ALLOW_PAID_GEMINI_FALLBACK=false`.
- **Knowledge & Memory**: AST Knowledge Graph (`graphify-out/graph.json`), Local Episodic Store (`.scratch/mem0_store.json`), Serena Memory Store.
