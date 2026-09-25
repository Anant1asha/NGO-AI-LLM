# Project: Class 8 Square and Cube Roots Standalone Gamified Chapter

## Architecture
- **Target Single-File Monolith**: `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html`
- **Zero-CDN Offline Self-Containment**:
  - 100% offline self-containment with zero external network or CDN calls at runtime.
  - Inlined system math typography (`Cambria Math`, `Times New Roman`, serif) and KaTeX WOFF2 data URIs.
  - Native procedural HTML5 Canvas 2D simulation engines (`drawSquareGridSim`, `drawIsoCubeSim`, `drawPrimeFactorSim`, `drawLockerRiddleSim`, `drawCubeEstimatorSim`).
  - Web Audio API procedural sound synthesis (`tap`, `correct`, `wrong`, `levelup`).
  - HTML5 Canvas particle confetti burst engine.
- **Same-Frame Mobile Viewport Responsiveness Invariant**:
  - Guaranteed simultaneous rendering of concept definition and interactive visual simulation in the exact same viewport frame across 16:9 (360x640), 19.5:9 (390x844, 393x852), and 20:9 (412x915, 360x800) aspect ratios.
  - `.screen { min-height: 0; }` with height-tiered media query clamping for `.concept-def` (80px / 110px / 125px) and `.sim-canvas` (92px / 115px / 125px).
  - Single-row horizontal swipe `.preset-bar` (`touch-action: pan-x; flex-wrap: nowrap; overflow-x: auto;`).
  - Minimum 44x44px touch targets on all interactive buttons.
  - Fully opaque fixed bottom navigation bar with `backdrop-filter: blur(20px)` and safe-area-inset bottom padding (`padding-bottom: calc(96px + env(safe-area-inset-bottom, 16px))`).
- **Bilingual Indic (Hindi) LLE Substrate & Math Insulation**:
  - Pre-LLE mathematical expression shielding via `packages/aasha-rules/math_insulator.ts` (`__AASHA_MATH_X__` placeholders and `<span class="math-var" data-math="true">`).
  - Comprehensive inlined dictionary (`window.WM = { ... }`) covering all chapter vocabulary from `experience_registry/aasha_dictionary_db.json`.
  - Interactive `#wordDialog` modal with Devanagari phonics badge, simple Hindi meaning, Web Speech API TTS audio (`window.speechSynthesis` with `en-IN` voice priority), and suffix stemming fallback.
- **Gamified 3-Tier Assessment & Scaffolding**:
  - 100% of textbook exercises (34 distinct question items) from `square and cube RL public school and ncert.pdf` partitioned into Tier 1 (Warm-Up: 12 items), Tier 2 (Deep Dive: 14 items), and Tier 3 (Boss Challenge: 8 items).
  - Pre-embedded misconception diagnostics (`m` attribute) with zero spoilers adhering to L-Truth standards.
  - 4-Tier progressive hints ($H_1$ Hook $\rightarrow$ $H_2$ Concept $\rightarrow$ $H_3$ Strategy $\rightarrow$ $H_4$ Procedure).

## Feature Inventory
Every feature enumerated from the Phase 0 Survey across the source PDF, pipeline, and simulation registry:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Source PDF Ground Truth & Exercise Extraction | 100% extraction of 34 question items (28 in-text + 9 Fig It Out p.10 + 5 Fig It Out p.16-17 + 2 p.18 puzzles) from `square and cube RL public school and ncert.pdf` | M1 | Survey |
| 2 | Section 24 YAML Reusable Content Contract | Creation and validation of `content/contracts/Mathematics_Class8_squares_and_cubes.yaml` via `npm run chapter:init` with math insulation and 4-tier hints | M1 | Survey |
| 3 | Question Schema & Anti-Spoiler Quality Assurance | Validation of all 34 questions via `QuestionSchemaValidator` with non-empty `m` (> 11 chars), zero spoilers, zero leak predicates, and 4-tier hints | M1 | Survey |
| 4 | Foundation Registry Matching & Contract | Binding prebuilt foundations (F01 Escape Run, F02 MicroSims, F04 PhET, F08 Physics Notebook) to `<aasha-sim>` Web Component contract | M2 | Survey |
| 5 | 2D Square Grid & Gnomon Visualizer Sim | Interactive 2D grid manipulative with side slider $s \in [1, 10]$, area display, and odd-layer peeling | M2 | Survey |
| 6 | 3D Isometric Cube Stacker Sim | 60 FPS 2D Canvas isometric 3D projection of $n \times n \times n$ blocks, layer slicing, and odd-sum sequence | M2 | Survey |
| 7 | Prime Factor Grouping Tree Sim | Manipulative for prime factor pairing ($\sqrt{N}$), tripling ($\sqrt[3]{N}$), and orphan multiplier/divisor identification | M2 | Survey |
| 8 | 100-Locker Riddle & Ending Digit Explorer Sim | Parity factor explorer proving square locker condition and ending digit bijection | M2 | Survey |
| 9 | Rapid 3-Digit Grouping Cube Estimator Sim | Tens and units bracket isolation manipulative for large perfect cubes | M2 | Survey |
| 10 | Monolithic HTML Shell & Zero-CDN Core | Standalone HTML document structure with zero runtime CDN calls, inlined CSS, JS, and SVG assets | M3 | Survey |
| 11 | Same-Frame Mobile Viewport Engine | CSS layout with `.screen { min-height: 0; }` and height-tiered clamping for 16:9, 19.5:9, and 20:9 | M3 | Survey |
| 12 | Opaque Bottom Nav & Touch Target Guardrails | Opaque navbar surface with backdrop blur, safe-area bottom clearance, and $\ge 44\times 44\text{px}$ touch targets | M3 | Survey |
| 13 | Web Audio API Procedural Sound Engine | Zero-dependency tone generator for `tap`, `correct`, `wrong`, and `levelup` frequencies | M3 | Survey |
| 14 | Confetti Particle Celebration FX | Inlined HTML5 Canvas particle system for mastery and milestone achievements | M3 | Survey |
| 15 | Pre-LLE Mathematical Formula Insulation | Shielding LaTeX notation and variables using `__AASHA_MATH_X__` placeholders and `<span class="math-var">` | M3 | Survey |
| 16 | Inlined Hindi Dictionary Substrate | Direct embedding of vocabulary terms from `experience_registry/aasha_dictionary_db.json` in `window.WM` | M3 | Survey |
| 17 | Connective Word Scaffolding (`CONN`) | Inline dual-language connective tags for natural reasoning flow (`because`, `therefore`, `if`) | M3 | Survey |
| 18 | Interactive `#wordDialog` Modal | Tap-to-reveal modal displaying word, Devanagari phonics badge, and simple Hindi meaning | M3 | Survey |
| 19 | Web Speech API Offline Phonics Audio | In-browser TTS speech synthesis with `en-IN` voice preference and suffix stemming fallback | M3 | Survey |
| 20 | Golden Flow Pedagogical Progression | WHAT (Inquiry) $\rightarrow$ WHY $\rightarrow$ HOW (WE) $\rightarrow$ SHOW (Sim) $\rightarrow$ TRY $\rightarrow$ FEEDBACK $\rightarrow$ CONNECT $\rightarrow$ NAME | M4 | Survey |
| 21 | Tier 1: Warm-Up Assessment Integration | Foundational properties, ending digits, square/cube identification (12 questions) | M4 | Survey |
| 22 | Tier 2: Deep Dive Assessment Integration | Prime factorisation, smallest multiplier/divisor, Pythagorean triplets, cube roots (14 questions) | M4 | Survey |
| 23 | Tier 3: Boss Challenge Assessment Integration | Multi-step word problems, 100-locker riddle, Queen Ratnamanjuri vault puzzle, Page 18 square pairs (8 questions) | M4 | Survey |
| 24 | L-Truth Zero-Spoiler Scaffolding | Pre-embedded progressive hints ($H_1 \rightarrow H_4$) with zero answer leaks or spoiler phrases | M4 | Survey |
| 25 | Gamified Mastery Economy & Feedback | XP rewards, token coins, streak counters, and badge milestones | M4 | Survey |
| 26 | QA L-Truth Benchmark 100/100 Certification | Automated execution of `qa_ltruth_benchmark.js` achieving 100/100, 0 spoilers, 0 rule violations | M5 | Survey |
| 27 | Headless Chrome CDP Responsiveness Certification | Automated execution of `automated_browser_verification.js` across 5 viewports with 0 errors | M5 | Survey |
| 28 | Adversarial Coverage Hardening (Tier 5) | Stress testing corner cases, large cube roots, non-square factor parity, and zero division | M5 | Survey |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Content Contract & Textbook Ingestion | Section 24 YAML contract (`content/contracts/Mathematics_Class8_squares_and_cubes.yaml`), 100% textbook question extraction (34 items) & schema validation in `chapters/square_cube_questions.json`, F01/F02/F04/F08 mapping | none | PLANNED |
| M2 | Interactive Simulation Engines & `<aasha-sim>` | 5-manipulative suite (2D square grid & gnomon, 3D isometric cube stacker, prime factor pairing/tripling tree, 100-locker parity explorer, rapid 3-digit cube estimator) implementing `AashaExperienceContract` with non-destructive pause/resume and synchronous DOM state binding | M1 | PLANNED |
| M3 | Bilingual Indic (Hindi) LLE Substrate & Architecture | Math insulator (`__AASHA_MATH_X__`), dictionary embedding in `window.WM`, `#wordDialog` modal, TTS audio, monolithic HTML shell, same-frame mobile layout (16:9, 19.5:9, 20:9), opaque bottom nav, Web Audio, and confetti engine | M2 | PLANNED |
| M4 | 3-Tier Gamified Assessment & Full Chapter Assembly | Golden Flow pedagogical loop, 100% textbook exercises across Tiers 1-3, zero-spoiler hints ($H_1 \to H_4$), gamified telemetry, Boss Challenge Queen Ratnamanjuri jewel vault puzzle | M2, M3 | PLANNED |
| M5 | Dual-Benchmark Quality Certification & Hardening | Phase 1: Pass 100% E2E tests (`qa_ltruth_benchmark.js` 100/100, Chrome CDP across 5 viewports); Phase 2: Adversarial coverage hardening | M4 | PLANNED |

## Interface Contracts

### Content Contract ↔ Chapter Assembler
- **Schema**: Section 24 YAML format in `Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml`.
- **Fields**: `subject: Mathematics`, `class: 8`, `topic: Squares and Cubes`, `foundations: [F01, F02, F04, F08]`, `pedagogical_flow: [WHAT, WHY, HOW, SHOW, TRY, FEEDBACK, CONNECT, NAME]`, `exercises: [Tier1, Tier2, Tier3]`.
- **Output Format**: Clean JSON structure consuming `chapters/square_cube_questions.json` (34 validated textbook questions: Warm-up: 12, Deep Dive: 14, Boss: 8) and Section 24 contract.

### `<aasha-sim>` Web Component ↔ Chapter Core
- **Interface**: `AashaExperienceContract`
  - `mount(container: HTMLElement, config: object): void`
  - `getState(): object`
  - `pause(): void` (Halts requestAnimationFrame and interval timers off-screen)
  - `resume(): void` (Restarts rendering loop without destroying canvas or state)
  - `reset(): void`
  - `destroy(): void`
- **Events**:
  - `aasha:telemetry`: Emits `{ type: string, detail: object }` for mastery tracking.
  - `aasha:state_change`: Emits `{ state: object }` for synchronous DOM state binding.

### MathInsulator ↔ LLE Lexer
- **Input**: Raw HTML / Markdown string containing LaTeX (`\( ... \)`, `$$ ... $$`, `$...$`) and variables.
- **Transformation**: Replaces all mathematical expressions with `__AASHA_MATH_${counter}__` placeholders.
- **LLE Processing**: Lexer tokenizes words, wraps technical terms with `rt('word')` and connectives with `CONN`.
- **Restoration**: Restores placeholders into `<span class="math-var" data-math="true">${formula}</span>`.
- **Invariant**: Zero math-rt collisions, zero single-letter translation lookups.

## Code Layout
- Target Chapter Artifact:
  - `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html`
- Source Reference Chapters:
  - `Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` (Reference Standard)
  - `Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html` (PhET Inlined Reference)
- Governance & Contracts:
  - `Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml`
  - `Aasha-AI/chapters/square_cube_questions.json`
  - `Aasha-AI/packages/chapter-contract-manager.ts`
  - `Aasha-AI/packages/aasha-rules/aasha_gatekeeper.ts`
  - `Aasha-AI/packages/aasha-rules/math_insulator.ts`
- Verification Harnesses:
  - `Aasha-AI/benchmarks/qa_ltruth_benchmark.js`
  - `Aasha-AI/benchmarks/question_schema_validator.js`
  - `Aasha-AI/benchmarks/automated_browser_verification.js`
- Test Infrastructure Document:
  - `TEST_INFRA.md`
- Test Readiness Signal:
  - `TEST_READY.md`
