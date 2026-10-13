# BASELINE_AUDIT.md
# AASHA AIOS Development Agent — Baseline Audit Report
**Authority**: Annanth Aasha Foundation / Super Admin Governance  
**Date**: 2026-10-12  
**Audit Stage**: Phase 0 — `REMOTE_AUDIT_COMPLETE_LOCAL_VERIFICATION_PENDING`  
**Evaluator**: Principal AI Systems Architect & Security QA Lead  

---

## 1. Executive Summary

This baseline audit establishes the empirical, source-backed foundation for the **AASHA AIOS Development Agent** across the primary repositories, runtime environments, and orchestration layers. In accordance with the mandatory operating tenets (**NO PRESUMPTION**, **INSPECT BEFORE DESIGNING**, **ZERO TOKEN BLEED**, and **SAFE FILE OPERATIONS**), every claim in this document is categorized by evidentiary status (FACT, INFERENCE, ASSUMPTION, UNKNOWN).

Implementation code generation is strictly blocked until human review and approval are recorded.

---

## 2. Pinned Repository & Working Tree Inventory

### 2.1 Pinned Repositories
1. **Root Repository (`NGO-AI-LLM`)**:
   - **Local Path**: `c:\Users\admin\Downloads\NGO AI LLM`
   - **Current Branch**: `master`
   - **Pinned HEAD Commit SHA**: `43760f8981600f6bc1e43d3e69188a803716a5b2` (`43760f8`)
   - **Commit Subject**: `docs(rules): enforce public repository zero-leakage privacy and security invariant`
   - **Remote Origin URL (Sanitized)**: `https://github.com/Anant1asha/NGO-AI-LLM.git`
   - **Working Tree State**: Unstaged modifications in `.agents/skills/aasha-ecosystem/SKILL.md` and `.serena/project.yml`.

2. **Sub-Repository (`Aasha-AI`)**:
   - **Local Path**: `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`
   - **Current Branch**: `aios/v2-bootstrap`
   - **Pinned HEAD Commit SHA**: `61fce9d53cf8e431844d242ce9f47567409582f1` (`61fce9d`)
   - **Remote Origin URL (Sanitized)**: `https://github.com/Anant1asha/Aasha-AI.git`
   - **Working Tree State**: Uncommitted modifications across 17 files; 34 untracked benchmark, verification, and script files.
   - **Remediation Status (SEC-001)**: Git remote URLs for both repositories have been successfully stripped of the embedded `github_pat_` token. Remote configurations now point cleanly to canonical HTTPS endpoints.

### 2.2 Subsystems Inventory
1. **`Aasha-AI/Aasha-AIOS/`**:
   - Structured into `layer-1-core/`, `layer-2-education/`, and `layer-3-product/`.
   - Contains canonical governance specifications: `AGENTS.md` (v1.0.0), `SUPER_ADMIN_AIOS_V2.md` (v2.0.0), and 6 pipeline agent definitions.
   - **Role**: Authoritative governance, architectural contracts, and layer boundary rules.
2. **`Aasha-AI/aasha-pipeline-with-master-json/`**:
   - Contains Python/Node hybrid ingestion scripts, PyMuPDF extractors, `MASTER_PROMPT.json`, and single-file HTML templates (`v5-engine-template.html`).
   - **Role**: Legacy ingestion harness and early template reference.
3. **`Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/`**:
   - Contains monolithic microservice definitions (`apps/`, `services/`, `simulations/`, `database/`).
   - **Role**: Reference repository for historical TEAS and impact schemas.
4. **Active Production Core (`Aasha-AI/packages/` & `Aasha-AI/agent_orchestrator.ts`)**:
   - Active TypeScript implementation of `ContextBus`, `v6_compiler.ts`, `domain_sim_generators.ts`, `openrouter_client.ts`, and `admin_memory_cli.ts`.
   - **Role**: Active operational engine currently driving benchmark certification.

---

## 3. Runtime & Execution Environment Baseline

| Environment / Service | Verified State | Version / Evidence | Boundary / Risk |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 10/11 x64 | PowerShell 5.1 / Node v22.x | Safe path handling, verbatim `@'...'@` strings required |
| **Node.js Runtime** | Active | Node.js v22.x with `tsx` 4.19.3 | Supported TypeScript execution via `npx tsx` |
| **Antigravity AIOS** | Active Host IDE | Session Conversation ID `f0ebf71d-c24b-45f6-8774-1abdda9cbe95` | Primary control plane and local developer environment |
| **Antigravity MCP Directory** | Discovered | `C:\Users\admin\.gemini\antigravity\mcp\` | Hosts 11 MCP servers (`github-mcp-server`, `serena`, `hatchable`, `playwright`, `n8n`, etc.) |
| **Hosted n8n Instance** | Active & Connected Outbound | `https://airtribe.app.n8n.cloud/mcp-server/http` via `mcp-remote` | Authenticated outbound HTTPS client connection. **Zero unauthenticated inbound listening ports on local workstation.** |
| **Gemini Model Access** | Configured via Router | `Aasha-AI/.env.example` & `openrouter_client.ts` | Tier 3 Reserve (Locked: `ALLOW_PAID_GEMINI_FALLBACK=false`); Tier 1 OpenRouter free models active |
| **REA Reverse Engineering** | Not Installed | `Get-Command rea` returned NOT_FOUND | Optional adapter; must not be a hard dependency |
| **Git / GitHub** | Active | Git 2.x; `github-mcp-server` registered | Worktree isolation mandatory for all implementations |

---

## 4. Test Suite & Verification Baseline

| Test Command | Working Directory | Observed Result | Evidence Details | Local Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| `node benchmarks/qa_ltruth_benchmark.js` | `Aasha-AI` | **PASS (100/100)** | 10 chapters tested, 140 questions, 395 misconceptions, 0 spoilers, 0 math collisions | Executed locally via PowerShell |
| `node ../tests/e2e_all_chapters_suite.js` | `Aasha-AI` | **PASS (36/36)** | 6 chapters tested: 20MB ceiling, zero CDN scripts, math insulation, mobile layout verified | Executed locally via PowerShell |
| `npx tsx tests/test_approval_authority.ts` | `Aasha-AI` | **PASS (1/1)** | Signature verification binds trusted reviewer, action, artifact, and version | Executed locally via PowerShell |
| `npx tsx tests/test_certification_gate.ts` | `Aasha-AI` | **PASS (1/1)** | VersionManager enforces signed evidence and blocks unauthorized state mutation | Executed locally via PowerShell |
| `npx tsx tests/test_registry_protocol_suite.ts` | `Aasha-AI` | **PASS (11/11)** | 11/11 pass: SHA-256 hashing, offline gate failure blocks promotion, zero URL leaks | Executed locally via PowerShell |
| `npx tsx tests/test_fault_injection_hardening.ts` | `Aasha-AI` | **PASS (10/10)** | 10/10 pass: 2-tier repair exhaustion quarantine, spoiler detection, timeout retry, ledger immutability | Executed locally via PowerShell |

---

## 5. Uncertainty & Verification Gaps Register

1. **[VERIFICATION-01] n8n Cloud Webhook Routing**: How do external GitHub events reach `airtribe.app.n8n.cloud`?
   - *Status*: Verified that n8n runs hosted on Airtribe Cloud. Webhooks ingress directly from GitHub to the cloud instance.
2. **[VERIFICATION-02] Antigravity Local Worker**: Since Antigravity connects outbound to n8n via `mcp-remote`, can n8n initiate tasks down to local Antigravity?
   - *Status*: Direct inbound connections into Antigravity are rejected. In Phase 1, workflow is GitHub-mediated (n8n reviews PRs/issues). In Phase 2, an authenticated outbound worker polls n8n.
3. **[VERIFICATION-03] REA Deployment**: REA remains uninstalled on host; isolated behind an optional wrapper that returns `REA_UNAVAILABLE`.
