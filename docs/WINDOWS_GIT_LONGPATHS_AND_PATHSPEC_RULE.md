# Windows & Multi-Plane Git Staging Rule (Mandatory for All AI Agents & IDE Runners)

## Problem
On Windows, passing many file paths on the `git add <file1> <file2> ...` command line or having >260-char paths triggers:
```text
Git add failed: fork/exec C:\Program Files\Git\cmd\git.exe: The filename or extension is too long.
```
Additionally, Google Drive for Desktop creates `desktop.ini` files inside `.git/refs/` (e.g., `.git/refs/codex/desktop.ini`), causing:
```text
fatal: bad object refs/codex/desktop.ini
```

## Mandatory Hard Rules (All 9 Executive Officers, IDE, Colab, & Local PC)
1. **Enable Long Paths**: Always run `git config core.longpaths true` before staging or fetching on Windows.
2. **Never Pass Bulk File Lists as CLI Args to `git add`**:
   - **FORBIDDEN**: `git add file1 file2 ... file200` (exceeds Windows `CreateProcess` 32,767-char limit).
   - **REQUIRED**: Use `git add --pathspec-from-file=-` (stdin) or `bash scripts/safe_git_add_and_commit.sh "<commit_msg>"`.
3. **Clean Google Drive `desktop.ini` Artifacts in `.git`**:
   - Before `git fetch`, `git push`, or `git gc` on Windows, run:
     `find .git -iname "desktop.ini" -delete 2>/dev/null || true`
4. **Keep Working Tree Clean of Timestamp-Only Output Churn**:
   - Do not stage regenerated `output/*.html` or `AASHA_Visual_Mass_Harvest_Phase3/*.html` files unless a cycle explicitly modifies HTML templates or chapter content.
