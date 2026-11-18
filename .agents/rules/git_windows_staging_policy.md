---
trigger: always_on
description: Mandatory pathspec-only Git staging to prevent Windows command line buffer overflow errors.
globs: "**/*"
---

# Universal Git Staging Policy for Windows, Colab & Agentic AI

1. **NEVER enumerate files into CLI arguments**:
   - Prohibited: `git add file1 file2 ... file200`
   - Prohibited: `git add $(git status -s)` or `git add $(git ls-files)`
   - Reason: Windows `cmd.exe` (8,191 chars) and `CreateProcessW` (32,767 chars) throw `ERROR_FILENAME_EXCED_RANGE` ("The filename or extension is too long").

2. **ALWAYS use Git Native Pathspecs or `--pathspec-from-file=-`**:
   - Stage directory: `git add scripts/ Aasha-AI/`
   - Stage tracked updates: `git add -u`
   - Stage via stdin: `bash scripts/safe_git_add_and_commit.sh "<commit_msg>"`
   - Enable long paths: `git config core.longpaths true`

3. **Clean Google Drive `desktop.ini` artifacts inside `.git`**:
   - Before `git fetch` or `git push` on Windows: `find .git -iname "desktop.ini" -delete 2>/dev/null || true`

4. **Keep `.venv/`, `.serena_venv/`, `.pytest_cache/`, and local DBs ignored in `.gitignore`**.

5. **Mandatory Pre-Commit Secret Scan**:
   - Run `node scripts/lint_staged_secrets.mjs` before committing.
