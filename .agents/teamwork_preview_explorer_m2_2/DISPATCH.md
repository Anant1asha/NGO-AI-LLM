## 2026-09-19T04:44:15+05:30
You are teamwork_preview_explorer_m2_2.
Your working directory is:
C:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_m2_2

You MUST read the authoritative user request at:
C:\Users\admin\Downloads\NGO AI LLM\.agents\ORIGINAL_REQUEST.md

And the project scope at:
C:\Users\admin\Downloads\NGO AI LLM\PROJECT.md

Your role is Read-Only Simulation Engines & <aasha-sim> Explorer.
DO NOT write or modify source code files. Write ONLY to your working directory.

Your mission:
Investigate `Aasha-AI/experience_registry/registry.json`, `Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml`, and existing procedural canvas simulation implementations in `Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html` and `Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html`.
Design and specify the exact architecture and procedural drawing code for the 5 interactive manipulatives for the Squares and Cubes chapter:
1. 2D Square Grid & Gnomon Visualizer Sim (side slider s in [1, 10], area display, odd-layer peeling 2n - 1, gnomon overlay).
2. 3D Isometric Cube Stacker Sim (60 FPS 2D canvas isometric projection of n x n x n unit blocks, layer slicing toggle, odd-sum grouping representation).
3. Prime Factor Grouping Tree Sim (prime factor decomposition, pairing for square roots sqrt(N), tripling for cube roots cbrt(N), orphan prime multiplier and divisor calculation).
4. 100-Locker Riddle & Ending Digit Explorer Sim (100 lockers parity simulation, toggle animation, open locker square condition, factor parity counter, ending digit bijection filter).
5. Rapid 3-Digit Grouping Cube Estimator Sim (units digit mapping 0->0, 1->1, 4->4, 5->5, 6->6, 9->9, 2<->8, 3<->7, thousands grouping bracket isolation).

Ensure each manipulative conforms to:
- `AashaExperienceContract`: `mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, and bubbles `aasha:telemetry` and `aasha:state_change` CustomEvents.
- Non-destructive pause()/resume() lifecycle preserving canvas buffers and state.
- Synchronous DOM state binding with parameter readouts.

Document all findings, verified procedural algorithms, and interface specifications in:
C:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_m2_2\handoff.md

When complete, send a message to your caller (parent) reporting completion.
