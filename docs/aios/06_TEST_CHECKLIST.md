# 06_TEST_CHECKLIST.md
# Verification, Testing & Empirical Evidence Checklist

Testing is factual evidence. Every check status must be backed by reproducible execution output.

Legend:
- `[ ]` NOT RUN
- `[~]` RUNNING
- `[✓]` VERIFIED
- `[✗]` FAILED
- `[!]` BLOCKED
- `[?]` UNKNOWN

---

## 1. Automated Architecture & Ecosystem Tests

| Check ID | Description | Status | Command | Expected Output | Actual Output | Evidence Location |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TEST-001** | Critical structure lint | `[✓]` | `node scripts/check-structure.mjs` | `Structure OK (12 critical files)` | `Structure OK (12 critical files)` | Execution at 2026-09-08 04:11:46 |
| **TEST-002** | Offline event outbox persistence & sync | `[✓]` | `node --test tests/unit/*.test.js` | `ok 1 - offline event outbox survives and syncs` | Pass (10.6ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-003** | Class 1–10 stage mapping | `[✓]` | `node --test tests/unit/*.test.js` | `ok 2 - Class 1-10 stage mapping` | Pass (4.1ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-004** | Chapter schema and TLN order | `[✓]` | `node --test tests/unit/*.test.js` | `ok 3 - chapter schema and TLN order` | Pass (5.8ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-005** | Assessment & TEAS separation | `[✓]` | `node --test tests/unit/*.test.js` | `ok 4 - assessment and TEAS separate mastery...` | Pass (1.7ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-006** | Reward ledger idempotency | `[✓]` | `node --test tests/unit/*.test.js` | `ok 5 - reward ledger is idempotent` | Pass (2.1ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-007** | Aggregate-only impact reporting | `[✓]` | `node --test tests/integration/*.test.js` | `ok 6 - impact reporting is aggregate-only` | Pass (2.0ms) | `Aasha-AI/.../tests/integration/ecosystem.test.js` |
| **TEST-008** | Approved assets and AI governance | `[✓]` | `node --test tests/integration/*.test.js` | `ok 7 - approved assets and AI governance` | Pass (2.4ms) | `Aasha-AI/.../tests/integration/ecosystem.test.js` |
| **TEST-009** | Class 7 Perimeter & Area schema validation | `[✓]` | `node --test tests/integration/*.test.js` | `ok 8 - Generalization: Class 7 Perimeter...` | Pass (10.7ms) | `Aasha-AI/.../tests/integration/ecosystem.test.js` |
| **TEST-010** | Modular 2D Grid Area visual model | `[✓]` | `node --test tests/integration/*.test.js` | `ok 9 - Generalization: Visual Engine renders...` | Pass (2.0ms) | `Aasha-AI/.../tests/integration/ecosystem.test.js` |
| **TEST-011** | Question Engine perimeter vs area misconceptions | `[✓]` | `node --test tests/integration/*.test.js` | `ok 10 - Generalization: Question Engine...` | Pass (0.9ms) | `Aasha-AI/.../tests/integration/ecosystem.test.js` |
| **TEST-012** | Two-tier diagnostic on Class 7 content | `[✓]` | `node --test tests/integration/*.test.js` | `ok 11 - Generalization: Two-tier diagnostic...` | Pass (1.4ms) | `Aasha-AI/.../tests/integration/ecosystem.test.js` |
| **TEST-013** | Interactive SVG fraction bar keyboard a11y | `[✓]` | `node --test tests/unit/*.test.js` | `ok 12 - P0-A & ISS-02: Visual engine renders...` | Pass (2.6ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-014** | Distractor misconception ID extraction | `[✓]` | `node --test tests/unit/*.test.js` | `ok 13 - P0-B & P0-D: Question engine extracts...` | Pass (0.6ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-015** | Fractions chapter 3 diagnostic questions/node | `[✓]` | `node --test tests/unit/*.test.js` | `ok 14 - P0-C: Fractions chapter contains 3...` | Pass (1.1ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-016** | Two-tier attempt tracking score decoupling | `[✓]` | `node --test tests/unit/*.test.js` | `ok 15 - ISS-01: Two-tier attempt tracking...` | Pass (0.7ms) | `Aasha-AI/.../tests/unit/learner.test.js` |
| **TEST-017** | Deterministic reward event ID prevents duplication | `[✓]` | `node --test tests/unit/*.test.js` | `ok 16 - ISS-03: Deterministic reward event ID...` | Pass (0.6ms) | `Aasha-AI/.../tests/unit/learner.test.js` |

---

## 2. Standalone Chapter Quality & L-Truth 200+ Verification (Run: 2026-09-08)

| Check ID | Target Chapter File | Status | Questions | Misconceptions | Spoilers | Score | Evidence |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **QA-CH-01** | `AlgebraicExpressions_Class8_Gamified_v5_Enhanced_v6.html` | `[✓]` | 20 | 58 | **0** | **100/100** | Full compliance across all 10 rules. |
| **QA-CH-02** | `ComparingQuantities_Percentage_Class8_Gamified_v5_(1)_Enhanced_v6.html` | `[✗]` | 73 | 164 | **82** | **0/100** | Leaks answers in calculations (BUG-003). |
| **QA-CH-03** | `Fractions_Gamified_v5_(2)_Enhanced_v6.html` | `[✗]` | 102 | 215 | **47** | **0/100** | Leaks answers (BUG-003); size 6.78MB (BUG-001). |
| **QA-CH-04** | `Perimeter_Area_Gamified_v5_(2)_Enhanced_v6.html` | `[✗]` | 70 | 168 | **60** | **0/100** | Leaks formulas/answers in `m` field (BUG-003). |
| **QA-CH-05** | `Polynomials_Class10_Gamified_v5_(1)_Enhanced_v6.html` | `[✗]` | 69 | 157 | **66** | **0/100** | Leaks roots/sums in `m` field (BUG-003). |
| **QA-CH-06** | `Polynomials_JSXGraph_Inlined_Enhanced_v6.html` | `[✗]` | 0 | 0 | 0 | **46/100** | Standalone demo missing standard v5 nav buttons. |
| **QA-CH-07** | `Polynomials_Offline_Demos_Enhanced_v6.html` | `[✗]` | 0 | 0 | 0 | **57/100** | Standalone demo missing standard v5 nav buttons. |

---

## 3. General Synthesis
- **Syntax Validation**: 7/7 (100% PASS).
- **Rule #10 Offline Compliance**: 7/7 (100% PASS - zero external CDNs).
- **Rule #1 Zero-Spoiler Compliance**: 1/7 PASS (`AlgebraicExpressions`), 4/7 FAIL with 255 total spoilers, 2/7 non-applicable (demos).
