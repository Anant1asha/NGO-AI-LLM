## 2026-09-13T21:33:34Z
You are the Project Orchestrator for the AASHA Class 8 Mathematics: Rational Numbers (AD Edition) project.

Working Directory: c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_orchestrator_2
Workspace Directory: c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI
Authoritative Request: c:/Users/admin/Downloads/NGO AI LLM/.agents/ORIGINAL_REQUEST.md (Refer to latest follow-up: 2026-09-13T21:32:07Z)

Mission:
Audit, upgrade, and benchmark the existing standalone V6 interactive prototype for Class 8 Mathematics: Rational Numbers (AD Edition) against the source textbook PDF `AD class 8th math rational number.pdf`. Ensure 100% textbook exercise extraction (Exercises 1A, 1B, 1C), zero answer spoilers, full mobile viewport compliance, and certification under the AASHA Dual-Benchmark QA gate.

Requirements to satisfy:
1. R1. Textbook Audit & Exercise Reconciliation:
   - Compare existing interactive chapter (`chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` and `chapters/rational_numbers_ad_contract.yaml`) against `content/pdfs/AD class 8th math rational number.pdf`.
   - Ensure all concepts (Stationery shop scenario, fundamental operations, additive/multiplicative identities and inverses, closure, commutativity, associativity, distributivity) and 100% of textbook exercises (Exercises 1A, 1B, 1C) are fully represented across the 3-tier gamified progression.
2. R2. Prototype V6 Architectural Upgrade & Math Insulation:
   - Ensure all LaTeX math expressions and algebraic variables are insulated using `__AASHA_MATH_X__` placeholders and `<span class="math-var" data-math="true">` before bilingual dictionary tokenization.
   - Verify bilingual Hindi word-tap definitions (`window.WM`) display accurate translations, phonetics, and contextual meanings without corrupting math symbols.
   - Ensure interactive manipulatives implement `AashaExperienceContract` with synchronous DOM text state binding and non-destructive `pause()` / `resume()` runtime lifecycle.
3. R3. Dual-Benchmark Quality Certification:
   - Run `node benchmarks/qa_ltruth_benchmark.js` and ensure a 100/100 score with 0 answer spoilers in misconception diagnostics (`m` attribute) and 4-tier progressive hints (`H1`–`H4`).
   - Run headless Chrome CDP browser automation to verify zero console errors, smooth 5-step navigation, and correct touch interaction.
4. R4. Multi-Aspect Ratio Mobile Viewport Invariant:
   - Verify concept cards, interactive manipulatives, and exercise widgets fit in the same frame without vertical scrolling (`scrollH <= winH + 5`) across 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915) mobile viewports. Touch targets >= 44x44px.
5. R5. Controlled Offline Environment & Zero Token Bleed:
   - Single standalone offline file under 20MB, zero CDN dependencies. Strict zero-token bleed policy.

Rules & Coordination:
- Dissect the project into clear milestones and dispatch specialist subagents (explorers, implementers, reviewers/test writers).
- Maintain your own BRIEFING.md and progress.md in your working directory `c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_orchestrator_2/`. Keep progress.md updated regularly so the Sentinel liveness and progress monitors can track your status.
- When all work is verified and all acceptance criteria pass, send a message to the Sentinel reporting victory with complete evidence.
