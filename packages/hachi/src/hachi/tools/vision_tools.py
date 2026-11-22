"""Vision input tool — let the agent *look at* an image (local file or URL).

``view_image`` reads an image (a local file path **or** an http(s) URL), base64-
encodes it, and returns it as an Anthropic image content block (wrapped in
:class:`ToolResultBlocks`) so the model sees the actual pixels on its next turn and
can describe / reason about them. This is the multimodal-input capability
(screenshots, photos, diagrams, charts) that brings Hachi to parity with
assistants that accept images.

Design notes:
    - **Provider-gated.** Anthropic and OpenAI-compatible providers receive native
      image blocks (different wire formats). Providers without vision support (e.g.,
      Ollama running a text-only model) receive a plain-text fallback notice so the
      agent can still communicate the limitation without crashing the request.
    - **Permission-gated.** Local reads go through the same ``PermissionGate`` path
      check as ``read_file``; URL fetches are SSRF-validated via ``net_guard``. The
      whole tool is disabled in the ``sandbox`` tier.
    - **Auto-resize.** Images exceeding 8000 px on any dimension (Anthropic API hard
      limit) are transparently downscaled via Pillow before encoding, preserving
      aspect ratio. Requires ``Pillow>=10`` (declared in project deps).
"""

from __future__ import annotations

import base64
import io
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from hachi.core.net_guard import validate_outbound_url
from hachi.core.tool_results import ToolResultBlocks
from hachi.tools.os_tools import _normalize_user_path

# Anthropic-decodable image media types, keyed by lowercased file extension.
_MEDIA_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_VALID_MEDIA: set[str] = set(_MEDIA_TYPES.values())

# Hard ceiling on the raw image bytes we will encode. Anthropic rejects images
# above ~5 MB; cap here so we fail fast with a friendly message instead of a 400.
_MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Anthropic rejects images where either dimension exceeds this pixel count.
_MAX_IMAGE_DIM = 8000

_MEDIA_TO_PIL_FORMAT: dict[str, str] = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/gif": "GIF",
    "image/webp": "WEBP",
}


def _resize_if_needed(raw: bytes, media_type: str) -> tuple[bytes, str]:
    """Downscale *raw* so neither dimension exceeds ``_MAX_IMAGE_DIM``.

    Returns the (possibly re-encoded) bytes and the (possibly updated) media_type.
    GIF inputs are converted to PNG on resize because PIL cannot write animated GIF
    with a simple thumbnail call and the Anthropic API doesn't benefit from animation.
    """
    from PIL import Image  # noqa: PLC0415 — imported here so the dep is optional at import time

    with Image.open(io.BytesIO(raw)) as img:
        w, h = img.size
        if w <= _MAX_IMAGE_DIM and h <= _MAX_IMAGE_DIM:
            return raw, media_type

        # Scale down so the larger dimension equals _MAX_IMAGE_DIM.
        scale = _MAX_IMAGE_DIM / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        resized = img.resize(new_size, Image.LANCZOS)  # type: ignore[attr-defined]

        out_media = media_type if media_type != "image/gif" else "image/png"
        pil_fmt = _MEDIA_TO_PIL_FORMAT.get(out_media, "PNG")

        # JPEG doesn't support alpha; convert RGBA→RGB.
        if pil_fmt == "JPEG" and resized.mode in ("RGBA", "P"):
            resized = resized.convert("RGB")

        buf = io.BytesIO()
        resized.save(buf, format=pil_fmt)
        return buf.getvalue(), out_media


# Browsing/vision is meaningless (and disabled) in the read-only sandbox tier.
_BLOCKED_TIERS = {"sandbox"}

VIEW_IMAGE_SCHEMA: dict[str, Any] = {
    "name": "view_image",
    "description": (
        "Look at an image — a local file (screenshot, photo, diagram, chart, scanned "
        "document) OR an http(s) image URL — so you can describe or reason about its "
        "visual contents. Use this whenever the user references an image/screenshot or "
        "asks what something looks like. Supported formats: PNG, JPEG, GIF, WebP."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Local image path (absolute, ~, or relative) OR an http(s) image URL."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Optional focus for the analysis, e.g. 'read the error message' "
                    "or 'summarize the chart'. Defaults to a general description."
                ),
            },
        },
        "required": ["path"],
    },
}


def _tier_blocked(gate: Any | None) -> str | None:
    """Return the blocking tier name if vision is disallowed, else None."""
    if gate is None:
        return None
    tier = getattr(gate, "tier", None)
    return tier if tier in _BLOCKED_TIERS else None


def _allow_private() -> bool:
    return os.environ.get("HACHI_REST_ALLOW_PRIVATE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _too_large(size: int, limit: int) -> str:
    return f"Error: image is {size // 1024} KB, exceeding the {limit // 1024} KB limit for viewing."


def _sniff_image_media_type(raw: bytes) -> str | None:
    """Infer an image media type from magic bytes.

    Used when the file has no usable extension — e.g. content-addressed
    attachment blobs are stored under their SHA-256 digest with no suffix, so
    extension-based lookup fails. Covers the four formats Anthropic decodes.
    """
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(raw) >= 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _is_managed_blob(target: Path) -> bool:
    """True when *target* lives under Hachi's managed attachment blob store.

    Files the user explicitly uploaded through the app are first-party content
    and always readable by ``view_image`` — the blob directory is an internal
    managed location, not a user-configured device-permission filesystem root,
    so it would otherwise be denied by the gate.
    """
    try:
        from hachi.core.paths import get_hachi_paths

        blobs = get_hachi_paths().blobs_dir.resolve()
        resolved = target.resolve()
        return resolved == blobs or blobs in resolved.parents
    except Exception:
        return False


def _read_local_image(path: str, gate: Any | None) -> tuple[bytes, str, str] | str:
    """Return ``(raw_bytes, media_type, label)`` for a local image, or an error string."""
    target = _normalize_user_path(path)
    # Managed attachment blobs bypass the device-permission filesystem roots:
    # they are first-party content the user uploaded through the app, and the
    # blob dir is never one of the user's configured allowed_paths.
    if gate is not None and not _is_managed_blob(target):
        check = gate.check_path(str(target), "read")
        if not getattr(check, "allowed", True):
            return f"Permission Denied: {getattr(check, 'reason', 'path not allowed')}"
    if not target.exists() or not target.is_file():
        return f"Error: image file not found: {target}"
    try:
        raw = target.read_bytes()
    except OSError as exc:
        return f"Error reading image: {exc}"
    # Prefer the file extension; fall back to magic-byte sniffing for
    # extension-less files (e.g. content-addressed attachment blobs).
    media_type = _MEDIA_TYPES.get(target.suffix.lower()) or _sniff_image_media_type(raw)
    if media_type is None:
        return (
            f"Error: unsupported image type '{target.suffix or '(none)'}'. "
            f"Supported: {', '.join(sorted(_MEDIA_TYPES))}."
        )
    gate_cap = getattr(gate, "max_file_size_bytes", None) if gate is not None else None
    limit = min(_MAX_IMAGE_BYTES, gate_cap) if isinstance(gate_cap, int) else _MAX_IMAGE_BYTES
    if len(raw) > limit:
        return _too_large(len(raw), limit)
    return raw, media_type, str(target)


def _fetch_url_image(url: str) -> tuple[bytes, str, str] | str:
    """Download an image from an http(s) URL. Returns ``(raw, media_type, label)`` or an error."""
    ok, reason = validate_outbound_url(url, allow_private=_allow_private())
    if not ok:
        return f"Blocked URL: {reason}"
    try:
        # follow_redirects=False: a redirect to an internal host would bypass the
        # SSRF check above (consistent with the REST adapter / browser policy).
        with httpx.Client(timeout=15.0, follow_redirects=False) as client:
            resp = client.get(url)
            resp.raise_for_status()
            raw = resp.content
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    except httpx.HTTPStatusError as exc:
        return f"Error fetching image: HTTP {exc.response.status_code}"
    except Exception as exc:
        return f"Error fetching image: {exc}"

    media_type = (
        ctype
        if ctype in _VALID_MEDIA
        else _MEDIA_TYPES.get(Path(urlparse(url).path).suffix.lower())
    )
    if media_type is None:
        return (
            f"Error: URL did not return a supported image (content-type: "
            f"{ctype or 'unknown'}). Supported: PNG, JPEG, GIF, WebP."
        )
    if len(raw) > _MAX_IMAGE_BYTES:
        return _too_large(len(raw), _MAX_IMAGE_BYTES)
    return raw, media_type, url


def _model_has_vision(model_id: str) -> bool:
    """Return ``True`` when *model_id* is in the bundled registry with VISION capability.

    Used as a fallback when the client's ``supports_vision`` property returns ``False``
    (i.e. the concrete client class hasn't overridden it yet).  This keeps the inline
    path working for existing Anthropic/OpenAI clients whose model supports vision.
    """
    if not model_id:
        return False
    try:
        from hachi.core.routing.capability import Capability
        from hachi.core.routing.descriptor import BUNDLED_MODEL_DEFAULTS

        for desc in BUNDLED_MODEL_DEFAULTS:
            if desc.id == model_id and Capability.VISION in desc.capabilities:
                return True
    except Exception:
        pass
    return False


_OPENAI_COMPAT_KINDS: frozenset[str] = frozenset(
    {
        "openai",
        "openai-compatible",
        "openrouter",
        "groq",
        "together",
        "deepseek",
        "gemini",
    }
)


def _provider_is_anthropic(provider_kind: str) -> bool:
    return provider_kind.lower() == "anthropic"


def _provider_is_openai_compat(provider_kind: str) -> bool:
    return provider_kind.lower() in _OPENAI_COMPAT_KINDS


def _build_image_blocks(
    raw: bytes, media_type: str, label: str, focus: str, is_anthropic: bool
) -> list[dict[str, Any]]:
    """Build provider-aware image content blocks.

    Returns Anthropic image blocks when *is_anthropic* is True; otherwise
    builds OpenAI-compatible ``image_url`` data-URL blocks.
    """
    data = base64.b64encode(raw).decode("ascii")
    size_kb = max(1, len(raw) // 1024)
    caption = f"Loaded image '{label}' ({size_kb} KB, {media_type}). {focus}"

    if is_anthropic:
        return [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            },
            {"type": "text", "text": caption},
        ]
    else:
        data_url = f"data:{media_type};base64,{data}"
        return [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": caption},
        ]


def _make_view_image(
    gate: Any | None,
    provider_kind: str,
    *,
    session_client: Any | None = None,
    router: Any | None = None,
) -> Callable[..., ToolResultBlocks | str]:
    """Build the ``view_image`` callable.

    Implements the 3-way capability gate (Design doc 20 §3):

    1. Session model HAS Capability.VISION → inline (today's fast path, no extra call).
    2. Session model LACKS vision AND a vision candidate is configured →
       ``router.select(VISION)`` routes to the vision model; its textual analysis
       is folded back as the tool result string.
    3. No vision model configured anywhere → graceful text fallback with a clear hint.

    The ``provider_kind`` string is retained for image-block format selection
    (Anthropic vs OpenAI-compat wire format) per the RESOLVED provider.

    Args:
        gate: Optional PermissionGate (path checks + tier gating).
        provider_kind: Primary session provider kind string; used as format fallback
            when routing is unavailable.
        session_client: Optional BaseLLMClient for the session model.  When it
            exposes ``supports_vision=True`` the inline path is taken.
        router: Optional ModelRouter (from Slice 2.1).  Used to resolve a vision
            client when the session model lacks vision.
    """

    def view_image(path: str, prompt: str = "") -> ToolResultBlocks | str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: viewing images is disabled in '{tier}' tier."

        is_url = path.strip().lower().startswith(("http://", "https://"))
        loaded = _fetch_url_image(path.strip()) if is_url else _read_local_image(path, gate)
        if isinstance(loaded, str):
            return loaded  # error message
        raw, media_type, label = loaded

        focus = prompt.strip() or "Describe what you see and use it to answer the user's request."

        # ------------------------------------------------------------------
        # 3-way routing gate (doc 20 §3)
        # ------------------------------------------------------------------

        # Step 1: does the session client itself support vision?
        # Check the client's supports_vision property (base class returns False;
        # ResilientClient delegates to inner).  If unavailable, fall back to a
        # bundled-registry lookup by model name so existing clients that haven't
        # overridden the property still benefit from the inline path.
        session_has_vision = bool(getattr(session_client, "supports_vision", False))
        if not session_has_vision and session_client is not None:
            session_has_vision = _model_has_vision(getattr(session_client, "model", ""))

        if session_has_vision:
            # Fast path: inline — no extra call.
            raw, media_type = _resize_if_needed(raw, media_type)
            size_kb = max(1, len(raw) // 1024)
            is_anth = _provider_is_anthropic(provider_kind)
            blocks = _build_image_blocks(raw, media_type, label, focus, is_anthropic=is_anth)
            return ToolResultBlocks(
                blocks=blocks, summary=f"Loaded image {label} ({media_type}, {size_kb} KB)"
            )

        # Step 2: try to route to a vision-capable model.
        if router is not None:
            try:
                from hachi.core.llm import Message
                from hachi.core.routing.capability import Capability
                from hachi.core.routing.router import NoRouteError, RouteConstraints

                resolved = router.select(Capability.VISION, RouteConstraints(needs_vision=True))
                vision_client = resolved.client
                vision_provider = resolved.descriptor.provider

                # Resize before encoding.
                raw, media_type = _resize_if_needed(raw, media_type)
                size_kb = max(1, len(raw) // 1024)
                is_anth = _provider_is_anthropic(vision_provider)
                image_blocks = _build_image_blocks(
                    raw, media_type, label, focus, is_anthropic=is_anth
                )

                # Build a minimal one-turn conversation for the vision model.
                vision_messages = [Message(role="user", content=image_blocks)]
                _vision_sys = (
                    "You are a vision analysis assistant. "
                    "Describe the image and answer the user's question concisely."
                )
                vision_resp = vision_client.generate(
                    vision_messages,
                    system_prompt=_vision_sys,
                )
                analysis = (vision_resp.content or "").strip() or "(no analysis returned)"
                return f"[Vision analysis of '{label}' via {vision_provider}] {analysis}"
            except NoRouteError:
                # Fall through to graceful fallback (Step 3).
                pass
            except Exception:
                # Routing error — fall through gracefully.
                pass

        # Step 3: no vision capability anywhere.
        size_kb = max(1, len(raw) // 1024)

        # For known vision providers (inline path was skipped only because
        # session_client is None/unknown) still send the image block.
        if _provider_is_anthropic(provider_kind) or _provider_is_openai_compat(provider_kind):
            raw, media_type = _resize_if_needed(raw, media_type)
            size_kb = max(1, len(raw) // 1024)
            is_anth = _provider_is_anthropic(provider_kind)
            blocks = _build_image_blocks(raw, media_type, label, focus, is_anthropic=is_anth)
            return ToolResultBlocks(
                blocks=blocks, summary=f"Loaded image {label} ({media_type}, {size_kb} KB)"
            )

        return (
            f"Image '{label}' ({size_kb} KB, {media_type}) was loaded, but no vision-capable "
            f"model is available. Configure a vision model (e.g. claude-opus-4 or gpt-4o) "
            f"under [routing.capabilities].vision in settings.toml to enable image analysis."
        )

    return view_image


def register_vision_tools(
    registry: Any,
    gate: Any | None = None,
    provider_kind: str = "anthropic",
    *,
    session_client: Any | None = None,
    router: Any | None = None,
) -> None:
    """Register the ``view_image`` tool under the lazy ``vision`` group.

    Args:
        registry: The ToolRegistry to register into.
        gate: Optional PermissionGate (path checks + tier gating).
        provider_kind: Active provider kind string (e.g. ``"anthropic"``). Used
            for image-block format selection when the inline path is taken.
        session_client: Optional BaseLLMClient for the session model.  When its
            ``supports_vision`` property returns ``True`` the inline path is used.
        router: Optional ModelRouter.  When provided and the session model lacks
            vision, the router selects a vision-capable model for the analysis call.
    """
    registry.register(
        VIEW_IMAGE_SCHEMA,
        _make_view_image(gate, provider_kind, session_client=session_client, router=router),
        group="vision",
    )
