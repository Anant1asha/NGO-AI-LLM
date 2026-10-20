---
name: open-source-harvesting
description: >-
  Autonomous open-source educational asset research, harvesting, refinement,
  and 5-point quality gate certification pipeline for AASHA AIOS (PhET,
  JSXGraph, KingsMath, CinePhysicsHQ, GeoGebra, Escapp).
---

# Open-Source Harvesting & Quality Gate Engine

An autonomous procedural runbook for researching, extracting, refining, and admitting open-source educational simulations, visual interactives, and scientific tools into the AASHA Local CDN (`assets/cdn/interactives/`), Local Vendor Library (`assets/cdn/vendor/`), and Global Prestack Manifest (`assets/prestack_manifest.json`).

---

## Architectural Guarantees & Dual-Mode Scope

1. **Runtime Zero-CDN Isolation**: Classrooms, offline tablet distributions, and student web views load **exclusively from the Local CDN and Local Vendor Library**. At runtime, there are zero external network calls, zero CDN script/link tags, and zero telemetry trackers.
2. **Continuous Research & Growth**: The ecosystem is not limited to a static catalog. It actively searches and harvests from **PhET Interactive Simulations**, **JSXGraph**, **KingsMath**, **CinePhysicsHQ-Labs**, **GeoGebra**, **Escapp**, and **Code for Life**.
3. **Automated 5-Point Quality Gate**: Every harvested asset must pass an automated 5-point quality gate before admission into the Local CDN and Global Manifest.

---

## The 5-Point Automated Quality Gate

Before any asset is admitted into `assets/cdn/interactives/`, the automated pipeline audits:

1. **100% Offline Integrity**:
   - Zero remote script/link tags (`http://`, `https://`, `//`).
   - All third-party telemetry (Google Tag Manager, Google Analytics, social share intents) is stripped and replaced with AASHA's local privacy-safe event bus (`window.AASHA.emit`).
2. **Strict Bundle Ceiling**:
   - Each interactive must remain strictly under 20MB (typical size is < 200KB; core AVRs are < 3KB each).
3. **License Isolation & Cleanroom Compliance**:
   - Permissively licensed assets (MIT, Apache 2.0) are incorporated directly with attribution.
   - Copyleft foundations (GPL-3.0, such as PhET or Escapp) strictly follow the `EXTRACT` or `INSPIRE` cleanroom strategy, extracting mathematical equations and mechanics wrapped in `<aasha-sim>` Web Component adapters to prevent copyleft contagion into core modules.
4. **Same-Frame Mobile Viewport Clamping**:
   - Evaluated in Headless Chrome at 390x844 mobile viewport.
   - Zero horizontal overflow, minimum touch target size $\ge 44 \times 44\text{px}$.
5. **AashaExperienceContract Compliance**:
   - Full event telemetry bridge (`window.AASHA.emit` and `window.__AASHA_EVENTS__`).
   - Standard lifecycle hooks (`mount`, `reset`, `destroy`) and state isolation.

---

## Refinement & Localization Pipeline

When raw source code is ingested from `external_sources/` or upstream repositories, `scripts/harvest_engine.mjs` executes:

1. **Tracker Stripping**: Removes `<script src="...googletagmanager.com...">` and `gtag()` initialization blocks.
2. **Dependency Localization**: Rewrites remote CDN tags (`https://cdn.jsdelivr.net/...`) to local vendor paths:
   - Chart.js $\rightarrow$ `../vendor/chart.umd.min.js`
   - MathJax $\rightarrow$ `../vendor/tex-chtml.js`
   - KaTeX $\rightarrow$ `../vendor/katex.min.js` and `../vendor/katex.min.css`
3. **Metadata Sanitization**: Replaces external OpenGraph URLs or placeholder images with SVG data URIs and `aasha://sim/<ID>` internal identifiers.
4. **Responsive Meta Injection**: Ensures `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">` is present.
5. **Telemetry Bridge Injection**: Automatically binds `window.AASHA` and auto-emits `SIMULATION_MOUNT` on `DOMContentLoaded`.

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

---

## Directory Organization

```
assets/
├── prestack_manifest.json       # Master Global DB index of all prestacked assets with sha256 checksums
├── README.md                    # Architecture and operational specification
└── cdn/
    ├── vendor/                  # Offline Local CDN Vendor Library
    │   ├── chart.umd.min.js     # Chart.js (MIT) — offline scientific plotting & regression
    │   ├── tex-chtml.js         # MathJax 3 (Apache-2.0) — offline LaTeX math typography
    │   ├── katex.min.js         # KaTeX (MIT) — ultra-fast math typesetting
    │   └── katex.min.css        # KaTeX styles
    └── interactives/            # Certified Standalone Visual Interactives (100% Offline)
        ├── AVR-P301 to AVR-P321 # Core AVR interactives
        └── AVR-P401 to AVR-P405 # Harvested and quality-certified labs
```
