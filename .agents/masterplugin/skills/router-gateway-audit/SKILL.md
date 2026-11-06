---
name: router-gateway-audit
description: Audits local 9Router proxy gateway health, verifies zero-secret .env isolation, runs Laya dual-path pre-routing, and certifies anti-bleed fallback cascade.
---

# /router-gateway-audit: 9Router Gateway & Laya Router Audit

Runbook for verifying 9Router local proxy connectivity, ensuring zero-secret staging compliance, validating Laya System 1 pre-routing, and testing circuit-breaker cascades.

## Quick Diagnostic Commands

Run all checks from the workspace root or `Aasha-AI`:

```powershell
# 0. Start 9Router Headless on Windows (Local-Only Daemon) if port 20128 is offline
$env:PORT='20128'; $env:HOSTNAME='127.0.0.1'; node "$env:APPDATA\npm\node_modules\9router\app\custom-server.js"

# 1. Zero-Secret Staging Audit (Must return 0 matches)
git grep -i "NINEROUTER_API_KEY="
git -C Aasha-AI grep -i "NINEROUTER_API_KEY="

# 2. Dual-Root Environment Check (Verify NINEROUTER_API_KEY is detected)
node -e "require('dotenv').config({path:'Aasha-AI/.env'}); console.log('9Router Key Configured:', Boolean(process.env.NINEROUTER_API_KEY))"

# 3. 9Router Primary Gateway & Anti-Bleed Self-Test
npx --prefix Aasha-AI tsx Aasha-AI/packages/llm-router/openrouter_client.ts --test

# 4. Laya System 1 Dual-Path Router Test (Offline Heuristic + Daemon Pipeline)
npx --prefix Aasha-AI tsx Aasha-AI/tests/laya_router.test.ts

# 5. Full Ecosystem Certification Gate
npx --prefix Aasha-AI tsc --noEmit -p Aasha-AI/tsconfig.json
npm --prefix Aasha-AI run test:server
npm --prefix Aasha-AI run test:ltruth
node tests/e2e_all_chapters_suite.js
npm --prefix multi-agent-tui test
```

## Gateway Behavioral Invariants

1. **Local Proxy Key Hygiene (`http://localhost:20128/dashboard`)**:
   - The key must reside exclusively in `Aasha-AI/.env` as `NINEROUTER_API_KEY`.
   - Never commit API key strings as code defaults; `.env` is shielded by `.gitignore`.

2. **Fast-Fail Circuit Breaker**:
   - On HTTP 401/403 or `ECONNREFUSED`, the router aborts multi-model retries immediately and fast-cascades to the Tier 1 OpenRouter free pool.

3. **Placeholder Sanitization**:
   - Template values such as `YOUR_9ROUTER_API_KEY_HERE` are stripped at runtime to prevent invalid bearer headers.

4. **Dual-Root `.env` Resolution**:
   - Multi-root runners load both `process.cwd()/.env` and `Aasha-AI/.env` automatically.
