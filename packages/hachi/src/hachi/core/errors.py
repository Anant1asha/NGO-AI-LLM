"""Structured exception hierarchy for the Hachi agent engine.

All domain exceptions inherit from :class:`HachiError` so callers can catch
the base class for a broad sweep or a specific subclass for targeted handling.

HTTP status codes are advisory — they are used by the gateway layer when
converting exceptions into HTTP responses, but have no effect in non-HTTP
contexts (TUI, sub-agents, tests).
"""

from __future__ import annotations

from typing import Any


class HachiError(Exception):
    """Base class for all Hachi domain exceptions.

    Attributes:
        code:        Machine-readable short string identifying the error class
                     (e.g. ``"og.parse_error"``).  Dot-namespaced by domain.
        detail:      Human-readable description of what went wrong.
        http_status: Advisory HTTP status code for gateway-layer translation.
                     Defaults to 500 (internal error).
        context:     Optional mapping of extra diagnostic key/value pairs that
                     should be logged alongside the error but not necessarily
                     exposed to end-users.
    """

    def __init__(
        self,
        detail: str = "",
        *,
        code: str = "hachi.error",
        http_status: int = 500,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http_status = http_status
        self.context: dict[str, Any] = context or {}

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"code={self.code!r}, "
            f"http_status={self.http_status}, "
            f"detail={self.detail!r})"
        )


# ---------------------------------------------------------------------------
# ObjectGraph (.og) errors
# ---------------------------------------------------------------------------


class OGParseError(HachiError):
    """Raised when the parser encounters malformed ObjectGraph syntax."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "og.parse_error")
        kwargs.setdefault("http_status", 422)
        super().__init__(detail, **kwargs)


class OGValidationError(HachiError):
    """Raised during Stage 3 Verification if a .og file violates accuracy thresholds."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "og.validation_error")
        kwargs.setdefault("http_status", 422)
        super().__init__(detail, **kwargs)


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class ConfigError(HachiError):
    """Raised when agent configuration is invalid or cannot be loaded."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "config.error")
        kwargs.setdefault("http_status", 500)
        super().__init__(detail, **kwargs)


class ConfigPermissionError(ConfigError):
    """Raised when an agent tries to write a configuration key it is not allowed to touch."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "config.permission_denied")
        kwargs.setdefault("http_status", 403)
        super().__init__(detail, **kwargs)


# ---------------------------------------------------------------------------
# Tool / MCP errors
# ---------------------------------------------------------------------------


class ToolError(HachiError):
    """Raised when a tool call fails in an unrecoverable way."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "tool.error")
        kwargs.setdefault("http_status", 500)
        super().__init__(detail, **kwargs)


class MCPError(ToolError):
    """Raised when communication with an MCP server subprocess fails."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "tool.mcp_error")
        kwargs.setdefault("http_status", 502)
        super().__init__(detail, **kwargs)


# ---------------------------------------------------------------------------
# Permission / security errors
# ---------------------------------------------------------------------------


class PermissionDeniedError(HachiError):
    """Raised by the PermissionGate when an action exceeds the configured tier."""

    def __init__(self, detail: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("code", "permission.denied")
        kwargs.setdefault("http_status", 403)
        super().__init__(detail, **kwargs)
