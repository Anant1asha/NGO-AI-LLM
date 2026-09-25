# EVID-002: L-Truth 200+ Verification Benchmark across 7 Generated Chapters

- **ID**: EVID-002
- **SOURCE**: Automated VM Sandbox AST Inspection + OpenRouter / Claude Code Verification Harness (`benchmarks/run_ltruth_7_chapters.js`)
- **DATE**: 2026-09-08T19:53:26+05:30
- **TYPE**: BENCHMARK_EXECUTION_REPORT
- **CLAIM**: Full syntax validation, Rule #1 Zero-Spoiler audit, math-rt collision detection, and 10 Critical Production QA Rules executed across all 7 generated chapter files in `chapters/`.
- **LOCATION**: `Aasha-AI/benchmarks/ltruth_7_chapters_report.json`
- **CONFIDENCE**: 1.0 (Direct empirical AST extraction across 334 questions and 762 misconceptions)

---

## 1. Summary Scorecard

| Chapter Filename | Size (KB) | Score | Status | Questions | Misconceptions | Spoiler Leaks | Rule Breaks | Syntax Errors |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `AlgebraicExpressions_Class8_Gamified_v5_Enhanced_v6.html` | 176.0 | **100/100** | **[PASSED]** | 20 | 58 | **0** | 0 | 0 |
| `ComparingQuantities_Percentage_Class8_Gamified_v5_(1)_Enhanced_v6.html` | 209.3 | **0/100** | [ACTION REQUIRED] | 73 | 164 | **82** | 0 | 0 |
| `Fractions_Gamified_v5_(2)_Enhanced_v6.html` | 6622.8 | **0/100** | [ACTION REQUIRED] | 102 | 215 | **47** | 0 | 0 |
| `Perimeter_Area_Gamified_v5_(2)_Enhanced_v6.html` | 198.4 | **0/100** | [ACTION REQUIRED] | 70 | 168 | **60** | 0 | 0 |
| `Polynomials_Class10_Gamified_v5_(1)_Enhanced_v6.html` | 214.8 | **0/100** | [ACTION REQUIRED] | 69 | 157 | **66** | 0 | 0 |
| `Polynomials_JSXGraph_Inlined_Enhanced_v6.html` | 1049.5 | **46/100** | [ACTION REQUIRED] | 0 | 0 | 0 | 5 | 0 |
| `Polynomials_Offline_Demos_Enhanced_v6.html` | 55.5 | **57/100** | [ACTION REQUIRED] | 0 | 0 | 0 | 4 | 0 |
| **TOTALS** | **8326.3** | - | **1 PASS / 6 FAIL** | **334** | **762** | **255** | **9** | **0** |

---

## 2. Key Empirical Findings

1. **Syntax Integrity (100% Passed)**:
   - All 7 files contain valid HTML wrappers and properly closed `<script>` tags. Zero JavaScript parse crashes occurred during VM sandbox execution.
2. **Offline Strictness (Rule #10, 100% Passed)**:
   - All 7 chapters contain zero external CDN links or network fonts.
3. **Critical Rule #1 Zero-Spoiler Violations (255 Leaks Found)**:
   - While `AlgebraicExpressions` is 100% clean (0 spoilers), the other four core textbook chapters (`ComparingQuantities`, `Fractions`, `Perimeter_Area`, `Polynomials`) systematically leak target numerical solutions inside the `m` (misconception) field.
   - Example from `ComparingQuantities`: `"30/50 x 100 = 60%. You need to multiply by 100."` (Leaks answer `60%`).
   - Example from `Perimeter_Area`: `"You added l+b=9 but forgot to multiply by 2. P = 2×9 = 18."` (Leaks answer `18`).
   - Example from `Fractions`: `"We multiply, not subtract. 20 ÷ 5 = 4, so multiply by 4."` (Leaks multiplier `4`).
4. **Standalone Demos vs Full Chapters**:
   - `Polynomials_JSXGraph` and `Polynomials_Offline_Demos` are interactive visual prototypes, not full v5 quiz chapters; they lack the standard navigation and localStorage reset lifecycle.
