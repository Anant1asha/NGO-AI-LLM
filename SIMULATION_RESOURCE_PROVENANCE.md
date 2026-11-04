# SIMULATION REUSABLE RESOURCE PROVENANCE & SELECTION LEDGER
**Document ID**: `SIMULATION_RESOURCE_PROVENANCE`  
**Workstream**: Task 2 — Adaptive Hybrid Simulation Subagent (`AASHA_TASK2_ADAPTIVE_HYBRID_SIMULATION`)  
**Ecosystem Standard**: AASHA AIOS Layer 3 Experience Registry & Invariant Compliance  
**Date**: 2026-11-04  

---

## 1. Resource Reuse Hierarchy & Decision Criteria

Under AASHA Invariants (`GEMINI.md:317-324`), implementation follows the strict priority order:
$$\text{EXACT\_REUSE} \longrightarrow \text{PARAMETRIC\_ADAPT} \longrightarrow \text{COMPOSE} \longrightarrow \text{LOCAL\_ADAPTATION} \longrightarrow \text{CERTIFIED\_GENERATION} \longrightarrow \text{SAFE\_FALLBACK}$$

Classification criteria:
- **`REUSE`**: Verified offline codebase asset directly compatible without architecture mutation.
- **`ADAPT`**: High-value mechanic requiring adaptation to `<aasha-sim>` Web Component and $\ge 44 \times 44$px touch targets.
- **`CREATE_NEW`**: Zero-dependency procedural synthesis when no existing asset fulfills the specific NCERT learning objective within offline size constraints.
- **`REJECT`**: Incompatible license (e.g. non-commercial copyleft without process boundary), remote runtime network dependencies, or excessive bundle footprint.

---

## 2. Resource Catalog Audit & Classification

| Resource Identifier | Source Repo / Foundation | License | Capabilities & Mechanics | Classification | Adaptation Strategy & Offline Assessment |
|---|---|---|---|---|---|
| **AashaExperienceContract** | `Aasha-AI/experience_registry/aasha_experience_contract.js` | MIT / Proprietary AASHA | Lifecycle (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`), `emitTelemetry` | **`REUSE`** | Authoritative Layer 3 standard. Directly implemented in `simulation_subagent.mjs`. |
| **F01 (Escape Run)** | `https://github.com/abhas9/escape-run` | MIT | PWA offline loops, adaptive mastery gating, local state persistence | **`REUSE`** | Extracted into chapter state coordinator and telemetry handlers. |
| **F02 (MicroSims)** | `https://github.com/dmccreary/microsims` | MIT | 2D dynamic grids, parameter sliders, visual models | **`ADAPT`** | Adapted into 2D Canvas Gnomon Square Visualizer (`drawSquareGridSim`). |
| **F04 (PhET Sims)** | `https://github.com/phetsims` | GPL-3.0 / CC-BY-4.0 | Fractions Intro, Area Model, Balance Explorer | **`REJECT` (Direct bundle)** / **`INSPIRE` (Mechanics)** | Direct embedding rejected due to 3.5MB+ Scenery dependency and GPL boundary; tactile partition mechanic adapted into native lightweight Canvas 2D. |
| **F08 (Physics Notebook)** | `https://github.com/CasberryIndia/Physics-Notebook` | MIT | 60 FPS Canvas 2D isometric projection, layer slicing | **`ADAPT`** | Adapted into 3D Isometric Cube Stacking & Slicing engine (`drawIsoCubeSim`). |
| **F20 (GameBox)** | `https://github.com/saiuttejr/GameBox` | MIT | Touch interaction primitives, responsive layout loops | **`ADAPT`** | Touch target CSS normalization ($\ge 44 \times 44$px) and touch event smoothing. |
| **DomainSimGenerators** | `Aasha-AI/packages/adapters/domain_sim_generators.ts` | AGPL-3.0 | Self-contained `<aasha-sim>` Web Component templates | **`ADAPT`** | Synthesizes standalone, offline Web Component classes for dynamic chapter embedding. |
| **Native Web Audio API** | W3C Standard Browser API | Open Standard | Procedural tone generation, ADSR envelope, zero remote sound files | **`REUSE`** | Synthesized procedural audio oscillator with explicit user gesture gate and mute toggle. |

---

## 3. Selected Task 2 Target Architecture

To guarantee 100% offline functionality, zero CDN calls, and strict containment under the 20 MB ceiling, `simulation_subagent.mjs` implements:

1. **Deterministic Domain Simulation Models**:
   - `SquareGnomonModel`: Pure mathematical simulation of square growth, area calculation ($s^2$), odd subtraction sequence ($2n-1$), and gnomon peeling.
   - `IsometricCubeModel`: Pure mathematical simulation of cubic growth ($n^3$), layer slicing ($n \times n^2$), and consecutive odd grouping.
2. **Adaptive Renderer Engine Selection**:
   - `DOM_SVG`: Selected for accessible controls, parameter sliders, ARIA live region readouts, and discrete buttons.
   - `CANVAS_2D`: Selected for high-performance visual models (gnomon tile grid, isometric 3D cube projections).
   - `WEBGL`: Rejected for simple 2D/3D geometric squares and cubes to avoid GPU overhead and ensure universal support across low-cost Android tablets.
3. **Touch-First Accessibility Controls**:
   - Every operable control (`<button>`, `<input type="range">`) strictly enforces minimum dimensions of $44 \times 44$ CSS pixels.
4. **Procedural Sound Synthesizer**:
   - Procedural Web Audio API sound generator providing subtle audio feedback for increment, decrement, peel, and reset actions without audio file assets.
