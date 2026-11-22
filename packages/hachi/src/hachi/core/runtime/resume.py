"""Resume logic for durable runs (Initiative D — A2 turn-granular resume).

resume_run() implements the A2 design:
1. Load RunState; guard WAITING→RUNNING (idempotent).
2. Load the session; replay durable transcript into a fresh MemoryManager.
3. Inject the wait result as a new user message.
4. Start a NEW turn (not mid-loop restart).
5. Transition RunState to COMPLETED (or FAILED on error).

If the infrastructure for full resume (session lookup, LLM client) is not
available in the current process context (e.g., CLI without gateway boot),
resume_run raises HonestResumeError so callers get a clear, honest failure.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HonestResumeError(Exception):
    """Raised when resume cannot be wired end-to-end in the current context.

    This is the honest-fail path: callers should surface this message to the
    operator rather than silently swallowing it.
    """


def resume_run(run_id: str, result: dict[str, Any]) -> str:
    """Resume a WAITING run, injecting *result* as the wait outcome.

    Implements A2 turn-granular resume:
    - Replays durable transcript into a fresh MemoryManager (reuses proven
      session.resume_from_session machinery where available).
    - Starts a NEW turn — no mid-loop checkpoint.
    - Idempotent: only WAITING→RUNNING transitions succeed (status guard).

    Args:
        run_id: The durable run identifier.
        result: The wake payload (e.g., ``{"decision": "approved"}``).

    Returns:
        The final response text from the resumed turn.

    Raises:
        HonestResumeError: When the gateway / session context is not available
                           in the current process (e.g., standalone CLI).
        KeyError: When no RunState is found for *run_id*.
    """
    from hachi.core.runtime.state import RunStatus
    from hachi.core.runtime.store import RunStateStore
    from hachi.core.runtime_events import RUN_RESUMED, now_iso

    store = RunStateStore()
    run = store.get(run_id)
    if run is None:
        raise KeyError(f"No RunState found for run_id={run_id!r}")

    # Idempotency guard: only WAITING→RUNNING is allowed.
    if run.status != RunStatus.WAITING:
        logger.info(
            "resume_run: run %r is %r (not WAITING) — skipping (idempotent)",
            run_id,
            run.status.value,
        )
        return f"no-op: status is {run.status.value}"

    # Transition to RUNNING
    run = run.model_copy(update={"status": RunStatus.RUNNING, "updated_at": now_iso()})
    store.upsert(run)

    # Inject wait result into payload for the resumed turn
    resume_context = dict(run.payload)
    resume_context["wait_result"] = result

    try:
        response = _do_resume(run.session_id, resume_context, run.resume_cursor)
        # Transition to COMPLETED
        run = run.model_copy(update={"status": RunStatus.COMPLETED, "updated_at": now_iso()})
        store.upsert(run)

        # Emit run.resumed via event bus if available
        _try_emit(RUN_RESUMED, {"run_id": run_id, "session_id": run.session_id})

        return response
    except HonestResumeError:
        # Re-raise without marking FAILED — the run is still WAITING conceptually
        run = run.model_copy(update={"status": RunStatus.WAITING, "updated_at": now_iso()})
        store.upsert(run)
        raise
    except Exception as exc:
        logger.error("resume_run: failed for run %r — %s", run_id, exc)
        from hachi.core.runtime.state import RunStatus

        run = run.model_copy(
            update={
                "status": RunStatus.FAILED,
                "payload": {**resume_context, "error": str(exc)},
                "updated_at": now_iso(),
            }
        )
        store.upsert(run)
        raise


def _do_resume(session_id: str, context: dict[str, Any], cursor: int) -> str:
    """Internal: find or rehydrate the gateway session and start a new turn.

    Hot path: the session is live in the active runtime → chat() directly.
    Cold path: the session is GONE (gateway restarted) → rehydrate from the
    SQLite transcript via :meth:`~hachi.cli.main._InProcessGatewayRuntime.rehydrate_session`,
    then inject the wait result and run a new turn.  The rehydration reuses
    the same ``boot_agent(resume_session_id=…)`` machinery as a normal session
    resume so the transcript replay is REAL, not faked.

    No-runtime path: no active runtime is attached (standalone CLI) →
    ``HonestResumeError`` so callers get a clear, honest failure.
    """
    # Resolve the active in-process runtime (set by _start_gateway_server / gateway command).
    # Read via the module object so monkeypatching and late writes are visible at call time.
    try:
        import hachi.cli.main as _main_mod

        runtime = getattr(_main_mod, "_ACTIVE_RUNTIME", None)
    except ImportError as exc:
        raise HonestResumeError(
            "resume_run: hachi.cli.main not available in current context. "
            "Start the gateway server to enable suspend/resume."
        ) from exc
    if runtime is None:
        raise HonestResumeError(
            "resume_run: no active in-process runtime "
            f"(_ACTIVE_RUNTIME is None) for session_id={session_id!r}. "
            "Cold-start resume requires a running gateway (--runtime flag). "
            "Trigger via POST /runs/{run_id}/wake after starting the gateway."
        )

    # Build the injection message from the wait result
    wait_result = context.get("wait_result", {})
    inject_text = f"[RESUME] Wait condition satisfied. Result: {wait_result}"

    # --- Hot path: session is already live ---
    with runtime._agents_lock:
        agent_session = runtime._agents.get(session_id)

    if agent_session is not None:
        logger.info("_do_resume: hot path — session %r is live, injecting turn", session_id)
        response: str = agent_session.chat(inject_text)
        return response

    # --- Cold path: session not live (gateway restarted) → rehydrate ---
    logger.info(
        "_do_resume: cold path — session %r not in live map; rehydrating from transcript",
        session_id,
    )
    rehydrated = runtime.rehydrate_session(session_id)
    if rehydrated is None:
        raise HonestResumeError(
            f"resume_run: cold-start rehydration failed for session_id={session_id!r}. "
            "The transcript may be empty or the agent boot may have errored. "
            "Check gateway logs for details."
        )

    logger.info(
        "_do_resume: rehydration succeeded for session %r; injecting resumed turn",
        session_id,
    )
    response = rehydrated.chat(inject_text)
    return response


def _try_emit(event_name: str, payload: dict[str, Any]) -> None:
    """Best-effort event emission — never raises."""
    try:
        bus = _get_process_bus()
        if bus is not None:
            from hachi.core.runtime_events import RuntimeEvent, now_iso

            bus.publish(RuntimeEvent(name=event_name, payload=payload, timestamp=now_iso()))
    except Exception:
        logger.debug("_try_emit: failed to emit %r — skipping", event_name, exc_info=True)


def _get_process_bus() -> Any:
    """Return the process-level EventBus singleton, or None."""
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        if shared is not None and hasattr(shared, "event_bus"):
            return shared.event_bus
    except Exception:
        pass
    return None
