# 13_LEARNING_CONTRACT.md
# Pedagogical & Learning Experience Contracts

Showing content does NOT prove learning. Every interactive educational module must be governed by an explicit Learning Contract that establishes measurable criteria for conceptual understanding.

---

### CONTRACT LC-001: Fractions — Conceptual Representation of Parts of a Whole
- **CONTRACT ID**: LC-001
- **TARGET GRADE**: Grade 4 (Mathematics)
- **LEARNING OBJECTIVE**: Student can define a fraction as equal parts of a single whole and correctly identify the numerator (parts considered) and denominator (total equal parts) up to denominators of 12.
- **PREREQUISITES**: Whole number counting (1–100), basic division concept (equal sharing).
- **CONCEPT**: A fraction represents one or more equal parts of a unit whole. If parts are unequal, fractional notation cannot be directly applied.
- **SKILL**: Partitioning a shape, counting shaded parts vs total parts, constructing symbolic representation $\frac{a}{b}$.
- **KNOWLEDGE STATE**:
  - `STATE_0_NAIVE`: Treats numerator and denominator as two independent unrelated integers.
  - `STATE_1_PARTIAL`: Understands denominator is total parts, but ignores whether parts are equal.
  - `STATE_2_COMPETENT`: Correctly identifies $\frac{a}{b}$ with equal partitions; understands $b \neq 0$.
  - `STATE_3_MASTER`: Can predict relative size (e.g., $\frac{1}{4} < \frac{1}{2}$) and apply to word problems.
- **LEARNING ACTIVITY**: Interactive Fraction Bar manipulative where dragging or tapping adjusts division lines and shading.
- **VISUALIZATION**: Responsive SVG bar with toggleable equal slices and dual numeric readouts.
- **INTERACTION**: Tap-to-partition, tap-to-shade (drag-and-drop prohibited).
- **PRACTICE**: 3 diagnostic formative assessment items per node.
- **FEEDBACK**: Distractor-specific verbal explanations addressing common misinterpretations.
- **MASTERY SIGNAL**: Student achieves first-attempt correct answer on 3 consecutive diagnostic questions across different partition types.
- **MISCONCEPTION SIGNAL**:
  - `MISC-FRAC-01`: Student counts shaded vs unshaded parts instead of shaded vs total (e.g., answering $\frac{3}{1}$ instead of $\frac{3}{4}$).
  - `MISC-FRAC-02`: Student treats unequal slices as valid fractional halves.
  - `MISC-FRAC-03`: Inverse denominator fallacy (assuming $\frac{1}{8} > \frac{1}{4}$ because $8 > 4$).
- **ADAPTATION & REMEDIATION**: If `MISC-FRAC-01` is triggered, the interactive bar dynamically flashes the entire bar outline to reinforce "total parts in the whole" before allowing retry.
- **EXTENSION**: Introduction to equivalent fractions on a number line.

---

### CONTRACT LC-002: Perimeter vs. Area — Boundary vs. Surface Differentiation
- **CONTRACT ID**: LC-002
- **TARGET GRADE**: Grade 7 (Mathematics)
- **LEARNING OBJECTIVE**: Student clearly differentiates between 1D perimeter (boundary length) and 2D area (enclosed surface) and calculates both for rectilinear shapes.
- **PREREQUISITES**: Multi-digit addition and multiplication, units of measurement (cm, m).
- **CONCEPT**:
  - Perimeter is linear distance around the outside ($P = \sum \text{sides}$, units: cm, m).
  - Area is the amount of 2D space inside ($A = \text{length} \times \text{width}$, units: $\text{cm}^2$, $\text{m}^2$).
- **KNOWLEDGE STATE**:
  - `STATE_CONFUSED`: Mixes up formulas (e.g. multiplies sides to find perimeter, or adds side lengths to find area).
  - `STATE_DIFFERENTIATED`: Computes both accurately with correct linear and square units.
- **LEARNING ACTIVITY**: 2D Grid Area manipulative where students trace outer fences vs tile inner squares.
- **VISUALIZATION**: Interactive SVG grid where perimeter highlights in orange border path and area highlights in green filled tiles.
- **MASTERY SIGNAL**: Correctly solves perimeter and area for irregular rectilinear shapes on first attempt.
- **MISCONCEPTION SIGNAL**:
  - `MISC-PA-01`: Multiplies all four sides to find perimeter.
  - `MISC-PA-02`: Uses linear units (cm) for area or square units ($\text{cm}^2$) for perimeter.
- **ADAPTATION & REMEDIATION**: Triggers visual border animation walking a character along the fence line when perimeter error occurs.
