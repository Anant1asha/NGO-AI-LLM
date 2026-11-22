"""Tests for the guided Telegram channel setup.

Covers:
- parse_allowlist / looks_like_token (pure)
- resolve_token priority (flag > env > vault) and absent-token handling
- save/load allowlist round-trip through a temp config (and the empty-table drop)
- the `channel telegram --setup` CLI flow (token + allowlist persisted, then runs)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.channels import telegram_setup as ts
from hachi.cli.main import app

runner = CliRunner()


class _FakeVault:
    """In-memory stand-in for CredentialVault (get_token raises when absent)."""

    def __init__(self, store: dict[str, str] | None = None) -> None:
        self.store = dict(store or {})

    def get_token(self, key: str, prompt_if_missing: bool = False) -> str:
        if key in self.store:
            return self.store[key]
        raise ValueError("Credential not found")

    def set_token(self, key: str, value: str) -> None:
        self.store[key] = value


def _temp_paths(tmp_path: Path):
    from hachi.core.paths import HachiPaths

    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


# --------------------------------------------------------------------------- #
# parse_allowlist
# --------------------------------------------------------------------------- #


class TestParseAllowlist:
    def test_comma_separated(self) -> None:
        assert ts.parse_allowlist("111,222,333") == ["111", "222", "333"]

    def test_whitespace_separated(self) -> None:
        assert ts.parse_allowlist("111 222  333") == ["111", "222", "333"]

    def test_mixed_with_spaces(self) -> None:
        assert ts.parse_allowlist(" 111, 222 ,333 ") == ["111", "222", "333"]

    def test_empty_and_none(self) -> None:
        assert ts.parse_allowlist("") == []
        assert ts.parse_allowlist(None) == []
        assert ts.parse_allowlist("   ") == []


# --------------------------------------------------------------------------- #
# looks_like_token
# --------------------------------------------------------------------------- #


class TestLooksLikeToken:
    def test_valid_shape(self) -> None:
        assert ts.looks_like_token("123456789:" + "A" * 30)

    def test_rejects_id_only(self) -> None:
        assert not ts.looks_like_token("123456789")

    def test_rejects_empty_and_none(self) -> None:
        assert not ts.looks_like_token("")
        assert not ts.looks_like_token(None)

    def test_rejects_non_numeric_head(self) -> None:
        assert not ts.looks_like_token("bot:" + "A" * 30)

    def test_rejects_short_secret(self) -> None:
        assert not ts.looks_like_token("123:short")


# --------------------------------------------------------------------------- #
# resolve_token
# --------------------------------------------------------------------------- #


class TestResolveToken:
    def test_explicit_wins(self) -> None:
        vault = _FakeVault({ts.TELEGRAM_TOKEN_KEY: "from-vault"})
        got = ts.resolve_token("explicit", vault=vault, env={ts.TELEGRAM_TOKEN_ENV: "from-env"})
        assert got == "explicit"

    def test_env_over_vault(self) -> None:
        vault = _FakeVault({ts.TELEGRAM_TOKEN_KEY: "from-vault"})
        got = ts.resolve_token(None, vault=vault, env={ts.TELEGRAM_TOKEN_ENV: "from-env"})
        assert got == "from-env"

    def test_falls_back_to_vault(self) -> None:
        vault = _FakeVault({ts.TELEGRAM_TOKEN_KEY: "from-vault"})
        assert ts.resolve_token(None, vault=vault, env={}) == "from-vault"

    def test_none_when_absent_everywhere(self) -> None:
        assert ts.resolve_token(None, vault=_FakeVault(), env={}) is None

    def test_strips_whitespace(self) -> None:
        assert ts.resolve_token("  tok  ", vault=_FakeVault(), env={}) == "tok"


# --------------------------------------------------------------------------- #
# save_token
# --------------------------------------------------------------------------- #


class TestSaveToken:
    def test_persists_to_vault(self) -> None:
        vault = _FakeVault()
        ts.save_token("123:secret", vault=vault)
        assert vault.store[ts.TELEGRAM_TOKEN_KEY] == "123:secret"

    def test_rejects_empty(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            ts.save_token("   ", vault=_FakeVault())


# --------------------------------------------------------------------------- #
# allowlist persistence round-trip
# --------------------------------------------------------------------------- #


class TestAllowlistPersistence:
    def test_round_trip(self, tmp_path: Path) -> None:
        paths = _temp_paths(tmp_path)
        ts.save_allowlist(["111", "222"], paths=paths)
        assert ts.load_allowlist(paths=paths) == ["111", "222"]
        text = paths.global_config_toml.read_text(encoding="utf-8")
        assert "channels" in text and "111" in text

    def test_default_load_is_empty(self, tmp_path: Path) -> None:
        paths = _temp_paths(tmp_path)
        assert ts.load_allowlist(paths=paths) == []

    def test_empty_allowlist_does_not_write_channels_table(self, tmp_path: Path) -> None:
        paths = _temp_paths(tmp_path)
        ts.save_allowlist([], paths=paths)
        if paths.global_config_toml.exists():
            assert "channels" not in paths.global_config_toml.read_text(encoding="utf-8")

    def test_save_strips_and_filters_blanks(self, tmp_path: Path) -> None:
        paths = _temp_paths(tmp_path)
        ts.save_allowlist([" 111 ", "", "222"], paths=paths)
        assert ts.load_allowlist(paths=paths) == ["111", "222"]


# --------------------------------------------------------------------------- #
# CLI: channel telegram --setup
# --------------------------------------------------------------------------- #


class TestChannelTelegramSetupCmd:
    def _patches(self):
        """Patch heavy/external deps; let the loop exit via KeyboardInterrupt."""
        adapter = MagicMock()
        adapter.poll_once.side_effect = KeyboardInterrupt
        adapter_cls = MagicMock(return_value=adapter)
        onboarding = MagicMock()
        onboarding.return_value.needs_setup.return_value = False
        return adapter, (
            patch("hachi.channels.telegram.TelegramAdapter", adapter_cls),
            patch("hachi.channels.runner.GatewaySessionRunner"),
            patch("hachi.channels.ChannelRouter"),
            patch("hachi.channels.telegram_setup.save_token"),
            patch("hachi.channels.telegram_setup.save_allowlist"),
            patch("hachi.channels.telegram_setup.load_allowlist", return_value=["555"]),
            patch("hachi.core.onboarding.OnboardingService", onboarding),
        )

    def test_setup_persists_token_and_allowlist(self) -> None:
        token = "123456789:" + "A" * 30
        _, patches = self._patches()
        with (
            patches[0],
            patches[1],
            patches[2],
            patch("hachi.channels.telegram_setup.save_token") as save_token,
            patch("hachi.channels.telegram_setup.save_allowlist") as save_allow,
            patches[5],
            patches[6],
        ):
            result = runner.invoke(
                app,
                ["channel", "telegram", "--setup"],
                input=f"{token}\n111,222\n",
            )

        assert result.exit_code == 0
        save_token.assert_called_once_with(token)
        save_allow.assert_called_once_with(["111", "222"])

    def test_setup_empty_token_aborts(self) -> None:
        _, patches = self._patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = runner.invoke(app, ["channel", "telegram", "--setup"], input="\n")
        assert result.exit_code == 2

    def test_run_without_token_exits_2(self) -> None:
        _, patches = self._patches()
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch("hachi.channels.telegram_setup.resolve_token", return_value=None),
        ):
            result = runner.invoke(app, ["channel", "telegram"])
        assert result.exit_code == 2

    def test_run_uses_resolved_token_and_stored_allowlist(self) -> None:
        adapter, patches = self._patches()
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch(
                "hachi.channels.telegram_setup.resolve_token",
                return_value="123:" + "A" * 30,
            ),
        ):
            result = runner.invoke(app, ["channel", "telegram"])
        assert result.exit_code == 0
        # The adapter was constructed and polled (then KeyboardInterrupt stopped it).
        assert adapter.poll_once.called
