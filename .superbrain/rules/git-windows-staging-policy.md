---
description: Mandatory pathspec-only Git staging to prevent Windows command line buffer overflow errors and ignored-file aborts.
globs: "**/*"
alwaysApply: true
---

# Superbrain Rule: Windows & Colab Safe Git Staging Policy

- **Pathspec-Only Staging**: Never pass file lists as CLI arguments to `git add`; use `git add -u`, directory pathspecs (`git add scripts/ tests/ Aasha-AI/`), or `git add --pathspec-from-file=-`.
- **Ignored Paths**: Never use broad `git add .` over directories containing ignored build outputs (`Aasha-AI/aasha-pipeline-with-master-json/output`). Set `git config advice.addIgnoredFile false`.
- **Windows Longpaths & Ref Hygiene**: Always enforce `git config core.longpaths true` and clean `.git/**/desktop.ini` before bundle sync or push.
- **Index Lock Contention**: Safely clear stale `.git/index.lock` on Windows only after verifying no active `git.exe` processes are running.
- **Transients Ignored**: Keep `.venv/`, `.serena_venv/`, `.pytest_cache/`, `Aasha-AI/server/aasha_local.db`, and `*.bundle` strictly in `.gitignore`.
- **ESM Loader Protocol**: Run root server integration tests via `node --loader ./tests/esm_offline_server_loader.mjs`.
- **Secret Scan**: Always run `node scripts/lint_staged_secrets.mjs` prior to commit.
