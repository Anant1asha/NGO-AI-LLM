# CANONICAL GLOSSARY & ARCHITECTURAL ACRONYMS
*AASHA Learning & Impact Ecosystem — Verified Ground Truth*
*Generated: 2026-09-16 | Authority: SUPER ADMIN Governance*

---

## 1. TEAS — Trust / Evidence / Assessment / Scoring

### Canonical Definition
**TEAS** stands for **Trust / Evidence / Assessment / Scoring**.
It is the two-tier diagnostic mastery and assessment authority of the AASHA Learning Ecosystem.

### Operational Semantics
- **Two-Tier Attempt Decoupling**: Decouples diagnostic conceptual understanding (Attempt 1) from gamified practice retries (Attempt 2+).
- **Mastery Mathematical Formula**:
  $$M = 0.6 \cdot H + 0.4 \cdot R$$
  where $H$ is historical performance and $R$ is recent performance across a bounded sliding window ($K = 100$).
- **Authority Invariant**: The Reward Engine only issues coins/XP based on TEAS-verified events, preventing replay score inflation.

### Evidence Sources
1. `docs/aios/04_ARCHITECTURE.md` (Line 26 & 63): Defines Component 3 as "TEAS Assessment Engine" (Trust / Evidence / Assessment / Scoring).
2. `Aasha-AI/archive/aasha-v5-reference-repo/docs/ARCHITECTURE.md` (Line 26): "TEAS — Trust / Evidence / Assessment / Scoring (mastery authority)".
3. `Aasha-AI/packages/v6-engine/v6_runtime_bus.ts` (Lines 85–118): Implements the exact 60/40 weighted composite scoring formula in TypeScript.
4. *Deprecated / Informal Variant*: "Tracked Evidence-based Assessment System" (`Aasha-AI/README.md`) is hereby marked **DEPRECATED** in favor of the canonical mnemonic "Trust / Evidence / Assessment / Scoring".

---

## 2. LLE — Language Layer Engine

### Canonical Definition
**LLE** stands for **Language Layer Engine**.
It is the portable bilingual rendering and phonetic scaffolding layer designed for Indic languages (with Hindi as primary active substrate).

### Operational Semantics
- **Word Map (`WM`) & Connectives (`CONN`)**: Maps English vocabulary to Indic script format: `सरल अर्थ (रोमनाइज्ड / देवनागरी उच्चारण)`.
- **Math Insulation Invariant**: All mathematical expressions (`\(...\)`, `$$...$$`, algebraic single letters $x, y, a, b$) are insulated with `__AASHA_MATH_X__` placeholders and `<span class="math-var" data-math="true">` before dictionary wrapping.
- **Client-Side Runtime**: Evaluates via `rt('word')` and `#wordDialog` modal with zero external network dependencies.

### Evidence Sources
1. `Aasha-AI/LLE layer/lle_engine.py` (Line 2 & 34): `LLE — Language Layer Engine (Python backend) ... class LLE: Language Layer Engine — bilingual English↔Hindi text renderer`.
2. `ORIGINAL_REQUEST.md` (Line 20): "R3. LLE (Language Layer Engine) Bilingual Substrate".
3. `docs/aios/04_ARCHITECTURE.md` (Line 81): "Component 5: Language Learning Engine (LLE)".
4. *Deprecated / Informal Variant*: "Language Learning Element" (`GRAPH_REPORT.md`) is hereby marked **DEPRECATED** as an informal descriptive term.

---

## 3. TLN — The Learning Node Engine

### Canonical Definition
**TLN** stands for **The Learning Node** (or **The Learning Node Engine**).
It represents individual atomic concept nodes (e.g., `node_1`, `node_2`) in the pedagogical curriculum graph.

### Operational Semantics
- Each chapter is structured into 3–5 TLN concept blocks to respect cognitive load bounds.
- Each TLN follows the progression: Intro $\to$ Concept Definition $\to$ Interactive Manipulative $\to$ Worked Example $\to$ TEAS Practice Checkpoint.

### Evidence Sources
1. `graphify-out/GRAPH_REPORT.md` (Community 1069): "Pedagogical Node Structure Standards (TLN)".
2. `docs/aios/04_ARCHITECTURE.md` & `Aasha-AI/aasha-pipeline-with-master-json/test_output/chapter.html`.

---

## 4. DDA — Dynamic Difficulty Adjustment

### Canonical Definition
**DDA** stands for **Dynamic Difficulty Adjustment**.
It provides sub-50ms latency runtime adaptation, modulating hint depth (H1–H4) and manipulative guidance based on learner error patterns without changing the underlying curriculum standard.

### Evidence Sources
1. `GEMINI.md`: "Bounded Sliding-Window Complexity Invariant (Sub-50ms Latency)... Dynamic Difficulty Adjustment (DDA)".
2. `Aasha-AI/Aasha_MVP_6_Documents.md`.
