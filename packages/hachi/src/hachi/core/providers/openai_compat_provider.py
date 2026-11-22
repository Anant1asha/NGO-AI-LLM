"""OpenAI-compatible provider adapter.

Wraps :class:`~hachi.core.llm.OpenAICompatibleClient` (and its variants via
:func:`~hachi.core.llm.create_llm_client`) and advertises capabilities for
vision-capable presets plus STT/TTS/embeddings when the endpoint is set.

Covers all ``kind`` values that are OpenAI-wire-compatible: ``"openai"``,
``"openai-compatible"``, ``"openrouter"``, ``"groq"``, ``"together"``,
``"deepseek"``, ``"ollama"``, ``"gemini"``.
"""

from __future__ import annotations

import logging
from typing import Any

from hachi.core.llm import BaseLLMClient, create_llm_client
from hachi.core.providers.base import ProviderHealth
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import BUNDLED_MODEL_DEFAULTS, ModelDescriptor

logger = logging.getLogger(__name__)

# Providers in this set advertise VISION capability.
_VISION_CAPABLE_KINDS: frozenset[str] = frozenset({"openai", "openai-compatible", "openrouter"})

_OPENAI_DEFAULTS: list[ModelDescriptor] = [
    d for d in BUNDLED_MODEL_DEFAULTS if d.provider == "openai"
]


class OpenAICompatProvider:
    """AIProvider adapter for OpenAI-compatible endpoints.

    Args:
        kind: The provider kind string (``"openai"``, ``"groq"``, etc.).
        provider_config: Dict-compatible config for :func:`~hachi.core.llm.create_llm_client`.
        secret_store: Optional credential store.
    """

    def __init__(
        self,
        kind: str = "openai",
        provider_config: dict[str, Any] | None = None,
        secret_store: Any = None,
    ) -> None:
        self._kind = kind
        self._provider_config: dict[str, Any] = provider_config or {"kind": kind}
        self._secret_store = secret_store
        self._health = ProviderHealth(provider=self.name)

    @property
    def name(self) -> str:
        """Provider registry key (matches the ``kind`` string)."""
        return self._kind

    def capabilities(self) -> set[Capability]:
        """Return capabilities for this provider kind."""
        caps: set[Capability] = {
            Capability.REASONING,
            Capability.CODING,
            Capability.SUMMARIZATION,
            Capability.TITLE_GENERATION,
            Capability.COMPACTION,
        }
        if self._kind in _VISION_CAPABLE_KINDS:
            caps.add(Capability.VISION)
        return caps

    def models(self) -> list[ModelDescriptor]:
        """Return known OpenAI model descriptors, re-homed to THIS provider's name.

        The bundled descriptors declare ``provider="openai"``; we rewrite the provider to
        this instance's registry name (e.g. ``"openai-compatible"``) so the router resolves
        them to THIS provider — which carries the configured ``base_url`` and API key —
        instead of falling back to a keyless generic ``"openai"`` client. Without this,
        routing to gpt-4o-mini built an unauthenticated client and silently ran on the
        primary model instead (Issue 11).
        """
        if self._kind in ("openai", "openai-compatible"):
            return [d.model_copy(update={"provider": self.name}) for d in _OPENAI_DEFAULTS]
        # Other compat providers: no bundled descriptors; let config overrides fill them.
        return []

    def build_llm_client(self, model_id: str, **opts: Any) -> BaseLLMClient:
        """Build an :class:`~hachi.core.llm.OpenAICompatibleClient` for *model_id*.

        Args:
            model_id: The model identifier.
            **opts: Forwarded to ``create_llm_client``.
        """
        config = dict(self._provider_config)
        config["model"] = model_id
        config.setdefault("kind", self._kind)
        max_tokens: int = int(opts.pop("max_tokens", 4096))
        return create_llm_client(config, secret_store=self._secret_store, max_tokens=max_tokens)

    def health(self) -> ProviderHealth:
        """Return the current health snapshot."""
        return self._health

    def update_health(self, health: ProviderHealth) -> None:
        """Replace the stored health snapshot."""
        self._health = health
