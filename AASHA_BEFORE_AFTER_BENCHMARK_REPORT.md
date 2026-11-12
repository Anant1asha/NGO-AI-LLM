# AASHA Before/After System-Wide Benchmark Report
Generated: `2026-11-12T20:00:46.200311+00:00`

| Metric | Before Baseline | After (`W0`-`W5`) | Evidence |
| :--- | :--- | :--- | :--- |
| **LLE Word Map (`WM`)** | `296` entries (`defaults.json`) | **`1,129` entries** (`+281%`) | `defaults_expanded_v2.json` |
| **LLE Connectors (`CONN`)** | `46` entries | **`85` entries** (`+85%`) | `defaults_expanded_v2.json` |
| **Operational DB Tables/Rows** | `1` table (`1` row) | **`6` tables (`1287` rows)** | `aasha_operational.db` |
| **Cached Reusable Code Assets** | `0` local cache index | **`48` assets** (`53.6 KB` tar.gz) | `CODEBASE_CACHE_INDEX.json` |
| **G3 Fractions Bundle** | `26 KB` (`25 WM`, `0` AVR) | **`93.7 KB` (`1,129 WM`, `2` AVR)** | `PHASE_G33_BACKLOG_EXECUTION_MANIFEST.json` |
| **`run_qa.js` VM Step/Flow** | `0/0` fallback | **`1/1` VM render + flow (`28/28`)** | `qa/run_qa.js` |
