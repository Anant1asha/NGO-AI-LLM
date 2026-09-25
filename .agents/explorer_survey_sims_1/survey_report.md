# AASHA Simulation & Foundation Registry Survey Report
## Class 8 Mathematics: Squares, Square Roots, Cubes & Cube Roots

- **Author**: `explorer_survey_sims_1` (Simulation Architect & Codebase Investigator)
- **Target Chapter**: Class 8 Mathematics — Squares, Square Roots, Cubes and Cube Roots
- **Source Textbook**: `content/pdfs/square and cube RL public school and ncert.pdf` (NCERT Ganita Prakash / RL Public School Edition, 22 Pages)
- **Working Workspace**: `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`
- **Date**: 2026-09-19
- **Status**: Complete & Verified

---

## 1. Executive Summary

This survey provides the foundational architectural and pedagogical specification for the interactive simulation layer of the **Class 8 Mathematics: Squares and Cube Roots** chapter in the AASHA Learning Ecosystem. 

In accordance with the **Universal Experience Reuse Mandate (Never Build From Scratch)**, this investigation queried the 20+ prebuilt open-source experience catalog (`experience_registry/registry.json`), executed the automated foundation matcher (`npm run admin:match`), and analyzed the textbook ground truth from `content/pdfs/square and cube RL public school and ncert.pdf`. 

Key conclusions:
1. **Foundation Match**: The optimal foundation suite combines **F02 (MicroSims)** for 2D dynamic grid manipulatives and parameter sliders, **F04 (PhET Interactive Simulations - Area Model)** for square partition models, **F08 (Physics Notebook)** for 60 FPS lightweight Canvas isometric 3D cube projections and formula synchronization, **F01 (Escape Run)** for the Tier 3 Boss Challenge cognitive obstacle loop, and the secondary library **`factors-game` (mnito/factors-game)** for prime factor pairing and tripling trees.
2. **License Compliance**: PhET (F04) is licensed under GPL-3.0; per the AASHA GPL-3.0 License Isolation Policy, we utilize the **`EXTRACT` / `INSPIRE` strategy**, encapsulating all mathematical models and rendering logic cleanly inside `<aasha-sim>` Web Component adapters with zero copyleft contagion into core chapter files.
3. **Manipulative Suite Designed**: Five focused, highly responsive visual manipulatives have been designed to fit seamlessly in the **same mobile frame** (360x640 16:9, 390x844 19.5:9, 412x915 20:9) with strict adherence to `AashaExperienceContract` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`).
4. **Pedagogical Alignment**: Grounded 100% in the source textbook, connecting Queen Ratnamanjuri's 100-locker puzzle (odd factor count), geometric $n \times n$ grids, inverted L-shaped gnomons (repeated odd subtraction), prime factor pairing/tripling, 3D layer volume assembly, and rapid 3-digit grouping estimation.

---

## 2. Prebuilt Foundation Registry Survey

### 2.1 Automated Resource Match Report

Executing `npm run admin:match -- Mathematics 8 "Square and Cube Roots"` against `experience_registry/registry.json` generated the following certified match:

```markdown
### RESOURCE MATCH REPORT
- **Chapter**: Square and Cube Roots
- **Class**: Class 8
- **Subject**: Mathematics
- **Learning Objectives**:
  1. Master core mechanics of Square and Cube Roots
  2. Diagnose and resolve student misconceptions without giving away answers
- **Best Existing Experiences**: Escape Run (F01: EXTRACT), MicroSims (F02: EXTRACT), PhET Interactive Simulations (F04: EXTRACT), Lightbot (F05: EXTRACT), MathFluency (F06: EXTRACT), The Long Game (F15: EXTRACT)
- **Best Reusable Mechanics**: adaptive_practice, mastery_gating, spaced_repetition, pwa_offline, local_persistence, micro_skills
- **Best Simulations**: Escape Run (https://github.com/abhas9/escape-run)
- **Best Narrative / Escape Structures**: Escapp (F09) progressive clue pattern / Chocolate Broccoli Challenge (F19) Observe->Decide->Act->Result
- **Existing Coverage**: 85%
- **New Work Required**: 15% (Adapting UI to AashaExperienceContract & Indic dictionary tokens)
- **Reuse Strategy**: EXTRACT
- **License Status**: PASS (MIT)
- **Offline**: PASS (Zero remote CDN scripts)
- **Mobile**: PASS (Fits same-frame mobile viewport, min 44px touch targets)
- **Accessibility**: PASS (High contrast, readable typography)
- **Localization**: PASS (Bilingual dictionary lookup in window.WM)
- **AI Integration**: PASS (Pre-seeded in Knowledge Graph and Context Bus)
- **Mastery**: PASS (4-stage progressive hints + zero spoiler feedback)
- **Telemetry**: PASS (AashaExperienceContract telemetry event bus)
- **Final Recommendation**: DO NOT BUILD FROM SCRATCH. Wrap and adapt Escape Run under AashaExperienceContract.
```

### 2.2 Foundation-to-Concept Mapping Matrix

The chapter concepts map directly into the prebuilt foundations catalog without requiring any new engine built from scratch:

| Foundation ID & Name | Source / License | Reusable Capabilities & Mechanics | Chapter Concept Binding | Reuse Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **F02: MicroSims** | `dmccreary/microsims` (MIT) | 2D dynamic grid manipulation, parameter sliders, visual stepping algorithms | **Node 1 & 2**: 2D square dot arrays, side slider $s \in [1, 10]$, area calculation $A = s^2$, and step-by-step odd subtraction gnomon highlights. | **EXTRACT** |
| **F04: PhET Simulations** | `phetsims` (GPL-3.0 / CC-BY-4.0) | Area Model (Decimals / Algebra), partition counting, number line integer brackets | **Node 1 & 5**: Area model tile layout and continuous number line brackets for estimating non-perfect roots ($\sqrt{50} \in (7, 8)$). | **INSPIRE / EXTRACT** (isolated inside `<aasha-sim>`) |
| **F08: Physics Notebook** | `CasberryIndia/Physics-Notebook` (MIT) | Canvas 2D rendering pipeline, dynamic formula bindings, responsive canvas scaling | **Node 4**: 3D isometric cube assembly, layer slicing ($s$ layers of $s \times s$), and real-time KaTeX formula synchronization. | **EXTRACT** |
| **Secondary: `factors-game`** | `mnito/factors-game` (MIT) | Prime factor decomposition, interactive factor trees, bubble grouping | **Node 3 & 5**: Prime factor grouping into pairs of 2 ($\sqrt{N}$) and triplets of 3 ($\sqrt[3]{N}$), visual orphan factor highlighting. | **EXTRACT** |
| **F01: Escape Run** | `abhas9/escape-run` (MIT) | Adaptive practice loops, streak counters, mastery gating, timed obstacle evasion | **Tier 3: Boss Challenge**: The Queen Ratnamanjuri jewel vault puzzle, multi-step problem progression, and gamified streak mechanics. | **EXTRACT** |
| **F06: MathFluency** | `CarnegieLearning/MathFluency` (MIT) | Arithmetic fluency drills, misconception diagnostic gating, micro-skills | **Tier 1: Warm-up**: Unit digit rapid classification drills (e.g. verifying ending digits 2, 3, 7, 8 cannot be square). | **EXTRACT** |
| **F19: Chocolate Broccoli** | `funksoup/chocolate-broccoli-challenge` (MIT) | Observe $\rightarrow$ Decide $\rightarrow$ Act $\rightarrow$ Result quality loop | **Quality Gate**: Gating student interactions so observation precedes formula memorization. | **QUALITY GATE** |
| **F20: GameBox** | `saiuttejr/GameBox` (MIT) | Offline touch interaction primitives, responsive layout, min 44x44px targets | **Touch Primitives**: Single-row horizontal preset bar, mobile touch sliders, tactile tap buttons. | **EXTRACT** |

---

## 3. `<aasha-sim>` Web Component Contract & Runtime Lifecycle

### 3.1 Contract Architecture (`AashaExperienceContract`)

All simulations must implement the standard contract defined in `Aasha-AI/experience_registry/aasha_experience_contract.js`:

```javascript
class AashaExperienceContract {
  mount(container, config) { /* DOM initialization & event binding */ }
  getState() { /* Returns current serializable state object */ }
  pause() { /* Halts rAF and timers without dropping state (>=4GB RAM invariant) */ }
  resume() { /* Resumes animation loops and active listeners */ }
  reset() { /* Returns component to initial baseline */ }
  destroy() { /* Cleans up listeners, observers, and DOM bindings */ }

  emitTelemetry(eventType, payload) {
    const event = new CustomEvent('aasha:telemetry', {
      bubbles: true,
      composed: true,
      detail: {
        timestamp: Date.now(),
        foundationId: this.foundationId || 'F02',
        experienceId: this.experienceId || 'square-cube-sim',
        eventType,
        payload
      }
    });
    if (this.container && typeof this.container.dispatchEvent === 'function') {
      this.container.dispatchEvent(event);
    }
  }

  emitStateChange(newState) {
    const event = new CustomEvent('aasha:state_change', {
      bubbles: true,
      composed: true,
      detail: {
        timestamp: Date.now(),
        foundationId: this.foundationId || 'F02',
        experienceId: this.experienceId || 'square-cube-sim',
        state: newState
      }
    });
    if (this.container && typeof this.container.dispatchEvent === 'function') {
      this.container.dispatchEvent(event);
    }
  }
}
```

### 3.2 Universal `<aasha-sim>` Web Component

The `<aasha-sim>` custom element wraps the simulation canvas and controls:

```javascript
class AashaSimElement extends HTMLElement {
  constructor() {
    super();
    this._adapter = null;
    this._observer = null;
  }

  static get observedAttributes() {
    return ['foundation', 'experience-id', 'auto-pause'];
  }

  connectedCallback() {
    this.style.display = 'block';
    this.style.width = '100%';
    this.style.position = 'relative';

    // Auto-pause when outside viewport (>=4GB RAM balanced lifecycle invariant)
    if (typeof IntersectionObserver !== 'undefined') {
      this._observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (!this._adapter) return;
          if (entry.isIntersecting) {
            if (typeof this._adapter.resume === 'function') this._adapter.resume();
          } else {
            if (typeof this._adapter.pause === 'function') this._adapter.pause();
          }
        });
      }, { threshold: 0.1 });
      this._observer.observe(this);
    }
  }

  disconnectedCallback() {
    if (this._observer) {
      this._observer.disconnect();
      this._observer = null;
    }
    if (this._adapter && typeof this._adapter.destroy === 'function') {
      this._adapter.destroy();
      this._adapter = null;
    }
  }

  bindAdapter(adapter, config = {}) {
    if (this._adapter && typeof this._adapter.destroy === 'function') {
      this._adapter.destroy();
    }
    this._adapter = adapter;
    if (this._adapter && typeof this._adapter.mount === 'function') {
      this._adapter.mount(this, config);
    }
  }

  get adapter() {
    return this._adapter;
  }
}
```

### 3.3 Core Runtime Invariants for Certification

1. **Non-Destructive Lifecycle ($\ge 4$ GB RAM Invariant)**:
   - When switching tabs (e.g., from Concept Lab to Warm-up Assessment), the DOM container is hidden via `display: none`.
   - `adapter.pause()` is called, immediately stopping any active `requestAnimationFrame` or interval timers to save CPU and battery.
   - Canvas elements and WebGL/2D contexts are **never destroyed or recreated**; their buffers remain intact.
   - Verified by test suite `tests/verify_m2_runtime_lifecycle.js`.

2. **Synchronous DOM State Binding Invariant**:
   - Interactive simulation manipulatives must **never decouple** internal canvas state from visible DOM text readouts (`#simReadout`).
   - Every slider drag, button tap, or parameter change must synchronously redraw the canvas and update `#simReadout` text in the **exact same call stack**.

3. **Multi-Aspect Ratio Same-Frame Mobile Responsiveness**:
   - The concept title, definition, bilingual word-tap spans, and `<aasha-sim>` canvas container must fit in the exact same mobile viewport without scrolling across:
     - **16:9 Budget Android (360x640)**: Canvas height clamped to 92px.
     - **19.5:9 Modern iPhone (390x844)**: Canvas height clamped to 115px.
     - **20:9 Modern Android (412x915)**: Canvas height clamped to 125px.
   - Implemented via dynamic DPR-aware scaling `App.fitCanvas(canvas)`:
     ```javascript
     fitCanvas: function(canvas) {
       if (!canvas) return;
       var container = canvas.parentElement;
       var rect = container ? container.getBoundingClientRect() : canvas.getBoundingClientRect();
       var dpr = window.devicePixelRatio || 1;
       var w = Math.floor(rect.width ? (rect.width - 24) : (window.innerWidth - 64));
       w = Math.max(260, Math.min(480, w));
       var isShort = window.innerHeight <= 700;
       var isMedium = window.innerHeight > 700 && window.innerHeight <= 860;
       var h = isShort ? 92 : (isMedium ? 115 : 125);
       canvas.width = Math.round(w * dpr);
       canvas.height = Math.round(h * dpr);
       canvas.style.width = w + 'px';
       canvas.style.height = h + 'px';
       var ctx = canvas.getContext('2d');
       if (ctx) {
         ctx.setTransform(1, 0, 0, 1, 0, 0);
         if (dpr !== 1) ctx.scale(dpr, dpr);
       }
     }
     ```
   - Control presets must be a single-row horizontal swipe container:
     ```css
     .preset-bar {
       display: flex;
       flex-wrap: nowrap;
       overflow-x: auto;
       touch-action: pan-x;
       gap: 6px;
       padding-bottom: 4px;
     }
     ```
   - All interactive touch buttons must enforce minimum size $44 \times 44\text{px}$.

---

## 4. Textbook Ground Truth & Pedagogical Progression

Analysis of `content/pdfs/square and cube RL public school and ncert.pdf` (22 pages) establishes the exact pedagogical structure for the chapter:

### 4.1 Textbook Breakdown by Section

1. **Pages 1–3: The Queen Ratnamanjuri Puzzle & 100 Lockers Riddle**:
   - *Hook*: Queen Ratnamanjuri leaves her fortune of precious stones (*ratnas*) to her son Khoisnam and 99 relatives with a locker riddle.
   - *Mathematical Principle*: 100 people toggle lockers 1 to 100. Locker $k$ is toggled by each of its factors. Non-square numbers have factors in distinct pairs $(a, b)$ with $a \ne b$, yielding an even number of toggles (ends CLOSED). Perfect squares have an unpaired factor $s \times s = k$, yielding an odd number of factors (ends OPEN). Lockers 1, 4, 9, 16, 25, 36, 49, 64, 81, 100 remain open!
   - *Geometric Definition*: Square numbers form an $s \times s$ grid of stones ($1\times 1=1, 2\times 2=4, 3\times 3=9, 4\times 4=16, 5\times 5=25\dots$).

2. **Pages 4–5: Properties & Ending Digits of Squares**:
   - *Ending Digits*: All perfect squares end in $0, 1, 4, 5, 6, 9$. Numbers ending in $2, 3, 7, 8$ can NEVER be perfect squares.
   - *Trailing Zeros*: Squares only have an even number of zeros at the end ($10^2 = 100, 20^2 = 400, 40^2 = 1600$).
   - *Differences of Consecutive Squares*: $(n+1)^2 - n^2 = 2n + 1$ (consecutive odd numbers $3, 5, 7, 9, \dots$).

3. **Pages 6–7: Repeated Odd Subtraction, Inverted L (Gnomons) & Triangular Numbers**:
   - *Consecutive Odd Sum*: Sum of first $n$ odd numbers is $n^2$: $1 + 3 + 5 + \dots + (2n-1) = n^2$.
   - *Geometric Gnomons*: Visual inverted-L layers surrounding $1\times 1$ grid demonstrate why each ring adds $2n+1$ units.
   - *Repeated Subtraction Method*: Testing if $N$ is square by successively subtracting $1, 3, 5, 7, \dots$. If it reaches $0$ in $k$ steps, $\sqrt{N} = k$. For example, $25 - 1 - 3 - 5 - 7 - 9 = 0$ (5 steps $\rightarrow \sqrt{25} = 5$). If it crosses 0 (e.g. $38 \rightarrow \text{remainder } 2$), it is not a square!
   - *Triangular Numbers*: Sum of two consecutive triangular numbers equals a perfect square ($T_{n-1} + T_n = n^2$, e.g. $1+3=4=2^2, 3+6=9=3^2, 6+10=16=4^2$).

4. **Pages 8–9: Square Roots & Prime Factorisation Method**:
   - *Dual Integer Roots*: If $y = x^2$, $x$ is the square root. Every positive square has two integer roots: $+x$ and $-x$ (denoted $\pm \sqrt{y}$). $\sqrt{64} = 8$ (principal positive root).
   - *Prime Factorisation Method*: Decompose $N$ into prime factors. A number is a perfect square if its prime factors can be divided into two equal groups, or grouped into pairs of identical factors:
     $$324 = (2 \times 2) \times (3 \times 3) \times (3 \times 3) = (2 \times 3 \times 3)^2 = 18^2 \implies \sqrt{324} = 18$$
   - *Smallest Multiplier/Divisor*: Identifying unpaired factors to find the smallest number to multiply/divide to make a perfect square.

5. **Pages 10–11: Pattern Explorations & Pythagorean Triplets**:
   - *Pythagorean Triplets*: $2m, m^2 - 1, m^2 + 1$.
   - *Identity Pattern*: $a^2 + b^2 + (ab)^2 = (ab+1)^2$:
     - $1^2 + 2^2 + 2^2 = 3^2$
     - $2^2 + 3^2 + 6^2 = 7^2$
     - $3^2 + 4^2 + 12^2 = 13^2$
     - $4^2 + 5^2 + 20^2 = 21^2$
     - $9^2 + 10^2 + 90^2 = 91^2$

6. **Pages 12–14: Cubes, 3D Volume Assembly & Odd Number Sums**:
   - *Definition*: Number multiplied by itself three times ($s \times s \times s = s^3$).
   - *Geometric Representation*: 3D cube of edge length $s$ made of $s$ layers, each containing $s \times s$ unit cubes (total $s^3$ unit cubes). For $s = 4$: 4 layers of 16 cubes = 64 unit cubes.
   - *Odd Sum Series for Cubes*:
     - $1 = 1^3$
     - $3 + 5 = 8 = 2^3$
     - $7 + 9 + 11 = 27 = 3^3$
     - $13 + 15 + 17 + 19 = 64 = 4^3$
     - $21 + 23 + 25 + 27 + 29 = 125 = 5^3$
     - Sum of $n$ consecutive odd numbers starting from $n(n-1) + 1$ equals $n^3$.
   - *Properties*: Cubes of even numbers are even, odd are odd. Can end in any digit $0$ through $9$. Cubes end in multiples of 3 zeros (never exactly two zeros). Cubes of negative numbers are negative: $(-6)^3 = -216$. Cubes of fractions: $(4/6)^3 = 64/216$.

7. **Pages 15–16: Cube Roots & Prime Factorisation (Triplets)**:
   - *Inverse Operation*: $8 = 2^3 \implies \sqrt[3]{8} = 2$.
   - *Prime Factorisation (Triplets)*: Each prime factor must appear in multiples of three:
     $$3375 = (3 \times 3 \times 3) \times (5 \times 5 \times 5) = 3^3 \times 5^3 \implies \sqrt[3]{3375} = 3 \times 5 = 15$$
     $$1728 = (2^3) \times (2^3) \times (3^3) \implies \sqrt[3]{1728} = 2 \times 2 \times 3 = 12$$
   - *Smallest Multiplier/Divisor for Cubes*: If a prime factor does not appear in a triplet (e.g. $250 = 2 \times 5 \times 5 \times 5$), factor 2 is untripled $\rightarrow$ multiply by $2 \times 2 = 4$ to get 1000 ($10^3$), or divide by 2 to get 125 ($5^3$).

8. **Pages 17–22: Rapid Estimation Method for Large Cubes & Textbook Exercises**:
   - *Grouping by 3s Method*: For large numbers like $1331, 4913, 12167, 32768$:
     - Group 1 (rightmost 3 digits): Determine the unit digit of the cube root from the unique unit digit of the cube.
       (e.g., for $12,167$: right group is $167$. Since $3^3 = 27$ ends in 7, the unit digit is $3$).
     - Group 2 (remaining leftmost digits): Find the largest cube less than or equal to this number.
       (e.g., $12$ lies between $2^3 = 8$ and $3^3 = 27$; the smaller cube is $2^3$, so tens digit is $2 \implies \sqrt[3]{12167} = 23$).
     - Verified examples: $\sqrt[3]{1331} = 11, \sqrt[3]{4913} = 17, \sqrt[3]{12167} = 23, \sqrt[3]{32768} = 32$.
   - *Comparison of Differences*: Evaluating expressions like $67^3 - 66^3$ vs $43^3 - 42^3$.

---

## 5. Interactive Manipulative Suite Specification

To ground these concepts with concrete, tactile understanding, five interactive manipulatives are specified. Each manipulative operates inside `<aasha-sim>` with non-destructive lifecycle and synchronous DOM state binding.

### 5.1 Manipulative 1: 2D Square Grid & Gnomon Visualizer
- **Target Concept**: Node 1 & 2 — Geometric Area $A = s^2$, Root $\sqrt{A} = s$, and Gnomon Odd-Layering.
- **Foundations**: F02 (MicroSims) + F04 (PhET Area Model) + F08 (Physics Notebook canvas)
- **Visual Mechanics**:
  - Renders an $s \times s$ grid of square tiles with soft glowing borders.
  - Color-coded inverted L-shaped layers (gnomons) representing consecutive odd numbers ($1$ = blue, $3$ = emerald, $5$ = amber, $7$ = purple, $9$ = rose).
  - Side length slider: $s \in [1, 10]$ (Area $1 \dots 100$).
  - Toggle Mode:
    1. **"Area & Root Mode"**: Changing slider dynamically updates grid dimensions, showing $s \times s = A$ and $\sqrt{A} = s$.
    2. **"Repeated Subtraction Mode"**: Animates peeling off odd-numbered gnomons from $N$, with a counter showing step number $k = \sqrt{N}$.
  - Presets: $16$ ($4^2$), $25$ ($5^2$), $49$ ($7^2$), $64$ ($8^2$), and Non-Square $38$ (shows incomplete border with remainder 2).
- **Synchronous DOM Readout (`#simReadout`)**:
  - *"Side: $s = 5$ ➔ Area: $5 \times 5 = 25$ sq units ➔ $\sqrt{25} = 5$ (Sum of first 5 odd numbers: $1+3+5+7+9 = 25$)"*
- **Canvas Implementation Blueprint**:
  ```javascript
  function drawSquareGridSim(canvas, s, mode, activeStep) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d'); var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    
    var pad = 12;
    var maxGridSize = Math.min(w - pad * 2, h - pad * 2);
    var tileSize = Math.floor(maxGridSize / Math.max(s, 6));
    var startX = Math.floor((w - s * tileSize) / 2);
    var startY = Math.floor((h - s * tileSize) / 2);
    
    var gnomonColors = ['#38bdf8', '#34d399', '#fbbf24', '#c084fc', '#f87171', '#818cf8', '#fb923c', '#4ade80', '#e879f9', '#22d3ee'];
    
    for (var r = 0; r < s; r++) {
      for (var c = 0; c < s; c++) {
        var layer = Math.max(r, c); // Index of the inverted-L gnomon
        var color = gnomonColors[layer % gnomonColors.length];
        
        ctx.fillStyle = (mode === 'subtraction' && layer >= activeStep) ? '#334155' : color;
        ctx.fillRect(startX + c * tileSize + 1, startY + r * tileSize + 1, tileSize - 2, tileSize - 2);
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1;
        ctx.strokeRect(startX + c * tileSize + 1, startY + r * tileSize + 1, tileSize - 2, tileSize - 2);
      }
    }
  }
  ```

---

### 5.2 Manipulative 2: 3D Isometric Cube Stacker
- **Target Concept**: Node 4 — 3D Volume $V = s^3$, Cube Root $\sqrt[3]{V} = s$, and Layer Decomposition.
- **Foundations**: F08 (Physics Notebook isometric canvas) + F02 (MicroSims) + F20 (GameBox touch primitives)
- **Visual Mechanics**:
  - High-performance 2D Canvas rendering of an isometric 3D cube projection ($30^\circ$ isometric angles).
  - Renders $s \times s \times s$ unit cubes with 3-tone lighting (Top: bright `#38bdf8`, Left: medium `#0284c7`, Right: shaded `#0369a1`).
  - Edge slider: $s \in [1, 5]$ ($V \in [1, 125]$).
  - Layer Stepper / Slider: $L \in [1, s]$, allowing the student to inspect the cube layer-by-layer (e.g. for $s=4$, shows 4 separate slabs of $4 \times 4 = 16$ cubes).
  - Toggle Mode:
    1. **"Solid Assembly"**: Full 3D cube with edge annotations.
    2. **"Exploded Layer View"**: Vertical spacing between layers highlighting that Volume = $s \times (\text{Base Area } s^2)$.
    3. **"Odd Numbers Sum"**: Displays the consecutive odd numbers corresponding to $s^3$ (e.g. for $3^3$: $7 + 9 + 11 = 27$).
  - Presets: $2^3 = 8$, $3^3 = 27$, $4^3 = 64$, $5^3 = 125$.
- **Synchronous DOM Readout (`#simReadout`)**:
  - *"Edge: $s = 4$ ➔ 4 Layers of $4 \times 4$ (16) cubes ➔ Total Volume: $4 \times 16 = 64$ unit cubes ➔ $\sqrt[3]{64} = 4$"*
- **Canvas Implementation Blueprint**:
  ```javascript
  function drawIsoCubeSim(canvas, s, exploded) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d'); var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    
    var uSize = Math.min(w, h) / (s * 3.2);
    var cos30 = Math.cos(Math.PI / 6);
    var sin30 = Math.sin(Math.PI / 6);
    var originX = w / 2;
    var originY = h * 0.72;
    var layerSpacing = exploded ? 14 : 0;
    
    // Painter's algorithm: draw from back-bottom to front-top
    for (var y = 0; y < s; y++) {
      var yOffset = y * (uSize + layerSpacing);
      for (var z = s - 1; z >= 0; z--) {
        for (var x = 0; x < s; x++) {
          var px = originX + (x - z) * uSize * cos30;
          var py = originY + (x + z) * uSize * sin30 - yOffset;
          
          // Draw single isometric unit cube at (px, py)
          drawIsoUnit(ctx, px, py, uSize, cos30, sin30);
        }
      }
    }
  }

  function drawIsoUnit(ctx, x, y, size, cos30, sin30) {
    var dx = size * cos30;
    var dy = size * sin30;
    
    // Top face
    ctx.fillStyle = '#38bdf8';
    ctx.beginPath();
    ctx.moveTo(x, y - size);
    ctx.lineTo(x + dx, y - size + dy);
    ctx.lineTo(x, y - size + dy * 2);
    ctx.lineTo(x - dx, y - size + dy);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = '#0369a1'; ctx.stroke();
    
    // Left face
    ctx.fillStyle = '#0284c7';
    ctx.beginPath();
    ctx.moveTo(x - dx, y - size + dy);
    ctx.lineTo(x, y - size + dy * 2);
    ctx.lineTo(x, y + dy * 2);
    ctx.lineTo(x - dx, y + dy);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = '#0369a1'; ctx.stroke();
    
    // Right face
    ctx.fillStyle = '#0369a1';
    ctx.beginPath();
    ctx.moveTo(x, y - size + dy * 2);
    ctx.lineTo(x + dx, y - size + dy);
    ctx.lineTo(x + dx, y + dy);
    ctx.lineTo(x, y + dy * 2);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = '#075985'; ctx.stroke();
  }
  ```

---

### 5.3 Manipulative 3: Prime Factor Pairing & Triplet Balance
- **Target Concept**: Node 3 & 5 — Prime Factorisation for $\sqrt{N}$ (pairs) and $\sqrt[3]{N}$ (triplets), and Smallest Multiplier/Divisor.
- **Foundations**: Secondary Library `factors-game` (mnito/factors-game) + F02 (MicroSims) + F06 (MathFluency)
- **Visual Mechanics**:
  - Dynamically decomposes input number $N$ into prime factor bubbles (e.g. $324 \rightarrow 2, 2, 3, 3, 3, 3$).
  - Target Mode Switcher:
    1. **"Square Root Mode ($\sqrt{N}$)"**: Buckets factors in pairs of 2. One representative from each pair drops down to calculate the root ($2 \times 3 \times 3 = 18$).
    2. **"Cube Root Mode ($\sqrt[3]{N}$)"**: Buckets factors in triplets of 3. One representative from each triplet drops down to calculate root ($3 \times 5 = 15$).
  - **Orphan Factor Detection**:
    - When a factor lacks a pair or triplet (e.g. $N = 250 = 2 \times 5 \times 5 \times 5$ in Cube Root mode), the single factor `2` glows amber with a diagnostic callout.
    - Interactive action buttons:
      - *"Multiply by $2 \times 2 = 4$ to complete triplet"* $\rightarrow$ transforms to $1000$ ($\sqrt[3]{1000} = 10$).
      - *"Divide by $2$ to discard orphan"* $\rightarrow$ transforms to $125$ ($\sqrt[3]{125} = 5$).
  - Presets:
    - Square presets: $324$ ($18^2$), $144$ ($12^2$), $90$ (unpaired $2 \times 5 \rightarrow$ smallest multiplier = $10$).
    - Cube presets: $216$ ($6^3$), $3375$ ($15^3$), $250$ (untripled $2 \rightarrow$ smallest multiplier = $4$, divisor = $2$).
- **Synchronous DOM Readout (`#simReadout`)**:
  - For $324$: *"Prime Factors: $(2 \times 2) \times (3 \times 3) \times (3 \times 3)$ ➔ Paired perfectly! $\sqrt{324} = 2 \times 3 \times 3 = 18$"*
  - For $250$: *"Untripled Factor: 2 is missing a pair of 2s ➔ Multiply by 4 ($2 \times 2$) to make $1000$ ($10^3$) or Divide by 2 to make $125$ ($5^3$)"*

---

### 5.4 Manipulative 4: 100-Locker Riddle & Unit Digit Pattern Explorer
- **Target Concept**: Node 1 — The Queen Ratnamanjuri Riddle, Odd Factor Count Theorem, and Square Ending Digit Invariant.
- **Foundations**: F01 (Escape Run) + F06 (MathFluency) + F19 (Chocolate Broccoli Challenge)
- **Visual Mechanics**:
  - Interactive grid of 100 lockers (or 20 for budget viewports).
  - Step button: "Run Person $k$" toggles lockers that are multiples of $k$.
  - "Run All 100 People" instant simulation: watch lockers flip states (blue = open, dark slate = closed).
  - Lockers 1, 4, 9, 16, 25, 36, 49, 64, 81, 100 remain glowing open!
  - Factor inspector: Tap any locker (e.g. #36) to see its factor pairs:
    $(1, 36), (2, 18), (3, 12), (4, 9), (6, 6) \implies 9\text{ factors (odd)} \implies \text{Open!}$
  - Unit Digit Mapper:
    - Tap base ending digits $0 \dots 9$ $\rightarrow$ highlights resulting square endings ($0, 1, 4, 5, 6, 9$) and flags impossible endings ($2, 3, 7, 8$ highlighted in red).
- **Synchronous DOM Readout (`#simReadout`)**:
  - *"Locker #36 has 9 factors (odd!) because $6 \times 6 = 36$ pairs with itself ➔ Remains OPEN! Only perfect squares remain open."*

---

### 5.5 Manipulative 5: Rapid 3-Digit Grouping Cube Root Estimator
- **Target Concept**: Node 5 — Mental Estimation of Cube Roots for Large Numbers ($1331, 4913, 12167, 32768$).
- **Foundations**: F04 (PhET Number Line Brackets) + F06 (MathFluency) + F02 (MicroSims)
- **Visual Mechanics**:
  - Displays large cube $N$ split into two distinct color brackets:
    `[ Tens Bracket | Unit Bracket ]` (e.g., for $12,167$: `[ 12 | 167 ]`).
  - Stage 1: Right Group ($167$) isolates the ending digit $7$. A reference circle illuminates $3^3 = 27$ (ends in 7), locking the unit digit to **3**.
  - Stage 2: Left Group ($12$) illuminates a number line bracket between $2^3 = 8$ and $3^3 = 27$. Since $8 \le 12 < 27$, the smaller cube root is selected, locking the tens digit to **2**.
  - Final combined readout: $\mathbf{23}$ ($23^3 = 12167$).
  - Presets: $1331 \rightarrow 11$, $4913 \rightarrow 17$, $12167 \rightarrow 23$, $32768 \rightarrow 32$, $110592 \rightarrow 48$.
- **Synchronous DOM Readout (`#simReadout`)**:
  - *"Number: 12,167 ➔ Group 1: 167 ends in 7 ➔ Unit digit is 3 | Group 2: 12 is between $2^3 (8)$ and $3^3 (27)$ ➔ Tens digit is 2 ➔ $\sqrt[3]{12167} = 23$"*

---

## 6. Node-by-Node Chapter Architecture & Golden Flow Mapping

The chapter follows the AASHA Golden Flow sequence (**WHAT $\rightarrow$ WHY $\rightarrow$ HOW $\rightarrow$ SHOW $\rightarrow$ TRY $\rightarrow$ FEEDBACK $\rightarrow$ CONNECT $\rightarrow$ NAME**) across 5 pedagogical concept nodes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AASHA CHAPTER PROGRESSION FLOW                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
      ┌────────────────────────────────┼────────────────────────────────┐
      ▼                                ▼                                ▼
┌──────────────┐             ┌────────────────────┐             ┌──────────────┐
│  TIER 1:     │             │  CONCEPT LAB       │             │  TIER 3:     │
│  WARM-UP     │             │  (NODES 1 – 5)     │             │  BOSS        │
│  DRILLS      │             │                    │             │  CHALLENGE   │
│  (Recall &   │             │  Dual-View Same    │             │  (Ratnaman-  │
│  Ending Dig) │             │  Frame Simulation  │             │  juri Vault) │
└──────────────┘             └────────────────────┘             └──────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   Node 1: Squares &             Node 3: Square Roots          Node 4: Cubes &
   Locker Riddle                 & Prime Factor Pairs          3D Isometric Layers
   [Sim 1: 2D Grid /             [Sim 3: Factor Tree /         [Sim 2: 3D Iso Cube
    Sim 4: Lockers]               Bucket Pairing]               Stacker & Slices]
         │                                                           │
         ▼                                                           ▼
   Node 2: Odd Patterns          Node 5: Cube Roots &          Tier 2: Deep Dive
   & Gnomons                     Rapid Estimation              Assessments
   [Sim 1: Repeated              [Sim 5: 3-Digit               (Linked to Sims)
    Subtraction Mode]             Grouping Brackets]
```

### Detailed Node Specifications

| Node | Inquiry Title (Universal Teaching Language) | Core Mathematical Concept | Bound Manipulative | Textbook Origin |
| :--- | :--- | :--- | :--- | :--- |
| **Node 1** | *Why do only certain lockers remain open in Queen Ratnamanjuri's riddle?* | Perfect squares, area of geometric squares $s^2$, odd number of factors, square ending digits ($0,1,4,5,6,9$). | **Sim 4**: 100-Locker Toggle & Unit Digit Explorer | Pages 1–5 |
| **Node 2** | *How can adding consecutive odd numbers build a perfect square?* | Consecutive odd sum $n^2$, gnomon L-layers, difference of consecutive squares $(n+1)^2 - n^2 = 2n+1$, repeated subtraction test. | **Sim 1**: 2D Square Grid & Gnomon Visualizer | Pages 5–7 |
| **Node 3** | *How do pairs of prime factors reveal the hidden side of a square?* | Square root $\pm \sqrt{N}$, prime factor pairing into two equal groups, smallest multiplier/divisor, Pythagorean triplets. | **Sim 3**: Prime Factor Pairing Balance | Pages 8–11 |
| **Node 4** | *What makes a number a 3D cube and how are its layers stacked?* | Cube numbers $s^3$, 3D volume layers $s \times s^2$, consecutive odd sums for cubes ($3+5=8, 7+9+11=27$), trailing zeros in 3s. | **Sim 2**: 3D Isometric Cube Stacker | Pages 12–14 |
| **Node 5** | *How can you find the cube root of a giant number in 5 seconds without a calculator?* | Cube roots $\sqrt[3]{N}$, prime factor triplets, 3-digit grouping rapid mental estimation ($1331, 4913, 12167, 32768$). | **Sim 5**: 3-Digit Grouping Estimator | Pages 15–22 |

---

## 7. Dual-Benchmark Quality Certification Guardrails

Before this chapter can be certified, the synthesis team must pass both automated gates:

### 7.1 Static Analysis Gate: `qa_ltruth_benchmark.js` (100/100 Score)
1. **Rule #1 Zero-Spoiler Invariant**:
   - The misconception explanation (`m` attribute / `data-m`) must **never** leak the correct answer, contain arithmetic evaluations matching the correct answer, or use giveaway phrasing (`is`, `giving`, `becomes`, `instead of`, `to get`, `yielding`, `result is`, `should be`).
   - All distractor feedback must be strictly diagnostic (>15 characters), explaining the procedural error (e.g. *"Subtracted the first odd number but forgot to proceed with consecutive odd numbers 3, 5, 7"*).
2. **Pre-LLE Mathematical Insulation**:
   - All LaTeX expressions (`\( ... \)`, `$$ ... $$`, `$...$`) and single algebraic variables ($x, y, s, n$) must be shielded via `__AASHA_MATH_X__` placeholders and `<span class="math-var" data-math="true">` before bilingual dictionary tokenization (`rt()` / `window.WM`).
   - Zero math-rt collisions permitted.
3. **Question Schema Validation**:
   - 100% of questions must have 4 distinct options, exactly 1 correct answer, and complete 4-tier scaffolding hints (`H1` hook $\rightarrow$ `H2` concept $\rightarrow$ `H3` strategy $\rightarrow$ `H4` intermediate step).

### 7.2 Dynamic Browser Automation Gate: Headless Chrome CDP Verification
1. **Console Cleanliness**: Zero JavaScript errors or uncaught exceptions during multi-step navigation.
2. **Same-Frame Mobile Viewport Compliance**:
   - Tested across 360x640, 390x844, and 412x915 viewports.
   - Enforces hard assertion: `scrollH <= winH + 5` on concept lab cards.
   - Interactive touch buttons must satisfy $\ge 44 \times 44\text{px}$.
3. **Bilingual Word-Tap Interactivity**:
   - 100% of vocabulary words trigger `#wordDialog` with valid Hindi translation, Devanagari phonetics, and functional Web Speech TTS button.
4. **Lifecycle & State Synchronization**:
   - Switching tabs triggers `adapter.pause()` without canvas DOM deletion.
   - Every slider or button interaction synchronously updates `#simReadout` and redraws the canvas in the same call stack.

---

## 8. Actionable Next Steps for Synthesis Team

1. **Contract Generation**: Execute `packages/chapter-contract-manager.ts` or run `npm run chapter:init -- Mathematics 8 "Square and Cube Roots"` to persist `content/contracts/Mathematics_Class8_square_and_cube_roots.yaml` with the pre-matched foundations.
2. **Exercise Bank Extraction**: Extract 100% of textbook exercises from `content/pdfs/square and cube RL public school and ncert.pdf` (Exercises across pages 18–22) into the 3-Tier Gamified Assessment (Warm-up, Deep Dive, Boss Challenge) with verified zero-spoiler `m` attributes.
3. **HTML Compilation**: Assemble `chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html` incorporating the 5 simulation procedural engines, `<aasha-sim>` Web Component adapters, KaTeX fonts inlined, and bilingual Hindi dictionary substrate (`window.WM`).
4. **Dual Certification**: Run `node benchmarks/qa_ltruth_benchmark.js` and Headless Chrome CDP verification to achieve 100/100 score and screenshot capture.
