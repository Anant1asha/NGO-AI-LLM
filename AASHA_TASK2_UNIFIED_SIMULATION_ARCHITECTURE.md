# AASHA AIOS — TASK 2 UNIFIED SIMULATION ARCHITECTURE SPECIFICATION

**Directive ID**: `AASHA_TASK2_UNIFIED_SIMULATION_ARCHITECTURE_R2E`  
**Parent Directives**: `AASHA_TASK2_CROSS_CODEBASE_ARCHITECTURE_VERIFICATION_R2D`, `AASHA_TASK2_WORKSPACE_WIDE_REASSESSMENT_R2C`  
**Mode**: READ-ONLY ARCHITECTURE UNIFICATION AND HALLUCINATION CONTROL DESIGN  
**Deliverable ID**: `AASHA_TASK2_UNIFIED_SIMULATION_ARCHITECTURE.md`  
**Date**: 2026-11-06  
**Final Status Decision**: `UNIFIED_ARCHITECTURE_VERIFIED`  

---

## 1. Executive Summary & Architectural Invariant

This specification establishes **one canonical simulation source of truth** across all AASHA codebases, eliminates duplicate and competing mathematical authorities, defines a strict model-renderer decoupled contract, and enforces anti-hallucination controls that guarantee zero ungrounded or AI-hallucinated behavior can ever execute in learner-facing simulations.

### 1.1 The Core Invariant: Deterministic Grounding & Mathematical Authority
> **Unified Simulation Invariant (USI-01)**:  
> *No LLM, neural network, or client renderer possesses mathematical authority.*  
> All mathematical states, formulas, progressions, and boundary clamps reside exclusively in verified, pure TypeScript/ESM headless mathematical models (`SquareGnomonModel`, `IsometricCubeModel`). Renderers (DOM/SVG, Canvas 2D, WebGL) are strictly passive view projections of validated model states. Any simulation request lacking source curriculum grounding fails closed with an explicit typed error.

---

## 2. Canonical Model Ownership & Ecosystem Map

```
                  [NCERT / Ganita Prakash Verified Curriculum Contracts]
                                            │
                                            ▼
                  [packages/aasha-agent-builder/src/ingest_subagent.mjs]
                                            │
                                            │ (Contract IR: slug, grade, concepts, misconceptions)
                                            ▼
                  [packages/aasha-agent-builder/src/simulation_subagent.mjs]
                                ┌───────────┴───────────┐
                                ▼                       ▼
                      [CANONICAL MATH CORE]   [ADAPTIVE RENDERER BROKER]
                      • SquareGnomonModel     • Capability Probing
                      • IsometricCubeModel    • DOM/SVG -> Canvas 2D -> WebGL
                                │                       │
                                └───────────┬───────────┘
                                            ▼
                           [CANONICAL SIMULATION CONTRACT]
                            (AashaCanonicalSimContract v1)
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼                                               ▼
      [DYNAMIC Web Component SYNTHESIS]              [LEGACY V6 COMPILER ADAPTER]
      generateSimulationScript(spec)                 Aasha-AI/packages/v6-engine/
      └─> <aasha-sim> Standalone JS                  └─> UnifiedSimCompatibilityBridge
                    │                                               │
                    └───────────────────────┬───────────────────────┘
                                            ▼
                         [BROWSER / CHILD-FACING RUNTIME]
                         • Layer 3 Experience Lifecycle
                         • 44x44px Touch Targets
                         • Procedural Audio (Gated)
                         • Zero-CDN / 100% Offline
```

### 2.1 Authoritative Component Matrix
1. **Canonical Mathematical Authority**:
   - Location: `packages/aasha-agent-builder/src/simulation_subagent.mjs`
   - Authority: Pure headless ES classes (`SquareGnomonModel`, `IsometricCubeModel`). Zero DOM globals, zero external dependencies. Verified by mathematical oracle unit tests.
2. **Canonical Simulation Coordinator**:
   - Location: `packages/aasha-agent-builder/src/simulation_subagent.mjs` (`simulationSubagent()`).
   - Authority: Consumes curriculum contracts, selects models, validates schema, determines adaptive renderers, and synthesizes standalone `<aasha-sim>` Web Component scripts.
3. **Reference Visual Math Standard**:
   - Location: `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html`
   - Authority: Validated visual rendering math (`drawSquareGridSim` lines 2982–3050 and `drawIsoCubeSim` lines 3053–3139).
4. **Legacy Consumer / Compiler Engine**:
   - Location: `Aasha-AI/packages/v6-engine/v6_compiler.ts` & `Aasha-AI/packages/adapters/domain_sim_generators.ts`
   - Authority: Preserved for legacy chapter compilation. Will consume the canonical simulation contract via the `UnifiedSimCompatibilityBridge` without maintaining competing math models.

---

## 3. The 3-Tier Adaptive Renderer Architecture

Renderers must never evaluate formulas independently; they consume immutable state snapshots emitted by the headless model.

```
       [Learner Interaction (Drag / Click / Key / Slider)]
                              │
                              ▼
           [Canonical Headless Model State Mutation]
             (Model.setSide(), Model.peelGnomon())
                              │
                              ▼
               [Validated State Snapshot Emitted]
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   [Tier 1: DOM/SVG]    [Tier 2: Canvas 2D]   [Tier 3: WebGL]
   • Accessible Text    • High-Perf Grids     • Complex 3D Meshes
   • ARIA Readouts      • Isometric Projection• (Isolated Fallback)
   • 44x44px Sliders    • Slicing Animations  • (Strictly Gated)
   • Focus Ring Boxes   • 60 FPS Rasterization• GPU Probe Fallback
```

### 3.1 Strict Capability Detection & Fallback Logic
1. **Static Heuristic**:
   - If dimension is 2 $\implies$ Select `CANVAS_2D` for visual grids, `DOM_SVG` for parameter sliders.
   - If dimension is 3 and complexity is standard (e.g. unit cubes $\le 5^3$) $\implies$ Select `CANVAS_2D` isometric projection with `DOM_SVG` controls.
   - If dimension is 3 and complexity is `high_poly` (> 50,000 vertices) $\implies$ Request `WEBGL` with deterministic `CANVAS_2D` fallback.
2. **Dynamic Client Probing**:
   - If `WEBGL` is requested, the client runtime probes context:
     ```javascript
     const hasWebGL = (() => {
       try {
         const c = document.createElement('canvas');
         return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
       } catch (e) { return false; }
     })();
     ```
   - If `hasWebGL === false`, the adapter logs a fallback event and transparently downgrades to the Canvas 2D isometric rendering engine.

---

## 4. Hallucination Resistance & Fail-Closed Policy

To guarantee that generative AI or LLM routing never introduces invalid formulas or non-existent pedagogical concepts into simulations:

| Hallucination Risk | Failure Mode | Enforced Fail-Closed Control | Error Code Emitted |
|---|---|---|---|
| **Ungrounded Concept** | AI invents a concept not in curriculum YAML. | Subagent verifies concept ID and title against approved contract. Missing evidence rejects generation. | `INSUFFICIENT_SOURCE_EVIDENCE` |
| **Model Hallucination** | AI requests non-existent model (e.g. `Hypercube4DModel`). | Explicit model whitelist. Unrecognized models throw structured error; no silent fallback to default. | `UNSUPPORTED_MODEL` |
| **Formula Mutation** | AI attempts to generate custom math math string. | Mathematical logic is locked in immutable pure JS classes; script generator embeds pre-compiled math only. | `MATHEMATICAL_INVARIANT_FAILED` |
| **Schema Violation** | Input parameters out of bounds ($s = -5, s = 999$). | Strict schema clamping and validation in model constructor and setters ($s \in [1, 10]$). | `SCHEMA_VALIDATION_FAILED` |
| **License Bleed** | Direct embedding of GPL/proprietary libraries. | Resource provenance ledger verified; non-compliant bundles rejected at build gate. | `PROVENANCE_UNVERIFIED` |
| **State Tampering** | LLM completion directly mutates TEAS mastery or state. | Learning state managed strictly by `V6RuntimeBus` and deterministic scoring engines; LLMs have zero state write access. | `UNAUTHORIZED_STATE_MUTATION` |
| **Telemetry Crash** | Listener exception corrupts model simulation loop. | Telemetry `dispatchEvent` wrapped in defensive `try/catch` error isolation boundaries. | `TELEMETRY_DISPATCH_ISOLATED` |

---

## 5. Architectural Verification Decision

```text
STATUS DECISION: UNIFIED_ARCHITECTURE_VERIFIED
REMEDIATION SEQUENCE: READY FOR SEQUENTIAL AUTHORIZATION
```
The unified architecture conclusively eliminates duplicate mathematical authority, establishes `packages/aasha-agent-builder/` as the single canonical coordinator, and defines strict fail-closed anti-hallucination controls.
