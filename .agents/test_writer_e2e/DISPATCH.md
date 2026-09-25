# DISPATCH: E2E Test Writer — Test Suite Infrastructure & Design

## Identity
- Role: E2E Test Suite Designer & Writer
- Working directory: C:\Users\admin\Downloads\NGO AI LLM\.agents\test_writer_e2e
- Target workspace: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
- Authoritative request: C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md

## Reference Reports
- PDF Textbook Survey: C:\Users\admin\Downloads\NGO AI LLM\.agents\spec_miner_survey_1\survey_report.md
- Pipeline & Benchmark Survey: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\survey_report.md
- Foundation & Simulation Survey: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_sims_1\survey_report.md

## Write Ownership
You exclusively own and may modify:
- `C:\Users\admin\Downloads\NGO AI LLM\TEST_INFRA.md`
- `C:\Users\admin\Downloads\NGO AI LLM\TEST_READY.md`
- `tests/e2e_square_cube_suite.js` (or `benchmarks/e2e_square_cube_suite.js`)

## Objective & Tasks
1. Create `C:\Users\admin\Downloads\NGO AI LLM\TEST_INFRA.md` following the template in the Project Orchestrator guidelines:
   - Test Philosophy: Requirement-driven, opaque-box testing derived from `ORIGINAL_REQUEST.md` and `PROJECT.md § Feature Inventory`.
   - 4-Tier Test Case Design:
     - Tier 1: Feature Coverage (>=5 per feature)
     - Tier 2: Boundary & Corner Cases (>=5 per feature)
     - Tier 3: Cross-Feature Combinations (pairwise interactions)
     - Tier 4: Real-World Application Scenarios (Queen Ratnamanjuri vault puzzle, 100-locker parity riddle, Page 18 square pairs row & circle)
2. Implement executable test runner script `tests/e2e_square_cube_suite.js` (or `benchmarks/e2e_square_cube_suite.js`) that verifies:
   - File existence and self-containment (< 20 MB ceiling, zero CDN URLs).
   - Question schema compliance: 100% of the 34 textbook questions present, 4 options each, non-empty `m` (> 11 chars), 0 spoiler phrases, 4-tier progressive hints.
   - Pre-LLE math insulation: zero math-rt collisions, variables shielded.
   - `<aasha-sim>` Web Component integration: existence of custom elements, custom events `aasha:telemetry` and `aasha:state_change`.
   - Same-frame mobile responsiveness CSS clamping and opaque bottom navigation rules.
3. Verify that running the test runner produces clean structured output and publishes `C:\Users\admin\Downloads\NGO AI LLM\TEST_READY.md`.
4. Write your handoff report to `C:\Users\admin\Downloads\NGO AI LLM\.agents\test_writer_e2e\handoff.md` and send a message back to parent when done.

## 2026-09-18T23:04:23Z
You are test_writer_e2e. Your working directory is C:\Users\admin\Downloads\NGO AI LLM\.agents\test_writer_e2e.
Read your dispatch file at C:\Users\admin\Downloads\NGO AI LLM\.agents\test_writer_e2e\DISPATCH.md, the authoritative request at C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md, and PROJECT.md at C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md.
Also read the survey reports in .agents/spec_miner_survey_1/survey_report.md and .agents/explorer_survey_pipeline_1/survey_report.md.

Execute E2E Testing Track:
1. Create C:\Users\admin\Downloads\NGO AI LLM\TEST_INFRA.md following the Project Pattern template with 4-tier methodology (Tiers 1-4).
2. Implement executable test suite in tests/e2e_square_cube_suite.js verifying chapter self-containment, 34 questions completeness, zero spoilers, math insulation, <aasha-sim> contracts, and mobile layout.
3. Run the test suite, verify its pass/fail semantics, and publish C:\Users\admin\Downloads\NGO AI LLM\TEST_READY.md.
4. Write your handoff report to C:\Users\admin\Downloads\NGO AI LLM\.agents\test_writer_e2e\handoff.md and send a completion message back to parent.

