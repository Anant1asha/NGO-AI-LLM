# Hachi one-liner installer (Windows / PowerShell)
#
#   irm https://raw.githubusercontent.com/OpenGigantic/hachi/main/install.ps1 | iex
#
# Bootstraps uv (which manages Python), fetches Hachi, installs deps, and
# launches the guided setup. Override the source repo or install location with
# the HACHI_REPO / HACHI_HOME environment variables.
#Requires -Version 5
$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:HACHI_REPO) { $env:HACHI_REPO } else { "https://github.com/OpenGigantic/hachi" }
# Pin what you install. Empty means the default branch, so re-running later
# silently upgrades. Set HACHI_REF=v0.1.0 for a reproducible install.
$HachiRef = $env:HACHI_REF
$InstallDir = if ($env:HACHI_HOME) { $env:HACHI_HOME } else { "$env:USERPROFILE\.hachi-src" }

function Info($message) { Write-Host "==> $message" -ForegroundColor Cyan }

# Never let git block on a credential prompt (fails fast instead of hanging).
# GIT_TERMINAL_PROMPT only covers *terminal* prompts - Git Credential Manager
# (Git for Windows' default helper) pops a GUI dialog instead, which still blocks
# a headless install. Blank the askpass helper too.
$env:GIT_TERMINAL_PROMPT = "0"
$env:GIT_ASKPASS = ""

# 1. Preconditions first - no point bootstrapping a Python toolchain only to
#    discover git is missing afterwards.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Error: git is required but not installed. Install git and re-run." -ForegroundColor Red
    exit 1
}

# 2. Ensure uv (it provisions a suitable Python automatically).
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Info "Installing uv (Python toolchain manager)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression

    # The upstream installer only edits the *registry* PATH; it does not refresh
    # this process. Without re-reading the user PATH here, `Get-Command uv`
    # still fails and the `uv sync` below aborts under $ErrorActionPreference=Stop.
    #
    # Prepend rather than replace: assigning machine;user discards directories
    # injected into this session (conda, scoop, wrapper shims), and the registry
    # values can still contain unexpanded %VAR% entries.
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$env:Path;" +
        [System.Environment]::ExpandEnvironmentVariables($machinePath) + ";" +
        [System.Environment]::ExpandEnvironmentVariables($userPath)

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "Error: uv was installed but is not on PATH for this session." -ForegroundColor Red
        Write-Host "Close and reopen PowerShell, then re-run this installer." -ForegroundColor Red
        exit 1
    }
}

# 3. Fetch (or update) the source. $env:GIT_TERMINAL_PROMPT=0 (set above) turns
#    a credential prompt into a clean failure rather than an indefinite hang.
if (Test-Path "$InstallDir\.git") {
    Info "Updating Hachi in $InstallDir..."
    git -C $InstallDir pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: could not update $InstallDir (local changes or rewritten history)." -ForegroundColor Red
        Write-Host "Remove that directory and re-run, or set HACHI_HOME to a fresh path." -ForegroundColor Red
        exit 1
    }
}
else {
    Info "Cloning Hachi into $InstallDir..."
    if ($HachiRef) {
        git clone --depth 1 --branch $HachiRef $RepoUrl $InstallDir
    }
    else {
        git clone --depth 1 $RepoUrl $InstallDir
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: git clone failed. If the repository is private, this installer cannot fetch it." -ForegroundColor Red
        exit 1
    }
}

# 4. Install dependencies. A native non-zero exit is NOT a terminating error
#    under $ErrorActionPreference = "Stop", so without this check a failed sync
#    fell through and printed the success banner anyway - the same masked-failure
#    class this change removed from the POSIX installer.
Set-Location $InstallDir
Info "Installing dependencies (this can take a minute)..."
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: dependency install failed. Run 'uv sync' in $InstallDir to see the full error." -ForegroundColor Red
    exit 1
}

# 4. Launch the guided setup - only when a human is present. `quickstart` is
#    interactive; under `irm ... | iex` in CI it would abort a successful install.
if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
    Info "Installed! Launching setup..."
    uv run --project $InstallDir hachi quickstart
}
else {
    Info "Installed (non-interactive session - skipping guided setup)."
}

# ASCII only: PowerShell 5.1 decodes a BOM-less script as ANSI, which turns
# box-drawing characters into mojibake.
Write-Host ""
Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "Hachi is installed. Start chatting with:" -ForegroundColor Green
Write-Host "  uv run --project `"$InstallDir`" hachi run"
Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
