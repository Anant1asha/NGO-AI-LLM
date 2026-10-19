---
name: lsp-toolchain-bootstrap
description: Audits, installs, and verifies language server protocol (LSP) runtimes (TypeScript, Pyright, Gopls) and persists tool paths to Windows User PATH with deduplication.
---

# LSP Toolchain Bootstrap & Environment Manager

This skill provides an automated, idempotent runbook to audit, install, and verify the 3 core language servers required for the AASHA AIOS multi-language substrate:
1. **TypeScript LSP** (`typescript-language-server`) for `Aasha-AI` TypeScript/React.
2. **Pyright LSP** (`pyright`) for Python PDF and AST pipelines.
3. **Gopls LSP** (`gopls`) for `gemini-web2api`.

---

## 1. Audit Runtimes & LSPs

Run the pre-flight check across all target binaries:
```powershell
Get-Command typescript-language-server, pyright, gopls, node, python, go -ErrorAction SilentlyContinue | Select-Object Name, Source
```

---

## 2. Non-Interactive Installation Pipeline (Windows)

### A. TypeScript Language Server
```powershell
npm install -g typescript-language-server typescript
```

### B. Pyright Language Server
```powershell
python -m pip install --upgrade pyright
```

### C. Go Runtime & Gopls
If `go.exe` is missing, install the official MSI non-interactively via `winget`:
```powershell
winget install --id GoLang.Go --exact --silent --accept-source-agreements --accept-package-agreements
```
Once Go is installed, compile Gopls:
```powershell
$env:Path = "C:\Program Files\Go\bin;" + $env:Path
go install golang.org/x/tools/gopls@latest
```

---

## 3. Persistent Windows Registry Environment Registration

In strict adherence to the *Windows Registry Environment Access Invariant*, safely append binary directories to User `PATH` with deduplication:

```powershell
try {
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $pathsToAdd = @(
        "C:\Program Files\nodejs",
        "C:\Users\admin\AppData\Roaming\npm",
        "C:\Users\admin\AppData\Local\Programs\Python\Python315\Scripts",
        "C:\Program Files\Go\bin",
        "$env:USERPROFILE\go\bin"
    )
    $currentPaths = $userPath -split ';' | Where-Object { $_ -ne "" }
    $updated = $false
    foreach ($p in $pathsToAdd) {
        if ($currentPaths -notcontains $p -and (Test-Path $p)) {
            $currentPaths += $p
            $updated = $true
        }
    }
    if ($updated) {
        $newPath = $currentPaths -join ';'
        [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "User PATH updated successfully."
    } else {
        Write-Host "All paths already present in User PATH."
    }
} catch {
    Write-Warning "Could not persist to User registry: $_. Falling back to session PATH."
}
```

---

## 4. Verification Suite

Validate all 3 language servers:
```powershell
typescript-language-server --version
pyright --version
gopls version
```
All commands must exit with code 0 and output valid version numbers.
