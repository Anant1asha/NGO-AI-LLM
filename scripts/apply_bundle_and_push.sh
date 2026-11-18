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

git fetch "$BUNDLE_PATH" "refs/heads/$TARGET_BRANCH"
git checkout -B "$TARGET_BRANCH" FETCH_HEAD
PYTHONPATH=.:src python3 scripts/reconcile_windows_mirror.py
git push origin "$TARGET_BRANCH"
echo "✅ Synced $TARGET_BRANCH @ $(git rev-parse --short HEAD) and reconciled operational SQLite mirror."
