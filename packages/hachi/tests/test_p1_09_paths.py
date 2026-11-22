"""P1-09: Path unification — skill-usage DB and RoleResolver use platformdirs.

Invariants:
  1. Fresh env: SkillEngine._usage_path is under get_hachi_paths().state_dir.
  2. RoleResolver: _roles_dir is under get_hachi_paths().data_dir.
  3. RoleResolver legacy shim: an existing ~/.hachi/skills/roles/ dir is checked as fallback.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hachi.core.paths import HachiPaths


def _mock_paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


# ---------------------------------------------------------------------------
# SkillEngine usage path
# ---------------------------------------------------------------------------


def test_skill_engine_uses_platformdirs_state_dir(tmp_path, monkeypatch):
    """_usage_path resolves to state_dir/skill_usage.json."""
    import hachi.og_engine.engine as engine_mod

    mock_paths = _mock_paths(tmp_path)
    mock_paths.state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(engine_mod, "get_hachi_paths", lambda: mock_paths)

    eng = engine_mod.SkillEngine()
    assert eng._usage_path == mock_paths.state_dir / "skill_usage.json"


# ---------------------------------------------------------------------------
# RoleResolver path
# ---------------------------------------------------------------------------


def test_role_resolver_uses_platformdirs_data_dir(tmp_path, monkeypatch):
    """RoleResolver._roles_dir is under data_dir/skills/roles."""
    import hachi.core.sub_agent as sub_agent_mod

    mock_paths = _mock_paths(tmp_path)
    monkeypatch.setattr(sub_agent_mod, "get_hachi_paths", lambda: mock_paths)

    resolver = sub_agent_mod.RoleResolver()
    assert resolver._roles_dir == mock_paths.data_dir / "skills" / "roles"


def test_role_resolver_resolves_builtin_role(tmp_path, monkeypatch):
    """Built-in roles (default_skills/roles/) still resolve after the path change."""
    import hachi.core.sub_agent as sub_agent_mod

    mock_paths = _mock_paths(tmp_path)
    monkeypatch.setattr(sub_agent_mod, "get_hachi_paths", lambda: mock_paths)

    resolver = sub_agent_mod.RoleResolver()
    # "coder" is a shipped built-in role.
    path = resolver.resolve("coder")
    assert path.exists()
    assert path.stem == "coder"


def test_role_resolver_falls_back_to_legacy_roles(tmp_path, monkeypatch):
    """If a role exists only in the legacy dir, it is found via the legacy shim."""
    import hachi.core.sub_agent as sub_agent_mod

    mock_paths = _mock_paths(tmp_path)
    monkeypatch.setattr(sub_agent_mod, "get_hachi_paths", lambda: mock_paths)

    # Create a custom role in the legacy location.
    legacy_roles = tmp_path / "legacy" / "skills" / "roles"
    legacy_roles.mkdir(parents=True)
    custom_role = legacy_roles / "custom_legacy.og"
    custom_role.write_text("::meta\n  title: Custom Legacy\n  version: 1.0.0\n", encoding="utf-8")

    # Point the legacy shim to our tmp_path legacy dir.
    resolver = sub_agent_mod.RoleResolver()
    resolver._legacy_roles_dir = legacy_roles  # override for test isolation

    path = resolver.resolve("custom_legacy")
    assert path == custom_role


def test_role_resolver_explicit_workspace_dir_disables_legacy_shim(tmp_path):
    """When workspace_dir is passed explicitly, the legacy shim is not applied."""
    from hachi.core.sub_agent import RoleResolver

    resolver = RoleResolver(workspace_dir=tmp_path)
    assert resolver._legacy_roles_dir is None


@pytest.mark.parametrize("role", ["analyst", "coder", "researcher"])
def test_role_resolver_lists_builtin_roles(tmp_path, monkeypatch, role):
    """list_available_roles() includes all shipped roles."""
    import hachi.core.sub_agent as sub_agent_mod

    mock_paths = _mock_paths(tmp_path)
    monkeypatch.setattr(sub_agent_mod, "get_hachi_paths", lambda: mock_paths)

    resolver = sub_agent_mod.RoleResolver()
    assert role in resolver.list_available_roles()
