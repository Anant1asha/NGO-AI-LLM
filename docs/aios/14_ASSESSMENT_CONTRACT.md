# 14_ASSESSMENT_CONTRACT.md
# Diagnostic Assessment Contracts & Misconception Taxonomy

Assessment items must never be arbitrary quizzes. Every question serves as a diagnostic instrument designed to detect specific mental models, preconceptions, and cognitive missteps.

---

### ASSESSMENT ITEM: ASM-FRAC-001
- **ASSESSMENT ID**: ASM-FRAC-001
- **CURRICULUM OBJECTIVE**: Grade 4 Fractions — Denominator Concept
- **SKILL**: Identify denominator from a partitioned visual model.
- **QUESTION**: "A pizza is cut into 8 equal slices. Sita eats 3 slices. What is the denominator of the fraction of pizza Sita ate?"
- **TASK TYPE**: Multiple Choice (Single Correct, 4 Shuffled Options).
- **DIFFICULTY**: Foundation (Tier 1).
- **EXPECTED RESPONSE**: `8` (`c: true`)
- **VALIDATION RULE**: Exact match on option ID marked `c: true`.
- **DISTRACTORS & MISCONCEPTIONS**:
  - Distractor 1: `3`
    - `misconception_id`: `MISC_DENOM_AS_PART_TAKEN`
    - `explanation_m`: "3 is the number of slices Sita ate, which is the numerator (top number). The denominator tells us the total number of equal slices in the whole pizza."
  - Distractor 2: `5`
    - `misconception_id`: `MISC_DENOM_AS_REMAINING_PARTS`
    - `explanation_m`: "5 is the number of slices left over ($8 - 3 = 5$). The denominator must represent the total equal slices the pizza was originally cut into."
  - Distractor 3: `11`
    - `misconception_id`: `MISC_DENOM_AS_SUM_OF_PARTS`
    - `explanation_m`: "Adding the eaten slices and total slices ($3 + 8$) gives 11. The denominator is simply the total number of equal slices in the whole pizza."
- **ZERO-SPOILER COMPLIANCE**: Verified. None of the misconception explanations state "The correct answer is 8".
- **SCORING**:
  - *Attempt 1 Correct*: +10 XP, `diagnostic_result: PASS`, recorded in diagnostic ledger.
  - *Attempt 1 Wrong*: 0 XP, `diagnostic_result: FAIL(misconception_id)`, recorded in diagnostic ledger.
  - *Attempt 2+ Correct*: +5 Practice XP, recorded in progression ledger only.
- **MASTERY RULE**: Diagnostic mastery requires first-attempt pass on 3 distinct concept questions.
- **RETRY RULE**: Student can retry indefinitely; retry button activates immediately after reading verbal feedback.

---

### ASSESSMENT ITEM: ASM-PA-002
- **ASSESSMENT ID**: ASM-PA-002
- **CURRICULUM OBJECTIVE**: Grade 7 Perimeter & Area — Boundary vs Space
- **SKILL**: Differentiate units of measurement for perimeter and area.
- **QUESTION**: "Ravi builds a rectangular fence around his garden of length 6 meters and width 4 meters. Which measurement describes the total length of wire required?"
- **TASK TYPE**: Multiple Choice (4 Shuffled Options).
- **DIFFICULTY**: Intermediate (Tier 2).
- **EXPECTED RESPONSE**: `20 meters` (`c: true`)
- **DISTRACTORS & MISCONCEPTIONS**:
  - Distractor 1: `24 square meters`
    - `misconception_id`: `MISC_CALCULATED_AREA_INSTEAD_OF_PERIMETER`
    - `explanation_m`: "Multiplying length by width ($6 \times 4 = 24$) calculates the area of the garden ground in square meters, not the outer boundary fence length."
  - Distractor 2: `10 meters`
    - `misconception_id`: `MISC_SUMMED_TWO_SIDES_ONLY`
    - `explanation_m`: "Adding just length and width ($6 + 4 = 10$) gives only half the fence. A rectangle has four boundary sides that must all be fenced."
  - Distractor 3: `20 square meters`
    - `misconception_id`: `MISC_INCORRECT_UNIT_DIMENSIONALITY`
    - `explanation_m`: "The boundary length calculation ($2 \times (6 + 4) = 20$) is correct, but fence length is measured in linear meters, not square meters."
- **SCORING**: TEAS Two-tier standard.
- **EVIDENCE**: Tested via `Generalization: Question Engine intercepts perimeter vs area cognitive misconceptions` (Node test 10 passing).
