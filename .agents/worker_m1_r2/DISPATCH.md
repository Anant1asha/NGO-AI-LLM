# DISPATCH: Worker — Milestone 1 Iteration 2 (Remediation & Build)

## Identity
- Role: Remediation & Build Worker
- Working directory: C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1_r2
- Target workspace: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
- Authoritative request: C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md

## Mandatory Remediation Plans to Ingest & Apply
1. Syntax & Integrity Fix: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_fix_syntax_and_integrity_r2\remediation_plan.md
2. Pedagogical Spoilers & Hints Fix: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_fix_spoilers_and_hints_r2\remediation_plan.md
3. Tests & Validator Hardening Fix: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_fix_validator_and_tests_r2\remediation_plan.md

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own and may modify:
- `chapters/square_cube_questions.json`
- `content/contracts/Mathematics_Class8_squares_and_cubes.yaml`
- `packages/aasha-rules/question_schema_validator.ts`
- `benchmarks/question_schema_validator.js`
- `benchmarks/test_square_cube_validator.js`
- `benchmarks/test_square_cube_math_oracle.js`
- `tests/e2e_square_cube_suite.js` (and project root `tests/e2e_square_cube_suite.js`)

## Tasks
1. Apply the line 300 trailing comma fix to `chapters/square_cube_questions.json`.
2. Apply all pedagogical non-spoiler hint and distractor replacements from `explorer_fix_spoilers_and_hints_r2` (`sc_q34` H1, `sc_q31` H3, `sc_q30` H4, `sc_q13`/`sc_q15`/`sc_q21`/`sc_q22`/`sc_q27` H4, `sc_q17` distractor 2).
3. Apply `sc_q28` typo correction in `chapters/square_cube_questions.json` and `benchmarks/test_square_cube_math_oracle.js`.
4. Update `tests/e2e_square_cube_suite.js` to directly load and parse physical `chapters/square_cube_questions.json`.
5. Apply validator hardening to `packages/aasha-rules/question_schema_validator.ts` and `benchmarks/question_schema_validator.js`.
6. Run builds and verification tests locally in `Aasha-AI`:
   - `node benchmarks/test_square_cube_validator.js`
   - `node benchmarks/test_square_cube_math_oracle.js`
   - `node tests/e2e_square_cube_suite.js`
7. Verify all 3 commands exit with code 0 and document output in `handoff.md`.
8. Send a completion message back to parent.

## 2026-09-18T23:29:41Z
<USER_REQUEST>
You are worker_m1_r2. Your working directory is C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1_r2.
Read your dispatch file at C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1_r2\DISPATCH.md, the authoritative request at C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md, and PROJECT.md at C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md.
Also read the remediation plans:
- C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_fix_syntax_and_integrity_r2\remediation_plan.md
- C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_fix_spoilers_and_hints_r2\remediation_plan.md
- C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_fix_validator_and_tests_r2\remediation_plan.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Apply all fixes across chapters/square_cube_questions.json, validator, oracle, and tests/e2e_square_cube_suite.js.
Run the verification test commands:
- node benchmarks/test_square_cube_validator.js
- node benchmarks/test_square_cube_math_oracle.js
- node tests/e2e_square_cube_suite.js
Write your handoff report to C:\Users\admin\Downloads\NGO AI LLM\.agents\worker_m1_r2\handoff.md with full execution output and send a completion message back to parent.
</USER_REQUEST>
