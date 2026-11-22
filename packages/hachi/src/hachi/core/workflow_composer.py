"""Workflow Composer: NL → preview card → approve → save_skill + create_schedule.

The Composer is *not* a new DSL.  It is a structured preview/confirmation layer
that the LLM calls before committing workflow artifacts to disk.  The approval
flow is:

    1. LLM builds a ``WorkflowSpec`` (via ``parse_workflow_spec`` or directly)
    2. ``render_workflow_preview`` produces a human-readable card
    3. User confirms → LLM calls existing ``save_skill`` + ``create_schedule`` tools
    4. User rejects → nothing written

Dry-run support (``dry_run=True`` on the spec) stubs all outbound sends and
file writes while still describing *what would happen*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStep:
    """A single step in a workflow — tool call or inline instruction."""

    description: str
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    send_stub: str = ""


@dataclass
class WorkflowTrigger:
    """How the workflow fires."""

    kind: str = "manual"  # "manual" | "cron" | "interval" | "condition"
    cron: str = ""
    interval_seconds: int = 0
    condition_skill: str = ""
    description: str = ""


@dataclass
class WorkflowSpec:
    """A structured, reviewable workflow definition.

    Attributes:
        name:            Short slug used as the skill name (e.g. ``morning_briefing``).
        description:     One-line human description shown in the preview card.
        trigger:         When and how the workflow fires.
        steps:           Ordered list of actions the workflow performs.
        scopes:          Integration scopes the workflow will use.
        est_cost_usd:    Estimated cost per run (informational only).
        dry_run:         If True, execution stubs writes and outbound sends.
        assertions:      OG-style pass/fail checks written into the saved skill.
    """

    name: str
    description: str = ""
    trigger: WorkflowTrigger = field(default_factory=WorkflowTrigger)
    steps: list[WorkflowStep] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    est_cost_usd: float = 0.0
    dry_run: bool = False
    assertions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Preview card rendering
# ---------------------------------------------------------------------------


def render_workflow_preview(spec: WorkflowSpec) -> str:
    """Return a human-readable preview card string for CLI / Telegram display.

    The card covers trigger, steps, scopes, and estimated cost.  It ends with
    [Approve] / [Reject] prompts so callers know what to display.
    """
    lines: list[str] = []
    sep = "─" * 60

    mode = " [DRY-RUN]" if spec.dry_run else ""
    lines.append(f"\n{sep}")
    lines.append(f"  Workflow Preview{mode}: {spec.name}")
    if spec.description:
        lines.append(f"  {spec.description}")
    lines.append(sep)

    # Trigger block
    t = spec.trigger
    if t.kind == "cron":
        trigger_label = f"cron  '{t.cron}'"
    elif t.kind == "interval":
        trigger_label = f"every {t.interval_seconds}s"
    elif t.kind == "condition":
        trigger_label = f"condition  '{t.condition_skill}'"
    else:
        trigger_label = "manual"
    if t.description:
        trigger_label += f"  ({t.description})"
    lines.append(f"\n  Trigger:  {trigger_label}")

    # Steps block
    lines.append(f"\n  Steps ({len(spec.steps)}):")
    for i, step in enumerate(spec.steps, 1):
        stub = f"  → would send: {step.send_stub}" if spec.dry_run and step.send_stub else ""
        tool_tag = f" [{step.tool}]" if step.tool else ""
        lines.append(f"    {i}. {step.description}{tool_tag}{stub}")

    # Scopes block
    if spec.scopes:
        lines.append(f"\n  Scopes:  {', '.join(spec.scopes)}")

    # Cost estimate
    if spec.est_cost_usd > 0:
        lines.append(f"\n  Est. cost/run:  ${spec.est_cost_usd:.4f}")

    # Assertions
    if spec.assertions:
        lines.append("\n  Assertions:")
        for assertion in spec.assertions:
            lines.append(f"    ✓  {assertion}")

    lines.append(f"\n{sep}")
    lines.append("  [Approve]  to save this workflow   |   [Reject]  to discard")
    lines.append(f"{sep}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dry-run annotation helpers
# ---------------------------------------------------------------------------


def annotate_dry_run_step(step: WorkflowStep) -> WorkflowStep:
    """Return a copy of ``step`` with a dry-run stub annotation if it has a send."""
    if step.send_stub or not step.tool:
        return step
    # Annotate tools that perform outbound sends
    outbound_tools = {
        "send_email",
        "send_slack_message",
        "send_telegram_message",
        "post_to_channel",
        "create_calendar_event",
        "delete_file",
        "write_file",
        "create_notion_page",
    }
    if step.tool in outbound_tools:
        return WorkflowStep(
            description=step.description,
            tool=step.tool,
            args=step.args,
            send_stub=f"[{step.tool}] (stubbed in dry-run)",
        )
    return step


def apply_dry_run(spec: WorkflowSpec) -> WorkflowSpec:
    """Return a copy of ``spec`` with dry-run annotations applied to all steps."""
    return WorkflowSpec(
        name=spec.name,
        description=spec.description,
        trigger=spec.trigger,
        steps=[annotate_dry_run_step(s) for s in spec.steps],
        scopes=spec.scopes,
        est_cost_usd=spec.est_cost_usd,
        dry_run=True,
        assertions=spec.assertions,
    )
