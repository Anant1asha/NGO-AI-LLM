# Phase 2 — Object Graph Deep Evaluation + Benchmark Spec

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Builds on:** [00-recon.md](00-recon.md) §6 (pipeline mechanics), [01-architecture-review.md](01-architecture-review.md) TD-7.
**Markers:** ✅ direct read · ▶ executed this session · Ⓐ subagent-verified · 🌐 web-verified this session · ⚠️ UNVERIFIED.
Voices kept separate: §1–§6 **What I found**, §7–§8 **What I propose** (incl. the benchmark spec).

---

## 1. The "graph" as actually implemented

| Layer | Spec/marketing language | Code reality |
|---|---|---|
| Structure | "queryable graph of typed nodes" | Flat dict `name→OGNode` + dict `keyword→[names]` ✅ engine.py:248–252. Edges exist as data (`requires`, `requires_auth`, freeform `::edges`) but only `requires` has behavior. |
| Traversal | "dependency-aware traversal", `::traverse` hints | `get_dependency_chain` (DFS w/ cycle detection ✅ engine.py:954–1007) + `skill_dependencies` tool. **Shipped content contains exactly 1 `requires` edge and 0 `::traverse` blocks** ▶ — the traversal machinery is built but practically data-free. |
| Retrieval | "O(1) keyword-based retrieval" | Exact dict hit **plus** a linear substring scan both directions (`term in kw or kw in term`) over all 169 keywords ✅ engine.py:360–372 ▶. No ranking signal except `::traverse` priority (which no shipped file sets); `confidence` parsed but never used in queries ✅. |
| Indexing | `::index` routing table per file | Honored when present; **6 of 29 shipped files have `::index`/`::meta` (brain + 5 roles); the other 23 have neither** ▶. Pass-1 for them rides on node-level `->[:keywords=…]` only. |
| Caching | 3-pass "delta loading", changelog | `skill_changelog` tool exists ✅ engine.py:884–909; loaded skill text enters *message history*, which is **not** prompt-cached (only system+tools carry `cache_control` ✅ llm.py:195–214) — so every loaded block is re-billed at full input price on every subsequent LLM call in the session. |
| Context selection | model-driven 3-pass | Real and instrumented: `search_skills → peek_skill (per-block token manifest) → load_skill(blocks=…)` ✅ og_tools.py, engine.py:445–580, with loop-level group unlock + usage tracking ✅ loop.py:519–530. |

**One-line synthesis (observation):** today `.og` is a *disciplined lazy-loading file format with rich
affordances*, not yet a graph and not yet a retrieval engine.

## 2. New measurements this phase

### 2.1 Shipped-content compliance ▶

- `::index` present: **6/29** files; `::meta`: 6/29; `::traverse`: **0**; `requires` edges: **1** total.
- `::dense` blocks average **38 est. tokens — over the engine's own 30-token budget** (lint would warn
  on the project's shipped content); 4 nodes have no dense at all (`analysis-protocol`,
  `safety-first`, `composition-rules`, `methodology`).
- Average Pass-3 `::full` ≈ 201 est. tokens, max 458 — nodes are small; the library is 42 nodes ≈ 9k tokens.

### 2.2 The namespace collision is live, not theoretical ▶

`manifest.json` installs `brain.og` + roles into the user skills dir ✅ manifest.json:2–11, so the
runtime engine indexes them all. Duplicate node names in shipped content: **`identity` ×6,
`report-format` ×5, `execution-protocol` ×2** — last-parsed file silently wins `_nodes[name]`
(engine.py:323–324 ✅). `peek_skill("identity")` returns whichever role file globbed last. This is
TD-7 from Phase 1 occurring in the box, on day one.

### 2.3 Retrieval-quality probe (22 realistic queries, live engine, shipped library) ▶

Method: `SkillEngine.load_directory(default_skills)`, natural-language queries, top-4 names recorded.

- **Hit-anything rate: 22/22 — but this is the failure, not the success.** The bidirectional
  substring fuzz means stopwords match: "what's the weather **in** paris" → `tool-philosophy,
  execution-protocol, identity, inbox_sentinel` (the weather skill **absent**); "translate hello to
  japanese" → `core_dictionary` noise (translator absent); "send an email to my boss" → no email
  node in top-4; "define serendipity" → `core_network`.
- Correct node in top-4 on ~9/22 queries (≈41% P@4); at rank 1 on ~5/22 (≈23% P@1). Exact-keyword
  phrasings work ("forecast tomorrow" → `core_weather`; "crypto price" → `core_finance`); anything
  paraphrased or stopword-laden degrades to noise.
- "deploy my app to production" (no relevant skill exists) returns 4 confident-looking irrelevant
  nodes — there is no "no match" signal, so the model is invited to peek garbage.
- Brain rule nodes (`tool-philosophy`, `skill-routing`, `report-format`) pollute *skill* search
  results because brain.og is indexed alongside skills (§2.2).

**Implication (observation):** the in-repo benchmark measures *token ratio assuming retrieval already
succeeded* (query = first indexed keyword ✅ test_og_benchmark.py:48–51); on realistic queries the
engine frequently routes to the wrong node, and the 3-pass protocol then *spends* its token savings
peeking/loading noise — or the model gives up and improvises, which the usage tracker would record as
a never-used skill.

### 2.4 Citation verification 🌐

docs/reference/benchmark.md cites three papers (benchmark.md:25–38):

| Citation | Verdict |
|---|---|
| `arXiv 2604.27820` — "The ObjectGraph format" | **Exists** 🌐: *"ObjectGraph: From Document Injection to Knowledge Traversal — A Native File Format for the Agentic Era"*, authors **Mohit Dubey and Open Gigantic**, submitted 2026-04-30. It is **first-party** (Open Gigantic owns this repo) but benchmark.md presents it as if independent. Its headline "up to 95.3%" reduction is a figure a prior verification pass (recorded in project memory) found unreliable — the agreed stance was to rely on the reproducible in-repo benchmark instead. ⚠️ The *refutation detail* comes from that earlier pass, not re-verified today; the self-authorship and the 95.3% claim on the abstract page are verified 🌐. |
| `arXiv 2604.05333` Graph-of-Skills | **Verified** 🌐: title, −56.72% tokens vs full skill-loading, GPT-5.2 Codex all appear as quoted. Genuine third-party support for *category* (dependency-aware structural retrieval), not for `.og` specifically — benchmark.md says this honestly (line 38–41). Note: that paper's retriever is **hybrid semantic-lexical** — precisely the component Hachi lacks (§2.3). |
| `arXiv 2603.29919` SkillReducer | **Verified** 🌐: 48% description / 39% body compression, ">60% of body content non-actionable" — matches benchmark.md's paraphrase. |

## 3. Does it actually beat markdown memory? (the honest answer)

### 3.1 Versus what, exactly — four distinct baselines

**(a) Dump-all markdown, no caching.** Yes, overwhelmingly — this is what the 97.2% measures, it is
real, reproducible ▶, and CI-gated (ci.yml:80–98 Ⓐ). But it is a strawman in 2026: nobody ships this.

**(b) Dump-all *with Anthropic prompt caching*.** Here the picture inverts at small scale. Model
(parameters: library L tokens, k LLM calls per task, history H tokens average per call, cache read
0.1×, write 1.25×):

```
dump-all marginal cost/task    ≈ 0.1·L·k            (after first-turn 1.25·L write)
3-pass marginal cost/task      ≈ 3 extra calls · (H + 0.1·S_sys)  +  (P1+P2+P3 ≈ 260+) tokens
                                  + loaded content re-billed in history for the session's remaining calls
```

Worked examples (assumptions: k=4 calls/task, H=4k, warm cache):
- **L = 9k (the shipped library):** dump-all ≈ 3.6k token-equivalents/task; 3-pass ≈ 3×4k + 0.26k ≈
  **12k+** → cached dump-all is ~3× *cheaper* and 3 round-trips (~2–6 s) faster.
- **L = 60k (~280 nodes):** dump-all ≈ 24k/task; 3-pass still ≈ 12k → 3-pass wins ~2×.
- **L = 200k:** dump-all stops fitting/causes distraction; 3-pass wins by an order of magnitude.

Crossover ≈ `L ≳ 30·H/k` → with these assumptions ~**30k library tokens (~140 avg nodes)**. Caveats
that move it: cache TTL ~5 min (idle chat re-pays 1.25×L — favors 3-pass); distraction cost of 9k
irrelevant tokens on answer quality (favors 3-pass; Graph-of-Skills' +25.55% reward is evidence the
effect is real 🌐); multi-skill tasks multiply Pass-3 loads (favors dump). **Confidence in the model
shape: high; in the exact crossover: low — measuring it is benchmark-spec Metric M3.**

**(c) File-granular lazy markdown (Claude Code Agent-Skills pattern: per-skill description always in
prompt, body read on demand).** This is the fair fight and the in-repo benchmark does not run it.
At 42 small nodes the description table ≈ the `::index`, and one `read_file` ≈ one `load_skill` —
costs are nearly identical. `.og`'s real deltas vs (c) are *qualitative*: sub-file block selection
(`blocks=["steps"]`), per-block token manifests before loading ✅ engine.py:463–497, machine-checkable
`::assertions`, RBAC scope filtering, changelog delta-loading, and skills that *carry their own
executable tools* (`::api` → UniversalRestAdapter, auto-unlocked on load ✅ loop.py:519–525) — that
last one file-lazy markdown genuinely cannot do.

**(d) Vector RAG over skill chunks.** Not implemented (no embeddings anywhere in og_engine ✅) and not
benchmarked. Given §2.3, an off-the-shelf embedding retriever would very likely beat the current
keyword search on paraphrase queries — this is the moat's most exposed flank.

### 3.2 Conditions under which `.og` wins / fails (summary)

**Wins when:** library ≳ ~30k tokens; tasks are procedural (steps/assertions matter); skills bundle
credentials-scoped REST tools; multi-tenant scoping (RBAC) or delta updates matter; authoring is
agent-driven (save_skill round-trip with lint ✅ engine.py:621–771 is genuinely novel).
**Fails when:** queries paraphrase (no semantic match); content authored without keywords/index
(23/29 of its *own* shipped files); names collide (live, §2.2); library small enough that cached
dump is cheaper; tasks need cross-skill composition (1 requires edge shipped; engine won't traverse
automatically by design ✅ engine.py:505–509).

### 3.3 Verdict

The 97.2% figure is **true, narrow, and over-claimed in extrapolation**: it proves selective loading
beats naive concatenation on token *count*, with a generous estimator (`len/4`), an oracle query, no
quality measurement, no caching in the baseline, and no competitive baseline. The format's defensible
advantages are real but currently *unrealized* in: shipped content (non-compliant), retrieval
(keyword-only, noise-prone), and graph behavior (no data). **The moat as shipped is the format
contract + authoring loop, not the runtime intelligence.** That is fixable — and the fix list is
short (§7).

---

## 4. What is genuinely defensible (observation, for Phase 3 positioning)

1. **Block-granular loading with pre-load cost manifests** (peek returns `available_blocks` token
   prices ✅ engine.py:470–489) — no markdown-skill system exposes this.
2. **Skills-as-capability-bundles**: `::api` definitions become live, SSRF-guarded, secret-injected
   tools on load ✅ rest_adapter.py Ⓐ — knowledge and capability ship in one reviewable file.
3. **Deterministic guardrails in content**: `::assertions` machine-checked pre-execution ✅
   assertion_eval + check_skill_assertions tool.
4. **Self-improvement loop**: save_skill → serialize (injection-escaped ✅ serializer.py:29–40) →
   lint advisories → refine, with semver+changelog ✅ engine.py:705–771.
5. **Scope/RBAC at the knowledge layer** ✅ engine.py:258–293 — per-role views of one library.
6. **A first-party spec + (first-party) paper** establishing the format vocabulary 🌐.

## 5. Where the current implementation contradicts its spec (consolidated from Phase 0 §6.7 + this phase)

| Spec promise | Reality | Severity for the moat |
|---|---|---|
| Auto-traversal of `requires` on resolve (§5.1) | Footer-only by deliberate design ✅ engine.py:505–509 | Low (defensible choice) — but then the *spec* is wrong |
| Confidence <0.3 auto-excluded (§5.3) | `confidence` never consulted ✅ | Medium |
| Session visited-skip (§5.4) | Absent ✅ | Low |
| "O(1) routing" | Linear substring scan ✅ engine.py:369–372 | Cosmetic now; real at 10k keywords |
| Dense ≤30 tok discipline | Shipped average 38 ▶ | Medium (credibility) |
| "Majority of queries complete at Pass 2" (benchmark.md:56) | No instrumentation measures pass-completion depth ✅ | Medium (unsubstantiated public claim) |

---

## 6. Risks if unaddressed (observation)

R-a. A competitor (or a blog post) runs exactly the probe in §2.3 and publishes "Hachi's flagship
benchmark can't find the weather skill from 'what's the weather in Paris'." The 97.2% headline then
reads as marketing, damaging the one number the project leads with.
R-b. Community packs (Phase 5 ambition) at today's namespace + lint-advisory-only rules produce
silent shadowing and unroutable skills at scale.
R-c. The first-party paper presented as independent support invites an OSS-credibility incident;
the two genuinely independent papers are *stronger* support and are diluted by it.

---

## 7. What I propose — moat-hardening before moat-marketing

| P | Proposal | Evidence it addresses | Effort (conf.) |
|---|---|---|---|
| P0 | **Retrieval v2**: tokenize queries with a stopword list; replace bidirectional substring with prefix/stem match; rank by BM25 over (keywords + dense + name), tie-break by `::traverse` priority then `confidence`; return a calibrated `no_match` signal below a score floor. Pure-Python, no new deps. | §2.3 probe | 2–4 d (high) |
| P0 | **Qualified node IDs + collision error** (Phase 1 R6) — shipped library already collides ×6. Also: exclude `brain.og` from the *skill* search surface (it is identity, not capability — it pollutes results). | §2.2 | 1–2 d (high) |
| P0 | **Make shipped skills exemplary**: add `::meta`+`::index` to all 29, dense ≤30, keywords incl. synonyms ("fx", "exchange rate"…), and ≥1 meaningful `requires` chain per pack. Wire `lint_og_file` over `default_skills/` as a CI job (errors block). | §2.1 | 1–2 d (high) |
| P1 | **Optional embedding rank** (reuse the ChromaDB dep already shipped): index node dense+keywords at boot; hybrid score = BM25 ⊕ cosine. Off by default for offline mode. | §3.1(d) | 2–4 d (medium) |
| P1 | **Instrument pass depth** (Pass-1/2/3 counters per query in usage DB) so "most queries stop at Pass 2" becomes a measured claim. | §5 | 0.5–1 d (high) |
| P1 | **Fix benchmark.md honesty**: disclose 2604.27820 as first-party; drop/replace the 95.3% reliance; add the §3.1(b) cost-model caveat ("below ~30k-token libraries, cached dump-all is competitive — `.og` is built for libraries that outgrow context"). Paradoxically this *strengthens* the pitch. | §2.4, R-c | 0.5 d (high) |
| P2 | Implement or delete spec promises (confidence filtering, visited-skip) and correct "O(1)" wording. | §5 | 1–2 d each (med) |

## 8. Benchmark specification — "OG vs the field" (proposal; runnable design)

**Goal:** replace a single token-ratio with a defensible, multi-axis, reproducible comparison that
Hachi can publish. Location: `benchmarks/og_bench/` + `hachi skill benchmark --suite {fast|retrieval|full}`.

### 8.1 Corpora (3 sizes × 2 sources)

| Corpus | Construction |
|---|---|
| **S-real** (42 nodes ≈ 9k tok) | The shipped library, post-§7-cleanup, frozen at a git tag. |
| **M-synth** (200 skills ≈ 60k tok) | Template-generated across 8 domains; controlled vocab with per-skill synonym sets; 30% of skills given 1–3 `requires` edges; 10% near-duplicate distractors (same domain, different procedure) to stress precision. Seeded ×3. |
| **L-conv** (≈1,000 skills) | Convert a public SKILL.md corpus (e.g. anthropics/skills + community sets; SkillReducer's 55k-skill crawl 🌐 shows supply exists) through the **existing** `skill_md_to_og` bridge ✅ engine.py:783–821. Key fairness property: *markdown and `.og` arms serve byte-equivalent content derived from the same source*. |

### 8.2 Query sets (per corpus; frozen JSON with ground truth)

5 types × ~100 queries: **K** verbatim-keyword · **P** paraphrase (zero keyword overlap; LLM-generated,
human-spot-checked 10%) · **I** task-intent ("I got double-charged, draft the support email") ·
**D** dependency (correct answer = skill + its `requires` closure) · **N** negative (no relevant
skill; correct answer = "none"). Ground truth = source skill id(s).

### 8.3 Arms

A. **Dump-all** markdown in system prompt, *with* prompt caching (the honest baseline).
B. **File-lazy markdown** (Agent-Skills pattern): name+description table in prompt; `read_file` on demand.
C. **OG as-is** (search→peek→load).
D. **OG + Retrieval v2** (§7 P0) — isolates the retrieval fix's contribution.
E. **Vector RAG**: Chroma over node (dense+full) chunks, top-k into context, no 3-pass.
F. **Hybrid**: vector recall → OG peek/load (block-granular).

### 8.4 Metrics

| ID | Metric | How |
|---|---|---|
| M1 | Retrieval P@1, P@5, R@5, MRR; false-positive rate on N-queries | Engine-only, deterministic, no LLM cost. Runs per-PR in CI. |
| M2 | Tokens **billed** per task | Real tokenizer (Anthropic count-tokens API; fallback tiktoken) + cache-aware cost model (write 1.25×, read 0.1×, messages uncached) over a scripted 10-turn session, 3 tasks/session. Reports $/task at current prices. |
| M3 | Crossover curve | M2 swept over corpus sizes S/M/L → "library size where each arm becomes cheapest" (answers §3.1(b) empirically). |
| M4 | Latency | Engine op time + (round-trips × configurable RTT, default 800 ms) + measured wall-clock on the live subset. |
| M5 | Task success | 50-task live-LLM subset (haiku-class): success = the skill's own `::assertions` evaluate true on the produced parameters (machine-scored ✅ assertion_eval) + 3-vote LLM-judge rubric for output quality. Paired across arms, same tasks. |
| M6 | Distraction cost | Accuracy on 30 *unrelated* QA tasks with each arm's context resident — quantifies dump-all's noise penalty (the Graph-of-Skills effect 🌐) instead of asserting it. |
| M7 | Pass-depth distribution (arms C/D/F) | % of queries resolved at Pass 1/2/3 — substantiates or kills the benchmark.md:56 claim. |

### 8.5 Protocol & hygiene

Paired per-query comparisons; medians + IQR; bootstrap CIs (n=10k resamples); 3 corpus seeds for
M-synth; fixed model + temperature 0 for live subset; all artifacts (corpora, queries, raw runs)
committed under `benchmarks/og_bench/data/` for re-runs. **CI tiers:** `fast` (current token gate +
M1 P@5 ≥ 0.8 on K+P queries — *adds a retrieval-quality gate so §2.3 can never regress in silence*)
per-PR; `retrieval` nightly; `full` (incl. M5/M6 live) weekly — est. live-LLM cost per full run
**$20–60** (low confidence; depends on judge votes and task length).

### 8.6 Publishable claim this enables (proposal)

If D/F win M1+M2+M5 at M/L scale, the honest headline becomes: *"At ≥200 skills, ObjectGraph's
block-granular 3-pass loads N× fewer billed tokens than cached full-context and matches/beats RAG on
task success — and below that scale we tell you to just dump your skills, because we measured it."*
That sentence is harder to attack than 97.2%.

---

**Carried to Phase 3:** §4 (defensible affordances) and §3.3 (verdict) are the raw material for the
switch argument; the §8 benchmark is the proof apparatus the positioning will lean on.
