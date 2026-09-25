# Benchmark & Mobile Viewport Verification Audit Report

**Chapter Under Audit**: `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`  
**Auditor**: `teamwork_preview_explorer_survey_3` (Benchmark & Viewport Verification Auditor)  
**Date**: 2026-09-14T03:11:00+05:30  
**Scope**: QA L-Truth Benchmark, Headless Chrome CDP Verification, Question Schemas & Distractors, 4-Tier Progressive Hints, and Multi-Aspect Ratio Mobile Viewport Invariants.

---

## 1. Executive Summary & Audit Scorecard

| Area / Invariant | Status | Reported Score | True Compliance | Primary Root Cause / Findings |
|---|---|---|---|---|
| **QA L-Truth Benchmark** | ⚠️ Bypassed Pass | 100/100 (12/12 passed) | 40/100 (Nominal) | Only 15 legacy questions tested; 48 textbook problems missing; math insulation bypassed via CSS comment `/* MathIsolation: true */`. |
| **Question Schema & Distractor Quality** | ⚠️ Partial | 0 flagged spoilers | 15/15 valid (tested only) | The 15 existing questions have high quality `m` strings (>15 chars, zero spoilers). However, zero questions possess 4-tier progressive hints (`H1`–`H4`). |
| **3-Tier Gamified Assessment (100% Exercises)** | ❌ FAILED | 0/48 exercises | 0% | No `#section-warmup`, `#section-deep_dive`, or `#section-boss` containers exist. Exercises 1A, 1B, 1C from `AD class 8th math rational number.pdf` are absent. |
| **Pre-LLE Math Insulation** | ❌ FAILED | Masked by regex check | 0% | No `__AASHA_MATH_X__` or `<span class="math-var" data-math="true">`. Variables $p, q, a, b$ are wrapped in `.word` spans and trigger Hindi word popups. |
| **Headless Chrome CDP Automation** | ⚠️ Shallow Pass | All 3 targets passed | Qualified Pass | Passes on Step 2 simulation frame, but masks dictionary gaps via fallback `cw + ' (शब्द)'` (e.g. "do", "need"), misses non-step-2 views, and checks $\ge 36\text{px}$ instead of $\ge 44\text{px}$. |
| **Same-Frame Mobile Viewport (`scrollH <= winH + 5`)** | ✅ PASSED (Step 2) | 0 vertical overflow | Passed on Step 2 | Step 2 concept + simulation fits in 360x640, 390x844, 393x852, 412x915, and 360x800. Height clamping works as intended. |
| **Touch Targets ($\ge 44 \times 44\text{px}$)** | ❌ FAILED | Verified $\ge 36\text{px}$ only | 4 Key Failures | `.exit-btn` (28x28px), `.dlg-close-x` (26x30px), `.dlg-audio-btn` (~28px height), and `.btn-back` (38px height) fail $\ge 44\text{px}$. |
| **Bottom Nav Clearance & Backdrop Invariant** | ❌ FAILED | Not verified in test | 2 Invariant Breaks | Missing `backdrop-filter: blur(20px)`; lacks `padding-bottom: calc(96px + env(safe-area-inset-bottom, 16px))` on `.screen`. |

---

## 2. Observation

### Observation 1: QA L-Truth Benchmark Run & Surface Results
- **Tool Command**:
  ```bash
  node benchmarks/qa_ltruth_benchmark.js --file chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html
  ```
- **Direct Output**:
  ```
  ================================================================================
   AASHA FOUNDATION — L-TRUTH GROUND TRUTH BENCHMARK REPORT
  ================================================================================

  [PASSED] RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html
      Benchmark Score: 100/100 | Checks Passed: 12 | Violations: 0
      Questions Tested: 15 | Misconceptions: 45
      Spoilers Found: 0 | Math-rt Collisions: 0 | Rule Breaks: 0
  --------------------------------------------------------------------------------
  Detailed report exported to: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\benchmarks\ltruth_benchmark_report.json
  ```
- **File Reference**: `Aasha-AI/benchmarks/qa_ltruth_benchmark.js`, lines 334–354 (scoring formula).

### Observation 2: Question Schema & Distractor Quality of Tested Items
- **Direct Code Inspection**: Extracted all 15 questions (5 node quizzes in `NODES` [lines 732–888] + 5 WE checks + 5 WE step checks in `WE` [lines 550–730]).
- **Distractor Validation**: Evaluated against `QuestionSchemaValidator.validateDistractor()`:
  - Total distractors: 45.
  - Missing misconceptions: 0.
  - Distractor explanations: All $> 15$ characters (average length 68 characters).
  - Evaluative negative phrasing (`❌ incorrect` / `wrong`): 0.
  - Zero-spoiler violations: 0. No answer formulas, fractions, or leak predicates (`is`, `equals`, `giving`, `yielding`, `result is`) were detected in the 45 distractors.
- **Limitation**: `qa_ltruth_benchmark.js` lines 168–184 only call `QuestionSchemaValidator.validateDistractor()`. It does **not** call `QuestionSchemaValidator.validateQuestion()` or `validateHints()`.

### Observation 3: Total Absence of 4-Tier Progressive Hints & 3-Tier Gamified Assessment
- **Direct Code Inspection**: In `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`:
  - Grep for `warmup`, `deep_dive`, `boss`, `tier`, or `section-warmup` returns **0 results**.
  - Grep for `hints`, `data-h1`, `data-h2`, `data-h3`, `data-h4`, `hint_1_attention` returns **0 results**.
  - Total questions in file: **15**.
- **Discrepancy with Authoritative Contract**:
  - In `chapters/rational_numbers_ad_contract.yaml` lines 53–69:
    ```yaml
    assessment_suite:
      total_questions: 48
      source_breakdown:
        exercise_1a: 24
        exercise_1b: 12
        exercise_1c: 12
      tiers:
        tier_1_warmup:
          title: "Warm-Up Drills (Direct Addition, Subtraction & Reciprocal)"
          count: 16
        tier_2_deep_dive:
          title: "Deep Dive Challenges (Multi-Step Fractions & Property Verification)"
          count: 18
        tier_3_boss:
          title: "Boss Challenge (Full Expression Simplification & Board Prescribed Problems)"
          count: 14
    ```
  - `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` actually contains the 5 worked examples and 5 node quizzes from `chapters/rational_numbers_contract.yaml` (the MDS/NCERT reference), **not** the 48 exercises from `AD class 8th math rational number.pdf` (Exercises 1A, 1B, 1C).

### Observation 4: Pre-LLE Math Insulation Bypass
- **Direct Code Inspection**:
  - `Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`, line 6:
    ```css
    /* MathIsolation: true */
    ```
  - `Aasha-AI/benchmarks/qa_ltruth_benchmark.js`, lines 196–200:
    ```javascript
    const isAlgebra = /\b(?:algebra|coefficient|monomial|binomial|polynomial|variable|identit(?:y|ies))\b/i.test(this.content);
    if (isAlgebra) {
      const isolatesMath = /(?:<math|data-math|`[^`]+`|\$\$.*?\$\$|MathJax|class="math"|\\\(|MathIsolation)/i.test(this.content);
      ...
    ```
  - `isolatesMath` evaluates to `true` strictly because of the comment string `/* MathIsolation: true */` in the CSS block.
  - In reality, in `function rt(text, sm)` (lines 363–410):
    - Math formulas and variables are **not** shielded.
    - Single letters $p, q, a, b$ in text like `"in the form p/q, where p and q are integers"` (line 744) are matched by `/[a-zA-Z]/.test(ch)` (line 398) and wrapped into `<span class="word" data-w="p" data-h="">p</span>` and `<span class="word" data-w="q" data-h="">q</span>`.
    - There are zero instances of `<span class="math-var" data-math="true">` or `__AASHA_MATH_X__`.

### Observation 5: Headless Chrome CDP Verification Execution & Test Harness Architecture
- **Tool Command**:
  ```bash
  node benchmarks/automated_browser_verification.js
  ```
- **Direct Output**:
  ```
  === STARTING AUTOMATED BROWSER VERIFICATION (CDP) ===
  Connected to Chrome: Chrome/152.0.7977.83
  ------------------------------------------------------------
  Testing Target: Rational Numbers Class 8 (AD Textbook Edition)
  File: Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html
  [PASS] Page loaded cleanly. Title: "Class 8 Rational Numbers (AD Edition — Full Book Exercises) — Aasha Learning Ecosystem"
  [PASS] Brand header verified: "AASHA LEARNING ECOSYSTEM"
  Found 33 vocabulary word elements on current screen.
    [PASS] Tap Word "why" -> Modal opened with Hindi: "क्यों"
    [PASS] Tap Word "do" -> Modal opened with Hindi: "do"
    [PASS] Tap Word "we" -> Modal opened with Hindi: "हम"
    [PASS] Tap Word "need" -> Modal opened with Hindi: "need"
    [PASS] Tap Word "numbers" -> Modal opened with Hindi: "संख्याएँ"
    [PASS] Dictionary check for "express": "व्यक्त करना (एक्सप्रेस)"
    [PASS] Dictionary check for "rational": "परिमेय संख्या (रैशनल)"
    ...
  Testing Responsive Layout & Same-Frame Rule across Mobile Aspect Ratios:
    [PASS] Viewport 16:9 Budget Android (360x640) (360x640): Same-Frame Verified! Canvas: 296x92px, 0 vertical scroll, 0 horizontal scroll, Touch Targets compliant.
    [PASS] Viewport 19.5:9 Modern iPhone (390x844) (390x844): Same-Frame Verified! Canvas: 314x115px, 0 vertical scroll, 0 horizontal scroll, Touch Targets compliant.
    [PASS] Viewport 19.5:9 iPhone Pro (393x852) (393x852): Same-Frame Verified! Canvas: 317x115px, 0 vertical scroll, 0 horizontal scroll, Touch Targets compliant.
    [PASS] Viewport 20:9 Modern Pixel/Galaxy (412x915) (412x915): Same-Frame Verified! Canvas: 336x125px, 0 vertical scroll, 0 horizontal scroll, Touch Targets compliant.
    [PASS] Viewport 20:9 Galaxy A-Series (360x800) (360x800): Same-Frame Verified! Canvas: 284x115px, 0 vertical scroll, 0 horizontal scroll, Touch Targets compliant.
  Testing step transitions and interactive progression...
    Step 1: Node 1, Step 1, Canvas present: true
    Step 2: Node 1, Step 2, Canvas present: true
    Step 3: Node 1, Step 3, Canvas present: true
    Step 4: Node 1, Step 3, Canvas present: true
    Step 5: Node 1, Step 3, Canvas present: true
  [PASS] 5-Step continuous progression verified with 0 exceptions or freezes.
  ============================================================
  [ALL BROWSER AUTOMATION & RESPONSIVENESS TESTS PASSED]
  ============================================================
  ```

### Observation 6: Word Modal Dictionary Fallback Masking in `showWord()`
- **Direct Code Inspection**: `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`, lines 454–456:
  ```javascript
  if (!fullVal || fullVal.includes('उपलब्ध नहीं') || fullVal.includes('not available')) {
    fullVal = cw + ' (शब्द)';
  }
  ```
  Lines 458–467:
  ```javascript
  var mMatch = fullVal.match(/^(.*?)\s*\((.*?)\)$/);
  var meaning = fullVal;
  var phonics = cw;
  if (mMatch) {
    meaning = mMatch[1].trim();
    phonics = mMatch[2].trim();
  }
  document.getElementById('dlgHindi').textContent = meaning;
  ```
- **Result**: When a word like `"do"` or `"need"` is clicked, `fullVal` becomes `"do (शब्द)"`, and `dlgHindi` displays the English string `"do"`.
- In `automated_browser_verification.js` lines 191–193:
  ```javascript
  if (!dlgHindi || dlgHindi.includes('उपलब्ध नहीं') || dlgHindi.includes('not available')) {
    throw new Error(`Word "${wordText}" displayed missing Hindi meaning! Received: "${dlgHindi}"`);
  }
  ```
  Because `"do"` and `"need"` do not contain `"not available"`, the test passed despite returning 0 actual Hindi translation.

### Observation 7: Viewport Responsiveness across Mobile Aspect Ratios
- **Direct CSS Inspection**: `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`:
  - 16:9 Budget Android (height $\le 700\text{px}$, lines 88–109):
    - `.brand-header { display: none; }`
    - `.concept-def { max-height: 80px; overflow-y: auto; font-size: 0.80rem; }`
    - `.sim-canvas { max-height: 92px; }`
    - Step 2 concept canvas renders at logical $296 \times 92\text{px}$.
  - 19.5:9 Modern iPhone ($701\text{px} - 860\text{px}$, lines 111–131):
    - `.concept-def { max-height: 110px; }`
    - `.sim-canvas { max-height: 115px; }`
    - Step 2 concept canvas renders at $314 \times 115\text{px}$.
  - 20:9 Modern Pixel/Galaxy ($\ge 861\text{px}$, lines 133–151):
    - `.concept-def { max-height: 125px; }`
    - `.sim-canvas { max-height: 125px; }`
    - Step 2 concept canvas renders at $336 \times 125\text{px}$.
- **CDP Assertion**: `scrollH <= winH + 5` was verified true across all 5 viewports specifically on Step 2.

### Observation 8: Touch Target Sizing Violations ($< 44 \times 44\text{px}$)
- **Target Sizes in CSS**:
  - Line 36: `.exit-btn { background:none; border:none; font-size:20px; color:var(--muted); cursor:pointer; padding:4px }` -> Bounding box is $28 \times 28\text{px}$. **VIOLATION (< 44px)**.
  - Line 207: `.dlg-close-x { background:none; border:none; font-size:1.2rem; color:#64748b; cursor:pointer; padding:2px 6px }` -> Bounding box is $26 \times 30\text{px}$. **VIOLATION (< 44px)**.
  - Line 210: `.dlg-audio-btn { display:inline-flex; align-items:center; gap:4px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:20px; padding:4px 10px; font-size:.78rem; ... }` -> Height is $\sim 28\text{px}$. **VIOLATION (< 44px)**.
  - Line 199: `.btn-back { width:auto; display:inline-block; padding:10px 16px; margin-right:8px; ... }` -> Height is $\sim 38\text{px}$. **VIOLATION (< 44px)**.
- **Why CDP Missed This**: In `automated_browser_verification.js` line 263:
  ```javascript
  return r.width < 36 || r.height < 36;
  ```
  The test threshold was relaxed to 36px, and it only filtered buttons `.preset-btn, .sim-btn, .btn-primary`, ignoring topbar and dialog buttons.

### Observation 9: Bottom Navigation Bar Invariants & Safe-Area Deficiencies
- **Direct CSS Inspection**: `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`:
  - Line 195:
    ```css
    .bottom-bar{position:fixed;bottom:0;left:0;right:0;max-width:520px;margin:0 auto;padding:12px 16px;background:var(--surface);border-top:1px solid var(--border);box-shadow:0 -4px 12px rgba(0,0,0,.05);display:none;z-index:60}
    ```
  - Mandatory Invariant (GEMINI.md): `backdrop-filter: blur(20px)` and top border shadow `0 -4px 16px rgba(0,0,0,0.05)`.
    - Current implementation has **no** `backdrop-filter` and shadow is `0 -4px 12px rgba(0,0,0,.05)`.
  - Mandatory Invariant (GEMINI.md): `padding-bottom: calc(96px + env(safe-area-inset-bottom, 16px))`.
    - Current implementation on `.screen`:
      - Line 46: `padding: 8px 12px 65px;`
      - Line 92: `padding: 4px 8px 56px;`
      - Line 119: `padding: 6px 12px 60px;`
      - Line 139: `padding: 6px 12px 60px;`
    - Lacks `env(safe-area-inset-bottom)` and calc-clearance. Content near the bottom will be occluded by modern mobile gesture home bars and fixed bottom buttons.

---

## 3. Logic Chain

1. **Premise**: An automated test suite passes with 100/100 only within the boundary of what it asserts. (Obs. 1, Obs. 5).
2. **Step 1 (Scope of Questions)**: `qa_ltruth_benchmark.js` iterates over `NODES` and `WE`. In `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`, this totals 15 questions. The contract in `rational_numbers_ad_contract.yaml` mandates 48 questions from Exercises 1A, 1B, 1C across 3 tiers (Obs. 3). Because the 48 exercises were never placed into the HTML file, the benchmark only validated the 15 legacy questions.
3. **Step 2 (Scaffolding Hints)**: The strict question schema specifies 4-tier progressive scaffolding hints (`H1`–`H4`) for every assessment item. In `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`, exactly 0 questions contain `hints` or `data-h` attributes (Obs. 3). Furthermore, `qa_ltruth_benchmark.js` only executes `validateDistractor()` and never calls `validateHints()` (Obs. 2). Thus, hint leaks were not caught because hints do not exist in this chapter.
4. **Step 3 (Math Insulation)**: Invariant requires math variables ($p, q, a, b$) and LaTeX formulas to be insulated from bilingual tokenization. In the benchmark script, `auditMathRtCollisions()` checks whether `this.content` matches `/(?:...|MathIsolation)/` (Obs. 4). The chapter includes `/* MathIsolation: true */` at line 6, which short-circuits the audit to return `[PASSED]`. In reality, `rt()` wraps $p$ and $q$ in `.word` spans, causing math variables to collide with the bilingual word popup engine.
5. **Step 4 (CDP Dictionary Masking)**: `automated_browser_verification.js` asserts that tapped words do not yield `"उपलब्ध नहीं"` or `"not available"` (Obs. 6). In `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`, unmapped words fall back to `fullVal = cw + ' (शब्द)';`, causing the English word to be rendered as the Hindi definition. The test interprets this as a valid translation and logs `[PASS]`, masking missing vocabulary.
6. **Step 5 (Ergonomics & Viewport Invariants)**: Mobile viewport rules mandate `scrollH <= winH + 5` (which holds on Step 2 via height clamping, Obs. 7), minimum touch targets $\ge 44 \times 44\text{px}$ (Obs. 8), and opaque navbar with `backdrop-filter: blur(20px)` and safe-area padding `calc(96px + env(safe-area-inset-bottom, 16px))` (Obs. 9). The current file violates touch targets on 4 interactive buttons and violates the bottom navigation and container clearance invariants.
7. **Conclusion**: While `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` superficially passes both `qa_ltruth_benchmark.js` (100/100) and `automated_browser_verification.js`, it fails the actual pedagogical and architectural mandates of the AASHA Universal Teaching Language System and Follow-up Request (zero 1A/1B/1C exercises, zero 4-tier hints, fake math insulation, fake dictionary fallback, and non-compliant touch targets).

---

## 4. Caveats

1. **Read-Only Scope**: In strict adherence to subagent boundaries, no source code or HTML files were altered. All findings reflect the exact state of the repository as of `2026-09-14T03:11:00+05:30`.
2. **Host Environment**: Headless Chrome CDP tests were executed on Windows 11 with `Chrome/152.0.7977.83` on port 9222. Mobile viewport dimensions were emulated via CDP `Emulation.setDeviceMetricsOverride`.
3. **Assessment Content Gap**: We could not test the 48 textbook exercises for answer spoilers or hint leakage because they are completely absent from `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`. When the implementer builds the full 48-question bank, `QuestionSchemaValidator.validateChapterHtml()` must be executed on all 48 items.

---

## 5. Conclusion

1. **Current Benchmark State**:
   - `qa_ltruth_benchmark.js`: Returns **100/100 (PASSED)**.
   - `automated_browser_verification.js`: Returns **ALL PASSED**.
2. **Deficiencies Discovered**:
   - **Critical Content Deficit**: 0 of the 48 exercises from `AD class 8th math rational number.pdf` (Exercises 1A, 1B, 1C) are present in the HTML file. The file is currently a duplicate of the 5-node MDS/NCERT chapter.
   - **Missing 4-Tier Scaffolding**: 0 questions have 4-tier progressive hints (`H1`–`H4`).
   - **Math Insulation**: Pseudo-insulated via CSS comment; variables $p, q, a, b$ are parsed into word popups.
   - **Dictionary Evasion**: `cw + ' (शब्द)'` fallback masks untranslated words as valid definitions in CDP tests.
   - **Touch Targets**: 4 buttons (`.exit-btn`, `.dlg-close-x`, `.dlg-audio-btn`, `.btn-back`) fail $\ge 44 \times 44\text{px}$.
   - **Navbar Clearance**: Missing `backdrop-filter: blur(20px)` and safe-area padding `calc(96px + env(safe-area-inset-bottom, 16px))`.
3. **Required Implementer Actions**:
   - Rebuild chapter according to `canonical_ir` standard (matching `AlgebraicExpressions_Class7_BETA_v6.html` architecture).
   - Ingest 100% of textbook exercises (48 questions across Warm-up, Deep Dive, Boss Challenge) with non-spoiler `m` diagnostics and 4-tier progressive hints (`H1`–`H4`).
   - Wrap mathematical variables in `<span class="math-var" data-math="true">` and update `rt()` to shield math before dictionary tokenization.
   - Eliminate `cw + ' (शब्द)'` fallback; ensure 100% genuine Hindi vocabulary in `window.WM`.
   - Update CSS touch targets to `min-height: 44px; min-width: 44px;` across all buttons, add `backdrop-filter: blur(20px)` to `.bottom-bar`, and apply safe-area bottom padding to `.screen`.

---

## 6. Verification Method

### 1. Independent Benchmark Execution
Run the official benchmark:
```bash
cd "c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI"
node benchmarks/qa_ltruth_benchmark.js --file chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html
```
Verify that it reports 100/100, 15 questions tested, 45 misconceptions.

### 2. Independent CDP Browser Verification
Run the headless Chrome verification:
```bash
cd "c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI"
node benchmarks/automated_browser_verification.js
```
Verify that all 3 targets complete with 0 runtime exceptions. Observe line output `Modal opened with Hindi: "do"` and `Modal opened with Hindi: "need"` confirming the fallback masking.

### 3. Verification of Missing Content & Invariants
Run in Node.js:
```bash
node -e "
const fs = require('fs');
const c = fs.readFileSync('chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html', 'utf8');
console.log('Warmup exists:', c.includes('warmup'));
console.log('Hints H1 exists:', c.includes('data-h1') || c.includes('hint_1_attention'));
console.log('MathVar exists:', c.includes('math-var'));
console.log('MathIsolation comment:', c.includes('MathIsolation: true'));
console.log('Fallback exists:', c.includes('(शब्द)'));
"
```
Expected output:
- `Warmup exists: false`
- `Hints H1 exists: false`
- `MathVar exists: false`
- `MathIsolation comment: true`
- `Fallback exists: true`

### 4. Invalidation Condition
This audit is invalidated if:
1. `chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` is updated to contain the 48 exercises from Exercises 1A, 1B, 1C across Warm-up, Deep Dive, and Boss tiers.
2. Every distractor and 4-tier hint passes `QuestionSchemaValidator.validateChapterHtml()`.
3. Genuine math insulation (`<span class="math-var" data-math="true">`) is active and verified without reliance on the CSS bypass string.
