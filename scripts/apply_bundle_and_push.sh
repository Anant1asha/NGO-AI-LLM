#!/usr/bin/env bash
# Auto-syncs aasha_aios_v2_bootstrap_full.bundle into aios/v2-bootstrap,
# reconciles aasha_operational_mirror.json into SQLite, and pushes strictly to origin/aios/v2-bootstrap.
set -euo pipefail

BUNDLE_PATH="${1:-/content/drive/MyDrive/NGO AI LLM/aasha_aios_v2_bootstrap_full.bundle}"
TARGET_BRANCH="aios/v2-bootstrap"

if [ ! -f "$BUNDLE_PATH" ]; then
  echo "Bundle not found at $BUNDLE_PATH" >&2
  exit 1
fi

git checkout -B "$TARGET_BRANCH"
git fetch "$BUNDLE_PATH" "$TARGET_BRANCH:$TARGET_BRANCH"
git checkout "$TARGET_BRANCH"
PYTHONPATH=.:src python3 scripts/reconcile_windows_mirror.py
git push origin "$TARGET_BRANCH"
echo "✅ Synced $TARGET_BRANCH @ $(git rev-parse --short HEAD) and reconciled operational SQLite mirror."
