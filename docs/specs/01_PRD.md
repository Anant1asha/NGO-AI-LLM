# AASHA AIOS — Product Requirements Document (PRD)
**Document Identifier:** `AASHA-SPEC-01-PRD`  
**Classification:** Canonical Product Requirement  
**Version:** 2.0.0 (Unified Ecosystem Release)  
**Lifecycle Status:** APPROVED / LEVEL 1 SPECIFICATION  
**Target Hardware / Context:** Offline-First Rural & Urban Learners, Class K-12, All Boards (CBSE, ICSE, NCERT, State Boards)

---

## 1. Executive Summary & Vision

AASHA (Annanth AASHA Learning & Impact Foundation) is a next-generation, AI-orchestrated, offline-first educational operating system. Its primary mission is delivering **Khan Academy+ caliber visual and interactive learning experiences** to every student, everywhere—without requiring active internet connectivity, high-end devices, or continuous cloud API expenditures.

AASHA transforms standardized textbook curriculum (NCERT/CBSE/ICSE) into highly visual, bilingual, and gamified interactive HTML5 modules. Each module is self-contained within an expanded **40 MB single-file bundle ceiling** (`41,943,040 bytes`), providing embedded KaTeX mathematical typography, bilingual Indic (Hindi-focused) contextual vocabulary definitions, interactive phenomenon-first simulations, and 3-tier gamified formative assessments.

---

## 2. Core Pedagogical Philosophy: The 8-Stage Golden Flow

Every learning unit generated within AASHA adheres strictly to the **8-Stage Golden Discovery Order**:
1. **WHAT (Phenomenon Hook):** Introduces a tangible physical phenomenon or observable paradox before any formal definitions.
2. **WHY (Real-World Motivation):** Connects the concept to the student's lived environment (farming, cooking, electricity, household budgeting).
3. **HOW (Interactive Manipulative):** Empowers the student to manipulate parameters directly via `<aasha-sim>` Web Component simulations.
4. **SHOW (Visual Proof):** Demonstrates underlying mechanics graphically (e.g., dynamic fraction area slicing, vector field trajectories).
5. **TRY (3-Tier Scaffolding):** Guides the student through low-stakes foundational practice before advancing.
6. **FEEDBACK (0-Spoiler Diagnostic Misconceptions):** Diagnoses specific conceptual errors instantly without ever revealing numerical or procedural answers.
7. **CONNECT (Bilingual Substrate):** Bridges intuitive mother-tongue understanding (Hindi) to formal terminology via tap-to-reveal modals (`window.WM`).
8. **NAME (Academic Standardization):** Formalizes the concept with rigorous academic KaTeX mathematical notation and CBSE/NCERT curriculum terminology.

---

## 3. Product Scope & Universal Curriculum Coverage

AASHA is designed for universal curriculum portability:
* **Academic Boards:** NCERT, CBSE, ICSE, and Indian State Boards.
* **Grade Bands:** Class 1 through Class 12.
* **Target Subject Domains:**
  * **Mathematics:** Number systems, algebra, geometry, coordinate geometry, calculus, statistics, financial arithmetic.
  * **Science (Physics, Chemistry, Biology):** Mechanics, thermodynamics, electromagnetism, chemical reactions, cell biology, environmental science.
  * **Social Studies:** Geography (cartography & topographical reasoning), Civics, History.
  * **Computer Science & Digital Literacy:** Algorithmic logic, block coding, cybersecurity awareness.
  * **Financial Literacy:** Household budgeting, rupee currency arithmetic, UPI security, savings vs. investment scenarios.

---

## 4. Key Functional Features & Non-Negotiable Invariants

### 4.1. 100% Textbook Exercise Utilization
* **Zero Dropped Exercises:** 100% of textbook exercises from the source chapter PDF must be extracted and mapped into the assessment system.
* **3-Tier Gamified Progression:**
  * **Tier 1: Warm-up (`#section-warmup`):** Rapid foundational mechanics & single-step MCQs.
  * **Tier 2: Deep Dive (`#section-deep_dive`):** Multi-step interactive problems linked directly to visual simulation manipulatives.
  * **Tier 3: Boss Challenge (`#section-boss`):** Complex textbook problems and synthesis challenges.

### 4.2. Zero-Spoiler Misconception Diagnostics (L-Truth Protocol)
* Every assessment distractor includes a pre-embedded diagnostic explanation (`m` attribute) targeting the procedural or conceptual root of the mistake.
* **Strict 0-Spoiler Rule:** Explanations must diagnose the thinking error without leaking the correct answer, numerical values, or intermediate arithmetic steps (e.g., phrases like `"is"`, `"gives"`, `"yields"`, `"result is"`, `"becomes"` are strictly prohibited).

### 4.3. 4-Tier Progressive Scaffolding Hints
Every exercise provides a progressive 4-step hint cascade on demand:
* **$H_1$ Hook:** Directs learner attention to relevant diagrams or givens.
* **$H_2$ Concept:** Identifies the governing physical law or mathematical rule.
* **$H_3$ Strategy:** Outlines the procedural plan or formula to apply.
* **$H_4$ Intermediate Step:** Solves the first operational step, leaving final computation to the student.

### 4.4. Hindi-Focused Bilingual Substrate (`window.WM`)
* **Mother-Tongue Tap-to-Reveal:** Any academic or technical English term is tappable, rendering a lightweight modal containing:
  * Devanagari Hindi translation.
  * Contextual real-world definition in simple spoken Hindi.
  * Audio phonetics guide (phonetic transcription).
* **Pre-LLE Mathematical Insulation:** All LaTeX formulas (`\( ... \)`, `$$ ... $$`) and single-letter algebraic variables are shielded via `__AASHA_MATH_X__` placeholders to eliminate dictionary tokenization collisions.

### 4.5. Harvested Visual Experience Foundation Reuse
* **Never Build From Scratch:** Standardized reuse of the 20+ prebuilt open-source foundations (F01–F20) cataloged in `experience_registry/registry.json`.
* **Harvested Visual Assets Integration:** Full integration of pre-harvested HTML5 assets from `AASHA_Visual_Mass_Harvest_Phase3/` (logic gates, springs, population growth, projectiles, bar charts) and `external_sources/CinePhysicsHQ-Labs/` (Vernier caliper, dimensional analysis, Lorentz force) wrapped in standard `<aasha-sim>` Web Component adapters.

---

## 5. Non-Functional Constraints & Hardware Budgets

| Dimension | Specification Budget | Verification Method |
|---|---|---|
| **Single-File Bundle Ceiling** | **Max 40 MB (`41,943,040 bytes`)** | Automated file size check in build pipeline & `VersionManager` |
| **Asset Inlining Architecture** | Raw inline `<script>` & `<style>`, Base64 strictly for binary assets | AST inspection |
| **Offline Portability** | Zero external CDNs, zero web fonts, zero remote scripts | CDP network request interceptor ($0$ remote URLs) |
| **Telemetry & Mastery Latency** | Sub-50ms execution ($O(1)$ sliding window over $K=100$) | In-situ performance telemetry |
| **Mobile Viewport Clearance** | Same-frame zero-scroll (`scrollH <= winH + 5`) on 16:9, 19.5:9, 20:9 | Headless Chrome CDP multi-viewport suite |
| **Minimum Touch Target** | $\ge 44 \times 44\text{ px}$ across all interactive controls | DOM client bounding rect inspection |

---

## 6. Success Metrics & Certification Criteria

1. **Pedagogical Rigor:** 100/100 score on `benchmarks/qa_ltruth_benchmark.js` (0 spoilers, 0 math collisions, 100% Hindi dictionary coverage).
2. **Runtime Stability:** 0 unhandled console errors across 5-step CDP user interaction runs across all supported mobile viewports.
3. **Child Safety & Privacy:** 100% air-gapped student execution. Zero external data transmission during learning sessions; telemetry persists asynchronously to local IndexedDB.
