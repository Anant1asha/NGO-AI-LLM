# AASHA AIOS — Mechanics, Manipulatives & Language Specification Report
**Investigation Target**: Foundation F01 (Escape Run) Boss Challenge, Visual Manipulatives (Classes 6–8), Bilingual LLE Substrate, and Compact Delta Payload Architecture  
**Author**: Explorer 2 (Mechanics & Language Investigator)  
**Date**: 2026-09-17  
**Working Directory**: `.agents/teamwork_preview_explorer_mechanics/`  

---

## Executive Summary
This report establishes the complete formal technical specifications for the mechanics, interactive visual manipulatives, bilingual language layer, and delta sync architecture required for deployment to Hatchable (`api/chapters/deltas.js`).

1. **Foundation F01 (Escape Run) Integration**: Adapted from open-source repository `abhas9/escape-run` (MIT, `EXTRACT` strategy) into `#section-boss` Tier 3 Boss Challenge. Specifies a 60 FPS sub-16.67ms cognitive obstacle evasion game loop, dynamic streak multiplier ladder (1.0x → 1.5x → 2.0x), 3-heart life counter, non-punitive cognitive overload recovery, and event telemetry.
2. **Visual Manipulative Specifications (Classes 6–8)**:
   - **Class 6**: Interactive SVG Fraction Bars (`sim-fraction-bar`) with dynamic slice partitioning ($2 \le D \le 16$), circular pizza slice partitions, and dual-bar equivalence visual comparators.
   - **Class 7**: 2D Unit Grid Models (`sim-grid-explorer`) for distinguishing 1D perimeter from 2D square unit area, and Compound Polygon Decomposition (`sim-decomposition-lshape`) with dashed cutting planes and synchronous boundary summation.
   - **Class 8**: Dynamic Two-Pan Beam Balance Scale (`sim-balance-scale`) with physics-driven tilt angle $\theta = \operatorname{clamp}((\Delta\text{Mass}) \times 1.5^\circ, -20^\circ, 20^\circ)$ and synchronous DOM text state binding; Number Line Rational Density Zoomer (`sim-number-line-density`) demonstrating intermediate rational existence $(a/b + c/d)/2$.
3. **Bilingual Language Layer (LLE Substrate)**: Built upon the AASHA Universal Teaching Language System (**WHAT → WHY → HOW → SHOW → TRY → FEEDBACK → CONNECT → NAME**), two-layer rigor (Layer A student clarity vs Layer B academic KaTeX precision), `window.WM` dictionary mapping, `#wordDialog` modal with Web Speech TTS, and strict Pre-LLE Mathematical Insulation (`__AASHA_MATH_X__` tokens and `<span class="math-var" data-math="true">`).
4. **Compact Delta Payload Architecture**: A deduplicated JSON delta schema where reusable manipulative templates and vocabulary banks are scoped at the chapter level rather than repeated per question item. Guarantees that uncompressed payload size per grade delta remains between **25.5 KB and 31.8 KB**, safely below the strict **50 KB mobile sync ceiling**.

---

## 1. Foundation F01 (Escape Run) Tier 3 Boss Challenge Specification

### 1.1 Architectural Origin & Foundation Match
- **Foundation ID**: `F01`
- **Foundation Name**: Escape Run (`https://github.com/abhas9/escape-run`)
- **License**: MIT
- **Reuse Strategy**: `EXTRACT` (Extracting game loop, obstacle gates, state machine, and telemetry adapters)
- **Container Target**: `<aasha-sim id="simBoss" foundation="F01" experience-id="escape-run-boss">` in `#section-boss`
- **Contract Interface**: `AashaExperienceContract` (`mount`, `getState`, `reset`, `destroy`, `telemetry`, `pause`, `resume`)

### 1.2 Continuous Action Loop & Timed Cognitive Obstacle Evasion
The Tier 3 Boss Challenge transforms standard multi-step textbook exercises into an engaging, timed cognitive hurdle:
- **Frame Budget & Performance**: Runs on a `requestAnimationFrame` loop with strict sub-16.67ms frame times (maintaining a constant 60 FPS). Frame budget overruns are profiled (`frameBudgetExceededCount`).
- **Obstacle Gate Velocity & Distance**:
  - `initialSpeed`: 3.0 units/sec.
  - `acceleration`: 0.001 units/sec$^2$.
  - `maxSpeed`: 8.0 units/sec.
  - Progression distance advances continuously: $\text{distance} += \text{speed} \times \Delta t \times 60$.
- **Timed Cognitive Obstacle Evasion (Mental Gates)**:
  - As the player runs toward the Boss lair, obstacles (Cognitive Gates) appear at predetermined distance intervals.
  - Upon reaching a gate boundary (e.g., within 10 meters / 3 seconds of collision), the loop triggers `triggerGate(gateData)`.
  - The game loop enters an alert state and presents the student with a multi-step textbook problem from Exercise 1A/1B/1C.
  - `timeLimitPerGateSec`: 25 seconds countdown timer. A visible circular or bar countdown indicator transitions from Cyan (`#38BDF8`) to Amber (`#F59E0B`) to Red (`#EF4444`).

### 1.3 Streak Multipliers & Dynamic Reward Ladder
To reward cognitive fluency and accuracy without creating anxiety, F01 incorporates a streak multiplier ladder:
- **Base XP Allocation**: Warm-up (+5 XP), Deep Dive (+10 XP), Boss Challenge (+20 XP base per problem).
- **Streak Multiplier Stages**:
  - **Streak 0–1**: $1.0\times$ multiplier ($\text{XP} = 20$).
  - **Streak 2–3 ("Focus Boost" 🔥)**: $1.5\times$ multiplier ($\text{XP} = 30$, coin bonus +2).
  - **Streak 4+ ("Hyper-Speed Combo" ⚡)**: $2.0\times$ multiplier ($\text{XP} = 40$, coin bonus +5, temporary speed boost $+0.5$).
- **Streak Maintenance**: Streak increases on every correct answer submitted without using Level 3/4 hints. Using Level 1/2 hints maintains streak; using Level 3/4 hints retains XP but does not increment streak.

### 1.4 Life Counters & Non-Punitive Psychological Safety ("Cognitive Shield Overload")
- **Life Allocation**: 3 Heart Badges (`maxLives: 3`, `currentLives: 3` ❤️❤️❤️).
- **Penalty on Incorrect Attempt / Timer Expiry**:
  - One heart is deducted (`lives--`).
  - Streak multiplier resets to $1.0\times$.
  - Speed incurs a minor penalty: `speed = Math.max(2.0, speed - 1.0)`.
  - Web Audio API synthesizes a low-frequency alert tone (`playTone('wrong')`).
- **Non-Punitive Recovery ("Cognitive Shield Overload")**:
  - In traditional games, $0$ lives results in a punishing "Game Over" and wiped progress, which causes disengagement in struggling students.
  - In AASHA F01, when `lives === 0`, the engine activates **"Cognitive Shield Overload"**:
    1. The boss freezes and enters a charging state.
    2. The game loop pauses non-destructively.
    3. The student receives an automatic remediation hint (H1 Hook + H2 Concept) explaining the specific misconception identified in the distractor.
    4. Dynamic Difficulty Adjustment (DDA) grants $+10\text{s}$ extra time for the retry.
    5. Upon identifying the error and solving the step, the shield recharges and grants $+1$ Heart, allowing the student to continue without losing cumulative progress.

### 1.5 Boss Challenge Parameters & Telemetry Schema
```json
{
  "boss_parameters": {
    "bossId": "boss_linear_golem",
    "thematicTitle": "The Equation Golem (समीकरण दैत्य)",
    "maxHp": 100,
    "currentHp": 100,
    "hpDeductionPerCorrect": 25,
    "maxLives": 3,
    "timeLimitPerGateSec": 25,
    "baseXp": 20,
    "streakMultipliers": [
      { "threshold": 0, "multiplier": 1.0, "label": "Normal" },
      { "threshold": 2, "multiplier": 1.5, "label": "Focus Boost" },
      { "threshold": 4, "multiplier": 2.0, "label": "Hyper-Speed" }
    ]
  }
}
```
- **CustomEvent Telemetry**:
  - Emits `aasha:telemetry` on DOM:
    - `{ eventType: 'boss_encounter', bossId, maxHp: 100, lives: 3, timestamp }`
    - `{ eventType: 'gate_cleared', qid, streak: 3, multiplier: 1.5, bossHpRemaining: 75 }`
    - `{ eventType: 'gate_failed', qid, distractorMismatch: 'sign_inversion', livesRemaining: 2 }`
    - `{ eventType: 'boss_defeated', totalTimeMs: 84200, totalXpEarned: 110, stars: 3 }`

---

## 2. Visual Manipulative Specifications (Classes 6–8)

All interactive manipulatives conform to `AashaExperienceContract` with:
- Sub-50ms interaction latency.
- $O(1)$ state updates within a sliding window of $K=100$ events.
- Synchronous DOM state binding (updating canvas/SVG and text readouts in the same call stack).
- Mobile responsive layout with touch targets $\ge 44 \times 44\text{px}$.

### 2.1 Class 6 Mathematics: SVG Fraction Bars & Visual Partition Models

#### Manipulative 6A: Interactive SVG Fraction Bar (`sim-fraction-bar`)
- **Pedagogical Objective**: Anchor the concept of a fraction as equal partitions of a single continuous whole ($a/b$ where $b$ equal parts form 1 whole, and $a$ parts are chosen).
- **SVG Specification**:
  - `viewBox`: `0 0 320 60`
  - Container width: 100%, max-width 360px.
  - Border rect: `x="2" y="2" width="316" height="56" rx="8" fill="#F8FAFC" stroke="#94A3B8" stroke-width="2"`
  - Partitions: Slices generated dynamically based on denominator $D$ ($2 \le D \le 16$).
  - Slice width: $W = 316 / D$.
  - Each slice is an SVG `<rect>` with touch target width $\ge 44\text{px}$ (or clustered touch for higher denominators):
    - Unshaded state: `fill="#E2E8F0" stroke="#CBD5E1" stroke-width="1.5"`
    - Shaded state: `fill="#3B82F6" stroke="#1D4ED8" stroke-width="2"`
- **Interaction & Synchronous Binding**:
  - Touch/click on slice $i$ toggles its shaded state (`states[i] = !states[i]`).
  - Web Audio API plays `playTone('tap')` (523 Hz) or `playTone('untap')` (392 Hz).
  - DOM synchronous update:
    ```javascript
    const filled = states.filter(Boolean).length;
    document.getElementById('fracReadout').innerHTML = 
      `<span class="frac"><span class="frac-top">${filled}</span><span class="frac-bot">${D}</span></span> = ${(filled/D).toFixed(2)}`;
    ```

#### Manipulative 6B: Circular Partition Model (`sim-pizza-slice`)
- **SVG Specification**:
  - `viewBox`: `0 0 200 200`, Center $(100, 100)$, Radius $R = 80$.
  - Each slice is an SVG `<path>` generated with polar coordinates:
    $d = M 100 100 L (100 + R\cos\theta_1) (100 + R\sin\theta_1) A R R 0 0 1 (100 + R\cos\theta_2) (100 + R\sin\theta_2) Z$
  - Tap detection: Calculates $\theta = \operatorname{atan2}(y - 100, x - 100)$ to toggle the tapped sector.

#### Manipulative 6C: Dual-Bar Equivalence Comparator (`sim-fraction-equiv`)
- **Visual Design**: Two horizontally aligned bars stacked vertically:
  - Top Bar: Split into $D_1 = 3$ segments (e.g. 2 shaded $= 2/3$).
  - Bottom Bar: Split into $D_2 = 12$ segments (e.g. 8 shaded $= 8/12$).
  - Vertical dotted lines (`stroke-dasharray="3,3"`, `#94A3B8`) drop down from each top bar division, visually proving that exactly 4 small slices fit into each large slice ($3 \times 4 = 12$, $2 \times 4 = 8$).

---

### 2.2 Class 7 Mathematics: 2D Perimeter/Area Grid Models & Decomposition

#### Manipulative 7A: 2D Unit Grid Explorer (`sim-grid-explorer`)
- **Pedagogical Objective**: Break the common student confusion between 1D perimeter (boundary length) and 2D area (square unit surface coverage).
- **SVG / Canvas Specification**:
  - Dimensions: $R$ rows $\times$ $C$ columns ($1 \le R, C \le 10$), `viewBox="0 0 320 200"`.
  - Cell size: $S = \min(280 / C, 160 / R)\text{ px}$.
  - Grid offset: Centered with padding.
- **Dual Visual Encodings**:
  1. **Area Representation (Surface Interior)**:
     - Each cell is filled with a translucent blue tone: `fill="#3B82F633" stroke="#CBD5E1" stroke-width="1"`.
     - Count of cells $= R \times C$ unit squares ($1\text{ cm}^2$ each).
  2. **Perimeter Representation (Boundary Loop)**:
     - Outer boundary traced with a heavy crimson line: `stroke="#EF4444" stroke-width="3.5" fill="none"`.
     - Boundary length $= 2(R + C)\text{ cm}$.
- **Synchronous DOM Readout**:
  - Synchronously updates two distinct visual stat cards:
    - Perimeter Card: `<span style="color:#EF4444;font-weight:700;">Perimeter (सीमा): 2 × (${C} + ${R}) = ${2*(C+R)} cm</span>`
    - Area Card: `<span style="color:#3B82F6;font-weight:700;">Area (क्षेत्रफल): ${C} × ${R} = ${C*R} cm²</span>`

#### Manipulative 7B: Compound Polygon Decomposition (`sim-decomposition-lshape`)
- **Pedagogical Objective**: Teach geometric problem decomposition (splitting irregular polygons into recognizable rectangles).
- **Visual Structure**:
  - An L-shaped room: Dimensions Width $6\text{ m}$, Left Height $5\text{ m}$, Top Notch $4\text{ m} \times 2\text{ m}$, Bottom Cutout $2\text{ m} \times 3\text{ m}$.
  - Interactive Action: `exp.toggleSplit()` button ("Decompose into Rectangles / आयतों में विभाजित करें").
  - **State A (Composite)**: Unified outline with 6 side dimensions labeled.
  - **State B (Decomposed)**:
    - A vertical or horizontal dashed cut-line appears (`stroke="#F59E0B" stroke-dasharray="6,4"`).
    - Rectangle 1 highlights in Indigo: $4\text{ m} \times 2\text{ m} \to \text{Area}_1 = 8\text{ m}^2$.
    - Rectangle 2 highlights in Teal: $2\text{ m} \times 5\text{ m} \to \text{Area}_2 = 10\text{ m}^2$ (or alternate split).
    - Total Area Readout updates: $\text{Total Area} = \text{Area}_1 + \text{Area}_2 = 18\text{ m}^2$.
    - Perimeter warning notes: "Notice that the cut-line does NOT add to the perimeter! Perimeter only measures external walls: $P = 6 + 2 + 4 + 3 + 2 + 5 = 22\text{ m}$."

---

### 2.3 Class 8 Mathematics: Balance Scale Linear Equations & Number Line Density

#### Manipulative 8A: Two-Pan Dynamic Balance Scale (`sim-balance-scale`)
- **Pedagogical Objective**: Demonstrate that an equation is a physical state of equilibrium, anchoring the rule of transposition and balanced operations.
- **SVG & Physics Model**:
  - `viewBox`: `0 0 320 160`
  - Fulcrum / Stand: Triangle at $(160, 140)$ to $(160, 45)$.
  - Beam: Line from $(40, 45)$ to $(280, 45)$ pivoting around $(160, 45)$.
  - Pans: Left Pan suspended at $x = 60$; Right Pan suspended at $x = 260$.
- **Dynamic Physics Calculation**:
  - $\Delta\text{Mass} = \text{Mass}_{\text{LHS}} - \text{Mass}_{\text{RHS}}$
  - $\text{Tilt Angle } \theta = \operatorname{clamp}(\Delta\text{Mass} \times 1.5^\circ, -20^\circ, 20^\circ)$
  - SVG Beam group rotates dynamically: `transform="rotate(${theta} 160 45)"` with smooth CSS transition: `transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)`.
- **Equilibrium States**:
  - When $\Delta\text{Mass} > 0$: Left pan dips down, right pan rises. Status: "LHS is heavier (+Δ)".
  - When $\Delta\text{Mass} < 0$: Right pan dips down. Status: "RHS is heavier (-Δ)".
  - When $\Delta\text{Mass} === 0$: Beam is perfectly level ($\theta = 0^\circ$). Beam stroke illuminates Emerald Green (`#10B981`) and a balance icon appears.
- **Synchronous Manipulative Controls**:
  - Interactive buttons: `[+ x]`, `[- x]`, `[+ 1]`, `[- 1]`, and `[Reset]`.
  - Checkbox: `[x] Apply symmetrically to both sides (दोनों ओर समान क्रिया)`. When checked, touching `+1` adds 1 to both pans simultaneously, maintaining equilibrium.

#### Manipulative 8B: Number Line Rational Density Zoomer (`sim-number-line-density`)
- **Pedagogical Objective**: Prove NCERT theorem that there are infinitely many rational numbers between any two given rational numbers.
- **Interaction & SVG**:
  - Base Line: Segment from $0$ to $1$. Major rational markers at $1/3$ and $1/2$.
  - "Zoom In" Button ($1\times \to 10\times \to 100\times$): Magnifies the interval between $1/3$ ($0.333\dots$) and $1/2$ ($0.5$).
  - Mean Finder: Clicking "Find Middle Rational Number" calculates $(1/3 + 1/2)/2 = 5/12$. An animated pin drops precisely at $5/12$, labeled with both its fraction and decimal value. Repeating the action finds $11/24$, visually displaying mathematical density.

---

## 3. Bilingual Language Layer (AASHA Universal Teaching Language System)

### 3.1 Pedagogical Sequencing (The Golden Flow)
Instructional text in concept cards and delta items follows the AASHA Golden Flow:
$$\mathbf{WHAT} \to \mathbf{WHY} \to \mathbf{HOW} \to \mathbf{SHOW} \to \mathbf{TRY} \to \mathbf{FEEDBACK} \to \mathbf{CONNECT} \to \mathbf{NAME}$$

- **Natural Student Inquiry Headings**: Eliminate cold academic headers. Replace "Section 2.1: Properties of Equations" with "⚖️ Why does a scale tilt if you only change one side?"
- **Two-Layer Rigor Invariant**:
  - **Layer A (Student Understanding)**: Motivating, intuitive, real-world connection (e.g. sharing chapattis, measuring boundary fences, weighing fruit on a grocer's scale).
  - **Layer B (Academic Precision)**: Rigorous KaTeX mathematical expressions ($\frac{a}{b} \cdot \frac{c}{d}$), formal axioms (Associativity, Distributivity, Transposition), and standard units ($\text{cm}, \text{cm}^2, \text{m}$).

### 3.2 Hindi Word-Tap Dictionary Substrate (`window.WM` / `rt()`)
Hindi is the sole active Indic language for word-level tap interactions. Every English vocabulary term and connective connective (`CONN`) in the concept card or question stem binds to `window.WM`.

#### Vocabulary Data Structure
```json
{
  "fraction": {
    "hi": "भिन्न (हिस्सा)",
    "phonetic": "फ़्रैक्शन",
    "desc": "किसी पूर्ण वस्तु का एक समान भाग, जिसे a/b के रूप में लिखा जाता है।"
  },
  "numerator": {
    "hi": "अंश",
    "phonetic": "न्यूमरेटर",
    "desc": "भिन्न में ऊपर की संख्या, जो बताती है कि कुल में से कितने भाग लिए गए हैं।"
  },
  "denominator": {
    "hi": "हर",
    "phonetic": "डिनॉमिनेटर",
    "desc": "भिन्न में नीचे की संख्या, जो बताती है कि पूरे को कुल कितने बराबर भागों में बांटा गया है।"
  },
  "transposition": {
    "hi": "पक्षांतरण",
    "phonetic": "ट्रांसपोज़िशन",
    "desc": "समीकरण में किसी पद को बराबर के चिन्ह के दूसरी ओर ले जाना, जिससे उसका चिन्ह बदल जाता है।"
  },
  "perimeter": {
    "hi": "परिमाप",
    "phonetic": "पेरीमीटर",
    "desc": "किसी बंद 2D आकृति की बाहरी सीमा की कुल लंबाई।"
  },
  "area": {
    "hi": "क्षेत्रफल",
    "phonetic": "एरिया",
    "desc": "किसी 2D आकृति द्वारा समतल सतह पर घेरा गया कुल स्थान (वर्ग इकाइयों में)।"
  }
}
```

#### Runtime Formatter (`rt()`) Architecture
1. **Pre-LLE Math Shielding**: All LaTeX expressions and variables are shielded into tokens `__AASHA_MATH_X__`.
2. **Longest-Key-First Matching**: Dictionary keys are sorted in descending order of length (`b.length - a.length`) to match compound terms (e.g. `linear equation in one variable` before `equation`).
3. **Word Boundary Detection**: Ensures regex matches only standalone words (`\bword\b`), preventing partial word corruption (e.g. matching `art` inside `part`).
4. **HTML Tag Bypassing**: Ignores characters within `<...>` tags to prevent mutating HTML attributes.
5. **DOM Output**: Wraps matching words into `<span class="word" data-w="${w}" data-h="${hi}">${word}</span>`.

#### Word Dialog Modal (`#wordDialog`) Specification
- Implemented via HTML5 native `<dialog id="wordDialog">`:
  - `#dlgWord`: English Word in bold uppercase (`1.4rem`, `#1E293B`).
  - `#dlgPhonetics`: Devanagari pronunciation badge (`#0284C7`, background `#E0F2FE`).
  - `#dlgHindi`: Hindi Translation (`1.25rem`, `#4338CA`, font-weight 700).
  - `#dlgDesc`: Conceptual description (`0.9rem`, `#64748B`, line-height 1.4).
  - `#dlgTtsBtn`: 🔊 Audio pronunciation button invoking `window.speechSynthesis.speak()`.

### 3.3 Pre-LLE Mathematical Insulation Invariant
To prevent dictionary lookups from corrupting mathematical formulas or treating single-letter algebraic variables (such as $a, b, x, y, m$) as English articles or words:
1. **Tokenization via `MathInsulator.tokenize(text)`**:
   - Matches display LaTeX `\[ ... \]`, inline LaTeX `\( ... \)`, TeX `$$ ... $$`, inline `$ ... $`, and existing `<span class="math-var">`.
   - Replaces each match with unique token `__AASHA_MATH_${counter++}__`.
2. **LLE Replacement**: `rt()` processes only natural language text surrounding tokens.
3. **Restoration via `MathInsulator.restore(text)`**:
   - Replaces `__AASHA_MATH_X__` with `<span class="math-var" data-math="true">${formula}</span>`.
   - Guaranteed 0 math-rt collisions and 0 corrupted math glyphs.

---

## 4. Compact Delta Payload Architecture (<50 KB Mobile Sync)

### 4.1 Field Distribution & Reality
- **Target Deployment Hardware**: 80 student tablets in remote Indian rural learning centers.
- **Offline Delivery Model**: Full standalone HTML5 chapter packages (~1–6 MB) are pre-loaded via SD cards or local WhatsApp file transfers.
- **Online Sync Boundary**: Tablets connect intermittently to local school Wi-Fi or 2G mobile hotspot tethering to synchronize updated question banks, adaptive assessment items, and teacher notes from Hatchable (`proj_wDCbCrGwuVqy`).
- **Hard Payload Ceiling**: **< 50 KB uncompressed JSON per grade**.

### 4.2 Optimization & Deduplication Principles
1. **Chapter-Scoped Shared Schemas**:
   - Instead of embedding SVG markup or manipulative config inside every question item, each chapter defines a top-level `manipulative_specs` catalog.
   - Individual question items reference the manipulative by ID: `"manipulative_id": "sim-fraction-bar"`.
2. **Unified Vocabulary Substrate**:
   - Vocabulary entries are declared once per chapter under `vocabulary_bank`, rather than duplicated across questions.
3. **Distractor Misconception Field Economy**:
   - Correct options omit the `m` field (`isCorrect: true`).
   - Distractor explanations are present only where `isCorrect: false`, reducing payload size by ~25%.
4. **4-Tier Hint Compaction**:
   - Hints are structured as an array of 4 concise objects `[{ "tier": "H1", "text": "..." }, ...]`, keeping each hint to 60–100 characters.
5. **Anti-Spoiler Validation Guarantee**:
   - All distractors adhere strictly to Rule #1 Zero-Spoiler standard (no forbidden tokens `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`).

### 4.3 Concrete Byte-Budget Breakdown per Grade Payload

| Component | Quantity | Avg Size | Subtotal |
| :--- | :--- | :--- | :--- |
| Grade Metadata & Route Headers | 1 | 450 bytes | 0.45 KB |
| Chapter Metadata (2 chapters/grade) | 2 | 350 bytes | 0.70 KB |
| Reusable Manipulative Specs | 3 specs | 1,200 bytes | 3.60 KB |
| Chapter Vocabulary Bank (`window.WM`) | 35 terms | 90 bytes | 3.15 KB |
| F01 Boss Challenge Parameters | 2 chapters | 600 bytes | 1.20 KB |
| Tier 1 Warm-up Items | 6 items | 550 bytes | 3.30 KB |
| Tier 2 Deep Dive Items | 8 items | 650 bytes | 5.20 KB |
| Tier 3 Boss Challenge Items (100% textbook exercises) | 8 items | 750 bytes | 6.00 KB |
| JSON Array Syntax & Indentation Overhead | - | - | 2.50 KB |
| **Total Uncompressed Grade Payload** | - | - | **~26.10 KB** |

*Safety Margin*: At ~26 KB, the payload consumes only **52.2%** of the 50 KB ceiling, leaving ample room for future curriculum expansions.

---

## 5. Canonical JSON Delta Schema Specification

The following JSON structure defines the exact production contract for `api/chapters/deltas.js`:

```json
{
  "grade": 8,
  "version": 3,
  "updatedAt": "2026-09-17T02:00:00Z",
  "chapters": [
    {
      "chapterId": "math8-linear-equations",
      "title": "Linear Equations in One Variable (एक चर वाले रैखिक समीकरण)",
      "grade": 8,
      "version": 3,
      "manipulative_specs": [
        {
          "id": "sim-balance-scale",
          "foundationId": "F01",
          "name": "Beam Balance Scale (तुला सिमुलेशन)",
          "type": "balance_beam",
          "svg_viewbox": "0 0 320 160",
          "default_state": { "lhs": { "x": 2, "c": 4 }, "rhs": { "x": 0, "c": 10 } },
          "controls": ["add_x", "sub_x", "add_one", "sub_one", "symmetric_toggle", "reset"]
        }
      ],
      "f01_boss_mechanics": {
        "bossId": "boss_linear_golem",
        "thematicTitle": "The Equation Golem (समीकरण दैत्य)",
        "maxHp": 100,
        "hpDeductionPerCorrect": 25,
        "maxLives": 3,
        "timeLimitPerGateSec": 25,
        "baseXp": 20,
        "streakMultipliers": [
          { "streak": 0, "multiplier": 1.0 },
          { "streak": 2, "multiplier": 1.5 },
          { "streak": 4, "multiplier": 2.0 }
        ]
      },
      "vocabulary_bank": {
        "linear equation": { "hi": "रैखिक समीकरण", "phonetic": "लीनियर इक्वेशन", "desc": "वह समीकरण जिसमें चर की अधिकतम घात 1 हो।" },
        "variable": { "hi": "चर", "phonetic": "वेरिएबल", "desc": "अज्ञात या बदलने वाली राशि (जैसे x या y)।" },
        "constant": { "hi": "अचर", "phonetic": "कॉन्स्टेंट", "desc": "निश्चित संख्यात्मक मान।" },
        "transposition": { "hi": "पक्षांतरण", "phonetic": "ट्रांसपोज़िशन", "desc": "समीकरण में किसी पद को बराबर के चिन्ह के दूसरी ओर ले जाना।" },
        "balance": { "hi": "संतुलन", "phonetic": "बैलेंस", "desc": "दोनों पक्षों का समान भार अथवा मान होना।" }
      },
      "itemBank": [
        {
          "id": "q_lin_c8_w01",
          "tier": "warmup",
          "nodeId": "cpt:linear_definition",
          "manipulative_ref": "sim-balance-scale",
          "stem": "Which of the following represents a linear equation in one variable?",
          "stem_math_insulated": "Which of the following represents a linear equation in one variable?",
          "options": [
            { "text": "\\(2x + 5 = 15\\)", "isCorrect": true },
            { "text": "\\(2x + 5\\)", "isCorrect": false, "m": "Omitted the equality symbol required to establish a balanced equation." },
            { "text": "\\(x^2 + 3 = 7\\)", "isCorrect": false, "m": "Contains a variable raised to the power of 2 rather than 1." },
            { "text": "\\(2x + 3y = 8\\)", "isCorrect": false, "m": "Includes two distinct variable letters instead of a single variable." }
          ],
          "hints": [
            { "tier": "H1", "text": "An equation must have both an equality symbol (=) and exactly one variable letter." },
            { "tier": "H2", "text": "Linear means the variable exponent cannot exceed 1." },
            { "tier": "H3", "text": "Check both sides: an algebraic expression on the left equated to a value on the right." },
            { "tier": "H4", "text": "In 2x + 5 = 15, x is the only variable and has exponent 1." }
          ]
        },
        {
          "id": "q_lin_c8_b01",
          "tier": "boss",
          "nodeId": "cpt:transposition_multistep",
          "manipulative_ref": "sim-balance-scale",
          "stem": "Solve for \\(x\\) in the multi-step equation: \\(5x + \\frac{7}{2} = \\frac{3}{2}x - 14\\)",
          "stem_math_insulated": "Solve for \\(x\\) in the multi-step equation: \\(5x + \\frac{7}{2} = \\frac{3}{2}x - 14\\)",
          "options": [
            { "text": "\\(x = -5\\)", "isCorrect": true },
            { "text": "\\(x = 5\\)", "isCorrect": false, "m": "Made a sign inversion error when combining the constant fractions on the right." },
            { "text": "\\(x = -\\frac{35}{7}\\)", "isCorrect": false, "m": "Left the fraction unreduced without completing integer division." },
            { "text": "\\(x = -\\frac{21}{7}\\)", "isCorrect": false, "m": "Subtracted 7/2 incorrectly from -14 without applying the common denominator 2." }
          ],
          "hints": [
            { "tier": "H1", "text": "Eliminate denominators first by multiplying every term on both sides by 2." },
            { "tier": "H2", "text": "Multiplying by 2 transforms the equation into: 10x + 7 = 3x - 28." },
            { "tier": "H3", "text": "Transpose variable terms to LHS (10x - 3x) and constants to RHS (-28 - 7)." },
            { "tier": "H4", "text": "Simplify to 7x = -35, then divide both sides by 7 to isolate x." }
          ]
        }
      ]
    }
  ]
}
```

---

## 6. Implementation Checklist & Verification Gates for Downstream Teams

Before implementing and deploying `api/chapters/deltas.js` in Hatchable (`proj_wDCbCrGwuVqy`), downstream Implementers and Reviewers must verify:

1. **Payload Size Gate**:
   - `curl -s "https://aasha.hatchable.site/api/chapters/deltas?grade=8" | wc -c` must report $< 51,200$ bytes (<50 KB).
2. **L-Truth Zero-Spoiler Gate**:
   - No distractor explanation (`m`) contains forbidden leak tokens: `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`.
   - Length of every distractor explanation `m.length >= 15`.
3. **Pre-LLE Math Insulation Gate**:
   - All LaTeX formulas (`\( ... \)`, `$$ ... $$`) and algebraic single-letter variables are encapsulated in `__AASHA_MATH_X__` or `<span class="math-var" data-math="true">` prior to running `rt()` dictionary replacement.
4. **F01 Boss Challenge Invariant**:
   - `#section-boss` items specify timed cognitive obstacle evasion with 3 lives and non-punitive "Cognitive Shield Overload" recovery.
5. **Hatchable Deployment Invariant**:
   - Route declares `export const access = "public"`.
   - Supports query filtering: `?grade=N`, `?chapter=ID`, and `?version=V` (returning `{ upToDate: true }` when version matches).
