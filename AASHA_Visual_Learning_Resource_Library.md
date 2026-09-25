# AASHA Resource Library — Visual Learning, Interactives & Simulations

**Source:** AASHA_Visual_Mass_Harvest_Phase3 (built from AASHA_Visual_Mass_Harvest_Phase3-2.zip — the newer, expanded build; supersedes Phase3.zip, which it extends with 19 additional harvest candidates and a browser smoke-test harness)
**Phase:** AASHA Visual Mass Harvest & Mechanic Extraction — Phase 3
**Pipeline:** Discover > Individualize > Audit > Extract > Normalize > Build > Test > Measure > Certify > Catalogue

**Library stats:** 21 built interactive visual resources (AVR-P301 to AVR-P321); 40 harvest candidates identified; total production bundle 48,887 bytes across all resources (largest single resource 2,678 bytes — far under the 20 MB ceiling); all static checks pass (8/8 per resource); browser certification NOT_CERTIFIED; zero third-party code or assets bundled.

## 1. What this library is

A bank of standalone, single-file HTML interactive resources for AASHA's visual learning layer: manipulatives, reveal diagrams, timelines, simulations, circuit builders, data interactives and more. Each one is AASHA-native original code implementing a mechanic *pattern* harvested from open-source simulation projects (PhET, GeoGebra, myPhysicsLab, all-science-sims, Pashasan, SimuTutor) — no source code or assets were copied from those projects. Every resource is offline-first (no network, zero external URLs/assets) and communicates through the standard AASHA contract.

## 2. The AASHA resource contract (how every resource behaves)

- **TLN (content injection):** the resource receives learning content (concept, objective, parameters) from the Teaching/Learning Network. It renders and supports interaction; it never decides mastery.
- **TEAS (evidence only):** the resource emits learning-evidence events via `AASHA.emit(type, payload)` (recorded in `window.__AASHA_EVENTS__` with a monotonic sequence). Event types: interaction, parameter_change, state_change, reveal, step_change. The assessment engine (TEAS) owns all mastery decisions.
- **LLE (language layer):** locale en-IN with tap-to-reveal mode and injected content; Hindi cues (e.g. देखें, समझें, बदलें, जाँचें) are supported via the LLE fixture contract.
- **Offline:** single-file HTML, zero external URLs, zero external assets, no network required.
- **Bundle:** every resource measured against a 20,971,520-byte ceiling — all pass with kilobytes to spare.
- Each resource ships with machine-readable fixtures: `.tln.json`, `.teas.json`, `.lle.json`, `.license.json`, `.manifest.json`, plus static (`.json`) and JS-syntax (`.js`) tests.

## 3. Built resources (21 interactives)

| Resource ID | Name | Family | Learning area | Bundle (bytes) | Static checks | Offline |
|---|---|---|---|---|---|---|
| AVR-P301 | Number Line Marker | number-line | Mathematics (number sense) | 2416 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P302 | Fraction Strip | number-line | Mathematics (number sense) | 2491 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P303 | Shape Transformer | geometry | Mathematics (geometry) | 2313 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P304 | Timeline Scrubber | timeline | Cross-subject (sequences/history/processes) | 2370 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P305 | Process Branch | process | Science / cross-subject (processes) | 2678 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P306 | Hotspot Reveal | diagram | Science / cross-subject (diagrams) | 2199 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P307 | Layer Reveal | diagram | Science / cross-subject (diagrams) | 2382 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P308 | Node Connector | anatomy | Biology (anatomy) | 2224 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P309 | Grid Coordinate Picker | spatial | Mathematics (spatial reasoning) | 2260 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P310 | Distance Ruler | spatial | Mathematics (spatial reasoning) | 2121 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P311 | Particle Temperature | molecule | Chemistry (atoms & molecules) | 2279 | 8/8 PASS (see audit flag) | Yes (no network, 0 external URLs/assets) |
| AVR-P312 | Particle Diffusion | molecule | Chemistry (atoms & molecules) | 2204 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P313 | Atom Builder | molecule | Chemistry (atoms & molecules) | 2298 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P314 | Switch Circuit | circuit | Physics / CS (electricity & logic) | 2590 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P315 | Logic Gate | circuit | Physics / CS (electricity & logic) | 2333 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P316 | System Flow | circuit | Physics / CS (electricity & logic) | 2210 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P317 | Parameterized Spring | simulation | Physics / science (simulations) | 2311 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P318 | Population Growth | simulation | Physics / science (simulations) | 2317 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P319 | Projectile Explorer | simulation | Physics / science (simulations) | 2340 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P320 | Bar Data Manipulator | data-viz | Mathematics / statistics (data) | 2195 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |
| AVR-P321 | Cause Effect Reveal | animation | Cross-subject (motion & animation) | 2356 | 8/8 PASS | Yes (no network, 0 external URLs/assets) |

## 4. Harvest candidate bank (40 pattern references)

These are upstream open-source resources studied as mechanic *patterns* for future AASHA-native builds. Sources: GeoGebra (3), Pashasan (1), PhET (24), SimuTutor (2), all-science-sims (8), myPhysicsLab (2). Candidate families: circuit/system (3), data visualization (1), diagram/anatomy (1), field/diagram (1), geometry (2), geometry/optics (1), geometry/visual math (1), graph (2), graph interaction (1), graph/geometry (1), graph/parameterized simulation (1), molecule (2), molecule/particle (2), number-line (2), optics/parameterized simulation (1), parameterized simulation (11), particle (1), probability/data visualization (1), process (1), process/diagram (1), process/population (1), ratio/visual math (1), timeline/spatial (1).

| Harvest ID | Source | Reference resource | Family | Decision | Evidence status |
|---|---|---|---|---|---|
| HARV-0001 | PhET | Graphing Lines | graph | EXTRACT | candidate pattern |
| HARV-0002 | PhET | Build an Atom | molecule | EXTRACT | candidate pattern |
| HARV-0003 | PhET | Build a Molecule | molecule | EXTRACT | candidate pattern |
| HARV-0004 | PhET | States of Matter | particle | EXTRACT | candidate pattern |
| HARV-0005 | PhET | pH Scale | parameterized simulation | EXTRACT | candidate pattern |
| HARV-0006 | PhET | Projectile Data Lab | graph/parameterized simulation | EXTRACT | candidate pattern |
| HARV-0007 | all-science-sims | Projectile Motion | parameterized simulation | EXTRACT | candidate pattern |
| HARV-0008 | all-science-sims | Logic Gates & Circuits | circuit/system | EXTRACT | candidate pattern |
| HARV-0009 | all-science-sims | Cell Explorer | diagram/anatomy | EXTRACT | candidate pattern |
| HARV-0010 | all-science-sims | DNA Transcription & Translation | process/diagram | EXTRACT | candidate pattern |
| HARV-0011 | all-science-sims | Moon Phases | timeline/spatial | EXTRACT | candidate pattern |
| HARV-0012 | all-science-sims | Hydrologic Cycle | process | EXTRACT | candidate pattern |
| HARV-0013 | all-science-sims | Sorting Visualizer | data visualization | EXTRACT | candidate pattern |
| HARV-0014 | all-science-sims | Linear Regression Playground | graph | EXTRACT | candidate pattern |
| HARV-0015 | myPhysicsLab | Pendulum | parameterized simulation | EXTRACT | candidate pattern |
| HARV-0016 | myPhysicsLab | Spring | parameterized simulation | EXTRACT | candidate pattern |
| HARV-0017 | GeoGebra | Geometry construction | geometry | AUDIT | license/source audit required |
| HARV-0018 | Pashasan | Fit-line slider | graph interaction | EXTRACT | pattern source |
| HARV-0019 | SimuTutor | Electric field | parameterized simulation | EXTRACT | pattern source |
| HARV-0020 | SimuTutor | Pendulum | parameterized simulation | EXTRACT | pattern source |
| HARV-0021 | PhET | Projectile Motion | parameterized simulation | EXTRACT | GitHub repo identified; individual dependency/license audit pending |
| HARV-0022 | PhET | Wave Interference | parameterized simulation | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0023 | PhET | Circuit Construction Kit: DC | circuit/system | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0024 | PhET | Circuit Construction Kit Common | circuit/system | EXTRACT | shared component; inspect for reusable mechanics |
| HARV-0025 | PhET | Build an Atom | molecule/particle | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0026 | PhET | Forces and Motion: Basics | parameterized simulation | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0027 | PhET | Bending Light | optics/parameterized simulation | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0028 | PhET | Natural Selection | process/population | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0029 | PhET | Plinko Probability | probability/data visualization | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0030 | PhET | Geometric Optics: Basics | geometry/optics | EXTRACT | GitHub repo identified; GPL-3.0 shown on repository page; asset/dependency audit pending |
| HARV-0031 | PhET | pH Scale | parameterized simulation | EXTRACT | GitHub repo identified; GPL-3.0 shown on repository page; asset/dependency audit pending |
| HARV-0032 | PhET | pH Scale: Basics | parameterized simulation | EXTRACT | GitHub repo identified; GPL-3.0 shown on repository page; asset/dependency audit pending |
| HARV-0033 | PhET | Charges and Fields | field/diagram | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0034 | PhET | States of Matter: Basics | molecule/particle | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0035 | PhET | Area Model Introduction | geometry/visual math | EXTRACT | GitHub repo identified; dependency/license audit pending |
| HARV-0036 | PhET | Number Line: Operations | number-line | EXTRACT | GitHub org/repository identified; shared number-line component worth inspecting |
| HARV-0037 | PhET | Number Line: Distance | number-line | EXTRACT | GitHub org/repository identified; shared number-line component worth inspecting |
| HARV-0038 | PhET | Ratio and Proportion | ratio/visual math | EXTRACT | GitHub org/repository identified; dependency/license audit pending |
| HARV-0039 | GeoGebra | Graphing Calculator | graph/geometry | AUDIT | GitHub mirror identified; licensing explicitly requires separate audit |
| HARV-0040 | GeoGebra | Geometry App | geometry | AUDIT | GitHub mirror identified; licensing explicitly requires separate audit |

Note on candidates HARV-0021 to HARV-0040 (added in the Phase3-2 expansion): these have GitHub repos identified, but individual dependency and license audits are still pending — they are pattern references only, not cleared for direct reuse. GeoGebra and PhET both carry explicit flags in LICENSE-AUDIT.json: separate license/dependency audits are required before any direct reuse.

## 5. Verification & certification status

- **Static checks:** 8/8 pass for all 21 resources (exists, no_network, no_external_assets, tln, lle, teas, offline, js_syntax). `all_static_checks_pass: true`.
- **Audit flag — AVR-P311 data inconsistency (RESOLVED & UPDATED):** The catalogue entry in `catalogue/visual-resource-catalogue-phase3.json` for AVR-P311 (Particle Temperature) previously recorded `static: FAIL` and `js_syntax: FAIL`. This has been officially corrected to `static: PASS` and `js_syntax: PASS` matching the 8/8 static test report and Node syntax validation. All 21 resources now show 8/8 PASS across all catalogue and test artifacts.
- **Browser smoke:** NOT_CERTIFIED. The Playwright + Chromium harness was built and run, but navigation to the local test server was blocked by the execution environment (`ERR_BLOCKED_BY_ADMINISTRATOR`). No browser PASS is claimed anywhere in the build report — an honest, auditable status. Re-running the harness in an unrestricted environment is the remaining step to full certification.
- **License audit:** `bundled_third_party_code: false`, `bundled_third_party_assets: false`. AASHA code is original; source repositories are pattern references only, and their licenses are not relicensed.

## 6. Utilization guidance (for the Sarvam AI agent)

When building or recommending visual learning content for AASHA:

1. **Never Build From Scratch (Multi-Agent Prebuilt Reuse Mandate):** Multi-agents (DesignAgent, AssessmentAgent, LLEAgent, AnalysisAgent) MUST query `AASHA_Visual_Learning_Resource_Library.md` and `experience_registry/registry.json` first. Always adapt prebuilt, proven, efficient resources (AVR-P301..AVR-P321 and F01–F20 foundations) and customize their parameters via TLN content injection rather than writing 100% custom code from scratch.
2. **Prefer the built AVRs first.** 21 certified-static interactives already exist; check the table in section 3 before building anything new. Each is a standalone HTML file that can be embedded, iframed, or served offline as-is.
3. **New visual mechanics follow the same contract.** Any new interactive must: accept TLN content injection, emit TEAS evidence events (never decide mastery), support LLE bilingual reveal, be single-file offline, and stay under the bundle ceiling. The AVR-P3xx codebase is the template — copy its `AASHA` runtime object and fixture structure.
4. **Mine the candidate bank for new mechanics.** When a TLN needs a visual pattern not yet built (e.g. wave interference, graphing calculator, ratio/proportion), consult the harvest table: the family column maps learning needs to pattern sources, and the evidence-status column tells you how much audit work remains.
5. **Research vs. Direct Copy Rule:** Sources like GeoGebra, PhET, and myPhysicsLab (HARV-0001..HARV-0040) are research pattern references for extracting physical models and mechanics. Multi-agents adapt these into 100% AASHA-native `<aasha-sim>` Web Component adapters with zero third-party code bloat or copyleft risk.
6. **Assessment integration:** All mastery logic stays in TEAS. Games and visuals are evidence emitters — the same authority rule as the gamified-learning library.

## 7. Relationship to the gamified-learning library

This library complements AASHA_Gamified_Learning_Resource_Library.md (open-source educational game repos for the gamified assessment & learning component). Shared rules across both: TLN content injection, TEAS evidence-only mastery, LLE bilingual support, offline-first bundles, and strict license auditing before any third-party reuse. Together they cover AASHA's interactive learning stack: harvested game repos (adapt/hatch) on one side, AASHA-native visual interactives and simulations on the other.
