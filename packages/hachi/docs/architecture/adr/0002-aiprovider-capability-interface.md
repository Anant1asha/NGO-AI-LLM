# ADR-0002 — Provider-agnostic `AIProvider` capability interface over `BaseLLMClient`

- **Status:** Proposed (Gate B)
- **Date:** 2026-06-21
- **Deciders:** Principal Architect (pending Gate B/C approval)
- **Related:** [11](../11-domain-boundaries.md), [13](../13-provider-architecture.md); enables ADR-0001

## Context

The `anthropic` SDK is cleanly confined to `core/llm.py` and `BaseLLMClient` (`llm.py:106`) is a
sound text/stream contract. But `create_llm_client()` (`:644`) is a hardcoded `kind` if-ladder,
`ResolvedConfig.providers` (`settings.py:130`) is inert, and non-LLM modalities (speech, search,
embeddings, storage) have no provider contract at all. Initiative I requires vendors to
**advertise capabilities** and Hachi to **route by capability across modalities**, while keeping
the clean vendor-SDK boundary.

## Decision

Layer a thin **`AIProvider`** capability interface above the retained `BaseLLMClient`: a provider
declares `capabilities()`, advertises `models()` as `ModelDescriptor`s, and `build_llm_client()`.
Define **sibling provider contracts** (`SpeechProvider`, `SearchProvider`, `StorageProvider`,
`Embedder`) for modalities whose method shape differs. Register all in one **`ProviderRegistry`**,
capability-indexed. **Widen the vendor-SDK boundary explicitly:** any vendor SDK may be imported
*only* inside `core/providers/*` (with `core/llm.py` grandfathered), enforced by an import-linter
contract test.

Existing clients (`AnthropicClient`, `OpenAICompatibleClient`) become adapters with no rewrite;
`create_llm_client()` is retained and called by them.

## Alternatives considered

1. **Extend `BaseLLMClient` to cover all modalities.** Rejected — bloats one interface with
   `transcribe`/`synthesize`/`search`/`embed`; violates interface-segregation; most providers
   would no-op most methods.
2. **No umbrella; independent per-modality registries.** Rejected — loses the unified
   capability vocabulary, health, and resilience the brief's failover/health requirements need;
   duplicates wiring.
3. **Adopt a third-party provider-abstraction framework.** Rejected — heavier dependency than the
   in-house `BaseLLMClient` already provides; the codebase's existing boundary is the asset to
   extend, not replace.

## Consequences

**Positive:** providers advertise capabilities → capability routing (ADR-0001) and cross-modal
workflows (Deepgram STT → Claude reasoning → Gemini vision → ElevenLabs TTS) become declarative;
the inert `providers` config is finally consumed; the vendor boundary becomes a *tested* invariant
rather than a convention; adding a provider is one adapter + registration.

**Negative / cost:** more interfaces and a new package (`core/providers/*`); the speech/search/
storage contracts must be designed alongside their initiatives (F/A/E); a (small) risk of
over-abstraction if a modality only ever has one provider — mitigated by §4a (ship one impl, the
contract is cheap, the seam is documented).

**Reversibility:** medium-high. `AIProvider` wraps existing clients additively; collapsing back to
direct `create_llm_client` calls is mechanical. The import-linter contract is the main new
constraint and is itself opt-in CI.
