# BRIEFING — 2026-09-16T20:51:00Z

## Mission
Extract and synthesize complete textbook exercise banks, question items, learning objectives, visual manipulative bindings, and misconception schemas for Class 6 Fractions, Class 7 Perimeter & Area, and Class 8 Rational Numbers & Linear Equations under the AASHA L-Truth zero-spoiler framework.

## 🔒 My Identity
- Archetype: teamwork_preview_spec_miner
- Roles: Curriculum & Question Bank Spec Miner
- Working directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum
- Original parent: 283f47a8-950a-4e27-bd0f-8a5ba2bfe0a7
- Milestone: M1_Curriculum_Spec_Mining

## 🔒 Key Constraints
- Anti-Spoiler Assessment Invariant: No forbidden words (is, giving, becomes, instead of, to get, yielding, result is, should be) in `m` attribute
- No intermediate calculations or answer leaks in `m`
- Non-empty verbal misconception diagnostic `m` > 15 chars for every distractor
- 4 options, exactly 1 correct answer per question
- 4-tier scaffolding hints (H1 Hook, H2 Concept, H3 Formula, H4 Intermediate Step) with zero answer spoilers
- Structure questions into 3-tier gamified assessment (Warm-up, Deep Dive, Boss Challenge)
- 100% textbook exercise utilization across Class 6 Fractions, Class 7 Perimeter & Area, Class 8 Rational Numbers & Linear Equations
- Pre-LLE math insulation for LaTeX and variables
- Write to report.md and handoff.md; send completion message via send_message to parent (283f47a8-950a-4e27-bd0f-8a5ba2bfe0a7)

## Current Parent
- Conversation ID: 283f47a8-950a-4e27-bd0f-8a5ba2bfe0a7
- Updated: not yet

## Task Summary
- **What to build**: Comprehensive curriculum specification report and question banks for Class 6, Class 7, and Class 8 math topics.
- **Success criteria**: Complete coverage of Class 6 Fractions, Class 7 Perimeter & Area, Class 8 Rational Numbers & Linear Equations; strictly conforming to L-Truth zero-spoiler standard; full 4-tier scaffolding; 3-tier gamified mapping.
- **Interface contracts**: `content/contracts/`, `packages/chapter-contract-manager.ts`, `packages/canonical-ir/`
- **Code layout**: Output in `.agents/teamwork_preview_spec_miner_curriculum/` (report.md, handoff.md, progress.md)

## Loaded Skills
- **Source**: c:\Users\admin\Downloads\NGO AI LLM\.agents\skills\aasha-ecosystem\SKILL.md
- **Local copy**: referenced directly
- **Core methodology**: Dual-Benchmark certification, Prebuilt foundations, Zero-token bleed
- **Source**: c:\Users\admin\Downloads\NGO AI LLM\.agents\skills\karaka-compiler\SKILL.md
- **Local copy**: referenced directly
- **Core methodology**: Pāṇinian Kāraka computational semantics, structured action gating

## Key Decisions Made
- Mined existing question contracts, textbook exercise banks, and benchmark test items in Aasha-AI as authoritative ground truth.
- Synthesized 43 questions (14 for Class 6 Fractions, 14 for Class 7 Perimeter & Area, 15 for Class 8 Rational Numbers & Linear Equations) conforming to the 3-Tier Gamified Assessment model (Warm-up, Deep Dive, Boss Challenge).
- Eliminated all forbidden spoiler words (`is, giving, becomes, instead of, to get, yielding, result is, should be`) across all 129 distractor explanations, achieving 100% L-Truth zero-spoiler compliance.

## Artifact Index
- `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\report.md` — Complete curriculum specification, learning objectives, visual manipulative bindings, LLE glossaries, and 43 certified question items.
- `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\handoff.md` — 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion, Verification Method).
- `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_spec_miner_curriculum\progress.md` — Liveness heartbeat (100% complete).

