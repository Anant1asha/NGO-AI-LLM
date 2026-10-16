---
name: anti-bleed
description: >-
  Audits LLM model routing, verifies that paid Gemini tokens are locked out,
  checks OpenRouter free pool availability, verifies Laya System 1 pre-routing,
  and ensures zero-token bleed across all tasks.
---

# /anti-bleed: LLM Routing & Cost Circuit Breaker Audit

Ensures 100% adherence to the Zero-Token Bleed & Circuit Breaker Mandate.

## Golden Rules

1. `ALLOW_PAID_GEMINI_FALLBACK=false` must remain locked at all times.
2. Routine orchestration, chat, AST lookups, and chapter checks route strictly to Tier 1 free models (`meta-llama/llama-3.1-8b-instruct:free`, `nvidia/nemotron-3.5-lightning:free`).
3. Paid Gemini keys are strictly reserved for explicit PDF vision ingestion and final Super Admin QA certification.
4. **Laya System 1 Pre-Routing**: Unclassified requests must be classified locally via `packages/llm-router/laya_classifier.ts` (0 token cost, sub-1ms Indic script isolation) before invoking any external provider.

## Quick Verification

```powershell
# 1. Verify environment locking
node -e "require('dotenv').config({path:'Aasha-AI/.env'}); console.log('ALLOW_PAID_GEMINI_FALLBACK:', process.env.ALLOW_PAID_GEMINI_FALLBACK)"

# 2. Test 9Router / OpenRouter Gateway Connection
npx --prefix Aasha-AI tsx Aasha-AI/packages/llm-router/openrouter_client.ts --test

# 3. Test Laya System 1 Zero-Token Pre-Router
npx --prefix Aasha-AI tsx Aasha-AI/tests/laya_router.test.ts
```
