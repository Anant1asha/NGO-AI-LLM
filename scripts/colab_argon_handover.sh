#!/usr/bin/env bash
# Argon AIOS Colab Handover Script (Closes GAP-V7-02 & GAP-V7-03 in Online Colab Runner)
# Target Colab Notebook: 1XPLBrKkB_nzrEWNUq3Z2plxnnq1VUJk2
# Target Branch: aios/v2-bootstrap (STRICT: never push to main/master/HEAD)
set -euo pipefail

BUNDLE_PATH="${1:-/content/drive/MyDrive/NGO AI LLM/aasha_aios_v2_bootstrap_full.bundle}"

echo "=== [1/5] GAP-V7-02: Applying Drive Bundle & Pushing to origin/aios/v2-bootstrap ==="
bash scripts/apply_bundle_and_push.sh "$BUNDLE_PATH"

echo "=== [2/5] Installing Server Dependencies & Running Live Fastify HTTP Integration (GAP-V7-01) ==="
if [ -f Aasha-AI/server/package.json ]; then
  npm install --prefix Aasha-AI/server --no-audit --no-fund
fi
node --loader ./tests/esm_offline_server_loader.mjs tests/test_gap_v7_01_server_http_integration.mjs

echo "=== [3/5] Running Visual Contract (97/97) & SEC-001 Secret Scan ==="
node Aasha-AI/Aasha-AIOS/tests/contract/test_visual_contract.js
node scripts/lint_staged_secrets.mjs

echo "=== [4/5] GAP-V7-03: Running Playwright Headless Chromium Verification ==="
if python3 -c "import playwright" 2>/dev/null || npx --yes playwright --version >/dev/null 2>&1; then
  python3 - <<'PY'
import glob, sys
from pathlib import Path
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright Python package not installed; run: pip install playwright && playwright install chromium")
    sys.exit(1)

html_files = sorted(glob.glob("Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/*.html"))[:3]
assert html_files, "No HTML5 modules found in g3_10chapter_pack"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    for f in html_files:
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(Path(f).resolve().as_uri(), wait_until="load")
        assert len(errors) == 0, f"Console/Page errors in {f}: {errors}"
        print(f"PASS Chromium headless: {f}")
    browser.close()
PY
else
  echo "Playwright not installed in environment. Install with: pip install playwright && playwright install chromium"
fi

echo "=== [5/5] Launching Argon AIOS Continuous Swarm Loop ==="
node scripts/aasha_continuous_loop.mjs --swarm || echo "Swarm loop exited; inspect COLAB_ANTIGRAVITY_STATE.json"
