# Milestone 1 Remediation Plan: Tests, Mathematical Accuracy & Validator Hardening

**Author**: `explorer_fix_validator_and_tests_r2` (Remediation Explorer)  
**Target Workspace**: `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`  
**Date**: 2026-09-18T23:30:00Z  
**Status**: Ready for Implementation by `worker`  

---

## 1. Executive Summary & Scope

During the Milestone 1 audit of the Class 8 Mathematics chapter **"Squares and Cubes"** (`square and cube RL public school and ncert.pdf`), adversarial reviews by `reviewer_2_m1`, `challenger_2_m1`, and `auditor_m1` identified three major defects requiring immediate architectural remediation:
1. **Mathematical Typo in `sc_q28`**: The option text and answer key assert an equality `\(90^2 = 91^2\)` instead of enumerating the missing pattern terms `\(21^2\) and \(90^2, 91^2\)`.
2. **Decoupled E2E Test Suite (`tests/e2e_square_cube_suite.js`)**: Suite 1 validates a hardcoded internal mock array (`AUTHORITATIVE_34_QUESTIONS`) with disconnected IDs (`wu_01_it06`), passing 34/34 tests while completely ignoring the actual deliverable files `chapters/square_cube_questions.json` and `content/contracts/Mathematics_Class8_squares_and_cubes.yaml`.
3. **`QuestionSchemaValidator` Exploitable Blind Spots**:
   - **Boolean Stopword Blindness**: Inclusion of `'true'` and `'false'` in `STOPWORDS` allows distractors in True/False questions to leak the correct answer (e.g., `"The statement is incorrect, the correct answer is False."`) with 0 errors detected.
   - **Adverb / Qualifier Evasion**: The predicate leak regex (`\s*[:=]?\s*${escapedN}`) requires strict immediate adjacency, allowing intervening adverbs and modifiers (e.g., `"giving a final total of 25"`, `"becomes approximately 25"`, `"became exactly 25"`, `"leaving a remainder of 25"`, `"leads directly to 25"`) to evade detection completely.

This remediation plan provides the exact root-cause analysis, mathematical corrections, test decoupling refactoring, and bulletproof validator hardening diff patches.

---

## 2. Issue 1: Mathematical Typo in `sc_q28`

### 2.1 Problem Analysis & Mathematical Ground Truth
- **Source**: NCERT Ganita Prakash Class 8, Chapter 1, Figure It Out 1.8, Page 11.
- **Pattern Identity**: For consecutive bases $n$ and $n + 1$, the algebraic sum of squares identity is:
  $$n^2 + (n+1)^2 + [n(n+1)]^2 = [n(n+1) + 1]^2$$
  - Row 1: $1^2 + 2^2 + 2^2 = 3^2$ ($1 \times 2 = 2$, $2 + 1 = 3$)
  - Row 2: $2^2 + 3^2 + 6^2 = 7^2$ ($2 \times 3 = 6$, $6 + 1 = 7$)
  - Row 3: $3^2 + 4^2 + 12^2 = 13^2$ ($3 \times 4 = 12$, $12 + 1 = 13$)
  - Row 4: $4^2 + 5^2 + 20^2 = (\dots)^2 \implies (\dots) = 20 + 1 = 21 \implies 21^2$
  - Row 5: $9^2 + 10^2 + (\dots)^2 = (\dots)^2 \implies 9 \times 10 = 90 \implies 90^2$, and $90 + 1 = 91 \implies 91^2$
- **The Question Prompt**:
  `"q": "Identify the missing values in the pattern: \\(1^2+2^2+2^2=3^2\\), \\(2^2+3^2+6^2=7^2\\), \\(3^2+4^2+12^2=13^2\\), \\(4^2+5^2+20^2=(\\dots)^2\\), \\(9^2+10^2+(\\dots)^2=(\\dots)^2\\)."`
- **The Defect**:
  In `Aasha-AI/chapters/square_cube_questions.json` (lines 993–1015):
  The target option is formatted as:
  `"ans": "\\(21^2\\) and \\(90^2 = 91^2\\)"`
  `"t": "\\(21^2\\) and \\(90^2 = 91^2\\)"`
  This asserts the equality $90^2 = 91^2$ ($8100 = 8281$), which is a false mathematical equation. The row in question is $9^2 + 10^2 + 90^2 = 91^2$; the missing values filling the blanks are $90^2$ and $91^2$, which must be written as a pair: `\(90^2, 91^2\)`.
- **Secondary Impact**:
  In `Aasha-AI/benchmarks/test_square_cube_math_oracle.js` (line 360), the oracle verification function for `sc_q28` was hardcoded to check for the typo string:
  `truth: \`\\(21^2\\) and \\(90^2 = 91^2\\)\`,`

### 2.2 Concrete Remediation for `chapters/square_cube_questions.json`
Apply the following replacement in `Aasha-AI/chapters/square_cube_questions.json` at lines 993–1016:

```json
<<<<
      "ans": "\\(21^2\\) and \\(90^2 = 91^2\\)",
      "m": "Misinterpreting the algebraic relationship between consecutive base products and the target sum base.",
      "opts": [
        {
          "t": "\\(21^2\\) and \\(90^2 = 91^2\\)",
          "c": true,
          "m": ""
        },
        {
          "t": "\\(25^2\\) and \\(90^2 = 92^2\\)",
          "c": false,
          "m": "Added 5 to 20 rather than adding 1 to 20 for the right-hand base."
        },
        {
          "t": "\\(21^2\\) and \\(80^2 = 81^2\\)",
          "c": false,
          "m": "Multiplied 9 by 9 rather than 9 by 10 for the third term."
        },
        {
          "t": "\\(20^2\\) and \\(100^2 = 101^2\\)",
          "c": false,
          "m": "Used 10 squared rather than the product of the first two bases."
        }
      ],
====
      "ans": "\\(21^2\\) and \\(90^2, 91^2\\)",
      "m": "Misinterpreting the algebraic relationship between consecutive base products and the target sum base.",
      "opts": [
        {
          "t": "\\(21^2\\) and \\(90^2, 91^2\\)",
          "c": true,
          "m": ""
        },
        {
          "t": "\\(25^2\\) and \\(90^2, 92^2\\)",
          "c": false,
          "m": "Added 5 to 20 rather than adding 1 to 20 for the right-hand base."
        },
        {
          "t": "\\(21^2\\) and \\(80^2, 81^2\\)",
          "c": false,
          "m": "Multiplied 9 by 9 rather than 9 by 10 for the third term."
        },
        {
          "t": "\\(20^2\\) and \\(100^2, 101^2\\)",
          "c": false,
          "m": "Used 10 squared rather than the product of the first two bases."
        }
      ],
>>>>
```

### 2.3 Concrete Remediation for `benchmarks/test_square_cube_math_oracle.js`
In `Aasha-AI/benchmarks/test_square_cube_math_oracle.js` at lines 352–363:

```javascript
<<<<
  sc_q28: () => {
    // Identity: n^2 + (n+1)^2 + (n(n+1))^2 = (n(n+1)+1)^2
    // Row 4: 4^2 + 5^2 + 20^2 = 21^2
    const row4_rhs = Math.round(Math.sqrt(4*4 + 5*5 + 20*20)); // 21
    // Row 5: 9^2 + 10^2 + 90^2 = 91^2
    const row5_c = 9 * 10; // 90
    const row5_rhs = Math.round(Math.sqrt(9*9 + 10*10 + 90*90)); // 91
    return {
      truth: `\\(21^2\\) and \\(90^2 = 91^2\\)`,
      matches: row4_rhs === 21 && row5_c === 90 && row5_rhs === 91
    };
  },
====
  sc_q28: () => {
    // Identity: n^2 + (n+1)^2 + (n(n+1))^2 = (n(n+1)+1)^2
    // Row 4: 4^2 + 5^2 + 20^2 = 21^2
    const row4_rhs = Math.round(Math.sqrt(4*4 + 5*5 + 20*20)); // 21
    // Row 5: 9^2 + 10^2 + 90^2 = 91^2
    const row5_c = 9 * 10; // 90
    const row5_rhs = Math.round(Math.sqrt(9*9 + 10*10 + 90*90)); // 91
    return {
      truth: `\\(21^2\\) and \\(90^2, 91^2\\)`,
      matches: row4_rhs === 21 && row5_c === 90 && row5_rhs === 91
    };
  },
>>>>
```

---

## 3. Issue 2: E2E Test Suite Decoupling in `tests/e2e_square_cube_suite.js`

### 3.1 Problem Analysis & Test Façade Detection
- **Observation**: `tests/e2e_square_cube_suite.js` defines an embedded 618-line JavaScript array `AUTHORITATIVE_34_QUESTIONS` (lines 44–662) with custom IDs (`wu_01_it06`..`wu_12_it19`, `dd_01_fio11`..`dd_14_fio24`, `boss_01_it01`..`boss_08_puz02`).
- **Failure of Test Independence**:
  In `runSuite1_34QuestionsSpecValidation()` (lines 715–777):
  ```javascript
  AUTHORITATIVE_34_QUESTIONS.length === 34
  const warmup = AUTHORITATIVE_34_QUESTIONS.filter(q => q.tier === 'warmup');
  ...
  QuestionSchemaValidator.validateExerciseBank(AUTHORITATIVE_34_QUESTIONS, 'SquareCubeAuthoritativeBank');
  ```
  The test suite **never touches the repository deliverables on disk**!
  As a consequence:
  1. It passed 34/34 when `chapters/square_cube_questions.json` was unparseable due to a syntax error at line 300.
  2. It passed when `sc_q34` contained a critical Hint 1 answer leak.
  3. It passed when `sc_q28` contained a false mathematical statement.
  4. It never checked `content/contracts/Mathematics_Class8_squares_and_cubes.yaml` for consistency with the question bank.

### 3.2 Architectural Decoupling Plan
Suite 1 in `tests/e2e_square_cube_suite.js` must be refactored to validate the physical files:
1. **Dynamic File Ingestion**:
   - Locate and load `Aasha-AI/chapters/square_cube_questions.json`.
   - Assert file existence and valid JSON parsing (`JSON.parse` must not throw).
   - Extract `questions` array.
2. **Schema & Taxonomy Invariants on Physical File**:
   - Total question count: exactly 34.
   - 3-Tier partition counts: Warm-up = 12, Deep Dive = 14, Boss = 8.
   - For all 34 questions: 4 options, exactly 1 `c: true`, correct `m === ''`, distractor `m` non-empty and length $\ge 12$, hints `h1`–`h4` all present.
3. **Section 24 Contract Cross-Reconciliation**:
   - Locate and load `Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml`.
   - Verify YAML structure: `chapter_meta.topic: "Squares and Cubes"`, foundations F01, F02, F04, F08 present.
   - Extract all 34 question IDs from `assessment_suite.tiers` (`sc_q01`–`sc_q12`, `sc_q13`–`sc_q26`, `sc_q27`–`sc_q34`).
   - Verify 1:1 bidirectional mapping between the contract IDs and `square_cube_questions.json` IDs (zero missing, zero orphaned).
4. **Live Validator Execution on Physical File**:
   - Run `QuestionSchemaValidator.validateExerciseBank(questions, 'SquareCubeBank')` on the loaded JSON questions.
   - Assert `bankResult.passed === true`, `bankResult.spoilerViolations === 0`, and `bankResult.errors.length === 0`.

### 3.3 Concrete Code Implementation for `tests/e2e_square_cube_suite.js`
Replace `runSuite1_34QuestionsSpecValidation` in `tests/e2e_square_cube_suite.js` (lines 715–777):

```javascript
  // --------------------------------------------------------------------------
  // SUITE 1: 34 QUESTIONS GROUND TRUTH SPECIFICATION, CONTRACT & SCHEMA
  // --------------------------------------------------------------------------
  runSuite1_34QuestionsSpecValidation() {
    this.log('\n--- SUITE 1: 34 Questions Ground Truth Specification & Schema ---');

    // 1. Resolve and read chapters/square_cube_questions.json
    const questionsJsonPath = path.join(AASHA_DIR, 'chapters', 'square_cube_questions.json');
    this.assert(
      fs.existsSync(questionsJsonPath),
      `Deliverable questions file exists at: ${path.relative(ROOT_DIR, questionsJsonPath)}`
    );

    let parsedBank = null;
    let jsonParseError = null;
    try {
      const rawJson = fs.readFileSync(questionsJsonPath, 'utf8');
      parsedBank = JSON.parse(rawJson);
    } catch (err) {
      jsonParseError = err;
    }

    this.assert(
      !jsonParseError && parsedBank !== null,
      `square_cube_questions.json is valid, parseable JSON (${jsonParseError ? jsonParseError.message : 'Clean syntax'})`
    );

    const questions = parsedBank ? (parsedBank.questions || parsedBank) : [];

    // TC-S1-1: Total question count
    this.assert(
      questions.length === 34,
      `Authoritative question bank contains exactly 34 extracted items (got ${questions.length})`
    );

    // TC-S1-2: 3-Tier partition counts (12 Warm-up, 14 Deep Dive, 8 Boss)
    const warmup = questions.filter(q => q.tier === 'warmup');
    const deepDive = questions.filter(q => q.tier === 'deep_dive');
    const boss = questions.filter(q => q.tier === 'boss');

    this.assert(warmup.length === 12, `Tier 1 (Warm-Up) contains exactly 12 items (got ${warmup.length})`);
    this.assert(deepDive.length === 14, `Tier 2 (Deep Dive) contains exactly 14 items (got ${deepDive.length})`);
    this.assert(boss.length === 8, `Tier 3 (Boss Challenge) contains exactly 8 items (got ${boss.length})`);

    // TC-S1-3: Schema validation for every question
    let allValidSchema = true;
    let zeroSpoilerCompliant = true;
    let allHintsPresent = true;
    const jsonQuestionIds = new Set();

    questions.forEach(q => {
      jsonQuestionIds.add(q.id);
      // 4 options check
      if (!Array.isArray(q.opts) || q.opts.length !== 4) {
        allValidSchema = false;
      }
      // Exactly 1 correct option
      const correct = (q.opts || []).filter(o => o.c === true);
      if (correct.length !== 1) {
        allValidSchema = false;
      } else if (correct[0].m && correct[0].m.trim().length > 0) {
        zeroSpoilerCompliant = false;
      }
      // Distractors m non-empty > 11 chars
      const distractors = (q.opts || []).filter(o => o.c === false);
      distractors.forEach(d => {
        if (!d.m || d.m.trim().length <= 11) {
          zeroSpoilerCompliant = false;
        }
      });
      // 4 progressive hints present
      if (!q.hints || !q.hints.h1 || !q.hints.h2 || !q.hints.h3 || !q.hints.h4) {
        allHintsPresent = false;
      }
    });

    this.assert(allValidSchema, 'All 34 questions conform to 4-option single-correct MCQ schema');
    this.assert(zeroSpoilerCompliant, 'All distractors feature substantive misconception diagnostics (m > 11 chars) with empty correct m');
    this.assert(allHintsPresent, '100% of questions include complete 4-tier progressive hints (H1 -> H4)');

    // TC-S1-4: Section 24 YAML Content Contract Reconciliation
    const contractYamlPath = path.join(AASHA_DIR, 'content', 'contracts', 'Mathematics_Class8_squares_and_cubes.yaml');
    this.assert(
      fs.existsSync(contractYamlPath),
      `Section 24 Content Contract exists at: ${path.relative(ROOT_DIR, contractYamlPath)}`
    );

    if (fs.existsSync(contractYamlPath)) {
      const contractText = fs.readFileSync(contractYamlPath, 'utf8');
      const hasTopic = contractText.includes('topic: "Squares and Cubes"') || contractText.includes('squares_and_cubes');
      const hasFoundations = contractText.includes('F01') && contractText.includes('F02') && contractText.includes('F04') && contractText.includes('F08');
      this.assert(hasTopic && hasFoundations, 'Section 24 contract declares correct topic metadata and foundation bindings (F01, F02, F04, F08)');

      // Extract question IDs declared in YAML contract
      const yamlIdMatches = contractText.match(/-\s*["'](sc_q\d{2})["']/g) || [];
      const yamlIds = yamlIdMatches.map(m => m.replace(/[-\s"']/g, ''));
      const uniqueYamlIds = new Set(yamlIds);

      this.assert(
        uniqueYamlIds.size === 34,
        `Section 24 contract declares exactly 34 question IDs in assessment_suite (found ${uniqueYamlIds.size})`
      );

      let contractReconciled = uniqueYamlIds.size === 34;
      uniqueYamlIds.forEach(id => {
        if (!jsonQuestionIds.has(id)) contractReconciled = false;
      });
      this.assert(
        contractReconciled,
        '100% 1:1 question ID reconciliation between Section 24 contract and square_cube_questions.json (zero dropped or orphaned questions)'
      );
    }

    // TC-S1-5: Run QuestionSchemaValidator on entire physical bank
    if (QuestionSchemaValidator && questions.length > 0) {
      const bankResult = QuestionSchemaValidator.validateExerciseBank(questions, 'SquareCubeAuthoritativeBank');
      this.assert(
        bankResult.passed && bankResult.spoilerViolations === 0 && bankResult.errors.length === 0,
        `QuestionSchemaValidator certified 34 items with 0 spoiler violations (score: ${bankResult.score}/100, errors: ${bankResult.errors.length})`
      );
    }
  }
```

---

## 4. Issue 3: QuestionSchemaValidator Hardening

### 4.1 Vulnerability 1: Boolean Stopword Blindness
#### Root Cause
In `benchmarks/question_schema_validator.js` line 53 and `packages/aasha-rules/question_schema_validator.ts` line 105:
`const STOPWORDS = new Set([ ..., 'true', 'false' ]);`
When validating a True/False question:
- Correct option: `{ t: "False", c: true }`
- Distractor: `{ t: "True", c: false, m: "The statement is incorrect, the correct answer is False." }`
The validator checks `isStopword = STOPWORDS.has('false')`. Because `'false'` is in `STOPWORDS`, the entire verbatim check `RULE_1_SPOILER_VERBATIM_ANSWER` is skipped! And because `'false'` is non-numeric, numerical and phrase leak checks are also skipped.
The distractor openly announces the answer ("the correct answer is False"), and the validator awards 100/100 with 0 errors.

#### Hardening Solution
1. Retain `'true'` and `'false'` in `STOPWORDS` so innocent words ("It is true that...", "false assumption") do not trigger loose substring errors.
2. Introduce a dedicated, assertive **Boolean Leak Detector** in `validateDistractor`:
   - Triggers when `normCorrect` is `'true'` or `'false'`.
   - Uses `LEAK_PREDICATES` plus assertive assertions (`statement is`, `claim is`, `option is`, `answer is`, `actually`, `is actually`, `correct answer is`).
   - If distractor explanation asserts the target boolean answer with a leak predicate, flag `RULE_1_SPOILER_BOOLEAN_LEAK`.
3. Introduce matching boolean leak detection in `validateHints` (`RULE_12_HINT_SPOILER_BOOLEAN`).

### 4.2 Vulnerability 2: Adverb / Qualifier Evasion
#### Root Cause
In `benchmarks/question_schema_validator.js` line 190 and line 270 (and `packages/aasha-rules/question_schema_validator.ts`):
```javascript
const leakPattern = new RegExp(`(?:${LEAK_PREDICATES.join('|')})\\s*[:=]?\\s*${escapedN}\\b`, 'i');
```
This requires immediate zero-distance adjacency between the predicate and the number.
- `"giving a final total of 25"` -> evades because 4 words intervene.
- `"The result becomes approximately 25"` -> evades because `"approximately"` intervenes.
- `"The calculated output became exactly 25"` -> evades because `"exactly"` intervenes.
- `"Leaving a remainder of 25"` -> evades because 3 words intervene.
- `"This leads directly to 25"` -> evades because `"directly"` splits `"leads to"`.

#### Hardening Solution
1. For multi-word predicates like `"leads to"`, allow an optional adverb between the words: `replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')`.
2. Wrap predicate disjunction in word boundaries `\b` so substring words (e.g. `"is"` inside `"factorisation"`) cannot trigger false positive intervening matches.
3. Allow up to 4 intervening qualifier/adverb words between the leak predicate and the target number: `\\s*(?:[a-z]+\\s*){0,4}[:=]?\\s*\\b${escapedN}\\b`.
4. Apply this to both `validateDistractor` (rule 4c) and `validateHints`.

### 4.3 Concrete Implementation for `benchmarks/question_schema_validator.js`

#### Diff Block 1: `validateDistractor` Hardening (Lines 135–205)
```javascript
<<<<
    // 4. Zero-Spoiler Invariant
    if (!correctOption || !correctOption.t) return errors;

    const rawCorrect = String(correctOption.t).trim();
    const normCorrect = normalizeMathText(rawCorrect).toLowerCase();
    const normM = normalizeMathText(mText).toLowerCase();

    // 4a. Verbatim target answer inclusion (for non-pure-number terms, e.g. text/phrases/algebra)
    const isPureNumber = /^-?\d+(?:\.\d+)?$/.test(normCorrect);
    if (!isPureNumber && normCorrect.length > 0) {
      const isStopword = STOPWORDS.has(normCorrect);
      if (!isStopword) {
        let verbatimMatch = false;
        if (normCorrect.length >= 3) {
          verbatimMatch = normM.includes(normCorrect);
        } else {
          // For short non-number tokens (e.g. x, 2x), use word/boundary matching
          const shortRegex = new RegExp(`(?:^|[\\s,;:(])${escapeRegex(normCorrect)}(?:$|[\\s,;:).!?])`, 'i');
          verbatimMatch = shortRegex.test(normM);
        }

        if (verbatimMatch) {
          errors.push({
            questionId: qId,
            ruleId: 'RULE_1_SPOILER_VERBATIM_ANSWER',
            severity: 'ERROR',
            message: `Rule #1 Spoiler: Distractor #${optIdx + 1} ('${option.t}') leaks the verbatim correct answer text '${rawCorrect}' in its explanation: "${mText}".`,
            context: qContext
          });
          return errors;
        }
      }
    }

    // 4b. Fraction answer leakage (e.g. -2/3 or -\frac{2}{3})
    const fracMatch = normCorrect.match(/^(-?\d+)\s*\/\s*(\d+)$/);
    if (fracMatch) {
      const num = fracMatch[1];
      const den = fracMatch[2];
      const fracRegex = new RegExp(`(?:${LEAK_PREDICATES.join('|')})?\\s*[:=]?\\s*${escapeRegex(num)}\\s*\\/\\s*${escapeRegex(den)}\\b`, 'i');
      if (fracRegex.test(normM)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_1_SPOILER_FRACTION_LEAK',
          severity: 'ERROR',
          message: `Rule #1 Spoiler: Distractor #${optIdx + 1} reveals the target fraction '${rawCorrect}' in explanation: "${mText}".`,
          context: qContext
        });
        return errors;
      }
    }

    // 4c. Numerical value leakage patterns with comprehensive leak predicates
    const nums = normCorrect.match(/-?\d+(?:\.\d+)?/g) || [];
    for (const n of nums) {
      const escapedN = escapeRegex(n);
      const leakPattern = new RegExp(`(?:${LEAK_PREDICATES.join('|')})\\s*[:=]?\\s*${escapedN}\\b`, 'i');
      if (leakPattern.test(normM)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_1_SPOILER_NUMERICAL_LEAK',
          severity: 'ERROR',
          message: `Rule #1 Spoiler: Distractor #${optIdx + 1} explicitly reveals target numerical value '${n}' in explanation: "${mText}".`,
          context: qContext
        });
        return errors;
      }
    }
====
    // 4. Zero-Spoiler Invariant
    if (!correctOption || !correctOption.t) return errors;

    const rawCorrect = String(correctOption.t).trim();
    const normCorrect = normalizeMathText(rawCorrect).toLowerCase();
    const normM = normalizeMathText(mText).toLowerCase();

    // 4a. Boolean stopword bypass hardening (True / False answer leak detection)
    const isBooleanTarget = /^(?:true|false)$/i.test(normCorrect);
    if (isBooleanTarget) {
      const boolLeakRegex = new RegExp(
        '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + '|statement\\s+is|claim\\s+is|option\\s+is|actually)\\b)\\s*(?:[a-z]+\\s*){0,3}[:=]?\\s*\\b' + escapeRegex(normCorrect) + '\\b',
        'i'
      );
      if (boolLeakRegex.test(normM)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_1_SPOILER_BOOLEAN_LEAK',
          severity: 'ERROR',
          message: `Rule #1 Spoiler: Distractor #${optIdx + 1} ('${option.t}') reveals target boolean answer '${rawCorrect}' in explanation: "${mText}".`,
          context: qContext
        });
        return errors;
      }
    }

    // 4b. Verbatim target answer inclusion (for non-pure-number terms, e.g. text/phrases/algebra)
    const isPureNumber = /^-?\d+(?:\.\d+)?$/.test(normCorrect);
    if (!isPureNumber && normCorrect.length > 0) {
      const isStopword = STOPWORDS.has(normCorrect);
      if (!isStopword) {
        let verbatimMatch = false;
        if (normCorrect.length >= 3) {
          verbatimMatch = normM.includes(normCorrect);
        } else {
          // For short non-number tokens (e.g. x, 2x), use word/boundary matching
          const shortRegex = new RegExp(`(?:^|[\\s,;:(])${escapeRegex(normCorrect)}(?:$|[\\s,;:).!?])`, 'i');
          verbatimMatch = shortRegex.test(normM);
        }

        if (verbatimMatch) {
          errors.push({
            questionId: qId,
            ruleId: 'RULE_1_SPOILER_VERBATIM_ANSWER',
            severity: 'ERROR',
            message: `Rule #1 Spoiler: Distractor #${optIdx + 1} ('${option.t}') leaks the verbatim correct answer text '${rawCorrect}' in its explanation: "${mText}".`,
            context: qContext
          });
          return errors;
        }
      }
    }

    // 4c. Fraction answer leakage (e.g. -2/3 or -\frac{2}{3})
    const fracMatch = normCorrect.match(/^(-?\d+)\s*\/\s*(\d+)$/);
    if (fracMatch) {
      const num = fracMatch[1];
      const den = fracMatch[2];
      const fracRegex = new RegExp(`(?:${LEAK_PREDICATES.join('|')})?\\s*[:=]?\\s*${escapeRegex(num)}\\s*\\/\\s*${escapeRegex(den)}\\b`, 'i');
      if (fracRegex.test(normM)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_1_SPOILER_FRACTION_LEAK',
          severity: 'ERROR',
          message: `Rule #1 Spoiler: Distractor #${optIdx + 1} reveals the target fraction '${rawCorrect}' in explanation: "${mText}".`,
          context: qContext
        });
        return errors;
      }
    }

    // 4d. Numerical value leakage patterns with adverb/modifier tolerance (up to 4 qualifier words)
    const nums = normCorrect.match(/-?\d+(?:\.\d+)?/g) || [];
    for (const n of nums) {
      const escapedN = escapeRegex(n);
      const leakPattern = new RegExp(
        '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + ')\\b)\\s*(?:[a-z]+\\s*){0,4}[:=]?\\s*\\b' + escapedN + '\\b',
        'i'
      );
      if (leakPattern.test(normM)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_1_SPOILER_NUMERICAL_LEAK',
          severity: 'ERROR',
          message: `Rule #1 Spoiler: Distractor #${optIdx + 1} explicitly reveals target numerical value '${n}' in explanation: "${mText}".`,
          context: qContext
        });
        return errors;
      }
    }
>>>>
```

#### Diff Block 2: `validateHints` Hardening (Lines 240–285)
```javascript
<<<<
    hintList.forEach((hintText, hIdx) => {
      const normH = normalizeMathText(hintText).toLowerCase();

      // Check verbatim leakage across all tiers (including Tier 4 procedural step)
      if (normCorrect.length > 0 && !isStopword) {
        let verbatimHint = false;
        if (normCorrect.length >= 3) {
          verbatimHint = normH.includes(normCorrect);
        } else {
          const shortRegex = new RegExp(`(?:^|[\\s,;:(])${escapeRegex(normCorrect)}(?:$|[\\s,;:).!?])`, 'i');
          verbatimHint = shortRegex.test(normH);
        }

        if (verbatimHint) {
          errors.push({
            questionId: qContext,
            ruleId: 'RULE_12_HINT_SPOILER',
            severity: 'ERROR',
            message: `Progressive Hint Tier ${hIdx + 1} leaks target answer '${correctOption.t}' in: "${hintText}".`,
            context: qContext
          });
        }
      }

      // Check numerical value leakage with leak predicates
      for (const n of nums) {
        const escapedN = escapeRegex(n);
        const leakPattern = new RegExp(`(?:${LEAK_PREDICATES.join('|')})\\s*[:=]?\\s*${escapedN}\\b`, 'i');
        if (leakPattern.test(normH)) {
          errors.push({
            questionId: qContext,
            ruleId: 'RULE_12_HINT_SPOILER_VALUE',
            severity: 'ERROR',
            message: `Progressive Hint Tier ${hIdx + 1} reveals answer value '${n}' in: "${hintText}".`,
            context: qContext
          });
        }
      }
    });
====
    const isBooleanTarget = /^(?:true|false)$/i.test(normCorrect);

    hintList.forEach((hintText, hIdx) => {
      const normH = normalizeMathText(hintText).toLowerCase();

      // Check boolean answer leakage in hints
      if (isBooleanTarget) {
        const boolHintPattern = new RegExp(
          '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + '|statement\\s+is|claim\\s+is|option\\s+is|actually)\\b)\\s*(?:[a-z]+\\s*){0,3}[:=]?\\s*\\b' + escapeRegex(normCorrect) + '\\b',
          'i'
        );
        if (boolHintPattern.test(normH)) {
          errors.push({
            questionId: qContext,
            ruleId: 'RULE_12_HINT_SPOILER_BOOLEAN',
            severity: 'ERROR',
            message: `Progressive Hint Tier ${hIdx + 1} reveals boolean answer '${correctOption.t}' in: "${hintText}".`,
            context: qContext
          });
        }
      }

      // Check verbatim leakage across all tiers (including Tier 4 procedural step)
      if (normCorrect.length > 0 && !isStopword) {
        let verbatimHint = false;
        if (normCorrect.length >= 3) {
          verbatimHint = normH.includes(normCorrect);
        } else {
          const shortRegex = new RegExp(`(?:^|[\\s,;:(])${escapeRegex(normCorrect)}(?:$|[\\s,;:).!?])`, 'i');
          verbatimHint = shortRegex.test(normH);
        }

        if (verbatimHint) {
          errors.push({
            questionId: qContext,
            ruleId: 'RULE_12_HINT_SPOILER',
            severity: 'ERROR',
            message: `Progressive Hint Tier ${hIdx + 1} leaks target answer '${correctOption.t}' in: "${hintText}".`,
            context: qContext
          });
        }
      }

      // Check numerical value leakage with leak predicates and adverb/qualifier tolerance
      for (const n of nums) {
        const escapedN = escapeRegex(n);
        const leakPattern = new RegExp(
          '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + ')\\b)\\s*(?:[a-z]+\\s*){0,4}[:=]?\\s*\\b' + escapedN + '\\b',
          'i'
        );
        if (leakPattern.test(normH)) {
          errors.push({
            questionId: qContext,
            ruleId: 'RULE_12_HINT_SPOILER_VALUE',
            severity: 'ERROR',
            message: `Progressive Hint Tier ${hIdx + 1} reveals answer value '${n}' in: "${hintText}".`,
            context: qContext
          });
        }
      }
    });
>>>>
```

### 4.4 Matching Implementation for TypeScript Source: `packages/aasha-rules/question_schema_validator.ts`
Apply the identical regex logic to `packages/aasha-rules/question_schema_validator.ts` inside `validateDistractor` (lines 191–260) and `validateHints` (lines 300–340).

### 4.5 Unit Test Suite Expansion for `tests/test_question_schema_validator.js`
Append the following two unit tests to `Aasha-AI/tests/test_question_schema_validator.js`:

```javascript
// Test 14: Boolean stopword blindness hardening
{
  const boolLeakQ = {
    id: 'test_bool_leak',
    q: 'State whether the statement is True or False: All square numbers are even.',
    opts: [
      { t: 'False', c: true, m: '' },
      { t: 'True', c: false, m: 'The statement is incorrect, the correct answer is False.' }
    ]
  };

  const errors = QuestionSchemaValidator.validateQuestion(boolLeakQ);
  const hasBoolLeak = errors.some(e => e.ruleId === 'RULE_1_SPOILER_BOOLEAN_LEAK');
  assert.strictEqual(hasBoolLeak, true, 'Expected RULE_1_SPOILER_BOOLEAN_LEAK error for boolean spoiler');
  console.log('  [PASS] Boolean stopword blindness hardening verified.');
}

// Test 15: Intervening adverb and modifier evasion hardening
{
  const adverbVectors = [
    { m: 'giving a final total of 25.', n: '25' },
    { m: 'The result becomes approximately 25', n: '25' },
    { m: 'The calculated output became exactly 25', n: '25' },
    { m: 'Leaving a remainder of 25', n: '25' },
    { m: 'This leads directly to 25', n: '25' }
  ];

  adverbVectors.forEach((vec, idx) => {
    const advQ = {
      id: `test_adv_leak_${idx}`,
      q: 'Evaluate 5 squared.',
      opts: [
        { t: '25', c: true, m: '' },
        { t: '50', c: false, m: vec.m }
      ]
    };
    const errors = QuestionSchemaValidator.validateQuestion(advQ);
    const hasLeak = errors.some(e => e.ruleId === 'RULE_1_SPOILER_NUMERICAL_LEAK');
    assert.strictEqual(hasLeak, true, `Expected numerical leak caught for: "${vec.m}"`);
  });
  console.log('  [PASS] Intervening adverb/modifier evasion hardening verified across all 5 vectors.');
}
```

---

## 5. Verification Method & Success Criteria

The implementing agent (`worker_fix_and_build_r2`) must verify the complete remediation using the following exact sequence:

1. **Verify Question Schema Validator Unit Tests**:
   ```powershell
   cd "C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI"
   node tests/test_question_schema_validator.js
   ```
   *Expected Output*: Exits with code 0, 15/15 tests passing, including Boolean Hardening and Adverb Evasion.

2. **Verify Milestone 1 Validator Benchmark**:
   ```powershell
   node benchmarks/test_square_cube_validator.js
   ```
   *Expected Output*: Exits with code 0, 34/34 questions passed, 0 errors, 0 spoilers, score 100/100.

3. **Verify Mathematical Oracle**:
   ```powershell
   node benchmarks/test_square_cube_math_oracle.js
   ```
   *Expected Output*: Exits with code 0, 34/34 questions mathematically verified, including `sc_q28` matching `\(21^2\) and \(90^2, 91^2\)`.

4. **Verify Comprehensive E2E Suite**:
   ```powershell
   cd "C:\Users\admin\Downloads\NGO AI LLM"
   node tests/e2e_square_cube_suite.js
   ```
   *Expected Output*: Exits with code 0, 35/35 assertions passed, Suite 1 verifying the physical `square_cube_questions.json` and Section 24 YAML contract.
