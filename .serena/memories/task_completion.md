# Task Completion Criteria

To declare a chapter or core engine task complete, the following verification gates must pass:
1. **L-Truth Benchmark**: Run `node benchmarks/qa_ltruth_benchmark.js`. Must score 100/100 with 0 spoilers and 0 math-rt collisions.
2. **Headless Chrome CDP Verification**: Run CDP verification script (`automated_browser_verification.js`). Must verify 0 console errors, 100% word-tap modal popups, valid canvas renders, and mobile viewport bounds (`scrollH <= winH + 5`).
3. **Graphify Sync**: Run `graphify update .` to ensure the project knowledge graph reflects all AST additions.
