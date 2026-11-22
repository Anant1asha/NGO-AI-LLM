"""Eval substrate for Hachi: failure-mining reports and regression-runner scaffold.

Public API
----------
- :class:`EvalReport` — typed dataclass holding aggregated analytics over interaction rows.
- :func:`build_failure_report` — pure function; no I/O; fully testable against seeded rows.
- :class:`EvalCase` — a named regression case with structural assertions.
- :class:`EvalAssertion` — typed union of assertion kinds.
- :class:`EvalCaseResult` — result of running one EvalCase.
- :func:`run_case` — executes one case against a caller-supplied turn function.
- :data:`DEFAULT_SUITE` — seed suite (1-2 generic cases); intended to grow over time.
"""

from hachi.core.eval.report import EvalReport, build_failure_report
from hachi.core.eval.runner import (
    DEFAULT_SUITE,
    EvalAssertion,
    EvalCase,
    EvalCaseResult,
    TurnTrajectory,
    run_case,
)

__all__ = [
    "EvalReport",
    "build_failure_report",
    "EvalAssertion",
    "EvalCase",
    "EvalCaseResult",
    "TurnTrajectory",
    "run_case",
    "DEFAULT_SUITE",
]
