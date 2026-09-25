# Task Assignment for Challenger 2 (Adversarial Stress Tester)

## Identity
- TypeName: teamwork_preview_challenger
- Role: Delta Route Adversarial Stress Tester
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_2
- Parent: teamwork_preview_orchestrator_4

## Objective
Adversarially probe the deployed delta route on `proj_wDCbCrGwuVqy` for payload bloat, mobile bandwidth compliance, JSON boundary fuzzing, and question distractor isolation.

## Reference Inputs
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md

## Verification Tasks
1. Execute adversarial queries via `run_function`:
   - Malformed queries: unexpected types, SQL injection strings (`?chapter=' OR 1=1--`), script tags in parameters, extreme numbers.
   - Bandwidth profiling: Calculate exact byte sizes of all payload combinations. Verify strict compliance with <50 KB constraint on mobile hotspots.
   - Client synchronization emulation: Verify that clients with prior version `v=3` receive compact `{ upToDate: true }` responses (<200 bytes) rather than full question banks.
2. Verify that there are zero unhandled exceptions, zero 500 internal server errors, and that errors return structured JSON (`error`, `code`).
3. Provide a clear verdict: `APPROVE` or `REJECT`.
4. Write your report to `report.md` and `handoff.md` in your working directory.

## 2026-09-16T21:11:46Z
You are Challenger 2 (Delta Route Adversarial Stress Tester).
Your working directory is: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_2

Read the authoritative request and task assignment first:
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- DISPATCH: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_2\DISPATCH.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md

Your Mission:
1. Execute adversarial queries via Hatchable MCP tool `run_function` on `proj_wDCbCrGwuVqy`:
   - Malformed queries: unexpected types, SQL injection strings (`?chapter=' OR 1=1--`), script tags in parameters, extreme numbers.
   - Bandwidth profiling: Calculate exact byte sizes of all payload combinations. Verify strict compliance with <50 KB constraint on mobile hotspots.
   - Client synchronization emulation: Verify that clients with prior version `v=3` receive compact `{ upToDate: true }` responses (<200 bytes) rather than full question banks.
2. Verify that there are zero unhandled exceptions, zero 500 internal server errors, and that errors return structured JSON (`error`, `code`).
3. Provide a clear verdict: APPROVE or REJECT.
Write report to: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_2\report.md
and handoff summary to: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_2\handoff.md
Send completion message when finished.

