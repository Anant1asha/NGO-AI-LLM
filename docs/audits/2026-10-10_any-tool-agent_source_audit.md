# AASHA Any-Tool Agent Runtime: Source-Backed Audit Baseline

- **Audit ID:** AASHA-AUDIT-2026-10-10-01
- **Status:** STATIC SOURCE INSPECTION; INCOMPLETE; NO IMPLEMENTATION APPROVAL
- **Prepared:** 2026-10-10
- **Audit branch:** `audit/2026-10-10-source-backed-baseline`
- **Primary repository snapshot:** [NGO-AI-LLM `master` @ `43760f8a9937a282eaff169ea5bb1a9a80854d74`](https://github.com/Anant1asha/NGO-AI-LLM/commit/43760f8a9937a282eaff169ea5bb1a9a80854d74)
- **Related implementation snapshot:** [Aasha-AI `main` @ `5ab3f2665f862db7cbf2d42b691a480a0a35b40e`](https://github.com/Anant1asha/Aasha-AI/commit/5ab3f2665f862db7cbf2d42b691a480a0a35b40e)

## 1. Executive finding

The inspected source establishes useful learning-pipeline, provider-routing, tool-scaffold, governance-documentation, and assessment foundations. It does **not** establish that the current system already has fully dynamic tool discovery, safe capability negotiation, or end-to-end runtime portability.

This audit is a read-only source inspection of selected files and repository metadata. No local checkout, build, unit test, integration test, provider call, or runtime certification was executed as part of this audit. Existing evidence documents are historical claims until re-run against the exact source snapshot.

## 2. Repository snapshots and authority

| Item | Observed evidence | Interpretation / limit |
|---|---|---|
| NGO-AI-LLM default branch | GitHub repository metadata reported `master`; commit snapshot above | Use as audit entry point, not automatically the sole canonical implementation. |
| NGO-AI-LLM branches | Branch listing returned only `master` at inspection | Does not prove there are no tags, forks, or unlisted external workspaces. |
| NGO-AI-LLM Actions | GitHub Actions runs endpoint returned `total_count: 0` | No Actions-run evidence was available from that endpoint; does not prove no other CI system exists. |
| Aasha-AI main | Commit snapshot above | Contains learning/impact implementation and routing code; its branch set includes numerous specification and feature branches. |
| Canonical cross-repository authority | Not conclusively resolved by this source pass | Human architecture decision required before cross-repo code changes or consolidation. |

## 3. Source evidence register

### E-01: Multi-agent TUI runner is a scaffold, not a live model loop

File: [`multi-agent-tui/src/agent.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/agent.ts)

Observed:
- The file labels the runner a placeholder and says the OpenRouter agent implementation is mocked.
- The intended agent creation/run code is commented out.
- `runAgent` returns the literal `Mock result from ...` string.
- Tool selection is a local role-based filter over `ALL_TOOLS`.

Conclusion: this file does not implement a live model-agent loop. A passing test of this return path would not prove model execution or tool execution.

### E-02: Human approval is disabled in the TUI configuration

File: [`multi-agent-tui/src/config.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/config.ts)

Observed: `harness.autoApproveAll` is `true`, with a comment stating HIL is disabled.

Conclusion: this configuration conflicts with the stated AASHA governance target for protected actions. Do not enable this configuration for consequential or canonical operations.

### E-03: Tool list is statically assembled

File: [`multi-agent-tui/src/tools/index.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/tools/index.ts)

Observed: six local tool definitions are imported and assembled into the `ALL_TOOLS` array: file read, file write, file edit, shell, sub-agent, and plan.

Conclusion: dynamic discovery from external capability sources is not demonstrated by this registry. This is not proof that no other discovery code exists elsewhere; repository-wide search and runtime tests remain required.

### E-04: Shell tool accepts arbitrary command strings

File: [`multi-agent-tui/src/tools/shell.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/tools/shell.ts)

Observed: the input schema accepts a command string and passes it to `child_process.exec`.

Conclusion: the inspected tool has no visible command allowlist or capability-scoped execution policy. Treat as high risk. Replace with policy-mediated, narrowly scoped execution or keep disabled until controls and adversarial tests exist.

### E-05: File write/edit operations lack visible workspace confinement

Files:
- [`file_write.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/tools/file_write.ts)
- [`file_edit.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/tools/file_edit.ts)

Observed:
- Write accepts an absolute path, creates parent directories, and writes content.
- Edit reads a path and applies search/replace edits.
- The inspected implementations show no repository-root confinement, protected-path policy, or approval check.

Conclusion: scope and authorization controls need to be enforced outside or inside these tools before they are available to an autonomous agent.

### E-06: Python chapter pipeline is a separate execution path

File: [`multi-agent-tui/src/pipeline_runner.ts`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/multi-agent-tui/src/pipeline_runner.ts)

Observed:
- The runner spawns a Python interpreter for `aasha-pipeline-with-master-json`.
- It parses JSON-line events and resolves a pipeline result.
- It determines success using the process exit code or a completion event, plus existence of the HTML output path.

Conclusion: this pipeline and the TUI agent scaffold are distinct orchestration paths. Their ownership of job state, validation, repair, and release gates must be mapped before consolidation. Output-file existence alone is not certification.

### E-07: Aasha-AI has a provider-specific router

File: [`llm_router.ts`](https://github.com/Anant1asha/Aasha-AI/blob/main/llm_router.ts)

Observed:
- The router defines a fixed `ProviderId` union and a hard-coded provider configuration/routing chain.
- Provider credentials are read from provider-specific environment variable names.
- Task types select preconfigured routing chains.

Conclusion: the current design has multiple provider routes, but a generic capability contract and provider-independent runtime are not demonstrated by this file. Multi-provider routing is not equivalent to tool discovery or complete portability.

### E-08: Deterministic agent roles return status without invoking the described scripts

File: [`agent_orchestrator.ts`](https://github.com/Anant1asha/Aasha-AI/blob/main/agent_orchestrator.ts)

Observed:
- The IngestAgent, QAAgent, and BrowserTesterAgent are configured as deterministic roles.
- The deterministic branch returns `{ status: 'success', method: 'deterministic' }` immediately.
- The prompts describe Python extraction, QA harness, and browser testing, but this branch does not invoke those scripts.

Conclusion: this branch reports a success-shaped result without demonstrating that the described work ran. Replace with real injected executors and evidence-backed result types before treating it as execution evidence.

Additional observed risk in the same file: after a failed `contextBus.validateOutput`, a repair call can replace the response; the displayed code then records the output with `gatekeeperPassed: true` without showing a second validation of the repaired response. This must be tested and corrected before any output can be certified.

### E-09: Repository state/evidence documents are dated and record incomplete status

Files:
- [`docs/aios/00_PROJECT_STATE.md`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/docs/aios/00_PROJECT_STATE.md)
- [`docs/aios/04_ARCHITECTURE.md`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/docs/aios/04_ARCHITECTURE.md)
- [`docs/aios/06_TEST_CHECKLIST.md`](https://github.com/Anant1asha/NGO-AI-LLM/blob/master/docs/aios/06_TEST_CHECKLIST.md)

Observed:
- The state snapshot marks `AGENT_STATUS: PARTIAL` and feature FEAT-002 `IN_PROGRESS`.
- The architecture document labels the full autonomous loop experimental.
- The test checklist records evidence from September 8, 2026 and reports multiple chapter failures, including 255 reported zero-spoiler leaks across four chapters and a 6.78 MB Fractions artifact.

Conclusion: those are repository-recorded historical statuses, not current test results. Re-run relevant tests at the inspected commit and update status only from captured output.

### E-10: Existing AI rules prescribe a vendor hierarchy

File: [`PROJECT_AI_RULES.md`](https://github.com/Anant1asha/Aasha-AI/blob/main/PROJECT_AI_RULES.md)

Observed: the current rule prioritizes Claude Code with OpenRouter, while describing Freebuff as a local tool; it also requires registry-first reuse for learning experiences.

Conclusion: the provider hierarchy conflicts with the target of no permanent provider dependency. Preserve registry-first resource reuse and other compatible learning rules; propose replacing vendor hierarchy with provider-neutral policy, subject to human approval.

## 4. Current Reality → Target Architecture gap matrix

| ID | Current source evidence | Gap | Recommended action | Gate |
|---|---|---|---|---|
| G-01 | TUI agent returns mock result | No live model-agent loop in inspected runner | REFACTOR behind provider-neutral execution interface | Unit + integration tests |
| G-02 | Static `ALL_TOOLS` array | Dynamic discovery unproven | ADD discovery-source and capability-descriptor contracts; implement only after source-wide search | Descriptor, discovery, revocation tests |
| G-03 | `autoApproveAll: true` | Human approval bypass is configured | REFACTOR to default-deny policy and explicit approval requirements | Negative authorization tests |
| G-04 | `exec(command)` | Arbitrary shell command execution | REFACTOR to allowlisted/scoped capabilities or disable | Adversarial command tests |
| G-05 | Unconfined-looking path inputs | Filesystem boundary unproven | REFACTOR to canonical workspace-root/path and protected-path checks | Traversal/symlink/path tests |
| G-06 | Fixed provider list in `llm_router.ts` | Provider portability contract unproven | ADAPT behind typed provider adapter; preserve existing router until parity tests pass | Same-contract multi-adapter tests |
| G-07 | Deterministic role returns success object | Described script work is not executed in that branch | REFACTOR to injected deterministic executors and typed evidence | Tests prove executor invocation and failure propagation |
| G-08 | Repair output not visibly revalidated | Invalid repaired output may be recorded as passed | REFACTOR validation loop; fail closed after two repair attempts | Invalid-after-repair test |
| G-09 | Separate TUI and Python pipeline paths | Job/state/release authority may be duplicated | RETAIN both during audit; map contracts before consolidation | Cross-path lifecycle tests |
| G-10 | Historical status/test docs | Current state can be overstated | UPDATE only after exact-commit test run | Captured command/output/commit evidence |
| G-11 | Vendor-specific policy in project rules | Conflicts with provider neutrality | PROPOSE policy-level ADR; do not silently rewrite canonical policy | Human approval |
| G-12 | No Actions runs returned | CI evidence unavailable in checked endpoint | ADD/repair CI only after existing CI discovery and test command audit | CI run with captured artifacts |

## 5. File disposition proposal

This is a proposal for review, not an instruction to immediately alter all files.

| File/path | Proposed disposition | Rationale |
|---|---|---|
| `docs/aios/02_DECISIONS.md` | RETAIN; append superseding record only after approval | Existing governance says historical decisions should not be erased. |
| `docs/aios/05_CONSTRAINTS.md` | RETAIN; reconcile with canonical child privacy/offline rules | Useful constraints; resolve any conflicting limits before changing them. |
| `docs/aios/06_TEST_CHECKLIST.md` | RETAIN; append dated current-run evidence | Historical evidence must remain distinguishable from current results. |
| `multi-agent-tui/src/agent.ts` | REFACTOR | Replace mock production path; separate test doubles explicitly. |
| `multi-agent-tui/src/config.ts` | REFACTOR | Remove auto-approval default for protected actions. |
| `multi-agent-tui/src/tools/index.ts` | ADAPT | Keep static tools as one possible discovery source; do not confuse it with dynamic discovery. |
| `multi-agent-tui/src/tools/shell.ts` | REFACTOR or disable pending safe executor | Current command boundary is too broad for autonomous use. |
| `multi-agent-tui/src/tools/file_write.ts`, `file_edit.ts` | REFACTOR | Enforce path scopes and protected-path policies. |
| `multi-agent-tui/src/pipeline_runner.ts` | RETAIN pending lifecycle mapping; then ADAPT | It already connects to the Python pipeline; avoid replacing before comparing behavior. |
| `Aasha-AI/llm_router.ts` | RETAIN during audit; ADAPT behind provider contract after approval | Existing routing may be reused as one adapter. |
| `Aasha-AI/agent_orchestrator.ts` | REFACTOR after cross-path mapping | Deterministic success shortcut and post-repair validation require correction. |
| New capability contract/adapter modules | ADD only after approved ADR | Avoid creating a second canonical state machine or duplicate contract set. |
| New tests | ADD alongside each approved change | Prove negative cases and portability, not just happy paths. |

## 6. Required test work before implementation approval

1. Install dependencies only in an isolated checkout; inspect lockfiles and scripts first.
2. Run existing tests and build commands at the pinned commits; capture command, exit code, environment versions, and output.
3. Test mock-runner paths cannot be counted as real model execution or certification.
4. Test deterministic roles actually invoke their intended executors and propagate failures.
5. Test repaired outputs are validated again and never recorded as passed without that validation.
6. Test path traversal, absolute-path escapes, symlinks, command injection, privilege escalation, revoked capability, and unauthorized state transitions.
7. Test capability selection against schema mismatch, permissions, cost, timeouts, unavailable providers, and version conflict.
8. Test provider and workflow adapters independently; core tests must run with no API keys and no mandatory workflow vendor.
9. Re-run the current chapter zero-spoiler and offline/bundle tests against the actual source artifacts.
10. Record unavailable services as NOT RUN/BLOCKED, never PASS.

No test in this list is claimed to have run during this source inspection.

## 7. Open questions requiring human decision

- Which repository/file is authoritative for the canonical control-plane state machine and durable evidence ledger?
- Is `NGO-AI-LLM` the governance/orchestration workspace while `Aasha-AI` remains the learning implementation, or should another repository/branch be designated?
- Which current persistence implementation owns job state and immutable artifacts? Do not assume a technology from older notes without locating and verifying the implementation.
- Which capability-discovery sources are allowed initially: repository-local registry only, explicitly configured MCP/API sources, or both?
- What approval policy governs shell-like operations, protected files, provider credential access, architecture changes, and publication?
- Which chapter-size limit is canonical where the repository's 1 MB documentation conflicts with the 20 MiB child-bundle ceiling recorded in later project context?
- Which CI/test command is authoritative for the current monorepo and nested repositories?

## 8. Audit status

**STATIC SOURCE FINDINGS: RECORDED.**
**RUNTIME STATUS: NOT VERIFIED BY THIS AUDIT.**
**DYNAMIC DISCOVERY: NOT DEMONSTRATED.**
**SAFE CAPABILITY NEGOTIATION: NOT DEMONSTRATED.**
**PROVIDER/WORKFLOW PORTABILITY: NOT CERTIFIED.**
**IMPLEMENTATION APPROVAL: NOT GRANTED.**

Next permitted step: human review of this artifact and the proposed architecture decision. After approval, execute a pinned-checkout test pass and implement incrementally on an isolated branch. Do not merge or promote automatically.
