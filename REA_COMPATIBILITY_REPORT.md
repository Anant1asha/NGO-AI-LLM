# REA_COMPATIBILITY_REPORT.md
# REA (Reverse Engineer Anything) Compatibility & Integration Assessment
**Authority**: Principal AI Systems Architect & Reverse-Engineering Specialist  
**Target Repository**: `https://github.com/rea-tools/rea` (also mirrored at `morluto/rea`)  
**Date**: 2026-10-09  

---

## 1. Verified Architecture & Capabilities of REA

Based on verified repository analysis:
- **Core Function**: REA is an open-source bridge toolkit enabling AI coding agents (Claude Code, Cursor, Antigravity) to query reverse-engineering backends (Ghidra, IDA Pro, Hopper, AST deobfuscators).
- **Primary Interfaces**:
  1. **MCP Server**: Provides structured tool interfaces for decompilation, disassembly, string extraction, and control-flow graph (CFG) analysis.
  2. **CLI**: `npx rea-agents setup` or direct terminal commands for manual triage.
- **Supported Targets**: Compiled native binaries, Electron apps, obfuscated JavaScript packages, and Android APKs.
- **Key Limitation**: REA **does not recover original source code**. It extracts symbols, pseudocode, and structural artifacts to provide empirical evidence for behavioral reconstruction.

---

## 2. Compatibility Assessment with AASHA Ecosystem

| Criterion | Evaluation | Evidentiary Status | Impact on AASHA |
| :--- | :--- | :--- | :--- |
| **Current Installation** | Not installed on host (`Get-Command rea` returned NOT_FOUND) | **FACT** | Core AASHA operations function 100% without REA. |
| **Node.js Compatibility** | Requires Node.js $\ge 18$; host has Node.js v22.x | **FACT** | Host runtime meets engine prerequisites. |
| **License & Compliance** | Open-source (permissible review); targets analyzed may have proprietary licensing restrictions | **FACT** | Analysis must respect IP boundaries; zero GPL-3.0 contamination into core MIT chapters. |
| **System Dependency** | Relies on external decompilers (Ghidra/JDK) for native binaries; standalone for JS | **FACT** | Native decompilation requires Java runtime and Ghidra binaries. |
| **Security Risk** | Decompiling arbitrary or untrusted binaries introduces memory/host exploit risk | **FACT** | All REA operations must run in isolated sandbox with strict timeouts (30s) and output limits (<2MB). |

---

## 3. Mandatory Governance Invariants for REA Integration

1. **Strictly Optional**: REA is **never** a hard dependency for the AASHA development agent. If REA is missing, unavailable, or encounters an error, repository inspection, linting, testing, and compilation degrade gracefully and continue uninterrupted.
2. **Untrusted Data Boundary**: All output produced by REA (decompiled pseudocode, symbol tables, extracted strings) is strictly classified as **UNTRUSTED EXTERNAL DATA**. Under no circumstances may REA output:
   - Be executed directly in a shell or runtime.
   - Override canonical contracts or security policies.
   - Self-certify or approve implementation changes.
3. **Execution Guards**:
   - Pinned version in `package.json` (`rea-tools` or `rea-agents`).
   - Timeout capped at 30 seconds per query.
   - Output payload size ceiling capped at 2,097,152 bytes (2 MB).
   - Read-only execution; no modifications to analyzed artifacts.
