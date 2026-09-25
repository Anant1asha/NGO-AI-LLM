---
name: workflow-skill-creator
description: >-
  Distills a completed user workflow or interaction into a reusable agent
  skill. Use when the user asks to turn their workflow, interaction, or
  multi-step process into a skill, or when they say "make this a skill",
  "create a skill from what we just did", "package this workflow" or similar.
---

# Workflow-to-Skill Distiller

Turns an existing completed workflow into a reusable agent skill.

## Workflow

1. **Understand Workflow**: Review conversation history and extract steps, inputs, outputs, and edge cases.
2. **Classify**: Determine if it should be an instruction-only rule/skill or a CLI script.
3. **Draft SKILL.md**: Follow the standard Antigravity YAML frontmatter and markdown sections.
4. **Place in Project**: Save to `.agents/skills/<skill-name>/SKILL.md`.
