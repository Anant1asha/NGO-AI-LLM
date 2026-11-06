---
name: aasha-agent-team
description: >-
  Procedural runbook and delegation protocols for the 5 AASHA AIOS workspace
  operational subagents (delivery-coordinator, market-researcher, growth-marketer,
  full-stack-developer, debug-test-engineer).
---

# AASHA AIOS Workspace Agent Team Management Skill

Procedural governance runbook for managing and delegating bounded tasks to the five Antigravity workspace operational subagents.

> [!IMPORTANT]
> **Advisory & Procedural Scope Only**:
> This skill is strictly procedural. Sovereign authority remains exclusively with the Super Admin AIOS and the founder. Workspace operational subagents do NOT possess sovereign governance authority, cannot promote code, and must never be added to canonical chapter pipeline registries (`Aasha-AI/agents.json`).

---

## 1. Subagent Roster & Operational Boundaries

The five operational subagents reside in `.agents/agents/` and are configured with least-privilege toolsets and `inheritMcp: false`:

| Subagent Name | Role Profile | Runtime File | Tool Permissions | Command Policy |
| :--- | :--- | :--- | :--- | :--- |
| `delivery-coordinator` | Delivery logistics & milestone tracker | `.agents/agents/delivery-coordinator.md` | Read-only | `off` |
| `market-researcher` | External curriculum & EdTech market intelligence | `.agents/agents/market-researcher.md` | Read-only + Web search | `off` |
| `growth-marketer` | Impact storytelling & teacher guide strategist | `.agents/agents/growth-marketer.md` | Read-only + Web search | `off` |
| `full-stack-developer` | Scoped code engineering & simulation engine | `.agents/agents/full-stack-developer.md` | Scoped file editing | `sandbox` |
| `debug-test-engineer` | Bug reproduction & targeted test verifier | `.agents/agents/debug-test-engineer.md` | Scoped test execution | `sandbox` |

---

## 2. Invariant Operating Laws

1. **Standby Default Invariant**:
   All five operational subagents are held in **STANDBY** mode (`subagent: true`, `mainAgent: false`). They must not execute background crawlers, autonomous loops, or external API calls without an explicit delegation brief from the Super Admin AIOS.

2. **Direct Orchestration Invariant**:
   All five subagents are spawned directly by the Super Admin AIOS / main agent. Nested subagent-to-subagent spawning is strictly prohibited. `delivery-coordinator` coordinates handoffs and recommends sequencing, but cannot spawn other subagents.

3. **Canonical Pipeline Protection**:
   The seven chapter pipeline agents (`AGT-001` through `AGT-007`) in `Aasha-AI/agents.json` remain the sole authorities for chapter compilation. Workspace operational subagents assist with outer logistics, research, and sandboxed developer tasks, but never mutate pedagogical schemas or chapter contracts.

4. **Offline & Size Invariant**:
   All student-facing bundles must remain strictly $\le 20,971,520\text{ bytes (20 MiB)}$ and operate 100% offline without remote network calls.

---

## 3. Subagent Task Delegation Protocol

When the Super Admin AIOS receives a founder goal requiring operational subagent support, use the following structured delegation contract:

```markdown
### Subagent Delegation Contract
- **Target Subagent**: [delivery-coordinator | market-researcher | growth-marketer | full-stack-developer | debug-test-engineer]
- **Task Objective**: [Clear, bounded description of outcome]
- **Source of Truth**: [Exact file paths, commits, and evidence]
- **Read / Write Scope**: [Strictly bounded file list]
- **Execution Policy**: [Sandbox or Off]
- **Deliverable**: [Concrete markdown brief, code patch, or test log]
- **Verification Gate**: [Automated command or manual check]
```

---

## 4. Discovery & Verification Commands

1. **Verify Subagent Discovery**:
   Open Antigravity's Agent Manager via `/agents` to confirm all five workspace subagents appear in the list.

2. **Verify Tooling & Security Schema**:
   Ensure all subagents maintain `inheritMcp: false` and valid tool names:
   ```bash
   node -e "const fs = require('fs'); ['delivery-coordinator', 'market-researcher', 'growth-marketer', 'full-stack-developer', 'debug-test-engineer'].forEach(a => { const c = fs.readFileSync('.agents/agents/' + a + '.md', 'utf8'); if (c.includes('inheritMcp: true')) throw new Error(a + ' has inheritMcp: true'); console.log('PASS: ' + a); });"
   ```

3. **Verify Boundary Non-Contamination**:
   Confirm zero workspace roles exist in `Aasha-AI/agents.json`:
   ```bash
   node -e "const fs = require('fs'); const aj = JSON.parse(fs.readFileSync('Aasha-AI/agents.json', 'utf8')); const extra = aj.agents.filter(a => ['delivery-coordinator', 'market-researcher', 'growth-marketer', 'full-stack-developer', 'debug-test-engineer'].includes(a.name)); if (extra.length > 0) throw new Error('Contamination detected in agents.json'); console.log('PASS: Canonical pipeline cleanly isolated (7 agents).');"
   ```
