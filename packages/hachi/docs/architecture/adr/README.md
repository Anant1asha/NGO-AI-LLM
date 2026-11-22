# Architecture Decision Records (ADRs)

This directory holds Hachi's **deep design ADRs** — the major architectural choices that
warrant a full Context / Decision / Alternatives / Consequences treatment and a stable,
citable number.

## Where decisions live — two tiers

| Tier | Home | Use it for |
|------|------|-----------|
| **Decision log** | [`DECISIONS.md`](../../DECISIONS.md) (repo root) | Every settled decision — process, tooling, bug-fix rationale, small architectural calls. Newest at the bottom. **This is the default.** |
| **Deep ADRs** | `docs/architecture/adr/NNNN-*.md` (here) | A *major* architectural decision that needs alternatives analysis and a long-lived reference. Link it from `DECISIONS.md`. |

Rule of thumb: **write it in `DECISIONS.md` first.** Promote to a numbered ADR only when the
decision is large enough that people will later need to re-read the *reasoning*, not just the
outcome.

## Index

| ADR | Title | Status (per file) |
|-----|-------|-------------------|
| [0001](0001-capability-based-model-routing.md) | Capability-based model routing | Proposed |
| [0002](0002-aiprovider-capability-interface.md) | Provider-agnostic `AIProvider` capability interface | Proposed |
| [0003](0003-event-bus-over-emit-funnel.md) | Event bus over the existing emit funnel | Proposed |
| [0004](0004-durable-run-state-on-sqlite-job-substrate.md) | Durable run-state on the SQLite job substrate | Proposed |
| [0005](0005-observability-correlation-and-injected-exporter.md) | Observability via correlation-id + injected exporter | Proposed |

> **Statuses are point-in-time and may lag implementation.** Several of these designs have
> since shipped; the **outcome of record** for a shipped decision is its `DECISIONS.md` entry,
> not the ADR's `Status:` line. Updating an ADR's status is a deliberate edit, never a drive-by.

## Adding an ADR

1. Copy [`0000-template.md`](0000-template.md) to the next free number:
   `NNNN-short-kebab-title.md`.
2. Fill in Context / Decision / Alternatives considered / Consequences.
3. Add a row to the **Index** table above. (`adr-lint` fails if an ADR isn't indexed.)
4. Link the ADR from the relevant `DECISIONS.md` entry.

`uv run python scripts/check_adrs.py` keeps this directory honest: every ADR must be
well-formed (filename `NNNN-kebab.md`, a `Status:` line, the Context/Decision/Consequences
sections) and listed in the Index above. It runs as an advisory step in `scripts/preflight.py`
and CI's `lint` job.
