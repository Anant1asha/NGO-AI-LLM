# AASHA AIOS Master Roadmap Charter & Architectural Invariants (v2.0)
**Authority**: Annanth Aasha Super Admin Governance  
**Date**: 2026-10-27  
**Status**: `RATIFIED_AND_LOCKED` (Approved via Super Admin /grill-me Alignment)  

---

## 1. Executive Identity & System Boundaries

1. **Definitive Build Purpose**: Despite the nominal workspace folder name `NGO AI LLM` and remote URL `NGO-AI-LLM.git`, this ecosystem **DOES NOT BUILD, PRE-TRAIN, OR FINE-TUNE LARGE LANGUAGE MODELS**.
2. **AI Agent Operating System (AASHA AIOS)**: The build consists strictly of an **Autonomous AI Agent Operating System** deploying:
   - 7 specialized pipeline agents (`IngestAgent`, `AnalysisAgent`, `DesignAgent`, `AssessmentAgent`, `LLEAgent`, `QAAgent`, `BrowserTesterAgent`).
   - Deterministic Foundation Engines & Tools (PyMuPDF vector extraction, LaTeX math insulation, KaTeX typography, procedural Web Audio synthesis, headless Chrome DevTools Protocol automation).
   - Multi-tier zero-cost local memory (Serena MCP, AST Codebase Graph, SQLite Operational Knowledge Graph).
   - Reusable Content Contracts (Section 24 YAML Reusable Content Contracts, F01–F27 Foundation catalog).
3. **External Model Consumption**: External LLMs (`llama-3.1-8b`, `nemotron-3.5`, `claude-3-5-sonnet`, `gemini-2.0-flash-exp`) are consumed strictly as *swappable, ephemeral reasoning utilities* through the 4-Tier Anti-Bleed Router.

---

## 2. Phase-by-Phase Codified Architectural Decisions

### Phase 1: Ingestion & Extraction Architecture
- **Decision**: **Hybrid Local-First Tier-0 with Resilient Free Vision Fallback**.
- **Execution Rule**:
  - Deterministic PyMuPDF digital text and vector drawing extraction runs first (<10ms, 0 tokens).
  - Multimodal vision is strictly restricted to scanned/low-text pages (<50 characters and 0 vector paths).
  - Images are rendered at max width 1000px, JPEG quality 80, `alpha=False` (~80–120KB per page).
  - Upstream requests round-robin across verified free vision models on OpenRouter with a 20-second circuit breaker.
  - If congested, synthesize structured geometric stub blocks to preserve pagination without pipeline halts.

### Phase 2: Pedagogical Transformation & L-Truth Anti-Spoiler Rules
- **Decision**: **Deterministic Regex/AST Scrubber with Pedagogical Pattern Replacement**.
- **Execution Rule**:
  - Hard zero-token filter (`sanitize_spec_misconceptions`) scrubs generated distractors.
  - Explanations must NEVER reveal or quote the target answer, calculation result, or direct formula substitution.
  - Leaks are rewritten deterministically into pedagogical reasoning clues (e.g., *"Check if you applied addition instead of repeated grouping"*).
  - LaTeX mathematical expressions are insulated with surrogate tokens (`[MATH_INSULATED_xyz]`) before bilingual translation to eliminate symbol corruption.

### Phase 3: Interactive Experiences & Foundation Catalog
- **Decision**: **3-Tier Experience Hierarchy with Cleanroom Isolation**.
- **Execution Rule**:
  - **Priority 1**: Foundation Adaptation via `<aasha-sim>` Web Component Contract reusing prebuilt foundations from catalog F01–F27 (`experience_registry/registry.json`).
  - **Priority 2**: Dynamic REA Reverse-Engineering decomposition when no foundation matches.
  - **Priority 3 (Last Resort)**: Lightweight Declarative SVG/Canvas state engine.
  - **GPL-3.0 Cleanroom Isolation**: Foundations under GPL-3.0 (PhET F04, Escapp F09, Code for Life F17) strictly use `EXTRACT` / `INSPIRE` cleanroom wrappers, isolating physics formulas inside `<aasha-sim>` to prevent copyleft contagion into MIT core chapters.

### Phase 4: Multi-Agent Orchestration & Financial Anti-Bleed
- **Decision**: **Strict 2-Repair Bounded Policy with Quarantined State & Chāṇakya HIL**.
- **Execution Rule**:
  - Autonomous self-repair between agents is strictly capped at **2 attempts**.
  - Upon exhausting the second repair attempt:
    1. Immediately halt autonomous execution.
    2. Preserve the isolated worktree and test diagnostics in `.scratch/quarantine/`.
    3. Block all downstream stages (`QAAgent`, `BrowserTesterAgent`).
    4. Emit a structured Chāṇakya Incident Packet with dual reports (technical diffs + non-technical Hindi teacher summary `शिक्षक के लिए सारांश`).
    5. Await Super Admin human authorization.
  - **Hard-Locked Circuit Breaker**: `ALLOW_PAID_GEMINI_FALLBACK=false` enforced across all `.env` files and `llm_router.ts` explicit route guards.

### Phase 5: Dual-Benchmark Certification & Closed Runtime Items
- **Decision**: **Resolved RG-001 & OI-003, Bounded OI-001**.
- **Execution Rule**:
  - **RG-001 (Closed / RUNTIME_VERIFIED)**: Upgraded Stage 3 Fork-Join concurrency to `runWithWorkerPool` capped strictly at `maxConcurrency = 2`. Eliminates Windows process table thrashing and thread starvation. Verified via `test_concurrency_wiring.ts` (6/6 PASS).
  - **OI-003 (Closed / TEST_VERIFIED)**: Validated synthetic fault injection and quarantine lifecycle via `test_fault_injection_hardening.ts` (10/10 PASS).
  - **OI-001 (Bounded / LOCAL_CIRCUIT_BREAKER_CERTIFIED)**: Upstream provider billing observability is formally bounded to client-side circuit breakers until provider billing webhooks are provisioned.
  - **Master Certification**: Chapters must achieve 100/100 L-Truth score and pass CDP mobile viewport headless testing.

### Phase 6: Edge Reality & Deployment
- **Decision**: **Dual Zero-Setup Distribution (Single-File Standalone HTML5 + USB/SD Flash Sync)**.
- **Execution Rule**:
  - Standalone HTML5 chapter modules must strictly remain $\le 20\text{MB}$ (`20,971,520 bytes`).
  - 100% offline executable via direct double-click (`file:///...`).
  - **ZERO external CDN dependencies**: All CSS, fonts, KaTeX assets, procedural Web Audio tone synthesizers, and simulation scripts are inlined.
  - Touch targets strictly $\ge 44\times 44\text{px}$; layout fits mobile viewports (375px width) without horizontal scroll.
  - Pre-commit automated secret scanning actively enforced via `scripts/lint_staged_secrets.mjs` and `.githooks/pre-commit`.
