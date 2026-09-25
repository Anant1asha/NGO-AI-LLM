# 08_FEATURE.md
# Feature Catalog & Specification Records

---

### FEATURE: FEAT-001 Standalone Offline Gamified Chapter Generation
- **FEATURE ID**: FEAT-001
- **OBJECTIVE**: Automatically transform a standard NCERT textbook PDF chapter into a single, self-contained, offline gamified HTML chapter file.
- **USER PROBLEM**: Rural Indian school students lack stable internet and cannot access dynamic web apps or stream video lectures.
- **TARGET USER**: Grade 3–10 students in government schools; teachers using DIKSHA offline.
- **SCOPE**:
  - PDF ingestion and text/image extraction.
  - Identification of 3–5 Topic Learning Nodes (TLNs).
  - Sequencing into intro, interactive manipulative, worked example, and diagnostic quiz steps.
  - Embedding bilingual Hindi phonetics & meanings (LLE).
  - Inlining all styles, scripts, and assets into a single HTML file.
- **NON-SCOPE**:
  - Student login / authentication.
  - Multi-user cohorts / classroom management.
  - Real-money marketplace or cloud progress sync.
- **REQUIREMENTS**:
  - Output must pass all 10 Critical Engineering Rules.
  - Output file size target <200 KB (max 1 MB).
  - Touch-optimized for 480px width mobile screens.
- **UX & LEARNING BEHAVIOR**:
  - Tap-to-select interaction (no drag-and-drop).
  - Instant verbal feedback on distractors explaining the misconception.
  - Shuffled options on every load.
  - Skip button on every simulation.
- **DATA**: Local state maintained in `localStorage`.
- **AGENT BEHAVIOR**:
  - `IngestAgent`: Extracts structured text & images from PDF without hallucination.
  - `AnalysisAgent`: Generates concept nodes and links.
  - `DesignAgent`: Configures interactive visual steps.
  - `AssessmentAgent`: Generates questions with zero-spoiler misconception explanations.
  - `LLEAgent`: Builds English-to-Hindi phonetic glossaries.
  - `QAAgent`: Verifies syntax and L-Truth criteria.
- **FILES**:
  - `aasha-pipeline-with-master-json/src/*.py`
  - `aasha-pipeline-with-master-json/template/v5-engine-template.html`
  - `chapters/*.html`
- **DEPENDENCIES**: PyMuPDF, Pydantic, jsonschema, Tenacity.
- **RISKS**: LLM hallucination of math solutions; base64 image bloat causing memory exhaustion.
- **IMPLEMENTATION**: Pipeline modules built in Python and Node.js.
- **VERIFICATION**: Tested against Fractions and Perimeter & Area chapters.
- **EVIDENCE**: 7 generated chapters in `Aasha-AI/chapters/`; 16/16 ecosystem tests passing.
- **LIMITATIONS**: Image quality constrained by base64 encoding budget.
- **STATUS**: VERIFIED
- **NEXT STEP**: Enforce vector SVG asset migration to reduce Fractions chapter bundle from 6.7MB to <500KB.

---

### FEATURE: FEAT-002 Two-Tier Diagnostic TEAS Assessment Engine
- **FEATURE ID**: FEAT-002
- **OBJECTIVE**: Decouple diagnostic conceptual scoring from formative practice retries to provide truthful learning analytics while maintaining gamified engagement.
- **USER PROBLEM**: In standard educational games, students guess through multiple-choice questions until they hit the right answer, corrupting learning analytics with artificial 100% scores.
- **TARGET USER**: Learners practicing concepts; pedagogical analysts evaluating true mastery.
- **SCOPE**:
  - Intercept and record first attempt in diagnostic ledger.
  - Permit unlimited subsequent attempts in formative practice ledger.
  - Compute composite mastery using 60% historical + 40% recent accuracy.
  - Trigger distractor-specific verbal misconception feedback on incorrect choices.
- **NON-SCOPE**: Remote proctoring or high-stakes timed testing.
- **REQUIREMENTS**:
  - Idempotent reward calculation (replaying a question must not grant duplicate XP/coins).
  - Misconceptions must never leak the correct answer.
- **UX**: Visual badge on first-try perfection; encouragement and retry prompt on misconception.
- **FILES**:
  - `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/packages/assessment-engine/`
  - `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/tests/unit/learner.test.js`
- **STATUS**: VERIFIED
- **EVIDENCE**: Test suite verification in `tests/unit/learner.test.js` (Tests 4, 10, 11, 14, 15, 16 passing).
- **NEXT STEP**: Extend misconception taxonomies to secondary science and biology curricula.
