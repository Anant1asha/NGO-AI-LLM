# 05 — Risk Assessment

> Phase 1 / Gate A. Baseline `main` @ `3d4fbe2`. Evidence is `file:line`.

Risks are grouped by category. Each carries **severity** (impact if it materializes),
**likelihood** (given the initiatives proceed), and a **mitigation**. A final section
covers **scope / over-reach risk** per Section 4a of the brief — the risk of building too
much, which for this backlog is as real as building too little.

## Severity × likelihood snapshot

```
                 IMPACT →   Low                 Medium                  High / Critical
 LIKELIHOOD
   High                     R14, R15            R5, R8, R10             R1, R2, R3, R6
   Medium                   R12, R13            R7, R9, R11             R4
   Low                      —                   R16                     R17
```

## Architectural risks

### R1 — No durable run state; in-flight runs vanish on restart · Sev: Critical · Likelihood: High
A gateway crash/restart mid-turn loses the entire run; the daemon restarts the *server*
(`daemon.py:234`), masking the loss as "it came back" while the user's task is silently
dropped. Nothing persists loop position, suspended workflows, pending approvals, leases, or
enqueued jobs.
- **Mitigation:** Initiative D must land a persisted run-state model (S10) before any
  "long-running" claim is made externally. Treat as a prerequisite, not a feature.

### R2 — `core_suspend_workflow` actively lies about persistence · Sev: Critical · Likelihood: High **[verified]**
`workflow_tools.py:15-21` saves nothing; shipped skills depend on auto-wake that does not
exist. Building Initiative D *on top of* this primitive without replacing it will produce
data-loss and stuck-agent bugs.
- **Mitigation:** replace the primitive with a real durable suspend/resume (S8+S9) as the
  first slice of D; until then, the tool should fail honestly rather than promise.

### R3 — No capability routing; the one multi-model path is provider-locked · Sev: High · Likelihood: High **[verified]**
`sub_agent.py:617-630` hardwires Anthropic; there is no model registry or router. Vision,
title-gen, compaction, and embeddings all bind to the session model or a fixed backend.
- **Mitigation:** Initiative B's `ModelRegistry`/`ModelRouter` (S2+S13); fix the sub-agent
  factory to honor session provider. B must precede G and I.

### R4 — Wiring layer (`boot_agent`) grows unmaintainable as platforms land · Sev: High · Likelihood: Medium
The 685-line god-function (`orchestrator.py:1453`) already concentrates boot complexity;
B/C/D/H each add boot wiring.
- **Mitigation:** extract boot sub-steps (provider build, memory wiring, event-bus setup)
  behind small factories *as part of* each initiative's slice — do not refactor wholesale
  up front (revert-risk), but do not pile onto it either.

## Reliability risks

### R5 — No retry / backoff / circuit-breaking anywhere · Sev: High · Likelihood: High
Zero application-level resilience (`grep` clean across `src`); Anthropic default timeout is
600s (`llm.py:226`). A transient provider error fails the turn; a flapping provider hangs it.
- **Mitigation:** a small, reusable resilience wrapper (timeout + bounded retry +
  breaker) behind `BaseLLMClient` and the HTTP adapter — a shared dependency of A, B, I.
  Build the seam once; do not scatter try/except.

### R6 — Durable-job substrate is inert; queued work is lost on restart · Sev: High · Likelihood: High **[verified]**
`queue.py:617-626` fails func-only jobs on recovery; `JobRegistry` is never wired.
- **Mitigation:** activate S8 (named handlers) before C/D/E rely on it; add a regression
  test asserting a handler-based job survives a simulated restart.

### R7 — Event log is memory-only and lossy · Sev: Medium · Likelihood: Medium
Cap-2000 in-memory list (`runtime_read_models.py:247`), not persisted. Slow SSE clients
past the window miss events; nothing replays after restart.
- **Mitigation:** persist the sequenced event log (reuse SessionStore patterns) as part of
  Initiative C; this also unlocks the "replay" seam without new machinery.

## Security risks

### R8 — Search/File ingestion expands the untrusted-input surface · Sev: High · Likelihood: High
Initiatives A and E pull arbitrary web/file content toward the model. The existing guards
(`net_guard.py:73`, `untrusted_content.py:37`, DNS pinning) are strong but must be applied
to **every** new fetch/extract path, and the brief's virus-scan hook (E) is currently absent.
- **Mitigation:** route all A/E ingress through `guard_untrusted` + `validate_outbound_url`
  by construction; make the virus-scan hook a real (even if no-op-by-default) interface in
  the file pipeline. Sanitize before content reaches model or user.

### R9 — Provider key sprawl and secrets-in-traces · Sev: Medium · Likelihood: Medium
More providers (B, F, I) means more keys; new observability (H) ships data to Langfuse.
- **Mitigation:** keep all keys in `SecretStore`/`CredentialVault` (S6, never in TOML); the
  event taxonomy already secret-scrubs (`runtime_events.py`) — ensure the Langfuse exporter
  inherits the same redaction; no raw prompts/keys in spans.

### R10 — Untyped routes break consumers silently · Sev: Medium · Likelihood: High
~15 routes return bare `dict`/`Any` (debt D11); the CI contract gate can't see them.
- **Mitigation:** every *new* route ships with a `response_model`; opportunistically type
  the legacy ones the initiatives touch. Add the audit-recommended check: grep frontend
  fetch paths against exported OpenAPI `paths`.

## Performance / scalability risks

### R11 — Single-node, local-disk storage; single-threaded job worker · Sev: Medium · Likelihood: Medium
All stores assume one machine (`paths.py:107`); the job worker pulls `limit=1`
(`queue.py:336`). Event→job fan-out (C) would serialize through one worker.
- **Mitigation:** keep single-node as the explicit target for now (Hachi is single-user);
  design the durable-job and storage interfaces so a future backend swap is additive, but
  **do not build multi-node/Postgres/S3 now** (Section 4a). Document the seam.

### R12 — Outbound HTTP has no cache/dedup/pool · Sev: Low · Likelihood: High
Each REST/search/image fetch is a fresh `httpx.Client` (`rest_adapter.py:307`), uncached.
Initiative A at volume would be slow and costly.
- **Mitigation:** a per-session search cache + shared client pool as a *cost-control* slice
  of A — not core infrastructure.

### R13 — Compaction / ChromaDB cold-start latency (pre-existing) · Sev: Low · Likelihood: Medium
Known hot-path items from prior audits; mostly already mitigated (compaction deferred to a
job, `memory.py:864`).
- **Mitigation:** out of scope for these initiatives; monitor via the new observability.

## Migration / compatibility risks

### R14 — No migration framework for evolving stores · Sev: Low (now) → High (as D/E add tables) · Likelihood: High
Only `SessionStore` migrates (`session_store.py:108`); `jobs.db`/`memory_index.db` cannot
evolve safely (debt D9).
- **Mitigation:** promote `_migrate_schema` to a shared `apply_migrations(conn, table,
  cols)` helper *before* D/E add their tables. Additive-only column changes.

### R15 — Public response shapes are wide and CI-enforced · Sev: Low · Likelihood: High
Session rows, memory fact dicts (SHA-256 ids), job dicts, og/schedule shapes feed the typed
frontend (`fastapi_app.py:579-1387`); changing them requires the OpenAPI regen dance or CI
fails.
- **Mitigation:** additive-only changes; run `gateway-openapi` + `generate:api` with every
  route touch (already CI-gated).

### R16 — `PROTOCOL_VERSION` lockstep · Sev: Medium · Likelihood: Low
`create_session` hard-rejects version mismatches (`control_plane.py:216`); a bump breaks all
clients at once.
- **Mitigation:** avoid bumping unless a genuinely breaking transport change lands; prefer
  additive event/field changes.

## Operational risks

### R17 — Observability is near-blind by default · Sev: High · Likelihood: Low (today) → High (as complexity grows) · 
Tracing is dormant (`HACHI_TRACING` off), logging is silent outside the daemon (debt D12/D13),
no metrics. Diagnosing the *new* subsystems (event bus, run-state, routing) without this is hard.
- **Mitigation:** sequence Initiative H's correlation-id + per-turn-root-span work *early*,
  so C/D/B are observable as they land — observability is an enabler, not a finale.

## Scope / over-reach risk (Section 4a)

The brief asks for nine platforms with ambitious machinery. The dominant *project* risk is
**building too much**:

| Over-reach temptation | Why it's premature for Hachi today | Recommended posture |
|---|---|---|
| Event replay + dead-letter queue + multi-region bus | Single-node, single-user; no consumer needs replay yet | Build pub/sub + async dispatch; leave persistence/DLQ as a documented seam |
| 8 search/voice/vision providers up front | One good impl proves the interface; more is YAGNI | Ship `SearchProvider`+Tavily, `SpeechProvider`+OpenAI-compat; seam for the rest |
| Postgres/S3/multi-node storage | No scale pressure; local SQLite is sufficient | Interface now, local impl only |
| Real-time streaming voice / conversation mode | Batch tools cover the need; streaming is a large, separate build | Defer; formalize the provider first |
| Full agent-state machine with every wait condition | `wait_for_user` + `wait_for_event` cover the real skills | Implement the two that exist in skills; seam for the rest |
| RAG ingestion index for files | No consumer yet; RRF seam already exists | Build the file *pipeline*; defer the index until a feature needs it |

**Principle for Gate B:** each initiative ships as *contract + one real implementation + a
documented extension point*, phased so that B (routing) and the C/D foundations (bus +
durable execution) land before the modality platforms that depend on them. A correct "we
don't need this yet, here's the seam" beats gold-plated infrastructure no one uses.

## Top-5 risks to resolve first

1. **R2 / R1** — replace the suspend no-op and add durable run state (D) before any
   long-running claim.
2. **R3** — model registry + router and de-lock the sub-agent (B) before G/I.
3. **R6** — activate the durable job substrate (already built) before C/D/E lean on it.
4. **R5** — one reusable resilience wrapper before multi-provider failover.
5. **R17/R8** — land correlation-id observability and enforce ingestion guards *as* the new
   subsystems are built, not after.
