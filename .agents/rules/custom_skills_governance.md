---
description: Governance and safe execution rules for custom skills and prompt compilers in the AASHA ecosystem.
globs: ["**/*"]
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

3. **Node.js 24 Native TypeScript Execution Invariants**:
   - When writing or invoking `.ts` scripts directly with `node script.ts`:
     - Relative imports between TypeScript files must explicitly include the `.ts` extension (`import { x } from './y.ts'`).
     - In ESM scope, `__dirname` must be derived via `path.dirname(fileURLToPath(import.meta.url))`.

4. **Antigravity Tool Calling Protocol**:
   - `ArtifactMetadata` is reserved strictly for artifact files written to `<appDataDir>/brain/<conversation-id>/`.
   - Never supply `ArtifactMetadata` when creating or editing project/workspace code files.

5. **AIOS Skill Authority Invariant & Command Hierarchy**:
   - $\text{KARAKA DECIDES} \longrightarrow \text{PROMPT COMPILER COMPILES} \longrightarrow \text{ROUTER ROUTES} \longrightarrow \text{AGENT EXECUTES} \longrightarrow \text{VALIDATOR VERIFIES}$
   - `karaka-compiler` is the Decision Synthesis Skill (produces sealed Decision Contracts; never compiles execution prompts).
   - `aasha-prompt-compiler` is the Prompt/Execution Specification Skill (consumes Decision Contracts and compiles prompts; never re-decides matters resolved by Kāraka).
   - The primary top-level user-facing command is `/chapter-compile`. The AIOS orchestrator autonomously composes internal skills without requiring the Super Admin to manually chain them.
   - Runtime operational state is maintained in local Native SQLite (<2ms latency), while SQLite MCP serves Super Admin inspection, diagnostics, and reporting.

