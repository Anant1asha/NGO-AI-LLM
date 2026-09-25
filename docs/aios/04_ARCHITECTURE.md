# 04_ARCHITECTURE.md
# Master System Architecture & Component Map

## 1. Product Purpose & System Boundaries
The Annanth Aasha Learning Impact Ecosystem delivers curriculum-aligned, high-engagement, offline-first digital learning experiences to underprivileged students in Indian government schools (Grades 3–10).
- **In-Scope Boundary**: Offline student chapter runtime (v5/v6 single-file HTML), multi-agent textbook compilation pipeline, two-tier diagnostic assessment engine, aggregate outbox sync, operator review UI.
- **Out-of-Scope Boundary (Explicitly Deferred)**: Cloud student accounts, social cohorts, high-frequency continuous tracking, real-money/coin marketplaces, cloud CMS.

---

## 2. Structural Layer Overview

```
+-----------------------------------------------------------------------------------+
| LAYER 3: PRODUCT EXPERIENCES & RUNTIMES                                           |
| - Standalone HTML Chapters (v5/v6 Engine, 480px, Offline, Touch-first)           |
| - Learner Web / PWA (ServiceWorker caching, IndexedDB outbox)                     |
| - Operator Dashboard (React + Vite + Tailwind)                                    |
+-----------------------------------------------------------------------------------+
| LAYER 2: EDUCATION ENGINES & PEDAGOGICAL SERVICES                                 |
| - TEAS Engine (Two-tier diagnostic tracking, 60% historical + 40% recent)         |
| - Question & Misconception Engine (Zero-spoiler distractor diagnosis)            |
| - Visual Manipulative System (SVG fraction bars, 2D grids, JSXGraph plots)        |
| - Bilingual Language Learning Engine (LLE: English → Hindi phonetics & meanings)  |
+-----------------------------------------------------------------------------------+
| LAYER 1: MULTI-AGENT COMPILATION PIPELINE                                         |
| - IngestAgent (PyMuPDF) -> AnalysisAgent (Concept nodes) -> DesignAgent (Flow)    |
| - AssessmentAgent (Quizzes) -> LLEAgent (Bilingual) -> QAAgent (200+ checks)      |
| - HTML Template Compiler & Asset Inliner (Base64 data URIs)                       |
+-----------------------------------------------------------------------------------+
| LAYER 0: DATA, TELEMETRY & GOVERNANCE                                             |
| - LocalStorage / IndexedDB state management                                       |
| - Idempotent Reward Ledger & Deterministic Event UUIDs                            |
| - Aggregate Impact Sync Service (Fastify backend, zero PII)                       |
| - AIOS Master Governance Plane (/docs/aios/)                                      |
+-----------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Map

### Component 1: v5/v6 Standalone Chapter Runtime
- **STATE**: IMPLEMENTED & VERIFIED
- **PURPOSE**: Provide complete offline, zero-dependency learning chapter execution within an isolated 480px viewport on budget mobile devices.
- **INPUT**: Chapter Spec JSON (`NODES`, `WE`, `WM`, `CONN`) injected at build time.
- **OUTPUT**: Rendered interactive DOM, interactive manipulatives, step progression, audio phonics, XP awards.
- **OWNER**: Frontend / Runtime Architect
- **DEPENDENCIES**: Native Browser JavaScript / DOM / Canvas / SVG. Zero external libraries at runtime.
- **FAILURE MODES**: Corrupt localStorage data; handled via automatic boundary validation and default state restoration.
- **SECURITY**: No network requests; `eval()` prohibited; all scripts static.

### Component 2: Automated Multi-Agent Pipeline
- **STATE**: IMPLEMENTED (CLI & Scripts) / EXPERIMENTAL (Full Autonomous Loop)
- **PURPOSE**: Ingest textbook PDFs and automatically produce compliant v5/v6 chapter JSON specs and assembled HTML.
- **INPUT**: PDF files (NCERT textbooks), metadata (grade, subject).
- **OUTPUT**: `chapter_spec.json`, `<chapter_name>_Gamified_v5.html`.
- **OWNER**: AI / Agent Architect
- **DEPENDENCIES**: Python (PyMuPDF, Pydantic, jsonschema, Tenacity), OpenRouter API / Claude Code / Freebuff CLI.
- **FAILURE MODES**: PDF reading order misinterpretation, LLM hallucination in mathematical calculations, schema mismatch.
- **REPLACEMENT STRATEGY**: Fallback to human editor modifying intermediate JSON spec prior to compiler assembly.

### Component 3: TEAS Assessment Engine
- **STATE**: IMPLEMENTED & VERIFIED
- **PURPOSE**: Decouple diagnostic conceptual understanding from gamified retries. Calculates composite mastery (60% historical + 40% recent).
- **INPUT**: Learner response actions, question distractors, attempt sequence.
- **OUTPUT**: Diagnostic event record (Attempt 1), practice reward event (Attempt 2+), next node unlock status.
- **OWNER**: Assessment Architect
- **DEPENDENCIES**: In-engine logic (`packages/assessment-engine/`).
- **SECURITY**: Local ledger validation prevents artificial coin/XP replay inflation.

### Component 4: Visual Manipulative Engine
- **STATE**: PARTIAL (SVGs & JSXGraph Implemented; others in registry)
- **PURPOSE**: Embed interactive math and science visual models (fraction bars, 2D grids, function plots) to provide concrete conceptual anchors.
- **INPUT**: Visual parameters, target equations/fractions, student touch/click inputs.
- **OUTPUT**: Visual state transformations, reactive readouts, success/completion triggers.
- **OWNER**: Multimodal AI & Learning Experience Designer
- **DEPENDENCIES**: Inlined lightweight SVG handlers, JSXGraph (~200KB).
- **FAILURE MODES**: Excessive asset size causing memory crashes on low-end phones.

### Component 5: Language Learning Engine (LLE)
- **STATE**: IMPLEMENTED & VERIFIED
- **PURPOSE**: Enable bilingual comprehension by embedding Hindi transliteration (Devanagari phonetics) and contextual translations for English terms.
- **INPUT**: Chapter vocabulary list.
- **OUTPUT**: `CONN` (inline connecting word dictionary) and `WM` (tap-to-reveal word map).
- **OWNER**: Learning Experience Designer
- **DEPENDENCIES**: Base dictionaries (46 CONN, 296+ WM entries) + chapter-specific LLM generator.
- **FAILURE MODES**: Translation altering mathematical variables; mitigated by strict math-character exclusion rules.

### Component 6: Fastify Server & Telemetry Sync
- **STATE**: IMPLEMENTED
- **PURPOSE**: Receive batch aggregate event sync payloads from devices when internet is briefly available.
- **INPUT**: Signed aggregate event arrays.
- **OUTPUT**: HTTP 200 OK + Sync confirmation hashes.
- **OWNER**: Backend Engineer
- **DEPENDENCIES**: Fastify, Node.js.
- **SECURITY**: Zero PII payload schema; strictly rejects any request containing names, phone numbers, or device tracking IDs.

---

## 4. Technical Debt & Immediate Priorities
1. **Chapter File Size Optimization**: Several generated chapters in `chapters/` contain large base64 raster blobs (Fractions chapter is 6.78MB). Must be optimized to lightweight vector SVGs to stay under 200KB–500KB.
2. **Third-Party License Segregation**: GeoGebra non-commercial license and PhET GPL v3 must be strictly separated or replaced with MIT alternatives (Mafs, JSXGraph) before commercial/open redistribution.
