# DISPATCH: Explorer — Pipeline & Tooling Survey

## Identity
- Role: Codebase Investigator / Pipeline Explorer
- Working directory: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1
- Target workspace: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
- Authoritative request: C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md

## Objective
Investigate the existing AASHA chapter generation pipeline, tooling, contracts, math insulation, and verification benchmarks to establish the exact commands and code paths needed for the new Square and Cube chapter.

## Tasks
1. Investigate `packages/chapter-contract-manager.ts`, `packages/aasha-rules/`, `package.json` scripts (e.g., `npm run chapter:init`, `npm run admin:match`).
2. Examine `content/contracts/` to see how Section 24 YAML contracts are formatted (e.g. `Mathematics_Class8_rational_numbers.yaml` or others).
3. Inspect `benchmarks/qa_ltruth_benchmark.js` and `benchmarks/question_schema_validator.js` to identify exact schema and spoiler rules that the new chapter must pass.
4. Inspect `benchmarks/automated_browser_verification.js` and the CDP automation harness to see how viewport checks, word dialog tests, and navigation are executed.
5. Inspect reference chapters (such as `chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` or `chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html`) for structure: header, `<style>`, KaTeX/math handling, dictionary `window.WM`, `<aasha-sim>`, gamified sections (`#section-warmup`, `#section-deep_dive`, `#section-boss`), word dialog `#wordDialog`.
6. Output a detailed report to:
   `C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\survey_report.md`
   and write a `handoff.md` summarizing key findings.
7. Send a completion message back to parent when done.

## 2026-09-18T22:53:25Z
You are explorer_survey_pipeline_1. Your working directory is C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1.
Read your dispatch file at C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\DISPATCH.md and the authoritative request at C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md.
Investigate the AASHA chapter generation pipeline in C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI:
packages/chapter-contract-manager.ts, packages/aasha-rules/, package.json scripts (e.g., npm run chapter:init), content/contracts/, benchmarks/qa_ltruth_benchmark.js, benchmarks/automated_browser_verification.js, and reference chapters.
Write your detailed report to C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\survey_report.md and your summary to C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_pipeline_1\handoff.md.
When finished, send a message back to parent with your summary and file paths.
