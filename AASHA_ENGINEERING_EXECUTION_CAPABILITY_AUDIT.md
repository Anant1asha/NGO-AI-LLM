# AASHA Engineering Execution Capability Audit (`MASTER_PROMPT_v7`)
Generated: `2026-11-16T12:12:14.029839+00:00` | Branch: `aios/v2-bootstrap` | HEAD: `1ca5fd9a2fa6cff1501051c751217832ce019b7d`

- **Verified Capabilities**: File read/write, Python 3.11 unittest execution, Node v18 ESM/CJS execution, SQLite3 DDL/DML & gzip export, Git commit/bundle creation, `SEC-001` secret scanning, Google Drive API sync.
- **Blocked/Unavailable in Cloud Sandbox**: Outbound internet (`git push`, `npm install`, `pip install`), Windows local path (`C:\Users\admin\Downloads\NGO AI LLM`), headless Chromium rendering.
