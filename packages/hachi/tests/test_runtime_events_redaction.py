"""Tests verifying that adapt_event() redacts secrets before they enter the
event stream, TUI transcript, gateway SSE, or persisted SQLite.

Covers:
  - ADV-009 (tool_call input redaction at the choke point)
  - ADV-009 (tool_result preview redaction before truncation)
  - Redaction is unconditional — not subject to HACHI_ALLOW_OUTBOUND_SECRETS.
"""

from __future__ import annotations

import pytest

from hachi.core.runtime_events import TOOL_CALL_COMPLETED, TOOL_CALL_STARTED, adapt_event
from hachi.core.secret_scanner import REDACTION_PLACEHOLDER

# Canonical secret fixtures — just long enough to match the scanner patterns.
_ANTHROPIC = "sk-ant-" + "A" * 40
_AWS = "AKIA" + "IOSFODNN7EXAMPLE"


# ---------------------------------------------------------------------------
# tool_call branch — input dict (flat and nested)
# ---------------------------------------------------------------------------


def test_tool_call_redacts_secret_in_flat_input() -> None:
    """A secret at the top level of tool_input must be replaced."""
    envelopes = adapt_event(
        "tool_call",
        {"name": "x", "input": {"api_key": _ANTHROPIC}},
    )

    assert len(envelopes) == 1
    ev = envelopes[0].primary
    assert ev.name == TOOL_CALL_STARTED
    assert _ANTHROPIC not in str(ev.payload)
    assert REDACTION_PLACEHOLDER in str(ev.payload)


def test_tool_call_redacts_secret_at_every_nesting_depth() -> None:
    """Secrets nested arbitrarily deep inside the input dict must be scrubbed."""
    envelopes = adapt_event(
        "tool_call",
        {
            "name": "x",
            "input": {
                "key": _ANTHROPIC,
                "nested": {"t": _AWS},
            },
        },
    )

    assert len(envelopes) == 1
    payload = envelopes[0].primary.payload
    assert _ANTHROPIC not in str(payload), "top-level secret leaked"
    assert _AWS not in str(payload), "nested secret leaked"
    assert REDACTION_PLACEHOLDER in str(payload)


def test_tool_call_clean_input_passes_through_unchanged() -> None:
    """Non-secret values must not be altered."""
    envelopes = adapt_event(
        "tool_call",
        {"name": "read_file", "input": {"path": "/tmp/report.txt"}},
    )
    payload = envelopes[0].primary.payload
    assert payload["input"]["path"] == "/tmp/report.txt"


# ---------------------------------------------------------------------------
# tool_result branch — result_preview
# ---------------------------------------------------------------------------


def test_tool_result_redacts_secret_in_preview() -> None:
    """A secret in the tool result must be redacted before entering the preview."""
    envelopes = adapt_event(
        "tool_result",
        {"name": "x", "result": f"token={_ANTHROPIC} and other stuff"},
    )

    assert len(envelopes) == 1
    ev = envelopes[0].primary
    assert ev.name == TOOL_CALL_COMPLETED
    assert _ANTHROPIC not in ev.payload["result_preview"]
    assert REDACTION_PLACEHOLDER in ev.payload["result_preview"]


def test_tool_result_redacts_before_truncation() -> None:
    """A secret near the start of a long result must not survive inside the 2000-char window."""
    # Place the secret at position 0, then pad to well beyond TOOL_RESULT_PREVIEW_MAX.
    long_result = _ANTHROPIC + " " + ("x" * 3000)
    envelopes = adapt_event(
        "tool_result",
        {"name": "x", "result": long_result},
    )

    preview = envelopes[0].primary.payload["result_preview"]
    assert len(preview) <= 2000, "preview must be capped at TOOL_RESULT_PREVIEW_MAX"
    assert _ANTHROPIC not in preview, "secret survived inside the preview window"
    assert REDACTION_PLACEHOLDER in preview


def test_tool_result_clean_passes_through_unchanged() -> None:
    """A clean result must not be altered by redaction."""
    result_text = "All 42 tests passed in 1.3 s."
    envelopes = adapt_event(
        "tool_result",
        {"name": "run_tests", "result": result_text},
    )
    preview = envelopes[0].primary.payload["result_preview"]
    assert preview == result_text


# ---------------------------------------------------------------------------
# Unconditional redaction — env opt-out must NOT disable internal scrubbing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("opt_out_value", ["1", "true", "yes"])
def test_tool_call_redaction_ignores_outbound_opt_out(
    monkeypatch: pytest.MonkeyPatch, opt_out_value: str
) -> None:
    """HACHI_ALLOW_OUTBOUND_SECRETS must NOT bypass internal event redaction."""
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", opt_out_value)

    envelopes = adapt_event(
        "tool_call",
        {"name": "x", "input": {"key": _ANTHROPIC}},
    )
    payload = envelopes[0].primary.payload
    assert _ANTHROPIC not in str(payload), (
        f"secret leaked with HACHI_ALLOW_OUTBOUND_SECRETS={opt_out_value!r}"
    )


@pytest.mark.parametrize("opt_out_value", ["1", "true", "yes"])
def test_tool_result_redaction_ignores_outbound_opt_out(
    monkeypatch: pytest.MonkeyPatch, opt_out_value: str
) -> None:
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", opt_out_value)

    envelopes = adapt_event(
        "tool_result",
        {"name": "x", "result": f"token={_ANTHROPIC}"},
    )
    preview = envelopes[0].primary.payload["result_preview"]
    assert _ANTHROPIC not in preview, (
        f"secret leaked with HACHI_ALLOW_OUTBOUND_SECRETS={opt_out_value!r}"
    )
