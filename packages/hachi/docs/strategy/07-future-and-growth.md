# Phase 7 — Multi-Agent Architecture, Bold Bets, Open-Source Growth

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Inputs:** Phases 0–6. **Voices:** §1 = What I found · §2–§5 = What I propose.

---

## 1. Multi-agent today (observation)

| Capability | Status |
|---|---|
| Star delegation: `delegate_task` / `delegate_parallel_tasks` | ✅ delegation_tools.py:51, 622 |
| Isolation: own memory, own loop, role `.og` persona, 10-iter/120 s caps, cheap model default | ✅ sub_agent.py:51–53, 131–208, 470–713 |
| Scoped capability views: role-filtered SkillEngine (`with_role`), rebound tool registry | ✅ engine.py:270–293, orchestrator.py:1411–1427 |
| Structured handoff: `SubAgentReport` → ~50–150 tok orchestrator string | ✅ sub_agent.py:104–123 |
| Shared accounting: one CostTracker across orchestrator + workers | ✅ orchestrator.py:1230 |
| Report persistence + search: `delegation_log` collection | ✅ memory_vault.py:87–90 |
| **Absent**: inter-agent communication, shared working memory, conflict mediation, plan-level coordination, resumable long-horizon delegations | ✅ (no code paths exist) |

The star topology is a *strength* to keep — it is why context stays clean and spend stays capped —
but at platform scale (Phase 5's resident agents) three gaps bite: two agents acting on the same
resource, knowledge learned by one agent invisible to another, and multi-step plans that outlive a
single delegation.

## 2. Multi-agent architecture (proposal): "shared graph, leased resources, star control"

Keep one orchestrator per session; never build free-form agent-to-agent chat (cost- and
safety-unbounded; nothing in the field validates it for personal agents). Add four mechanisms, all
riding Phase 4/5 machinery:

1. **The plan is a graph, not a prompt.** Multi-step work compiles to `task` nodes with
   `next`/`blocks` edges in the Phase 4 memory schema (already designed). Delegation = assigning a
   task node; resumability = the graph *is* the state (a crashed run resumes from open nodes —
   pairs with the durable queue, R5). The "continue the migration" path (Phase 4 §5) is exactly
   this mechanism in single-agent form.
2. **Memory sharing = scoped views over the memory graph**, unifying with pack scopes (Phase 5 §6):
   workers read `projects/<their-assignment>` + `people/*` per scope; write **append-only** with
   provenance edges `->[:by=agent:researcher]` into a turn-scoped namespace; the orchestrator's
   gardener (Phase 4 §6.4) merges/supersedes into canon. Conflicting *claims* become two nodes with
   a proposed `supersedes` — reviewable, never lost. (Same governance answer as Phase 3; no new
   trust model to invent.)
3. **Conflict = leases, not locks-by-convention.** A tiny in-process lease table keyed by declared
   write-targets (path prefixes, integration scopes — the pack manifest §6 already declares them):
   a delegation that claims `gmail.send` or `~/work/billing/**` blocks a second claimant until
   release/expiry; read access unaffected. Per-session serialization (R1) makes this sound.
   Effort: 1–2 d (high) once R1 lands.
4. **Continuations instead of conversations.** A worker may return
   `needs: {role: analyst, task: …}` in its report metadata (field exists ✅ sub_agent.py:102); the
   orchestrator decides whether to spawn — coordination stays auditable and budgeted at the star's
   center. Effort: 1–2 d (high).

Total new machinery: ~1 week on top of Phases 1+4. Everything else is policy in `brain.og`'s
existing delegation framework ✅ default_skills/brain.og:110–146.

## 3. Bold bets (5–10 yr) — only what the OG advantage earns

**Killed first** (true of every agent, no format leverage): "smarter via bigger models" · voice/
multimodal everywhere · robot embodiment · generic AGI-assistant visions · IDE/coding-agent land war.

### B1 — Own the file-format layer: `.og` as the portable agent-brain standard
Your agent's entire competence and memory is a directory of typed, signed, diffable files — movable
between machines, engines, and (eventually) competitors. The `skill_md_to_og` bridge ✅, serializer
round-trip ✅, `min_agent_version` ✅, and (Phase 5) signed packs are the seed. 10-yr shape: `.og` is
to agents what Markdown became to docs — the neutral substrate; Hachi is its reference engine
(analogy: Obsidian's relationship to Markdown). **Leading indicator:** a second, non-Hachi tool
ships `.og` read support. **First 90-day step:** publish the spec as versioned standalone repo +
conformance test suite (the spec doc ✅ exists; conformance = parser tests extracted). **Risk:**
agentskills.io/SKILL.md gravity — mitigation: keep the lossless import bridge and *export* too.

### B2 — The federated skill economy with verified provenance
Agents author skills today (`save_skill` ✅), usage-track them ✅, lint them ✅. The bet: skills
become tradeable units with signed lineage — who authored (human/agent), what assertions they carry,
how they performed (pass-depth + assertion outcomes, Phase 2 M7) — federated indexes rather than one
registry. ClawHavoc 🌐 proved naive registries poison; Hermes 🌐 proved self-authored skills compound.
The differentiated substrate is exactly the governance stack: lint gates + assertions + signatures +
scope manifests. 10-yr shape: reputation-weighted skill exchange where your agent *buys* (or barters)
verified procedures. **Indicator:** ≥100 community packs with signatures; skill reuse across
strangers' agents. **First step:** Phase 5 Stage-1 index repo with signing from day one. **Risk:**
cold start — seed with the 7 first-party agents' packs.

### B3 — The personal institutional memory ("life graph")
Phase 4's decision/causal/temporal edges, compounded over *years*, become something no chat log can
be: "what did I decide about X in 2027, why, what did it cause, who was involved" answered with
evidence links. The moat is the data shape, not the model — and because it's user-owned files (G1),
it is sovereignty-compatible lock-in: leaving Hachi means abandoning your own institutional
memory *only if* no other engine reads `.og` — which B1 deliberately gives away, making the
retention story *quality of traversal*, not hostage-taking. **Indicator:** users with >1k memory
nodes; "ask about last year" weekly actives. **First step:** Phase 4 M0–M2 + a yearly "memoir"
artifact generated from the journal layer (demo that markets itself). **Risk:** extraction quality
(Phase 4 §8 measurement plan).

### B4 — Device-fleet sovereignty: the agent that lives in *your* devices
`.og` memory/skills are plain text → trivially syncable (git, Syncthing, CRDT-merge later); the
engine already runs local models ✅ llm.py ollama path; channels make any device a surface. The bet:
one agent identity across laptop + home server + phone, memory converging via file sync, compute
chosen per task (local for private, API for hard) — the structural opposite of cloud-assistant
platforms, and the segment (self-host, 🌐 Hermes' $5-VPS audience) big tech won't serve. **Indicator:**
multi-device sync in >20% of installs. **First step (90-day):** document + test the git-synced
workspace pattern (near-zero eng: files are already the state — needs conflict-policy docs + journal
shard-per-device naming). **Risk:** sync conflicts on SQLite/Chroma — mitigated by Phase 4 M4 making
files canonical and indexes derived (rebuildable).

*(Why exactly these four: each is downstream of the typed-file decision — portability (B1), verified
exchange (B2), longitudinal structure (B3), sync-ability (B4). None is available to a competitor
whose brain is a prompt and whose memory is a vector DB.)*

## 4. Open-source growth strategy (proposal)

**Constraint recap (Phase 3):** capability ≈ met for a v0.1; distribution ≈ zero; the category's
attention is currently shaped by OpenClaw's security crisis — a governance-positioned entrant has a
narrative window 🌐.

### 4.1 Two onramps, not one

- **Pack authors (no Python).** `.og` authoring is the low-floor contribution path — skill authors
  are domain people, not engine devs. Needs: `hachi skill new` scaffold (CLI has the verbs ✅),
  authoring guide distilled from the spec, lint-in-CI template repo, and the Stage-1 index
  (Phase 5). This is the path ClawHub proved demand for (13.7k skills 🌐) — gated this time.
- **Core contributors (Python).** Assets in place: fast suite (61 s ▶), uv, CONTRIBUTING.md ✅,
  AGENTS.md ✅. Gaps to fix: stale CLAUDE.md (R10), no ARCHITECTURE.md (distill Phase 0 recon —
  0.5 d), no curated starter issues (**the Phase 1 debt register is a ready-made
  `good-first-issue` list** — each TD item is typed, file-cited, and scoped), **no SECURITY.md /
  disclosure policy** ✅ (absent from repo listing — indefensible for a governance-positioned
  project; 0.5 d, P0 for credibility).

### 4.2 Plugin SDK (the extensibility contract)

Today's extension points — tools (`register_*` ✅), packs (`.og`), MCP servers ✅, providers
(`BaseLLMClient` ✅) — work but are *internal* APIs. Proposal: a `hachi.sdk` namespace re-exporting
the stable surface (ToolRegistry/ToolSpec, pack manifest types, runtime-event names, BaseLLMClient),
**semver'd independently of the app**, with contract tests third-party authors can run
(`hachi doctor --plugin <pkg>`). Effort 3–5 d (medium). Without this, every internal refactor
(Phase 1 R11) breaks the ecosystem we're trying to start.

### 4.3 Five growth loops (each with its existing artifact)

| Loop | Mechanism | Existing seed |
|---|---|---|
| **Benchmark loop** | Publish Phase 2's 6-arm benchmark + honest crossover math → HN/blog → "finally an agent that measures itself" | benchmark harness ✅ + Phase 2 spec |
| **Pack loop** | Author → `save_skill` → publish to index → consumers become users → some author | save_skill ✅, lint ✅, Phase 5 format |
| **Telegram demo loop** | 5-min guided setup → screenshot/share "my agent briefed me" — OpenClaw's actual viral motion Ⓢ, minus the exposed-gateway failure | telegram_setup.py ✅ (this branch) |
| **Switcher loop** | "Bring your memory": importer already parses **ChatGPT/Gemini/Hermes** exports Ⓐ memory_importer.py → Phase 4 typed import = a switching-cost destroyer aimed at the 180k-star Hermes audience | memory_importer.py Ⓐ |
| **Governance content loop** | Security-audit CLI + postmortem-literate writing (ClawHavoc/CVE analyses) → the trust segment; every Phase 1/2 fix is a publishable engineering post | security-audit ✅, this docs/strategy corpus |

### 4.4 Operating rhythm & metrics

- **Cadence:** 2-week release trains (RELEASING.md + OIDC pipeline ✅ make this cheap); RFCs as ADRs
  in-repo for surface-area changes.
- **Honest metrics** (stars are vanity): onboarding completion rate (state file exists ✅
  paths.py:33), weekly schedulers-retained (≥1 enabled schedule = the "always-on" behavior),
  packs published, PyPI downloads, time-to-first-magic p50.
- **Sequencing guard:** loops 1/3/4 fire **only after** Phase 1 R1–R4 + Phase 2 P0s land — Phase 3
  §7 risk 2 (marketing before fixes falsifies the position) is the single biggest self-own
  available. The launch order is: fix → benchmark → tell.

## 5. Effort summary (feeds Phase 8)

| Item | Effort (conf.) |
|---|---|
| Leases + continuations + scoped memory views (multi-agent v2) | 4–6 d (medium-high), after R1/R5 + Phase 4 M1 |
| SECURITY.md + disclosure policy + ARCHITECTURE.md + starter-issue curation | 1–2 d (high) — immediate |
| `hachi.sdk` contract surface + plugin doctor | 3–5 d (medium) |
| Spec repo + conformance suite (B1 first step) | 2–4 d (medium-high) |
| Pack-author scaffold + guide (`skill new`) | 2–3 d (high) |
| Git-synced workspace pattern docs/tests (B4 first step) | 1–2 d (medium) |
