---
name: hachi-agent-governance
description: >-
  Guides the use of the Hachi ObjectGraph (.og) engine, 3-pass token-efficient skill retrieval
  (97.6% token savings), isolated sub-agent delegation with write-target locks, and mechanical 8-layer guardrails.
  Use when delegating complex subtasks, converting SKILL.md to .og, or invoking Hachi MCP tools.
---

# Hachi Agent Governance & ObjectGraph Skill

## Overview
Hachi provides deterministic, code-enforced multi-agent delegation, token budgeting, and surgical skill retrieval via ObjectGraph (`.og`). It is integrated into `packages/hachi` with an isolated virtual environment and exposed through the native MCP server and the Node.js bridge (`scripts/hachi_bridge.mjs`).

---

## 1. The 3-Pass ObjectGraph Retrieval Protocol (97.6% Token Savings)
Instead of dumping full skill manuals and prompt instructions into the model's context window, agents MUST follow the 3-pass retrieval model:

```
Pass 1: Search (~tens of tokens) ──► Pass 2: Peek (~30 tokens) ──► Pass 3: Load (Targeted Blocks)
```

1. **Pass 1 — Search**:
   - Query candidate skills by keyword or intent using `hachi_search_skills(query="...")` or `node scripts/hachi_bridge.mjs search "<query>"`.
   - Returns a lightweight ranked list of matching skill names, roles, and keywords.
2. **Pass 2 — Peek**:
   - Inspect the candidate skill using `hachi_peek_skill(names=["<skill_name>"])` or `node scripts/hachi_bridge.mjs peek <skill_name>`.
   - Returns the ultra-dense summary (~30 tokens), any active warnings, and a token cost manifest for heavy blocks.
3. **Pass 3 — Load**:
   - If (and only if) the dense summary confirms relevance, load the exact required blocks using `hachi_load_skill(name="<skill_name>", blocks=["steps", "assertions"])`.
   - Avoid loading unnecessary full prose when only `steps` or `code` are needed.

---

## 2. Isolated Sub-Agent Delegation Protocol
When an orchestrator task requires multiple tool calls across different domains or noisy trial-and-error operations, delegate to a specialized worker:

### Available Blueprints (`hachi_list_roles` / `npm run hachi -- roles`):
- `coder`: Production code synthesis, debugging, bisection testing, zero unnecessary cat/dir calls.
- `researcher`: Web, Drive, documentation research.
- `analyst`: Data parsing, CSV, JSON, sheet analysis.
- `devops`: Infrastructure, git, packaging, deployment.
- `emailer`: Communication drafting and inbox workflows.

### Delegation Invariants:
1. **Declare Write Targets**:
   - Always declare `write_targets` prefixes (e.g. `['Aasha-AI/content', 'packages/']`) to prevent parallel subagents from conflicting on filesystem writes.
2. **Context Isolation**:
   - Subagents execute in isolated context windows. Intermediate logs and trial-and-error reasoning do NOT pollute the orchestrator's context.
3. **Restricted Capabilities**:
   - Subagents are strictly stripped of `delegate_task` (no runaway recursive spawning).
   - Subagents are blocked from modifying long-term memory.
4. **Structured Handoff**:
   - Subagents must return an immutable structured report in **under 200 words** containing:
     1. Actions taken.
     2. Files touched.
     3. Verification result.
     4. Unresolved issues (if any).

---

## 3. SKILL.md to ObjectGraph Bridge
Convert existing or newly created markdown skills into `.og` using:
`hachi_import_skill_md(markdown_content=...)`

This automatically:
1. Extracts frontmatter into `::meta` declarations.
2. Compresses the body into an indexable `::dense` summary.
3. Extracts numbered steps into a machine-executable `::steps` block.
4. Generates an executable `::assertion` block for precondition validation.

---

## 4. Mechanical 8-Layer Guardrails
Follow the principle: *"Stop writing rules. Start enforcing them with the computer."*

| Layer | Name | Mechanism |
| :--- | :--- | :--- |
| **Layer 1** | **The Gate** | One command that gates everything: `npm run lint:superbrain && npm run lint:secrets && npm run test:master`. |
| **Layer 2** | **The Locks** | Pre/post-tool hooks blocking dangerous moves (e.g. unapproved push to main). |
| **Layer 3** | **The Rails** | Typed signatures and `import-linter` boundary contracts. |
| **Layer 4** | **The Net** | The Regression Law: every fixed bug must have a failing regression test committed first. |
| **Layer 5** | **The Plan** | Plan before code; never guess. |
| **Layer 6** | **Hygiene** | Lean context, fresh subagents for independent tasks. |
| **Layer 7** | **The Map** | Living architecture documentation as source of truth. |
| **Layer 8** | **Memory** | Autopsy logging to prevent ever encountering the same bug twice. |

---

## 5. Developer CLI & Orchestration Cheatsheet

```bash
# Diagnostics & health check
npm run hachi -- doctor

# Inspect all specialized worker roles
npm run hachi -- roles

# Search skills with BM25 ranking
npm run hachi -- search "coder"

# Peek dense summary (~30 tokens)
npm run hachi -- peek coder:execution-protocol

# Load specific steps and assertions
npm run hachi -- load coder:execution-protocol
```
