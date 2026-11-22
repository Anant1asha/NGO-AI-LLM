"""Production replay harness for deterministic, CI-able eval runs.

Purpose
-------
This module provides the scaffolding that makes ``hachi eval run`` a REAL,
deterministic, CI-able command — without requiring a live Anthropic API key.

The core mechanism is **record/replay**: every ``ReplayCase`` bundles a
pre-recorded sequence of ``LLMResponse`` objects (the LLM script) together
with an ``EvalCase`` (user input + structural assertions).  At run time,
``make_replay_turn_fn`` builds a real ``ExecutionLoop`` whose LLM transport is
replaced by a ``ScriptedLLMClient`` that replays the recorded responses in
order.  Everything else — the ReAct loop, tool dispatch, memory management —
is real production code.

Anti-fake contract
------------------
1. The replay ``turn_fn`` drives the PRODUCTION ``ExecutionLoop`` class — the
   exact same class exercised by ``test_e2e_loop.py``.  It is NOT a stub that
   returns hand-crafted trajectories.  The only thing scripted/stubbed is the
   LLM transport boundary (the non-deterministic external call).
2. Pass/fail logic is NEVER reimplemented here.  ``run_replay_suite`` calls the
   existing ``run_case`` from ``runner.py`` for every case — that function is the
   audited anti-fake core (it sets ``passed = len(failures) == 0``).
3. ``run_replay_suite`` returns real ``EvalCaseResult`` objects.  The CLI layer
   checks ``result.passed`` and calls ``raise typer.Exit(code=1)`` when any case
   fails.

Honest cost limitation
-----------------------
``ScriptedLLMClient`` has no real cost meter — it is entirely offline.
``TurnTrajectory.cost_usd`` is therefore always ``0.0`` for replay-based runs.
Do NOT include ``max_cost_usd`` assertions in ``DEFAULT_REPLAY_SUITE``; checking
a real threshold against a synthetic 0.0 cost would be meaningless.  If you
want to exercise the cost-assertion code path, do it in a unit test with an
explicit synthetic ``TurnTrajectory``.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any

from hachi.core.eval.runner import EvalCase, EvalCaseResult, TurnTrajectory, run_case
from hachi.core.llm import LLMResponse
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.sub_agent import SubAgentMemory

# ---------------------------------------------------------------------------
# Scripted LLM client — production-grade copy of the test harness client.
# DO NOT import this from tests/test_eval_runner.py; keeping both copies
# independent ensures each file is independently runnable and readable.
# ---------------------------------------------------------------------------

_EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


def _tool_schema(name: str, description: str = "") -> dict[str, Any]:
    """Return a minimal valid tool schema for use with ToolRegistry.register()."""
    return {
        "name": name,
        "description": description or name,
        "input_schema": _EMPTY_SCHEMA,
    }


class ScriptedLLMClient:
    """Offline LLM client that replays a pre-recorded queue of ``LLMResponse`` objects.

    Every call to ``generate()`` returns the next response in the queue.  When
    the queue is exhausted it replays the last response indefinitely (so a
    misconfigured script doesn't raise an index error mid-loop — it just stalls
    as a no-op final reply, which the loop catches as a clean finish).

    This is a PRODUCTION class — it is imported by both ``corpus.py`` and any
    user-authored ``--suite`` file.  It is intentionally a mirror of the one in
    ``tests/test_eval_runner.py`` so both remain independently readable.

    Attributes
    ----------
    model:
        A fixed model name string so ``ExecutionLoop._resolve_turn_client`` and
        tracing helpers don't crash trying to read it.
    calls:
        Number of times ``generate()`` has been called (useful for debugging).
    """

    model: str = "scripted-replay-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        if not responses:
            raise ValueError("ScriptedLLMClient requires at least one LLMResponse.")
        self._responses = responses
        self.calls: int = 0

    def generate(self, **kwargs: Any) -> LLMResponse:
        """Return the next scripted response (repeats the last when exhausted)."""
        idx = min(self.calls, len(self._responses) - 1)
        resp = self._responses[idx]
        self.calls += 1
        return resp

    def generate_stream(self, **kwargs: Any) -> Generator[str, None, LLMResponse]:
        """Thin streaming shim: delegates to ``generate()`` and yields the content."""
        response = self.generate(**kwargs)

        def _gen() -> Generator[str, None, LLMResponse]:
            if response.content:
                yield response.content
            return response

        return _gen()


# ---------------------------------------------------------------------------
# ToolSpec — describes a tool to register in the replay ToolRegistry
# ---------------------------------------------------------------------------


@dataclass
class ToolSpec:
    """A tool definition for use in a ``ReplayCase``.

    Attributes
    ----------
    name:
        The tool name (used as the key in ``ToolRegistry`` and what the LLM
        script should reference via ``ToolCall.name``).
    callable:
        A deterministic callable that the ``ExecutionLoop`` will invoke when
        the scripted LLM requests this tool.  Keep it trivial and side-effect
        free (e.g. ``lambda **kw: "result"``).
    description:
        Human-readable description embedded in the schema sent to the LLM.
    """

    name: str
    callable: Callable[..., Any]
    description: str = ""


# ---------------------------------------------------------------------------
# ReplayCase — the unit of record/replay
# ---------------------------------------------------------------------------


@dataclass
class ReplayCase:
    """A self-contained, deterministic eval case bundling the EvalCase + LLM script.

    A ``ReplayCase`` is the record/replay unit:
    - ``case`` carries the user input and structural assertions.
    - ``llm_script`` is the sequence of ``LLMResponse`` objects the scripted LLM
      will return, in order.
    - ``tools`` lists any tools the script will call (must be registered so the
      ``ToolRegistry.execute()`` path doesn't hit "tool not registered" errors).

    Attributes
    ----------
    case:
        The :class:`~hachi.core.eval.runner.EvalCase` to run.
    llm_script:
        Ordered list of ``LLMResponse`` objects.  Must have at least one element.
        The last element is replayed indefinitely when the list is shorter than the
        number of LLM calls the loop makes.
    tools:
        Optional list of :class:`ToolSpec` objects.  Register every tool the
        ``llm_script`` will call via ``ToolCall``; an unregistered tool causes a
        "tool not registered" error that makes the assertion ``no_error()`` fail.
    """

    case: EvalCase
    llm_script: list[LLMResponse]
    tools: list[ToolSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# make_replay_turn_fn — wires a ReplayCase into a real ExecutionLoop turn_fn
# ---------------------------------------------------------------------------


def make_replay_turn_fn(rc: ReplayCase) -> Callable[[str], TurnTrajectory]:
    """Build a turn_fn that drives a REAL ``ExecutionLoop`` with a scripted LLM.

    This is the anti-fake proof: ``ExecutionLoop`` is the production class.
    ``ScriptedLLMClient`` is deterministic but the ReAct loop, tool dispatch,
    and memory management are all real.  The returned ``TurnTrajectory`` has
    output, tool_calls, and error populated from real execution — not fabricated.

    ``cost_usd`` is always ``0.0`` because the scripted client has no cost meter
    (see module docstring for the honest limitation).

    Args:
        rc: The :class:`ReplayCase` to build a turn_fn for.

    Returns:
        A callable ``(user_input: str) -> TurnTrajectory`` suitable for passing
        to :func:`~hachi.core.eval.runner.run_case`.
    """
    llm = ScriptedLLMClient(rc.llm_script)
    reg = ToolRegistry()
    for ts in rc.tools:
        reg.register(_tool_schema(ts.name, ts.description), ts.callable)
    mem = SubAgentMemory()
    loop = ExecutionLoop(
        llm_client=llm,
        registry=reg,
        memory=mem,
        base_system_prompt="eval-replay",
    )

    def turn_fn(user_input: str) -> TurnTrajectory:
        loop.add_user_message(user_input)
        try:
            output = loop.run(max_iterations=10)
            tool_names = loop.last_tool_calls
            return TurnTrajectory(
                output=output,
                tool_calls=tool_names,
                cost_usd=0.0,  # scripted LLM has no real cost meter
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            return TurnTrajectory(error=str(exc))

    return turn_fn


# ---------------------------------------------------------------------------
# run_replay_suite — run a list of ReplayCases and return EvalCaseResults
# ---------------------------------------------------------------------------


def run_replay_suite(suite: list[ReplayCase]) -> list[EvalCaseResult]:
    """Execute every :class:`ReplayCase` in the suite and return results.

    This function NEVER reimplements pass/fail logic.  It delegates each case
    to :func:`~hachi.core.eval.runner.run_case`, which is the audited anti-fake
    core.  Pass/fail is set exactly once: in ``run_case``, as
    ``passed = len(failures) == 0``.

    Args:
        suite: Ordered list of :class:`ReplayCase` objects to run.

    Returns:
        A list of :class:`~hachi.core.eval.runner.EvalCaseResult` objects in the
        same order as ``suite``.
    """
    results: list[EvalCaseResult] = []
    for rc in suite:
        turn_fn = make_replay_turn_fn(rc)
        result = run_case(rc.case, turn_fn=turn_fn)
        results.append(result)
    return results
