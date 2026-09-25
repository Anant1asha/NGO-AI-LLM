---
name: aasha-ecosystem
description: >-
  Operational runbook for the AASHA Learning Ecosystem. Provides procedures,
  commands, and architectural rules for Super Admin Memory, the 20+ Prebuilt
  Open-Source Experience Foundations matcher, Dual-Benchmark certification,
  and Zero-Token Bleed circuit breaker routing.
---

# AASHA Learning Ecosystem Operational Skill

This skill guides agents and developers in operating the Annanth AASHA Foundation learning platform across any school, board (CBSE, ICSE, NCERT, State Boards), class (Class 1–10), and subject.

## Core Mandates & Golden Invariants

1. **Never Build From Scratch**:
   Always query the 20+ prebuilt open-source experience foundations in `Aasha-AI/experience_registry/registry.json` before designing any new simulation, game, or interactive exercise. Adapt foundations under `AashaExperienceContract`.

2. **Automated Chapter Contract & Resource Matcher**:
   Before generating or updating any chapter, initialize its Section 24 contract and matched foundation via:
   ```bash
   npm run chapter:init -- "<Subject>" <Class> "<Topic>"
   ```
   This automatically queries the 20+ foundations, creates `content/contracts/<Subject>_Class<Class>_<Topic>.yaml`, embeds the Resource Match Report, and binds the simulation adapter. The `AASHAGatekeeper` automatically enforces this in the background.

3. **Zero-Token Bleed Circuit Breaker**:
   Keep `ALLOW_PAID_GEMINI_FALLBACK=false` in `Aasha-AI/.env` to prevent cascading billing leakage during automated tasks. Automated batch jobs route through free OpenRouter models with 3s backoff on 429s.

4. **Pre-LLE Math Insulation**:
   Always insulate LaTeX math (`\( ... \)`, `$$ ... $$`, `$...$`) and single-letter algebraic variables with `__AASHA_MATH_X__` using `packages/aasha-rules/math_insulator.ts` before bilingual dictionary wrapping.

5. **Dual-Benchmark 100% Quality Invariant**:
   All chapters must pass both benchmarks:
   - Benchmark 1: `node benchmarks/qa_ltruth_benchmark.js` (100/100, 0 spoilers, 0 math collisions)
   - Benchmark 2: Headless Chrome CDP automation (`automated_browser_verification.js`: 0 console errors, 5-step navigation)

6. **GPL-3.0 License Isolation Policy**:
   Foundations licensed under GPL-3.0 (F04 PhET, F09 Escapp, F17 Code for Life) must strictly use `EXTRACT` or `INSPIRE` reuse strategies (extracting mathematical models, mechanics, and public assets) or run via clean iframe/adapter isolation to prevent copyleft contagion into the MIT core chapter files.

7. **Hindi-Focused Bilingual Substrate**:
   Right now, **Hindi** is the sole active Indic language for bilingual word-tap popups (`window.WM`). Focus verification on 100% Hindi dictionary coverage, pronunciation accuracy, and math insulation before introducing other regional languages.

8. **Unified 3-in-1 Pipeline Execution Modes**:
   - **Mode A (Autonomous Worker)**: Headless pipeline running Ingest -> QA with automated self-repair on benchmark failures.
   - **Mode B (Interactive Gate)**: `--interactive` flag pauses after Section 24 contract creation for Super Admin review.
   - **Mode C (Batch Folder Runner)**: `--batch-dir` processes full textbook directories under zero-bleed model rotation.

9. **Simulation Web Component & Telemetry (`<aasha-sim>`)**:
   All interactive simulations must adapt to `AashaExperienceContract` wrapped in the universal `<aasha-sim>` Web Component emitting bubbling `aasha:telemetry` and `aasha:state_change` CustomEvents.

10. **Balanced Runtime Lifecycle ($\ge 4$ GB RAM Invariant)**:
    All target deployment hardware possesses $\ge 4$ GB RAM. Never destroy DOM nodes or wipe canvas contexts on card collapse. Implement a non-destructive lifecycle: `pause()` (halts `requestAnimationFrame` loops and interval timers to save CPU and battery while preserving simulation state and canvas buffers) and `resume()`.

11. **Smart Dual Inlining & File Size Limit (20 MB)**:
    To prevent the 33% Base64 text overhead:
    - Inline raw JavaScript directly in `<script>` tags and CSS directly in `<style>` tags.
    - Reserve Base64 Data URIs (`data:...;base64,`) strictly for binary assets (images, audio, fonts).
    - Maximum self-contained chapter file size is 20 MB with SHA-256 local disk caching and 5s remote network timeouts.

12. **100% Textbook Exercise Utilization & Gamified 3-Tier Scaffolding**:
    Every single problem and exercise from the chapter PDF must be extracted and mapped into the 3-tier gamified progression:
    - **Tier 1: Warm-up** (`#section-warmup`) - Foundational mechanics & MCQs.
    - **Tier 2: Deep Dive** (`#section-deep_dive`) - Multi-step interactive problems linked to visual simulation.
    - **Tier 3: Boss Challenge** (`#section-boss`) - Complex textbook challenge problems.
    All questions must have pre-embedded misconception diagnostics (`m` attribute) and 4-tier progressive hints (`H1` hook $\rightarrow$ `H2` concept $\rightarrow$ `H3` formula $\rightarrow$ `H4` intermediate step) without any answer spoilers (L-Truth standard).

13. **Human-in-the-Loop (HIL) Teacher Console & Instant Browser Preview (`[O]`)**:
    The `multi-agent-tui` console enforces the 4-pillar pedagogical audit, provides a concise Hindi summary (`शिक्षक के लिए सारांश`) for non-technical educators, and enables instant browser verification via the `[O]` keystroke before final `[S]` sign-off.

14. **Python f-string Curly Brace Invariant**:
    In Python code synthesizers generating HTML/CSS/JS via f-strings, all literal braces must be double-escaped as `{{` and `}}` to prevent `NameError` runtime crashes.

15. **Multi-Agent TUI & Streaming JSON IPC Architecture**:
    The system follows a strict two-tier architecture:
    - **Tier 1: Autonomous Pipeline (Headless Background)**:
      • PyMuPDF ingestion & KaTeX math shielding (`packages/aasha-rules/math_insulator.ts`).
      • Phenomenon-First Micro-Worlds matched against Foundations F01–F20 (`Aasha-AI/experience_registry/registry.json`).
      • 3-Tier gamified assessment with strict 0-spoiler misconception diagnostics (`m` attribute).
      • Smart dual inlining (raw `<script>`/`<style>`, Base64 only for binaries, $\le 20\text{ MB}$ ceiling).
      • Emits structured line-delimited streaming events via `--json-events` flag.
    - **Tier 2: Multi-Agent TUI (Educator Standards & Readiness Console)**:
      • **Live Pipeline Monitor**: Real-time stage progress, agent activity stream, multimodal SHA-256 cache hits, and token usage tracker.
      • **4-Pillar Pedagogical Scorecard**:
        1. *Pillar 1: Golden Flow* (Discovery Order: WHAT → WHY → HOW → SHOW → TRY → FEEDBACK → CONNECT → NAME).
        2. *Pillar 2: Two-Layer Rigor* (Layer A Student Clarity vs Layer B Formal Academic/KaTeX Math).
        3. *Pillar 3: Misconception Audit* (100% diagnostic explanations in `m` attribute, strict 0 spoilers).
        4. *Pillar 4: Air-Gapped Child Safety* (0 external URLs, 0 tracking scripts, mobile viewport compliant).
      • **Remediation Workflow**:
        - `[R]`: Targeted Agent Auto-Repair (re-prompts flagged rule/agent).
        - `[E]`: Quick Inline Terminal Patch (in-place interactive regex text patch).
        - `[O]`: Instant browser preview (`शिक्षक पूर्वावलोकन`).
      • **Sign-Off Gating**:
        - Critical Flaws (spoilers, external URLs, corrupted math): HARD LOCKED (`signOffAllowed = false`).
        - Advisories (pacing, reading level): EDUCATOR OVERRIDE allowed.
        - `[S]`: One-Key Final Sign-Off certifying chapter for classroom deployment.

16. **Strict Question Schema Validation Engine**:
    All assessment questions and textbook exercises must be verified using `QuestionSchemaValidator` (`Aasha-AI/benchmarks/question_schema_validator.js` and `packages/aasha-rules/question_schema_validator.ts`). Never allow trivial placeholders (`"Review the concept"`) or numerical answer leaks in misconception explanations or progressive hints. Math text must be normalized (`normalizeMathText`) and short answers (< 3 chars) checked with word-boundary patterns.

17. **Multi-Aspect Ratio Same-Frame Layout Standard**:
    All standalone chapters must pass headless Chrome verification across 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915).
    - Canvas must adapt via `fitCanvas(canvas)` using CSS logical pixels and DPR.
    - Preset bars must never wrap to multi-line (`flex-wrap: nowrap; overflow-x: auto; touch-action: pan-x;`).
    - Viewport overflow is strictly prohibited (`scrollH <= winH + 5`).
    - Touch targets must remain $\ge 44\times 44\text{px}$ across all viewports.
