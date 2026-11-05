# AASHA AIOS — TASK 2 WORKSPACE-WIDE REMEDIATION PLAN (REVISION R2E)

**Directive ID**: `AASHA_TASK2_UNIFIED_SIMULATION_ARCHITECTURE_R2E`  
**Deliverable ID**: `AASHA_TASK2_WORKSPACE_WIDE_REMEDIATION_PLAN.md`  
**Status**: `UNIFIED ARCHITECTURE INTEGRATED — AWAITING HUMAN SUPERVISOR AUTHORIZATION`  
**Parent Directives**: `AASHA_TASK2_CROSS_CODEBASE_ARCHITECTURE_VERIFICATION_R2D`, `AASHA_TASK2_WORKSPACE_WIDE_REASSESSMENT_R2C`  
**Date**: 2026-11-06  

---

## 1. Remediation Strategy, Unified Architecture & Budget Governance

This updated remediation plan incorporates the unified simulation architecture, the canonical simulation contract schema (`AashaCanonicalSimContract v1`), legacy bridge migration rules, and fail-closed anti-hallucination policies.

### 1.1 Canonical Ownership & Scope Lock
- **Single Canonical Implementation**: All code modifications are strictly scoped to the canonical target:
  - `packages/aasha-agent-builder/src/simulation_subagent.mjs`
  - `packages/aasha-agent-builder/test/simulation_subagent.test.mjs`
  - `packages/aasha-agent-builder/test/simulation_browser_cdp.test.mjs` (New test file in Batch C)
- **Immutable Ecosystem Preservations**:
  - `Aasha-AI/packages/adapters/domain_sim_generators.ts` remains strictly preserved as a legacy template engine without mutation.
  - `Aasha-AI/packages/v6-engine/v6_compiler.ts` consumes canonical scripts via the `UnifiedSimCompatibilityBridge`.
  - `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html` remains the immutable visual reference source.
  - `packages/aasha-agent-builder/src/ingest_subagent.mjs` (Task 1) remains 100% untouched.
  - `output/pilot-pack/` distribution manifests remain 100% untouched.
- **Repair Budget Limit**: Maximum **two (2) repair attempts** per defect class before mandatory HIL escalation.
- **Zero Token Bleed**: 100% deterministic local TypeScript/ESM implementation.

---

## 2. Master 10-Step Remediation Sequence

```
[1. Verify Simulations & Canonical Ownership] ──> COMPLETE (R2D-02 & Ownership Matrix)
[2. Establish Affected Workspace Files]       ──> COMPLETE (R2D-05)
[3. Finalize Unified Architecture & Policies] ──> COMPLETE (R2E Documents Delivered)
        │
        ▼ (Awaiting Human Supervisor Command: "AUTHORIZE SUB-SCOPE A1")
[4. Authorize A1 Security Hardening]          ──> D-02 textContent + Unicode escape
[5. Inspect A1 Code Diff & Security Tests]    ──> Verify XSS title injection sanitized
        │
        ▼ (Awaiting Human Supervisor Command: "AUTHORIZE SUB-SCOPE A2")
[6. Authorize A2 Lifecycle & Telemetry]       ──> D-01 AbortController + REQ-14 + REQ-18
[7. Inspect A2 Code Diff & Isolation Tests]   ──> Verify unmount cleanup & error isolation
        │
        ▼ (Awaiting Human Supervisor Command: "AUTHORIZE BATCH B")
[8. Authorize Batch B Model Dispatch]         ──> D-03 Port drawIsoCubeSim + 3D Dispatch
        │
        ▼ (Awaiting Human Supervisor Command: "AUTHORIZE BATCH C")
[9. Complete Browser, Offline & Touch Hits]   ──> E-01 Headless Chrome CDP Live Layout
        │
        ▼ (Awaiting Final Supervisor Closure)
[10. Run Full Regression & Certification]     ──> 24/24 FULLY_MET Sign-Off Report
```

---

## 3. Detailed Batch Specifications & Acceptance Boundaries

| Batch / Sub-Scope | Target Files | Defect / Scope Ref | Exact Technical Changes | Test Harness & Empirical Verification Criteria | Rollback Procedure |
|---|---|---|---|---|---|
| **Sub-Scope A1 (Security Hardening)** | `packages/aasha-agent-builder/src/simulation_subagent.mjs` | **D-02** (XSS Sink, REQ-21) | 1. Remove `${SPEC.title}` from `container.innerHTML` template.<br>2. Insert `<span class="sim-title" id="simTitle"></span>`.<br>3. Assign title strictly via `container.querySelector('#simTitle').textContent = SPEC.title \|\| '...'`.<br>4. Harden JSON script injection: `.replace(/</g, '\\u003c').replace(/>/g, '\\u003e')`. | New unit test in `simulation_subagent.test.mjs`: Pass concept title containing `<img src=x onerror=alert(1)>` and assert that no `<img>` tag is created in DOM and title is safely rendered as plain text. | `git checkout -- packages/aasha-agent-builder/src/simulation_subagent.mjs` |
| **Sub-Scope A2 (Lifecycle & Telemetry)** | `packages/aasha-agent-builder/src/simulation_subagent.mjs` | **D-01** (Memory Leak, REQ-13), **REQ-14** (Telemetry Isolation), **REQ-18** (Audio Disposal) | 1. Initialize `this._abortController = new AbortController()` in adapter constructor.<br>2. Pass `{ signal: this._abortController.signal }` to all DOM event bindings in `bindEvents()`.<br>3. In `destroy()`, call `this._abortController.abort()`, unbind audio context reference, and nullify container.<br>4. In `emitTelemetry()`, wrap `this.container.dispatchEvent` in `try/catch` so external listener errors cannot crash simulation state. | New unit test in `simulation_subagent.test.mjs`: Mount and destroy custom element across 5 cycles asserting event listener detachment and fault-tolerant telemetry when listener throws. | Revert Sub-Scope A2 diff |
| **Batch B (3D Isometric Simulation & Dispatch)** | `packages/aasha-agent-builder/src/simulation_subagent.mjs`, `simulation_subagent.test.mjs` | **D-03** (Model-to-Script Dispatch Disconnect), **REQ-07**, **REQ-08**, **REQ-05** | 1. Port validated `drawIsoCubeSim` from chapter v6 into `IsometricCubeSimulationAdapter`.<br>2. Implement conditional dispatch in `generateSimulationScript(spec)` based on `spec.modelType`.<br>3. Add client-side WebGL fallback to Canvas 2D.<br>4. Enforce fail-closed `UNSUPPORTED_MODEL` error for unknown models. | New unit test in `simulation_subagent.test.mjs`: Pass 3D cubic concept spec to `simulationSubagent()` and assert generated script contains `IsometricCubeSimulationAdapter` and executes cubic slicing logic. | `git checkout -- packages/aasha-agent-builder/` |
| **Batch C (Live Browser Layout & Offline)** | `packages/aasha-agent-builder/test/simulation_browser_cdp.test.mjs` | **E-01** (Live Browser Layout Box, REQ-16), **REQ-19** (Offline Live Execution) | 1. Implement Headless Chrome CDP runner on dynamic ephemeral port.<br>2. Mount `<aasha-sim>` component in live browser DOM.<br>3. Measure `el.getBoundingClientRect()` across all operable buttons and sliders.<br>4. Assert all hit targets $\ge 44 \times 44$ CSS pixels.<br>5. Execute with network disabled (`Network.emulateNetworkConditions({ offline: true })`) asserting zero failed network requests. | `npm --prefix packages/aasha-agent-builder test` executes CDP test suite and reports 100% compliant layout bounding boxes and zero network requests. | Delete `simulation_browser_cdp.test.mjs` |

---

## 4. Human Approval Gates & Execution Protocol

Every single step is gated behind explicit human supervisor authorization:
- **Gate A1**: Await command `"AUTHORIZE SUB-SCOPE A1"` $\to$ Apply A1 $\to$ Test & inspect diff.
- **Gate A2**: Await command `"AUTHORIZE SUB-SCOPE A2"` $\to$ Apply A2 $\to$ Test & inspect diff $\to$ Certify Batch A.
- **Gate B**: Await command `"AUTHORIZE BATCH B"` $\to$ Apply B $\to$ Test & inspect diff $\to$ Certify Batch B.
- **Gate C**: Await command `"AUTHORIZE BATCH C"` $\to$ Apply C $\to$ Run browser CDP layout verification $\to$ Certify Batch C.
- **Gate Final**: Present 24/24 `FULLY_MET` Certification Report $\to$ Await human command to close Task 2.

---

## 5. Current Control Status

```text
STATUS DECISION: UNIFIED_ARCHITECTURE_VERIFIED
TASK 2 STATUS: OPEN
IMPLEMENTATION AUTHORIZATION: NOT_GRANTED (Read-only compliance maintained)
RECOMMENDED IMMEDIATE NEXT ACTION: AWAIT HUMAN SUPERVISOR COMMAND "AUTHORIZE SUB-SCOPE A1"
```
