"""
Phase 0 — offline measurement harness tests.

Asserts that ``count_prompt_tokens`` is:
  1. Deterministic (same result on repeated calls with the same registry).
  2. Structurally correct (all expected keys present, reasonable types).
  3. Within ±20 % of the recorded offline baseline from ``COST_BASELINE.json``
     (the existing measurement at brain.og revision + lazy-tool trim, ~5 037 tokens
     from the live run).  20 % tolerance handles the char-based estimator vs a real
     tokenizer.
  4. Reports at least the 18 known core tools (OS + OG + memory + session + use_tools).

No live API calls.  The HACHI_DISABLE_DOTENV_AUTOLOAD guard is set by the script
module on import, so conftest's existing guard is not double-applied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_BASELINE_FILE = _REPO_ROOT / "docs" / "audit" / "2026-06-28" / "COST_BASELINE.json"

# The live "after" baseline captured on 2026-06-28: 5 037 input tokens for a trivial
# turn (brain.og + 19 core tool schemas + 10-token user message).
# Offline estimator uses 4 bytes/token, so the estimated total will differ; allow ±20 %.
_LIVE_BASELINE_TOKENS = 5_037
_TOLERANCE = 0.20


@pytest.fixture(scope="module")
def registry():
    """Pre-built core registry — built once per module to speed up the suite."""
    from scripts.measure_turn import build_core_registry

    return build_core_registry()


@pytest.fixture(scope="module")
def brain_content() -> str:
    """brain.og text (empty string when the file is absent — unit tests still pass)."""
    from hachi.core.paths import get_hachi_paths

    p = get_hachi_paths().brain_file
    return p.read_text(encoding="utf-8") if p.exists() else ""


@pytest.fixture(scope="module")
def offline_metrics(registry, brain_content) -> dict[str, Any]:
    from scripts.measure_turn import count_prompt_tokens

    return count_prompt_tokens(brain_content=brain_content, registry=registry)


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


def test_offline_returns_expected_keys(offline_metrics: dict[str, Any]) -> None:
    expected = {
        "method",
        "system_tokens",
        "tool_tokens",
        "user_tokens",
        "total_tokens",
        "core_tool_count",
        "brain_content_bytes",
        "tool_json_bytes",
    }
    assert expected <= offline_metrics.keys(), f"Missing keys: {expected - offline_metrics.keys()}"


def test_offline_method_is_offline(offline_metrics: dict[str, Any]) -> None:
    assert offline_metrics["method"] == "offline"


def test_offline_all_token_counts_positive(offline_metrics: dict[str, Any]) -> None:
    for key in ("system_tokens", "tool_tokens", "user_tokens", "total_tokens"):
        assert offline_metrics[key] > 0, f"{key} must be > 0, got {offline_metrics[key]}"


def test_offline_total_equals_sum(offline_metrics: dict[str, Any]) -> None:
    expected = (
        offline_metrics["system_tokens"]
        + offline_metrics["tool_tokens"]
        + offline_metrics["user_tokens"]
    )
    assert offline_metrics["total_tokens"] == expected


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------


def test_offline_is_deterministic(brain_content: str, registry) -> None:
    from scripts.measure_turn import count_prompt_tokens

    m1 = count_prompt_tokens(brain_content=brain_content, registry=registry)
    m2 = count_prompt_tokens(brain_content=brain_content, registry=registry)
    assert m1["total_tokens"] == m2["total_tokens"], "offline count must be deterministic"
    assert m1["core_tool_count"] == m2["core_tool_count"]


# ---------------------------------------------------------------------------
# Core-tool count guard
# ---------------------------------------------------------------------------


def test_offline_core_tool_count_at_least_18(offline_metrics: dict[str, Any]) -> None:
    """OS (4) + OG (6-8) + use_tools (1) + memory (6) + session (1) = ≥18 core tools."""
    count = offline_metrics["core_tool_count"]
    assert count >= 18, f"Expected ≥18 core tools, got {count}"


# ---------------------------------------------------------------------------
# Tolerance vs the live baseline
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _BASELINE_FILE.exists(),
    reason="COST_BASELINE.json not present; tolerance check skipped",
)
def test_offline_total_within_tolerance_of_live_baseline(
    offline_metrics: dict[str, Any],
    brain_content: str,
) -> None:
    """Offline estimate must be within ±20 % of the live 5037-token baseline.

    The estimator is rough (4 bytes/token), but the canonical query + brain.og + 19
    core tools produce a stable total.  A >20 % deviation signals that either the
    brain.og grew significantly or the tool set changed substantially.
    """
    if not brain_content:
        pytest.skip("brain.og absent in this environment; tolerance check skipped")

    total = offline_metrics["total_tokens"]
    lo = _LIVE_BASELINE_TOKENS * (1 - _TOLERANCE)
    hi = _LIVE_BASELINE_TOKENS * (1 + _TOLERANCE)
    assert lo <= total <= hi, (
        f"Offline token estimate {total:,} is outside ±{_TOLERANCE:.0%} of live "
        f"baseline {_LIVE_BASELINE_TOKENS:,} (expected {lo:.0f}–{hi:.0f})"
    )


# ---------------------------------------------------------------------------
# _estimate_tokens unit test
# ---------------------------------------------------------------------------


def test_estimate_tokens_ascii() -> None:
    from scripts.measure_turn import _estimate_tokens

    text = "Hello world"  # 11 bytes → 2 tokens
    assert _estimate_tokens(text) == 2


def test_estimate_tokens_empty_returns_one() -> None:
    from scripts.measure_turn import _estimate_tokens

    assert _estimate_tokens("") == 1  # min(1, ...) guard


def test_estimate_tokens_longer_text() -> None:
    from scripts.measure_turn import _estimate_tokens

    text = "a" * 400  # 400 bytes → 100 tokens
    assert _estimate_tokens(text) == 100
