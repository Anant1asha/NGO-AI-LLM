# scripts/start_9router_hidden.ps1
# AASHA AIOS — Headless Windows Auto-Start Bridge for 9Router Gateway
$ErrorActionPreference = "SilentlyContinue"
$WorkspaceRoot = "C:\Users\admin\Downloads\NGO AI LLM"
$EnsureScript = Join-Path $WorkspaceRoot "scripts\ensure_9router.js"
if (Test-Path $EnsureScript) {
    node "$EnsureScript" *> $null
}
