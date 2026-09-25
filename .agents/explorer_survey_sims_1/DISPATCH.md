## 2026-09-19T04:23:26Z
# DISPATCH: Explorer — Simulation & Foundation Registry Survey

## Identity
- Role: Codebase Investigator / Simulation Explorer
- Working directory: C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_sims_1
- Target workspace: C:\Users\admin\Downloads\NGO AI LLM\Aasha-AI
- Authoritative request: C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md

## Objective
Investigate the Foundation Registry (`experience_registry/registry.json`), `<aasha-sim>` Web Component architecture, and existing manipulative implementations to identify or design the Square and Cube Roots interactive simulations.

## Tasks
1. Query or inspect `experience_registry/registry.json` and run/examine matching tools (`npm run admin:match -- Mathematics 8 "Square and Cube Roots"` or similar).
2. Check Foundations F01–F20 in `experience_registry/` or `foundations/` to see which prebuilt foundations match square roots and cube roots (e.g. geometric square area grids, cube volume 3D blocks, prime factorisation trees, prime factor grouping balance, continuous estimation number line).
3. Inspect the `<aasha-sim>` Web Component contract (`AashaExperienceContract` with `mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `telemetry`, and CustomEvents `aasha:telemetry`, `aasha:state_change`).
4. Detail the architectural and mathematical specification for the Square and Cube Roots interactive visualizer (e.g., 2D interactive grid building perfect squares with $\sqrt{N}$ slider, 3D isometric cube assembly for $N^3$, prime factor grouping tree manipulative).
5. Output a detailed report to:
   `C:\Users\admin\Downloads\NGO AI LLM\.agents\explorer_survey_sims_1\survey_report.md`
   and write a `handoff.md` summarizing key findings.
6. Send a completion message back to parent when done.
