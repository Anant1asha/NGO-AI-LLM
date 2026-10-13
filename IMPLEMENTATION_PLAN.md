# IMPLEMENTATION_PLAN.md
# AASHA AIOS Development Agent — Phased Implementation Plan (v1.1)
**Authority**: Principal AI Systems Architect & Technical Product Manager  
**Date**: 2026-10-12  
**Version**: 1.1 (Revised following Architecture Review & Credential Remediation)  
**Status**: `REMOTE_AUDIT_COMPLETE_LOCAL_VERIFICATION_PENDING` (Implementation NOT Authorized)  

---

## 1. Executive Summary & Review Status
This revised implementation plan addresses all feedback from the Phase 0 Architecture Review:
1. **Security Remediation (SEC-001)**: Git remote URLs for both root (`NGO-AI-LLM`) and sub-repo (`Aasha-AI`) have been sanitized to remove embedded PAT strings. Credential rotation and pre-commit secret scrubbing are enforced.
2. **Architecture Boundary**: Verified that Antigravity connects **OUTBOUND** to hosted n8n (`https://airtribe.app.n8n.cloud/mcp-server/http`) via `mcp-remote` with Bearer auth. Zero inbound ports are exposed on the developer machine.
3. **Financial Anti-Bleed Governance**: Strict 3-tier model routing is formally documented with explicit tool and execution permissions. Paid Gemini API tokens remain hard-locked (`ALLOW_PAID_GEMINI_FALLBACK=false`).
4. **REA Invariant**: REA remains an optional adapter; core repository reconnaissance, testing, and compilation are 100% independent of REA.

---

## 2. Pinned Commits & Target Reality
- **Root Repository (`NGO-AI-LLM`)**: Commit `43760f8981600f6bc1e43d3e69188a803716a5b2` (`43760f8`) on `master`.
- **Sub-Repository (`Aasha-AI`)**: Commit `61fce9d53cf8e431844d242ce9f47567409582f1` (`61fce9d`) on `aios/v2-bootstrap`.
- **Hosted Orchestrator**: `https://airtribe.app.n8n.cloud` (connected outbound via Antigravity `mcp-remote`).
- **Development IDE & Control Plane**: Google Antigravity AIOS (local Windows host).

---

## 3. Universal 3-Tier Model Routing & Capability Policy

| Tier | Provider & Models | Permitted Task Classes | Tool & Execution Permissions | Data Access & Bounds | Fallback Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Free Routine)** | OpenRouter Free Pool: `llama-3.1-8b-instruct:free`, `nemotron-3.5-lightning:free`, `gemini-2.0-flash-exp:free` | Intake classification, repository reconnaissance, architecture audits, diff reviews, schema validations, simple edits (<200 lines). | **READ-ONLY TOOLS ONLY**. Can inspect files, query ASTs, run linters. **CANNOT** write to disk, run shell commands, or approve promotions. | Anonymized code, sanitized issues, local AST graph. **Zero PII or credentials**. | Rotate models within Tier 1 with 3s backoff on 429. After 3 failures, escalate to Tier 2. **NEVER to Tier 3**. |
| **Tier 2 (Free Coding)** | Claude Code / OpenRouter: `claude-3-5-sonnet`, `claude-3-haiku`, `qwen-2.5-coder:free` | Multi-file TypeScript synthesis, isolated worktree coding, test harness orchestration, browser CDP scripts. | **WORKTREE READ/WRITE & ALLOWLISTED EXECUTION**. Can modify files in `.worktrees/<task-id>/` and run approved test suites. **CANNOT** push to remote or bypass diff review. | Isolated worktree context, task contract, test outputs. | Retry with backoff. If exhausted, mark task `BLOCKED` and escalate to human. |
| **Tier 3 (Paid Reserve)** | Google Gemini Direct API: `gemini-2.0-flash`, `gemini-1.5-pro` | Multimodal PDF textbook ingestion, full-chapter synthesis (>100k tokens), final certification runs, or explicit `/boost`. | **ANALYSIS & SYNTHESIS ONLY**. No shell execution permissions. | Raw textbook PDFs, curriculum specs. | **NO AUTOMATIC FALLBACK**. Hard locked: `ALLOW_PAID_GEMINI_FALLBACK=false`. |

---

## 4. Execution State Machine & Bounded Repair Policy

### 4.1 State Machine
$$\text{RECEIVED} \rightarrow \text{VALIDATED} \rightarrow \text{RECONNAISSANCE} \rightarrow \text{AUDIT\_READY} \rightarrow \text{PLAN\_READY} \rightarrow \text{AWAITING\_AUTHORIZATION}$$
$$\rightarrow \text{EXECUTING} \rightarrow \text{VERIFYING} \rightarrow \text{REVIEW\_READY} \rightarrow \text{AWAITING\_PROMOTION\_APPROVAL} \rightarrow \text{PROMOTED}$$

**Exception States**: `BLOCKED`, `QUARANTINED`, `FAILED`, `CANCELLED`.
- Every transition is validated by deterministic code; invalid transitions are rejected.
- State persists in durable storage across worker restarts; duplicate webhook deliveries are idempotent.

### 4.2 Bounded Repair Policy
- Initial implementation: 1 attempt.
- Maximum autonomous repair attempts: 2.
- Upon exhausting the second repair attempt:
  1. Halt autonomous implementation immediately.
  2. Preserve the isolated worktree and test diagnostics as quarantined evidence.
  3. Set state to `QUARANTINED` / `BLOCKED`.
  4. Emit a structured incident report and escalate to human review.
  5. Never enter unbounded recursive agent loops.

---

## 5. Detailed Component Specifications

### 5.1 `TaskClassifier` (`packages/dev-agent/task_classifier.ts`) — INTRODUCE_AFTER_APPROVAL
- Classifies incoming requests deterministically into: `AUDIT_ONLY`, `PLAN_ONLY`, `TEST_ONLY`, `IMPLEMENTATION`, `SECURITY_REVIEW`, `DOCUMENTATION`, `BLOCKED`.
- Defaults to `AUDIT_ONLY` on ambiguous or unverified authorization.
- Enforces strict separation between task classification and execution rights; never grants elevated permissions based solely on an LLM-generated label.

### 5.2 `IsolatedWorktreeManager` (`packages/dev-agent/worktree_manager.ts`) — INTRODUCE_AFTER_APPROVAL
- Records base commit SHA before creating an ephemeral branch `dev-agent/<task-id>-<slug>`.
- Verifies that the primary working tree is clean; refuses any operation that could overwrite uncommitted user changes.
- Restricts all file mutations strictly to `.worktrees/<task-id>/`.
- Preserves failed or rejected worktrees as immutable quarantined evidence until authorized cleanup.

### 5.3 `CommandAllowlistExecutor` (`packages/dev-agent/command_executor.ts`) — INTRODUCE_AFTER_APPROVAL
- Executes commands using fixed executable paths and validated argument arrays (no raw shell string evaluation).
- Enforces an allowlist of approved commands (`git`, `node`, `npm test`, `npx tsx`).
- Strictly denies arbitrary shell scripts, shell chaining (`&&`), destructive commands (`rm -rf`, `Remove-Item`), and network access unless separately authorized.
- Applies execution limits: default 30s timeout, 1 MB stdout/stderr cap, and restricted environment variables.

### 5.4 `IndependentDiffReviewer` (`packages/dev-agent/diff_reviewer.ts`) — INTRODUCE_AFTER_APPROVAL
- Directly inspects the actual `git diff` and file tree (never relying on the agent's textual summary).
- Validates the diff against 12 core criteria:
  1. Scope boundary adherence (only authorized files modified).
  2. Secret scanning (zero regex matches for API keys, PATs, tokens).
  3. No unapproved dependency or lockfile changes.
  4. Preserves 20,971,520 byte single-file bundle ceiling for student chapters.
  5. Zero external CDN dependencies.
  6. Mathematical insulation preserved (no translation collisions).
  7. Zero answer spoilers in misconception explanations (`m` field).
  8. TEAS learning state strictly decoupled from telemetry state.
  9. Preserves 100% offline-first functionality.
  10. Strict student data privacy (zero PII in payloads or logs).
  11. GPL-3.0 license isolation (no copyleft contamination in MIT code).
  12. Bounded changes (diff size within authorized budget).
- Reports each check with structured status: `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, or `NOT_APPLICABLE`.

### 5.5 `EvidenceLedger` & `ApprovalGate` (`packages/dev-agent/evidence_ledger.ts`) — INTRODUCE_AFTER_STORAGE_AUTHORITY_REVIEW
- **Storage Authority Alignment**: Aligns with `SUPER_ADMIN_AIOS_V2.md`:
  - Primary: `hatchable` PostgreSQL (`evidence_ledger` table).
  - Local Fallback: Local append-only SQLite/JSON store (`aasha_dev_agent.db`).
  - Does NOT create a competing source of truth for pedagogical TLN or TEAS data.
- **Approval Gate**:
  - Cryptographically binds approval to: `taskId`, `repository`, `baseCommit`, exact `diffHash` (SHA-256), `authorizedScope`, `approverIdentity`, and `expiry`.
  - Invalidation Rule: Any modification to the worktree that alters the diff hash instantly invalidates the earlier approval.
  - An LLM cannot approve its own implementation; passing tests do not equal promotion authorization.

### 5.6 `ReaAdapter` (`packages/dev-agent/rea_adapter.ts`) — INTRODUCE_OPTIONALLY
- Optional module for reverse-engineering tasks.
- If REA is not installed or unreachable, returns `status: REA_UNAVAILABLE` and allows the pipeline to continue.
- Enforces a 30s timeout and a 2 MB output ceiling.
- Treats all output as untrusted external data; REA output is never executed directly.

### 5.7 `n8n Workflows` (`workflows/n8n/`) — INTRODUCE_AFTER_DESIGN_REVIEW
- 10 modular workflow definitions (`WF-01` to `WF-10`).
- Exported JSON files version-controlled with all secrets removed.
- Webhook endpoints enforce HMAC signatures and idempotent deduplication.
- Restart recovery reloads task state without bypassing authorization gates.

---

## 6. Phase Gates & Exit Criteria

### Phase 0: Baseline Audit & Evidence
- **Status**: `REMOTE_AUDIT_COMPLETE_LOCAL_VERIFICATION_PENDING`.
- **Deliverables Delivered**:
  1. `BASELINE_AUDIT.md` (Updated with pinned SHAs and remote sanitization)
  2. `CREDENTIAL_REMEDIATION_RECORD.md` (SEC-001 remediation documented)
  3. `CANONICAL_CONTRACT_REGISTER.md`
  4. `ANTIGRAVITY_INTEGRATION_REPORT.md`
  5. `REA_COMPATIBILITY_REPORT.md`
  6. `FILE_DISPOSITION_MATRIX.md`
  7. `THREAT_MODEL.md` (Updated with outbound-only n8n boundary)
  8. `IMPLEMENTATION_PLAN.md` (v1.1)
  9. `ACCEPTANCE_TEST_PLAN.md`
- **Exit Gate Criteria**: Human reviews credentials remediation, approves storage authority, and authorizes Phase 1.

### Phase 1: Read-Only Governed Prototype
- **Status**: `NOT_AUTHORIZED`.
- **Scope**: Intake classification, repository reconnaissance, contract mapping, read-only GitHub inspection, test discovery, durable task state, evidence reporting.
- **Strictly Prohibited**: Application code writes, unrestricted shell execution, automatic merge, automatic deployment.
- **Exit Gate Criteria**: All prototype safety tests pass; reproducible evidence generated; human reviews implementation diff.

### Phase 2: Bounded Implementation & Verification
- **Status**: `NOT_AUTHORIZED`.
- **Scope**: Isolated worktrees, allowlisted commands, test orchestration, independent diff review, optional REA adapter, human-approved PR preparation.
- **Exit Gate Criteria**: Authorization, recovery, and diff-binding tests pass; Super Admin promotion approval recorded.

---

## 7. Human Review Decisions Required Before Implementation
- **[HR-01]** Approve credential remediation procedure and confirm git remote sanitization.
- **[HR-02]** Confirm canonical repository and contract authority (`SUPER_ADMIN_AIOS_V2.md` & `AGENTS.md`).
- **[HR-03]** Approve storage authority (hatchable PostgreSQL primary / local SQLite fallback).
- **[HR-04]** Approve universal 3-tier Gemini model routing policy.
- **[HR-05]** Approve Phase 1 read-only prototype scope.
