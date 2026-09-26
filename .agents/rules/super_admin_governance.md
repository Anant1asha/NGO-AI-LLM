---
description: Universal Super Admin Epistemic & Execution Governance Rule for AASHA
always_on: true
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

### Canonical Open Items:
- `OI-001`: Upstream Billing Telemetry (`STATUS: OPEN / EXTERNAL OBSERVABILITY LIMITATION`).
- `OI-002`: Async Fork-Join Concurrency (`STATUS: OPEN / IMPLEMENTATION PENDING`).
- `OI-003`: Synthetic Fault Injection Test Coverage (`STATUS: OPEN / TEST-COVERAGE GAP`). Required test sequence: `INJECT -> CLASSIFY -> REPAIR 1 -> REPAIR 2 -> EXHAUSTION -> QUARANTINE -> DOWNSTREAM BLOCK -> HIL PACKET -> ASSERT FINAL STATE`.

### Canonical Runtime Gaps:
- `RG-001`: Async Runtime Concurrency (`STATUS: OPEN / IMPLEMENTATION GAP`, current: sequential).
- `RG-002`: Subprocess Ingestion (`STATUS: ACCEPTED CURRENT IMPLEMENTATION / RUNTIME-VERIFIED`, Python + PyMuPDF).
- `RG-003`: Synthetic Fault Injection (`STATUS: OPEN / TEST-COVERAGE GAP`).
- `RG-004`: Provider Billing Telemetry (`STATUS: OPEN / EXTERNAL OBSERVABILITY GAP`).
