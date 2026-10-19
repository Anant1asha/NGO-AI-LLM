---
description: Enforces Method B (Local Stack / Offline-First) architecture. Forbids gcloud CLI installation, disables cloud SDK setup prompts, and routes all storage, database, and analytics to local engines.
globs: ["**/*"]
---

# Local Stack & Offline-First Invariant (Method B)

This rule establishes **Method B (Local Stack)** as the non-negotiable default for all data processing, storage, analytics, and tool integrations in this workspace.

## 1. Absolute Cloud CLI & Credential Bypass
- **No `gcloud` or Cloud SDK Required**: Agents and subagents must NEVER prompt the user to install `gcloud`, Google Cloud SDK, AWS CLI, or Azure CLI.
- **Ignore DAK Setup Nagging**: Proactively suppress or ignore session-start prompts from the Data Agent Kit (DAK) plugin requesting `dak-setup`, `gcloud auth`, or GCP project/region selection.
- **Zero Cloud Credentials on Disk**: In accordance with the *Public Repository Zero-Leakage Policy*, never prompt for, generate, stage, or store Google Cloud Service Account JSON keys or cloud credential files in this repository.

## 2. Local-First Replacements
Whenever a task requires storage, database, or analytics capabilities, use only the verified local stack:
- **Asset & Content Storage (replaces GCS/S3)**: Local directory trees in `Aasha-AI/content/`, `Aasha-AI/chapters/`, and `Aasha-AI/experience_registry/`. If S3/GCS API emulation is strictly required by an external tool, run an isolated local emulator (e.g., `fake-gcs-server` or `MinIO` on `localhost`) with zero cloud keys.
- **Analytics & SQL (replaces BigQuery/Snowflake)**: In-process **DuckDB** or embedded **SQLite** directly over local JSON, CSV, and Parquet files.
- **Operational State & Memory (replaces Cloud SQL/Spanner)**: Local Native SQLite (`aasha_operational.db`), Mem0 episodic store (`.scratch/mem0_store.json`), and AST Codebase Graph (`graphify-out/graph.json`).
- **Language Intelligence & LSPs**: Active local language servers (`typescript-lsp`, `pyright-lsp`, `gopls-lsp`) configured in `.claude/settings.json`.

## 3. Remote Automation Boundary
- If external cloud automation or curriculum ingress is explicitly requested by the user, route strictly through the hosted **n8n gateway** (`https://airtribe.app.n8n.cloud/`) via outbound webhooks using the `/n8n-trigger` skill. Never attempt to orchestrate cloud workloads from the local developer terminal.
