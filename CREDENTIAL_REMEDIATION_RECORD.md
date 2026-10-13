# CREDENTIAL_REMEDIATION_RECORD.md
# AASHA AIOS — Credential Audit & Remediation Record (SEC-001)
**Authority**: Principal AI Systems Architect & Security QA Lead  
**Audit Finding**: SEC-001 (Priority: P0)  
**Date**: 2026-10-12  
**Status**: REMEDIATION IN PROGRESS / GIT REMOTES SANITIZED  

---

## 1. Summary of Identified Credential Exposure

During the Phase 0 audit, the following credential exposures were detected in configuration and environment files:

| Credential Type | File / Location | Exposure Type | Severity | Status |
| :--- | :--- | :--- | :--- | :--- |
| **GitHub PAT** | `c:\Users\admin\Downloads\NGO AI LLM\.git\config` | Embedded in `remote.origin.url` (`https://github_pat_11CAGO...`) | **CRITICAL** | **REMEDIATED (URL Sanitized)** |
| **GitHub PAT** | `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\.git\config` | Embedded in `remote.origin.url` (`https://github_pat_11CAGO...`) | **CRITICAL** | **REMEDIATED (URL Sanitized)** |
| **Graphify Bearer Token** | `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\.mcp.json` (Line 6) | Hard-coded Bearer token `Bearer pc_key_df279cd7_...` | **HIGH** | **PENDING ROTATION / ENV MIGRATION** |
| **Antigravity Global Config** | `C:\Users\admin\.gemini\config\mcp_config.json` | Hard-coded `GITHUB_PERSONAL_ACCESS_TOKEN`, `StitchMCP` API key, and `n8n` JWT | **HIGH** | **ISOLATED IN USER APPDATA (NOT IN REPO)** |

---

## 2. Immediate Remediation Actions Completed

### 2.1 Git Remote Origin Sanitization
Both the root repository and the sub-repository had their origin remote URLs stripped of the embedded `github_pat_...` string using `git remote set-url`:

```bash
# Executed remediation commands:
git remote set-url origin https://github.com/Anant1asha/NGO-AI-LLM.git
git -C .\Aasha-AI remote set-url origin https://github.com/Anant1asha/Aasha-AI.git
```

**Verification Evidence**:
- `git remote get-url origin` $\rightarrow$ `https://github.com/Anant1asha/NGO-AI-LLM.git` (Zero token characters)
- `git -C .\Aasha-AI remote get-url origin` $\rightarrow$ `https://github.com/Anant1asha/Aasha-AI.git` (Zero token characters)
- Neither `.git/config` file contains plain-text credentials in the remote URL.
- Authentication now relies on standard Git Credential Manager (GCM) or environment variables.

### 2.2 Pre-Commit Secret Scanning Invariant
Before staging any files (`git add`), the development agent must enforce an automated regex pattern match checking for:
- `github_pat_[a-zA-Z0-9_]{30,}`
- `ghp_[a-zA-Z0-9]{36}`
- `sk-[a-zA-Z0-9]{32,}`
- `sk-or-v1-[a-zA-Z0-9]{64}`
- `AIzaSy[a-zA-Z0-9_-]{33}`
- `Bearer\s+[a-zA-Z0-9_\-\.]{20,}`

Any commit attempt containing matched tokens will be rejected immediately by `PreCommitScrubber`.

---

## 3. Required Follow-up Actions for Repository Owner
1. **Rotate Exposed GitHub PAT**: Because the PAT `github_pat_11CAGO...[REDACTED_PAT]` was present in the local configuration and command history, revoke and regenerate it via GitHub Settings $\rightarrow$ Developer Settings $\rightarrow$ Personal Access Tokens.
2. **Rotate Graphify Bearer Token**: Rotate token `pc_key_df279cd7_...` in Graphify dashboard and inject via `.env` variable `GRAPHIFY_API_KEY`.
3. **Verify Git History**: Run `git log -S "github_pat_"` to confirm no previous commit introduced tokens into git history.
