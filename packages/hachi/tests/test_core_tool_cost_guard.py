"""R3 CI cost-regression guard — assembled-prompt token budget.

Imports the Phase 0 offline harness (scripts/measure_turn.py) and asserts
that the total prompt token count for a canonical query has not grown more
than 10 % over the recorded baseline.  Pins model + core tools only so
unrelated routing config does not flake it.

This test is deterministic (no API call, no live provider) and runs as part
of the standard pytest suite.  A deliberate brain.og bloat will cause it to
fail; reverting the bloat will fix it.

Baseline: 5 673 tokens (Phase 0 offline measurement, 2026-06-28,
18 core tools, 1-byte-≈-4-chars heuristic).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/ importable without installing it.
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Recorded baseline (Phase 0 offline run, 2026-06-28)
# ---------------------------------------------------------------------------

_BASELINE_TOTAL_TOKENS = 5_673
_TOOL_JSON_BYTES_BASELINE = 26_835  # core-tool schema size at baseline
_TOLERANCE = 0.10  # 10 % growth ceiling


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_harness():
    """Import the Phase 0 offline harness.  Skip if scripts/ missing deps."""
    try:
        import measure_turn  # noqa: PLC0415

        return measure_turn
    except ImportError as exc:
        pytest.skip(f"measure_turn.py not importable: {exc}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCoreToolCostGuard:
    """Assembled-prompt token count must not grow more than 10 % over baseline."""

    def test_total_tokens_within_budget(self) -> None:
        """The canonical-query total prompt tokens must stay ≤ baseline × 1.10."""
        harness = _import_harness()
        result = harness.count_prompt_tokens()

        total = result["total_tokens"]
        ceiling = int(_BASELINE_TOTAL_TOKENS * (1 + _TOLERANCE))
        assert total <= ceiling, (
            f"Prompt grew too large: {total} tokens > {ceiling} ceiling "
            f"({_BASELINE_TOTAL_TOKENS} baseline + {int(_TOLERANCE * 100)}% tolerance). "
            f"Breakdown — system:{result['system_tokens']} "
            f"tool:{result['tool_tokens']} user:{result['user_tokens']}. "
            "Reduce brain.og or core-tool schemas to bring it back under budget."
        )

    def test_core_tool_schema_bytes_within_budget(self) -> None:
        """Core-tool JSON schema bytes must not grow more than 10 % over baseline."""
        harness = _import_harness()
        result = harness.count_prompt_tokens()

        schema_bytes = result["tool_json_bytes"]
        ceiling = int(_TOOL_JSON_BYTES_BASELINE * (1 + _TOLERANCE))
        assert schema_bytes <= ceiling, (
            f"Tool schemas grew too large: {schema_bytes} bytes > {ceiling} ceiling "
            f"({_TOOL_JSON_BYTES_BASELINE} baseline + {int(_TOLERANCE * 100)}% tolerance). "
            "A new tool or expanded schema description caused the regression."
        )

    def test_harness_returns_expected_keys(self) -> None:
        """Smoke-test that count_prompt_tokens() returns the expected dict shape."""
        harness = _import_harness()
        result = harness.count_prompt_tokens()

        assert result["method"] == "offline"
        for key in (
            "system_tokens",
            "tool_tokens",
            "user_tokens",
            "total_tokens",
            "core_tool_count",
            "brain_content_bytes",
            "tool_json_bytes",
        ):
            assert key in result, f"Missing key: {key}"
        assert result["total_tokens"] == (
            result["system_tokens"] + result["tool_tokens"] + result["user_tokens"]
        )

    def test_core_tool_count_stable(self) -> None:
        """Core tool count should not silently drop (regression: tool accidentally removed)."""
        harness = _import_harness()
        result = harness.count_prompt_tokens()

        # Baseline: 18 core tools at Phase 0.  A drop below 15 signals a breakage.
        assert result["core_tool_count"] >= 15, (
            f"Only {result['core_tool_count']} core tools found — "
            "expected ≥ 15 (baseline was 18). A tool may have been accidentally removed."
        )
