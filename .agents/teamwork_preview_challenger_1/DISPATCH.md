# Task Assignment for Challenger 1 (Empirical Challenger)

## Identity
- TypeName: teamwork_preview_challenger
- Role: Delta Route Empirical Challenger
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_1
- Parent: teamwork_preview_orchestrator_4

## Objective
Empirically test and stress the live delta endpoint on Hatchable `proj_wDCbCrGwuVqy` using Hatchable MCP tools (`run_function`).

## Reference Inputs
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md

## Verification Tasks
1. Execute live test harness against `proj_wDCbCrGwuVqy`:
   - Call `run_function` with varied combinations of parameters:
     - Root manifest: `/api/chapters/deltas`
     - All grades: `grade=6`, `grade=7`, `grade=8`
     - Valid and invalid chapter IDs
     - Version combinations: `version=1`, `version=2`, `version=3`, `version=4`, `version=abc`
     - Edge cases: non-existent grades (`grade=0`, `grade=-1`, `grade=99`), non-GET methods (POST, PUT, DELETE) to verify 405 or handling
2. Measure response latencies and payload sizes (ensure all <50 KB).
3. Validate JSON structure of responses:
   - Ensure all returned items have valid types, options arrays of length 4, hints object with h1, h2, h3, h4.
4. Provide a clear verdict: `APPROVE` or `REJECT`.
5. Write your report to `report.md` and `handoff.md` in your working directory.

## 2026-09-16T21:16:49Z
- Sender: 283f47a8-950a-4e27-bd0f-8a5ba2bfe0a7 (parent)
- Context: Empirical Testing of Hatchable Delta Route
- Content: Status check on live test suite execution.
- Action: Please complete your test execution and deliver report.md and handoff.md.
