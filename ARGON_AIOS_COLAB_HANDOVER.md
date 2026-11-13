# Argon AIOS & Colab Handover Guide (GAP-V7-01..04 & Phase G40)

## 1. Verified Local Status on `aios/v2-bootstrap`
- **GAP-V7-01 (`CLOSED_LOCAL_VERIFIED`)**: Added missing `Aasha-AI/server/package.json` (`"type": "module"`) and verified `9/9` live HTTP endpoints on an ephemeral port (`tests/test_gap_v7_01_server_http_integration.mjs`), including `/api/health`, `/api/store/items`, `/api/sync/quiz-results`, `/api/teacher/misconception-analytics`, `/api/student/:id/redeem` (PIN `1080` + coin conservation), `/api/sync/cohort-order-pack`, and `/api/sync/student-snapshot`.
- **GAP-V7-04 (`CLOSED_LOCAL_VERIFIED`)**: Verified deterministic offline pipeline execution (`tests/test_gap_v7_04_pipeline_offline_cli.py`) using `defaults_expanded_v2.json`, `Orchestrator`, `FrontendCodeSynthesizer.run`, and `node Aasha-AI/aasha-pipeline-with-master-json/qa/run_qa.js`.
- **Phase G40 (`CLOSED_LOCAL_VERIFIED`)**: Added Continuous Field Telemetry Sentinel (`src/aasha/orchestrator/phase_g40_field_telemetry_and_authoring.py`) and bilingual NCVET/PSSCIVE + STEM Teacher Authoring Template Pack (`Aasha-AI/experience_registry/teacher_authoring_template_v1.json`).
- **Contract & Secret Gates**: `97/97` Visual Contract assertions passing; `SEC-001` (`lint_staged_secrets.mjs`) clean.

## 2. Online Colab / Argon AIOS Execution (Closes `GAP-V7-02` & `GAP-V7-03`)
Run these commands inside your [Online Antigravity Colab Runner](https://colab.research.google.com/drive/1XPLBrKkB_nzrEWNUq3Z2plxnnq1VUJk2?ouid=117981788088187594825) after mounting Google Drive:

```bash
# 1. Mount Drive & enter repo
cd /content/aasha_aios_unified_repo || git clone https://github.com/Anant1asha/NGO-AI-LLM.git /content/aasha_aios_unified_repo && cd /content/aasha_aios_unified_repo

# 2. Run the unified Argon AIOS handover script (pushes aios/v2-bootstrap, runs server + Playwright Chromium + Argon swarm)
chmod +x scripts/colab_argon_handover.sh
bash scripts/colab_argon_handover.sh "/content/drive/MyDrive/NGO AI LLM/aasha_aios_v2_bootstrap_full.bundle"
```

## 3. Guardrails for Argon AIOS
- **Branch Isolation**: Push strictly to `aios/v2-bootstrap`. Never push to `main`, `master`, or `HEAD`.
- **Zero-Secret Policy (`SEC-001`)**: Never commit `.env` files, API keys, or tokens.
- **Offline Child Safety**: Maintain `< 20,971,520` bytes (`20 MiB`) per HTML5 module and `0` external runtime URLs.
