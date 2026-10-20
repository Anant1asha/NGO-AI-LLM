# AASHA AIOS — Human-in-the-Loop (HIL) Beta Specification

## 1. Core Operating Principle
> **"By HIL in beta phase, I mean myself that makes instant review of mine, and for all other tasks full access is granted."**  
> — *Super Admin Governance Policy*

In the beta development phase of AASHA AIOS, **Human-in-the-Loop (HIL)** does NOT mean frequent permission popups, repetitive OAuth consent loops (`https://airtribe.app.n8n.cloud/oauth/consent`), or pausing autonomous agents for routine coding and testing steps. 

Instead, HIL designates a precise, high-trust operational model:
- **Full Autonomous Access Granted** for all internal operations.
- **Instant Super Admin Review** at well-defined, consequential release gates.

---

## 2. Dual-Layer Operational Model

```mermaid
graph TD
    subgraph Autonomous Layer ["Autonomous Execution Layer (Full Access Pre-Authorized)"]
        A1["Code Synthesis & Refactoring"]
        A2["Test Harnesses & Benchmark Runs"]
        A3["Prestack Asset Ingestion & Local CDN Build"]
        A4["Laya System 1 Pre-Routing"]
        A5["Headless n8n Webhook / API Calls"]
        A6["AST & Memory Graph Synchronization"]
    end

    subgraph HIL Gate ["Super Admin Instant Review (HIL Gateway)"]
        G1["Gate 6: Git Push to Public Remote"]
        G2["Production Release Artifact Publication"]
        G3["Destructive Schema / Database Migrations"]
    end

    Autonomous Layer -->|All routine tasks execute continuously| Autonomous Layer
    Autonomous Layer -->|Reaches Gate 6 / Final Deliverable| HIL Gate
    HIL Gate -->|Instant One-Click Approval by Super Admin| Deployed["Promoted to Production"]
```

---

## 3. Boundary Matrix

| Task Category | Access Level | Interruption Policy | Mechanism |
|---|---|---|---|
| **Code Editing & Creation** | FULL ACCESS | 0 prompts | Antigravity IDE / Claude Code tools |
| **Unit & E2E Testing** | FULL ACCESS | 0 prompts | `npm test`, `test:master`, `test:ltruth` |
| **Prestack Asset Ingestion** | FULL ACCESS | 0 prompts | `node scripts/orchestrate_local_cdn.mjs` |
| **Local Memory & Graph Updates** | FULL ACCESS | 0 prompts | Serena MCP, SQLite `aasha_operational.db` |
| **External Webhook / n8n Trigger** | FULL ACCESS | 0 prompts (Headless) | `scripts/n8n_headless_client.mjs` (Zero OAuth popups) |
| **Laya System 1 Routing** | FULL ACCESS | 0 prompts (<1ms) | Local Python daemon / in-memory regex |
| **Gate 6 Git Remote Push** | **HIL GATED** | Instant Review Required | Diff artifact summary + single-click user confirmation |
| **Release Installer Signoff** | **HIL GATED** | Instant Review Required | Checksum validation + human confirmation |

---

## 4. Elimination of the n8n OAuth Consent Loop
Past setups occasionally redirected developer browsers to `https://airtribe.app.n8n.cloud/oauth/consent` under the assumption that every remote workflow trigger required interactive human re-authorization.

**Remediation Rule**:
- All agent-to-n8n communication operates strictly through **headless outbound HTTPS requests** with static Bearer/API tokens.
- Interactive OAuth consent redirects are completely disabled during agent execution loops.

---

## 5. Review Protocol for Super Admin
When the agent reaches an approved HIL gate:
1. The agent compiles an **Evidence & Diff Summary Artifact** (e.g. `walkthrough.md` or release note).
2. The agent states the exact actions ready to be promoted.
3. The Super Admin reviews the proposal and issues a clean approval (`Proceed`, `LGTM`, or guidance).
4. Upon approval, execution immediately completes without additional prompts.
