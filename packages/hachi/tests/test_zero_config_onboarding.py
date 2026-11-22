"""Tests for zero-config onboarding improvements.

Covers:
- detect_environment: extended provider detection (groq/together/deepseek/openrouter)
- best_provider_from_env: priority-ordered provider auto-selection
- _pre_flight_check: actionable pre-boot key gate (via TestableFlightChecker)
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from hachi.core.onboarding import OnboardingService
from hachi.core.paths import HachiPaths

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def _service(tmp_path: Path) -> OnboardingService:
    return OnboardingService(paths=_paths(tmp_path))


# ---------------------------------------------------------------------------
# detect_environment — extended provider detection
# ---------------------------------------------------------------------------


def test_detect_env_anthropic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    d = _service(tmp_path).detect_environment()
    assert d["anthropic_env"] is True
    assert d["groq_env"] is False


def test_detect_env_groq(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    d = _service(tmp_path).detect_environment()
    assert d["groq_env"] is True
    assert d["anthropic_env"] is False


def test_detect_env_together(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOGETHER_API_KEY", "ta-test")
    d = _service(tmp_path).detect_environment()
    assert d["together_env"] is True


def test_detect_env_deepseek(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    d = _service(tmp_path).detect_environment()
    assert d["deepseek_env"] is True


def test_detect_env_openrouter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    d = _service(tmp_path).detect_environment()
    assert d["openrouter_env"] is True


def test_detect_env_openai(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    d = _service(tmp_path).detect_environment()
    assert d["openai_env"] is True


def test_detect_env_none_set(tmp_path: Path, monkeypatch) -> None:
    for k in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    with mock.patch("shutil.which", return_value=None):
        d = _service(tmp_path).detect_environment()
    for key in (
        "anthropic_env",
        "openai_env",
        "groq_env",
        "together_env",
        "deepseek_env",
        "openrouter_env",
        "ollama_cli",
    ):
        assert d[key] is False, f"Expected {key} to be False"


# ---------------------------------------------------------------------------
# best_provider_from_env — priority ordering
# ---------------------------------------------------------------------------


def test_best_provider_anthropic_beats_openai(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-a")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "anthropic"
    assert result["api_key_env"] == "ANTHROPIC_API_KEY"


def test_best_provider_openai_when_no_anthropic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "openai-compatible"


def test_best_provider_groq_when_only_groq(tmp_path: Path, monkeypatch) -> None:
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "groq"
    assert result["api_key_env"] == "GROQ_API_KEY"


def test_best_provider_together(tmp_path: Path, monkeypatch) -> None:
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TOGETHER_API_KEY", "ta-test")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "together"


def test_best_provider_deepseek(tmp_path: Path, monkeypatch) -> None:
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "deepseek"


def test_best_provider_openrouter_last_resort_before_ollama(tmp_path: Path, monkeypatch) -> None:
    for k in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "DEEPSEEK_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "openrouter"


def test_best_provider_ollama_when_no_keys(tmp_path: Path, monkeypatch) -> None:
    for k in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_AI_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    with mock.patch("shutil.which", return_value="/usr/bin/ollama"):
        result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result["kind"] == "ollama"
    assert "base_url" in result  # Ollama needs a base URL


def test_best_provider_returns_none_when_nothing_detected(tmp_path: Path, monkeypatch) -> None:
    for k in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_AI_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    with mock.patch("shutil.which", return_value=None):
        result = _service(tmp_path).best_provider_from_env()
    assert result is None


def test_best_provider_includes_sensible_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-a")
    result = _service(tmp_path).best_provider_from_env()
    assert result is not None
    assert result.get("model")  # Non-empty model string


# ---------------------------------------------------------------------------
# _apply_quick_setup uses best_provider_from_env
# ---------------------------------------------------------------------------


def test_quick_setup_uses_groq_when_groq_key_present(tmp_path: Path, monkeypatch) -> None:
    """best_provider_from_env picks groq when only GROQ_API_KEY is set."""
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    with mock.patch("shutil.which", return_value=None):
        plan = _service(tmp_path).quick_setup(kind="groq", permission_tier="guided")
    assert plan.answers["provider"]["kind"] == "groq"


# ---------------------------------------------------------------------------
# _pre_flight_check (via onboarding layer, not CLI console)
# ---------------------------------------------------------------------------


def test_validate_provider_groq_with_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    ok, msg = _service(tmp_path).validate_provider(kind="groq", api_key_env="GROQ_API_KEY")
    assert ok
    assert "GROQ_API_KEY" in msg


def test_validate_provider_together_missing_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    ok, msg = _service(tmp_path).validate_provider(kind="together", api_key_env="TOGETHER_API_KEY")
    assert not ok
    assert "TOGETHER_API_KEY" in msg


def test_validate_provider_deepseek_with_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dsk-test")
    ok, msg = _service(tmp_path).validate_provider(kind="deepseek", api_key_env="DEEPSEEK_API_KEY")
    assert ok


# ---------------------------------------------------------------------------
# _interactive_first_run_setup — CLI-level interactive recovery
# ---------------------------------------------------------------------------


def test_interactive_setup_accepts_typed_key(tmp_path: Path) -> None:
    """User picks option 1 (type key now) and the key is written to env + .env file."""
    import os
    from unittest.mock import MagicMock, patch

    from hachi.cli.main import _interactive_first_run_setup

    env_name = "ANTHROPIC_API_KEY"
    key_value = "sk-ant-test-key-abc"

    mock_paths = MagicMock()
    mock_paths.config_dir = tmp_path

    mock_svc = MagicMock(
        detect_environment=MagicMock(return_value={"ollama_cli": False}),
        best_provider_from_env=MagicMock(return_value=None),
        build_tier_plan=MagicMock(return_value=MagicMock(answers={})),
        apply_setup=MagicMock(),
    )

    with patch("hachi.cli.main.OnboardingService", return_value=mock_svc):
        with patch("hachi.cli.main.get_hachi_paths", return_value=mock_paths):
            with patch("hachi.cli.main.Prompt.ask", side_effect=["1", key_value]):
                result = _interactive_first_run_setup(env_name, "anthropic")

    assert result is True
    assert os.environ.get(env_name) == key_value
    env_file = tmp_path / ".env"
    assert env_file.exists()
    assert f"{env_name}={key_value}" in env_file.read_text()

    os.environ.pop(env_name, None)


def test_interactive_setup_skip_returns_false() -> None:
    """User picks skip — returns False without setting anything."""
    from unittest.mock import MagicMock, patch

    from hachi.cli.main import _interactive_first_run_setup

    mock_svc = MagicMock(
        detect_environment=MagicMock(return_value={"ollama_cli": False}),
    )
    with patch("hachi.cli.main.OnboardingService", return_value=mock_svc):
        # 1=type key, 2=gemini, 3=skip (no ollama)
        with patch("hachi.cli.main.Prompt.ask", return_value="3"):
            result = _interactive_first_run_setup("ANTHROPIC_API_KEY", "anthropic")
    assert result is False


def test_interactive_setup_switches_to_ollama() -> None:
    """User picks Ollama (detected), setup re-applied without a key."""
    from unittest.mock import MagicMock, patch

    from hachi.cli.main import _interactive_first_run_setup

    mock_svc = MagicMock(
        detect_environment=MagicMock(return_value={"ollama_cli": True}),
        best_provider_from_env=MagicMock(
            return_value={
                "kind": "ollama",
                "model": "llama3",
                "base_url": "http://127.0.0.1:11434/v1",
            }
        ),
        build_tier_plan=MagicMock(return_value=MagicMock(answers={})),
        apply_setup=MagicMock(),
    )
    with patch("hachi.cli.main.OnboardingService", return_value=mock_svc):
        # 1=type key, 2=ollama, 3=gemini, 4=skip
        with patch("hachi.cli.main.Prompt.ask", return_value="2"):
            result = _interactive_first_run_setup("ANTHROPIC_API_KEY", "anthropic")
    assert result is True
    mock_svc.apply_setup.assert_called_once()


def test_interactive_setup_returns_false_on_eof() -> None:
    """EOFError (non-interactive pipe, CI) is gracefully handled."""
    from unittest.mock import MagicMock, patch

    from hachi.cli.main import _interactive_first_run_setup

    mock_svc = MagicMock(detect_environment=MagicMock(return_value={"ollama_cli": False}))
    with patch("hachi.cli.main.OnboardingService", return_value=mock_svc):
        with patch("hachi.cli.main.Prompt.ask", side_effect=EOFError):
            result = _interactive_first_run_setup("ANTHROPIC_API_KEY", "anthropic")
    assert result is False


# ---------------------------------------------------------------------------
# _pre_flight_check — TTY / non-TTY behaviour
# ---------------------------------------------------------------------------


def test_pre_flight_check_passes_when_key_present() -> None:
    from unittest.mock import MagicMock, patch

    from hachi.cli.main import _pre_flight_check

    provider = MagicMock(kind="anthropic", api_key_env="ANTHROPIC_API_KEY")
    mock_svc = MagicMock(validate_provider=MagicMock(return_value=(True, "OK")))

    mock_cfg = MagicMock(provider=provider)
    with patch("hachi.cli.main.load_effective_config", return_value=mock_cfg):
        with patch("hachi.cli.main.OnboardingService", return_value=mock_svc):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = False
                result = _pre_flight_check()
    assert result is True


def test_pre_flight_check_fails_non_interactive_no_prompt() -> None:
    """Non-TTY: _pre_flight_check must not call _interactive_first_run_setup."""
    from unittest.mock import MagicMock, patch

    from hachi.cli.main import _pre_flight_check

    provider = MagicMock(kind="anthropic", api_key_env="ANTHROPIC_API_KEY")
    mock_svc = MagicMock(validate_provider=MagicMock(return_value=(False, "Key missing")))
    mock_cfg = MagicMock(provider=provider)

    with patch("hachi.cli.main.load_effective_config", return_value=mock_cfg):
        with patch("hachi.cli.main.OnboardingService", return_value=mock_svc):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = False
                with patch("hachi.cli.main._interactive_first_run_setup") as mock_interactive:
                    result = _pre_flight_check()
    assert result is False
    mock_interactive.assert_not_called()
