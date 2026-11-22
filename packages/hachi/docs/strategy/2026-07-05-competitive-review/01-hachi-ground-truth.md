# 01 — Hachi Ground Truth (what it does today)

*Source: read-only codebase audit (2026-07-05) cross-checked against [`docs/audit/2026-07-03/`](../../audit/2026-07-03/PRODUCTION_READINESS.md). Test baseline: 4,151 passed / 21 skipped / 0 failed.*

The one-line verdict: **a well-engineered engine with a serious claim-vs-code gap.** The infrastructure
for governed autonomy is real and rare; the headline features are broken at the exact points the brand
depends on. Fixing the four criticals + nine highs is concentrated work (~1–2 weeks), not a rewrite.

## Maturity by area

| # | Area | Verdict | One-line evidence |
|---|---|---|---|
| 1 | Core agent loop | **Production-ready** | Real ReAct in `core/loop.py`; streaming; Esc-interrupt; sub-agent delegation; per-session + per-turn cost/token caps enforced between calls |
| 2 | `.og` ObjectGraph format | **Ready (governance honor-system)** | Working 3-pass retrieval in `og_engine/engine.py`; 31 bundled skills / 60 nodes; `save_skill` writes versioned `.og`; lint/assertions **not enforced in the loop** |
| 3 | Memory | **Broken / partial** | **Auto-extract is a silent no-op (C1)** — missing `get_memory_vault()` symbol; every extraction job swallowed. Explicit `remember` works. Also gated on `ANTHROPIC_API_KEY` even for injected non-Anthropic clients |
| 4 | Permissions / "leash" | **Partial (engine works, UX broken)** | Call-time `PermissionGate`; 3 tiers (`sandbox`/`guided`/`unrestricted`); **web approve/decline never calls backend**; skill governance advisory only (M2) |
| 5 | Cost governance | **Partial (operational bugs)** | Real `CostTracker` + caps + routing; background-spend path leaks a SQLite connection (H2); post-hoc check can overrun by one generation; no single model registry yet |
| 6 | Channels & integrations | **Partial / facade** | Telegram real; Google OAuth real; Slack/Discord outbound; generic inbound webhook; **Notion/Slack OAuth is a facade — tokens stored, nothing consumes them (H5)**; scheduler races on shared file (H3); WhatsApp/email unverified |
| 7 | Surfaces (web / TUI / gateway) | **Works (governance surfaces broken)** | ~9/11 web screens render; TUI works; gateway well-hardened (loopback + SHA256 bearer, constant-time); approvals optimistic-only; facade sessions skip ownership (H6) |
| 8 | Sandboxing / exec safety | **Partial (defects)** | Docker + call-time gates + SSRF/injection guards are solid; some file-gate bypasses (M3); secrets-store durability gap (M1) |
| 9 | Eval / benchmark | **Partial (headline broken)** | `hachi eval run` replay gate is real; **"97.6%" benchmark measures a failed query (C3/C4)** and the frozen corpus is stale vs shipped |
| 10 | Distinctive assets | **Real but partly claimed-false** | `.og` format, in-loop spend caps, multi-provider routing, call-time gating all real; the "governed / self-improving" claim is currently false in practice |

## The ship-blockers (from the 2026-07-03 audit)

**Criticals (block launch):**
- **C1 — Auto-memory is a silent no-op.** Missing `get_memory_vault()`; every fact-extraction job is
  swallowed and returns a misleading "skipped" — nothing is written to ChromaDB. Untested production path.
- **C2 — File-attachment tools crash on invocation.** Wrong `PermissionRequest` API + a call to a
  non-existent `gate.check()` method.
- **C3 — Headline benchmark number measures a failed query.** The "97.6%" comparison's later passes are
  short error strings, not real skill loads.
- **C4 — Benchmark CI gate is red on a clean checkout.** Frozen corpus is out of date vs the shipped
  library; the prefix matcher over-matches (high false-positive rate).

**Representative highs (normal-use bugs):** history mutated without a lock (H1); background-spend SQLite
connection leak (H2); per-session scheduler double-fires over one file (H3); ~85% of advertised slash
commands do not exist (H4); Notion/Slack OAuth facade (H5); facade sessions are ownerless (H6);
resilience subsystem decorative (H7); "delete session" doesn't delete the transcript (H8); PyPI install
broken (H9).

**Governance-tier:** governance is honor-system (M2) — lint never rejects a skill write in the loop,
`.og` assertions have no enforcement point, and web approvals don't call the backend.

## What a new user actually gets today

**Works:** install/quickstart, first conversation (TUI or web, streaming, tool use, session persistence),
skill load/search over the bundled library, permission tiers enforced at call time, per-session spend
tracking and caps, Google integrations (real OAuth).

**Breaks or misleads:** automatic memory writes nothing; file-attachment tools crash; most documented
slash commands don't exist; the web approval flow renders success without doing anything; Notion/Slack
"integrations" store tokens but never use them; the flagship benchmark number is measured off a failure
case; `pipx install hachi-og` 404s.

## Distinctive assets worth defending

These are genuinely rare in the category and are where Hachi is uniquely strong today:

1. **`.og` ObjectGraph format** — typed, scoped, versioned skill files with sub-file-granular loading.
   No competitor offers this (OpenClaw and Hermes both use markdown).
2. **In-loop spend caps** — per-session and per-turn budget enforced *between* LLM calls, able to stop
   mid-turn. Neither OpenClaw nor Hermes ship this.
3. **Call-time permission gating** — gates run at tool invocation, not just as prompts.
4. **Durable job queue + SQLite session store** — turns serialized per session, work persisted, resumable.
5. **Multi-provider routing** across Anthropic / OpenAI-compatible / OpenRouter / Groq / DeepSeek /
   Gemini / Ollama — no vendor lock-in (a structural advantage vs Claude Code and Copilot).
6. **Eval replay CI gate** — `hachi eval run` replays a frozen corpus through the real loop.
7. **Hardened gateway** — loopback default + SHA256 bearer (constant-time) + session ownership.

The strategic caveat: the assets the *pitch* leans on (memory, self-improvement, enforced governance)
are the ones that are broken or advisory; the assets that genuinely work (`.og`, spend caps,
multi-provider, eval gate) are under-marketed.
