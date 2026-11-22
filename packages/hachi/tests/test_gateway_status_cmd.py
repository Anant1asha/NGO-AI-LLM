"""Tests for `hachi gateway-status`.

Fully offline: urllib calls are mocked so no real HTTP connection is made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


def _mock_urlopen(status: int = 200, body: bytes = b'{"status": "ok"}'):
    """Return a context-manager mock that urllib.request.urlopen will return."""
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = lambda self: self
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestGatewayStatusReachable:
    def test_reachable_exits_0(self) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
            result = runner.invoke(app, ["gateway-status"])
        assert result.exit_code == 0

    def test_reachable_shows_host_port(self) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
            result = runner.invoke(app, ["gateway-status"])
        assert "127.0.0.1" in result.output
        assert "8787" in result.output

    def test_json_output_reachable(self) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
            result = runner.invoke(app, ["gateway-status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "reachable"
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 8787

    def test_json_includes_http_status(self) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(status=200)):
            result = runner.invoke(app, ["gateway-status", "--json"])
        data = json.loads(result.output)
        assert data["http_status"] == 200

    def test_custom_host_port(self) -> None:
        with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
            result = runner.invoke(
                app, ["gateway-status", "--host", "0.0.0.0", "--port", "9999", "--json"]
            )
        data = json.loads(result.output)
        assert data["host"] == "0.0.0.0"
        assert data["port"] == 9999


class TestGatewayStatusUnreachable:
    def test_unreachable_exits_1(self) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = runner.invoke(app, ["gateway-status"])
        assert result.exit_code == 1

    def test_unreachable_json_has_status_unreachable(self) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = runner.invoke(app, ["gateway-status", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] == "unreachable"
        assert "error" in data

    def test_unreachable_human_output_shows_start_hint(self) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = runner.invoke(app, ["gateway-status"])
        assert "hachi gateway" in result.output
