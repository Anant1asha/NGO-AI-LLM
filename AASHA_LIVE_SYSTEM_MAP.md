# AASHA AIOS Live System Map & Environment Specification

**Document Version**: 1.0.0  
**Generated Date**: 2026-11-14  
**Classification**: LIVE_VERIFIED (Step 1 Complete)  
**Execution Plane**: Windows Local Workstation (`c:\Users\admin\Downloads\NGO AI LLM`)  
**Target Architecture**: Annanth Aasha Learning Ecosystem — AASHA AIOS

---

## 1. Executive Summary & Verification Classification

This document records the empirical live reality of the AASHA AIOS development environment. Every claim herein is classified in accordance with the 7-level Truth-Seeking Protocol:
- **`LIVE_VERIFIED`**: Directly probed via local CLI commands, runtime inspections, and filesystem queries during this session.
- **`ACCEPTED_LOCAL_STATE`**: Explicitly sanctioned offline/local operational configurations per canonical governance (`local_stack_offline_first.md`).
- **`UNKNOWN / PENDING`**: Awaiting external/remote probe or downstream worker audit.

---

## 2. Source Repositories & Git DAG Topology

The workspace operates as a multi-root dual-repository structure on Windows:

| Repository Identifier | Absolute Filesystem Root | Active Branch | Tracking Remote & Upstream | Current Commit SHA | Working Tree Status | Remote Default Trunk |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Root (`NGO AI LLM`)** | `c:\Users\admin\Downloads\NGO AI LLM` | `aios/v2-bootstrap` | `origin/aios/v2-bootstrap` (Synchronized) | `9f55623` | Modified: `PC_ANTIGRAVITY_STATE.json`, `scripts/aasha_continuous_loop.mjs`<br>Untracked: `LOCAL_AIOS_MASTER_PROMPT_PHASE_H016.json` | `origin/master` |
| **Sub-repository (`Aasha-AI`)** | `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI` | `aios/v2-bootstrap` | `origin/aios/v2-bootstrap` (Synchronized) | `185a54d` | Modified: `aasha-pipeline-with-master-json/config/candidate_dictionary_hi.json` | `origin/main` |

### Dual-Sync DAG Governance
Both repositories share the active task branch `aios/v2-bootstrap`. Gate 6 release promotions enforce dual-sync to remote trunks (`master` on root, `main` on `Aasha-AI`) using the `-s ours` strategy for safe reconciliation of diverged histories without working tree contamination.

---

## 3. Host Runtime & Toolchain Baseline

All tools and runtimes were empirically inspected in the active host environment:

| Tool / Runtime | Live Detected Version | Binary / Invocation Path | Operational Verification Note |
| :--- | :--- | :--- | :--- |
| **Node.js** | `v24.19.0` | System PATH | Node 24 native ESM execution active (`import.meta.url`, pure `.mjs` without TS decorators). |
| **npm** | `11.17.0` | System PATH | Monorepo package management. |
| **npx** | `11.17.0` | System PATH | CLI executor. |
| **Python** | `3.15.0b3` | System PATH | Standard Python runtime. |
| **PyMuPDF (`fitz`)** | `1.28.2` | Python runtime | Thread-safe native vector and PDF drawing extraction (`get_drawings()`). |
| **Pillow (`PIL`)** | `12.3.0` | Python runtime | Image processing and raster stroke thresholding. |
| **SQLite3 CLI** | `3.53.2` | System PATH | Local dual-plane relational database engine. |
| **uv** | `0.11.21` | System PATH | Fast Python tool & dependency management. |
| **TypeScript** | `5.9.3` | `Aasha-AI/node_modules/.bin/tsc` | Core compiler and typechecker. |
| **Git** | `2.54.0.windows.1` | System PATH | Version control and worktree manager. |

---

## 4. Local Services, Persistence & Offline Stack (Method B)

Per `local_stack_offline_first.md`, Method B mandates complete independence from mandatory cloud credentials and cloud CLIs (`gcloud`, `aws`, `az` are bypassed):

| Service / Database | Address / Target | Live Probe Status | Verification Category | Invariant & Operational Role |
| :--- | :--- | :--- | :--- | :--- |
| **9Router AI Gateway** | `http://127.0.0.1:20128` | Not reachable (dormant) | `ACCEPTED_LOCAL_STATE` | Zero-token-bleed local gateway proxy; launcher script exists (`scripts/ensure_9router.js`). Fast-fails to Tier 1 free pool on disconnect. |
| **PostgreSQL Database** | `localhost:5432` | Connection refused | `ACCEPTED_LOCAL_STATE` | PostgreSQL is the central authority in prod; absence on dev workstation is accepted local state. All writes persist gracefully to local SQLite. |
| **`aasha_operational.db`** | `c:\Users\admin\Downloads\NGO AI LLM\aasha_operational.db` | Exists (73.7 KB) | `LIVE_VERIFIED` | 7 tables: `concept_nodes` (7), `operational_state` (6), `memory_sync_audit_log` (10), `cross_grade_knowledge_nodes` (40), `cross_grade_prerequisite_edges` (36), `classroom_telemetry_events` (1), `ngo_impact_snapshots` (0). |
| **`offline_sync.db`** | `Aasha-AI/server/offline_sync.db` | Exists (36.8 KB) | `LIVE_VERIFIED` | 3 tables: `student_sync_data` (25), `evidence_ledger` (35), `pipeline_jobs` (0). |
| **Serena Local Memory** | `.serena/memories/*.md` | 7/7 files present | `LIVE_VERIFIED` | Primary local semantic memory: `conventions`, `core`, `local_memory`, `memory_maintenance`, `suggested_commands`, `task_completion`, `tech_stack`. |
| **Graphify AST Graph** | `graphify-out/graph.json` | Exists (17.1 MB) | `LIVE_VERIFIED` | Offline structural code graph (8,000+ AST nodes & edges) for symbol discovery without LLM tokens. |
| **Mem0 Episodic Store** | `.scratch/mem0_store.json` | Exists (11.9 KB) | `LIVE_VERIFIED` | Offline episodic interaction store. |

---

## 5. Multi-Agent Topology & Skills Inventory

### 5.1 Operational Multi-Agent Tier (Standby by Default per Rule 1)
Registered in `.agents/agents/` (Least-privilege, `inheritMcp: false`):
1. `delivery-coordinator`: Chief-of-Staff-equivalent delivery logistics (read-only).
2. `market-researcher`: External K-12 education intelligence & competitor benchmarking (read-only + web).
3. `growth-marketer`: Impact storytelling, teacher guides & onboarding (read-only + web).
4. `full-stack-developer`: Scoped engineering, `<aasha-sim>` component wrapping (sandboxed tools).
5. `debug-test-engineer`: Failure reproduction, log diagnosis, targeted test runs (sandboxed tools).

### 5.2 Canonical Pedagogical Chapter Pipeline Agents (`Aasha-AI/agents.json`)
Sovereign pipeline agents for textbook-to-HTML5 synthesis:
1. `AGT-001 IngestAgent`: PyMuPDF / deep vector parsing.
2. `AGT-002 AnalysisAgent`: Pāṇinian Kāraka decomposition & Bloom's taxonomy mapping.
3. `AGT-003 DesignAgent`: F01–F20 Foundation simulations.
4. `AGT-004 AssessmentAgent`: 3-Tier gamified assessments & 4-tier progressive hints ($H_1 \to H_4$).
5. `AGT-005 LLEAgent`: Indic bilingual glossing (Hindi/English) & KaTeX math insulation.
6. `AGT-006 QAAgent`: 200+ L-Truth verification points.
7. `AGT-007 BrowserTesterAgent`: Headless Chrome CDP & $\ge 44 \times 44\text{px}$ touch target audit.

### 5.3 Registered Skills Inventory (26 Active Skills in `.agents/skills/`)
1. `a11y-touch-auditor`: Headless CDP & touch target verification.
2. `aasha-agent-team`: Runbook for 5 workspace subagents.
3. `aasha-ecosystem`: Super Admin memory & experience foundations.
4. `aasha-ecosystem-orchestrator`: Autonomous loop engine.
5. `aasha-prompt-compiler`: Pāṇinian Kāraka prompt compilation pipeline.
6. `anti-bleed`: 4-tier LLM routing audit & circuit breaker enforcement.
7. `api-routing`: OpenRouter free pool rotation & reserve policies.
8. `cat-assessment-authoring`: Psychometric IRT & CAT authoring.
9. `chapter-compile`: Autonomous textbook chapter compiler.
10. `ci-workflow-sanitizer`: GitHub Actions workflow audit & secret hygiene.
11. `ecosystem-identity-audit`: Repository identity & anti-hallucination verification.
12. `gamified-quest-architect`: 3-tier gamified mastery loops & reward mechanics.
13. `graphify`: AST knowledge graph query & shortest path traversal.
14. `jagiye-maakiran`: Master ecosystem wake-up and Serena memory self-healing.
15. `karaka-compiler`: Pāṇinian Kāraka decision synthesis engine.
16. `laya-cadence`: 5-phase daily operational cadence.
17. `lsp-toolchain-bootstrap`: Language server protocol runtime auditor.
18. `n8n-trigger`: n8n outbound webhook automation orchestrator.
19. `open-source-harvesting`: Open-source educational asset harvester (PhET, JSXGraph, etc.).
20. `rea-environment-runbook`: Reverse Engineer Anything & Ghidra runbook.
21. `reasoning-check`: 7-step Rigorous Truth-Seeking Protocol.
22. `router-gateway-audit`: 9Router health & zero-secret .env audit.
23. `sprint-verifier`: 5-pillar verification & hardening scorecard.
24. `universal-sim-engine`: 60 FPS simulation engine synthesis.
25. `uv`: Fast Python package manager bootstrap.
26. `workflow-skill-creator`: Interaction-to-skill distillation.

### 5.4 Active MCP Servers
`graphify`, `supabase`, `hatchable`, `serena`, `StitchMCP`, `github-mcp-server`, `n8n`, `context7`, `playwright`, `sequential-thinking`, `filesystem`, `postgres`, `lovable`, `rea`.

### 5.5 External Plugin Authentication Status
- `gdrive`: Connected (`mylifemyfae@gmail.com`).
- `gsheets`: Not connected.
