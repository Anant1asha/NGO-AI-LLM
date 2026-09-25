# 16_AGENT_CONTRACT.md
# Multi-Agent Operational Contracts & Governance Bounds

Every agent operating within the Aasha AIOS runs under strict least-privilege boundaries and bounded decision rights.

---

### AGENT CONTRACT: AGT-001 IngestAgent
- **AGENT ID**: AGT-001
- **ROLE**: Deterministic Document Ingestion Specialist
- **PURPOSE**: Extract clean, structured text, section headings, and embedded diagrams from raw textbook PDF chapters.
- **INPUT**: Binary `.pdf` file.
- **OUTPUT**: `raw_extract.json` containing ordered page elements, text blocks, and image data.
- **TOOLS**: PyMuPDF (`fitz`), Pillow (PIL image optimizer).
- **MEMORY**: Stateless per chapter execution.
- **AUTHORITY & DECISION RIGHTS**: Can determine reading order across multi-column layouts; can discard unreadable page borders or artifacts.
- **PROHIBITIONS**: Cannot alter textbook terminology; cannot hallucinate missing text; cannot author quizzes.
- **MODEL**: NONE (Deterministic Python execution).
- **COST**: $0.00.
- **LATENCY**: < 5 seconds for a 20-page PDF.
- **ESCALATION RULES**: Halts and flags operator if PDF has DRM protection, scanned illegible handwriting, or missing pages.

---

### AGENT CONTRACT: AGT-002 AnalysisAgent
- **AGENT ID**: AGT-002
- **ROLE**: Pedagogical Concept Decomposition Specialist
- **PURPOSE**: Analyze raw textbook extracts to identify 3–5 foundational Topic Learning Nodes (TLNs) and map prerequisite relationships.
- **INPUT**: `raw_extract.json`, syllabus grade guidelines.
- **OUTPUT**: `content_map.json` (3–5 Nodes with target learning competencies).
- **TOOLS**: Semantic chunker, NCERT syllabus lookup.
- **AUTHORITY**: Can group sub-sections into cohesive nodes; can identify worked example candidates.
- **BOUNDARIES**: Cognitive Load Ceiling — must NEVER exceed 5 nodes per chapter.
- **MODEL**: Gemini 1.5/2.5 Flash / GPT-4o-mini / Local 8B.
- **COST TARGET**: < $0.05.
- **ESCALATION RULES**: Flags human if extracted chapter lacks identifiable worked examples or clear curriculum milestones.

---

### AGENT CONTRACT: AGT-003 DesignAgent
- **AGENT ID**: AGT-003
- **ROLE**: Interactive Learning Experience Sequencer
- **PURPOSE**: Sequence each concept node into the standard pedagogical rhythm (Intro → Text → Visual Manipulative → Worked Example → Quiz → Progress).
- **INPUT**: `content_map.json`, Visual Contract Registry (`15_VISUAL_CONTRACT.md`).
- **OUTPUT**: Structured step array in `chapter_spec.json`.
- **AUTHORITY**: Selects appropriate visual manipulative tool from approved registry.
- **PROHIBITIONS**: Cannot create unsupported custom step types or inject unverified third-party libraries.
- **MODEL**: Fast Reasoning model.

---

### AGENT CONTRACT: AGT-004 AssessmentAgent
- **AGENT ID**: AGT-004
- **ROLE**: Socratic Assessment Author
- **PURPOSE**: Generate diagnostic multiple-choice questions with 3–4 plausible distractors and distractor-specific verbal misconception feedback (`m` field).
- **INPUT**: Node concept definitions, worked examples.
- **OUTPUT**: Diagnostic question objects conforming to `14_ASSESSMENT_CONTRACT.md`.
- **AUTHORITY**: Formulates distractors representing genuine student errors.
- **PROHIBITIONS**: **ZERO-SPOILER RULE** — Explanations must NEVER state or reveal the correct answer.
- **MODEL**: Deep Reasoning (Claude 3.5 Sonnet / Gemini Pro / Freebuff + Linter).
- **ESCALATION RULES**: Halts if distractor cannot be tied to a distinct cognitive error.

---

### AGENT CONTRACT: AGT-005 LLEAgent
- **AGENT ID**: AGT-005
- **ROLE**: Bilingual Language Bridge Specialist
- **PURPOSE**: Generate phonetic Devanagari pronunciation and contextual Hindi translations for chapter vocabulary.
- **INPUT**: Chapter text token streams.
- **OUTPUT**: `CONN` (inline connecting words) and `WM` (word dictionary) JSON objects.
- **AUTHORITY**: Maps English terms to conversational Hindi meanings suitable for rural school students.
- **PROHIBITIONS**: **MATH COLLISION RULE** — Must NEVER translate mathematical variables ($x$, $y$, $z$) or formula symbols.
- **MODEL**: Indic-specialized / Gemini Flash + Base Dictionary lookup.

---

### AGENT CONTRACT: AGT-006 QAAgent
- **AGENT ID**: AGT-006
- **ROLE**: Rigorous Verification & L-Truth Auditor
- **PURPOSE**: Execute the 200+ check automated verification harness against the compiled standalone HTML chapter.
- **INPUT**: Compiled `.html` file.
- **OUTPUT**: Verification Report with binary Gate Decision (PASS / FAIL).
- **AUTHORITY**: Absolute blocking gate — halts chapter distribution on any failure.
- **PROHIBITIONS**: Cannot mutate chapter source code to force a pass.
- **MODEL**: NONE (Deterministic Node.js / JSDOM harness).
- **ESCALATION RULES**: Emits immediate alert with exact failing check name and line number.
