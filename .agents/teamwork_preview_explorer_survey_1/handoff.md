# Forensic Textbook & Exercise Audit Report: Class 8 Mathematics — Rational Numbers (AD Edition)

**Auditor Agent**: `teamwork_preview_explorer_survey_1`  
**Date & Timestamp**: 2026-09-14T03:16:00Z  
**Source Artifact**: `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/content/pdfs/AD class 8th math rational number.pdf` (Extracted high-res page scans in `content/extracted_pages/ad_rational_9p/page_01.png` to `page_09.png`)  
**Contract Artifact**: `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/rational_numbers_ad_contract.yaml`  
**HTML Implementation Artifact**: `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`  
**Intermediate Pipeline JSONs**: `chapters/ad_all_questions.json`, `chapters/ad_full_nodes_46.json`

---

## 1. Observation

### 1.1 Direct Inspection of Source Textbook PDF (`AD class 8th math rational number.pdf`)
The source textbook PDF consists of 9 pages of scanned images (`page_01.png` to `page_09.png` in `content/extracted_pages/ad_rational_9p/`). The page-by-page curricular breakdown is observed as follows:

- **Page 1 & 2 (`page_01.png`, `page_02.png`) — Chapter Inception & Real-World Embark On**:
  - Title: *"1 CHAPTER Rational Numbers"*
  - Embark On Scenario: *"Seema wants to buy three pens, each costing ₹5. Her brother Sachin wants to buy 2 similar pens. They decided to go to a wholesale shop to make their purchase. At the shop, the shopkeeper tells them that a packet of 5 pens costs ₹22. Now, Seema and Sachin need to figure out the cost of each pen to ensure they are getting a good deal. Seema knows that each pen costs ₹5 when bought individually. However, the shopkeeper offers a packet of 5 pens for ₹22. To find out the cost of each pen when bought in a packet, we divide the total cost of the packet by the number of pens in it. Mathematically, this is represented as: cost of each pen = ₹ 22/5. Dividing ₹22 by 5 gives us: 22/5 = ₹4.40. Therefore, each pen in the packet costs ₹4.40. The division resulted in a number that isn't a whole number, but a fraction or decimal, specifically ₹4.40. Here, ₹4.40 is a rational number because it can be expressed as a fraction where both the numerator (22) and the denominator (5) are integers."*

- **Page 3 (`page_03.png`) — Exploring Essential Ideas & Definitions**:
  - Definition: *"A rational number is a number that can be expressed as a quotient or fraction p/q of two integers, where p (the numerator) is an integer and q (the denominator) is a non-zero integer. Rational numbers are numbers that can be written in the form p/q where p and q are integers and q ≠ 0."*
  - Core Axioms:
    1. *"Any integer is a rational number, as it can be expressed as a/1, where a is an integer."*
    2. *"Rational numbers include both positive and negative numbers, as well as zero."*
    3. *"Rational numbers can be represented on the number line."*
    4. *"Every fraction is a rational number."*
  - Operational Rules & Worked Examples:
    - Addition (same denominator): $\frac{a}{b} + \frac{c}{b} = \frac{a+c}{b}$. Example: $\frac{5}{3} + \frac{4}{3} = \frac{5+4}{3} = \frac{9}{3} = 3$.
    - Addition (different denominators): $\frac{a}{b} + \frac{c}{d} = \frac{ad+bc}{bd}$. Example: $\frac{-9}{7} + \frac{5}{8} = \frac{-9 \times 8 + 7 \times 5}{7 \times 8} = \frac{-72 + 35}{56} = \frac{-37}{56}$.
    - Additive Inverse: If $\frac{a}{b} + \frac{c}{d} = 0$, then $\frac{a}{b}$ is the additive inverse of $\frac{c}{d}$. Example: $\frac{a}{b} + \left(\frac{-a}{b}\right) = 0$; additive inverse of $\frac{3}{7}$ is $\frac{-3}{7}$ and vice versa.
    - Subtraction: Subtracting $\frac{c}{d}$ from $\frac{a}{b}$ means adding additive inverse: $\frac{a}{b} - \frac{c}{d} = \frac{a}{b} + \left(\frac{-c}{d}\right)$. Example: $\frac{-4}{9}$ from $\frac{-5}{7} \implies \frac{-5}{7} - \left(\frac{-4}{9}\right) = \frac{-5}{7} + \frac{4}{9} = \frac{-45 + 28}{63} = \frac{-17}{63}$.
    - Multiplication: $\frac{a}{b} \times \frac{c}{d} = \frac{ac}{bd}$. Product of numerators divided by product of denominators.
    - Reciprocal: If $\frac{a}{b} \times \frac{c}{d} = 1$, then $\frac{a}{b}$ is the reciprocal of $\frac{c}{d}$.

- **Page 4 (`page_04.png`) — Division Theory & Exercise 1A**:
  - Division Theory: $\frac{a}{b} \div \frac{c}{d} = \frac{a}{b} \times \text{reciprocal of } \frac{c}{d} = \frac{a}{b} \times \frac{d}{c}$ ($c/d \ne 0$). Example: $\frac{9}{11} \div \frac{3}{5} = \frac{9}{11} \times \frac{5}{3} = \frac{15}{11}$.
  - **Exercise 1A (Complete text)**:
    - **Q1. Add the following rational numbers**:
      (a) $\frac{5}{2}$ and $\frac{-11}{2}$
      (b) $\frac{7}{5}$ and $\frac{13}{5}$
      (c) $\frac{-7}{8}$ and $\frac{12}{-8}$
      (d) $\frac{-11}{5}$ and $\frac{-9}{5}$
      (e) $\frac{4}{-7}$ and $\frac{-5}{8}$
      (f) $\frac{-13}{7}$ and $\frac{12}{-5}$
      (g) $\frac{-15}{9}$ and $\frac{-17}{11}$
      (h) $\frac{-9}{-33}$ and $\frac{5}{11}$
    - **Q2. Subtract the following rational numbers**:
      (a) $\frac{-18}{5} - \left(\frac{-8}{5}\right)$
      (b) $\frac{-19}{15} - \left(\frac{-6}{30}\right)$
      (c) $\frac{-6}{11} - \left(\frac{-7}{11}\right)$
      (d) $\frac{-1}{4} - \left(\frac{-2}{8}\right)$
      (e) $\frac{-59}{5} - \frac{19}{5}$
      (f) $\frac{-4}{7} - \left(\frac{-8}{9}\right)$
      (g) $\frac{7}{24} - \left(\frac{-13}{-26}\right)$
      (h) $\frac{7}{25} - \left(\frac{-6}{15}\right)$
    - **Q3. Multiply the following**:
      (a) $\frac{4}{7}$ by $\frac{-2}{5}$
      (b) $\frac{-3}{8}$ by $\frac{-12}{15}$
      (c) $\frac{11}{-13}$ by $\frac{-39}{22}$
      (d) $\frac{-5}{9}$ by $\frac{81}{35}$
      (e) $\frac{-9}{25}$ by $\frac{-35}{27}$
      (f) $\frac{-18}{25}$ by $\frac{40}{-36}$
    - **Q4. Divide the following**:
      (a) $\frac{16}{7}$ by $\frac{-8}{14}$
      (b) $\frac{-7}{8}$ by $-21$
      (c) $\frac{3}{8}$ by $\frac{-4}{5}$
      (d) $\frac{-1}{15}$ by $\frac{8}{3}$
      (e) $\frac{-3}{26}$ by $\frac{9}{78}$
      (f) $\frac{-22}{26}$ by $\frac{-33}{39}$
    - **Q5. Simplify**:
      (a) $\left[\frac{3}{2} \times \frac{-7}{4} \times \frac{8}{9}\right] - \left[\frac{-15}{2} \times \frac{3}{7} \times \frac{8}{14}\right]$
      (b) $\left[\frac{7}{3} \times \frac{9}{11}\right] + \left[\frac{4}{3} \times \frac{7}{22}\right] - \left[\frac{3}{-11} \times \frac{-7}{9}\right]$

- **Page 5 (`page_05.png`) — Properties of Addition of Rational Numbers**:
  - Closure Property: $\frac{3}{4} + \frac{7}{3} = \frac{37}{12}$ (rational).
  - Commutative Property: $\frac{a}{b} + \frac{c}{d} = \frac{c}{d} + \frac{a}{b}$. Verified with $\frac{3}{8} + \frac{5}{7} = \frac{61}{56}$.
  - Associative Property: $\left(\frac{a}{b} + \frac{c}{d}\right) + \frac{e}{f} = \frac{a}{b} + \left(\frac{c}{d} + \frac{e}{f}\right)$. Verified with $\frac{-2}{5} + \left[\frac{3}{4} + \left(\frac{-7}{8}\right)\right] = \frac{-21}{40}$.
  - Additive Property of Zero ($0$): $0 + \frac{a}{b} = \frac{a}{b} + 0 = \frac{a}{b}$. $0$ is the additive identity. Example: $0 + \frac{2}{5} = \frac{2}{5}$.

- **Page 6 (`page_06.png`) — Properties of Subtraction & Exercise 1B**:
  - Subtraction Closure: $\frac{c}{d} - \frac{a}{b}$ is rational. Example: $\frac{-3}{5} - \left(\frac{-7}{6}\right) = \frac{17}{30}$.
  - Subtraction Property of Zero: $\frac{a}{b} - 0 = \frac{a}{b}$.
  - **Exercise 1B (Complete text)**:
    - **Q1. Fill in the blanks using commutative property for addition of rational numbers**:
      (a) $\frac{-3}{7} + \frac{4}{9} = \_\_\_\_\_\_\_\_$ [Answer: $\frac{4}{9} + \left(\frac{-3}{7}\right)$]
      (b) $\frac{2}{3} + \left(\frac{-5}{6}\right) = \_\_\_\_\_\_\_\_$ [Answer: $\left(\frac{-5}{6}\right) + \frac{2}{3}$]
      (c) $\left[\frac{-11}{29}\right] + \left[\frac{-5}{31}\right] = \_\_\_\_\_\_\_\_$ [Answer: $\left[\frac{-5}{31}\right] + \left[\frac{-11}{29}\right]$]
      (d) $\frac{-7}{13} + \frac{11}{23} = \_\_\_\_\_\_\_\_$ [Answer: $\frac{11}{23} + \left(\frac{-7}{13}\right)$]
    - **Q2. Fill in the blanks using associative property for addition of rational numbers**:
      (a) $\left[\frac{1}{11} + \frac{2}{13}\right] + \frac{7}{6} = \_\_\_\_\_\_\_\_$ [Answer: $\frac{1}{11} + \left[\frac{2}{13} + \frac{7}{6}\right]$]
      (b) $\frac{17}{21} + \left[\frac{-5}{13} + \frac{9}{16}\right] = \_\_\_\_\_\_\_\_$ [Answer: $\left[\frac{17}{21} + \left(\frac{-5}{13}\right)\right] + \frac{9}{16}$]
      (c) $\left[\frac{-31}{41}\right] + \left[\frac{9}{14} + \frac{8}{15}\right] = \_\_\_\_\_\_\_\_$ [Answer: $\left[\frac{-31}{41} + \frac{9}{14}\right] + \frac{8}{15}$]
      (d) $\left[\frac{2}{7} + \frac{3}{8}\right] + \frac{-9}{14} = \_\_\_\_\_\_\_\_$ [Answer: $\frac{2}{7} + \left[\frac{3}{8} + \left(\frac{-9}{14}\right)\right]$]
    - **Q3. State the property used in each of the following**:
      (a) $\frac{-2}{5} + \frac{3}{7} = \frac{3}{7} + \frac{-2}{5}$ [Answer: Commutative Property of Addition]
      (b) $\frac{2}{5} + \left[\frac{9}{7} + \left(\frac{-3}{8}\right)\right] = \left[\frac{2}{5} + \frac{9}{7}\right] + \left(\frac{-3}{8}\right)$ [Answer: Associative Property of Addition]
      (c) $\frac{-3}{7} + \left[\frac{-5}{8} + \frac{9}{4}\right] = \left[\frac{-3}{7} + \left(\frac{-5}{8}\right)\right] + \frac{9}{4}$ [Answer: Associative Property of Addition]
      (d) $\frac{3}{10} + \left[\frac{-11}{15} + \frac{9}{-7}\right] = \left[\frac{3}{10} + \left(\frac{-11}{15}\right)\right] + \frac{9}{-7}$ [Answer: Associative Property of Addition]
    - **Q4. Verification**:
      If $a = \frac{8}{9}$ and $b = \frac{-3}{8}$, then verify that $a + b = b + c$ [Note: Textbook misprint for $a + b = b + a$. Verified LHS = RHS = $\frac{37}{72}$].

- **Page 7 & 8 (`page_07.png`, `page_08.png`) — Properties of Multiplication & Distributivity**:
  - Multiplication Closure: $\frac{3}{4} \times \frac{2}{7} = \frac{3}{14}$ (rational).
  - Multiplication Commutativity: $\frac{a}{b} \times \frac{c}{d} = \frac{c}{d} \times \frac{a}{b}$. Example: $\frac{3}{4} \times \frac{8}{26} = \frac{3}{13}$.
  - Multiplication Associativity: $\left(\frac{a}{b} \times \frac{c}{d}\right) \times \frac{e}{f} = \frac{a}{b} \times \left(\frac{c}{d} \times \frac{e}{f}\right)$. Example: $\left[\frac{-2}{5} \times \frac{3}{7}\right] \times \frac{3}{8} = \frac{-9}{140}$.
  - Multiplicative Identity ($1$): $1 \times \frac{a}{b} = \frac{a}{b}$. $1$ is called multiplicative identity.
  - Multiplication Property of Zero ($0$): $0 \times \frac{a}{b} = 0 = \frac{a}{b} \times 0$.
  - Distributive Property of Multiplication over Addition/Subtraction:
    $\frac{a}{b} \times \left(\frac{c}{d} \pm \frac{e}{f}\right) = \left(\frac{a}{b} \times \frac{c}{d}\right) \pm \left(\frac{a}{b} \times \frac{e}{f}\right)$.
    Verified on Page 8: $\frac{2}{5} \times \left[\frac{-3}{7} + \frac{6}{11}\right] = \frac{18}{385}$.
  - Division Properties (Page 8):
    (a) $\frac{a}{b} \div \frac{c}{d}$ is rational for $\frac{c}{d} \ne 0$.
    (b) $\frac{a}{b} \div \frac{a}{b} = 1$; $\frac{a}{b} \div \left(\frac{-a}{b}\right) = -1$; $\left(\frac{-a}{b}\right) \div \frac{a}{b} = -1$.
    (c) $\frac{a}{b} \div 1 = \frac{a}{b}$; $\frac{a}{b} \div (-1) = \frac{-a}{b}$.
  - **Exercise 1C (Page 8 & 9)**:
    - **Q1. Find the product and verify the commutative property for multiplication of rational numbers**:
      (a) $\frac{1}{11} \times \frac{6}{7}$ [Product: $\frac{6}{77}$]
      (b) $\frac{3}{5} \times \left[\frac{-7}{8}\right]$ [Product: $\frac{-21}{40}$]
      (c) $\left[\frac{-13}{19}\right] \times \frac{7}{8}$ [Product: $\frac{-91}{152}$]
      (d) $\frac{-5}{9} \times \left[\frac{-11}{32}\right]$ [Product: $\frac{55}{288}$]
    - **Q2. Find the product and verify the associative property for multiplication of rational numbers**:
      (a) $\left[\frac{7}{20} \times \frac{5}{21}\right] \times \frac{1}{3}$ [Product: $\frac{1}{36}$]
      (b) $\frac{2}{7} \times \left[\frac{-7}{3} \times \frac{6}{-11}\right]$ [Product: $\frac{4}{11}$]
      (c) $\left[\frac{-7}{15} \times \frac{-2}{9}\right] \times \left[\frac{-3}{7}\right]$ [Product: $\frac{-2}{45}$]
      (d) $\frac{8}{9} \times \left[\frac{-8}{5} \times \frac{6}{7}\right]$ [Product: $\frac{-128}{105}$]
    - **Q3. Simplify the following and verify the distributive property of multiplication over addition**:
      (a) $\frac{5}{4} \times \left[\frac{-6}{7} + \frac{2}{5}\right]$ [Result: $\frac{-4}{7}$]
      (b) $3 \times \left[\frac{1}{3} + \left(\frac{-5}{11}\right)\right]$ [Result: $\frac{-4}{11}$]
      (c) $0 \times \left[\frac{1}{2} + \frac{2}{5}\right]$ [Result: $0$]
    - **Q4. Write the name of the property used in each of the following**:
      (a) $\frac{2}{7} \times \frac{13}{11} = \frac{13}{11} \times \frac{2}{7}$ [Commutative Property of Multiplication]
      (b) $\frac{-5}{7} \times \left[\frac{6}{11} \times \frac{7}{13}\right] = \left[\frac{-5}{7} \times \frac{6}{11}\right] \times \frac{7}{13}$ [Associative Property of Multiplication]
      (c) $\frac{1}{7} \times \frac{3}{5} = \frac{3}{35}$ is a rational number [Closure Property of Multiplication]
      (d) $\frac{7}{11} \times \left[\frac{1}{6} + \frac{2}{13}\right] = \frac{7}{11} \times \frac{1}{6} + \frac{7}{11} \times \frac{2}{13}$ [Distributive Property of Multiplication over Addition]
      (e) $\frac{-9}{8} \times 0 = 0 = 0 \times \frac{-9}{8}$ [Multiplicative Property of Zero]
      (f) $1 \times \frac{7}{9} = \frac{7}{9}$ [Multiplicative Identity (Property of 1)]
    - **Q5. Fill in the blanks (Page 9)**:
      (a) $\left[\frac{-9}{16}\right] \times \left[\frac{11}{7}\right] = \left[\frac{11}{7}\right] \times \left[\underline{\frac{-9}{16}}\right]$
      (b) $\left[\underline{\frac{-5}{8}}\right] \times \left[\frac{-7}{9}\right] = \left[\frac{-7}{9}\right] \times \left[\frac{-5}{8}\right]$
      (c) $\left[\frac{-7}{13}\right] \times \underline{1} = \left[\frac{-7}{13}\right]$
      (d) $\underline{0} \times \left(\frac{-19}{47}\right) = 0$
      (e) $\frac{-3}{4} \times \left[\frac{1}{3} + \left(\frac{-5}{6}\right)\right] = \left[\frac{-3}{4} \times \underline{\frac{1}{3}}\right] + \left[\frac{-3}{4} \times \underline{\frac{-5}{6}}\right]$
      (f) $\frac{-2}{5} \times \left[\frac{6}{7} \times \left(\frac{-8}{9}\right)\right] = \left[\frac{-2}{5} \times \underline{\frac{6}{7}}\right] \times \left(\frac{-8}{9}\right)$
      (g) $\frac{3}{8} \div \frac{3}{8} = \underline{1}$
      (h) $\frac{7}{13} \div \left[\underline{\frac{-7}{13}}\right] = -1$
      (i) $\frac{14}{19} \div \underline{1} = \frac{14}{19}$
      (j) $\left[\underline{\frac{-13}{15}}\right] \div \left[\frac{-13}{15}\right] = 1$

- **Page 9 (`page_09.png`) — Prescribed Questions with Solutions**:
  - **Q1. Name the property under multiplication used in each of the following**:
    (i) $\frac{-4}{5} \times 1 = 1 \times \frac{-4}{5} = \frac{-4}{5}$ [Solution: 1 is the multiplicative identity]
    (ii) $\frac{-13}{17} \times \frac{-2}{7} = \frac{-2}{7} \times \frac{-13}{17}$ [Solution: Commutativity]
    (iii) $\frac{-19}{29} \times \frac{29}{-19} = 1$ [Solution: Multiplicative inverse]
  - **Q2. Tell what property allows you to compute $\frac{1}{3} \times \left[6 \times \frac{4}{3}\right]$ as $\left[\frac{1}{3} \times 6\right] \times \frac{4}{3}$**:
    [Solution: Form $a \times (b \times c) = (a \times b) \times c$. Hence, Associative Property]
  - **Q3. The product of two rational numbers is always a _______**:
    [Solution: rational number]

---

### 1.2 Inspection of `rational_numbers_ad_contract.yaml`
Lines 53–68 of `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/rational_numbers_ad_contract.yaml` state:
```yaml
53: assessment_suite:
54:   total_questions: 48
55:   source_breakdown:
56:     exercise_1a: 24
57:     exercise_1b: 12
58:     exercise_1c: 12
59:   tiers:
60:     tier_1_warmup:
61:       title: "Warm-Up Drills (Direct Addition, Subtraction & Reciprocal)"
62:       count: 16
63:     tier_2_deep_dive:
64:       title: "Deep Dive Challenges (Multi-Step Fractions & Property Verification)"
65:       count: 18
66:     tier_3_boss:
67:       title: "Boss Challenge (Full Expression Simplification & Board Prescribed Problems)"
68:       count: 14
```
**Discrepancy**: The contract specifies a total of 48 questions (1A: 24, 1B: 12, 1C: 12), whereas the actual textbook contains 75 distinct questions (1A: 30, 1B: 13, 1C: 27, Prescribed: 5). 27 questions were omitted from the contract scope.

### 1.3 Inspection of `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`
Direct code inspection reveals:
1. **Zero Gamified Assessment Sections**: Neither `#section-warmup`, `#section-deep_dive`, nor `#section-boss` exists anywhere in the HTML file (`grep_search` returned 0 matches).
2. **Missing 98.7% of Textbook Exercises**: The HTML contains only the 5 generic linear concept nodes with:
   - 5 end-of-node multiple-choice quizzes (lines 750, 781, 812, 843, 874).
   - 5 worked examples in `var WE` (lines 544–730).
   - Among these 10 items, **only 1 single sub-question** from the AD textbook is present: Exercise 1A Q3(c) ($\frac{11}{-13} \times \frac{-39}{22}$) inside `we_multiplication` (line 658).
   - **74 out of 75 textbook questions are completely absent from the HTML file.**
3. **Corrupted Real-World Hook**:
   Line 739: `Seema bought 5 pens for 40 rupees wholesale at 8 rupees per pen.`
   Textbook Ground Truth (Page 1): Seema wants 3 pens, Sachin wants 2 pens (₹5 individually); 5 pens cost ₹22 wholesale $\implies$ cost per pen = ₹22/5 = ₹4.40. The HTML replaces the fundamental non-integer fraction $\frac{22}{5} = 4.40$ with an integer division $\frac{40}{5} = 8$, completely destroying the pedagogical purpose of the hook!
4. **Out-of-Syllabus Regrouping Example**:
   Line 695: `we_regrouping` uses `3/7 + (-6/11) + (-8/21) + 5/22`. This is an NCERT Class 8 worked example, not from the AD textbook.

### 1.4 Inspection of Intermediate Files (`ad_all_questions.json` & `compile_all_ad_questions.py`)
In `chapters/compile_all_ad_questions.py` and `chapters/add_remaining_questions.py`:
1. Total questions compiled was 46 (omitting 29 textbook questions).
2. **Severe Arithmetic Flaw in Ex 1A Q5(a)** (lines 1111–1133 of `ad_all_questions.json`):
   ```json
   "q": "Simplify: [(3/2) × (-7/4) × (8/9)] - [(-15/2) × (3/7) × (8/14)]",
   "ans": "-13/21",
   "m": "First term cancels to -7/3; second cancels to -90/56 = -45/28. Combine carefully.",
   "exp": "First bracket cancels to -7/3. Second bracket cancels to -45/28. Difference = -7/3 - (-45/28) = -13/21."
   ```
   **Proof of Error**:
   - Term 1: $\frac{3 \times (-7) \times 8}{2 \times 4 \times 9} = \frac{-168}{72} = \frac{-7}{3}$.
   - Term 2: If the problem is as printed in the JSON ($\frac{-15}{2} \times \frac{3}{7} \times \frac{8}{14}$), then $\frac{-15 \times 3 \times 8}{2 \times 7 \times 14} = \frac{-360}{196} = \frac{-90}{49}$.
   - If the denominator was 56 (as claimed in the JSON comment), then $(-7/3) - (-45/28) = -7/3 + 45/28 = \frac{-196 + 135}{84} = \frac{-61}{84} \approx -0.726$.
   - The JSON asserts the answer is $-13/21 = \frac{-52}{84} \approx -0.619$.
   - In neither case does the expression equal $-13/21$. This is a severe mathematical defect.

---

## 2. Logic Chain

1. **Premise 1 (Authoritative Mandate)**: The task mandate (`ORIGINAL_REQUEST.md` R1, Follow-up R1/R4, and user prompt) requires:
   - 100% of textbook exercises from `AD class 8th math rational number.pdf` (Exercises 1A, 1B, 1C) must be enumerated and mapped into a 3-tier gamified assessment (Warm-up `#section-warmup` $\to$ Deep Dive `#section-deep_dive` $\to$ Boss Challenge `#section-boss`).
   - Zero dropped exercises.
   - 100% textbook ground truth with zero spoilers and mathematical accuracy.

2. **Premise 2 (Empirical Ground Truth)**: Direct inspection of `page_01.png` through `page_09.png` establishes that the AD textbook contains:
   - Exercise 1A: 5 main questions comprising 30 sub-parts ($8 + 8 + 6 + 6 + 2$).
   - Exercise 1B: 4 main questions comprising 13 sub-parts ($4 + 4 + 4 + 1$).
   - Exercise 1C: 5 main questions comprising 27 sub-parts ($4 + 4 + 3 + 6 + 10$).
   - Prescribed Board Solved Questions: 3 main questions comprising 5 sub-parts ($3 + 1 + 1$).
   - Total exact question count = $30 + 13 + 27 + 5 = \mathbf{75}$ questions.

3. **Premise 3 (Audit of Existing Implementation)**:
   - `rational_numbers_ad_contract.yaml` accounts for only 48 questions (1A: 24, 1B: 12, 1C: 12), dropping 27 questions.
   - `chapters/ad_all_questions.json` compiles 46 questions, dropping 29 questions.
   - `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` implements only 1 single sub-part from the textbook in a worked example (`we_multiplication`), with 0 questions in `#section-warmup`, `#section-deep_dive`, and `#section-boss` (the sections do not exist in the DOM).

4. **Inference / Gap Analysis**:
   - There is a massive reconciliation gap of 74 missing questions between the textbook (75 questions) and the deployed HTML (1 question).
   - Even between the contract (48 questions) and the deployed HTML, 47 questions were never integrated into the HTML.
   - The contract itself under-counted the textbook by 27 questions.
   - The stationery shop scenario in the HTML uses erroneous integer data (`5 pens for 40 rupees wholesale at 8 rupees per pen`) instead of the textbook's defining fraction ($\frac{22}{5} = ₹4.40$).

5. **Structural Mapping to 3-Tier Gamified Assessment**:
   To reconcile 100% of the 75 questions into the AASHA pedagogical progression:
   - **Tier 1 — Warm-up (`#section-warmup`)** [31 Questions]: Foundational arithmetic operations and direct blanks.
     - Ex 1A Q1(a–h) [8]
     - Ex 1A Q2(a–h) [8]
     - Ex 1B Q1(a–d) [4]
     - Ex 1C Q5(a–j) [10]
     - Prescribed Q3 [1]
   - **Tier 2 — Deep Dive (`#section-deep_dive`)** [30 Questions]: Multiplicative operations, property identification, and associative groupings.
     - Ex 1A Q3(a–f) [6]
     - Ex 1A Q4(a–f) [6]
     - Ex 1B Q2(a–d) [4]
     - Ex 1B Q3(a–d) [4]
     - Ex 1C Q4(a–f) [6]
     - Prescribed Q1(i–iii) [3]
     - Prescribed Q2 [1]
   - **Tier 3 — Boss Challenge (`#section-boss`)** [14 Questions]: Complex multi-step expressions, nested brackets, and algebraic verifications.
     - Ex 1A Q5(a, b) [2]
     - Ex 1B Q4 [1]
     - Ex 1C Q1(a–d) [4]
     - Ex 1C Q2(a–d) [4]
     - Ex 1C Q3(a–c) [3]

---

## 3. Caveats

1. **Scanned Image Resolution & Misprints in Textbook**:
   - Page 6, Exercise 1B Q4 contains a printed misprint in the textbook: *"verify that $a + b = b + c$"*. Since only two variables $a$ and $b$ are given ($a = \frac{8}{9}, b = \frac{-3}{8}$), the third letter $c$ is obviously a misprint for $a$. The audit corrects this to $a + b = b + a$.
   - Page 4, Exercise 1A Q5(a) printed denominator in the second bracket: whether it is $\frac{8}{14}$ or $\frac{8}{4}$ has subtle scan artifact blur. The arithmetic was computed as printed $\frac{8}{14}$, giving $\frac{-73}{147}$.
   - Page 8, Exercise 1C Q3(c) printed operator: printed as $0 \times \left[\frac{1}{2} + \frac{2}{5}\right]$ (or $\times$). Evaluates to $0$.
   - Page 9 bottom contains a header "Multiple Choice Questions" which is cut off at the page footer (the PDF ends on page 9). These are partial fragments and not complete textbook exercises.
2. **Scope Boundary**: As an exploration subagent, this audit is strictly read-only. No source files or HTML files have been edited. All proposed reconciliations and question banks are documented for downstream implementers.

---

## 4. Conclusion

1. **Definitive Enumeration**: The AD Class 8 Mathematics textbook Chapter 1 contains exactly **75 textbook exercises and solved board questions** across Exercises 1A (30), 1B (13), 1C (27), and Prescribed Board Solved (5).
2. **Current Implementation Status**:
   - `rational_numbers_ad_contract.yaml` is incomplete: it accounts for only 48 questions (64% coverage), omitting 27 questions.
   - `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` is severely deficient: it contains only 1 question from the textbook (1.3% coverage), lacking 74 textbook questions, lacking the 3-tier gamified assessment DOM structure (`#section-warmup`, `#section-deep_dive`, `#section-boss`), and containing an incorrect introductory real-world hook ($40/5 = 8$ instead of $22/5 = 4.40$).
3. **Actionable Roadmap for Implementer**:
   - Step 1: Update `rational_numbers_ad_contract.yaml` to reflect the complete 75-question curriculum and correct the tier counts (Warm-up: 31, Deep Dive: 30, Boss: 14).
   - Step 2: Fix the introductory Stationery Shop narrative in Node 1 to faithfully use ₹22 for 5 pens ($22/5 = ₹4.40$).
   - Step 3: Fix the arithmetic flaw in Ex 1A Q5(a) and author complete, insulated question schemas for all 75 questions with valid misconception feedback ($m > 15$ chars, 0 spoilers) and 4-tier progressive hints ($H1$–$H4$).
   - Step 4: Rebuild `RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` with the complete 75-question 3-tier assessment DOM engine and dual-view manipulatives under full KaTeX/math insulation.

---

## 5. Verification Method

To independently verify all claims and findings in this report:

1. **Verify Source Textbook Images**:
   Inspect the 9 extracted page scans in `content/extracted_pages/ad_rational_9p/`:
   - `page_01.png` & `page_02.png`: Verify Seema & Sachin pen scenario (₹22 for 5 pens, ₹4.40 per pen).
   - `page_04.png`: Verify Exercise 1A (Q1: 8 parts, Q2: 8 parts, Q3: 6 parts, Q4: 6 parts, Q5: 2 parts = 30 parts).
   - `page_06.png`: Verify Exercise 1B (Q1: 4 parts, Q2: 4 parts, Q3: 4 parts, Q4: 1 part = 13 parts).
   - `page_08.png` & `page_09.png`: Verify Exercise 1C (Q1: 4 parts, Q2: 4 parts, Q3: 3 parts, Q4: 6 parts, Q5: 10 parts = 27 parts).
   - `page_09.png`: Verify Prescribed Questions (Q1: 3 parts, Q2: 1 part, Q3: 1 part = 5 parts).

2. **Verify Missing Sections in Current HTML**:
   Run grep searches on `chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`:
   - Search `section-warmup`: Result must be 0 matches.
   - Search `section-deep_dive`: Result must be 0 matches.
   - Search `section-boss`: Result must be 0 matches.
   - Search `40 rupees`: Confirm line 739 corrupts the hook numbers.

3. **Verify Existing Benchmark Command**:
   ```bash
   node benchmarks/qa_ltruth_benchmark.js --file chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html
   ```
   Note that while the current file passes the benchmark syntactically due to its minimal 5 generic nodes, it fails the substantive curriculum requirement of 100% textbook exercise extraction.

---

### Appendix: Comprehensive Master Question Inventory (75 Items)

| Index | ID | Textbook Tag | Question Text Summary | Type | Target Tier |
|---|---|---|---|---|---|
| 1 | `ad_1a_q1_a` | Ex 1A Q1(a) | Add: 5/2 and -11/2 | Addition (same den) | Warm-up |
| 2 | `ad_1a_q1_b` | Ex 1A Q1(b) | Add: 7/5 and 13/5 | Addition (same den) | Warm-up |
| 3 | `ad_1a_q1_c` | Ex 1A Q1(c) | Add: -7/8 and 12/-8 | Addition (neg den) | Warm-up |
| 4 | `ad_1a_q1_d` | Ex 1A Q1(d) | Add: -11/5 and -9/5 | Addition (same den) | Warm-up |
| 5 | `ad_1a_q1_e` | Ex 1A Q1(e) | Add: 4/-7 and -5/8 | Addition (diff den) | Warm-up |
| 6 | `ad_1a_q1_f` | Ex 1A Q1(f) | Add: -13/7 and 12/-5 | Addition (diff den) | Warm-up |
| 7 | `ad_1a_q1_g` | Ex 1A Q1(g) | Add: -15/9 and -17/11 | Addition (diff den) | Warm-up |
| 8 | `ad_1a_q1_h` | Ex 1A Q1(h) | Add: -9/-33 and 5/11 | Addition (reduce first) | Warm-up |
| 9 | `ad_1a_q2_a` | Ex 1A Q2(a) | Subtract: (-18/5) - (-8/5) | Subtraction (same den) | Warm-up |
| 10 | `ad_1a_q2_b` | Ex 1A Q2(b) | Subtract: (-19/15) - (-6/30) | Subtraction (reduce) | Warm-up |
| 11 | `ad_1a_q2_c` | Ex 1A Q2(c) | Subtract: (-6/11) - (-7/11) | Subtraction (same den) | Warm-up |
| 12 | `ad_1a_q2_d` | Ex 1A Q2(d) | Subtract: (-1/4) - (-2/8) | Subtraction (zero result) | Warm-up |
| 13 | `ad_1a_q2_e` | Ex 1A Q2(e) | Subtract: (-59/5) - 19/5 | Subtraction (same den) | Warm-up |
| 14 | `ad_1a_q2_f` | Ex 1A Q2(f) | Subtract: (-4/7) - (-8/9) | Subtraction (diff den) | Warm-up |
| 15 | `ad_1a_q2_g` | Ex 1A Q2(g) | Subtract: 7/24 - (-13/-26) | Subtraction (reduce) | Warm-up |
| 16 | `ad_1a_q2_h` | Ex 1A Q2(h) | Subtract: 7/25 - (-6/15) | Subtraction (diff den) | Warm-up |
| 17 | `ad_1a_q3_a` | Ex 1A Q3(a) | Multiply: (4/7) by (-2/5) | Multiplication | Deep Dive |
| 18 | `ad_1a_q3_b` | Ex 1A Q3(b) | Multiply: (-3/8) by (-12/15) | Multiplication | Deep Dive |
| 19 | `ad_1a_q3_c` | Ex 1A Q3(c) | Multiply: (11/-13) by (-39/22) | Multiplication | Deep Dive |
| 20 | `ad_1a_q3_d` | Ex 1A Q3(d) | Multiply: (-5/9) by (81/35) | Multiplication | Deep Dive |
| 21 | `ad_1a_q3_e` | Ex 1A Q3(e) | Multiply: (-9/25) by (-35/27) | Multiplication | Deep Dive |
| 22 | `ad_1a_q3_f` | Ex 1A Q3(f) | Multiply: (-18/25) by (40/-36) | Multiplication | Deep Dive |
| 23 | `ad_1a_q4_a` | Ex 1A Q4(a) | Divide: (16/7) by (-8/14) | Division (reciprocal) | Deep Dive |
| 24 | `ad_1a_q4_b` | Ex 1A Q4(b) | Divide: (-7/8) by (-21) | Division (integer divisor) | Deep Dive |
| 25 | `ad_1a_q4_c` | Ex 1A Q4(c) | Divide: (3/8) by (-4/5) | Division (reciprocal) | Deep Dive |
| 26 | `ad_1a_q4_d` | Ex 1A Q4(d) | Divide: (-1/15) by (8/3) | Division (reciprocal) | Deep Dive |
| 27 | `ad_1a_q4_e` | Ex 1A Q4(e) | Divide: (-3/26) by (9/78) | Division (-1 result) | Deep Dive |
| 28 | `ad_1a_q4_f` | Ex 1A Q4(f) | Divide: (-22/26) by (-33/39) | Division (1 result) | Deep Dive |
| 29 | `ad_1a_q5_a` | Ex 1A Q5(a) | Simplify: [(3/2)*(-7/4)*(8/9)] - [(-15/2)*(3/7)*(8/14)] | Multi-step nested | Boss Challenge |
| 30 | `ad_1a_q5_b` | Ex 1A Q5(b) | Simplify: [(7/3)*(9/11)] + [(4/3)*(7/22)] - [(3/-11)*(-7/9)] | Multi-step nested | Boss Challenge |
| 31 | `ad_1b_q1_a` | Ex 1B Q1(a) | Commutative fill: -3/7 + 4/9 = ___ + (-3/7) | Commutative fill | Warm-up |
| 32 | `ad_1b_q1_b` | Ex 1B Q1(b) | Commutative fill: 2/3 + (-5/6) = (-5/6) + ___ | Commutative fill | Warm-up |
| 33 | `ad_1b_q1_c` | Ex 1B Q1(c) | Commutative fill: [(-11/29)] + [(-5/31)] = ___ | Commutative fill | Warm-up |
| 34 | `ad_1b_q1_d` | Ex 1B Q1(d) | Commutative fill: -7/13 + 11/23 = ___ | Commutative fill | Warm-up |
| 35 | `ad_1b_q2_a` | Ex 1B Q2(a) | Associative fill: [(1/11)+(2/13)]+7/6 = 1/11+[___+7/6] | Associative fill | Deep Dive |
| 36 | `ad_1b_q2_b` | Ex 1B Q2(b) | Associative fill: 17/21+[(-5/13)+9/16] = [17/21+___]+9/16 | Associative fill | Deep Dive |
| 37 | `ad_1b_q2_c` | Ex 1B Q2(c) | Associative fill: [(-31/41)]+[9/14+8/15] = [___+9/14]+8/15 | Associative fill | Deep Dive |
| 38 | `ad_1b_q2_d` | Ex 1B Q2(d) | Associative fill: [(2/7+3/8)]+(-9/14) = 2/7+[3/8+___] | Associative fill | Deep Dive |
| 39 | `ad_1b_q3_a` | Ex 1B Q3(a) | State property: -2/5 + 3/7 = 3/7 + (-2/5) | Property Name | Deep Dive |
| 40 | `ad_1b_q3_b` | Ex 1B Q3(b) | State property: 2/5 + [9/7 + (-3/8)] = [2/5 + 9/7] + (-3/8) | Property Name | Deep Dive |
| 41 | `ad_1b_q3_c` | Ex 1B Q3(c) | State property: -3/7 + [(-5/8) + 9/4] = [(-3/7) + (-5/8)] + 9/4 | Property Name | Deep Dive |
| 42 | `ad_1b_q3_d` | Ex 1B Q3(d) | State property: 3/10 + [(-11/15) + 9/-7] = [3/10 + (-11/15)] + 9/-7 | Property Name | Deep Dive |
| 43 | `ad_1b_q4` | Ex 1B Q4 | If a=8/9, b=-3/8, verify a+b = b+a | Property Verify | Boss Challenge |
| 44 | `ad_1c_q1_a` | Ex 1C Q1(a) | Multiply and verify Commutativity: (1/11) * (6/7) | Property Verify | Boss Challenge |
| 45 | `ad_1c_q1_b` | Ex 1C Q1(b) | Multiply and verify Commutativity: (3/5) * [(-7/8)] | Property Verify | Boss Challenge |
| 46 | `ad_1c_q1_c` | Ex 1C Q1(c) | Multiply and verify Commutativity: [(-13/19)] * (7/8) | Property Verify | Boss Challenge |
| 47 | `ad_1c_q1_d` | Ex 1C Q1(d) | Multiply and verify Commutativity: (-5/9) * [(-11/32)] | Property Verify | Boss Challenge |
| 48 | `ad_1c_q2_a` | Ex 1C Q2(a) | Multiply and verify Associativity: [(7/20)*(5/21)]*(1/3) | Property Verify | Boss Challenge |
| 49 | `ad_1c_q2_b` | Ex 1C Q2(b) | Multiply and verify Associativity: (2/7)*[(-7/3)*(6/-11)] | Property Verify | Boss Challenge |
| 50 | `ad_1c_q2_c` | Ex 1C Q2(c) | Multiply and verify Associativity: [(-7/15)*(-2/9)]*[(-3/7)] | Property Verify | Boss Challenge |
| 51 | `ad_1c_q2_d` | Ex 1C Q2(d) | Multiply and verify Associativity: (8/9)*[(-8/5)*(6/7)] | Property Verify | Boss Challenge |
| 52 | `ad_1c_q3_a` | Ex 1C Q3(a) | Simplify and verify Distributivity: (5/4)*[(-6/7) + 2/5] | Property Verify | Boss Challenge |
| 53 | `ad_1c_q3_b` | Ex 1C Q3(b) | Simplify and verify Distributivity: 3*[1/3 + (-5/11)] | Property Verify | Boss Challenge |
| 54 | `ad_1c_q3_c` | Ex 1C Q3(c) | Simplify and verify Distributivity: 0*[1/2 + 2/5] | Property Verify | Boss Challenge |
| 55 | `ad_1c_q4_a` | Ex 1C Q4(a) | Name property: (2/7)*(13/11) = (13/11)*(2/7) | Property Name | Deep Dive |
| 56 | `ad_1c_q4_b` | Ex 1C Q4(b) | Name property: (-5/7)*[(6/11)*(7/13)] = [(-5/7)*(6/11)]*(7/13) | Property Name | Deep Dive |
| 57 | `ad_1c_q4_c` | Ex 1C Q4(c) | Name property: (1/7)*(3/5) = 3/35 is rational | Property Name | Deep Dive |
| 58 | `ad_1c_q4_d` | Ex 1C Q4(d) | Name property: (7/11)*[1/6 + 2/13] = (7/11)*(1/6) + (7/11)*(2/13) | Property Name | Deep Dive |
| 59 | `ad_1c_q4_e` | Ex 1C Q4(e) | Name property: (-9/8)*0 = 0 = 0*(-9/8) | Property Name | Deep Dive |
| 60 | `ad_1c_q4_f` | Ex 1C Q4(f) | Name property: 1 * (7/9) = 7/9 | Property Name | Deep Dive |
| 61 | `ad_1c_q5_a` | Ex 1C Q5(a) | Fill in blank: [(-9/16)*(11/7)] = (11/7)*[___] | Property fill | Warm-up |
| 62 | `ad_1c_q5_b` | Ex 1C Q5(b) | Fill in blank: [___]*[(-7/9)] = [(-7/9)]*[(-5/8)] | Property fill | Warm-up |
| 63 | `ad_1c_q5_c` | Ex 1C Q5(c) | Fill in blank: [(-7/13)] * ___ = [(-7/13)] | Property fill | Warm-up |
| 64 | `ad_1c_q5_d` | Ex 1C Q5(d) | Fill in blank: ___ * (-19/47) = 0 | Property fill | Warm-up |
| 65 | `ad_1c_q5_e` | Ex 1C Q5(e) | Fill in blank: -3/4*[1/3 + (-5/6)] = [(-3/4)*___] + [(-3/4)*___] | Distributive fill | Warm-up |
| 66 | `ad_1c_q5_f` | Ex 1C Q5(f) | Fill in blank: -2/5*[6/7 * (-8/9)] = [(-2/5)*___]*(-8/9) | Associative fill | Warm-up |
| 67 | `ad_1c_q5_g` | Ex 1C Q5(g) | Fill in blank: (3/8) ÷ (3/8) = ___ | Division fill | Warm-up |
| 68 | `ad_1c_q5_h` | Ex 1C Q5(h) | Fill in blank: (7/13) ÷ ___ = -1 | Division fill | Warm-up |
| 69 | `ad_1c_q5_i` | Ex 1C Q5(i) | Fill in blank: (14/19) ÷ ___ = 14/19 | Division fill | Warm-up |
| 70 | `ad_1c_q5_j` | Ex 1C Q5(j) | Fill in blank: ___ ÷ [(-13/15)] = 1 | Division fill | Warm-up |
| 71 | `ad_presc_1_i` | Prescribed Q1(i) | Name property: (-4/5) * 1 = 1 * (-4/5) = -4/5 | Property Name | Deep Dive |
| 72 | `ad_presc_1_ii` | Prescribed Q1(ii) | Name property: (-13/17) * (-2/7) = (-2/7) * (-13/17) | Property Name | Deep Dive |
| 73 | `ad_presc_1_iii` | Prescribed Q1(iii) | Name property: (-19/29) * (29/-19) = 1 | Property Name | Deep Dive |
| 74 | `ad_presc_2` | Prescribed Q2 | What property allows computing 1/3 * [6 * 4/3] as [1/3 * 6] * 4/3? | Property Name | Deep Dive |
| 75 | `ad_presc_3` | Prescribed Q3 | The product of two rational numbers is always a _______ | Closure Property | Warm-up |
