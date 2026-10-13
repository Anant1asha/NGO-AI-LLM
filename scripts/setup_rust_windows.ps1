param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " [AASHA Studio] Windows Native Rust Toolchain Prerequisite Setup      " -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Note: If you only need to preview chapters or edit Section 24 contracts," -ForegroundColor DarkGray
Write-Host "Tier 3 Zero-Rust Browser Mode works out-of-the-box (Zero Rust required)." -ForegroundColor DarkGray
Write-Host ""

# Check Cargo in path or user directory
$cargoInPath = Get-Command "cargo.exe" -ErrorAction SilentlyContinue
$userCargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
$userCargoExe = Join-Path $userCargoBin "cargo.exe"

if (-not $cargoInPath -and (Test-Path $userCargoExe)) {
    $env:PATH = $userCargoBin + ";" + $env:PATH
    $cargoInPath = Get-Command "cargo.exe" -ErrorAction SilentlyContinue
}

$rustcInPath = Get-Command "rustc.exe" -ErrorAction SilentlyContinue

# Check VS Build Tools via vswhere or cl.exe
$progFilesX86 = [System.Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
if (-not $progFilesX86) { $progFilesX86 = "C:\Program Files (x86)" }
$vswhere = Join-Path $progFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"

$hasMsvc = $false
if (Test-Path $vswhere) {
    $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
    if ($vsPath) {
        $hasMsvc = $true
    }
} else {
    $clInPath = Get-Command "cl.exe" -ErrorAction SilentlyContinue
    if ($clInPath) { $hasMsvc = $true }
}

Write-Host "Toolchain Inspection Status:" -ForegroundColor White
if ($cargoInPath) {
    $cargoVer = & cargo --version
    Write-Host "  [+] Cargo:    $cargoVer" -ForegroundColor Green
} else {
    Write-Host "  [-] Cargo:    NOT FOUND" -ForegroundColor Red
}

if ($rustcInPath) {
    $rustcVer = & rustc --version
    Write-Host "  [+] Rust:     $rustcVer" -ForegroundColor Green
} else {
    Write-Host "  [-] Rust:     NOT FOUND" -ForegroundColor Red
}

if ($hasMsvc) {
    Write-Host "  [+] MSVC C++: Installed and detected" -ForegroundColor Green
} else {
    Write-Host "  [!] MSVC C++: Not detected in default path (Visual Studio C++ Build Tools)" -ForegroundColor Yellow
}

Write-Host ""

if ($CheckOnly) {
    if ($cargoInPath -and $hasMsvc) {
        Write-Host "Native toolchain is complete. Ready for 'cargo tauri build' (.exe / .msi)!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "Toolchain incomplete for native .exe packaging. Tier 3 Zero-Rust mode remains active." -ForegroundColor Yellow
        exit 0
    }
}

# If both are present, we're ready!
if ($cargoInPath -and $hasMsvc) {
    Write-Host "Both Rust and MSVC C++ tools are ready! You can compile native Windows installers:" -ForegroundColor Green
    Write-Host "   npm run studio:package" -ForegroundColor Cyan
    exit 0
}

# Installation Assistant
Write-Host "Installing missing toolchain components via Windows Package Manager (winget)..." -ForegroundColor Cyan

$winget = Get-Command "winget.exe" -ErrorAction SilentlyContinue
if (-not $winget) {
    Write-Host "winget.exe not found. Please install Rust manually:" -ForegroundColor Red
    Write-Host "   1. Download and run: https://win.rustup.rs/x86_64" -ForegroundColor White
    Write-Host "   2. Install Visual Studio C++ Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor White
    exit 1
}

if (-not $cargoInPath) {
    Write-Host "Installing Rustup via winget..." -ForegroundColor Yellow
    winget install Rustlang.Rustup --accept-package-agreements --accept-source-agreements
    if (Test-Path $userCargoExe) {
        $env:PATH = $userCargoBin + ";" + $env:PATH
        $currentUserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
        [System.Environment]::SetEnvironmentVariable("PATH", $userCargoBin + ";" + $currentUserPath, "User")
        Write-Host "Rustup installed! Cargo is now available in session." -ForegroundColor Green
    }
}

if (-not $hasMsvc) {
    Write-Host "To compile native C++ binaries, install Microsoft Visual Studio C++ Build Tools:" -ForegroundColor Yellow
    Write-Host "   Run this command in an Administrator terminal:" -ForegroundColor White
    Write-Host "   winget install Microsoft.VisualStudio.2022.BuildTools --force --override `"--passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended`"" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Note: Even without Rust installed, you can launch the full AASHA Studio GUI:" -ForegroundColor Cyan
Write-Host "   npm run studio" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan
