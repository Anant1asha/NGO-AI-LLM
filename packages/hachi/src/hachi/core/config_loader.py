from __future__ import annotations

import logging
import os
import stat
import sys
import tomllib
from pathlib import Path
from typing import Any

import tomlkit

from hachi.core.paths import (
    HachiPaths,
    ensure_directories,
    get_hachi_paths,
)
from hachi.core.settings import ResolvedConfig, default_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known top-level keys in ResolvedConfig (read from model fields — not hard-coded)
# ---------------------------------------------------------------------------


def _known_config_keys() -> frozenset[str]:
    """Return the set of top-level key names declared on ResolvedConfig."""
    return frozenset(ResolvedConfig.model_fields.keys())


# ---------------------------------------------------------------------------
# File-permission safety check
# ---------------------------------------------------------------------------


def _check_file_permissions(path: Path, *, strict: bool = False) -> None:
    """Warn (or abort under strict) if *path* is world-writable on POSIX.

    On Windows the ``stat`` mode bits are not meaningful for world-writability
    (Windows uses ACLs), so the check is skipped silently.

    Args:
        path: The settings file to inspect.
        strict: When ``True``, raise :class:`PermissionError` instead of
            logging a warning.
    """
    if sys.platform == "win32":
        return  # ACL-based; mode bits are not reliable — skip silently
    try:
        mode = path.stat().st_mode
    except OSError:
        return  # File missing or inaccessible — let the caller handle it
    if mode & stat.S_IWOTH:
        msg = (
            f"SECURITY: settings file {path} is world-writable (mode {oct(mode)}). "
            "An unprivileged process could tamper with agent configuration. "
            'Fix with: chmod o-w "' + str(path) + '"'
        )
        if strict:
            raise PermissionError(msg)
        logger.warning(msg)


# ---------------------------------------------------------------------------
# Unknown-key validation
# ---------------------------------------------------------------------------


def _warn_unknown_keys(parsed: dict[str, Any], path: Path, *, strict: bool = False) -> None:
    """Compare *parsed* TOML against known ResolvedConfig fields and warn/raise on unknowns.

    Only top-level keys are checked — sub-section extra keys are silently
    ignored by Pydantic's ``extra="ignore"`` setting on each nested model.

    Args:
        parsed: The raw TOML dict just loaded from *path*.
        path: The file path (for error messages only).
        strict: When ``True``, raise :class:`ValueError` listing all unknown keys.
    """
    known = _known_config_keys()
    unknown = sorted(set(parsed.keys()) - known)
    if not unknown:
        return
    msg = (
        f"settings file {path} contains unknown top-level key(s): "
        f"{', '.join(unknown)}. "
        "These keys are ignored. Check for typos or consult settings.example.toml."
    )
    if strict:
        raise ValueError(msg)
    logger.warning(msg)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_toml(
    path: Path,
    *,
    primary: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    """Read a TOML settings file and return its contents as a dict.

    Args:
        path: The TOML file to read.
        primary: When ``True``, a malformed file emits a louder, actionable
            error message (the user's session will run on defaults — they need
            to know). Secondary/project files get the quieter path.
        strict: When ``True``, raise on malformed TOML or unknown top-level keys
            (can also be triggered by ``HACHI_CONFIG_STRICT=1``).

    Returns:
        Parsed TOML as a plain ``dict``, or ``{}`` on any read/parse error.
    """
    strict = strict or bool(os.environ.get("HACHI_CONFIG_STRICT"))
    if not path.exists():
        return {}
    _check_file_permissions(path, strict=strict)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        if primary:
            logger.error(
                "PRIMARY settings file %s is malformed and was IGNORED. "
                "Hachi is running on built-in defaults. "
                "Fix the file or delete it to restore normal operation. "
                "Parse error: %s",
                path,
                exc,
            )
        else:
            # A corrupt secondary config must not crash every command.
            logger.warning("Ignoring malformed config %s: %s", path, exc)
        if strict:
            raise
        return {}
    _warn_unknown_keys(raw, path, strict=strict)
    return raw


def _read_env_file(project_dir: Path | None) -> dict[str, str]:
    if not project_dir:
        return {}

    env_path = project_dir / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_overrides(
    project_dir: Path | None,
    base_provider: dict[str, Any] | None = None,
    *,
    has_explicit_provider: bool = False,
) -> dict[str, Any]:
    env_file = _read_env_file(project_dir)
    current_provider = dict(base_provider or {})
    base_kind = str(current_provider.get("kind", "")).strip().lower()

    def env_get(name: str) -> str | None:
        return os.environ.get(name) or env_file.get(name)

    result: dict[str, Any] = {}

    # When the user has written an explicit provider choice to their config file,
    # honour it — don't let env-var auto-detection override it.  Only
    # HACHI_MODEL is still respected as an explicit per-run override.
    if has_explicit_provider:
        explicit_model = env_get("HACHI_MODEL")
        if explicit_model:
            result = _deep_merge(result, {"provider": {"model": explicit_model}})
    else:
        has_anthropic = bool(env_get("ANTHROPIC_API_KEY"))
        openai_key = env_get("OPENAI_API_KEY")
        openai_base = env_get("OPENAI_BASE_URL")
        has_openai = bool(openai_key or openai_base)
        has_ollama = bool(env_get("OLLAMA_HOST"))

        if has_anthropic:
            provider_payload: dict[str, Any] = {
                "kind": "anthropic",
                "api_key_env": "ANTHROPIC_API_KEY",
            }
            explicit_model = env_get("HACHI_MODEL")
            if explicit_model:
                provider_payload["model"] = explicit_model
            elif not (has_openai or has_ollama) and base_kind != "anthropic":
                provider_payload["model"] = "claude-haiku-4-5"
            result = _deep_merge(result, {"provider": provider_payload})

        if has_openai:
            provider_payload = {
                "kind": "openai-compatible",
                "api_key_env": "OPENAI_API_KEY",
            }
            if openai_base:
                provider_payload["base_url"] = openai_base
            explicit_model = env_get("OPENAI_MODEL")
            if explicit_model:
                provider_payload["model"] = explicit_model
            elif not has_ollama and base_kind != "openai-compatible":
                provider_payload["model"] = "gpt-4o-mini"
            result = _deep_merge(result, {"provider": provider_payload})

        if has_ollama:
            provider_payload = {
                "kind": "ollama",
                "base_url": env_get("OLLAMA_HOST"),
            }
            explicit_model = env_get("OLLAMA_MODEL")
            if explicit_model:
                provider_payload["model"] = explicit_model
            elif base_kind != "ollama":
                provider_payload["model"] = "llama3.1:8b"
            result = _deep_merge(result, {"provider": provider_payload})

    if env_get("HACHI_PERMISSION_TIER"):
        result = _deep_merge(result, {"permissions": {"tier": env_get("HACHI_PERMISSION_TIER")}})

    if env_get("HACHI_MAX_TOKENS"):
        try:
            max_tokens = int(env_get("HACHI_MAX_TOKENS") or "8192")
            result = _deep_merge(result, {"agent": {"max_tokens": max_tokens}})
        except ValueError:
            pass

    return result


def _project_config(project_dir: Path | None, *, strict: bool = False) -> dict[str, Any]:
    if not project_dir:
        return {}
    return _read_toml(project_dir / ".hachi" / "settings.toml", strict=strict)


def load_effective_config(
    project_dir: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    paths: HachiPaths | None = None,
    *,
    strict: bool = False,
) -> ResolvedConfig:
    """Build the merged :class:`ResolvedConfig` from all config sources.

    Sources (lowest → highest precedence):
        built-in defaults → global settings.toml → project .hachi/settings.toml
        → environment variables / .env → cli_overrides.

    Args:
        project_dir: Optional project root; enables per-project config.
        cli_overrides: Ad-hoc overrides from CLI flags (highest precedence).
        paths: Override the resolved :class:`HachiPaths` (useful in tests).
        strict: When ``True`` (or ``HACHI_CONFIG_STRICT=1``), raise on unknown
            keys or world-writable settings file instead of logging a warning.
    """
    strict = strict or bool(os.environ.get("HACHI_CONFIG_STRICT"))
    paths = paths or get_hachi_paths()
    ensure_directories(paths)

    defaults = default_config().model_dump(mode="python")
    global_config = _read_toml(paths.global_config_toml, primary=True, strict=strict)

    project = _project_config(project_dir, strict=strict)
    pre_env = _deep_merge(_deep_merge(defaults, global_config), project)
    # Detect whether the user has explicitly written a provider kind to their
    # config files.  When true, env-var auto-detection must not override it.
    has_explicit_provider = bool(
        global_config.get("provider", {}).get("kind") or project.get("provider", {}).get("kind")
    )
    env = _env_overrides(
        project_dir,
        base_provider=pre_env.get("provider", {}),
        has_explicit_provider=has_explicit_provider,
    )
    cli = cli_overrides or {}

    merged = defaults
    for layer in (global_config, project, env, cli):
        merged = _deep_merge(merged, layer)

    return ResolvedConfig.model_validate(merged)


def write_global_config(config: ResolvedConfig, paths: HachiPaths | None = None) -> Path:
    paths = paths or get_hachi_paths()
    ensure_directories(paths)

    if paths.global_config_toml.exists():
        doc = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
    else:
        doc = tomlkit.document()
        doc.add(tomlkit.comment("Hachi user settings"))

    payload = config.model_dump(mode="python", exclude_none=True)
    # Don't write an empty providers table — it's the default and would clutter the file.
    if not payload.get("providers"):
        payload.pop("providers", None)
    # Same for channels: only persist once a channel actually has configuration
    # (e.g. a Telegram allowlist), otherwise it just adds an empty table.
    channels = payload.get("channels") or {}
    if not channels.get("telegram", {}).get("allowlist"):
        payload.pop("channels", None)
    # Same for limits: only persist once a cap is actually set, else it's an empty table.
    if not payload.get("limits"):
        payload.pop("limits", None)
    for key, value in payload.items():
        doc[key] = value

    # Atomic write: serialize to a temp file then os.replace, so a crash mid-write
    # can't truncate settings.toml (which would silently reset the user's config).
    target: Path = paths.global_config_toml
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_text(tomlkit.dumps(doc), encoding="utf-8")
    os.replace(tmp, target)
    return target
