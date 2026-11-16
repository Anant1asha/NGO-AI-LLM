# AASHA Code-Build-Test-Debug Pipeline Audit
Generated: `2026-11-16T12:12:14.029839+00:00`

- **Build & Synthesis**: `FrontendCodeSynthesizer`, `SixAgentV5EngineSynthesizer`, `sqlite_exporter.py`, `bundler.py`, `HydrogenArgonSwarmRouter` (`scripts/aasha_continuous_loop.mjs --swarm`).
- **Test & QA**: `61` Python test suites, `97` Visual Contract assertions, `qa/run_qa.js` (`28` checks with Node VM DOM shim), `lint_staged_secrets.mjs`.
- **Debug & Self-Heal**: `run_html5_self_healing_qa_pass(max_attempts=2)` + `HydrogenArgonSwarmRouter` 2-repair circuit breaker (`BLOCKED_HIL`).
