---
name: sprint-verifier
description: Autonomous 5-pillar verification and hardening engine for AASHA AIOS. Runs bounded async concurrency tests (RG-001), synthetic fault injection quarantine (OI-003), live USD billing telemetry (OI-001), pre-commit zero-secret scanning (SEC-002), and Superbrain rule parity (64/64 checks). Emits a Markdown audit scorecard with pass/fail badges.
---

# AASHA AIOS Sprint Verifier

Autonomously audits, tests, and certifies all 5 architectural safety pillars of AASHA AIOS.

## Overview

The `sprint-verifier` skill provides a single, deterministic command to verify system health across the complete AIOS operational stack before git promotions, major builds, or daily releases.

## The 5 Pillars Verified

1. **Pillar 1: Bounded Async Concurrency (`RG-001`)**
   - Asserts that multi-agent fork-join stages strictly run with max 2 workers (`runWithWorkerPool`).
   - Verifies parallel runtime speedup over sequential execution while preventing Windows process table thrashing.

2. **Pillar 2: Synthetic Fault Injection & Quarantine (`OI-003`)**
   - Asserts the 2-repair failure lifecycle (`INJECT -> REPAIR 1 -> REPAIR 2 -> EXHAUSTION -> QUARANTINE -> DOWNSTREAM BLOCK -> HIL PACKET`).
   - Verifies zero memory banking side-effects on quarantine.

3. **Pillar 3: Live USD Billing Telemetry & High-Worth Routing (`OI-001`)**
   - Asserts live USD cost calculation in `router_usage.json`.
   - Verifies $10.00 daily spend cap circuit breaker and authorized high-worth task whitelist (`coding`, `high_worth_coding`, `pdf_ingestion`).

4. **Pillar 4: Pre-Commit Zero-Secret Scanner (`SEC-002`)**
   - Scans staged diffs for uninsulated API keys, PATs, private keys, cookies, and active `.env` files.

5. **Pillar 5: Superbrain Rule Parity & Schema Compliance**
   - Enforces 1:1 parity between `.agents/rules/` and `.superbrain/rules/` with 0 `!!seq` YAML list errors.

---

## Usage Instructions

### CLI Execution

Execute the verification engine from the repository root:

```bash
# Full 5-pillar audit suite (generates SPRINT_VERIFICATION_REPORT.md)
npm run verify:sprint

# Quick static scan (<2s: secrets, rule parity, and workflows only)
npm run verify:sprint -- --quick

# Custom report destination
npm run verify:sprint -- --report my_audit.md

# Machine-readable JSON output for CI/CD pipelines
npm run verify:sprint -- --json
```

### When to Invoke

- **Pre-Promotion**: Run before opening a pull request or merging code.
- **Post-Refactoring**: Run after modifying agent orchestration, LLM routers, or rules.
- **Daily Cadence**: Run on daily scheduled runs to confirm zero drift.
