# Serena Default Local Memory System

- **Primary Role**: Serena MCP is the default local memory system for the AASHA AI Learning Ecosystem (`NGO AI LLM`).
- **Storage Location**: `.serena/memories/` (persisted as durable Markdown files in the workspace repository).
- **Core Memory Graph**:
  - `mem:core` — Root domain map and top-level ecosystem references.
  - `mem:tech_stack` — Runtimes, compilers, frameworks, LLM anti-bleed tiers, and memory engines.
  - `mem:suggested_commands` — CLI build, test, chapter-init, and graphify commands.
  - `mem:conventions` — Invariants (bilingual insulation, zero-spoiler hints, responsive layout).
  - `mem:task_completion` — Dual-benchmark certification gates (L-Truth + CDP audit).
  - `mem:memory_maintenance` — Memory discovery graph standards and reference conventions.
  - `mem:local_memory` — Local memory tiering, precedence, and retrieval protocol.
- **Memory Tiering & Precedence**:
  1. **Serena Local Memories (`.serena/memories/`)**: Default authoritative store for project invariants, architectural decisions, and agent conventions.
  2. **Graphify AST (`graphify-out/graph.json`)**: Code symbol relationships, call graphs, and structural dependencies.
  3. **Local Offline Stores (`.scratch/mem0_store.json`, `aasha_operational.db`)**: Episodic learner preferences and operational SQLite tables.
- **Zero-Token Bleed Integration**: All memory operations are 100% local with zero remote API calls. Agents must query Serena memories first before making external calls.
