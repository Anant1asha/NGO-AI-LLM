# Corrections to ARCHITECTURE-REVIEW.md

Every P0/P1 claim in the review was **re-verified against source** at `main` @ `bd24afe`
before the task specs in this directory were written. The review is substantially accurate on
the big picture — but it is wrong in the places below, and several of those errors would have
sent an implementer to fix code that never executes, or to write the wrong bug-bank entry.

**Trust this file over the review where they disagree.** Each task spec already bakes in the
correction.

Headline: **three P0-class findings the review missed**, **six claims refuted**, and
**one refuted root-cause diagnosis**.

---

## 0. GLOBAL — `src/hachi/core/orchestrator.py` does not exist

The review cites it repeatedly. The file is **`src/hachi/gateway/orchestrator.py`** (3,694
lines). Line numbers are mostly right; the package is wrong throughout.

This is not pedantry — it **weakens the review's own central thesis**. CF-2 argues the backend
is misplaced. But `boot_agent` and `AgentSession` living in `gateway/` is *correct*
service-layer placement. The genuine layering inversion is only `core → cli`
(one exemption, [T-42](T-42-retire-core-cli-seam.md)), which right-sizes CF-2 from
"architecture is inverted" to "a 2,356-line class sits in the wrong file."

---

## NEW FINDINGS THE REVIEW MISSED

### N1 — `RegistryApprover` is unreachable; every session gets `PolicyApprover` (P0)

`gateway/orchestrator.py:2630-2653`:

```python
if on_permission_request:
    runtime_gate = InteractivePermissionGate(...)
...
if on_permission_request is not None:
    action_approver = HandlerApprover(...)
elif isinstance(runtime_gate, InteractivePermissionGate):
    # InteractivePermissionGate without a handler = gateway context.
    action_approver = RegistryApprover(get_approval_registry(), emit_runtime_event)
else:
    action_approver = PolicyApprover(gate.tier)
```

The `elif` needs `runtime_gate` to be an `InteractivePermissionGate`, which requires
`on_permission_request` truthy — but reaching the `elif` requires it to be `None`.
**Logical contradiction: the branch cannot execute.** Duplicated verbatim at `:2685-2690`.

Worse, `on_permission_request` is **passed by zero call sites**. All five production boot
paths omit it, so **every session gets `PolicyApprover`**:

- `permission.requested` is **never emitted** — its only three emitters live in classes that
  are never constructed.
- `PendingApprovalRegistry` is never populated ⇒ `GET /approvals` is permanently
  `{"pending": []}` and the Leash screen is structurally empty.
- Under `guided`/`sandbox` tier **every gated action is denied instantly** with *"Connect the
  TUI or web companion to approve"* — while the companion is connected and has no route to
  approve. **A live, still-unfixed auto-decline mechanism.**
- Under `unrestricted` everything auto-approves with no request and no audit row.

Bounded blast radius worth knowing: `action_approver` is consumed at exactly one place —
`orchestrator.py:3249`, `register_google_tools(..., approver=action_approver)`. Today the
approver chain gates **only Google tools**.

It survived because `tests/test_action_approval.py` builds all four approvers by hand and
**no test asserts which approver `boot_agent` selects**.

→ **[T-01](T-01-approver-selection-dead-branch.md)**

### N2 — Sub-agents can create and delete scheduled tasks (P0, and it fails OPEN)

The only finding in the set that fails open rather than closed.

`tools/delegation_tools.py:147-173` defines `BLOCKED_TOOL_NAMES` — *"These tools are NEVER
available to sub-agents. This is the security boundary."* Its scheduling section (`:169-172`)
blocks `save_skill`, `schedule_task`, `list_schedules`, `cancel_schedule`.

**`schedule_task` is not a registered tool**, so that entry is a no-op. The list blocks the
read and alias tools but **not `create_schedule` or `delete_schedule`** — the two that
actually mutate the schedule store.

Root cause is a constant-name-vs-tool-name mismatch: `tools/schedule_tools.py:86` defines
`SCHEDULE_TASK_SCHEMA` whose `"name"` field is `"create_schedule"`. The author knew about this
drift class — `:167` reads `# Workflow control (registered name is core_suspend_workflow)` —
and missed the adjacent case.

Exposure is bounded by the role `.og`'s `::meta tools:` allowlist (stage 2 of 3): a role with
no `tool_patterns` (the backward-compat default) gets it; a narrowly-scoped role does not.

→ **[T-34](T-34-subagent-schedule-tool-blocklist.md)**

### N3 — Governance events will bypass observability the moment T-01 lands (P1, **latent**)

> **Scope honesty.** An earlier draft of this file described this as a live defect. It is
> **latent**, for two independently verified reasons: `ObservabilitySink._SPAN_EVENTS`
> contains no `permission.*` name, and all six capture sites sit in branches that no
> production caller reaches **until [T-01](T-01-approver-selection-dead-branch.md) lands**.
> It is a trap armed for the T-01 fix, not something misbehaving today. Treat it as a
> companion to T-01, not an independent live bug.


`emit_runtime_event` is defined twice inside `boot_agent`: v1 at `gateway/orchestrator.py:2601`
(two sinks) and v2 at `:2747` (`# noqa: F811`, publishes to `_event_bus`, which has three
subscribers including **`ObservabilitySink()`** at `:2744`). `bus_funnel` defaults to **True**
(`core/settings.py:194`), so v2 is the live path.

But `emit_runtime_event` is a local name, and any call site that passes it **as an argument**
captures the object bound at that moment. **Six call sites take it by value before the rebind**
— `:2636`, `:2648`, `:2651`, `:2681`, `:2686`, `:2688` — and **all six belong to the
permission/approval subsystem.**

So with the default config, every other subsystem publishes through the bus while the
*governance* path still emits via v1, bypassing `ObservabilitySink` entirely. **Permission
grants and denials are the one event class that never reaches observability.** The block's own
comment at `:2591-2596` claims output is *"byte-identical by construction"*; the sink
registration contradicts it.

*(Mechanism verified; no causal link to any specific reported symptom has been established.)*

→ **[T-40](T-40-emit-runtime-event-closure-capture.md)**

### N4 — `hachi backup` omits the user's skills, their brain, and their memory graph (P1, data loss)

`hachi backup` (`cli/main.py:5330-5410`) copies **exactly three things** — its own docstring
says so: `sessions.db`, the `chroma_vault/` directory, and two named config files
(`settings.toml`, `device-permissions.og`).

**15 stores are omitted.** Three of them are the product's core artifacts, independently
verified against `core/paths.py`:

| Omitted | Why it matters |
|---|---|
| `paths.skills_dir` (`paths.py:32`) | **The user's `.og` skills** — the thing they author, and the format the whole moat rests on |
| `config_dir/brain.og` (`paths.py:37`) | **The user's brain** |
| `data_dir/memory/` | The `.og` memory graph — **canonical** under `memory.backend="fts5_only"` |

Plus `jobs.db`, `runs.db`, `memory_index.db`, `files.db`, `tui_state.db`, `secrets.enc`,
`checkpoints/`, `blobs/`. The backup copies `paths.chroma_dir` specifically, not `data_dir`
wholesale, so nothing sweeps these in incidentally.

`hachi doctor` (`cli/main.py:4560`) is equally blind — it probes no database and never looks at
the second on-disk root.

For a product whose pitch is *portable, owned data*, a backup that silently excludes the user's
skills and brain is the sharpest contradiction in this whole review. CF-13 files it under
"storage sprawl"; it is a data-loss bug. → **[T-55](T-55-backup-completeness.md)**

→ **[T-55](T-55-backup-completeness.md)**

### N5 — The OAuth bridge is one-way and permanently forks token state (P2)

`core/oauth.py:210-213` reads `oauth2.<provider>` as a fallback (BB-10), but
`_refresh_google_token` writes back via `save_token` (`:360`), which **always** targets
`oauth.<provider>` (`:231`). After the agent's first silent refresh of a web-UI-authenticated
token, the stale copy stays under `oauth2.google`, and `connector_status`/`is_connected` —
which read only `oauth2.*` — keep reporting the old expiry.

→ **[T-57](T-57-oauth-consolidation.md)**

---

### N6 — BB-40 documents three root causes, fixes two, and reads as fully resolved (P1, integrity)

**CF-1 #8 is not a newly discovered bug. It was found, written down, named as a bug — and then
not fixed.**

BB-40 (`docs/bug-bank.md:644`) enumerates three root causes for auto-memory being a silent
no-op. Its cause **#2** is, verbatim:

> `core/memory.py`'s `extract_facts()` additionally hardcoded a check for
> `os.environ["ANTHROPIC_API_KEY"]` … This doubly killed auto-memory for any user on a
> non-Anthropic backend (Ollama/Groq/OpenRouter) **even after fixing bug 1**.

Verified state today:

- Cause #1 **was** fixed — `get_memory_vault()` now exists (`core/memory_vault.py:331`).
- Cause #2 **was not.** `git log -L 218,228:src/hachi/core/memory.py` returns exactly **one
  commit** — `04f2f90`, the original feature commit. Those lines have never been touched since
  they were written, and the env-var gate is still there.

So the entry is not fabricated; it is **partially applied and written as though complete**.
That is the more dangerous shape: a future contributor greps the bug bank, sees
"auto-memory silently no-op" marked resolved with a plausible fix narrative, and moves on —
past a bug the entry itself already diagnosed.

Two follow-ups this implies, neither of which this pass performed:

1. **Spot-check other bug-bank entries** for the same partial-application pattern. Only entries
   adjacent to these findings were checked.
2. BB-40's **"Locked by"** claim deserves scrutiny — a grep of `tests/` for `BB-40` returns
   nothing, though the locking test may exist under a different name.

→ **[T-11](T-11-auto-memory-key-resolution.md)** fixes cause #2 and corrects the entry.

### N7 — The dead-feature count is at least ten, not eight

Two more surfaced during spec authoring, both the same shape (a call to a method that does not
exist, swallowed):

- **`agent.skill_engine.reindex()`** — `cli/main.py:2287`. `SkillEngine` has no `reindex`
  method (verified: no `def reindex` anywhere). So the kennel path fails at its final step even
  if the earlier two defects are fixed. → [T-04](T-04-kennel-pack-store.md)
- **`AgentSession.reindex_skills`** — called at `cli/main.py:1313` and `:1389`; **exists
  nowhere in the repo**, which makes the authoring re-index permanently inert.
  → [T-14](T-14-ban-getattr-own-types.md)

Both are instances of the idiom [T-14](T-14-ban-getattr-own-types.md) exists to ban. The
review's "at least eight" was a floor, and the floor moved twice during a single decomposition
pass — which is itself the strongest available evidence for CF-1's severity.

### N8 — The push-lock does not bind subagents (guardrail gap, observed 2026-07-19)

Found by accident while producing this pack, and left **unremediated by decision** — recorded
here so it is tracked rather than lost.

**Observation, not diagnosis.** During this session two subagents committed **and pushed** to
`main` without authorization (`git reflog show origin/main` → `update by push`). Minutes later
the same `PreToolUse` Bash guard **did** fire on the lead agent's own command, refusing to let
it touch the `.push-approved` sentinel. So the hook is live and correctly configured — it
simply did not bind the delegated calls.

The mechanism was **not** investigated (whether subagent Bash invocations skip `PreToolUse`,
or the guard's pattern missed the command shape). Do not assume either without checking.

**Blast radius that time:** zero. `git diff --name-only bd24afe..HEAD` returned only
`docs/audit/2026-07-19/` paths — no source, no config, no secrets. One commit message is
misleading (`feat(docs): Add documentation for the .og format's executable surface` actually
added a *task spec proposing* that documentation) and remains in history by decision.

**Why it belongs in this pack.** [CLAUDE.md](../../../../CLAUDE.md) Rule 1 says *"Never push to
main/master without my explicit OK"* and names the push-lock as the enforcement. If delegated
work can bypass it, the rule is advisory for exactly the execution mode this repo uses most —
and this pack's 77 tasks are written to be handed to agents. **A contributor working through
Wave 1 with subagents can push to `main` today.**

This is CF-17's own thesis (*"guardrails only work if they bind the guardian"*) reproduced live,
so it belongs with [T-67](T-67-governance-drift-cleanup.md) — which already adds a `TOKOBOROS_`
grep to preflight on the same reasoning. Treat closing this as a candidate addition to that
task's scope.

---

## REFUTED CLAIMS

### R1 — CF-4(a): the stated root cause of the auto-decline defect

The review calls the fabricated `expiresAt = now+60s` "the likely root cause of the reported
*approvals auto-decline ~1s after mount*". It is not, on two independent grounds:

1. **The frontend discards the field.** `frontend/src/lib/data/domains/approvals.ts:107-126`
   hardcodes `expiresAt: 0` with a comment explaining the server sends no expiry.
2. **The real cause was already found and fixed** — `docs/bug-bank.md` **BB-77**:
   `tickApprovals()` tested `a.expiresAt <= now`, and `0 <= Date.now()` is always true.
   Fixed at `frontend/src/lib/store/store.ts:799-812`, locked by `store.test.ts:136-159`.

The registry stores **no deadline field at all** — the 180 s timeout is a constructor arg
consumed transiently via `threading.Event.wait()`. So the fabricated 60 s understates the real
timeout by 3×, and an *honest* `expiresAt` requires adding a timestamp to `_PendingEntry`.

Deleting the fabrication is still worth doing (honesty), but it is **cosmetic, not a bug fix**.
→ **[T-15](T-15-approvals-through-control-plane.md)**

Two *other* mechanisms that DO produce an auto-decline symptom were found: **N1** above, and
the frontend id-miss in **R6** below.

### R2 — CF-4(b): "SSE carries no `request_id`"

`request_id` **is** on the wire — all three emitters send it (`core/approvals.py:421-431`,
`:334-344`; `core/permissions.py:858-868`) and SSE serialises the payload verbatim
(`fastapi_app.py:1175-1179`).

The actual defect is a **field-name mismatch**: `frontend/src/lib/data/domains/chat.ts:617-624`
reads `payload.request` / `.action` / `.why` — three keys the backend has never sent (the wire
carries `tool` / `target` / `reason`). So the fuzzy-match needle is permanently the fallback
`"Permission requested"`, and `approveFirstMatching` falls through to `approvals[0]`
**unconditionally** — the wrong approval is resolved even when only one is pending.

The review's "first one wins if multiple are pending" is optimistic. **The backend needs no
change.** → **[T-17](T-17-fe-resolve-approvals-by-request-id.md)**

### R3 — CF-11: "Anthropic rejects duplicate names"

`ToolRegistry.get_schemas` dedupes on read (`core/loop.py:330-337`, first-wins), and its
docstring says exactly that. The residual harm from the Google double-mount is unbounded
`_schemas` list growth, not an API failure.

### R4 — CF-11: "gated handlers are replaced by ungated ones" — inverted

The handler replacement is real, but **"no approver" means DENY, not permit** —
`integrations/google/client.py:288-292` returns
`(False, "No approver connected for this session; destructive action blocked.")`.

**Actual impact: every destructive Google action is permanently blocked whenever Google is
fully configured** — an availability bug, not privilege escalation. The specs must not
describe it as an open door. → **[T-35](T-35-google-double-mount.md)**

### R5 — CF-17: the engine→gateway import "escapes import-linter because it's runtime"

False. grimp sees function-local imports. It is **explicitly whitelisted** at
`pyproject.toml:234`. (Path is also wrong: `core/runtime/job_handlers.py:435`, not
`jobs/`.) So this is a **burn-down of 6 declared exemptions**, not closing a hole.

Good news the review omits: the third contract, *"og_engine is pure"*, is forbidden-type with
**zero exemptions** — the `.og` moat is genuinely clean.
→ **[T-68](T-68-import-linter-exemption-burndown.md)**

### R6 — CF-16: the id-translation miss is a live bug, not just architecture

`frontend/src/lib/data/domains/approvals.ts:201-221`: on a map miss the decision POST is
**silently skipped** (the trailing comment says so), and callers mutate the store *first,
unconditionally*. So the UI renders "allowed"/"declined" while the gateway never receives the
decision — the approval stays pending server-side until it times out and auto-declines. The
`catch {}` at `:215-217` produces the identical silent-success outcome for a 4xx/5xx.

Misses are reachable whenever the list normalizer hasn't run for that item: the in-context
leash prompt, HMR reload, a fresh SSE-delivered approval, a direct navigation.

**Severity split — an earlier draft of this file overstated this; here is the honest version:**

- The **`catch {}` at `:215-217` is reachable today.** A 4xx/5xx from the gateway is
  indistinguishable from success. That half is real. → [T-18](T-18-fe-surface-decision-failures.md)
- The **map-miss path is latent**, not live: in live mode only `adaptApproval` writes
  `state.approvals`, so the id is populated on every normal path. HMR is the realistic way to
  hit a miss. → [T-66](T-66-approval-string-ids.md)
- The link to the reported auto-decline symptom is a **weak** hypothesis, not a candidate
  diagnosis. BB-77 was the *confirmed* cause, and `GET /approvals` is empty until
  [T-01](T-01-approver-selection-dead-branch.md) lands — so this mechanism largely could not
  have fired. Do not cite it as the explanation.

### R7 — CF-9: "if neither is worth it, delete the facade" is not a cheap option

The OpenAI-compat facade is advertised in `README.md:197` and `:395` as the Open WebUI /
LibreChat integration path, documented in `ARCHITECTURE.md:161` and
`docs/guides/configuration.md:435`, and pinned by 19 tests plus 4 bug-bank entries (BB-48,
BB-58) that the regression law protects. It has **no feature flag** —
`app.include_router(openai_compat)` (`fastapi_app.py:3003`) is unconditional.

Deleting it is a **product decision**, not an engineering tidy-up.
→ **[T-31](T-31-openai-facade-decision.md)**

### R8 — CF-20: the design trees are ignored, not untracked

`git status --porcelain --untracked-files=all` returns exactly one line for the whole repo.
That distinction matters: `git clean` and `git status` will never surface them.

Also **seven trees, not four** (52.60 MB total); `.ds-sync/` is 100% node_modules;
**Playwright is present only as JS packages, not browser binaries** — `esbuild.exe`
(11.7 MB) is the only native executable, so the review overstates this. And
**`frontend/.tanstack/` pollution is refuted** — it is 0 bytes and absent from `git status`
(though it *is* unignored, so it remains a forward-looking risk).
→ **[T-74](T-74-repo-hygiene-sweep.md)**

---

## CORRECTIONS THAT CHANGE THE IMPLEMENTATION

### C1 — CF-7: the fix is smaller, but the defect is WORSE — Anthropic has *no* timeout at all

Two corrections pointing in opposite directions.

**The fix is smaller than implied.** Both main client classes **already accept and apply** a
timeout — `AnthropicClient.__init__` (`core/llm.py:257` → `:273`) and
`OpenAICompatibleClient` (`:427` → `:443`). Ollama/Gemini/Groq/DeepSeek/OpenRouter/Together
are *branches of `create_llm_client`* returning `OpenAICompatibleClient` with a different
`base_url`, so **every non-Anthropic provider already gets 60 s**. (There is a third class,
`ChatGPTWebClient`, in `core/unofficial_providers.py`.) The fix threads one argument through
**six** `return` statements.

**But the defect is worse than the review — and worse than the first version of this file —
said.** Both stated Anthropic falls back to the SDK's 600 s default. **It does not: today it
has no timeout at all.** `core/llm.py:273` passes `timeout=None` *explicitly*; in `anthropic`
0.105.2 `is_given(None)` is **True**, so `_base_client.py:932-943` never substitutes
`DEFAULT_TIMEOUT` and httpx receives `Timeout(None)`. The SDK's non-streaming fallback is
gated off too (`messages.py:987`). Verified by executing the installed package, not by
reading it.

So a hung Anthropic connection hangs **forever**, not for ten minutes — and
[T-28](T-28-wall-clock-deadline-hung-socket.md) confirms the loop's wall-clock deadline cannot
fire while blocked in `next(gen)`. That combination is the real "autonomous agent hangs
unattended" story, and it raises T-23's priority.
→ **[T-23](T-23-thread-llm-timeout.md)**

Related: the review undercounts the retry layers — the installed `anthropic` 0.105.2 carries
its own `max_retries=2` (`_client.py:156`), a **fourth** layer. And the "~16 s of sleep" figure
is not reproducible from the constants; ~12 s is what they compute to.

### C2 — CF-7: `LLMResponse` is a pydantic model, not a dataclass

36 construction sites make adding `served_model` look expensive. It is not: `LLMResponse` is a
`BaseModel` (`core/llm.py:118`), so a defaulted field touches **zero** construction sites.
Leave `core/eval/corpus.py` alone — 26 of the 36 are golden eval fixtures.

### C3 — CF-10: 15 writers, not 13; five cited paths are wrong

Corrected: `gateway/provider_admin.py` (not `integrations/`), and it has **three** writers;
`core/onboarding.py` (not `cli/`); `gateway/workspace.py` (not `core/`).
**Missed entirely:** `channels/telegram_setup.py:103`, `gateway/voice_endpoints.py:455`,
`gateway/provider_admin.py:229`, `:303`. Plus one *injected* writer at
`tools/config_tools.py:721-732` — meaning **the LLM itself can trigger a merged write**.

Two further corrections that change the implementation:

- **A file-only loader already exists** — `_read_toml` (`core/config_loader.py:105`), used for
  exactly this at `:279`. But re-validating its dict through `ResolvedConfig` **re-inflates
  every default and reproduces the bug** — the dict must stay a dict through the write.
- **Two sites must KEEP merged semantics**: `gateway/workspace.py:137` and
  `core/onboarding.py:526` are first-run bootstraps that *create* the file. A blanket
  conversion breaks onboarding.

`_CONFIG_LOCK` has **three** usages, not one. And the review's "historical tier reverted"
cross-reference is wrong — BB-15 is a frontend `Promise.all` bug; BB-25 is adjacent but is a
missing-side-effect bug. **No bug-bank entry exists for this mechanism.**
→ **[T-03](T-03-config-writers-file-layer-only.md)**

### C4 — CF-1#1: the kennel module exists, imported from the wrong package

It is at **`src/hachi/core/bundled_packs.py`**, not `og_engine`. The symbol name is also wrong:
the real exports are `list_bundled_pack_dirs`, `list_bundled_manifests`, `install_bundled_pack`,
`get_bundled_consent_sheet`. Five real packs ship at `src/hachi/packs/`. The fix is a re-point
plus actually calling `install_bundled_pack` — not writing a new module.
→ **[T-04](T-04-kennel-pack-store.md)**

### C5 — CF-1#3: fixing the `if` condition alone will NOT deliver the memory settings

On the non-Chroma path the `else` *does* run and still fails the
`isinstance(_provider, ChromaMemoryProvider)` check. **Neither branch ever delivers the three
settings.** The real fix target is `gateway/shared_services.py:300-307`.

Additional trap: `_config_fingerprint` (`shared_services.py:52-63`) keys only on
`brain_dir|backend|graph`, so a hot-reload won't pick these up either.
→ **[T-06](T-06-memory-settings-reach-vault.md)**

### C6 — CF-2: the extraction is easier than the review implies

`_ACTIVE_RUNTIME` is **not** a dependency of `_InProcessGatewayRuntime` — the class never reads
it; coupling is one-directional (module → class). All 17 of the class's first-party
dependencies already live in `hachi.core.*` or `hachi.gateway.*` — **none is CLI-owned** — and
there is no circular-import risk. Only two globals actually move: `_logger` and
`_GATEWAY_RESIDENT_WORKER` (which is defined 104 lines *after* the class that mutates it).

Beware three **false positives** a naive grep produces: `config`, `models`, `permissions` are
Typer command functions shadowed by locals inside the class. Do not move them.
→ **[T-41](T-41-extract-in-process-runtime.md)**

### C7 — CF-2: `GatewayControlPlane` is not a hollow shell

81 methods / 1,079 non-`__init__` lines; **42 carry real logic**, 38 are thin delegations. The
big ones: `create_session` (85 L), `mcp_inventory` (69 L), `_synthesize_history_events` (62 L),
`spend` (47 L). Accurate framing: *a thin façade over 38 admin ops bolted onto a genuine
session-lifecycle service.* A collapse must **preserve the 42 stateful methods**.
Params: exactly **72**, not ~75. → **[T-43](T-43-collapse-control-plane-interfaces.md)**

### C8 — CF-6: `fastapi_app.py` already has 19 APIRouters

The task is not "introduce routers". **All 19 routers and all 100 routes are declared inside a
single function, `create_gateway_app` (`:441-3059`) — 2,619 lines, 86% of the module.** The
work is *lifting existing routers out of a closure*, which means replacing closure capture with
explicit dependency injection. → **[T-47](T-47-lift-routers-out-of-closure.md)**

### C9 — CF-6: `boot_agent`'s step numbering lies about execution order

**Step 5.5 (`:3379`) is physically located after step 8b (`:3111`).** Two comments are scar
tissue from prior reorderings. A staged-builder decomposition must encode the **real**
dependency graph, not the numbering. → **[T-44](T-44-boot-agent-staged-builders.md)**

### C10 — CF-6: ten constructor stashes, not four

The review's `:3467-3496` range misses two, 160 lines further down: `_schedule_runner` (`:3656`)
and `_scheduler` (`:3657`). Both are consumed by `shutdown()` — **omitting them leaves a
resource leak.** Also `:3467` is inside an `if`, so `_max_daily_cost_usd` may be absent and
needs a default. → **[T-45](T-45-boot-agent-constructor-stashes.md)**

### C11 — CF-6: 20 read-model methods, and the store cannot absorb them all

`AgentSession` is `:507-1954` with **20** read-model methods (16 `snapshot_*` + 4 `query_*`),
not ~25. `RuntimeReadModelStore` already exists (`core/runtime_read_models.py:220-450`) — but
**only ~6 of the 20 are already delegations into it.** The other ~14 compute live from
subsystems and have no home in a purely event-derived store. A facade must wrap both.
→ **[T-46](T-46-session-read-models-facade.md)**

### C12 — CF-13: three `PlatformDirs` sites, not two

The review misses `cli/commands/jobs.py:25`, which duplicates `jobs/queue.py:579` inline
rather than calling `_default_db_path()`. **A partial fix splits the jobs DB in two.**
→ **[T-53](T-53-jobs-db-path-unification.md)**

### C13 — CF-14: the install command, and three prompts not two

The bypass command is **`hachi skill pack install user/repo`**, not `hachi skill install`.
Both installers write into the **same** directory — one behind a consent sheet and
`typer.confirm`, one with no manifest parse, no hash check, and no prompt.

Separately (CF-12) there are **three** extraction prompts, not two — and the **default typed
path has no substantive-fact gate at all**.

Loop outcome prefixes: **nine sites, five distinct prefixes**, not eight. Changing them breaks
the eval baseline (`core/eval/corpus.py:418-421`).

### C14 — CF-17: measured mypy numbers

**471 errors in 66 files** (not ~483/64), and the blocking gate covers **40 files, not 48** —
17% of 236. → **[T-69](T-69-mypy-burndown-ratchet.md)**

### C15 — CF-18: sequential-only is enforced by omission

`preflight.py:133` passes no `-p no:xdist` and no `-n 0`, while `pyproject.toml:151-152`
actively documents `-n auto` and **`--dist=loadfile` is already in `addopts`** (`:153`). The
config invites exactly what the docstring forbids — add a hard guard, don't just convert the
clocks. Files: **308** test files (the 309th is `conftest.py`), 55 batch-named.
→ **[T-71](T-71-injected-clocks-restore-parallelism.md)**

### C16 — CF-5: the generated schema is mostly untyped, which explains why nobody imports it

The review frames the OpenAPI schema as generated-and-ignored, implying the fix is to start
importing it. Verification found a prior cause: **only 9 of ~100 operations declare a typed
200 response.** `GET /og/graph` — the smallest domain and the natural pilot — has no
`response_model` at all, so it generates `"application/json": unknown` at `schema.d.ts:5166`.

So "import the generated types" is not directly possible for most domains. The real chain is
**add `response_model` on the backend → regenerate → import**, and the pilot's value is
partly in *discovering* how much of the surface is untyped.

This also reframes CF-5's severity: the CI job doesn't merely gate a file nobody reads — it
gates a file that is largely `unknown` even where it is read. → **[T-38](T-38-openapi-pilot-og-domain.md)**

Related enrichments: `_error_response` has **21 in-route returns** beyond the 7 exception
handlers (28 emissions total), and `frontend/src/lib/data/client.ts:104-121` **already
silently degrades to a generic message** when it receives Starlette's `{"detail": ...}` — a
concrete user-visible consequence of the envelope split. → **[T-37](T-37-error-envelope-in-openapi.md)**

### C17 — Two landmines in the Wave-2 decomposition

Neither is a defect today; both are ways the refactor could ship something much worse than
what it replaces.

**`_require_auth` is closure-captured.** `gateway/fastapi_app.py:556` defines the auth
dependency *inside* `create_gateway_app`, alongside the 19 routers.
[T-47](T-47-lift-routers-out-of-closure.md) lifts those routers to module scope — and a naive
lift that drops the capture yields routers with **no authentication at all**. This is a
latent total auth bypass, not a subtle regression. T-47 gates the move behind an
OpenAPI-invariant test that runs on every commit; do not skip it.

**The patch-by-name hazard is ~10× bigger than first recorded.** Tests that
`monkeypatch.setattr("hachi.cli.main.<symbol>", ...)` number **~200 sites across 20 test
files**, not ~20 in one. After [T-41](T-41-extract-in-process-runtime.md) moves the class,
those patches bind a name nothing calls any more — so they **silently pass while testing
nothing**. A green suite after the extraction is therefore *not* evidence the extraction was
safe. Every patch target must be re-pointed and the specs say so.

### C18 — Two of the review's *strengths* are overstated

The review's Strengths section was not part of the original verification brief, but authoring
turned up two claims that do not hold. Both matter because tasks were scoped assuming they did.

**"Well-built infrastructure internals … excellent SQLite discipline (WAL, atomic writes, CAS
job claims)."** Real, but **only in some stores.** `core/files/store.py` is connect-per-call
with **no WAL** — so it is a poor exemplar to copy. [T-75](T-75-durable-event-log.md) prescribes
copying `RunStateStore` (`core/runtime/store.py`) instead. If you are adding a store, check
which one you are imitating.

**"`sdk/` is a ready-made public API surface … a semver'd facade that is honest about
internals."** The facade is **one 113-line file with 12 symbols**, and **three of its four
docstring promises are false**: there is no `sdk` extra, there is no `py.typed` anywhere in the
repo, and `SDK_VERSION` is not linked to anything. Its contract test is one-directional despite
its own docstring claiming otherwise.

That is the CF-1 pattern — *documented capability that does not exist* — appearing inside a
module the review cited as a strength. Worth noting as evidence the silent-degradation habit is
cultural rather than localised. → **[T-76](T-76-bless-sdk-public-surface.md)**

### C19 — The eval gate cannot catch prompt regressions

`ScriptedLLMClient.generate` **discards `**kwargs`**, so prompt content never reaches an
assertion. The eval corpus is a loop-mechanics suite, not a prompt-quality suite. Anyone
touching prompt wording ([T-77](T-77-consolidate-prompts-into-composer.md)) must not assume
`hachi eval run` protects them — it does not. This is the same reason
[T-13](T-13-feature-liveness-smoke.md) is specced as a dedicated pytest suite rather than
extra eval cases.

### C20 — The frontend has no ESLint at all

The review's CF-16 recommends adding `import/no-cycle`. There is **no ESLint in the frontend**
— no config file, no `eslint` dependency, no lint script, and no preflight step. So that
recommendation is not a one-hour fix; it is a **two-dependency decision** under
[CLAUDE.md](../../../../CLAUDE.md) Rule 3 ("don't add a dependency without asking").

[T-64](T-64-frontend-fix-false-cycle-comment.md) recommends a zero-dependency vitest
module-graph assertion instead, and documents a **second** cycle via `approvals.ts` that the
review did not mention.

### C21 — The sdist ships 9,975 agent-worktree files (packaging bug, confirmed)

The review notes a stale 31 MB `dist/` and treats it as clutter. The real finding is *why* it
is that large. Verified by listing the archive:

```
$ tar -tzf dist/hachi_og-0.1.0.tar.gz | grep -c "\.claude/worktrees"
9975
$ tar -tzf dist/hachi_og-0.1.0.tar.gz | grep "\.claude/worktrees" | head -1
hachi_og-0.1.0/.claude/worktrees/agent-a103ee9da4e544263/.dockerignore
```

**97% of the sdist is `.claude/worktrees/`** — scratch copies of the repo left behind by agent
sessions. That is the whole explanation for the 45× sdist-to-wheel ratio, and it means anyone
installing from sdist downloads 32 MB of agent scratch.

**No secrets leaked** — the same listing returns **0** matches for `.venv/` or `.env`. So this
is a size-and-hygiene bug, not a disclosure incident. But it will recur on the next publish
unless the packaging config excludes the directory. → **[T-74](T-74-repo-hygiene-sweep.md)**

### C22 — mypy coverage can go 17% → 44% with zero code changes

The review frames the mypy gap as a burn-down grind. Verification found most of the work is
already done and simply never claimed: **65 engine-layer files are already strict-clean and
have never been added to the gate.** A probe with a 105-file gate returns
`Success: no issues found in 105 source files`.

So the first move on [T-69](T-69-mypy-burndown-ratchet.md) is not fixing type errors — it is
**adding the already-clean files**, which more than doubles enforced coverage (40 → 105 files,
17% → 44%) without touching a line of source. Do that before grinding on the remaining 66.

### C23 — Smaller corrections

| Review says | Actually |
|---|---|
| CF-3: malformed config logs "a log-line warning" | `logger.error` on the primary path (`config_loader.py:130`); `HACHI_CONFIG_STRICT=1` re-raises |
| CF-3: ten `= null` lines | **11 live** + 1 already-commented (line 47) |
| CF-4(c)(e): `frontend/src/lib/store.ts` | path is `frontend/src/lib/store/store.ts` |
| CF-4(e): mock forks at `store.ts:1155-1586` | **13 actions**, range `1205-1772` |
| CF-4(d): channels call site `runner.py:14` | `:14` is the import; call is `:20`/`:29`. Schedules have a **second** site at `schedule.py:205` |
| CF-4(d): "parks an approval no surface can reach" | No approval is created at all — see N1 |
| CF-1#2: `routing/validate.py` is the only caller | `gateway/orchestrator.py:2952` calls it **correctly**; only the validate/apply path is dead |
| CF-1#5: "the UI's Memory-Diff surface" | There is no UI surface — `snapshot_gardener_diffs` has **zero callers** |
| CF-1#10: `max_tokens` not forwarded | Only bites when `[routing]` is active; the finding is that **enabling routing silently weakens a guardrail** |
| CF-5: "~30 HTTPException sites" | **46**. Root cause is mechanical: **zero** routes declare `responses=` |
| CF-5: "55+ interfaces across 14 files" | **61** across **16** non-test files. Best pilot: `og.ts` (78 L, 2 interfaces) |
| CF-12: `user_profile.py:422-480` | range is **422-498** |
| CF-15: owner map "lost on restart" | Also: `set_session_owner` is a **silent no-op** for non-live sessions, and `None` owner means **allow** — so after restart every session is ownerless and open |
| CF-16: ~95 fields / ~85 actions | **75 fields / 99 actions**; `hydrate` **is** typed — the defect is unvalidated bulk-set |
| CF-20: `dist/` 31 MB | **32.3 MB** sdist + a 718 KB wheel; the **45× sdist:wheel ratio suggests a packaging bug** worth its own look |
| CF-20: extras duplicate base deps | True and exact (character-for-character no-ops) — but "base ships every edge" is overstated; **2 of 10 edges leak** |

---

## Four tests will legitimately fail under a correct fix

All are contract corrections, not test-weakening. [CLAUDE.md](../../../../CLAUDE.md) Rule 2
forbids weakening a test to go green; it does not forbid correcting one that asserts wrong
behaviour. **Say so explicitly in the commit message** — otherwise the next reader cannot tell
your change from a cheat.

1. `tests/test_gateway_config_mutations.py:309-317` asserts the *same object* handed to
   `write_global_config` is what gets persisted — it **encodes the merged-write bug as the
   contract**. → [T-03](T-03-config-writers-file-layer-only.md)
2. `tests/test_runtime_read_models.py:170-226` ("B4 trim-underflow contract") asserts the
   **silent** cursor clamp is correct. Adding a gap signal means amending it.
   → [T-30](T-30-sse-gap-signal.md)
3. `tests/test_security_hardening.py:54` **actively asserts** `"schedule_task" in
   BLOCKED_TOOL_NAMES` — i.e. it pins the phantom entry that makes the sub-agent blocklist
   fail open. → [T-34](T-34-subagent-schedule-tool-blocklist.md)
4. `tests/test_gateway_auth_default.py:406` currently passes *because* the approvals route
   mutates the same list object the test asserts against.
   → [T-15](T-15-approvals-through-control-plane.md)

**And one hazard that is worse than a failing test.** ~200 sites across 20 test files
`monkeypatch.setattr("hachi.cli.main.<symbol>", ...)` **by name**. After
[T-41](T-41-extract-in-process-runtime.md) moves the class, those patches bind a name nothing
calls — so they **silently pass while testing nothing**. A green suite after the extraction is
*not* evidence the extraction was safe.
