## 2026-09-13T22:31:07Z

You are teamwork_preview_worker_m2, an implementation worker subagent.
Working Directory: c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_worker_m2
Workspace Directory: c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI
Authoritative Request: c:/Users/admin/Downloads/NGO AI LLM/.agents/ORIGINAL_REQUEST.md (MANDATORY: You MUST read this file completely before doing anything else).
Domain Skill Path: c:/Users/admin/Downloads/NGO AI LLM/.agents/skills/aasha-ecosystem/SKILL.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Role: V6 Prototype & Math Insulation Implementer (Milestone 2)

Mission & Scope:
Upgrade `chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` to satisfy all AASHA V6 engine, math insulation, manipulative lifecycle, mobile viewport, and 100% textbook exercise requirements.

Your Exclusive File Ownership:
- `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html`
- `c:/Users/admin/Downloads/NGO AI LLM/PROJECT.md`

Input Artifacts to Read:
- `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json` (Certified 75-question bank across 3 tiers)
- `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/rational_numbers_ad_contract.yaml` (Certified contract)
- `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/experience_registry/aasha_dictionary_db.json` (Full 1,142-word dictionary)
- `c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/packages/aasha-rules/math_insulator.ts`
- `c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_explorer_survey_2/handoff.md` (Explains math insulation failure, dictionary gaps, and lifecycle bugs)
- `c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_explorer_survey_3/handoff.md` (Explains touch target violations and bottom nav invariants)

Specific Implementation Tasks:
1. 3-Tier Gamified Assessment Integration:
   - Embed all 75 questions from `ad_all_questions.json` into the chapter with full UI rendering across `#section-warmup` (31 questions), `#section-deep_dive` (30 questions), and `#section-boss` (14 questions).
   - Render the 4 options, misconception feedback (`m`), and 4-tier progressive hints (`h1`–`h4`) for every question.
   - Update Node 1 real-world hook to faithful textbook truth: 5 pens for ₹22 $\implies$ ₹22/5 = ₹4.40 per pen.
2. Pre-LLE Mathematical Formula & Variable Insulation:
   - Implement genuine math insulation: wrap all LaTeX expressions (`\( ... \)`, `$$ ... $$`) and algebraic single-letter variables (`p`, `q`, `a`, `b`, `c`, `x`, `y`) into `<span class="math-var" data-math="true">` prior to dictionary tokenization.
   - Update `rt(text)` so algebraic variables and insulated spans are NOT tokenized into clickable `.word` spans.
   - Remove the dummy comment `/* MathIsolation: true */` and ensure genuine math insulation is active.
3. Bilingual Indic (Hindi) LLE Substrate:
   - Inline the full 1,142-term vocabulary from `experience_registry/aasha_dictionary_db.json` into `window.WM`.
   - Remove the fake fallback `cw + ' (शब्द)'` in `showWord()`. Ensure genuine Hindi meanings and Devanagari phonics are displayed.
4. Interactive Manipulatives & AashaExperienceContract:
   - Implement `AashaExperienceContract` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `telemetry`).
   - Wrap simulation elements into `<aasha-sim>` or contract-compliant custom elements with non-destructive `pause()` / `resume()` runtime lifecycle (halt RAF off-screen, do NOT execute destructive `innerHTML = ''` DOM tearing on step transitions).
   - Synchronous DOM state binding: every manipulative interaction (preset click, button change) must synchronously update visible DOM text readouts (e.g. fraction strings, coordinate labels) in the same call stack alongside the canvas.
5. Mobile Viewport & Ergonomics Compliance:
   - Enforce touch target size $\ge 44 \times 44\text{px}$ on all interactive buttons (`.exit-btn`, `.dlg-close-x`, `.dlg-audio-btn`, `.btn-back`, `.preset-btn`, `.sim-btn`).
   - Fix fixed bottom navigation bar: `background: #ffffff` (fully opaque), `backdrop-filter: blur(20px)`, top shadow `0 -4px 16px rgba(0,0,0,0.05)`.
   - Add `.screen { padding-bottom: calc(96px + env(safe-area-inset-bottom, 16px)); min-height: 0; }` for safe-area clearance.
   - Keep file completely offline self-contained (0 external CDN calls) and under 20MB.
6. Validation & Documentation:
   - Run `node benchmarks/qa_ltruth_benchmark.js --file chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` and verify score.
   - Update `PROJECT.md` line 68 (Milestone M2).
   - Document all changes and test outputs in `c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_worker_m2/handoff.md`.
   - Send completion message to parent.
