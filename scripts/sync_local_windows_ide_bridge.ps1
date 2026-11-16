<#
.SYNOPSIS
  Plane 3 (Local Windows Workstation & IDE) <-> Plane 1 (Google Drive) <-> GitHub Bridge Script.
  Unifies C:\Users\admin\Downloads\NGO AI LLM with aasha_aios_v2_bootstrap_full.bundle and origin/aios/v2-bootstrap.
#>
param(
  [ValidateSet("PullFromDrive", "PushToDriveAndGitHub", "FullBidirectionalSync")]
  [string]$Direction = "FullBidirectionalSync",
  [string]$WorkspaceRoot = "C:\Users\admin\Downloads\NGO AI LLM",
  [string]$DriveFolder = ""
)

$ErrorActionPreference = "Stop"
$TargetBranch = "aios/v2-bootstrap"
$GitHubRemote = "https://github.com/Anant1asha/NGO-AI-LLM.git"
$BundlePath = Join-Path $WorkspaceRoot "aasha_aios_v2_bootstrap_full.bundle"

if (-not $DriveFolder) {
  $Candidates = @(
    "G:\My Drive\NGO AI LLM",
    "G:\Other computers\My Laptop\NGO AI LLM",
    "$env:USERPROFILE\Google Drive\NGO AI LLM",
    "$env:USERPROFILE\My Drive\NGO AI LLM"
  )
  foreach ($c in $Candidates) {
    if (Test-Path $c) { $DriveFolder = $c; break }
  }
}

Set-Location $WorkspaceRoot

# --- Remote Invariant Enforcement ---
$currentOrigin = (git config --get remote.origin.url 2>$null)
if (-not $currentOrigin -or ($currentOrigin -like "*.bundle*") -or ($currentOrigin -notmatch "github\.com[/:].*NGO-AI-LLM")) {
  Write-Warning "Remediating misconfigured remote.origin (was: '$currentOrigin') -> setting to GitHub '$GitHubRemote'"
  git remote set-url origin $GitHubRemote 2>$null
  if ($LASTEXITCODE -ne 0) {
    git remote add origin $GitHubRemote 2>$null
  }
}

# Ensure read-only bundle remote is configured
$bundleRemote = (git config --get remote.bundle.url 2>$null)
if (-not $bundleRemote) {
  git remote add bundle "$BundlePath" 2>$null
}
git config remote.bundle.pushurl "DISABLED: Git bundles are read-only snapshot archives"

# Ensure target branch and upstream tracking
git checkout -B $TargetBranch
git branch --set-upstream-to="origin/$TargetBranch" $TargetBranch 2>$null

if ($Direction -in @("PullFromDrive", "FullBidirectionalSync")) {
  if ($DriveFolder -and (Test-Path "$DriveFolder\aasha_aios_v2_bootstrap_full.bundle")) {
    Write-Host "==> [1/4] Fetching Drive bundle from $DriveFolder\aasha_aios_v2_bootstrap_full.bundle ..."
    git fetch "$DriveFolder\aasha_aios_v2_bootstrap_full.bundle" "${TargetBranch}:refs/remotes/drive/${TargetBranch}"
    git merge --ff-only "refs/remotes/drive/${TargetBranch}"
  } else {
    Write-Warning "Drive bundle not found at $DriveFolder; skipping bundle fetch."
  }

  Write-Host "==> [2/4] Reconciling aasha_operational_mirror.json into local SQLite (aasha_operational.db) ..."
  $env:PYTHONPATH = ".;src"
  python scripts/reconcile_windows_mirror.py
}

if ($Direction -in @("PushToDriveAndGitHub", "FullBidirectionalSync")) {
  Write-Host "==> [3/4] Running SEC-001 secret scanner & pushing strictly to origin/$TargetBranch ..."
  node scripts/lint_staged_secrets.mjs

  # Assert origin remote is strictly GitHub before pushing
  $verifyOrigin = (git config --get remote.origin.url).Trim()
  if ($verifyOrigin -like "*.bundle*" -or $verifyOrigin -match "\.bundle($|[/\\])") {
    throw "CRITICAL INVARIANT VIOLATION: remote.origin.url points to a bundle file ('$verifyOrigin'). Git cannot push to bundle files! Refusing push."
  }

  git push origin $TargetBranch

  Write-Host "==> [4/4] Rebuilding aasha_aios_v2_bootstrap_full.bundle & syncing state files to Google Drive ..."
  git bundle create aasha_aios_v2_bootstrap_full.bundle $TargetBranch
  if ($DriveFolder -and (Test-Path $DriveFolder)) {
    Copy-Item -Force aasha_aios_v2_bootstrap_full.bundle, PC_ANTIGRAVITY_STATE.json, COLAB_ANTIGRAVITY_STATE.json, IDE_CLOUD_ASYNC_BUS.json "$DriveFolder\"
    Write-Host "✅ Synced bundle and 3-plane state files to $DriveFolder"
  }
}
