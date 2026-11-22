# 28 — Rollout Plan

> Phase 2 / Gate B. The build order, flags, and exit gates. Each slice is independently
> reviewable, behind config, backward-compatible, and observable (the Phase-4 definition of done).

## 1. Phasing (dependency-ordered)

| Phase | Slices | Flag | Exit gate |
|---|---|---|---|
| **2.1 — Provider & Routing (B)** | `ModelDescriptor`/`Registry`; `ProviderRegistry`; `ResilientClient`+health; `ModelRouter`; default-route synth; de-lock sub-agent; pricing→registry; centralize model defaults | `[routing]` (absent = today's behavior) | GATE-ROUTE, GATE-FAILOVER, GATE-COMPAT green; suite green |
| **2.2 — Events & Durable (C, D)** | `EventBus` over the funnel; activate `JobRegistry`; `RunState`+`WaitConditionRegistry`; replace suspend (fail-honest → real resume); `apply_migrations` helper | per-feature flags; suspend honest-fail first | GATE-RESUME, GATE-DURABLE, GATE-MIGRATE green |
| **2.3 — Observability (H)** | per-turn root span; thread-context propagation; id stamping; cost-on-span; exporter config; `setup_logging` | `[observability].exporter=console` default | GATE-TRACE green; B/C/D traceable |
| **2.4 — Modalities (A, E, F, G)** | Search+Tavily; File pipeline+routes; Voice `SpeechProvider`; Vision auto-route | `[search]`/`[files]`/`[voice]` present to enable | GATE-FILE, GATE-VISION, search-injection green |
| **2.5 — Multi-provider depth (I)** | health-aware ordering; budget-aware selection; 2nd LLM/speech/search providers | config | failover under load; cost attribution |

**Why this order:** 2.1 is the keystone (G/I depend on it) and delivers resilience to everything;
2.2 fixes the two correctness criticals (R1/R2) and unlocks reactive agents; 2.3 lands *before*
the modalities so they ship observable; 2.4/2.5 are additive on fixed contracts.

## 2. Slice discipline (Phase-4 rules, restated)

Each slice: behind a flag where it changes behavior · with unit+integration+the relevant gate ·
backward-compatible (or the one approved break, [26](26-backward-compatibility.md) §3) · traced ·
documented (ADR if significant) · independently revertible. Before writing each slice's code:
state in one line *why it's correct, why it won't regress, and what it touches* (the brief's
Phase-4 requirement).

## 3. Parallelization (for Phase 4 task decomposition)

After 2.1 fixes the contracts, work parallelizes cleanly by domain (separate file trees, the
Gate-A finding that the spine has no cycles):

```
2.1 (serial — shared core contracts, one owner)
      │
      ├── 2.2 Events/Durable ── core/runtime, jobs, loop
      ├── 2.3 Observability ──── core/obs, tracing (independent)
      └── 2.4 Modalities (parallel once 2.1 + 2.2 land):
            ├── A Search ── core/providers/search, tools/search_tools
            ├── E Files ─── core/files, tools/file_tools, gateway routes
            ├── F Voice ─── core/providers/speech (wraps voice.py)
            └── G Vision ── tools/vision_tools (needs 2.1 router)
```

Collision rule: 2.1 and 2.2 both touch `core/loop.py` (router param vs resume cursor) and
`gateway/orchestrator.py` (boot) — **serialize 2.1 before 2.2** under one owner, then fan out.
Mirrors the prior audit's "don't split shared-file work" lesson.

## 4. Risk-gated checkpoints

- After **2.1**: validate no cost/latency regression on the happy path; confirm zero-config
  parity (GATE-COMPAT) before anyone relies on routing.
- After **2.2**: the suspend/resume correctness fix is the highest-risk change — soak-test a
  reactive skill end-to-end and a mid-run restart before enabling real suspend (honest-fail until
  then).
- After **2.3**: turn on tracing in dev (`console`) and confirm trace trees before modalities.

## 5. What "done" looks like for this program

All nine initiatives shipped as *contract + one real implementation + a documented seam*, behind
config, backward-compatible, traced, and tested — with the deferred machinery
([05](05-risk-assessment.md) §scope, and each doc's "Deferred" section) explicitly left as named
seams with trigger conditions. **No speculative infrastructure built ahead of a consumer.**
