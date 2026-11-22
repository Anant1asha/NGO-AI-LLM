"""Tests for view_image http(s) URL support (download + SSRF guard + media typing)."""

from __future__ import annotations

import base64

import httpx

import hachi.tools.vision_tools as vt
from hachi.core.tool_results import ToolResultBlocks
from hachi.tools.vision_tools import _make_view_image

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
_URL = "https://example.com/pic.png"


class _Gate:
    def __init__(self, tier: str = "guided") -> None:
        self.tier = tier


def _patch_response(monkeypatch, response: httpx.Response) -> None:
    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_a) -> None:
            return

        def get(self, _url: str) -> httpx.Response:
            return response

    monkeypatch.setattr(vt.httpx, "Client", lambda **_kw: _FakeClient())


def _resp(status: int, content: bytes = _PNG, ctype: str = "image/png", url: str = _URL):
    return httpx.Response(
        status, content=content, headers={"content-type": ctype}, request=httpx.Request("GET", url)
    )


def test_url_png_returns_image_block(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")  # skip DNS in net_guard
    _patch_response(monkeypatch, _resp(200))
    out = _make_view_image(_Gate(), provider_kind="anthropic")(_URL)
    assert isinstance(out, ToolResultBlocks)
    img = next(b for b in out.blocks if b["type"] == "image")
    assert img["source"]["media_type"] == "image/png"
    assert base64.b64decode(img["source"]["data"]) == _PNG
    assert _URL in out.summary


def test_url_media_type_from_content_type(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    _patch_response(monkeypatch, _resp(200, ctype="image/jpeg"))
    out = _make_view_image(_Gate(), provider_kind="anthropic")(_URL)
    assert isinstance(out, ToolResultBlocks)
    assert out.blocks[0]["source"]["media_type"] == "image/jpeg"


def test_url_falls_back_to_extension_when_content_type_generic(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    _patch_response(monkeypatch, _resp(200, ctype="application/octet-stream"))
    out = _make_view_image(_Gate(), provider_kind="anthropic")(_URL)  # url ends .png
    assert isinstance(out, ToolResultBlocks)
    assert out.blocks[0]["source"]["media_type"] == "image/png"


def test_url_non_image_is_error(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    resp = _resp(200, ctype="text/html", url="https://example.com/page")
    _patch_response(monkeypatch, resp)
    out = _make_view_image(_Gate(), provider_kind="anthropic")("https://example.com/page")
    assert isinstance(out, str)
    assert "did not return a supported image" in out


def test_url_too_large(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    big = b"x" * (vt._MAX_IMAGE_BYTES + 10)
    _patch_response(monkeypatch, _resp(200, content=big))
    out = _make_view_image(_Gate(), provider_kind="anthropic")(_URL)
    assert isinstance(out, str)
    assert "exceeding" in out


def test_url_http_error(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    _patch_response(monkeypatch, _resp(404))
    out = _make_view_image(_Gate(), provider_kind="anthropic")(_URL)
    assert isinstance(out, str)
    assert "HTTP 404" in out


def test_url_blocked_by_ssrf_guard(monkeypatch) -> None:
    # Loopback host, private egress not allowed → blocked before any fetch.
    monkeypatch.delenv("HACHI_REST_ALLOW_PRIVATE", raising=False)
    out = _make_view_image(_Gate(), provider_kind="anthropic")("http://127.0.0.1/x.png")
    assert isinstance(out, str)
    assert "Blocked URL" in out


def test_url_blocked_in_sandbox_tier(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    out = _make_view_image(_Gate("sandbox"), provider_kind="anthropic")(_URL)
    assert isinstance(out, str)
    assert "Permission Denied" in out and "sandbox" in out


def test_url_non_openai_compat_returns_text(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    _patch_response(monkeypatch, _resp(200))
    out = _make_view_image(_Gate(), provider_kind="ollama")(_URL)
    assert isinstance(out, str)
    # New graceful fallback message (doc 20 §3 step 4).
    assert "no vision-capable" in out or "configure a vision model" in out.lower()
