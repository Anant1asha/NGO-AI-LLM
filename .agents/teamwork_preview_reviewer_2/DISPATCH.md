# Task Assignment for Reviewer 2 (Pedagogy & Schema Reviewer)

## Identity
- TypeName: teamwork_preview_reviewer
- Role: Delta Route Pedagogy & Schema Reviewer
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_reviewer_2
- Parent: teamwork_preview_orchestrator_4

## Objective
Independently review the pedagogical structure, item bank quality, and schema compliance of the deployed `api/chapters/deltas.js` on `proj_wDCbCrGwuVqy`.

## Reference Inputs
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- Spec Miner Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\report.md
- Mechanics Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_mechanics\report.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md

## Verification Tasks
1. Verify question bank inventory:
   - 43 genuine textbook questions total (Class 6: 14 items, Class 7: 14 items, Class 8: 15 items).
   - 3-tier gamified assessment mapping: Warm-up (`#section-warmup`), Deep Dive (`#section-deep_dive`), Boss Challenge (`#section-boss`).
2. Verify Foundation F01 (Escape Run) Boss Challenge mechanics:
   - 25s obstacle evasion timer, streak multipliers (1.0x, 1.5x, 2.0x), 3 hearts, non-punitive "Cognitive Shield Overload" remediation.
3. Verify Visual Manipulatives & Bilingual Vocabulary:
   - SVG specifications for Fraction bars, 2D grids, balance scales.
   - Devanagari phonics & Hindi definitions (`window.WM` / `rt()`).
4. Verify Anti-Spoiler & Schema Invariant:
   - Exactly 4 options per question, exactly 1 correct answer (`c: true`).
   - Non-empty misconception diagnostics (`m`) > 15 chars for all distractors.
   - Zero occurrences of forbidden leak words (`/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`).
   - Zero calculation leaks producing target answer.
   - Complete 4-tier progressive scaffolding hints (`H1`-`H4`) for every question.
5. Provide a clear verdict: `APPROVE` or `REQUEST_CHANGES`.
6. Write your report to `report.md` and `handoff.md` in your working directory.

## 2026-09-17T02:41:45Z
You are Reviewer 2 (Delta Route Pedagogy & Schema Reviewer).
Your working directory is: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_reviewer_2

Read the authoritative request and task assignment first:
- ORIGINAL_REQUEST: c:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md
- DISPATCH: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_reviewer_2\DISPATCH.md
- Spec Miner Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\report.md
- Mechanics Report: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_mechanics\report.md
- Worker Handoff: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_worker_1\handoff.md

Your Mission:
1. Verify question bank inventory on live Hatchable `proj_wDCbCrGwuVqy`:
   - 43 genuine textbook questions total (Class 6: 14 items, Class 7: 14 items, Class 8: 15 items).
   - 3-tier gamified assessment mapping: Warm-up (`#section-warmup`), Deep Dive (`#section-deep_dive`), Boss Challenge (`#section-boss`).
2. Verify Foundation F01 (Escape Run) Boss Challenge mechanics:
   - 25s obstacle evasion timer, streak multipliers (1.0x, 1.5x, 2.0x), 3 hearts, non-punitive "Cognitive Shield Overload" remediation.
3. Verify Visual Manipulatives & Bilingual Vocabulary:
   - SVG specifications for Fraction bars, 2D grids, balance scales.
   - Devanagari phonics & Hindi definitions (`window.WM` / `rt()`).
4. Verify Anti-Spoiler & Schema Invariant:
   - Exactly 4 options per question, exactly 1 correct answer (`c: true`).
   - Non-empty misconception diagnostics (`m`) > 15 chars for all distractors.
   - Zero occurrences of forbidden leak words (`/\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i`).
   - Zero calculation leaks producing target answer.
   - Complete 4-tier progressive scaffolding hints (`H1`-`H4`) for every question.
5. Provide a clear verdict: APPROVE or REQUEST_CHANGES.
Write report to: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_reviewer_2\report.md
and handoff summary to: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_reviewer_2\handoff.md
Send completion message when finished.
