@echo off
setlocal EnableDelayedExpansion
title AASHA AIOS — 1-Command Windows PC Sync & Verification (Focus Units B-001 & B-002)

echo ============================================================================
echo   AASHA AIOS + AASHA Studio — 1-Command Local Windows PC Sync
echo   Target Root: C:\Users\admin\Downloads\NGO AI LLM
echo ============================================================================

set "ROOT_DIR=C:\Users\admin\Downloads\NGO AI LLM"
if not exist "%ROOT_DIR%" (
    set "ROOT_DIR=%~dp0"
)
cd /d "%ROOT_DIR%"
echo [1/5] Active Workspace Root: %CD%

set "ZIP_FILE=%CD%\aasha_phase1_and_pc_bridge_bundle.zip"
if not exist "%ZIP_FILE%" (
    if exist "%USERPROFILE%\Downloads\aasha_phase1_and_pc_bridge_bundle.zip" (
        set "ZIP_FILE=%USERPROFILE%\Downloads\aasha_phase1_and_pc_bridge_bundle.zip"
    )
)

if exist "%ZIP_FILE%" (
    echo [2/5] Extracting %ZIP_FILE% into staging folder...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$staging = Join-Path '%CD%' '.aasha_sync_staging'; " ^
      "if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }; " ^
      "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath $staging -Force; " ^
      "$pipeDest = Join-Path '%CD%' 'Aasha-AI\aasha-pipeline-with-master-json\aasha-pipeline'; " ^
      "if (-not (Test-Path $pipeDest)) { $pipeDest = Join-Path '%CD%' 'Aasha-AI\aasha-pipeline-with-master-json' }; " ^
      "if (Test-Path (Join-Path $staging 'aasha-pipeline')) { " ^
      "  Copy-Item -Path (Join-Path $staging 'aasha-pipeline\*') -Destination $pipeDest -Recurse -Force; " ^
      "  Write-Host '  -> Synced updated aasha-pipeline modules into ' $pipeDest -ForegroundColor Green; " ^
      "}; " ^
      "$catDest = Join-Path '%CD%' 'AASHA_Visual_Mass_Harvest_Phase3\catalogue\visual-resource-catalogue-phase3.json'; " ^
      "if (Test-Path (Join-Path $staging 'AASHA_Visual_Mass_Harvest_Phase3\catalogue\visual-resource-catalogue-phase3.json')) { " ^
      "  if (Test-Path (Split-Path $catDest)) { Copy-Item -Path (Join-Path $staging 'AASHA_Visual_Mass_Harvest_Phase3\catalogue\visual-resource-catalogue-phase3.json') -Destination $catDest -Force; } " ^
      "}; " ^
      "Copy-Item -Path (Join-Path $staging 'aasha_pc_antigravity_daemon.ps1') -Destination '%CD%\aasha_pc_antigravity_daemon.ps1' -Force; " ^
      "Copy-Item -Path (Join-Path $staging 'aasha_antigravity_daily_ecosystem_runner.py') -Destination '%CD%\aasha_antigravity_daily_ecosystem_runner.py' -Force; " ^
      "Remove-Item $staging -Recurse -Force;"
) else (
    echo [2/5] Note: aasha_phase1_and_pc_bridge_bundle.zip not found in root; checking synced files...
)

echo [3/5] Fixing false-green console.assert in Aasha-AIOS contract test (if present)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$contractTest = Join-Path '%CD%' 'Aasha-AI\Aasha-AIOS\tests\contract\test_visual_contract.js'; " ^
  "if (Test-Path $contractTest) { " ^
  "  $c = Get-Content $contractTest -Raw; " ^
  "  if ($c -match 'console\.assert') { " ^
  "    $c = \"const assert = require('node:assert/strict');`n\" + ($c -replace 'console\.assert\(', 'assert.ok('); " ^
  "    Set-Content -Path $contractTest -Value $c -Encoding UTF8; " ^
  "    Write-Host '  -> Upgraded test_visual_contract.js to node:assert/strict' -ForegroundColor Green; " ^
  "  } " ^
  "}"

echo [4/5] Running QA & Pipeline Verification Checks...
if exist "%CD%\Aasha-AI\aasha-pipeline-with-master-json\aasha-pipeline\qa\run_qa.js" (
    node "%CD%\Aasha-AI\aasha-pipeline-with-master-json\aasha-pipeline\qa\run_qa.js" "%CD%\Aasha-AI\aasha-pipeline-with-master-json\aasha-pipeline\examples\Fractions_Gamified_v5_3.html"
)

echo [5/5] Writing PC_ANTIGRAVITY_STATE.json heartbeat for Google Drive sync...
if exist "%CD%\aasha_pc_antigravity_daemon.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\aasha_pc_antigravity_daemon.ps1" -Once
)

echo ============================================================================
echo   SYNC COMPLETE! Google Drive for Desktop will now sync PC_ANTIGRAVITY_STATE.json.
echo ============================================================================
