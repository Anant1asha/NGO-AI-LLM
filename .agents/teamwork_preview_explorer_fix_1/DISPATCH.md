# Task Assignment for Explorer Fix 1 (Parameter & Sync Remediation)

## Identity
- TypeName: teamwork_preview_explorer
- Role: Parameter & Sync Remediation Investigator
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_fix_1
- Parent: teamwork_preview_orchestrator_4

## Objective
Analyze the exact query parameter parsing issue identified by Challenger 2 in `api/chapters/deltas.js` on Hatchable isolate `proj_wDCbCrGwuVqy`.
Challenger 2 found that when clients query `?chapter=c6_fractions&v=3` or `?grade=6&v=3`, the endpoint ignores `v` (only checking `version`), causing cache misses and transmitting the entire ~40 KB question bank instead of the 100-byte `{ upToDate: true }` packet.

## Instructions
1. Inspect `api/chapters/deltas.js` lines 1070–1150 via Hatchable MCP `read_file`.
2. Propose the precise patch:
   - Support both `version` and `v` aliases (`const requestedVer = version || v; const clientVer = parseInt(requestedVer, 10);`).
   - Ensure both chapter-level and grade-level queries evaluate `v` identically to `version`.
3. Document your recommendation in `report.md` and `handoff.md`.

## 2026-09-16T21:18:52Z
You are Explorer Fix 1 (Parameter & Sync Remediation Investigator).
Your working directory is: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_fix_1

Read the authoritative request and task assignment first:
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- DISPATCH: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_fix_1\DISPATCH.md
- Challenger 2 Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_challenger_2\handoff.md

Your Mission:
Inspect `api/chapters/deltas.js` on `proj_wDCbCrGwuVqy` via Hatchable MCP `read_file`.
Formulate the exact patch to support both `version` and `v` query aliases (`v=3` and `version=3`), ensuring client cache synchronization returns `{ upToDate: true }` (<150 bytes) rather than transmitting the full 40 KB question bank.
Write report to `report.md` and handoff summary to `handoff.md`.
Send a completion message when finished.
