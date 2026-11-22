# T-77 · Consolidate the stray prompt sites into a prompt registry

|  |  |
|---|---|
| **Source finding** | Missed Opportunity #6 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) — **optional leverage, not gate-blocking. See §2.** |
| **Depends on** | none — but **serialize against [T-51](T-51-memory-delete-tri-store.md)**; both edit `core/memory.py` (§12) |
| **Blocks** | nothing |
| **Effort** | ~4 days |
| **Difficulty** | High — the moves are mechanical, but §3.4's differing quality gates mean a careless consolidation silently changes what gets written to memory, and §3.5 means the gate will not catch it |
| **Files you will touch** | `src/hachi/core/prompt_composer.py`, `src/hachi/core/memory.py`, `src/hachi/core/session_titler.py`, `src/hachi/tools/memory_tools.py`, `src/hachi/tools/vision_tools.py`, `src/hachi/cli/main.py`, `tests/test_prompt_composer.py`, `tests/test_prompt_registry.py` *(new)* |

---

## 1. Brief

`src/hachi/core/prompt_composer.py` declares in its own docstring that *"no other module should
concatenate system-prompt strings directly."* That invariant is violated **26 times across 8 files**.
Eight auxiliary LLM call sites build their prompts inline; nine more model-facing fragments are
assembled outside the composer entirely. When you are done, the prompt-bearing call sites draw their
text from a named, versioned registry, so a prompt can be snapshot-tested and diffed rather than
grepped for.

**This is not a bug fix.** Every prompt works. The gap is that prompt text — the thing that most
determines model behaviour — is the only major input in this codebase with no single owner, no
version, and no test. §4 shows you the evidence; there is no failure to reproduce.

## 2. Why this matters

**The argument is entirely about timing, and it is the reason to do this at all.** The review:
*"`prompt_composer` is 80% of a prompt registry. Consolidating the ~8 stray prompt sites into it makes
prompts testable/versionable — **cheap now, expensive after prompt-injection hardening starts
depending on exact wording**."*

That is the whole case. Today a prompt is a string literal you can move freely, because nothing
depends on its exact bytes. The moment prompt-injection hardening ships — delimiter conventions,
untrusted-content fencing, instruction-hierarchy markers — every one of these 26 literals acquires
security-relevant wording, and moving them stops being a refactor and becomes a security review. The
repo already has untrusted-content guards (the review credits them as *"above typical for pre-v1"*),
so this is a near-term direction, not a hypothetical.

The secondary payoff is ordinary but real: eight prompts spread across `core/`, `tools/`, and `cli/`
cannot be reviewed together, so they have drifted. Three fact-extraction prompts in one file give the
model three different definitions of what a "fact" is (§3.4), and nothing surfaces that.

**Read this too: this task is optional leverage and it is not gate-blocking.** It comes from the
review's *Missed Opportunities*, not the release gate. **Do not start it while Wave 1 is open.**
Nothing in Wave 1 depends on it, and it touches `core/memory.py` — a file several Wave 1 and Wave 2
memory tasks also edit.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 What `prompt_composer` is today — and what it is not

`src/hachi/core/prompt_composer.py`, **134 lines**, three functions, no classes:

| `path:line` | Symbol |
|---|---|
| `:12` | `_build_time_header() -> str` (private) |
| `:27` | `build_stable_base(brain_text, skill_count=0, integration_count=0, permission_block="", capability_block="", tool_groups=None) -> str` |
| `:98` | `compose(stable_base, user_profile_snapshot=None, agent_profile_snapshot=None, recalled_context=None) -> tuple[str, str]` |

The module docstring, `:1-5` — **this is the invariant the task enforces, and it is already written
down**:

```python
"""PromptComposer — single location for all system-prompt assembly.

All prompt ingredients flow through compose() / build_stable_base(); no other
module should concatenate system-prompt strings directly.
"""
```

**What it already does well:**

- **Ordered sections.** `build_stable_base` appends in a fixed order (`:50-95`): `brain_text` → skills
  block (`:52`) → integrations block (`:66`) → `permission_block` (`:75`) → capabilities block (`:78`)
  → tool-groups block (`:85`). Each is conditional on a non-empty input.
- **Cache-aware splitting.** `compose` returns `(cacheable, dynamic)` so volatile content sits after
  the provider cache breakpoint — `:116` (`# Cacheable prefix: stable across the session.`) and
  `:128-129` (`# Dynamic tail: changes every turn — must sit AFTER the cache breakpoint.`).
- **Purity.** Both functions are stateless and side-effect-free — trivially testable, which is why
  `tests/test_prompt_composer.py` gets 15 tests out of 105 lines.

**What it is not — read this before planning:**

- **No registry.** There is no way to ask it for "the fact-extraction prompt". It has no named
  templates, no lookup, no catalogue. It assembles *system-prompt sections for the main agent loop*
  from **pre-rendered strings the caller supplies**.
- **No versioning.** No `VERSION`, no template ids, no hashes. Nothing to pin a prompt revision to.
- **Ordering is implicit in statement order.** There is no priority field or ordering key — section
  order is the order of the `parts.append(...)` calls.

So the review's *"80% of a prompt registry"* is fair about the shape and optimistic about the fit: the
eight stray sites are **task prompts for auxiliary one-shot LLM calls**, not system-prompt sections.
**Consolidating them requires extending `prompt_composer` with a template registry — it cannot absorb
them as-is.** Plan for that (§5), or you will spend day one discovering it.

**Exactly two call sites** in all of `src/hachi/`:

| Import | Call |
|---|---|
| `src/hachi/gateway/orchestrator.py:53` | `src/hachi/gateway/orchestrator.py:3380` |
| `src/hachi/core/turn_context.py:18` | `src/hachi/core/turn_context.py:106` |

`orchestrator.py:3379` states the intent: `# 5.5 Assemble the stable base system prompt via PromptComposer (single call site).`

**Tests:** `tests/test_prompt_composer.py` (105 lines, **15** tests) and
`tests/test_prompt_cache_ordering.py` (**3** tests). All are substring-shape assertions
(is-X-in-cacheable / is-Y-in-dynamic). **None asserts prompt content or quality.**

### 3.2 The full enumeration — 8 call sites, 26 literals

The review says "~8" and does not enumerate. Both are right, at different granularities: there are
**8 prompt-bearing auxiliary LLM call sites**, carrying **17 distinct prompt literals** between them
(most sites have both a user-message prompt and a `system_prompt`), plus **9 more model-facing
fragments** assembled outside the composer. **26 literals across 8 files.**

Verified by combining five searches: `*_PROMPT`/`SYSTEM_*`-shaped constants; `"You are …"`;
`Output only|Return ONLY|pure JSON|Your task`; `role="system"|role="user"|system_prompt=|messages=[`;
and every `.generate(` / `messages.create(` call. The `.generate(` sweep is the closure — **every LLM
invocation in `src/hachi/` is accounted for below**, with transport plumbing (`core/llm.py:199,385`,
`core/resilience.py:407,453`, `core/eval/replay.py:106`) excluded as carrying no prompt text.

#### Tier A — the 8 call sites (17 literals). These are the task.

| # | Prompt literal | LLM call | Enclosing symbol | Purpose | Opening text |
|---|---|---|---|---|---|
| 1 | `core/memory.py:237` | — | `_EXTRACT_TOOL` (module const) | Extraction tool-schema description (model-facing) | `"Extract durable memory nodes from a conversation exchange. "` |
| 2 | `core/memory.py:311` | `core/memory.py:310` | `extract_facts` (typed path) | Fact extraction — user msg | `content=f"Extract memory from:\n\n{snippet}"` |
| 3 | `core/memory.py:312-317` | ″ | ″ | Fact extraction — system | `"You are a precision memory extraction engine. "` |
| 4 | `core/memory.py:370-386` | `core/memory.py:388` | `extract_facts` (flat path) | Fact extraction — user msg | `"Extract ONLY permanent facts from this exchange into three buckets.\n\n"` |
| 5 | `core/memory.py:390` | ″ | ″ | Fact extraction — system | `system_prompt="You are a fact extraction engine. Output pure JSON only."` |
| 6 | `core/memory.py:1461-1470` | `core/memory.py:1472` | `MemoryManager._flush_facts_to_vault` | Fact extraction on compaction | `"Extract any permanent, atomic facts from this conversation snippet into a "` |
| 7 | `core/memory.py:1474` | ″ | ″ | — system | `system_prompt="You are an elite data extraction agent. Output pure JSON only."` |
| 8 | `core/memory.py:1531-1542` | `core/memory.py:1550` | `MemoryManager._generate_structured_summary` | Compaction summary | `"Summarize this dropped conversation segment into a structured checkpoint.\n"` |
| 9 | `core/memory.py:1552-1556` | ″ | ″ | — system | `"You are a context summarization agent. "` |
| 10 | `core/session_titler.py:28-34` | `core/session_titler.py:112` | `_TITLE_SYSTEM_PROMPT` (module const) | Session titling — system | `"You write a short, specific title for a conversation between a user and an AI "` |
| 11 | `core/session_titler.py:105-109` | ″ | `generate_title` | Session titling — user msg | `prompt = f"User: {user_message[:600]}"` … `prompt += "\n\nTitle:"` |
| 12 | `tools/memory_tools.py:121-135` | `tools/memory_tools.py:137` | `save_memory` → `_smart_upsert` | Memory consolidation / dedup | `"You are a memory consolidation engine.\n"` |
| 13 | `tools/memory_tools.py:139` | ″ | ″ | — system | `system_prompt="You are a data merger. Output pure JSON only."` |
| 14 | `tools/vision_tools.py:359` | `tools/vision_tools.py:409` | `view_image` | Vision — default focus text | `focus = prompt.strip() or "Describe what you see and use it to answer the user's request."` |
| 15 | `tools/vision_tools.py:405-408` | ″ | ″ | Vision — system | `"You are a vision analysis assistant. "` |
| 16 | `cli/main.py:1206-1212` | `cli/main.py:1221` | `.og` authoring patch generator | Authoring — system | `"You are a precise code editor for Hachi .og skill files. "` |
| 17 | `cli/main.py:1213-1219` | ″ | ″ | Authoring — user msg | `f"File: {name}\n\n"` … `f"Requested change: {prompt}\n\n"` |

**Note site 10.** `_TITLE_SYSTEM_PROMPT` at `session_titler.py:28` is the **only module-level named
prompt constant in the repo**. It is already in the shape a registry wants — start there to prove the
pattern, then do the rest.

#### Tier B — 9 model-facing fragments assembled outside the composer

Lower priority; several are deliberately out of scope (§9).

| # | `path:line` | Enclosing symbol | What it is |
|---|---|---|---|
| 18 | `core/sub_agent.py:236-288` | `class PromptBuilder` | **A second, parallel prompt composer** — see §3.3 |
| 19 | `core/sub_agent.py:283` | `PromptBuilder.build` | `sections.append(f"--- Available Capabilities ---\n{index_map}")` |
| 20 | `core/sub_agent.py:318` | `PromptBuilder._extract_identity` | `parts.append(f"You are a specialized sub-agent: {og_file.meta.title}")` |
| 21 | `core/sub_agent.py:341` | `PromptBuilder._extract_warnings` | `return "--- CRITICAL CONSTRAINTS ---\n" + "\n".join(warnings)` |
| 22 | `core/sub_agent.py:391-408` | `PromptBuilder._build_task_section` | `"--- YOUR ASSIGNED TASK ---"` … `"\n--- OUTPUT REQUIREMENTS ---\n"` |
| 23 | `core/loop.py:554-561` | `ExecutionLoop._build_system_prompt` | Fallback concat that bypasses the composer: `return f"{self.base_system_prompt}\n\n{context_header}"` |
| 24 | `core/memory.py:883-887` | `MemoryManager.get_context_header` | `lines = ["--- Previously Completed Tasks This Session ---"]` |
| 25 | `core/memory.py:440` | `_CLEARED_TOOL_RESULT` (module const) | `"[tool result cleared to reclaim context — re-run the tool if you need this output again]"` |
| 26 | `core/memory.py:1423` | `MemoryManager._apply_summary_to_history` | `"[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]\n{summary}"` |

**Concentration: `core/memory.py` holds 11 of the 26.**

Deliberately **not** counted: `gateway/workspace.py:120-125` writes a fallback `brain.og` to disk
(`"You are Hachi, an elite autonomous agent.\n"`) — that is bootstrap file content, not a call site,
though it does become `brain_text` fed into `build_stable_base`. The `.og` files under
`src/hachi/default_skills/` and `src/hachi/packs/` are data-driven skill definitions loaded by the
og_engine — conceptually prompts, but not stray Python literals, and firmly out of scope (§9).

### 3.3 `sub_agent.PromptBuilder` is a second composer, not a stray literal

`src/hachi/core/sub_agent.py:236-249`:

```python
class PromptBuilder:
    """Constructs a layered system prompt from an OGFile's rich tags.

    The prompt is assembled from 5 distinct layers, each sourced from specific
    ObjectGraph tags. This ensures the sub-agent receives a perfectly curated,
    minimal prompt — no bloat, no ambiguity.

    Layer Architecture:
        Layer 1 — Identity:     WHO the sub-agent is (from ::dense + ::full of persona nodes)
        Layer 2 — Warnings:     Critical constraints (from ::warning blocks — ALWAYS included)
        Layer 3 — Instructions: HOW to behave (from ::steps + ::assertion of rule nodes)
        Layer 4 — Index Map:    WHAT exists in the file (from ::index — compact routing table)
        Layer 5 — Task:         WHAT to do (from the delegate_task call — task + context)
    """

    @staticmethod
    def build(og_file: OGFile, task: str, context: str | None = None) -> str:
```

This is a designed, documented, layered composer for sub-agents that reads directly from `.og` tags.
It is a genuine duplicate-concept finding — the repo has two prompt composers. **It is also explicitly
out of scope for this task** (§9): merging two composers with different input models (pre-rendered
strings vs. parsed `OGFile` nodes) is its own multi-day design job, and doing it alongside the memory
work in §3.4 gives you one change with two independent ways to silently alter model behaviour.

### 3.4 HAZARD 1 — the memory prompts have DIFFERENT quality gates, and one has none

**This is the most dangerous part of the task. Read it twice.**

`core/memory.py` contains **four** LLM prompts, not three. All four are extraction-or-summarization
prompts that look interchangeable. **They are not: each applies a different gate to the model's
response, and consolidating them without preserving each gate silently changes what gets written to
memory.**

The gate itself is `_is_substantive_fact`, `core/memory.py:142-164`, with `_MIN_FACT_LENGTH = 12` at
`:117` and a 17-entry `_TRIVIAL_FACT_PATTERNS` frozenset at `:119-139`:

```python
    stripped = fact.strip()
    if len(stripped) < _MIN_FACT_LENGTH:
        return False
    if stripped.lower() in _TRIVIAL_FACT_PATTERNS:
        return False
    return True
```

It is called at exactly four places: `:404`, `:412`, `:420` (the flat path's three buckets) and
`:1483` (`_flush_facts_to_vault`). **Not** in the typed path.

| Prompt | Call | Gate applied to the response |
|---|---|---|
| **1. typed/tool path** — `:312-317`, in `extract_facts` (branch at `:231`) | `:310` | **Schema-shape only.** Role whitelist with silent fallback (`:335-336`), slugified name (`:337`), 200-char truncation of `dense` (`:342`), empty-list early return (`:328-330`), plus name-keyed upsert dedup downstream. **`_is_substantive_fact` is NEVER called.** A 3-character `dense` value goes straight to `write_nodes` at `:351` |
| **2. flat path** — `:370-390`, same function (branch at `:368`) | `:388` | **Strongest.** Fence-strip + JSON parse (`:394-400`), then `_is_substantive_fact` on **all three** buckets (`:404`, `:412`, `:420`) |
| **3. `_flush_facts_to_vault`** — `:1461-1474` | `:1472` | **Yes** — `_is_substantive_fact` at `:1483`. Slightly weaker fence-strip than #2: `:1478-1479` handles only ` ```json `, not bare ` ``` `, so a bare-fenced response raises `JSONDecodeError` (by design — the docstring at `:1443-1444` routes it to the JobWorker failure pipeline) |
| **4. `_generate_structured_summary`** — `:1531-1556` | `:1550` | **NONE.** `:1558` is `return response.content.strip()`. The prompt demands five specific `##` headings and **nothing verifies a single one is present** — no length check, no schema check, no non-empty check. The only `except` (`:1559-1561`) catches transport failures, not bad content. The result is written verbatim into live conversation history via `_apply_summary_to_history` (`:1410`, assignment at `:1430`) |

**Two answers to "which has no quality gate", because the honest answer depends on the question:**

- **Of the three the review named:** the **typed/tool path (`:310-319`)** — it validates *shape* but
  never *substance*.
- **Of all four:** **`_generate_structured_summary` (`:1531-1557`)** has literally zero post-response
  validation of any kind.

Also verified: **there is no confidence threshold anywhere** in any of the four paths — the extraction
tool schema at `:242-307` has no confidence field at all.

**What this means for you:** if you route all four through one registry entry, or "harmonise" them
into one prompt, you have changed memory-write behaviour in a way no test will catch (§3.5). Prompts 1
and 2 are *branches of the same function* (`extract_facts` at `:182`, `if memory_writer is not None:`
at `:231` / `else:` at `:368`) and are the most tempting to merge. **Do not.** Consolidate the *text*
into named registry entries; leave every gate exactly where it is (§5.3).

Cross-link: [T-51](T-51-memory-delete-tri-store.md) also edits `core/memory.py`, as do other Wave 2
memory tasks (T-48, T-50, T-52). **Serialize** — see §12.

### 3.5 HAZARD 2 — the eval corpus will NOT catch a prompt-quality regression

`scripts/preflight.py:117` runs the eval suite as a gate step:

```python
    Step("eval regression", [["uv", "run", "hachi", "eval", "run"]]),
```

**Do not assume this protects you. It cannot.** `src/hachi/core/eval/corpus.py` (427 lines, **14**
`ReplayCase` entries) says so itself at `:5-10`:

```python
This corpus is a **loop-mechanics regression suite** — it protects the ReAct loop's
control flow (tool dispatch, multi-step sequencing, error handling, iteration cap,
output assembly) against refactors.  It does NOT test model decision quality: the LLM
transport is entirely scripted (``ScriptedLLMClient``), so pass/fail reflects whether
the production ``ExecutionLoop`` behaves correctly given a fixed sequence of responses —
not whether the model makes good decisions.
```

The mechanism, `src/hachi/core/eval/replay.py:97-102`:

```python
    def generate(self, **kwargs: Any) -> LLMResponse:
        """Return the next scripted response (repeats the last when exhausted)."""
        idx = min(self.calls, len(self._responses) - 1)
        resp = self._responses[idx]
        self.calls += 1
        return resp
```

**It takes `**kwargs` and discards them.** `system_prompt` and `messages` are never read. It is wired
into a *real* `ExecutionLoop` at `replay.py:201-210` with a placeholder
`base_system_prompt="eval-replay"`.

The full assertion vocabulary (imported at `corpus.py:41-49`) is `no_error`, `output_contains`,
`output_not_contains`, `tool_call_count`, `tool_called`, `tool_called_in_order`. Every
`output_contains` matches a string the case itself scripted — e.g. `corpus.py:184` scripts
`LLMResponse(content="The capital of France is Paris.")` and `:181` asserts `output_contains("Paris")`.
That verifies the loop does not mangle text; it says nothing about prompt quality.

**State this plainly to yourself before you start: nothing in the eval corpus would fail if every one
of the 26 prompts were replaced with an empty string.** The gate is green either way. Your §7 tests
are the only instrument you have.

## 4. See the opportunity

**There is no failure to reproduce. This is an opportunity, not a defect** — every prompt works today.
Do not manufacture a repro. The evidence is a documented invariant measured against reality.

### 4.1 The module's own contract, versus grep

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
cd D:/OpenGigantic/hachi

# The invariant, in the composer's own words:
sed -n '1,5p' src/hachi/core/prompt_composer.py

# Who actually uses it? (expect: 2 call sites)
grep -rn "build_stable_base\|prompt_composer import\|_compose_prompt(" --include=*.py src/hachi/

# Who builds prompt text without it? (expect: many)
grep -rn "system_prompt=" --include=*.py src/hachi/ | grep -v "prompt_composer\|def \|:param\|Args:"

# Every LLM call site in the codebase:
grep -rn "\.generate(" --include=*.py src/hachi/ | grep -v "def generate"
```

**You will see now:** a docstring asserting *"no other module should concatenate system-prompt strings
directly"*; **2** call sites using the composer; and **14** `.generate(` sites of which **8** carry
inline prompt text the composer has never seen (the other 6 are transport plumbing in `llm.py`,
`resilience.py`, and `eval/replay.py`).

**You should see after the change:** the prompt-bearing call sites resolve their text from named
registry entries, and a grep for inline prompt literals outside the registry returns the Tier B
fragments only (§9 keeps those).

### 4.2 The four memory prompts, side by side

This one is worth doing by eye, because the drift is the point:

```bash
sed -n '312,317p'   src/hachi/core/memory.py   # 1. typed:   "precision memory extraction engine"
sed -n '390p'       src/hachi/core/memory.py   # 2. flat:    "fact extraction engine"
sed -n '1474p'      src/hachi/core/memory.py   # 3. flush:   "elite data extraction agent"
sed -n '1552,1556p' src/hachi/core/memory.py   # 4. summary: "context summarization agent"

# The gate that only SOME of them apply:
grep -n "_is_substantive_fact" src/hachi/core/memory.py
```

**You will see now:** four different personas instructing the model about what a durable fact is,
inside one file, none referencing the others — and `_is_substantive_fact` defined at `:142` but called
at only `:404`, `:412`, `:420`, `:1483`. **The typed path (`:310`) is absent from that list.** Nothing
in the codebase makes that asymmetry visible at review time; you have to grep for it, which is exactly
the cost this task removes.

### 4.3 Prove the gate does not protect prompts

```bash
uv run pytest -q tests/test_prompt_composer.py tests/test_prompt_cache_ordering.py
uv run hachi eval run
```

Both are green. Now consider that `ScriptedLLMClient.generate` (`core/eval/replay.py:97`) never reads
`system_prompt` (§3.5), and that all 18 composer tests assert substring placement rather than content.
**There is no test anywhere that would notice if a prompt's meaning changed.** That is the hole §7
fills.

## 5. What "fixed" looks like

`prompt_composer` gains a **named template registry** alongside its existing assembly functions. The
eight Tier A call sites resolve their text through it. Every prompt becomes greppable by name,
snapshot-testable, and versioned as a set.

### 5.1 The registry shape

Decided here so you do not have to decide. Keep it boring, keep it pure, keep it in the same module —
that module already declares itself the single location for prompt assembly (§3.1).

```python
# src/hachi/core/prompt_composer.py

PROMPT_REGISTRY_VERSION = "1"
"""Bumped whenever any registered template's text changes. Snapshot tests pin
the (version, digest) pair — see tests/test_prompt_registry.py."""


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """A named, versioned prompt template.

    Attributes:
        name:     Stable lookup id, e.g. "memory.extract.typed.system".
        text:     The template body. May contain {placeholders} for .render().
        purpose:  One line, for humans reading the registry.
    """

    name: str
    text: str
    purpose: str

    def render(self, **kwargs: object) -> str:
        """Substitute placeholders. Raises KeyError on a missing key — never silently."""
        return self.text.format(**kwargs)


_TEMPLATES: dict[str, PromptTemplate] = {}


def register_prompt(template: PromptTemplate) -> None:
    """Register *template*. Raises ValueError on a duplicate name."""


def get_prompt(name: str) -> PromptTemplate:
    """Return the registered template. Raises KeyError if unknown — never returns a default."""
```

Three deliberate properties:

- **`get_prompt` raises on an unknown name.** No silent default. A typo must be loud — a
  silently-empty prompt is the CF-1 failure mode wearing a prompt's clothes.
- **`render` raises `KeyError` on a missing placeholder.** `str.format` already does; do not catch it.
- **Frozen dataclass.** Prompts are data, not state.

### 5.2 Naming

Use `<domain>.<operation>.<variant>.<role>`, so the registry sorts into readable groups and the drift
in §4.2 becomes visible at a glance:

```
memory.extract.typed.system          memory.extract.typed.user
memory.extract.flat.system           memory.extract.flat.user
memory.extract.tool_schema.description
memory.flush.system                  memory.flush.user
memory.summarize.system              memory.summarize.user
session.title.system                 session.title.user
memory.consolidate.system            memory.consolidate.user
vision.analyze.system                vision.analyze.default_focus
authoring.patch.system               authoring.patch.user
```

### 5.3 The consolidation rule — TEXT moves, LOGIC does not

**This is the rule that keeps §3.4 from biting you:**

> Move the **string literal** into the registry. Leave **every** parse step, fence-strip, gate call,
> truncation, and dedup exactly where it is, in the same order, in the same function.

Concretely, `extract_facts`'s typed branch becomes:

```python
        response = llm_client.generate(
            messages=[_LLMMessage(
                role="user",
                content=get_prompt("memory.extract.typed.user").render(snippet=snippet),
            )],
            system_prompt=get_prompt("memory.extract.typed.system").text,
            tools=[_EXTRACT_TOOL],
        )
```

and **everything after it — `:328-364`, including the fact that `_is_substantive_fact` is not called —
stays byte-for-byte identical.** You are not fixing the missing gate in this task (§9). You are making
it *visible* that four prompts with four different gates exist.

> **Do not "harmonise" the four memory prompts into one.** They read as near-duplicates and they are
> not: they feed different downstream pipelines with different validation. Register four entries.
> If the drift should be resolved, that is a follow-up with its own testing story.

Similarly, register the text at `session_titler.py:28` **verbatim** — do not improve the wording while
you move it. A move you can diff to zero is reviewable; a move-plus-edit is not.

### 5.4 Which sites are in scope

**In scope: all 17 Tier A literals at the 8 call sites** (§3.2). That is the task.

**Out of scope: all 9 Tier B fragments** (§9). They are structural markers inside larger assembly
routines, not standalone prompts, and `sub_agent.PromptBuilder` is a second composer with a different
input model (§3.3).

Suggested order — prove the mechanism on the easy one first:

1. `session_titler.py` (2 literals) — already a module constant; near-zero risk.
2. `tools/vision_tools.py` (2), `tools/memory_tools.py` (2), `cli/main.py` (2).
3. `core/memory.py` (9 literals, 4 prompts) — **last**, most carefully, one prompt per commit if you
   can.

## 6. Steps

1. Write the failing snapshot test from §7 first, against today's `session_titler` prompt. Watch it
   fail on the missing registry.
2. Add `PromptTemplate`, `_TEMPLATES`, `register_prompt`, `get_prompt`, and
   `PROMPT_REGISTRY_VERSION` to `src/hachi/core/prompt_composer.py` (§5.1). Do not touch
   `build_stable_base` or `compose`.
3. Move `_TITLE_SYSTEM_PROMPT` (`core/session_titler.py:28-34`) and the user prompt (`:105-109`) into
   the registry verbatim. Confirm the existing titler tests still pass unchanged.
4. Repeat for `tools/vision_tools.py:359,405-408`, `tools/memory_tools.py:121-135,139`, and
   `cli/main.py:1206-1219`.
5. `core/memory.py`, one prompt at a time, in this order: `_generate_structured_summary`
   (`:1531-1556`) → `_flush_facts_to_vault` (`:1461-1474`) → flat path (`:370-390`) → typed path
   (`:311-317`) → `_EXTRACT_TOOL` description (`:237`). **After each, run the memory tests and diff
   the rendered prompt against the original string** (§7b).
6. Add the registry-completeness test (§7c).
7. Update `prompt_composer`'s module docstring: it now owns named templates as well as assembly, and
   Tier B fragments are a known, listed exception. **The docstring currently asserts an invariant the
   codebase violates — do not leave it overclaiming after this task either.**
8. Run the gate (§10), and re-read §3.5 before believing it.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

**The right instrument here is a prompt-snapshot test**, because the failure mode this task risks is
"the text changed and nothing noticed" — §3.5 proves the eval gate is blind to it, and the 18 existing
composer tests only assert substring placement. A snapshot test pins the exact bytes of each
registered prompt so any future edit is a visible, intentional diff in the test file.

**It is not a behavioural regression test, and you should not pretend it is.** No behaviour is wrong
today. Say so in the commit message.

### 7a. The snapshot lock (the primary test)

- **File:** `tests/test_prompt_registry.py` (new)
- **Test name:** `test_registered_prompts_match_snapshot`
- **It must assert:** every registered template's `.text` matches a checked-in digest, so editing a
  prompt fails until the snapshot is updated deliberately.
- **It must FAIL before your fix** with `ModuleNotFoundError`/`ImportError: cannot import name
  'get_prompt' from 'hachi.core.prompt_composer'`.

```python
# sketch — adapt to the repo's existing fixtures
import hashlib

from hachi.core.prompt_composer import PROMPT_REGISTRY_VERSION, all_prompts


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# Snapshot as of PROMPT_REGISTRY_VERSION "1".
# Changing a prompt REQUIRES updating this map and bumping the version in the
# same commit. Prompt wording changes model behaviour — make it a visible diff.
_SNAPSHOT: dict[str, str] = {
    "session.title.system": "<fill in from the failing output>",
    # ... one entry per registered template
}


def test_registered_prompts_match_snapshot() -> None:
    """T-77: a prompt cannot change without a deliberate snapshot update."""
    assert PROMPT_REGISTRY_VERSION == "1"

    live = {name: _digest(t.text) for name, t in all_prompts().items()}
    assert live == _SNAPSHOT, (
        "A registered prompt changed. If intentional: update _SNAPSHOT and bump "
        "PROMPT_REGISTRY_VERSION. If not: revert. Prompt text is model behaviour."
    )
```

### 7b. The move-is-lossless check (do this per site, while moving)

This is the test that actually protects the consolidation. For each site you move, assert the
registry's rendered output equals the **original literal**, pasted verbatim into the test:

- **Test name:** `test_<site>_prompt_text_unchanged_by_move`
- **It must assert:** `get_prompt("session.title.system").text == "<the exact original string>"`.
- **It must FAIL before the move** with `KeyError` (the name is not registered yet).

Write one per Tier A prompt. They are tedious and they are the entire safety net: they turn "I moved a
string" from a claim into a check. **For the four `core/memory.py` prompts these are mandatory**, not
optional — §3.4 is why.

### 7c. The completeness lock

- **Test name:** `test_no_inline_system_prompt_literals_at_migrated_sites`
- **It must assert:** the migrated modules no longer contain inline prompt literals — e.g. read
  `core/session_titler.py` as text and assert `"You write a short, specific title"` does not appear.
  Crude, and effective: it fails if someone reintroduces an inline prompt at a migrated site.
- **It must FAIL before your fix**, since the literal is there today.

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Note the asymmetry: 7a and 7c fail naturally before the change; 7b fails with `KeyError`. If any of
> them is green before you start, you have written it wrong.

## 8. Acceptance criteria

- [ ] The regression test from §7a exists, and failed before the change with an import error.
- [ ] A `test_..._prompt_text_unchanged_by_move` test exists for **each** of the 17 Tier A literals,
      pinning the moved text to the original byte-for-byte.
- [ ] All 8 Tier A call sites (§3.2) resolve their prompt text via `get_prompt(...)`.
- [ ] **Every quality gate is exactly where it was.** Specifically: `_is_substantive_fact` is still
      called at 4 sites and still **not** called on the typed path; `_generate_structured_summary`
      still returns unvalidated content. Verify by diff, and say in the commit message that you
      checked.
- [ ] The four `core/memory.py` prompts remain **four** registry entries. None was merged, and none
      was reworded.
- [ ] `get_prompt` raises `KeyError` on an unknown name; `render` raises on a missing placeholder.
      Neither has a silent default.
- [ ] `PROMPT_REGISTRY_VERSION` exists and the snapshot test pins it.
- [ ] `prompt_composer`'s module docstring is updated and no longer asserts an invariant the codebase
      violates.
- [ ] The 18 existing tests in `tests/test_prompt_composer.py` and
      `tests/test_prompt_cache_ordering.py` pass **unchanged** — `build_stable_base` and `compose`
      were not modified.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts) — **and you state
      in your report that green does not imply prompt quality was preserved (§3.5)**; the §7b tests
      are what does.

## 9. Out of scope — do NOT

- **Do not start this while Wave 1 is open.** This is optional leverage from the review's *Missed
  Opportunities*, not a release-gate item. If Wave 1 is unfinished, close this file. This is the
  primary boundary on the task.
- **Do not fix the missing quality gate on the typed extraction path** (§3.4). Adding
  `_is_substantive_fact` there changes what gets written to memory — a real behaviour change needing
  its own regression test and its own review. Record it; leave it. Same for
  `_generate_structured_summary`'s total absence of validation.
- **Do not merge or reword the four `core/memory.py` prompts.** They look like duplicates and feed
  different pipelines with different gates. Four entries, verbatim.
- **Do not consolidate `sub_agent.PromptBuilder`** (§3.3, Tier B #18-22). It is a second composer with
  a different input model (`OGFile` tags, not strings). Merging the two composers is a separate design
  task — and doing it here means one change with two independent ways to alter model behaviour
  silently.
- **Do not touch `build_stable_base` or `compose`.** You are adding a registry beside them, not
  refactoring them. Their 18 tests must pass unchanged; that is your proof you stayed in scope.
- **Do not migrate the Tier B fragments** (§3.2, #18-26). Structural markers like
  `"--- CRITICAL CONSTRAINTS ---"` inside a larger assembly routine are not standalone prompts.
- **Do not touch the `.og` files** under `src/hachi/default_skills/` or `src/hachi/packs/`, or the
  fallback `brain.og` writer at `gateway/workspace.py:120-125`. Skill content is data loaded by the
  og_engine and governed by [the .og spec](../../../reference/objectgraph-spec.md) — a completely
  different lifecycle. See also [T-72](T-72-og-spec-executable-surface.md).
- **Do not "fix" `ExecutionLoop._build_system_prompt`'s `getattr` fallback** (`core/loop.py:554-561`,
  Tier B #23). That `getattr` is [T-14](T-14-ban-getattr-own-types.md)'s territory.
- **Do not add prompt-injection hardening in this task.** §2 argues this should land *before* that
  work, not as part of it. Consolidating and hardening in one change makes both unreviewable.
- **Do not add eval cases to compensate for §3.5.** Extending the corpus into prompt-quality
  territory means a non-scripted LLM in the gate — a much larger decision about determinism, cost, and
  CI runtime.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_prompt_registry.py tests/test_prompt_composer.py \
                 tests/test_prompt_cache_ordering.py

# The memory suites are the ones §3.4 puts at risk — run them explicitly.
uv run pytest -q tests/ -k "memory or titler or vision"

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts — **and state explicitly that a green eval step does not mean
prompt quality was preserved** (§3.5). The `test_..._prompt_text_unchanged_by_move` tests are the only
evidence for that claim. Do not let a green gate stand in for them.

## 11. Bug bank entry

**No `docs/bug-bank.md` entry is warranted, and you should not invent one.** Nothing misbehaves at
runtime; this is a consolidation. Forcing an entry devalues the file.

**Do record two things:**

1. **A decision note** in `docs/DECISIONS.md` (or an ADR under `docs/architecture/adr/` if you prefer
   — it must then be linked from that directory's `README.md` and carry `Status:` +
   `## Context` / `## Decision` / `## Consequences`, per `scripts/check_adrs.py:26-28`): that
   `prompt_composer` is now the registry, what the naming convention is, and that
   `sub_agent.PromptBuilder` remains a deliberate second composer pending its own task.

2. **The two hazards you did not fix**, so the next person does not assume they are safe. Suggested
   text for `docs/DECISIONS.md`:

```markdown
### Prompt registry consolidation (T-77) — two known gaps left in place

**Found.** `core/memory.py` holds four LLM prompts with four different response gates:
`_is_substantive_fact` (`:142`) is applied on the flat extraction path (`:404`, `:412`, `:420`)
and in `_flush_facts_to_vault` (`:1483`), but NOT on the typed/tool extraction path (`:310-364`),
which validates shape only. `_generate_structured_summary` (`:1531-1557`) applies NO validation
at all — `:1558` returns `response.content.strip()` verbatim into live conversation history,
despite a prompt demanding five specific `##` sections.

**Decided.** T-77 moved the prompt TEXT into the registry and left every gate exactly where it
was. Closing either gap changes what is written to memory and needs its own regression test.

**Why.** The eval corpus cannot catch a prompt-quality regression: `ScriptedLLMClient.generate`
(`core/eval/replay.py:97`) accepts `**kwargs` and discards them, so `system_prompt` is never
read. `corpus.py:5-10` states the suite tests loop mechanics, not model decision quality. The
per-prompt snapshot tests in `tests/test_prompt_registry.py` are the only protection.
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`core/memory.py` is a collision point.** [T-51](T-51-memory-delete-tri-store.md) and the other
  Wave 2 memory tasks (T-48 memory package boundary, T-50 session provenance, T-52 compaction
  persistence) all edit it, and 11 of this task's 26 sites live there. **Serialize — do not run two
  memory tasks against this file concurrently.** If T-51 is in flight, do the six non-memory sites
  first and hold the `memory.py` commits.
- **The gate is green either way (§3.5).** `uv run hachi eval run` passes whether your prompts are
  correct, mangled, or empty. This is the single most dangerous property of this task. Your §7b tests
  are the real gate; treat a green preflight as necessary, not sufficient, and say so in your report.
- **`_is_substantive_fact` is called at 4 of 5 plausible sites.** After every `memory.py` edit, re-run
  `grep -n "_is_substantive_fact" src/hachi/core/memory.py` and confirm you still see exactly
  `:142` (def), `:404`, `:412`, `:420`, `:1483`. If that list changes, you changed memory-write
  behaviour.
- **Prompts 1 and 2 are branches of one function.** `extract_facts` (`:182`) branches at
  `if memory_writer is not None:` (`:231`, typed) / `else:` (`:368`, flat). They share a name, a
  signature, and a return-string convention, and they are the most tempting merge in the file.
  Registering one entry for both is the failure mode this task exists to prevent.
- **The fence-strip differs between prompts 2 and 3.** `:395-398` handles both ` ```json ` and bare
  ` ``` `; `:1478-1479` handles only ` ```json `. That asymmetry is deliberate per the docstring at
  `:1443-1444` (failures route to the JobWorker pipeline). Do not "unify" it while you are in there.
- **`str.format` and prompts containing braces.** Several prompts contain literal `{` / `}` — e.g. the
  JSON example at `core/memory.py:384` (`'{"user_facts": [...]}'`) and at `:1467`. If you route them
  through `PromptTemplate.render`, `str.format` will raise `KeyError` or `IndexError` on those braces.
  **Either escape them as `{{`/`}}` — which changes the literal and breaks your §7b byte-equality
  test — or store such prompts as `.text` and never call `.render()` on them.** Prefer the latter:
  keep the bytes identical and only render templates that genuinely need substitution.
- **`cli/main.py` is 5,524 lines and a collision point** (T-03, T-04, T-41, T-55, T-67). Your change
  there is two literals at `:1206-1219`; keep it surgical.
- **BB-4 does not apply.** No gateway route changes, so no OpenAPI or frontend-type regeneration.
