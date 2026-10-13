# THREAT_MODEL.md
# AASHA AIOS Development Agent — Security Threat Model
**Authority**: Senior Security QA Lead & Systems Architect  
**Model Standard**: STRIDE & MITRE ATT&CK for Agentic Systems  
**Date**: 2026-10-12  
**Status**: ACTIVE THREAT MODEL (SEC-001 Remediated in Git Remotes)  

---

## 1. Threat Environment & Core Security Tenets

1. **Public Repository Default Assumption**: Every ecosystem repository (`NGO-AI-LLM`, `Aasha-AI`, `aasha-studio`) is assumed to be **100% PUBLIC**. No repository or branch is treated as private.
2. **Absolute Zero-Secret Staging Policy**: API keys, PATs, cryptographic keys, and active `.env` files must NEVER be staged, committed, or pushed.
3. **Untrusted Data Boundary**: Repository files, issue bodies, PR comments, web pages, test terminal output, and REA outputs are untrusted. Indirect prompt injections contained in these sources must NEVER alter system state, bypass authorization, or elevate execution permissions.
4. **Least Privilege & No Self-Promotion**: An LLM or automated workflow cannot grant itself permissions or approve its own code promotion.
5. **Zero Inbound Port Exposure**: No public inbound HTTP/TCP listeners or tunnels are permitted on the developer workstation. All communication with hosted services (`airtribe.app.n8n.cloud`, GitHub, OpenRouter) is strictly **OUTBOUND HTTPS**.

---

## 2. Threat Analysis (STRIDE Matrix)

| Threat Category | Attack Vector / Scenario | Impact | Mitigation Strategy | Enforcement Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **Spoofing (S)** | Malicious webhook or unauthenticated actor triggers task execution in n8n. | Unauthorized code execution or test resource exhaustion. | HMAC-SHA256 signature verification on all incoming intake webhooks. | `WebhookSignatureValidator` node / middleware. |
| **Tampering (T)** | Prompt injection inside a committed markdown/code file instructs the agent to modify governance rules or bypass tests. | Architectural drift, deletion of safety checks, or spoiler leakage. | Rigid separation between data and instructions; deterministic Gatekeeper schema audits; system prompts marked immutable. | Strict input sanitization; AST-level schema validation (`ContextBus.validateOutput()`). |
| **Repudiation (R)** | Code changes promoted without auditable proof of reviewer authorization or test pass. | Inability to audit defective or insecure releases. | Cryptographically signed, artifact-bound Evidence Ledger. Every promotion requires binding exact commit SHA and diff hash. | `VersionManager` & `EvidenceLedger` HMAC signatures. |
| **Information Disclosure (I)** | Accidental leakage of API keys, GitHub PATs, or student PII via commit diffs, logs, or n8n exports. | Account compromise, compliance violation (child data protection). | Zero-token logging policy; pre-commit regex scrubbing; `.gitignore` enforcement; mandatory credential masking. | `PreCommitScrubber` & Secret Linter regex suite. |
| **Denial of Service (D)** | Unbounded recursive repair loops or model API flooding causing financial token bleed or server lockup. | API rate limiting, resource exhaustion, financial waste. | Strict Bounded Repair Policy (1 attempt + max 2 repairs); 3s backoff; Tier 1 free pool fallback; paid Gemini hard lock. | `openrouter_client.ts` circuit breaker; sliding-window token caps. |
| **Elevation of Privilege (E)** | Model executes arbitrary shell commands (e.g. `rm -rf`, `curl | bash`, or unauthorized git push). | Host compromise or unauthorized repository mutation. | Strict command allowlist; execution restricted to isolated Git worktree; human approval gate bound to diff hash. | `CommandAllowlistExecutor` & Worktree Manager. |

---

## 3. Remediation Status of Specific Security Findings

### Finding SEC-001: Embedded GitHub PAT in Sub-Repository Remote URL
- **Severity**: **CRITICAL** $\rightarrow$ **REMEDIATED (In Config)**.
- **Action Taken**: Both root and `Aasha-AI` remote URLs updated via `git remote set-url origin` to remove all token strings.
- **Follow-up**: User requested to rotate token in GitHub UI.

### Finding SEC-002: Embedded API Key in `.mcp.json`
- **Location**: `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\.mcp.json` line 6.
- **Severity**: **HIGH**.
- **Action Required**: Migrate token to environment variable interpolation (`${GRAPHIFY_API_KEY}`) and verify `.gitignore` blocks `.mcp.json` if it contains private secrets.

### Finding SEC-003: Insecure Local IDE Inbound Exposure Risk
- **Risk**: Opening an unauthenticated port to connect hosted n8n to local Antigravity.
- **Severity**: **CRITICAL (Architectural Boundary)**.
- **Resolution**: Confirmed that Antigravity connects **OUTBOUND** to hosted n8n (`https://airtribe.app.n8n.cloud/mcp-server/http`) via `mcp-remote` with Bearer auth. Hosted n8n coordinates with GitHub directly; no inbound listening port is created on the developer workstation.
