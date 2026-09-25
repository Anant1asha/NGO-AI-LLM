# 09_BUG.md
# Active & Resolved Bug Tracking Records

A code change does NOT equal a fixed bug. A bug is only marked RESOLVED when verified by test output.

---

### BUG: BUG-003 Systematic Rule #1 Zero-Spoiler Violations in 4 Generated Chapters
- **BUG ID**: BUG-003
- **SEVERITY**: CRITICAL (Violates Core Pedagogical Rule #1)
- **STATUS**: IN_PROGRESS
- **DATE**: 2026-09-08
- **ENVIRONMENT**: Standalone HTML Chapters (`ComparingQuantities`, `Fractions`, `Perimeter_Area`, `Polynomials`)
- **REPRODUCTION**: Run `node benchmarks/run_ltruth_7_chapters.js`.
- **EXPECTED**: 0 spoiler violations across all assessment distractors (`m` field must explain the misconception without stating the correct numerical answer or phrase).
- **ACTUAL**: 255 spoiler violations detected across 4 chapters:
  - `ComparingQuantities`: 82 violations
  - `Polynomials_Class10`: 66 violations
  - `Perimeter_Area`: 60 violations
  - `Fractions`: 47 violations
- **EVIDENCE**: Detailed AST inspection report in `Aasha-AI/benchmarks/ltruth_7_chapters_report.json` and `docs/aios/evidence/EVID-002_ltruth_7_chapters_benchmark.md`.
- **EXAMPLES**:
  - `ComparingQuantities`: `"30/50 x 100 = 60%. You need to multiply by 100."` (Target answer: 60%)
  - `Perimeter_Area`: `"You added l+b=9 but forgot to multiply by 2. P = 2×9 = 18."` (Target answer: 18)
  - `Fractions`: `"We multiply, not subtract. 20 ÷ 5 = 4, so multiply by 4."` (Target answer: 4)
  - `Polynomials`: `"Sum = -b/a = -(-8)/1 = 8. The negative of b is positive here since b = -8."` (Target answer: 8)
- **ROOT CAUSE**: LLM prompt during assessment authoring (`AssessmentAgent`) instructed the model to "explain why the answer is wrong and show the calculation," which caused the model to write out the full worked solution into distractor `m` fields.
- **FILES**:
  - `Aasha-AI/chapters/ComparingQuantities_Percentage_Class8_Gamified_v5_(1)_Enhanced_v6.html`
  - `Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html`
  - `Aasha-AI/chapters/Perimeter_Area_Gamified_v5_(2)_Enhanced_v6.html`
  - `Aasha-AI/chapters/Polynomials_Class10_Gamified_v5_(1)_Enhanced_v6.html`
  - `aasha-pipeline-with-master-json/src/assessment.py`
- **FIX (PROPOSED)**:
  1. Update `AssessmentAgent` system prompt to strictly enforce the Socratic error-diagnosis pattern established in `AlgebraicExpressions` (which achieved 100/100 zero-spoiler compliance).
  2. Implement an automated post-generation regex filter rejecting any `m` string containing the target correct answer.
- **REGRESSION RISK**: Low (text-only change in JSON/HTML data strings).
- **TESTS**: `node benchmarks/run_ltruth_7_chapters.js` must report 0 spoiler violations.
- **VERIFICATION**: PENDING.

---

### BUG: BUG-001 Standalone Fractions Chapter File Size Bloat
- **BUG ID**: BUG-001
- **SEVERITY**: HIGH (Performance / Out-of-Memory Risk on Low-End Mobile)
- **STATUS**: IN_PROGRESS
- **DATE**: 2026-09-08
- **ENVIRONMENT**: Standalone HTML Chapter / Android WebView
- **REPRODUCTION**: Inspect file size of `chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html`.
- **EXPECTED**: Standalone file size should be `<= 1,000,000 bytes` (target `< 200,000 bytes`).
- **ACTUAL**: File size is `6,781,761 bytes` (~6.78 MB).
- **EVIDENCE**: Directory listing of `Aasha-AI/chapters/` indicates 6,781,761 bytes on disk.
- **SUSPECTED CAUSE**: High-resolution bitmap images embedded as Base64 Data URIs inside HTML steps instead of lightweight procedural SVGs.
- **ROOT CAUSE**: Ingestion pipeline extracted uncompressed page scan illustrations and inlined full-resolution PNG data strings into the `{{CONTENT}}` step definitions.
- **FILES**:
  - `Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html`
  - `aasha-pipeline-with-master-json/src/ingest.py`
  - `aasha-pipeline-with-master-json/src/compiler.py`
- **FIX (PROPOSED)**: Replace raster fraction illustrations with interactive mathematical SVG fraction bars.
- **REGRESSION RISK**: Visual rendering differences if SVG generator lacks specific textbook artwork.
- **TESTS**: Check file size `< 500 KB`.
- **VERIFICATION**: PENDING.

---

### BUG: BUG-002 [HISTORICAL / RESOLVED] Duplicate Reward Event Generation on Question Replay
- **BUG ID**: BUG-002
- **SEVERITY**: MEDIUM
- **STATUS**: VERIFIED_RESOLVED
- **DATE**: 2026-09-05
- **ENVIRONMENT**: Learner Web / Assessment Engine
- **REPRODUCTION**: Complete a diagnostic question, navigate back, and re-answer the same question.
- **EXPECTED**: Reward ledger should be strictly idempotent; student earns coins/XP only once per unique challenge.
- **ACTUAL**: Re-answering previously completed questions generated redundant reward ledger entries, inflating scores.
- **EVIDENCE**: Unit test `ISS-03: Deterministic reward event ID prevents duplicate coins on replay` passed.
- **ROOT CAUSE**: Reward event IDs were generated with non-deterministic timestamps (`Date.now()`) rather than deterministic hashes.
- **FILES**:
  - `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/packages/assessment-engine/`
  - `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/tests/unit/learner.test.js`
- **FIX**: Changed event generation to derive deterministic UUIDv5 using question identity hashes.
- **TESTS**: `node --test tests/unit/learner.test.js` test 16 passed in 0.6ms.
- **VERIFICATION**: Verified in test run at 2026-09-08 04:12:03.
