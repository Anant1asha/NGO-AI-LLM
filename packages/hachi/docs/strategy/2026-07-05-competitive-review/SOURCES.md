# SOURCES — Competitive Review 2026-07-05

All sources fetched 2026-07-05 via a deep-research harness (fan-out search → source extraction →
3-vote adversarial verification). **Verification status** reflects the adversarial pass:

- **Verified 3-0 / 2-0** — three (or two, one errored) independent skeptic votes failed to refute the
  claim against the live primary source.
- **`[primary, unverified]`** — extracted from an official primary doc with a verbatim quote, but the
  adversarial re-check was interrupted by a session rate limit before completing. Treat as
  well-sourced but not independently re-verified.

## Primary sources — OpenClaw & Hermes (verified 3-0)

| # | Source | Used for | Status |
|---|---|---|---|
| 1 | https://github.com/openclaw/openclaw | MIT license; local-first gateway architecture; 23-channel list; pairing/allowlist/`dmPolicy`/sandbox governance | Verified 3-0 |
| 2 | https://docs.openclaw.ai/concepts/memory | Native `MEMORY.md` memory; daily notes; `memory_search` hybrid search + embedding providers | Verified 3-0 |
| 3 | https://hermes-agent.nousresearch.com/docs/user-guide/features/memory | `MEMORY.md`/`USER.md`; user modeling; background self-improvement review; approval gating + staged review | Verified 3-0 |
| 4 | https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban | Kanban board; append-only `task_events` audit log; worker logs; live WebSocket dashboard + tail CLI | Verified 3-0 (audit-log claim 2-0) |

## Primary sources — incumbent coding agents (`[primary, unverified re-check]`)

| # | Source | Used for |
|---|---|---|
| 5 | https://code.claude.com/docs/en/permission-modes.md | Claude Code 6 permission modes; auto-mode classifier; "Recently denied" review |
| 6 | https://code.claude.com/docs/en/agent-sdk/permissions | Deterministic permission-eval order; deny-rule hard override |
| 7 | https://cursor.com/docs/agent/security | Cursor default-restrictive terminal approval; MCP approval; Run Modes + honest-limits framing |
| 8 | https://cursor.com/docs/cli/reference/permissions | Cursor CLI default-deny approval model |
| 9 | https://docs.github.com/en/copilot/reference/copilot-allowlist-reference | Copilot cloud-agent default-on network allowlist |
| 10 | https://docs.github.com/en/copilot/concepts/policies | Copilot org/enterprise governance policies |
| 11 | https://github.com/NousResearch/hermes-agent | Hermes repo (licensing/momentum cross-check) |

## Secondary / blog — momentum, pricing, thesis (context, not load-bearing on their own)

| # | Source | Date | Used for |
|---|---|---|---|
| 12 | https://www.glukhov.org/ai-systems/comparisons/openclaw-hermes-alternatives-popularity/ | 2026 | Star counts; OpenClaw velocity collapse (+40k→+1.7k/wk); Hermes +3.8k/wk |
| 13 | https://www.marktechpost.com/2026/05/10/openclaw-vs-hermes-agent-why-nous-researchs-self-improving-agent-now-leads-openrouters-global-rankings/ | 2026-05-10 | Hermes overtakes OpenClaw on OpenRouter daily tokens (224B vs 186B); cumulative 9.17T vs 6.35T |
| 14 | https://smartproductivitytools.com/openclaw-in-2026-is-the-hype-dead-or-just-growing-up/ | 2026 | OpenClaw adoption cooling; compute-cost/trust friction |
| 15 | https://medium.com/data-science-in-your-pocket/openclaw-is-dead-6f6e3cab731f | 2026-05-14 | Early promoters stepping back (qualitative) |
| 16 | https://github.com/openclaw/openclaw/issues/43747 | 2026-03-12 | Memory inconsistency across installs (user report, v2026.3.8) |
| 17 | https://www.mindstudio.ai/blog/agent-harnesses-beat-model-upgrades-5-benchmarks | 2026-05-01 | Endor Labs 61.5% vs 87.2% same-model harness gap; Google "LLM ≈ 10%" |
| 18 | https://medium.com/@adambaitch/the-model-vs-the-harness-which-actually-matters-more-59dd3116bb31 | 2026-03-04 | Model-sets-ceiling / harness-realizes-it nuance |
| 19 | https://zylos.ai/research/2026-05-01-ai-agent-governance-compliance-2026/ | 2026-05-01 | Gartner 40%-of-enterprise-apps-by-end-2026 governance trend |
| 20 | https://thenewstack.io/openclaw-hermes-agent-harness/ | 2026 | OpenClaw/Hermes harness comparison (context) |
| 21 | https://hackernoon.com/hermes-agent-vs-openclaw-which-ai-agent-framework-wins-in-2026 | 2026 | Framework comparison (context) |
| 22 | https://www.sitepoint.com/claude-code-vs-cursor-vs-claude-code-the-2026-developer-comparison/ | 2026 | Pricing cross-check (Cursor/Copilot/Claude Code) |
| 23 | https://spectrumailab.com/blog/ai-coding-tools-pricing-compared-2026 | 2026 | Copilot tiered pricing detail |
| 24 | https://hermes-ai.net/ | 2026 | Hermes self-improvement/user-modeling marketing (Honcho detail `[primary, unverified]`) |

## Grounding claims — verification outcomes

| Grounding claim (as given to the exercise) | Outcome |
|---|---|
| OpenClaw won early mindshare on integration breadth + fine-grained manual control | **Confirmed** (23 channels; pairing/allowlist/sandbox) |
| OpenClaw has **no native memory layer** | **Refuted** — native `MEMORY.md` + hybrid `memory_search` (source #2) |
| OpenClaw is losing users in 2026 | **Partially confirmed** — star velocity collapsed, adoption cooling, but still large; qualitative, not a usage cliff |
| Hermes gaining share fast on self-improvement loop + Kanban dashboard | **Confirmed** (skill/memory loop; Kanban; #1 OpenRouter daily) |
| Hermes has **less fine-grained control/visibility than OpenClaw** | **Refuted** — approval gating, staged review, append-only Kanban audit log, live dashboard (sources #3, #4) |
| Harness quality matters more than model quality | **Supported with a boundary** (model sets ceiling; harness realizes it) — source #17, #18 |
| Governance + visibility becoming table stakes | **Confirmed** — all five ship it; source #19 + all primary docs |

## Research limitations
- The final synthesis + several coding-agent verification votes did not complete (session rate limit).
  The strategy-critical findings (OpenClaw memory; Hermes governance; momentum) are all in the
  verified-3-0 set; the incumbent coding-agent details are primary-sourced but not adversarially
  re-checked.
- Momentum figures come from secondary trackers and should be treated as directional, not audited.
