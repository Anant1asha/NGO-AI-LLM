## 2026-09-16T21:11:45Z

# Task Assignment for Reviewer 1 (Code & Architectural Reviewer)

## Identity
- TypeName: teamwork_preview_reviewer
- Role: Delta Route Code & Architectural Reviewer
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_reviewer_1
- Parent: teamwork_preview_orchestrator_4

## Objective
Independently review the newly deployed `api/chapters/deltas.js` on live Hatchable isolate `proj_wDCbCrGwuVqy` (`aasha` v7).
Examine code architecture, runtime safety, HTTP protocol conformance, error handling, query routing, payload size, and caching semantics.

## Reference Inputs
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md
- Worker Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\report.md

## Verification Tasks
1. Read `api/chapters/deltas.js` on `proj_wDCbCrGwuVqy` using Hatchable MCP `read_file`.
2. Inspect exports: `export const access = "public"`, `export const methods = ["GET"]`, `export default async function (req, res)`.
3. Test live execution using Hatchable MCP `run_function` across query routes:
   - Root index / manifest: `/api/chapters/deltas`
   - Class 6: `/api/chapters/deltas?grade=6`
   - Class 7: `/api/chapters/deltas?grade=7`
   - Class 8: `/api/chapters/deltas?grade=8`
   - Chapter IDs and aliases: `?chapter=c6_fractions`, `?chapter=math8-rational-numbers`
   - Version caching: `?chapter=c6_fractions&version=3` -> should return `{ upToDate: true }`
   - Error cases: invalid grade (`?grade=99`), invalid chapter (`?chapter=unknown`)
4. Verify response payloads are <50 KB per grade.
5. Provide a clear verdict: `APPROVE` or `REQUEST_CHANGES`.
6. Write your report to `report.md` and `handoff.md` in your working directory.
