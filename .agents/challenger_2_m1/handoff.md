# Milestone 1 Adversarial Challenge Report & Verdict
**Agent**: `challenger_2_m1` (Empirical Challenger / Critic & Specialist)  
**Target Workspace**: `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`  
**Date**: 2026-09-18T23:22:00Z  
**Verdict**: **REJECT** (Gated on remediating `sc_q34` H1 premature spoiler and `QuestionSchemaValidator` boolean blind spot)

---

## Challenge Summary

- **Target Artifacts**:
  - `chapters/square_cube_questions.json` (34 questions, 102 distractors)
  - `content/contracts/Mathematics_Class8_squares_and_cubes.yaml`
  - `packages/aasha-rules/question_schema_validator.ts` / `benchmarks/question_schema_validator.js`
- **Overall Risk Assessment**: **MEDIUM to HIGH**
  - While the textbook exercise mapping (34 items), mathematical correctness (100%), and distractor pedagogical rationales (`opt.m` > 15 chars, zero discouraging language) are exceptionally strong, empirical mutation testing identified **two critical bypasses in the validator** and **one critical premature spoiler in `sc_q34` Hint 1**.

---

## 1. Observation

### Obs 1: Mutation Testing Against `QuestionSchemaValidator` (30 Vectors Executed)
We executed a 30-vector adversarial mutation suite testing leak predicates, phrase proximity, LaTeX units, negative numbers, capitalization, and trivial placeholders.
- **Predicates successfully caught** (29/30): `is`, `was`, `=`, `becomes`, `giving`, `gives`, `yields`, `yielding`, `produces`, `leads to`, `should be`, `must be`, `to get`, `instead of`, `result is`, `the result is`, `the correct answer is`, `BECOMES` (uppercase), `Yields` (capitalized), `\text{ m}` units, negative integers (`-8`), and multi-number answers (`30 and 22`).
- **FAILED CATCH 1 (Intervening Adverbs/Modifiers)**:
  `m: "giving a final total of 25."` (with target "25") returned `caught: false, errors: []`.
  `m: "The result becomes approximately 25"` returned `errors: []`.
  `m: "The calculated output became exactly 25"` returned `errors: []`.
  `m: "Leaving a remainder of 25"` returned `errors: []`.
  `m: "This leads directly to 25"` returned `errors: []`.
  *Root Cause*: `LEAK_PREDICATES` regex in lines 246-247 of `benchmarks/question_schema_validator.js` strictly requires `(?:${LEAK_PREDICATES.join('|')})\\s*[:=]?\\s*${escapedN}\\b` with 0 intervening words. Any adverb or qualifier breaks the match.
- **FAILED CATCH 2 (Boolean Stopword Blindness)**:
  `optCorrect = { t: "False", c: true };`
  `optLeak = { t: "True", c: false, m: "The statement is incorrect, the correct answer is False." };`
  Returned: `[]` (0 errors!).
  *Root Cause*: Lines 53-55: `'true'` and `'false'` are defined in `STOPWORDS`. Line 201: `const isStopword = STOPWORDS.has(normCorrect);` evaluates to `true`, completely skipping `RULE_1_SPOILER_VERBATIM_ANSWER`. Because "False" is not numeric, numerical leak and phrase leak checks also do not trigger.

### Obs 2: Scaffolding Leak in `chapters/square_cube_questions.json` (`sc_q34`)
- **File**: `chapters/square_cube_questions.json`, Lines 1205–1239
- **Question Prompt**:
  ```json
  "q": "The taxicab number \\(4104\\) can be expressed as the sum of two cubes in two different ways: \\(2^3 + 16^3\\) and which other pair of cubes?",
  "ans": "\\(9^3 + 15^3\\)",
  ```
- **Options**:
  - Option 1 (c: true): `\\(9^3 + 15^3\\)`
  - Option 2 (c: false): `\\(10^3 + 14^3\\)`
  - Option 3 (c: false): `\\(8^3 + 16^3\\)`
  - Option 4 (c: false): `\\(11^3 + 13^3\\)`
- **Verbatim Hint Progression**:
  ```json
  "hints": {
    "h1": "Compute the cubes: 9 cubed equals 729 and 15 cubed equals 3375.",
    "h2": "Add 729 and 3375 together.",
    "h3": "Verify that the sum matches 4104.",
    "h4": "Confirm that this forms the second Ramanujan partition for 4104."
  }
  ```
- **Violation**:
  Hint 1 ($H_1$), which is mandated to be an *attention hook*, immediately gives away the exact target pair: `9 cubed equals 729 and 15 cubed equals 3375`. The learner does not need to analyze units digits, bound the search, or test candidates; Option 1 is revealed directly in the first hint.
  *Why validator missed it*: The option is formatted as `\(9^3 + 15^3\)` while $H_1$ uses words `"9 cubed"` and `"15 cubed"`. Neither verbatim equality nor numerical leak predicates matched.

### Obs 3: Degraded Hint Scaffolding in `sc_q31`
- **File**: `chapters/square_cube_questions.json`, Lines 1097–1131
- **Question Prompt**:
  `"In the 'Square Pairs' circle of numbers from \\(1\\) to \\(32\\), which of the following represents a valid adjacent pair whose sum is a perfect square?"`
- **Options**:
  - Option 1 (c: true): `\\(32\\) and \\(17\\) (sum \\(= 49\\))`
  - Option 2 (c: false): `\\(32\\) and \\(18\\) (sum \\(= 50\\))`
  - Option 3 (c: false): `\\(32\\) and \\(16\\) (sum \\(= 48\\))`
  - Option 4 (c: false): `\\(32\\) and \\(20\\) (sum \\(= 52\\))`
- **Hint 3**:
  `"h3": "Evaluate 32 plus 17 and test whether it matches 7 squared."`
- **Observation**:
  Hint 3 singles out Option 1 (`32 plus 17`) rather than providing a strategy to test candidate sums against the set of squares {36, 49, 64}.

### Obs 4: Mathematical Oracle Verification (All 34 Questions)
We constructed an independent mathematical verification oracle in JavaScript and tested every single question:
- 34/34 questions (100%) have mathematically verified answers.
- 0 duplicate options across all 34 questions.
- 0 mathematical equivalence collisions between distractors and correct options.
- 102/102 distractors have non-empty, constructive rationales > 15 characters (average length: 82 characters).
- 0 instances of discouraging or negative phrasing (`❌ incorrect`, `wrong`, etc.).
- 34/34 question-level misconceptions (`q.m`) contain zero answer spoilers.

---

## 2. Logic Chain

1. **Premise 1 (Anti-Spoiler & Scaffolding Invariant)**: PROJECT.md Section "Interface Contracts" and GEMINI.md Anti-Spoiler Assessment Invariant mandate that progressive hints ($H_1 \to H_4$) must scaffold attention, relationship, strategy, and intermediate procedure with **zero answer spoilers**.
2. **Step 2 (Empirical Finding)**: In `sc_q34`, Hint 1 ($H_1$) explicitly states: `"Compute the cubes: 9 cubed equals 729 and 15 cubed equals 3375."` This directly reveals the correct answer components (`9` and `15`) in the very first hint.
3. **Step 3 (Validator Failure)**: `QuestionSchemaValidator` evaluated `chapters/square_cube_questions.json` and scored it 100/100, failing to catch the spoiler in `sc_q34` H1 because of syntactic mismatch (`\(9^3 + 15^3\)` vs `"9 cubed"`).
4. **Step 4 (Validator Blind Spot Proof)**: By injecting `"The statement is incorrect, the correct answer is False."` into a True/False distractor, we proved that `QuestionSchemaValidator` has an architectural blind spot due to `'false'` being included in `STOPWORDS`.
5. **Conclusion**: Because `sc_q34` contains a direct answer giveaway in Hint 1, and the gatekeeping validator possesses exploitable blind spots, Milestone 1 cannot be certified in its current state.

---

## 3. Caveats

- **DOM Rendering & Visual Simulations**: Interactive canvas manipulative behaviors (2D square grid, 3D isometric stacker, prime factor tree, 100-locker explorer) belong to Milestone 2 and were not evaluated in this assessment bank audit.
- **Section 24 Contract Structure**: `content/contracts/Mathematics_Class8_squares_and_cubes.yaml` is structurally complete, has valid foundations (F01, F02, F04, F08), and contains zero spoiler leaks in its general misconception schemas.

---

## 4. Conclusion & Actionable Recommendations

**Verdict**: **REJECT** (Request Changes).

To achieve **APPROVE**, the worker must complete the following concrete fixes:

### Remediation 1: Fix `sc_q34` Hint Scaffolding (`chapters/square_cube_questions.json:1234-1238`)
Replace the existing hints with true pedagogical scaffolding:
```json
"hints": {
  "h1": "Observe that the target sum 4104 terminates in the digit 4.",
  "h2": "Since 16 cubed equals 4096, both unknown cubes must have bases strictly less than 16.",
  "h3": "Identify which pair of cubic units digits sum to a value terminating in 4 (such as digits ending in 9 and 5).",
  "h4": "Evaluate the cubic sum of the candidate bases below 16 that end in 9 and 5: test 9 cubed plus 15 cubed."
}
```

### Remediation 2: Refine `sc_q31` Hint 3 (`chapters/square_cube_questions.json:1128`)
Replace `h3` to scaffold strategy rather than naming Option A:
```json
"h3": "Test each candidate sum (48, 49, 50, 52) against the nearest square numbers.",
"h4": "Notice that 49 equals 7 squared, confirming the valid square-sum pair."
```

### Remediation 3: Patch `QuestionSchemaValidator` Boolean & Adverb Blind Spots
In `packages/aasha-rules/question_schema_validator.ts` (and `benchmarks/question_schema_validator.js`):
1. Remove `'true'` and `'false'` from `STOPWORDS`, or add an explicit check for boolean spoilers:
   ```js
   if (/^(?:true|false)$/i.test(normCorrect)) {
     const boolLeak = new RegExp(`(?:${LEAK_PREDICATES.join('|')})\\s*[:=]?\\s*${normCorrect}\\b`, 'i');
     if (boolLeak.test(normM)) { /* report error */ }
   }
   ```
2. In `leakPattern`, allow up to 2 intervening words between predicate and number:
   ```js
   const leakPattern = new RegExp(`(?:${LEAK_PREDICATES.join('|')})\\s*(?:[a-z]+\\s*){0,2}[:=]?\\s*${escapedN}\\b`, 'i');
   ```

---

## 5. Verification Method

To independently verify these empirical findings:

1. **Verify `sc_q34` Hint 1 Giveaway**:
   Inspect lines 1208–1238 of `chapters/square_cube_questions.json`. Compare the prompt and options to Hint 1.
2. **Verify Boolean Blind Spot**:
   Run the following snippet in Node.js:
   ```js
   const { QuestionSchemaValidator } = require('./benchmarks/question_schema_validator.js');
   const optCorrect = { t: "False", c: true };
   const optDistractor = { t: "True", c: false, m: "The statement is incorrect, the correct answer is False." };
   const errs = QuestionSchemaValidator.validateDistractor(optDistractor, optCorrect, "TEST_TF", 1);
   console.log('Errors detected:', errs.length); // Prints 0 (FAILED CATCH)
   ```
3. **Verify Adverb Evasion**:
   ```js
   const optCorrect = { t: "25", c: true };
   const optDistractor = { t: "50", c: false, m: "The base was halved so it becomes approximately 25." };
   const errs = QuestionSchemaValidator.validateDistractor(optDistractor, optCorrect, "TEST_ADV", 1);
   console.log('Errors detected:', errs.length); // Prints 0 (FAILED CATCH)
   ```
4. **Verify Invalidation Condition**:
   Once the recommended hint revisions are applied and the validator patches are deployed, the 30-vector mutation suite must score 30/30 (100% detection) and `chapters/square_cube_questions.json` must exhibit zero premature answer disclosures across all 34 questions.
