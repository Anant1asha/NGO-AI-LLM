# AASHA Engineering Execution Capability Audit (`MASTER_PROMPT_v7`)
Generated: `2026-11-13T13:48:55.327575+00:00` | Branch: `aios/v2-bootstrap` | HEAD: `3e603129c85536485ef8b736b6813db2816ba0f6`

- **Verified Capabilities**: File read/write, Python 3.11 unittest execution, Node v18 ESM/CJS execution, SQLite3 DDL/DML & gzip export, Git commit/bundle creation, `SEC-001` secret scanning, Google Drive API sync.
- **Blocked/Unavailable in Cloud Sandbox**: Outbound internet (`git push`, `npm install`, `pip install`), Windows local path (`C:\Users\admin\Downloads\NGO AI LLM`), headless Chromium rendering.
