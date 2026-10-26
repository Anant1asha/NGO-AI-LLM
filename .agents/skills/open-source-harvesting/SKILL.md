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
        └── AVR-P401 to AVR-P406 # Harvested and quality-certified labs
```

---

## 3-Tier Resource Library Ingestion & Preservation Standards

Whenever researching, harvesting, or reverse-engineering an upstream open-source educational repository (e.g., KingsMath, CinePhysicsHQ, PhET):

### Tier 1: Raw Harvested Source Ingestion (`external_sources/<library-name>/`)
1. **Permanent Storage**: Raw upstream source code must be stored permanently in `external_sources/<library-name>/` (e.g., `external_sources/kingsmath-web-games/`), NEVER left only in ephemeral `.scratch/`.
2. **Archive & Nested Zip Scrubbing Rule**:
   - `*.zip` files are strictly blocked by `.gitignore`.
   - When extracting upstream distribution archives into `external_sources/`, filter out all nested `.zip` archives (e.g. internal backup zips in dashboards) to maintain zero-secret and zero-archive git compliance.
3. **Mandatory Provenance Documentation**:
   - Include `README.md` identifying the upstream repository URL, catalog description, and AASHA cleanroom integration role.
   - Include `LICENSE` with verbatim upstream license text (e.g., CC BY-NC 4.0 or MIT) and explicit author attribution.

### Tier 2: Certified Standalone Offline Interactive (`assets/cdn/interactives/`)
1. Refine and package a single-file, 100% offline HTML interactive named with the canonical prefix:
   `assets/cdn/interactives/AVR-P4xx-<name>.html`
2. Ensure zero remote script/link tags, inlined procedural Web Audio synthesis, and standard event bus bindings (`window.AASHA.emit` and `window.__AASHA_EVENTS__`).
3. Compute exact byte size and SHA-256 checksum:
   ```powershell
   python -c "import hashlib, os; path='assets/cdn/interactives/AVR-P4xx.html'; print(os.path.getsize(path), hashlib.sha256(open(path, 'rb').read()).hexdigest())"
   ```

### Tier 3: Reusable Engine Adapter (`Aasha-AI/experience_registry/adapters/`)
1. Synthesize a reusable cleanroom adapter (`aasha_<name>_adapter.js`) implementing `AashaExperienceContract` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`).
2. Register the foundation ID (e.g., `F27`) in `Aasha-AI/experience_registry/registry.json`.

---

## Prestack Manifest & Local CDN Synchronization Workflow
Whenever a new interactive is added to `assets/cdn/interactives/`:
1. **Manifest Registration (`assets/prestack_manifest.json`)**:
   - Add entry under `interactives[]` with `id` (e.g., `AVR-P406`), `name`, `family`, `filename`, `local_cdn_path`, `bundle_bytes`, `sha256`, `ceiling_bytes: 20971520`, `offline_certified: true`, `subject`, `classes`, `topics`, `board`, `contract`, `license`, `provenance`, and `foundation_source`.
   - Increment `statistics.interactives_count`.
   - Update `statistics.total_interactives_bundle_bytes` ($+ \text{bundle\_bytes}$).
2. **Documentation Sync (`assets/README.md`)**:
   - Add the interactive under `assets/cdn/interactives/` file list.
   - Update the **Catalog Summary** counts (`Certified Ingested Interactives` and `Prebuilt Experience Foundations`).
3. **Automated Verification Suite (`Aasha-AI/tests/verify_*_integration.js`)**:
   - Assert `external_sources/<name>/` exists with expected file and directory counts.
   - Assert `assets/cdn/interactives/AVR-P4xx.html` exists and is indexed in `prestack_manifest.json`.

