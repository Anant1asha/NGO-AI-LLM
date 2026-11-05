# AASHA AIOS — TASK 2 UNIFIED ENGINE CAPABILITY MATRIX

**Directive ID**: `AASHA_TASK2_R2G_DELIVERY_CAPABILITY_AND_COMPETITOR_BENCHMARK`  
**Deliverable ID**: `TASK2_UNIFIED_ENGINE_CAPABILITY_MATRIX.md`  
**Date**: 2026-11-06  
**Target Module**: `packages/aasha-agent-builder/src/simulation_subagent.mjs`  
**Evaluation Mode**: SOURCE CODE & RUNTIME CAPABILITY VERIFICATION  

---

## 1. Engine Capability Matrix (10 Core Subsystems)

| Subsystem ID | Target Capability | Documented Specification | Actual Source Code Reality in `simulation_subagent.mjs` | Verified Status | Defect / Gap Ref | Remediation Phase |
|---|---|---|---|---|---|---|
| **CAP-01** | **Mathematical Model Ownership** | Single canonical authority in `packages/aasha-agent-builder/src/` | Pure headless ES classes `SquareGnomonModel` and `IsometricCubeModel` implemented at lines 16–203. No competing classes in any other repository. | **VERIFIED** | None | N/A (Baseline Complete) |
| **CAP-02** | **Square & Cube Mathematical Models** | Discrete geometric gnomon peeling ($s^2$) and cubic odd sum volumetric progression ($n^3$). | Implemented and verified via unit tests at lines 21–79 of `simulation_subagent.test.mjs`. Clamping enforced ($s \in [1, 10], n \in [1, 5]$). | **VERIFIED** | None | N/A (Baseline Complete) |
| **CAP-03** | **Client-Side Model Dispatch** | Dynamically synthesizes either 2D Square Gnomon adapter or 3D Isometric Cube adapter based on model type. | Coordinator creates `IsometricCubeModel`, but `generateSimulationScript(spec)` hardcodes `SquareGnomonSimulationAdapter` only (lines 251–254, 643). | **FAILED** | **D-03** | **Batch B** |
| **CAP-04** | **Renderer Selection Envelope** | 3-tier hierarchy: DOM/SVG $\to$ Canvas 2D $\to$ WebGL. | `selectAdaptiveRenderer()` assigns static fallback metadata based on device and dimensionality rules. | **VERIFIED** (Design & Metadata) | None | N/A |
| **CAP-05** | **Runtime Capability Probing & Fallback** | Live browser capability detection (e.g. testing WebGL context availability) with automatic runtime degradation. | No client-side probe in synthesized script. Client adapter assumes Canvas 2D context is always available. | **PARTIAL** | REQ-05 / REQ-08 | **Batch B** |
| **CAP-06** | **Procedural Web Audio Engine** | Pure Web Audio oscillator synthesis (chimes, clicks, chords), gesture-gated, accessible mute toggle, zero audio files. | Implemented in `SimpleAudio` class (lines 278–344). Synthesizes pleasant sine waves. Contains mute toggle. However, audio context is not cleanly closed in `destroy()`. | **PARTIAL** | **REQ-18** | **Batch A (Sub-Scope A2)** |
| **CAP-07** | **Interactive Lifecycle Management** | Standard non-destructive lifecycle: `mount()`, `getState()`, `pause()`, `resume()`, `reset()`, `destroy()`. | Custom element implements lifecycle methods, but `bindEvents()` attaches anonymous event listeners that are not detached in `destroy()`, causing listener accumulation. | **FAILED** | **D-01** | **Batch A (Sub-Scope A2)** |
| **CAP-08** | **Aasha ExperienceContract Compliance** | Standard contract with state isolation, telemetry events (`aasha:telemetry`), touch targets $\ge 44 \times 44$px. | Emits `CustomEvent('aasha:telemetry')`. However, `dispatchEvent` is not wrapped in `try/catch`. Title insertion uses unsafe `innerHTML` interpolation (`D-02`). | **FAILED** | **D-02**, **REQ-14** | **Batch A (Sub-Scope A1 & A2)** |
| **CAP-09** | **Legacy Consumer Isolation** | `v6_compiler.ts` is sole consumer. Legacy generator `domain_sim_generators.ts` isolated and preserved. | Inspected `v6_compiler.ts:154-168`. Consumes `domain_sim_generators.ts`. No circular dependencies or leaks into canonical engine. | **VERIFIED** | None | N/A |
| **CAP-10** | **Compatibility Bridge Boundary** | Seamless bridge (`UnifiedSimCompatibilityBridge`) permitting V6 compiler to consume canonical scripts. | Fully specified in `AASHA_TASK2_LEGACY_ENGINE_MIGRATION_MATRIX.md`. Implementation in `v6_compiler.ts` remains pending post-Task 2 closure. | **DESIGN_VERIFIED** (Implementation Pending) | Legacy Bridge Migration | Post-Task 2 |

---

## 2. Forensic Analysis of Known Defects & Remediation Mapping

```text
+---------------------------------------------------------------------------------------+
| DEFECT D-01: Custom Element Lifecycle Memory Leak (REQ-13)                            |
+---------------------------------------------------------------------------------------+
| File: packages/aasha-agent-builder/src/simulation_subagent.mjs:568-630                |
| Cause: Anonymous event listeners attached to DOM buttons without AbortSignal.          |
| Impact: DOM node leaks and duplicate event executions when custom element is re-added.|
| Fix: Instantiate AbortController in adapter; pass { signal } to all addEventListener; |
|      call abort() and close AudioContext in destroy().                                |
| Target Batch: Sub-Scope A2 (Lifecycle & Telemetry Hardening)                          |
+---------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------+
| DEFECT D-02: Security / DOM XSS Sink via Title Interpolation (REQ-21)                  |
+---------------------------------------------------------------------------------------+
| File: packages/aasha-agent-builder/src/simulation_subagent.mjs:484, 549               |
| Cause: ${SPEC.title || 'Interactive Simulation'} directly interpolated into innerHTML.|
| Impact: DOM XSS vulnerability if curriculum title contains unescaped HTML/JS payload. |
| Fix: Use static DOM container with <span id="simTitle">; assign textContent;          |
|      escape '<' and '>' in JSON serialization (.replace(/</g, '\\u003c')).            |
| Target Batch: Sub-Scope A1 (Security Hardening)                                       |
+---------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------+
| DEFECT D-03: Model-to-Script Dispatch Disconnect (REQ-07, REQ-08)                     |
+---------------------------------------------------------------------------------------+
| File: packages/aasha-agent-builder/src/simulation_subagent.mjs:251-254, 643           |
| Cause: generateSimulationScript() hardcodes SquareGnomonSimulationAdapter only.       |
| Impact: Ingesting a 3D cubic concept generates a 2D square gnomon simulation script. |
| Fix: Port drawIsoCubeSim from chapter v6 into IsometricCubeSimulationAdapter;         |
|      dispatch dynamically based on spec.modelType; throw UNSUPPORTED_MODEL on unknown.|
| Target Batch: Batch B (3D Isometric Model & Dynamic Dispatch)                         |
+---------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------+
| EVIDENCE GAP E-01: Missing Headless Chrome CDP Live Layout Verification (REQ-16)     |
+---------------------------------------------------------------------------------------+
| File: packages/aasha-agent-builder/test/simulation_browser_cdp.test.mjs (To Create)   |
| Cause: Unit test runner asserts CSS string presence, not rendered layout bounding box.|
| Impact: Touch targets might measure < 44x44 CSS pixels due to CSS collapse/padding.   |
| Fix: Implement ephemeral Headless Chrome CDP runner asserting getBoundingClientRect() |
|      >= 44x44 CSS px for all interactive controls.                                    |
| Target Batch: Batch C (Live Browser CDP Layout & Offline Emulation)                   |
+---------------------------------------------------------------------------------------+
```

---

## 3. Byte Budget and Offline Delivery Reality

- **Child-Facing HTML5 Bundle Ceiling**: `CHILD_HTML5_BUNDLE_MAX_BYTES = 20,971,520` (20 MiB).
- **Canonical Generated Simulation Script**:
  - Raw client script size: **13,924 bytes (13.6 KiB)**.
  - Percentage of budget: **0.066%**.
- **Reference Standalone Class 8 Chapter Module (`SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html`)**:
  - Full bundle size: **207,872 bytes (203 KiB)**.
  - Percentage of budget: **0.991%**.
- **External CDN Calls in Bundle**: **0** (Zero Google Fonts, Zero external CDNs, Zero unbundled JavaScript libraries).
- **Procedural Sound Overhead**: **0 bytes** of external MP3/WAV files; audio synthesized entirely through standard Web Audio API oscillator nodes.
