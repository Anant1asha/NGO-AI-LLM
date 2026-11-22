# T-72 · Decide and document the `.og` format's executable surface

|  |  |
|---|---|
| **Source finding** | CF-19 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing directly — but [T-56](T-56-pack-consent-every-install-path.md) cannot state what a pack is consenting *to* until this is settled |
| **Effort** | ~2 days |
| **Difficulty** | High — the writing is easy; the decision is not |
| **Files you will touch** | `docs/reference/objectgraph-spec.md`, `scripts/lint_skills.py` (if you pick option B), `tests/`, `docs/DECISIONS.md`, `docs/bug-bank.md` |

---

## 1. Brief

`.og` is the stated moat, and the format's most security-sensitive capability is entirely
undocumented. The parser and runtime execute `::config`, `::tool`, and `::api` blocks and act
on node roles `env`, `integration`, and `mcp` — **an installed `.og` file can declare
credentials, call arbitrary REST endpoints, and start an MCP subprocess.** The specification
contains **zero occurrences of any of those six tokens**.

When you are done, either the executable surface is documented as public API (and you have
accepted the compatibility commitment that implies), or it is explicitly marked internal and
`scripts/lint_skills.py` rejects it in community packs. **Either is a valid outcome. The
current silent middle is not.**

## 2. Why this matters

Every strategy document in this repo puts the `.og` format at the centre of the thesis, and
the pitch is *verifiable, owned, portable* skills. Both halves of that break here:

- **Ecosystem.** A pack author cannot target a capability that is not in the spec. Today the
  only way to learn that `::api` exists is to read `og_engine/parser.py` — so the format's
  most useful feature is effectively first-party-only, by accident rather than by decision.
- **Trust — the serious half.** Third-party review of a malicious pack is impossible against
  an incomplete spec. A reviewer diffing a community `.og` against
  `docs/reference/objectgraph-spec.md` and finding it conformant has verified nothing about
  the three tags that actually *do* something. And these are not theoretical: `role=mcp`
  **starts a subprocess** at session boot (§3.4).

This is the same trust story as [T-56](T-56-pack-consent-every-install-path.md) — consent is
meaningless if the consent sheet cannot name what is being granted — and
[T-58](T-58-declarative-integrations-consolidation.md), where `role=env` is the
plaintext-credential path.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The parser executes three undocumented block types — `og_engine/parser.py:616-620`

```python
        elif block_type == "config":
            node.config = _parse_key_value_block(block_content)
        elif block_type == "tool":
            node.tool_def = _parse_key_value_block(block_content)
        elif block_type == "api":
            if block_arg:
                api_def = _parse_key_value_block(block_content)
                # Strict JSON validation for LLM Tool Generation
                if "schema" in api_def:
                    try:
                        # ADV-025: guard against deeply-nested JSON before parsing.
                        _check_json_depth(api_def["schema"])
                        json.loads(api_def["schema"])
```

The parser recognises **17** `block_type == "…"` literals in total:

```
api  assertion  code  config  dense  edges  example  full  list  note
reference  steps  summary  table  tool  traverse  warning
```

### 3.2 The runtime acts on three undocumented node roles

| Anchor | Symbol | What it does |
|---|---|---|
| `core/integrations.py:49` | `load_env_node(self, node)` | *"Ingest credentials from a role=env node's `::dense` block … KEY=VALUE pairs"* |
| `core/integrations.py:81` | `setup_integration(self, node)` | Dispatches to `_setup_smtp` (`:142`) or `_setup_http` (`:215`); builds a tool schema at `:280` |
| `core/mcp_client.py:1531` | `setup_from_node(self, node)` | *"Create and start an MCP server from a role=mcp .og node"* |

### 3.3 The spec is silent on all six — verified by grep, not by reading

```
docs/reference/objectgraph-spec.md   (1,741 lines)

::api              -> 0
::tool             -> 0
::config           -> 0
role=env           -> 0
role=integration   -> 0
role=mcp           -> 0
```

The spec documents **20** distinct `::` tokens:

```
::end ::dense ::full ::node ::index ::code ::table ::steps ::meta ::warning
::assertion ::list ::edges ::traverse ::schema ::reference ::changelog ::note
::example ::summary
```

**None of the three executable ones is among them.**

**⚠️ It is worse than the review states: the spec never documents `role=` at all.**
`grep -n "role=" docs/reference/objectgraph-spec.md` returns exactly two hits — `:731` and
`:736` — and both are the Python kwarg `agent_role="orchestrator"` in a code sample, not the
`.og` node attribute. The real syntax, from a shipped skill
(`src/hachi/default_skills/general/currency.og:11`):

```
::node[core_currency]
->[:role=skill]
->[:keywords=currency, convert, exchange rate, forex, money, fx, fiat]

::api[convert_currency]
method=GET
endpoint=https://api.frankfurter.app/latest?amount={amount}&from={base}&to={target}
schema={"amount": "number", "base": "string", "target": "string"}
description=Converts fiat currency using real-time European Central Bank rates. ...
```

So the *entire node-role concept* is undocumented, and a fourth value —
`role=native_integration`, recognised at `og_engine/engine.py:260`
(`_SKILL_ROLES = frozenset({"skill", "native_integration"})`) and used throughout
`src/hachi/default_skills/core_integrations.og` — is undocumented too.

**The eight bare `mcp` hits in the spec are about something else.** `:54`, `:1322`, `:1324`,
`:1327`, `:1328`, `:1436`, `:1449`, `:1675` all concern *exporting the OG engine as an MCP
tool* ("8.3 Agentic Tooling (MCP)", `# mcp_og_tools.py`, `from mcp import tool`) — the
opposite direction from `role=mcp`, which lets a `.og` file **start** an MCP server. Do not
mistake one for the other.

### 3.4 These are live boot paths, not dormant code

`gateway/orchestrator.py` scans **every loaded `.og` file** for these roles at session boot:

| Anchor | Code |
|---|---|
| `:2026` | `for node in skill_engine.get_nodes_by_role("mcp"):` |
| `:2063` | `started = mcp_manager.setup_from_node(node)` |
| `:2822` | `for node in skill_engine.get_nodes_by_role("env"):` |
| `:2823` | `integrations.load_env_node(node)` |
| `:2825` | `for node in skill_engine.get_nodes_by_role("integration"):` |
| `:2826` | `if integrations.setup_integration(node):` |

**Lead with this.** Installing a `.og` file is not "adding a document to a knowledge base" —
it can register credentials, mount an HTTP-calling tool, and spawn a subprocess, all at boot,
all from a format whose specification says none of that is possible.

### 3.5 `::api` is already load-bearing for first-party skills — 10 of 36 shipped `.og` files

```
src/hachi/default_skills/general/currency.og:14        ::api[convert_currency]
src/hachi/default_skills/general/dictionary.og:14      ::api[lookup_word]
src/hachi/default_skills/general/finance.og:15         ::api[fetch_crypto_price]
src/hachi/default_skills/general/flight_radar.og:14    ::api[fetch_local_airspace]
src/hachi/default_skills/general/math_engine.og:14     ::api[evaluate_math]
src/hachi/default_skills/general/network.og:14         ::api[lookup_ip]
src/hachi/default_skills/general/translator.og:14      ::api[translate_text]
src/hachi/default_skills/general/weather.og:14         ::api[fetch_weather]
src/hachi/default_skills/general/wiki.og:14            ::api[fetch_wiki_summary]
src/hachi/default_skills/technical/github.og:15        ::api[create_github_issue]
```

**This constrains the decision.** `::api` cannot simply be "internal": it is how Hachi's own
bundled skills declare REST tools, and a spec that omits it is describing a different format
from the one that ships. No shipped `.og` currently uses `role=env`, `role=integration`, or
`role=mcp` — those three are runtime-only capabilities with no first-party example, which is
exactly why nobody noticed they were undocumented.

## 4. Reproduce the failure

Not a runtime failure — a documentation gap, and it is decisive from a shell.

```bash
SPEC=docs/reference/objectgraph-spec.md

# The six tokens. Every count must be 0.
for t in '::api' '::tool' '::config' 'role=env' 'role=integration' 'role=mcp'; do
  printf '%-18s -> %s\n' "$t" "$(grep -Fc -- "$t" "$SPEC" || echo 0)"
done

# What the spec DOES document.
grep -oE '::[a-z_]+' "$SPEC" | sort -u

# What the parser actually handles.
rg -o 'block_type == "[a-z_]+"' src/hachi/og_engine/parser.py | sed 's/.*== //' | sort -u

# The live boot paths.
rg -n 'get_nodes_by_role\("(mcp|env|integration)"\)' src/hachi/gateway/orchestrator.py

# First-party dependence on ::api.
rg -c '::api' --glob '*.og' src/ | wc -l
```

**You will see now:** six zeroes; 20 spec tokens; 17 parser tokens with `api`/`tool`/`config`
present in the second set and absent from the first; three live `get_nodes_by_role` boot
scans; 10 shipped skills using `::api`.

**You should see after the fix:** every one of the six greps returns a non-zero count in the
spec (option A), **or** `scripts/lint_skills.py` rejects them outside `src/hachi/default_skills/`
and the spec says so explicitly (option B). Not silence.

## 5. What "fixed" looks like

> ### 🔷 DECISION REQUIRED
>
> **The question:** are `.og`'s executable tags **public format surface** that third parties
> may use and that you will support — or **internal runtime tags** that first-party skills
> use and community packs may not?
>
> This is a product call about what `.og` *is*. Do not let an implementer make it by
> accident, and do not let it stay unmade — the status quo is the only option with no
> defence.
>
> ---
>
> **Option A — document them as public surface.**
> Add a *"Runtime & integration tags"* section to `docs/reference/objectgraph-spec.md`
> covering `::config`, `::tool`, `::api`, and the `role=` attribute (all five values:
> `skill`, `native_integration`, `env`, `integration`, `mcp`), each with syntax, a worked
> example, and an explicit security note.
>
> *For:* it is the honest description of the shipping format; `::api` is already load-bearing
> for 10 first-party skills (§3.5), so the spec is *wrong* today, not merely incomplete; it
> unblocks the ecosystem story; and reviewers get something to audit against.
> *Against:* **documenting the surface commits you to supporting it.** `::api`'s
> `method`/`endpoint`/`schema` keys and `role=mcp`'s server-launch contract become things you
> cannot change without a breaking-change process. It also advertises, in writing, that
> installing a pack can start a subprocess — which is true today and which
> [T-56](T-56-pack-consent-every-install-path.md) must then be able to gate.
>
> ---
>
> **Option B — mark them internal and lint against them in community packs.**
> Add a short spec section stating the tags exist, are **reserved for bundled skills**, and
> are not part of the portable format. Enforce it in `scripts/lint_skills.py` (already a
> blocking preflight step, `scripts/preflight.py:81`): reject `::api`/`::tool`/`::config` and
> `role=env|integration|mcp` in any `.og` outside `src/hachi/default_skills/`.
>
> *For:* smallest compatibility commitment; shrinks the untrusted-pack attack surface to
> roughly nothing; mechanically enforced rather than advisory; reversible — you can promote
> to public later, which you cannot undo the other way.
> *Against:* it is a real capability reduction for pack authors, and it is an awkward
> position to publish ("Hachi's own skills use a tag yours may not"). It also does nothing for
> the 10 first-party skills' *documentation* debt — the spec still would not describe the
> format Hachi ships.
>
> ---
>
> **Recommendation: A for `::api` and `::config`/`::tool`; B for the three roles.**
>
> The split is not a fudge — the two groups have genuinely different risk profiles, and the
> evidence separates them cleanly:
>
> - `::api`/`::tool`/`::config` are **declarative**: data the engine turns into a tool
>   schema. `::api` is already in 10 shipped skills, so it is de-facto public and the spec is
>   simply wrong. Document it. Its network reach is real but is the same reach the agent has
>   anyway, and SSRF pinning already exists at the edge.
> - `role=env`, `role=integration`, `role=mcp` are **imperative**: they ingest plaintext
>   credentials and start subprocesses at boot (§3.4). **Zero shipped `.og` files use them**,
>   so restricting them to first-party costs nothing today and closes a genuine
>   untrusted-pack hole. Document that they exist and that they are reserved; lint them.
>
> If you disagree, pick one of the pure options and say so in `docs/DECISIONS.md`. What is
> not acceptable is leaving it undecided.

Whichever you choose, the deliverable includes all of:

1. A new spec section — the tags **named**, so a grep for any of the six tokens hits the spec.
2. `docs/DECISIONS.md` entry recording the choice and its reasoning (that file is the
   repo's decision log; see [CLAUDE.md](../../../../CLAUDE.md)).
3. A mechanical check that keeps the spec honest as the parser grows (§7).
4. If option B (in whole or part): the `scripts/lint_skills.py` rule, plus a positive test
   that a bundled skill using the tag still passes.

## 6. Steps

1. **Get the decision.** Do not start writing until you have it. Record it in
   `docs/DECISIONS.md` first.
2. Write the §7 spec-coverage test. Watch it fail listing all six tokens.
3. Read `og_engine/parser.py:560-700` (the block dispatch) and `core/integrations.py:39-320`
   end to end. Document what the code **does**, never what you assume it does — this is a
   specification, and a wrong spec is worse than a missing one.
4. Write the spec section. Model its structure on the existing block-type sections so it
   reads as part of the document, not an appendix.
5. Include a worked example per tag. Use the real `currency.og` one for `::api` (§3.3) rather
   than inventing syntax.
6. Add the explicit security note: what an installed `.og` can do at boot, keyed to the three
   `get_nodes_by_role` scans at `gateway/orchestrator.py:2026`, `:2822`, `:2825`.
7. If option B applies: add the `lint_skills.py` rule + tests, and confirm
   `uv run python scripts/lint_skills.py` still passes on all 36 shipped `.og` files.
8. Cross-link [T-56](T-56-pack-consent-every-install-path.md) from the security note.
9. Run the FULL `uv run python scripts/preflight.py` and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

This is a documentation task, and **a pytest test IS the right instrument here** — because the
invariant is mechanical and permanent: *every block type the parser executes must appear in
the spec.* That check keeps working forever, including for the block type someone adds next
year.

- **File:** `tests/test_p5_01_conformance.py` (**existing** — it already owns spec
  conformance and already resolves the spec path via `Path(__file__).parent.parent / "spec"`;
  confirm the path before adding)
- **Test names:** `test_spec_documents_every_parser_block_type`,
  `test_spec_documents_every_executable_node_role`
- **It must assert:** against the **real** parser source and the **real** spec file — that
  every `block_type == "X"` literal in `og_engine/parser.py` has a `::X` occurrence in
  `docs/reference/objectgraph-spec.md`, and that each executable role token appears. Derive
  the parser's list by reading the source, not from a hardcoded copy, so a new block type
  fails the test automatically.
- **It must FAIL before your fix** with
  `AssertionError: parser block types missing from the spec: ['api', 'config', 'tool']`.

```python
# sketch — adapt to the repo's existing fixtures
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "reference" / "objectgraph-spec.md"
PARSER = ROOT / "src" / "hachi" / "og_engine" / "parser.py"


def test_spec_documents_every_parser_block_type() -> None:
    """The .og spec must describe every block the parser executes.

    Regression: ::config, ::tool and ::api were executed by the parser and appeared
    ZERO times in the spec — so the format's executable surface (REST calls, tool
    definitions) was invisible to pack authors and unauditable by reviewers.
    """
    spec = SPEC.read_text(encoding="utf-8")
    handled = set(re.findall(r'block_type == "([a-z_]+)"', PARSER.read_text(encoding="utf-8")))
    assert handled, "parser dispatch not found — did the block dispatch move?"

    missing = sorted(b for b in handled if f"::{b}" not in spec)
    assert not missing, (
        f"parser block types missing from {SPEC.name}: {missing}. "
        "Document them, or mark them internal and lint against them (T-72)."
    )


def test_spec_documents_every_executable_node_role() -> None:
    """role=env/integration/mcp ingest credentials, mount HTTP tools and START
    SUBPROCESSES at session boot. The spec must name them either way."""
    spec = SPEC.read_text(encoding="utf-8")
    missing = [r for r in ("role=env", "role=integration", "role=mcp") if r not in spec]
    assert not missing, f"executable node roles missing from {SPEC.name}: {missing}"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> **Under option B these tests still apply** — "reserved for bundled skills; not part of the
> portable format" is a spec mention and satisfies both. The tests assert the format is
> *described*, not that it is *permitted*.

## 8. Acceptance criteria

- [ ] The decision is recorded in `docs/DECISIONS.md` **before** the spec was edited.
- [ ] The §7 tests exist and failed before the fix with `['api', 'config', 'tool']`.
- [ ] All six greps in §4 return a non-zero count against the spec.
- [ ] The spec's new section documents `role=` as a node attribute and enumerates all five values (`skill`, `native_integration`, `env`, `integration`, `mcp`).
- [ ] Each documented tag has a worked example taken from a real shipped `.og`, not invented.
- [ ] A security note states plainly what an installed `.og` can do at boot, anchored to `gateway/orchestrator.py:2026`, `:2822`, `:2825`.
- [ ] It cross-links [T-56](T-56-pack-consent-every-install-path.md) and [T-58](T-58-declarative-integrations-consolidation.md).
- [ ] If option B applies: `scripts/lint_skills.py` rejects the reserved tags outside `src/hachi/default_skills/`, **and** all 36 shipped `.og` files still lint clean.
- [ ] `uv run python scripts/lint_skills.py` passes.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change the parser or the runtime.** This task documents (or restricts) what
  exists. Renaming `::api` to something nicer, adding validation, deprecating `::tool` — all
  are separate changes with separate blast radii. The 10 shipped skills at §3.5 depend on
  today's behaviour.
- **Do not fix `role=env`'s plaintext-credential handling.** `load_env_node`
  (`core/integrations.py:49`) reads `KEY=VALUE` pairs from a `::dense` block. That is
  [T-58](T-58-declarative-integrations-consolidation.md)'s subject. **Document it, name the
  risk, move on.**
- **Do not build the consent flow.** [T-56](T-56-pack-consent-every-install-path.md) owns
  install-path consent. You are giving it the vocabulary, not the mechanism.
- **Do not fix the unapproved native-tool mount** at `gateway/orchestrator.py:3325-3352`
  (`instance.register_tools(tool_registry)` with no approver). That is CF-11 /
  [T-35](T-35-google-double-mount.md), and [T-01](T-01-approver-selection-dead-branch.md)
  explicitly fences it off.
- **Do not rewrite the rest of the spec.** It is 1,741 lines. Add your section, fix any
  cross-reference your section needs, stop ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- **Do not delete the "8.3 Agentic Tooling (MCP)" section** (`:1322-1330`) as a duplicate. It
  documents the opposite direction — exporting `.og` as an MCP tool — and is unrelated (§3.3).
- **Do not add an `::api` example that hits a real endpoint** in test fixtures. Use the
  shipped `currency.og` text verbatim as illustration; do not make the suite call the network.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/lint_skills.py         # all 36 shipped .og files must still pass
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

If you took option B, the highest-value manual check is the negative one: **write a throwaway
`.og` outside `default_skills/` containing `role=mcp` and confirm the linter rejects it.**
A lint rule nobody has watched fire is a lint rule that does not work. Delete the file
afterwards.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — The `.og` spec omitted every executable tag the runtime acts on

- **Symptom:** `docs/reference/objectgraph-spec.md` contained ZERO occurrences of `::api`,
  `::tool`, `::config`, `role=env`, `role=integration` or `role=mcp` — and never documented
  the `role=` node attribute at all — while the parser executed all three block types
  (`og_engine/parser.py:616-620`) and the gateway scanned every loaded .og for all three
  roles at session boot (`gateway/orchestrator.py:2026`, `:2822`, `:2825`). An installed .og
  could ingest credentials, mount an HTTP-calling tool, and start an MCP subprocess, from a
  format whose spec said none of that was possible.
- **Root cause:** the spec tracks the *knowledge* format; the runtime tags accreted in code
  only, and nothing tied the two together. `::api` even reached 10 shipped first-party
  skills without the spec noticing.
- **Fix:** documented the executable surface (and/or marked it reserved and enforced that in
  `scripts/lint_skills.py`), plus a conformance test that derives the parser's block types
  from the parser source and requires each to appear in the spec.
- **Avoid:** when a format is the product, its spec is not documentation — it is the
  contract a third-party reviewer audits against. Any new `block_type ==` branch or
  `get_nodes_by_role(...)` scan must land in the same PR as its spec section; the
  conformance test now enforces that for block types.
- **Locked by:** `tests/test_p5_01_conformance.py` — `test_spec_documents_every_parser_block_type`, `test_spec_documents_every_executable_node_role`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **The two `mcp` meanings.** The spec's existing MCP content (`:54`, `:1322-1330`, `:1436`,
  `:1449`, `:1675`) is about *exporting the OG engine as an MCP tool*. `role=mcp` is about a
  `.og` file *starting* an MCP server. Opposite directions. Writing your section next to
  §8.3 without saying so will confuse every reader.
- **`::api` is `block_type == "api"` only when `block_arg` is present** (`parser.py:620-621`
  — `if block_arg:`). `::api` with no `[name]` silently parses to nothing. Document that;
  it is exactly the kind of quiet failure the review flagged as the repo's systemic pattern.
- **`_check_json_depth`** (`parser.py:626`, ADV-025) guards `schema=` against deeply-nested
  JSON. If you document the `schema` key, document the bound too — otherwise the first
  author to hit it experiences a security control as a parser bug.
- **`scripts/lint_skills.py` is BLOCKING in preflight** (`scripts/preflight.py:81`). A new
  rule that false-positives on any of the 36 shipped `.og` files turns the gate red for
  everyone. Run it against `src/hachi/default_skills/` and `src/hachi/packs/` before you
  commit.
- **`tests/test_p5_01_conformance.py:19` resolves `Path(__file__).parent.parent / "spec"`** —
  the repo-root `spec/` directory, *not* `docs/reference/`. Do not assume the fixture you
  need already exists; and note this file is one of the 29 that
  [T-70](T-70-test-tree-mirroring.md) must convert before it can move.
- **Do not confuse `role=native_integration` with `role=integration`.** They are different
  values with different handlers: `native_integration` is recognised at
  `og_engine/engine.py:260` and drives the capability registry; `integration` is handled by
  `core/integrations.py:81`. Both need documenting; they are not synonyms.
