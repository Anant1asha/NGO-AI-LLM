# 11_MODEL_CONTEXT.md
# AI Provenance, Model Context & Decision Traceability

Every AI proposal, generation step, and architectural recommendation must be traced to a specific model, version, input context, and empirical rationale.

---

### Record: MC-001 AIOS Governance Bootstrap
- **MODEL**: Gemini 3.8 Flash
- **VERSION**: gemini-3.8-flash (Antigravity Runtime)
- **AGENT**: AIOS Central Reasoning & Engineering Architecture Layer
- **DATE**: 2026-09-08
- **TASK**: Initialize Master AIOS Operating System and audit repository empirical state.
- **INPUT CONTEXT**: Workspace `c:\Users\admin\Downloads\NGO AI LLM`, user prompt specifying 48 AIOS master directives, `GEMINI.md` truth-seeking protocol, and `Aasha-AI` repository artifacts.
- **DECISION**: Gemini 3.8 Flash proposed establishing the complete 19-document `/docs/aios/` governance architecture in the root workspace because empirical inspection revealed active sub-projects (`Aasha-AI`, `Aasha-AIOS`, `Aasha-Learning-Impact-Ecosystem-v0.3-full-repo`) requiring unified cross-plane coherence between product, learning, visuals, assessment, and software engineering.
- **FILES**:
  - `docs/aios/*.md`
- **TOOLS USED**: `list_dir`, `view_file`, `run_command` (PowerShell test execution), `write_to_file`.
- **VERIFICATION**: All 16 Node.js unit and integration tests executed and verified passing prior to status classification.
- **LIMITATIONS**: Python pipeline dependencies (PyMuPDF, Pydantic) not invoked directly during this bootstrap session; reliance placed on existing repository code and test harnesses.

---

### Record: MC-002 Claude Code & OpenRouter Role Partitioning
- **MODEL**: Claude 3.5 Sonnet / Nemotron-3.5-lightning (Historical Record from Project Guidelines)
- **VERSION**: claude-3-5-sonnet-20241022 & nvidia/nemotron-3.5-lightning:free
- **AGENT**: Project Architect
- **DATE**: 2026-09-06
- **TASK**: Partition LLM responsibilities across the Aasha project to optimize accuracy and cost.
- **INPUT CONTEXT**: Freebuff CLI local compute constraints vs OpenRouter auto tier vs Claude Code reasoning benchmarks.
- **DECISION**: Claude 3.5 Sonnet proposed reserving Claude Code for complex mathematical simulations (JSXGraph, PhET), Fastify backend architecture, and TEAS engine edge-case logic, while routing batch chapter generation through OpenRouter free/auto models and local Freebuff CLI for grammar checks, based on empirical token cost ceilings (<$0.50/chapter) defined in the PRD.
- **FILES**: `Aasha-AI/PROJECT_AI_RULES.md`, `Aasha-AI/agent_orchestrator.ts`
- **VERIFICATION**: Documented in `PROJECT_AI_RULES.md`.
- **LIMITATIONS**: Free OpenRouter tiers can experience transient rate limits during bulk generation batches.
