# AASHA AIOS — TASK 2 WORKSPACE-WIDE REASSESSMENT & LOCAL INVENTORY REPORT

**Directive ID**: `AASHA_TASK2_WORKSPACE_WIDE_REASSESSMENT_R2C`  
**Parent Directives**: `AASHA_TASK2_EVIDENCE_RECONCILIATION_R2B`, `AASHA_TASK2_COMPLETE_SCOPE_REASSESSMENT_R2`  
**Execution Mode**: READ-ONLY WORKSPACE DISCOVERY, CROSS-CODEBASE DEPENDENCY AUDIT & PLAN REBASE  
**Deliverable ID**: `WS-01` / `AASHA_TASK2_WORKSPACE_INVENTORY_REPORT.md`  
**Audit Date**: 2026-11-06  
**Status**: `WORKSPACE_AUDIT_COMPLETE`  

---

## 1. Absolute Workspace Identification & Discovery Bounds

| Discovery Parameter | Verified Actual Value / Filesystem State |
|---|---|
| **IDE / Environment Root** | `C:\Users\admin\Downloads\NGO AI LLM` |
| **Primary Project Root** | `C:\Users\admin\Downloads\NGO AI LLM` |
| **Task 2 Working Directory** | `C:\Users\admin\Downloads\NGO AI LLM\packages\aasha-agent-builder` |
| **Active Primary Git Root** | `C:\Users\admin\Downloads\NGO AI LLM` (`.git`) |
| **Active Git Branch** | `aios/v2-bootstrap` |
| **Active Git Commit HEAD** | `007350b90b636c0aadac27ab5eb862616c8c4fc3` |
| **Task 2 Baseline Commit** | `7cd1e9bbe0c8374ae79a62ce68f4096bb314f89a` |
| **Baseline Diff Check** | `git diff 7cd1e9b HEAD -- packages/aasha-agent-builder/ output/pilot-pack/ Aasha-AI/content/contracts/` $\implies$ **ZERO DIFF (Byte-identical)** |

---

## 2. Complete Inventory of Discovered Git Repositories and Local Projects

Across the primary workspace tree, 9 distinct Git repositories and sub-projects were discovered:

| Repository / Sub-Project Path | Git Root Status | Current Branch | Commit HEAD | Working Tree Status | Role in AASHA Ecosystem | Relevance to Task 2 |
|---|---|---|---|---|---|---|
| `.` (Workspace Root) | Root Git Repo | `aios/v2-bootstrap` | `007350b` | Clean (2 untracked audit reports) | Root Orchestrator & Multi-Project Container | **DIRECT (Hosts packages/aasha-agent-builder)** |
| `Aasha-AI` | Nested Git Repo | `aios/v2-bootstrap` | `5de5aa3` | Clean | Core engine, content contracts, experience registry | **DIRECT (Source of contracts, reference ch v6)** |
| `aasha-studio` | Nested Git Repo | `main` | `37f4a42` | Clean | AGPL-3.0 repackaged classroom UI & workspace tools | **INDIRECT (Tooling & CLI runner)** |
| `external_sources/CinePhysicsHQ` | Nested Git Repo | `main` | `137a27d` | Clean | Visual asset foundation | **REFERENCE (External source)** |
| `external_sources/CinePhysicsHQ-Labs` | Nested Git Repo | `main` | `82cadfd` | Clean | Interactive lab foundation | **REFERENCE (External source)** |
| `gemini-web2api` | Nested Git Repo | `main` | `024c544` | Clean | Go OpenAI-compatible Gemini web bridge | **INDEPENDENT (External router bridge)** |
| `multi-agent-tui` | Sub-Project (inside Root) | (Inherits Root) | `007350b` | Clean | Teacher-facing TUI and terminal agent controller | **INDIRECT (Spawns Python pipeline)** |
| `.scratch/kingsmath` | Nested Git Repo | (Detached/Local) | `f089601` | Clean | Isolated sandbox for math experiments | **SCRATCH (Isolated)** |
| `scratch/gemini-web2api` | Nested Git Repo | `main` | `024c544` | Clean | Duplicate sandbox for web bridge | **SCRATCH (Isolated)** |

---

## 3. Comprehensive File Category Inventory (Relevant to Task 2)

### 3.1 Task 2 Core Implementation Files
- **Primary Subagent Coordinator**: `packages/aasha-agent-builder/src/simulation_subagent.mjs` (759 lines, 26,450 bytes). Contains `SquareGnomonModel`, `IsometricCubeModel`, `selectAdaptiveRenderer()`, `generateSimulationScript()`, and `simulationSubagent()`.
- **Task 1 Baseline Predecessor**: `packages/aasha-agent-builder/src/ingest_subagent.mjs` (547 lines, 18,920 bytes). Certified intact; verified byte hash.
- **Agent Builder Package Manifest**: `packages/aasha-agent-builder/package.json` (ESM module `@aasha/agent-builder@1.0.0`).

### 3.2 Test Suites & Verification Harnesses
- **Simulation Unit Tests**: `packages/aasha-agent-builder/test/simulation_subagent.test.mjs` (136 lines, 5 tests).
- **Task 1 & Task 2 Integration**: `packages/aasha-agent-builder/test/task1_task2_integration.test.mjs` (45 lines, 1 test).
- **Ingestion Unit Tests**: `packages/aasha-agent-builder/test/ingest_subagent.test.mjs` (124 lines, 5 tests).
- **Existing Browser CDP Harness**: `scripts/verify_prestack_assets_browser.mjs` (Prestack verification harness on port 9222).

### 3.3 Authoritative Content Contracts & Reference Implementations
- **NCERT Class 8 Squares & Cubes Contract**: `Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml` (Authoritative curriculum intent, Bloom's verbs, 5 core concepts, misconceptions).
- **Reference Procedural Chapter**: `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html` (Authoritative source for `drawSquareGridSim` lines 2982-3050 and `drawIsoCubeSim` lines 3053-3139).
- **Chapter Assembly Script**: `Aasha-AI/chapters/build_square_cube_chapter.js` (Orchestrates chapter compilation and domain vocabulary).
- **Universal Experience Contract**: `Aasha-AI/experience_registry/aasha_experience_contract.js` (Defines Layer 3 `AashaExperienceContract` non-destructive lifecycle).
- **Domain Simulation Generators**: `Aasha-AI/packages/adapters/domain_sim_generators.ts` (Pre-existing domain simulation generator engine).
- **Foundation Resource Registry**: `Aasha-AI/experience_registry/registry.json` (Live catalog of Foundations F01–F22).

### 3.4 Protected Distribution Artifacts
- **Classroom Pilot Pack Manifest**: `output/pilot-pack/PILOT_PACK_MANIFEST.json` (24 modules, 2,608,444 bytes, SHA-256 verified, strictly protected against mutation).

---

## 4. Cross-Codebase Duplication, Drift, and Competition Analysis

1. **Simulation Generator Implementations**:
   - `packages/aasha-agent-builder/src/simulation_subagent.mjs`: Task 2 implementation producing standalone `<aasha-sim>` Web Component scripts with pure headless math models.
   - `Aasha-AI/packages/adapters/domain_sim_generators.ts`: Earlier TypeScript engine generating domain simulations (ten-frame, fraction, balance equation).
   - *Audit Finding*: The two engines serve distinct stages. `domain_sim_generators.ts` is a template library for legacy chapters, while `simulation_subagent.mjs` is the autonomous subagent coordinator designed to ingest YAML contracts dynamically and synthesize targeted components. No direct runtime collision exists, but `simulation_subagent.mjs` must maintain parity with the touch target and iframe sandboxing standards in `domain_sim_generators.ts`.
2. **Procedural 3D Isometric Drawing Engine**:
   - `Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html:3053-3139` contains the battle-tested Canvas 2D isometric rendering function `drawIsoCubeSim(canvas, n, sliced, showOddSum)`.
   - *Audit Finding*: Defect `D-03` occurs because `simulation_subagent.mjs` implemented `IsometricCubeModel` in headless JS, but failed to port `drawIsoCubeSim` into `generateSimulationScript()`. Porting this existing local function in Batch B fulfills AASHA's `LOCAL_ADAPTATION` reuse invariant (`GEMINI.md:317-324`) without generating new unverified code.

---

## 5. Security, Path Traversal, and Workspace Isolation Audit

- **Dynamic Path Resolution**: `resolveWorkspaceRoot()` and `resolveSecurePath()` in `ingest_subagent.mjs` enforce that all file accesses are bounded inside the workspace root. Traversal attempts (`../`) are blocked.
- **Untrusted Content Injection Sink (Defect D-02)**: Discovered that `simulation_subagent.mjs:484` and `549` interpolate `${SPEC.title}` directly into `container.innerHTML`. The fix requires static template instantiation and assignment strictly via DOM `.textContent`.
- **Secret Staging Check**: No `.env` files, API keys, or private tokens are tracked or exposed across the workspace.

---

## 6. Workspace Audit Conclusion & Decision

```text
STATUS DECISION: WORKSPACE_AUDIT_COMPLETE
```
All local workspace roots, nested Git repositories, shared libraries, contracts, reference implementations, and test harnesses have been inventoried. Zero source or test files were mutated.
