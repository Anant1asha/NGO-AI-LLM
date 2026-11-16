param([string]$RepoRoot = "C:\Users\admin\Downloads\NGO AI LLM")
Set-Location $RepoRoot

$bundlePath = "$PSScriptRoot\aasha_aios_v2_bootstrap_full.bundle"
if (-not (Test-Path $bundlePath)) {
    $bundlePath = "$RepoRoot\aasha_aios_v2_bootstrap_full.bundle"
}

git bundle verify "$bundlePath"
if ($LASTEXITCODE -ne 0) { throw "Invalid git bundle" }

git fetch "$bundlePath" "aios/v2-bootstrap:refs/remotes/cloud/aios/v2-bootstrap"
$cloudSha = git rev-parse refs/remotes/cloud/aios/v2-bootstrap
git checkout -B aios/v2-bootstrap refs/remotes/cloud/aios/v2-bootstrap --force
git reset --hard refs/remotes/cloud/aios/v2-bootstrap
Write-Host "✅ Fast-forwarded local aios/v2-bootstrap to cloud HEAD $(git rev-parse --short HEAD)"
