# Empirical Challenge Report & Handoff — Milestone 1 Gate
**Agent**: `teamwork_preview_challenger_m1_2` (Mathematical Soundness & Arithmetic Challenger)  
**Date**: 2026-09-13T22:05:00Z  
**Target File**: `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json`  
**Verdict**: **APPROVE** (Mathematical Soundness & Arithmetic Accuracy) with **ADVISORY ACTION REQUIRED** (21 Pedagogical Hint/Distractor Spoilers under Rule #1)

---

## 1. Observation

### 1.1 Test Harnesses Executed
Two independent mathematical oracles were authored and executed against the 75 textbook questions in `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json`:
1. **Python Mathematical Oracle** (`tests/verify_ad_math_oracle.py`) using `fractions.Fraction` exact rational arithmetic.
2. **Node.js Mathematical Oracle** (`tests/verify_ad_math_oracle.js`) using exact BigInt `Rational` arithmetic and integrating `QuestionSchemaValidator`.

### 1.2 Execution Commands & Verbatim Outputs
Command 1: `node tests/verify_ad_math_oracle.js`
Verbatim output snippet:
```
Loaded 75 questions from C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\chapters\ad_all_questions.json
================================================================================
[ 1/75] ad_1a_q1_a       | Addition             | PASS | 5/2 + -11/2 = -3
[ 2/75] ad_1a_q1_b       | Addition             | PASS | 7/5 + 13/5 = 4
[ 3/75] ad_1a_q1_c       | Addition             | PASS | -7/8 + -3/2 = -19/8
...
[62/75] ad_1a_q5_a       | Multi-bracket        | PASS | [-7/3] - [-90/49] = -73/147
[63/75] ad_1a_q5_b       | Multi-bracket        | PASS | [21/11] + [14/33] - [7/33] = 70/33
[64/75] ad_1b_q4         | Commutative Verification | PASS | LHS=37/72, RHS=37/72
...
[75/75] ad_1c_q3_c       | Distributive Mul     | PASS | Result = 0
================================================================================
SUMMARY: 75/75 questions mathematically verified.
Discrepancies: 0
QuestionSchemaValidator Violations: 21
```

Command 2: `python tests/verify_ad_math_oracle.py`
Verbatim output snippet:
```
================================================================================
SUMMARY: 75/75 questions mathematically verified.
Discrepancies: 0
Schema errors: 0
================================================================================
MANDATORY FOCAL CHECKS VERIFICATION:
================================================================================
1. Ex 1A Q5(a): [3/2 * -7/4 * 8/9] - [-15/2 * 3/7 * 8/14]
   Bracket 1: -7/3 (exact -7/3)
   Bracket 2: -90/49 (exact -90/49)
   Difference: (-7/3) - (-90/49) = -73/147
   Match -73/147: True

2. Ex 1B Q4: a = 8/9, b = -3/8
   a + b = 8/9 + (-3/8) = 37/72
   b + a = -3/8 + 8/9 = 37/72
   Commutative equality verified: True
   Match 37/72: True

3. Negative Denominator Test: 12/-8
   Fraction('12/-8') = -3/2 (formatted: -3/2)
   Match -3/2: True
   Double Negative Test: -9/-33
   Fraction('-9/-33') = 3/11 (formatted: 3/11)
   Match 3/11: True

>>> ALL 75 QUESTIONS PASSED MATHEMATICAL ORACLE VERIFICATION CLEANLY <<<
```

### 1.3 Key Mathematical Checks Observed
- **Ex 1A Q5(a)** (lines 2213-2247):
  - Expression: $\left[\frac{3}{2} \times \frac{-7}{4} \times \frac{8}{9}\right] - \left[\frac{-15}{2} \times \frac{3}{7} \times \frac{8}{14}\right]$
  - Bracket 1: $\frac{3 \times (-7) \times 8}{2 \times 4 \times 9} = \frac{-168}{72} = -\frac{7}{3}$
  - Bracket 2: $\frac{-15 \times 3 \times 8}{2 \times 7 \times 14} = \frac{-360}{196} = -\frac{90}{49}$
  - Subtraction: $\left(-\frac{7}{3}\right) - \left(-\frac{90}{49}\right) = -\frac{343}{147} + \frac{270}{147} = -\frac{73}{147}$
  - JSON `ans`: `"-73/147"`, Option with `c: true`: `"-73/147"`. **Verified Exact Match**.
- **Ex 1B Q4** (lines 2285-2319):
  - Values: $a = \frac{8}{9}, b = -\frac{3}{8}$
  - $a + b = \frac{64}{72} + \left(-\frac{27}{72}\right) = \frac{37}{72}$
  - $b + a = -\frac{27}{72} + \frac{64}{72} = \frac{37}{72}$
  - JSON `ans`: `"37/72"`, Option with `c: true`: `"37/72"`. **Verified Exact Match & Commutative Equality**.
- **Negative Denominators & Standard Form**:
  - Ex 1A Q1(c) (line 92): $\frac{12}{-8} = -\frac{3}{2}$, $-\frac{7}{8} + \left(-\frac{12}{8}\right) = -\frac{19}{8}$. **Verified Exact Match**.
  - Ex 1A Q1(h) (line 272): $\frac{-9}{-33} = \frac{3}{11}$, $\frac{3}{11} + \frac{5}{11} = \frac{8}{11}$. **Verified Exact Match**.
  - Ex 1A Q2(g) (line 524): $-\frac{13}{-26} = \frac{1}{2}$, $\frac{7}{24} - \frac{1}{2} = -\frac{5}{24}$. **Verified Exact Match**.
  - Ex 1A Q3(f) (line 1316): $\frac{40}{-36} = -\frac{10}{9}$, $-\frac{18}{25} \times \left(-\frac{10}{9}\right) = \frac{4}{5}$. **Verified Exact Match**.
  - Ex 1C Q2(b) (line 2504): $\frac{6}{-11} = -\frac{6}{11}$, $\frac{2}{7} \times \left(-\frac{7}{3} \times \frac{6}{-11}\right) = \frac{4}{11}$. **Verified Exact Match**.

---

## 2. Logic Chain

1. **Analytical & Computational Convergence**:
   - The question bank `ad_all_questions.json` contains 75 items across 3 tiers (31 warmup, 30 deep_dive, 14 boss) mapping Exercises 1A, 1B, 1C, and 5 prescribed board solved examples.
   - Every arithmetic operation (rational addition, subtraction, multiplication, division, multi-step bracket evaluation) was independently recalculated using Python's standard `fractions.Fraction` and Node.js `BigInt` exact rational reducer.
   - For all 75 questions, the oracle output exactly matches the `ans` field and the option marked `c: true`.
   - No arithmetic or sign discrepancy exists ($0 / 75$ errors).

2. **Standard Form Reduction & Negative Denominator Conformance**:
   - In rational arithmetic, negative denominators must satisfy standard form $\frac{a}{-b} = \frac{-a}{b}$.
   - Questions featuring negative denominators (e.g. `12/-8`, `4/-7`, `12/-5`, `-9/-33`, `-13/-26`, `11/-13`, `40/-36`, `6/-11`) correctly apply standard form normalization without losing signs or creating false double-negatives.

3. **Adversarial Schema & Hint Audit**:
   - When subjecting the questions to `QuestionSchemaValidator` from `benchmarks/question_schema_validator.js`, the mathematical arithmetic remained 100% sound, but 21 warnings/errors were triggered regarding pedagogical hint/distractor leaks (Rule #1 Anti-Spoiler).
   - Specifically, distractor `ad_1b_q1_b` Option 2 states `"Flipped the sign of 2/3 when changing its order."`, leaking the target correct answer `2/3`.
   - Multiple progressive hints in Tier 2/3 state intermediate numerical values or property names (e.g. `ad_presc_2` hint h3 mentions `"Associative Property of Multiplication"`).
   - These findings do not compromise mathematical soundness, but are critical findings for the subsequent QA L-Truth certification gate.

---

## 3. Caveats

1. **Scope Boundary**: This evaluation tested mathematical soundness, rational arithmetic accuracy, sign handling, and algebraic identities of `ad_all_questions.json`. It did not test client-side browser DOM event bindings or canvas frame rates (which are verified under the headless Chrome CDP suite).
2. **Zero In-Place Edits**: In strict compliance with the challenger role constraint ("Review-only — do NOT modify implementation code"), no changes were applied to `chapters/ad_all_questions.json`. The 21 hint/distractor leakage findings are reported as actionable items for the implementing agent or reviewer subagent.

---

## 4. Conclusion

- **Definitive Verdict for Mathematical Soundness**: **APPROVE**.
- All 75 questions in `chapters/ad_all_questions.json` are 100% mathematically correct, consistent with CBSE Class 8 NCERT/AD curriculum ground truth, and free of arithmetic errors.
- Both Ex 1A Q5(a) ($-\frac{73}{147}$) and Ex 1B Q4 ($\frac{37}{72}$) are strictly confirmed.
- **Recommended Action for Implementer**: Clean up the 21 distractor/hint leaks before the final QA L-Truth benchmark run (`node benchmarks/qa_ltruth_benchmark.js`).

---

## 5. Verification Method

To independently reproduce and verify this assessment, run the test harnesses:
```powershell
# Python exact rational oracle
python tests/verify_ad_math_oracle.py

# Node.js exact rational oracle & schema auditor
node tests/verify_ad_math_oracle.js
```
Expected outcome: Exit code 0, 75/75 mathematical questions PASSED.

---

## 6. Complete 75-Question Mathematical Validation Table

| # | ID | Tag | Category | Question Prompt Summary | Stored Ans | Oracle Ans | Status |
|---|---|---|---|---|---|---|---|
| 1 | `ad_1a_q1_a` | AD Ex 1A Q1(a) | Addition | 5/2 + -11/2 | -3 | -3 | **PASS** |
| 2 | `ad_1a_q1_b` | AD Ex 1A Q1(b) | Addition | 7/5 + 13/5 | 4 | 4 | **PASS** |
| 3 | `ad_1a_q1_c` | AD Ex 1A Q1(c) | Addition | -7/8 + 12/-8 | -19/8 | -19/8 | **PASS** |
| 4 | `ad_1a_q1_d` | AD Ex 1A Q1(d) | Addition | -11/5 + -9/5 | -4 | -4 | **PASS** |
| 5 | `ad_1a_q1_e` | AD Ex 1A Q1(e) | Addition | 4/-7 + -5/8 | -67/56 | -67/56 | **PASS** |
| 6 | `ad_1a_q1_f` | AD Ex 1A Q1(f) | Addition | -13/7 + 12/-5 | -149/35 | -149/35 | **PASS** |
| 7 | `ad_1a_q1_g` | AD Ex 1A Q1(g) | Addition | -15/9 + -17/11 | -106/33 | -106/33 | **PASS** |
| 8 | `ad_1a_q1_h` | AD Ex 1A Q1(h) | Addition | -9/-33 + 5/11 | 8/11 | 8/11 | **PASS** |
| 9 | `ad_1a_q2_a` | AD Ex 1A Q2(a) | Subtraction | (-18/5) - (-8/5) | -2 | -2 | **PASS** |
| 10 | `ad_1a_q2_b` | AD Ex 1A Q2(b) | Subtraction | (-19/15) - (-6/30) | -16/15 | -16/15 | **PASS** |
| 11 | `ad_1a_q2_c` | AD Ex 1A Q2(c) | Subtraction | (-6/11) - (-7/11) | 1/11 | 1/11 | **PASS** |
| 12 | `ad_1a_q2_d` | AD Ex 1A Q2(d) | Subtraction | (-1/4) - (-2/8) | 0 | 0 | **PASS** |
| 13 | `ad_1a_q2_e` | AD Ex 1A Q2(e) | Subtraction | (-59/5) - (19/5) | -78/5 | -78/5 | **PASS** |
| 14 | `ad_1a_q2_f` | AD Ex 1A Q2(f) | Subtraction | (-4/7) - (-8/9) | 20/63 | 20/63 | **PASS** |
| 15 | `ad_1a_q2_g` | AD Ex 1A Q2(g) | Subtraction | (7/24) - (-13/-26) | -5/24 | -5/24 | **PASS** |
| 16 | `ad_1a_q2_h` | AD Ex 1A Q2(h) | Subtraction | (7/25) - (-6/15) | 17/25 | 17/25 | **PASS** |
| 17 | `ad_1b_q1_a` | AD Ex 1B Q1(a) | Commutative Add | (-3/7) + (4/9) = ___ + (-3/7) | 4/9 | 4/9 | **PASS** |
| 18 | `ad_1b_q1_b` | AD Ex 1B Q1(b) | Commutative Add | (2/3) + (-5/6) = (-5/6) + ___ | 2/3 | 2/3 | **PASS** |
| 19 | `ad_1b_q1_c` | AD Ex 1B Q1(c) | Commutative Add | [(-11/29)] + [(-5/31)] = [(-5/31)] + ___ | -11/29 | -11/29 | **PASS** |
| 20 | `ad_1b_q1_d` | AD Ex 1B Q1(d) | Commutative Add | (-7/13) + (11/23) = (11/23) + ___ | -7/13 | -7/13 | **PASS** |
| 21 | `ad_1c_q5_a` | AD Ex 1C Q5(a) | Commutative Mul | [(-9/16) * (11/7)] = (11/7) * [___] | -9/16 | -9/16 | **PASS** |
| 22 | `ad_1c_q5_b` | AD Ex 1C Q5(b) | Commutative Mul | [___] * [(-7/9)] = [(-7/9)] * [(-5/8)] | -5/8 | -5/8 | **PASS** |
| 23 | `ad_1c_q5_c` | AD Ex 1C Q5(c) | Identity Mul | (-7/13) * ___ = (-7/13) | 1 | 1 | **PASS** |
| 24 | `ad_1c_q5_d` | AD Ex 1C Q5(d) | Zero Property | ___ * (-19/47) = 0 | 0 | 0 | **PASS** |
| 25 | `ad_1c_q5_e` | AD Ex 1C Q5(e) | Distributive Mul | (-3/4)*[1/3+(-5/6)]=[(-3/4)*___]+[(-3/4)*(-5/6)] | 1/3 | 1/3 | **PASS** |
| 26 | `ad_1c_q5_f` | AD Ex 1C Q5(f) | Associative Mul | (-2/5)*[(6/7)*(-8/9)]=[(-2/5)*___]*(-8/9) | 6/7 | 6/7 | **PASS** |
| 27 | `ad_1c_q5_g` | AD Ex 1C Q5(g) | Division Identity | (3/8) / (3/8) = ___ | 1 | 1 | **PASS** |
| 28 | `ad_1c_q5_h` | AD Ex 1C Q5(h) | Division Inversion | (7/13) / [___] = -1 | -7/13 | -7/13 | **PASS** |
| 29 | `ad_1c_q5_i` | AD Ex 1C Q5(i) | Division Identity | (14/19) / ___ = 14/19 | 1 | 1 | **PASS** |
| 30 | `ad_1c_q5_j` | AD Ex 1C Q5(j) | Division Identity | [___] / [(-13/15)] = 1 | -13/15 | -13/15 | **PASS** |
| 31 | `ad_presc_3` | AD Prescribed Q3 | Closure Concept | Product of two rational numbers is always a ___ | rational number | rational number | **PASS** |
| 32 | `ad_1a_q3_a` | AD Ex 1A Q3(a) | Multiplication | (4/7) * (-2/5) | -8/35 | -8/35 | **PASS** |
| 33 | `ad_1a_q3_b` | AD Ex 1A Q3(b) | Multiplication | (-3/8) * (-12/15) | 3/10 | 3/10 | **PASS** |
| 34 | `ad_1a_q3_c` | AD Ex 1A Q3(c) | Multiplication | (11/-13) * (-39/22) | 3/2 | 3/2 | **PASS** |
| 35 | `ad_1a_q3_d` | AD Ex 1A Q3(d) | Multiplication | (-5/9) * (81/35) | -9/7 | -9/7 | **PASS** |
| 36 | `ad_1a_q3_e` | AD Ex 1A Q3(e) | Multiplication | (-9/25) * (-35/27) | 7/15 | 7/15 | **PASS** |
| 37 | `ad_1a_q3_f` | AD Ex 1A Q3(f) | Multiplication | (-18/25) * (40/-36) | 4/5 | 4/5 | **PASS** |
| 38 | `ad_1a_q4_a` | AD Ex 1A Q4(a) | Division | (16/7) / (-8/14) | -4 | -4 | **PASS** |
| 39 | `ad_1a_q4_b` | AD Ex 1A Q4(b) | Division | (-7/8) / (-21) | 1/24 | 1/24 | **PASS** |
| 40 | `ad_1a_q4_c` | AD Ex 1A Q4(c) | Division | (3/8) / (-4/5) | -15/32 | -15/32 | **PASS** |
| 41 | `ad_1a_q4_d` | AD Ex 1A Q4(d) | Division | (-1/15) / (8/3) | -1/40 | -1/40 | **PASS** |
| 42 | `ad_1a_q4_e` | AD Ex 1A Q4(e) | Division | (-3/26) / (9/78) | -1 | -1 | **PASS** |
| 43 | `ad_1a_q4_f` | AD Ex 1A Q4(f) | Division | (-22/26) / (-33/39) | 1 | 1 | **PASS** |
| 44 | `ad_1b_q2_a` | AD Ex 1B Q2(a) | Associative Add | [(1/11)+(2/13)]+(7/6)=(1/11)+[___+(7/6)] | 2/13 | 2/13 | **PASS** |
| 45 | `ad_1b_q2_b` | AD Ex 1B Q2(b) | Associative Add | (17/21)+[(-5/13)+(9/16)]=[(17/21)+___]+(9/16) | -5/13 | -5/13 | **PASS** |
| 46 | `ad_1b_q2_c` | AD Ex 1B Q2(c) | Associative Add | [(-31/41)]+[(9/14)+(8/15)]=[___+(9/14)]+(8/15) | -31/41 | -31/41 | **PASS** |
| 47 | `ad_1b_q2_d` | AD Ex 1B Q2(d) | Associative Add | [(2/7)+(3/8)]+(-9/14)=(2/7)+[(3/8)+___] | -9/14 | -9/14 | **PASS** |
| 48 | `ad_1b_q3_a` | AD Ex 1B Q3(a) | Property ID | (-2/5)+(3/7)=(3/7)+(-2/5) | Commutative Property of Addition | Commutative Property of Addition | **PASS** |
| 49 | `ad_1b_q3_b` | AD Ex 1B Q3(b) | Property ID | (2/5)+[(9/7)+(-3/8)]=[(2/5)+(9/7)]+(-3/8) | Associative Property of Addition | Associative Property of Addition | **PASS** |
| 50 | `ad_1b_q3_c` | AD Ex 1B Q3(c) | Property ID | (-3/7)+[(-5/8)+(9/4)]=[(-3/7)+(-5/8)]+(9/4) | Associative Property of Addition | Associative Property of Addition | **PASS** |
| 51 | `ad_1b_q3_d` | AD Ex 1B Q3(d) | Property ID | (3/10)+[(-11/15)+(9/-7)]=[(3/10)+(-11/15)]+(9/-7) | Associative Property of Addition | Associative Property of Addition | **PASS** |
| 52 | `ad_1c_q4_a` | AD Ex 1C Q4(a) | Property ID | (2/7)*(13/11)=(13/11)*(2/7) | Commutative Property of Multiplication | Commutative Property of Multiplication | **PASS** |
| 53 | `ad_1c_q4_b` | AD Ex 1C Q4(b) | Property ID | (-5/7)*[(6/11)*(7/13)]=[(-5/7)*(6/11)]*(7/13) | Associative Property of Multiplication | Associative Property of Multiplication | **PASS** |
| 54 | `ad_1c_q4_c` | AD Ex 1C Q4(c) | Property ID | (1/7)*(3/5)=3/35 is rational | Closure Property of Multiplication | Closure Property of Multiplication | **PASS** |
| 55 | `ad_1c_q4_d` | AD Ex 1C Q4(d) | Property ID | (7/11)*[(1/6)+(2/13)]=[(7/11)*(1/6)]+[(7/11)*(2/13)] | Distributive Property of Multiplication over Addition | Distributive Property of Multiplication over Addition | **PASS** |
| 56 | `ad_1c_q4_e` | AD Ex 1C Q4(e) | Property ID | (-9/8)*0=0=0*(-9/8) | Multiplicative Property of Zero | Multiplicative Property of Zero | **PASS** |
| 57 | `ad_1c_q4_f` | AD Ex 1C Q4(f) | Property ID | 1*(7/9)=7/9 | Multiplicative Identity (Property of 1) | Multiplicative Identity (Property of 1) | **PASS** |
| 58 | `ad_presc_1_i` | AD Prescribed Q1(i) | Property ID | (-4/5)*1=1*(-4/5)=-4/5 | 1 is the Multiplicative Identity | 1 is the Multiplicative Identity | **PASS** |
| 59 | `ad_presc_1_ii`| AD Prescribed Q1(ii)| Property ID | (-13/17)*(-2/7)=(-2/7)*(-13/17) | Commutative Property of Multiplication | Commutative Property of Multiplication | **PASS** |
| 60 | `ad_presc_1_iii`| AD Prescribed Q1(iii)| Property ID | (-19/29)*(29/-19)=1 | Multiplicative Inverse (Reciprocal Property) | Multiplicative Inverse (Reciprocal Property) | **PASS** |
| 61 | `ad_presc_2` | AD Prescribed Q2 | Property ID | (1/3)*[6*(4/3)] as [(1/3)*6]*(4/3) | Associative Property of Multiplication | Associative Property of Multiplication | **PASS** |
| 62 | `ad_1a_q5_a` | AD Ex 1A Q5(a) | Multi-bracket | [(3/2)*(-7/4)*(8/9)] - [(-15/2)*(3/7)*(8/14)] | -73/147 | -73/147 | **PASS** |
| 63 | `ad_1a_q5_b` | AD Ex 1A Q5(b) | Multi-bracket | [(7/3)*(9/11)] + [(4/3)*(7/22)] - [(3/-11)*(-7/9)] | 70/33 | 70/33 | **PASS** |
| 64 | `ad_1b_q4` | AD Ex 1B Q4 | Commutative Add | a=8/9, b=-3/8. Verify a+b = b+a | 37/72 | 37/72 | **PASS** |
| 65 | `ad_1c_q1_a` | AD Ex 1C Q1(a) | Commutative Mul | (1/11) * (6/7) | 6/77 | 6/77 | **PASS** |
| 66 | `ad_1c_q1_b` | AD Ex 1C Q1(b) | Commutative Mul | (3/5) * [(-7/8)] | -21/40 | -21/40 | **PASS** |
| 67 | `ad_1c_q1_c` | AD Ex 1C Q1(c) | Commutative Mul | [(-13/19)] * (7/8) | -91/152 | -91/152 | **PASS** |
| 68 | `ad_1c_q1_d` | AD Ex 1C Q1(d) | Commutative Mul | (-5/9) * [(-11/32)] | 55/288 | 55/288 | **PASS** |
| 69 | `ad_1c_q2_a` | AD Ex 1C Q2(a) | Associative Mul | [(7/20)*(5/21)]*(1/3) | 1/36 | 1/36 | **PASS** |
| 70 | `ad_1c_q2_b` | AD Ex 1C Q2(b) | Associative Mul | (2/7)*[(-7/3)*(6/-11)] | 4/11 | 4/11 | **PASS** |
| 71 | `ad_1c_q2_c` | AD Ex 1C Q2(c) | Associative Mul | [(-7/15)*(-2/9)]*[(-3/7)] | -2/45 | -2/45 | **PASS** |
| 72 | `ad_1c_q2_d` | AD Ex 1C Q2(d) | Associative Mul | (8/9)*[(-8/5)*(6/7)] | -128/105 | -128/105 | **PASS** |
| 73 | `ad_1c_q3_a` | AD Ex 1C Q3(a) | Distributive Mul | (5/4)*[(-6/7)+(2/5)] | -4/7 | -4/7 | **PASS** |
| 74 | `ad_1c_q3_b` | AD Ex 1C Q3(b) | Distributive Mul | 3*[(1/3)+(-5/11)] | -4/11 | -4/11 | **PASS** |
| 75 | `ad_1c_q3_c` | AD Ex 1C Q3(c) | Distributive Mul | 0*[(1/2)+(2/5)] | 0 | 0 | **PASS** |

---

## 7. Adversarial Findings & Advisory Action Items

While mathematical arithmetic is 100% sound, `QuestionSchemaValidator` surfaced 21 items in `ad_all_questions.json` violating the Anti-Spoiler Invariant:

1. **Distractor Spoilers**:
   - `ad_1b_q1_b` (Option 2): `"Flipped the sign of 2/3 when changing its order."` -> Leaks target answer `2/3`.
   - `ad_1a_q2_e` (Option 4): `"Subtracted or added denominators instead of preserving denominator 5."` -> Triggered by phrase `instead of` followed by `5`.

2. **Progressive Hint Spoilers**:
   - `ad_1a_q1_f` (Hint h2): Reveals denominator `35` (`"Determine the LCM of denominators 7 and 5, which is 35."`).
   - `ad_1a_q2_f` (Hint h2): Reveals denominator `63` (`"Find the LCM of denominators 7 and 9, which is 63."`).
   - `ad_1b_q4` (Hint h1): Reveals denominator `72` (`"Find the common denominator for denominators 9 and 8, which is 72."`).
   - `ad_1c_q5_c` (Hint h2): Leaks target answer `1` (`"...multiplying any number by 1 leaves it unchanged."`).
   - `ad_1c_q5_e` (Hint h2): Leaks target answer `1/3` (`"Here, a is -3/4, b is 1/3, and c is -5/6."`).
   - `ad_1c_q5_f` (Hint h3): Leaks target answer `6/7` (`"Compare the terms: a is -2/5, b is 6/7, and c is -8/9."`).
   - `ad_1c_q5_g` (Hint h2): Leaks target answer `1` (`"Dividing any non-zero rational number by itself always equals 1."`).
   - `ad_1c_q5_i` (Hints h2, h3): Leaks target answer `1`.
   - `ad_presc_2` (Hint h3): Leaks target answer string `"Associative Property of Multiplication"`.
   - `ad_1c_q1_a` (Hint h2): Leaks numerator value `6`.
   - `ad_1c_q2_b` (Hints h2, h3): Leaks target fraction `4/11`.
   - `ad_1c_q3_c` (Hint h3): Leaks target answer `0`.

**Advisory Recommendation**: Implementers should rephrase these distractor explanations and progressive hints to guide conceptually (e.g. "Recall the multiplicative identity element" instead of "multiplying by 1") to pass the dual-benchmark gate with 0 spoiler flags.
