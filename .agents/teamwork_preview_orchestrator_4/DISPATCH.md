## 2026-09-16T20:49:07Z
You are the Project Orchestrator (teamwork_preview_orchestrator).

## Your Mission
Deploy an experimental Delta Route (`api/chapters/deltas.js`) on the live Hatchable project (`proj_wDCbCrGwuVqy`) to serve lightweight JSON question item banks for Class 6–8 Mathematics, supporting hybrid offline delivery where HTML5 chapters are distributed via WhatsApp group / SD card and deltas sync via Wi-Fi.

## Working Context & Metadata
- **Your Working Directory**: `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_orchestrator_4`
- **Project Directory**: `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`
- **Authoritative Request**: `c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md`
- **Parent (Sentinel)**: `ed39879c-4353-4d5c-aa9c-0af29c71b106`

## Core Requirements & Specifications
1. **R1. Delta Route Implementation (`api/chapters/deltas.js`)**:
   Implement `api/chapters/deltas.js` in the Hatchable isolate project (`proj_wDCbCrGwuVqy`) exposing versioned, lightweight JSON question banks for:
   - Class 6 Mathematics: Fractions (Fraction bars, visual partition models, equivalent fractions, 100% textbook exercises)
   - Class 7 Mathematics: Perimeter & Area (2D grid models, decomposition, geometric measurement)
   - Class 8 Mathematics: Rational Numbers & Linear Equations (Balance scale models, algebraic identities, number line density)
   Declare `export const access = "public"` and support query filtering (`?grade=N` or `?chapter=ID`).

2. **R2. Strict Pedagogy & Anti-Spoiler Compliance (L-Truth Ground Truth)**:
   - 4 options, exactly 1 correct answer.
   - Non-empty verbal misconception diagnostic in `m` attribute for every distractor.
   - Zero answer spoilers in explanations (prohibiting leaks like "is", "becomes", "yielding", "result is", "should be").
   - 4-tier scaffolding hints (`H1` hook -> `H2` concept -> `H3` formula -> `H4` intermediate step) with zero final answer revelations.

3. **R3. Safe Deployment & Live Verification**:
   - Use Hatchable MCP tools (`write_files`, `dry_run_deploy`, `deploy`) to publish the delta route to `proj_wDCbCrGwuVqy`.
   - Programmatically verify the live endpoint with `run_function` across query parameters (`?grade=6`, `?grade=7`, `?grade=8`).
   - Verify that response payloads remain compact (<50 KB per grade) for high-speed download on mobile hotspots.

4. **R4. Super Admin Directives & Pedagogical Guidelines**:
   - Language Layer & Bilingual Semantics: AASHA Universal Teaching Language System, Hindi bilingual word-tap popups/definitions (`window.WM` / `rt()`), strictly enforce Pre-LLE Mathematical Insulation.
   - Visual Interactions & Sims: Bind concept nodes to visual manipulative specifications (interactive SVG fraction bars, 2D perimeter/area grid models, balance scale equations, KaTeX notation).
   - Prebuilt Foundation Integration: Leverage Foundation F01 (Escape Run) mechanics for Tier 3 Boss Challenge (`#section-boss`), with timed cognitive obstacle evasion and streak multipliers. 100% textbook exercises mapped across Warm-up -> Deep Dive -> Boss Challenge with zero dropped problems.

## Execution Rules
- Maintain your own `progress.md` and `BRIEFING.md` in `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_orchestrator_4`.
- Coordinate specialists or execute the workflow per standard orchestrator protocol.
- Once completed and independently validated, send your completion handoff report to Sentinel (`ed39879c-4353-4d5c-aa9c-0af29c71b106`).
