# AASHA System Architecture & Data-Flow Map
Generated: `2026-11-12T20:00:46.200311+00:00`

1. **Plane 1 (Google Drive Bridge `1Xgtf699BHe2yKdw6ne1ilihXsgP6WMxD`)**: Stores `aasha_aios_v2_bootstrap_full.bundle`, `aasha_operational_mirror.json`, `AASHA_OpenSource_Codebase_Cache` (`1B2Au3mwU-ZU1A1UTJtZfCVZrKdnV-2xI`), and verification reports.
2. **Plane 2 (Cloud Sandbox / Colab `1XPLBrKkB_nzrEWNUq3Z2plxnnq1VUJk2`)**: Executes `HydrogenArgonSwarmRouter` (`scripts/aasha_continuous_loop.mjs --swarm`), Python orchestrators (`src/aasha/orchestrator/`), and QA (`qa/run_qa.js`).
3. **Plane 3 (Windows Workstation `C:\Users\admin\Downloads\NGO AI LLM`)**: Reconciles offline state idempotently via `scripts/reconcile_windows_mirror.py` on reconnect.
