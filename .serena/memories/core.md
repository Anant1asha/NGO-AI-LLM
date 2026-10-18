# AASHA AIOS Core Architecture & Ecosystem Identity

- **Project Root**: AASHA AI Learning Ecosystem (`aasha-learning-ecosystem-root` / `NGO AI LLM`).
- **Core Identity & Purpose**: This project **DOES NOT BUILD, PRE-TRAIN, OR FINE-TUNE LARGE LANGUAGE MODELS**. It is an **Autonomous AI Agent Ecosystem (AASHA AIOS)** for K-12 interactive education, featuring:
  - **Multi-Agent Orchestration**: 7 canonical pipeline agents (`IngestAgent`, `AnalysisAgent`, `DesignAgent`, `AssessmentAgent`, `LLEAgent`, `QAAgent`, `BrowserTesterAgent` in `agents.json`).
  - **Multi-Tier Agent Memory**: Serena Local Semantic Memory (`.serena/memories/`), Mem0 dual-write episodic store (`.scratch/mem0_store.json`), SQLite Operational Knowledge Graph (`aasha_operational.db`), and AST Codebase Graph (`graphify-out/graph.json`).
  - **Deterministic Multi-Tools & Foundation Engines**: PyMuPDF extraction, LaTeX math insulator (`math_insulator.ts`), KaTeX typography inliners, procedural Web Audio synthesizer, Headless Chrome CDP browser automation (`automated_browser_verification.js`), and 20+ prebuilt simulation foundations (F01–F20 in `experience_registry/registry.json`).
  - **Curated Resources & Reusable Contracts**: Section 24 YAML Reusable Content Contracts (`content/contracts/`), bilingual Hindi dictionary databases (`aasha_dictionary_db.json`), and NCERT syllabus catalogs (`ncert_books.json`).
  - **Procedural Skills**: Capability runbooks in `.agents/skills/` (`aasha-ecosystem`, `aasha-aios-orchestrator`, `aasha-prompt-compiler`, `anti-bleed`, `chapter-compile`, `karaka-compiler`, `universal-sim-engine`).
- **LLM Consumption Model**: External models are consumed strictly as *swappable reasoning engines* via the 3-Tier Anti-Bleed LLM Router (`packages/llm-router/openrouter_client.ts`). Models are reasoning tools, NOT the system being built.
- **Default Local Memory**: Serena MCP is the designated default local memory engine (`.serena/memories/`), organizing persistent architectural rules, invariant conventions, and domain knowledge.

## Sub-domain Memories
- Architecture & Technical Stack: `mem:tech_stack`
- Local Memory Architecture: `mem:local_memory`
- Development Commands & Windows Environment: `mem:suggested_commands`
- Code Rules & Invariants: `mem:conventions`
- Task Completion & Certification Gates: `mem:task_completion`
- Memory Architecture & Discovery Model: `mem:memory_maintenance`
