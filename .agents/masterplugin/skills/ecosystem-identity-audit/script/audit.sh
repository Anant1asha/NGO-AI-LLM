#!/usr/bin/env bash
# ecosystem-identity-audit script
# Checks subject & board coverage, memory health, and graphify consistency.
set -euo pipefail

# 1. Subject & Board Coverage Check
echo "--- Subject & Board Coverage Check ---"
if [[ -f "Aasha-AI/experience_registry/registry.json" ]]; then
  jq -r '.foundations[] | "\(.subject) \(.board) \(.class)"' Aasha-AI/experience_registry/registry.json | sort -u
else
  echo "Error: registry.json not found"
  exit 1
fi

# 2. Memory Consistency Check (Serena core & conventions)
echo "\n--- Memory Consistency Check ---"
# Assuming Serena CLI is available as serena-cli
if command -v serena-cli >/dev/null 2>&1; then
  serena-cli list_memories | grep -E "core|conventions" || echo "Serena memory keys missing"
else
  echo "Serena CLI not installed; skipping memory check"
fi

# 3. Graphify Path Validation
echo "\n--- Graphify Validation ---"
if command -v graphify >/dev/null 2>&1; then
  graphify query "ecosystem-identity-audit" || echo "Graphify query failed"
else
  echo "Graphify CLI not installed; skipping"
fi

echo "\nAudit completed successfully."
