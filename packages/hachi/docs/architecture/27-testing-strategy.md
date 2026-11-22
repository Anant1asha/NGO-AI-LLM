# 27 — Testing Strategy

> Phase 2 / Gate B. Per the brief's cross-cutting requirement: unit · integration · e2e · and
> failure/chaos tests, plus the contract tests that keep the architecture honest. Seams are
> `file:line`.

## 1. Test pyramid + new contract tests

| Level | What | Examples |
|---|---|---|
| **Unit** | each new construct in isolation with fakes | `ModelRouter.select` ordering/determinism; `RoutingPolicy` back-compat synth; `WaitConditionRegistry` resolve; `ResilientClient` retry/breaker; `FilePipeline` stages; `apply_migrations` idempotency |
| **Integration** | constructs wired together | boot with `ProviderRegistry`+`ModelRouter`; `EventBus` publish→subscribe→job; suspend→persist→resume; file upload→extract→index; search tool→cache→guard_untrusted |
| **E2E** | through the gateway/CLI | vision auto-route (3 scenarios); `wait_for_event` skill suspends+resumes; `/files` round-trip; failover across providers |
| **Chaos / failure** (brief-mandated) | inject failures | provider 503→retry→failover; model returns malformed→handled; event handler throws→isolated; upload of oversized/malicious file→quarantined; restart mid-run→recovered |
| **Contract** (new, architecture-enforcing) | invariants | **import-linter: vendor SDK only in `core/providers/*`**; frontend-path-vs-OpenAPI; OpenAPI `schema.d.ts` diff (existing); migration upgrade-from-snapshot |

## 2. Fakes already available (low-friction isolation)

`InMemoryProvider`/`InMemoryJobQueue` exist (`memory_provider.py:144`, `queue.py:178`); the voice
backends are injectable (`voice.py:314`); the brief's pattern of constructor-injected `BootDeps`
makes the whole graph fakeable. New fakes: `FakeLLMProvider` (scriptable responses/failures),
`FakeSearchProvider`, `FakeStorageProvider`, `FakeClock` (for wait/timeout determinism — note
`Date.now`-style nondeterminism must be injected, mirroring the codebase's existing discipline).

## 3. Security tests (brief-mandated, adversarial)

- **Search/file ingestion injection:** a malicious search result / file content cannot issue
  instructions — asserts `guard_untrusted` framing is present and effective.
- **Vendor-boundary:** the import-linter contract fails the build if any non-provider module
  imports a vendor SDK.
- **Provider keys:** never appear in logs/spans/events (extends the existing secret-scrub test to
  the new exporter).
- **File pipeline:** path traversal, type spoofing, zip-bomb size cap, virus-scan-hook invoked.

## 4. Per-initiative acceptance gates (named, like the prior audit's gates)

| Gate | Assertion |
|---|---|
| GATE-ROUTE | `select(VISION)` returns a vision model; `NoRouteError` only under impossible constraints |
| GATE-FAILOVER | primary 503 → fallback serves; `provider.failover` event emitted |
| GATE-RESUME | suspend on `wait_for_event` → event fires → run resumes & completes; bad wake idempotent |
| GATE-DURABLE | a `handler_name` job survives a simulated restart (the exact `queue.py:617` gap) |
| GATE-VISION | Haiku session + configured vision candidate → routed; none → graceful fallback; Opus → inline |
| GATE-FILE | upload→validate→scan→store→extract→index round-trip; oversized→rejected; malicious→quarantined |
| GATE-TRACE | `tool.call` spans nest under `agent.turn`; every event carries `trace_id` |
| GATE-MIGRATE | boot against prior-schema snapshot upgrades cleanly, no data loss |
| GATE-COMPAT | zero-config run produces identical behavior/SSE to baseline |

## 5. Performance assertions

Resilience adds no latency on the happy path (no-op when healthy); router `select` is O(candidates)
and cached per capability per turn; observability spans are no-ops when unconfigured. Each is a
before/after micro-benchmark, matching the codebase's existing perf-test discipline.

## 6. CI integration

All of the above run in the existing six-job pipeline (`test`, `security`, `lint`, `skill-lint`,
`benchmark`, `frontend-contract`). The import-linter contract and the frontend-path check are
added to `lint`/`frontend-contract` respectively. Lint+type-check stay strict on PRs
(`mypy --strict`, `ruff`).
