# 14 — Model & Capability Registry

> Phase 2 / Gate B. Initiative **B** (the "Model Registry + Capability Registry" pieces).
> Contract + one impl + seam. Seams are `file:line`.

## 1. Problem

There is no source of truth for *what models exist and what they can do*. `core/models.py` is
OG schemas (a false friend); `MODEL_PRICING` (`cost.py:19`) is pricing-only for 5 families;
model lists are static arrays (`cli/main.py:626`); capability is implied by scattered
`provider_kind` string checks (`vision_tools.py:222`). Routing by capability has nothing to
read.

## 2. Naming — resolving the collision

An existing `CapabilityRegistry` (`orchestrator.py:145`, surfaced by
`PUT /capabilities/{id}/enabled`) governs **feature toggles** (memory on/off, etc.). It keeps
its name and role. The new concepts are named to avoid collision:

| New construct | Role |
|---|---|
| `ModelRegistry` | the set of known models and their `ModelDescriptor`s |
| `RoutingPolicy` | capability → ordered candidate model ids (config-driven) — the "Capability Registry" of the brief |
| `ModelRouter` | the engine that picks a model given capability + runtime signals ([15](15-model-routing.md)) |

## 3. Contract — `ModelDescriptor` and `ModelRegistry`

```python
# core/routing/descriptor.py
class Pricing(BaseModel):
    input_per_mtok: float
    output_per_mtok: float
    cache_read_mult: float = 0.1      # mirrors cost.py:29 Anthropic multipliers
    cache_write_mult: float = 1.25

class ModelDescriptor(BaseModel):
    id: str                            # "claude-opus-4-8", "gpt-4o"
    provider: str                      # ProviderRegistry key: "anthropic", "openai", ...
    capabilities: frozenset[Capability]
    context_window: int                # tokens
    max_output: int
    pricing: Pricing | None = None     # None = unknown (router may still pick; cost flagged unknown)
    supports_tools: bool = True
    supports_streaming: bool = True
    # NOTE: no quality/latency score here — see ADR-0001 §Deferred. Those come from
    # live telemetry later; baking guesses in now would be fiction.

# core/routing/registry.py
class ModelRegistry:
    def register(self, d: ModelDescriptor) -> None: ...
    def get(self, model_id: str) -> ModelDescriptor | None: ...
    def by_capability(self, cap: Capability) -> list[ModelDescriptor]: ...
    def all(self) -> list[ModelDescriptor]: ...
```

`Pricing` **absorbs and replaces** `MODEL_PRICING` (`cost.py:19-25`): `CostTracker` switches to
look up `registry.get(model).pricing` (longest-prefix fallback preserved as a registry method),
so cost and capability share one source of truth and unpriced-model drift (debt D4) is visible
(`pricing is None`) rather than silently `(1.0, 5.0)`.

## 4. One concrete implementation — seeding the registry

Precedence (low → high), so config always wins and offline still works:

```
bundled defaults (data table)  ←  provider discovery (list_models())  ←  config overrides
```

```python
@classmethod
def build(cls, config: ResolvedConfig, providers: ProviderRegistry) -> "ModelRegistry":
    reg = cls()
    for d in BUNDLED_MODEL_DEFAULTS:            # replaces cost.py table + cli static lists
        reg.register(d)
    for p in providers.llm_providers():         # best-effort; list_models() already exists (llm.py:174)
        for d in p.models():
            reg.register(d)                      # provider advertisement overrides bundled
    for override in config.routing.model_overrides:  # user-declared caps/pricing/context
        reg.register(override)                   # config wins
    return reg
```

`BUNDLED_MODEL_DEFAULTS` is a single curated data table (the *only* place model ids/caps live
as data, never in business logic) — e.g.:

```python
BUNDLED_MODEL_DEFAULTS = [
    ModelDescriptor(id="claude-opus-4-8", provider="anthropic",
        capabilities=frozenset({REASONING, CODING, VISION, LONG_CONTEXT, SUMMARIZATION}),
        context_window=200_000, max_output=64_000,
        pricing=Pricing(input_per_mtok=…, output_per_mtok=…)),
    ModelDescriptor(id="claude-haiku-4-5", provider="anthropic",
        capabilities=frozenset({REASONING, TITLE_GENERATION, COMPACTION, SUMMARIZATION}),
        context_window=200_000, max_output=8_192, pricing=Pricing(...)),
    ModelDescriptor(id="gpt-4o", provider="openai",
        capabilities=frozenset({REASONING, VISION}), context_window=128_000, …),
    # embeddings/STT/TTS descriptors as their providers come online
]
```

> Pricing numbers are deliberately omitted from this doc — they are billing-sensitive data,
> kept in the table and refreshed there, never quoted in design prose. (Today's values live at
> `cost.py:19-25` and migrate verbatim.)

## 5. `RoutingPolicy` — the capability registry (config-driven)

The capability→candidates map lives in **config**, not code (satisfies "no model names in
business logic"):

```toml
[routing]
default_model = "claude-haiku-4-5"        # back-compat: the single session model

[routing.capabilities]                     # ordered candidates per capability
reasoning         = ["claude-opus-4-8", "claude-haiku-4-5"]
title_generation  = ["claude-haiku-4-5"]
compaction        = ["claude-haiku-4-5"]
vision            = ["claude-opus-4-8", "gpt-4o"]
embeddings        = ["local-minilm"]       # current Chroma default (memory_vault.py)

[routing.model_overrides]                  # optional: declare caps/pricing for unknown models
# [[routing.model_overrides]] id="my-llama" provider="ollama" capabilities=["reasoning"] context_window=32000
```

```python
# core/routing/policy.py
class RoutingPolicy(BaseModel):
    default_model: str
    capabilities: dict[Capability, list[str]] = {}     # cap → ordered model ids
    def candidates(self, cap: Capability) -> list[str]: ...   # explicit, else []→router derives
```

**Back-compat (critical):** if `[routing]` is absent, `RoutingPolicy` is synthesized from the
single configured `provider.model` (`settings.py:34`) as the sole candidate for **every**
capability — i.e. today's exact behavior (one model for everything), now expressed through the
new mechanism. No user config change is required to upgrade.

## 6. What it touches

| File | Change |
|---|---|
| `core/routing/*` (new) | `ModelDescriptor`, `ModelRegistry`, `RoutingPolicy`, defaults table |
| `core/cost.py:19` | `MODEL_PRICING` → registry-backed lookup (data migrates verbatim) |
| `core/settings.py` | new `[routing]` section on `ResolvedConfig` |
| `cli/main.py:626` | static model lists → `registry.all()` (debt: model list now dynamic — also fixes H6 lineage) |
| `gateway/fastapi_app.py` `/models` | served from the registry |

## 7. What could break (and the guard)

- **Cost numbers shift if a descriptor's pricing differs from `MODEL_PRICING`.** *Guard:*
  migrate the exact `cost.py` values into the defaults table; a test asserts
  `registry pricing == old MODEL_PRICING` for the 5 existing families.
- **`/models` content changes** (now dynamic). *Guard:* a regression test pins that the
  configured running model appears (addresses the prior H6 class); additive to the contract.
- **Unknown models now surface `pricing=None`** instead of a silent default. *Guard:* router
  treats `None` as "cost-unknown, allowed unless a cost constraint is set" — documented, tested.

## 8. Deferred (seam only)

Quality/latency scores on descriptors (need live telemetry — ADR-0001); automated pricing
feeds; per-user capability policies; capability inference for arbitrary models (today: declared
in the table or config overrides).
