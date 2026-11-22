"""Vision routing gate tests — 3-way capability check (Design doc 20 §3).

Tests:
  (a) Session model HAS VISION → inline path; no extra call to a router.
  (b) Session model LACKS VISION + a configured vision candidate → routed to
      the vision model; returns its analysis.
  (c) No vision model configured anywhere → graceful text fallback.

All with mocked clients/router — NO network.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from hachi.core.llm import LLMResponse
from hachi.core.loop import ToolRegistry
from hachi.core.tool_results import ToolResultBlocks
from hachi.tools.vision_tools import _make_view_image, register_vision_tools

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# A valid 1×1 transparent PNG (~68 bytes).
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class _Result:
    def __init__(self, allowed: bool, reason: str = "") -> None:
        self.allowed = allowed
        self.reason = reason


class _Gate:
    def __init__(self, tier: str = "guided", allowed: bool = True) -> None:
        self.tier = tier
        self._allowed = allowed
        self.max_file_size_bytes = 10 * 1024 * 1024

    def check_path(self, path: str, mode: str) -> _Result:
        return _Result(self._allowed, "" if self._allowed else "path not allowed")


def _write_png(tmp_path: Path, name: str = "shot.png") -> Path:
    p = tmp_path / name
    p.write_bytes(_PNG_1X1)
    return p


# ---------------------------------------------------------------------------
# Mock LLM client helpers
# ---------------------------------------------------------------------------


class _VisionCapableClient:
    """Mock session client whose model has VISION — inline path triggers."""

    model = "claude-opus-4"
    supports_vision = True

    def generate(self, messages: Any, **_kw: Any) -> LLMResponse:
        raise AssertionError("Should not call generate on session client in inline path")


class _NoVisionClient:
    """Mock session client whose model lacks VISION."""

    model = "claude-haiku-4-5"
    supports_vision = False

    def generate(self, messages: Any, **_kw: Any) -> LLMResponse:
        raise AssertionError("Should not call generate on non-vision client")


class _RoutedVisionClient:
    """Mock vision client returned by the router; returns a fixed analysis."""

    model = "gpt-4o"

    def generate(self, messages: Any, **_kw: Any) -> LLMResponse:
        return LLMResponse(content="Vision analysis: a tiny transparent pixel.")


# ---------------------------------------------------------------------------
# Mock router
# ---------------------------------------------------------------------------


class _MockRouteResult:
    def __init__(self, client: Any, provider: str) -> None:
        self.client = client
        self.descriptor = MagicMock()
        self.descriptor.provider = provider


class _RouterWithVision:
    """Router that returns a vision-capable client."""

    def __init__(self, vision_client: Any) -> None:
        self._vision_client = vision_client

    def select(self, capability: Any, constraints: Any = None) -> Any:
        from hachi.core.routing.capability import Capability

        if capability == Capability.VISION:
            return _MockRouteResult(self._vision_client, "openai")
        raise RuntimeError(f"Unexpected capability: {capability}")


class _RouterNoVision:
    """Router that raises NoRouteError for VISION."""

    def select(self, capability: Any, constraints: Any = None) -> Any:
        from hachi.core.routing.capability import Capability
        from hachi.core.routing.router import NoRouteError

        if capability == Capability.VISION:
            raise NoRouteError(Capability.VISION, "no vision candidates configured")
        raise RuntimeError(f"Unexpected capability: {capability}")


# ---------------------------------------------------------------------------
# Test (a): session model HAS vision → inline path, ToolResultBlocks returned
# ---------------------------------------------------------------------------


def test_vision_gate_a_inline_when_session_has_vision(tmp_path: Path) -> None:
    """Gate (a): session model has VISION → inline ToolResultBlocks, no router call."""
    img = _write_png(tmp_path)
    router = _RouterWithVision(_RoutedVisionClient())
    client = _VisionCapableClient()

    view = _make_view_image(
        _Gate("guided"),
        "anthropic",
        session_client=client,
        router=router,
    )
    result = view(str(img), prompt="what is in this image?")

    # Must be a ToolResultBlocks (inline path), NOT a string analysis.
    assert isinstance(result, ToolResultBlocks), f"Expected ToolResultBlocks, got: {type(result)}"
    # Inline path → Anthropic image block format.
    image_blocks = [b for b in result.blocks if b.get("type") == "image"]
    assert len(image_blocks) == 1, "Inline path should produce one image block"
    assert image_blocks[0]["source"]["type"] == "base64"


def test_vision_gate_a_inline_by_model_name_lookup(tmp_path: Path) -> None:
    """Gate (a) variant: supports_vision=False but model is in bundled VISION registry."""
    img = _write_png(tmp_path)

    # Client whose supports_vision property returns False but whose model name
    # is a vision model in the bundled defaults table.
    class _FallbackVisionClient:
        model = "claude-opus-4"
        supports_vision = False  # property not overridden yet

    view = _make_view_image(
        _Gate("guided"),
        "anthropic",
        session_client=_FallbackVisionClient(),
        router=None,
    )
    result = view(str(img))

    # _model_has_vision("claude-opus-4") → True → inline path.
    assert isinstance(result, ToolResultBlocks)


# ---------------------------------------------------------------------------
# Test (b): session model LACKS vision + router has a vision candidate → routed
# ---------------------------------------------------------------------------


def test_vision_gate_b_routes_to_vision_model(tmp_path: Path) -> None:
    """Gate (b): session model lacks VISION, router has a candidate → routed analysis."""
    img = _write_png(tmp_path)
    router = _RouterWithVision(_RoutedVisionClient())
    client = _NoVisionClient()

    view = _make_view_image(
        _Gate("guided"),
        "anthropic",
        session_client=client,
        router=router,
    )
    result = view(str(img), prompt="describe it")

    # Routed path returns a plain string analysis.
    assert isinstance(result, str), f"Expected str from routed path, got: {type(result)}"
    assert "Vision analysis" in result, f"Expected vision analysis text, got: {result!r}"
    assert "a tiny transparent pixel" in result


def test_vision_gate_b_routed_uses_resolved_provider_format(tmp_path: Path) -> None:
    """Gate (b): image blocks sent to the routed vision model use the resolved provider format."""
    img = _write_png(tmp_path)

    captured_messages: list[Any] = []

    class _CapturingVisionClient:
        model = "gpt-4o"

        def generate(self, messages: Any, **_kw: Any) -> LLMResponse:
            captured_messages.extend(messages)
            return LLMResponse(content="saw an image")

    router = _RouterWithVision(_CapturingVisionClient())
    view = _make_view_image(
        _Gate("guided"),
        "anthropic",  # session provider = anthropic
        session_client=_NoVisionClient(),
        router=router,
    )
    view(str(img))

    # Router resolved provider="openai" → OpenAI-compat image_url block.
    assert captured_messages, "Vision model should have received messages"
    content = captured_messages[0].content
    image_url_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "image_url"]
    assert len(image_url_blocks) == 1, (
        f"Expected one image_url block for openai provider, blocks: {content}"
    )


# ---------------------------------------------------------------------------
# Test (c): no vision model configured → graceful text fallback
# ---------------------------------------------------------------------------


def test_vision_gate_c_graceful_fallback_no_router(tmp_path: Path) -> None:
    """Gate (c): no router, non-vision provider → graceful text fallback with hint."""
    img = _write_png(tmp_path)

    # A provider that doesn't support vision (e.g., ollama text-only).
    class _TextOnlyClient:
        model = "llama3"
        supports_vision = False

    view = _make_view_image(
        _Gate("guided"),
        "ollama",  # non-vision provider kind
        session_client=_TextOnlyClient(),
        router=None,
    )
    result = view(str(img))

    assert isinstance(result, str)
    assert "no vision-capable" in result or "configure a vision model" in result.lower()


def test_vision_gate_c_graceful_fallback_router_no_candidate(tmp_path: Path) -> None:
    """Gate (c): router raises NoRouteError → graceful fallback with clear hint."""
    img = _write_png(tmp_path)

    view = _make_view_image(
        _Gate("guided"),
        "ollama",
        session_client=_NoVisionClient(),
        router=_RouterNoVision(),
    )
    result = view(str(img))

    assert isinstance(result, str)
    # Should include a hint about configuring a vision model.
    lower = result.lower()
    assert "vision" in lower and ("configure" in lower or "no vision" in lower)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_vision_tools_with_router() -> None:
    """register_vision_tools accepts session_client and router kwargs."""
    registry = ToolRegistry()
    router = _RouterWithVision(_RoutedVisionClient())
    register_vision_tools(
        registry,
        _Gate("guided"),
        provider_kind="anthropic",
        session_client=_VisionCapableClient(),
        router=router,
    )
    names = {schema["name"] for schema in registry.get_schemas()}
    assert "view_image" in names
    assert "vision" in registry.available_groups()
