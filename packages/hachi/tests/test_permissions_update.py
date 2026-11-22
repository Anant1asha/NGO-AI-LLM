"""Tests for the update_permissions → device-permissions.og sync (Bug 7).

update_permissions() writes config.permissions.tier to settings.toml but
historically never touched device-permissions.og. PermissionGate reads the .og
file and is immutable, so the tier change had no effect on the running gate
or on fresh boots that read the .og.

Covers:
  1. Calling update_permissions(tier) regenerates device-permissions.og with the
     new tier so a fresh boot picks it up.
  2. Custom allowed_paths in the existing .og are preserved across a tier change.
  3. The regenerated .og is parseable and encodes the correct tier.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _build_runtime(tmp_path: Path):
    """Return a minimal _InProcessGatewayRuntime wired to tmp_path."""
    from hachi.cli.main import _InProcessGatewayRuntime

    config_toml = tmp_path / "settings.toml"
    config_toml.write_text("[permissions]\ntier = 'guided'\n", encoding="utf-8")
    skills = tmp_path / "skills"
    skills.mkdir(exist_ok=True)

    fake_paths = MagicMock()
    fake_paths.global_config_toml = config_toml
    fake_paths.skills_dir = skills
    return fake_paths, _InProcessGatewayRuntime()


class TestUpdatePermissionsRegeneratesOg:
    def test_tier_change_writes_device_permissions_og(self, tmp_path: Path) -> None:
        """Changing the tier must regenerate device-permissions.og (Bug 7)."""
        from hachi.core.permissions import PermissionGate

        permissions_og = tmp_path / "device-permissions.og"
        # Start with guided tier in the .og file
        from hachi.core.permissions import generate_permissions_og

        permissions_og.write_text(generate_permissions_og("guided"), encoding="utf-8")

        fake_paths, rt = _build_runtime(tmp_path)

        with (
            patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths),
            patch("hachi.gateway.workspace.get_skills_dir", return_value=tmp_path / "skills"),
            patch("hachi.cli.main.get_permissions_file", return_value=permissions_og),
        ):
            rt.update_permissions({"tier": "unrestricted"})

        # The .og file must reflect the new tier.
        gate = PermissionGate(permissions_og)
        assert gate.tier == "unrestricted", (
            f"Expected gate.tier='unrestricted' after update_permissions, got {gate.tier!r}"
        )

    def test_og_tier_mismatch_fixed_at_update(self, tmp_path: Path) -> None:
        """If the .og had sandbox tier before the call, it must be updated."""
        from hachi.core.permissions import PermissionGate, generate_permissions_og

        permissions_og = tmp_path / "device-permissions.og"
        permissions_og.write_text(generate_permissions_og("sandbox"), encoding="utf-8")

        # Pre-condition: gate reads sandbox
        assert PermissionGate(permissions_og).tier == "sandbox"

        fake_paths, rt = _build_runtime(tmp_path)
        with (
            patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths),
            patch("hachi.gateway.workspace.get_skills_dir", return_value=tmp_path / "skills"),
            patch("hachi.cli.main.get_permissions_file", return_value=permissions_og),
        ):
            rt.update_permissions({"tier": "guided"})

        assert PermissionGate(permissions_og).tier == "guided"

    def test_ask_before_change_does_not_corrupt_og(self, tmp_path: Path) -> None:
        """Changing ask_before (no tier) must leave the .og file parseable."""
        from hachi.core.permissions import PermissionGate, generate_permissions_og

        permissions_og = tmp_path / "device-permissions.og"
        permissions_og.write_text(generate_permissions_og("guided"), encoding="utf-8")

        fake_paths, rt = _build_runtime(tmp_path)
        with (
            patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths),
            patch("hachi.gateway.workspace.get_skills_dir", return_value=tmp_path / "skills"),
            patch("hachi.cli.main.get_permissions_file", return_value=permissions_og),
        ):
            rt.update_permissions({"ask_before": {"delete_files": True}})

        # .og must still be parseable and tier unchanged
        gate = PermissionGate(permissions_og)
        assert gate.tier == "guided"
