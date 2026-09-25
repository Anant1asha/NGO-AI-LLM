# 12_CONTENT_STATE.md
# Educational & Content State Management

This document tracks all curriculum topics, chapters, learning objectives, and reusable content blocks across the ecosystem.

---

## 1. Chapter Inventory & Pipeline Verification State

| Chapter Name | Subject | Grade | Curriculum | Source File | Visual Manipulatives | LLE Status | Bundle Size | Validation Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fractions** | Mathematics | Grade 4 | NCERT | `Fractions_Gamified_v5_(2)_Enhanced_v6.html` | SVG Fraction Bar, Fraction Grid | Hindi Tap-to-Reveal + Phonics | 6.78 MB | `[!]` Exceeds size budget |
| **Perimeter & Area** | Mathematics | Grade 7 | NCERT | `Perimeter_Area_Gamified_v5_(2)_Enhanced_v6.html` | 2D Grid Area Model, Border tracer | Hindi Tap-to-Reveal + Phonics | 203 KB | `[✓]` VERIFIED PASS |
| **Algebraic Expressions** | Mathematics | Grade 8 | NCERT | `AlgebraicExpressions_Class8_Gamified_v5_Enhanced_v6.html` | Variable balance scale, Tile models | Hindi Tap-to-Reveal + Phonics | 180 KB | `[✓]` VERIFIED PASS |
| **Comparing Quantities (Percentage)** | Mathematics | Grade 8 | NCERT | `ComparingQuantities_Percentage_Class8_Gamified_v5_(1)_Enhanced_v6.html` | 100-Grid percentage visualizer | Hindi Tap-to-Reveal + Phonics | 214 KB | `[✓]` VERIFIED PASS |
| **Polynomials (Standard)** | Mathematics | Grade 10 | NCERT | `Polynomials_Class10_Gamified_v5_(1)_Enhanced_v6.html` | Quadratic curve explorer, Root finder | Hindi Tap-to-Reveal + Phonics | 219 KB | `[✓]` VERIFIED PASS |
| **Polynomials (JSXGraph)** | Mathematics | Grade 10 | NCERT | `Polynomials_JSXGraph_Inlined_Enhanced_v6.html` | Inlined JSXGraph coordinate plane | Hindi Tap-to-Reveal + Phonics | 1.07 MB | `[✓]` VERIFIED PASS |
| **Polynomials (Offline Demos)** | Mathematics | Grade 10 | NCERT | `Polynomials_Offline_Demos_Enhanced_v6.html` | Offline interactive mini-sims | Hindi Tap-to-Reveal + Phonics | 56 KB | `[✓]` VERIFIED PASS |

---

## 2. Canonical Reusable Vocabulary & Concept Blocks (LLE)

### A. Core Connecting Words (`CONN`)
- **Total Registered**: 46 canonical terms.
- **Visual Presentation**: Inline light blue text with tap-to-reveal Hindi meaning and phonetic guide.
- **Sample Verified Blocks**:
  - `is`: `है (इज़)`
  - `of`: `का/की/के (ऑफ़)`
  - `equal`: `बराबर (इक्वल)`
  - `greater than`: `से बड़ा (ग्रेटर दैन)`
  - `less than`: `से छोटा (लेस दैन)`
  - `divided by`: `विभाजित (डिवाइडेड बाई)`

### B. Word Map Dictionary (`WM`)
- **Total Registered**: 296+ canonical math and science vocabulary entries.
- **Sample Concept Blocks**:
  - `fraction`: `भिन्न (फ्रैक्शन)` — Definition: A part of a whole number.
  - `numerator`: `अंश (न्यूमरेटर)` — Definition: The top number in a fraction showing parts taken.
  - `denominator`: `हर (डिनॉमिनेटर)` — Definition: The bottom number showing total equal parts.
  - `perimeter`: `परिमाप (पेरीमीटर)` — Definition: The total boundary length of a 2D shape.
  - `area`: `क्षेत्रफल (एरिया)` — Definition: The total 2D surface enclosed within a boundary.

---

## 3. Pedagogical Node Structure Standards (TLN)

Every chapter must strictly partition its learning into 3 to 5 Topic Learning Nodes (TLNs). Each node sequences through:
1. **Intro Step**: Anchors the concept in everyday rural/urban Indian contexts (e.g., sharing chapatis, fencing a garden).
2. **Concept Text**: Clear, low-reading-level English paired with LLE tap-to-reveal tokens.
3. **Visual Interactive**: Guided touch manipulative allowing physical exploration of mathematical invariants.
4. **Worked Example (WE)**: Scaffolded step-by-step resolution with embedded micro-checks (`_weCheckRendered`).
5. **Formative Diagnostic Quiz**: 3 diagnostic questions with distractor-specific verbal misconception feedback.
6. **Progress Gate**: XP celebration and node completion badge.
