# AASHA Learning Ecosystem — PowerShell Root Launcher
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
node scripts\aasha_root_orchestrator.js @args
