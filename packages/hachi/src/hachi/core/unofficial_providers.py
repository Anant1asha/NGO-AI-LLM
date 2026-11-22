"""Unofficial / web-session LLM providers.

These providers interact with AI platform web APIs that are not officially
supported for programmatic access.  They let users consume their existing
free-tier accounts without an API key.

IMPORTANT — Terms of Service warning
--------------------------------------
Web-session providers reverse-engineer the web interfaces of third-party
services.  Using them **may violate those services' Terms of Service** and
could result in account suspension.  Only use these providers on accounts
you own and with a full understanding of the risk.

Current providers
-----------------
ChatGPTWebClient  — gpt-4o / gpt-4-turbo via the ChatGPT.com web API.
                    Requires a ``session_token`` from the browser (the value
                    of the ``__Secure-next-auth.session-token`` cookie) or an
                    ``access_token`` from https://chatgpt.com/api/auth/session.

Getting a session token (Chrome / Edge)
-----------------------------------------
1. Open https://chatgpt.com and sign in.
2. Open DevTools (F12) → Application → Cookies → chatgpt.com.
3. Copy the value of ``__Secure-next-auth.session-token``.
4. Set it as ``CHATGPT_SESSION_TOKEN`` in your environment or ``settings.toml``.

Config example (settings.toml)
-------------------------------
```toml
[provider]
kind  = "chatgpt-web"
model = "gpt-4o"

[provider.secrets]
api_key_env = "CHATGPT_SESSION_TOKEN"
```
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from hachi.core.llm import BaseLLMClient, LLMResponse, Message, TokenUsage

logger = logging.getLogger(__name__)

_CHATGPT_AUTH_URL = "https://chatgpt.com/api/auth/session"
_CHATGPT_API_URL = "https://chatgpt.com/backend-api/conversation"
_CHATGPT_HEADERS = {
    "Accept": "text/event-stream",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin": "https://chatgpt.com",
    "Referer": "https://chatgpt.com/",
}

# Map our internal role names to ChatGPT web API roles.
_ROLE_MAP = {"user": "user", "assistant": "assistant", "system": "system"}


def _parse_sse_content(raw_body: str) -> str:
    """Extract concatenated text from a ChatGPT SSE stream."""
    collected: list[str] = []
    for line in raw_body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload in ("[DONE]", ""):
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        # Stream message delta
        parts = (
            data.get("message", {}).get("content", {}).get("parts", [])
            or data.get("choices", [{}])[0].get("delta", {}).get("content")
            and [data["choices"][0]["delta"]["content"]]
            or []
        )
        for part in parts:
            if isinstance(part, str) and part:
                collected.append(part)
    # Deduplicate prefix accumulation (ChatGPT sends the full text each tick).
    # Take only the last non-empty part if the stream accumulates.
    return collected[-1] if collected else ""


class ChatGPTWebClient(BaseLLMClient):
    """LLM client that speaks to the ChatGPT.com web API.

    This is an **unofficial** integration.  See module docstring for ToS notes.

    Parameters
    ----------
    session_token:
        The ``__Secure-next-auth.session-token`` cookie value (or an already-
        resolved access token).  If ``None`` the client attempts to read the
        token from the ``CHATGPT_SESSION_TOKEN`` env var at call time.
    model:
        ChatGPT model name as shown in the web interface (e.g. ``"gpt-4o"``).
    max_tokens:
        Not enforced by the web API; stored for interface compatibility.
    """

    def __init__(
        self,
        session_token: str | None = None,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
    ) -> None:
        self._session_token = session_token
        self.model = model
        self.max_tokens = max_tokens
        self._access_token: str | None = None

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _resolve_access_token(self) -> str:
        """Exchange a session cookie for a short-lived access token."""
        if not self._session_token:
            raise RuntimeError(
                "ChatGPT web provider: no session token configured.\n"
                "Set CHATGPT_SESSION_TOKEN in your environment or add\n"
                "  api_key_env = 'CHATGPT_SESSION_TOKEN'\n"
                "under [provider] in settings.toml.\n"
                "\n"
                "To obtain the token:\n"
                "  1. Open https://chatgpt.com and sign in.\n"
                "  2. DevTools → Application → Cookies → chatgpt.com.\n"
                "  3. Copy the value of __Secure-next-auth.session-token."
            )

        cookies = {"__Secure-next-auth.session-token": self._session_token}
        response = httpx.get(_CHATGPT_AUTH_URL, cookies=cookies, headers=_CHATGPT_HEADERS)
        response.raise_for_status()
        data = response.json()
        token = data.get("accessToken")
        if not token:
            raise RuntimeError(
                "ChatGPT web provider: could not obtain an access token from the session. "
                "The session token may have expired — please refresh it from your browser."
            )
        return str(token)

    def _get_access_token(self) -> str:
        """Return cached access token, refreshing if needed."""
        if not self._access_token:
            self._access_token = _resolve_access_token_or_use_directly(self._session_token)
        return self._access_token

    # ------------------------------------------------------------------
    # BaseLLMClient interface
    # ------------------------------------------------------------------

    def generate(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> LLMResponse:
        """Send a conversation to the ChatGPT web API and return the response.

        Tool calling is not supported by the web API; ``tools`` is silently
        ignored to maintain interface compatibility.
        """
        try:
            access_token = self._get_access_token()
        except RuntimeError as exc:
            return LLMResponse(content=str(exc))

        # Build the messages array — inject system prompt as a system message.
        api_messages: list[dict[str, Any]] = []
        if system_prompt:
            sys_parts = [system_prompt]
            if dynamic_system:
                sys_parts.append(dynamic_system)
            api_messages.append(
                {
                    "id": "system-0",
                    "author": {"role": "system"},
                    "content": {"content_type": "text", "parts": ["\n\n".join(sys_parts)]},
                }
            )

        for i, msg in enumerate(messages):
            role = _ROLE_MAP.get(msg.role, "user")
            content_text = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            api_messages.append(
                {
                    "id": f"msg-{i}",
                    "author": {"role": role},
                    "content": {"content_type": "text", "parts": [content_text]},
                }
            )

        payload: dict[str, Any] = {
            "action": "next",
            "messages": api_messages,
            "model": self.model,
            "timezone_offset_min": 0,
            "history_and_training_disabled": False,
            "conversation_mode": {"kind": "primary_assistant"},
            "force_paragen": False,
            "force_rate_limit": False,
        }

        headers = {
            **_CHATGPT_HEADERS,
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = httpx.post(
                _CHATGPT_API_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            text = _parse_sse_content(resp.text)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                # Token expired — clear cache so next call re-authenticates.
                self._access_token = None
                return LLMResponse(
                    content=(
                        "ChatGPT web session expired. "
                        "Please refresh your CHATGPT_SESSION_TOKEN from the browser."
                    )
                )
            logger.exception("ChatGPT web API HTTP error")
            return LLMResponse(content=f"ChatGPT web API error: {exc}")
        except Exception as exc:
            logger.exception("ChatGPT web API unexpected error")
            return LLMResponse(content=f"ChatGPT web provider error: {exc}")

        return LLMResponse(
            content=text,
            tool_calls=[],
            usage=TokenUsage(),
        )

    def list_models(self) -> list[str]:
        """Return a static list of known ChatGPT web models."""
        return ["gpt-4o", "gpt-4-turbo", "gpt-4o-mini", "o1", "o1-mini"]


def _resolve_access_token_or_use_directly(session_token: str | None) -> str:
    """Return a usable access token.

    If *session_token* looks like a JWT (contains dots), treat it as an already-
    resolved access token and return it directly.  Otherwise exchange it via the
    session endpoint.
    """
    if not session_token:
        raise RuntimeError("No session token provided.")

    # A JWT access token has exactly 3 dot-separated base64 segments.
    if session_token.count(".") >= 2 and len(session_token) < 800:
        return session_token

    # Looks like a session cookie — exchange it.
    cookies = {"__Secure-next-auth.session-token": session_token}
    response = httpx.get(_CHATGPT_AUTH_URL, cookies=cookies, headers=_CHATGPT_HEADERS)
    response.raise_for_status()
    data = response.json()
    token = data.get("accessToken")
    if not token:
        raise RuntimeError("Could not obtain an access token. Session token may have expired.")
    return str(token)
