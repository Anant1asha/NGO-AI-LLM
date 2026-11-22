"""Workflow Management Tools

Provides tools for the agent to manage long-running, multi-step workflows.
The suspend tool signals the ExecutionLoop to end the current turn; the
gateway layer persists RunState and arms the WaitConditionRegistry.
"""

from __future__ import annotations

from hachi.core.loop import SuspendWorkflow, ToolRegistry


def register_workflow_tools(registry: ToolRegistry) -> None:
    """Mount workflow orchestration tools into the LLM's active toolset."""

    def suspend_workflow(
        reason: str,
        wait_kind: str = "user",
        wait_key: str = "",
    ) -> str:
        """Signal the ExecutionLoop to suspend the current turn.

        The loop catches SuspendWorkflow, ends the turn cleanly, and the gateway
        layer persists RunState(WAITING) + arms the WaitConditionRegistry so the
        run can be resumed when the wait condition is satisfied.
        """
        raise SuspendWorkflow(
            reason=reason,
            wait_kind=wait_kind,
            wait_key=wait_key,
        )

    registry.register(
        {
            "name": "core_suspend_workflow",
            "description": (
                "Suspend the current workflow turn and wait for an external condition. "
                "The current turn ends cleanly. Resume requires an external trigger "
                "(human approval, an event, a scheduled time, or a /runs/{id}/wake call). "
                "Use wait_kind='user' for human approval, 'event' for an EventBus pattern, "
                "'time' for an ISO-8601 timestamp, 'webhook' for an inbound webhook."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the workflow is suspending.",
                    },
                    "wait_kind": {
                        "type": "string",
                        "enum": ["user", "event", "time", "webhook"],
                        "description": "The kind of condition to wait for.",
                        "default": "user",
                    },
                    "wait_key": {
                        "type": "string",
                        "description": (
                            "The specific condition key: approval id for 'user', "
                            "event pattern for 'event', ISO-8601 for 'time', "
                            "webhook token for 'webhook'."
                        ),
                        "default": "",
                    },
                },
                "required": ["reason"],
            },
        },
        suspend_workflow,
    )
