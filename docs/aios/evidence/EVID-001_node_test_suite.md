# EVID-001: Ecosystem Node.js Test Suite Execution Evidence

- **ID**: EVID-001
- **SOURCE**: Node.js Test Runner execution in `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo`
- **DATE**: 2026-09-08T04:12:03+05:30
- **TYPE**: TEST_EXECUTION_LOG
- **CLAIM**: All 16 unit and integration tests for offline outbox, stage mapping, TLN order, TEAS scoring, reward ledger, and visual engines pass with zero errors.
- **LOCATION**: `tests/unit/*.test.js`, `tests/integration/*.test.js`
- **RESULT**:
  - Tests: 16 passed, 0 failed, 0 cancelled, 0 skipped.
  - Duration: 611.52 ms.
- **CONFIDENCE**: 1.0 (Direct empirical terminal output)

```
TAP version 13
# Subtest: offline event outbox survives and syncs
ok 1 - offline event outbox survives and syncs
# Subtest: Class 1-10 stage mapping
ok 2 - Class 1-10 stage mapping
# Subtest: chapter schema and TLN order
ok 3 - chapter schema and TLN order
# Subtest: assessment and TEAS separate mastery from progression
ok 4 - assessment and TEAS separate mastery from progression
# Subtest: reward ledger is idempotent
ok 5 - reward ledger is idempotent
# Subtest: impact reporting is aggregate-only
ok 6 - impact reporting is aggregate-only
# Subtest: approved assets and AI governance
ok 7 - approved assets and AI governance
# Subtest: Generalization: Class 7 Perimeter and Area passes content schema and TLN order
ok 8 - Generalization: Class 7 Perimeter and Area passes content schema and TLN order
# Subtest: Generalization: Visual Engine renders modular 2D Grid Area model with dual readouts
ok 9 - Generalization: Visual Engine renders modular 2D Grid Area model with dual readouts
# Subtest: Generalization: Question Engine intercepts perimeter vs area cognitive misconceptions
ok 10 - Generalization: Question Engine intercepts perimeter vs area cognitive misconceptions
# Subtest: Generalization: Two-tier diagnostic assessment and TEAS progression on Class 7 content
ok 11 - Generalization: Two-tier diagnostic assessment and TEAS progression on Class 7 content
# Subtest: P0-A & ISS-02: Visual engine renders interactive SVG fraction bar with keyboard accessibility
ok 12 - P0-A & ISS-02: Visual engine renders interactive SVG fraction bar with keyboard accessibility
# Subtest: P0-B & P0-D: Question engine extracts distractor-specific feedback and misconception IDs
ok 13 - P0-B & P0-D: Question engine extracts distractor-specific feedback and misconception IDs
# Subtest: P0-C: Fractions chapter contains 3 diagnostic questions per concept node
ok 14 - P0-C: Fractions chapter contains 3 diagnostic questions per concept node
# Subtest: ISS-01: Two-tier attempt tracking decouples diagnostic score from retries
ok 15 - ISS-01: Two-tier attempt tracking decouples diagnostic score from retries
# Subtest: ISS-03: Deterministic reward event ID prevents duplicate coins on replay
ok 16 - ISS-03: Deterministic reward event ID prevents duplicate coins on replay
1..16
# pass 16
# fail 0
```
