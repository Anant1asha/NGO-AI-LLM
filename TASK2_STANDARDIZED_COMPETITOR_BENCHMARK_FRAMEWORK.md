# AASHA AIOS — MULTI-DIMENSIONAL COMPETITOR BENCHMARK SPECIFICATION & RECONSTRUCTION

**Directive Ref**: `AASHA_TASK2_R2G_DELIVERY_CAPABILITY_REVIEW`  
**Deliverable ID**: `TASK2_STANDARDIZED_COMPETITOR_BENCHMARK_FRAMEWORK.md`  
**Evaluation Standard**: 8 Weighted Dimensions (100% Total) separating Runtime, Authoring & Delivery  
**Date**: 2026-11-06  

---

## 1. Weighted Evaluation Framework (3 Distinct Questions)

To eliminate the methodological bias of comparing raw generation time against polished multi-year runtime applications, the benchmark is strictly separated into three independent evaluation planes:
1. **Runtime Capability**: How well does the simulation function for a child in a classroom?
2. **Authoring & Generation Capability**: How much time, cost, and human effort is needed to create a new simulation?
3. **Delivery & Deployment Capability**: Can it execute completely offline on low-cost rural hardware within byte budgets?

```
+-----------------------------------------------------------------------------------------------+
| WEIGHTED BENCHMARK DIMENSIONS (100% TOTAL)                                                    |
+-------------------------------------------------------------------+---------+-----------------+
| Dimension                                                         | Weight  | Category        |
+-------------------------------------------------------------------+---------+-----------------+
| 1. Learning and Mathematical Correctness                           | 20%     | Runtime         |
| 2. Interaction and Simulation Depth                               | 15%     | Runtime         |
| 3. Visual Quality and Clarity                                     | 10%     | Runtime         |
| 4. Generation and Authoring Efficiency                            | 15%     | Authoring       |
| 5. Offline and Low-End Device Performance                         | 15%     | Delivery        |
| 6. Accessibility and Touch Compliance                             | 10%     | Delivery        |
| 7. Reusability and Extensibility                                  | 5%      | Authoring       |
| 8. Reliability, Security and Lifecycle Management                 | 10%     | Delivery        |
+-------------------------------------------------------------------+---------+-----------------+
```

---

## 2. Rigorous Scoring Rubric & Measurement Standards

Each dimension is scored from 0 to 10 based on reproducible, empirical criteria:

### Dim 1: Learning and Mathematical Correctness (20% Weight)
- **10**: Verified by deterministic mathematical oracles; bounds strictly clamped; curriculum-aligned (NCERT/Ganita Prakash); zero mathematical hallucinations or drift.
- **7**: High mathematical accuracy, but occasional floating-point rounding quirks or manual authoring error risk.
- **4**: Visual approximation only; lacks underlying formal mathematical state model.
- **0**: Unbounded or mathematically invalid state transitions.

### Dim 2: Interaction and Simulation Depth (15% Weight)
- **10**: Multi-step tactile manipulation (*Kriyātmaka Bodha*); reversible exploration (peeling, slicing, parameter tuning); dynamic feedback.
- **7**: Rich interactive controls, but linear progression with limited exploratory freedom.
- **4**: Click-to-advance or simple form inputs.
- **0**: Static or animated non-interactive display.

### Dim 3: Visual Quality and Clarity (10% Weight)
- **10**: Consistent 60 FPS rendering; crisp vector/Canvas graphics on high-DPI displays; high-contrast pedagogical color palette.
- **7**: Smooth rendering, but visual clutter or occasional frame drop during resize.
- **4**: Low-resolution raster assets or aliased rendering.
- **0**: Janky rendering (< 30 FPS) or broken layout.

### Dim 4: Generation and Authoring Efficiency (15% Weight)
- **10**: Automated, reproducible synthesis from standard curriculum contracts in $< 30$ seconds at zero incremental marginal cost.
- **7**: Semi-automated authoring using graphical builders taking $< 2$ hours per module.
- **4**: Manual coding required using specialized SDKs (2–4 weeks per module).
- **0**: Complex monolithic software engineering requiring multiple months and specialized simulation developer teams.

### Dim 5: Offline and Low-End Device Performance (15% Weight)
- **10**: 100% standalone single-file bundle; zero external network requests; total bundle $< 20$ MiB; RAM footprint $< 50$ MB; CPU usage $< 15\%$ on low-end ARM chips.
- **7**: Runs offline if pre-cached, but requires 5–15 MB runtime bundles; moderate memory footprint (100–200 MB).
- **4**: Heavy local runtime; sluggish on entry-level Android tablets.
- **0**: Hard cloud dependency; fails immediately when disconnected from internet.

### Dim 6: Accessibility and Touch Compliance (10% Weight)
- **10**: All interactive touch targets measure $\ge 44 \times 44$ CSS pixels verified in real browser layout; WCAG 2.1 AA contrast ($\ge 4.5:1$); screen-reader ARIA live announcements; keyboard navigable.
- **7**: Good touch targets on mobile, but lacks complete ARIA live readouts or keyboard traps present.
- **4**: Desktop-centric small controls (< 30px); poor contrast.
- **0**: Touch inaccessible.

### Dim 7: Reusability and Extensibility (5% Weight)
- **10**: Standard Web Component architecture (`<aasha-sim>`); standard lifecycle contract (`mount`, `reset`, `destroy`); modular headless math core.
- **7**: Modular library, but tight coupling to a proprietary runtime framework.
- **4**: Monolithic applet architecture; difficult to embed or extract.
- **0**: Completely closed, non-reusable binary blob.

### Dim 8: Reliability, Security and Lifecycle Management (10% Weight)
- **10**: Zero XSS sinks (no raw `innerHTML` interpolation); complete event listener cleanup on detach (`AbortController`); isolated telemetry bus (`try/catch`); clean AudioContext disposal.
- **7**: Secure DOM handling, but minor listener accumulation across rapid unmounts.
- **4**: Vulnerable to script injection or crashes parent page on telemetry failure.
- **0**: Critical DOM XSS or unhandled exceptions that break host application.

---

## 3. Comparative Evaluation: Existing Products vs. AASHA Baseline & Target

| Benchmark Dimension | Weight | PhET (HTML5) | GeoGebra (Web) | Desmos (Studio) | H5P (Widgets) | AASHA (Current Baseline `7cd1e9b`) | AASHA (Target Post-Remediation) |
|---|---|---|---|---|---|---|---|
| **1. Math Correctness** | 20% | 10 (2.0) | 10 (2.0) | 10 (2.0) | 7 (1.4) | **9 (1.8)** *(Oracles pass, but D-03 disconnects cube)* | **10 (2.0)** |
| **2. Interaction Depth** | 15% | 10 (1.5) | 9 (1.35) | 9 (1.35) | 5 (0.75) | **7 (1.05)** *(Gnomon peels, slice not yet wired)* | **9 (1.35)** |
| **3. Visual Quality** | 10% | 9 (0.9) | 8 (0.8) | 10 (1.0) | 7 (0.7) | **8 (0.8)** *(Canvas 2D dot grids, v6 visual math)* | **9 (0.9)** |
| **4. Authoring Efficiency**| 15% | 2 (0.3) | 6 (0.9) | 6 (0.9) | 7 (1.05) | **9 (1.35)** *(1.10s local synthesis, zero token)* | **10 (1.5)** |
| **5. Offline / Low-End** | 15% | 6 (0.9) | 6 (0.9) | 0 (0.0) | 7 (1.05) | **9 (1.35)** *(13.9 KB script, 203 KB v6 bundle)* | **10 (1.5)** |
| **6. Touch & Accessibility**| 10% | 10 (1.0) | 6 (0.6) | 9 (0.9) | 7 (0.7) | **5 (0.5)** *(CSS declared, CDP layout unverified E-01)*| **10 (1.0)** |
| **7. Reusability** | 5% | 7 (0.35) | 6 (0.3) | 4 (0.2) | 8 (0.4) | **8 (0.4)** *(Web Component <aasha-sim>, F01-F20)* | **10 (0.5)** |
| **8. Reliability & Security**| 10% | 10 (1.0) | 8 (0.8) | 9 (0.9) | 8 (0.8) | **4 (0.4)** *(D-01 leak, D-02 XSS sink)* | **10 (1.0)** |
| **TOTAL WEIGHTED SCORE** | **100%**| **7.95 (79.5%)**| **7.65 (76.5%)**| **7.25 (72.5%)**| **6.85 (68.5%)**| **6.65 (66.5%)** | **9.25 (92.5%)** |

---

## 4. Methodological Findings & Honest Assessment

1. **Rejection of the Inflationary 84.2% Rating**:
   - When evaluating AASHA against the rigorous, weighted standard that penalizes unresolved security defects (D-02) and lifecycle memory leaks (D-01), **AASHA's true current baseline score is 66.5% (Grade D+)**.
   - Claiming an "A-" while shipping an active DOM XSS sink (`innerHTML = ${SPEC.title}`) and an unconnected 3D simulation adapter (`D-03`) is invalid.
2. **Competitor Realities**:
   - **PhET** achieves a top-tier runtime score (79.5%), but is severely dragged down in authoring efficiency (2/10) because each simulation requires 3–6 months of human software engineering and generates 5–18 MB bundles.
   - **Desmos** provides world-class visual polish (10/10), but completely fails the rural deployment requirement (0/10 offline score due to hard cloud dependency).
   - **AASHA's Real Competitive Edge**: If and only if the four remediation gates are executed, AASHA's score elevates to **92.5% (Grade A+)**, combining automated 1.1s generation with single-file, 200 KB offline delivery and mathematically certified oracles.
