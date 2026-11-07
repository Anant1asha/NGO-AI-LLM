<#
.SYNOPSIS
    AASHA AIOS V3 — Plane 3 (Mode D Local PC) Zero-Approval Async IDE Daemon
.DESCRIPTION
    Synchronizes C:\Users\admin\Downloads\NGO AI LLM (Local IDE / Antigravity / VS Code)
    with Plane 1 (Google Drive 1Xgtf699BHe2yKdw6ne1ilihXsgP6WMxD) and Plane 2
    (Colab 24/7 Cloud Worker 1XPLBrKkB_nzrEWNUq3Z2plxnnq1VUJk2) WITHOUT human approval pauses
    and WITHOUT ever overwriting or contradicting the V3 CRDT chunk cursor.

    Key Guarantees:
    1. ZERO HUMAN APPROVAL: Executes autonomously via AUTONOMOUS_ZERO_HIL_CRYPTO_PROOF.
    2. JOIN-SEMILATTICE CRDT MERGE: Never wipes completed_chunks, active_chunk_id, vector_clock,
       or cursor_lock_sha256 in PC_ANTIGRAVITY_STATE.json. Always merges with COLAB_ANTIGRAVITY_STATE.json
       and IDE_CLOUD_ASYNC_BUS.json.
    3. LOCAL IDE FILE-LEASE BROADCAST: Publishes uncommitted/dirty IDE files into IDE_CLOUD_ASYNC_BUS.json
       so the Cloud Runner automatically selects a disjoint chunk and never causes merge conflicts.
    4. CLEAN WORKTREE AUTO-PULL: Automatically applies aasha_aios_v2_bootstrap_full.bundle from Google
       Drive when the local worktree is clean, and updates .serena/memories/active_chunk_context.md
       so the Local IDE AI assistant sees the latest cloud progress immediately.
#>

param(
    [string]$RepoPath = "C:\Users\admin\Downloads\NGO AI LLM",
    [string]$DriveSyncFolderId = "1Xgtf699BHe2yKdw6ne1ilihXsgP6WMxD",
    [string]$ColabNotebookId = "1XPLBrKkB_nzrEWNUq3Z2plxnnq1VUJk2",
    [switch]$Loop,
    [int]$IntervalSeconds = 120
)

$ErrorActionPreference = "Continue"
$TargetBranch = "aios/v2-bootstrap"

function Invoke-AashaV3AsyncIDESync {
    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host " [AASHA V3 ASYNC IDE DAEMON] Zero-Approval 3-Plane CRDT Sync Starting " -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan

    if (-not (Test-Path $RepoPath)) {
        Write-Host "[WARN] Local repo path not found: $RepoPath" -ForegroundColor Yellow
        return
    }

    Set-Location $RepoPath

    # 1. Enforce strict non-main branch lock (aios/v2-bootstrap ONLY)
    $currentBranch = (git rev-parse --abbrev-ref HEAD 2>$null).Trim()
    if ($currentBranch -ne $TargetBranch) {
        Write-Host "[BRANCH-LOCK] Switching from '$currentBranch' to '$TargetBranch'..." -ForegroundColor Yellow
        git checkout -B $TargetBranch 2>$null | Out-Null
        $currentBranch = $TargetBranch
    }

    # 2. Inspect Local IDE dirty files (uncommitted edits in Antigravity / VS Code)
    $porcelain = @(git status --porcelain 2>$null)
    $dirtyFiles = @()
    foreach ($line in $porcelain) {
        if ($line.Length -gt 3) {
            $fileRel = $line.Substring(3).Trim()
            if ($fileRel -notmatch "^(PC_ANTIGRAVITY_STATE\.json|COLAB_ANTIGRAVITY_STATE\.json|IDE_CLOUD_ASYNC_BUS\.json|\.serena/)") {
                $dirtyFiles += $fileRel
            }
        }
    }

    # 3. If local IDE worktree is clean and a newer bundle exists from Plane 1 Drive, fast-forward from bundle
    $bundlePath = Join-Path $RepoPath "aasha_aios_v2_bootstrap_full.bundle"
    if (($dirtyFiles.Count -eq 0) -and (Test-Path $bundlePath)) {
        git bundle verify $bundlePath 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            git fetch $bundlePath "$TargetBranch`:refs/remotes/drive/$TargetBranch" 2>$null | Out-Null
            $localHead = (git rev-parse HEAD 2>$null).Trim()
            $bundleHead = (git rev-parse "refs/remotes/drive/$TargetBranch" 2>$null).Trim()
            if ($bundleHead -and ($localHead -ne $bundleHead)) {
                Write-Host "[ASYNC-BUS] Fast-forwarding clean Local IDE worktree to Drive Bundle HEAD $($bundleHead.Substring(0,7))..." -ForegroundColor Green
                git merge --ff-only "refs/remotes/drive/$TargetBranch" 2>$null | Out-Null
            }
        }
    }

    $headSha = (git rev-parse HEAD 2>$null).Trim()

    # 4. Run Python V3 CRDT State Merger + Anti-Contradiction Oracle + Serena IDE Memory Writer
    $env:PYTHONPATH = "src"
    $dirtyJson = ($dirtyFiles | ConvertTo-Json -Compress)
    if (-not $dirtyJson) { $dirtyJson = "[]" }
    if ($dirtyFiles.Count -eq 1) { $dirtyJson = "[$dirtyJson]" }

    $pyCmd = @"
import json
from aasha.orchestrator.zero_approval_async_ide_bus import AsyncLocalIDEBridgeBus, AntiContradictionGroundingOracle, AutonomousCryptographicProofGate
bus = AsyncLocalIDEBridgeBus('.')
oracle = AntiContradictionGroundingOracle('.')
proof = oracle.verify_claims(['src/aasha/orchestrator/zero_approval_async_ide_bus.py'], {'branch': '$TargetBranch'})
gate = AutonomousCryptographicProofGate().authorize_action('LOCAL_IDE_CRDT_SYNC', 'B1', 'PLANE_3_LOCAL_PC', '$TargetBranch', True, proof.passed)
res = bus.synchronize_ide_and_cloud_planes(
    newly_completed_chunk=None,
    ide_dirty_files=json.loads('''$dirtyJson'''),
    git_head_sha='$headSha',
    git_branch='$TargetBranch',
    active_writer_plane='PLANE_3_LOCAL_PC',
    oracle_digest=proof.oracle_proof_sha256,
    auth_proof_token=gate.proof_token_sha256,
)
print(json.dumps(res))
"@

    $syncOut = python -c $pyCmd 2>$null
    if ($LASTEXITCODE -eq 0 -and $syncOut) {
        $syncObj = $syncOut | ConvertFrom-Json
        Write-Host "[CRDT-SYNC] Completed Chunks: $($syncObj.completed_chunks -join ', ') | Next Active Chunk: $($syncObj.active_chunk_id) | CursorSHA: $($syncObj.cursor_lock_sha256.Substring(0,16))" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Executed Node fallback for CRDT IDE bus sync..." -ForegroundColor Yellow
        node scripts/aasha_continuous_loop.mjs --audit-only
    }
}

do {
    Invoke-AashaV3AsyncIDESync
    if ($Loop) {
        Start-Sleep -Seconds $IntervalSeconds
    }
} while ($Loop)
