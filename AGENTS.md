# Annanth Aasha Learning Ecosystem — AASHA AIOS
# AGENTS.md: Unified Multi-Agent Team Rules & Architecture Governance

**Version**: 2.0.0 (Unified Operational & Pedagogical Architecture)  
**Target Environments**: Antigravity, Claude Code, AASHA Root Orchestrator, Node.js / Python Runtimes  
**Status of Custom Operational Agents**: **STANDBY (Configured — Do Not Run Yet)**

---

## 1. Ecosystem Multi-Agent Topology
The Annanth Aasha AIOS multi-agent ecosystem is partitioned into two complementary, non-conflicting operational tiers:

```
                           ┌──────────────────────────────────────────────┐
                           │          Human Super Admin / Founder         │
                           └──────────────────────┬───────────────────────┘
                                                  │
                                                  ▼
                           ┌──────────────────────────────────────────────┐
                           │      OPS-001: Chief of Staff (AIOS Lead)     │
                           └───────┬──────────────┬──────────────┬────────┘
                                   │              │              │
         ┌─────────────────────────┘              │              └──────────────────────────┐
         ▼                                        ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐                     ┌──────────────────┐
│ OPS-002: Market  │                    │ OPS-004: Full    │                     │ OPS-003:         │
│ Researcher       │                    │ Stack Developer  │                     │ Marketer         │
│ (Curriculum &    │                    │ (Architecture &  │                     │ (Storytelling &  │
│ EdTech Intel)    │                    │ Hybrid Engine)   │                     │ NGO Outreach)    │
└──────────────────┘                    └─────────┬────────┘                     └──────────────────┘
                                                  │
                                                  ▼
                                        ┌──────────────────┐
                                        │ OPS-005: Run,    │
                                        │ Debug & Test     │
                                        │ (CDP & Regress)  │
                                        └─────────┬────────┘
                                                  │ (Validates)
══════════════════════════════════════════════════╪══════════════════════════════════════════════════
                                                  ▼ (Triggers Content Pipeline)
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                 TIER 2: PEDAGOGICAL CHAPTER PIPELINE (Aasha-AI / agents.json)                   │
│                                                                                                  │
│  [AGT-001 IngestAgent]        ──▶ [AGT-002 AnalysisAgent]      ──▶ [AGT-003 DesignAgent]        │
│  (PyMuPDF / Vector Parse)         (Pāṇinian Kāraka / Bloom)         (F01-F20 Foundation Sims)    │
│                                                                                                  │
│  [AGT-004 AssessmentAgent]    ──▶ [AGT-005 LLEAgent]           ──▶ [AGT-006 QAAgent]             │
│  (3-Tier Gamified / Hints)        (Indic Glossing / Math Insul)     (200+ L-Truth Verification)  │
│                                                                                                  │
│                               ──▶ [AGT-007 BrowserTesterAgent]                                   │
│                                   (Headless Chrome CDP / 44px)                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory & File Mapping
Every custom agent has its own dedicated operational specification in `output/` and an Antigravity registry entry in `antigravity/agents/`:

| Agent ID | Agent Name | Domain / Job | Primary Spec File | Antigravity Registry |
| :--- | :--- | :--- | :--- | :--- |
| **OPS-001** | `chief_of_staff` | AIOS Executive Coordination & Governance | `output/chief_of_staff.md` | `antigravity/agents/manifest.json` |
| **OPS-002** | `market_researcher` | K-12 Curriculum & Competitor Intelligence | `output/market_researcher.md` | `antigravity/agents/manifest.json` |
| **OPS-003** | `marketer` | Impact Storytelling & NGO Partner Growth | `output/marketer.md` | `antigravity/agents/manifest.json` |
| **OPS-004** | `full_stack_developer` | Unified Hybrid Architecture & Simulation Engine | `output/full_stack_developer.md` | `antigravity/agents/manifest.json` |
| **OPS-005** | `run_debug_test` | CDP Automation, Debugging & QA Defense | `output/run_debug_test.md` | `antigravity/agents/manifest.json` |
| **AGT-001..007** | *Pipeline Agents* | Ingest, Analysis, Design, Assessment, LLE, QA, CDP | `Aasha-AI/agents.json` | `Aasha-AI/Aasha-AIOS/AGENTS.md` |

---

## 3. Unified Team Rules (The 7 Invariant Operating Laws)

### Rule 1: Standby Default (Do Not Run Yet)
All custom operational agents (`OPS-001` through `OPS-005`) are currently in **STANDBY** mode. They must not execute autonomous mutation loops, background crawlers, or external API calls until explicitly activated by the Human Super Admin.

### Rule 2: Evidence Over Confidence (Truth-Seeking Protocol)
Every recommendation, finding, or test claim must be anchored in empirical evidence:
- Never speculate about test results—always cite exact command output and exit codes.
- Responses must conform to the standard structure: **Answer**, **Confidence (0.0–1.0)**, and **Caveats**.
- Confidence $< 0.8$ mandates explicit disclosure of gaps or clarifying questions.

### Rule 3: Zero Interference & Non-Conflicting Authority
- **Operational agents do not mutate pedagogical contracts**: `market_researcher`, `marketer`, and `full_stack_developer` do not invent or rewrite textbook question keys or hint schemas. That is the exclusive authority of `AssessmentAgent`.
- **Pipeline agents do not alter platform architecture**: `IngestAgent` through `QAAgent` consume and produce standardized JSON/HTML artifacts; they never touch root build scripts, marketing materials, or repo configs.
- **`chief_of_staff` arbitrates collisions**: If sprint velocity conflicts with the 20MB offline ceiling, the ceiling always wins.

### Rule 4: Scope-Locked 20MB & Offline Integrity Invariant
- Every child-facing HTML5 bundle produced must remain **strictly $\le 20,971,520\text{ bytes (20 MiB)}$** (typically $< 300\text{KB}$).
- Absolutely zero external network calls, remote CDN script tags, external fonts, or live web tracking are permitted inside student learning files.
- All styles, KaTeX fonts (WOFF2 data URIs), and audio synthesis (Web Audio API) must be inlined.

### Rule 5: Same-Frame Mobile Ergonomics & Viewport Clamping
- Touch targets must strictly measure **$\ge 44 \times 44\text{px}$** for all buttons, sliders, and interactive tabs.
- The interactive simulation and pedagogical concept text must render simultaneously in the exact same viewport frame across 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915) mobile viewports without vertical collision or horizontal scrolling.

### Rule 6: Anti-Spoiler Pedagogical Rule #1
- Misconception explanation feedback (the `m` attribute) for wrong answer choices must **never reveal, imply, or leak the correct answer**.
- Scaffolding must progress through the 4-tier model: $H_1$ (Hook) $\to$ $H_2$ (Visual Anchor) $\to$ $H_3$ (Elimination Strategy) $\to$ $H_4$ (Procedural Step).

### Rule 7: Zero-Secret Staging & Public Repo Hygiene
- All ecosystem repositories are treated as 100% public.
- Never stage or commit API keys (`sk-`, `ghp_`, `AIzaSy`), passwords, cookies, `.env` files, or student PII.
- All mock secrets in test fixtures must use string concatenation (`'sk-' + 'dummy'`) to avoid false-positive static scanner alarms.

---

## 4. Inter-Agent Communication & Execution Workflow
When operational agents are transitioned from Standby to Active:

1. **Strategic Intent**: Founder issues goals $\to$ `chief_of_staff` synthesizes sprint tasks in `startup.md`.
2. **Context & Positioning**:
   - `market_researcher` drafts curriculum targets and competitor intelligence.
   - `marketer` drafts value proposition and NGO teacher onboarding materials.
3. **Engineering Implementation**:
   - `full_stack_developer` writes code, components, or simulation engines.
4. **Verification & Hardening**:
   - `run_debug_test` runs automated headless Chrome CDP and E2E suites.
   - Issues PASS / FAIL certification before any release promotion.
5. **Human Gate 6**: Super Admin reviews telemetry and authorizes final release.

---

## 5. Workspace Delivery Subagents (`.agents/agents/`) & Boundary Isolation

Five workspace-level specialist subagents are registered in `.agents/agents/` to support delivery logistics, external intelligence, and sandboxed implementation without expanding sovereign authority or mutating canonical chapter pipelines:

| Subagent File | Role / Domain | Runtime Boundaries | Allowed Actions | Strictly Prohibited Actions |
| :--- | :--- | :--- | :--- | :--- |
| `.agents/agents/delivery-coordinator.md` | Chief-of-Staff-equivalent delivery logistics | Read-only tools (`view_file`, `grep_search`, `find_by_name`, `code_search`, `send_message`) | Cross-repo milestone mapping, dependency sequencing, risk tracking, delivery status reporting | Spawning subagents autonomously, modifying code, approving PRs, executing builds/tests, policy decisions |
| `.agents/agents/market-researcher.md` | Sourced external education market & EdTech intel | Read-only + web (`search_web`, `read_url_content`, `view_file`, `send_message`) | External curriculum demand analysis, competitor benchmarking, NGO grant discovery | Internal codebase research (reserved for built-in `research`), publishing, mutating repo files |
| `.agents/agents/growth-marketer.md` | Impact storytelling, teacher guides & adoption | Read-only + web (`search_web`, `read_url_content`, `view_file`, `send_message`) | Value proposition drafting, teacher onboarding guides, NGO partner outreach concepts | Live posting, sending external communications, ad spending, production code edits |
| `.agents/agents/full-stack-developer.md` | Scoped engineering, `<aasha-sim>`, offline bundles | Sandboxed tools (`view_file`, `grep_search`, `find_by_name`, `code_search`, `replace_file_content`, `run_command`, `send_message`) | Scoped component edits in task worktrees, `<aasha-sim>` wrapping, targeted unit runs upon explicit dispatch | Autonomous task execution without task brief, modifying sovereign governance/rules, promoting code |
| `.agents/agents/debug-test-engineer.md` | Failure reproduction, log diagnosis, targeted tests | Sandboxed tools (`view_file`, `grep_search`, `find_by_name`, `code_search`, `replace_file_content`, `run_command`, `send_message`) | Failure reproduction, log diagnosis, running targeted suites on failing paths, fix verification | Final QA certification (reserved for canonical `QAAgent`), HIL sign-off, unsandboxed commands |

### Strict Non-Contamination & Standby Invariants
1. **Zero Contamination of `agents.json`**: These workspace subagents must NEVER be registered in `Aasha-AI/agents.json` or `agent_orchestrator.ts`. The seven canonical chapter pipeline agents (`AGT-001` through `AGT-007`) remain sole authorities for chapter compilation.
2. **Least Privilege (`inheritMcp: false`)**: All five workspace subagents operate with `inheritMcp: false`, preventing unconstrained database or external tool execution without explicit task scoping.
3. **Standby Default Invariant**: All five subagents remain in **STANDBY** mode (definitions exist on disk, discoverable via `/agents`, but not invoked / no task dispatched).
4. **Direct Orchestration Only**: All five subagents are spawned and coordinated directly by the Super Admin AIOS / main agent. Nested subagent-to-subagent spawning is strictly prohibited.

---

## 6. Current MVP Planning Authority Register

Product and engineering scope are anchored in the living constitutional planning artifacts:
- **Companion Startup Specification**: [`agent-startup-spec.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/agent-startup-spec.md)
- **Unified MVP Plan Index**: [`output/UNIFIED_MVP_PLAN.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/output/UNIFIED_MVP_PLAN.md)
- **Agent Registry & Responsibility Boundaries**: [`output/AGENT_REGISTRY_AND_BOUNDARIES.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/output/AGENT_REGISTRY_AND_BOUNDARIES.md)
- **Package Manifest & Integrity Hashes**: [`BUNDLE_MANIFEST.json`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/BUNDLE_MANIFEST.json)
- **Installation & Boundary Guide**: [`INSTALLATION.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/INSTALLATION.md)

