# ADR-PROPOSED-001: Provider-Neutral, Capability-Driven Agent Runtime

- **Status:** ACCEPTED — APPROVED BY SUPER ADMIN
- **Date:** 2026-10-10 (Approved: 2026-10-20)
- **Scope:** AASHA AIOS agent orchestration across NGO-AI-LLM and Aasha-AI
- **Evidence basis:** [AASHA-AUDIT-2026-10-10-01](../audits/2026-10-10_any-tool-agent_source_audit.md)

## Context

The source audit identified:
- A mock-only agent runner in `NGO-AI-LLM/multi-agent-tui/src/agent.ts`.
- A static six-tool list in `multi-agent-tui/src/tools/index.ts`.
- `autoApproveAll: true` in `multi-agent-tui/src/config.ts`.
- An arbitrary shell command passed to `child_process.exec` in `multi-agent-tui/src/tools/shell.ts`.
- File tools without visible repository-root confinement in the inspected implementations.
- A fixed provider list/routing chain in `Aasha-AI/llm_router.ts`.
- Deterministic roles in `Aasha-AI/agent_orchestrator.ts` that return a success-shaped status without invoking the described scripts in that branch.
- A repair path that does not visibly revalidate the replacement response before recording it with a passed gatekeeper flag.
- Two distinct orchestration paths: the TUI and the Python chapter pipeline.

These observations do not prove the absence of all other implementations elsewhere in either repository. A repository-wide call graph and runtime tests remain required.

## Decision proposed for review

Adopt a provider-neutral capability architecture with the following boundaries:

1. **AASHA AIOS Control Plane** remains the sole authority for canonical job state, policy decisions, authorization, protected state transitions, approval, certification, and release.
2. **Any-Tool AGI / Capability Resolver** is a subordinate subsystem responsible for capability discovery, descriptor validation, compatibility negotiation, eligible capability selection, bounded dispatch, result evaluation, and evidence collection.
3. **Provider adapters** implement typed model-inference interfaces. No provider-specific SDK, model ID, key name, or fallback chain may become a required dependency of the control plane.
4. **Tool adapters** expose typed capabilities with declared input/output schemas, permissions, side effects, authentication needs, timeouts, cancellation, cost limits, and provenance.
5. **Workflow/dispatch adapters** are optional. n8n, a queue, a scheduler, or a native runner may trigger or dispatch work, but cannot own canonical state or bypass policy gates.
6. **Deterministic validation and teacher/HIL approvals** remain independent of model outputs. A model cannot certify its own output.
7. **Test doubles** are permitted for tests only and must be explicitly identified so they cannot produce production certification evidence.
8. **Unknown, incompatible, revoked, or unauthorized capabilities fail closed.** Discovery does not grant execution permission.
9. **Repair is bounded:** at most two autonomous repair attempts after the initial attempt, with revalidation after every repair; otherwise quarantine and escalate.
10. **No broad code-generation implementation** starts until this ADR and the source-backed audit are reviewed and approved by the human project authority.

## Options considered

### Option A: Keep current vendor-specific routing and add more agents

**Reject.** It increases the number of agents without proving discovery, authorization, safe execution, or portability.

### Option B: Replace the current provider with a different preferred provider

**Reject.** It changes the vendor lock-in rather than removing the architectural dependency.

### Option C: Add a provider-neutral adapter layer under the existing control plane

**Recommended, pending approval.** It supports incremental migration, permits existing routers to be wrapped as adapters, and avoids replacing the learning pipeline before behavior and ownership are mapped.

### Option D: Replace both repositories with a new orchestration framework

**Reject for the initial phase.** It creates unnecessary migration risk and may duplicate canonical state, learning contracts, and release gates before the current system is understood.

## Proposed target boundary

```text
AASHA AIOS Control Plane
  ├── canonical job state and authorization
  ├── policy / approval / release gates
  └── immutable evidence and audit history
           |
           v
Any-Tool AGI Capability Resolver
  ├── discovery sources and descriptor validation
  ├── compatibility + policy negotiation
  ├── bounded dispatch and cancellation
  └── result evaluation / evidence normalization
           |
           +--> Model provider adapters (all optional)
           +--> Tool capability adapters (least privilege)
           +--> Workflow/queue adapters (all optional)
           +--> Deterministic executors and validators
           |
           v
Existing AASHA learning pipeline
  └── source provenance -> TLN/LLE -> experience reuse
      -> assessment -> independent QA -> teacher review
      -> offline bundle -> impact evidence
```

This is a target boundary, not a claim that the diagram is already implemented.

## Consequences

### Benefits
- Removes mandatory dependency on any one model provider, tool host, or workflow engine.
- Makes tool eligibility and authorization explicit and testable.
- Enables reuse of existing provider routers and pipeline components through adapters where they satisfy contracts.
- Separates generated claims from deterministic verification and human approval.
- Supports provider-free unit tests and controlled offline execution.

### Costs and risks
- Requires typed capability contracts, schema/version policy, credential handling, timeout/cancellation behavior, and adapter conformance tests.
- Requires mapping and reconciling duplicate orchestration/state paths before implementation.
- Dynamic discovery expands the attack surface; source trust, revocation, permission scopes, and supply-chain provenance are mandatory.
- Existing mocks and historical test reports must not be misrepresented as real integration evidence.

## Proposed implementation gates

- **Gate 0 — Human decision:** confirm repository authority, canonical state owner, discovery sources, approval policy, and conflicting bundle limits.
- **Gate 1 — Baseline:** run current tests on pinned commits and capture reproducible evidence.
- **Gate 2 — Contracts:** approve versioned capability and evidence interfaces; prove with test doubles.
- **Gate 3 — Safety:** prove default-deny permissions, workspace confinement, safe command execution, revalidation after repair, and bounded recovery.
- **Gate 4 — Portability:** run the same contract suite across two independent model adapters and two execution/dispatch paths, plus a provider-free deterministic path.
- **Gate 5 — Learning vertical slice:** process a source chapter through provenance, TLN/LLE, experience reuse, assessment, independent QA, teacher review, and offline packaging.
- **Gate 6 — Promotion:** human approval only after evidence is reviewed. No automatic merge, release, or certification.

## Questions the human reviewer must resolve

1. Confirm whether NGO-AI-LLM is the governance/orchestration audit workspace and Aasha-AI is the learning implementation repository, or designate a different authority.
2. Identify the actual canonical owner of job state and immutable evidence after inspecting the implementation, not just older architecture notes.
3. Approve the initial capability discovery boundary: repository-local registry only, configured MCP/API sources, or both.
4. Confirm the policy for shell-like operations, protected file access, secrets, architecture changes, and release.
5. Resolve conflicting child-bundle size limits and identify the source-of-truth contract.
6. Approve or reject Option C.

## Approval record

- Human decision: **ACCEPTED**
- Approved by: **Super Admin (Human Authority)**
- Date: **2026-10-20**
- Scope approved: **Option C — Provider-neutral adapter layer under existing AASHA AIOS control plane**
- Implementation authorized by this ADR: **YES (Bounded, Incremental Provider-Neutral Capability Runtime)**
