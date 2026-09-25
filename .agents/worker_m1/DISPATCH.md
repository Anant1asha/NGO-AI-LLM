# DISPATCH: Worker — Milestone 1 (Content Contract & Textbook Ingestion)

## Identity
- Role: Implementation Worker
- Working directory: C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1
- Target workspace: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
- Authoritative request: C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md

## Reference Reports
- PDF Textbook Survey: C:\Users\admin\Downloads\NGO AI LLM\.agents\spec_miner_survey_1\survey_report.md
- Pipeline & Benchmark Survey: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\survey_report.md
- Foundation & Simulation Survey: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_sims_1\survey_report.md

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own and may modify:
- `content/contracts/Mathematics_Class8_squares_and_cubes.yaml`
- `chapters/square_cube_questions.json`

## Objective & Tasks
1. Execute `npm run chapter:init -- Mathematics 8 "Squares and Cubes"` in `C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI` to initialize the contract node and directory.
2. Synthesize `content/contracts/Mathematics_Class8_squares_and_cubes.yaml` adhering strictly to Section 24 YAML contract schema:
   - Topic: Squares and Cubes, Subject: Mathematics, Class: 8
   - Prebuilt Foundations: F01 (Escape Run), F02 (MicroSims), F04 (PhET), F08 (Physics Notebook)
   - Pedagogical sequence: WHAT -> WHY -> HOW -> SHOW -> TRY -> FEEDBACK -> CONNECT -> NAME
   - 100% textbook exercises from `survey_report.md` (all 34 items).
   - Pre-embedded misconception diagnostics (`m` attribute) with zero spoilers (no leak predicates: 'is', 'was', '=', 'becomes', 'result is', 'yielding', 'should be', 'to get').
   - 4-tier hints ($H_1 \to H_4$) with zero spoilers.
   - LaTeX mathematical expressions insulated with `__AASHA_MATH_X__`.
3. Create `chapters/square_cube_questions.json` containing the structured JSON array of all 34 questions partitioned into:
   - Tier 1 (Warm-up): 12 items
   - Tier 2 (Deep Dive): 14 items
   - Tier 3 (Boss Challenge): 8 items
4. Run validation on the generated contract and question bank using `QuestionSchemaValidator`:
   Verify that all 34 questions pass with 0 errors, 0 spoilers, and valid schema.
5. Write your handoff report to `C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1\handoff.md` detailing all files created, verification commands executed, and verification output.
6. Send a message back to parent when done.

## 2026-09-18T23:04:23Z
You are worker_m1. Your working directory is C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1.
Read your dispatch file at C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1\DISPATCH.md, the authoritative request at C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md, and PROJECT.md at C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md.
Also read the survey reports:
- C:\Users\admin\Downloads\NGO AI LLM\.agents\spec_miner_survey_1\survey_report.md
- C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\survey_report.md
- C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_sims_1\survey_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Execute Milestone 1:
1. Run npm run chapter:init -- Mathematics 8 "Squares and Cubes" in C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI.
2. Create and validate content/contracts/Mathematics_Class8_squares_and_cubes.yaml with Section 24 contract, all 34 textbook questions, non-empty m diagnostics (zero spoilers), 4-tier hints, math insulation.
3. Create chapters/square_cube_questions.json with the 34 validated questions (12 Warm-up, 14 Deep Dive, 8 Boss).
4. Run validation using QuestionSchemaValidator.
5. Write your handoff report to C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1\handoff.md and send a completion message back to parent.
