# Installation Guide — AASHA Antigravity Agent Team

## Target workspace

The repository snapshot `PC_ANTIGRAVITY_STATE.json` records the Windows workspace as:

`C:\Users\admin\Downloads\NGO AI LLM`

This is a dated snapshot, not a live local path check. Confirm the actual active Antigravity workspace before copying.

## Install (workspace-scoped, not machine-global)

1. Extract this bundle.
2. Copy the bundle's **contents** into the actual workspace root (`NGO AI LLM`), preserving directory structure.
3. The expected result is:
   - `AGENTS.md`
   - `.agents/agents/delivery-coordinator.md`
   - `.agents/agents/market-researcher.md`
   - `.agents/agents/growth-marketer.md`
   - `.agents/agents/full-stack-developer.md`
   - `.agents/agents/debug-test-engineer.md`
   - `output/agent-team/` review copies
   - `output/UNIFIED_MVP_PLAN.md`
4. Before replacing any file, compare with existing local files. This package is designed to add a root `AGENTS.md` and `.agents/agents/` files; do not replace `GEMINI.md`, `.agents/rules/`, Super Admin documents, or pipeline registry files.
5. Reopen Antigravity's Agent Manager using `/agents`. Confirm the five workspace agents appear under available agents.

Official Antigravity discovery locations:
- Workspace: `.agents/agents/<name>.md` or `.agents/agents/<name>/agent.md`.
- Global: `~/.gemini/config/agents/` (not used by this package).

## Do not run yet

The five agent files have `subagent: true` and `mainAgent: false`. They are definitions only. Do not invoke them as part of installation. Agent execution should begin only after the founder/primary AIOS explicitly delegates a task.

## Preserve the current system

Do not:
- Add these roles to Aasha-AI `agents.json` or `agent_orchestrator.ts`.
- Replace the canonical Super Admin / AIOS or seven pipeline agents.
- Copy these definitions into `Aasha-AI/aasha-pipeline-with-master-json/output/` (that directory is for chapter/build artifacts).
- Sync, reset, merge, or push local/remote repositories merely to install this pack.
- Run builds or tests as part of this installation.

## Verification after manual installation

Without invoking agents, check only:
- Files landed at the exact expected paths.
- Each agent starts with YAML frontmatter containing a unique `name`, description, and valid tool names.
- `/agents` discovers the five roles.

The agent definitions are configured for Antigravity subagent delegation. They are not automatically registered in AASHA's chapter pipeline.
