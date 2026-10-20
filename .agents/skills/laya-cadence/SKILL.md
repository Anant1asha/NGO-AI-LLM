---
name: laya-cadence
description: Runs the disciplined 5-phase daily Laya execution loop (gateway/memory health audit, contract synthesis, multi-scenario test verification, surgical code optimization, and verified telemetry recording).
---

# /laya-cadence: AASHA AIOS Daily Execution Cadence

Runbook for executing the daily high-rigor development cadence across the AASHA ecosystem.

## 5-Phase Cadence Execution

### Phase 1: Context Priming & Health Audit
1. Audit local 9Router proxy gateway:
   ```bash
   npm run audit:gateway
   ```
   If offline, launch the background daemon bound strictly to local loopback:
   ```powershell
   $env:PORT='20128'; $env:HOSTNAME='127.0.0.1'; node "$env:APPDATA\npm\node_modules\9router\app\custom-server.js"
   ```
2. Audit persistent memory and knowledge graph status:
   ```bash
   npm run admin:status
   ```

### Phase 2: Product & Pedagogical Synthesis
1. Review `CANONICAL_CONTRACT_REGISTER.md` for active governance contracts (`CON-001` through `CON-012`).
2. Review `ACCEPTANCE_TEST_PLAN.md` for the 18 master acceptance criteria.

### Phase 3: Deep Research & Multi-Scenario Verification
1. Run Laya System 1 pre-routing test:
   ```bash
   npm run laya:test
   ```
2. Run master unified multi-chapter E2E test harness:
   ```bash
   npm run test:master
   ```
3. Run L-Truth ground truth anti-spoiler benchmark:
   ```bash
   npm run test:ltruth
   ```
4. Run Fork-Join concurrency wiring & fault injection hardening suites:
   ```bash
   npm --prefix Aasha-AI exec -- tsx tests/test_concurrency_wiring.ts
   npm --prefix Aasha-AI exec -- tsx tests/test_fault_injection_hardening.ts
   ```

### Phase 4: Surgical Optimization & Multi-Repo Alignment
1. Check git remote status across repositories (`NGO-AI-LLM`, `Aasha-AI`, `aasha-studio`); fast-forward upstream PR merges cleanly using safe stash-pull-pop.
2. In unit test harnesses evaluating deterministic byte-for-byte equivalence, isolate dynamic timestamp generators via `useIEC: false`.
3. Inspect benchmark warnings or spoiler leaks (Rule #1) and apply non-spoiling explanations that clarify the misconception without revealing numerical answers.
4. Keep individual chapters compliant with the 20MB ceiling, zero external CDNs, math insulation, and mobile viewport clamping.

### Phase 5: Re-Verification & Telemetry Ledger
1. Re-run all test suites (`npm run test:master`, `npm run test:ltruth`, `npm run laya:test`).
2. Verify 100% pass rate (0 failures).
3. Record verified execution telemetry into both `VERIFICATION_REPORT.md` and `.scratch/daily_laya_digest.md`.

## Multi-Repo Safe Promotion & Zero-Leakage Git Protocol
1. Verify `.gitignore` actively blocks `.scratch/`, `**/.scratch/`, `*cookie*`, `*.zip`, `.claude/`, `.env`, and `secrets/`.
2. Run pre-commit regex scanning across diffs for secrets (`sk-`, `ghp_`, `github_pat_`, `AIzaSy`).
3. Coordinate staging and committing across `NGO-AI-LLM` (`origin/master`) and `Aasha-AI` (`origin/aios/v2-bootstrap`).
4. Push clean commits to remotes with explicit human authorization.
