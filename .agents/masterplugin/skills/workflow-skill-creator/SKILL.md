---
name: workflow-skill-creator
description: >-
  Distills a completed user workflow or interaction into a reusable agent
  skill. Use when the user asks to turn their workflow, interaction, or
  multi-step process into a skill, or when they say "make this a skill",
  "create a skill from what we just did", "package this workflow" or similar.
  Do not use for creating skills from scratch without an existing workflow.
---

# Workflow-to-Skill Distiller

Turns an existing completed workflow into a reusable agent skill. Specifically, this skill extracts patterns from an interaction or workflow that **already happened** and packages them.

> [!CAUTION]
> **You MUST complete Phase 1 (Brainstorming) before writing any code or SKILL.md content.** Skipping brainstorming produces skills that are either too rigid or too vague. The brainstorming conversation is the most important part of this process.

---

## Phase 1: Brainstorming (MANDATORY)

Have an **iterative back-and-forth conversation** with the user. Do NOT ask all questions at once. Pick 2-3 relevant questions per round, refine your understanding, and ask follow-ups.

### Round 1: Understand the Workflow

Start by summarizing what you observed from the workflow, then ask:

1. "Here's my understanding of the workflow: [summary]. Is this accurate? What would you change?"
2. "What are the expected inputs and outputs for this workflow?"
3. "How often do you expect to run this workflow? Is it recurring or one-off?"

### Round 2: Flexibility and Error Handling

For each step identified in the workflow, determine its rigidity:

1. "For [step X], if the primary approach fails (e.g., API down, no results), should the agent: (a) ask you for guidance, (b) try alternative approaches automatically, or (c) fail loudly with an error?"
2. "Are there any steps where the exact method matters vs. steps where any reasonable approach is fine?"
3. "Should the skill handle edge cases silently or surface them to the user?"

### Round 3: Dependencies and Resources

Before asking these questions, check which of your installed skills overlap with the workflow.

1. "I noticed the workflow uses functionality covered by [existing skill X, skill Y]. The new skill will reference these rather than reimplementing them. Are there any other tools or skills you'd like me to incorporate?"
2. "Are there any API rate limits or authentication tokens I should be aware of?"
3. "Are there specific reference files that provide important context for this skill?"

### Round 4: Scope and Shape

1. "Our workflow covered [X, Y, Z]. Should I distill all of these into the skill, or is there additional functionality that's important to include?"
2. Determine whether the skill needs any code:
   - If any step involves calling an API, processing data, reading/writing files, or computing results, the skill **needs code** (CLI pattern).
   - If every step is purely about reasoning, coordinating existing tools, or following a written protocol, use the **instruction-only pattern**.
3. "Where should the skill be installed? (Workspace local `.agents/skills/`, global `~/.gemini/config/skills/`, or dual installation?)"

### Brainstorming Completion Criteria

You are ready to move to Phase 2 when you can confidently answer ALL of:

- [ ] What is the workflow's purpose and scope?
- [ ] What are the inputs and outputs?
- [ ] Which steps are strict vs. flexible?
- [ ] Which existing skills should be referenced?
- [ ] What new scripts (if any) are needed?
- [ ] How should errors be handled?
- [ ] Does the workflow need code (CLI) or is it instruction-only?
- [ ] Where should the skill be installed?

---

## Phase 2: Skill Design

Produce a **design document** (as an artifact with `RequestFeedback: true`) and present it to the user for approval. The document must include:

1. **Skill name and description** (YAML frontmatter rules: name $\le$ 64 chars, lowercase + hyphens; description $\le$ 1024 chars).
2. **Directory structure** showing all planned files and the install location.
3. **Existing skills referenced** with rationale.
4. **New scripts** (if any) with proposed CLI subcommands and arguments.
5. **Rate limiting and error handling strategies**.

**Wait for explicit user approval before proceeding to Phase 3.**

---

## Phase 3: Implementation

### Guiding Principles

- Use `node` or `uv run` for executing companion scripts.
- Prefer standard libraries over heavy third-party dependencies.
- Output from scripts must default to file output or concise summaries ($<500$ lines).
- All Markdown files must adhere to strict markdownlint spacing:
  - `MD022`: Heading blank lines before and after.
  - `MD028`: No blank line inside blockquotes.
  - `MD031`: Blank lines before and after code fences.
  - `MD032`: Blank lines surrounding lists.
  - `MD012`: Exactly one trailing newline at EOF.

### SKILL.md Structure

Every generated `SKILL.md` must follow this structure:

```markdown
---
name: {skill-name}
description: >-
  {description}
---

# {Skill Title}

## Overview
{Brief description of what the skill does.}

## Dependencies
{List of required skills, if any.}

## Quick Start
{Minimal example to get started.}

## Workflow (if instruction-only)
{Numbered steps with clear instructions.}

## Common Mistakes
{List 2-3 common pitfalls.}
```

---

## Phase 4: Validation

After implementation is complete:

1. **Test the skill / script**: Run the verification command or linter script.
2. **Synchronize AST Knowledge Graph**: Run `graphify build` (AST-only, zero token cost).
3. **Verify Identity & Ecosystem Health**: Run `npm run audit:identity`.
