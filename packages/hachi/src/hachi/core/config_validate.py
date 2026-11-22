"""Pure validation checks over a resolved Hachi configuration.

Separated from the CLI so the rules are unit-testable without I/O. The CLI
(`hachi config-validate`) supplies the loaded config plus the provider
API-key check result (which is network/env-bound) and renders the report.
"""

from __future__ import annotations

from typing import Any

from hachi.core.settings import PermissionTier, ProviderKind

# Derived from the settings Literals so this stays in sync with the schema.
_VALID_KINDS = set(ProviderKind.__args__)
_VALID_TIERS = set(PermissionTier.__args__)


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def validate_config(
    config: Any,
    *,
    provider_key_ok: bool | None = None,
    provider_key_detail: str = "",
) -> dict[str, Any]:
    """Run the schema/consistency checks over a resolved ``config``.

    Args:
        config: A resolved config object (``ResolvedConfig``) with ``provider``,
            ``permissions``, and ``agent`` sections.
        provider_key_ok: Result of the provider API-key check (network/env-bound,
            done by the caller). ``None`` skips that check.
        provider_key_detail: Human-readable detail for the key check.

    Returns:
        ``{"ok": bool, "checks": [{"name", "ok", "detail"}, ...]}``.
    """
    provider = getattr(config, "provider", None)
    permissions = getattr(config, "permissions", None)
    agent = getattr(config, "agent", None)

    checks: list[dict[str, Any]] = []

    kind = getattr(provider, "kind", "")
    checks.append(
        _check(
            "provider_kind",
            kind in _VALID_KINDS,
            f"kind='{kind}'" if kind in _VALID_KINDS else f"unknown provider kind: {kind!r}",
        )
    )

    tier = getattr(permissions, "tier", "")
    checks.append(
        _check(
            "permission_tier",
            tier in _VALID_TIERS,
            f"tier='{tier}'" if tier in _VALID_TIERS else f"unknown permission tier: {tier!r}",
        )
    )

    max_tokens = getattr(agent, "max_tokens", 0)
    checks.append(
        _check(
            "max_tokens",
            isinstance(max_tokens, int) and max_tokens > 0,
            f"max_tokens={max_tokens}",
        )
    )

    # The model guardrail: if an allowlist is configured, the active model must be
    # in it — otherwise the configured model can never actually be selected.
    model = getattr(provider, "model", "")
    allowed = list(getattr(provider, "allowed_models", []) or [])
    if allowed:
        in_list = model in allowed
        checks.append(
            _check(
                "model_allowlist",
                in_list,
                f"model '{model}' is in allowed_models"
                if in_list
                else f"configured model '{model}' is NOT in allowed_models {allowed} "
                "— it would be blocked",
            )
        )

    if provider_key_ok is not None:
        checks.append(_check("provider_api_key", provider_key_ok, provider_key_detail))

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
