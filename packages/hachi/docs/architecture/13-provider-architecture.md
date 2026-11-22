# 13 — Provider Architecture

> Phase 2 / Gate B. Initiatives **B** and **I**. Contract + one impl + seam.
> Proposed interface sketches are illustrative (Phase 4 implements), idiomatic to the
> codebase (py3.11, pydantic, Protocol/ABC). Seams are `file:line`.

## 1. Problem

Today the `anthropic` SDK is cleanly confined to `core/llm.py`, `BaseLLMClient` (`:106`) is a
real contract, and `create_llm_client()` (`:644`) is a provider factory — but provider
selection is a hardcoded `kind` if-ladder, the one multi-model path forces Anthropic
(`sub_agent.py:617`), and named providers in config (`settings.py:130`) are inert. We need
providers that **advertise capabilities** and a registry that selects **by capability, not
vendor name** — without throwing away the clean `BaseLLMClient` boundary.

## 2. Contract

We **keep `BaseLLMClient`** as the LLM text/stream client contract and add a thin
capability-advertising layer above it. Non-LLM modalities get sibling provider contracts.

```python
# core/routing/capability.py
class Capability(StrEnum):
    REASONING = "reasoning";          CODING = "coding"
    SUMMARIZATION = "summarization";  TITLE_GENERATION = "title_generation"
    COMPACTION = "compaction";        LONG_CONTEXT = "long_context"
    VISION = "vision";                EMBEDDINGS = "embeddings"
    SPEECH_TO_TEXT = "speech_to_text"; TEXT_TO_SPEECH = "text_to_speech"
    WEB_SEARCH = "web_search";        REALTIME = "realtime"

# core/providers/base.py
class AIProvider(Protocol):
    """A vendor adapter. The ONLY place a vendor SDK may be imported."""
    name: str                                   # registry key, e.g. "anthropic"
    def capabilities(self) -> set[Capability]: ...
    def models(self) -> list[ModelDescriptor]: ...        # advertised LLM models (may be [])
    def build_llm_client(self, model_id: str, **opts) -> BaseLLMClient: ...
    def health(self) -> ProviderHealth: ...
```

LLM is the common case and routes through `ModelDescriptor`/`ModelRouter` ([14](14-capability-registry.md),
[15](15-model-routing.md)). **Service modalities** whose method shape is not "generate text"
get their own contracts, registered in the same registry:

```python
class SpeechProvider(Protocol):                # F
    name: str
    def capabilities(self) -> set[Capability]  # {STT}|{TTS}|both
    def transcribe(self, audio: bytes, **opts) -> str: ...
    def synthesize(self, text: str, **opts) -> bytes: ...

class SearchProvider(Protocol):                # A
    name: str
    def search(self, query: str, **opts) -> list[SearchResult]: ...
    def extract(self, url: str, **opts) -> ExtractResult: ...

class StorageProvider(Protocol): ...           # E (see 18)
class Embedder(Protocol): ...                  # embeddings capability
```

> **Design decision (defended at Gate C):** model capabilities and service capabilities share
> the *same `Capability` vocabulary, health, resilience, and config* but use *two resolvers* —
> `ModelRouter` (pick a model) and `ProviderRegistry.get(capability)` (pick a service
> provider). A single God-resolver was rejected: `generate()` and `transcribe()` have
> irreconcilable shapes, so unifying them buys nothing and costs type safety. The caller still
> asks **by capability** in both cases — the brief's requirement is met.

## 3. The registry

```python
# core/providers/registry.py
class ProviderRegistry:
    def register(self, provider: AIProvider | SpeechProvider | SearchProvider | StorageProvider) -> None: ...
    def providers_for(self, cap: Capability) -> list[Any]: ...     # capability-indexed
    def llm_providers(self) -> list[AIProvider]: ...
    def get_speech(self, cap: Capability) -> SpeechProvider: ...   # config-policy + health
    def get_search(self) -> SearchProvider: ...
    def health(self) -> dict[str, ProviderHealth]: ...

    @classmethod
    def from_config(cls, config: ResolvedConfig, secret_store: SecretStore) -> "ProviderRegistry":
        """Build adapters for every configured/auto-detected provider.
        Reads ResolvedConfig.providers (settings.py:130 — finally consumed) + env
        auto-detect (config_loader.py:84). Keys resolved lazily from SecretStore."""
```

## 4. One concrete implementation (LLM)

The existing clients become adapters — **no rewrite**, just a thin wrapper:

```python
# core/providers/anthropic_provider.py
class AnthropicProvider:                       # the ONLY new anthropic-importing site beyond llm.py
    name = "anthropic"
    def capabilities(self): return {REASONING, CODING, SUMMARIZATION, TITLE_GENERATION,
                                    COMPACTION, LONG_CONTEXT, VISION}
    def models(self): return ANTHROPIC_DEFAULTS          # bundled ModelDescriptors (see 14)
    def build_llm_client(self, model_id, **o): return AnthropicClient(model=model_id, **o)  # llm.py:200
    def health(self): return self._health.snapshot()

# core/providers/openai_compat_provider.py — wraps OpenAICompatibleClient (llm.py:362),
# advertises vision for the vision-capable presets, plus STT/TTS/embeddings if endpoint set.
```

`create_llm_client()` (`llm.py:644`) is retained and called by these adapters; the if-ladder
becomes the per-provider builder it already is. Adding a provider = add one adapter + register
it; no business-logic edit.

## 5. Resilience & health (shared by all providers)

The reliability gap (no retry/breaker, 600s Anthropic default — debt D6) is closed **once**,
here, not scattered:

```python
# core/resilience.py
class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff_base_s: float = 0.5
    timeout_s: float = 60.0
    breaker_threshold: int = 5
    breaker_cooldown_s: float = 30.0
    # retry_on defaults to transient: 429, 5xx, timeouts, connection errors

class ResilientClient(BaseLLMClient):
    """Decorates any BaseLLMClient with timeout + bounded retry + circuit-breaker,
    recording latency/error-rate into ProviderHealth. Drop-in: it IS a BaseLLMClient,
    so the loop (loop.py:305) is unchanged."""
    def __init__(self, inner: BaseLLMClient, policy: RetryPolicy, recorder: HealthRecorder): ...

def resilient_call(fn, policy, recorder):       # generic, for SpeechProvider/SearchProvider
    ...

@dataclass
class ProviderHealth:
    provider: str; available: bool
    recent_error_rate: float; p50_latency_ms: float
    consecutive_failures: int
    breaker: Literal["closed", "open", "half_open"]
```

Health feeds routing ([15](15-model-routing.md)); a provider with an open breaker is skipped.

## 6. Failover

Failover is a property of the **resolved client**, not the provider: `ModelRouter.select()`
returns a `ResilientClient` whose fallback chain is `[primary, …secondary]`. On terminal
failure of the primary (after retries / breaker open), the resilient client transparently
re-issues against the next candidate and records the fallback as a span event + a
`provider.failover` runtime event for observability ([21](21-observability.md)).

## 7. What it touches

| File | Change |
|---|---|
| `core/llm.py:644` | `create_llm_client` retained; called by adapters |
| `core/providers/*` (new) | `AIProvider`/`SpeechProvider`/`SearchProvider`/`StorageProvider`, adapters, registry |
| `core/routing/*` (new) | `Capability`, descriptors, router (14/15) |
| `core/resilience.py` (new) | `ResilientClient`, `resilient_call`, health |
| `core/settings.py:130` | activate `providers` map; add `[providers.NAME]` consumption |
| `core/sub_agent.py:617` | **fix:** build client via `ProviderRegistry`/router, not hardwired `AnthropicClient` |
| `gateway/orchestrator.py:1663` | boot constructs `ProviderRegistry` + wraps the session client in `ResilientClient` |
| `cli/main.py:471,545` | widen provider write-path allow-sets to match `ProviderKind` (debt D15) |

## 8. What could break (and the guard)

- **Sub-agent behavior change:** delegation with `model=` no longer silently forces Anthropic
  — it routes to the right provider. *Guard:* regression test asserting an OpenAI-session
  delegation uses an OpenAI client; back-compat for Anthropic sessions preserved.
- **Boot ordering:** `ProviderRegistry` must build before the loop. *Guard:* it slots into the
  existing provider-build step (`orchestrator.py:1663`); pure addition.
- **Resilience changing timing:** adding retries can lengthen a failing call. *Guard:* total
  bounded by `max_attempts × timeout_s`; default timeout drops from 600s → 60s (an
  improvement); covered by a chaos test (provider returns 503 → asserts ≤N attempts).
- **Import-linter contract:** new vendor imports must live only in `core/providers/*`.
  *Guard:* the import contract test ([11](11-domain-boundaries.md) §3).

## 9. Deferred (seam only, per §4a)

Native ElevenLabs/Deepgram/Azure/Tavily-cluster adapters; provider pricing feeds; per-tenant
provider policy; adaptive/latency-learned routing. Each is "add an adapter / a config policy"
against the contract above — no core change.
