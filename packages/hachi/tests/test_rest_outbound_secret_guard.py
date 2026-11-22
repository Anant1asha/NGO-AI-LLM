"""REST adapter must redact accidental provider secrets from outbound requests."""

from __future__ import annotations

from hachi.core.loop import ToolRegistry
from hachi.core.rest_adapter import UniversalRestAdapter

_SECRET = "sk-ant-" + "a" * 40


def _register(monkeypatch, method: str = "GET"):
    registry = ToolRegistry()
    captured: dict = {}

    class _FakeResponse:
        status_code = 200
        text = "{}"

        def raise_for_status(self) -> None:
            return

        def json(self) -> dict:
            return {"ok": True}

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            return

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return

        def request(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    monkeypatch.setattr("hachi.core.rest_adapter.httpx.Client", _FakeClient)
    # BB-53: an empty allowlist now fails closed — this test is about outbound
    # secret redaction, not the allowlist, so allowlist the host under test explicitly.
    adapter = UniversalRestAdapter(registry, allowed_hosts=["127.0.0.1"])
    api_def = {
        "method": method,
        "endpoint": "http://127.0.0.1:9000/x",
        "schema": "{}",
        "headers": "{}",
    }
    adapter._register_single_api(tool_name="api", api_def=api_def, node_name="n")
    return registry, captured


def test_secret_in_query_param_is_redacted(monkeypatch) -> None:
    registry, captured = _register(monkeypatch, method="GET")
    registry._tools["api"](token=_SECRET)
    assert captured["params"]["token"] == "[REDACTED SECRET]"


def test_secret_in_json_body_is_redacted(monkeypatch) -> None:
    registry, captured = _register(monkeypatch, method="POST")
    registry._tools["api"](data=_SECRET)
    assert captured["json"]["data"] == "[REDACTED SECRET]"


def test_ordinary_param_is_untouched(monkeypatch) -> None:
    # A generic third-party API key (no provider prefix) is NOT a scanner pattern.
    registry, captured = _register(monkeypatch, method="GET")
    registry._tools["api"](appid="abc123weatherkey")
    assert captured["params"]["appid"] == "abc123weatherkey"


def test_opt_out_env_keeps_secret(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", "true")
    registry, captured = _register(monkeypatch, method="GET")
    registry._tools["api"](token=_SECRET)
    assert captured["params"]["token"] == _SECRET
