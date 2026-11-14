# Task Completion Criteria

To declare a chapter or core engine task complete, the following verification gates must pass:
1. **L-Truth Benchmark**: Run `node benchmarks/qa_ltruth_benchmark.js`. Must score 100/100 with 0 spoilers and 0 math-rt collisions.
2. **Headless Chrome CDP & Physical Ergonomics**: Run CDP verification script (`scripts/verify_gold_standard_cdp.mjs` or `automated_browser_verification.js`). Must verify 0 console errors, 100% word-tap modal popups, valid 60 FPS canvas/manipulative renders, mobile viewport bounds (`scrollH <= winH + 5`), and strict touch target clamping (0 violations < 44x44px).
3. **Dual-Layer Language Learning Experience (LLE)**: Must verify word-level phonics + Hindi translation modals and full sentence-level Hindi translation box toggles (`.hiBtn` -> `.hiBox`).
4. **Scope-Locked Offline Bundle Integrity**: Single-file deliverable must remain strictly <= 20 MiB with zero external CDN scripts, remote fonts, or network requests.
5. **Open-Source Harvesting 5-Point Quality Gate**: Any imported open-source foundation or interactive component must pass: (1) Zero external network calls, (2) Local/inlined dependencies, (3) >=44px mobile touch ergonomics, (4) Dual-view viewport clamping (360x640, 390x844, 412x915), (5) AASHA Experience Contract telemetry (`window.AASHA.emit`).
6. **Graphify Sync**: Run `graphify build` or `graphify update .` to ensure the project knowledge graph reflects all AST additions.
