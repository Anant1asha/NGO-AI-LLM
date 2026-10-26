---
description: Enforces Method B (Local Stack / Offline-First) architecture. Forbids gcloud CLI installation, disables cloud SDK setup prompts, and routes all storage, database, and analytics to local engines.
globs: **/*
alwaysApply: true
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

## 4. Tier-0 Deep Offline Vectorization & Synthesis Invariant
- **No Network Dependency for Chapter Generation**: The pipeline must be capable of generating 100% compliant, interactive HTML5 chapters completely offline via `--offline` using `DeepOfflineVectorizer` and `OfflineSynthesizer`.
- **Zero Placeholder Guarantee**: Scanned pages or pages with drawings must never degrade to generic placeholder strings (`"[Page X: Visual diagram or illustration content]"`). They must extract vector SVG geometry, classified diagrams (`number_line`, `balance_scale`, `geometric_circle`, `coordinate_graph`), and KaTeX formulas.
- **Thread-Safe PyMuPDF Operations**: When accessing PDF documents in parallel worker pools, always open per-thread document handles (`fitz.open(str(pdf_path))`) to prevent C-level concurrency faults.

## 5. Copyleft Cleanroom Isolation Invariant (GPL-3.0 Guardrail)
- Foundations or libraries licensed under GPL-3.0 (e.g. PhET, Escapp, Code for Life) must strictly follow the **EXTRACT** or **INSPIRE** cleanroom strategy:
  1. Extract only mathematical formulas, physical parameters, and public game mechanics.
  2. Implement simulations inside isolated `<aasha-sim>` Web Component adapters.
  3. Never copy raw GPL-3.0 source code or bundled assets directly into MIT-licensed chapter templates.

## 6. Distractor Anti-Spoiler Sanitization Invariant (L-Truth Rule #1)
- Misconception explanations in assessment distractors must NEVER reveal or quote the correct target answer or numerical value.
- The pipeline orchestrator must enforce `sanitize_spec_misconceptions()` before HTML assembly, replacing accidental answer leaks with pedagogical reasoning clues.
