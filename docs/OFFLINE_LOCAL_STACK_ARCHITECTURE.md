# AASHA AIOS: Offline-First Local Stack Architecture & Persistence Hierarchy (Method B)

**Document ID:** ARCH-SPEC-003  
**Status:** APPROVED & ACTIVE  
**Authority:** Human Super Admin / Founder Mandate  
**Cross-References:** `.agents/rules/local_stack_offline_first.md`, `GEMINI.md`, `SUPERBRAIN.md`, `AGENTS.md`

---

## 1. Executive Summary & Core Principle

The Annanth Aasha Learning Ecosystem (AASHA AIOS) operates under **Method B (Local Stack & Offline-First Invariant)** as its non-negotiable architectural foundation. 

This architecture guarantees that:
1. **Zero Cloud Dependency for Core Operations:** Educational chapter compilation, simulation execution, 0-spoiler student assessments, AST knowledge navigation, and local memory engines run with 100% fidelity without network connectivity or cloud CLI authentication.
2. **Deterministic Graceful Degradation:** Absence of a central PostgreSQL instance or cloud database server never halts, errors, or blocks local orchestration. The system automatically and seamlessly defaults to local embedded SQLite (`aasha_operational.db` and `Aasha-AI/server/offline_sync.db`).
3. **Public Repository Zero-Leakage:** Zero cloud service account keys, `.env` production credentials, or OAuth tokens reside on disk or in Git staging.

---

## 2. 4-Tier Persistence & Authority Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   LEVEL 0: CHILD-FACING LEARNING RUNTIME                    │
│   • Single-File Standalone HTML5 WebApps (Strictly <= 20,971,520 bytes)     │
│   • Zero CDN dependencies, inlined Web Audio, SVG geometry, KaTeX fonts    │
│   • Local localStorage / IndexedDB state persistence (<15ms latency)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Async telemetry packet when online)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 LEVEL 1: LOCAL DEVELOPER & AIOS ORCHESTRATOR                │
│   • Native Node 24 SQLite (node:sqlite) + Python sqlite3 (<2ms latency)    │
│   • aasha_operational.db (concept nodes, state machine, memory sync log)    │
│   • Aasha-AI/server/offline_sync.db (evidence ledger, student sync data)    │
│   • Serena MCP Local Semantic Memory (.serena/memories/ - 7/7 online)       │
│   • Graphify AST Knowledge Graph (graphify-out/graph.json - 14,700+ nodes)  │
│   • Local 9Router AI Gateway (http://127.0.0.1:20128 - Tier 1 Free Pool)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Optional outbound push when available)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                LEVEL 2: LOCAL OPTIONAL DOCKER BACKEND (STANDBY)             │
│   • PostgreSQL 17 + FastAPI Backend (docker-compose.yml)                    │
│   • Activated only when Docker Desktop is explicitly running on host        │
│   • Dormant by default to preserve developer host RAM and disk space        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Outbound event replication via webhook)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               LEVEL 3: ASYNCHRONOUS OUTBOUND CLOUD ADAPTERS                 │
│   • Hatchable PostgreSQL MCP (proj_wDCbCrGwuVqy / evidence_ledger table)    │
│   • Hosted n8n Gateway (https://airtribe.app.n8n.cloud/) via HMAC webhooks  │
│   • Strictly optional; failure/absence never interrupts local pipeline      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Method B Operating Laws & Invariant Protocols

### Law 1: Cloud Credential Bypass & Anti-Nagging Guard
- **No Cloud SDK Required:** Neither `gcloud`, Google Cloud SDK, AWS CLI, nor Azure CLI are required or expected on developer workstations.
- **Proactive DAK Suppression:** Prompts from the Data Agent Kit (DAK) plugin requesting `dak-setup`, `gcloud auth`, or GCP project/region selection are proactively ignored and bypassed.
- **Zero Cloud Credentials on Disk:** In accordance with the *Public Repository Zero-Leakage Policy*, no Google Cloud Service Account JSON keys or cloud credential files may be created or staged.

### Law 2: Local SQLite as Primary Evidence Authority
- When a central PostgreSQL server is not running on `localhost:5432`, the system automatically commits evidence ledger entries, concept nodes, and operational state to:
  1. `aasha_operational.db` (Primary operational state at repository root)
  2. `Aasha-AI/server/offline_sync.db` (Evidence ledger fallback with 100% schema parity to PostgreSQL `evidence_ledger`)
- Both SQLite databases use additive DDL migrations (`CREATE TABLE IF NOT EXISTS`), guaranteeing that existing records are never wiped or locked during branch checkouts.

### Law 3: Zero-Disk, Zero-RAM Local AI Model Footprint
- Heavy local LLM inference engines (such as **Ollama**, **llama.cpp**, and **LiteLLM Proxy**) requiring multi-gigabyte GGUF model weights (e.g. Qwen2.5-Coder-7B at 4.5 GB RAM, Llama-3.2-3B at 2.0 GB RAM) are **strictly excluded** from local developer workstation deployment to protect system memory and disk limits.
- Instead, the local AIOS leverages the lightweight **9Router** proxy (`http://127.0.0.1:20128`), consuming **<30 MB RAM** and **0 bytes of model disk storage**, automatically routing routine requests to the Tier 1 OpenRouter Free Pool (`meta-llama/llama-3.1-8b-instruct:free`, `nvidia/nemotron-3.5-lightning:free`, `google/gemini-2.0-flash-exp:free`) with automated circuit breaking.

---

## 4. Database Schema Parity (PostgreSQL <-> SQLite)

The `evidence_ledger` schema is 100% portable across both engines:

```sql
-- SQLite Local DDL (aasha_operational.db / offline_sync.db)
CREATE TABLE IF NOT EXISTS evidence_ledger (
  task_id          TEXT PRIMARY KEY,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  objective        TEXT NOT NULL,
  repository_state TEXT,
  plan             TEXT,
  agents_used      TEXT,
  harness_used     TEXT,
  tools_used       TEXT,
  files_changed    TEXT,
  tests_run        TEXT,
  test_results     TEXT,
  risks            TEXT,
  decisions        TEXT,
  rollback_plan    TEXT,
  final_status     TEXT NOT NULL DEFAULT 'PLANNED'
    CHECK(final_status IN ('PLANNED','RUNNING','BLOCKED','FAILED','VERIFIED','HIL_REQUIRED','COMPLETE'))
);

-- PostgreSQL DDL (Hatchable / Docker Compose)
CREATE TABLE IF NOT EXISTS evidence_ledger (
  task_id          TEXT PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  objective        TEXT NOT NULL,
  repository_state JSONB,
  plan             TEXT,
  agents_used      JSONB,
  harness_used     TEXT,
  tools_used       JSONB,
  files_changed    JSONB,
  tests_run        JSONB,
  test_results     JSONB,
  risks            TEXT,
  decisions        TEXT,
  rollback_plan    TEXT,
  final_status     TEXT NOT NULL DEFAULT 'PLANNED'
    CHECK(final_status IN ('PLANNED','RUNNING','BLOCKED','FAILED','VERIFIED','HIL_REQUIRED','COMPLETE'))
);
```

---

## 5. Future-Ready Local Ecosystem Build Plan & Vision

1. **Phase 1: Pure Local Offline Autonomy (Current)**
   - All state mutations reside in local SQLite (`aasha_operational.db`, `offline_sync.db`).
   - All code symbols and relationships are mapped by Graphify AST (`graphify-out/graph.json`).
   - All operational subagents operate under least-privilege configurations (`inheritMcp: false`).
2. **Phase 2: Hybrid Outbound Sync Adapter (Next)**
   - A background synchronization worker (`sync_offline_evidence.mjs`) periodically checks for network availability and replays uncommitted SQLite evidence ledger rows to Hatchable PostgreSQL via `hatchable.execute_sql`.
   - Idempotent upserts (`INSERT ... ON CONFLICT (task_id) DO UPDATE ...`) ensure zero duplicated evidence records.
3. **Phase 3: Classroom Tablet Mesh Integration**
   - In rural classrooms without Internet, teacher tablets act as local Level 1 SQLite hosts over a peer-to-peer Wi-Fi hotspot (`mDNS`).
   - Student tablets running single-file HTML5 packages send compressed delta sync packets (`/api/events/batch`) to the teacher station.
   - When the teacher returns to cellular connectivity, the station pushes batched impact metrics to Hatchable PostgreSQL.
