"""Tests for the HACHI_DISABLE_DOTENV_AUTOLOAD guard in hachi.cli.main.

These tests verify that:
1. When HACHI_DISABLE_DOTENV_AUTOLOAD=1 the _load_dotenv_into_environ function
   is a no-op (real provider keys are never leaked into os.environ).
2. When HACHI_DISABLE_DOTENV_AUTOLOAD=0 the function works normally.
3. The test harness default (set by conftest.py) is "1", proving the suite
   always runs in hermetic mode.
"""

from __future__ import annotations

import os

import pytest

from hachi.cli.main import _load_dotenv_into_environ

# A unique sentinel key unlikely to collide with any real env var or .env entry.
_SENTINEL_KEY = "HACHI_TEST_SENTINEL_KEY_HERMETICITY_CHECK"
_SENTINEL_VALUE = "sentinel-value-abc123"


def test_autoload_skipped_when_flag_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> None:
    """When HACHI_DISABLE_DOTENV_AUTOLOAD=1 the function must not set any keys."""
    monkeypatch.setenv("HACHI_DISABLE_DOTENV_AUTOLOAD", "1")

    dotenv_file = tmp_path / ".env"  # type: ignore[operator]
    dotenv_file.write_text(f"{_SENTINEL_KEY}={_SENTINEL_VALUE}\n", encoding="utf-8")

    # Ensure the key is absent before calling the function.
    assert _SENTINEL_KEY not in os.environ, (
        f"{_SENTINEL_KEY} already in os.environ — test isolation failure"
    )

    _load_dotenv_into_environ(dotenv_file)

    assert _SENTINEL_KEY not in os.environ, (
        "Flag=1: _load_dotenv_into_environ must not set any env vars"
    )


def test_autoload_active_when_flag_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> None:
    """When HACHI_DISABLE_DOTENV_AUTOLOAD=0 the function merges the .env normally."""
    monkeypatch.setenv("HACHI_DISABLE_DOTENV_AUTOLOAD", "0")

    dotenv_file = tmp_path / ".env"  # type: ignore[operator]
    dotenv_file.write_text(f"{_SENTINEL_KEY}={_SENTINEL_VALUE}\n", encoding="utf-8")

    # Ensure the key is absent before calling the function so the non-overwrite
    # logic doesn't hide a bug.
    assert _SENTINEL_KEY not in os.environ, (
        f"{_SENTINEL_KEY} already in os.environ — test isolation failure"
    )

    try:
        _load_dotenv_into_environ(dotenv_file)
        assert os.environ.get(_SENTINEL_KEY) == _SENTINEL_VALUE, (
            "Flag=0: _load_dotenv_into_environ must set the key from .env"
        )
    finally:
        # Clean up the mutation so it doesn't leak to other tests (monkeypatch
        # restores env vars it set, but the function writes directly to os.environ).
        os.environ.pop(_SENTINEL_KEY, None)


def test_conftest_default_flag_is_set() -> None:
    """Regression guard: conftest.py must default HACHI_DISABLE_DOTENV_AUTOLOAD to '1'.

    If this fails the test harness is no longer hermetic — the developer's .env
    would be merged at import time, flipping import-time skipif guards on live-
    gateway tests and leaking real provider secrets into the test process.
    """
    assert os.environ.get("HACHI_DISABLE_DOTENV_AUTOLOAD") == "1", (
        "HACHI_DISABLE_DOTENV_AUTOLOAD must be '1' in the test harness "
        "(set by tests/conftest.py). The suite is not hermetic."
    )
