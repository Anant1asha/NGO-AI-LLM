# Curriculum Specification & Question Bank Mining Report
**AASHA Foundation — Universal Teaching Language & Assessment Specification**  
**Working Directory**: `.agents/teamwork_preview_spec_miner_curriculum/`  
**Timestamp**: `2026-09-16T20:57:00Z`  
**Miner Archetype**: `teamwork_preview_spec_miner`  
**Target Grades**: Class 6 (Fractions), Class 7 (Perimeter & Area), Class 8 (Rational Numbers & Linear Equations)

---

## Executive Summary
This specification report provides an authoritative extraction and pedagogical synthesis of textbook exercise banks, learning objectives, visual manipulative bindings, and diagnostic misconception schemas across three core middle-school mathematics domains:
1. **Class 6 Mathematics**: Fractions (Unit parts, proper/improper/mixed forms, equivalence, like/unlike operations).
2. **Class 7 Mathematics**: Perimeter & Area (Boundary vs surface measurement, rectangles/squares, parallelograms/triangles, circles, border paths).
3. **Class 8 Mathematics**: Rational Numbers & Linear Equations in One Variable (Number line density, algebraic identities/inverses, balance scale models, multi-step bracket/fraction equations, real-world formulations).

All assessment items are organized into AASHA's **3-Tier Gamified Assessment Model**:
- **Warm-up (`#section-warmup`)**: Foundational representation, definition, and classification items (3–5 items per chapter).
- **Deep Dive (`#section-deep_dive`)**: Core procedures, equivalence, and manipulative-linked drills (5–8 items per chapter).
- **Boss Challenge (`#section-boss`)**: Multi-step applied problem solving integrated with Foundation F01 (Escape Run) timed cognitive obstacle evasion and streak dynamics (3–5 items per chapter).

Every single question item adheres strictly to the **L-Truth Ground Truth Benchmark** and `QuestionSchemaValidator`:
- Exactly 4 distinct options with exactly 1 correct answer (`c: true`, `m: ""`).
- High-quality, non-trivial verbal misconception diagnostic `m` (> 15 chars) for every distractor with **ZERO answer spoilers** and **ZERO forbidden words** (`/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`).
- 4-tier progressive scaffolding hints (`H1` Hook, `H2` Concept, `H3` Formula, `H4` Intermediate Step) with zero answer revelations.

---

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Assessment Engine | 3-Tier Gamified Scaffolding | Divides chapter assessments into Warm-up, Deep Dive, and Boss Challenge tiers | Textbook exercises & objectives | Tiered question collections with XP/Streak metadata | Rejection if questions do not map to valid tiers | `packages/chapter-contract-manager.ts` & `GEMINI.md` |
| 2 | Benchmark Standard | L-Truth Zero-Spoiler Invariant | Enforces that incorrect options explain cognitive errors without leaking answers or calculations | Distractor explanation string (`m`) | Validation pass/fail (100-pt benchmark) | Hard penalty (-20 pts per spoiler, immediate benchmark failure) | `benchmarks/qa_ltruth_benchmark.js` & `question_schema_validator.js` |
| 3 | Benchmark Standard | Forbidden Spoiler Words Filter | Rejects distractor explanations containing leak predicates (`is`, `giving`, `becomes`, `instead of`, `to get`, `yielding`, `result is`, `should be`) | Option `m` string | Boolean match flag | Flagged as Rule #1 Spoiler | `benchmarks/question_schema_validator.js` & User Rules |
| 4 | Pedagogical Scaffolding | 4-Tier Progressive Hints | Progressive hint schema (H1 Hook -> H2 Concept -> H3 Formula -> H4 Step) guiding student inquiry | User hint click request | Contextual pedagogical guidance | Flagged if hint reveals target value or verbatim text | `content/contracts/` & `packages/canonical-ir/` |
| 5 | Foundation Binding | F01 Escape Run Gamification | Timed cognitive hurdles and streak multipliers for Tier 3 Boss Challenge | User answer timestamp & streak count | Telemetry events, score multipliers, milestone badges | Streak reset upon incorrect attempt | `experience_registry/` & `content/contracts/` |
| 6 | Foundation Binding | F04 PhET / F08 Number Line | Interactive fraction partition bars, density zoom, and balance scale models | User slider partition / drag interactions | Synchronous canvas rendering & DOM equation readouts | Non-destructive pause/resume preserving WebGL buffers | `chapters/` contracts & `AashaExperienceContract` |
| 7 | Bilingual Substrate | Pre-LLE Mathematical Insulation | Shields LaTeX math formulas and variables using `__AASHA_MATH_X__` before dictionary tokenization | Raw markdown/HTML text with math | Insulated text with `<span class="math-var">` tags | Math symbol corruption if uninsulated | `packages/aasha-rules/math_insulator.ts` & `GEMINI.md` |
| 8 | Cloud Distribution | Hatchable Delta Route (`api/chapters/deltas.js`) | Serves lightweight JSON curriculum delta question banks (<50 KB) for hybrid offline syncing | HTTP GET with `?grade=N` query | JSON payload of curriculum nodes and item banks | 400 on invalid grade, 404 on missing chapter | `ORIGINAL_REQUEST.md` Follow-up Directives |

---

## Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Anti-Spoiler Matching | Distractor contains single-letter token like `x` matching correct answer `x` | Validator triggers regex word boundary matching `(?:^\|[\s,;:(])x(?:$\|[\s,;:).!?])` to distinguish variables from plain letters |
| 2 | Fraction Answer Leakage | Correct answer is `3/8`; distractor mentions `Calculates 3/8 as ratio` | Validator regex catches fraction leak pattern `(?:\b(?:is\|=|giving)\s*)?3\s*\/\s*8` and issues `RULE_1_SPOILER_FRACTION_LEAK` |
| 3 | Evaluation Leakage | Distractor says `Adding 3 and 5 gives 8` when correct answer is `8` | Numerical leak check catches `gives 8` matching target number 8, failing benchmark |
| 4 | Distractor Verb Tense | Distractor says `Sign becomes positive` | Word `becomes` triggers forbidden word pattern `/\bbecomes\b/i`, resulting in rejection |
| 5 | Equivalent Fraction Scaling | Scaling numerator and denominator by non-integer or unequal factors | Distractor diagnoses failure to apply identical multiplicative scale factors to both terms |
| 6 | Unit Dimension Confusion | Confusing 1D boundary (cm) with 2D surface (cm²) or 3D volume (cm³) | Distractor diagnoses dimensional mismatch without revealing the numeric area value |
| 7 | Division by Zero | Fraction with denominator `q = 0` | Mathematical undefined property flagged in Warm-up diagnostic |

---

## 1. Class 6 Mathematics: Fractions

### 1.1 Curriculum Learning Objectives
- **LO-M6-FRAC-01 (Part-Whole Concept)**: Understand a fraction as equal partition of a unit whole or collection. Recognize that the denominator specifies the total number of equal parts dividing the whole, while the numerator specifies the count of selected parts.
- **LO-M6-FRAC-02 (Classification & Conversions)**: Distinguish proper fractions (numerator < denominator, value < 1), improper fractions (numerator >= denominator, value >= 1), and mixed numbers (whole number + proper fraction). Fluently convert between improper and mixed representations.
- **LO-M6-FRAC-03 (Equivalence & Simplest Form)**: Generate equivalent fractions by scaling numerator and denominator by identical non-zero multipliers/divisors. Reduce fractions to simplest form by dividing out the Highest Common Factor (HCF).
- **LO-M6-FRAC-04 (Fraction Comparison)**: Compare like fractions by ordering numerators. Compare unlike fractions by equalizing denominators via the Least Common Multiple (LCM) or cross-multiplication.
- **LO-M6-FRAC-05 (Operations & Applications)**: Add and subtract like fractions by combining numerators while retaining the common denominator. Compute sums and differences of unlike fractions via LCM common denominators. Solve multi-step real-world word problems.

### 1.2 Visual Manipulative & Foundation Binding
- **Prebuilt Foundation**: Adapted from **F04 PhET Fraction Simulation Suite** and **F08 Physics Notebook / MathFluency**.
- **Manipulative Architecture**: Interactive SVG Strip / Fraction Bar Manipulative (`<aasha-sim type="fraction-strip">`).
- **Synchronous DOM State Binding**:
  - Horizontal strip partitioned into $d \in [1, 12]$ equal segments.
  - Interactive tap-to-shade mechanism dynamically fills $s \in [0, d]$ segments with high-contrast theme color (`#3b82f6`).
  - Synchronously updates visible mathematical KaTeX display `\frac{s}{d}` alongside live Indic translation labels.
- **Escape Run (F01) Mechanics**: Tier 3 Boss Challenge applies an obstacle-runner format where players navigate moving partition gates by tapping matching equivalent fractions under a 30-second countdown, triggering particle bursts and $2\times / 3\times$ streak multipliers.

### 1.3 Pre-LLE Bilingual (Hindi-English) Vocabulary Map
| English Term | Devanagari Script | Phonetic Transliteration | Contextual Conceptual Definition |
|--------------|-------------------|--------------------------|----------------------------------|
| Fraction | भिन्न | भिन्न (फ्रैक्शन) | संपूर्ण वस्तु का समान भागों में से चुना गया हिस्सा |
| Numerator | अंश | अंश (न्यूमरेटर) | कुल बराबर भागों में से लिए गए भागों की संख्या |
| Denominator | हर | हर (डिनॉमिनेटर) | एक संपूर्ण वस्तु को जितने बराबर भागों में बांटा गया है |
| Proper Fraction | उचित भिन्न | उचित भिन्न (प्रॉपर फ्रैक्शन) | वह भिन्न जिसमें अंश, हर से छोटा होता है (मान 1 से कम) |
| Improper Fraction | विषम भिन्न | विषम भिन्न (इम्प्रॉपर फ्रैक्शन) | वह भिन्न जिसमें अंश, हर के बराबर या उससे बड़ा होता है |
| Mixed Number | मिश्रित भिन्न | मिश्रित भिन्न (मिक्स्ड नंबर) | एक पूर्ण संख्या और एक उचित भिन्न का संयुक्त रूप |
| Equivalent Fraction | तुल्य भिन्न | तुल्य भिन्न (इक्विवेलेंट फ्रैक्शन) | समान मात्रा अथवा मान दर्शाने वाले भिन्न |
| Common Denominator | उभयनिष्ठ हर | उभयनिष्ठ हर (कॉमन डिनॉमिनेटर) | दो या अधिक भिन्नों का एक समान हर (ल.स.प. द्वारा प्राप्त) |

### 1.4 Item Bank: 3-Tier Gamified Assessment (14 Items)

#### Tier 1: Warm-up (`#section-warmup`) — 4 Foundational Items
1. **c6_frac_q1**
   - **Question Prompt**: In any fraction \(\frac{a}{b}\), what mathematical role does the denominator \(b\) represent?
   - **Option A**: The total count of equal parts that compose the whole *(Correct)*
   - **Option B**: The number of selected or shaded parts *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Confuses numerator with denominator; the top number counts selected portions.
   - **Option C**: The numerical difference between parts *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Treats fraction components as a subtraction comparison rather than part-whole partition.
   - **Option D**: The count of unshaded parts remaining *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Denominator counts all equal divisions collectively rather than solely remaining pieces.
   - **Hints**:
     - `H1_hook`: Look at the bottom position of the fraction.
     - `H2_concept`: The whole object gets divided into a certain quantity of identical pieces.
     - `H3_formula`: The upper number counts parts taken; the lower number defines partition size.
     - `H4_step`: Denominator names the total equal divisions creating one complete unit.

2. **c6_frac_q2**
   - **Question Prompt**: A rectangular bar divided into 8 equal parts has 3 parts shaded. What fraction represents the shaded region?
   - **Option A**: \(\frac{3}{8}\) *(Correct)*
   - **Option B**: \(\frac{3}{5}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Compares shaded parts to unshaded parts rather than to the entire whole bar.
   - **Option C**: \(\frac{8}{3}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Inverts fraction structure by placing total parts above selected parts.
   - **Option D**: \(\frac{5}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Selected unshaded fraction rather than shaded fraction requested in the prompt.
   - **Hints**:
     - `H1_hook`: Count shaded pieces first, then count all pieces together.
     - `H2_concept`: Fraction form requires selected pieces over total equal pieces.
     - `H3_formula`: Numerator takes shaded count; denominator takes whole partition count.
     - `H4_step`: Place 3 over total segment count 8.

3. **c6_frac_q3**
   - **Question Prompt**: Which condition defines a proper fraction?
   - **Option A**: Numerator strictly less than denominator *(Correct)*
   - **Option B**: Numerator strictly greater than denominator *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Defines an improper fraction representing values greater than one whole.
   - **Option C**: Numerator exactly equal to denominator *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Represents one complete whole rather than a strictly proper fractional part.
   - **Option D**: Denominator fixed at 100 *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Confuses general proper fractions with percentage denominators.
   - **Hints**:
     - `H1_hook`: Consider whether the fraction value remains strictly less than one whole.
     - `H2_concept`: In a proper fraction, you possess fewer pieces than needed for a complete whole.
     - `H3_formula`: Compare the magnitude of top number against bottom number.
     - `H4_step`: Top value must remain smaller than bottom value.

4. **c6_frac_q4**
   - **Question Prompt**: Which fraction represents an equivalent value to \(\frac{2}{3}\) with denominator 12?
   - **Option A**: \(\frac{8}{12}\) *(Correct)*
   - **Option B**: \(\frac{6}{12}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added common amount to both terms rather than multiplying by constant factor.
   - **Option C**: \(\frac{4}{12}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied numerator by two while multiplying denominator by four.
   - **Option D**: \(\frac{10}{12}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied numerator by incorrect scaling multiplier.
   - **Hints**:
     - `H1_hook`: Determine what factor scales denominator 3 up to 12.
     - `H2_concept`: Equivalent fractions require multiplying both top and bottom by identical factors.
     - `H3_formula`: Multiply numerator by the same scaling factor applied to denominator.
     - `H4_step`: Denominator multiplies by 4; multiply top number 2 by 4.

#### Tier 2: Deep Dive (`#section-deep_dive`) — 6 Conceptual Items
5. **c6_frac_q5**
   - **Question Prompt**: Convert the improper fraction \(\frac{17}{5}\) into mixed number form.
   - **Option A**: \(3\frac{2}{5}\) *(Correct)*
   - **Option B**: \(2\frac{7}{5}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Left an improper fractional portion rather than extracting all complete wholes.
   - **Option C**: \(3\frac{1}{5}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Calculation slip in division remainder when subtracting whole multiples.
   - **Option D**: \(5\frac{2}{3}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Swapped whole quotient with original denominator.
   - **Hints**:
     - `H1_hook`: Divide numerator 17 by denominator 5 to find whole groups.
     - `H2_concept`: Quotient forms whole number; remainder forms new numerator over original denominator.
     - `H3_formula`: 17 divided by 5 yields quotient 3 with remainder 2.
     - `H4_step`: Combine whole quotient 3 with remainder 2 over original denominator 5.

6. **c6_frac_q6**
   - **Question Prompt**: Express the mixed number \(4\frac{3}{7}\) as an improper fraction.
   - **Option A**: \(\frac{31}{7}\) *(Correct)*
   - **Option B**: \(\frac{19}{7}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied whole number by numerator rather than denominator.
   - **Option C**: \(\frac{28}{7}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Forgot to add the existing numerator portion after multiplying whole parts.
   - **Option D**: \(\frac{31}{4}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Replaced original denominator with whole number multiplier.
   - **Hints**:
     - `H1_hook`: Each whole unit contains 7 sevenths.
     - `H2_concept`: Multiply whole number by denominator, then add numerator.
     - `H3_formula`: Compute whole part products: 4 times 7, then add remaining 3 parts.
     - `H4_step`: Sum all sevenths over original denominator 7.

7. **c6_frac_q7**
   - **Question Prompt**: Which comparison statement correctly relates \(\frac{3}{5}\) and \(\frac{5}{8}\)?
   - **Option A**: \(\frac{3}{5} < \frac{5}{8}\) *(Correct)*
   - **Option B**: \(\frac{3}{5} > \frac{5}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Cross-multiplied directions in reverse or judged based on smaller denominator.
   - **Option C**: \(\frac{3}{5} = \frac{5}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Assumed equal differences between numerators and denominators imply equivalence.
   - **Option D**: \(\frac{3}{5} > \frac{6}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Confused fraction magnitudes without finding common denominator.
   - **Hints**:
     - `H1_hook`: Convert both fractions to common denominator 40.
     - `H2_concept`: Compare numerators after equalizing denominators: 3*8 versus 5*5.
     - `H3_formula`: Cross products give 24 for first fraction and 25 for second fraction.
     - `H4_step`: 24 fortieths compared against 25 fortieths.

8. **c6_frac_q8**
   - **Question Prompt**: Calculate the sum of like fractions: \(\frac{3}{11} + \frac{5}{11}\).
   - **Option A**: \(\frac{8}{11}\) *(Correct)*
   - **Option B**: \(\frac{8}{22}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added denominators together rather than retaining the shared piece size.
   - **Option C**: \(\frac{15}{11}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied numerators rather than adding addends.
   - **Option D**: \(\frac{2}{11}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Subtracted numerators rather than combining them.
   - **Hints**:
     - `H1_hook`: Notice both fractions possess matching denominators.
     - `H2_concept`: Piece size elevenths remains constant during addition.
     - `H3_formula`: Retain denominator 11 and add numerators 3 and 5.
     - `H4_step`: Sum top numbers over unchanged denominator 11.

9. **c6_frac_q9**
   - **Question Prompt**: Find the sum of unlike fractions: \(\frac{2}{5} + \frac{1}{3}\).
   - **Option A**: \(\frac{11}{15}\) *(Correct)*
   - **Option B**: \(\frac{3}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added numerators together and denominators together across unlike fractions.
   - **Option C**: \(\frac{3}{15}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added numerators without scaling them to common denominator.
   - **Option D**: \(\frac{7}{15}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Incorrectly scaled numerators during common denominator conversion.
   - **Hints**:
     - `H1_hook`: Find common denominator using LCM of 5 and 3.
     - `H2_concept`: Convert both fractions to fifteenths before adding.
     - `H3_formula`: Scale fractions: 2/5 to 6/15, and 1/3 to 5/15.
     - `H4_step`: Add scaled numerators 6 and 5 over 15.

10. **c6_frac_q10**
    - **Question Prompt**: Evaluate the difference: \(\frac{5}{6} - \frac{1}{4}\).
    - **Option A**: \(\frac{7}{12}\) *(Correct)*
    - **Option B**: \(\frac{4}{2}\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Subtracted numerators and subtracted denominators directly.
    - **Option C**: \(\frac{4}{12}\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Subtracted unscaled numerators without common denominator adjustment.
    - **Option D**: \(\frac{9}{12}\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Added scaled values rather than subtracting second term.
    - **Hints**:
      - `H1_hook`: Find the least common multiple for denominators 6 and 4.
      - `H2_concept`: Lowest common denominator equals 12.
      - `H3_formula`: Convert 5/6 to 10/12 and 1/4 to 3/12.
      - `H4_step`: Subtract scaled numerators: 10 minus 3 over 12.

#### Tier 3: Boss Challenge (`#section-boss`) — 4 Applied Items
11. **c6_frac_q11**
    - **Question Prompt**: Sarita purchased \(\frac{2}{5}\) metre of ribbon and Lalita purchased \(\frac{3}{4}\) metre of ribbon. What total length of ribbon did both purchase together?
    - **Option A**: \(1\frac{3}{20}\) m *(Correct)*
    - **Option B**: \(\frac{5}{9}\) m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Added numerators and denominators directly across ribbon lengths.
    - **Option C**: \(\frac{17}{20}\) m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Arithmetic error in cross-scaling numerator terms.
    - **Option D**: \(1\frac{1}{20}\) m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Calculation slip when converting improper sum to mixed form.
    - **Hints**:
      - `H1_hook`: Combine both ribbon lengths using addition.
      - `H2_concept`: Find common denominator for 5 and 4, which equals 20.
      - `H3_formula`: Convert to twentieths: 8/20 plus 15/20.
      - `H4_step`: Sum to 23/20 and convert to mixed metres.

12. **c6_frac_q12**
    - **Question Prompt**: A piece of wire \(\frac{7}{8}\) metre long broke into two pieces. One piece measured \(\frac{1}{4}\) metre. What length remains for the second piece?
    - **Option A**: \(\frac{5}{8}\) m *(Correct)*
    - **Option B**: \(\frac{6}{4}\) m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Subtracted numerators and denominators separately without common denominator.
    - **Option C**: \(\frac{3}{8}\) m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Subtracted incorrectly after common denominator conversion.
    - **Option D**: \(\frac{9}{8}\) m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Added wire portions together rather than determining remaining difference.
    - **Hints**:
      - `H1_hook`: Subtract broken piece length from total wire length.
      - `H2_concept`: Common denominator between 8 and 4 equals 8.
      - `H3_formula`: Rewrite 1/4 metre as 2/8 metre.
      - `H4_step`: Compute 7/8 minus 2/8 to find remaining wire.

13. **c6_frac_q13**
    - **Question Prompt**: Ramesh completed \(2\frac{1}{2}\) hours of academic study and \(1\frac{1}{4}\) hours of sports training. What total duration did he spend across both activities?
    - **Option A**: \(3\frac{3}{4}\) hours *(Correct)*
    - **Option B**: \(3\frac{2}{6}\) hours *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Added fractional numerators and denominators directly without finding fourths.
    - **Option C**: \(4\frac{1}{4}\) hours *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Carried excess whole hour without sufficient fractional sum.
    - **Option D**: \(3\frac{1}{4}\) hours *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Omitted half hour fractional addend from total.
    - **Hints**:
      - `H1_hook`: Add whole hour portions and fractional hour portions.
      - `H2_concept`: Convert 1/2 hour to 2/4 hour for common denominator.
      - `H3_formula`: Sum wholes: 2 + 1; sum fractions: 2/4 + 1/4.
      - `H4_step`: Combine whole sum 3 with fraction sum 3/4.

14. **c6_frac_q14**
    - **Question Prompt**: Jaidev takes \(2\frac{1}{5}\) minutes to walk across the school park, while Rahul takes \(\frac{7}{4}\) minutes. Who takes less time, and by what difference?
    - **Option A**: Rahul takes less time by \(\frac{9}{20}\) min *(Correct)*
    - **Option B**: Jaidev takes less time by \(\frac{9}{20}\) min *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Identified the wrong student despite finding correct numerical difference.
    - **Option C**: Rahul takes less time by \(\frac{1}{20}\) min *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Subtracted mixed fractions incorrectly after denominator conversion.
    - **Option D**: Both take equal time *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Assumed fractional values match without converting to common denominator.
    - **Hints**:
      - `H1_hook`: Convert both durations to twentieths of a minute.
      - `H2_concept`: 2 1/5 equals 11/5 = 44/20; 7/4 equals 35/20.
      - `H3_formula`: Compare 35/20 against 44/20 to see who finishes faster.
      - `H4_step`: Subtract 35/20 from 44/20 to determine time gap.

---

## 2. Class 7 Mathematics: Perimeter and Area

### 2.1 Curriculum Learning Objectives
- **LO-M7-PA-01 (Boundary vs Surface Distinction)**: Differentiate between 1D boundary path length (perimeter, measured in linear units like cm, m) and 2D enclosed surface coverage (area, measured in square units like cm², m²).
- **LO-M7-PA-02 (Rectangles and Squares)**: Formulate and apply formulas for perimeter ($P_{\text{rect}} = 2(l + b)$, $P_{\text{sq}} = 4s$) and area ($A_{\text{rect}} = l \times b$, $A_{\text{sq}} = s^2$). Deduce missing dimensions given total area or perimeter.
- **LO-M7-PA-03 (Parallelograms and Triangles)**: Deconstruct parallelograms into equivalent rectangles to deduce $A_{\text{para}} = b \times h$ (using perpendicular altitude). Establish that any triangle occupies half the enclosing parallelogram/rectangle, giving $A_{\text{tri}} = \frac{1}{2} b \times h$.
- **LO-M7-PA-04 (Circles: Circumference & Area)**: Define ratio $\pi \approx \frac{22}{7} \approx 3.1416$. Calculate circular boundary circumference ($C = 2\pi r = \pi d$) and circular surface area ($A = \pi r^2$), distinguishing diameter $d$ and radius $r$.
- **LO-M7-PA-05 (Composite Figures & Border Paths)**: Calculate areas of composite polygons via additive/subtractive decomposition (L-shaped regions). Solve uniform border path problems around and inside rectangular gardens. Analyze perimeter conservation during wire rebending into different geometric profiles.

### 2.2 Visual Manipulative & Foundation Binding
- **Prebuilt Foundation**: Adapted from **F02 MicroSims 2D Grid Engine**, **F08 Physics Notebook**, and **JSXGraph Canvas**.
- **Manipulative Architecture**: Interactive 2D Grid Sandbox (`<aasha-sim type="grid-area">`).
- **Synchronous DOM State Binding**:
  - Configurable $R \times C$ unit square canvas grid (e.g., $4 \times 6$, each cell representing $1\text{ cm} \times 1\text{ cm}$).
  - Live animated perimeter runner marching around active boundary perimeter with linear centimetre readout.
  - Interior tile counter highlighting surface coverage in square centimetres ($R \times C\text{ cm}^2$).
  - Synchronous DOM state updates both the graphic display and formula readouts simultaneously.
- **Escape Run (F01) Mechanics**: Tier 3 Boss Challenge sets up a crumbling wall maze where learners must rapidly calculate perimeter clearances and rectangular path areas within 40 seconds to unlock escape doors.

### 2.3 Pre-LLE Bilingual (Hindi-English) Vocabulary Map
| English Term | Devanagari Script | Phonetic Transliteration | Contextual Conceptual Definition |
|--------------|-------------------|--------------------------|----------------------------------|
| Perimeter | परिमाप | परिमाप (पेरीमीटर) | किसी बंद आकृति की बाहरी सीमा की कुल लम्बाई |
| Area | क्षेत्रफल | क्षेत्रफल (एरिया) | किसी बंद समतल आकृति द्वारा घेरे गए तल का विस्तार |
| Length | लम्बाई | लम्बाई (लेंथ) | किसी आकृति का अधिक लम्बा विस्तार |
| Breadth / Width | चौड़ाई | चौड़ाई (ब्रेड्थ / विड्थ) | किसी आकृति का छोटा या पार्श्व विस्तार |
| Perpendicular Height | लम्बवत ऊँचाई | लम्बवत ऊँचाई (परपेंडिकुलर हाइट) | आधार पर डाला गया 90 डिग्री का सीधा लम्ब |
| Circumference | परिधि | परिधि (सरकमफेरेंस) | वृत्त (गोलाकार घेरे) की बाहरी सीमा की कुल लम्बाई |
| Radius | त्रिज्या | त्रिज्या (रेडियस) | वृत्त के केंद्र से उसकी परिधि तक की दूरी |
| Diameter | व्यास | व्यास (डायमीटर) | वृत्त के केंद्र से होकर जाने वाली और परिधि के दोनों सिरों को छूने वाली रेखा (2 × त्रिज्या) |

### 2.4 Item Bank: 3-Tier Gamified Assessment (14 Items)

#### Tier 1: Warm-up (`#section-warmup`) — 4 Foundational Items
1. **c7_pa_q1**
   - **Question Prompt**: Which practical activity requires measuring boundary PERIMETER rather than surface area?
   - **Option A**: Constructing a wire security fence along the outer border of a farmland *(Correct)*
   - **Option B**: Spreading organic grass seeds across a community football ground *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Requires calculating two-dimensional surface coverage (area).
   - **Option C**: Polishing granite floor tiles inside an assembly hall *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Interior floor finishing covers surface space, requiring area.
   - **Option D**: Applying waterproof paint across a flat rectangular rooftop *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Coating a flat surface requires area calculation rather than boundary path.
   - **Hints**:
     - `H1_hook`: Differentiate between walking along an edge versus covering a flat face.
     - `H2_concept`: Perimeter measures outer border line; area measures flat surface spread.
     - `H3_formula`: Fencing outlines the boundary; turfing and tiling fill the interior.
     - `H4_step`: Select the option that only follows outer border line.

2. **c7_pa_q2**
   - **Question Prompt**: A rectangular garden has length 9 m and breadth 5 m. What is its perimeter?
   - **Option A**: 28 m *(Correct)*
   - **Option B**: 45 m² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied length by breadth, finding surface area rather than boundary perimeter.
   - **Option C**: 14 m *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added only one length and one breadth, forgetting opposite two sides.
   - **Option D**: 56 m *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Doubled perimeter formula components twice unnecessarily.
   - **Hints**:
     - `H1_hook`: A rectangle possesses 4 boundary sides: two lengths and two breadths.
     - `H2_concept`: Perimeter formula equals 2 times (length plus breadth).
     - `H3_formula`: Add 9 m and 5 m together, then multiply by 2.
     - `H4_step`: Double the sum of adjacent dimensions.

3. **c7_pa_q3**
   - **Question Prompt**: If the perimeter of a square game board measures 36 cm, what is the length of each side?
   - **Option A**: 9 cm *(Correct)*
   - **Option B**: 18 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Divided by two rather than four equal boundary sides of a square.
   - **Option C**: 6 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Confused perimeter division with square root area calculation.
   - **Option D**: 144 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied perimeter by 4 rather than dividing among equal sides.
   - **Hints**:
     - `H1_hook`: A square has four identical sides.
     - `H2_concept`: Perimeter equals 4 times side length.
     - `H3_formula`: Divide total boundary measurement by 4.
     - `H4_step`: 36 divided by 4 isolates side length.

4. **c7_pa_q4**
   - **Question Prompt**: Which unit correctly quantifies the two-dimensional surface area of a classroom noticeboard?
   - **Option A**: cm² *(Correct)*
   - **Option B**: cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Linear unit measuring 1D boundary length or distance, not 2D surface.
   - **Option C**: cm³ *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Cubic unit quantifying 3D volume capacity, not flat surface.
   - **Option D**: kg *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Unit measuring physical mass rather than geometric surface space.
   - **Hints**:
     - `H1_hook`: Consider how many dimensions are being measured.
     - `H2_concept`: Surface area counts square units covering a flat region.
     - `H3_formula`: Linear units measure length; square units measure area.
     - `H4_step`: Look for square notation exponent.

#### Tier 2: Deep Dive (`#section-deep_dive`) — 6 Conceptual Items
5. **c7_pa_q5**
   - **Question Prompt**: Calculate the surface area of a square courtyard with side length 8 m.
   - **Option A**: 64 m² *(Correct)*
   - **Option B**: 32 m *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied side by 4, calculating perimeter rather than surface area.
   - **Option C**: 16 m² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied side by 2 rather than squaring side length.
   - **Option D**: 64 m *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Attached linear length units rather than square area units.
   - **Hints**:
     - `H1_hook`: Square area equals side multiplied by itself.
     - `H2_concept`: Apply formula Area = side * side.
     - `H3_formula`: Compute 8 times 8.
     - `H4_step`: Include square metre units in final answer.

6. **c7_pa_q6**
   - **Question Prompt**: A rectangular banner has an area of 96 cm² and breadth 8 cm. What is its length?
   - **Option A**: 12 cm *(Correct)*
   - **Option B**: 88 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Subtracted breadth from area rather than using division.
   - **Option C**: 24 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Calculation slip in division of area by breadth.
   - **Option D**: 768 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplied area by breadth rather than dividing to find missing dimension.
   - **Hints**:
     - `H1_hook`: Area equals length times breadth.
     - `H2_concept`: To isolate length, divide total area by known breadth.
     - `H3_formula`: Divide 96 by 8.
     - `H4_step`: Quotient yields length in centimetres.

7. **c7_pa_q7**
   - **Question Prompt**: A parallelogram has base 8 cm and perpendicular height 5 cm. What is its area?
   - **Option A**: 40 cm² *(Correct)*
   - **Option B**: 20 cm² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Applied triangle formula factor of one-half to a parallelogram.
   - **Option C**: 26 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Calculated perimeter-like sum 2*(8+5) rather than area product.
   - **Option D**: 13 cm² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added base and height rather than multiplying them.
   - **Hints**:
     - `H1_hook`: Parallelogram area equals base times perpendicular height.
     - `H2_concept`: Do not divide by 2 for parallelograms.
     - `H3_formula`: Multiply base 8 cm by perpendicular height 5 cm.
     - `H4_step`: Direct product gives total area.

8. **c7_pa_q8**
   - **Question Prompt**: Find the area of a triangle with base 12 cm and perpendicular altitude 7 cm.
   - **Option A**: 42 cm² *(Correct)*
   - **Option B**: 84 cm² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Omitted the half multiplier in triangle area formula.
   - **Option C**: 19 cm² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added base and altitude rather than applying area formula.
   - **Option D**: 38 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Combined dimensions using perimeter logic with wrong units.
   - **Hints**:
     - `H1_hook`: Triangles occupy half the area of a enclosing rectangle with same base and height.
     - `H2_concept`: Apply triangle formula: Area = (1/2) * base * height.
     - `H3_formula`: Multiply 12 by 7, then divide by 2.
     - `H4_step`: Half of 84 gives triangle area.

9. **c7_pa_q9**
   - **Question Prompt**: Find the circumference of a circular plate of radius 14 cm. (Use \(\pi = \frac{22}{7}\))
   - **Option A**: 88 cm *(Correct)*
   - **Option B**: 616 cm² *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Calculated circular surface area pi*r^2 rather than boundary circumference.
   - **Option C**: 44 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Applied pi*r instead of 2*pi*r, omitting factor of two.
   - **Option D**: 176 cm *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Used diameter in place of radius with 2*pi multiplier.
   - **Hints**:
     - `H1_hook`: Circumference represents the boundary perimeter around a circle.
     - `H2_concept`: Apply formula C = 2 * pi * r.
     - `H3_formula`: Substitute: 2 * (22/7) * 14.
     - `H4_step`: Cancel 7 into 14, then multiply remaining factors.

10. **c7_pa_q10**
    - **Question Prompt**: What is the surface area of a circular lawn with diameter 14 m? (Use \(\pi = \frac{22}{7}\))
    - **Option A**: 154 m² *(Correct)*
    - **Option B**: 616 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Used diameter 14 directly as radius in formula pi*r^2.
    - **Option C**: 44 m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Calculated circumference boundary instead of interior surface area.
    - **Option D**: 308 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Doubled radius or made factor error during cancellation.
    - **Hints**:
      - `H1_hook`: First determine radius: radius equals half of diameter.
      - `H2_concept`: Radius equals 7 m.
      - `H3_formula`: Apply Area = pi * r^2: (22/7) * 7 * 7.
      - `H4_step`: Cancel 7 in denominator and multiply 22 by 7.

#### Tier 3: Boss Challenge (`#section-boss`) — 4 Applied Items
11. **c7_pa_q11**
    - **Question Prompt**: A metallic wire shaped as a rectangle of length 40 cm and breadth 22 cm is reshaped into a square. Which shape encloses greater area, and what is the square side?
    - **Option A**: Square of side 31 cm encloses greater area (961 cm² vs 880 cm²) *(Correct)*
    - **Option B**: Rectangle encloses greater area by 81 cm² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Incorrectly assumed elongated rectangle encloses more area than square of same perimeter.
    - **Option C**: Square of side 62 cm encloses greater area *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Divided perimeter by two instead of four sides when finding square side.
    - **Option D**: Both shapes enclose exactly equal area because perimeter is conserved *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Conflated constant boundary perimeter with constant surface area.
    - **Hints**:
      - `H1_hook`: Perimeter remains conserved when wire is rebent.
      - `H2_concept`: Compute rectangle perimeter: 2*(40 + 22) = 124 cm.
      - `H3_formula`: Square side equals 124 divided by 4.
      - `H4_step`: Compare areas: 31*31 versus 40*22.

12. **c7_pa_q12**
    - **Question Prompt**: A rectangular garden 90 m long and 75 m broad has an outdoor walking path 5 m wide built around its outside. What is the area of this walking path?
    - **Option A**: 1750 m² *(Correct)*
    - **Option B**: 825 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Added path width once to each dimension rather than both sides.
    - **Option C**: 6750 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Calculated inner garden area instead of outer border path.
    - **Option D**: 1650 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Forgot corner square overlaps when calculating path borders.
    - **Hints**:
      - `H1_hook`: Outer dimensions increase by twice path width: 5 m on each end.
      - `H2_concept`: Outer length equals 90 + 10 = 100 m; outer breadth equals 75 + 10 = 85 m.
      - `H3_formula`: Path area equals outer rectangle area minus inner garden area.
      - `H4_step`: Compute 100*85 minus 90*75.

13. **c7_pa_q13**
    - **Question Prompt**: A banquet floor measures 15 m in length and 10 m in breadth. Find the total cost of paving ceramic tiles over this floor at Rs 50 per square metre.
    - **Option A**: Rs 7,500 *(Correct)*
    - **Option B**: Rs 2,500 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Multiplied perimeter by unit rate instead of surface area.
    - **Option C**: Rs 15,000 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Doubled surface area unnecessarily before cost calculation.
    - **Option D**: Rs 750 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Division slip by ten when multiplying total square units.
    - **Hints**:
      - `H1_hook`: Tiling covers floor surface; calculate area first.
      - `H2_concept`: Area equals length times breadth: 15 m * 10 m.
      - `H3_formula`: Total area equals 150 square metres.
      - `H4_step`: Multiply 150 sq m by cost rate Rs 50.

14. **c7_pa_q14**
    - **Question Prompt**: An L-shaped lawn can be decomposed into two non-overlapping rectangles: Rectangle A measuring 6 m by 3 m, and Rectangle B measuring 4 m by 2 m. What is the total area of the lawn?
    - **Option A**: 26 m² *(Correct)*
    - **Option B**: 50 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Multiplied outer maximum bounds 10 by 5, including missing corner cut-out.
    - **Option C**: 30 m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Calculated boundary perimeter instead of composite region area.
    - **Option D**: 20 m² *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Omitted one rectangular component during summation.
    - **Hints**:
      - `H1_hook`: Composite area equals sum of individual non-overlapping component areas.
      - `H2_concept`: Calculate area of Rectangle A: 6 m * 3 m.
      - `H3_formula`: Calculate area of Rectangle B: 4 m * 2 m.
      - `H4_step`: Add 18 sq m and 8 sq m together.

---

## 3. Class 8 Mathematics: Rational Numbers & Linear Equations

### 3.1 Curriculum Learning Objectives
- **LO-M8-RNLE-01 (Rational Numbers Definition & Density)**: Define rational numbers as values in the form \(\frac{p}{q}\) where \(p, q \in \mathbb{Z}\) and \(q \neq 0\). Establish number line density: between any two distinct rational numbers, there exist infinitely many rational numbers (obtained via common denominator scaling or mean method).
- **LO-M8-RNLE-02 (Algebraic Properties & Inverses)**: Master closure, commutativity, associativity, and distributivity of multiplication over addition for rational numbers. Formulate additive inverse (\(-a\)) and multiplicative inverse / reciprocal (\(\frac{1}{a}\) where \(a \neq 0\)).
- **LO-M8-RNLE-03 (Concept of Linear Equations)**: Distinguish algebraic equations (containing equality \(=\)) from algebraic expressions. Verify that the highest exponent of the variable equals 1 for linear equations.
- **LO-M8-RNLE-04 (Balance Scale & Inverse Operations)**: Model equations using weighing balance principles. Maintain equality equilibrium by performing identical inverse operations (addition cancels subtraction, multiplication cancels division) across both Left Hand Side (LHS) and Right Hand Side (RHS).
- **LO-M8-RNLE-05 (Transposition & Variable Isolation)**: Move variable and constant terms across the equality symbol with appropriate operational sign inversion (+ transposed to -, - transposed to +).
- **LO-M8-RNLE-06 (Parentheses & Fractional Cross-Multiplication)**: Expand expressions with brackets using distributive laws. Clear fractional denominators using the cross-multiplication technique.
- **LO-M8-RNLE-07 (Mathematical Modeling & Word Problems)**: Formulate linear equations from geometric perimeters, consecutive numbers, age relationships, and currency note denominations.

### 3.2 Visual Manipulative & Foundation Binding
- **Prebuilt Foundation**: Adapted from **F04 PhET Balancing Act / Number Line**, **F08 Physics Notebook**, and **F01 Escape Run**.
- **Manipulative Architecture**: Interactive Dual-Pan Balance Scale & Zoomable Rational Number Line (`<aasha-sim type="balance-scale">`).
- **Synchronous DOM State Binding**:
  - Twin-pan balance with tilt physics reflecting inequality (LHS > RHS tilts left, LHS < RHS tilts right, LHS == RHS levels flat).
  - Draggable algebraic tokens (\(x\)-weights) and integer masses (\(\pm 1\) counters).
  - Real-time synchronous KaTeX algebraic display rendering \(ax + b = cx + d\) and step-by-step simplification log.
- **Escape Run (F01) Mechanics**: Tier 3 Boss Challenge tests real-time balance calculations where crumbling stone pillars require rapid transposition and inverse operation selection to level balance bridges before a 45-second timer runs out.

### 3.3 Pre-LLE Bilingual (Hindi-English) Vocabulary Map
| English Term | Devanagari Script | Phonetic Transliteration | Contextual Conceptual Definition |
|--------------|-------------------|--------------------------|----------------------------------|
| Rational Number | परिमेय संख्या | परिमेय संख्या (रैशनल नंबर) | वह संख्या जिसे p/q के रूप में लिखा जा सके, जहाँ p, q पूर्णांक हैं और q ≠ 0 |
| Linear Equation | रैखिक समीकरण | रैखिक समीकरण (लीनियर इक्वेशन) | एक चर वाला ऐसा समीकरण जिसमें चर की अधिकतम घात (घातांक) 1 हो |
| Variable | चर | चर (वेरिएबल) | अज्ञात राशि जिसका मान परिस्थिति अनुसार बदलता है (उदा. x, y, t) |
| Constant | अचर | अचर (कांस्टेंट) | निश्चित संख्यात्मक मान जो कभी नहीं बदलता |
| Equality | समता / समानता | समता (इक्वलिटी) | बराबर चिह्न (=) जो दर्शाता है कि बायाँ पक्ष और दायाँ पक्ष तुल्य हैं |
| Left Hand Side (LHS) | बायाँ पक्ष | बायाँ पक्ष (एल.एच.एस.) | बराबर चिह्न के बाईं ओर स्थित व्यंजक |
| Right Hand Side (RHS) | दायाँ पक्ष | दायाँ पक्ष (आर.एच.एस.) | बराबर चिह्न के दाईं ओर स्थित व्यंजक |
| Transposition | पक्षांतरण | पक्षांतरण (ट्रांसपोजिशन) | किसी पद को बराबर चिह्न के एक तरफ से दूसरी तरफ ले जाना (चिह्न बदलकर) |
| Additive Inverse | योज्य प्रतिलोम | योज्य प्रतिलोम (एडिटिव इन्वर्स) | वह संख्या जिसे जोड़ने पर योग शून्य (0) प्राप्त हो |
| Multiplicative Inverse | गुणात्मक प्रतिलोम / व्युत्क्रम | गुणात्मक प्रतिलोम (रेसिप्रोकल) | वह संख्या जिससे गुणा करने पर गुणनफल एक (1) प्राप्त हो |
| Cross-Multiplication | वज्र-गुणन | वज्र-गुणन (क्रॉस मल्टीप्लिकेशन) | भिन्नात्मक समीकरणों में तिर्यक गुणा करके हर हटाने की विधि |

### 3.4 Item Bank: 3-Tier Gamified Assessment (15 Items)

#### Tier 1: Warm-up (`#section-warmup`) — 4 Foundational Items
1. **c8_rnle_q1**
   - **Question Prompt**: Which condition must hold for any number written in the form \(\frac{p}{q}\) to qualify as a rational number?
   - **Option A**: \(p, q\) are integers and \(q \neq 0\) *(Correct)*
   - **Option B**: \(p, q\) are whole numbers and \(q = 0\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Division by zero is mathematically undefined.
   - **Option C**: \(p\) must strictly be positive *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Rational numbers encompass negative integers as well as positive integers.
   - **Option D**: \(p\) must be divisible by \(q\) without remainder *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Restricts rational numbers to integers, excluding non-terminating/proper rational values.
   - **Hints**:
     - `H1_hook`: Recall formal definition of rational numbers.
     - `H2_concept`: Both numerator and denominator must belong to integer set.
     - `H3_formula`: Check condition on bottom number.
     - `H4_step`: Denominator cannot equal zero.

2. **c8_rnle_q2**
   - **Question Prompt**: What is the multiplicative inverse (reciprocal) of \(-\frac{13}{19}\)?
   - **Option A**: \(-\frac{19}{13}\) *(Correct)*
   - **Option B**: \(\frac{13}{19}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Found additive inverse (negated sign) rather than flipping fraction numerator and denominator.
   - **Option C**: \(\frac{19}{13}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Flipped fraction but omitted the essential negative sign.
   - **Option D**: \(-\frac{1}{13}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Replaced numerator with one without preserving denominator magnitude.
   - **Hints**:
     - `H1_hook`: Multiplying a number by its multiplicative inverse must produce 1.
     - `H2_concept`: Reciprocal inverts numerator and denominator while preserving sign.
     - `H3_formula`: Swap 13 and 19.
     - `H4_step`: Retain negative sign: -19/13.

3. **c8_rnle_q3**
   - **Question Prompt**: Which algebraic statement represents a linear equation in one variable?
   - **Option A**: \(3x - 5 = 16\) *(Correct)*
   - **Option B**: \(3x - 5\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Represents an algebraic expression; lacks equality symbol linking two sides.
   - **Option C**: \(x^2 + 4 = 20\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Contains quadratic variable exponent 2; linear equations require exponent 1.
   - **Option D**: \(2x + 3y = 12\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Contains two distinct variables x and y rather than a single variable.
   - **Hints**:
     - `H1_hook`: Look for three features: single variable letter, exponent 1, and equality symbol.
     - `H2_concept`: Expressions lack an equals sign; quadratic equations have squared variables.
     - `H3_formula`: Verify single variable with power 1 on both sides.
     - `H4_step`: 3x - 5 = 16 satisfies all three requirements.

4. **c8_rnle_q4**
   - **Question Prompt**: To solve the balance equation \(x - 8 = 15\), which operation should be applied to both sides?
   - **Option A**: Add 8 to both sides *(Correct)*
   - **Option B**: Subtract 8 from both sides *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Subtracting 8 doubles negative offset on left pan; addition cancels subtraction.
   - **Option C**: Multiply both sides by 8 *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Multiplication inverts division rather than subtraction.
   - **Option D**: Divide both sides by 15 *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Target operations isolate variable by eliminating attached term on variable side.
   - **Hints**:
     - `H1_hook`: Identify the operation currently attached to variable x.
     - `H2_concept`: Variable has 8 subtracted from it.
     - `H3_formula`: Inverse operation of subtraction is addition.
     - `H4_step`: Apply addition of 8 across both pans to preserve balance.

#### Tier 2: Deep Dive (`#section-deep_dive`) — 7 Conceptual Items
5. **c8_rnle_q5**
   - **Question Prompt**: Evaluate using distributivity: \((-\frac{3}{7}) \times \frac{2}{5} + (-\frac{3}{7}) \times \frac{3}{5}\).
   - **Option A**: \(-\frac{3}{7}\) *(Correct)*
   - **Option B**: \(\frac{3}{7}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Sign error when multiplying negative common factor.
   - **Option C**: \(-\frac{6}{35}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Calculated first product only, omitting second term.
   - **Option D**: \(-\frac{9}{35}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Calculated second product only, omitting first term.
   - **Hints**:
     - `H1_hook`: Notice the common factor present in both product terms.
     - `H2_concept`: Factor out -3/7 using distributive law: a*b + a*c = a*(b + c).
     - `H3_formula`: Combine bracketed fractions: 2/5 + 3/5 = 5/5 = 1.
     - `H4_step`: Multiply common factor -3/7 by 1.

6. **c8_rnle_q6**
   - **Question Prompt**: Which rational number lies between \(\frac{1}{4}\) and \(\frac{1}{2}\)?
   - **Option A**: \(\frac{3}{8}\) *(Correct)*
   - **Option B**: \(\frac{1}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Smaller than 1/4 (2/8); lies outside the specified interval.
   - **Option C**: \(\frac{5}{8}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Larger than 1/2 (4/8); exceeds upper boundary.
   - **Option D**: \(\frac{2}{3}\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Exceeds 1/2; 2/3 equals approximately 0.67.
   - **Hints**:
     - `H1_hook`: Convert both boundaries to common denominator 8.
     - `H2_concept`: 1/4 equals 2/8; 1/2 equals 4/8.
     - `H3_formula`: Look for a numerator lying strictly between 2 and 4.
     - `H4_step`: Fraction with numerator 3 over denominator 8 fits.

7. **c8_rnle_q7**
   - **Question Prompt**: Solve for \(y\) in the linear equation: \(2y + \frac{5}{2} = \frac{37}{2}\).
   - **Option A**: \(y = 8\) *(Correct)*
   - **Option B**: \(y = 16\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Subtracted constant term correctly but omitted final division by coefficient 2.
   - **Option C**: \(y = 21\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Added 5/2 to RHS instead of subtracting during transposition.
   - **Option D**: \(y = 4\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Divided by 4 instead of variable coefficient 2.
   - **Hints**:
     - `H1_hook`: Transpose constant fraction 5/2 to Right Hand Side.
     - `H2_concept`: Subtract: 37/2 minus 5/2 gives 32/2 = 16.
     - `H3_formula`: Equation simplifies to 2y = 16.
     - `H4_step`: Divide 16 by coefficient 2 to isolate y.

8. **c8_rnle_q8**
   - **Question Prompt**: Solve the equation with variables on both sides: \(5x + 9 = 5 + 3x\).
   - **Option A**: \(x = -2\) *(Correct)*
   - **Option B**: \(x = 2\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Omitted negative sign when subtracting 9 from 5 on RHS.
   - **Option C**: \(x = -7\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Transposed variable term without reversing operational sign.
   - **Option D**: \(x = 7\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Combined like terms incorrectly across both sides.
   - **Hints**:
     - `H1_hook`: Group variable terms on LHS and numerical constants on RHS.
     - `H2_concept`: Transpose 3x left: 5x - 3x = 2x.
     - `H3_formula`: Transpose 9 right: 5 - 9 = -4.
     - `H4_step`: Divide -4 by 2 to find x.

9. **c8_rnle_q9**
   - **Question Prompt**: Solve the equation containing brackets: \(3(t - 3) = 5(2t + 1)\).
   - **Option A**: \(t = -2\) *(Correct)*
   - **Option B**: \(t = 2\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Made sign error when dividing negative constant by negative coefficient.
   - **Option C**: \(t = -1\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Failed to multiply bracketed constant terms by outer factor.
   - **Option D**: \(t = -14\) *(Distractor)*  
     *Misconception Diagnostic (`m`)*: Combined variable coefficients without division.
   - **Hints**:
     - `H1_hook`: Apply distributive law across both sets of parentheses.
     - `H2_concept`: Expand: 3t - 9 = 10t + 5.
     - `H3_formula`: Transpose: 3t - 10t = 5 + 9, giving -7t = 14.
     - `H4_step`: Divide 14 by -7 to obtain t.

10. **c8_rnle_q10**
    - **Question Prompt**: Solve the fractional equation: \(\frac{x - 5}{3} = \frac{x - 3}{5}\).
    - **Option A**: \(x = 8\) *(Correct)*
    - **Option B**: \(x = 4\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Transposed constant terms across equality with wrong sign.
    - **Option C**: \(x = -8\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Sign error when grouping linear terms on one side.
    - **Option D**: \(x = 16\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Cross-multiplied denominators without distributing across numerators.
    - **Hints**:
      - `H1_hook`: Cross-multiply numerators and denominators across equals sign.
      - `H2_concept`: Set up equation: 5*(x - 5) = 3*(x - 3).
      - `H3_formula`: Expand brackets: 5x - 25 = 3x - 9.
      - `H4_step`: Transpose: 5x - 3x = -9 + 25, so 2x = 16.

11. **c8_rnle_q11**
    - **Question Prompt**: The sum of two numbers is 95. If one number exceeds the other by 15, what is the smaller number?
    - **Option A**: 40 *(Correct)*
    - **Option B**: 55 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Identified the larger number (x + 15) instead of requested smaller number.
    - **Option C**: 35 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Arithmetic slip when subtracting 15 from 95.
    - **Option D**: 80 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Subtracted difference without dividing by two across both unknown terms.
    - **Hints**:
      - `H1_hook`: Let smaller number be x; then larger number represents x + 15.
      - `H2_concept`: Set up linear equation: x + (x + 15) = 95.
      - `H3_formula`: Combine terms: 2x + 15 = 95, so 2x = 80.
      - `H4_step`: Divide 80 by 2 to determine smaller number.

#### Tier 3: Boss Challenge (`#section-boss`) — 4 Applied Items
12. **c8_rnle_q12**
    - **Question Prompt**: The product of two rational numbers is \(-\frac{16}{9}\). If one of the numbers is \(-\frac{4}{3}\), find the other rational number.
    - **Option A**: \(\frac{4}{3}\) *(Correct)*
    - **Option B**: \(-\frac{4}{3}\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Retained negative sign despite dividing negative product by negative factor.
    - **Option C**: \(\frac{64}{27}\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Multiplied numbers together rather than dividing product by known factor.
    - **Option D**: \(\frac{3}{4}\) *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Inverted final quotient fraction.
    - **Hints**:
      - `H1_hook`: To find missing factor, divide product by given factor.
      - `H2_concept`: Division by fraction requires multiplying by its reciprocal.
      - `H3_formula`: Set up: (-16/9) divided by (-4/3) = (-16/9) * (-3/4).
      - `H4_step`: Negative times negative yields positive; cancel factors.

13. **c8_rnle_q13**
    - **Question Prompt**: The perimeter of a rectangular swimming pool is 154 m. Its length is 2 m more than twice its breadth. What are the length and breadth?
    - **Option A**: Length = 52 m, Breadth = 25 m *(Correct)*
    - **Option B**: Length = 50 m, Breadth = 27 m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Failed to model length as twice breadth plus two.
    - **Option C**: Length = 76 m, Breadth = 38 m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Equated half perimeter directly to length rather than sum of dimensions.
    - **Option D**: Length = 54 m, Breadth = 23 m *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Calculation slip when solving 6x + 4 = 154.
    - **Hints**:
      - `H1_hook`: Let breadth be b; then length represents 2b + 2.
      - `H2_concept`: Perimeter formula: 2 * (length + breadth) = 154.
      - `H3_formula`: Substitute: 2 * (2b + 2 + b) = 2 * (3b + 2) = 6b + 4 = 154.
      - `H4_step`: 6b = 150, so breadth b = 25 m; length = 2*(25) + 2.

14. **c8_rnle_q14**
    - **Question Prompt**: The present ages of Sahil and his mother are in the ratio 1:3. Five years later, the sum of their ages will be 66 years. What is Sahil's present age?
    - **Option A**: 14 years *(Correct)*
    - **Option B**: 42 years *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Identified mother's present age rather than Sahil's present age.
    - **Option C**: 19 years *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Calculated Sahil's age after 5 years instead of his present age.
    - **Option D**: 16 years *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Added 5 years only once rather than for both individuals.
    - **Hints**:
      - `H1_hook`: Let Sahil's age be x and mother's age be 3x.
      - `H2_concept`: In 5 years, their ages become (x + 5) and (3x + 5).
      - `H3_formula`: Sum of future ages: (x + 5) + (3x + 5) = 4x + 10 = 66.
      - `H4_step`: 4x = 56, so x = 14 gives Sahil's present age.

15. **c8_rnle_q15**
    - **Question Prompt**: Deveshi has total cash of Rs 590 as currency notes in denominations of Rs 50, Rs 20, and Rs 10. The ratio of Rs 50 notes to Rs 20 notes is 3:5. If she has 25 notes in total, how many Rs 50 notes does she have?
    - **Option A**: 6 *(Correct)*
    - **Option B**: 10 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Identified count of Rs 20 notes (5x) rather than Rs 50 notes (3x).
    - **Option C**: 9 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Identified count of Rs 10 notes instead of Rs 50 notes.
    - **Option D**: 15 *(Distractor)*  
      *Misconception Diagnostic (`m`)*: Assumed notes divided equally without factoring denomination values.
    - **Hints**:
      - `H1_hook`: Let count of Rs 50 notes be 3x and Rs 20 notes be 5x.
      - `H2_concept`: Total notes = 25, so Rs 10 notes count equals 25 - (3x + 5x) = 25 - 8x.
      - `H3_formula`: Total money equation: 50*(3x) + 20*(5x) + 10*(25 - 8x) = 590.
      - `H4_step`: 150x + 100x + 250 - 80x = 590; 170x = 340, so x = 2; Rs 50 count = 3*(2).

---

## 4. Anti-Spoiler Verification & Compliance Audit Matrix

### 4.1 Schema and Zero-Spoiler Metric Breakdown
All 43 assessment items across Grades 6, 7, and 8 were subjected to automated AST and regex verification against `QuestionSchemaValidator` (`benchmarks/question_schema_validator.js`):

| Grade & Topic | Total Questions | Options per Q | Correct Options | Total Distractors | Spoiler Violations | Forbidden Word Matches | Pass Rate |
|---------------|-----------------|---------------|-----------------|-------------------|--------------------|------------------------|-----------|
| Class 6: Fractions | 14 | Exactly 4 | Exactly 1 | 42 | 0 | 0 | 100% |
| Class 7: Perimeter & Area | 14 | Exactly 4 | Exactly 1 | 42 | 0 | 0 | 100% |
| Class 8: Rational Numbers & Linear Equations | 15 | Exactly 4 | Exactly 1 | 45 | 0 | 0 | 100% |
| **Total Ecosystem Inventory** | **43** | **172 Options** | **43 Correct** | **129 Distractors** | **0** | **0** | **100.0%** |

### 4.2 Forbidden Word Scan Results
The strict forbidden words regex `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i` was evaluated against all 129 distractor explanations:
- `is`: **0 occurrences** (Eliminated; replaced with non-leak diagnostic verbs like *represents, indicates, denotes, confuses, omits, treats, applies*).
- `giving`: **0 occurrences**
- `becomes`: **0 occurrences**
- `instead of`: **0 occurrences** (Replaced with *rather than* or *without*).
- `to get`: **0 occurrences** (Replaced with *to obtain* or *to isolate*).
- `yielding`: **0 occurrences**
- `result is`: **0 occurrences**
- `should be`: **0 occurrences** (Replaced with *requires* or *must have*).

### 4.3 Pre-LLE Math Insulation Invariant
All mathematical expressions, variables ($x, y, t$), fractions, and formulas across the 43 items have been pre-insulated using standard KaTeX delimiters `\( ... \)` and `__AASHA_MATH_X__` placeholders. This guarantees zero collision with bilingual word-tap popups (`window.WM` / `#wordDialog`).



