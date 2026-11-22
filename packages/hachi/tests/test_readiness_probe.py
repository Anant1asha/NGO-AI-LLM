"""Tests for the deep readiness probe (P2-11).

Covers:
- Probe returns not-ready when a critical dependency is missing.
- Probe returns ready when all critical checks pass.
- Structured result names the failing check.
- /readiness HTTP route returns 200 when ready and 503 when not.
- Legacy 2-tuple probe still works through GatewayControlPlane.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from hachi.core.paths import HachiPaths
from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_paths(tmp_path: Path, *, with_config: bool = True, with_perms: bool = True) -> HachiPaths:
    """Build a HachiPaths rooted under *tmp_path*."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    cache_dir = tmp_path / "cache"

    for d in (config_dir, data_dir, state_dir, cache_dir):
        d.mkdir(parents=True, exist_ok=True)

    if with_config:
        (config_dir / "settings.toml").write_text("", encoding="utf-8")
    if with_perms:
        (config_dir / "device-permissions.og").write_text("", encoding="utf-8")

    return HachiPaths(
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        state_dir=state_dir,
    )


def _make_fake_config(kind: str = "anthropic", api_key_env: str = "ANTHROPIC_API_KEY") -> Any:
    """Return a minimal config-like object with a provider attribute."""
    provider = MagicMock()
    provider.kind = kind
    provider.api_key_env = api_key_env
    cfg = MagicMock()
    cfg.provider = provider
    return cfg


# ---------------------------------------------------------------------------
# Unit tests for _gateway_readiness_probe
# ---------------------------------------------------------------------------


def test_probe_ready_when_all_checks_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Probe reports ready when config, perms, provider key, and store dir are all OK."""
    paths = _make_paths(tmp_path)
    fake_cfg = _make_fake_config()

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")
    # Reset worker slot so the worker check is "not started" (not a blocker).
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert ready is True, f"Expected ready but blockers={blockers}"
    assert blockers == []
    assert checks["config_file"] == "ok"
    assert checks["permissions_file"] == "ok"
    assert checks["provider_configured"].startswith("ok")
    assert checks["session_store_writable"] == "ok"
    assert checks["job_worker"] == "not started"


def test_probe_not_ready_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Probe names 'config_file' as a blocker when the settings TOML is absent."""
    paths = _make_paths(tmp_path, with_config=False)  # no settings.toml
    fake_cfg = _make_fake_config()

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert ready is False
    assert "config_file" in blockers
    assert "missing" in checks["config_file"]


def test_probe_not_ready_when_permissions_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Probe names 'permissions_file' as a blocker when the .og file is absent."""
    paths = _make_paths(tmp_path, with_perms=False)  # no device-permissions.og
    fake_cfg = _make_fake_config()

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert ready is False
    assert "permissions_file" in blockers
    assert "missing" in checks["permissions_file"]


def test_probe_not_ready_when_api_key_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Probe names 'provider_configured' as a blocker when no API key is resolvable."""
    paths = _make_paths(tmp_path)
    fake_cfg = _make_fake_config(kind="anthropic", api_key_env="ANTHROPIC_API_KEY")

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    # No env key
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Secret store also returns nothing
    fake_store = MagicMock()
    fake_store.get.return_value = None
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: fake_store)
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert ready is False
    assert "provider_configured" in blockers
    assert "no API key" in checks["provider_configured"]


def test_probe_ready_for_keyless_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keyless providers (Ollama) pass the provider check without an API key."""
    paths = _make_paths(tmp_path)
    fake_cfg = _make_fake_config(kind="ollama", api_key_env="")

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert "provider_configured" not in blockers
    assert "keyless" in checks["provider_configured"]


def test_probe_not_ready_when_store_dir_unwritable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Probe names 'session_store_writable' as a blocker when mkstemp fails."""
    paths = _make_paths(tmp_path)
    fake_cfg = _make_fake_config()

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    def _exploding_mkstemp(**kwargs: Any) -> None:  # type: ignore[return]
        raise OSError("disk full")

    monkeypatch.setattr(tempfile, "mkstemp", _exploding_mkstemp)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert ready is False
    assert "session_store_writable" in blockers
    assert "not writable" in checks["session_store_writable"]


def test_probe_not_ready_when_worker_dead(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Probe names 'job_worker' as a blocker when the resident thread is dead."""
    paths = _make_paths(tmp_path)
    fake_cfg = _make_fake_config()

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")

    dead_worker = MagicMock()
    dead_worker.is_running = False
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", dead_worker)

    from hachi.cli.main import _gateway_readiness_probe

    ready, blockers, checks = _gateway_readiness_probe()

    assert ready is False
    assert "job_worker" in blockers
    assert "not alive" in checks["job_worker"]


def test_probe_checks_key_present_in_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The structured result always names every check, even passing ones."""
    paths = _make_paths(tmp_path)
    fake_cfg = _make_fake_config()

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")
    monkeypatch.setattr("hachi.cli.main._GATEWAY_RESIDENT_WORKER", None)

    from hachi.cli.main import _gateway_readiness_probe

    _ready, _blockers, checks = _gateway_readiness_probe()

    expected_keys = {
        "config_file",
        "permissions_file",
        "provider_configured",
        "session_store_writable",
        "job_worker",
    }
    assert expected_keys.issubset(checks.keys()), (
        f"Missing check keys: {expected_keys - checks.keys()}"
    )


# ---------------------------------------------------------------------------
# HTTP /readiness endpoint tests
# ---------------------------------------------------------------------------


def test_readiness_http_200_when_ready() -> None:
    """/readiness returns HTTP 200 and ready=True when probe passes."""
    cp = GatewayControlPlane(
        readiness_probe=lambda: (True, [], {"config_file": "ok", "provider_configured": "ok"})
    )
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        resp = client.get("/readiness")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["blockers"] == []
        assert isinstance(body["checks"], dict)
        assert body["checks"]["config_file"] == "ok"


def test_readiness_http_503_when_not_ready() -> None:
    """/readiness returns HTTP 503 and ready=False when a blocker is present."""
    cp = GatewayControlPlane(
        readiness_probe=lambda: (
            False,
            ["provider_configured"],
            {"config_file": "ok", "provider_configured": "no API key for 'anthropic'"},
        )
    )
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        resp = client.get("/readiness")
        assert resp.status_code == 503
        body = resp.json()
        assert body["ready"] is False
        assert "provider_configured" in body["blockers"]
        assert "no API key" in body["checks"]["provider_configured"]


def test_readiness_http_checks_field_present() -> None:
    """The /readiness response always includes a 'checks' key."""
    cp = GatewayControlPlane(readiness_probe=lambda: (True, [], {"all": "ok"}))
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        body = client.get("/readiness").json()
        assert "checks" in body


def test_readiness_legacy_2tuple_probe_still_works() -> None:
    """Legacy probes returning a 2-tuple continue to work; 'checks' defaults to {}."""
    cp = GatewayControlPlane(
        readiness_probe=lambda: (False, ["boot_incomplete"])  # old 2-tuple style
    )
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        resp = client.get("/readiness")
        assert resp.status_code == 503
        body = resp.json()
        assert body["ready"] is False
        assert body["blockers"] == ["boot_incomplete"]
        assert body["checks"] == {}
