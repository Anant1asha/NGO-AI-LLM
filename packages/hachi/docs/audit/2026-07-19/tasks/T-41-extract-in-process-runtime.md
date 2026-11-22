# T-41 · Extract `_InProcessGatewayRuntime` out of the CLI into `hachi.gateway`

|  |  |
|---|---|
| **Source finding** | CF-2 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | [T-42](T-42-retire-core-cli-seam.md), [T-43](T-43-collapse-control-plane-interfaces.md) |
| **Effort** | ~1 week |
| **Difficulty** | Medium (large diff, near-zero design judgement — read §5 and §9) |
| **Files you will touch** | `src/hachi/gateway/in_process_runtime.py` (new), `src/hachi/cli/main.py`, `src/hachi/gateway/control_plane.py` (docstring only), ~20 files under `tests/` |

---

## 1. Brief

`_InProcessGatewayRuntime` — the entire in-process gateway backend, **2,356 lines and 79
methods** — lives inside `src/hachi/cli/main.py`. Every web-UI, TUI, and `hachi serve`
request transits the CLI module to reach it. Move the class **verbatim** to
`src/hachi/gateway/in_process_runtime.py`, rewriting only import paths, so the gateway
backend lives in the gateway package and `cli/main.py` becomes a CLI again.

**This is the keystone Wave-2 task. Feature-freeze the affected files while it is in flight.**

## 2. Why this matters

Layering is inverted in spirit while green in letter. A standalone gateway is impossible
today: `hachi serve`, the web UI, and the TUI all import the Typer module to get a backend.
`cli/main.py` is 5,524 lines and the highest-churn file in the repo (~93 touches since
April), so every backend feature — regardless of domain — collides in the same file. Adding
one endpoint currently touches four places (runtime method, control-plane parameter,
delegate, CLI wiring). And it is the reason `core/runtime/resume.py` reaches back into the
CLI ([T-42](T-42-retire-core-cli-seam.md)).

**If your diff changes behaviour, you have missed the point.** The value here is entirely
in the *location* of the code, not its content. A move that also "improves things a bit" is
unreviewable and will be rejected.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The class

`src/hachi/cli/main.py:244` — class opens:

```python
class _InProcessGatewayRuntime:
    """Bridge gateway API calls to the in-process AgentSession runtime."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentSession] = {}
        self._agents_lock = threading.Lock()
```

The class body ends at **`:2599`** (last method `probe_provider` opens at `:2588`); the next
module-level definition is `_gateway_readiness_probe` at `:2603`.

- **Span: `cli/main.py:244–2599` = 2,356 lines = 42.6 % of the 5,524-line file.**
- **79 methods** — 71 public, 8 private (`_boot_session_agent`, `_get_agent`,
  `_reload_agents`, `_standalone_og_engine`, `_resolve_authoring_target_path`,
  `_mcp_live_server_names`, `_mcp_node_names`, plus `__init__`).

> **Correction to the review.** CF-2 states "`cli/main.py:244–2601` — 2,358 lines, 85
> methods". The verified figures are **244–2599, 2,356 lines, 79 methods**. Use these.

### 3.2 This extraction is EASIER than CF-2 implies — verify it yourself

CF-2 frames this as a risky mega-move. It is not, and you should know that before you start:

**(a) Not one dependency is CLI-owned.** All 17 first-party symbols the class consumes
already live under `hachi.core.*` or `hachi.gateway.*`. The class imports *nothing* that
belongs to `hachi.cli`. The move is therefore a pure relocation, not an untangling.

**(b) There is no circular-import risk.** `gateway/orchestrator.py` — the source of
`AgentSession` and `boot_agent`, the class's heaviest dependency — **does not import
`hachi.cli` at all.** Confirm:

```bash
grep -n "hachi\.cli" src/hachi/gateway/orchestrator.py    # → no import lines
```

The single hit anywhere in `gateway/` is a **docstring cross-reference** at
`gateway/control_plane.py:1156` (`:meth:`~hachi.cli.main._InProcessGatewayRuntime.session_messages``),
which is stale documentation, not code. Fix it as part of this task.

### 3.3 `_ACTIVE_RUNTIME` is NOT a dependency of the class

CF-2's phrasing implies the module global and the class are entangled. They are not.

`cli/main.py:2710` — defined **111 lines after the class ends**:

```python
_ACTIVE_RUNTIME: "_InProcessGatewayRuntime | None" = None
```

Every write is from a **module-level function**, never from the class:

- `cli/main.py:2931-2932` — inside `_start_gateway_server`
- `cli/main.py:3974-3975` — inside the `gateway` command

```bash
grep -n "_ACTIVE_RUNTIME" src/hachi/cli/main.py
# 2710 (definition), 2931/2932, 3974/3975 — all outside 244–2599
```

**The class never reads it.** Coupling is one-directional (module → class). `_ACTIVE_RUNTIME`
therefore **stays in `cli/main.py`**; only its type annotation changes to reference the
imported class. [T-42](T-42-retire-core-cli-seam.md) deals with it separately.

### 3.4 Only TWO module-level globals actually move

| Global | Defined | Used by |
|---|---|---|
| `_logger` | `cli/main.py:154` | `update_permissions`, `set_mcp_enabled`, `delete_mcp_server`, `set_routing` |
| `_GATEWAY_RESIDENT_WORKER` | `cli/main.py:2703` | written by `_boot_session_agent`; read by `_gateway_readiness_probe` |

`_logger` is trivial — the new module gets its own `logging.getLogger(__name__)`.

**`_GATEWAY_RESIDENT_WORKER` is the only true write-shared global, and it is the one real
hazard in this task.** `cli/main.py:277-283`, inside `_boot_session_agent`:

```python
        # Expose the resident worker to the module-level readiness probe so it
        # can check worker liveness without coupling probe ↔ runtime instance.
        global _GATEWAY_RESIDENT_WORKER  # noqa: PLW0603
        worker = getattr(agent, "_resident_worker", None)
        if worker is not None:
            _GATEWAY_RESIDENT_WORKER = worker
        return agent
```

⚠️ **The slot is defined at `cli/main.py:2703` — 104 lines *after* the class that mutates
it, and 2,420 lines after the `global` statement that binds it.** Python tolerates this;
a file split does not. You must either move the slot into the new module alongside the class,
or invert it into injected state. See §5 for the decision (it is already made for you).

⚠️ **Eight tests patch `"hachi.cli.main._GATEWAY_RESIDENT_WORKER"` by name.** They will
break loudly (good) or silently (bad) depending on which option you take. §7 covers it.

### 3.5 Dependency fan-in — the extraction order

Highest fan-in first. Useful if you stage partial extractions; also the checklist for the
import block in the new module.

| Symbol | Methods using it |
|---|---|
| `GatewayProtocolError` | 21 |
| `load_effective_config` | 11 |
| `asdict` (stdlib `dataclasses`) | 8 |
| `get_hachi_paths` | 5 |
| `get_permissions_file` | 5 |
| `write_global_config` | 5 |
| `AgentSession` | 4 |
| `SessionStore` | 3 |
| `create_default_secret_store` | 3 |
| `OnboardingService` | 2 |
| `boot_agent`, `ConnectRequest`, `GatewayEvent`, `ScheduleStore`, `redact_secrets`, `looks_like_env_var_name`, `persist_provider_api_key` | 1 each |

Stdlib imports the class needs: `logging` (`cli/main.py:14`), `threading` (`:17`),
`asdict` (`:18`), `datetime.date as _date` (`:19`), `pathlib.Path` (`:20`).

### 3.6 ⚠️ FALSE POSITIVES — do NOT move these

A naive `grep` for names referenced inside the class will surface three symbols that look
like module-level dependencies. **They are Typer commands, shadowed by local variables
inside the class.** They stay in `cli/main.py`.

| Name | Actually is | At |
|---|---|---|
| `config` | `@app.command()` `def config(show_paths: bool = ...)` | `cli/main.py:4162` |
| `models` | `@app.command()` `def models(json_output: bool = ...)` | `cli/main.py:4438` |
| `permissions` | `@app.command()` `def permissions(reset: bool = ...)` | `cli/main.py:3444` |

Moving or importing any of these would drag the Typer app into `hachi.gateway` and create
the exact inversion this task exists to remove.

### 3.7 The 13 method groups

The class's 79 methods partition cleanly into 13 domains. **This is the staged-extraction
plan** and, not coincidentally, is near-isomorphic with the 15 parameter groups of
`GatewayControlPlane` ([T-43](T-43-collapse-control-plane-interfaces.md)) — the same domains
wired twice. Groups are ordered by *independence*: **9–13 are the cheapest first cuts;
group 1 owns the mutable state and comes LAST.**

| # | Group | Methods | ~Lines | Line anchors |
|---|---|---|---|---|
| 1 | **Session lifecycle + locking** — owns `_agents`, `_agents_lock` ← **extract LAST** | 15 | ~285 | `__init__` 247, `_boot_session_agent` 263, `_get_agent` 285, `register_connection` 292, `close_connection` 328, `rehydrate_session` 339, `_reload_agents` 372, `chat` 398, `interrupt_session` 416, `read_events` 440, `session_state` 452, `recent_sessions` 455, `session_messages` 472, `delete_session_record` 487, `shutdown` 939 |
| 2 | Runtime observability read-models — **all one-line `asdict()` delegations** | 6 | ~46 | `runtime_events` 495, `mcp_inventory` 509, `active_jobs` 516, `failed_jobs` 523, `permission_audit` 530, `subagent_reports` 537 |
| 3 | Scheduling | 4 | ~29 | `list_schedules` 545, `cancel_schedule` 554, `toggle_schedule` 562, `run_schedule_now` 570 |
| 4 | **Config / provider / setup — largest group** | 10 | ~382 | `capabilities` 578, `get_config` 615, `update_provider` 646, `validate_provider` 730, `update_permissions` 760, `update_memory` 823, `list_models` 843, `setup_state` 912, `apply_setup` 921, `set_capability_enabled` 1614 |
| 5 | Skills / memory / OG | 7 | ~168 | `get_skills` 953, `get_memory` 961, `get_memory_recall` 969, `get_og_graph` 999, `_standalone_og_engine` 1034, `add_memory_fact` 1638, `delete_memory_fact` 2293 |
| 6 | Authoring | 7 | ~365 | `get_authoring_targets` 1065, `_resolve_authoring_target_path` 1107, `get_authoring_target` 1144, `authoring_generate` 1157, `authoring_apply` 1264, `authoring_save_source` 1322, `authoring_revert` 1397 |
| 7 | Spend | 2 | ~177 | `get_spend` 1435 (**151 L — the single largest method in the class**), `get_spend_daily` 1587 |
| 8 | Permissions / limits | 6 | ~222 | `update_limits` 1678, `add_allowed_folder` 1713, `add_allowed_command` 1754, `remove_allowed_folder` 1791, `remove_allowed_command` 1823, `add_always_allow` 1851 |
| 9 | MCP admin | 5 | ~315 | `register_mcp_server` 1905, `_mcp_live_server_names` 2029, `_mcp_node_names` 2040, `set_mcp_enabled` 2056, `delete_mcp_server` 2125 |
| 10 | Kennel | 2 | ~65 | `get_kennel` 2225, `add_skill_from_kennel` 2266 |
| 11 | Secrets | 3 | ~35 | `store_secret` 2329, `list_secret_names` 2347, `delete_secret` 2359 |
| 12 | Search | 1 | ~22 | `reload_search_tools` 2366 |
| 13 | Providers / routing admin | 11 | ~208 | `list_providers` 2390, `add_or_update_provider` 2400, `remove_provider` 2416, `get_routing` 2431, `set_routing` 2441, `validate_routing` 2510, `rollback_routing` 2530, `get_routing_audit` 2551, `test_provider_connection` 2565, `list_all_models` 2578, `probe_provider` 2588 |

Regenerate this list any time with:

```bash
awk 'NR>=244 && NR<=2599' src/hachi/cli/main.py \
  | grep -n "^    def " | awk -F'[:(]' '{print $1+243": "$2}' | sed 's/    def //'
```

### 3.8 ⚠️ The test suite patches `hachi.cli.main.*` **by name**, ~200 times

This is the largest silent-failure risk in the task, and it is bigger than CF-2 suggests.
`unittest.mock.patch` resolves the string at call time against the *named module*. Once
the class lives in `hachi.gateway.in_process_runtime`, its methods resolve
`load_effective_config`, `write_global_config`, `get_hachi_paths`, etc. in the **new**
module's namespace. Patching the old path then does nothing — and the test **still passes**,
because it now exercises the real function against a tmp path that happens to work.

Patch-target census across `tests/`:

```
 51  "hachi.cli.main.load_effective_config"
 37  "hachi.cli.main.get_hachi_paths"
 19  "hachi.cli.main.write_global_config"
 17  "hachi.cli.main.create_default_secret_store"
 13  "hachi.cli.main.boot_agent"
 10  "hachi.cli.main.OnboardingService"
  8  "hachi.cli.main._GATEWAY_RESIDENT_WORKER"
  4  "hachi.cli.main.get_permissions_file"
  ... plus 15 lower-count CLI-only targets
```

Distributed across 20 test files (patch-string count per file):

```
tests/test_cli_gateway_command.py            47
tests/test_gateway_config_mutations.py       33
tests/test_readiness_probe.py                25
tests/test_gateway_models.py                 14
tests/test_backup_restore.py                 12
tests/test_zero_config_onboarding.py         10
tests/test_config_get_set.py                  9
tests/test_gateway_runtime_validation.py      7
tests/test_cli_run_once.py                    7
tests/test_cli_creds_and_og.py                7
tests/test_gateway_new_endpoints.py           6
tests/test_authoring_backend.py               5
tests/test_permissions_update.py              3
tests/test_config_validate.py                 3
tests/test_cold_start_resume.py               3
tests/test_web_gui_diag.py                    2
tests/test_session_messages_cold_boot.py      2
tests/test_g1_wave1.py                        2
tests/test_cli_models.py                      2
tests/test_google_auth_cmd.py                 1
```

**Not all of these move.** A patch belongs to the new module only if the code under test is
a `_InProcessGatewayRuntime` method. Patches that target CLI *commands* (`hachi config`,
`hachi models`, onboarding, backup/restore) keep `hachi.cli.main.*`. §6 gives the mechanical
way to tell them apart.

Reproduce the census:

```bash
grep -rhoE '"hachi\.cli\.main\.[a-zA-Z_]+"' tests/ | sort | uniq -c | sort -rn
```

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor. There is no runtime failure, no crash, no wrong output, and no
user-visible symptom.** Do not invent one, and do not go looking for a bug to justify the
work — the defect is structural. Here is how to *see* it:

```bash
# 1. The CLI module is a backend, by size.
wc -l src/hachi/cli/main.py                    # 5524
awk 'NR>=244 && NR<=2599' src/hachi/cli/main.py | wc -l   # 2356 → 42.6% of the file

# 2. That backend has 79 methods spanning 13 unrelated domains.
awk 'NR>=244 && NR<=2599' src/hachi/cli/main.py | grep -c "^    def "   # 79

# 3. The gateway does NOT depend on the CLI — so nothing justifies the placement.
grep -n "hachi\.cli" src/hachi/gateway/orchestrator.py     # → nothing (docstring only elsewhere)

# 4. But the ENGINE does, because of where the class sits.
grep -n "import hachi.cli.main" src/hachi/core/runtime/resume.py   # :124

# 5. And the linter has a standing exemption for exactly that.
sed -n '195,211p' pyproject.toml
```

**You will see now:** a 5,524-line Typer module that contains the entire gateway backend,
and an engine-layer file importing it.
**You should see after the fix:** `cli/main.py` around 3,150 lines and no gateway backend in
it; `src/hachi/gateway/in_process_runtime.py` holding the class;
`grep -c "^    def " src/hachi/gateway/in_process_runtime.py` → 79.

## 5. What "fixed" looks like

**New file:** `src/hachi/gateway/in_process_runtime.py`

```python
"""In-process bridge from gateway API calls to the AgentSession runtime.

Extracted verbatim from ``hachi.cli.main`` (T-41). Behaviour is unchanged;
only import paths were rewritten.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict
from datetime import date as _date
from pathlib import Path
from typing import Any

from hachi.core.config_loader import load_effective_config, write_global_config
# … the remaining 16 first-party imports from §3.5 …

_logger = logging.getLogger(__name__)

#: Module-level slot for the ResidentWorkerThread started by the in-process
#: gateway runtime. Set by :class:`InProcessGatewayRuntime` once an agent
#: session is booted; read by the CLI's readiness probe.
_GATEWAY_RESIDENT_WORKER: "ResidentWorkerThread | None" = None


class _InProcessGatewayRuntime:
    """Bridge gateway API calls to the in-process AgentSession runtime."""
    # … all 79 methods, byte-identical …
```

**Decisions already made — do not re-litigate:**

1. **Keep the leading underscore.** `_InProcessGatewayRuntime`, not
   `InProcessGatewayRuntime`. Renaming is a second, separable change and it would churn
   every test patch string a second time. Rename later, in its own commit, if at all.
2. **`_GATEWAY_RESIDENT_WORKER` moves with the class**, into the new module. `cli/main.py`
   keeps a *re-export* so `_gateway_readiness_probe` and the 8 tests that patch it keep
   working:
   ```python
   # cli/main.py — after the import
   from hachi.gateway.in_process_runtime import _InProcessGatewayRuntime
   ```
   and `_gateway_readiness_probe` reads it through the module object, not a `from` import:
   ```python
   from hachi.gateway import in_process_runtime as _runtime_mod
   worker = _runtime_mod._GATEWAY_RESIDENT_WORKER
   ```
   A `from … import _GATEWAY_RESIDENT_WORKER` would snapshot `None` at import time and
   permanently break the readiness probe. **This is the single easiest way to break this
   task.**
3. **`_ACTIVE_RUNTIME` stays in `cli/main.py`.** Only its annotation changes. It is
   [T-42](T-42-retire-core-cli-seam.md)'s problem.
4. **`cli/main.py` imports the class at module scope**, not lazily. There is no cycle
   (§3.2), so a lazy import would only obscure the dependency.
5. **Zero behaviour change.** No renamed methods, no changed signatures, no reordered
   parameters, no "while I'm here" fixes, no docstring rewrites beyond the stale
   `control_plane.py:1156` reference.

## 6. Steps

**Staging is the whole discipline here. Three commits, in this order, each independently
reviewable and each green.**

### Commit 1 — characterization tests (no source change)

1. Write the characterization test from §7. It must pass **before** you move anything.
2. Run the full suite and **record the exact counts**. This number is your contract for
   commits 2 and 3.
   ```bash
   uv run pytest -q    # or: python -m pytest -q   (BB-1)
   ```

### Commit 2 — the verbatim move

3. Create `src/hachi/gateway/in_process_runtime.py` with the module docstring and
   `from __future__ import annotations`.
4. **Cut** `cli/main.py:244–2599` and paste it into the new file. Do not retype it. Do not
   reformat it. `git diff` should show a delete-block and an add-block of equal length.
5. Add the import block: the 5 stdlib imports from §3.5 and the 17 first-party imports.
   Resolve each by reading the corresponding import line in `cli/main.py` — copy the
   module path exactly, do not guess it.
6. Add `_logger = logging.getLogger(__name__)`.
7. **Move** `_GATEWAY_RESIDENT_WORKER` (`cli/main.py:2703`, with its comment) into the new
   module, placed **above** the class.
8. In `cli/main.py`: add `from hachi.gateway.in_process_runtime import _InProcessGatewayRuntime`.
9. In `cli/main.py`: rewrite `_gateway_readiness_probe` to read `_GATEWAY_RESIDENT_WORKER`
   **through the module object** (§5 decision 2). This is the only logic edit in the whole
   commit — call it out in the commit message.
10. Delete now-unused imports from `cli/main.py`. Let `ruff check` tell you which; **do not
    run `ruff format` on the file** (Rule 3 — the auto-format hook handles touched lines).
11. Fix the stale docstring at `gateway/control_plane.py:1156`.
12. Re-point the test patch strings. Mechanical rule: **a patch target moves iff the code
    under test is a runtime method.**
    ```bash
    # find every patch string, then classify by what the test calls
    grep -rn '"hachi\.cli\.main\.\(load_effective_config\|write_global_config\|get_hachi_paths\|create_default_secret_store\|boot_agent\|OnboardingService\|get_permissions_file\)"' tests/
    ```
    For each hit, read the test body: if it constructs `_InProcessGatewayRuntime()` or drives
    the gateway control plane, change the string to
    `"hachi.gateway.in_process_runtime.<name>"`. If it invokes a Typer command via
    `CliRunner`, leave it alone.
    ⚠️ **A wrong answer here does not fail — it passes while testing nothing.** After
    re-pointing, sanity-check one test per file by breaking the patched function's real
    implementation temporarily and confirming the test goes red.
13. Run the full suite. **The counts must match commit 1 exactly.** Any delta is a
    behaviour change you introduced; find it before proceeding.

### Commit 3 — retire the linter exemption for this class (optional; hand off if it grows)

14. Confirm `import-linter` is still green:
    ```bash
    uv run lint-imports
    ```
15. Do **not** touch the `resume.py` exemption in this commit — that is
    [T-42](T-42-retire-core-cli-seam.md), and it is trivial once this lands.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law), applied to a
refactor.** There is no bug to reproduce, so the correct instrument is a **characterization
test**: assert the *current* behaviour before the move, so the move is provably
behaviour-neutral. It passes before and after — that is the point, and it is the one
legitimate case where a green-before test is correct.

- **File:** `tests/test_in_process_runtime_extraction.py` (new)
- **Test names:** `test_runtime_exposes_the_full_method_surface`,
  `test_runtime_is_importable_from_gateway_without_cli`,
  `test_resident_worker_slot_is_visible_to_readiness_probe`
- **It must assert:** the real, observed method surface and the real cross-module global
  read — not a mock's return value.
- **It will PASS before the move** (it characterizes today's behaviour) **and must still
  pass after.** The second test is the exception: it **must FAIL before** the move with
  `ModuleNotFoundError: No module named 'hachi.gateway.in_process_runtime'`.

```python
# sketch — adapt to the repo's existing fixtures
import sys

EXPECTED_METHODS = {
    "chat", "register_connection", "close_connection", "rehydrate_session",
    "get_spend", "get_spend_daily", "set_routing", "register_mcp_server",
    # … all 79 names from §3.7; generate them, do not hand-type them …
}


def test_runtime_exposes_the_full_method_surface() -> None:
    """Lock the 79-method surface so the move cannot silently drop one."""
    from hachi.gateway.in_process_runtime import _InProcessGatewayRuntime

    actual = {n for n in vars(_InProcessGatewayRuntime) if callable(getattr(_InProcessGatewayRuntime, n))}
    assert EXPECTED_METHODS <= actual, f"methods lost in the move: {EXPECTED_METHODS - actual}"
    assert len(EXPECTED_METHODS) == 79


def test_runtime_is_importable_from_gateway_without_cli() -> None:
    """The gateway backend must not need the Typer module to import.

    FAILS before T-41 with ModuleNotFoundError.
    """
    for mod in [m for m in sys.modules if m.startswith("hachi.cli")]:
        del sys.modules[mod]
    import hachi.gateway.in_process_runtime  # noqa: F401

    assert "hachi.cli.main" not in sys.modules


def test_resident_worker_slot_is_visible_to_readiness_probe(monkeypatch) -> None:
    """The probe must observe a LATE write to the worker slot across the module seam.

    Guards §5 decision 2: a `from … import _GATEWAY_RESIDENT_WORKER` in cli/main
    would snapshot None and this test would fail.
    """
    from hachi.gateway import in_process_runtime as runtime_mod

    monkeypatch.setattr(runtime_mod, "_GATEWAY_RESIDENT_WORKER", object(), raising=False)
    from hachi.cli.main import _gateway_readiness_probe

    ok, blockers, detail = _gateway_readiness_probe()
    assert "resident worker" not in " ".join(blockers).lower()
```

> Generate `EXPECTED_METHODS` once with the `awk` command in §3.7 and paste the literal set.
> A test that derives the set at runtime from the class under test asserts nothing.

Do **not** add a "does it still work" smoke test that boots a real agent — that belongs to
the existing suite, which already covers it across the 20 files in §3.8.

## 8. Acceptance criteria

- [ ] The characterization tests from §7 exist; `test_runtime_is_importable_from_gateway_without_cli`
      failed before the move with `ModuleNotFoundError`.
- [ ] `src/hachi/gateway/in_process_runtime.py` exists and
      `grep -c "^    def " src/hachi/gateway/in_process_runtime.py` → **79**.
- [ ] `awk 'NR>=244 && NR<=2599' src/hachi/cli/main.py | grep -c "class _InProcessGatewayRuntime"` → **0**;
      `wc -l src/hachi/cli/main.py` is ~3,150.
- [ ] `git diff --stat` for commit 2 shows a near-symmetric ~2,356-line move. **If the
      added block is materially larger than the removed block, you rewrote code — revert
      and redo it as a cut-and-paste.**
- [ ] `grep -rn '"hachi\.cli\.main\.' tests/` returns only CLI-command patch targets; every
      runtime-method patch target now reads `"hachi.gateway.in_process_runtime.…"`.
- [ ] For at least one re-pointed patch per touched test file, you temporarily broke the real
      function and confirmed the test went red (the anti-silent-pass check from §6 step 12).
- [ ] `uv run lint-imports` is green and no new `ignore_imports` entry was added.
- [ ] `grep -n "hachi.cli.main" src/hachi/gateway/control_plane.py` → nothing.
- [ ] Full-suite pass/fail counts are **identical** to the commit-1 baseline. Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change behaviour while moving code.** This is the primary boundary of this task.
  No renamed methods, no changed signatures, no new parameters, no reordered logic, no
  simplified conditionals, no "obviously safe" cleanups. If you spot a bug in the 2,356
  lines, **note it and leave it** — a bug fix inside this diff is unreviewable.
- Do not rename `_InProcessGatewayRuntime` (§5 decision 1).
- Do not split the class into 13 classes yet. The groups in §3.7 are a *map*, not this
  task's deliverable. Grouping is [T-43](T-43-collapse-control-plane-interfaces.md).
- Do not touch `core/runtime/resume.py` or the `pyproject.toml` exemption — that is
  [T-42](T-42-retire-core-cli-seam.md).
- Do not move `config`, `models`, or `permissions` (§3.6 — they are Typer commands).
- Do not move `_ACTIVE_RUNTIME`, `_start_gateway_server`, `_build_gateway_control_plane`,
  or `_gateway_readiness_probe`.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). In particular, a test that breaks after
  re-pointing a patch string is telling you the truth about the new module boundary.
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3). It
  reflows ~100 files and would bury the move in noise.
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
uv run lint-imports                          # layering must stay green
```

Report the **actual** pass/fail counts, and state explicitly that they match the pre-move
baseline. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — `mock.patch("hachi.cli.main.X")` silently tests nothing after a class moves modules

- **Symptom:** After extracting `_InProcessGatewayRuntime` from `cli/main.py` to
  `gateway/in_process_runtime.py`, ~200 `patch("hachi.cli.main.…")` sites across 20 test
  files kept passing while patching a name the code under test no longer resolves.
- **Root cause:** `unittest.mock.patch` binds a *string* to a *module namespace* at call
  time. Moving the consumer to a new module leaves the old patch a no-op; the real
  implementation runs and often happens to succeed against tmp paths.
- **Fix:** Re-point every patch target whose consumer moved; verify by temporarily breaking
  the real implementation and confirming the test goes red.
- **Avoid:** When you move a class between modules, grep the test tree for
  `patch("<old.module>.` and re-point it — a green suite after a module move proves nothing
  until you have seen at least one of those tests fail on purpose.
- **Locked by:** `tests/test_in_process_runtime_extraction.py` —
  `test_runtime_is_importable_from_gateway_without_cli`
```

## 12. Known traps

- **The `_GATEWAY_RESIDENT_WORKER` snapshot trap.** `from … import _GATEWAY_RESIDENT_WORKER`
  in `cli/main.py` binds `None` at import time and never updates. The readiness probe then
  reports the worker dead forever. Read it through the module object. Covered by
  `test_resident_worker_slot_is_visible_to_readiness_probe`.
- **The silent-patch trap (§3.8).** The most likely way this task ships broken with a green
  suite.
- **The false-positive trap (§3.6).** `config` / `models` / `permissions` are Typer commands.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Note that
  `test_runtime_is_importable_from_gateway_without_cli` deletes `hachi.cli*` entries from
  `sys.modules` — scope it to the `hachi.cli` prefix and never touch `chromadb`.
- **BB-5:** `paths.workspace_dir` does not exist — use `paths.skills_dir`. Several moved
  methods take `paths`; do not "fix" them to `workspace_dir` on the way past.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Several moved methods
  `getattr` around this; preserve the `getattr` calls verbatim even though CF-1 flags the
  idiom — changing them is a different task.
- **Merge conflicts.** `cli/main.py` is the highest-churn file in the repo. Land this on a
  short-lived branch, rebase daily, and land commit 2 the same day you write it.
