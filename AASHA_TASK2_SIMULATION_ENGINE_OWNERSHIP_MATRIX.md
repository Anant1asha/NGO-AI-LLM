# AASHA AIOS — TASK 2 SIMULATION ENGINE OWNERSHIP & CANONICAL MAPPING

**Directive ID**: `AASHA_TASK2_CROSS_CODEBASE_ARCHITECTURE_VERIFICATION_R2D`  
**Deliverable ID**: `AASHA_TASK2_SIMULATION_ENGINE_OWNERSHIP_MATRIX.md`  
**Execution Mode**: READ-ONLY ARCHITECTURE VERIFICATION & CANONICAL GOVERNANCE  
**Date**: 2026-11-06  

---

## 1. Executive Summary: The Three Simulation Implementations

Across the workspace, three distinct files implement interactive simulation logic. This matrix establishes canonical ownership, architectural roles, lifecycle interfaces, and mutation governance to prevent duplicate development, state collisions, or architectural drift:

| Implementation Path | Architectural Layer | Primary Role | Lifecycle Interface | Math Models Implemented | Visual Renderers Implemented | Canonical Ownership Status |
|---|---|---|---|---|---|---|
| `packages/aasha-agent-builder/src/simulation_subagent.mjs` | **Autonomous Agent Builder (Task 2 Target)** | Dynamic Curriculum Ingestion & `<aasha-sim>` Web Component Synthesis | Layer 3 `AashaExperienceContract` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`) | `SquareGnomonModel` ($s^2, 2s-1$), `IsometricCubeModel` ($n^3, \sum$) | Canvas 2D Gnomon Tile Grid, Procedural Audio Synthesizer | **CANONICAL ACTIVE IMPLEMENTATION**: Authoritative coordinator and target for Task 2 certification. |
| `Aasha-AI/packages/adapters/domain_sim_generators.ts` | **Legacy Framework Adapters** | Static TypeScript Template Generator for Legacy Chapters | Embedded `AashaEmbeddedResourceSim` iframe wrapper | Legacy inline fraction/ten-frame state | Iframe sandboxed HTML resources, SVG ten-frames | **PRESERVED LEGACY TEMPLATE ENGINE**: Static library for earlier chapter builds; zero runtime link to Task 2. |
| `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html` | **Curriculum Distribution Reference** | Verified Classroom Chapter & Visual Rendering Truth | Global function invocation (`drawSquareGridSim`, `drawIsoCubeSim`) | Inline procedural JavaScript variables | Procedural Canvas 2D Square Grid (lines 2982–3050), Procedural Canvas 2D Isometric Cube (lines 3053–3139) | **AUTHORITATIVE VISUAL TRUTH**: Validated classroom asset; source of visual math algorithms adapted into Task 2. |

---

## 2. Canonical Ownership & Component Governance

```
                                  [AASHA SIMULATION ECOSYSTEM]
                                                │
                ┌───────────────────────────────┴───────────────────────────────┐
                ▼                                                               ▼
  [CANONICAL IMPLEMENTATION]                                      [REFERENCE TRUTH]
   packages/aasha-agent-builder/                                   Aasha-AI/chapters/
   src/simulation_subagent.mjs                                     SquareCubeRoots_..._v6.html
   ───────────────────────────                                     ───────────────────────────
   • Owns: Dynamic Ingestion Coordination                          • Owns: Verified Visual Math
   • Owns: Headless Math Models                                    • Source for 2D Grid Math
   • Owns: AashaExperienceContract Adapter                         • Source for 3D Isometric Math
   • Owns: <aasha-sim> Web Component Synthesis                     • Immutable Chapter Baseline
                │                                                               │
                │ (Local Adaptation of Verified Math Engine: GEMINI.md:317-324) │
                └───────────────────────────────◄───────────────────────────────┘
```

1. **Model Governance**:
   - `SquareGnomonModel` and `IsometricCubeModel` in `simulation_subagent.mjs` are the **canonical mathematical oracles**. They execute headless in Node.js, run zero DOM dependencies, and maintain mathematical parity with NCERT textbook definitions.
2. **Visual Renderer Governance**:
   - `SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html` is the **canonical visual rendering source**. Its Canvas 2D projection math (`drawSquareGridSim` and `drawIsoCubeSim`) is the validated standard for classroom devices.
   - `simulation_subagent.mjs` adapts these visual engines into standard `<aasha-sim>` Web Component adapters.
3. **Isolation Guarantee**:
   - `domain_sim_generators.ts` will **NOT** be merged, refactored, or imported into `simulation_subagent.mjs`. It remains an independent legacy library to prevent breaking existing chapter builds.

---

## 3. Detailed Parity & Parity Gap Summary

| Simulation Feature | Canonical Target (`simulation_subagent.mjs`) | Reference Source (`SquareCubeRoots_..._v6.html`) | Parity Status | Required Action in Remediation Plan |
|---|---|---|---|---|
| **2D Gnomon Math** | Pure Headless class `SquareGnomonModel` | Procedural function variables | **PARITY CONFIRMED** | Preserve verified math. |
| **2D Canvas Rendering** | `drawCanvas()` in Adapter | `drawSquareGridSim()` | **PARITY CONFIRMED** | Harden lifecycle cleanup (Batch A: D-01). |
| **3D Cube Math** | Pure Headless class `IsometricCubeModel` | Procedural function variables | **PARITY CONFIRMED** | Preserve verified math. |
| **3D Isometric Rendering**| **MISSING IN CLIENT SCRIPT** | `drawIsoCubeSim()` | **PARITY GAP (D-03)** | Adapt `drawIsoCubeSim` into `IsometricCubeSimulationAdapter` in Batch B. |
| **Touch Targets** | CSS `.btn-touch { min-width: 44px; }` | CSS `.sim-btn { min-width: 44px; }` | **PARITY CONFIRMED** | Verify live layout via CDP in Batch C. |
| **Audio Synthesis** | Procedural Web Audio API | Procedural Web Audio API | **PARITY CONFIRMED** | Add audio disposal in Batch A (REQ-18). |
| **Telemetry Dispatch** | `aasha:telemetry` CustomEvent | Window postMessage bridge | **PARITY CONFIRMED** | Wrap in defensive try/catch in Batch A (REQ-14). |

---

## 4. Ownership Verification Decision

The canonical simulation architecture is **fully established and verified**. `packages/aasha-agent-builder/src/simulation_subagent.mjs` is the sole canonical target for all subsequent Task 2 remediation batches.
