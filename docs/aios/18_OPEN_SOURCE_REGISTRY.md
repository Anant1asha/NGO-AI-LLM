# 18_OPEN_SOURCE_REGISTRY.md
# Open-Source Component & Manipulative Registry

**Strategy**: REUSE BEFORE REBUILD.  
Every external library must be strictly evaluated for offline capability, base64 embeddability, mobile touch compatibility, and license compatibility before inclusion.

### Classification Scheme
- **Class A**: DIRECTLY REUSABLE (Permissive license, fully offline, standalone embeddable, low footprint).
- **Class B**: REUSABLE WITH ADAPTATION (Requires tree-shaking, transpilation, or wrapper adaptation).
- **Class C**: REFERENCE ONLY (Architecture/algorithms useful, but cannot be distributed inline due to licensing or weight).
- **Class D**: REJECT (Violates offline, license, or mobile constraints).

---

## Registry of Evaluated Components

| Component | Repository / Source | License | Classification | Size (Inlined) | Offline / Standalone Fit | Educational Purpose | Notes & Constraints |
| :--- | :--- | :--- | :---: | :--- | :---: | :--- | :--- |
| **JSXGraph** | jsxgraph.uni-bayreuth.de | **LGPL-3.0 / MIT (Dual)** | **Class A** | ~200 KB | Excellent | Dynamic geometry, function plotting, coordinate planes | Used in Class 10 Polynomials chapter. High mathematical fidelity. |
| **Mafs** | github.com/stevenpetryk/mafs | **MIT** | **Class A** | ~150 KB | Excellent | Reactive math visualizer, vectors, curves | Highly modular React/SVG components. Modern, accessible. |
| **Mermaid.js** | github.com/mermaid-js/mermaid | **MIT** | **Class B** | ~150 KB | Good | Flowcharts, state diagrams, concept hierarchies | Requires headless compilation to static SVG to avoid client JS bloat. |
| **Fabric.js** | github.com/fabricjs/fabric.js | **MIT** | **Class B** | ~300 KB | Good | Interactive biology anatomy labeling, touch hotspots | Touch events must be tuned for Android WebView responsiveness. |
| **H5P Core** | github.com/h5p/h5p-core | **MIT** | **Class B** | ~500 KB | Moderate | Branching scenarios, interactive sorting | Heavy runtime; extract individual interaction algorithms rather than full player. |
| **PhET Simulations**| github.com/phetsims | **GNU GPL v3** | **Class C** | ~50 KB (core logic) | Requires Isolation | Physics, chemistry, circuit simulations | **Licensing Warning**: GPL v3 requires copyleft compliance. Must NOT be inlined into MIT chapters without clear license boundary. |
| **GeoGebra** | geogebra.org | **Non-Commercial Creative Commons** | **Class C** | ~800 KB | Poor (Heavy) | Geometry, 3D shapes, calculus | **Strict Warning**: Non-commercial license creates distribution risks for NGO open-access scale. Replace with JSXGraph/Mafs. |
| **Hot Potatoes**| halfbakedsoftware.com | **GPL** | **Class C** | ~50 KB | Moderate | JQuiz, JMatch matching exercises | Reference only for interactive quiz templates. Built-in assessment engine supersedes it. |
| **PyMuPDF (fitz)**| github.com/pymupdf/PyMuPDF | **AGPL-3.0 / Commercial** | **Class B** | Server CLI | Pipeline Backend | Deterministic PDF text, layout, and image extraction | Used strictly on operator backend/CLI; never bundled into client HTML. |
| **jsdom** | github.com/jsdom/jsdom | **MIT** | **Class A** | Node devDep | QA Harness | Headless browser rendering for DOM verification | Powers the automated 200+ check L-Truth verification harness. |
| **Fastify** | github.com/fastify/fastify | **MIT** | **Class A** | Node server | Backend Service | Lightweight telemetry outbox sync API | High performance, low memory footprint. |

---

## Approved Reuse Protocol
Before adding any new dependency:
1. Search registry above.
2. If absent, evaluate against the 18 criteria.
3. Obtain written approval from Project Architect if component is Class B or C.
4. Class D candidates are permanently barred from the repository.
