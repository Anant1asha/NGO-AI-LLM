---
name: anti-bleed
description: >-
  Audits LLM model routing, verifies that paid Gemini tokens are locked out,
  checks OpenRouter free pool availability, and ensures zero-token bleed across
  all tasks.
---

# /anti-bleed: LLM Routing & Cost Circuit Breaker Audit

Ensures 100% adherence to the Zero-Token Bleed & Circuit Breaker Mandate.

## Golden Rules

1. `ALLOW_PAID_GEMINI_FALLBACK=false` must remain locked at all times.
2. Routine orchestration, chat, AST lookups, and chapter checks route strictly to Tier 1 free models (`meta-llama/llama-3.1-8b-instruct:free`, `nvidia/nemotron-3.5-lightning:free`).
3. Paid Gemini keys are strictly reserved for explicit PDF vision ingestion and final Super Admin QA certification.

## Quick Verification

```powershell
# 1. Verify environment locking
node -e "require('dotenv').config({path:'Aasha-AI/.env'}); console.log('ALLOW_PAID_GEMINI_FALLBACK:', process.env.ALLOW_PAID_GEMINI_FALLBACK)"

# 2. Test OpenRouter Free Tier Connection
node Aasha-AI/packages/llm-router/openrouter_client.ts --test
```
