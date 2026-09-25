# E2E Test Infrastructure: Class 8 Square and Cube Roots Standalone Chapter

## 1. Test Philosophy & Opaque-Box Mandate
- **Opaque-Box & Requirement-Driven**: Derived strictly from `ORIGINAL_REQUEST.md`, `PROJECT.md § Feature Inventory`, and the source textbook PDF `square and cube RL public school and ncert.pdf` (including the RL Public School worked solutions manual).
- **Zero-Implementation Assumption**: Tests validate observable contracts, DOM outputs, question schemas, mathematical truth, simulation lifecycle, and mobile layout constraints without relying on internal variable names or implementation coupling.
- **Strict Quality Invariants**:
  1. **Zero Spoilers (Rule #1)**: 0 verbatim, numerical, or predicate leaks in misconception explanations (`m`) or progressive hints ($H_1 \to H_4$).
  2. **Pre-LLE Mathematical Formula Insulation**: All LaTeX expressions and single-letter variables shielded (`__AASHA_MATH_X__` / `<span class="math-var" data-math="true">`) before bilingual dictionary tokenization; zero math-rt collisions.
  3. **100% Textbook Exercise Extraction**: Exactly 34 verified textbook question items (Warm-Up: 12, Deep Dive: 14, Boss Challenge: 8) with 0 omitted exercises.
  4. **`<aasha-sim>` Universal Contract**: All interactive manipulatives conform to `AashaExperienceContract` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `telemetry`), bubbling CustomEvents (`aasha:telemetry`, `aasha:state_change`).
  5. **Same-Frame Mobile Viewport Responsiveness**: Guaranteed simultaneous rendering of concept definition and interactive visual simulation in the exact same viewport frame across 16:9 (360x640), 19.5:9 (390x844, 393x852), and 20:9 (412x915, 360x800) with `scrollH <= winH + 5` and $\ge 44\times 44\text{px}$ touch targets.
  6. **100% Offline Self-Containment**: Single HTML document under 20 MB ceiling with zero runtime CDN calls, inlined CSS/JS, and KaTeX WOFF2 assets.

---

## 2. Feature Inventory & 4-Tier Test Mapping (F01–F28)

| # | Feature | Requirement Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Scenario) |
|---|---------|-------------------|:-----------------:|:-----------------:|:---------------------:|:-----------------:|
| **F01** | Source PDF Ground Truth & 34 Exercises Extraction | ORIGINAL_REQUEST §R1, PROJECT §F1 | ≥5 | ≥5 | ✓ | S01, S03 |
| **F02** | Section 24 YAML Reusable Content Contract | ORIGINAL_REQUEST §R1, PROJECT §F2 | ≥5 | ≥5 | ✓ | S01 |
| **F03** | Question Schema & Anti-Spoiler Quality Assurance | ORIGINAL_REQUEST §R1, PROJECT §F3 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F04** | Foundation Registry Matching (F01, F02, F04, F08) | ORIGINAL_REQUEST §R1, PROJECT §F4 | ≥5 | ≥5 | ✓ | S01, S04 |
| **F05** | 2D Square Grid & Gnomon Visualizer Sim | ORIGINAL_REQUEST §R2, PROJECT §F5 | ≥5 | ≥5 | ✓ | S02 |
| **F06** | 3D Isometric Cube Stacker Sim | ORIGINAL_REQUEST §R2, PROJECT §F6 | ≥5 | ≥5 | ✓ | S07 |
| **F07** | Prime Factor Grouping Tree Sim | ORIGINAL_REQUEST §R2, PROJECT §F7 | ≥5 | ≥5 | ✓ | S02 |
| **F08** | 100-Locker Riddle & Ending Digit Explorer Sim | ORIGINAL_REQUEST §R2, PROJECT §F8 | ≥5 | ≥5 | ✓ | S01 |
| **F09** | Rapid 3-Digit Grouping Cube Estimator Sim | ORIGINAL_REQUEST §R2, PROJECT §F9 | ≥5 | ≥5 | ✓ | S06 |
| **F10** | Monolithic HTML Shell & Zero-CDN Core (<20MB) | ORIGINAL_REQUEST §R2, PROJECT §F10 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F11** | Same-Frame Mobile Viewport Engine (16:9, 19.5:9, 20:9) | ORIGINAL_REQUEST §R2, PROJECT §F11 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F12** | Opaque Bottom Nav & Touch Target Guardrails (≥44px) | ORIGINAL_REQUEST §R2, PROJECT §F12 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F13** | Web Audio API Procedural Sound Engine | ORIGINAL_REQUEST §R2, PROJECT §F13 | ≥5 | ≥5 | ✓ | S01 |
| **F14** | Confetti Particle Celebration FX | ORIGINAL_REQUEST §R2, PROJECT §F14 | ≥5 | ≥5 | ✓ | S01 |
| **F15** | Pre-LLE Mathematical Formula Insulation | ORIGINAL_REQUEST §R3, PROJECT §F15 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F16** | Inlined Hindi Dictionary Substrate (`window.WM`) | ORIGINAL_REQUEST §R3, PROJECT §F16 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F17** | Connective Word Scaffolding (`CONN`) | ORIGINAL_REQUEST §R3, PROJECT §F17 | ≥5 | ≥5 | ✓ | S01 |
| **F18** | Interactive `#wordDialog` Modal & Indic Definition | ORIGINAL_REQUEST §R3, PROJECT §F18 | ≥5 | ≥5 | ✓ | S01 |
| **F19** | Web Speech API Offline Phonics Audio (`en-IN`) | ORIGINAL_REQUEST §R3, PROJECT §F19 | ≥5 | ≥5 | ✓ | S01 |
| **F20** | Golden Flow Pedagogical Progression (WHAT→NAME) | ORIGINAL_REQUEST §R2, PROJECT §F20 | ≥5 | ≥5 | ✓ | S01, S02 |
| **F21** | Tier 1: Warm-Up Assessment Integration (12 Qs) | ORIGINAL_REQUEST §R4, PROJECT §F21 | ≥5 | ≥5 | ✓ | S03 |
| **F22** | Tier 2: Deep Dive Assessment Integration (14 Qs) | ORIGINAL_REQUEST §R4, PROJECT §F22 | ≥5 | ≥5 | ✓ | S04 |
| **F23** | Tier 3: Boss Challenge Assessment Integration (8 Qs) | ORIGINAL_REQUEST §R4, PROJECT §F23 | ≥5 | ≥5 | ✓ | S01, S04 |
| **F24** | L-Truth Zero-Spoiler Scaffolding ($H_1 \to H_4$) | ORIGINAL_REQUEST §R4, PROJECT §F24 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F25** | Gamified Mastery Economy & Feedback (XP, Coins) | ORIGINAL_REQUEST §R5, PROJECT §F25 | ≥5 | ≥5 | ✓ | S01 |
| **F26** | QA L-Truth Benchmark 100/100 Certification | ORIGINAL_REQUEST §R5, PROJECT §F26 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F27** | Headless Chrome CDP Responsiveness Certification | ORIGINAL_REQUEST §R5, PROJECT §F27 | ≥5 | ≥5 | ✓ | S01–S08 |
| **F28** | Adversarial Coverage Hardening (Tier 5 Corner Cases)| ORIGINAL_REQUEST §R5, PROJECT §F28 | ≥5 | ≥5 | ✓ | S01–S08 |

---

## 3. Tier 1: Feature Coverage Specifications (≥5 per Feature)

For each feature in scope, the following test cases must be verified:

### F01: Source PDF Ground Truth & Exercise Extraction
- **TC-F01-1**: Verify total question count extracted from textbook is exactly 34 items.
- **TC-F01-2**: Verify all in-text inquiry problems (IT-01 to IT-28) are mapped into question objects.
- **TC-F01-3**: Verify "Figure it Out" Problem Set 1 (Page 10, Q1–Q9) items are present with exact numerical parameters.
- **TC-F01-4**: Verify "Figure it Out" Problem Set 2 (Pages 16–17, Q1–Q5) items and subparts (Q3(i)–(v)) are present.
- **TC-F01-5**: Verify Page 18 Square Pairs extension puzzles (Row 1..17 and Circle 1..32) are included.

### F02: Section 24 YAML Reusable Content Contract
- **TC-F02-1**: Verify contract exists at `content/contracts/Mathematics_Class8_squares_and_cubes.yaml`.
- **TC-F02-2**: Verify YAML schema contains valid `chapter_meta`, `resource_match_report`, and `pedagogy_structure`.
- **TC-F02-3**: Verify all Golden Rule stages (`WHAT`, `WHY`, `HOW`, `SHOW`, `TRY`, `FEEDBACK`, `CONNECT`, `NAME`) are declared.
- **TC-F02-4**: Verify `misconceptions` mapping contains 4-tier hints and zero-spoiler explanations.
- **TC-F02-5**: Verify `assessment_suite` accurately partitions the 34 questions into Warm-Up (12), Deep Dive (14), and Boss (8).

### F03: Question Schema & Anti-Spoiler Quality Assurance
- **TC-F03-1**: Verify every question contains 3 or 4 options, with exactly 1 marked correct (`c: true`).
- **TC-F03-2**: Verify every distractor has a non-empty `m` explanation with length $> 11$ characters.
- **TC-F03-3**: Verify zero occurrences of forbidden spoiler predicates (`is`, `becomes`, `yielding`, `result is`, `should be`, `equals`) preceding target answers.
- **TC-F03-4**: Verify zero occurrences of verbatim correct answer substrings in distractor explanations.
- **TC-F03-5**: Verify zero occurrences of negative discouraging phrasing (`❌ incorrect`, `wrong`) in distractor feedback.

### F04: Foundation Registry Matching & `<aasha-sim>` Binding
- **TC-F04-1**: Verify matched foundation IDs include F01 (Escape Run), F02 (MicroSims), and F08 (Physics Notebook).
- **TC-F04-2**: Verify `experience_registry/registry.json` contains registered square/cube simulation entries.
- **TC-F04-3**: Verify `<aasha-sim>` custom element definition is registered on `customElements`.
- **TC-F04-4**: Verify `<aasha-sim>` implements the mandatory `AashaExperienceContract` interface methods (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`).
- **TC-F04-5**: Verify custom events `aasha:telemetry` and `aasha:state_change` bubble with non-null detail payloads.

### F05: 2D Square Grid & Gnomon Visualizer Sim
- **TC-F05-1**: Verify 2D canvas simulation renders square grid of side $s \in [1, 10]$.
- **TC-F05-2**: Verify gnomon inverted-L overlay highlights the $2n-1$ odd boundary tiles.
- **TC-F05-3**: Verify area readout updates synchronously to $s^2$ in the DOM upon slider movement.
- **TC-F05-4**: Verify non-destructive pause stops animation loops when navigating away.
- **TC-F05-5**: Verify resume restores rendering loop without canvas tearing.

### F06: 3D Isometric Cube Stacker Sim
- **TC-F06-1**: Verify isometric 3D canvas draws $n \times n \times n$ stacked unit blocks.
- **TC-F06-2**: Verify layer slicing toggle exposes consecutive odd-number grouping representation.
- **TC-F06-3**: Verify edge slider $e \in [1, 10]$ updates total volume readout to $e^3$.
- **TC-F06-4**: Verify 60 FPS animation loop maintains steady canvas rendering without memory leak.
- **TC-F06-5**: Verify WebGL / 2D canvas context is properly released on `destroy()`.

### F07: Prime Factor Grouping Tree Sim
- **TC-F07-1**: Verify prime factor tree decomposes input composite numbers into prime factor leaves.
- **TC-F07-2**: Verify pairing mode highlights equal prime pairs for square root calculation ($\sqrt{N}$).
- **TC-F07-3**: Verify tripling mode highlights equal prime triplets for cube root calculation ($\sqrt[3]{N}$).
- **TC-F07-4**: Verify orphan prime factor identification displays the smallest multiplier required to make a perfect power.
- **TC-F07-5**: Verify orphan prime factor identification displays the smallest divisor required to make a perfect power.

### F08: 100-Locker Riddle & Ending Digit Explorer Sim
- **TC-F08-1**: Verify locker simulation toggles 100 lockers across 100 simulated visitors.
- **TC-F08-2**: Verify final open lockers match exactly the set of square numbers $\{1, 4, 9, 16, 25, 36, 49, 64, 81, 100\}$.
- **TC-F08-3**: Verify factor counter displays odd parity for square lockers and even parity for non-square lockers.
- **TC-F08-4**: Verify ending digit filter proves squares end only in $0, 1, 4, 5, 6, 9$.
- **TC-F08-5**: Verify digit filter demonstrates that ending in 6 does not guarantee a square (counterexample 26, 56).

### F09: Rapid 3-Digit Grouping Cube Estimator Sim
- **TC-F09-1**: Verify 3-digit grouping divides large cubes into units group and thousands group.
- **TC-F09-2**: Verify units digit mapping identifies root's units digit based on $0 \to 0, 1 \to 1, 4 \to 4, 5 \to 5, 6 \to 6, 9 \to 9, 2 \leftrightarrow 8, 3 \leftrightarrow 7$.
- **TC-F09-3**: Verify thousands group bracket correctly bounds root's tens digit between consecutive cubes.
- **TC-F09-4**: Verify estimation calculates $\sqrt[3]{17576} = 26$ and $\sqrt[3]{32768} = 32$ without factorisation.
- **TC-F09-5**: Verify invalid non-cube inputs produce an alert indicating non-perfect cube status.

### F10: Monolithic HTML Shell & Zero-CDN Core
- **TC-F10-1**: Verify target file size is strictly $< 20\text{ MB}$.
- **TC-F10-2**: Verify zero external network calls (`http://` or `https://` in `src` or `href` attributes, excluding standard XML namespaces).
- **TC-F10-3**: Verify KaTeX WOFF2 fonts are inlined as Base64 Data URIs.
- **TC-F10-4**: Verify all CSS styles and JavaScript code are inlined directly into `<style>` and `<script>` tags.
- **TC-F10-5**: Verify offline load completes with 0 HTTP requests dispatched to the network.

### F11: Same-Frame Mobile Viewport Engine
- **TC-F11-1**: Verify `.screen { min-height: 0; }` is declared in CSS.
- **TC-F11-2**: Verify height-tiered media query clamping for `.concept-def` (80px for $\le 700\text{px}$, 110px for $701–860\text{px}$, 125px for $\ge 861\text{px}$).
- **TC-F11-3**: Verify height-tiered media query clamping for `.sim-canvas` (92px for $\le 700\text{px}$, 115px for $701–860\text{px}$, 125px for $\ge 861\text{px}$).
- **TC-F11-4**: Verify `.preset-bar` declares `flex-wrap: nowrap; overflow-x: auto; touch-action: pan-x;`.
- **TC-F11-5**: Verify `scrollH <= winH + 5` assertion holds on 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915).

### F12: Opaque Bottom Nav & Touch Target Guardrails
- **TC-F12-1**: Verify bottom navigation bar has opaque background and `backdrop-filter: blur(20px)`.
- **TC-F12-2**: Verify bottom nav top shadow prevents content bleed.
- **TC-F12-3**: Verify scrollable container enforces `padding-bottom: calc(96px + env(safe-area-inset-bottom, 16px))`.
- **TC-F12-4**: Verify all interactive buttons, options, and slider thumbs have bounding rect $\ge 44 \times 44\text{px}$.
- **TC-F12-5**: Verify primary buttons (`#backBtn`, `#continueBtn`) remain permanently anchored and visible.

### F13: Web Audio API Procedural Sound Engine
- **TC-F13-1**: Verify audio synthesizer utilizes Web Audio API (`AudioContext` or `webkitAudioContext`).
- **TC-F13-2**: Verify `tap` tone synthesizes clean click frequency.
- **TC-F13-3**: Verify `correct` tone plays harmonic major chord or arpeggio.
- **TC-F13-4**: Verify `wrong` tone plays low-frequency corrective buzz without harsh distortion.
- **TC-F13-5**: Verify audio engine handles locked audio contexts gracefully on initial user gesture.

### F14: Confetti Particle Celebration FX
- **TC-F14-1**: Verify HTML5 canvas `#confettiCanvas` exists in the DOM.
- **TC-F14-2**: Verify `fireConfetti(count)` initializes particles with randomized velocities and gravity.
- **TC-F14-3**: Verify particle animation terminates cleanly and clears canvas after duration.
- **TC-F14-4**: Verify confetti triggers upon completing assessment tiers or boss challenge.
- **TC-F14-5**: Verify confetti canvas does not intercept pointer events (`pointer-events: none`).

### F15: Pre-LLE Mathematical Formula Insulation
- **TC-F15-1**: Verify LaTeX formulas (`\( ... \)`, `$$ ... $$`) are shielded with `__AASHA_MATH_X__` placeholders.
- **TC-F15-2**: Verify single-letter algebraic variables ($n, s, e, x, y$) are wrapped in `<span class="math-var" data-math="true">`.
- **TC-F15-3**: Verify zero single-letter keys in `window.WM` collide with algebraic variables.
- **TC-F15-4**: Verify CSS includes `/* MathIsolation: true */` comment header.
- **TC-F15-5**: Verify mathematical expressions remain uncorrupted by bilingual word-tap tokenization.

### F16: Inlined Hindi Dictionary Substrate (`window.WM`)
- **TC-F16-1**: Verify `window.WM` contains at least 1,000 Indic vocabulary entries.
- **TC-F16-2**: Verify core chapter terms (*square*, *cube*, *root*, *factor*, *prime*, *odd*, *even*, *area*, *volume*) exist in `window.WM`.
- **TC-F16-3**: Verify dictionary entries follow `[सरल अर्थ] ([देवनागरी उच्चारण])` format.
- **TC-F16-4**: Verify zero missing word fallbacks ("Hindi meaning not available") during vocabulary lookups.
- **TC-F16-5**: Verify dictionary lookup is case-insensitive and trims trailing punctuation.

### F17: Connective Word Scaffolding (`CONN`)
- **TC-F17-1**: Verify `CONN` dictionary contains reasoning connectives (`because`, `therefore`, `if`, `hence`, `since`).
- **TC-F17-2**: Verify connective words display bilingual scaffolding tags without breaking English grammar.
- **TC-F17-3**: Verify clicking connectives reveals contextual semantic intent.
- **TC-F17-4**: Verify connective styling maintains high contrast and visual distinctiveness.
- **TC-F17-5**: Verify mathematical steps utilize natural connective flow (HOW $\rightarrow$ SHOW $\rightarrow$ WHY).

### F18: Interactive `#wordDialog` Modal
- **TC-F18-1**: Verify `<dialog id="wordDialog">` exists in the DOM.
- **TC-F18-2**: Verify modal displays target English word in `#dlgWord`.
- **TC-F18-3**: Verify modal displays Devanagari phonics pronunciation in `#dlgPhonics`.
- **TC-F18-4**: Verify modal displays clear Hindi meaning in `#dlgHindi`.
- **TC-F18-5**: Verify modal closes cleanly on click outside or "Got It" button tap.

### F19: Web Speech API Offline Phonics Audio
- **TC-F19-1**: Verify `#dlgAudioBtn` triggers `window.speechSynthesis.speak()`.
- **TC-F19-2**: Verify speech synthesis prioritizes `en-IN` voice where available.
- **TC-F19-3**: Verify fallback suffix stemming isolates root words when inflected forms are tapped.
- **TC-F19-4**: Verify speech rate is calibrated to 0.85x for clear Indian learner comprehension.
- **TC-F19-5**: Verify speech synthesis handles unsupported browser environments without throwing uncaught exceptions.

### F20: Golden Flow Pedagogical Progression
- **TC-F20-1**: Verify concept flow follows WHAT $\rightarrow$ WHY $\rightarrow$ HOW $\rightarrow$ SHOW $\rightarrow$ TRY $\rightarrow$ FEEDBACK $\rightarrow$ CONNECT $\rightarrow$ NAME.
- **TC-F20-2**: Verify headings are formulated as natural inquiry questions (no bookish meta-labels).
- **TC-F20-3**: Verify worked examples contain multi-phase checks guarded by `_weCheckRendered`.
- **TC-F20-4**: Verify concept cards include visible "Skip this activity $\to$" escape routes.
- **TC-F20-5**: Verify mastery checkpoints gate progression until active understanding is demonstrated.

### F21: Tier 1: Warm-Up Assessment Integration (12 Questions)
- **TC-F21-1**: Verify `#section-warmup` contains exactly 12 `.quiz-card` elements.
- **TC-F21-2**: Verify questions cover fundamental properties: units digits, square identification, trailing zeros.
- **TC-F21-3**: Verify options shuffle randomly using `sort(function() { return Math.random() - 0.5 })`.
- **TC-F21-4**: Verify correct answer selection awards Tier 1 XP and coin rewards.
- **TC-F21-5**: Verify wrong answer selection reveals non-spoiler misconception diagnostic.

### F22: Tier 2: Deep Dive Assessment Integration (14 Questions)
- **TC-F22-1**: Verify `#section-deep_dive` contains exactly 14 `.quiz-card` elements.
- **TC-F22-2**: Verify questions cover prime factorisation, smallest multiplier/divisor, Pythagorean triplets, and cube roots.
- **TC-F22-3**: Verify questions incorporate interactive manipulative hints linked to `<aasha-sim>`.
- **TC-F22-4**: Verify 4-tier progressive hints cycle through $H_1 \to H_4$ upon button tap.
- **TC-F22-5**: Verify streak multipliers increment correctly upon consecutive correct responses.

### F23: Tier 3: Boss Challenge Assessment Integration (8 Questions)
- **TC-F23-1**: Verify `#section-boss` contains exactly 8 `.quiz-card` elements.
- **TC-F23-2**: Verify includes Queen Ratnamanjuri locker parity puzzle.
- **TC-F23-3**: Verify includes Page 18 Square Pairs sequence arrangement ($1..17$).
- **TC-F23-4**: Verify includes Page 18 Square Pairs circular cycle ($1..32$).
- **TC-F23-5**: Verify includes LCM square problem (divisible by 4, 9, 10 $\implies 900$).

### F24: L-Truth Zero-Spoiler Scaffolding ($H_1 \to H_4$)
- **TC-F24-1**: Verify Hint 1 ($H_1$) focuses learner attention on the key perceptual feature with zero math calculation.
- **TC-F24-2**: Verify Hint 2 ($H_2$) articulates the core conceptual relationship.
- **TC-F24-3**: Verify Hint 3 ($H_3$) proposes an actionable problem-solving strategy or formula.
- **TC-F24-4**: Verify Hint 4 ($H_4$) computes an intermediate checkpoint step without revealing the final answer.
- **TC-F24-5**: Verify all 4 hint tiers pass `QuestionSchemaValidator` zero-spoiler check.

### F25: Gamified Mastery Economy & Feedback
- **TC-F25-1**: Verify XP points increment appropriately across tiers (Warm-Up: 10 XP, Deep Dive: 25 XP, Boss: 50 XP).
- **TC-F25-2**: Verify token coin economy updates synchronously in HUD topbar.
- **TC-F25-3**: Verify streak counter increments on consecutive correct answers and resets on error.
- **TC-F25-4**: Verify level up badge triggers celebration particle burst upon reaching XP thresholds.
- **TC-F25-5**: Verify gamified state persists safely in `localStorage` wrapped in `try-catch`.

### F26: QA L-Truth Benchmark 100/100 Certification
- **TC-F26-1**: Verify running `node benchmarks/qa_ltruth_benchmark.js` produces a final score of 100/100.
- **TC-F26-2**: Verify 0 spoiler violations detected across all nodes, worked examples, and assessment items.
- **TC-F26-3**: Verify 0 math-rt collisions detected.
- **TC-F26-4**: Verify 0 rule violations across the 10 production QA rules.
- **TC-F26-5**: Verify report export creates valid `ltruth_benchmark_report.json`.

### F27: Headless Chrome CDP Responsiveness Certification
- **TC-F27-1**: Verify automated Chrome browser automation executes across all 5 device viewports.
- **TC-F27-2**: Verify 0 unhandled console errors or exceptions during execution.
- **TC-F27-3**: Verify `scrollH <= winH + 5` assertion holds on all 5 device screens.
- **TC-F27-4**: Verify tapping `.word` opens `#wordDialog` with valid Indic translations.
- **TC-F27-5**: Verify 5-step continuous navigation advances without UI freeze.

### F28: Adversarial Coverage Hardening (Tier 5 Corner Cases)
- **TC-F28-1**: Verify factor parity correctly handles $N=1$ (single factor $1$, odd count, locker remains open).
- **TC-F28-2**: Verify prime squares ($N = p^2$) have exactly 3 factors ($1, p, p^2$).
- **TC-F28-3**: Verify sixth powers ($N = 64 = 8^2 = 4^3$) factor count is odd because it is a square, not because it is a cube.
- **TC-F28-4**: Verify fraction squaring for $x \in (0, 1)$ demonstrates $x^2 < x$ (e.g. $(0.6)^2 = 0.36 < 0.6$).
- **TC-F28-5**: Verify cube of negative integers is negative ($(-6)^3 = -216$) while square of negative integers is positive ($(-6)^2 = +36$).

---

## 4. Tier 2: Boundary & Corner Cases (≥5 per Feature)

| Feature | Boundary Condition | Input Value | Expected Behavior / Proof |
|---|---|---|---|
| **F01 / F08** | Minimum positive integer | $N = 1$ | $1^2 = 1$; exactly 1 factor ($1$); Locker 1 remains OPEN. |
| **F01 / F08** | Prime numbers factor count | $N \in \{2, 3, 5, 7, 11\}$ | Exactly 2 factors ($1, p$); toggled twice; ends CLOSED; forms passcode `2-3-5-7-11`. |
| **F01 / F08** | Maximum locker index | $N = 100$ | $100 = 10^2$; 9 factors ($1, 2, 4, 5, 10, 20, 25, 50, 100$); odd count; remains OPEN. |
| **F03 / F08** | Non-square with valid unit digit | $N = 26, 56, 86$ | Ends in 6, but has 4 factors; ends CLOSED; proves ending in 6 is not sufficient. |
| **F03 / F08** | Square with odd trailing zeros | $N = 4000$ | $4000 = 40^2 \times 2.5$; 3 trailing zeros $\implies$ non-square despite 4 being square. |
| **F05 / F28** | Proper fraction squaring | $x = 3/5 = 0.6$ | $(3/5)^2 = 9/25 = 0.36 < 0.6$; area is smaller than side length. |
| **F05 / F28** | Decimal squaring place shift | $x = 0.05$ | $(0.05)^2 = 0.0025$ (2 decimal places double to 4 decimal places). |
| **F06 / F28** | Negative base cube | $x = -6$ | $(-6)^3 = -216$; negative sign preserved on odd exponent. |
| **F06 / F28** | Negative base square | $x = -6$ | $(-6)^2 = +36$; negative sign eliminated on even exponent. |
| **F07 / F28** | Square root of non-square | $N = 156$ | $156 = 2^2 \times 3 \times 13$; 3 and 13 unpaired $\implies$ irrational root, not perfect square. |
| **F07 / F28** | Smallest multiplier for square | $N = 9408$ | $9408 = 2^6 \times 3 \times 7^2$; orphan prime is 3; multiply by 3 to get $28224 = 168^2$. |
| **F07 / F28** | Smallest multiplier for cube | $N = 1323$ | $1323 = 3^3 \times 7^2$; orphan prime is 7; multiply by 7 to get $9261 = 21^3$. |
| **F08 / F28** | Trailing zeros of cubes | $N = 100$ | $100$ has 2 zeros $\implies$ cannot be a cube; cubes must have $3k$ zeros. |
| **F09 / F28** | Smallest 4-digit cube | $N = 1000$ | $\sqrt[3]{1000} = 10$; boundary between 3-digit and 4-digit cubes. |
| **F09 / F28** | Largest 2-digit base cube | $N = 99$ | $99^3 = 970299$ (6 digits); proves 2-digit cube can NEVER have 7 digits. |
| **F20 / F23** | Graph degree 1 endpoints | Numbers 16 & 17 in $1..17$ | Only $16+9=25$ and $17+8=25$; degree 1 forces them to be the outer endpoints of row. |
| **F20 / F23** | Hamiltonian cycle closure | Circular $1..32$ | $15+1 = 16 = 4^2$ closes the circular loop seamlessly. |
| **F28** | Non-squares between $n^2, (n+1)^2$ | $n = 16$ | Strictly between $256$ and $289$: $289 - 256 - 1 = 32 = 2(16)$. |

---

## 5. Tier 3: Cross-Feature Combinations & Interface Contracts

Pairwise and cross-module interactions verified by the test infrastructure:

1. **Math Insulation $\leftrightarrow$ LLE Word-Tap (`F15` $\times$ `F16` $\times$ `F18`)**:
   - Verify that when a mathematical definition like "Area $= s^2$" is rendered, the variable $s$ is wrapped in `<span class="math-var" data-math="true">` while the word "Area" triggers Hindi definition "क्षेत्रफल (Kshetraphal)".
   - Assert zero dictionary lookups triggered on algebraic variables.
2. **`<aasha-sim>` Telemetry $\leftrightarrow$ Gamified Telemetry (`F04` $\times$ `F05` $\times$ `F25`)**:
   - Verify slider adjustments on `<aasha-sim>` dispatch `aasha:telemetry` events with state `{ s: number, area: number }`.
   - Chapter HUD listens to `aasha:telemetry` and increments exploratory XP without triggering spoilers.
3. **Same-Frame Mobile Clamping $\leftrightarrow$ Canvas Resizing (`F05` $\times$ `F06` $\times$ `F11`)**:
   - Verify dynamic window resizing across 360x640, 390x844, and 412x915 invokes `fitCanvas(canvas)` synchronously without DOM overflow.
   - Assert `scrollH <= winH + 5` maintains at all aspect ratios.
4. **Golden Flow Progression $\leftrightarrow$ 3-Tier Assessment State (`F20` $\times$ `F21` $\times$ `F22` $\times$ `F23`)**:
   - Verify completing concept nodes unlocks Tier 1 Warm-up.
   - Completing Warm-up unlocks Deep Dive, and completing Deep Dive unlocks Boss Challenge.
   - Mode switcher buttons update active container synchronously.
5. **Anti-Spoiler Scaffolding $\leftrightarrow$ Progressive Hint Cycling (`F03` $\times$ `F24`)**:
   - Tapping "Need a hint?" cycles through $H_1 \to H_2 \to H_3 \to H_4$ with DOM re-render.
   - Verify hint box never reveals the final option text or numerical solution.

---

## 6. Tier 4: Real-World Application Scenarios (S01–S08)

### S01: The Will of Queen Ratnamanjuri & The 100-Locker Mystery
- **Context**: Queen Ratnamanjuri's vault contains 100 locked chests numbered 1 to 100. 100 relatives take turns toggling the lockers.
- **Mathematical Principle**: Factors come in pairs $(a, b)$ where $a \times b = N$, except for perfect squares where $a = b$ produces an odd number of distinct factors.
- **Assertion**: Lockers $1, 4, 9, 16, 25, 36, 49, 64, 81, 100$ remain open. Passcode clue ("first 5 lockers touched twice") resolves to prime numbers `2-3-5-7-11`.

### S02: Visual Gnomon Peeling & Consecutive Odd Numbers
- **Context**: Deriving $(n+1)^2 = n^2 + (2n + 1)$ via L-shaped tile addition.
- **Mathematical Principle**: $\sum_{i=1}^n (2i-1) = n^2$.
- **Assertion**: Calculating $36^2$ from $35^2 = 1225$ without full multiplication adds the 36th odd number $2(36) - 1 = 71 \implies 1225 + 71 = 1296$.

### S03: Akhil's Cloth Handkerchief Integer Root Bound
- **Context**: Akhil has a square cloth of area $125\text{ cm}^2$ and wants to cut the largest possible square handkerchief with an integer side length.
- **Mathematical Principle**: Bounding $11^2 = 121 \le 125 < 144 = 12^2$.
- **Assertion**: Maximum integer side length is strictly $11\text{ cm}$.

### S04: Aribam & Bijou Square Root Estimation Game
- **Context**: Estimating $\sqrt{250}$ without paper calculation.
- **Mathematical Principle**: Proximity interpolation between known decade squares ($15^2 = 225$ and $16^2 = 256$).
- **Assertion**: Since 250 is very close to 256, estimate is slightly under 16 ($\approx 15.8$).

### S05: The Vector Bridge: 1000 Tiny Squares Array
- **Context**: Page 11 vector diagram showing 40 clusters of $5 \times 5$ square arrays.
- **Mathematical Principle**: $40 \times 25 = 1000 = 10^3 = 2^3 \times 5^3$.
- **Assertion**: Connects square tiles to cubic numbers seamlessly; validates prime factorisation $2^3 \times 5^3$.

### S06: Hardy-Ramanujan Taxicab Partitions
- **Context**: Hardy's visit to Ramanujan discussing cab number 1729.
- **Mathematical Principle**: Smallest integer expressible as sum of two positive cubes in two different ways.
- **Assertion**: $1729 = 1^3 + 12^3 = 9^3 + 10^3$. Dual partition for 4104 is $2^3 + 16^3 = 9^3 + 15^3$, and for 13832 is $2^3 + 24^3 = 10^3 + 22^3$.

### S07: Consecutive Difference Trees
- **Context**: Successive difference calculus on square and cubic sequences.
- **Mathematical Principle**: Polynomial degree $d$ yields constant difference $d!$ at level $d$.
- **Assertion**: Square numbers ($1, 4, 9, 16, 25$) yield constant level 2 difference $\Delta^2 = 2$. Cubic numbers ($1, 8, 27, 64, 125$) yield constant level 3 difference $\Delta^3 = 6$.

### S08: Page 18 Extension Puzzles: "Square Pairs!"
- **Context**: Arranging integers such that every adjacent pair sums to a square number.
- **Mathematical Principle**: Hamiltonian path and cycle on square-sum graph.
- **Assertion**:
  - Row 1 to 17 unique path: `16-9-7-2-14-11-5-4-12-13-3-6-10-15-1-8-17` (degree 1 endpoints 16 & 17).
  - Circle 1 to 32 Hamiltonian cycle: `[1, 8, 28, 21, 4, 32, 17, 19, 30, 6, 3, 13, 12, 24, 25, 11, 5, 31, 18, 7, 29, 20, 16, 9, 27, 22, 14, 2, 23, 26, 10, 15]`.

---

## 7. Test Execution & Verification Protocol

### Test Runner Commands
```bash
# 1. Standalone E2E Test Suite (Node.js)
node tests/e2e_square_cube_suite.js

# 2. Dual-Benchmark L-Truth QA Static Analysis
node Aasha-AI/benchmarks/qa_ltruth_benchmark.js --file Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html

# 3. Headless Chrome CDP Automation
node Aasha-AI/benchmarks/automated_browser_verification.js
```

### Pass / Fail Certification Criteria
1. **Exit Code**: Exit code `0` on 100% pass; non-zero exit code on any failure.
2. **Score**: L-Truth benchmark score must be strictly `100/100`.
3. **Violations**: Exactly `0` spoilers, `0` missing misconceptions, `0` math collisions, `0` rule violations.
4. **Questions**: All 34 textbook exercises verified present, correctly classified into T1/T2/T3, with 4-tier hints.
5. **Publish Readiness**: Upon passing, generate `TEST_READY.md` containing verification signatures and test run summary.
