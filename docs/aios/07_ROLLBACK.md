# 07_ROLLBACK.md
# Rollback Procedures & Recovery Protocols

To maintain a way back at all times, every structural, schema, or configuration modification must define a verified rollback path prior to execution.

---

## 1. Active Rollback Protocols

### Protocol RB-001: Chapter Template Compiler Rollback
- **CHANGE**: Upgrading `v5-engine-template.html` or injecting new global scripts into chapter compiler.
- **RISK**: High (can corrupt all newly generated standalone chapters or break compatibility with Android WebViews).
- **BASELINE**: Stable v5 production template (`aasha-pipeline-with-master-json/template/v5-engine-template.html`).
- **AFFECTED FILES**:
  - `aasha-pipeline-with-master-json/template/v5-engine-template.html`
  - `aasha-pipeline-with-master-json/src/compiler.py`
- **ROLLBACK METHOD**:
  1. Revert `v5-engine-template.html` via Git to baseline commit.
  2. Regenerate test chapters: `python test_synthesizer_runner.py`.
  3. Re-run QA suite: `node qa/qa_ltruth_benchmark.js`.
- **DATA ROLLBACK**: N/A (Compiler is stateless).
- **CONFIG ROLLBACK**: Restore `config.yaml`.
- **POST-ROLLBACK TEST**: Run `node qa/qa_ltruth_benchmark.js` and verify PASS on `Perimeter_Area_Gamified_v5.html`.
- **IRREVERSIBLE ACTIONS**: None.

---

### Protocol RB-002: Assessment Engine Two-Tier Attempt Schema Rollback
- **CHANGE**: Modifying the scoring weights (e.g. altering 60% historical + 40% recent ratio or attempt tracking structure).
- **RISK**: High (affects student diagnostic accuracy and outbox sync payloads).
- **BASELINE**: `Aasha-Learning-Impact-Ecosystem-v0.3-full-repo` test suite passing at 16/16.
- **AFFECTED FILES**:
  - `packages/assessment-engine/`
  - `packages/event-outbox/`
- **ROLLBACK METHOD**:
  1. Discard working tree changes in `packages/assessment-engine/`.
  2. Run `npm test` from root of ecosystem package.
- **DATA ROLLBACK**: If local storage schemas changed, wipe `localStorage` test namespace `aasha_test_state`.
- **CONFIG ROLLBACK**: None.
- **POST-ROLLBACK TEST**: `node --test tests/unit/learner.test.js` must return 16 passing tests.
- **IRREVERSIBLE ACTIONS**: Any remote server telemetry written with mismatched schema; server must version endpoints `/api/v1/` vs `/api/v2/`.

---

### Protocol RB-003: Third-Party Manipulative Reversion
- **CHANGE**: Inlining experimental library (e.g. Scilab or 3D GeoGebra bundle).
- **RISK**: Critical (Causes silent out-of-memory crashes on 1GB RAM devices or license violations).
- **BASELINE**: Core SVG + JSXGraph math manipulative baseline.
- **ROLLBACK METHOD**:
  1. Remove experimental manipulative definition from `aasha-pipeline-with-master-json/schema/visual_registry.json`.
  2. Remove base64 asset injection from compiler.
  3. Recompile affected chapter.
- **POST-ROLLBACK TEST**: Check bundle size `< 500 KB` and verify in headless Chrome via Puppeteer.
- **IRREVERSIBLE ACTIONS**: None.
