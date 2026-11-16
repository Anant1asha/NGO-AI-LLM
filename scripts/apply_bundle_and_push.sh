#!/usr/bin/env bash
# scripts/apply_bundle_and_push.sh
# AASHA AIOS — Apply Cloud/Drive Bundle and Push strictly to GitHub Origin
# Reconciles aasha_operational_mirror.json into SQLite, and pushes strictly to origin/aios/v2-bootstrap.
set -euo pipefail

BUNDLE_PATH="${1:-/content/drive/MyDrive/NGO AI LLM/aasha_aios_v2_bootstrap_full.bundle}"
TARGET_BRANCH="aios/v2-bootstrap"
GITHUB_REMOTE="https://github.com/Anant1asha/NGO-AI-LLM.git"

if [ ! -f "$BUNDLE_PATH" ]; then
  echo "Bundle not found at $BUNDLE_PATH" >&2
  exit 1
fi

# 1. Enforce Remote Invariant: origin MUST point strictly to GitHub, never a .bundle file
CURRENT_ORIGIN="$(git config --get remote.origin.url || true)"
if [[ -z "$CURRENT_ORIGIN" ]] || [[ "$CURRENT_ORIGIN" == *".bundle"* ]] || [[ "$CURRENT_ORIGIN" != *"github.com"* ]]; then
  echo "Remediating misconfigured remote.origin ('$CURRENT_ORIGIN') -> '$GITHUB_REMOTE'"
  git remote set-url origin "$GITHUB_REMOTE" 2>/dev/null || git remote add origin "$GITHUB_REMOTE"
fi

# Ensure read-only bundle remote
git config remote.bundle.url "$BUNDLE_PATH" 2>/dev/null || true
git config remote.bundle.pushurl "DISABLED: Git bundles are read-only snapshot archives"

# 2. Checkout target branch and fetch bundle into refs/remotes/bundle/$TARGET_BRANCH
git checkout -B "$TARGET_BRANCH"
git fetch "$BUNDLE_PATH" "$TARGET_BRANCH:refs/remotes/bundle/$TARGET_BRANCH"
git merge --ff-only "refs/remotes/bundle/$TARGET_BRANCH" || {
  echo "Non-fast-forward bundle update detected. Resetting to bundle ref..."
  git reset --hard "refs/remotes/bundle/$TARGET_BRANCH"
}

# 3. Ensure branch tracks GitHub origin
git branch --set-upstream-to="origin/$TARGET_BRANCH" "$TARGET_BRANCH"

# 4. Reconcile operational SQLite mirror
PYTHONPATH=.:src python3 scripts/reconcile_windows_mirror.py

# 5. Pre-push sanity check: verify origin is strictly NOT a bundle
PUSH_TARGET="$(git config --get remote.origin.url)"
if [[ "$PUSH_TARGET" == *".bundle"* ]]; then
  echo "❌ CRITICAL ERROR: remote.origin.url is pointing to a bundle file ($PUSH_TARGET)!" >&2
  echo "Git cannot push to bundle files. Aborting push." >&2
  exit 1
fi

# 6. Push strictly to GitHub origin
git push origin "$TARGET_BRANCH"
echo "✅ Synced $TARGET_BRANCH @ $(git rev-parse --short HEAD) and pushed strictly to GitHub origin."
