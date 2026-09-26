# AASHA AIOS — Technical Requirements Document (TRD)
**Document Identifier:** `AASHA-SPEC-02-TRD`  
**Classification:** Canonical Technical Specification  
**Version:** 2.0.0 (Unified Ecosystem Release)  
**Lifecycle Status:** APPROVED / LEVEL 1 SPECIFICATION  
**Execution Environment:** Node.js v20+, TypeScript v5.8+, Browser (HTML5 / ES2022 / Canvas / WebGL)

---

## 1. System Architecture Overview

The AASHA AIOS Technical Architecture is structured across two distinct planes:
1. **Control & Build Plane (Offline/Local Developer & Super Admin Host):**
   * **Node.js & TypeScript Runtime:** Executes `admin_memory_cli.ts`, Section 24 contract generators, canonical IR assembly, and HTML compilation (`tsx@4.19.3`, `typescript@5.8.2`).
   * **Python Harvester & Provenance Engine:** PyMuPDF-based textbook extractor, SHA-256 PDF byte hasher, and page range slicer (`aasha-pipeline-with-master-json`).
   * **Local Knowledge & Memory Store:** SQLite local knowledge graph (`graphify-out/graph.json`) and local episodic store (`.scratch/mem0_store.json`).
   * **Automated Dual-Benchmark Harness:** Static AST regex validator (`qa_ltruth_benchmark.js`) and Headless Chrome DevTools Protocol client (`verify_square_cube_cdp.js`).

2. **Learner Execution Plane (Air-Gapped Client Runtime):**
   * **Single-File HTML5 Distribution:** Standalone monolithic bundle containing HTML, raw CSS, raw JS, and Base64-encoded binary assets.
   * **V6 Runtime Bus (`V6RuntimeBus`):** Pure vanilla JavaScript event bus managing card state transitions, manipulative synchronization, and progressive hint disclosure.
   * **Asynchronous Telemetry Engine (`AashaTelemetryClient`):** Browser-native IndexedDB event logger buffering semantic events without blocking the main interaction thread.

---

## 2. Hard Technical Budgets & Constraints

### 2.1. Single-File HTML5 Bundle Ceiling: 40 MB
```text
CHILD_HTML5_BUNDLE_MAX_BYTES = 41_943_040  // Exactly 40 MB (40 * 1024 * 1024 bytes)
```
* **Enforcement:** The build pipeline (`v6_compiler.ts`) and version manager (`version_manager.ts`) automatically calculate total byte length upon bundle emission. Any chapter exceeding $41,943,040\text{ bytes}$ triggers a compilation error and enters quarantine.
* **Smart Inlining Rule:**
  * Raw JavaScript is inlined directly inside `<script>` tags.
  * Raw CSS is inlined directly inside `<style>` tags (avoiding 33% Base64 text overhead).
  * Base64 Data URIs (`data:...;base64,`) are strictly reserved for binary assets (PNG/JPEG visuals, MP3 audio phonetics, WOFF2 fonts).

### 2.2. Memory & Runtime Lifecycle: Balanced Invariant ($\ge 4$ GB RAM)
* **Target Hardware:** Budget Android devices and laptops with $\ge 4\text{ GB}$ system RAM.
* **Non-Destructive Pause/Resume:** When switching between cards or collapsing sections:
  * DOM tearing and canvas context recreation are strictly prohibited.
  * Simulation engines must implement `pause()` (halting `requestAnimationFrame` loops and clearing interval timers) and `resume()`.
  * WebGL/2D Canvas context buffers and internal physics states are preserved across navigation.

### 2.3. Bounded Telemetry Complexity: Sub-50ms Latency
* **Algorithmic Complexity:** All dynamic mastery calculations and TEAS scoring operate in $O(1)$ time relative to total session length.
* **Sliding Window:** Telemetry scans are bounded to a sliding window of the latest $K = 100$ events.
* **Asynchronous Non-Blocking Emission:** Telemetry emission must execute in $< 2\text{ms}$ on the main thread via asynchronous IndexedDB batching. If storage fails, interaction continues unimpeded.

---

## 3. Mathematical & Bilingual Substrate Protection

### 3.1. Pre-LLE Mathematical Insulation Protocol
* **Problem:** Bilingual dictionary tokenizers (`rt()` / `window.WM`) misidentify mathematical variables ($x, y, a, b$) and LaTeX syntax (`\frac`, `\sqrt`) as translatable English text.
* **Deterministic Solution:**
  1. All LaTeX expressions (`\( ... \)`, `$$ ... $$`, `$...$`) are extracted and shielded with opaque tokens: `__AASHA_MATH_X__`.
  2. Single-letter algebraic variables are wrapped in protected DOM tags: `<span class="math-var" data-math="true">`.
  3. LLE dictionary tokenizer processes remaining natural language tokens.
  4. Post-processing step unwraps `__AASHA_MATH_X__` into pure, uncorrupted KaTeX rendered nodes.

### 3.2. Dictionary Caching & Zero-Token Fallback
* Hindi dictionary entries are stored locally in `experience_registry/aasha_dictionary_db.json`.
* When a chapter introduces new terms, `syncChapterVocabulary()` persists the translations without BOM, ensuring zero third-party API token consumption during subsequent builds.

---

## 4. Universal Web Component Adapter Specification (`<aasha-sim>`)

All interactive visual foundations (F01–F20, Phase3 AVR Harvest, CinePhysicsHQ Labs) must implement the `AashaExperienceContract`:

```typescript
export interface AashaExperienceContract {
  mount(container: HTMLElement, config?: Record<string, any>): Promise<void>;
  getState(): Record<string, any>;
  setState(state: Record<string, any>): void;
  pause(): void;
  resume(): void;
  reset(): void;
  destroy(): void;
  onTelemetry(callback: (event: AashaTelemetryEvent) => void): void;
}
```

### `<aasha-sim>` Custom Element Implementation
```html
<aasha-sim 
  data-foundation="F04_PHET_SPRING" 
  data-adapter="ParameterizedSpringAdapter"
  data-aspect-ratio="16:9">
  <div class="sim-stage-container"></div>
</aasha-sim>
```
* **Event Dispatching:** Simulations bubble two standardized CustomEvents:
  1. `aasha:telemetry`: Emitted on meaningful student actions (slider move, toggle switch, test run).
  2. `aasha:state_change`: Emitted on state mutations to maintain synchronous DOM binding with accompanying readouts.

---

## 5. Security, Trust Boundary & Cryptographic Verification

### 5.1. HMAC Scoped Signing Key Enforcement
Release certification and registry promotion are cryptographically gated:
* **Environment Variable:** `AASHA_HIL_TRUSTED_KEYS_JSON` containing key IDs and HMAC-SHA256 secrets.
* **Payload Verification:** Signatures are computed over `SHA-256(canonical_ir) + SHA-256(contract_yaml) + SHA-256(ltruth_report)`.
* **Fail-Closed Gate:** If `AASHA_HIL_TRUSTED_KEYS_JSON` is missing or keys are invalid, the build exits with `QUARANTINE_ERROR` and status remains `CONDITIONAL / BLOCKED FOR RELEASE CERTIFICATION`.

### 5.2. Headless Chrome CDP Evaluation Scope Invariant
To prevent `Identifier has already been declared` syntax crashes across sequential DevTools evaluations:
* All scripts executed via `Runtime.evaluate` over CDP must be wrapped inside an IIFE:
  ```javascript
  (() => {
    const targetElement = document.querySelector('#section-warmup');
    return targetElement ? targetElement.clientHeight : 0;
  })();
  ```
