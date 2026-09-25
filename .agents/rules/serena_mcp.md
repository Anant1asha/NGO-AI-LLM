# Serena MCP Parameter & Memory Invariants

This rule defines the exact tool parameter schemas and memory onboarding standards for Serena MCP server interactions in this workspace.

## 1. Tool Parameter Schemas
- `activate_project`: `{ "project": "<absolute_path>" }` (Key is `project`, NOT `project_path`).
- `list_dir`: `{ "relative_path": "<path>", "recursive": false }` (`recursive` boolean is mandatory).
- `read_memory`: `{ "memory_name": "<name>" }` (Key is `memory_name`).
- `write_memory`: `{ "memory_name": "<name>", "content": "<markdown>" }` (`memory_name` and `content` mandatory).
- `initial_instructions`: `{}` (Reads initial instruction manual).
- `onboarding`: `{}` (Triggers memory layout setup).

## 2. Mandatory Memory Architecture
Every active project must maintain the following 6 core memories in `.serena/`:
1. `mem:core` — Root domain map and top-level references.
2. `mem:tech_stack` — Runtimes, compilers, frameworks, LLM anti-bleed tiers.
3. `mem:suggested_commands` — CLI build, test, and graphify commands.
4. `mem:conventions` — Invariants (bilingual insulation, zero-spoiler hints, responsive layout).
5. `mem:task_completion` — Dual-benchmark certification gates (L-Truth + CDP audit).
6. `mem:memory_maintenance` — Memory discovery graph standards.

## 3. Editing Guidelines
- Errs on the side of symbolic tools (`find_symbol`, `get_symbols_overview`, `replace_symbol_body`, `rename_symbol`, `safe_delete_symbol`).
- ERR on batching independent tool calls within single turns to minimize token cost.
