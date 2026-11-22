# ObjectGraph (.og) Token-Efficiency Benchmark

**TL;DR:** Answering a query by routing through the 3-pass ObjectGraph model
uses **98.0% fewer tokens** than naively concatenating all skill files into the
prompt — measured against the 31-file / 60-node bundled skill pack shipped
with Hachi (corpus S-real, regenerated 2026-07-05).

> **Scope caveat:** below ~30 k tokens of total library content, a cached
> dump-all approach is competitive on cost. ObjectGraph is built for libraries
> that grow beyond that threshold — sub-file node granularity and `requires`
> traversal matter most when the library no longer fits in a single context window.

Reproducible at any time:

```bash
uv run hachi skill benchmark               # human-readable panel (token savings only)
uv run hachi skill benchmark --suite fast  # token + M1 retrieval quality
uv run hachi skill benchmark --suite full  # all metrics (M1/M2/M4/M7)
uv run hachi skill benchmark --json        # machine-readable JSON (CI / sharing)
uv run pytest tests/test_og_benchmark.py -s    # unit-test form with raw numbers
```

---

## Why this matters

Every modern agent framework faces a **context-loading problem**: skill files,
tool docs, and examples must reach the model somehow.  The naive solution —
concatenate everything — is simple but catastrophically wasteful as the skill
library grows.  Worse, irrelevant content adds noise that degrades answer
quality and inflates per-turn costs.

The ObjectGraph format (arXiv [2604.27820](https://arxiv.org/abs/2604.27820),
*"ObjectGraph: From Document Injection to Knowledge Traversal"*, Open Gigantic —
**first-party**: Hachi is the reference implementation described in that paper)
treats the context-loading problem as a **file-format problem**.  Rather than
a flat document you load or skip, a `.og` file is a **queryable graph of typed
nodes**, each carrying structured metadata that agents can index and traverse
without reading full content.

Independent third-party research validates the same category of solution:

| Paper | Finding |
|-------|---------|
| Graph-of-Skills (arXiv 2604.05333) | −56.72% tokens / +25.55% peak reward (GPT-5.2 Codex) vs flat skill loading |
| SkillReducer (arXiv 2603.29919) | ~60% of skill body is non-actionable; 39–48% compression with +2.8% quality |

Neither paper used `.og` — they validate that **format-aware selective loading**
is the right category of solution.  `.og` is Hachi's concrete implementation
of that insight, with sub-file node granularity and dependency-aware traversal
that file-level lazy loading cannot provide.

---

## The 3-pass model

When the agent needs a skill it runs three ranked passes, stopping as soon as it
has what it needs:

| Pass | Content loaded | Cost |
|------|---------------|------|
| **Pass 1 — index** | `::index` routing table (node names + role + keywords) | ~30 tok / file |
| **Pass 2 — dense** | `::dense` compressed summaries for the matching candidates | ~150–300 tok total |
| **Pass 3 — full** | `::full` content for the single best node | exact skill size |

Based on the S-real probe corpus (31 real queries), **87% of queries resolve at
Pass 1**.  Pass 3 is not reached by any current probe.

Compare this to **competitor approaches**:

| Approach | Granularity | Dependency-aware? |
|----------|------------|-------------------|
| Dump all `.md` into system prompt | File (all-or-nothing) | No |
| Anthropic Agent Skills (3-level) | File | No |
| MCP tool filtering | Tool schema | No |
| **ObjectGraph 3-pass** | **Sub-file node** | **Yes** (`requires` edges) |

---

## Current results (bundled default_skills)

Measured against the 60 `.og` nodes (31 files) shipped with Hachi, corpus
S-real (36 probes: 16 keyword / 10 procedural / 5 instructional / 5 negative).

### Token efficiency (M0)

| Metric | Value |
|--------|-------|
| Skill nodes | 60 |
| Baseline — dump all (tokens) | 12,150 |
| 3-pass total (tokens) | 248 |
| &nbsp;&nbsp;└ Pass 1 — index search | 31 |
| &nbsp;&nbsp;└ Pass 2 — dense peek (top 5) | 85 |
| &nbsp;&nbsp;└ Pass 3 — full resolve (1 node) | 132 |
| **Token savings** | **98.0%** |
| CI gate | ≥ 80% |

The CI gate enforces that this savings ratio never regresses below 80% as the
skill library grows.

### Retrieval quality (M1)

Measured against 31 positive probes (K/P/I types) + 5 negative probes:

| Metric | Value | Gate |
|--------|-------|------|
| P@1 — rank-1 correct | 0.871 | — |
| P@5 — correct in top 5 | 1.000 | ≥ 0.80 ✅ |
| MRR — mean reciprocal rank | 0.936 | — |
| FPR — false positive rate (N-probes) | 0.0000 | ≤ 0.20 ✅ |

No misses; no false positives on negative probes.

### Pass-depth distribution (M7)

How far into the 3-pass model each query goes:

| Depth | Rate |
|-------|------|
| Pass 1 sufficient (rank-1 hit) | **87.1%** |
| Pass 2 sufficient (top-5 hit) | 12.9% |
| Pass 3 required (not in top 5) | 0.0% |

100% of queries are resolved within 2 passes.

### Token cost model (M2)

Estimated cost per query, treating all tokens as uncached input (conservative
upper bound — cache hits reduce cost substantially in production):

| Metric | Value |
|--------|-------|
| Avg tokens / query (Pass 1) | 116.9 |
| Avg tokens / query (Pass 2) | 124.2 |
| Avg tokens / query (Pass 3) | 205.3 |
| **Avg tokens / query (total)** | **446.4** |
| Estimated cost / 1k queries | **$1.34** |

Pricing model: Anthropic 2026-06 uncached input @ $3.00/Mtok.  With prompt
caching (Pass 1 index is highly cache-friendly), effective cost is lower.

### Engine latency (M4)

Engine-only timing (search + peek + resolve, no LLM calls):

| Metric | Value |
|--------|-------|
| Avg engine ops | **~0.08 ms** |
| RTT model (3 passes × 800 ms) | 2,400 ms |
| Total estimated wall-clock | ~2.4 s |

Engine overhead is negligible; end-to-end latency is dominated by LLM
round-trip time.  The 800 ms/pass RTT is a conservative baseline; in practice
Claude Haiku averages 400–600 ms TTFT on warm requests.

_Numbers reproducible via `uv run hachi skill benchmark --suite full --json`._

---

## Methodology

### Token estimator

`estimate_tokens(text)` is a lightweight approximation (chars / 4, roughly
matching GPT-3.5-style BPE for English prose and JSON).  It is intentionally
conservative — actual savings with the Anthropic tokenizer are typically higher
because the index JSON structure is tokenized more efficiently than prose.

### Baseline

The baseline simulates the "dump-all" pattern: every node's `::full` content is
concatenated with `\n` separators and the total estimated token count is used
as the denominator.

### 3-pass measurement

1. Run `engine.search(query)` → top-5 candidate index entries → `estimate_tokens(json.dumps(results[:5]))`.
2. Run `engine.peek(candidates)` → dense summaries for all 5 → `estimate_tokens(json.dumps(...))`.
3. Run `engine.resolve_node(candidates[0])` → full content for the single best node → `estimate_tokens(...)`.

The representative query is chosen by `pick_representative_query()`
(`benchmarks/og_bench/metrics.py`): it walks every indexed node's keywords and
returns the first one whose top search hit actually resolves to real Pass-3
content — not merely the first keyword in index order, which can land on an
ambiguous bare name (e.g. a role name defined once per `roles/*.og` file) that
`resolve_node` refuses to load.

### Probe corpus (S-real)

The S-real corpus (`benchmarks/og_bench/s_real_probes.json`) contains 36 probes
authored against the default_skills pack:

- **16 keyword (K)** — single-concept lookups (e.g. "currency", "weather")
- **10 procedural (P)** — multi-step task queries (e.g. "how do I set up a standup")
- **5 instructional (I)** — configuration / setup questions
- **5 negative (N)** — out-of-scope queries that should return no results

M1/M7/M2/M4 metrics are computed over the 31 positive probes (K+P+I).

### CI enforcement

The benchmark runs as both a pytest test (`tests/test_og_benchmark.py`,
threshold 80%) and a dedicated CI job (`benchmark` in `.github/workflows/ci.yml`)
that runs `skill benchmark --suite fast --json --threshold 0.80` and fails the
build if savings drop below the gate or P@5 drops below 0.80.

---

## Running against your own skill pack

```bash
uv run hachi skill benchmark --dir /path/to/your/skills
uv run hachi skill benchmark --dir /path/to/your/skills --json
```

The `--suite` flag selects which metrics to compute:

```bash
uv run hachi skill benchmark --suite token   # token savings only (fast, default)
uv run hachi skill benchmark --suite fast    # token + M1 retrieval quality
uv run hachi skill benchmark --suite full    # all metrics (M1/M2/M4/M7)
```

The `--threshold` flag lets you set a custom savings gate:

```bash
uv run hachi skill benchmark --threshold 0.90  # fail unless savings ≥ 90%
```

---

## Sharing results

Run `skill benchmark --suite full --json` and paste the output as a snippet in
your README or submit it to the Hachi skill registry.  Example (truncated):

```json
{
  "suite": "full",
  "nodes": 60,
  "token": {
    "baseline_tokens": 12150,
    "three_pass_tokens": 248,
    "savings_pct": 0.979588,
    "passed": true
  },
  "m1": {
    "p_at_1": 0.871,
    "p_at_5": 1.0,
    "mrr": 0.9355,
    "fpr_negative": 0.0,
    "passed": true
  },
  "m7": {
    "p1_rate": 0.871,
    "p2_rate": 0.129,
    "p3_rate": 0.0
  },
  "m2": {
    "avg_tokens_total": 446.4,
    "estimated_usd_per_1k_queries": 1.3392
  },
  "m4": {
    "avg_engine_ms": 0.08,
    "rtt_estimate_ms": 2400.0,
    "total_estimate_ms": 2400.1
  },
  "passed": true
}
```
