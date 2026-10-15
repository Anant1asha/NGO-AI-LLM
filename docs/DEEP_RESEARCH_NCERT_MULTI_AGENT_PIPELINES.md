# DEEP RESEARCH REPORT: ARCHITECTURES FOR MULTI-AGENT LLM SYNTHESIS OF OFFLINE GAMIFIED NCERT K-12 LEARNING MODULES

**Document Identifier:** `AASHA-RESEARCH-2026-01`  
**Classification:** Deep Research Synthesis & System Architecture Reference  
**Subject Focus:** Indian K-12 (NCERT/State Boards) Pedagogy, Offline HTML5 Delivery, and Multi-Agent LLM Pipeline Engineering  
**Authors:** Annanth AASHA Research & Architecture Group  
**Status:** Canonical Reference Specification  

---

## EXECUTIVE SUMMARY

This research report synthesizes the theoretical, curricular, and systems-engineering foundations required to automatically transform Indian K-12 textbook curricula (NCERT, CBSE, ICSE, and State Boards) into interactive, gamified, bilingual, and air-gapped offline HTML5 learning modules.

The central technical challenge is defined as the **"EdTech Iron Triangle"**:
1. **Curricular & Pedagogical Rigor:** 100% textbook problem coverage, strict alignment with NEP 2020 and NCF-SE 2023 Competency-Based Education (CBE) frameworks, zero-spoiler misconception diagnostics, and preservation of academic terminology.
2. **Air-Gapped Client Runtime Constraints:** Monolithic, single-file HTML5 bundles with zero external CDN dependencies, running smoothly on low-cost ($\ge 4\text{ GB}$ RAM) Android/Linux hardware under a strict $20\text{ MB}$ bundle ceiling and $44\text{px}$ touch-target minimums.
3. **Deterministic Multi-Agent Synthesis:** Orchestrating Large Language Models (LLMs) alongside deterministic compute workers without hallucination, token explosion, mathematical expression corruption, or cascade failures.

```
                  ===================================================
                  |                PEDAGOGICAL RIGOR                |
                  |  (NEP 2020, NCF-SE, 100% Coverage, 0-Spoiler)  |
                  ===================================================
                                         /\
                                        /  \
                                       /    \
                                      /      \
                                     /  AASHA \
                                    / ECOSYSTEM\
                                   /            \
                                  /              \
  ====================================        ====================================
  |       AIR-GAPPED CLIENT RUNTIME   | <----> |     DETERMINISTIC MULTI-AGENT    |
  |  (Offline-First, Zero-CDN, <20MB) |        |   (Schema Governance, AST Reuse) |
  ====================================        ====================================
```

---

## PART I: INDIAN K-12 (NCERT / STATE BOARDS) PEDAGOGY & OFFLINE ARCHITECTURE

### 1.1 Curricular Context: NEP 2020 and NCF-SE 2023 Alignment

The National Education Policy (NEP 2020) and the National Curriculum Framework for School Education (NCF-SE 2023) mandate a foundational shift in Indian primary and secondary schooling:
* **From Rote Memorization to Competency-Based Education (CBE):** Assessment must gauge conceptual reasoning, procedural fluency, and real-world application rather than factual recall.
* **Reduction in Curriculum Content Load:** Focusing on core concepts, high-order thinking skills (HOTS), and inquiry-based learning.
* **Multilingualism & Mother-Tongue Scaffolding:** Recognizing that conceptual comprehension flourishes when learners can access vernacular bridges (home language) without diluting standardized academic English vocabulary.

### 1.2 The 8-Stage Golden Discovery Order

To translate textbook prose into experiential discovery without trivializing academic rigor, learning units adhere to the **8-Stage Golden Teaching Flow**:

$$\text{WHAT} \longrightarrow \text{WHY} \longrightarrow \text{HOW} \longrightarrow \text{SHOW} \longrightarrow \text{TRY} \longrightarrow \text{FEEDBACK} \longrightarrow \text{CONNECT} \longrightarrow \text{NAME}$$

1. **WHAT (Phenomenon Hook):** Presents a real-world scenario, physical observation, or cognitive puzzle before formal rules are introduced.
2. **WHY (Real-World Motivation):** Grounding the concept in everyday contexts (farming, cooking, electricity, construction, sports).
3. **HOW (Interactive Manipulative):** Interactive sandboxes (`<aasha-sim>`) allowing parameter tweaking (e.g., sliders for radius, friction, or variables).
4. **SHOW (Visual Proof / Representation):** Multi-modal visualization (area models for algebra, ray tracing for optics, phase diagrams for chemistry).
5. **TRY (Scaffolded Practice):** Low-stakes, formative interactions guiding the learner through progressive complexity.
6. **FEEDBACK (Zero-Spoiler Misconception Diagnosis):** Immediate cognitive feedback explaining *why* a chosen distractor indicates a specific misunderstanding, without revealing the correct numerical or procedural answer.
7. **CONNECT (Bilingual Vernacular Bridge):** Contextual Indic translation (e.g., Hindi Devanagari definitions and phonetics) accessible via tap-to-reveal modals (`window.WM`).
8. **NAME (Academic Formalization):** Introducing standard NCERT/CBSE terminology, rigorous definitions, and KaTeX mathematical notation.

### 1.3 Zero-Spoiler Misconception Diagnostics (L-Truth Protocol)

In conventional multiple-choice tests, distractors are arbitrary plausible numbers. In high-efficacy pedagogical systems:
* Every distractor must map to a documented **cognitive bug** or procedural arithmetic error (e.g., adding exponents instead of multiplying, confusing perimeter with area, inversion errors in fraction division).
* **The Zero-Spoiler Invariant:** Remediation text presented upon selecting an incorrect option must explain the cognitive defect without revealing the correct answer or intermediate steps.

| Question Prompt | Distractor | Cognitive Bug (Diagnosis) | Spoiler Violation (Prohibited) | Permitted Zero-Spoiler Feedback |
|---|---|---|---|---|
| Simplify $\sqrt{16 + 9}$ | $7$ | Additive linearity fallacy: assuming $\sqrt{a+b} = \sqrt{a} + \sqrt{b}$ | "Wrong, $\sqrt{25} = 5$, not 7." | "Check whether square roots distribute across addition; evaluate the sum inside the radical first." |
| Calculate $-3 - (-5)$ | $-8$ | Sign multiplication error: treating $-(-5)$ as $-5$ | "Incorrect, minus of minus is plus so $-3 + 5 = 2$." | "Recall how subtracting a negative quantity alters the direction on a number line." |

### 1.4 Dual-Layer Language Architecture

To solve the tension between English-medium aspirations and vernacular comprehension:
* **Layer A (Student Interface):** Natural, conversational English accompanied by tap-to-reveal vernacular cards.
* **Layer B (Academic Invariant):** Formal terminology (e.g., *Photosynthesis*, *Centripetal Force*, *Refraction*, *Hypotenuse*) and mathematical notation are strictly preserved and never substituted with informal slang.

### 1.5 Air-Gapped Offline HTML5 Engineering Constraints

To operate across rural, semi-urban, and low-connectivity environments:
* **Zero External Network Calls:** Absolutely no external CDN script tags (`cdnjs`, `unpkg`, `fonts.googleapis.com`). All scripts, styles, and fonts must be bundled locally.
* **Smart Dual Inlining:**
  * Raw JavaScript is directly inlined in `<script>` tags.
  * Raw CSS is directly inlined in `<style>` tags (avoiding Base64's 33% text bloat).
  * Binary assets (SVG/PNG diagrams, audio clips, WOFF2 fonts) are encoded as Base64 Data URIs (`data:...;base64,...`).
* **Scope-Locked $20\text{ MB}$ Ceiling:** The entire standalone child-facing HTML5 bundle must remain strictly $\le 20,971,520\text{ bytes}$ (`CHILD_HTML5_BUNDLE_MAX_BYTES`).
* **Ergonomics for Low-Cost Hardware:** Minimum $44 \times 44\text{ px}$ interactive touch targets, GPU memory preservation via non-destructive `pause()` and `resume()` hooks (preventing canvas teardown), and $O(1)$ sub-$50\text{ms}$ telemetry logging.

---

## PART II: MULTI-AGENT LLM PIPELINE ARCHITECTURES FOR EDUCATIONAL SYNTHESIS

### 2.1 The Core Design Tenet: "More Specialization != More Agents"

A major pathology in early autonomous agent systems is **agent sprawl**—creating dozens of micro-agents communicating via unconstrained natural language. This leads to:
1. Compounding error rates ($E_{\text{total}} = 1 - \prod (1 - e_i)$).
2. Prohibitive token costs and API latency.
3. Non-deterministic divergence from source textbook ground truth.

The canonical architecture decouples **Deterministic Compute Workers** from **LLM Reasoning Roles**:

```
+-----------------------------------------------------------------------------------+
|                           CANONICAL PIPELINE TOPOLOGY                             |
+-----------------------------------------------------------------------------------+

[Textbook PDF]
      |
      v
+-----------------------------+
| AGT-001 Ingest Worker       | (Deterministic: PyMuPDF / fitz)
| - Page Slicing & SHA256     | Extracts raw text, layout AST, diagrams, exercises
+-----------------------------+
      |
      | raw_extract.json (ContextBus Handoff)
      v
+-----------------------------+
| AGT-002 Analysis Agent      | (LLM Reasoning: OpenRouter / Gemini Tier 1)
| - Concept DAG & Pedagogy    | Maps 3-5 foundational concept nodes, prerequisites
+-----------------------------+
      |
      | concept_map.json
      v
+-----------------------------+
| AGT-003 Design Agent        | (LLM Reasoning + Local Registry Lookup)
| - 8-Stage Golden Sequence   | Binds interactive foundations (F01-F20) to concept nodes
+-----------------------------+
      |
      | chapter_contract.json
      v
+-----------------------------+
| AGT-004 Assessment Agent    | (LLM Reasoning + Math Insulator)
| - 100% Exercise Mapping     | 3-Tier quiz, 0-spoiler distractor rationale (m-attr)
+-----------------------------+
      |
      | assessment_ir.json
      v
+-----------------------------+
| AGT-005 LLE / Indic Agent   | (LLM Reasoning with Token Insulation)
| - Bilingual Word Map        | Extracts Indic vocabulary map (window.WM); shields math
+-----------------------------+
      |
      | master_chapter.json
      v
+-----------------------------+
| V6 HTML5 Compiler Engine    | (Deterministic Node Compiler)
| - Smart Inlining            | Compiles standalone single-file bundle <= 20 MB
+-----------------------------+
      |
      | bundle.html
      +---------------------------------------+
      |                                       |
      v                                       v
+-----------------------------+   +-----------------------------+
| AGT-006 QA Auditor Agent    |   | AGT-007 Browser Tester      |
| (Deterministic AST Worker)  |   | (Deterministic Chrome CDP)  |
| - 10-Gate L-Truth Audit     |   | - Touch targets (>=44px)    |
| - 0-Spoiler regex checks    |   | - Viewport overflow checks  |
+-----------------------------+   +-----------------------------+
```

### 2.2 Inventory of Specialized Conceptual Roles & Workers

| Component | Identifier | Nature | Primary Responsibility | Input / Output Contract |
|---|---|---|---|---|
| **Ingest Worker** | `AGT-001` | Deterministic Worker (Python/PyMuPDF) | High-fidelity PDF text, vector, and image rasterization | `chapter.pdf` $\to$ `raw_extract.json` |
| **Analysis Agent** | `AGT-002` | LLM Reasoning Agent | Pedagogical dependency graph extraction & Bloom classification | `raw_extract.json` $\to$ `concept_dag.json` |
| **Design Agent** | `AGT-003` | LLM + Registry Broker | Interaction mapping & 8-stage pedagogical sequencing | `concept_dag.json` $\to$ `chapter_contract.json` |
| **Assessment Agent**| `AGT-004` | LLM Reasoning Agent | 3-tier quiz authoring, 100% textbook problem coverage | `raw_extract.json` $\to$ `assessment_ir.json` |
| **LLE Indic Agent** | `AGT-005` | LLM Reasoning Agent | Bilingual vocabulary extraction & mother-tongue bridge | `assessment_ir.json` $\to$ `bilingual_wm.json` |
| **QA Auditor** | `AGT-006` | Deterministic Worker (Node AST/Regex) | 10-Gate pedagogical, schema, and zero-spoiler audit | `bundle.html` $\to$ `qa_audit_report.json` |
| **Browser Tester** | `AGT-007` | Deterministic Worker (Chrome CDP) | Viewport rendering, DOM memory stability, touch targets | `bundle.html` $\to$ `cdp_telemetry.json` |

### 2.3 The Resource-First Reuse Hierarchy

A critical design flaw in generic AI code generators is prompting an LLM to generate interactive physics or math simulations from scratch in JavaScript/WebGL on every run. This produces fragile, unmaintainable, and CPU-intensive code.

AASHA enforces the normative **Resource-First Resolution Order**:

$$\text{EXACT\_REUSE} \longrightarrow \text{PARAMETRIC\_ADAPT} \longrightarrow \text{COMPOSE} \longrightarrow \text{LOCAL\_ADAPTATION} \longrightarrow \text{CERTIFIED\_GENERATION} \longrightarrow \text{SAFE\_FALLBACK}$$

* **EXACT_REUSE:** Fetching pre-verified, battle-tested interactive foundations from `experience_registry/registry.json` (e.g., PhET Interactive Simulations, JSXGraph geometry engines, interactive area slicers).
* **PARAMETRIC_ADAPT:** Adapting initial state variables (e.g., mass, spring constant, focal length) of an existing component via JSON configuration without touching implementation code.
* **COMPOSE:** Combining two or more pre-existing verified widgets into a dual-stage sandbox.
* **CERTIFIED_GENERATION:** Synthetic code generation is permitted only as a strict last resort, requiring isolated sandbox evaluation and CDP regression tests before acceptance.

### 2.4 Pre-LLE Mathematical Token Insulation Protocol

A notorious point of failure when LLMs translate or process technical educational content into Indic languages (Hindi, Marathi, Tamil, etc.) is the corruption of mathematical expressions:
* **The Problem:** Tokenizers split LaTeX macros (`\frac`, `\sqrt`) or algebraic variables ($x, y$) and erroneously translate them as dictionary terms or introduce illegal white space.
* **The Deterministic Solution:**
  1. **Phase 1 (Shielding):** Regex AST passes identify all LaTeX delimiters (`\( ... \)`, `$$ ... $$`, `$...$`) and algebraic spans, replacing them with immutable placeholder tokens:
     $$\text{"Simplify } \sqrt{x^2 + y^2}\text{"} \longrightarrow \text{"Simplify } \texttt{\_\_AASHA\_MATH\_0\_\_}\text{"}$$
  2. **Phase 2 (Translation / Vocabulary Mapping):** The natural language substrate is processed by the LLE Agent while math tokens remain opaque.
  3. **Phase 3 (Deshielding):** Placeholder tokens are reconstituted verbatim and rendered using KaTeX.

```
+--------------------+        +---------------------+        +--------------------+
| Raw Textbook Math  | -----> | Math Insulation Pass| -----> | LLE Bilingual Pass |
| \( \sqrt{x+y} \)   |        | __AASHA_MATH_0__    |        | (Hindi / Indic)    |
+--------------------+        +---------------------+        +--------------------+
                                                                        |
+--------------------+        +---------------------+                   |
| Verified HTML5 DOM | <----- | Post-LLE Unwrapping | <-----------------+
| Pure KaTeX Render  |        | Restore Formula     |
+--------------------+        +---------------------+
```

---

## PART III: COMPARATIVE SYSTEMS MATRIX

| Architectural Dimension | Traditional Commercial EdTech (e.g., BYJU'S, Unacademy) | Open-Source Platforms (e.g., Khan Academy, Diksha) | Unconstrained Monolithic LLM Generation | Governed Multi-Agent Pipeline (AASHA) |
|---|---|---|---|---|
| **Authoring Cost per Chapter** | High (\$5,000–\$15,000 per interactive chapter) | Moderate (\$1,500–\$3,000 manual authoring) | Low (\$0.50–\$2.00 API tokens) | Ultra-Low (\$0.05–\$0.30 via local models & Tier-1 OpenRouter) |
| **Delivery Model** | Cloud-native, streaming video, proprietary app | Cloud web app, high bandwidth requirement | Raw text/code snippets, no runtime container | Standalone monolithic HTML5, 100% offline air-gapped |
| **Bundle Size & Dependencies** | 100+ MB app + continuous video CDN streams | Multiple CDN bundles, external Google Fonts | Variable / Broken external script tags | Single file $\le 20\text{ MB}$, zero external CDN calls |
| **Textbook Coverage** | Curated cherry-picked exercises (20–40%) | Curated standard mastery challenges | Random loss of exercises during token overflow | **100% Exercise Retention** (Zero dropped questions) |
| **Misconception Diagnosis** | Static answer keys; video explanation | Hints and scratchpad; basic hints | Hallucinated hints that often leak answers | **Zero-Spoiler Diagnostic Regex & AST Enforcement** |
| **Bilingual Support** | Separate video dubbing per language | Translated UI strings; English-dominant STEM | Inconsistent translation; math corruption | **Pre-insulated Bilingual Tap-to-Reveal** (`window.WM`) |
| **Hardware Accessibility** | Modern smartphone / broadband | Browser on tablet/PC with internet | Desktop developer environment | **Budget Android ($\ge 4\text{ GB}$ RAM), 44px touch targets** |

---

## PART IV: IMPLEMENTATION SPECIFICATIONS & VERIFICATION PROTOCOLS

### 4.1 Strict Schema Enforcement (Zod / Pydantic)

All inter-agent handoffs must pass through schema validation gates. No downstream agent is invoked if upstream output fails structural validation.

```typescript
// Canonical Assessment Question Schema (TypeScript / Zod)
import { z } from 'zod';

export const AssessmentQuestionSchema = z.object({
  id: z.string().regex(/^Q_[A-Z0-9_]+$/),
  tier: z.enum(['warmup', 'deep_dive', 'boss']),
  source_exercise_ref: z.string(), // e.g., "Exercise 6.1, Question 4"
  prompt_latex: z.string(),
  visual_component_ref: z.string().optional(),
  options: z.array(z.object({
    id: z.string().length(1), // 'A', 'B', 'C', 'D'
    text_latex: z.string(),
    is_correct: z.boolean(),
    // Zero-Spoiler Misconception Diagnostic attribute:
    m: z.string().refine(val => {
      const forbiddenSpoilers = [/\bis\b/i, /\bgives\b/i, /\byields\b/i, /\bresult is\b/i, /\bbecomes\b/i, /\bequals\b/i];
      return !forbiddenSpoilers.some(rx => rx.test(val));
    }, { message: "Misconception text must diagnose thinking error without spoiling answer." })
  })).min(3).max(4),
  scaffolding_hints: z.tuple([
    z.string(), // H1: Hook / Attention directing
    z.string(), // H2: Governing Law / Concept
    z.string(), // H3: Strategy / Formula
    z.string()  // H4: Intermediate Operational Step
  ])
});
```

### 4.2 Automated 10-Gate L-Truth Static Benchmark

Before any compiled HTML5 bundle is cleared for distribution to learners, it must pass the automated 10-gate audit:
1. **Gate 1 (Zero CDN):** Regex scan ensuring zero occurrences of `http://`, `https://`, or `//` in `<script>` or `<link>` tags.
2. **Gate 2 (Bundle Ceiling):** File size validation verifying byte count $\le 20,971,520\text{ bytes}$ ($20\text{ MB}$).
3. **Gate 3 (Math Formula Integrity):** Zero unescaped or orphaned `__AASHA_MATH_X__` tokens in rendered output.
4. **Gate 4 (100% Exercise Accounting):** Extracted textbook exercise inventory matching compiled interactive cards.
5. **Gate 5 (Zero Spoiler Compliance):** Automated regex audit scanning all distractor `m` attributes against prohibited spoiler terms.
6. **Gate 6 (Bilingual Word Map):** Verification that `window.WM` dictionary contains Hindi definitions for all tagged technical terms.
7. **Gate 7 (Touch Target Ergonomics):** Headless Chrome CDP evaluation confirming all clickable elements occupy $\ge 44 \times 44\text{ CSS pixels}$.
8. **Gate 8 (DOM Memory Preservation):** Verification that card switching invokes `pause()` and `resume()` without destroying canvas contexts.
9. **Gate 9 (Sub-50ms Telemetry):** Benchmark confirming IndexedDB event writes complete without blocking the UI thread.
10. **Gate 10 (Offline Typography):** Verification that embedded KaTeX WOFF2 fonts render mathematical glyphs correctly without network dependencies.

---

## CONCLUSION & ARCHITECTURAL DIRECTIVES

1. **Pedagogical Alignment:** The 8-Stage Golden Teaching Flow (`WHAT -> WHY -> HOW -> SHOW -> TRY -> FEEDBACK -> CONNECT -> NAME`) provides a systematic formula for converting static Indian textbook PDFs into experiential learning modules that honor NEP 2020 / NCF-SE mandates.
2. **Deterministic-First AI Engineering:** High-reliability educational synthesis requires bounding LLMs to bounded reasoning tasks (Analysis, Sequence Design, Assessment Authoring) while assigning extraction, validation, browser testing, and packaging to deterministic workers.
3. **Strict Invariant Governance:** The $20\text{ MB}$ bundle ceiling, zero-CDN packaging, pre-insulated mathematical tokenization, and zero-spoiler diagnostic feedback serve as non-negotiable architectural boundaries ensuring equitable, high-impact education for every learner across India.

---
*Report compiled and certified for the Annanth AASHA Ecosystem.*
