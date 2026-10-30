<#
.SYNOPSIS
  AASHA AIOS — Local Windows PC & Antigravity Infrastructure Auto-Bridge Daemon
  Target Directory: C:\Users\admin\Downloads\NGO AI LLM

.DESCRIPTION
  1. Registers itself as a Windows Logon Scheduled Task ("AASHA_Antigravity_PC_Bridge")
     when invoked with -InstallStartupTask so it runs automatically whenever the PC turns on.
  2. Synchronizes the sanitized .agents\mcp_config.json (Sequential Thinking, Context7,
     Playwright MCP, and mark3labs Filesystem Server) to both the workspace and
     %USERPROFILE%\.gemini\config\mcp_config.json.
  3. Checks and boots local AASHA infrastructure when available:
     - Docker Desktop / PostgreSQL 17 + FastAPI backend (docker-compose.yml)
     - Local gemini-web2api OpenAI-compatible proxy binary
     - Local Antigravity IDE / agy CLI status
  4. Audits Git branch, HEAD commit SHA, uncommitted file count, and L-Truth QA status
     across both C:\Users\admin\Downloads\NGO AI LLM and nested .\Aasha-AI.
  5. Writes a deterministic PC_ANTIGRAVITY_STATE.json manifest and pushes/syncs it so
     the Gemini Cloud Scheduled Agent ("Sync local Antigravity PC infra") detects that
     your PC is online and runs the next phased MVP build step automatically.
#>

param(
    [string]$WorkspaceRoot = "C:\Users\admin\Downloads\NGO AI LLM",
    [int]$HeartbeatIntervalSeconds = 900,
    [switch]$Once,
    [switch]$InstallStartupTask
)

$ErrorActionPreference = "Continue"

function Register-AashaStartupTask {
    param([string]$ScriptFullPath, [string]$RootPath)
    $TaskName = "AASHA_Antigravity_PC_Bridge"
    $ArgList = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptFullPath`" -WorkspaceRoot `"$RootPath`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ArgList
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Description "Auto-starts AASHA Antigravity PC infrastructure and syncs state whenever the PC is on." `
        -Force | Out-Null
    Write-Host "[AASHA-BRIDGE] Registered Windows Startup Task: $TaskName" -ForegroundColor Green
}

function Ensure-AntigravityMcpConfig {
    param([string]$RootPath)
    $AgentsDir = Join-Path $RootPath ".agents"
    if (-not (Test-Path $AgentsDir)) {
        New-Item -ItemType Directory -Force -Path $AgentsDir | Out-Null
    }
    $McpConfigPath = Join-Path $AgentsDir "mcp_config.json"
    $NormalizedRoot = $RootPath -replace "\\", "/"
    $McpJson = @{
        mcpServers = [ordered]@{
            "sequential-thinking" = @{
                command = "npx"
                args    = @("-y", "@modelcontextprotocol/server-sequential-thinking")
                env     = @{ DISABLE_THOUGHT_LOGGING = "false" }
            }
            "context7" = @{
                command = "npx"
                args    = @("-y", "@upstash/context7-mcp", "--api-key", "`${CONTEXT7_API_KEY}")
            }
            "playwright" = @{
                command = "npx"
                args    = @("@playwright/mcp@latest", "--isolated", "--headless")
            }
            "filesystem" = @{
                command = "mcp-filesystem-server"
                args    = @(
                    "$NormalizedRoot",
                    "$NormalizedRoot/Aasha-AI",
                    "$NormalizedRoot/AASHA_Visual_Mass_Harvest_Phase3"
                )
            }
        }
    } | ConvertTo-Json -Depth 6

    Set-Content -Path $McpConfigPath -Value $McpJson -Encoding UTF8

    $GlobalMcpPath = Join-Path $env:USERPROFILE ".gemini\config\mcp_config.json"
    $GlobalMcpDir = Split-Path $GlobalMcpPath
    if (-not (Test-Path $GlobalMcpDir)) {
        New-Item -ItemType Directory -Force -Path $GlobalMcpDir | Out-Null
    }
    if (-not (Test-Path $GlobalMcpPath)) {
        Set-Content -Path $GlobalMcpPath -Value $McpJson -Encoding UTF8
    }
}

function Invoke-AashaInfrastructureWakeAndSync {
    param([string]$RootPath)

    if (-not (Test-Path $RootPath)) {
        Write-Warning "[AASHA-BRIDGE] Workspace folder not found: $RootPath"
        return
    }

    Set-Location $RootPath
    Ensure-AntigravityMcpConfig -RootPath $RootPath

    # 1. Start Docker Compose services (Postgres 17 + Backend) if Docker is running
    $DockerActive = $false
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $DockerActive = $true
            $ComposeCandidates = @(
                (Join-Path $RootPath "docker-compose.yml"),
                (Join-Path $RootPath "Aasha-AI\docker-compose.yml"),
                (Join-Path $RootPath "Aasha-AI\Aasha-Learning-Impact-Ecosystem-v0.3-full-release\docker-compose.yml")
            )
            foreach ($cf in $ComposeCandidates) {
                if (Test-Path $cf) {
                    docker compose -f $cf up -d *> $null
                    break
                }
            }
        }
    }

    # 2. Start gemini-web2api local proxy if binary exists and is not running
    $GeminiProxyActive = [bool](Get-Process -Name "gemini-web2api*" -ErrorAction SilentlyContinue)
    if (-not $GeminiProxyActive) {
        $ProxyExe = Join-Path $RootPath "gemini-web2api\gemini-web2api.exe"
        if (Test-Path $ProxyExe) {
            Start-Process -FilePath $ProxyExe -WorkingDirectory (Split-Path $ProxyExe) -WindowStyle Hidden
            $GeminiProxyActive = $true
        }
    }

    # 2b. Check and auto-enable 9Router local gateway on port 20128 if not responding
    $NineRouterActive = $false
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $tcpClient.BeginConnect("127.0.0.1", 20128, $null, $null)
        $waitHandle = $asyncResult.AsyncWaitHandle.WaitOne(800, $false)
        if ($waitHandle -and $tcpClient.Connected) {
            $tcpClient.EndConnect($asyncResult)
            $NineRouterActive = $true
        }
        $tcpClient.Close()
    } catch {
        $NineRouterActive = $false
    }

    if (-not $NineRouterActive) {
        $NineRouterCandidates = @(
            (Join-Path $env:APPDATA "npm\node_modules\9router\app\custom-server.js"),
            (Join-Path $env:USERPROFILE "AppData\Roaming\npm\node_modules\9router\app\custom-server.js")
        )
        foreach ($serverScript in $NineRouterCandidates) {
            if (Test-Path $serverScript) {
                Write-Host "[AASHA-BRIDGE] 9Router offline on port 20128. Auto-enabling background daemon..." -ForegroundColor Yellow
                $NodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
                if (-not $NodeExe) { $NodeExe = "node.exe" }
                Start-Process -FilePath $NodeExe -ArgumentList "`"$serverScript`"" `
                    -Environment @{ PORT = "20128"; HOSTNAME = "127.0.0.1" } `
                    -WindowStyle Hidden
                $NineRouterActive = $true
                break
            }
        }
    }

    $AntigravityActive = [bool](Get-Process -Name "Antigravity*","agy*" -ErrorAction SilentlyContinue)

    # 3. Inspect Git state in Root (NGO AI LLM) and Nested (Aasha-AI)
    $RootBranch = (git rev-parse --abbrev-ref HEAD 2>$null)
    $RootCommit = (git rev-parse HEAD 2>$null)
    $RootStatus = @(git status --porcelain 2>$null)

    $AashaAiDir = Join-Path $RootPath "Aasha-AI"
    $AashaBranch = "NOT_FOUND"
    $AashaCommit = "NOT_FOUND"
    $AashaStatus = @()

    if (Test-Path $AashaAiDir) {
        Push-Location $AashaAiDir
        $AashaBranch = (git rev-parse --abbrev-ref HEAD 2>$null)
        $AashaCommit = (git rev-parse HEAD 2>$null)
        $AashaStatus = @(git status --porcelain 2>$null)
        Pop-Location
    }

    # 4. Emit deterministic PC_ANTIGRAVITY_STATE.json
    $StateObject = [ordered]@{
        schema_version = "1.0.0"
        timestamp_utc  = (Get-Date).ToUniversalTime().ToString("o")
        pc_hostname    = $env:COMPUTERNAME
        workspace_root = $RootPath
        infrastructure = [ordered]@{
            antigravity_running  = $AntigravityActive
            docker_running       = $DockerActive
            gemini_proxy_running = $GeminiProxyActive
            ninerouter_running   = $NineRouterActive
            node_version         = (node -v 2>$null)
            python_version       = (python --version 2>$null)
        }
        repositories = [ordered]@{
            ngo_ai_llm_root = [ordered]@{
                branch            = $RootBranch
                head_commit       = $RootCommit
                dirty_file_count  = $RootStatus.Count
                dirty_files_sample = ($RootStatus | Select-Object -First 20)
            }
            aasha_ai_monorepo = [ordered]@{
                branch            = $AashaBranch
                head_commit       = $AashaCommit
                dirty_file_count  = $AashaStatus.Count
                dirty_files_sample = ($AashaStatus | Select-Object -First 20)
            }
        }
    }

    $StatePathRoot = Join-Path $RootPath "PC_ANTIGRAVITY_STATE.json"
    $StateObject | ConvertTo-Json -Depth 6 | Set-Content -Path $StatePathRoot -Encoding UTF8

    if (Test-Path $AashaAiDir) {
        $StatePathSub = Join-Path $AashaAiDir "PC_ANTIGRAVITY_STATE.json"
        Copy-Item -Path $StatePathRoot -Destination $StatePathSub -Force

        Push-Location $AashaAiDir
        git fetch origin 2>$null
        git add PC_ANTIGRAVITY_STATE.json 2>$null
        git diff --cached --quiet 2>$null
        if ($LASTEXITCODE -ne 0) {
            git commit -m "chore(pc-bridge): auto-sync local PC Antigravity & infra state [skip ci]" 2>$null
            git push origin HEAD 2>$null
        }
        Pop-Location
    }

    Write-Host "[AASHA-BRIDGE] Synced PC_ANTIGRAVITY_STATE.json at $((Get-Date).ToString('u'))" -ForegroundColor Cyan
}

if ($InstallStartupTask) {
    Register-AashaStartupTask -ScriptFullPath $MyInvocation.MyCommand.Definition -RootPath $WorkspaceRoot
}

do {
    Invoke-AashaInfrastructureWakeAndSync -RootPath $WorkspaceRoot
    if ($Once) { break }
    Start-Sleep -Seconds $HeartbeatIntervalSeconds
} while ($true)
