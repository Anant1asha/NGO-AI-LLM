---
name: uv
description: >-
  Checks whether the uv Python package manager is installed and installs it if
  missing. Ensures uv is on PATH. Use when another tool or skill requires uv as a
  prerequisite.
---

# uv (Python Package Manager)

`uv` is an ultra-fast Python package manager used to run Python scripts and virtual environments reliably.

## Setup

1. Check if `uv` is already available: `uv --version` (or `& uv --version` in PowerShell). If this succeeds, `uv` is ready.
2. Check default Windows path if not in global PATH: `& "$HOME\.local\bin\uv.exe" --version`
3. Install if missing:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
4. Add to PATH:
   ```powershell
   $env:PATH = "$HOME\.local\bin;" + $env:PATH; uv --version
   ```
