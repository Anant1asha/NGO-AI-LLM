"""ProviderRegistry — capability-indexed store of provider adapters.

All provider types (AIProvider, SpeechProvider, SearchProvider, StorageProvider,
Embedder) are registered here and looked up by capability.

Factory method ``from_config`` builds adapters for every configured/auto-detected
provider from :class:`~hachi.core.settings.ResolvedConfig`.
"""

from __future__ import annotations

import logging
from typing import Any

from hachi.core.providers.base import (
    AIProvider,
    Embedder,
    ProviderHealth,
    SearchProvider,
    SpeechProvider,
    StorageProvider,
)
from hachi.core.routing.capability import Capability

logger = logging.getLogger(__name__)

# Union of all provider types for the registry.
AnyProvider = AIProvider | SpeechProvider | SearchProvider | StorageProvider | Embedder


class ProviderRegistry:
    """Registry that maps capabilities to provider instances.

    Amendment A6: one adapter class may implement multiple Protocols; the registry
    indexes it under every capability it advertises.
    """

    def __init__(self) -> None:
        self._providers: list[Any] = []
        self._by_name: dict[str, Any] = {}
        self._by_capability: dict[Capability, list[Any]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(
        self,
        provider: Any,
    ) -> None:
        """Add a provider to the registry, indexed by its capabilities.

        Args:
            provider: Any object that implements one or more provider protocols.
                      It must have a ``name`` attribute and a ``capabilities()`` method.
        """
        name: str = getattr(provider, "name", "")
        if name in self._by_name:
            logger.debug("ProviderRegistry: replacing provider %r", name)

        self._by_name[name] = provider
        if provider not in self._providers:
            self._providers.append(provider)

        try:
            caps: set[Capability] = provider.capabilities()
        except Exception:
            caps = set()

        for cap in caps:
            self._by_capability.setdefault(cap, [])
            if provider not in self._by_capability[cap]:
                self._by_capability[cap].append(provider)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def providers_for(self, cap: Capability) -> list[Any]:
        """Return all providers that advertise *cap*."""
        return list(self._by_capability.get(cap, []))

    def llm_providers(self) -> list[AIProvider]:
        """Return all registered AI (LLM) providers."""
        from hachi.core.providers.base import AIProvider

        return [p for p in self._providers if isinstance(p, AIProvider)]

    def get_speech(self, cap: Capability) -> SpeechProvider | None:
        """Return the first SpeechProvider that advertises *cap*, or ``None``."""
        from hachi.core.providers.base import SpeechProvider

        for p in self._by_capability.get(cap, []):
            if isinstance(p, SpeechProvider):
                return p
        return None

    def get_search(self) -> SearchProvider | None:
        """Return the first registered SearchProvider, or ``None``."""
        from hachi.core.providers.base import SearchProvider

        for p in self._providers:
            if isinstance(p, SearchProvider):
                return p
        return None

    def get_by_name(self, name: str) -> Any | None:
        """Look up a provider by its registry key (``provider.name``)."""
        return self._by_name.get(name)

    def health(self) -> dict[str, ProviderHealth]:
        """Return health snapshots for all registered providers."""
        result: dict[str, ProviderHealth] = {}
        for p in self._providers:
            try:
                h: ProviderHealth = p.health()
                result[h.provider] = h
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: Any, secret_store: Any = None) -> ProviderRegistry:
        """Build a :class:`ProviderRegistry` from :class:`~hachi.core.settings.ResolvedConfig`.

        Reads ``config.provider`` (the primary provider) and ``config.providers``
        (additional named providers).  Each is wrapped in the appropriate adapter
        and registered.

        Credentials are resolved lazily (at ``build_llm_client`` call time) so this
        method is safe to call during boot without a network round-trip.

        Args:
            config: A :class:`~hachi.core.settings.ResolvedConfig` instance.
            secret_store: Optional :class:`~hachi.core.secret_store.SecretStore`.

        Returns:
            A populated :class:`ProviderRegistry`.
        """
        from hachi.core.providers.anthropic_provider import AnthropicProvider
        from hachi.core.providers.openai_compat_provider import OpenAICompatProvider

        reg = cls()

        _OPENAI_COMPAT_KINDS = frozenset(
            {
                "openai",
                "openai-compatible",
                "openrouter",
                "groq",
                "together",
                "deepseek",
                "ollama",
                "gemini",
            }
        )

        def _register_provider_config(pcfg: Any) -> None:
            """Register one ProviderSettings (or dict-like) entry."""
            if isinstance(pcfg, dict):
                kind = str(pcfg.get("kind", "anthropic")).lower()
                cfg_dict: dict[str, Any] = dict(pcfg)
            else:
                kind = str(getattr(pcfg, "kind", "anthropic")).lower()
                # Convert Pydantic model to dict for create_llm_client.
                try:
                    cfg_dict = pcfg.model_dump()
                except AttributeError:
                    cfg_dict = {}
                    for attr in ("kind", "model", "base_url", "api_key_ref", "api_key_env"):
                        val = getattr(pcfg, attr, None)
                        if val is not None:
                            cfg_dict[attr] = val

            if kind == "anthropic":
                reg.register(AnthropicProvider(provider_config=cfg_dict, secret_store=secret_store))
            elif kind in _OPENAI_COMPAT_KINDS:
                reg.register(
                    OpenAICompatProvider(
                        kind=kind, provider_config=cfg_dict, secret_store=secret_store
                    )
                )
            else:
                logger.warning(
                    "ProviderRegistry.from_config: unknown provider kind %r — skipped", kind
                )

        # Primary provider.
        primary = getattr(config, "provider", None)
        if primary is not None:
            _register_provider_config(primary)
        elif isinstance(config, dict):
            _register_provider_config(config.get("provider", {"kind": "anthropic"}))

        # Named additional providers.
        additional: dict[str, Any] = {}
        if hasattr(config, "providers"):
            additional = getattr(config, "providers", {}) or {}
        elif isinstance(config, dict):
            additional = config.get("providers", {}) or {}

        for _name, pcfg in additional.items():
            try:
                _register_provider_config(pcfg)
            except Exception:
                logger.warning(
                    "ProviderRegistry.from_config: failed to register provider %r",
                    _name,
                    exc_info=True,
                )

        # Speech provider (Initiative F): build from [voice] config with HACHI_STT_*/HACHI_TTS_*
        # env fallback.  Registered only when at least one backend is configured (api key present).
        try:
            from hachi.core.providers.speech import OpenAICompatibleSpeechProvider
            from hachi.core.resilience import RetryPolicy

            _retry = RetryPolicy.from_config(config)
            _voice_cfg = getattr(config, "voice", None)
            _speech = OpenAICompatibleSpeechProvider.from_config(_voice_cfg, retry_policy=_retry)
            if _speech.capabilities():
                reg.register(_speech)
                logger.debug(
                    "ProviderRegistry: registered speech provider with caps=%s",
                    _speech.capabilities(),
                )
        except Exception:
            logger.debug(
                "ProviderRegistry.from_config: speech provider init skipped (no key or error)",
                exc_info=False,
            )

        # Search provider (Initiative A / Issue 5): register TavilySearchProvider when:
        #   (a) config.search.provider == "tavily", OR
        #   (b) TAVILY_API_KEY env var is set, OR
        #   (c) the secret store holds a "tavily_api_key" entry.
        # The provider itself resolves the key lazily at call time; we only decide
        # here whether to register the adapter (defensively, no network call).
        try:
            import os as _os

            _search_cfg = getattr(config, "search", None)
            _search_provider_name = (
                getattr(_search_cfg, "provider", None) if _search_cfg is not None else None
            )
            _tavily_by_config = (
                _search_provider_name and str(_search_provider_name).lower() == "tavily"
            )

            # Resolve key availability without triggering a network round-trip.
            _tavily_env_key = bool(_os.environ.get("TAVILY_API_KEY", "").strip())
            _tavily_store_key = False
            if not _tavily_env_key and secret_store is not None:
                # The integrations UI stores the key namespaced as
                # "apikey.tavily.tavily_api_key" (oauth_flow.store_apikey_credential),
                # while `hachi set tavily_api_key=...` stores the bare name. Check both.
                for _k in ("apikey.tavily.tavily_api_key", "tavily_api_key"):
                    try:
                        _stored = secret_store.get(_k)
                    except Exception:
                        _stored = None
                    if _stored and str(_stored).strip():
                        _tavily_store_key = True
                        break

            if _tavily_by_config or _tavily_env_key or _tavily_store_key:
                from hachi.core.providers.tavily_provider import TavilySearchProvider
                from hachi.core.resilience import RetryPolicy as _RetryPolicy

                _search_retry = _RetryPolicy.from_config(config)
                _tavily = TavilySearchProvider(
                    secret_store=secret_store,
                    retry_policy=_search_retry,
                )
                reg.register(_tavily)
                logger.debug(
                    "ProviderRegistry: registered Tavily search provider "
                    "(by_config=%s, env=%s, store=%s)",
                    _tavily_by_config,
                    _tavily_env_key,
                    _tavily_store_key,
                )
        except Exception:
            logger.debug(
                "ProviderRegistry.from_config: search provider init skipped (no key or error)",
                exc_info=False,
            )

        return reg
