"""Tests for `hachi mcp` CLI sub-commands.

Covers:
1. mcp list — no servers → informational message; JSON with empty list
2. mcp list — with a configured server .og node → shows the server
3. mcp add — creates mcp-<name>.og in the skills dir with correct content
4. mcp add — adds env vars into the ::config block
5. mcp add — rejects invalid names (spaces, special chars)
6. mcp add --json — emits JSON with file path
7. mcp remove — deletes the .og file
8. mcp remove — missing file exits 1
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_skills_dir(tmp_path: Path) -> Path:
    """Create a minimal skills dir and patch get_skills_dir to return it."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


# ---------------------------------------------------------------------------
# 1. mcp list — no servers
# ---------------------------------------------------------------------------


def test_mcp_list_no_servers_shows_hint(tmp_path: Path) -> None:
    skills_dir = _setup_skills_dir(tmp_path)
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "No MCP servers" in result.output or "mcp add" in result.output.lower()


def test_mcp_list_json_empty(tmp_path: Path) -> None:
    import json

    skills_dir = _setup_skills_dir(tmp_path)
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] == 0
    assert data["servers"] == []


# ---------------------------------------------------------------------------
# 2. mcp list — with a pre-existing mcp node
# ---------------------------------------------------------------------------


def test_mcp_list_shows_configured_servers(tmp_path: Path) -> None:
    import json

    skills_dir = _setup_skills_dir(tmp_path)
    # Create an MCP .og node manually (::node[name] format with ->[:role=mcp] edge)
    og = """\
::node[github]
->[:role=mcp]
->[:keywords=mcp, github]

::dense
MCP server: github

::config
command: npx
args: -y @modelcontextprotocol/server-github
"""
    (skills_dir / "mcp-github.og").write_text(og, encoding="utf-8")

    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] == 1
    assert data["servers"][0]["name"] == "github"
    assert "@modelcontextprotocol/server-github" in data["servers"][0]["args"]


# ---------------------------------------------------------------------------
# 3. mcp add — creates the .og file
# ---------------------------------------------------------------------------


def test_mcp_add_creates_og_file(tmp_path: Path) -> None:
    skills_dir = _setup_skills_dir(tmp_path)
    pkg = "@modelcontextprotocol/server-postgres"
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "add", "postgres", pkg])
    assert result.exit_code == 0, result.output
    dest = skills_dir / "mcp-postgres.og"
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "role=mcp" in content  # ->[:role=mcp] edge annotation
    assert "@modelcontextprotocol/server-postgres" in content
    assert "command: npx" in content


# ---------------------------------------------------------------------------
# 4. mcp add with --env inserts env vars into ::config
# ---------------------------------------------------------------------------


def test_mcp_add_with_env_vars(tmp_path: Path) -> None:
    skills_dir = _setup_skills_dir(tmp_path)
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(
            app,
            [
                "mcp",
                "add",
                "github",
                "@modelcontextprotocol/server-github",
                "--env",
                "GITHUB_TOKEN=ghp_test123",
            ],
        )
    assert result.exit_code == 0, result.output
    content = (skills_dir / "mcp-github.og").read_text(encoding="utf-8")
    assert "env_GITHUB_TOKEN: ghp_test123" in content


# ---------------------------------------------------------------------------
# 5. mcp add -- rejects invalid name
# ---------------------------------------------------------------------------


def test_mcp_add_rejects_invalid_name(tmp_path: Path) -> None:
    skills_dir = _setup_skills_dir(tmp_path)
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "add", "bad name!", "@some/package"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# 6. mcp add --json emits JSON with file path
# ---------------------------------------------------------------------------


def test_mcp_add_json_output(tmp_path: Path) -> None:
    import json

    skills_dir = _setup_skills_dir(tmp_path)
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "add", "myserver", "@org/myserver", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["name"] == "myserver"
    assert "mcp-myserver.og" in data["file"]
    assert data["package"] == "@org/myserver"


# ---------------------------------------------------------------------------
# 7. mcp remove — deletes the .og file
# ---------------------------------------------------------------------------


def test_mcp_remove_deletes_og_file(tmp_path: Path) -> None:
    skills_dir = _setup_skills_dir(tmp_path)
    # Pre-create the file
    og_file = skills_dir / "mcp-github.og"
    og_file.write_text("::meta\nname: github\nrole: mcp\n", encoding="utf-8")

    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "remove", "github", "--yes"])
    assert result.exit_code == 0, result.output
    assert not og_file.exists()
    assert "Removed" in result.output


# ---------------------------------------------------------------------------
# 8. mcp remove — missing file exits 1
# ---------------------------------------------------------------------------


def test_mcp_remove_missing_exits_1(tmp_path: Path) -> None:
    skills_dir = _setup_skills_dir(tmp_path)
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["mcp", "remove", "nonexistent", "--yes"])
    assert result.exit_code == 1
    assert "Not found" in result.output or "not found" in result.output.lower()
