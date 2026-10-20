---
name: n8n-trigger
description: >-
  Orchestrates and queries n8n automation pipelines (curriculum PDF ingestion,
  webhook alerts, teacher feedback loops, and scheduled state backups).
---

# /n8n-trigger: Headless Automation Pipeline Orchestrator

Integrates the AASHA AIOS orchestrator with external workflows hosted on n8n (`https://airtribe.app.n8n.cloud/`).

## Headless Zero-Consent Architecture
To avoid repetitive, blocking browser OAuth consent redirects (`https://airtribe.app.n8n.cloud/oauth/consent`), all automation triggers execute **headlessly** via direct outbound HTTPS requests with persistent Bearer/API token authorization.

- **Zero Browser Popups**: Pipeline tasks, curriculum ingestion, and automated backups run autonomously without user prompt disruption.
- **Outbound Boundary Invariant**: All connections are outbound client requests over HTTPS (`443`). No local listening ports or tunnels (`ngrok`) are opened.

## Capabilities

* **Curriculum Ingestion**: Webhook triggers when new state syllabus PDFs are uploaded.
* **Teacher Feedback Ingress**: Receives educator reviews and passes them into the Chāṇakya governance loop.
* **Zero-Cost Scheduled Backups**: Triggers regular SQLite and episodic memory exports to local disk.

## CLI Usage
```bash
# Check connectivity headlessly (verifies 200 OK without browser prompts):
node scripts/n8n_headless_client.mjs --check

# Trigger a specific webhook workflow:
node scripts/n8n_headless_client.mjs trigger /webhook/curriculum-ingest
node scripts/n8n_headless_client.mjs trigger /webhook/state-backup
```
