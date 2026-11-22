from hachi.core.runtime_events import (
    JOB_COMPLETED,
    JOB_STARTED,
    TOOL_CALL_COMPLETED,
    TOOL_CALL_STARTED,
    adapt_event,
)
from hachi.core.runtime_read_models import RuntimeReadModelStore


def test_tool_call_adapts_without_permission_side_effects() -> None:
    envelopes = adapt_event("tool_call", {"name": "read_file", "input": {"path": "x"}})

    assert len(envelopes) == 1
    assert envelopes[0].primary.name == TOOL_CALL_STARTED


def test_tool_result_adapts_without_permission_side_effects() -> None:
    envelopes = adapt_event("tool_result", {"name": "read_file", "result": "ok"})

    assert len(envelopes) == 1
    assert envelopes[0].primary.name == TOOL_CALL_COMPLETED


def _job_event(envelopes, name):
    return next(env.primary for env in envelopes if env.primary.name == name)


def test_delegation_start_and_complete_share_job_id() -> None:
    """Regression: the JOB_COMPLETED job_id must equal the JOB_STARTED one.

    They previously diverged (start folded in the task slug, complete did not),
    so a finished sub-agent was never matched and stayed "running" forever.
    """
    role, task = "researcher", "Write a long debate argument about AI"

    started = _job_event(adapt_event("delegation_start", {"role": role, "task": task}), JOB_STARTED)
    completed = _job_event(
        adapt_event("delegation_complete", {"role": role, "status": "success", "task": task}),
        JOB_COMPLETED,
    )

    assert started.payload["job_id"] == completed.payload["job_id"]


def test_completed_subagent_leaves_active_jobs() -> None:
    """End-to-end: a completed delegation is cleared from active_jobs()."""
    role, task = "researcher", "Write a long debate argument about AI"
    store = RuntimeReadModelStore()

    for env in adapt_event("delegation_start", {"role": role, "task": task}):
        store.append_event(env.primary)
    assert any(job.kind == "subagent" for job in store.active_jobs()), (
        "sub-agent job should be running right after delegation_start"
    )

    for env in adapt_event(
        "delegation_complete", {"role": role, "status": "success", "task": task}
    ):
        store.append_event(env.primary)

    assert not any(job.kind == "subagent" for job in store.active_jobs()), (
        "sub-agent job must leave the Active Jobs table once it completes"
    )
