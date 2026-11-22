"""Tests for unofficial web-session LLM providers.

These tests NEVER make real HTTP requests — all network calls are patched.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from hachi.core.unofficial_providers import (
    ChatGPTWebClient,
    _parse_sse_content,
    _resolve_access_token_or_use_directly,
)

# ---------------------------------------------------------------------------
# _parse_sse_content
# ---------------------------------------------------------------------------


def test_parse_sse_extracts_last_part() -> None:
    # ChatGPT sends the full accumulated text in each SSE tick.
    body = (
        'data: {"message": {"content": {"parts": ["Hello"]}}}\n'
        'data: {"message": {"content": {"parts": ["Hello world"]}}}\n'
        "data: [DONE]\n"
    )
    assert _parse_sse_content(body) == "Hello world"


def test_parse_sse_skips_done_and_empty() -> None:
    body = "data: [DONE]\ndata: \n"
    assert _parse_sse_content(body) == ""


def test_parse_sse_handles_malformed_json() -> None:
    body = "data: not-json\ndata: [DONE]\n"
    assert _parse_sse_content(body) == ""


def test_parse_sse_empty_body() -> None:
    assert _parse_sse_content("") == ""


# ---------------------------------------------------------------------------
# _resolve_access_token_or_use_directly
# ---------------------------------------------------------------------------


def test_resolve_uses_jwt_directly() -> None:
    # Looks like a JWT (header.payload.signature, short enough)
    fake_jwt = "eyJhbGc.eyJzdWIiOiJ1c2VyIn0.sig"
    result = _resolve_access_token_or_use_directly(fake_jwt)
    assert result == fake_jwt


def test_resolve_exchanges_session_cookie(monkeypatch: Any) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"accessToken": "tok-abc123"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        token = _resolve_access_token_or_use_directly("long-session-cookie-value-no-dots")
    assert token == "tok-abc123"
    mock_get.assert_called_once()


def test_resolve_raises_on_none() -> None:
    with pytest.raises(RuntimeError, match="No session token"):
        _resolve_access_token_or_use_directly(None)


def test_resolve_raises_when_no_access_token_in_response() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"error": "invalid"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="Could not obtain"):
            _resolve_access_token_or_use_directly("session-cookie-no-dots-here")


# ---------------------------------------------------------------------------
# ChatGPTWebClient — no session token
# ---------------------------------------------------------------------------


def test_no_session_token_returns_helpful_message() -> None:
    client = ChatGPTWebClient(session_token=None)
    # Patch _resolve to raise immediately (no network)
    with patch(
        "hachi.core.unofficial_providers._resolve_access_token_or_use_directly",
        side_effect=RuntimeError("No session token provided."),
    ):
        resp = client.generate([])
    assert "session token" in resp.content.lower() or "no session" in resp.content.lower()


# ---------------------------------------------------------------------------
# ChatGPTWebClient — successful generation
# ---------------------------------------------------------------------------


def _make_sse_body(text: str) -> str:
    return f'data: {{"message": {{"content": {{"parts": ["{text}"]}}}}}}\ndata: [DONE]\n'


def test_generate_returns_text_on_success() -> None:
    client = ChatGPTWebClient(session_token="eyJhbGc.eyJzdWIiOiJ1c2VyIn0.sig")

    mock_resp = MagicMock()
    mock_resp.text = _make_sse_body("The answer is 42.")
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_resp):
        result = client.generate([MagicMock(role="user", content="What is the answer?")])

    assert result.content == "The answer is 42."
    assert result.tool_calls == []


def test_generate_includes_system_prompt() -> None:
    client = ChatGPTWebClient(session_token="eyJhbGc.eyJ.sig")

    mock_resp = MagicMock()
    mock_resp.text = _make_sse_body("OK")
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        client.generate(
            messages=[MagicMock(role="user", content="hello")],
            system_prompt="You are a helpful assistant.",
        )

    call_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]["json"]
    messages = call_json["messages"]
    system_msg = next((m for m in messages if m["author"]["role"] == "system"), None)
    assert system_msg is not None
    assert "helpful assistant" in system_msg["content"]["parts"][0]


def test_generate_handles_401_and_clears_token() -> None:
    client = ChatGPTWebClient(session_token="eyJhbGc.eyJ.sig")
    client._access_token = "stale-token"

    mock_response = MagicMock(status_code=401)
    http_err = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)
    with patch("httpx.post", side_effect=http_err):
        result = client.generate([MagicMock(role="user", content="hi")])

    assert "expired" in result.content.lower() or "session" in result.content.lower()
    assert client._access_token is None


def test_generate_handles_generic_exception() -> None:
    client = ChatGPTWebClient(session_token="eyJhbGc.eyJ.sig")

    with patch("httpx.post", side_effect=ConnectionError("network unreachable")):
        result = client.generate([MagicMock(role="user", content="hi")])

    assert "error" in result.content.lower()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


def test_list_models_returns_known_models() -> None:
    client = ChatGPTWebClient(session_token="eyJhbGc.eyJ.sig")
    models = client.list_models()
    assert "gpt-4o" in models
    assert len(models) >= 3


# ---------------------------------------------------------------------------
# create_llm_client integration — gemini + chatgpt-web
# ---------------------------------------------------------------------------


def test_create_llm_client_gemini() -> None:
    from hachi.core.llm import OpenAICompatibleClient, create_llm_client

    client = create_llm_client({"kind": "gemini", "model": "gemini-2.0-flash"})
    assert isinstance(client, OpenAICompatibleClient)
    assert "generativelanguage" in client.base_url


def test_create_llm_client_gemini_default_model() -> None:
    from hachi.core.llm import OpenAICompatibleClient, create_llm_client

    # When the generic default is left, should resolve to gemini-2.0-flash.
    client = create_llm_client({"kind": "gemini"})
    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == "gemini-2.0-flash"


def test_create_llm_client_chatgpt_web(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_UNOFFICIAL", "1")
    from hachi.core.llm import create_llm_client

    client = create_llm_client(
        {"kind": "chatgpt-web", "model": "gpt-4o"},
    )
    assert isinstance(client, ChatGPTWebClient)
    assert client.model == "gpt-4o"


def test_create_llm_client_chatgpt_web_default_model(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_UNOFFICIAL", "1")
    from hachi.core.llm import create_llm_client

    client = create_llm_client({"kind": "chatgpt-web"})
    assert isinstance(client, ChatGPTWebClient)
    assert client.model == "gpt-4o"


def test_chatgpt_web_unavailable_without_opt_in(monkeypatch) -> None:
    """chatgpt-web raises a clear error when HACHI_UNOFFICIAL is not set."""
    monkeypatch.delenv("HACHI_UNOFFICIAL", raising=False)
    from hachi.core.llm import create_llm_client

    with pytest.raises(ValueError, match="HACHI_UNOFFICIAL"):
        create_llm_client({"kind": "chatgpt-web"})
