---
description: Governance and safe execution rules for custom skills and prompt compilers in the AASHA ecosystem.
globs: **/*
alwaysApply: true
---

# Custom Skills Governance: Read & Evaluate First, Never Auto-Mutate

This rule governs all interactions involving custom skills, prompt compilers, and orchestration plugins within this project.

## Golden Rules

1. **Skill != System**:
   - Custom skills (such as `aasha-prompt-compiler`, `assessment-authoring`, or others) are localized advisory capabilities tailored specifically to this project, NOT the entire application system.
   - A skill must introduce **zero unprompted changes** to the existing repository build plan, core runtime, or architecture.

2. **Zero Autonomous File Mutations**:
   - Merely having, discovering, or activating a custom skill gives **zero authority** to modify or mutate codebase files, existing chapters, or runtime systems.
   - Any agent operating in this workspace must strictly follow the mandatory 4-step workflow:
     1. **Step 1 (Read)**: Inspect source files, existing contracts, and textbook context first.
     2. **Step 2 (Evaluate)**: Perform formal semantic decomposition (Pāṇinian Kāraka IR), evidence classification, and delta computation without modifying target files.
     3. **Step 3 (Propose)**: Emit an isolated developer proposal (`.proposal.md`) and a non-technical Hindi teacher summary (`शिक्षक के लिए सारांश`).
     4. **Step 4 (Await Explicit Approval)**: Never apply code changes until the proposal has been explicitly reviewed and approved by the user.

3. **Node.js 24 Native Execution & Companion Script Invariants**:
   - When writing or invoking `.ts` scripts directly with `node script.ts`:
     - Relative imports between TypeScript files must explicitly include the `.ts` extension (`import { x } from './y.ts'`).
     - In ESM scope, `__dirname` must be derived via `path.dirname(fileURLToPath(import.meta.url))`.
   - **Pure JavaScript ESM Constraint for `*.mjs` Companion Scripts**:
     - Scripts authored with the `.mjs` extension (e.g., `scripts/*.mjs`) and executed directly via `node script.mjs` must remain 100% pure standard ECMAScript JavaScript.
     - TypeScript syntax (such as `interface`, `type` aliases, enum declarations, or type annotations like `(err: any)`) is strictly prohibited in `.mjs` files to prevent Node.js runtime `SyntaxError` crashes.
     - Use standard JSDoc comments (`/** @type {...} */`) for typing in `.mjs`, or author the file as `.ts` executed via `tsx`.

4. **Antigravity Tool Calling Protocol**:
   - `ArtifactMetadata` is reserved strictly for artifact files written to `<appDataDir>/brain/<conversation-id>/`.
   - Never supply `ArtifactMetadata` when creating or editing project/workspace code files.

5. **AIOS Skill Authority Invariant & Command Hierarchy**:
   - $\text{KARAKA DECIDES} \longrightarrow \text{PROMPT COMPILER COMPILES} \longrightarrow \text{ROUTER ROUTES} \longrightarrow \text{AGENT EXECUTES} \longrightarrow \text{VALIDATOR VERIFIES}$
   - `karaka-compiler` is the Decision Synthesis Skill (produces sealed Decision Contracts; never compiles execution prompts).
   - `aasha-prompt-compiler` is the Prompt/Execution Specification Skill (consumes Decision Contracts and compiles prompts; never re-decides matters resolved by Kāraka).
   - The primary top-level user-facing command is `/chapter-compile`. The AIOS orchestrator autonomously composes internal skills without requiring the Super Admin to manually chain them.
   - Runtime operational state is maintained in local Native SQLite (<2ms latency), while SQLite MCP serves Super Admin inspection, diagnostics, and reporting.

6. **Cross-IDE Rule Parity & Modern Skill Standard**:
   - Every rule in `.agents/rules/<snake_case>.md` must maintain an identical 1:1 counterpart in `.superbrain/rules/<kebab-case>.md`.
   - All rule files in `.agents/rules/*.md` must include valid YAML frontmatter specifying `trigger: always_on` (or `trigger: model_decision`), `description: ...`, and scalar string `globs: "**/*"`. NEVER use YAML sequence arrays (`globs: [...]`), as Antigravity's Go language server (`language_server.exe`) unmarshals frontmatter into `struct { Globs string }` and fails with `cannot unmarshal !!seq into string`.
   - **Automated Rule Validation Task**: When creating or modifying rules in the future, you MUST automatically run `npm run lint:superbrain` to ensure no accidental YAML list syntax (`!!seq`) is introduced and 100% schema compliance is verified before concluding the turn or staging files.
   - Legacy workflow files (`.agents/workflows/*.md`) are deprecated; all reusable agent capabilities must reside exclusively in `.agents/skills/<name>/SKILL.md`.
   - Rule parity must be validated via `npm run lint:superbrain` prior to staging changes.
