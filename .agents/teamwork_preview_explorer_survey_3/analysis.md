# Survey Analysis: Prebuilt Foundation Registry, Verification Suites, & Chapter Contract Governance

**Agent**: `teamwork_preview_explorer_survey_3`  
**Milestone**: Phase 0: Survey  
**Target Chapter**: Class 8 Mathematics — Rational Numbers  
**Date**: 2026-09-12 / 2026-09-13  

---

## 1. Executive Summary

This survey provides a comprehensive architectural and evidentiary investigation into three foundational pillars of the AASHA Learning Ecosystem required for rebuilding the standalone offline interactive HTML chapter for **Class 8 Rational Numbers**:

1. **AASHA Prebuilt Foundation Registry (`Aasha-AI/experience_registry/registry.json`)**:
   Catalog of 20 core open-source foundations (F01–F20) and 7 secondary domain libraries, focusing on F04 (PhET) and F08 (Physics Notebook) for number line, rational density, fraction reslicing, and balance models. Detailed analysis of `AashaExperienceContract`, `<aasha-sim>` Web Component wrapper, and GPL-3.0 license isolation constraints.
2. **Verification Suites & Dual-Benchmark Quality Certification Gate**:
   Deep inspection of `Aasha-AI/benchmarks/qa_ltruth_benchmark.js` and `question_schema_validator.js`, documenting the exact mathematical scoring formula, 10 critical production QA rules, Know-Stage pedagogy, zero-spoiler regex leak predicates, and math-rt collision isolation. In-depth analysis of headless Chrome CDP automation (`automated_browser_verification.js`), detailing exact command-line parameters, viewports, touch target thresholds, and same-frame layout assertions (`scrollH <= winH + 5`).
3. **Chapter Contract Manager & AASHAGatekeeper Governance**:
   Analysis of `packages/chapter-contract-manager.ts`, `content/contracts/`, and `packages/aasha-rules/aasha_gatekeeper.ts`, documenting the automatic generation and verification of Section 24 YAML Reusable Content Contracts and Mandatory Resource Match Reports.

---

## 2. AASHA Prebuilt Foundation Registry

### 2.1 Complete Catalog of 20 Core Foundations (F01–F20)

Source: `Aasha-AI/experience_registry/registry.json` (lines 4–523)

| ID | Foundation Name | Source Repository | License | Target Subjects | Target Classes | Core Mechanics & Interaction Models | Reuse Strategy |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **F01** | **Escape Run** | [abhas9/escape-run](https://github.com/abhas9/escape-run) | MIT | Mathematics, General | 1–8 | adaptive_practice, mastery_gating, spaced_repetition, pwa_offline, local_persistence, micro_skills | `EXTRACT` |
| **F02** | **MicroSims** | [dmccreary/microsims](https://github.com/dmccreary/microsims) | MIT | Mathematics, Physics, Science, CS | 4–10 | concept_simulations, interactive_diagrams, visual_models, algorithm_visualization, parameter_sliders | `EXTRACT` |
| **F03** | **All Science Sims** | [listyantidewi1/all-science-sims](https://github.com/listyantidewi1/all-science-sims) | OpenSource | Science, Physics, Chemistry, Biology | 6–10 | science_simulations, offline_browser_models, bilingual_discovery | `INSPIRE` |
| **F04** | **PhET Interactive Simulations** | [phetsims](https://github.com/phetsims) | GPL-3.0 / CC-BY-4.0 | Mathematics, Physics, Chemistry, Biology | 3–10 | fractions_intro, fraction_matcher, number_line_integers, equality_explorer, friction, density, buoyancy, neuron, molecule_builder, states_of_matter | `EXTRACT` |
| **F05** | **Lightbot** | [haan/Lightbot](https://github.com/haan/Lightbot) | MIT | Computer Science, Coding, Mathematics | 3–10 | command_sequencing, loops, conditionals, problem_decomposition, puzzle_progression | `EXTRACT` |
| **F06** | **MathFluency** | [CarnegieLearning/MathFluency](https://github.com/CarnegieLearning/MathFluency) | MIT | Mathematics | 1–8 | fluency_drills, learning_evidence_tracking, misconception_diagnosis, progression_gating | `EXTRACT` |
| **F07** | **Wiki Physics Game** | [cometsinthesky/wiki-physics-game](https://github.com/cometsinthesky/wiki-physics-game) | MIT | Science, Physics | 6–10 | story_concept_interaction_simulation_feedback_loop, visual_novels, parameter_sliders | `EXTRACT` |
| **F08** | **Physics Notebook** | [CasberryIndia/Physics-Notebook](https://github.com/CasberryIndia/Physics-Notebook) | MIT | Science, Physics | 7–10 | canvas_visualization, real_time_formulas, interactive_experiment_notebook | `EXTRACT` |
| **F09** | **Escapp** | [ging/escapp](https://github.com/ging/escapp) | GPL-3.0 | Cross-Curricular, Science, Math, Social | 5–10 | escape_room, room_puzzle_hint_solution_evidence_flow, team_challenge | `INSPIRE` |
| **F10** | **QuestJS** | [ThePix/QuestJS](https://github.com/ThePix/QuestJS) | MIT | Language, Social Science, Life Skills | 4–10 | interactive_fiction, state_choice_consequence_loop, branching_story | `EXTRACT` |
| **F11** | **Squiffy** | [textadventures/squiffy](https://github.com/textadventures/squiffy) | MIT | Language, Social Science, Life Skills, Ethics | 5–10 | branching_scenarios, dilemma_decisions, narrative_learning | `EXTRACT` |
| **F12** | **GeoGuess** | [Geoguess/Geoguess](https://github.com/Geoguess/Geoguess) | MIT | Geography, Social Science | 4–10 | spatial_reasoning, map_landmarks, indian_geography_adaptation | `EXTRACT` |
| **F13** | **Learn Worldmap** | [koljapluemer/learn-worldmap](https://github.com/koljapluemer/learn-worldmap) | MIT | Geography, Social Science | 5–10 | spaced_repetition_geography, retrieval_practice, map_memory | `EXTRACT` |
| **F14** | **Geographical Adventures** | [SebLague/Geographical-Adventures](https://github.com/SebLague/Geographical-Adventures) | MIT | Geography, Science | 6–10 | spatial_exploration, mission_route_planning, country_learning | `INSPIRE` |
| **F15** | **The Long Game** | [smcgrath-coder/the-long-game](https://github.com/smcgrath-coder/the-long-game) | MIT | Financial Literacy, Mathematics, Life Skills | 6–10 | saving_risk_budgeting, rupees_upi_adaptation, needs_vs_wants_decisions | `EXTRACT` |
| **F16** | **FinanceGame / LearnBu** | [ayazhankadessova/FinanceGame](https://github.com/ayazhankadessova/FinanceGame) | MIT | Financial Literacy, Social Science | 7–10 | scenario_budgeting, credit_savings_investing, household_decisions | `EXTRACT` |
| **F17** | **Code for Life** | [ocadotechnology/codeforlife-portal](https://github.com/ocadotechnology/codeforlife-portal) | GPL-3.0 | Coding, Computer Science | 3–10 | coding_progression, computational_thinking_portal, puzzle_levels | `INSPIRE` |
| **F18** | **Secure Code Game** | [valentinvarbanov/skills-secure-code-game](https://github.com/valentinvarbanov/skills-secure-code-game) | MIT | Cybersecurity, Computer Science, Digital Literacy | 8–10 | vulnerability_spotting, secure_thinking, indian_digital_safety_scenarios | `EXTRACT` |
| **F19** | **Chocolate Broccoli Challenge** | [funksoup/chocolate-broccoli-challenge](https://github.com/funksoup/chocolate-broccoli-challenge) | MIT | Cross-Curricular, Design Quality Gate | 1–10 | observe_decide_act_result_gate, authentic_subject_mastery_evaluator | `QUALITY_GATE` |
| **F20** | **GameBox / Mini Games** | [saiuttejr/GameBox](https://github.com/saiuttejr/GameBox) | MIT | Cross-Curricular, Touch Primitives | 1–10 | touch_interaction_primitives, offline_mini_game_loops, responsive_layout | `EXTRACT` |

### 2.2 Secondary Open-Source Domain Libraries
In addition to F01–F20, `registry.json` indexes 41 secondary open-source repositories:
- **Mathematics**: `race-to-100`, `tica-math`, `GeometryWorld`, `factors-game`, `Collatz-Jump`, `CalcRace`, `math-game`, `cmgame`, `MATH-SPRINT-GAME`, `THE-MATH-GAME`.
- **Geography**: `world-guesser`, `posio`, `geo-game`, `pampa.place`, `flagged-it`, `React-GeoZora`.
- **Language**: `spelling_game`, `Speller`, `word-search-game`, `Golingo`, `hello`, `TypeQuest`, `typing-game`, `SimpleWordGame`.
- **Interactive Fiction**: `Dedalus`, `undum`, `wreck`, `interactive-fiction`, `ScholCom202X`.
- **Escape Rooms**: `caesar-escape-room`, `escape_room`, `escape-room`.
- **Coding**: `Coding-Game`, `Epsilon-Prime`, `chs-js-lib`.
- **Science**: `osp`, `tracker`, `interactive-simulators`, `simulations.borck.education`, `virtual-lab-resources`, `science-based-games-list`.

### 2.3 Focus on F04 (PhET) & F08 (Physics Notebook) for Rational Numbers

For Class 8 Rational Numbers, the key mathematical models are:
1. **Number Line Integer & Rational Placement (F04 `number_line_integers` + F08 canvas)**:
   - Dynamic unit interval partitioning ($1/d, 2/d, \dots, d/d$).
   - Bounded rational locating between lower and upper integer limits ($\lfloor p/q \rfloor$ and $\lfloor p/q \rfloor + 1$).
   - Bidirectional positive and negative rational positioning (e.g. $-8/3$, $7/4$, $-3/5$).
2. **Fraction Density & Equivalence Zoom (F04 `fractions_intro` / `equality_explorer`)**:
   - Reslicing intervals to show infinite rational numbers between any two integers or fractions (density property: $(a+b)/2$).
   - Equivalent fraction bar partitioning (e.g. $32/-48 = -2/3$).
   - LCM common denominator equalization for addition and subtraction.
3. **Multiplicative Inverse / Reciprocal Balance (F04 / F08 mechanics)**:
   - Physical balance scale beam simulation calculating product $p/q \times q/p = 1$.
   - Real-time beam tilt angle dynamic based on torque difference $(\text{product} - 1) \times \theta$.

### 2.4 `AashaExperienceContract` and `<aasha-sim>` Web Component

Source: `Aasha-AI/experience_registry/aasha_experience_contract.js` and `packages/aasha-rules/`

```javascript
class AashaExperienceContract {
  mount(container, config)    // Attaches DOM/canvas, initializes listeners
  getState()                  // Returns JSON snapshot of current manipulative state
  pause()                     // Non-destructive halt of rAF/timers (saves CPU/battery)
  resume()                    // Resumes render loops without reloading or losing state
  reset()                     // Returns manipulative to initial baseline
  destroy()                   // Detaches listeners and cleans up DOM
  emitTelemetry(type, data)   // Dispatches CustomEvent('aasha:telemetry')
  emitStateChange(newState)   // Dispatches CustomEvent('aasha:state_change')
}
```

#### Key Invariant: Balanced Runtime Lifecycle ($\ge 4$ GB RAM)
Because target mobile devices have $\ge 4$ GB RAM:
- DOM tearing or wiping canvas buffers on card transitions or card collapses is **strictly forbidden**.
- The `<aasha-sim>` Web Component implements automatic pause/resume via `IntersectionObserver` (threshold: 0.1):
  - When scrolled out of view: `sim.pause()` cancels `requestAnimationFrame` and clears active timers to prevent battery drain.
  - When scrolled into view: `sim.resume()` immediately unfreezes the render loop without redrawing from scratch or resetting state.

#### Real-Time Telemetry Contract
Every manipulative interaction dispatches bubbling CustomEvents:
- `aasha:telemetry`: captures `timestamp`, `foundationId` (e.g. `'F04_PHET'`, `'F08_PHYSICS_NOTEBOOK'`), `eventType`, and `payload`.
- `aasha:state_change`: captures real-time manipulative properties to synchronize visible DOM text readouts in the same call stack (Synchronous DOM State Binding Invariant).

### 2.5 GPL-3.0 License Isolation Policy

Source: `GEMINI.md` and `aasha-ecosystem/SKILL.md` (Rule 6)

Three foundations in the catalog are licensed under GPL-3.0:
- **F04 PhET Interactive Simulations**
- **F09 Escapp**
- **F17 Code for Life**

**The Isolation Rules**:
1. **EXTRACT Strategy (Preferred)**:
   Extract mathematical formulations, algorithmic logic, numerical models, and public-domain mechanics into clean, MIT-licensed JavaScript/Canvas code. Zero copyleft code from the upstream GPL-3.0 repository enters the file.
2. **INSPIRE Strategy**:
   Design original gameplay, branching fiction, or puzzle progression patterns inspired by the foundation's pedagogy, implemented from scratch in MIT code.
3. **IFRAME/Sandbox Isolation (Alternative)**:
   If an intact upstream GPL-3.0 simulation is embedded (as seen in the Class 6 Fractions reference `Fractions_Gamified_v5_(2)_Enhanced_v6.html` line 1408), it must run inside an isolated sandboxed `<iframe>`. The host HTML page and AASHA runtime communicate across iframe boundaries only via messaging/contracts, strictly preventing copyleft contagion into the core MIT chapter file.

---

## 3. Verification Suites & Quality Certification Gate

### 3.1 QA L-Truth Benchmark (`benchmarks/qa_ltruth_benchmark.js`)

#### 3.1.1 Exact Scoring Algorithm
The benchmark evaluates each chapter using a deterministic formula:
```javascript
const total = this.passedChecks.length + this.failedChecks.length;
const baseRate = total > 0 ? (this.passedChecks.length / total) * 100 : 0;
const penalty = (this.stats.spoilerViolations * 12) + 
                (this.stats.ruleViolations * 8) + 
                (this.stats.mathRtCollisions * 8);
const finalScore = Math.max(0, Math.min(100, Math.round(baseRate - (penalty * 0.4))));
```
**Requirements for 100/100 Score**:
- `finalScore === 100`
- `failedChecks.length === 0`
- `stats.spoilerViolations === 0`
- `stats.missingMisconceptions === 0`
- `stats.ruleViolations === 0`
- `stats.mathRtCollisions === 0`

#### 3.1.2 The 10 Critical Production QA Rules Checked
1. **Rule #1: Zero-Spoiler Misconception Policy**: Every distractor must have a valid `m` field explaining why the student made that specific error without revealing or computing the correct answer. Correct option `m` must be empty.
2. **Rule #2: Randomized Option Shuffling**: Assessment options must be shuffled using `Math.random() - 0.5`.
3. **Rule #3: Tap-Only Interaction**: Zero HTML5 drag-and-drop events (`ondragstart`, `ondrop`, `draggable="true"`). Low-end mobile devices require tap-to-place.
4. **Rule #4: Clean Mobile Execution**: Zero browser-freezing calls (`alert()`, `confirm()`, `prompt()`).
5. **Rule #5: Activity Skip Capability**: All interactive canvas or manipulative activities must provide a visible `'Skip this activity →'` link.
6. **Rule #6: Primary Navigation Anchoring**: Primary navigation buttons (`#backBtn` and `#continueBtn`) must exist and never get permanently stuck disabled.
7. **Rule #7: Worked Example State Guard**: Worked Example flows must include the `_weCheckRendered` state guard to coordinate multi-phase step checks.
8. **Rule #8: Safe Persistent Storage**: All `localStorage.getItem` and `JSON.parse` operations must be wrapped in bounds-checked `try-catch` blocks.
9. **Rule #9: Instant Clean Exit**: `exit()` method must immediately reset `this.nIdx = 0` and clear state without showing blocking confirmation dialogs.
10. **Rule #10: Offline-First Zero CDN Dependencies**: Zero external network script or stylesheet dependencies (`src="http..."` or `href="http..."`, excluding standard XML schemas `w3.org`/`schema.org`).

#### 3.1.3 Know-Stage Cognitive Hierarchy Check
Every concept node in `NODES` must follow the pedagogical sequence:
- `step.t === 'intro'` (Curiosity hook / Inquiry title)
- `step.t === 'text'` (Foundational Know stage)
- `step.t` in `['quiz', 'worked', 'vq', 'solve']` (Active concept verification check)

#### 3.1.4 Spoiler Detection Regexes & Leak Predicates
Source: `benchmarks/question_schema_validator.js` (lines 19–56)

1. **Leak Predicates (`LEAK_PREDICATES`)**:
   `'is'`, `'was'`, `'='`, `'giving'`, `'gives'`, `'give'`, `'becomes'`, `'became'`, `', not \\+?'`, `'not'`, `'equals'`, `'equal to'`, `'equals to'`, `'result is'`, `'results in'`, `'yielding'`, `'yields'`, `'produces'`, `'produced'`, `'produces a value of'`, `'leaving'`, `'leaves'`, `'leads to'`, `'should be'`, `'must be'`, `'to get'`, `'target is'`, `'target value is'`, `'correct value is'`, `'correct answer is'`, `'answer is'`, `'answer was'`, `'answer:'`, `'instead of'`.
2. **Spoiler Phrases (`SPOILER_PHRASES`)**:
   `'the result is'`, `'the correct answer is'`, `'correct answer is'`, `'giving'`, `'gives'`, `'answer is'`, `'answer was'`, `'answer should be'`, `'sum is'`, `'product is'`, `'difference is'`, `'quotient is'`, `'leaving no'`, `'which is equal to'`, `'equals to'`, `'equal to'`, `'evaluates to'`, `'instead of'`, `'yielding'`, `'yields'`, `'produces'`, `'leads to'`.
3. **Trivial Misconception Patterns (`TRIVIAL_MISCONCEPTION_PATTERNS`)**:
   - `^(?:wrong|incorrect|false|not correct|not right|try again|think again|review the concept|check again|no|rethink)[.!]?$`
   - `^(?:this is wrong|that is wrong|this is incorrect|that is incorrect)[.!]?$`
   - `^(?:review chapter|read again|study again|see notes|review the foundational concept rule)[.!]?$`
   - Strings with length $< 12$ characters.
4. **Fraction Leakage Regex**:
   `/(?:${LEAK_PREDICATES.join('|')})?\s*[:=]?\s*${num}\s*\/\s*${den}\b/i`
5. **Numerical Leakage Regex**:
   `/(?:${LEAK_PREDICATES.join('|')})\s*[:=]?\s*${number}\b/i`
6. **Revealing Phrase + Number Proximity**:
   `/(?:${phrase})\s*(?:[a-z]+\s*){0,3}[:=]?\s*\b${number}\b/i`
7. **Prohibited Negative Feedback**:
   Rejects `❌ incorrect` and `❌ wrong`.
8. **Mathematical Normalization (`normalizeMathText`)**:
   Normalizes Unicode dashes (`\u2212`, `\u2013`, `\u2014` $\rightarrow$ `-`), converts LaTeX fractions (`\frac{a}{b}` $\rightarrow$ `a/b`), strips LaTeX delimiters (`\(`, `\)`, `$$`, `$`), and normalizes whitespace before pattern matching.

#### 3.1.5 Math-rt Collision Detection Engine
- Detects whether single-letter keys in bilingual dictionary `WM` (e.g. `'a'`) collide with algebraic expressions.
- Requires `MathIsolation: true` or mathematical variable insulation tags (`<span class="math-var" data-math="true">`, `__AASHA_MATH_X__`) so algebraic variables in equations like $4a$ or $(a + b)$ do not trigger Devanagari dictionary popups instead of mathematical symbols.

---

### 3.2 Headless Chrome CDP Verification Suite

Source: `Aasha-AI/benchmarks/automated_browser_verification.js`

#### 3.2.1 Exact Chrome Launch Command Line
```powershell
chrome.exe `
  --remote-debugging-port=9222 `
  --user-data-dir="<temp_dir>" `
  --headless=new `
  --disable-gpu `
  --no-sandbox `
  --remote-allow-origins=* `
  about:blank
```
Connects over native WebSocket to DevTools Protocol (`Page.enable`, `Runtime.enable`, `Emulation.setDeviceMetricsOverride`).

#### 3.2.2 Viewports Tested (Aspect Ratio Responsiveness Invariant)
The test suite iterates over 5 distinct mobile viewports covering all standard mobile form factors:
1. **16:9 Budget Android**: $360 \times 640$, DPR 2.0
2. **19.5:9 Modern iPhone**: $390 \times 844$, DPR 3.0
3. **19.5:9 iPhone Pro**: $393 \times 852$, DPR 3.0
4. **20:9 Modern Pixel/Galaxy**: $412 \times 915$, DPR 2.625
5. **20:9 Galaxy A-Series**: $360 \times 800$, DPR 2.0

#### 3.2.3 Assertions Enforced
1. **Same-Frame Mobile Viewport Rule**:
   - `frameRect.bottom <= bbRect.top + 8`: Active concept definition and interactive simulation must fit together in the viewport above the sticky bottom navigation bar.
2. **Zero Scroll Overflow Assertions**:
   - `scrollH <= winH + 5`: Hard check that no vertical scrolling occurs on concept/simulation frames.
   - `scrollW <= winW + 2`: Zero horizontal window overflow.
3. **Touch Target Size Rule**:
   - All interactive controls (`.preset-btn`, `.sim-btn`, `.btn-primary`) must meet minimum dimensions: `width >= 36` and `height >= 36` (target design standard is $\ge 44 \times 44\text{px}$).
4. **Bilingual LLE Word-Tap Modal Opening**:
   - Programmatically clicks `.word[data-w]` elements.
   - Verifies `#wordDialog` opens and `#dlgHindi` is populated.
   - Hard assertion: definition must NOT be empty and must NOT contain `'उपलब्ध नहीं'` or `'not available'`.
5. **Critical Dictionary Substrate Verification**:
   - Direct verification that critical chapter keywords exist in `window.WM` (`express`, `rational`, `standard`, `form`, `positive`, `denominator`, `numerator`, `multiplying`, `entire`, `placed`, `fractions`, `understanding`).
6. **Canvas Presence & Dynamic Sizing**:
   - Verification that `<canvas>` exists and renders with valid dimensions adapted via `fitCanvas(canvas)`.
7. **Continuous 5-Step Progression**:
   - Advances 5 sequential steps across nodes (`App.nIdx`, `App.sIdx`, quiz selections, `App.next()`) verifying 0 console errors, 0 exceptions, and 0 execution freezes.

---

## 4. Chapter Contract Manager & AASHAGatekeeper Governance

### 4.1 Chapter Contract Manager (`packages/chapter-contract-manager.ts`)

- **CLI Entry Point**: `npm run chapter:init -- "<Subject>" <Class> "<Topic>"`
- **File Generation Target**: `content/contracts/<Subject>_Class<Class>_<TopicSlug>.yaml`
- **Existing Contracts in `content/contracts/`**:
  - `Mathematics_Class8_rational_numbers.yaml`
  - `Mathematics_Class8_rational_numbers_ad_edition.yaml`
  - `Mathematics_Class8_exponents_and_powers.yaml`
  - `Mathematics_Class8_linear_equations.yaml`

#### 4.1.1 Mandatory Resource Match Report Structure
The `generateResourceMatchReport()` method analyzes `experience_registry/registry.json` matching subject and grade, producing the standard 17-point audit report:
```markdown
### RESOURCE MATCH REPORT
- **Chapter**: Rational Numbers
- **Class**: Class 8
- **Subject**: Mathematics
- **Learning Objectives**:
  1. Understand, reason, and visualize the core mechanics of Rational Numbers
  2. Diagnose and correct student misconceptions without leaking answers
- **Best Existing Experiences**: Escape Run (F01), MicroSims (F02), PhET (F04), MathFluency (F06)
- **Best Reusable Mechanics**: fractions_intro, number_line_integers, concept_simulations, parameter_sliders
- **Best Simulations**: PhET Interactive Simulations (F04) / Physics Notebook (F08)
- **Best Narrative / Escape Structures**: Escapp (F09) / Chocolate Broccoli Challenge (F19)
- **Existing Coverage**: 85%
- **New Work Required**: 15% (Adapting UI to AashaExperienceContract & Indic dictionary tokens)
- **Reuse Strategy**: EXTRACT
- **License Status**: PASS (MIT / GPL-3.0 isolation compliant)
- **Offline**: PASS (Zero remote CDN scripts)
- **Mobile**: PASS (Fits same-frame mobile viewport, min 44px touch targets)
- **Accessibility**: PASS (High contrast, readable typography)
- **Localization**: PASS (Bilingual dictionary lookup in window.WM)
- **AI Integration**: PASS (Pre-seeded in Knowledge Graph and Context Bus)
- **Mastery**: PASS (4-stage progressive hints + zero spoiler feedback)
- **Telemetry**: PASS (AashaExperienceContract telemetry event bus)
- **Final Recommendation**: DO NOT BUILD FROM SCRATCH. Wrap and adapt F04/F08 under AashaExperienceContract.
```

#### 4.1.2 Section 24 YAML Reusable Content Contract Schema
The YAML contract enforces 7 structured sections:
1. `chapter_meta`: subject, class, topic, slug, version, created_at.
2. `resource_match_report`: matched_foundation_id, source_repo, reuse_strategy, license, telemetry_compliant, same_frame_mobile_viewport.
3. `pedagogy_structure`: golden_rule_stages (WHAT $\rightarrow$ WHY $\rightarrow$ HOW $\rightarrow$ SHOW $\rightarrow$ TRY $\rightarrow$ FEEDBACK $\rightarrow$ CONNECT $\rightarrow$ NAME), teaching_mode (`"Notice -> Represent -> Reason"` for Math).
4. `curriculum_intent`: core_concepts with hook, why_type, student explanation layer, academic precision layer.
5. `misconceptions`: trigger_error, 4-tier progressive hints (`H1` attention, `H2` relationship, `H3` strategy, `H4` procedure), zero_spoiler_explanation.
6. `simulation_adapter`: contract_interface (`AashaExperienceContract`), target_foundation, container_id, methods (`mount`, `getState`, `reset`, `destroy`, `telemetry`).
7. `lle_bilingual_insulation`: math_insulation_enabled, target_languages (`["hi"]`), dictionary_substrate (`"window.WM"`).

### 4.2 Knowledge Graph Integration
When `ensureChapterContract()` runs, it registers the chapter node and relationship into the SQLite / Graphify persistent knowledge graph via `ContextBus`:
- Node: `id: "chapter_rational_numbers"`, `label: "ChapterContract"`
- Edge: `source: "chapter_rational_numbers"`, `target: "foundation_F04"`, `relation: "ADAPTS_FOUNDATION"`, `properties: { strategy: "EXTRACT" }`.

### 4.3 AASHAGatekeeper Governance (`packages/aasha-rules/aasha_gatekeeper.ts`)
The gatekeeper acts as the automated quality barrier, performing deterministic audits before human review or QA:
1. **Section 16 & 13 Prohibited Patterns**:
   Rejects text containing unscientific diluting phrases (e.g. `"water disappearing"`), childish slang (`"super-duper"`), manufactured hype (`"fun adventure 🚀"`), or purely evaluative negative phrasing (`"❌ incorrect"`).
2. **Section 15 LaTeX Notation Integrity**:
   Verifies exact matching count of inline LaTeX delimiters (`\(` and `\)`) and display LaTeX delimiters (`\[` and `\]`).
3. **Section 11 & 12 Question Schema & Distractor Validation**:
   Runs `QuestionSchemaValidator.validateExerciseBank()` on assessment items, detecting spoilers, missing `m` fields, low quality explanations, or hint answer leaks.
4. **Automated Repair Prompt Generation**:
   If violations occur, generates an actionable repair prompt targeting the specific rule violations.

---

## 5. Architectural Blueprint for Class 8 Rational Numbers Rebuild

Based on the survey, the rebuild of `Aasha-AI/chapters/RationalNumbers_Class8_Gamified_v5_Enhanced_v6.html` must follow this consolidated blueprint:

1. **Self-Containment & Zero CDN**:
   - Inline KaTeX CSS and WOFF2 fonts (or fallback high-contrast Unicode/serif font rendering).
   - Inline JSXGraph/Canvas simulation engines directly inside `<script>` and styles in `<style>`.
   - Single HTML file under 20 MB.
2. **Same-Frame Mobile Viewport Guarantees**:
   - Media queries tiered at $\le 700\text{px}$ (16:9), $701\text{--}860\text{px}$ (19.5:9), and $>860\text{px}$ (20:9).
   - `.screen { min-height: 0; padding-bottom: 96px; }` with opaque bottom bar.
   - Dynamic canvas sizing via `fitCanvas(canvas)` adapting logical pixels to DPR.
   - Single-row horizontal swipe preset bar (`flex-wrap: nowrap; overflow-x: auto; touch-action: pan-x;`).
   - Strict adherence to `scrollH <= winH + 5` and touch targets $\ge 44 \times 44\text{px}$.
3. **Pre-LLE Math Insulation Invariant**:
   - Apply `MathInsulator.tokenize()` to replace LaTeX expressions and single-letter variables with `__AASHA_MATH_X__` placeholders.
   - Wrap formula tokens in `<span class="math-var" data-math="true">` to prevent `rt()` dictionary token collisions.
4. **Bilingual Indic Substrate (Hindi Sole Focus)**:
   - 100% vocabulary coverage in `window.WM` with `[सरल अर्थ] ([देवनागरी उच्चारण])`.
   - Accessible `#wordDialog` modal with offline Web Speech API TTS (`window.speechSynthesis`).
5. **Interactive Manipulatives (F04/F08 EXTRACT Strategy)**:
   - Density Zoom & Number Line Partitioning (`drawNumLineSim`).
   - Equivalent Fraction Standard Form Bar (`drawEquivSim`).
   - LCM Reslicing for Addition/Subtraction (`drawAddSubSim`).
   - Reciprocal Balance Scale Beam (`drawReciprocalSim`).
   - Commutative & Associative Geometry Blocks (`drawPropsSim`).
   - Wrapped inside `<aasha-sim>` Web Component with `aasha:telemetry` and `aasha:state_change` CustomEvents.
6. **100% Textbook Exercise Bank & 3-Tier Gamified Assessment**:
   - Tier 1 Warm-up (`#section-warmup`): Foundation identification and standard form representation.
   - Tier 2 Deep Dive (`#section-deep_dive`): Density, equivalence, and arithmetic operations linked to simulation state.
   - Tier 3 Boss Challenge (`#section-boss`): Multi-step word problems from Class 8 textbook PDFs.
   - Every distractor has high-quality `m` (>15 chars, zero spoilers, constructive diagnostics).
   - Every question has 4-tier progressive hints ($H_1 \rightarrow H_4$) with zero answer leaks.
7. **Benchmark Passing Certification**:
   - 100/100 on `node benchmarks/qa_ltruth_benchmark.js`.
   - Pass `node benchmarks/automated_browser_verification.js` with 0 console errors across all 5 viewports.
