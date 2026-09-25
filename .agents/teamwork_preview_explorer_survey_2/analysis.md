# AASHA V5 Architectural Teardown & Class 8 Rational Numbers Survey Report

**Author**: `teamwork_preview_explorer_survey_2` (Phase 0: Survey Explorer)  
**Date**: 2026-09-13  
**Status**: COMPLETE  
**Target File**: `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_survey_2\analysis.md`

---

## Executive Summary

This report delivers a rigorous architectural teardown of the AASHA V5 benchmark standard, examining the reference implementations in `Aasha-AI/chapters/` (specifically the 6.78 MB Class 6 Fractions reference standard `Fractions_Gamified_v5_(2)_Enhanced_v6.html`, the 1.02 MB JSXGraph-inlined Polynomials chapter `Polynomials_JSXGraph_Inlined_Enhanced_v6.html`, and existing 93–94 KB Class 8 Rational Numbers chapters `RationalNumbers_Class8_Gamified_v5_Enhanced_v6.html` and `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`).

The survey establishes the exact technical mechanics underpinning **Zero-CDN Self-Containment**, the **Golden Flow pedagogical sequence** (WHAT → WHY → HOW → SHOW → TRY → FEEDBACK → CONNECT → NAME), the **Same-Frame Mobile Viewport Responsiveness Invariant** across 16:9, 19.5:9, and 20:9 aspect ratios, the **Bilingual Indic (Hindi) LLE Substrate** with mathematical insulation, and the automated compilation and QA benchmark harnesses (`qa_ltruth_benchmark.js` and `automated_browser_verification.js`).

---

## 1. Architectural Teardown of the V5 Reference Benchmark

### 1.1 Comparative Analysis of Chapter Implementations

| Metric / Feature | Class 6 Fractions Benchmark (`Fractions_Gamified_v5_(2)_Enhanced_v6.html`) | Class 10 Polynomials (`Polynomials_JSXGraph_Inlined_Enhanced_v6.html`) | Existing Class 8 Rational Numbers (`RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`) |
| :--- | :--- | :--- | :--- |
| **Total File Size** | **6,781,761 bytes (6.47 MB)** | **1,074,645 bytes (1.02 MB)** | **94,814 bytes (0.09 MB / 92.6 KB)** |
| **External CDN Calls** | **0 (100% Offline)** | **0 (100% Offline)** | **0 (100% Offline)** |
| **Simulation Engine** | Inlined PhET Equality Simulation (Base64 decoded HTML payload: 6,586,569 chars) | Inlined JSXGraph 1.13.2 Library (JS + CSS inlined: ~800 KB) | Procedural Canvas 2D Engine (5 custom interactive manipulatives) |
| **KaTeX / Math Engine** | MathJax / system font fallback | Inlined KaTeX tags / JSXGraph renderers | MathIsolation CSS + Unicode + System Math Fonts (`Cambria Math`, `Times New Roman`) |
| **Audio Synthesis** | Web Audio API procedural synthesis | Web Audio API tone synthesis | Web Audio API procedural tone synthesis (`tap`, `correct`, `wrong`, `levelup`) |
| **Particle FX** | Inlined Canvas Confetti Engine | — | Inlined Canvas Confetti Engine (50 particles, zero dependencies) |
| **LLE Bilingual Word Map** | Inline `var WM = { ... }` (6,626 chars) | — | Inline `var WM = { ... }` (140+ terms) + `CONN` connectives |
| **QA L-Truth Score** | 100/100 (0 questions tested in legacy structure) | — | 100/100 (15 questions, 45 misconceptions, 0 spoilers, 0 collisions) |
| **Chrome CDP Browser Test** | Untested | Untested | 100% PASSED across 5 mobile viewports (16:9, 19.5:9, 20:9) |

### 1.2 The 6+ MB Benchmark Anatomy: Why Fractions is 6.78 MB

Inspection of `Fractions_Gamified_v5_(2)_Enhanced_v6.html` revealed that the 6.78 MB payload is partitioned as follows:
1. **Inlined PhET Simulation (`var PHET_SIMS`)**: Line 38 contains `var PHET_SIMS = { equality: atobDecode("PCFET0NUWVBFIEhUTUw+...") }`. This single Base64-encoded string spans **6,586,569 characters** (97.1% of the entire file). It encapsulates the complete standalone HTML5/WebGL PhET Fraction Equality simulation (from Foundation F04). At runtime, `atobDecode()` inflates the simulation into an isolated iframe without network access.
2. **H5P & PIE Components Wrapper**: Injected by `packages/chapter-builder/base64-bundler.js`, adding inlined webpack bundles `dist/h5p-standalone-wrapper.js` (22,789 chars) and `dist/pie-player-components.js` (19,691 chars).
3. **Core Aasha Runtime**: 68,247 characters of CSS, DOM controllers, Web Audio API synthesis, LLE word maps, and state management.

### 1.3 Zero-CDN Self-Containment Mechanics

Self-containment is achieved without external network or CDN calls (`http://` or `https://` scripts/links):
1. **Fonts**:
   - Primary typographical stack relies on system font stacks: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`.
   - Mathematical expressions leverage system math fonts: `'Cambria Math', 'Times New Roman', serif`.
   - In full pipeline builds (as noted in `OPEN_SOURCE_TOOLING.md` and `rebuild-v5-chapters.js`), custom fonts (Fredoka, Inter, or KaTeX Math fonts) are converted to WOFF2 Base64 data URIs embedded directly inside `@font-face { src: url('data:font/woff2;base64,...'); }`.
2. **Audio Tone Synthesis**:
   - Implemented via the browser's native Web Audio API (`window.AudioContext || window.webkitAudioContext`), requiring zero external `.mp3` or `.wav` files.
   - Procedurally synthesizes 4 distinct sound frequencies:
     - `tap`: 440 Hz (A4) sine wave, 80ms decay (`gain.exponentialRampToValueAtTime(0.001, now + 0.08)`).
     - `correct`: Major third chime (523.25 Hz C5 followed by 659.25 Hz E5 at +100ms, 280ms duration).
     - `wrong`: Low dissonance buzz (260 Hz, 250ms duration).
     - `levelup`: Arpeggio chord progression (523.25 Hz C5, 659.25 Hz E5, 783.99 Hz G5, 1046.5 Hz C6 staggered by 90ms intervals).
3. **Confetti Particle Engine**:
   - Direct HTML5 Canvas procedural rendering (`#confettiCanvas`).
   - Generates 40–60 particles with random velocities (`vx = (Math.random() - 0.5) * 12`, `vy = (Math.random() - 0.7) * 14`), gravity acceleration (`vy += 0.3`), and color palette (`['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#dc2626']`). No external canvas or particle libraries required.
4. **Icons**:
   - Inlined SVG vectors (e.g., brand logo in `.brand-logo svg`) and Unicode emojis (`🪙`, `⭐`, `🔥`, `🌱`, `📍`, `⚖️`, `✨`).

---

## 2. Golden Flow Teardown: Pedagogical Progression & Same-Frame Viewport

### 2.1 The 8-Stage Pedagogical Sequence

The chapter architecture strictly maps to the AASHA Universal Teaching Language System:

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  WHAT   │ ──> │   WHY   │ ──> │   HOW   │ ──> │  SHOW   │
│ (Hook)  │     │ (Incept)│     │(Proc/WE)│     │ (Dual)  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │                                               │
     ▼                                               ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  NAME   │ <── │ CONNECT │ <── │FEEDBACK │ <── │   TRY   │
│ (Badge) │     │ (CONN)  │     │(Diag-m) │     │(Manip)  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

1. **WHAT (Inquiry Hook)**:
   - Implemented via `step.t === 'intro'` in `NODES[nIdx].steps[0]`.
   - Never uses meta-labels like "The Real-World Hook".
   - Presents a grounded real-world scenario with a natural student inquiry heading (e.g., *"Seema & Sachin at the Stationery Shop: Why do we need numbers beyond whole numbers and fractions?"*).
2. **WHY (Conceptual Inception)**:
   - Implemented via `step.t === 'text'` in `NODES[nIdx].steps[1]`.
   - Explains the causal *why* behind mathematical rules (e.g., why a denominator cannot be zero because division by zero is mathematically undefined; why multiplying numerator and denominator by $-1$ preserves the fraction's value).
3. **HOW (Procedural Scaffolding & Worked Example)**:
   - Implemented via `step.t === 'worked'` pointing to `WE[weId]`.
   - Breaks down problem solving into distinct steps (`we.steps`), each accompanied by intermediate checks (`s.check`) before revealing the final answer (`final: true`).
4. **SHOW (Interactive Dual-View Simulation)**:
   - Embedded directly alongside the concept definition in the same frame (`mountSim(step.simType)`).
   - Renders 5 custom interactive models:
     - `equiv`: Non-standard vs. standard form bar partitioning with HCF reduction.
     - `numline`: Real-time number line coordinate pin with unit interval subdivision.
     - `addsub`: Common denominator pizza-slice equalizer with LCM scaling.
     - `reciprocal`: Multiplicative inverse balance scale balancing to product 1.
     - `props`: Commutative and associative geometric tile rearranger.
5. **TRY (Interactive Manipulatives & Step Checks)**:
   - Direct student interaction via single-row swipeable presets (`.preset-bar`) and control buttons (`.sim-btn`).
   - Real-time manipulation updates the canvas instantly (`playTone('tap')`).
6. **FEEDBACK (Zero-Spoiler Misconception Diagnosis)**:
   - Implemented via `opt.m` attributes on all distractor options.
   - Diagnoses the exact conceptual fallacy (e.g., confusing reciprocal with additive inverse) without revealing the correct value or formula.
   - Enforced by `QuestionSchemaValidator` and `qa_ltruth_benchmark.js`.
7. **CONNECT (Bilingual Connective Scaffolding)**:
   - Non-intrusive linguistic scaffolding via `var CONN = { "if": "यदि / अगर", "because": "क्योंकि", "therefore": "इसलिए", "which means": "जिसका अर्थ है", ... }`.
   - Automatically wraps up to 2 connectives per sentence with inline Hindi cues (`<span class="connective">because <span class="connective-hi">(क्योंकि)</span></span>`).
8. **NAME (Formal Terminology & Mastery Milestones)**:
   - Concepts culminate in formal terms and mastery badges (`LEVELS`, `BADGES`: *"Standard Form Hero"*, *"Number Line Navigator"*, *"Reciprocal Champion"*).

### 2.2 Same-Frame Mobile Viewport Layout Rules

A fundamental constraint is that **concept definitions and interactive visual simulations MUST render in the exact same visual frame without scrolling on mobile viewports**.

#### Viewport-Specific CSS Clamping Rules

```css
/* Screen Container Base */
.screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 8px 12px 65px;
  min-height: 0;             /* Invariant: prevents flex item vertical overflow */
  box-sizing: border-box;
}

/* 1. 16:9 Budget Android (360x640) */
@media (max-height: 700px) {
  .brand-header { display: none; }                           /* Suppress brand header to free vertical space */
  .topbar { padding: 4px 10px; gap: 6px; }
  .screen { padding: 4px 8px 56px; min-height: 0; }
  .concept-frame { padding: 8px 10px; margin-bottom: 4px; }
  .inquiry-title { font-size: 0.88rem; margin-bottom: 3px; line-height: 1.22; }
  .concept-def { 
    font-size: 0.80rem; 
    line-height: 1.35; 
    margin-bottom: 4px; 
    max-height: 80px;                                        /* Clamped to 80px */
    overflow-y: auto; 
  }
  .sim-container { padding: 6px; margin: 4px 0; border-radius: 8px; }
  .sim-canvas { max-height: 92px; }                          /* Clamped to 92px */
  .preset-btn, .sim-btn { min-height: 44px; min-width: 44px; padding: 6px 10px; font-size: 0.76rem; }
  .bottom-bar { padding: 6px 12px; }
  .btn-primary { padding: 10px 16px; min-height: 44px; font-size: 0.90rem; }
}

/* 2. 19.5:9 Modern iPhone (390x844, 393x852) & 20:9 (360x800) */
@media (min-height: 701px) and (max-height: 860px) {
  .brand-header { padding: 4px 12px; }
  .brand-logo { width: 28px; height: 28px; }
  .brand-name { font-size: 0.75rem; }
  .brand-name-hi, .brand-tagline { display: none; }
  .topbar { padding: 6px 12px; gap: 8px; }
  .screen { padding: 6px 12px 60px; min-height: 0; }
  .concept-frame { padding: 10px 12px; margin-bottom: 6px; }
  .inquiry-title { font-size: 0.98rem; margin-bottom: 4px; line-height: 1.3; }
  .concept-def { 
    font-size: 0.84rem; 
    line-height: 1.45; 
    margin-bottom: 6px; 
    max-height: 110px;                                       /* Clamped to 110px */
    overflow-y: auto; 
  }
  .sim-canvas { max-height: 115px; }                         /* Clamped to 115px */
  .preset-btn, .sim-btn { min-height: 44px; min-width: 44px; }
  .bottom-bar { padding: 8px 14px; }
  .btn-primary { padding: 12px 16px; min-height: 44px; font-size: 0.95rem; }
}

/* 3. 20:9 Modern Pixel/Galaxy (412x915) */
@media (min-height: 861px) {
  .brand-header { padding: 4px 14px; }
  .brand-logo { width: 30px; height: 30px; }
  .brand-name { font-size: 0.78rem; }
  .topbar { padding: 6px 12px; }
  .screen { padding: 6px 12px 60px; min-height: 0; }
  .concept-frame { padding: 10px 12px; margin-bottom: 6px; }
  .inquiry-title { font-size: 0.98rem; margin-bottom: 4px; line-height: 1.25; }
  .concept-def { 
    font-size: 0.86rem; 
    line-height: 1.45; 
    margin-bottom: 6px; 
    max-height: 125px;                                       /* Clamped to 125px */
    overflow-y: auto; 
  }
  .sim-canvas { max-height: 125px; }                         /* Clamped to 125px */
  .preset-btn, .sim-btn { min-height: 44px; min-width: 44px; }
  .bottom-bar { padding: 8px 14px; }
  .btn-primary { padding: 12px 16px; min-height: 44px; font-size: 0.95rem; }
}
```

#### Preset Bar Single-Row Horizontal Swipe

```css
.preset-bar {
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  gap: 6px;
  justify-content: flex-start;
  padding: 2px 4px;
  max-width: 100%;
  scrollbar-width: none;
  touch-action: pan-x;
}
.preset-bar::-webkit-scrollbar {
  display: none;
}
.preset-btn {
  flex-shrink: 0;
  min-height: 44px;
  min-width: 44px;
  touch-action: manipulation;
  background: #f1f5f9;
  border: 1px solid var(--border-dk);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
```

#### Dynamic Canvas Scaling (`fitCanvas`)

The `fitCanvas(canvas)` function dynamically binds DOM bounding box dimensions and Device Pixel Ratio (DPR):

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

#### Bottom Navigation Bar Clearance & Backdrop

```css
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  max-width: 520px;
  margin: 0 auto;
  padding: 12px 16px;
  background: #ffffff;                                       /* 100% Opaque surface */
  border-top: 1px solid var(--border);
  box-shadow: 0 -4px 12px rgba(0,0,0,.05);
  z-index: 60;
}
```
Clearance is maintained through bottom padding on `.screen` (`56px` to `65px` + safe-area insets) and fixed height containment, ensuring buttons never overlap content.

---

## 3. Teardown of the Bilingual Indic (Hindi) LLE Substrate

### 3.1 Mathematical Insulation: `packages/aasha-rules/math_insulator.ts`

The Language Layer Engine (`rt()`) must never corrupt LaTeX formulas, mathematical symbols, or single-letter algebraic variables ($a, b, x, y, p/q$).

`MathInsulator` operates as a two-phase masking and restoration pipeline:

```typescript
export class MathInsulator {
  private static MATH_PATTERNS = [
    /\\\[[\s\S]*?\\\]/g,            // Display LaTeX \[ ... \]
    /\\\([\s\S]*?\\\)/g,            // Inline LaTeX \( ... \)
    /\$\$[\s\S]*?\$\$/g,            // Display TeX $$ ... $$
    /\$[^\$\n]+?\$/g,               // Inline TeX $ ... $
    /<span[^>]*class=["'][^"']*math[^"']*["'][^>]*>[\s\S]*?<\/span>/gi, // Math spans
  ];

  static tokenize(text: string): { maskedText: string; tokenMap: Map<string, string> } {
    const tokenMap = new Map<string, string>();
    let counter = 0;
    let masked = text;
    for (const pattern of this.MATH_PATTERNS) {
      masked = masked.replace(pattern, (match) => {
        const token = `__AASHA_MATH_${counter++}__`;
        tokenMap.set(token, match);
        return token;
      });
    }
    return { maskedText: masked, tokenMap };
  }

  static restore(maskedText: string, tokenMap: Map<string, string>): string {
    let restored = maskedText;
    for (const [token, original] of tokenMap.entries()) {
      restored = restored.replace(token, () => original);
    }
    return restored;
  }

  static wrapWithIsolation(formula: string): string {
    return `<span class="math-var" data-math="true">${formula}</span>`;
  }
}
```

In runtime HTML:
- Fractions are protected using regex fraction replacement before word splitting:
  `html = html.replace(/(-?\d+)\/(\d+)/g, '<span class="frac"><span class="frac-top">$1</span><span class="frac-bot">$2</span></span>');`
- HTML tags (`<...>`) are skipped in the lexer loop:
  `if (ch === '<') { var ci = html.indexOf('>', i); if (ci >= 0) { result += html.substring(i, ci + 1); i = ci + 1; continue; } }`
- Single-letter variables wrapped with `.math` or `.math-var` are preserved untouched.
- `qa_ltruth_benchmark.js` validates this via `auditMathRtCollisions()`, failing if single-letter keys (like `a`) exist in `WM` without `MathIsolation: true`.

### 3.2 Dictionary Database: Structure and Coverage

File: `Aasha-AI/experience_registry/aasha_dictionary_db.json`
- **Total Entries**: **1,142 terms**.
- **Format**: Flat Key-Value String Mapping matching the canonical standard:
  `"[सरल अर्थ] ([देवनागरी उच्चारण])"`
- **Samples**:
  - `"rational"`: `"परिमेय संख्या (p/q रूप में लिखी जा सकने वाली संख्या)"`
  - `"numerator"`: `"अंश (बटे के ऊपर की संख्या)"`
  - `"denominator"`: `"हर (बटे के नीचे की संख्या)"`
  - `"additive"`: `"योज्य (जोड़ से संबंधित)"`
  - `"multiplicative"`: `"गुणात्मक (Multiplicative Inverse: गुणा करने पर 1 आना)"`
  - `"inverse"`: `"प्रतिलोम / उलटा (Inverse)"`
  - `"commutative"`: `"क्रमविनिमेय नियम (क्रम बदलने पर भी उत्तर समान रहना)"`
  - `"associative"`: `"सहचारिता नियम (समूह बदलने पर भी उत्तर समान रहना)"`
  - `"distributive"`: `"वितरण नियम: a(b + c) = ab + ac"`
  - `"closure"`: `"संवृत नियम (Closure Property)"`
- In HTML chapters, the dictionary is compiled directly into `window.WM = { ... }` ensuring 100% offline lookup without external API or JSON fetching.

### 3.3 The `#wordDialog` Modal & Speech Synthesis

File: `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` (lines 259–280, 419–474):

```html
<dialog id="wordDialog" class="lle-dialog">
  <div class="dlg-content">
    <div class="dlg-header">
      <span class="dlg-badge">AASHA LLE BILINGUAL BRIDGE</span>
      <button class="dlg-close-x" onclick="document.getElementById('wordDialog').close();document.getElementById('wordDialog').style.display='none'">✕</button>
    </div>
    <div class="dlg-word-row">
      <span class="dlg-word" id="dlgWord">Word</span>
      <button class="dlg-audio-btn" id="dlgAudioBtn" onclick="speakCurrentWord()" title="Listen to pronunciation">🔊 बोलें</button>
    </div>
    <div class="dlg-phonics-row">
      <span class="dlg-phonics-label">उच्चारण (Phonics):</span>
      <span class="dlg-phonics" id="dlgPhonics">—</span>
    </div>
    <div class="dlg-meaning-row">
      <span class="dlg-meaning-label">सरल अर्थ (Meaning):</span>
      <span class="dlg-hindi" id="dlgHindi">—</span>
    </div>
    <div class="dlg-desc" id="dlgDesc">Aasha Universal Teaching Vocabulary (आशा शिक्षण शब्दावली)</div>
    <button class="dlg-btn" onclick="document.getElementById('wordDialog').close();document.getElementById('wordDialog').style.display='none'">ठीक है (Got It)</button>
  </div>
</dialog>
```

Key features:
1. **Devanagari Phonics & Meaning Extraction**:
   Uses regex parsing `var mMatch = fullVal.match(/^(.*?)\s*\((.*?)\)$/);` to split the string into Meaning (`#dlgHindi`) and Phonics Badge (`#dlgPhonics`).
2. **Offline Web Speech API TTS**:
   ```javascript
   function speakCurrentWord() {
     var w = document.getElementById('dlgWord').textContent;
     if (!w || !('speechSynthesis' in window)) return;
     window.speechSynthesis.cancel();
     var u = new SpeechSynthesisUtterance(w);
     var voices = window.speechSynthesis.getVoices() || [];
     var v = voices.find(function(voice) { return voice.lang === 'en-IN'; }) ||
             voices.find(function(voice) { return voice.lang.startsWith('en'); }) ||
             voices[0];
     if (v) { u.voice = v; u.lang = v.lang; } else { u.lang = 'en-IN'; }
     u.rate = 0.85;
     window.speechSynthesis.speak(u);
   }
   ```
3. **Stemmer Fallback**:
   If an exact inflected word is missing, it dynamically stems suffixes (`-s`, `-es`, `-ed`, `-d`, `-ing`, `-ly`) to resolve the base root. If still missing, it guarantees a clean fallback `${word} (शब्द)` to prevent ever showing `"उपलब्ध नहीं"` or `"not available"`.

---

## 4. Chapter Generation, Bundling, and Compilation Pipelines

### 4.1 Pipeline Architecture Map

```
Textbook PDFs (Class 8 Math)
           │
           ▼
packages/chapter-contract-manager.ts (CLI: admin_memory_cli.ts init-chapter)
           │
           ▼
YAML Contracts (content/contracts/rational_numbers_contract.yaml)
           │
           ▼
Prebuilt Experience Registry (experience_registry/registry.json: F01–F20)
           │
           ▼
AASHAGatekeeper & QuestionSchemaValidator (Zero-Spoiler & Distractor Check)
           │
           ▼
Chapter Assembler (assemble_complete_46_ad.py / chapter-builder/base64-bundler.js)
           │
           ▼
Compiled Monolithic HTML (chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html)
           │
     ┌─────┴─────────────────────────────────────┐
     ▼                                           ▼
qa_ltruth_benchmark.js               automated_browser_verification.js
(Anti-Spoiler, Math-rt, 10 Rules)    (Chrome CDP, Viewports, Modal, Progression)
```

### 4.2 Core Tooling Components

1. **Section 24 Contract Manager (`chapter-contract-manager.ts`)**:
   - Generates and enforces Section 24 contract schema.
   - Maps curriculum intent, learning objectives, worked examples, and 4-tier progressive hints (`H1` Hook → `H2` Concept → `H3` Strategy → `H4` Checkpoint) before any HTML is written.
2. **Foundation Matcher (`admin_memory_cli.ts match-foundation`)**:
   - Queries `experience_registry/registry.json`.
   - For Rational Numbers, maps to Foundation **F04 PhET** (`fractions_intro`, `fraction_matcher`, `number_line_integers`, `density`) and **F08 Physics Notebook** (`canvas_visualization`, `real_time_formulas`).
3. **AASHA Gatekeeper (`packages/aasha-rules/aasha_gatekeeper.ts`)**:
   - Performs deterministic Phase 1 audit:
     - Section 16 & 13: Prohibited phrases & childish slang check (`PROHIBITED_PATTERNS`).
     - Section 15: Formal LaTeX notation delimiter balancing (`\(` vs `\)`, `\[` vs `\]`).
     - Section 11 & 12: Anti-spoiler distractor validation via `QuestionSchemaValidator`.
4. **Base64 Bundler (`packages/chapter-builder/base64-bundler.js`)**:
   - Loads HTML AST using `cheerio`.
   - Integrates `inline-source` to inline external scripts and stylesheets.
5. **Quality Certification Gate (Dual Benchmarks)**:
   - **`qa_ltruth_benchmark.js`**: Enforces 10 critical QA rules, zero spoiler giveaways in `m` fields, math-rt isolation, and Know-stage pedagogy.
   - **`automated_browser_verification.js`**: Launches headless Chrome via DevTools Protocol (CDP), sets device metrics across 5 mobile aspect ratios, tests vocabulary word-tap dialogs, verifies same-frame geometry (`scrollH <= winH + 5`), and exercises 5-step continuous progression.

---

## 5. Synthesis & Rebuild Blueprint for Class 8 Rational Numbers

### 5.1 Identified Gaps in Legacy vs. Target V5 Standard

1. **File Size vs. Self-Containment Strategy**:
   - The 6.78 MB Fractions benchmark achieves its weight because it inlined a 6.58 MB PhET simulation.
   - For Rational Numbers, we can either:
     - Option A: Inline a complete Foundation simulation (e.g. PhET Number Line Integers or Fraction Matcher Base64 payload), matching the 6+ MB footprint.
     - Option B: Deliver high-fidelity procedural Canvas 2D / JSXGraph simulations (as in `Polynomials_JSXGraph_Inlined_Enhanced_v6.html` ~1.02 MB) with zero external dependencies, staying well within the 20 MB ceiling while delivering sub-50ms render performance on budget devices.
2. **Textbook Exercise Coverage**:
   - The original request mandates 100% textbook coverage from the Class 8 textbook PDFs (AD Class 8th math rational number, MDS Class 8th rational number).
   - In `assemble_ad.py` and `ad_full_nodes_46.json`, all 46–48 textbook exercises across Exercise 1A (Addition, Subtraction, Multiplication, Division), Exercise 1B (Properties of Addition), Exercise 1C (Properties of Multiplication & Distributivity), and Prescribed Board Solved Questions are cataloged.
   - The standalone rebuild must map all 46+ questions across the 3 gamified challenge tiers:
     - Tier 1 Warm-up (Foundational representation, classification, single-step operations).
     - Tier 2 Deep Dive (Density, equivalence, multi-step fractions linked to manipulatives).
     - Tier 3 Boss Challenge (Complex algebraic property verification, multi-term regrouping, board word problems).
3. **Strict Compliance Checklist**:
   - [x] Zero CDN calls: All assets inlined.
   - [x] Golden Flow sequence: Natural inquiry prompts, causal *why* explanations.
   - [x] Same-frame mobile viewport: `.screen { min-height: 0; }`, height-tiered clamping (`80px/110px/125px` and `92px/115px/125px`), horizontal swipe preset bar (`pan-x`), touch targets $\ge 44\times 44$px.
   - [x] Math insulation: LaTeX and variables protected from Hindi word translation.
   - [x] 100% dictionary coverage: Word-tap modal with Devanagari phonics badge, Hindi meaning, and Web Speech API TTS.
   - [x] Dual-benchmark certification: 100/100 QA L-Truth score and CDP browser verification pass.

---
*Report compiled and verified against codebase ground truth.*
