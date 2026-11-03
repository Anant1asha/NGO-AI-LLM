# AASHA Autonomous Learning & Gamified Assessment Agent (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and certify the MVP Autonomous AI Tool cum Agent with multi-subagent orchestration that takes curriculum inputs and generates standalone, 100% offline-first, gamified HTML5 learning modules (<20MB) featuring adaptive hybrid simulations, 3-tier scaffolded assessments, and bilingual Indic math insulation.

**Architecture:** A modular Node/TypeScript orchestrator (`scripts/aasha_learning_agent_runner.mjs`) coordinates 5 specialized subagent engines: Curriculum Ingest, Adaptive Hybrid Simulation Generator (Canvas 2D/WebGL/SVG), 3-Tier Gamified Assessment Synthesizer (4-tier hints + anti-spoiler diagnostics), Bilingual Indic & Math Insulator, and Single-File Zero-CDN Packager. Verified by an automated end-to-end test suite checking bundle size, zero network leaks, mobile viewport responsiveness, and anti-spoiler invariants.

**Tech Stack:** Node.js (v20+ / ES Modules), TypeScript, Canvas 2D API, WebGL / Three.js procedural shaders, Web Audio API procedural synthesis, KaTeX inline typography, JSDOM test harness, PyMuPDF / JSON contracts.

**Spec:** [`startup.md`](startup.md), [`AGENTS.md`](AGENTS.md), and [`.claude/agents/aasha-learning-agent.md`](.claude/agents/aasha-learning-agent.md).

## Global Constraints
- `CHILD_HTML5_BUNDLE_MAX_BYTES = 20971520` (Strict 20MB standalone ceiling for generated HTML5 modules).
- Zero external network, CDN, remote font, or analytics requests at runtime in generated files.
- Minimum interactive touch target size $\ge 44 \times 44\text{px}$ across all interactive buttons, sliders, and options.
- Same-frame mobile viewport responsiveness: concept definition and simulation visible simultaneously without scrolling across 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915).
- Anti-Spoiler Rule #1: Misconception explanations (`m` attribute) must never state or imply the numerical/direct answer.
- Pre-LLE math insulation: All LaTeX formulas and expressions must be shielded as `__AASHA_MATH_X__` tokens before linguistic processing.

## Review Focus
1. Bundle contains unexpected external CDN URLs (`http://`, `https://`, `cdn.jsdelivr`, `cdnjs`) -> Test must fail if any remote script/link/image tag is present.
2. Misconception explanation leaks the correct answer -> Test regex scanner detects if correct answer appears in wrong-option feedback.
3. Mathematical expressions colliding with Indic translation tags -> Test confirms zero math-rt collisions and exact LaTeX restoration.
4. Mobile viewport overflow or touch targets $< 44\text{px}$ -> Test verifies all interactive selectors meet CSS minimum dimension requirements.
5. Ingestion of malformed/empty topic schema -> Generator gracefully falls back to canonical default template with non-crashing valid output.

---

### Task 1: Autonomous Ingest & Curriculum Analysis Subagent Engine

**Files:**
- Create: `packages/aasha-agent-builder/src/ingest_subagent.mjs`
- Test: `packages/aasha-agent-builder/tests/test_ingest_subagent.mjs`

**Interfaces:**
- Consumes: `{ topic: string, subject: string, grade: number, rawContent?: string, contractYaml?: string }`
- Produces: `ConceptMapResult { topicNodes: Array<{ id: string, name: string, actionVerb: string, coreFormula?: string, description: string }>, targetGrade: number, subject: string }`

- [ ] **Step 1: Write the failing test**
  Write unit tests validating that `ingestCurriculum(input)` extracts 3–5 concept nodes, maps active Bloom's verbs, and safely handles missing/raw content.
- [ ] **Step 2: Run test to verify it fails**
  Run: `node packages/aasha-agent-builder/tests/test_ingest_subagent.mjs`
  Expected: FAIL with module/function not found.
- [ ] **Step 3: Implement `ingestCurriculum` in `packages/aasha-agent-builder/src/ingest_subagent.mjs`**
  Implement curriculum parser supporting Section 24 YAML contracts, JSON syllabus nodes, and prompt-driven fallback synthesis with 3–5 node ceiling.
- [ ] **Step 4: Run test to verify it passes**
  Run: `node packages/aasha-agent-builder/tests/test_ingest_subagent.mjs`
  Expected: PASS with 3-5 concept nodes generated.
- [ ] **Step 5: Commit**
  `git add packages/aasha-agent-builder/ && git commit -m "feat(agent): implement curriculum ingest subagent"`

---

### Task 2: Adaptive Hybrid Simulation & Visual Engine Subagent

**Files:**
- Create: `packages/aasha-agent-builder/src/simulation_subagent.mjs`
- Test: `packages/aasha-agent-builder/tests/test_simulation_subagent.mjs`

**Interfaces:**
- Consumes: `ConceptNode { id: string, name: string, actionVerb: string, type: "2d" | "3d" | "hybrid" }`
- Produces: `SimulationBundle { htmlMarkup: string, canvasScript: string, webglScript?: string, soundScript: string }` complying with `AashaExperienceContract`.

- [ ] **Step 1: Write the failing test**
  Write test verifying that `generateSimulationComponent(node)` outputs procedural Canvas 2D routines, Web Audio API procedural sound generators, and $\ge 44\text{px}$ touch target bindings.
- [ ] **Step 2: Run test to verify it fails**
  Run: `node packages/aasha-agent-builder/tests/test_simulation_subagent.mjs`
  Expected: FAIL.
- [ ] **Step 3: Implement `generateSimulationComponent` in `packages/aasha-agent-builder/src/simulation_subagent.mjs`**
  Generate self-contained interactive Canvas 2D/WebGL simulation code implementing `mount()`, `getState()`, `pause()`, and `reset()`.
- [ ] **Step 4: Run test to verify it passes**
  Run: `node packages/aasha-agent-builder/tests/test_simulation_subagent.mjs`
  Expected: PASS.
- [ ] **Step 5: Commit**
  `git commit -m "feat(agent): implement adaptive hybrid simulation subagent"`

---

### Task 3: 3-Tier Gamified Assessment & Anti-Spoiler Subagent

**Files:**
- Create: `packages/aasha-agent-builder/src/assessment_subagent.mjs`
- Test: `packages/aasha-agent-builder/tests/test_assessment_subagent.mjs`

**Interfaces:**
- Consumes: `ConceptMapResult`
- Produces: `AssessmentSuite { tier1: Question[], tier2: Question[], tier3: Question[] }` where each `Question` has 3-4 options, 1 correct index, 4 progressive hints ($H_1 \to H_4$), and non-spoiling misconception diagnostics (`m`).

- [ ] **Step 1: Write the failing test**
  Write test validating question schemas, option counts, hint tiers, and regex anti-spoiler audit verifying that no `m` field contains the correct answer.
- [ ] **Step 2: Run test to verify it fails**
  Run: `node packages/aasha-agent-builder/tests/test_assessment_subagent.mjs`
  Expected: FAIL.
- [ ] **Step 3: Implement `generateAssessmentSuite` in `packages/aasha-agent-builder/src/assessment_subagent.mjs`**
  Implement question generation with 3 tiers (Warm-up, Deep Dive, Boss Challenge), XP/streak rewards, and anti-spoiler linter.
- [ ] **Step 4: Run test to verify it passes**
  Run: `node packages/aasha-agent-builder/tests/test_assessment_subagent.mjs`
  Expected: PASS with 0 anti-spoiler violations.
- [ ] **Step 5: Commit**
  `git commit -m "feat(agent): implement 3-tier gamified assessment subagent"`

---

### Task 4: Bilingual Indic LLE & Math Insulator Subagent

**Files:**
- Create: `packages/aasha-agent-builder/src/lle_subagent.mjs`
- Test: `packages/aasha-agent-builder/tests/test_lle_subagent.mjs`

**Interfaces:**
- Consumes: `rawHtmlText: string, vocabularyTerms?: string[]`
- Produces: `InsulatedLleBundle { processedHtml: string, inlinedDictionary: Record<string, any>, phonicsAudioJs: string }`

- [ ] **Step 1: Write the failing test**
  Test verifying that formulas (e.g. `\(a^2 + b^2 = c^2\)`) are shielded as `__AASHA_MATH_X__`, technical vocabulary is wrapped with `<rt>` / `window.WM` dictionary lookups, and formulas are restored 100% intact.
- [ ] **Step 2: Run test to verify it fails**
  Run: `node packages/aasha-agent-builder/tests/test_lle_subagent.mjs`
  Expected: FAIL.
- [ ] **Step 3: Implement `processBilingualLle` in `packages/aasha-agent-builder/src/lle_subagent.mjs`**
  Integrate formula shielding regex, dictionary matching against `experience_registry/aasha_dictionary_db.json`, and offline TTS / Web Audio phonics bindings.
- [ ] **Step 4: Run test to verify it passes**
  Run: `node packages/aasha-agent-builder/tests/test_lle_subagent.mjs`
  Expected: PASS.
- [ ] **Step 5: Commit**
  `git commit -m "feat(agent): implement bilingual Indic and math insulator subagent"`

---

### Task 5: Master Autonomous Orchestrator & Single-File HTML5 Packager

**Files:**
- Create: `scripts/aasha_learning_agent_runner.mjs`
- Create: `packages/aasha-agent-builder/src/packager.mjs`
- Modify: `package.json:10-30`
- Test: `packages/aasha-agent-builder/tests/test_e2e_packaging.mjs`

**Interfaces:**
- Consumes: User prompt or curriculum input `{ topic: string, grade: number, subject: string }`
- Produces: Standalone offline HTML5 file in `output/` (e.g. `output/Class8_SquaresCubes_Gamified.html`).

- [ ] **Step 1: Write the failing E2E packaging test**
  Test checking full end-to-end generation, single-file output existence, byte size $\le 20\text{MB}$, zero remote URLs (`https?://(?!www\.w3\.org)`), and touch target CSS $\ge 44\text{px}$.
- [ ] **Step 2: Run test to verify it fails**
  Run: `node packages/aasha-agent-builder/tests/test_e2e_packaging.mjs`
  Expected: FAIL.
- [ ] **Step 3: Implement `packager.mjs` and `scripts/aasha_learning_agent_runner.mjs`**
  Assemble all subagents' outputs into a monolithic HTML template with inlined CSS, procedural canvas JS, Web Audio synthesizer, confetti engine, and 3-tier quiz UI. Add `"agent:generate": "node scripts/aasha_learning_agent_runner.mjs"` to root `package.json`.
- [ ] **Step 4: Run test to verify it passes**
  Run: `node packages/aasha-agent-builder/tests/test_e2e_packaging.mjs`
  Expected: PASS with 100% offline self-containment certified.
- [ ] **Step 5: Commit**
  `git commit -m "feat(agent): complete master autonomous learning agent packager and CLI"`

---

### Task 6: Master End-to-End Verification & Laya Audit

**Files:**
- Test: `tests/test_aasha_learning_agent_e2e.mjs`
- Output: `output/Class8_SquareCubeRoots_MVP_Module.html`

- [ ] **Step 1: Run the Agent to generate the reference MVP chapter**
  Execute `node scripts/aasha_learning_agent_runner.mjs --topic "Class 8 Square and Cube Roots" --output "output/Class8_SquareCubeRoots_MVP_Module.html"`
- [ ] **Step 2: Run the automated QA audit suite**
  Execute automated checks verifying:
  - File size $< 20\text{MB}$ (typically $< 300\text{KB}$)
  - Zero external CDN links
  - All touch targets $\ge 44\times 44\text{px}$
  - Zero spoiler leaks in question hints/misconceptions
- [ ] **Step 3: Verify existing ecosystem test suites pass**
  Run `npm run laya:test` and verify zero regressions.
- [ ] **Step 4: Final commit**
  `git commit -m "feat(agent): verify and certify MVP autonomous learning agent generation"`
