# 03_FLOW.md
# End-to-End System Execution Flows

## 1. Master System Flow Architecture

```
INPUT (PDF Textbook / Syllabus JSON)
  ↓
OPERATOR UI / CLI (Upload / Metadata Selection)
  ↓
APPLICATION LOGIC (Fastify / Flask Orchestration)
  ↓
AGENT PIPELINE (Ingest → Analysis → Design → Assessment → LLE → QA)
  ↓
SERVICE / ENGINE (HTML Compiler / Template Injector)
  ↓
DATA LAYER (Chapter Spec JSON / Word Maps / Offline Event Ledger)
  ↓
OUTPUT (Standalone v5/v6 Offline HTML Chapter)
  ↓
STUDENT RUNTIME & ASSESSMENT (Learner Web / PWA / Webview)
  ↓
TELEMETRY / IMPACT (Local Outbox → Aggregate Sync Service)
```

---

## 2. Core Execution Flow 1: Automated Chapter Generation Pipeline

- **FLOW ID**: FLOW-001
- **ENTRY POINT**: Operator selects single chapter PDF via Web UI or executes CLI command `python build_chapter.py --pdf <file> --grade <g> --subject <s>`.
- **TRIGGER**: File submission / CLI run trigger.
- **FILES INVOLVED**:
  - `aasha-pipeline-with-master-json/src/ingest.py`
  - `aasha-pipeline-with-master-json/src/analysis.py`
  - `aasha-pipeline-with-master-json/src/design.py`
  - `aasha-pipeline-with-master-json/src/assessment.py`
  - `aasha-pipeline-with-master-json/src/lle.py`
  - `aasha-pipeline-with-master-json/src/compiler.py`
  - `aasha-pipeline-with-master-json/template/v5-engine-template.html`
- **MODULES & AGENTS**:
  1. `IngestAgent`: PyMuPDF reads PDF, cleans OCR errors, extracts raw text & figures.
  2. `AnalysisAgent`: Identifies 3–5 Topic Learning Nodes (TLNs) and core concepts.
  3. `DesignAgent`: Sequences steps: Intro → Text → Visual → Worked Example → Quiz → Progress.
  4. `AssessmentAgent`: Generates questions with distractors and zero-spoiler misconception explanations (`m`).
  5. `LLEAgent`: Generates bilingual Hindi phonetic & meaning glossaries (`CONN` and `WM`).
  6. `QAAgent`: Runs syntax check and L-Truth 200+ rule verification harness.
- **DATA & STATE**:
  - Raw extract JSON → Content map JSON → Chapter Spec JSON (`NODES`, `WE`, `WM`, `CONN`).
- **DEPENDENCIES**: PyMuPDF, Pydantic, jsonschema, Tenacity, OpenRouter / Claude / LLM APIs.
- **ERROR PATH & FALLBACK**:
  - If LLM call fails: Tenacity retries 3x with exponential backoff.
  - If LLE word generation fails: Falls back to default string `"इस शब्द का हिंदी अर्थ अभी उपलब्ध नहीं है"`.
  - If structural schema validation fails: Pipeline halts, preserves intermediate JSON spec, logs failing rule, and alerts human operator.
- **OUTPUT**: Single-file standalone HTML chapter (`<ChapterName>_Gamified_v5.html`).
- **VERIFICATION**: `QAAgent` executes `node qa/qa_ltruth_benchmark.js` against generated HTML.

---

## 3. Core Execution Flow 2: Student Learning & Two-Tier Assessment Cycle

- **FLOW ID**: FLOW-002
- **ENTRY POINT**: Learner opens standalone HTML file in Android WebView, Chrome, or Learner PWA.
- **TRIGGER**: User tap on "Start" / Step navigation.
- **FILES INVOLVED**:
  - Generated chapter file (e.g. `chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html`)
  - `Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/apps/learner-web/`
  - `Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/packages/assessment-engine/`
- **EXECUTION SEQUENCE**:
  1. **Topic Introduction**: Displays real-world context and visual hook.
  2. **Conceptual Interaction**: Student interacts with visual manipulative (SVG fraction bar, 2D area grid, JSXGraph coordinate plane).
  3. **Worked Example (WE)**: Guided step-by-step problem resolution with embedded micro-checks (`_weCheckRendered`).
  4. **Formative Diagnostic Assessment**:
     - Question displayed with shuffled options.
     - Student selects option.
     - *If Correct on Attempt 1*: +10 XP, diagnostic ledger records `FIRST_ATTEMPT_SUCCESS`, progression unlocked.
     - *If Wrong on Attempt 1*: Diagnostic ledger records `FIRST_ATTEMPT_MISCONCEPTION(id)`. Verbal misconception explanation appears (`m` field). Options are not revealed. Retry enabled.
     - *On Retry Success*: +5 practice XP recorded in progression ledger; diagnostic baseline remains intact.
  5. **Node Progress & Milestone**: Node completion badge and confetti animation.
- **DATA & STATE**: Local state persisted in `localStorage['aasha_state_<chapterId>']`.
- **ERROR PATH & FALLBACK**: Corrupt `localStorage` automatically caught and reset to safe defaults without alert/crash dialogs (PRD Rule 8 & 9).
- **VERIFICATION**: Node unit tests `ISS-01: Two-tier attempt tracking` and `P0-C: Fractions chapter contains 3 diagnostic questions per concept node`.

---

## 4. Core Execution Flow 3: Offline Event Outbox & Telemetry Synchronization

- **FLOW ID**: FLOW-003
- **ENTRY POINT**: Learner activity event generated during chapter completion.
- **TRIGGER**: Event dispatcher triggered on question completion, node mastery, or reward earning.
- **FILES INVOLVED**:
  - `Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/packages/event-outbox/`
  - `Aasha-AI/server/server.js`
- **EXECUTION SEQUENCE**:
  1. Event created with deterministic UUIDv5/hash `event_id` preventing duplicate rewards.
  2. Stripped of all personal identifiers (contains only `anonymous_learner_hash`, `chapter_id`, `node_id`, `misconception_code`, `score_tier_1`, `score_tier_2`).
  3. Stored in IndexedDB/localStorage Outbox queue.
  4. Background sync worker checks `navigator.onLine`.
  5. When connection is detected, batches outbox events and pushes to Fastify `/api/v1/telemetry/sync` endpoint.
  6. Server acknowledges reception; outbox marks events as `SYNCED` and purges acknowledged records.
- **ERROR PATH & FALLBACK**: Retained in offline queue indefinitely until network is restored. No data is dropped.
- **VERIFICATION**: Node test `offline event outbox survives and syncs` (passes in 10.6ms).
