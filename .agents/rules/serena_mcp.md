# Serena MCP Parameter & Memory Invariants

This rule defines the exact tool parameter schemas and memory onboarding standards for Serena MCP server interactions in this workspace.

## 0. Default Local Memory Mandate
**Serena MCP is the primary default local memory system** for this workspace (`NGO AI LLM`).
1. **Always Active**: On every session or task start, ensure the `NGO AI LLM` project is active (`activate_project: { "project": "NGO AI LLM" }`).
2. **First-Lookup Protocol**: Before initiating external queries or large prompt builds, agents and subagents must consult Serena memories (`read_memory`) for architectural rules, conventions, and constraints.
3. **Zero Token Bleed**: Serena memories are stored locally in `.serena/memories/` as zero-cost Markdown artifacts, eliminating external cloud dependency.

## 1. Tool Parameter Schemas
- `activate_project`: `{ "project": "<absolute_path_or_registered_name>" }` (Key is `project`, NOT `project_path`).
- `list_dir`: `{ "relative_path": "<path>", "recursive": false }` (`recursive` boolean is mandatory).
- `read_memory`: `{ "memory_name": "<name>" }` (Key is `memory_name`).
- `write_memory`: `{ "memory_name": "<name>", "content": "<markdown>" }` (`memory_name` and `content` mandatory).
- `edit_memory`: `{ "memory_name": "<name>", "needle": "<text_to_replace>", "replacement": "<new_text>" }`
- `initial_instructions`: `{}` (Reads initial instruction manual).
- `onboarding`: `{}` (Triggers memory layout setup).

## 2. Mandatory Memory Architecture
Every active project must maintain the following core memories in `.serena/memories/`:
1. `mem:core` — Root domain map and top-level references.
2. `mem:local_memory` — Local memory architecture, precedence, and retrieval hierarchy.
3. `mem:tech_stack` — Runtimes, compilers, frameworks, LLM anti-bleed tiers.
4. `mem:suggested_commands` — CLI build, test, and graphify commands.
5. `mem:conventions` — Invariants (bilingual insulation, zero-spoiler hints, responsive layout).
6. `mem:task_completion` — Dual-benchmark certification gates (L-Truth + CDP audit).
7. `mem:memory_maintenance` — Memory discovery graph standards.

## 3. Memory Precedence Hierarchy
1. **Serena Local Memory (`.serena/memories/`)**: Authoritative repository truth for project architecture, rules, and guidelines.
2. **Graphify AST Knowledge Graph (`graphify-out/graph.json`)**: Codebase symbol definitions, references, and structural AST relations.
3. **Local Episodic Stores (`.scratch/mem0_store.json`, `aasha_operational.db`)**: Zero-cost offline episodic logs and operational state.

## 4. Editing Guidelines
- Errs on the side of symbolic tools (`find_symbol`, `get_symbols_overview`, `replace_symbol_body`, `rename_symbol`, `safe_delete_symbol`).
- ERR on batching independent tool calls within single turns to minimize token cost.

## 5. Autonomous Auto-Activation & Self-Healing (`/jagiye-maakiran` Invariant)
1. **Self-Healing Guard**: If any Serena MCP tool call ever returns `No active project`, the agent MUST NOT fail, hallucinate, or ask the user for manual guidance. The agent MUST autonomously invoke `activate_project: { "project": "NGO AI LLM" }` and immediately retry the memory or symbol operation in the same turn.
2. **Master Wake-up Intent (`/jagiye-maakiran`)**: Trigger `/jagiye-maakiran` (or phrase `jagiye maakiran`, `जागिए माँ किरण`) at any time to awaken and prime the full ecosystem, verify 7/7 core memories, check the 8,000+ node Graphify AST, and inspect offline dual-plane state.
3. **Engine-Level Auto-Fallback**: Serena's CLI startup (`cli.py`) has been patched to fall back to the registered default project (`NGO AI LLM` in `serena_config.yml`) whenever `--project-from-cwd` does not detect a project root, guaranteeing autonomous initialization on launch.


