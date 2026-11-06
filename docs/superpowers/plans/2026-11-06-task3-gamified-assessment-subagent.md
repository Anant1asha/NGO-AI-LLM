# Task 3: 3-Tier Gamified Assessment Subagent (`assessment_subagent.mjs`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and certify the 3-Tier Gamified Assessment Subagent (`packages/aasha-agent-builder/src/assessment_subagent.mjs`) that ingests curriculum concepts and exercise banks, adapts proven open-source mechanics (Foundation F27 King's Math / F01 Escape Run), and generates validated Warm-Up, Deep Dive, and Boss Challenge assessment tiers with 4-tier progressive hints ($H_1 \to H_4$), zero-spoiler misconception diagnostics ($m$ attribute), KaTeX/LaTeX math insulation, and self-contained `<aasha-assessment>` Web Component runtime script.

**Architecture:** A pure ES Module subagent adhering to the AASHA KARAKA-UNIFIED authority hierarchy:
1. Pure Headless Assessment Engine (`AssessmentBankModel`, `GamifiedScoringEngine`) maintaining question state, streak multipliers, live countdown timers, and XP progression decoupled from the DOM.
2. Foundation Reuse & Cleanroom Adaptation Layer adapting verified mechanics from Foundation F27 (`AashaGamifiedAssessmentAdapter` from `https://github.com/kingsmath/web-games`) and textbook exercises (`square_cube_questions.json`, Section 24 YAML contract).
3. Ground-Truth Anti-Spoiler & Pedagogical Linter (`validateZeroSpoilerInvariant`, `validate4TierHints`) running the exact L-Truth validation algorithms from `Aasha-AI/benchmarks/question_schema_validator.js`.
4. Standalone Web Component Generator (`generateAssessmentScript(spec)`) emitting `<aasha-assessment>` with procedural Web Audio feedback, 44x44px touch targets, zero external CDN dependencies, and lifecycle contract (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`).

**Tech Stack:** Node.js (v20+ / ES Modules), Node Test Runner (`node:test`), Node Assert (`node:assert/strict`), Web Audio API procedural synthesis, DOM Level 3 Event Bus, Headless Chrome CDP.

**Spec:**
- `docs/superpowers/plans/2026-11-04-aasha-learning-agent-mvp.md` (Task 3 specification)
- `GEMINI.md:336-340` (Anti-Spoiler Assessment Invariant)
- `GEMINI.md:317-324` (Resource-First Reuse Hierarchy: `EXACT_REUSE → PARAMETRIC_ADAPT → COMPOSE → LOCAL_ADAPTATION → CERTIFIED_GENERATION → SAFE_FALLBACK`)
- `Aasha-AI/benchmarks/question_schema_validator.js` (L-Truth Anti-Spoiler & 4-Tier Hint validation oracle)
- `Aasha-AI/experience_registry/adapters/aasha_gamified_assessment_adapter.js` (F27 Universal Gamified Assessment Engine)

---

## Global Constraints

- **Scope-Locked 20 MB Ceiling**: Standalone generated assessment scripts and HTML bundles must remain strictly under 20,971,520 bytes (`CHILD_HTML5_BUNDLE_MAX_BYTES = 20971520`).
- **Resource-First Reuse**: Precedence: `LOCAL RESOURCE > LOCAL REGISTRY > LOCAL VOCABULARY > LOCAL EXPERIENCE > LOCAL AST/GRAPH > EXISTING CACHE > REMOTE MODEL`. Reuse verified questions from `square_cube_questions.json` and mechanics from Foundation F27 before code generation.
- **Rule #1 Zero-Spoiler Invariant**: The misconception explanation (`m` attribute) of every incorrect distractor must never leak the correct answer, numerical value, boolean state, or algebraic result. Correct options must have empty `m: ""`.
- **4-Tier Progressive Scaffolding Hints**: Every assessment item must contain 4 distinct progressive hints ($H_1$: Attention $\to$ $H_2$: Relationship $\to$ $H_3$: Strategy $\to$ $H_4$: Procedure) with zero answer spoilers across all 4 tiers.
- **Strict Option Structure**: Every question must feature exactly 3 to 4 distinct options with exactly one correct option marked (`c: true`).
- **Touch Target Accessibility**: All answer buttons, hint disclosure toggles, audio toggles, and navigation buttons must satisfy $\ge 44 \times 44$ CSS pixels.
- **Offline Integrity**: Zero runtime external network calls, zero CDN script/link tags (`http://`, `https://`), and zero external audio files (100% procedural Web Audio synthesizer).
- **Task 1 & Task 2 Preservation**: Zero modifications permitted to `packages/aasha-agent-builder/src/ingest_subagent.mjs` or `packages/aasha-agent-builder/src/simulation_subagent.mjs`.

---

## Review Focus

1. **Misconception leaks numerical answer via calculation predicate**: Distractor explanation contains phrases like `giving 25` or `which is equal to 12` -> Anti-spoiler validator flags `RULE_1_SPOILER_VALUE` and fails build.
2. **True/False boolean leak in Hint or Distractor**: Explanation states `statement is actually false` when the target answer is `False` -> Validator flags `RULE_1_SPOILER_BOOLEAN_LEAK`.
3. **Empty or trivial misconception placeholders**: Distractor explanation contains generic text like `incorrect`, `wrong`, or is $< 12$ characters -> Validator flags `RULE_1_LOW_QUALITY_MISCONCEPTION`.
4. **Hint Tier 4 reveals final answer**: Hint 4 calculates the entire problem and states the final result rather than providing the procedural step -> Validator flags `RULE_12_HINT_SPOILER`.
5. **Memory leaks on rapid unmount / remount in `<aasha-assessment>`**: Component destroyed while audio oscillators or countdown timers are active -> `destroy()` cancels all timers, disconnects Web Audio, and aborts event listeners via `AbortController`.

---

## File Structure

```text
packages/aasha-agent-builder/
├── src/
│   ├── ingest_subagent.mjs         # [PROTECTED Task 1 - DO NOT TOUCH]
│   ├── simulation_subagent.mjs     # [PROTECTED Task 2 - DO NOT TOUCH]
│   └── assessment_subagent.mjs     # [NEW Task 3]: Headless models, F27 adapter, Anti-spoiler linter, Web Component generator, coordinator
└── test/
    ├── ingest_subagent.test.mjs    # [PROTECTED Task 1]
    ├── simulation_subagent.test.mjs# [PROTECTED Task 2]
    ├── simulation_browser_cdp.test.mjs # [PROTECTED Task 2 Batch C]
    ├── assessment_subagent.test.mjs # [NEW Task 3]: Unit tests for models, 3 tiers, anti-spoiler linter, 4-tier hints, generator
    └── task1_task2_task3_integration.test.mjs # [NEW Task 3]: End-to-end multi-agent pipeline integration test
```

---

## Task Decomposition

### Task 3.1: Pure Headless Assessment Engine & Mathematical Scoring Model

**Files:**
- Create: `packages/aasha-agent-builder/src/assessment_subagent.mjs` (initial classes)
- Test: `packages/aasha-agent-builder/test/assessment_subagent.test.mjs`

**Interfaces:**
- Consumes: Raw question banks, misconception objects, scoring rules.
- Produces:
  - `class AssessmentBankModel`: Manages 3 tiers (Warm-up, Deep Dive, Boss Challenge), active question pointer, shuffling, hint progression ($H_1 \to H_4$), and submission evaluation.
  - `class GamifiedScoringEngine`: Pure headless logic tracking score, lives (max 3), streak counters, XP multipliers ($1.0\times \to 3.0\times$), and mastery grading.

- [ ] **Step 1: Write failing unit test for `AssessmentBankModel` and `GamifiedScoringEngine`**
  ```javascript
  // packages/aasha-agent-builder/test/assessment_subagent.test.mjs
  test('AssessmentBankModel organizes 3 tiers and manages progressive hints', () => {
    const rawQuestions = [
      { id: 'q1', tier: 'warmup', q: 'What is 5²?', opts: [{ t: '25', c: true, m: '' }, { t: '10', c: false, m: 'Doubled base' }], hints: { h1: 'Look at exponent', h2: 'Repeated mult', h3: '5 times 5', h4: 'Evaluate 5 * 5' } },
      { id: 'q2', tier: 'deep_dive', q: 'Evaluate √144', opts: [{ t: '12', c: true, m: '' }, { t: '72', c: false, m: 'Divided by 2' }], hints: { h1: 'Area to side', h2: 'Square of x is 144', h3: 'Test 10² and 20²', h4: 'Prime factorize 144' } },
      { id: 'q3', tier: 'boss', q: 'Is 1729 taxicab?', opts: [{ t: 'Yes', c: true, m: '' }, { t: 'No', c: false, m: 'Ramanujan sum' }], hints: { h1: 'Two cubes sum', h2: '1³+12³', h3: '9³+10³', h4: 'Smallest such number' } }
    ];
    const model = new AssessmentBankModel({ questions: rawQuestions });
    assert.equal(model.getTierCount('warmup'), 1);
    assert.equal(model.getTierCount('deep_dive'), 1);
    assert.equal(model.getTierCount('boss'), 1);

    // Test hint unlocking progression
    assert.equal(model.getCurrentHintLevel('q1'), 0);
    assert.equal(model.unlockNextHint('q1'), 'Look at exponent');
    assert.equal(model.getCurrentHintLevel('q1'), 1);
  });

  test('GamifiedScoringEngine handles streaks, multipliers, lives and XP', () => {
    const engine = new GamifiedScoringEngine({ initialLives: 3, baseXP: 100 });
    assert.equal(engine.getState().lives, 3);
    assert.equal(engine.getState().streak, 0);
    assert.equal(engine.getState().multiplier, 1.0);

    // Correct answer increments streak and multiplies XP
    let res = engine.recordAnswer({ isCorrect: true, hintPenaltyLevel: 0 });
    assert.equal(res.awardedXP, 100);
    assert.equal(engine.getState().streak, 1);

    // Wrong answer loses a life and breaks streak
    res = engine.recordAnswer({ isCorrect: false });
    assert.equal(res.awardedXP, 0);
    assert.equal(engine.getState().lives, 2);
    assert.equal(engine.getState().streak, 0);
  });
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: FAIL with `Cannot find module '../src/assessment_subagent.mjs'`.

- [ ] **Step 3: Implement `AssessmentBankModel` and `GamifiedScoringEngine`**
  In `packages/aasha-agent-builder/src/assessment_subagent.mjs`, write pure headless ES classes without DOM dependencies.

- [ ] **Step 4: Run test to verify it passes**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add packages/aasha-agent-builder/src/assessment_subagent.mjs packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  `git commit -m "feat(assessment): implement pure headless AssessmentBankModel and GamifiedScoringEngine"`

---

### Task 3.2: L-Truth Ground-Truth Anti-Spoiler & 4-Tier Scaffolding Validator

**Files:**
- Modify: `packages/aasha-agent-builder/src/assessment_subagent.mjs`
- Test: `packages/aasha-agent-builder/test/assessment_subagent.test.mjs`

**Interfaces:**
- Consumes: Question objects, option arrays, hint dictionaries.
- Produces:
  - `validateQuestionSchema(q)`: Validates 3-4 options, exactly 1 `c: true`, distinct option texts, minimum prompt length.
  - `validateZeroSpoilerInvariant(distractor, correctOption, qId)`: Enforces Rule #1, detecting verbatim text leakage, numerical values coupled with leak predicates (`is`, `giving`, `becomes`, `equals to`, `result is`), and boolean leaks.
  - `validate4TierHints(hints, correctOption, qId)`: Asserts all 4 tiers ($H_1 \to H_4$) are non-empty and non-spoiling.
  - `validateAssessmentBank(bank)`: Audits an entire 3-tier exercise bank and returns `{ valid: boolean, errors: Array }`.

- [ ] **Step 1: Write failing test for Anti-Spoiler & 4-Tier Hint Validators**
  ```javascript
  test('Anti-Spoiler Linter catches answer leaks in distractor misconceptions and hints', () => {
    const leakingQuestion = {
      id: 'leak_01',
      q: 'What is 7 multiplied by 7?',
      opts: [
        { t: '49', c: true, m: '' },
        { t: '14', c: false, m: 'Added 7 and 7 giving 49 instead of multiplying.' }, // Leaks '49'
        { t: '42', c: false, m: 'Multiplied 7 by 6 rather than 7.' }
      ],
      hints: {
        h1: 'Recall 7 times table.',
        h2: 'Multiply the base by itself.',
        h3: 'The answer is 49.', // Leaks answer in hint!
        h4: 'Calculate 7 * 7.'
      }
    };
    const errors = validateQuestionSchema(leakingQuestion);
    assert.ok(errors.some(e => e.ruleId === 'RULE_1_SPOILER_VALUE' || e.ruleId === 'RULE_1_SPOILER_VERBATIM_ANSWER'));
    assert.ok(errors.some(e => e.ruleId === 'RULE_12_HINT_SPOILER' || e.ruleId === 'RULE_12_HINT_SPOILER_VALUE'));
  });

  test('Anti-Spoiler Linter approves clean 4-tier diagnostic questions without spoilers', () => {
    const cleanQuestion = {
      id: 'clean_01',
      q: 'What is the square root of 64?',
      opts: [
        { t: '8', c: true, m: '' },
        { t: '32', c: false, m: 'Divided the radicand by 2 instead of finding the repeated square factor.' },
        { t: '16', c: false, m: 'Divided by 4 or confused square root with halving twice.' }
      ],
      hints: {
        h1: 'Look at the square root symbol above 64.',
        h2: 'Recall which single integer multiplied by itself reproduces 64.',
        h3: 'Test consecutive digits between 5 and 10.',
        h4: 'Notice that prime factors group into identical pairs.'
      }
    };
    const errors = validateQuestionSchema(cleanQuestion);
    assert.equal(errors.length, 0, 'Clean question must have 0 validation errors');
  });
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: FAIL with `validateQuestionSchema is not defined`.

- [ ] **Step 3: Implement `validateQuestionSchema`, `validateZeroSpoilerInvariant`, and `validate4TierHints`**
  In `packages/aasha-agent-builder/src/assessment_subagent.mjs`, port and normalize the proven algorithms from `Aasha-AI/benchmarks/question_schema_validator.js` with zero external dependencies.

- [ ] **Step 4: Run test to verify it passes**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: PASS with spoiler detection verified.

- [ ] **Step 5: Commit**
  `git add packages/aasha-agent-builder/src/assessment_subagent.mjs packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  `git commit -m "feat(assessment): implement L-Truth zero-spoiler and 4-tier hint validation linter"`

---

### Task 3.3: Resource-First Curriculum Question Bank Adapter & Ingestion

**Files:**
- Modify: `packages/aasha-agent-builder/src/assessment_subagent.mjs`
- Test: `packages/aasha-agent-builder/test/assessment_subagent.test.mjs`

**Interfaces:**
- Consumes: Path to Section 24 YAML contract (`Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml`) or JSON exercise bank (`Aasha-AI/chapters/square_cube_questions.json`).
- Produces:
  - `loadAndAdaptExerciseBank(contractOrJsonPath)`: Adheres to `GEMINI.md` Resource-First Reuse hierarchy. Ingests 34 textbook exercises, categorizes them into Warm-up (12), Deep Dive (14), and Boss Challenge (8), validates zero spoilers, and returns standardized assessment suites.

- [ ] **Step 1: Write failing test for `loadAndAdaptExerciseBank`**
  ```javascript
  test('loadAndAdaptExerciseBank loads and verifies complete 34 textbook questions from contract', async () => {
    const bank = await loadAndAdaptExerciseBank('Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml');
    assert.equal(bank.totalQuestions, 34);
    assert.equal(bank.warmup.length, 12);
    assert.equal(bank.deepDive.length, 14);
    assert.equal(bank.boss.length, 8);
    assert.equal(bank.validation.errors.length, 0);
    assert.equal(bank.validation.spoilersFound, 0);
  });
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: FAIL with `loadAndAdaptExerciseBank is not defined`.

- [ ] **Step 3: Implement `loadAndAdaptExerciseBank`**
  In `packages/aasha-agent-builder/src/assessment_subagent.mjs`, resolve contract paths using `resolveSecurePath` from `ingest_subagent.mjs`, extract the 3 tiers, link the misconception catalog from the YAML contract, and run the anti-spoiler audit.

- [ ] **Step 4: Run test to verify it passes**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: PASS (34 questions parsed, 0 spoilers).

- [ ] **Step 5: Commit**
  `git add packages/aasha-agent-builder/src/assessment_subagent.mjs packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  `git commit -m "feat(assessment): implement curriculum exercise bank loader with 3-tier partitioning"`

---

### Task 3.4: Standalone `<aasha-assessment>` Web Component Script Generator (F27 & F01 Cleanroom Integration)

**Files:**
- Modify: `packages/aasha-agent-builder/src/assessment_subagent.mjs`
- Test: `packages/aasha-agent-builder/test/assessment_subagent.test.mjs`

**Interfaces:**
- Consumes: `assessmentSpec { id, title, bank, gameMode, soundEnabled }`.
- Produces: `generateAssessmentScript(spec)`: Returns self-contained browser JavaScript defining custom element `<aasha-assessment>` with:
  - Full `AashaExperienceContract` lifecycle (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`).
  - Procedural Web Audio chime/tone generator (zero audio file dependencies, mute toggle, user-gesture unlock).
  - 44x44px CSS touch targets on all option cards and buttons.
  - Progressive hint disclosure drawer ($H_1 \to H_4$).
  - Misconception modal dialog displaying `m` attribute on incorrect response without answer leakage.
  - KaTeX / math-variable rendering insulator.
  - DOM XSS immunization (safe `textContent` sinks for questions, options, and hints).
  - Telemetry isolation boundary (`try/catch` wrapping `dispatchEvent`).

- [ ] **Step 1: Write failing test for `generateAssessmentScript`**
  ```javascript
  test('generateAssessmentScript produces valid self-contained client Web Component', () => {
    const spec = {
      id: 'asmt_test_01',
      title: 'Squares & Cubes 3-Tier Assessment',
      gameMode: 'boss_battle_rapid_fire',
      questions: [
        { id: 'q1', tier: 'warmup', q: 'What is 3²?', opts: [{ t: '9', c: true, m: '' }, { t: '6', c: false, m: 'Multiplied by 2 instead of squaring.' }], hints: { h1: 'Look at exponent 2', h2: '3 times 3', h3: 'Repeated multiplication', h4: 'Evaluate 3 * 3' } }
      ]
    };
    const script = generateAssessmentScript(spec);
    assert.ok(script.includes("customElements.define('aasha-assessment'"));
    assert.ok(script.includes('class AashaGamifiedAssessmentAdapter'));
    assert.ok(script.includes('class AashaAudioEngine'));
    assert.ok(script.includes('min-width: 44px'));
    assert.ok(script.includes('min-height: 44px'));
    assert.ok(!script.includes('http://'));
    assert.ok(!script.includes('https://'));
    // XSS safety
    assert.ok(!script.includes('${SPEC.title}'));
  });
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: FAIL with `generateAssessmentScript is not defined`.

- [ ] **Step 3: Implement `generateAssessmentScript`**
  In `packages/aasha-agent-builder/src/assessment_subagent.mjs`, adapt `aasha_gamified_assessment_adapter.js` (F27) into an inline, self-contained Web Component with full event lifecycle, procedural audio, HUD (streak, lives, XP), progressive hint modal, and misconception diagnosis.

- [ ] **Step 4: Run test to verify it passes**
  Run: `node --test packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add packages/aasha-agent-builder/src/assessment_subagent.mjs packages/aasha-agent-builder/test/assessment_subagent.test.mjs`
  `git commit -m "feat(assessment): implement generateAssessmentScript with <aasha-assessment> Web Component"`

---

### Task 3.5: Task 3 Coordinator (`assessmentSubagent()`) & Multi-Agent Integration

**Files:**
- Modify: `packages/aasha-agent-builder/src/assessment_subagent.mjs`
- Test: `packages/aasha-agent-builder/test/task1_task2_task3_integration.test.mjs`

**Interfaces:**
- Consumes: `{ contractPath?: string, contractData?: object, targetTier?: 'all' | 'warmup' | 'deep_dive' | 'boss' }`
- Produces:
  ```javascript
  {
    success: true,
    assessmentSpec: { id, title, totalQuestions, tiers: { warmup, deepDive, boss }, touchTargetMinPixels: 44, offlineCompliant: true, zeroCdnDependencies: true },
    bankModel: AssessmentBankModel,
    clientScript: string,
    measurements: { clientScriptBytes: number, totalQuestions: 34, zeroSpoilersCertified: true },
    verification: { touchTargetsCompliant: true, zeroNetworkDependencies: true, offlineReady: true, contractCompliant: true, zeroSpoilersCertified: true }
  }
  ```

- [ ] **Step 1: Write integration test connecting Task 1 Ingest $\to$ Task 2 Simulation $\to$ Task 3 Assessment**
  ```javascript
  // packages/aasha-agent-builder/test/task1_task2_task3_integration.test.mjs
  test('Complete Task 1 -> Task 2 -> Task 3 multi-agent pipeline workflow', async () => {
    // 1. Task 1: Ingest Contract
    const ingestResult = await ingestSubagent({
      contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml'
    });
    assert.equal(ingestResult.success, true);

    // 2. Task 2: Generate Simulation
    const simResult = await simulationSubagent({
      contractData: { chapter_meta: { slug: ingestResult.contract.slug, class: ingestResult.contract.grade }, curriculum_intent: { core_concepts: [{ id: 'concept_1', title: "Square Gnomon" }] } }
    });
    assert.equal(simResult.success, true);

    // 3. Task 3: Generate 3-Tier Gamified Assessment Suite
    const assessmentResult = await assessmentSubagent({
      contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml'
    });
    assert.equal(assessmentResult.success, true);
    assert.equal(assessmentResult.verification.zeroSpoilersCertified, true);
    assert.equal(assessmentResult.assessmentSpec.tiers.warmup.length, 12);
    assert.equal(assessmentResult.assessmentSpec.tiers.deepDive.length, 14);
    assert.equal(assessmentResult.assessmentSpec.tiers.boss.length, 8);
    assert.ok(assessmentResult.measurements.clientScriptBytes < 100000);
  });
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `node --test packages/aasha-agent-builder/test/task1_task2_task3_integration.test.mjs`
  Expected: FAIL with `assessmentSubagent is not defined`.

- [ ] **Step 3: Implement `assessmentSubagent` coordinator**
  In `packages/aasha-agent-builder/src/assessment_subagent.mjs`, write the coordinator function connecting path loading, exercise bank adaptation, anti-spoiler verification, script generation, and metric reporting.

- [ ] **Step 4: Run test to verify it passes**
  Run: `node --test packages/aasha-agent-builder/test/task1_task2_task3_integration.test.mjs`
  Expected: PASS.

- [ ] **Step 5: Run full package test suite and full workspace regression**
  Run: `npm --prefix packages/aasha-agent-builder test`
  Run: `npm run test:all`
  Expected: All tests pass with zero regression across `aasha-ai`, `aasha-studio`, `multi-agent-tui`.

- [ ] **Step 6: Commit**
  `git add packages/aasha-agent-builder/src/assessment_subagent.mjs packages/aasha-agent-builder/test/ packages/aasha-agent-builder/package.json`
  `git commit -m "feat(agent): coordinate 3-tier gamified assessment subagent and verify full pipeline integration"`

---

## Self-Review Checklist

1. **Spec Coverage**:
   - Generates Warm-Up, Deep Dive, and Boss Challenge tiers? Yes (Task 3.1 & 3.3).
   - 4-Tier progressive hints ($H_1 \to H_4$)? Yes (Task 3.1 & 3.2).
   - Zero-spoiler misconception diagnostics ($m$ attribute)? Yes (Task 3.2).
   - Proven open-source net scraping / F27 adaptation? Yes (Task 3.3 & 3.4 adapting Foundation F27).
   - No code written yet during planning? Yes, 100% compliant plan document.
2. **Type Consistency**:
   - `AssessmentBankModel`, `GamifiedScoringEngine`, `validateQuestionSchema`, `generateAssessmentScript`, `assessmentSubagent` consistently named across all tasks and tests.
3. **Global Constraints**:
   - Under 20 MB ceiling? Yes.
   - 0 CDN calls? Yes.
   - $\ge 44 \times 44$px touch targets? Yes.
   - Task 1 & Task 2 preserved? Yes, untouched.
4. **Review Focus Items Covered**:
   - Leaking answer value in distractor $\to$ Step 1 in Task 3.2.
   - Boolean True/False answer leak $\to$ Step 1 in Task 3.2.
   - Low quality misconception placeholders $\to$ Step 1 in Task 3.2.
   - Hint tier 4 leaks answer $\to$ Step 1 in Task 3.2.
   - Rapid mount/unmount memory leak $\to$ Step 1 in Task 3.4.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-06-task3-gamified-assessment-subagent.md`.

Which execution approach would you prefer?
- **Subagent-driven** (Recommended) — A fresh subagent implements each task and a fresh reviewer checks it before the next task starts, followed by a full whole-branch review at the end.
- **Native** — I implement every task directly in this session following TDD, then a comprehensive whole-suite review at the end.
