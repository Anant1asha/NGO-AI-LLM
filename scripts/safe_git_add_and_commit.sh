#!/usr/bin/env bash
# Cross-platform safe Git staging & commit helper (Windows Git Bash, Colab, Linux).
# Prevents Windows CreateProcess 32,767-char limit ("The filename or extension is too long")
# and Windows MAX_PATH (260-char) errors by using --pathspec-from-file=- and core.longpaths=true.
set -euo pipefail

COMMIT_MSG="${1:-chore(aios): atomic safe commit}"
shift || true

git config core.longpaths true
find .git -iname "desktop.ini" -delete 2>/dev/null || true

if [ "$#" -gt 0 ]; then
  printf '%s\n' "$@" | git add --pathspec-from-file=-
elif [ ! -t 0 ]; then
  git add --pathspec-from-file=-
else
  # Stage modified/untracked files in bounded batches via NUL-delimited pathspec
  git status --porcelain -z | tr '\0' '\n' | sed -E 's/^.. //' | git add --pathspec-from-file=-
fi

if [ -f "scripts/lint_staged_secrets.mjs" ] && command -v node >/dev/null 2>&1; then
  node scripts/lint_staged_secrets.mjs
fi

git commit -m "$COMMIT_MSG"
echo "✅ Safe commit created: $(git rev-parse --short HEAD)"
