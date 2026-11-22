---
trigger: always_on
description: Mandatory pathspec-only Git staging to prevent Windows command line buffer overflow errors and ignored-file aborts.
globs: "**/*"
---

# Universal Git Staging Policy for Windows, Colab & Agentic AI

## 1. Absolute Prohibition on Command-Line File Enumeration
- **NEVER enumerate files into CLI arguments**:
  - Prohibited: `git add file1 file2 ... file200`
  - Prohibited: `git add $(git status -s)` or `git add $(git ls-files)`
  - Reason: Windows `cmd.exe` (8,191 chars) and `CreateProcessW` (32,767 chars) throw `ERROR_FILENAME_EXCED_RANGE` ("The filename or extension is too long").

## 2. Mandatory Use of Git Native Pathspecs & Stdin
- **ALWAYS use Native Pathspecs or Stdin Streams**:
  - Stage tracked updates: `git add -u` (Safest: only stages modifications to already tracked files; never trips ignored file warnings).
  - Stage specific directories: `git add scripts/ Aasha-AI/ tests/`
  - Stage single files: `git add path/to/specific_file.mjs`
  - Stage via stdin stream: `bash scripts/safe_git_add_and_commit.sh "<commit_msg>"` (uses `git add --pathspec-from-file=-`).
  - Enable long paths: `git config core.longpaths true` (System, Global, and Local).

## 3. Ignored-File Handling & Staging Protection
- **Disable Ignored-File Warning Aborts**:
  - Run: `git config advice.addIgnoredFile false`
  - Never run `git add .` or `git add -A` when untracked output or cache directories (such as `Aasha-AI/aasha-pipeline-with-master-json/output/`) exist in the tree.
  - Rely on `git add -u` for tracked changes, followed by explicit single-file adds for newly created tests/modules.

## 4. Google Drive & File Watcher Lock Hygiene
- **Purge Google Drive `desktop.ini` artifacts inside `.git`**:
  - Before any `git fetch`, `git bundle`, `git merge`, or `git push` on Windows:
    `find .git -iname "desktop.ini" -delete 2>/dev/null || true`
    or in PowerShell:
    `Get-ChildItem -Path ".git" -Filter "desktop.ini" -Recurse -Force | Remove-Item -Force`
  - Prevents Git ref parser failures (`fatal: bad object refs/heads/aios/desktop.ini`).
- **Windows `.git/index.lock` Contention**:
  - If a background task, IDE file watcher, or antivirus process leaves a stale `.git/index.lock`, verify that no `git.exe` process is actively writing before removing the lock:
    `if (!(Get-Process git -ErrorAction SilentlyContinue)) { Remove-Item -Force .git/index.lock -ErrorAction SilentlyContinue }`

## 5. Repository Cleanliness & `.gitignore` Invariants
- Keep the following strictly ignored in `.gitignore`:
  `.venv/`, `.serena_venv/`, `.pytest_cache/`, `*.bundle`, `aasha_local.db`, `Aasha-AI/aasha-pipeline-with-master-json/output/`, `node_modules/`.

## 6. Multi-Root ESM Test Execution Protocol
- When executing root test suites that require subpackage dependencies (`better-sqlite3`, `fastify`), always run with the offline ESM loader:
  `node --loader ./tests/esm_offline_server_loader.mjs tests/<test_file>.mjs`

## 7. Mandatory Pre-Commit Secret Scan
- Always execute `node scripts/lint_staged_secrets.mjs` before committing.

## 8. IDE UI Source Control & GUI Commit Invariant (.vscode/settings.json)
- **GUI Commit Failure Prevention**:
  To prevent Antigravity IDE / VS Code from crashing with `The filename or extension is too long` when clicking the UI **Commit** button:
  - Configure `.vscode/settings.json`:
    ```json
    {
      "git.smartCommitChanges": "tracked",
      "git.untrackedChanges": "separate",
      "git.enableSmartCommit": true
    }
    ```
  - `"git.smartCommitChanges": "tracked"` forces the IDE to invoke `git commit -a`, which stages tracked changes internally within Git's native C engine with **zero file path CLI arguments**.
  - `"git.untrackedChanges": "separate"` isolates untracked files from accidental bulk staging.

## 9. Universal Safe Commit & Push Commands (Windows & Colab)
- **Cross-Platform Staging & Push Engine (`scripts/safe_commit_and_push.mjs`)**:
  Instead of manual multi-step git operations, use the automated wrapper commands:
  ```bash
  npm run safe:commit   # Stages via pathspec (git add -u), scans secrets, commits
  npm run safe:push     # Stages, scans secrets, commits, and pushes to origin
  ```
  - Compatible with Windows PowerShell, Git Bash, Linux, and Colab environments.
  - Automatically sanitizes `.git` lock artifacts, verifies `core.longpaths true`, and avoids argument expansion.
