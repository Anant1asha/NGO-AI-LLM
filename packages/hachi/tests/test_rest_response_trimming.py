"""REST tool output trimming: .og field projection + a generic size cap.

Keeps tool results (and token cost) tight — e.g. fetch_wiki_summary returns only
title/extract instead of the full Wikipedia REST JSON.
"""

from __future__ import annotations

import json

from hachi.core.loop import ToolRegistry
from hachi.core.rest_adapter import (
    _MAX_REST_RESPONSE_CHARS,
    UniversalRestAdapter,
    _truncate_rest_response,
)

_BEGIN = "<<<UNTRUSTED_CONTENT_BEGIN>>>\n"
_END = "\n<<<UNTRUSTED_CONTENT_END>>>"


def _unwrap(out: str) -> str:
    """Extract inner content from a guard_untrusted data envelope (SEC-002).

    REST responses are now framed as untrusted data; the projected/truncated
    payload lives inside the markers.
    """
    if _BEGIN in out and _END in out:
        return out.split(_BEGIN, 1)[1].rsplit(_END, 1)[0]
    return out


def _register(monkeypatch, payload: dict, api_def: dict) -> ToolRegistry:
    registry = ToolRegistry()

    class _FakeResponse:
        status_code = 200
        text = json.dumps(payload)

        def raise_for_status(self) -> None:
            return

        def json(self) -> dict:
            return payload

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            return

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return

        def request(self, **_kwargs):
            return _FakeResponse()

    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    monkeypatch.setattr("hachi.core.rest_adapter.httpx.Client", _FakeClient)
    # BB-53: an empty allowlist now fails closed — this test is about response
    # trimming/projection, not the allowlist, so allowlist the host under test explicitly.
    adapter = UniversalRestAdapter(registry, allowed_hosts=["127.0.0.1"])
    base = {"method": "GET", "endpoint": "http://127.0.0.1:9000/x", "schema": "{}", "headers": "{}"}
    base.update(api_def)
    adapter._register_single_api(tool_name="api", api_def=base, node_name="n")
    return registry


def test_field_projection_returns_only_declared_fields(monkeypatch) -> None:
    payload = {
        "title": "Sunflower",
        "extract": "A tall plant.",
        "extract_html": "<p>huge html blob</p>",
        "thumbnail": {"source": "x"},
        "namespace": {"id": 0},
    }
    registry = _register(monkeypatch, payload, {"fields": "title, extract"})
    result = json.loads(_unwrap(registry._tools["api"]()))
    assert result == {"title": "Sunflower", "extract": "A tall plant."}
    assert "extract_html" not in result and "thumbnail" not in result


def test_projection_falls_back_to_full_when_no_field_matches(monkeypatch) -> None:
    payload = {"a": 1, "b": 2}
    registry = _register(monkeypatch, payload, {"fields": "nonexistent"})
    assert json.loads(_unwrap(registry._tools["api"]())) == payload  # not an empty dict


def test_no_fields_directive_returns_full_response(monkeypatch) -> None:
    payload = {"a": 1, "b": 2}
    registry = _register(monkeypatch, payload, {})
    assert json.loads(_unwrap(registry._tools["api"]())) == payload


def test_oversized_response_is_truncated_with_guidance(monkeypatch) -> None:
    payload = {"data": "x" * (_MAX_REST_RESPONSE_CHARS + 5_000)}
    registry = _register(monkeypatch, payload, {})
    out = registry._tools["api"]()
    inner = _unwrap(out)  # truncation cap applies to the content inside the envelope
    assert len(inner) <= _MAX_REST_RESPONSE_CHARS + 200  # cap plus a short notice
    assert "truncated" in inner and "fields=" in inner


def test_truncate_helper_passthrough_when_within_limit() -> None:
    assert _truncate_rest_response("short text") == "short text"
