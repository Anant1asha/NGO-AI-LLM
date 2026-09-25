# Pedagogical Remediation Plan: Zero-Spoiler Scaffolding & Distractor Invariant
**Chapter**: Class 8 Mathematics — Squares and Cubes (`chapters/square_cube_questions.json`)  
**Author**: `explorer_fix_spoilers_and_hints_r2` (Remediation Explorer)  
**Target Workspace**: `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`  
**Standard**: AASHA Rule #1 & L-Truth Zero-Spoiler Assessment Invariant  
**Date**: 2026-09-19T04:56:00Z  

---

## 1. Executive Summary

A forensic pedagogical investigation was conducted across `Aasha-AI/chapters/square_cube_questions.json` (34 questions, 102 distractors, 136 hints) guided by the audit reports from `reviewer_2_m1`, `challenger_2_m1`, and `auditor_m1`.

The investigation confirmed **5 categories of pedagogical defects**:
1. **Premature Answer Giveaway in Hint 1 (`sc_q34`)**: Hint 1 directly names target numbers 9 and 15 and evaluates their cubes ($9^3 = 729, 15^3 = 3375$), eliminating student problem-solving before they begin.
2. **Singling Out Option Candidates (`sc_q31`)**: Hint 3 explicitly names candidate 17 and sum 49 out of four multiple-choice options.
3. **Discriminatory Keyword Leakage (`sc_q30`)**: Hint 4 quotes the specific distinguishing keyword `"degree 1"`, which uniquely matches the correct option text.
4. **Direct Arithmetic Evaluation Leaks in Tier 4 Hints (`sc_q21`, `sc_q13`, `sc_q15`, `sc_q22`, `sc_q27`)**: Hint 4 performs exact arithmetic computations ($1225+71=1296$, $125+126=251$, $2\times 16=32$, $2\times 12=24$, $180\times 5=900$) that evaluate directly to the target answer.
5. **Distractor Misconception Leaking Target Factor (`sc_q17`)**: Distractor 3 (`9`) states *"rather than completing the power of 7"*, disclosing the winning factor 7.
6. **Auxiliary Defects**:
   - **Syntax Error (`sc_q08` Line 300)**: Missing trailing comma after `"h3": "Compute the cube of 100: 100 cubed has seven digits."`.
   - **Mathematically False Equality (`sc_q28`)**: Option text asserts $90^2 = 91^2$ ($8100 = 8281$) instead of listing missing terms as $21^2$ and $90^2, 91^2$.
   - **Advisory Scaffolding Leak (`sc_q16`)**: Hints 3 & 4 reveal $1000$ and $2^3 \times 5^3$.

This plan provides **exact, drop-in replacement strings** and **unified git diffs** for every defect, guaranteeing 100% compliance with L-Truth and `QuestionSchemaValidator`.

---

## 2. Remediation Specifications

### Item 1: `sc_q34` — Eliminating Premature Hint 1 Spoiler
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:1205-1239`
- **Tag**: `NCERT Taxicab Numbers p.13` (Tier: `boss`)
- **Question**:
  `"The taxicab number \\(4104\\) can be expressed as the sum of two cubes in two different ways: \\(2^3 + 16^3\\) and which other pair of cubes?"`
- **Target Answer**: `"\\(9^3 + 15^3\\)"`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Compute the cubes: 9 cubed equals 729 and 15 cubed equals 3375.",
    "h2": "Add 729 and 3375 together.",
    "h3": "Verify that the sum matches 4104.",
    "h4": "Confirm that this forms the second Ramanujan partition for 4104."
  }
  ```
- **Violation**: Hint 1 immediately reveals the target numbers 9 and 15 and gives their cubic values. Hint 2 directs adding them, and Hint 3 states the sum 4104. This is a complete answer walkthrough that destroys pedagogical value.
- **Pedagogical Solution**:
  - $H_1$ (Hook): Focus attention on the units digit ($4104$ terminates in $4$).
  - $H_2$ (Concept/Bounds): Since $16^3 = 4096 \approx 4104$, both bases in the second pair must be positive integers strictly below $16$.
  - $H_3$ (Strategy): Identify which pairs of units digits for natural cubes sum to a units digit of $4$ (such as cubes ending in $9$ and $5$).
  - $H_4$ (Checkpoint): Test candidate base pairs below $16$ ending in those units digits by summing their cubic values to reach $4104$.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Observe the units digit of the target taxicab sum: 4104 terminates in the digit 4.",
    "h2": "Because 16 cubed equals 4096, any other two cubes summing to 4104 must have positive integer bases strictly below 16.",
    "h3": "Analyze which pairs of units digits for natural cubes sum to a units digit of 4, such as single digits ending in 9 and 5.",
    "h4": "Identify candidate base pairs below 16 that match those ending digits, and sum their cubic values to find the combination reaching 4104."
  }
  ```

---

### Item 2: `sc_q31` — Scaffolding Candidate Range Instead of Singling Out 17
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:1097-1131`
- **Tag**: `NCERT Extension Puzzle 2 p.18` (Tier: `boss`)
- **Question**:
  `"In the 'Square Pairs' circle of numbers from \\(1\\) to \\(32\\), which of the following represents a valid adjacent pair whose sum is a perfect square?"`
- **Target Answer**: `"\\(32\\) and \\(17\\) (sum \\(= 49\\))"`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Calculate the sum of each pair: 32 plus candidate.",
    "h2": "Check which sum appears in the list of perfect squares: 36, 49, 64.",
    "h3": "Evaluate 32 plus 17 and test whether it matches 7 squared.",
    "h4": "Confirm that 49 is a perfect square."
  }
  ```
- **Violation**: Hint 3 explicitly names candidate 17 out of the four options (`17, 18, 16, 20`), and Hint 4 confirms 49, removing the need to evaluate any other options.
- **Pedagogical Solution**:
  - $H_1$ (Hook): State the criterion for adjacent pairs in the circle: their sum must be a perfect square.
  - $H_2$ (Bounds): Adding 32 to the option candidates yields sums strictly between 48 and 52.
  - $H_3$ (Strategy): Inspect the sequence of nearby squares ($6^2 = 36, 7^2 = 49, 8^2 = 64$) to locate the square falling in that range.
  - $H_4$ (Checkpoint): Identify which square falls in the [48, 52] interval and select the candidate pair that reaches that total.
- **Replacement**:
  ```json
  "hints": {
    "h1": "In the square pairs arrangement, two adjacent numbers form a valid pair if and only if their sum equals a perfect square.",
    "h2": "With 32 as the fixed number, summing with the given options produces totals lying strictly between 48 and 52.",
    "h3": "Consider the sequence of consecutive perfect squares in this neighborhood: 6 squared (36), 7 squared (49), and 8 squared (64).",
    "h4": "Determine which integer square falls within the interval from 48 to 52, and select the candidate pair that reaches that total."
  }
  ```

---

### Item 3: `sc_q30` — Removing Discriminatory Keyword "degree 1"
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:1061-1095`
- **Tag**: `NCERT Extension Puzzle 1 p.18` (Tier: `boss`)
- **Question**:
  `"In the 'Square Pairs' challenge for numbers \\(1\\) to \\(17\\), adjacent pairs must sum to a square. Why must \\(16\\) and \\(17\\) be the two endpoints of the row?"`
- **Target Answer**: `"In the square-sum connectivity graph, \\(16\\) and \\(17\\) each connect to only one other number (degree \\(1\\))."`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Find all numbers from 1 to 17 that can add with 16 to form a square.",
    "h2": "Notice 16 can only pair with 9 (to make 25); no other number from 1 to 17 works.",
    "h3": "Check 17: it can only pair with 8 (to make 25); no other number from 1 to 17 works.",
    "h4": "Any vertex with degree 1 must be placed at an end of a non-branching row."
  }
  ```
- **Violation**: Hint 4 quotes the unique identifying phrase `"degree 1"`, which appears verbatim only in the correct option. A student can match the keyword without conceptual understanding.
- **Pedagogical Solution**:
  - $H_1$ (Hook): Count how many compatible partners in $\{1, \dots, 17\}$ can add with 16 to produce a square.
  - $H_2$ (Verification): Show that 16 pairs only with 9 ($16+9=25$).
  - $H_3$ (Verification): Show that 17 pairs only with 8 ($17+8=25$).
  - $H_4$ (Checkpoint): Explain the topological principle: in a linear row where every interior position requires two adjacent neighbors, any number possessing only a single valid partner cannot sit in the interior and must terminate the row.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Count how many compatible partner numbers from 1 to 17 can add with 16 to form a perfect square.",
    "h2": "Notice that 16 can only pair with 9 (16 + 9 = 25); no other integer in the set produces an allowed square sum.",
    "h3": "Similarly test 17: it can only pair with 8 (17 + 8 = 25) to form an allowed square sum.",
    "h4": "In a linear chain where every internal member must connect to two neighbors, any number possessing only a single valid partner cannot sit in the interior and must form an endpoint."
  }
  ```

---

### Item 4: `sc_q21` — Removing Evaluation Leak ($1225 + 71$)
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:737-770`
- **Tag**: `NCERT In-Text p.6` (Tier: `deep_dive`)
- **Question**:
  `"Given that \\(35^2 = 1225\\), find \\(36^2\\) using the consecutive odd numbers summation method."`
- **Target Answer**: `"\\(1296\\)"`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Recall that 35 squared represents the sum of the first 35 odd natural numbers.",
    "h2": "To obtain 36 squared, add the 36th odd natural number to 1225.",
    "h3": "Find the 36th odd number using the formula 2n - 1 with n denoting 36.",
    "h4": "Add 71 to 1225 to determine the value."
  }
  ```
- **Violation**: Hint 4 calculates $2(36) - 1 = 71$ and instructs the student: `"Add 71 to 1225 to determine the value."` Adding $1225 + 71$ yields $1296$, the exact target answer.
- **Pedagogical Solution**:
  - $H_3$ states the formula $2n - 1$ for the $n$-th odd number ($n=36$).
  - $H_4$ instructs the student to calculate that specific odd number and add it to 1225, without evaluating 71 or the sum.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Recall that the square of any natural number n represents the sum of the first n consecutive odd natural numbers.",
    "h2": "Because 35 squared is the sum of the first 35 odd numbers, obtaining 36 squared requires adding the 36th odd number to 1225.",
    "h3": "Express the nth odd natural number using the general relation 2n - 1, setting n equal to 36.",
    "h4": "Calculate the value of that 36th odd number and add it to 1225 to find the next square."
  }
  ```

---

### Item 5: `sc_q13` — Removing Assembly Leak ($125 + 126 = 251$)
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:449-483`
- **Tag**: `NCERT Fig It Out 1.3 p.10` (Tier: `deep_dive`)
- **Question**:
  `"Given that \\(125^2 = 15625\\), what is the value of \\(126^2\\) using the consecutive squares property?"`
- **Target Answer**: `"\\(15625 + 251\\)"`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Recall the algebraic identity: (n + 1) squared equals n squared plus 2n plus 1.",
    "h2": "The difference between consecutive squares equals n plus (n + 1), which simplifies to 2n + 1.",
    "h3": "Here n denotes 125, so compute 125 + 126.",
    "h4": "Combine that sum with 15625 to express 126 squared."
  }
  ```
- **Violation**: The target option is literally `"\(15625 + 251\)"`. Hint 3 directs computing $125 + 126$ ($= 251$), and Hint 4 tells the student to attach it to $15625$, assembling the exact option string.
- **Pedagogical Solution**:
  - $H_3$ defines the increment as the sum of base $125$ and its immediate successor.
  - $H_4$ directs adding the two consecutive bases and appending the increment to 15625, leaving the calculation of 251 to the learner.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Recall the algebraic relationship between consecutive squares: (n + 1) squared minus n squared equals n plus (n + 1).",
    "h2": "Stepping from one square to the next requires adding the sum of the two consecutive bases, which simplifies to 2n + 1.",
    "h3": "Identify the base n as 125 and formulate the increment as the sum of 125 and its consecutive successor.",
    "h4": "Add the two consecutive bases together to find the required increment, and attach it to 15625 to express 126 squared."
  }
  ```

---

### Item 6: `sc_q15` — Removing Doubling Evaluation Leak ($2 \times 16 = 32$)
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:521-555`
- **Tag**: `NCERT Fig It Out 1.7 p.10` (Tier: `deep_dive`)
- **Question**:
  `"How many natural numbers lie strictly between \\(16^2\\) and \\(17^2\\)?"`
- **Target Answer**: `"\\(32\\)"`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Recall that the number of non-square natural numbers between n squared and (n+1) squared equals 2n.",
    "h2": "The smaller base n denotes 16.",
    "h3": "Check by interval subtraction: 289 minus 256 minus 1.",
    "h4": "Multiply 2 by 16 directly to determine the count of intermediate numbers."
  }
  ```
- **Violation**: Hint 4 states: `"Multiply 2 by 16 directly..."`, directly computing $2 \times 16 = 32$.
- **Pedagogical Solution**:
  - $H_1$–$H_2$ explain the $(n+1)^2 - n^2 - 1 = 2n$ principle.
  - $H_3$ identifies $16$ as the smaller base $n$.
  - $H_4$ instructs applying the doubling relation to the smaller base without performing the arithmetic.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Consider the interval of natural numbers strictly between the consecutive squares n squared and (n + 1) squared.",
    "h2": "Subtracting the boundary squares and excluding endpoints yields (n + 1) squared minus n squared minus 1, which simplifies to 2n.",
    "h3": "Identify the smaller base integer n in the given pair of squares 16 squared and 17 squared.",
    "h4": "Apply the non-square count relation to that smaller base to find the exact number of intermediate natural numbers."
  }
  ```

---

### Item 7: `sc_q22` — Removing Doubling Evaluation Leak ($2 \times 12 = 24$)
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:773-807`
- **Tag**: `NCERT In-Text p.7` (Tier: `deep_dive`)
- **Question**:
  `"How many non-square natural numbers lie strictly between \\(12^2\\) and \\(13^2\\)?"`
- **Target Answer**: `"\\(24\\)"`
- **Existing Flaw**:
  ```json
  "hints": {
    "h1": "Recall the rule for non-square numbers between consecutive squares: 2n.",
    "h2": "The smaller base n denotes 12.",
    "h3": "Verify by subtracting: 169 minus 144 minus 1.",
    "h4": "Calculate 2 times 12 to find the exact count."
  }
  ```
- **Violation**: Hint 4 states: `"Calculate 2 times 12 to find the exact count."`, directly evaluating $2 \times 12 = 24$.
- **Pedagogical Solution**:
  - $H_4$ instructs applying the doubling rule to the smaller base without calculating the product.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Recall that the count of non-square natural numbers lying strictly between n squared and (n + 1) squared is given by 2n.",
    "h2": "The count depends exclusively on doubling the smaller base of the two consecutive squares.",
    "h3": "Identify the smaller base integer n from the given consecutive squares 12 squared and 13 squared.",
    "h4": "Apply the doubling rule to that smaller base to determine the exact number of non-square natural numbers."
  }
  ```

---

### Item 8: `sc_q27` — Removing Multiplication Evaluation Leak ($180 \times 5 = 900$) & Factor Leak
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:953-987`
- **Tag**: `NCERT Fig It Out 1.5 p.10` (Tier: `boss`)
- **Question**:
  `"Find the smallest square number that is divisible by each of the numbers: \\(4, 9,\\) and \\(10\\)."`
- **Target Answer**: `"\\(900\\)"`
- **Existing Flaw**:
  - Hint 4: `"Multiply 180 by the unpaired factor 5 to reach the smallest perfect square."` ($180 \times 5 = 900$).
  - Distractor 4 (`360`): `"m": "Doubled the LCM rather than multiplying by the unpaired factor 5."` (reveals factor 5).
- **Violation**: Both Hint 4 and Distractor 4 leak the unpaired factor 5, and Hint 4 performs the exact multiplication reaching the answer 900.
- **Pedagogical Solution**:
  - $H_4$ instructs finding which prime factor has an odd exponent and multiplying the LCM by that factor to form complete pairs.
  - Distractor 4 `m` replaces `"unpaired factor 5"` with `"unpaired prime factor required to complete square pairs"`.
- **Replacement**:
  - Distractor 4:
    ```json
    {
      "t": "\\(360\\)",
      "c": false,
      "m": "Doubled the LCM rather than multiplying by the unpaired prime factor required to complete square pairs."
    }
    ```
  - Hints:
    ```json
    "hints": {
      "h1": "Any common multiple of 4, 9, and 10 must be a multiple of their least common multiple (LCM).",
      "h2": "Determine the prime factorisation of the LCM of 4, 9, and 10 by checking powers of 2, 3, and 5.",
      "h3": "For a number to form a perfect square, every prime factor in its prime factorisation must have an even exponent.",
      "h4": "Find which prime factor currently appears with an odd exponent, and multiply the LCM by that missing factor to form complete pairs."
    }
    ```

---

### Item 9: `sc_q17` — Eliminating Target Factor 7 Disclosure in Distractors
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:593-627`
- **Tag**: `NCERT Fig It Out 2.2 p.16` (Tier: `deep_dive`)
- **Question**:
  `"What is the smallest natural number by which \\(1323\\) must be multiplied so that the product becomes a perfect cube?"`
- **Target Answer**: `"\\(7\\)"`
- **Existing Flaw**:
  - Distractor 3 (`9`): `"m": "Attempted to complete an unnecessary power of 3 rather than completing the power of 7."`
  - Distractor 4 (`49`): `"m": "Multiplied by 7 squared rather than the single missing factor needed to complete a triplet."`
- **Violation**: Distractor 3 reveals the target answer: `"rather than completing the power of 7"`. Distractor 4 reveals `"7 squared"`.
- **Pedagogical Solution**:
  - In Distractor 3, diagnose that 3 is already a complete triplet and explain the mistake without naming 7.
  - In Distractor 4, diagnose multiplying by the square of the incomplete prime rather than the single missing factor.
- **Replacement**:
  ```json
  {
    "t": "\\(9\\)",
    "c": false,
    "m": "Attempted to introduce additional powers of an already complete prime factor rather than completing the triplet for the incomplete prime factor."
  },
  {
    "t": "\\(49\\)",
    "c": false,
    "m": "Multiplied by the square of the incomplete prime rather than the single missing factor needed to complete a triplet."
  }
  ```

---

### Item 10: `sc_q28` — Remediation of Mathematically False Equality
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:989-1023`
- **Tag**: `NCERT Fig It Out 1.8 p.11` (Tier: `boss`)
- **Question**:
  `"Identify the missing values in the pattern: \\(1^2+2^2+2^2=3^2\\), \\(2^2+3^2+6^2=7^2\\), \\(3^2+4^2+12^2=13^2\\), \\(4^2+5^2+20^2=(\\dots)^2\\), \\(9^2+10^2+(\\dots)^2=(\\dots)^2\\)."`
- **Target Answer**: `"\\(21^2\\) and \\(90^2 = 91^2\\)"`
- **Existing Flaw**: The string asserts $90^2 = 91^2$ ($8100 = 8281$), which is a mathematically false equality.
- **Pedagogical Solution**: Change the options to list the missing terms cleanly as comma-separated pairs: `\(21^2\) and \(90^2, 91^2\)`.
- **Replacement**:
  ```json
  "ans": "\\(21^2\\) and \\(90^2, 91^2\\)",
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
  ]
  ```

---

### Item 11: `sc_q08` Line 300 — Fixing Fatal Syntax Error
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:300`
- **Existing Flaw**:
  ```json
  300:         "h3": "Compute the cube of 100: 100 cubed has seven digits."
  301:         "h4": "Since 99 cubed is strictly less than 1000000, it can occupy at most six digit positions."
  ```
- **Replacement**:
  Add trailing comma to line 300:
  ```json
  300:         "h3": "Compute the cube of 100: 100 cubed has seven digits.",
  301:         "h4": "Since 99 cubed is strictly less than 1000000, it can occupy at most six digit positions."
  ```

---

### Item 12 (Advisory): `sc_q16` — Scaffolding Block Calculation & Prime Decomposition
- **Location**: `Aasha-AI/chapters/square_cube_questions.json:585-590`
- **Tag**: `NCERT Fig It Out 1.9 p.11` (Tier: `deep_dive`)
- **Question**: Total tiny squares in 40 blocks of 5x5 and its prime factorisation.
- **Answer**: `"\\(1000\\) squares, \\(2^3 \\times 5^3\\)"`
- **Existing Flaw**: Hint 3 states `"amounts to 1000"`, and Hint 4 states `"2 cubed times 5 cubed"`.
- **Replacement**:
  ```json
  "hints": {
    "h1": "Calculate the number of tiny squares in one block of 5 by 5: evaluate 5 squared.",
    "h2": "Multiply that block count by the total of 40 blocks to find the overall square count.",
    "h3": "Express the resulting product as a power of 10.",
    "h4": "Decompose the base 10 into its prime factors 2 and 5, applying the power of a product rule to find the prime factorisation."
  }
  ```

---

## 3. Complete Unified Diff Patch

For direct application by the implementer, here is the exact git diff against `Aasha-AI/chapters/square_cube_questions.json`:

```diff
--- a/chapters/square_cube_questions.json
+++ b/chapters/square_cube_questions.json
@@ -297,7 +297,7 @@
       "hints": {
         "h1": "Identify the largest possible two-digit natural number.",
         "h2": "The largest two-digit natural number is 99, which is strictly below 100.",
-        "h3": "Compute the cube of 100: 100 cubed has seven digits."
+        "h3": "Compute the cube of 100: 100 cubed has seven digits.",
         "h4": "Since 99 cubed is strictly less than 1000000, it can occupy at most six digit positions."
       }
     },
@@ -477,8 +477,8 @@
       "hints": {
         "h1": "Recall the algebraic identity: (n + 1) squared equals n squared plus 2n plus 1.",
         "h2": "The difference between consecutive squares equals n plus (n + 1), which simplifies to 2n + 1.",
-        "h3": "Here n denotes 125, so compute 125 + 126.",
-        "h4": "Combine that sum with 15625 to express 126 squared."
+        "h3": "Identify the base n as 125 and formulate the increment as the sum of 125 and its consecutive successor.",
+        "h4": "Add the two consecutive bases together to find the required increment, and attach it to 15625 to express 126 squared."
       }
     },
     {
@@ -550,7 +550,7 @@
       "hints": {
         "h1": "Recall that the number of non-square natural numbers between n squared and (n+1) squared equals 2n.",
         "h2": "The smaller base n denotes 16.",
-        "h3": "Check by interval subtraction: 289 minus 256 minus 1.",
-        "h4": "Multiply 2 by 16 directly to determine the count of intermediate numbers."
+        "h3": "Identify the smaller base integer n in the given pair of squares 16 squared and 17 squared.",
+        "h4": "Apply the non-square count relation to that smaller base to find the exact number of intermediate natural numbers."
       }
     },
     {
@@ -611,7 +611,7 @@
         {
           "t": "\\(9\\)",
           "c": false,
-          "m": "Attempted to complete an unnecessary power of 3 rather than completing the power of 7."
+          "m": "Attempted to introduce additional powers of an already complete prime factor rather than completing the triplet for the incomplete prime factor."
         },
         {
           "t": "\\(49\\)",
-          "m": "Multiplied by 7 squared rather than the single missing factor needed to complete a triplet."
+          "m": "Multiplied by the square of the incomplete prime rather than the single missing factor needed to complete a triplet."
         }
       ],
@@ -766,7 +766,7 @@
       "hints": {
         "h1": "Recall that 35 squared represents the sum of the first 35 odd natural numbers.",
         "h2": "To obtain 36 squared, add the 36th odd natural number to 1225.",
-        "h3": "Find the 36th odd number using the formula 2n - 1 with n denoting 36.",
-        "h4": "Add 71 to 1225 to determine the value."
+        "h3": "Express the nth odd natural number using the general relation 2n - 1, setting n equal to 36.",
+        "h4": "Calculate the value of that 36th odd number and add it to 1225 to find the next square."
       }
     },
     {
@@ -802,7 +802,7 @@
       "hints": {
         "h1": "Recall the rule for non-square numbers between consecutive squares: 2n.",
         "h2": "The smaller base n denotes 12.",
-        "h3": "Verify by subtracting: 169 minus 144 minus 1.",
-        "h4": "Calculate 2 times 12 to find the exact count."
+        "h3": "Identify the smaller base integer n from the given consecutive squares 12 squared and 13 squared.",
+        "h4": "Apply the doubling rule to that smaller base to determine the exact number of non-square natural numbers."
       }
     },
     {
@@ -976,7 +976,7 @@
         {
           "t": "\\(360\\)",
           "c": false,
-          "m": "Doubled the LCM rather than multiplying by the unpaired factor 5."
+          "m": "Doubled the LCM rather than multiplying by the unpaired prime factor required to complete square pairs."
         }
       ],
       "hints": {
@@ -982,7 +982,7 @@
         "h1": "Find the least common multiple (LCM) of 4, 9, and 10.",
         "h2": "Express the LCM 180 in prime factorisation: 2 squared times 3 squared times 5.",
         "h3": "Identify which prime factor lacks a pair in the prime decomposition.",
-        "h4": "Multiply 180 by the unpaired factor 5 to reach the smallest perfect square."
+        "h4": "Find which prime factor currently appears with an odd exponent, and multiply the LCM by that missing factor to form complete pairs."
       }
     },
     {
@@ -990,26 +990,26 @@
       "id": "sc_q28",
       "tag": "NCERT Fig It Out 1.8 p.11",
       "tier": "boss",
       "q": "Identify the missing values in the pattern: \\(1^2+2^2+2^2=3^2\\), \\(2^2+3^2+6^2=7^2\\), \\(3^2+4^2+12^2=13^2\\), \\(4^2+5^2+20^2=(\\dots)^2\\), \\(9^2+10^2+(\\dots)^2=(\\dots)^2\\).",
-      "ans": "\\(21^2\\) and \\(90^2 = 91^2\\)",
+      "ans": "\\(21^2\\) and \\(90^2, 91^2\\)",
       "m": "Misinterpreting the algebraic relationship between consecutive base products and the target sum base.",
       "opts": [
         {
-          "t": "\\(21^2\\) and \\(90^2 = 91^2\\)",
+          "t": "\\(21^2\\) and \\(90^2, 91^2\\)",
           "c": true,
           "m": ""
         },
         {
-          "t": "\\(25^2\\) and \\(90^2 = 92^2\\)",
+          "t": "\\(25^2\\) and \\(90^2, 92^2\\)",
           "c": false,
           "m": "Added 5 to 20 rather than adding 1 to 20 for the right-hand base."
         },
         {
-          "t": "\\(21^2\\) and \\(80^2 = 81^2\\)",
+          "t": "\\(21^2\\) and \\(80^2, 81^2\\)",
           "c": false,
           "m": "Multiplied 9 by 9 rather than 9 by 10 for the third term."
         },
         {
-          "t": "\\(20^2\\) and \\(100^2 = 101^2\\)",
+          "t": "\\(20^2\\) and \\(100^2, 101^2\\)",
           "c": false,
           "m": "Used 10 squared rather than the product of the first two bases."
         }
@@ -1090,7 +1090,7 @@
       "hints": {
         "h1": "Find all numbers from 1 to 17 that can add with 16 to form a square.",
         "h2": "Notice 16 can only pair with 9 (to make 25); no other number from 1 to 17 works.",
         "h3": "Check 17: it can only pair with 8 (to make 25); no other number from 1 to 17 works.",
-        "h4": "Any vertex with degree 1 must be placed at an end of a non-branching row."
+        "h4": "In a linear chain where every internal member must connect to two neighbors, any number possessing only a single valid partner cannot sit in the interior and must form an endpoint."
       }
     },
     {
@@ -1125,8 +1125,8 @@
       "hints": {
-        "h1": "Calculate the sum of each pair: 32 plus candidate.",
-        "h2": "Check which sum appears in the list of perfect squares: 36, 49, 64.",
-        "h3": "Evaluate 32 plus 17 and test whether it matches 7 squared.",
-        "h4": "Confirm that 49 is a perfect square."
+        "h1": "In the square pairs arrangement, two adjacent numbers form a valid pair if and only if their sum equals a perfect square.",
+        "h2": "With 32 as the fixed number, summing with the given options produces totals lying strictly between 48 and 52.",
+        "h3": "Consider the sequence of consecutive perfect squares in this neighborhood: 6 squared (36), 7 squared (49), and 8 squared (64).",
+        "h4": "Determine which integer square falls within the interval from 48 to 52, and select the candidate pair that reaches that total."
       }
     },
@@ -1233,7 +1233,7 @@
       "hints": {
-        "h1": "Compute the cubes: 9 cubed equals 729 and 15 cubed equals 3375.",
-        "h2": "Add 729 and 3375 together.",
-        "h3": "Verify that the sum matches 4104.",
-        "h4": "Confirm that this forms the second Ramanujan partition for 4104."
+        "h1": "Observe the units digit of the target taxicab sum: 4104 terminates in the digit 4.",
+        "h2": "Because 16 cubed equals 4096, any other two cubes summing to 4104 must have positive integer bases strictly below 16.",
+        "h3": "Analyze which pairs of units digits for natural cubes sum to a units digit of 4, such as single digits ending in 9 and 5.",
+        "h4": "Identify candidate base pairs below 16 that match those ending digits, and sum their cubic values to find the combination reaching 4104."
       }
     }
```

---

## 4. Verification & Invalidation Conditions

### Independent Verification Procedure
1. Apply the patch to `Aasha-AI/chapters/square_cube_questions.json`.
2. Run the validator suite:
   ```bash
   node Aasha-AI/benchmarks/test_square_cube_validator.js
   ```
   **Expected Result**: Exit code 0, 100/100 score, 0 spoiler violations, 0 hint violations, 0 errors.
3. Run the independent mathematical oracle:
   ```bash
   node Aasha-AI/benchmarks/test_square_cube_math_oracle.js
   ```
   **Expected Result**: Exit code 0, 34/34 mathematical checks pass.

### Invalidation Conditions
- Any occurrence of numbers `9` and `15` in `sc_q34` $H_1$–$H_3$.
- Any occurrence of candidate number `17` in `sc_q31` $H_1$–$H_3$.
- Any appearance of the phrase `"degree 1"` in `sc_q30` hints.
- Any direct arithmetic sum ($1225+71$, $125+126$, $2\times 16$, $2\times 12$, $180\times 5$) evaluating to the target answer in any Tier 4 hint.
- Any mention of factor `7` in `sc_q17` distractor explanations.
