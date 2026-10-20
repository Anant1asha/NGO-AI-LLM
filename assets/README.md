# AASHA AIOS — Local CDN, Open-Source Harvesting & Asset Orchestration Repository

## Overview
This directory serves as the **Global DB, Local CDN & Continuous Open-Source Research Harvesting Engine** for the AASHA Learning Ecosystem.
It delivers 100% offline-first educational interactives, simulation foundations, and runtime substrates for any school, any board (CBSE, ICSE, NCERT, State Boards), and any class (Class 1–12).

---

## Architectural Principle: Runtime Zero CDN vs. Continuous Harvesting
1. **Runtime Zero CDN Guarantee**: Classrooms, offline tablet distributions, and student web views load **exclusively from the Local CDN** (`assets/cdn/interactives/` and `assets/cdn/vendor/`). At runtime, there are zero external network calls, zero CDN script/link tags, and zero telemetry trackers.
2. **Continuous Open-Source Research & Harvesting Engine**: The ecosystem is **not limited** to static assets. It continuously searches, researches, harvests, and refines open-source source code and tools from the broader ecosystem (e.g., **PhET Interactive Simulations**, **JSXGraph**, **KingsMath**, **CinePhysicsHQ-Labs**, **GeoGebra**, **Escapp**, **Code for Life**).
3. **Automated 5-Point Quality Gate**: Every harvested asset must pass an automated 5-point quality gate before admission into the Local CDN and Global Manifest.

---

## 5-Point Automated Quality Gate
Before any asset is admitted into `assets/cdn/interactives/`, the automated pipeline audits:
1. **100% Offline Integrity**: Zero remote script/link tags (`http://`, `https://`, `//`). All third-party telemetry (Google Tag Manager, Google Analytics) is stripped and replaced with AASHA's local privacy-safe event bus.
2. **Strict Bundle Ceiling**: Each interactive must remain under 20MB (typical size is < 200KB; AVR-P301–P321 are < 3KB each).
3. **License Isolation & Cleanroom Compliance**: Permissively licensed assets (MIT, Apache 2.0) are incorporated directly. Copyleft foundations (GPL-3.0, such as PhET or Escapp) strictly use the `EXTRACT` or `INSPIRE` cleanroom strategy, wrapped in `<aasha-sim>` Web Component adapters to prevent copyleft contagion.
4. **Same-Frame Mobile Viewport Clamping**: Evaluated in Headless Chrome at 390x844 mobile viewport. Zero horizontal overflow, minimum touch target size $\ge 44 \times 44\text{px}$.
5. **AashaExperienceContract Compliance**: Full event telemetry bridge (`window.AASHA.emit` and `window.__AASHA_EVENTS__`), lifecycle hooks (`mount`, `reset`, `destroy`), and state isolation.

---

## Directory Structure
```
assets/
├── prestack_manifest.json       # Master Global DB index of all prestacked assets with sha256 checksums
├── README.md                    # This architecture and operational specification
└── cdn/
    ├── vendor/                  # Offline Local CDN Vendor Library
    │   ├── chart.umd.min.js     # Chart.js (MIT) — offline scientific plotting & regression
    │   ├── tex-chtml.js         # MathJax 3 (Apache-2.0) — offline LaTeX math typography
    │   ├── katex.min.js         # KaTeX (MIT) — ultra-fast math typesetting
    │   └── katex.min.css        # KaTeX styles
    └── interactives/            # Certified Standalone Visual Interactives (100% Offline)
        ├── AVR-P301-number-line-marker.html        (Mathematics, Cl 1-8)
        ├── AVR-P302-fraction-strip.html            (Mathematics, Cl 2-7)
        ├── AVR-P303-shape-transformer.html         (Mathematics, Cl 4-9)
        ├── AVR-P304-timeline-scrubber.html         (Cross-Curricular, Cl 3-10)
        ├── AVR-P305-process-branch.html            (Science, Cl 5-10)
        ├── AVR-P306-hotspot-reveal.html            (Science, Cl 4-10)
        ├── AVR-P307-layer-reveal.html              (Science, Cl 5-12)
        ├── AVR-P308-node-connector.html            (Biology, Cl 6-12)
        ├── AVR-P309-grid-coordinate-picker.html    (Mathematics, Cl 5-10)
        ├── AVR-P310-distance-ruler.html            (Mathematics, Cl 2-7)
        ├── AVR-P311-particle-temperature.html      (Chemistry, Cl 6-11)
        ├── AVR-P312-particle-diffusion.html        (Chemistry, Cl 7-12)
        ├── AVR-P313-atom-builder.html              (Chemistry, Cl 8-11)
        ├── AVR-P314-switch-circuit.html            (Physics, Cl 6-12)
        ├── AVR-P315-logic-gate.html                (Physics, Cl 9-12)
        ├── AVR-P316-system-flow.html               (Physics, Cl 6-12)
        ├── AVR-P317-parameterized-spring.html      (Physics, Cl 8-11)
        ├── AVR-P318-population-growth.html         (Biology, Cl 8-12)
        ├── AVR-P319-projectile-explorer.html       (Physics, Cl 9-11)
        ├── AVR-P320-bar-data-manipulator.html      (Mathematics, Cl 4-10)
        ├── AVR-P321-cause-effect-reveal.html       (Cross-Curricular, Cl 4-10)
        ├── AVR-P401-vernier-caliper-virtual-lab.html   (Physics, Cl 9-11)
        ├── AVR-P402-magnetic-lorentz-force-simulator.html (Physics, Cl 11-12)
        ├── AVR-P403-error-analysis-virtual-lab.html      (Physics, Cl 11-12)
        ├── AVR-P404-dimensional-analysis-virtual-lab.html(Physics, Cl 11)
        └── AVR-P405-ten-frame-place-value-mastery.html   (Mathematics, Cl 1-4)
```

---

## Catalog Summary
- **Certified Ingested Interactives**: 26 HTML5 simulations (21 core AVR-P301–P321 + 5 harvested labs AVR-P401–P405)
- **Prebuilt Experience Foundations**: 26 cataloged open-source foundations (F01–F26: PhET, KingsMath, JSXGraph, Escapp, QuestJS, Lightbot, CinePhysicsHQ, etc.)
- **Harvest Research Candidates**: 40 mapped candidate patterns (HARV-0001–HARV-0040)
- **Core Shared Substrates**: 4 offline substrates (KaTeX math, Indic dictionary, Web Audio tone synthesizer, Local Vendor chart/math cache)

---

## CLI & Pipeline Commands
```bash
# 1. Search the Open-Source Research Catalog across Foundations & Candidates:
npm run harvest:search -- "phet"
npm run harvest:search -- "kingsmath"
npm run harvest:search -- "lorentz"
npm run harvest:search -- "fractions"

# 2. Run the Continuous Harvesting, Refinement & Quality Gate Pipeline:
npm run harvest:run

# 3. Verify Local Vendor Library Dependencies:
npm run harvest:vendor

# 4. Re-orchestrate Prestack Manifest & Curricular Mapping:
npm run assets:orchestrate

# 5. Run Full Automation Headless Chrome CDP Verification:
npm run test:browser
npm run test:browser -- --file AVR-P402-magnetic-lorentz-force-simulator.html
npm run test:browser -- --file AVR-P403-error-analysis-virtual-lab.html
```
