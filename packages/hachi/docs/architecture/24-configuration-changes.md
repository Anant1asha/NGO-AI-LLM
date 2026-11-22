# 24 — Configuration Changes

> Phase 2 / Gate B. New config sections from docs 12–21. All **additive**; `extra="ignore"`
> (`settings.py`) + env fallback mean old configs keep loading unchanged. Seams are `file:line`.

## 1. New / activated sections on `ResolvedConfig` (`settings.py:125`)

```toml
[routing]                                  # B (14/15)
default_model = "claude-haiku-4-5"         # = today's single model when nothing else set
[routing.capabilities]
reasoning = ["claude-opus-4-8", "claude-haiku-4-5"]
vision    = ["claude-opus-4-8", "gpt-4o"]
title_generation = ["claude-haiku-4-5"]
compaction       = ["claude-haiku-4-5"]
[routing.resilience]                       # 13 — closes the no-retry gap (D6)
max_attempts = 3
timeout_s = 60
breaker_threshold = 5
# [[routing.model_overrides]] id=... provider=... capabilities=[...] context_window=...

[providers.openai]                         # I — finally consumed (settings.py:130 was inert)
kind = "openai-compatible"
api_key_env = "OPENAI_API_KEY"

[search]                                   # A (17)
provider = "tavily"
max_calls_per_turn = 5
cache_ttl_s = 900

[files]                                    # E (18)
max_size_mb = 25
allowed_types = ["application/pdf", "text/csv", "text/plain", "image/png", ...]
storage_backend = "local"
virus_scan = "noop"

[voice]                                    # F (19) — absorbs HACHI_STT_*/HACHI_TTS_* (env fallback)
stt_provider = "openai-compatible"
tts_provider = "openai-compatible"

[observability]                            # H (21)
exporter = "console"                       # console | otlp | langfuse
log_level = "INFO"
```

## 2. Env-var convention (unchanged `HACHI_*`)

New vars follow the established pattern with config precedence
(`defaults→global→project→env→cli`, `config_loader.py:174`): `HACHI_LOG_LEVEL`,
`HACHI_OBS_EXPORTER`, `HACHI_SEARCH_PROVIDER`, plus the existing `HACHI_STT_*`/`HACHI_TTS_*` now
folded under `[voice]` with env fallback. Provider API keys remain **name-indirected** — only the
env-var *name* is written to TOML; secrets stay in `SecretStore` (`update_provider`,
`cli/main.py:502`).

## 3. Schema-vs-write-path fix (debt D15)

The provider write-path allow-sets (`cli/main.py:471,545`, currently 3 kinds) are widened to match
the `ProviderKind` literal (`settings.py:8`, 7 kinds), so a schema-valid provider config is no
longer rejected by the gateway.

## 4. Back-compat guarantees

- **Zero new config required.** Absent `[routing]`, the single `provider.model` (`settings.py:34`)
  is synthesized as the only candidate for every capability — today's exact behavior.
- **Unknown keys ignored** (`extra="ignore"`), so newer configs load on older builds and vice
  versa.
- **Empty/default tables omitted on write** (`config_loader.py:193`), so files stay clean.

## 5. What could break (and the guard)

- **Typo'd keys silently dropped** (existing `extra="ignore"` behavior — debt D15-minor).
  *Guard:* `hachi doctor` gains a config-lint that warns on unknown top-level keys (non-fatal).
- **Precedence surprises** with the new sections. *Guard:* a precedence test fixes
  env-over-file-over-default for each new section.
