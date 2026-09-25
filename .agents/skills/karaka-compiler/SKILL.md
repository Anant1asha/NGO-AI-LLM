---
name: karaka-compiler
description: >-
  Internal Pāṇinian Kāraka computational decision and prompt compiler for AASHA.
  Deconstructs complex tasks into structured Kāraka relations (Kartā, Karma, Karaṇa,
  Adhikaraṇa, Apādāna, Hetu, Sampradāna, Phala) to eliminate ambiguity, enforce
  autonomy-by-default, and gate consequential actions at defined HIL boundaries.
version: 1.0.0
layer: governance-ir
compatibility:
  runtimes: [antigravity, claude-code, nodejs]
---

# Pāṇinian Kāraka Computational Decision & Compilation Engine

## 1. What Kāraka IR Is (and Is NOT)
- **IS**: An internal epistemic representation for breaking down tasks, tracking agency, identifying tools, verifying baselines, evaluating risk, and determining whether an action is autonomous or requires HIL.
- **IS NOT**: A user-facing feature, a product architecture, a new database, or a religious doctrine.

## 2. The 8 Kāraka Roles & Decision Mapping

| Kāraka | Role | Operational Question in AASHA | Example Mapping |
|---|---|---|---|
| **Kartā** | The Independent Agent / Actor | *Who executes this step?* (AI autonomous worker vs. Human gatekeeper) | `SUPER_ADMIN_AGENT` |
| **Karma** | The Direct Object | *What file, module, or schema is being created or modified?* | `chapters/RationalNumbers.html` |
| **Karaṇa** | The Instrument / Tool | *What tool or algorithm achieves this?* (Native script, compiler, benchmark) | `v6_compiler.ts` + `openrouter_client` |
| **Adhikaraṇa** | The Locus / Context | *Where does this live in the system architecture?* | `Aasha-AI/packages/v6-engine/` |
| **Apādāna** | The Baseline / Fixed Source | *What committed code/contract are we taking as unchanging ground truth?* | `Section 24 YAML contract` |
| **Hetu** | The Purpose / Cause | *Why are we doing this?* (Pedagogical requirement, bug fix, test gap) | NCERT Exercise 1.1 coverage |
| **Sampradāna** | The Beneficiary | *Who receives or evaluates the output?* | Rural offline student on Android phone |
| **Phala** | The Expected Outcome | *What verifiable metric proves success?* | $100/100$ L-Truth + file size $\le 20\text{MB}$ |

## 3. Normalized Compilation Pipeline

For every complex or multi-step action, compile the prompt into this structure:

```text
KARTĀ:        <Autonomous Worker | HIL Authority>
ACTION:       <Deterministic Operation | Synthesis | Verification>
KARMA:        <Target File / Artifact / Test Suite>
KARAṆA:       <Specific Compiler / Shell / Script / Model Tier>
AUTHORITY:    <Level 0 User Instruction | Level 1 Canonical File | Level 2 Tests>
EVIDENCE:     <Verified Commit / File Path / Line Numbers>
HETU:         <Pedagogical Goal or Engineering Invariant>
RISK:         <Routine / Reversible> OR <Consequential / Irreversible>
PHALA:        <Exact Test Assertion / File Size / Benchmark Score>
HIL_REQUIRED: <false (Autonomous) | true (Create HIL Decision Packet)>
```

## 4. Execution & Autonomy Gate

```
                  ┌──────────────────────┐
                  │  COMPILE KĀRAKA IR   │
                  └──────────┬───────────┘
                             │
            Is Action Routine & Reversible?
                 ┌───────────┴───────────┐
                 ▼                       ▼
               [YES]                   [NO]
     ┌───────────────────────┐ ┌───────────────────────┐
     │ EXECUTE AUTONOMOUSLY  │ │ CREATE HIL PACKET     │
     │ - Inspect, edit, test │ │ - Issue, Options,     │
     │ - Verify with Level 2 │ │   Consequences        │
     │ - Update Truth Graph  │ │ - Await Human Signoff │
     └───────────────────────┘ └───────────────────────┘
```

## 5. HIL Decision Packet Specification
When `HIL_REQUIRED = true`, present only this minimal packet to the user:
- **Issue**: Single-sentence statement of the conflict or risk.
- **Evidence**: Canonical file paths and contradictory lines.
- **Options**: Direct concrete alternatives (Option A vs. Option B).
- **Consequences**: Immediate architectural or pedagogical impact.
- **Recommendation**: Best path aligned with AASHA invariants.
- **Required Decision**: Exactly what choice the user must make.
