# CANONICAL_CONTRACT_REGISTER.md
# AASHA AIOS Canonical Contract & Authority Register
**Authority**: Annanth Aasha Super Admin Governance  
**Version**: 2.0.0  
**Effective Date**: 2026-10-09  

---

## 1. Governance Authority Hierarchy

In any conflict between architectural artifacts, the following strict hierarchy of authority governs:

$$\text{SUPER ADMIN} > \text{CANONICAL GOVERNANCE DOCS} > \text{TLN/TEAS/HIL CONTRACTS} > \text{CURRENT REPOSITORY SOURCE} > \text{APPROVED SCHEMAS} > \text{VERIFIED TEST HARNESSES} > \text{MODEL/AGENT SUGGESTIONS} > \text{TOOL OUTPUT}$$

No AI agent, LLM prompt, n8n workflow, or external tool may modify governance authority or grant itself elevated permissions.

---

## 2. Canonical Contracts Inventory

| Contract ID | Contract Name | Type | Canonical File Location | Owner / Authority | Enforcement Mechanism | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CON-001** | Super Admin Sovereignty | POLICY | `Aasha-AI/Aasha-AIOS/SUPER_ADMIN_AIOS_V2.md` | Super Admin Board | Antigravity AIOS Control Plane | **CANONICAL ACTIVE** |
| **CON-002** | Multi-Agent Taxonomy & Boundaries | INTERFACE | `Aasha-AI/Aasha-AIOS/AGENTS.md` | Systems Architect | `ContextBus.validateOutput()` | **CANONICAL ACTIVE** |
| **CON-003** | Learning & Pedagogical Contract | INTERFACE | `docs/aios/13_LEARNING_CONTRACT.md` | Pedagogy Lead | `QuestionSchemaValidator` | **CANONICAL ACTIVE** |
| **CON-004** | Socratic Assessment & Anti-Spoiler | POLICY / SCHEMA | `docs/aios/14_ASSESSMENT_CONTRACT.md` | Assessment Lead | `qa_ltruth_benchmark.js` | **CANONICAL ACTIVE** |
| **CON-005** | Visual Experience Contract | INTERFACE | `docs/aios/15_VISUAL_CONTRACT.md` | Experience Lead | `<aasha-sim>` Web Component Contract | **CANONICAL ACTIVE** |
| **CON-006** | Agent Capability & Bounds | INTERFACE | `docs/aios/16_AGENT_CONTRACT.md` | Multi-Agent Lead | `agent_orchestrator.ts` Gatekeeper | **CANONICAL ACTIVE** |
| **CON-007** | Zero-Leakage Privacy & Public Repo | POLICY | `GEMINI.md` | Security QA Lead | Pre-commit Scrubbing & Test Suite | **CANONICAL ACTIVE** |
| **CON-008** | Anti-Bleed 3-Tier API Routing | OPERATIONAL | `Aasha-AI/ROUTER_GUIDE.md` & `openrouter_client.ts` | DevOps / Finance | Circuit Breaker `ALLOW_PAID_GEMINI_FALLBACK=false` | **CANONICAL ACTIVE** |
| **CON-009** | Standalone Single-File Ceiling (20MB) | INTERFACE | `docs/aios/02_DECISIONS.md` (DEC-001) | Delivery Lead | `e2e_all_chapters_suite.js` | **CANONICAL ACTIVE** |
| **CON-010** | TEAS Mastery Decoupling | SCHEMA / IMPL | `docs/aios/02_DECISIONS.md` (DEC-002) | Impact Lead | Native SQLite / `v6_runtime_bus.ts` | **CANONICAL ACTIVE** |
| **CON-011** | Canonical IR Schema | SCHEMA | `packages/canonical-ir/canonical_ir_schema.ts` | Architecture Lead | TypeScript Type Checking & Zod | **CANONICAL ACTIVE** |
| **CON-012** | Foundation Registry Protocol | INTERFACE | `experience_registry/registry.json` | Resource Curator | `three_tier_matcher.ts` & Registry Bench | **CANONICAL ACTIVE** |

---

## 3. Discrepancy & Conflict Resolution Protocol

1. **Conflict Rule**: If an agent discovers a conflict between `Aasha-AIOS/AGENTS.md`, `SUPER_ADMIN_AIOS_V2.md`, and any implementation file:
   - The agent MUST immediately halt implementation.
   - Record the conflicting claims, file paths, and lines in `UNRESOLVED_CONFLICTS.md`.
   - Mark the affected task as `BLOCKED`.
   - Escalate to the Super Admin via the Human Approval Gate.
2. **Immutability Invariant**: Approved Topic Learning Nodes (TLNs) and certification evidence hashes are strictly immutable. Updates require publishing a new version; in-place mutation of approved artifacts is forbidden.
