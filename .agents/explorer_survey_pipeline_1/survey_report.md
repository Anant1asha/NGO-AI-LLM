# AASHA Pipeline & Tooling Survey Report: Square and Cube Roots Chapter Rebuild

**Author**: `explorer_survey_pipeline_1`  
**Date**: 2026-09-18  
**Target Workspace**: `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`  
**Source PDF**: `content/pdfs/square and cube RL public school and ncert.pdf`  
**Reference Benchmark**: Dual-Benchmark (L-Truth 100/100 + Headless Chrome CDP)

---

## 1. Executive Summary

This report documents the end-to-end architecture, tools, contracts, and quality benchmarks of the AASHA Learning Ecosystem in `Aasha-AI`. It establishes the exact code paths, commands, schemas, and structural patterns required to transform the Class 8 textbook PDF `square and cube RL public school and ncert.pdf` into a standalone, offline, gamified interactive chapter adhering strictly to AASHA Universal Teaching Language standards, Section 24 YAML contracts, L-Truth anti-spoiler rules, and same-frame mobile responsiveness across 16:9, 19.5:9, and 20:9 viewports.

---

## 2. Pipeline Architecture & CLI Tooling

### 2.1 Package Scripts & CLI Commands (`package.json` & `admin_memory_cli.ts`)

In `Aasha-AI/package.json`:
```json
{
  "scripts": {
    "admin:status": "tsx admin_memory_cli.ts status",
    "admin:backup": "tsx admin_memory_cli.ts backup",
    "admin:rules": "tsx admin_memory_cli.ts rules",
    "admin:seed": "tsx admin_memory_cli.ts seed-rules",
    "admin:seed-foundations": "tsx admin_memory_cli.ts seed-foundations",
    "admin:match": "tsx admin_memory_cli.ts match-foundation",
    "admin:init-chapter": "tsx admin_memory_cli.ts init-chapter",
    "chapter:init": "tsx admin_memory_cli.ts init-chapter",
    "admin:experience": "tsx admin_memory_cli.ts add-experience",
    "admin:learn": "tsx admin_memory_cli.ts learn",
    "test:ltruth": "node benchmarks/qa_ltruth_benchmark.js",
    "test:all": "node benchmarks/qa_ltruth_benchmark.js"
  }
}
```

#### Key Execution Commands
1. **Foundation Matching**:
   ```bash
   npm run admin:match -- Mathematics 8 "Squares and Cubes"
   ```
   *Behavior*: Queries `experience_registry/registry.json`, matches foundations by subject (`Mathematics`) and class (`8`), and outputs the **Mandatory Resource Match Report**. For Class 8 Math, matches include `F01 (Escape Run)`, `F02 (MicroSims)`, `F04 (PhET)`, `F05 (Lightbot)`, `F06 (MathFluency)`, and `F15 (The Long Game)`.

2. **Chapter Initialization & Section 24 Contract Creation**:
   ```bash
   npm run chapter:init -- Mathematics 8 "Squares and Cubes"
   ```
   *Behavior*: Invokes `ChapterContractManager.ensureChapterContract()`. Creates `content/contracts/Mathematics_Class8_squares_and_cubes.yaml` if missing, binds foundation F01/F02, and seeds the chapter node into the local Knowledge Graph SQLite store.

3. **Dual-Benchmark Quality Verification**:
   ```bash
   node benchmarks/qa_ltruth_benchmark.js --file chapters/<Generated_Chapter>.html
   ```
   *Behavior*: Runs static analysis against 10 critical QA rules, Rule #1 zero spoilers, math-rt collisions, and Know-stage pedagogy.
   ```bash
   node benchmarks/automated_browser_verification.js
   ```
   *Behavior*: Launches headless Chrome over CDP, testing 5 mobile viewports (360x640, 390x844, 393x852, 412x915, 360x800) for `scrollH <= winH + 5`, word-tap popup Hindi definitions, 44x44px touch targets, and continuous 5-step navigation.

---

## 3. Section 24 YAML Reusable Content Contracts

### 3.1 Contract Location and Taxonomy
Contracts reside in `content/contracts/` and `chapters/`:
- `content/contracts/Mathematics_Class8_rational_numbers.yaml` (Section 24 specification contract)
- `chapters/rational_numbers_ad_contract.yaml` (Exhaustive 75-question textbook exercise mapping & pedagogy breakdown)
- `chapters/exponents_powers_contract.yaml` (Concept definitions, worked examples, and misconception feedback)

### 3.2 Required Section 24 Schema Structure
To satisfy `packages/chapter-contract-manager.ts` and `aasha_gatekeeper.ts`:
```yaml
chapter_meta:
  subject: "Mathematics"
  class: 8
  topic: "Squares and Cubes"
  slug: "squares_and_cubes"
  version: "1.0.0"
  created_at: "2026-09-18T22:53:25Z"

resource_match_report:
  matched_foundation_id: "F01"
  matched_foundation_name: "Escape Run"
  source_repo: "https://github.com/abhas9/escape-run"
  reuse_strategy: "EXTRACT"
  license: "MIT"
  telemetry_compliant: true
  same_frame_mobile_viewport: true

pedagogy_structure:
  golden_rule_stages:
    - "WHAT"
    - "WHY"
    - "HOW"
    - "SHOW"
    - "TRY"
    - "FEEDBACK"
    - "CONNECT"
    - "NAME"
  teaching_mode: "Notice -> Represent -> Reason"

curriculum_intent:
  core_concepts:
    - id: "concept_1"
      title: "Perfect Squares & Geometric Dot Patterns"
      hook: "Arrange pebbles in equal rows and columns: 1x1, 2x2, 3x3, 4x4. Why do only certain numbers form complete squares?"
      why_type: "Conceptual"
      explanation_student_layer: "A square number is the area of a square whose side is an integer."
      academic_precision_layer: "A natural number n is a square number if n = m² for some natural number m."
    - id: "concept_2"
      title: "Properties of Square Numbers (Units Digits & Zeros)"
    - id: "concept_3"
      title: "Square Roots: Inverse Operation & Prime Factorization"
    - id: "concept_4"
      title: "Long Division Method for Square Roots & Decimals"
    - id: "concept_5"
      title: "Perfect Cubes & Cube Roots by Estimation and Factorization"

misconceptions:
  - id: "misc_square_vs_double"
    trigger_error: "Confusing squaring a number with multiplying by 2 (e.g. 5² = 10 instead of 25)"
    feedback_4_tier_hints:
      hint_1_attention: "Look at the exponent 2 above the base."
      hint_2_relationship: "Squaring represents multiplying the base by itself, not multiplying by two."
      hint_3_strategy: "Write out the repeated multiplication: base multiplied by base."
      hint_4_procedure: "Calculate base times base to find the geometric area."
    zero_spoiler_explanation: "Doubled the base rather than performing repeated multiplication by itself."

simulation_adapter:
  contract_interface: "AashaExperienceContract"
  target_foundation: "F01"
  container_id: "sim-container"
  methods_implemented:
    - "mount"
    - "getState"
    - "reset"
    - "destroy"
    - "telemetry"

lle_bilingual_insulation:
  math_insulation_enabled: true
  target_languages: ["hi"]
  dictionary_substrate: "window.WM"

assessment_suite:
  total_questions: <Total Extracted from PDF>
  tiers:
    tier_1_warmup:
      title: "Level 1: Warm-Up Drills (Direct Identification, Unit Digits, Mental Squares)"
      count: <Count>
    tier_2_deep_dive:
      title: "Level 2: Deep Dive Challenges (Prime Factorization, Long Division, Smallest Multipliers)"
      count: <Count>
    tier_3_boss:
      title: "Level 3: Boss Challenge (Multi-Step Geometry, Word Problems, Estimation Drills)"
      count: <Count>
```

---

## 4. Anti-Spoiler & Schema Validation Engine (`packages/aasha-rules/`)

### 4.1 Four Core Source Files
1. `aasha_rules.ts` (8,676 bytes):
   - Direct programmatic implementation of Sections 1–24.
   - Prohibits superficial hype (`fun adventure 🚀`, `super-duper`), scientific dilution (`water disappearing`), and purely negative evaluative feedback (`❌ incorrect`).
   - Defines Subject Teaching Modes (Math: `Notice -> Represent -> Reason -> Calculate -> Verify -> Generalize`).
2. `math_insulator.ts` (1,830 bytes):
   - `MATH_PATTERNS`:
     - Display LaTeX: `/\\\[[\s\S]*?\\\]/g`
     - Inline LaTeX: `/\\\([\s\S]*?\\\)/g`
     - Display TeX: `/\$\$[\s\S]*?\$\$/g`
     - Inline TeX: `/\$[^\$\n]+?\$/g`
     - Math spans: `/<span[^>]*class=["'][^"']*math[^"']*["'][^>]*>[\s\S]*?<\/span>/gi`
   - `tokenize(text)`: Masks expressions with `__AASHA_MATH_N__` before dictionary tokenization.
   - `restore(maskedText, tokenMap)`: Restores original formulas.
   - `wrapWithIsolation(formula)`: Wraps in `<span class="math-var" data-math="true">${formula}</span>`.
3. `aasha_gatekeeper.ts` (4,894 bytes):
   - `auditDeterministic(content, agentRole)`:
     - Section 16 & 13 Prohibited Phrase checks.
     - Section 15 Formal LaTeX Delimiter Parity check (`\(` vs `\)`, `\[` vs `\]`).
     - Section 11 & 12 Question and Distractor checks via `QuestionSchemaValidator`.
4. `question_schema_validator.ts` (21,567 bytes):
   - Strict validator for individual distractors, question items, exercise banks, and chapter HTML DOM.

### 4.2 Exact Spoiler and Distractor Quality Rules
- **Correct Option (`c: true`)**:
  - `m` attribute MUST be empty (`RULE_1_CORRECT_OPTION_M_EMPTY`).
- **Distractor Option (`c: false`)**:
  - `m` CANNOT be empty (`RULE_1_MISSING_MISCONCEPTION`).
  - `m` CANNOT be trivial or < 12 characters (`RULE_1_LOW_QUALITY_MISCONCEPTION`). Forbidden examples: `"wrong"`, `"incorrect"`, `"try again"`, `"review the concept"`, `"check again"`.
  - `m` CANNOT contain negative phrasing (`SECTION_11_NEGATIVE_FEEDBACK`): `/❌\s*incorrect/i`, `/❌\s*wrong/i`.
  - **Zero-Spoiler Leakage**:
    - Verbatim Answer Leak (`RULE_1_SPOILER_VERBATIM_ANSWER`): Non-numeric correct answer text cannot appear as a verbatim substring in `m`.
    - Fraction Leak (`RULE_1_SPOILER_FRACTION_LEAK`): Correct fraction cannot be preceded by leak predicates in `m`.
    - Numerical Value Leak (`RULE_1_SPOILER_NUMERICAL_LEAK`): Target numeric values cannot be preceded by leak predicates:
      ```
      'is', 'was', '=', 'giving', 'gives', 'give', 'becomes', 'became', 'not', 'equals', 'equal to', 'equals to', 'result is', 'results in', 'yielding', 'yields', 'produces', 'produced', 'leaving', 'leaves', 'leads to', 'should be', 'must be', 'to get', 'target is', 'target value is', 'correct value is', 'correct answer is', 'answer is', 'answer was', 'answer:', 'instead of'
      ```
    - Spoiler Phrases (`RULE_1_SPOILER_PHRASE_LEAK`): Cannot combine phrases like `"the result is"`, `"the correct answer is"`, `"answer should be"`, `"yielding"`, `"evaluates to"` with numerical values.
  - **4-Tier Progressive Hints (`h1`–`h4`)**:
    - None of the 4 hints may leak the final answer or target numerical value (`RULE_12_HINT_SPOILER`, `RULE_12_HINT_SPOILER_VALUE`).
    - Hint progression: H1 (Attention Hook) → H2 (Conceptual Relationship) → H3 (Strategy/Rule) → H4 (Intermediate Procedural Step).

---

## 5. Dual-Benchmark Quality Gates

### 5.1 Static Benchmark: `benchmarks/qa_ltruth_benchmark.js`
The script runs in Node.js and executes four inspection passes:

| Pass | Target | Hard Invariants |
|---|---|---|
| **Pass 1: Rule #1 Spoilers** | `NODES`, `WE`, `.quiz-card`, `IR.assessment_items` | 0 Spoilers, 0 Missing Misconceptions, 0 Trivial Placeholders. |
| **Pass 2: Math-rt Collisions** | `WM` (Dictionary) & Body text | Math expressions insulated with `<span class="math-var" data-math="true">` or `/* MathIsolation: true */`. Single-letter algebraic variables shielded from `window.WM` collision. |
| **Pass 3: 10 Critical Rules** | Entire HTML file | **Rule 2**: `sort(function() { return Math.random() - 0.5 })` option shuffle.<br>**Rule 3**: Tap-only (0 `ondragstart`, 0 `ondrop`, 0 `draggable="true"`).<br>**Rule 4**: Zero `alert()`, `confirm()`, `prompt()`.<br>**Rule 5**: Visible `Skip this activity` link on interactive simulations.<br>**Rule 6**: Primary navigation anchors `id="backBtn"` and `id="continueBtn"`.<br>**Rule 7**: Multi-phase Worked Example `_weCheckRendered` state guard.<br>**Rule 8**: `localStorage.getItem` wrapped in bounds-checked `try-catch`.<br>**Rule 9**: Instant `exit()` reset without modal dialogs.<br>**Rule 10**: 100% Offline-First (0 external CDN scripts or stylesheet links). |
| **Pass 4: Know-Stage Pedagogy** | `NODES` array | Every concept node must contain: `intro` step + `text` (foundational Know) step + verification check (`quiz`, `worked`, `vq`, or `solve`). |

*Score Formula*:
$$\text{BaseRate} = \frac{\text{Passed Checks}}{\text{Total Checks}} \times 100$$
$$\text{Penalty} = (\text{Spoilers} \times 12) + (\text{Rule Violations} \times 8) + (\text{Math Collisions} \times 8)$$
$$\text{Final Score} = \text{round}(\text{BaseRate} - (\text{Penalty} \times 0.4))$$
*Pass Criterion*: **100/100 score, 0 spoilers, 0 rule breaks, 0 math collisions**.

### 5.2 Dynamic Browser Automation: `benchmarks/automated_browser_verification.js`
- Connects via Chrome DevTools Protocol (CDP) WebSocket.
- Audits five device viewports:
  1. `16:9 Budget Android (360x640)`
  2. `19.5:9 Modern iPhone (390x844)`
  3. `19.5:9 iPhone Pro (393x852)`
  4. `20:9 Modern Pixel/Galaxy (412x915)`
  5. `20:9 Galaxy A-Series (360x800)`
- Asserts:
  - `sameFrame`: Active concept frame bottom $\le$ bottomBar top $+ 8\text{px}$.
  - `noVerticalScroll`: `document.documentElement.scrollHeight <= window.innerHeight + 5`.
  - `noHorizontalScroll`: `document.documentElement.scrollWidth <= window.innerWidth + 2`.
  - `touchTargets`: All interactive buttons, presets, and options $\ge 44 \times 44\text{px}$ (strictly $\ge 36\text{px}$ in bounding rect).
  - `bilingualWordTap`: Tapping `.word` opens `#wordDialog`, displaying English word, Devanagari phonics badge in `#dlgPhonics`, and Hindi translation in `#dlgHindi` (with zero `"उपलब्ध नहीं"` or `"not available"`).
  - `dictionaryIntegrity`: Core mathematical terms present in `window.WM`.
  - `stepAdvancement`: 5-step continuous navigation with 0 unhandled console errors or exceptions.

---

## 6. Blueprint of Gold-Standard Reference Chapter (`RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`)

An exhaustive audit of the 363 KB gold-standard chapter revealed its exact DOM, CSS, and JS components:

```
[HTML Shell]
├── <!DOCTYPE html>
├── <head>
│   ├── <meta charset="UTF-8">
│   ├── <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
│   ├── <style>
│   │   ├── /* MathIsolation: true */
│   │   ├── CSS Variables: --bg, --surface, --blue, --green, --amber, --purple, --red, --border, --brand
│   │   ├── Brand Header & Logo SVG (.brand-header)
│   │   ├── Gamified HUD Topbar (.topbar, .progress-track, .stat.coins, .stat.xp, .stat.lvl, .stat.streak)
│   │   ├── Mode Bar Tabs (.mode-bar, .mode-btn) -> [Concepts, Warm-up, Deep Dive, Boss Challenge]
│   │   ├── Same-Frame Mobile Viewport Clamping Rules:
│   │   │   ├── @media (max-height: 700px) [16:9]: .concept-def max-height: 80px; .sim-canvas max-height: 92px;
│   │   │   ├── @media (min-height: 701px) and (max-height: 860px) [19.5:9]: .concept-def max-height: 110px; .sim-canvas max-height: 115px;
│   │   │   └── @media (min-height: 861px) [20:9]: .concept-def max-height: 125px; .sim-canvas max-height: 125px;
│   │   ├── Preset Bar: flex-wrap: nowrap; overflow-x: auto; touch-action: pan-x; scrollbar-width: none;
│   │   ├── Touch Target Sizing: min-height: 44px; min-width: 44px; touch-action: manipulation;
│   │   └── Math & LLE Typography: .math, .math-var, .word, .connective, .connective-hi, .frac
├── <body>
│   ├── <div class="app">
│   │   ├── <div class="brand-header">...</div>
│   │   ├── <div class="topbar">...</div>
│   │   ├── <div class="mode-bar">...</div>
│   │   ├── <div class="screen" id="screen">
│   │   │   ├── <!-- Concept Discovery Flow (5 Nodes) -->
│   │   │   │   ├── <div id="viewIntro">...</div>
│   │   │   │   ├── <div id="viewConcept">
│   │   │   │   │   ├── <div class="concept-frame">
│   │   │   │   │   │   ├── <span class="concept-badge" id="conceptBadge">...</span>
│   │   │   │   │   │   ├── <h2 class="inquiry-title" id="conceptTitle">...</h2>
│   │   │   │   │   │   ├── <div class="concept-def" id="conceptDef">...</div>
│   │   │   │   │   │   ├── <div class="sim-container">
│   │   │   │   │   │   │   ├── <aasha-sim id="conceptSim" foundation="F04" experience-id="...">
│   │   │   │   │   │   │   │   ├── <div class="sim-readout" id="simReadout">...</div>
│   │   │   │   │   │   │   │   ├── <canvas id="conceptCanvas" class="sim-canvas"></canvas>
│   │   │   │   │   │   │   │   ├── <div class="sim-controls" id="conceptControls"></div>
│   │   │   │   │   │   │   │   └── <div class="sim-caption" id="simCaption"></div>
│   │   │   │   │   │   │   └── </aasha-sim>
│   │   │   │   │   │   │   └── <button class="btn-skip" onclick="App.next()">Skip this activity →</button>
│   │   │   │   │   │   └── </div>
│   │   │   │   │   └── </div>
│   │   │   │   ├── <div id="viewWorked">...</div>
│   │   │   │   ├── <div id="viewQuiz">...</div>
│   │   │   │   └── <div id="viewProgress">...</div>
│   │   │   ├── <!-- 3-Tier Gamified Assessment Container (Static DOM) -->
│   │   │   │   ├── <div id="assessmentContainer" style="display:none">
│   │   │   │   │   ├── <div class="assessment-section" id="section-warmup">
│   │   │   │   │   │   └── <div class="quiz-card" id="..."> ... </div>
│   │   │   │   │   ├── <div class="assessment-section" id="section-deep_dive">
│   │   │   │   │   │   └── <div class="quiz-card" id="..."> ... </div>
│   │   │   │   │   └── <div class="assessment-section" id="section-boss">
│   │   │   │   │       └── <div class="quiz-card" id="..."> ... </div>
│   │   ├── <div class="bottom-bar" id="bottomBar">
│   │   │   ├── <button class="btn-back" id="backBtn" onclick="App.goBack()">← Back</button>
│   │   │   └── <button class="btn-primary" id="continueBtn" onclick="App.next()">Continue →</button>
│   ├── <dialog id="wordDialog" class="lle-dialog">
│   │   ├── <div class="dlg-content">
│   │   │   ├── <div class="dlg-header">...</div>
│   │   │   ├── <div class="dlg-word-row"><span id="dlgWord"></span><button id="dlgAudioBtn" onclick="speakCurrentWord()">🔊 बोलें</button></div>
│   │   │   ├── <div class="dlg-phonics-row"><span id="dlgPhonics"></span></div>
│   │   │   ├── <div class="dlg-meaning-row"><span id="dlgHindi"></span></div>
│   │   │   ├── <div id="dlgDesc"></div>
│   │   │   └── <button class="dlg-btn" onclick="document.getElementById('wordDialog').close()">ठीक है (Got It)</button>
│   ├── <canvas id="confettiCanvas"></canvas>
│   └── <script>
│       ├── var CONN = { ... };
│       ├── var WM = { ... }; // 1,142+ Indic entries from aasha_dictionary_db.json
│       ├── var NODES = [ ... ]; // 5 Concept nodes with intro, text, quiz, solve, progress
│       ├── var WE = { ... }; // Worked examples with _weCheckRendered guard
│       ├── function showWord(w, h, d) { ... }
│       ├── function speakCurrentWord() { window.speechSynthesis.speak(...) }
│       ├── function playTone(type) { Web Audio API synthesized tones (tap, correct, wrong, levelup) }
│       ├── function fireConfetti(count) { ... }
│       ├── Universal <aasha-sim> Web Component:
│       │   └── customElements.define('aasha-sim', AashaSimElement) implementing AashaExperienceContract
│       └── var App = {
│           ├── init(), render(), next(), goBack(), advance(), exit()
│           ├── switchMode(mode), answerAssessment(el, qid, isCorrect, miscText, xp)
│           ├── showNextHint(qid) [Cycles 4-tier hints with DOM update]
│           └── safe storage in try { JSON.parse(localStorage.getItem(...)) }
```

---

## 7. Operational Action Plan for "Squares and Cubes" Chapter

To execute the authoritative request for `square and cube RL public school and ncert.pdf`:

### Phase 1: Foundation Initialization & YAML Contract
1. Run:
   ```bash
   npm run chapter:init -- Mathematics 8 "Squares and Cubes"
   ```
   This generates `content/contracts/Mathematics_Class8_squares_and_cubes.yaml`.
2. Extract 100% of exercises from `square and cube RL public school and ncert.pdf`:
   - Properties of Square Numbers (Units digits: 0, 1, 4, 5, 6, 9; even/odd squares; sum of consecutive odd numbers).
   - Finding Squares (Column method, diagonal method, $(a+b)^2$, numbers ending in 5: $(n \times (n+1))\text{ hundred} + 25$).
   - Pythagorean Triplets ($2m, m^2-1, m^2+1$).
   - Square Roots by Repeated Subtraction (odd numbers).
   - Square Roots by Prime Factorization (finding smallest multiplier or divisor to make perfect square).
   - Square Roots by Long Division Method (pairing bars, integral and decimal roots).
   - Cube Numbers & Patterns (units digit patterns, adding consecutive odd numbers).
   - Cube Roots by Prime Factorization (groups of 3).
   - Cube Roots by Estimation (units place digit + tens estimation from cubes table).
3. Expand `Mathematics_Class8_squares_and_cubes.yaml` with the full exercise breakdown across Warm-up, Deep Dive, and Boss tiers.

### Phase 2: Interactive Manipulative Adapter (`<aasha-sim>`)
- Bind to Foundation F02 / F04 / Canvas:
  - **Manipulative 1: Geometric Square Dot Grid & Pythagorean Triplet Balancer**
    - Sliders for $n$ from 1 to 25.
    - Grid of $n \times n$ animated tiles illustrating $n^2$ as geometric area.
    - Visual decomposition of $(a+b)^2 = a^2 + 2ab + b^2$ or $n^2$ into $L$-shaped gnomon additions ($1 + 3 + 5 + \dots + (2n-1) = n^2$).
  - **Manipulative 2: 3D Isometric Cube Visualizer**
    - $n \times n \times n$ block building with layer slicing.
  - Implement full `AashaExperienceContract` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`).

### Phase 3: Chapter HTML Synthesis
- Synthesize `chapters/SquaresCubes_Class8_Gamified_v5_Enhanced_v6.html`:
  - 5 Golden Flow Nodes (`intro` → `text` → `quiz` / `solve` → `progress`).
  - 3-Tier Gamified Assessment Container (`#section-warmup`, `#section-deep_dive`, `#section-boss`).
  - Strict Question Schema:
    - 0 verbatim spoilers, 0 leak predicates in `m`.
    - Every distractor has non-empty diagnostic `m` > 15 chars.
    - 4 progressive hint tiers (`data-h1` attention, `data-h2` relationship, `data-h3` strategy, `data-h4` procedure) with zero answers.
  - Full `window.WM` dictionary from `experience_registry/aasha_dictionary_db.json` with math insulation.
  - Responsive CSS media queries matching 16:9, 19.5:9, and 20:9 viewports.
  - Touch targets $\ge 44 \times 44\text{px}$, tap-only interaction, skip button, and safe storage.

### Phase 4: Quality Gate Certification
1. Run:
   ```bash
   node benchmarks/qa_ltruth_benchmark.js --file chapters/SquaresCubes_Class8_Gamified_v5_Enhanced_v6.html
   ```
   Must achieve **100/100 score, 0 spoilers, 0 math collisions, 0 rule violations**.
2. Run automated headless Chrome CDP verification across viewports:
   - Check `scrollH <= winH + 5`.
   - Verify word-tap modal opens with Indic translations.
   - Verify 0 console errors across 5 steps.

---

## 8. Conclusion

All pipeline tooling, contract generation scripts, validation regexes, and browser automation suites in `Aasha-AI` have been thoroughly audited, verified in code, and executed via live test runs. The repository possesses a mature, robust architecture ready for the immediate ingestion and synthesis of the Square and Cube Roots chapter.
