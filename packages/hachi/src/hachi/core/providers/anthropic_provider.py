"""Anthropic provider adapter.

Thin wrapper around :class:`~hachi.core.llm.AnthropicClient` that advertises
capabilities and models via the :class:`~hachi.core.providers.base.AIProvider`
protocol.

This is one of TWO authorised import sites for the ``anthropic`` SDK (the other
being ``core/llm.py``).  All other modules must use ``BaseLLMClient``.
"""

from __future__ import annotations

import logging
from typing import Any

from hachi.core.llm import BaseLLMClient, create_llm_client
from hachi.core.providers.base import AIProvider, ProviderHealth  # noqa: F401 (Protocol)
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import BUNDLED_MODEL_DEFAULTS, ModelDescriptor

logger = logging.getLogger(__name__)

# Capabilities that every Anthropic model exposes at the provider level.
_ANTHROPIC_CAPABILITIES: set[Capability] = {
    Capability.REASONING,
    Capability.CODING,
    Capability.SUMMARIZATION,
    Capability.TITLE_GENERATION,
    Capability.COMPACTION,
    Capability.LONG_CONTEXT,
    Capability.VISION,
}

_ANTHROPIC_DEFAULTS: list[ModelDescriptor] = [
    d for d in BUNDLED_MODEL_DEFAULTS if d.provider == "anthropic"
]


class AnthropicProvider:
    """AIProvider adapter for Anthropic (wraps ``create_llm_client`` in llm.py).

    Args:
        provider_config: Dict-compatible config (matches what
            :func:`~hachi.core.llm.create_llm_client` accepts).  Used to
            resolve API keys without importing the Anthropic SDK here.
        secret_store: Optional :class:`~hachi.core.secret_store.SecretStore` for
            credential resolution.
    """

    name = "anthropic"

    def __init__(
        self,
        provider_config: dict[str, Any] | None = None,
        secret_store: Any = None,
    ) -> None:
        self._provider_config: dict[str, Any] = provider_config or {"kind": "anthropic"}
        self._secret_store = secret_store
        self._health = ProviderHealth(provider=self.name)

    # ------------------------------------------------------------------
    # AIProvider protocol
    # ------------------------------------------------------------------

    def capabilities(self) -> set[Capability]:
        """Return the capabilities this provider supports."""
        return _ANTHROPIC_CAPABILITIES

    def models(self) -> list[ModelDescriptor]:
        """Return the bundled Anthropic model descriptors.

        A live ``list_models()`` call is NOT made here — that's the registry
        build step's job via provider-advertised discovery.
        """
        return _ANTHROPIC_DEFAULTS

    def build_llm_client(self, model_id: str, **opts: Any) -> BaseLLMClient:
        """Build an :class:`~hachi.core.llm.AnthropicClient` for *model_id*.

        Args:
            model_id: The Anthropic model identifier.
            **opts: Forwarded to ``create_llm_client`` (e.g. ``max_tokens``).
        """
        config = dict(self._provider_config)
        config["model"] = model_id
        config.setdefault("kind", "anthropic")
        max_tokens: int = int(opts.pop("max_tokens", 4096))
        return create_llm_client(config, secret_store=self._secret_store, max_tokens=max_tokens)

    def health(self) -> ProviderHealth:
        """Return the current health snapshot."""
        return self._health

    def update_health(self, health: ProviderHealth) -> None:
        """Replace the stored health snapshot (called by the resilience layer)."""
        self._health = health
