#!/usr/bin/env bash
# Auto-syncs aasha_aios_v2_bootstrap_full.bundle into aios/v2-bootstrap,
# reconciles aasha_operational_mirror.json into SQLite, and pushes strictly to origin/aios/v2-bootstrap.
set -euo pipefail

TARGET_BRANCH="aios/v2-bootstrap"
COLAB_BUNDLE="/content/drive/MyDrive/NGO AI LLM/aasha_aios_v2_bootstrap_full.bundle"
LOCAL_BUNDLE="./aasha_aios_v2_bootstrap_full.bundle"

if [ -n "${1:-}" ]; then
  BUNDLE_PATH="$1"
elif [ -f "$COLAB_BUNDLE" ]; then
  BUNDLE_PATH="$COLAB_BUNDLE"
elif [ -f "$LOCAL_BUNDLE" ]; then
  BUNDLE_PATH="$LOCAL_BUNDLE"
else
  echo "Bundle not found at $COLAB_BUNDLE or $LOCAL_BUNDLE" >&2
  exit 1
fi

# Remove Windows / Google Drive Desktop desktop.ini files inside .git that break git ref resolution
git config core.longpaths true
find .git -iname "desktop.ini" -delete 2>/dev/null || true

# Fetch bundle head
git fetch "$BUNDLE_PATH" "refs/heads/$TARGET_BRANCH"

# Compare FETCH_HEAD against HEAD to prevent accidental non-fast-forward regressions
CURRENT_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")

if [ -n "$CURRENT_HEAD" ] && git merge-base --is-ancestor FETCH_HEAD HEAD 2>/dev/null; then
  echo "Bundle ref $(git rev-parse --short FETCH_HEAD) is already integrated into local HEAD ($(git rev-parse --short HEAD))."
elif [ -n "$CURRENT_HEAD" ] && git merge-base --is-ancestor HEAD FETCH_HEAD 2>/dev/null; then
  echo "Fast-forwarding $TARGET_BRANCH to incoming bundle $(git rev-parse --short FETCH_HEAD)..."
  git checkout -B "$TARGET_BRANCH" FETCH_HEAD
else
  echo "Merging bundle $(git rev-parse --short FETCH_HEAD) into $TARGET_BRANCH..."
  git merge --no-edit FETCH_HEAD -m "sync(bundle): merge incoming bundle into $TARGET_BRANCH" || true
fi

# Reconcile operational SQLite mirror
PYTHON_BIN="python3"
if ! command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
PYTHONPATH=.:src "$PYTHON_BIN" scripts/reconcile_windows_mirror.py

# Push strictly to origin target branch
git push origin "$TARGET_BRANCH"
echo "✅ Synced $TARGET_BRANCH @ $(git rev-parse --short HEAD) and reconciled operational SQLite mirror."
