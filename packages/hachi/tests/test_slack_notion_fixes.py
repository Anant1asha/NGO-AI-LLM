"""Tests for UC-INT-001 (Slack user-token remediation) and UC-INT-003 (Notion search pagination).

All HTTP calls are mocked — no network access or real credentials required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeVault:
    """Minimal CredentialVault stand-in that serves tokens from a dict or raises ValueError."""

    def __init__(self, tokens: dict[str, str | None]) -> None:
        self._tokens = tokens

    def get_token(self, key: str, prompt_if_missing: bool = False) -> str | None:
        value = self._tokens.get(key)
        if value is None:
            raise ValueError(f"Credential not found. Run: hachi secrets --set {key}")
        return value


def _make_slack_workspace(
    bot_token: str | None = None,
    user_token: str | None = None,
    monkeypatch: Any = None,
):
    """Construct a SlackWorkspace with a mocked CredentialVault.

    Uses monkeypatch (pytest fixture) matching the pattern in test_phase7_integrations.
    """
    tokens: dict[str, str | None] = {
        "slack_bot_token": bot_token,
        "slack_user_token": user_token,
    }
    vault = _FakeVault(tokens)

    # Pre-import so monkeypatch can find the attribute
    import hachi.core.credential_vault as _cv_mod

    monkeypatch.setattr(_cv_mod, "CredentialVault", lambda: vault)

    from hachi.integrations.slack.workspace import SlackWorkspace

    svc = SlackWorkspace()
    # Keep vault so _ensure_* helpers can retry via svc._vault
    svc._vault = vault
    return svc


def _make_notion_databases(api_key: str = "secret-test-key", monkeypatch: Any = None):
    """Construct a NotionDatabases with a mocked CredentialVault."""
    vault = _FakeVault({"notion_api_key": api_key})

    import hachi.core.credential_vault as _cv_mod

    monkeypatch.setattr(_cv_mod, "CredentialVault", lambda: vault)

    from hachi.integrations.notion.databases import NotionDatabases

    svc = NotionDatabases()
    svc._vault = vault
    return svc


# ---------------------------------------------------------------------------
# UC-INT-001 — Slack user-token remediation
# ---------------------------------------------------------------------------


class TestSlackUserTokenConsistency:
    """Verify that SlackService reads slack_user_token and that search_messages uses it."""

    def test_service_stores_user_token_when_present(self, monkeypatch):
        """SlackService.__init__ should populate user_token from the vault."""
        svc = _make_slack_workspace(
            bot_token="xoxb-bot", user_token="xoxp-user", monkeypatch=monkeypatch
        )
        assert svc.user_token == "xoxp-user"

    def test_service_user_token_none_when_absent(self, monkeypatch):
        """user_token is None (not an error) when slack_user_token is not configured."""
        svc = _make_slack_workspace(bot_token="xoxb-bot", user_token=None, monkeypatch=monkeypatch)
        assert svc.user_token is None

    def test_search_messages_sends_user_token_in_authorization_header(self, monkeypatch):
        """search_messages must use the xoxp- user token, NOT the bot token."""
        svc = _make_slack_workspace(
            bot_token="xoxb-bot", user_token="xoxp-user123", monkeypatch=monkeypatch
        )

        captured_headers: dict[str, str] = {}

        def fake_get(url: str, headers: dict, params: Any = None, timeout: float = 30.0):
            captured_headers.update(headers)
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "ok": True,
                "messages": {
                    "matches": [
                        {
                            "channel": {"name": "general"},
                            "username": "alice",
                            "text": "hello world",
                            "ts": "1700000000.000000",
                        }
                    ]
                },
            }
            return mock_resp

        with patch("httpx.get", side_effect=fake_get):
            result = svc.search_messages("hello")

        assert captured_headers.get("Authorization") == "Bearer xoxp-user123", (
            "search_messages must authenticate with the user token (xoxp-), not the bot token"
        )
        assert "hello world" in result

    def test_search_messages_returns_error_string_without_user_token(self, monkeypatch):
        """When no user token is configured, the returned string must name slack_user_token."""
        svc = _make_slack_workspace(bot_token="xoxb-bot", user_token=None, monkeypatch=monkeypatch)

        result = svc.search_messages("anything")

        # The ValueError is caught by search_messages and returned as a string.
        assert "slack_user_token" in result, (
            "Remediation message must reference 'slack_user_token' so users know which "
            "secret to configure — the old message incorrectly named 'slack_bot_token'"
        )

    def test_search_messages_does_not_use_bot_token(self, monkeypatch):
        """Ensure the bot token is never sent to search.messages (it requires user scope)."""
        svc = _make_slack_workspace(
            bot_token="xoxb-should-not-appear",
            user_token="xoxp-correct",
            monkeypatch=monkeypatch,
        )

        captured_headers: dict[str, str] = {}

        def fake_get(url: str, headers: dict, params: Any = None, timeout: float = 30.0):
            captured_headers.update(headers)
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"ok": True, "messages": {"matches": []}}
            return mock_resp

        with patch("httpx.get", side_effect=fake_get):
            svc.search_messages("test")

        assert "xoxb-should-not-appear" not in captured_headers.get("Authorization", ""), (
            "Bot token must not be sent to search.messages — that endpoint requires xoxp-"
        )

    def test_bot_token_guidance_names_correct_secret(self, monkeypatch):
        """_ensure_token error must reference slack_bot_token — not the user token."""
        svc = _make_slack_workspace(bot_token=None, user_token=None, monkeypatch=monkeypatch)
        with pytest.raises(ValueError, match="slack_bot_token"):
            svc._ensure_token()

    def test_user_token_guidance_names_correct_secret(self, monkeypatch):
        """_ensure_user_token error must reference slack_user_token."""
        svc = _make_slack_workspace(bot_token=None, user_token=None, monkeypatch=monkeypatch)
        with pytest.raises(ValueError, match="slack_user_token"):
            svc._ensure_user_token()


# ---------------------------------------------------------------------------
# UC-INT-003 — Notion search_workspace pagination
# ---------------------------------------------------------------------------


def _page_result(title: str, idx: int) -> dict:
    """Build a minimal Notion page result dict."""
    return {
        "id": f"page-id-{idx}",
        "object": "page",
        "url": f"https://www.notion.so/page-{idx}",
        "properties": {
            "title": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestNotionSearchWorkspacePagination:
    """Verify that search_workspace follows has_more/next_cursor beyond the first page."""

    def test_single_page_no_pagination(self, monkeypatch):
        """When has_more is False, only one POST is made and all results are returned."""
        svc = _make_notion_databases(monkeypatch=monkeypatch)

        pages = [_page_result(f"Page {i}", i) for i in range(5)]
        response = {"results": pages, "has_more": False}

        call_count = 0

        def fake_post(url: str, headers: dict, json: dict, timeout: float):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.json.return_value = response
            return mock_resp

        with patch("httpx.post", side_effect=fake_post):
            result = svc.search_workspace("Page")

        assert call_count == 1
        for i in range(5):
            assert f"Page {i}" in result

    def test_pagination_follows_next_cursor(self, monkeypatch):
        """When has_more is True, search_workspace POSTs again with next_cursor."""
        svc = _make_notion_databases(monkeypatch=monkeypatch)

        # Two pages: first 20 items, then 15 more.
        page1_items = [_page_result(f"Result {i}", i) for i in range(20)]
        page2_items = [_page_result(f"Result {i}", i) for i in range(20, 35)]

        responses = [
            {"results": page1_items, "has_more": True, "next_cursor": "cursor-abc"},
            {"results": page2_items, "has_more": False},
        ]
        call_payloads: list[dict] = []

        def fake_post(url: str, headers: dict, json: dict, timeout: float):
            call_payloads.append(json)
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.json.return_value = responses[len(call_payloads) - 1]
            return mock_resp

        with patch("httpx.post", side_effect=fake_post):
            result = svc.search_workspace("Result")

        assert len(call_payloads) == 2, "Expected exactly two POST requests (2 pages)"
        # First call must not include a cursor
        assert "start_cursor" not in call_payloads[0]
        # Second call must carry the cursor from page 1
        assert call_payloads[1].get("start_cursor") == "cursor-abc"
        # All 35 results should appear in the output
        for i in range(35):
            assert f"Result {i}" in result

    def test_pagination_three_pages(self, monkeypatch):
        """Verify the pagination loop terminates correctly over three pages."""
        svc = _make_notion_databases(monkeypatch=monkeypatch)

        responses = [
            {
                "results": [_page_result(f"Item {i}", i) for i in range(20)],
                "has_more": True,
                "next_cursor": "c1",
            },
            {
                "results": [_page_result(f"Item {i}", i) for i in range(20, 40)],
                "has_more": True,
                "next_cursor": "c2",
            },
            {
                "results": [_page_result(f"Item {i}", i) for i in range(40, 45)],
                "has_more": False,
            },
        ]
        call_count = 0

        def fake_post(url: str, headers: dict, json: dict, timeout: float):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.json.return_value = resp
            return mock_resp

        with patch("httpx.post", side_effect=fake_post):
            result = svc.search_workspace("Item")

        assert call_count == 3
        # Spot-check results spread across the three pages
        for i in [0, 19, 20, 39, 40, 44]:
            assert f"Item {i}" in result

    def test_empty_workspace_returns_no_results_message(self, monkeypatch):
        """An empty first page with has_more=False returns the 'no results' message."""
        svc = _make_notion_databases(monkeypatch=monkeypatch)

        def fake_post(url: str, headers: dict, json: dict, timeout: float):
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.json.return_value = {"results": [], "has_more": False}
            return mock_resp

        with patch("httpx.post", side_effect=fake_post):
            result = svc.search_workspace("nothing")

        assert "No results found" in result

    def test_api_error_returns_friendly_message(self, monkeypatch):
        """An HTTP error from Notion is returned as a friendly string, not an exception."""
        svc = _make_notion_databases(monkeypatch=monkeypatch)

        def fake_post(url: str, headers: dict, json: dict, timeout: float):
            mock_resp = MagicMock()
            mock_resp.is_success = False
            mock_resp.status_code = 401
            mock_resp.json.return_value = {
                "code": "unauthorized",
                "message": "API token is invalid",
            }
            return mock_resp

        with patch("httpx.post", side_effect=fake_post):
            result = svc.search_workspace("anything")

        assert "Failed to search Notion workspace" in result
