---
description: Universal Git staging, bundle push safeguards, branch protections, and cross-platform runtime execution invariants.
globs: "**/*"
---

# Git, Staging & Cross-Platform Runtime Guardrails

## 1. Git Staging & Windows Command Buffer Limit

- **NEVER** stage files by expanding lists of file paths into CLI arguments (e.g., `git add file1 file2 ... fileN`). Win32 `CreateProcessW` has a strict 32,767-character limit; long file lists trigger OS error 206 (`ERROR_FILENAME_EXCED_RANGE`).
- **ALWAYS** stage using Git pathspecs (e.g., `git add -A` or `git add .`) or pipe path lists via `git add --pathspec-from-file=-`.
- Ensure `core.longpaths` is enabled (`git config core.longpaths true`).

## 2. Remote Targets & Bundle File Invariants

- **NEVER** push to a `.bundle` file URL or a bundle remote. Git bundles are read-only snapshot archives and do not support `git-receive-pack`.
- **`origin`** must ALWAYS point to the authoritative GitHub repository (`https://github.com/Anant1asha/NGO-AI-LLM.git`).
- Dedicated offline bundles must be updated exclusively using `git bundle create <file.bundle> <ref>` and fetched read-only via `git bundle verify`.
- The pre-push hook at `.git/hooks/pre-push` actively enforces this invariant.

## 3. Branch Protection Invariants

- **NEVER** push directly to `main`, `master`, `release`, or `production`.
- Active development and autonomous loop iterations must strictly target `aios/v2-bootstrap` or designated feature branches.

## 4. Cross-Platform Process Execution & Environment Variables

- **NEVER** use POSIX-style prefix syntax (e.g., `PYTHONPATH=foo python3 bar.py`) in shell commands or `execSync` calls on Windows. `cmd.exe` does not parse inline variable prefixes.
- **ALWAYS** inject environment variables via the execution environment options (e.g., Node's `execSync(cmd, { env: { ...process.env, PYTHONPATH: ... } })`).
- When resolving `python3` on Windows, ensure the active interpreter precedes the Windows Store `WindowsApps` execution alias.

## 5. Pre-Commit Security & Secret Sanitization

- All staged changes must be validated with `node scripts/lint_staged_secrets.mjs` before committing. Zero unencrypted tokens, private keys, or passwords may be committed.
