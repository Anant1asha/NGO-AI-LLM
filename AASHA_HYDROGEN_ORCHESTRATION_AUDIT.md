# AASHA Hydrogen Orchestration Audit
Generated: `2026-11-12T20:00:46.200311+00:00`

- **Entrypoint**: `src/aasha/orchestrator/hydrogen_argon_swarm_router.py` (`HydrogenArgonSwarmRouter`), wired into `scripts/aasha_continuous_loop.mjs --swarm`.
- **State Machine**: `HYDROGEN_ORCHESTRATE` -> `ARGON_EXECUTE` -> `HYDROGEN_INDEPENDENT_QA` -> `CERTIFIED_CHECKPOINT` (or `BLOCKED_HIL` after 2 failed repairs).
- **Verified Invariants**: Distinct builder vs. verifier IDs enforced; write-scope contention rejected (`test_hydrogen_argon_swarm_router.py` 4/4 pass).
