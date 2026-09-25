# Task Assignment for Forensic Auditor (Integrity Forensics)

## Identity
- TypeName: teamwork_preview_auditor
- Role: Forensic Integrity Auditor
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_auditor_1
- Parent: teamwork_preview_orchestrator_4

## Objective
Conduct an exhaustive forensic integrity audit of the Delta Route deployment on Hatchable `proj_wDCbCrGwuVqy` (`api/chapters/deltas.js`) and its local artifacts.
Verify authentic implementation vs cheating, fake mock data, or hardcoded shortcuts.

## Reference Inputs
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md
- Worker Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\report.md

## Audit Scope & Verification Checks
1. **Source Code Authenticity Check**:
   - Inspect `api/chapters/deltas.js` directly on `proj_wDCbCrGwuVqy` via Hatchable MCP `read_file`.
   - Verify that all 43 questions are genuinely authored and contained in code, not dummy stubs or hollow mocks.
   - Verify that questions contain genuine mathematics for Class 6 (Fractions), Class 7 (Perimeter & Area), and Class 8 (Rational Numbers & Linear Equations).
2. **Anti-Spoiler / L-Truth Integrity Check**:
   - Run automated regex scan on all distractor explanations `m`:
     `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`.
   - Verify that there are ZERO occurrences of these forbidden leak words.
   - Verify that no distractor explanation performs arithmetic calculations that evaluate to the correct answer.
   - Verify that all distractors have substantive explanations (`m.length >= 15`).
   - Verify that each question has exactly 4 options and exactly 1 correct answer (`c: true`).
   - Verify that all 4-tier scaffolding hints (`H1`-`H4`) are present with zero final answer disclosures.
3. **Live Isolate Verification**:
   - Execute `run_function` calls against `proj_wDCbCrGwuVqy` to confirm that the live endpoint runs this genuine code and returns the verified questions, F01 mechanics, SVG schemas, and LLE vocabulary.
4. **No-Cheating & Forensic Integrity Verdict**:
   - Issue a binary verdict: `CLEAN` or `INTEGRITY VIOLATION`.
   - Write your complete audit evidence to `report.md` and `handoff.md` in your working directory.

## 2026-09-16T21:11:47Z
You are Auditor 1 (Forensic Integrity Auditor).
Your working directory is: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_auditor_1

Read the authoritative request and task assignment first:
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- DISPATCH: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_auditor_1\DISPATCH.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md
- Worker Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\report.md

Your Mission:
Conduct an exhaustive forensic integrity audit of the Delta Route deployment on Hatchable `proj_wDCbCrGwuVqy` (`api/chapters/deltas.js`) and its local artifacts.
Verify authentic implementation vs cheating, fake mock data, or hardcoded shortcuts:
1. Source Code Authenticity Check:
   - Inspect `api/chapters/deltas.js` directly on `proj_wDCbCrGwuVqy` via Hatchable MCP `read_file`.
   - Verify that all 43 questions are genuinely authored and contained in code, not dummy stubs or hollow mocks.
   - Verify that questions contain genuine mathematics for Class 6 (Fractions), Class 7 (Perimeter & Area), and Class 8 (Rational Numbers & Linear Equations).
2. Anti-Spoiler / L-Truth Integrity Check:
   - Run automated regex scan on all distractor explanations `m`:
     `/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`.
   - Verify that there are ZERO occurrences of these forbidden leak words.
   - Verify that no distractor explanation performs arithmetic calculations that evaluate to the correct answer.
   - Verify that all distractors have substantive explanations (`m.length >= 15`).
   - Verify that each question has exactly 4 options and exactly 1 correct answer (`c: true`).
   - Verify that all 4-tier scaffolding hints (`H1`-`H4`) are present with zero final answer disclosures.
3. Live Isolate Verification:
   - Execute `run_function` calls against `proj_wDCbCrGwuVqy` to confirm that the live endpoint runs this genuine code and returns the verified questions, F01 mechanics, SVG schemas, and LLE vocabulary.
4. Issue a binary verdict: CLEAN or INTEGRITY VIOLATION.
Write full audit evidence to: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_auditor_1\report.md
and handoff summary to: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_auditor_1\handoff.md
Send completion message when finished.
