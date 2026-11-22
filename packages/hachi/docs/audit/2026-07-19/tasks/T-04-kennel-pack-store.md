# T-04 · Make the kennel pack store actually install packs

|  |  |
|---|---|
| **Source finding** | CF-1 #1 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · corrected by [CORRECTIONS.md](CORRECTIONS.md) §7 |
| **Severity** | P0 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~4–6 hours |
| **Difficulty** | Medium |
| **Files you will touch** | `src/hachi/cli/main.py`, `src/hachi/core/bundled_packs.py` (docstring only), `tests/test_kennel_install.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

The skill kennel is a complete lie end-to-end. `GET /skills/kennel` never returns a
single bundled pack (the import that would load them names a module that does not
exist), and `POST /skills/add` returns `{"ok": True, "installed": True}` **without
installing anything** — it never even looks at the `kennel_id` it was given. Five real
packs ship inside the wheel at `src/hachi/packs/` and a fully-working install function
sits unused in `src/hachi/core/bundled_packs.py`.

When you are done: the kennel lists the five real bundled packs, clicking **Add**
installs the pack's `.og` files into the user's skills directory, and any failure on
either path is a `logger.warning` — not a swallowed exception behind a success toast.

## 2. Why this matters

This is the single most user-visible instance of CF-1's "report success, degrade
silently" idiom. A user browses the kennel, clicks Add, sees *"Added Research Agent —
it's ready to use"*, and then finds the skill is not there. That is worse than a
missing feature: it is a feature that lies. The fix has **two halves** and neither is
optional — (1) make the install actually happen, and (2) make the next failure LOUD, so
this class of breakage is discovered by the system rather than by a user filing a bug.

Note the review says the module "doesn't exist anywhere." That is **wrong** — see
[CORRECTIONS.md](CORRECTIONS.md) §7. You are re-pointing an import and calling an
existing function, not writing a new subsystem.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The list path imports a module that does not exist

`src/hachi/cli/main.py:2225-2247` — `_InProcessGatewayRuntime.get_kennel`:

```python
    def get_kennel(self) -> list[dict]:
        """Return the skill kennel catalogue (GET /skills/kennel).

        Returns bundled community packs when available, otherwise falls back to
        the agent's installed skill index so the browse panel is never empty.
        """
        try:
            from hachi.og_engine.bundled_packs import list_bundled_packs

            packs = list_bundled_packs()
            if packs:
                return [
                    {
                        "id": p.get("id") or p.get("name", ""),
                        ...
                    }
                    for p in packs
                ]
        except Exception:
            pass
```

Broken on **two** counts:

1. **Wrong package.** The module is `hachi.core.bundled_packs`, not
   `hachi.og_engine.bundled_packs`.
2. **Wrong symbol.** `list_bundled_packs` exists **nowhere in `src/`** — not even in
   the correct module. (It is named only in that module's own stale docstring, see 3.3.)

The `except Exception: pass` at `:2246-2247` swallows the `ModuleNotFoundError`, so
`get_kennel` always silently falls through to the "installed skills" fallback at
`:2249-2264`. On a fresh install with no user skills, that returns `[]`.

### 3.2 The install path installs nothing

`src/hachi/cli/main.py:2266-2291` — `add_skill_from_kennel`:

```python
    def add_skill_from_kennel(self, kennel_id: str) -> dict:
        """Install a skill from the kennel (POST /skills/add).
        ...
        """
        if not kennel_id.strip():
            raise GatewayProtocolError("kennel_id cannot be empty")

        # Ask the agent to re-index skills (picks up newly activated packs).
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            try:
                agent.skill_engine.reindex()
            except Exception:
                pass

        return {"ok": True, "kennel_id": kennel_id, "installed": True}
```

Dead on **three** counts:

1. `kennel_id` is validated non-empty at `:2279-2280` and then **never used again**.
   Nothing is installed.
2. `agent.skill_engine.reindex()` at `:2287` — **`SkillEngine` has no `reindex`
   method.** Verified: `grep -rn "def reindex" src/hachi/og_engine/engine.py` returns
   nothing. The public re-index mechanism is `SkillEngine.load_directory(skills_dir)`
   (`src/hachi/og_engine/engine.py:540`). So `:2287` raises `AttributeError` on every
   call and `:2288-2289` swallows it.
3. The return value is a hardcoded success literal.

### 3.3 The real module — and it has zero production callers

`src/hachi/core/bundled_packs.py`. Real exports:

| Symbol | Line | Signature |
|---|---|---|
| `list_bundled_pack_dirs` | `:30` | `() -> list[Path]` |
| `list_bundled_manifests` | `:40` | `() -> list[OgPackManifest]` |
| `install_bundled_pack` | `:52` | `(pack_id: str, skills_dir: Path, *, confirm: bool = False) -> tuple[OgPackManifest, list[str]] \| None` |
| `get_bundled_consent_sheet` | `:75` | `(pack_id: str) -> str` |

Its own module docstring is stale and names the nonexistent function
(`src/hachi/core/bundled_packs.py:4`):

```python
:func:`list_bundled_packs` enumerates them; :func:`install_bundled_pack` copies
```

**No function in this module has any production caller.** Verified:

```
$ grep -rn "install_bundled_pack\|list_bundled_manifests\|list_bundled_pack_dirs\|get_bundled_consent_sheet" src/
src/hachi/core/bundled_packs.py:...   (definitions and internal use only)
```

Every other hit is in `tests/test_p2_12_agent_packs.py`. The whole subsystem is dead,
not just the import.

`install_bundled_pack` delegates to `install_ogpack_from_dir`
(`src/hachi/core/og_pack.py:334-341`), which returns
`tuple[OgPackManifest, list[str]]` and writes into `skills_dir/packs/<id>/`.

### 3.4 The manifest shape you must adapt to the wire format

`src/hachi/core/og_pack.py:77-103` — `OgPackManifest` is a
`@dataclass(frozen=True, slots=True)`:

```python
    id: str
    semver: str = "0.0.0"
    min_agent_version: str = ""
    scopes: tuple[PackScope, ...] = ()
    fs_paths: tuple[str, ...] = ()
    schedule_budget: ScheduleBudget = field(default_factory=ScheduleBudget)
    sha256s: dict[str, str] = field(default_factory=dict)
    signature: str = ""
    description: str = ""
    author: str = ""
```

**There is no `name` field and no `tags` field.** The wire contract the frontend reads
is `{id, name, description, version, tags}` (see 3.6). You must map:
`name` ← derive from `id` (e.g. `"crm-agent"` → `"Crm Agent"`, or a small explicit
title map), `version` ← `semver`, `tags` ← `[]` or scope ids.

### 3.5 The five real packs

```
$ ls src/hachi/packs/
crm-agent  finance-agent  inbox-sentinel  meeting-copilot  research-agent
```

`src/hachi/packs/crm-agent/pack.toml`:

```toml
id = "crm-agent"
semver = "1.0.0"
min_agent_version = "0.1.0"
description = "Relationship management: tracks contacts, captures interactions, writes person nodes, answers 'catch me up on X'."
author = "Hachi Team"
```

### 3.6 The full user-visible chain (cite this in your PR)

| Layer | Anchor |
|---|---|
| CLI wiring | `src/hachi/cli/main.py:3019-3020` — `get_kennel=support.get_kennel`, `add_skill=support.add_skill_from_kennel` |
| Control plane ctor | `src/hachi/gateway/control_plane.py:145` (`get_kennel` param), `:223` (`self._get_kennel = get_kennel`) |
| Control plane methods | `src/hachi/gateway/control_plane.py:1183-1187` (`kennel()`), `:1189-1192` (`add_skill()`) |
| REST | `src/hachi/gateway/fastapi_app.py:1958-1961` (`GET /skills/kennel`), `:1964-1970` (`POST /skills/add`) |
| Frontend loader | `frontend/src/lib/data/domains/skills.ts:138` (`loadKennel`), `:164-178` (`addSkillLive`) |
| Frontend UI | `frontend/src/routes/skills.tsx:127` (`KennelCard`), `:184-188` (`kennel` state + `useEffect`) |

`frontend/src/lib/data/domains/skills.ts:176-179` is where the lie surfaces:

```ts
    await apiSend<unknown>("POST", "/skills/add", { kennel_id: kennelId });
    // Refresh installed skills + kennel from gateway
    await Promise.all([loadSkills(), loadKennel()]);
    showToast(`Added ${label} — it's ready to use`, "success");
```

The POST returns HTTP 200 with `installed: true`, so the success toast fires. Nothing
was installed.

### 3.7 Why the tests did not catch it

- `tests/test_p2_12_agent_packs.py:137-190` tests `hachi.core.bundled_packs` **directly**
  and is green — but nothing in `src/` imports that module, so it is a green orphan.
- `tests/test_g1_wave1.py:247-256` stubs the handler entirely:

  ```python
  def test_kennel_returns_list() -> None:
      stub = [
          {"id": "research", "name": "Deep Research", "description": "", "version": "", "tags": []}
      ]
      client = _app(get_kennel=lambda: stub)
  ```

  It never touches `_InProcessGatewayRuntime.get_kennel`. Same for
  `test_skill_add_returns_ok` at `:266-274`, which supplies its own `_stub`.

This is CF-1's structural point in one place: **the units pass; the wiring is absent.**

## 4. Reproduce the failure

The import failure is directly reproducible:

```bash
uv run python -c "import hachi.og_engine.bundled_packs"
```

**You will see now:**

```
ModuleNotFoundError: No module named 'hachi.og_engine.bundled_packs'
```

**You should see after the fix:** nothing — because that import is gone. Instead:

```bash
uv run python -c "from hachi.core.bundled_packs import list_bundled_manifests; print([m.id for m in list_bundled_manifests()])"
# ['crm-agent', 'finance-agent', 'inbox-sentinel', 'meeting-copilot', 'research-agent']
```

The *install* failure is **not** reproducible from a shell — `add_skill_from_kennel`
returns HTTP 200 and writes nothing, producing no output anywhere. The code-reading
proof is §3.2: `kennel_id` is used only in the validity check at `:2279` and in the
returned dict at `:2291`; there is no call to any install function in the method body.
Confirm it yourself:

```bash
# the whole method body — read it; there is no install call in it
sed -n '2266,2292p' src/hachi/cli/main.py
```

Confirm `reindex` is absent:

```bash
grep -rn "def reindex" src/hachi/og_engine/engine.py   # no output
```

## 5. What "fixed" looks like

**`get_kennel()`** returns the five bundled packs, built from real manifests:

```python
    def get_kennel(self) -> list[dict]:
        try:
            from hachi.core.bundled_packs import list_bundled_manifests

            manifests = list_bundled_manifests()
            if manifests:
                return [
                    {
                        "id": m.id,
                        "name": _pack_display_name(m.id),
                        "description": m.description,
                        "version": m.semver,
                        "tags": sorted(m.scope_ids()),
                    }
                    for m in manifests
                ]
            logger.warning(
                "get_kennel: no bundled pack manifests found under hachi/packs — "
                "the kennel will fall back to installed skills"
            )
        except Exception:
            logger.warning("get_kennel: bundled pack listing failed", exc_info=True)
```

Note the swallow is replaced by `logger.warning(..., exc_info=True)`, and the
*empty-but-no-exception* case gets its own warning. Keep the installed-skills fallback
below it — do not delete it (CLAUDE.md Rule 3).

`_pack_display_name` is a tiny module-level helper in `cli/main.py`:
`"crm-agent"` → `"Crm Agent"` via `id.replace("-", " ").title()`. Do not invent a
translation table unless a pack id titles badly.

**`add_skill_from_kennel()`** actually installs:

```python
    def add_skill_from_kennel(self, kennel_id: str) -> dict:
        if not kennel_id.strip():
            raise GatewayProtocolError("kennel_id cannot be empty")

        from hachi.core.bundled_packs import install_bundled_pack
        from hachi.core.paths import get_hachi_paths

        skills_dir = get_hachi_paths().skills_dir       # BB-5: NOT paths.workspace_dir
        result = install_bundled_pack(kennel_id.strip(), skills_dir, confirm=False)
        if result is None:
            raise GatewayProtocolError(f"unknown kennel pack: {kennel_id!r}")
        manifest, installed_files = result

        # Re-index so the newly installed .og files are visible this session.
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            try:
                agent.skill_engine.load_directory(skills_dir)
            except Exception:
                logger.warning(
                    "add_skill_from_kennel: re-index after installing %r failed; "
                    "the pack is on disk but will not be visible until restart",
                    kennel_id,
                    exc_info=True,
                )

        return {
            "ok": True,
            "kennel_id": manifest.id,
            "installed": True,
            "files": installed_files,
        }
```

Three things to notice:

- `install_bundled_pack` returning `None` becomes a `GatewayProtocolError`, i.e. an HTTP
  error the frontend's `catch` at `skills.ts:182-184` already turns into a `"blocked"`
  toast. **An unknown pack must no longer report success.**
- The re-index call is corrected to the method that exists (`load_directory`), and its
  failure is a warning, not `pass`.
- `installed: True` is now only reachable after a real install.

**Wire contract:** the added `files` key is additive; `frontend/.../skills.ts:176`
ignores the response body entirely. No frontend change is required, and **no OpenAPI
regeneration is required** because no route signature changed. (If you change
`SkillAddRequest`/response models, BB-4 applies — regenerate.)

## 6. Steps

1. Write the regression test from §7 first. Run it. Watch it fail.
2. Fix the stale docstring at `src/hachi/core/bundled_packs.py:4` — replace
   `list_bundled_packs` with `list_bundled_manifests`. (One line; it is what sent the
   original author to a nonexistent symbol.)
3. Add `_pack_display_name(pack_id: str) -> str` near the other module-level helpers in
   `src/hachi/cli/main.py`.
4. Rewrite the `try` block in `get_kennel` (`cli/main.py:2231-2247`) per §5. Keep the
   installed-skills fallback that follows it.
5. Rewrite `add_skill_from_kennel` (`cli/main.py:2282-2291`) per §5.
6. Run the test. Watch it pass.
7. Run `uv run python scripts/preflight.py`. Report real counts.
8. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_kennel_install.py` (new)
- **Test names:** `test_get_kennel_lists_real_bundled_packs`,
  `test_add_skill_from_kennel_actually_installs_og_files`,
  `test_add_skill_from_kennel_rejects_unknown_pack`
- **It must assert:** real filesystem state — that `.og` files exist under
  `skills_dir/packs/<id>/` after the call. **Do not assert on the returned dict alone**;
  today's broken code already returns `installed: True`, so a dict-shape assertion
  passes against the bug.
- **It must FAIL before your fix** with, respectively:
  `AssertionError: assert 'crm-agent' in set()` (the kennel list is empty because the
  import dies), and `AssertionError: assert False` on `installed_dir.exists()` (nothing
  was written).

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path
from unittest.mock import patch

import pytest

from hachi.cli.main import _InProcessGatewayRuntime
from hachi.core.paths import HachiPaths


@pytest.fixture
def runtime_and_paths(tmp_path: Path):
    paths = HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
    paths.skills_dir.mkdir(parents=True, exist_ok=True)
    # Construct the runtime the way the existing CLI tests do — check
    # tests/test_backup_restore.py for the established patch target/shape.
    runtime = _InProcessGatewayRuntime()      # adapt to the real ctor
    with patch("hachi.cli.main.get_hachi_paths", return_value=paths):
        yield runtime, paths


def test_get_kennel_lists_real_bundled_packs(runtime_and_paths):
    runtime, _ = runtime_and_paths
    ids = {item["id"] for item in runtime.get_kennel()}
    # These five ship in the wheel at src/hachi/packs/.
    assert {"crm-agent", "research-agent", "inbox-sentinel"} <= ids
    crm = next(i for i in runtime.get_kennel() if i["id"] == "crm-agent")
    assert crm["description"]          # real manifest text, not ""
    assert crm["version"] == "1.0.0"   # from pack.toml `semver`


def test_add_skill_from_kennel_actually_installs_og_files(runtime_and_paths):
    runtime, paths = runtime_and_paths
    result = runtime.add_skill_from_kennel("inbox-sentinel")
    assert result["ok"] is True
    installed = paths.skills_dir / "packs" / "inbox-sentinel"
    assert installed.exists(), "pack directory was not created — nothing installed"
    assert any(p.suffix == ".og" for p in installed.iterdir())


def test_add_skill_from_kennel_rejects_unknown_pack(runtime_and_paths):
    from hachi.gateway.control_plane import GatewayProtocolError

    runtime, _ = runtime_and_paths
    with pytest.raises(GatewayProtocolError):
        runtime.add_skill_from_kennel("no-such-pack")
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The third test is the important one: today `add_skill_from_kennel("no-such-pack")`
returns `{"ok": True, "installed": True}`. Confirm that with your eyes before fixing.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix.
- [ ] `grep -rn "og_engine.bundled_packs" src/` returns **no** hits.
- [ ] `grep -rn "list_bundled_packs" src/` returns **no** hits (including the docstring).
- [ ] `GET /skills/kennel` on a fresh profile returns 5 items with non-empty
      `description` and `version`.
- [ ] `POST /skills/add` with an unknown id returns an HTTP error, not `ok: True`.
- [ ] Both former `except Exception: pass` sites in `get_kennel` /
      `add_skill_from_kennel` are now `logger.warning(..., exc_info=True)`.
- [ ] `tests/test_p2_12_agent_packs.py` still passes untouched.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not build a remote/community pack registry.** The `add_skill_from_kennel`
  docstring says *"For community packs it downloads and installs the .og file"* — there
  is no download code and no registry URL. Ship the bundled-pack path; leave the
  docstring's community half as a documented gap or delete that sentence. **Adding an
  HTTP fetch here is a new network surface and a new dependency decision** (CLAUDE.md
  Rule 3).
- **Do not touch the consent flow.** `get_bundled_consent_sheet` exists and the frontend
  has a `kennelConsent` overlay (BB-79), but wiring consent into the install path is
  owned by [T-56](T-56-pack-consent-every-install-path.md). Your install path must not
  *bypass* consent in a way that makes T-56 harder — leave the frontend's consent overlay
  behaviour exactly as it is and let T-56 connect it.
- Do not fix the other `getattr`-against-own-type sites you will notice in
  `cli/main.py` (e.g. `getattr(agent, "reindex_skills", None)` at `:1313` and `:1389` —
  `reindex_skills` does not exist either). Those belong to
  [T-14](T-14-ban-getattr-own-types.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — Kennel "Add" reported success while installing nothing, for every user

- **Symptom:** `GET /skills/kennel` never listed a bundled pack, and clicking **Add**
  in the web UI showed "Added <pack> — it's ready to use" while no file was written.
  Requesting a pack id that does not exist also returned `{"ok": true, "installed": true}`.
- **Root cause:** three independent dead links in one feature.
  (1) `_InProcessGatewayRuntime.get_kennel` imported
  `hachi.og_engine.bundled_packs.list_bundled_packs` — wrong *package* (the module is
  `hachi.core.bundled_packs`) **and** a symbol that exists nowhere in `src/`. The
  `ModuleNotFoundError` was swallowed by `except Exception: pass`.
  (2) `add_skill_from_kennel` validated `kennel_id` as non-empty and then never used
  it — no install call existed in the method — before returning a hardcoded
  `{"ok": True, "installed": True}`.
  (3) Its re-index call was `agent.skill_engine.reindex()`; `SkillEngine` has no
  `reindex` method, so that raised `AttributeError` into another `except: pass`.
  No function in `hachi/core/bundled_packs.py` had any production caller at all.
- **Fix:** re-pointed the listing at `list_bundled_manifests()`, called the existing
  `install_bundled_pack(pack_id, get_hachi_paths().skills_dir)` (BB-5) on the add path,
  raised `GatewayProtocolError` on an unknown pack id, corrected the re-index call to
  `skill_engine.load_directory(skills_dir)`, and replaced both `except Exception: pass`
  swallows with `logger.warning(..., exc_info=True)`.
- **Avoid:** a `try: from x import y / except Exception: pass` around a *feature's only
  entry point* is not graceful degradation — it is a permanently disabled feature that
  reports success. Grep that the module AND the symbol exist before trusting a bare
  swallow, and never return a hardcoded success literal from a handler that performed
  no work. A unit test that stubs the handler (`_app(get_kennel=lambda: stub)`) proves
  nothing about wiring.
- **Locked by:** `tests/test_kennel_install.py` —
  `test_add_skill_from_kennel_actually_installs_og_files`,
  `test_add_skill_from_kennel_rejects_unknown_pack`
```

## 12. Known traps

- **BB-5:** `paths.workspace_dir` does not exist — use `get_hachi_paths().skills_dir`.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-4:** any gateway *route or model* change ⇒ regenerate the OpenAPI spec **and**
  the frontend API types, or CI fails. The fix in §5 changes neither, so you should not
  need this — but if you alter `SkillAddRequest` (`fastapi_app.py:305`), you do.
- **`install_bundled_pack` writes to a real directory.** It has no dry-run. Your test
  MUST pass a `tmp_path`-backed `skills_dir` or it will write into the developer's real
  `~/.hachi` data dir. `get_hachi_paths()` (`core/paths.py:117-124`) has **no env
  override** — patch it (`patch("hachi.cli.main.get_hachi_paths", ...)`, the pattern
  used throughout `tests/test_backup_restore.py`).
- **`OgPackManifest` is frozen + slotted** (`og_pack.py:77`) — you cannot attach a
  `name` attribute to it. Map to the wire dict instead.
- The `_agents` map is empty until a session boots, so the re-index branch is a no-op
  in a bare unit test. That is correct — assert on the filesystem, not the re-index.
