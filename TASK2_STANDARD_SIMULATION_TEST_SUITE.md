# AASHA AIOS — STANDARD SIMULATION TEST SUITE SPECIFICATION

**Directive ID**: `AASHA_TASK2_R2G_DELIVERY_CAPABILITY_AND_COMPETITOR_BENCHMARK`  
**Deliverable ID**: `TASK2_STANDARD_SIMULATION_TEST_SUITE.md`  
**Standard**: Multi-Tier Verification (Headless Math Oracles $\to$ Custom Element Lifecycle $\to$ Live Browser Layout)  
**Date**: 2026-11-06  

---

## 1. Test Suite Architecture

The AASHA Simulation Test Suite is organized into three distinct verification tiers:

```
[Tier 1: Pure Headless Math Oracles] ──> Node.js pure ES math models (SquareGnomon, IsoCube)
[Tier 2: Component Lifecycle & Security] ──> Custom element DOM simulation (DOM XSS, memory leak, telemetry)
[Tier 3: Live Browser CDP Layout] ──> Real Headless Chrome (44x44px bounding box, offline emulation)
```

---

## 2. Standard 8 Curriculum Scenarios & Acceptance Criteria

| Scenario ID | Topic & Concept | Grade / Board | Mathematical Invariant & Oracle | Primary Renderer | Audio Event | Acceptance Gate |
|---|---|---|---|---|---|---|
| **SCN-01** | **Square Gnomon Peeling** | Class 8 (NCERT) | $s^2 = \sum_{k=1}^s (2k-1)$; active area $(s-p)^2$; gnomon $2(s-p)-1$. | Canvas 2D + SVG controls | Harmonic pitch scale per side $s$; click on peel | $s \in [1, 10]$; peel clamp $[0, s-1]$. |
| **SCN-02** | **Isometric Cube Slicing** | Class 8 (NCERT) | $n^3 = \sum_{k=0}^{n-1} (n(n-1)+1+2k)$; volume $n^3$. | Canvas 2D isometric projection | Chime on slice toggle; bass tone on $n$ change | $n \in [1, 5]$; layer gap on slice. |
| **SCN-03** | **Fraction Strip Equivalence** | Class 6 (NCERT) | $\frac{a}{b} = \frac{c}{d} \iff ad = bc$; unit bar partitioning. | DOM / SVG interactive bars | Snap tone on equal alignment | Strip width ratio $\le 1.0$. |
| **SCN-04** | **Solar System Orbital Motion** | Class 8 (NCERT) | Kepler's 3rd Law: $T^2 \propto r^3$; relative orbital speeds. | Canvas 2D procedural orbit loop | Ambient orbital hum (gated) | Zero drift over 1000 frames. |
| **SCN-05** | **Plant Cell Anatomy** | Class 8 (NCERT) | Discrete cell part targeting (Cell wall, Vacuole, Chloroplast). | SVG clickable layered paths | Click pop on organelle selection | 100% hit test accuracy. |
| **SCN-06** | **Water Cycle Evaporation** | Class 7 (NCERT) | Conservation of water mass: $M_{\text{total}} = M_{\text{liquid}} + M_{\text{vapor}}$. | Canvas 2D particle simulation | Soft white noise on phase transition | Particle bounds clamp $[0, W] \times [0, H]$. |
| **SCN-07** | **Triangle Angle Sum Theorem** | Class 7 (NCERT) | $\angle A + \angle B + \angle C = 180^\circ$ for all drag coordinates. | SVG draggable vertex handles | Chime when angle sum snaps to $180^\circ$ | Vertex drag handles $\ge 44 \times 44$px. |
| **SCN-08** | **Series / Parallel Circuit** | Class 8 (NCERT) | Ohm's Law: $I = \frac{V}{R}$; current loop continuity. | Canvas 2D electron flow | Switch click sound | Current drop on open switch. |

---

## 3. Automated Test Specifications for Task 2 Active Scope

### Test 1: Mathematical Oracle Unit Tests (`simulation_subagent.test.mjs`)
- **Status**: Implemented & Passing (11/11 tests).
- **Checks**:
  - `SquareGnomonModel`: Formula validation, active area peeling, odd sequence generation, out-of-bounds input clamping.
  - `IsometricCubeModel`: Formula validation, volume calculation, consecutive odds generation, slicing toggle.

### Test 2: Security & DOM XSS Injection Test (To Add in Sub-Scope A1)
- **Target**: `packages/aasha-agent-builder/test/simulation_subagent.test.mjs`
- **Specification**:
  ```javascript
  test('generateSimulationScript sanitizes XSS in concept title and script JSON', () => {
    const maliciousTitle = 'Squares <script>window.__xss=true</script><img src=x onerror=alert(1)>';
    const spec = { id: 'test_xss', title: maliciousTitle, modelType: 'SquareGnomonModel', initialState: { side: 5 } };
    const script = generateSimulationScript(spec);
    
    // Assert no raw HTML tags in script template
    assert.strictEqual(script.includes('<script>window.__xss'), false);
    assert.strictEqual(script.includes('\\u003cscript\\u003e'), true);
  });
  ```

### Test 3: Custom Element Detach & Lifecycle Cleanup Test (To Add in Sub-Scope A2)
- **Target**: `packages/aasha-agent-builder/test/simulation_subagent.test.mjs`
- **Specification**:
  ```javascript
  test('AashaExperienceAdapter detaches event listeners on destroy using AbortController', () => {
    const adapter = new SquareGnomonSimulationAdapter();
    const mockContainer = createMockContainer();
    adapter.mount(mockContainer, { side: 5 });
    
    assert.strictEqual(adapter._abortController.signal.aborted, false);
    adapter.destroy();
    assert.strictEqual(adapter._abortController.signal.aborted, true);
  });
  ```

### Test 4: Dynamic 3D Isometric Model Dispatch Test (To Add in Batch B)
- **Target**: `packages/aasha-agent-builder/test/simulation_subagent.test.mjs`
- **Specification**:
  ```javascript
  test('simulationSubagent dispatches IsometricCubeSimulationAdapter for 3D concepts', async () => {
    const result = await simulationSubagent({
      conceptText: 'Discovering 3D cube numbers and layer slicing',
      contractData: { chapter_meta: { slug: 'cubes' } }
    });
    assert.strictEqual(result.simulationSpec.modelType, 'IsometricCubeModel');
    assert.strictEqual(result.clientScript.includes('IsometricCubeSimulationAdapter'), true);
    assert.strictEqual(result.clientScript.includes('SquareGnomonSimulationAdapter'), false);
  });
  ```

### Test 5: Headless Chrome CDP Live Layout & Offline Test (To Add in Batch C)
- **Target**: `packages/aasha-agent-builder/test/simulation_browser_cdp.test.mjs`
- **Specification**:
  ```javascript
  test('Rendered touch targets measure >= 44x44 CSS pixels in live Headless Chrome', async () => {
    const browser = await launchHeadlessChrome();
    const page = await browser.newPage();
    await page.setContent(renderedHtmlBundle);
    
    const buttonBoxes = await page.evaluate(() => {
      const els = document.querySelectorAll('button, input[type=range]');
      return Array.from(els).map(el => {
        const r = el.getBoundingClientRect();
        return { tag: el.tagName, width: r.width, height: r.height };
      });
    });
    
    for (const box of buttonBoxes) {
      assert.ok(box.width >= 44, `Target width ${box.width} < 44px on ${box.tag}`);
      assert.ok(box.height >= 44, `Target height ${box.height} < 44px on ${box.tag}`);
    }
    await browser.close();
  });
  ```
