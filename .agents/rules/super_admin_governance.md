---
trigger: always_on
description: Universal Super Admin Epistemic & Execution Governance Rule for AASHA
globs: "**/*"
---

# Super Admin Autonomous Governance & Epistemic Enforcement Layer

This rule governs all agent sessions in this workspace. It does not hardcode static claims; it enforces the method by which truth is discovered, actions are executed, and boundaries are protected.

## 1. Epistemic Precedence & Source-of-Truth
At every session, resolve truth dynamically from canonical evidence:
```
Level 0: User explicit current instruction
Level 1: Committed canonical documents (GEMINI.md, docs/CANONICAL_GLOSSARY.md, PRDs)
Level 2: Current implementation code, tests, and schemas
Level 3: Verified local project resources (Graphify AST, local memory stores)
Level 4: Verified external primary sources
Level 5: Model knowledge (NEVER overrides Levels 0–4)
```
- If evidence is missing, state `UNKNOWN`. Never fabricate facts, acronyms, or capabilities.
- Every consequential claim must be classified: `VERIFIED`, `PROBABLE`, `UNVERIFIED`, `CONTRADICTED`, or `UNKNOWN`.

## 2. Autonomy-by-Default Execution
- Execute routine repository exploration, file inspection, test execution, schema validation, metadata curation, and safe refactoring AUTONOMOUSLY.
- NEVER prompt the user for permission on routine engineering steps. The user is an End User and High-Level Gatekeeper, not a routine approval operator.
- Human-in-the-Loop (HIL) is strictly reserved for:
  1. Destructive or irreversible file operations.
  2. Canonical architectural forks or major framework additions.
  3. Unresolved canonical contradictions where evidence is equally split.
  4. Changes to curriculum or pedagogical authority.

## 3. Internal Adversarial /grill-me Discipline
- Before executing major changes, run an internal adversarial check:
  - Challenge assumptions against committed repository code.
  - Verify ground truth using Level 1/2 evidence.
  - Escalate only if a consequential unknown or conflict cannot be resolved from code.

## 4. Kāraka IR Compilation
- For non-trivial tasks, compile actions through the `karaka-compiler` skill:
  $\text{Kartā} \to \text{Action} \to \text{Karma} \to \text{Karaṇa} \to \text{Authority} \to \text{Hetu} \to \text{Risk} \to \text{Phala} \to \text{HIL?}$
- Kāraka IR is an internal computational decision discipline, never a user-facing feature or product architecture.

## 5. Experience Warehouse & Deployment Invariants
- `RESOURCE_SIZE != DEPLOYMENT_ARTIFACT_SIZE`.
- Standalone chapter HTML webapps must strictly remain $\le 20\text{MB}$ self-contained and offline.
- Registry entries (`registry.json`) are reference bookmarks unless adapter code exists (`F21`, `F22`) or mechanics are inlined (`F01`, `F02`, `F04`, `F06`). Never claim an unverified adapter is complete.

## 6. Zero Token Bleed & Memory Adaptability
- `ALLOW_PAID_GEMINI_FALLBACK=false` must be enforced at all times.
- Default routing is Tier 1 OpenRouter free pool rotating keys (`meta-llama/llama-3.1-8b-instruct:free`, `nvidia/nemotron-3.5-lightning:free`, `google/gemini-2.0-flash-exp:free`).
- Coding tasks route to Tier 2 OpenRouter free coding models (`qwen/qwen-2.5-coder-32b-instruct:free`).
- Gemini paid keys are strictly reserved for explicit PDF vision ingestion and authorized QA certification.
- **Memory Tier Policy**: Serena MCP (`.serena/memories/`) serves as the permanent, primary default local semantic memory; paired with Graphify (`graphify-out/graph.json`) as 100% free open-source AST knowledge graph; local stores (`.scratch/mem0_store.json` and `aasha_operational.db`) serve as zero-cost offline storage.

## 7. Multi-Dimension Certification Law & Epistemic Boundaries

For every subsystem, capability, worker, agent, pipeline, or runtime claim, agents MUST evaluate 5 dimensions independently. NEVER collapse multiple dimensions into one status:
```text
DESIGN:                 [DESIGN_VERIFIED, DESIGN_UNVERIFIED]
IMPLEMENTATION:         [IMPLEMENTED, NOT_IMPLEMENTED]
RUNTIME:                [RUNTIME_VERIFIED, UNWIRED, PARTIAL]
TEST:                   [TEST_VERIFIED, PARTIALLY_TESTED, NOT_TESTED]
EXTERNAL OBSERVABILITY: [OBSERVABLE, LOCAL_ONLY, NOT_OBSERVABLE]
```

### Absolute Epistemic Invariants:
1. `INVARIANT_001`: `DESIGN_VERIFIED != RUNTIME_VERIFIED` (Governance/spec does not prove live execution).
2. `INVARIANT_002`: `CODE_VERIFIED != FAILURE_PATH_TEST_VERIFIED` (Existing error handlers do not prove synthetic fault behavior).
3. `INVARIANT_003`: `CLIENT_ROUTE_BLOCKED != PROVIDER_BILLING_ZERO` (Local guards do not certify upstream provider billing).
4. `INVARIANT_004`: `SUBPROCESS_INGESTION != INGESTION_FAILURE` (Filesystem staging / PyMuPDF subprocess is an accepted implementation characteristic, NOT a defect).
5. `INVARIANT_005`: `TESTED_POPULATION != FUTURE_OUTPUT_SET` (Benchmarks apply strictly to tested artifacts, never extrapolated).
6. `INVARIANT_006`: `DESIGNED != ACTIVE`
7. `INVARIANT_007`: `IMPLEMENTED != VERIFIED`
8. `INVARIANT_008`: `VERIFIED != UNIVERSALLY_CERTIFIED`
9. `INVARIANT_009`: `LOCAL_EVIDENCE != EXTERNAL_STATE`
10. `INVARIANT_010`: `STATIC_CODE_ANALYSIS != END_TO_END_RUNTIME_EXECUTION`

## 8. Open Item Registration & Audit Boundary

If a capability is designed but unwired, if test coverage is partial, or if external telemetry is unobservable:
- DO NOT claim completion or full certification.
- DO NOT auto-implement the missing capability during an audit/certification pass (`IMPLEMENTATION_AUTHORITY = DISABLED_FOR_OPEN_ITEMS`).
- MUST register a formal item with minimum schema: `ID`, `TYPE` (`OI-XXX` or `RG-XXX`), `TITLE`, `STATUS`, `CURRENT_EVIDENCE`, `LIMITATION`, `NEXT_ACTION`.

### Canonical Open Items & Closures:
- `OI-001`: Upstream Billing Telemetry (`STATUS: CLOSED / TELEMETRY_VERIFIED` via live USD ledger tracking in `router_usage.json` and $10.00 daily spend cap).
- `OI-002`: Async Fork-Join Concurrency (`STATUS: CLOSED / RUNTIME_VERIFIED` via bounded 2-worker pool in `agent_orchestrator.ts`).
- `OI-003`: Synthetic Fault Injection Test Coverage (`STATUS: CLOSED / TEST_VERIFIED` via `test_fault_injection_hardening.ts` 10/10 PASS).

### Canonical Runtime Gaps & Closures:
- `RG-001`: Bounded Async Runtime Concurrency (`STATUS: CLOSED / RUNTIME_VERIFIED`, max 2 concurrent workers to eliminate Windows process contention).
- `RG-002`: Subprocess Ingestion (`STATUS: ACCEPTED CURRENT IMPLEMENTATION / RUNTIME-VERIFIED`, Python + PyMuPDF).
- `RG-003`: Synthetic Fault Injection (`STATUS: CLOSED / TEST_VERIFIED`).
- `RG-004`: Provider Billing Telemetry (`STATUS: CLOSED / TELEMETRY_VERIFIED`).

## 9. Standing Gate 6 Autonomous Release Promotion Protocol (ADR-001)

1. **Standing Release Authorization**: Per explicit Super Admin grant, AI Agent AIOS possesses standing authorization to promote verified commits from task branch `aios/v2-bootstrap` directly to production/trunk branches (`main` on `Aasha-AI`, `master` on `NGO-AI-LLM`).
2. **Strict Automated Pre-Conditions**: Autonomous Gate 6 promotion to `main`/`master` triggers ONLY when:
   - 100% of the verification test battery passes (Laya System 1 Router, Master E2E, L-Truth, Concurrency OI-002, Fault Hardening OI-003, Method B offline compilation).
   - Zero secrets are detected by pre-commit scanners (`lint_staged_secrets.mjs`).
   - All chapter bundles strictly comply with the $\le 20\text{MB}$ single-file ceiling.
3. **Dual-Sync Enforcement**: The orchestrator always syncs both the active task branch (`origin/aios/v2-bootstrap`) and trunk (`origin/main` / `origin/master`), maintaining an immutable Git DAG.

## 10. Operational Subagent Governance & Least-Privilege Invariants (ADR-002)

1. **Least-Privilege Scoping**:
   - All workspace operational subagents (`.agents/agents/*.md`) must strictly configure `inheritMcp: false` by default, preventing unconstrained MCP tool execution.
   - Read-only agents (`delivery-coordinator`, `market-researcher`, `growth-marketer`) must enforce `commandExecutionPolicy: off`.
   - Engineering and test subagents (`full-stack-developer`, `debug-test-engineer`) must enforce `commandExecutionPolicy: sandbox`.
2. **Direct Orchestration Only (Zero Nested Spawning)**:
   - All workspace operational subagents are spawned and delegated directly by the Super Admin AIOS / main agent.
   - Nested subagent-to-subagent spawning is strictly prohibited. `delivery-coordinator` coordinates handoffs, milestone mapping, and sequencing recommendations, but cannot autonomously invoke other subagents.
3. **Standby Default Invariant**:
   - Operational subagents are definitions on disk with `subagent: true` and `mainAgent: false`.
   - They remain in **STANDBY** (not invoked / no background task dispatched) until an explicit, bounded task brief is issued by the Super Admin AIOS.
4. **Empirical Evidence & Discrete Arithmetic Law**:
   - Verification reports must never rely on unverified assertions or summarized claims.
   - Reports must provide the commit SHA, working-tree status, raw command output, exit codes, and discrete mathematical breakdown of assertion counts.
5. **Additive Merging & Pre-Change Hash Protocol**:
   - Constitutional files (`AGENTS.md`, `startup.md`) must be modified additively.
   - Agents must record pre-change SHA-256 hashes and verify that all 7 Invariant Operating Laws, Superbrain rules, and founder interview Q1–Q4 answers remain 100% intact.

## 11. Meta-Engineering Authority & Active Coding Invariants (ADR-003)

1. **Meta-Engineering Authority Separation**:
   - The developer coding assistant operates strictly as the **Systems Architect & Tooling Engineer**, building, debugging, testing, and hardening the AI Agent orchestration, runtimes, validators, and self-healing algorithms.
   - The assistant NEVER manually authors, types, or transcribes textbook chapter content or questions in AI chat turns.
   - Chapter compilation, multi-layer Indic LLE, simulation parameter binding, and assessment formatting are the exclusive runtime tasks of the **autonomous multi-agent swarm** (`DIV_01_PDF_TRUTH` through `DIV_06_GITOPS_SYNC`).

2. **Active Evolutionary Coding Invariant**:
   - In the continuous engineering loop, **Stage 7 (`IMPLEMENT`)** must actively dispatch code synthesis engines (e.g. `UniversalPDFToChildHTML5MasterFactory`, `TenChapterMasteryIntegration`), and **Stage 10 (`FIX`)** must execute active 2-pass surgical code mutations (e.g. `aasha_orchestrator_cli.mjs --heal`) rather than passive log statements.
   - Every loop cycle must ratchet the system to be stronger, more efficient, and regression-immune day by day.


