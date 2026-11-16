<#
.SYNOPSIS
  AASHA AIOS — Apply Cloud/Drive Bundle to Local Workstation
  Verifies and applies an incoming bundle into local aios/v2-bootstrap while preserving
  remote origin strictly as GitHub (https://github.com/Anant1asha/NGO-AI-LLM.git).
#>
param([string]$RepoRoot = "C:\Users\admin\Downloads\NGO AI LLM")
Set-Location $RepoRoot

$TargetBranch = "aios/v2-bootstrap"
$GitHubRemote = "https://github.com/Anant1asha/NGO-AI-LLM.git"

$bundlePath = "$PSScriptRoot\aasha_aios_v2_bootstrap_full.bundle"
if (-not (Test-Path $bundlePath)) {
    $bundlePath = "$RepoRoot\aasha_aios_v2_bootstrap_full.bundle"
}

if (-not (Test-Path $bundlePath)) {
    throw "Git bundle not found at '$bundlePath'"
}

Write-Host "==> [1/4] Verifying incoming git bundle integrity..."
git bundle verify "$bundlePath"
if ($LASTEXITCODE -ne 0) { throw "Invalid git bundle at '$bundlePath'" }

# --- Remote Invariant Enforcement ---
Write-Host "==> [2/4] Enforcing Git remote invariants..."
$currentOrigin = (git config --get remote.origin.url 2>$null)
if (-not $currentOrigin -or ($currentOrigin -like "*.bundle*") -or ($currentOrigin -notmatch "github\.com[/:].*NGO-AI-LLM")) {
    Write-Warning "Remediating misconfigured remote.origin ('$currentOrigin') -> setting to GitHub '$GitHubRemote'"
    git remote set-url origin $GitHubRemote 2>$null
    if ($LASTEXITCODE -ne 0) {
        git remote add origin $GitHubRemote 2>$null
    }
}

# Ensure read-only bundle remote is configured
$bundleRemote = (git config --get remote.bundle.url 2>$null)
if (-not $bundleRemote) {
    git remote add bundle "$bundlePath" 2>$null
} else {
    git remote set-url bundle "$bundlePath" 2>$null
}
git config remote.bundle.pushurl "DISABLED: Git bundles are read-only snapshot archives (use 'git bundle create')"

# --- Apply Bundle and Re-link Tracking ---
Write-Host "==> [3/4] Fetching refs from bundle into refs/remotes/bundle/$TargetBranch..."
git fetch "$bundlePath" "${TargetBranch}:refs/remotes/bundle/${TargetBranch}"
git checkout -B $TargetBranch "refs/remotes/bundle/${TargetBranch}" --force
git reset --hard "refs/remotes/bundle/${TargetBranch}"

Write-Host "==> [4/4] Restoring upstream tracking to origin/$TargetBranch..."
git branch --set-upstream-to="origin/$TargetBranch" $TargetBranch

Write-Host "✅ Fast-forwarded local $TargetBranch to bundle HEAD $(git rev-parse --short HEAD)"
Write-Host "   - remote.origin: $(git config --get remote.origin.url)"
Write-Host "   - tracking:      $(git rev-parse --abbrev-ref --symbolic-full-name @{u})"
Write-Host "   - remote.bundle: $(git config --get remote.bundle.url) [read-only]"
