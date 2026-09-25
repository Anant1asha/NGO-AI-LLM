# Task Assignment for Spec Miner (Curriculum & Question Banks)

## Identity
- TypeName: teamwork_preview_spec_miner
- Role: Curriculum & Question Bank Spec Miner
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum
- Parent: teamwork_preview_orchestrator_4

## Objective
Extract and synthesize the complete textbook exercise banks, question items, learning objectives, and misconception schemas for:
1. Class 6 Mathematics: Fractions (Fraction bars, visual partition models, equivalent fractions, 100% textbook exercises).
2. Class 7 Mathematics: Perimeter & Area (2D grid models, decomposition, geometric measurement).
3. Class 8 Mathematics: Rational Numbers & Linear Equations (Balance scale models, algebraic identities, number line density).

## Instructions & Scope
1. Search and inspect files in `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI` and `c:\Users\admin\Downloads\NGO AI LLM\.agents\`:
   - Search for existing chapter contracts (`content/contracts/`), question banks, benchmarks (`benchmarks/qa_ltruth_benchmark.js`), test cases, and schemas (`packages/chapter-contract-manager.ts`, `packages/canonical-ir/`, `packages/aasha-rules/`).
   - Extract real NCERT / standard textbook exercises for these 3 chapters.
2. Structure the questions into the 3-tier gamified assessment model:
   - Warm-up (`#section-warmup`): 3-5 foundational questions.
   - Deep Dive (`#section-deep_dive`): 5-8 conceptual questions.
   - Boss Challenge (`#section-boss`): 3-5 challenging questions with timed/streak dynamics.
3. For EVERY question:
   - Provide question text, 4 options (A, B, C, D), exactly 1 correct answer index or value.
   - For every incorrect option, provide a non-empty misconception diagnostic `m` that explains the thinking error without leaking the answer or intermediate calculations, and without forbidden words (`is`, `becomes`, `yielding`, `result is`, `should be`).
   - Provide 4-tier scaffolding hints (`H1` hook, `H2` concept, `H3` formula, `H4` intermediate step) with zero final answer revelation.
4. Write your full structured inventory into `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\report.md` and `handoff.md`.

## 2026-09-16T20:49:51Z
Curriculum & Question Bank Spec Miner assignment received.
Extract and synthesize complete textbook exercise banks, question items, learning objectives, and misconception schemas for:
1. Class 6 Mathematics: Fractions (Fraction bars, visual partition models, equivalent fractions, 100% textbook exercises).
2. Class 7 Mathematics: Perimeter & Area (2D grid models, decomposition, geometric measurement).
3. Class 8 Mathematics: Rational Numbers & Linear Equations (Balance scale models, algebraic identities, number line density).
Output report: report.md
Output handoff: handoff.md

## 2026-09-16T20:55:48Z
From: parent (283f47a8-950a-4e27-bd0f-8a5ba2bfe0a7)
Context: Phase 0 Spec Mining
Content: Status check on question verification script and final report synthesis.
Action: Please conclude your verification and deliver report.md and handoff.md.
