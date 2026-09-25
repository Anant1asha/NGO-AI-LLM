---
name: n8n-trigger
description: >-
  Orchestrates and queries n8n automation pipelines (curriculum PDF ingestion,
  webhook alerts, teacher feedback loops, and scheduled state backups).
---

# /n8n-trigger: Automation Pipeline Orchestrator

Integrates the AASHA AIOS orchestrator with external workflows hosted on n8n (`https://airtribe.app.n8n.cloud/`).

## Capabilities

* **Curriculum Ingestion**: Webhook triggers when new state syllabus PDFs are uploaded.
* **Teacher Feedback Ingress**: Receives educator reviews and passes them into the Chāṇakya governance loop.
* **Zero-Cost Scheduled Backups**: Triggers regular SQLite and episodic memory exports to local disk.
