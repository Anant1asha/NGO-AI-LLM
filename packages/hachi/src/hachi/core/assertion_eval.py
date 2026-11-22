"""Deterministic evaluator for ObjectGraph ``::assertion`` preconditions.

`.og` skills carry executable validation conditions the agent MUST verify before
acting. In practice the bundled skills express these as input-precondition checks
over the skill's parameters, e.g.::

    assert channel_name != "" "A target Slack channel must be provided."
    assert base != target  "Base and target currencies must be different."
    assert lamin != 0       "A valid bounding box must be provided."

This module evaluates those ``assert <lhs> <op> <rhs> "<message>"`` lines against a
dict of parameter values the agent intends to use. It is a **safe, bounded**
evaluator — a tiny comparison grammar over a bindings dict, NOT ``eval`` and NOT a
shell — so it realizes the "deterministic validation" promise without any code- or
command-execution surface. Lines that aren't in the recognized form are reported as
``manual`` (the agent verifies them itself) rather than guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# assert <lhs> <op> <rhs> "<message>"
_ASSERT_RE = re.compile(r'^assert\s+(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s+"(.*)"\s*$')


@dataclass
class AssertionResult:
    """Outcome of evaluating a single assertion line.

    ``status`` is one of: ``pass``, ``fail``, ``unknown`` (a referenced value was
    not supplied or types couldn't be compared), or ``manual`` (the line isn't an
    auto-checkable ``assert`` form).
    """

    assertion: str
    status: str
    message: str = ""
    detail: str = ""


def _resolve(token: str, params: dict[str, Any]) -> tuple[Any, bool]:
    """Resolve an operand to a value. Returns ``(value, resolved)``.

    A quoted string or numeric literal resolves to itself; a bare identifier
    resolves from ``params``. ``resolved=False`` means an identifier had no value.
    """
    token = token.strip()
    if token in ('""', "''"):
        return "", True
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1], True
    try:
        return (float(token) if "." in token else int(token)), True
    except ValueError:
        pass
    if token in params:
        return params[token], True
    return None, False


def _apply(op: str, left: Any, right: Any) -> bool | None:
    """Apply a comparison operator. Returns None when operands aren't comparable."""
    if op == "==":
        return bool(left == right)
    if op == "!=":
        return bool(left != right)
    # Ordering: prefer numeric comparison; fall back to native comparison.
    try:
        lf, rf = float(left), float(right)
        left, right = lf, rf
    except (TypeError, ValueError):
        pass
    try:
        if op == ">":
            return bool(left > right)
        if op == "<":
            return bool(left < right)
        if op == ">=":
            return bool(left >= right)
        if op == "<=":
            return bool(left <= right)
    except TypeError:
        return None
    return None


def evaluate_assertion(line: str, params: dict[str, Any]) -> AssertionResult:
    """Evaluate one assertion line against ``params``."""
    raw = line.strip()
    match = _ASSERT_RE.match(raw)
    if not match:
        return AssertionResult(
            assertion=raw,
            status="manual",
            detail="Not an auto-checkable 'assert <expr> \"message\"' form — verify it yourself.",
        )
    lhs_t, op, rhs_t, message = match.groups()
    lval, lok = _resolve(lhs_t, params)
    rval, rok = _resolve(rhs_t, params)
    if not lok or not rok:
        missing = [t for t, ok in ((lhs_t.strip(), lok), (rhs_t.strip(), rok)) if not ok]
        return AssertionResult(
            assertion=raw,
            status="unknown",
            message=message,
            detail=f"Provide a value for: {', '.join(missing)}",
        )
    result = _apply(op, lval, rval)
    if result is None:
        return AssertionResult(
            assertion=raw,
            status="unknown",
            message=message,
            detail=f"Cannot compare {lval!r} {op} {rval!r}.",
        )
    return AssertionResult(assertion=raw, status="pass" if result else "fail", message=message)


def evaluate_assertions(assertions: list[str], params: dict[str, Any]) -> list[AssertionResult]:
    """Evaluate every assertion line; see :func:`evaluate_assertion`."""
    return [evaluate_assertion(a, params) for a in assertions]


@dataclass
class AssertionReport:
    """Aggregate verdict over a node's assertions."""

    skill: str
    results: list[AssertionResult] = field(default_factory=list)

    @property
    def failed(self) -> list[AssertionResult]:
        return [r for r in self.results if r.status == "fail"]

    @property
    def unknown(self) -> list[AssertionResult]:
        return [r for r in self.results if r.status == "unknown"]

    @property
    def ok(self) -> bool:
        """True when nothing failed and every checkable assertion could be evaluated."""
        return not self.failed and not self.unknown
