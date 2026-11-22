from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from hachi.core.atomic_io import atomic_write_json, quarantine_corrupt_file
from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.paths import (
    HachiPaths,
    ensure_directories,
    get_hachi_paths,
)
from hachi.gateway.workspace import install_optional_skill_pack

SetupTier = Literal["lightning", "recommended", "enhanced", "power"]
SetupStep = Literal["welcome", "provider", "safety", "memory", "integrations", "advanced", "finish"]


class OnboardingState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    setup_version: int = 1
    selected_tier: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    last_seen_release: str | None = None
    migration_markers: dict[str, str] = Field(default_factory=dict)


class SetupPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tier: SetupTier
    steps: list[SetupStep] = Field(default_factory=list)
    answers: dict[str, Any] = Field(default_factory=dict)
    enable_memory: bool = True
    show_integrations: bool = False
    show_advanced: bool = False


TIER_STEP_PLANS: dict[str, list[SetupStep]] = {
    "lightning": ["welcome", "provider", "safety", "finish"],
    "recommended": ["welcome", "provider", "safety", "memory", "finish"],
    "enhanced": ["welcome", "provider", "safety", "memory", "integrations", "finish"],
    "power": ["welcome", "provider", "safety", "memory", "integrations", "advanced", "finish"],
}


_PROVIDER_KINDS = {
    "anthropic",
    "openai-compatible",
    "openrouter",
    "groq",
    "together",
    "deepseek",
    "ollama",
    "gemini",
    "chatgpt-web",
}
_PERMISSION_TIERS = {"sandbox", "guided", "unrestricted"}

# Providers that require an API key (ollama runs locally and does not).
_KEYLESS_PROVIDERS = {"ollama"}

# Sensible default model + the env var users are most likely to have set, per provider.
# Used by the conversational quickstart so non-technical users don't have to know
# model identifiers.
_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {"model": "claude-haiku-4-5", "api_key_env": "ANTHROPIC_API_KEY"},
    "openai-compatible": {"model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
    "openrouter": {"model": "openai/gpt-4o-mini", "api_key_env": "OPENROUTER_API_KEY"},
    "groq": {"model": "llama-3.3-70b-versatile", "api_key_env": "GROQ_API_KEY"},
    "together": {
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "api_key_env": "TOGETHER_API_KEY",
    },
    "deepseek": {"model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
    "ollama": {"model": "llama3.1", "api_key_env": ""},
    "gemini": {"model": "gemini-2.0-flash", "api_key_env": "GEMINI_API_KEY"},
    "chatgpt-web": {"model": "gpt-4o", "api_key_env": "CHATGPT_SESSION_TOKEN"},
}


def default_model_for(kind: str) -> str:
    """Return a reasonable default model id for a provider kind."""
    return _PROVIDER_DEFAULTS.get(kind.strip().lower(), {}).get("model", "")


def default_api_key_env_for(kind: str) -> str:
    """Return the conventional API-key env var name for a provider kind."""
    return _PROVIDER_DEFAULTS.get(kind.strip().lower(), {}).get("api_key_env", "")


def looks_like_env_var_name(value: str) -> bool:
    """True when ``value`` is shaped like an env-var NAME (UPPER_SNAKE), not a raw secret.

    Used to tell apart an ``api_key_ref`` that legitimately *references* a secret
    (e.g. ``"ANTHROPIC_API_KEY"``) from a raw key a client mistakenly placed in
    that field (e.g. ``"sk-ant-..."``, which has lowercase + hyphens).
    """
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]*", (value or "").strip()))


def persist_provider_api_key(
    kind: str,
    raw_key: str,
    *,
    api_key_env: str | None = None,
    secret_store: Any | None = None,
) -> str | None:
    """Persist a raw provider API key to the secret store + process env.

    Mirrors the TUI's paste-key flow: the key is written to the OS secret store
    (keyring) under the provider's conventional env-var name AND exported into
    ``os.environ`` for the running process, so the next LLM client build resolves
    it. The raw secret is never written to the config file — only the env-var
    *name* is (returned here, to be stored as ``api_key_ref`` / ``api_key_env``).

    Returns the env-var name, or ``None`` when there is nothing to persist
    (blank key, or a provider with no conventional env var).
    """
    key = (raw_key or "").strip()
    if not key:
        return None
    env_name = (api_key_env or default_api_key_env_for(kind) or "").strip()
    if not env_name:
        return None
    os.environ[env_name] = key  # immediate effect for the running process
    try:
        store = secret_store
        if store is None:
            from hachi.core.secret_store import create_default_secret_store

            store = create_default_secret_store()
        store.set(env_name, key)
    except Exception:
        pass  # keyring/passphrase unavailable → env-only for this process
    return env_name


def resolve_provider_model(
    kind: str,
    model: str | None,
    *,
    previous_kind: str | None = None,
    previous_model: str | None = None,
) -> str:
    """Return a provider-appropriate model, preserving explicit overrides."""
    normalized_kind = kind.strip().lower()
    default_model = default_model_for(normalized_kind)
    resolved_model = (model or "").strip()
    previous_kind_n = previous_kind.strip().lower() if previous_kind else ""
    previous_model_n = previous_model.strip() if previous_model else ""

    if previous_kind_n and previous_model_n and normalized_kind != previous_kind_n:
        if not resolved_model or resolved_model == previous_model_n:
            return default_model or resolved_model or previous_model_n

    if resolved_model:
        return resolved_model
    return default_model or previous_model_n


class OnboardingService:
    def __init__(self, paths: HachiPaths | None = None):
        self.paths: HachiPaths = paths if paths is not None else get_hachi_paths()
        ensure_directories(self.paths)

    def resume_state(self) -> OnboardingState:
        path = self.paths.onboarding_state_file
        if not path.exists():
            return OnboardingState()

        try:
            return OnboardingState.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            # BB-51: quarantine the unparseable file BEFORE returning the empty
            # default, so the next save_state() can't silently clobber it.
            quarantine_corrupt_file(path)
            return OnboardingState()

    def save_state(self, state: OnboardingState) -> Path:
        dest: Path = self.paths.onboarding_state_file
        atomic_write_json(dest, state.model_dump(mode="json"))
        return dest

    def detect_environment(self, project_dir: Path | None = None) -> dict[str, Any]:
        """Probe the runtime environment for available providers and credentials.

        Returns a flat dict of boolean flags suitable for auto-selection logic.
        Keys ending in ``_env`` mean the corresponding API-key env var is set.
        Ollama is detected by CLI presence (no key needed).
        """
        return {
            "anthropic_env": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "openai_env": bool(os.environ.get("OPENAI_API_KEY")),
            "groq_env": bool(os.environ.get("GROQ_API_KEY")),
            "together_env": bool(os.environ.get("TOGETHER_API_KEY")),
            "deepseek_env": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "openrouter_env": bool(os.environ.get("OPENROUTER_API_KEY")),
            "gemini_env": bool(
                os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY")
            ),
            "ollama_cli": shutil.which("ollama") is not None,
            "project_dir": str(project_dir) if project_dir else None,
        }

    def best_provider_from_env(self) -> dict[str, str] | None:
        """Return the highest-priority auto-detected provider config, or None.

        Priority (highest first):
        anthropic → openai-compatible → groq → together → deepseek → openrouter → gemini → ollama.
        Returns a provider dict ready for ``apply_setup`` / ``build_tier_plan``.
        """
        detected = self.detect_environment()
        if detected["anthropic_env"]:
            return {
                "kind": "anthropic",
                "model": _PROVIDER_DEFAULTS["anthropic"]["model"],
                "api_key_env": "ANTHROPIC_API_KEY",
            }
        if detected["openai_env"]:
            return {
                "kind": "openai-compatible",
                "model": _PROVIDER_DEFAULTS["openai-compatible"]["model"],
                "api_key_env": "OPENAI_API_KEY",
            }
        if detected["groq_env"]:
            return {
                "kind": "groq",
                "model": _PROVIDER_DEFAULTS["groq"]["model"],
                "api_key_env": "GROQ_API_KEY",
            }
        if detected["together_env"]:
            return {
                "kind": "together",
                "model": _PROVIDER_DEFAULTS["together"]["model"],
                "api_key_env": "TOGETHER_API_KEY",
            }
        if detected["deepseek_env"]:
            return {
                "kind": "deepseek",
                "model": _PROVIDER_DEFAULTS["deepseek"]["model"],
                "api_key_env": "DEEPSEEK_API_KEY",
            }
        if detected["openrouter_env"]:
            return {
                "kind": "openrouter",
                "model": _PROVIDER_DEFAULTS["openrouter"]["model"],
                "api_key_env": "OPENROUTER_API_KEY",
            }
        if detected["gemini_env"]:
            api_key_env = (
                "GEMINI_API_KEY" if os.environ.get("GEMINI_API_KEY") else "GOOGLE_AI_API_KEY"
            )
            return {
                "kind": "gemini",
                "model": _PROVIDER_DEFAULTS["gemini"]["model"],
                "api_key_env": api_key_env,
            }
        if detected["ollama_cli"]:
            return {
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model": _PROVIDER_DEFAULTS["ollama"]["model"],
            }
        return None

    def validate_provider(
        self,
        *,
        kind: str,
        api_key_env: str | None = None,
        api_key: str | None = None,
    ) -> tuple[bool, str]:
        """Check that a provider is usable BEFORE the first chat.

        Today a missing/typo'd API key only surfaces when the agent first tries to
        answer — the most common stumbling block for non-technical users. This
        validates the provider kind and that an API key is actually resolvable
        (passed directly, or present in the named/conventional environment
        variable). Local providers (ollama) need no key.

        Returns ``(ok, message)`` where ``message`` is human-friendly guidance.
        """
        kind_n = (kind or "").strip().lower()
        if kind_n not in _PROVIDER_KINDS:
            return False, (
                f"Unknown provider '{kind}'. Choose one of: {', '.join(sorted(_PROVIDER_KINDS))}."
            )
        if kind_n in _KEYLESS_PROVIDERS:
            return True, "Local provider — no API key required."

        env_name = (api_key_env or default_api_key_env_for(kind_n)).strip()
        resolved = api_key or (os.environ.get(env_name) if env_name else None)
        # Also check the secret store (keyring) — a key pasted during a prior
        # setup run is stored there and does not reappear in os.environ after a
        # restart, but the LLM client can still use it.
        if not resolved and env_name:
            try:
                from hachi.core.secret_store import create_default_secret_store

                resolved = create_default_secret_store().get(env_name)
            except Exception:
                pass
        if not resolved:
            return False, (
                f"No API key found for {kind_n}. Set it first, e.g.:\n"
                f"  export {env_name or 'YOUR_API_KEY_ENV'}=sk-...\n"
                "then re-run setup."
            )
        source = "keyring" if not os.environ.get(env_name) else env_name
        return True, f"API key found ({source})."

    def quick_setup(
        self,
        *,
        kind: str,
        model: str | None = None,
        api_key_env: str | None = None,
        permission_tier: str = "guided",
        enable_memory: bool = True,
        project_dir: Path | None = None,
    ) -> SetupPlan:
        """One-call conversational setup: pick provider + safety, persist, done.

        Wraps :meth:`build_tier_plan` + :meth:`apply_setup` with non-technical
        defaults (sensible model per provider, guided safety tier, memory on) so a
        brand-new user is ready after answering a couple of plain questions.
        """
        kind_n = (kind or "").strip().lower()
        if kind_n not in _PROVIDER_KINDS:
            raise ValueError(f"kind must be one of: {', '.join(sorted(_PROVIDER_KINDS))}")
        resolved_model = (model or default_model_for(kind_n)).strip()
        resolved_env = (api_key_env or default_api_key_env_for(kind_n)).strip() or None

        answers = {
            "provider": {
                "kind": kind_n,
                "model": resolved_model,
                "api_key_env": resolved_env,
            },
            "permission_tier": permission_tier,
        }
        tier = "recommended" if enable_memory else "lightning"
        plan_payload = self.build_tier_plan(tier, answers)
        return self.apply_setup(plan_payload, project_dir=project_dir)

    def needs_setup(self, project_dir: Path | None = None) -> bool:
        config = load_effective_config(project_dir=project_dir, paths=self.paths)
        state = self.resume_state()

        provider_ready = bool(config.provider.kind and config.provider.model)
        tier_ready = bool(config.permissions.tier)
        completed = set(state.completed_steps)
        is_marked_done = {"provider", "safety"}.issubset(completed)

        if not (provider_ready and tier_ready and is_marked_done):
            return True

        # Even when setup is marked done, verify the provider key is actually
        # resolvable so we route the user back to Setup instead of booting into
        # a crash.  Keyless providers (Ollama) skip this check.
        kind = str(config.provider.kind).strip().lower()
        if kind not in _KEYLESS_PROVIDERS:
            env_name = (config.provider.api_key_env or default_api_key_env_for(kind) or "").strip()
            api_key_ref = (config.provider.api_key_ref or "").strip()

            resolved: str | None = os.environ.get(env_name) if env_name else None
            if not resolved:
                lookup = api_key_ref or env_name
                if lookup:
                    try:
                        from hachi.core.secret_store import create_default_secret_store

                        resolved = create_default_secret_store().get(lookup)
                    except Exception:
                        pass
            if not resolved:
                return True

        return False

    def build_tier_plan(self, tier: str, answers: dict[str, Any]) -> dict[str, Any]:
        normalized_tier = str(tier).strip().lower()
        if normalized_tier not in TIER_STEP_PLANS:
            normalized_tier = "lightning"

        # M7 (MED-029/UX-14): memory is core to the product — enable it on ALL tiers,
        # including lightning.  The lightning tier stays fast and minimal (no memory
        # *setup step* in its flow) but the resulting config now activates memory so
        # users who choose the fastest path still benefit from retention.
        return SetupPlan(
            tier=normalized_tier,  # type: ignore[arg-type]
            steps=TIER_STEP_PLANS[normalized_tier],
            answers=dict(answers),
            enable_memory=True,
            show_integrations=normalized_tier in {"enhanced", "power"},
            show_advanced=normalized_tier == "power",
        ).model_dump(mode="python")

    def apply_setup(
        self, plan_payload: dict[str, Any], project_dir: Path | None = None
    ) -> SetupPlan:
        plan = SetupPlan.model_validate(plan_payload)
        config = load_effective_config(project_dir=project_dir, paths=self.paths)
        current_provider_kind = str(config.provider.kind).strip()
        current_provider_model = str(config.provider.model).strip()

        provider = plan.answers.get("provider", {})
        if isinstance(provider, dict):
            kind = provider.get("kind")
            model = provider.get("model")
            base_url = provider.get("base_url")
            api_key = provider.get("api_key")
            api_key_env = provider.get("api_key_env")
            api_key_ref = provider.get("api_key_ref")

            if kind is not None:
                normalized_kind = str(kind).strip()
                if normalized_kind not in _PROVIDER_KINDS:
                    raise ValueError(
                        "provider.kind must be one of: anthropic, openai-compatible, ollama"
                    )
                config.provider.kind = normalized_kind
            else:
                normalized_kind = current_provider_kind

            if model is not None:
                normalized_model = str(model).strip()
                if not normalized_model:
                    raise ValueError("provider.model cannot be empty")
                config.provider.model = resolve_provider_model(
                    normalized_kind,
                    normalized_model,
                    previous_kind=current_provider_kind,
                    previous_model=current_provider_model,
                )
            elif normalized_kind != current_provider_kind:
                config.provider.model = resolve_provider_model(
                    normalized_kind,
                    None,
                    previous_kind=current_provider_kind,
                    previous_model=current_provider_model,
                )
            if base_url is not None:
                config.provider.base_url = str(base_url).strip() or None

            # API key handling. The web wizard sends the raw key as `api_key`;
            # older clients sent it as `api_key_ref`. A raw secret must never land
            # in the config file — persist it to the secret store + process env
            # and record only the env-var NAME.
            raw_api_key = api_key
            if not raw_api_key and api_key_ref and not looks_like_env_var_name(str(api_key_ref)):
                raw_api_key = api_key_ref
                api_key_ref = None

            if api_key_env is not None:
                config.provider.api_key_env = str(api_key_env).strip() or None

            if raw_api_key:
                env_name = persist_provider_api_key(
                    normalized_kind,
                    str(raw_api_key),
                    api_key_env=config.provider.api_key_env,
                )
                if env_name:
                    config.provider.api_key_ref = env_name
                    config.provider.api_key_env = env_name
            elif api_key_ref is not None:
                config.provider.api_key_ref = str(api_key_ref).strip() or None

        safety_tier = plan.answers.get("permission_tier")
        if safety_tier is not None:
            normalized_tier = str(safety_tier).strip()
            if normalized_tier not in _PERMISSION_TIERS:
                raise ValueError("permission_tier must be one of: sandbox, guided, unrestricted")
            config.permissions.tier = normalized_tier

        memory_answers = plan.answers.get("memory", {})
        if isinstance(memory_answers, dict):
            if "enable_session_history" in memory_answers:
                value = memory_answers["enable_session_history"]
                if not isinstance(value, bool):
                    raise ValueError("memory.enable_session_history must be a boolean")
                config.memory.enable_session_history = value
            if "enable_semantic_memory" in memory_answers:
                value = memory_answers["enable_semantic_memory"]
                if not isinstance(value, bool):
                    raise ValueError("memory.enable_semantic_memory must be a boolean")
                config.memory.enable_semantic_memory = value
        elif plan.enable_memory:
            config.memory.enable_session_history = True
            config.memory.enable_semantic_memory = True

        integrations = plan.answers.get("integrations", {})
        if isinstance(integrations, dict):
            for cap_id, cap_answer in integrations.items():
                if cap_id not in config.capabilities:
                    continue

                cap_state = config.capabilities[cap_id]
                if isinstance(cap_answer, dict):
                    if "enabled" in cap_answer:
                        enabled = cap_answer["enabled"]
                        if not isinstance(enabled, bool):
                            raise ValueError(f"integrations.{cap_id}.enabled must be a boolean")
                        cap_state.enabled = enabled
                    if "configured" in cap_answer:
                        configured = cap_answer["configured"]
                        if not isinstance(configured, bool):
                            raise ValueError(f"integrations.{cap_id}.configured must be a boolean")
                        cap_state.configured = configured
                else:
                    if not isinstance(cap_answer, bool):
                        raise ValueError(f"integrations.{cap_id} must be a boolean")
                    cap_state.enabled = cap_answer

                if cap_state.enabled:
                    install_optional_skill_pack(cap_id)

        write_global_config(config, paths=self.paths)

        state = self.resume_state()
        state.selected_tier = plan.tier
        state.setup_version = max(state.setup_version, 1)
        for step in plan.steps:
            if (
                step in {"provider", "safety", "memory", "integrations", "advanced", "finish"}
                and step not in state.completed_steps
            ):
                state.completed_steps.append(step)
        self.save_state(state)

        return plan
