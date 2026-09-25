# Task Assignment for Explorer Fix 2 (Error Schema Remediation)

## Identity
- TypeName: teamwork_preview_explorer
- Role: Error Schema Remediation Investigator
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_fix_2
- Parent: teamwork_preview_orchestrator_4

## Objective
Analyze the error payload schema issue identified by Challenger 2 in `api/chapters/deltas.js` on Hatchable isolate `proj_wDCbCrGwuVqy`.
Challenger 2 found that error responses emit `error` but lack the structured `code` property (e.g. `code: "CHAPTER_NOT_FOUND"`, `code: "GRADE_NOT_FOUND"`, `code: "METHOD_NOT_ALLOWED"`).

## Instructions
1. Inspect `api/chapters/deltas.js` lines 1070–1150 via Hatchable MCP `read_file`.
2. Propose the precise patch:
   - Ensure 404 for missing chapter returns `{ error: "chapter_not_found", code: "CHAPTER_NOT_FOUND", ... }`.
   - Ensure 404 for missing grade returns `{ error: "grade_not_found", code: "GRADE_NOT_FOUND", ... }`.
3. Document your recommendation in `report.md` and `handoff.md`.
