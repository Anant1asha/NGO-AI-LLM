# Task Assignment for Worker 1 (Delta Route Developer & Deployer)

## Identity
- TypeName: teamwork_preview_worker
- Role: Delta Route Developer & Hatchable Deployer
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1
- Parent: teamwork_preview_orchestrator_4

## File Ownership
- Exclusively owns `api/chapters/deltas.js` on Hatchable isolate `proj_wDCbCrGwuVqy`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Objective
Assemble the complete, production-grade `api/chapters/deltas.js` combining all 43 textbook items, F01 Escape Run mechanics, SVG manipulative specifications, and bilingual Hindi vocabulary; deploy it to Hatchable isolate `proj_wDCbCrGwuVqy`; and verify live execution.

## Reference Inputs
1. `c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md`
2. `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_hatchable\report.md` (runtime rules, export contracts, template)
3. `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\report.md` (43 verified textbook items, zero-spoiler diagnostics, 4-tier hints)
4. `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_mechanics\report.md` (F01 mechanics, SVG manipulatives, bilingual dictionary, <50 KB compact structure)

## Steps
1. Assemble `api/chapters/deltas.js` with ES module syntax, `export const access = "public"`, `export const methods = ["GET"]`, and `export default async function(req, res)`.
2. Write file to `proj_wDCbCrGwuVqy` using Hatchable MCP tool `write_file` or `write_files`.
3. Run `dry_run_deploy` on `proj_wDCbCrGwuVqy` to confirm zero syntax or bundling errors.
4. Run `deploy` on `proj_wDCbCrGwuVqy` to publish the new version.
5. Verify live execution via `run_function` across query parameters (`?grade=6`, `?grade=7`, `?grade=8`, unparameterized index, version caching).
6. Verify payload sizes (<50 KB per grade).
7. Document commands, results, and full verification in `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\report.md` and `handoff.md`.

## 2026-09-16T21:00:32Z - Invocation Prompt
You are Worker 1 (Delta Route Developer & Hatchable Deployer).
Your working directory is: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1
File Ownership: You exclusively own `api/chapters/deltas.js` on Hatchable isolate project `proj_wDCbCrGwuVqy`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read these authoritative input documents before beginning:
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- DISPATCH: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\DISPATCH.md
- Hatchable Explorer Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_hatchable\report.md
- Spec Miner Report (43 verified questions): c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\report.md
- Mechanics & Language Report (F01, SVGs, LLE vocab, schema): c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_mechanics\report.md

Your Mission:
1. Implement the complete, production-grade `api/chapters/deltas.js` for project `proj_wDCbCrGwuVqy`:
   - Declare `export const access = "public"`.
   - Declare `export const methods = ["GET"]`.
   - Default async handler: `export default async function (req, res)`.
   - Support query routing:
     - `?grade=6` returns Class 6 Fractions delta.
     - `?grade=7` returns Class 7 Perimeter & Area delta.
     - `?grade=8` returns Class 8 Rational Numbers & Linear Equations delta.
     - `?chapter=ID` returns specific chapter delta (`c6_fractions`, `c7_perimeter_area`, `c8_rational_linear`).
     - `?version=V` caching support (returns `{ upToDate: true }` if client already has current version).
     - No query parameters: returns index listing available chapter deltas and summary metadata.
   - Embed all 43 genuine textbook questions synthesized by Spec Miner across Class 6, 7, and 8.
   - Enforce 3-tier gamified mapping: Warm-up (`#section-warmup`), Deep Dive (`#section-deep_dive`), and Boss Challenge (`#section-boss`).
   - For Boss Challenge, embed Foundation F01 (Escape Run) parameters (25s obstacle evasion timer, streak multiplier 1.0x/1.5x/2.0x, 3 hearts).
   - Embed SVG visual manipulative specifications (fraction bars, 2D grids, balance scales) and bilingual Hindi vocabulary mapping (`window.WM` / `rt()`) hoisted at chapter level for compactness.
   - Ensure every distractor explanation has NO forbidden words (`is`, `giving`, `becomes`, `instead of`, `to get`, `yielding`, `result is`, `should be`), NO answer leaks, and full 4-tier scaffolding hints (`H1`-`H4`).
2. Use Hatchable MCP tools (`call_mcp_tool` on server "hatchable"):
   - Stage the code using `write_file` or `write_files` to `api/chapters/deltas.js` on `proj_wDCbCrGwuVqy`.
   - Execute `dry_run_deploy` on `proj_wDCbCrGwuVqy` to verify zero bundling or syntax errors.
   - Execute `deploy` on `proj_wDCbCrGwuVqy` to publish the updated version.
3. Test live execution using `run_function` on `proj_wDCbCrGwuVqy` for:
   - `?grade=6`
   - `?grade=7`
   - `?grade=8`
   - unparameterized call
   - version check
4. Measure and document payload sizes to verify <50 KB per grade.
5. Write your complete report and verification results to:
   c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\report.md
   and handoff summary to:
   c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md
   Send a completion message back when finished.
