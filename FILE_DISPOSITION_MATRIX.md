# FILE_DISPOSITION_MATRIX.md
# AASHA AIOS Subsystem & File Disposition Matrix
**Authority**: Senior Full-Stack Engineer & Systems Architect  
**Date**: 2026-10-09  

---

## 1. Classification Definitions
- **RETAIN**: Production-grade, verified source code or documentation that remains unchanged and actively supported.
- **REFACTOR**: Active code that requires interface standardization, type refinement, or credential isolation without architectural replacement.
- **DEPRECATE**: Legacy or superseded code marked for eventual sunset; maintained strictly read-only until migration is certified. (No silent deletion).
- **INTRODUCE**: New modular components, adapters, or workflows specifically required for the development agent.
- **HOLD**: Subsystems under active investigation whose disposition cannot be finalized without additional empirical evidence.

---

## 2. Comprehensive File & Directory Disposition

| Path / Subsystem | Current Purpose | Verification Evidence | Proposed Disposition | Action Plan & Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **`Aasha-AI/Aasha-AIOS/`** | Canonical governance, layer definitions (`layer-1-core/`, `layer-2-education/`, `layer-3-product/`), and `AGENTS.md`. | Verified canonical governance authority (Version 1.0.0 / 2.0.0). | **RETAIN** | Preserved as canonical system-of-record for multi-agent roles and invariants. |
| **`Aasha-AI/agent_orchestrator.ts`** | Core Node.js/TypeScript pipeline orchestrator, Gatekeeper, and 2-tier repair loop. | 10/10 fault injection tests pass; 100/100 L-Truth pass. | **RETAIN** | Operational engine. Serves as execution target for the development agent. |
| **`Aasha-AI/packages/llm-router/`** | 3-tier anti-bleed routing and OpenRouter free pool client. | Verified anti-bleed lock (`ALLOW_PAID_GEMINI_FALLBACK=false`). | **RETAIN** | Strict cost and circuit breaker governance. |
| **`Aasha-AI/packages/v6-engine/`** | Single-file HTML v6 compiler, TEAS event bus, and math insulator. | 36/36 E2E chapter tests pass; zero CDN violations. | **RETAIN** | Core learning artifact compiler. |
| **`Aasha-AI/experience_registry/`** | Prebuilt 20+ simulation foundations catalog & component schema. | 11/11 registry protocol tests pass. | **RETAIN** | Foundation reuse engine. |
| **`Aasha-AI/benchmarks/`** | L-Truth anti-spoiler benchmark, CDP browser verification, and mathematical oracles. | 100/100 benchmark score verified. | **RETAIN** | Definitive certification gate. |
| **`Aasha-AI/aasha-pipeline-with-master-json/`** | Hybrid Python/Node pipeline, PyMuPDF extraction, legacy template. | Contains legacy dependencies (`pyproject.toml`, `requirements.txt`). | **HOLD** | Do not delete or deprecate prematurely. Retain PyMuPDF extractor tools while inspecting active pipeline usage. |
| **`Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/`** | Full-stack monorepo prototype (Next.js PWA, microservices, database). | Historical reference repository for TEAS schemas. | **HOLD** | Preserved as reference architecture; isolate from active single-file build paths. |
| **`Aasha-AI/.mcp.json`** | Local MCP configuration for graphify, a11y, puppeteer. | Discovered embedded bearer token in file. | **REFACTOR** | Scrub embedded Bearer token string into environment variables (`.env`) to satisfy zero-leakage invariant. |
| **`Aasha-AI/.git/config`** | Git remote origin configuration. | Discovered embedded GitHub PAT in remote URL. | **REFACTOR** | Sanitize remote URL to standard SSH / credential-helper format without in-URL tokens. |
| **`packages/dev-agent/` (Proposed)** | AASHA AI development agent core (Task intake, Worktree manager, Command runner, Diff reviewer). | New capability required by Master Build prompt. | **INTRODUCE** | Minimal, testable TypeScript modules following least-privilege boundaries. |
| **`workflows/n8n/` (Proposed)** | Modular n8n workflow definitions (`WF-01` to `WF-10`). | Required workflow orchestration exports. | **INTRODUCE** | Exported JSON workflows using n8n Workflow SDK without hard-coded credentials. |
