# Tech Stack

- **Runtime & Environment**: Node.js, TypeScript (ESNext / CommonJS / ESM dual build), Windows OS (`PowerShell`), Python 3.13 (`uv tool` isolated environment).
- **Core Orchestrator**: AASHA AIOS, Canonical IR Assembler (`packages/canonical-ir`), V6 Event Bus (`packages/v6-engine`).
- **Front-end / Interactive**: HTML5 Web Components (`<aasha-sim>`), KaTeX, JSXGraph, Canvas 2D / WebGL.
- **LLM API & Routing**: 3-Tier anti-bleed router (`packages/llm-router/openrouter_client.ts`). Tier 1: OpenRouter free models; Tier 2: Claude Code; Tier 3: Gemini paid (strict reserve). `ALLOW_PAID_GEMINI_FALLBACK=false`.
- **System 1 Task Classifier & Guardrails**: Laya v0.4.7 (`convaiinnovations/laya`), providing sub-millisecond Indic script detection (`laya.detect_script`), zero-token non-autoregressive calibrated task routing (`coding`, `assessment`, `design`, `analysis`, `lle-indic`, `vision`), and resident daemon integration in `Aasha-AI/packages/llm-router/laya_classifier.ts`.
- **Knowledge & Memory**: Serena Local Semantic Memory (DEFAULT, `.serena/memories/`), AST Knowledge Graph (`graphify-out/graph.json`), Local SQLite & Offline Episodic Store (`.scratch/mem0_store.json`, `aasha_operational.db`).
