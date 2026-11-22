from __future__ import annotations

from pathlib import Path

from hachi.core.config_loader import load_effective_config
from hachi.core.paths import HachiPaths


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def test_config_precedence_explicit_provider_wins_over_env(monkeypatch, tmp_path: Path) -> None:
    """Explicit provider.kind in the config file must not be overridden by env vars.

    The old behaviour (env always won) caused bug reports where switching from
    OpenAI → Anthropic in the setup wizard had no effect while OPENAI_API_KEY
    was still present in the environment.
    """
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)

    (paths.config_dir / "settings.toml").write_text(
        """
[provider]
kind = "anthropic"
model = "global-model"
""",
        encoding="utf-8",
    )

    project_dir = tmp_path / "project"
    (project_dir / ".hachi").mkdir(parents=True, exist_ok=True)
    (project_dir / ".hachi" / "settings.toml").write_text(
        """
[provider]
model = "project-model"
""",
        encoding="utf-8",
    )
    (project_dir / ".env").write_text(
        "OPENAI_API_KEY=testkey\nOPENAI_MODEL=env-model\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    cfg = load_effective_config(
        project_dir=project_dir,
        cli_overrides={"provider": {"model": "cli-model"}},
        paths=paths,
    )

    # Explicit config kind must survive; CLI model override must still apply.
    assert cfg.provider.kind == "anthropic"
    assert cfg.provider.model == "cli-model"


def test_config_precedence_env_auto_detects_without_explicit_config(
    monkeypatch, tmp_path: Path
) -> None:
    """When no config file has been written, env vars auto-detect the provider."""
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)

    project_dir = tmp_path / "project"
    (project_dir / ".hachi").mkdir(parents=True, exist_ok=True)
    (project_dir / ".env").write_text("OPENAI_API_KEY=testkey\n", encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cfg = load_effective_config(project_dir=project_dir, paths=paths)

    # No explicit config → env-var detection should kick in.
    assert cfg.provider.kind == "openai-compatible"


def test_env_numeric_parse_failure_does_not_override_agent_tokens(
    monkeypatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HACHI_MAX_TOKENS", "not-a-number")

    cfg = load_effective_config(paths=paths)

    assert cfg.agent.max_tokens == 8192


def test_env_file_with_malformed_quotes_is_tolerated(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)

    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".env").write_text(
        'OPENAI_API_KEY="unterminated\nOPENAI_MODEL=env-model\n',
        encoding="utf-8",
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    cfg = load_effective_config(project_dir=project_dir, paths=paths)

    assert cfg.provider.kind == "openai-compatible"
    assert cfg.provider.model == "env-model"


def test_openai_default_model_is_catalog_member(monkeypatch, tmp_path: Path) -> None:
    """config_loader must not default to a model id that is absent from the registry.

    gpt-4.1-mini is not in BUNDLED_MODEL_DEFAULTS, so using it as the fallback model
    breaks cost tracking and model-selection UI (Bug 1).
    """
    from hachi.core.routing.registry import ModelRegistry

    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    cfg = load_effective_config(paths=paths)
    default_model = cfg.provider.model

    reg = ModelRegistry.build(object(), None)
    assert reg.get(default_model) is not None, (
        f"Default model {default_model!r} is not in ModelRegistry catalog — "
        "cost tracking and model-selection UI will be broken"
    )


def test_openai_key_env_does_not_reset_existing_openai_model(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)

    (paths.config_dir / "settings.toml").write_text(
        """
[provider]
kind = "openai-compatible"
model = "gpt-5.4-nano"
api_key_env = "OPENAI_API_KEY"
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    cfg = load_effective_config(paths=paths)

    assert cfg.provider.kind == "openai-compatible"
    assert cfg.provider.model == "gpt-5.4-nano"
