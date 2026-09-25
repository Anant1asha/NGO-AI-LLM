# Original User Request

## Initial Request — 2026-09-09T20:48:29Z

This is a focused single implementer with adversarial review team; keep it focused and rigorous.

Rebuild both Class 8 Math chapters (**Rational Numbers** and **Exponents & Powers**) as standalone offline interactive HTML webapps overwriting `Aasha-AI/chapters/RationalNumbers_Class8_Gamified_v5_Enhanced_v6.html` and `Aasha-AI/chapters/ExponentsPowers_Class8_Gamified_v5_Enhanced_v6.html`. The rebuild must seamlessly combine the AASHA Universal Teaching Language System on top of the LLE bilingual literacy layer, alongside interactive dual-view simulations and 100% textbook-derived gamified assessments.

Working directory: `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`
Integrity mode: `development`

## Requirements

### R1. Textbook Ground Truth & Zero Spoilers (Rule #1)
Content must be 100% derived from the Class 8 textbook PDFs located in `Aasha-AI/textbook_chapters/Class_8/`. Every assessment, worked example, and step check must target curriculum learning objectives. Distractors must target genuine student misconceptions. Misconception feedback must provide progressive hints without ever stating or computing the target correct answer.

### R2. AASHA Universal Teaching Language System
Implement the pedagogical sequence: **WHAT → WHY → HOW → SHOW → TRY → FEEDBACK → CONNECT → NAME**. Headings must be natural inquiry questions rather than bookish meta-labels. Explanations must articulate the causal *why* behind operations (e.g. why denominator operations must mirror the numerator).

### R3. LLE (Language Layer Engine) Bilingual Substrate — Dual Language Fluency
Do NOT break English sentence structure or grammar. The goal is to build dual-language skills organically through non-intrusive cue connectives (`CONN`) and tap-to-learn interactions. Every English vocabulary term must carry word-level tap-to-reveal Hindi meaning with phonetic English pronunciation in Devanagari script: `[सरल अर्थ] ([देवनागरी उच्चारण])`. The interactive `#wordDialog` modal must include offline Web Speech API TTS audio (`window.speechSynthesis`). Ensure 100% dictionary coverage against `Aasha-AI/experience_registry/aasha_dictionary_db.json` with 0 missing words. Mathematical notation ($x, y, a/b$) must be strictly insulated from word translation.

### R4. Rich Visual Simulations in Same Frame & 5G Mid-End Mobile Optimization
Given that learners have mid-end 5G mobile smartphones, developers have full freedom to utilize rich, high-fidelity visual assets, animations, and pre-built/adaptive resources (file size up to 20MB per chapter). The core pedagogical requirement is that concept definitions and interactive visual simulations/animations MUST appear together in the same frame for immediate feedback loops, rather than stacked after one another. The UI must adapt smoothly across vertical and horizontal mobile orientations with bold, high-contrast text that never blends with backgrounds.

### R5. Gamified Mastery Loop
Include XP rewards, token coins, streak counters, Web Audio API tone synthesis, confetti particle bursts, and badge milestones.

## Verification Resources

The implementing agent and reviewer must execute and pass the existing automated verification suites:
1. **QA L-Truth Benchmark**:
   ```bash
   node Aasha-AI/benchmarks/qa_ltruth_benchmark.js
   ```
   Must score 100/100 across all chapters with 0 answer spoilers and 0 math collisions.
2. **Headless Chrome Browser Automation (CDP)**:
   ```bash
   node "C:\Users\admin\.gemini\antigravity\brain\2a8df84b-dcb7-47dd-856a-cea6f5cdf40e\scratch\automated_browser_verification.js"
   ```
   Must pass with 0 console errors, 0 runtime exceptions, 100% word-tap modal opens, and smooth multi-step progression.

## Acceptance Criteria

### Pedagogical & Visual Presentation
- [ ] Definition and interactive canvas simulation render in the same visual frame on mobile viewports
- [ ] All headings are natural student inquiry prompts (no meta-labels like "The Real-World Hook")
- [ ] Option cards and question texts have distinct high-contrast background and bold text (no color blending)
- [ ] Visual animations and simulations utilize rich, responsive canvas rendering tailored for mid-end 5G devices (within 20MB limit)

### LLE Compliance & Bilingual Scaffolding
- [ ] English grammar and structure remain natural and intact while providing cue connectives and tap-to-learn support
- [ ] 100% of body text words have verified LLE entries in `[सरल अर्थ] ([देवनागरी उच्चारण])` format
- [ ] `#wordDialog` renders English word, Devanagari phonics badge, simple Hindi meaning, and functional 🔊 TTS button
- [ ] Zero instances of "Hindi meaning not available" on word tap
- [ ] Mathematical variables ($x, y, a/b$) are insulated from translation collision

### Programmatic & Technical Tests
- [ ] Standalone offline execution: 0 external CDN dependencies, single HTML file under 20MB per chapter
- [ ] Automated headless Chrome browser CDP test passes with 0 console errors, 0 runtime exceptions, and 0 freezes
- [ ] QA L-Truth benchmark passes 100/100 (0 answer spoilers, 0 math collisions)

## Follow-up — 2026-09-12T22:12:20Z

Transform the Class 8 Rational Numbers textbook PDFs into standalone, self-contained interactive gamified HTML chapters that meet or exceed the V5 minimum build quality benchmark (matching the 6+ MB Class 6 Fractions reference standard), establishing the gold reference before scaling to remaining textbook PDFs.

Working directory: c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
Integrity mode: development

## Requirements

### R1. Textbook Extraction & Foundation Binding
Extract 100% of theory, definitions, number line properties, and exercises from the Rational Numbers textbook PDFs (content/pdfs/AD class 8th math rational number.pdf, MDS  class  8th Rational number learning part.pdf, MDS grade 8th rational number.pdf, Rational numer part 2.pdf). Map the interactive models directly to the AASHA Prebuilt Foundation Registry (F04 PhET / F08 Physics Notebook number line and fraction density models).

### R2. V5 Standalone Architecture & Zero-CDN Self-Containment
Compile the output as a fully standalone, self-contained single HTML file in chapters/ matching the V5 architectural standard:
- Inline all required KaTeX fonts, CSS, and JSXGraph/canvas simulation engines with zero runtime CDN calls.
- Implement the Golden Flow progression: WHAT → WHY → HOW → SHOW → TRY with interactive manipulatives (density zoom, positive/negative rational placement, additive/multiplicative inverses).
- Embed a mobile-responsive layout fitting budget (16:9) and modern (19.5:9, 20:9) viewports with opaque bottom navigation and >= 44x44px touch targets.

### R3. Bilingual Indic (Hindi) LLE Substrate with Math Insulation
Equip the chapter with the bilingual LLE word-tap engine:
- Shield all mathematical notation (\( ... \), $$ ... $$, variables) prior to dictionary tokenization to prevent symbol corruption.
- Provide interactive word-tap definitions and pronunciations in Hindi (#wordDialog modal) for all technical and connective terms.

### R4. 3-Tier Gamified Assessment with 4-Tier Zero-Spoiler Scaffolding
Incorporate 100% of the textbook exercises into a 3-tier gamified challenge:
- Tier 1 (Warm-up): Foundational representation and classification questions.
- Tier 2 (Deep Dive): Density, equivalence, and arithmetic operations linked to the simulation.
- Tier 3 (Boss Challenge): Word problems and multi-step textbook exercises.
- Every question must include pre-embedded misconception diagnostics (m attribute) and 4-tier progressive hints (H1 Hook -> H2 Concept -> H3 Strategy -> H4 Checkpoint) adhering strictly to L-Truth zero-spoiler standards.

### R5. Verification Resources & Quality Certification Gate
The rebuilt chapter must be validated by running the existing test harness:
- node benchmarks/qa_ltruth_benchmark.js: Must achieve 100/100 score with 0 spoilers in misconception explanations, 0 math-rt collisions, and 100% question schema validity.
- Headless Chrome CDP verification: 0 console errors, interactive word-tap functional, canvas active, and mobile viewport assertion scrollH <= winH + 5.

## Acceptance Criteria

### Content Completeness & Self-Containment
- [ ] 100% of textbook exercises from the source Rational Numbers PDFs are represented in the gamified assessment tiers without omission.
- [ ] The generated chapter is completely self-contained in a single .html file with zero external network or CDN calls at runtime.
- [ ] Interactive number line simulation supports density zooming and fractional partitioning with real-time DOM synchronization.

### Benchmark & Quality Guardrails
- [ ] node benchmarks/qa_ltruth_benchmark.js passes with a perfect 100/100 score and 0 rule violations.
- [ ] Zero answer leaks or phrase giveaways in misconception diagnostic explanations.
- [ ] Mathematical formulas and algebraic variables remain completely uncorrupted by bilingual dictionary tokenization.
- [ ] Mobile viewport renders without vertical overflow clipping or semi-transparent nav bleed across 360x640, 390x844, and 412x915 resolutions.

## Follow-up — 2026-09-13T21:32:07Z

Audit, upgrade, and benchmark the existing standalone V6 interactive prototype for Class 8 Mathematics: Rational Numbers (AD Edition) against the source textbook PDF `AD class 8th math rational number.pdf`. Ensure 100% textbook exercise extraction (Exercises 1A, 1B, 1C), zero answer spoilers, full mobile viewport compliance, and certification under the AASHA Dual-Benchmark QA gate.

Working directory: `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI`
Integrity mode: development

## Requirements

### R1. Textbook Audit & Exercise Reconciliation
Compare the existing interactive chapter (`chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` and `chapters/rational_numbers_ad_contract.yaml`) against `content/pdfs/AD class 8th math rational number.pdf`. Ensure all concepts (Stationery shop scenario, fundamental operations, additive/multiplicative identities and inverses, closure, commutativity, associativity, distributivity) and 100% of textbook exercises (Exercises 1A, 1B, 1C) are fully represented across the 3-tier gamified progression.

### R2. Prototype V6 Architectural Upgrade & Math Insulation
Upgrade the chapter to satisfy full AASHA V6 engine standards:
1. Ensure all LaTeX math expressions and algebraic variables are insulated using `__AASHA_MATH_X__` placeholders and `<span class="math-var" data-math="true">` before bilingual dictionary tokenization.
2. Verify that bilingual Hindi word-tap definitions (`window.WM`) display accurate translations, phonetics, and contextual meanings without corrupting mathematical symbols.
3. Ensure interactive manipulatives implement `AashaExperienceContract` with synchronous DOM text state binding and non-destructive `pause()` / `resume()` runtime lifecycle.

### R3. Dual-Benchmark Quality Certification
Subject the upgraded chapter to the AASHA dual-benchmark quality gate:
1. Run `node benchmarks/qa_ltruth_benchmark.js` and ensure a 100/100 score with 0 answer spoilers in misconception diagnostics (`m` attribute) and 4-tier progressive hints (`H1`–`H4`).
2. Run headless Chrome CDP browser automation to verify zero console errors, smooth 5-step navigation, and correct touch interaction.

### R4. Multi-Aspect Ratio Mobile Viewport Invariant
Verify that concept cards, interactive manipulatives, and exercise widgets fit in the same frame without vertical scrolling (`scrollH <= winH + 5`) across 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915) mobile viewports. Ensure all interactive touch targets meet the $\ge 44 \times 44\text{px}$ standard.

### R5. Controlled Offline Environment & Zero Token Bleed
Ensure the chapter remains a 100% self-contained offline package with zero external CDN dependencies and under the 20 MB ceiling. Any model calls must adhere to the Zero-Token Bleed policy (OpenRouter free pool default with paid Gemini reserve strictly locked).

## Acceptance Criteria

### Content & Pedagogical Quality
- [ ] 100% of textbook problems from Exercises 1A, 1B, and 1C of `AD class 8th math rational number.pdf` are mapped and functional.
- [ ] Every question passes `QuestionSchemaValidator` with diagnostic misconception explanations (`m` > 15 characters, no spoilers, no discouraging phrasing) and 4-tier progressive hints.
- [ ] Word-tap popups correctly display Hindi translations and conceptual definitions for key vocabulary.

### Technical & Engine Invariants
- [ ] Zero CDN script or font dependencies; the package is fully offline runnable.
- [ ] Math expressions remain pristine with zero math-rt collisions.
- [ ] Manipulatives maintain 60 FPS and synchronously update DOM readouts upon user interaction.

### Verification Benchmarks
- [ ] `qa_ltruth_benchmark.js` passes with 100/100 and 0 flagged spoilers.
- [ ] Chrome CDP automated browser verification passes with 0 runtime console errors.
- [ ] Mobile viewport height test passes with `scrollH <= winH + 5` on 360x640, 390x844, and 412x915.

## Follow-up — 2026-09-16T20:45:18Z

Deploy an experimental Delta Route (`api/chapters/deltas.js`) on the live Hatchable project (`proj_wDCbCrGwuVqy`) to serve lightweight JSON question item banks for Class 6–8 Mathematics, supporting hybrid offline delivery where HTML5 chapters are distributed via WhatsApp group / SD card and deltas sync via Wi-Fi.

Working directory: c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
Integrity mode: development
Requested team: Full team

## Core MVP Mission & Pedagogical Directives
- **Key Task**: Transform textbook PDFs into AI/LLM-generated visual learning and gamified assessments with **100% of textbook exercises mapped** (zero dropped exercises from the student's book).
- **Gamified 3-Tier Scaffolding**: Questions must map cleanly into:
  1. Tier 1: Warm-up (`#section-warmup`) — Core recall & visual concept anchoring
  2. Tier 2: Deep Dive (`#section-deep_dive`) — Worked examples & procedure drills
  3. Tier 3: Boss Challenge (`#section-boss`) — Multi-step cognitive problem solving
- **Foundation Reuse**: Incorporate prebuilt visual foundations (F01–F20, SVG manipulatives, KaTeX notation, canvas engines).
- **Distribution Reality**: Standalone single-file HTML5 chapters are distributed via WhatsApp groups / local SD cards to 80 student tablets for zero-bandwidth offline learning. Hatchable acts as the headless cloud infrastructure for serving updated JSON item bank deltas when tablets connect to Wi-Fi.

## Requirements

### R1. Delta Route Implementation (`api/chapters/deltas.js`)
Implement `api/chapters/deltas.js` in the Hatchable isolate project (`proj_wDCbCrGwuVqy`) exposing versioned, lightweight JSON question banks for:
- Class 6 Mathematics: Fractions (Fraction bars, visual partition models, equivalent fractions, 100% textbook exercises)
- Class 7 Mathematics: Perimeter & Area (2D grid models, decomposition, geometric measurement)
- Class 8 Mathematics: Rational Numbers & Linear Equations (Balance scale models, algebraic identities, number line density)
Every route must declare `export const access = "public"` and support query filtering (`?grade=N` or `?chapter=ID`).

### R2. Strict Pedagogy & Anti-Spoiler Compliance (L-Truth Ground Truth)
All question items in delta banks must comply with Aasha L-Truth rules:
- 4 options, exactly 1 correct answer.
- Non-empty verbal misconception diagnostic in `m` attribute for every distractor.
- Zero answer spoilers in explanations (prohibiting leaks like "is", "becomes", "yielding", "result is", "should be").
- 4-tier scaffolding hints (`H1` hook -> `H2` concept -> `H3` formula -> `H4` intermediate step) with zero final answer revelations.

### R3. Safe Deployment & Live Verification
- Use Hatchable MCP tools (`write_files`, `dry_run_deploy`, `deploy`) to publish the delta route to `proj_wDCbCrGwuVqy`.
- Programmatically verify the live endpoint with `run_function` across query parameters (`?grade=6`, `?grade=7`, `?grade=8`).
- Verify that response payloads remain compact (<50 KB per grade) for high-speed download on mobile hotspots.

## Acceptance Criteria

### API Contract & Performance
- [ ] `GET /api/chapters/deltas` returns HTTP 200 with a structured JSON array of curriculum deltas.
- [ ] Querying by grade (e.g. `?grade=8`) filters response to matching curriculum nodes only.
- [ ] Response payload is compact (<50 KB) to ensure rapid download on 2G/mobile hotspots.

### L-Truth & Schema Verification
- [ ] 100% of questions in the item bank pass Zero-Spoiler validation.
- [ ] All distractors include cognitive misconception diagnostics (`m` attribute).
- [ ] 4-tier progressive scaffolding hints (`H1`–`H4`) present for every question.

### Live Platform Deployment
- [ ] `dry_run_deploy` returns `ok: true` with zero errors.
- [ ] `deploy` increments project version cleanly on `proj_wDCbCrGwuVqy`.
- [ ] `run_function` returns status 200 with verified payload.

## Follow-up — 2026-09-16T20:47:52Z

[SUPER ADMIN DIRECTIVE & SPECIFICATION UPDATE]
The project owner has provided mandatory pedagogical and foundation guidelines for the Class 6-8 item banks and delta routes:

1. Language Layer & Bilingual Semantics:
   - Adhere to the AASHA Universal Teaching Language System.
   - Include Hindi bilingual word-tap popups and conceptual definitions (`window.WM` / `rt()`).
   - Strictly enforce Pre-LLE Mathematical Insulation: shield all LaTeX formulas and algebraic variables before applying bilingual wrapping to avoid corrupting math symbols.

2. Visual Interactions, Animations & Sims:
   - Every concept node in the delta must bind to a visual manipulative specification (interactive SVG fraction bars, 2D perimeter/area grid models, balance scale equations, KaTeX notation).
   - Ensure visual animations and simulations demonstrate conceptual understanding rather than rote calculation.

3. Prebuilt Foundation Integration (Escape Run & F01-F20):
   - Leverage Foundation F01 (Escape Run) mechanics for the Tier 3 Boss Challenge (`#section-boss`), with timed cognitive obstacle evasion and streak multipliers.
   - Map 100% of textbook exercises into the 3-tier gamified taxonomy (Warm-up -> Deep Dive -> Boss Challenge) with zero dropped textbook problems.

Incorporate these visual sim schemas, F01 Escape Run mechanics, and LLE semantic metadata into the JSON delta payload in `api/chapters/deltas.js`.

## Follow-up — 2026-09-18T22:51:46Z

Transform the PDF "square and cube RL public school and ncert.pdf" located at C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\content\pdfs into a complete AASHA learning and gamified assessment chapter HTML adhering to AASHA Universal Teaching Language, Section 24 YAML contracts, bilingual Hindi LLE substrate, zero-spoiler 4-tier hints, and <aasha-sim> interactive simulations.

Working directory: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
Integrity mode: development

## Requirements

### R1. Textbook Ingestion & Section 24 Contract Generation
Extract 100% of textbook exercises, theory, and misconception diagnostics from content/pdfs/square and cube RL public school and ncert.pdf. Generate and validate the Section 24 YAML Content Contract via npm run chapter:init with math insulation and zero-spoiler 4-tier hints (H1 -> H4).

### R2. Gamified Assessment & Interactive Chapter Synthesis
Compile the self-contained chapter HTML featuring <aasha-sim> Web Component adapters for interactive manipulatives (Square Roots & Cube Roots visualizer), 3-tier gamified assessment (Warm-up, Deep Dive, Boss Challenge), bilingual Indic (Hindi) word-tap popups (window.WM), and non-destructive DOM runtime lifecycle.

### R3. Dual-Benchmark Verification & CDP Certification
Verify the chapter against benchmarks/qa_ltruth_benchmark.js (100/100 score, 0 spoilers, 0 math-rt collisions) and Headless Chrome CDP automation (automated_browser_verification.js) ensuring 0 console errors, same-frame mobile responsiveness (16:9, 19.5:9, 20:9), and screenshot capture.

## Acceptance Criteria

### Content & Contract Integrity
- [ ] 100% of textbook exercises mapped to 3-tier gamified assessments without missing questions.
- [ ] Section 24 contract passes QuestionSchemaValidator with zero spoilers in misconception explanations (m).
- [ ] All math formulas insulated via __AASHA_MATH_X__ before dictionary tokenization.

### Interactive & Responsive UI
- [ ] Self-contained HTML file (inline JS/CSS) under 20 MB ceiling.
- [ ] Fits comfortably on mobile viewports (16:9, 19.5:9, 20:9) without horizontal or unintended vertical scrolling (scrollH <= winH + 5).
- [ ] Interactive <aasha-sim> implements full AashaExperienceContract (mount, getState, reset, destroy, telemetry).

### Quality & Benchmark Certification
- [ ] 100/100 L-Truth QA score on static analysis.
- [ ] 0 console errors during CDP browser navigation across all screens.
- [ ] Evidence screenshots generated and stored in app data.

## Follow-up — 2026-09-18T23:10:23Z

# Teamwork Project Prompt — Square and Cube Roots Chapter Transformation

Transform Class 8 "Square and Cube Roots" textbook PDF located at `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\content\pdfs\square and cube RL public school and ncert.pdf` into a fully responsive, bilingual (Hindi-insulated), 3-tier gamified learning and assessment chapter HTML (`SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html`) adhering strictly to the AASHA Universal Teaching Language System, Zero-Spoiler L-Truth standard, and Dual-Benchmark certification.

Working directory: `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`
Integrity mode: development

## Requirements

### R1. PDF Content Ingestion & Section 24 Contract Creation
Extract 100% of textbook exercises, formulas, and conceptual definitions from `square and cube RL public school and ncert.pdf`. Generate Section 24 Content Contract (`content/contracts/Mathematics_Class8_squares_and_cubes.yaml`) with math insulation (`__AASHA_MATH_X__`), non-spoiler misconception diagnostics (`m`), and 4-tier progressive hints ($H_1 \rightarrow H_4$).

### R2. Simulation Adaptation & Experience Registry Integration
Query `experience_registry/registry.json` and adapt prebuilt math simulation engines into standardized `<aasha-sim>` Web Component contracts (`mount`, `getState`, `reset`, `destroy`, `telemetry`) for interactive square building, prime factorization, estimation, and cube root block counting.

### R3. Autonomous Gamified Chapter HTML Synthesis
Synthesize the single-file self-contained HTML chapter at `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html`. Include 3 gamified tiers (#section-warmup, #section-deep_dive, #section-boss), non-destructive DOM state transitions (`pause()`/`resume()`), KaTeX math rendering, and Hindi word-tap dictionary (`window.WM`).

### R4. Dual-Benchmark Quality Certification & CDP Verification
Validate the synthesized chapter against `benchmarks/qa_ltruth_benchmark.js` (target 100/100 score, 0 math-rt collisions, 0 spoiler leaks) and run headless CDP browser verification across mobile viewports (16:9, 19.5:9, 20:9) enforcing `scrollH <= winH + 5` and touch target clearance.

## Acceptance Criteria

### Content & Quality Certification
- [ ] 100% textbook exercise utilization from the PDF with zero dropped questions.
- [ ] 100/100 score on L-Truth static QA benchmark with zero spoilers in `m` fields.
- [ ] All math formulas and variables insulated from bilingual dictionary wrapping.

### User Experience & Viewport Compliance
- [ ] Same-frame mobile viewport responsiveness (`scrollH <= winH + 5`) across 360x640, 390x844, and 412x915 viewports.
- [ ] Touch targets adhere to minimum 44x44px target size.
- [ ] Fully opaque bottom navigation clearance with backdrop filter blur.

### Runtime Engine & Execution
- [ ] Standalone HTML file size under 20 MB ceiling with inlined JS/CSS.
- [ ] Automated Chrome CDP test suite executes with 0 console errors and 100% step completion.


