# T-56 · Make consent apply to every pack install path

|  |  |
|---|---|
| **Source finding** | CF-14 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P1** |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | `src/hachi/core/community_packs.py`, `src/hachi/cli/commands/skill.py`, possibly `src/hachi/core/og_pack.py`, `tests/test_community_pack_consent.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Hachi has **three** pack ecosystems. One of them (`og_pack`) implements genuinely
good trust engineering: a declared-scope manifest, a rendered consent sheet, a
mandatory confirmation prompt, and per-file sha256 integrity verification. The other
two implement **none of it** — and one of those, the community pack installer, writes
`.og` files into **the same directory** as the consent-gated one, from which the same
`SkillEngine` loads them by the same recursive glob.

When you are done, `hachi skill pack install user/repo` cannot copy a single `.og` file
onto disk without first showing the user what the pack declares and getting an explicit
"yes" — the same gate `hachi ogpack install` already enforces.

## 2. Why this matters

**This is a security asymmetry, not hygiene.** Read that sentence again before you
start, because it determines what a correct fix looks like.

Hachi's product thesis is governed, consented, auditable agency. `og_pack` is the
best expression of that thesis anywhere in the repo — it is the one place the codebase
says "declare your scopes, show the user, get a yes, verify the bytes." And it currently
guards the *least-used* of three install paths, while the path that accepts a GitHub
shorthand and an arbitrary archive URL from the internet has no gate at all.

The two installers are not sandboxed from each other. They resolve the same skills root
via the same function and both write into `<skills_dir>/packs/<name>/` (§3.4). A user
who installs one consent-gated pack and one ungated pack ends up with both loaded into
the same agent by the same loader, with no way to tell which one they actually approved.

If the fix you are about to write ends with "consent is now shown on the community
path too, but the two paths still have separate manifest formats, separate installers
and separate trust models" — you have done half the job. Read §5.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The three ecosystems

| Module | Lines | Manifest | Consent | sha256 | Scopes |
|---|---:|---|---|---|---|
| `src/hachi/core/og_pack.py` | 490 | `pack.toml` | **yes** | **yes** | **yes** |
| `src/hachi/core/community_packs.py` | 500 | `pack.json` | no | no | no |
| `src/hachi/core/skill_packs.py` | 126 | `manifest.json` | no | no | no |

The absence is mechanically verifiable, not a judgement call:

```bash
grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/community_packs.py   # -> 0
grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/skill_packs.py       # -> 0
grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/og_pack.py           # -> 52
```

`skill_packs.py` resolves its manifest at `_manifest_path` (`core/skill_packs.py:36-37`):

```python
def _manifest_path() -> Path:
    return _default_skills_root() / "manifest.json"
```

It only ever copies from `src/hachi/default_skills/` — packs the project itself ships —
so it is the *least* urgent of the three. Do not let it distract you (§9).

### 3.2 What og_pack actually implements

- **Scopes** — `OgPackManifest.scopes` (`core/og_pack.py:97`), parsed at `:148-153`,
  with widening detection at `:105-114`:

  ```python
      def scope_ids(self) -> frozenset[str]:
          return frozenset(s.id for s in self.scopes)

      def widened_scopes(self, other: OgPackManifest) -> frozenset[str]:
          """Scopes in ``other`` that are not in ``self`` — i.e., new permissions."""
          return other.scope_ids() - self.scope_ids()
  ```

- **Consent sheet** — `render_consent_sheet` (`core/og_pack.py:187`), and the
  update-time diff `render_scope_diff` (`:229`).
- **Integrity** — `sha256s` field (`:100`), parsed at `:162-163`, verified by
  `verify_pack_checksums` (`:315-326`) which is called *after* the copy and **raises**
  on mismatch (`install_ogpack_from_dir`, `:380-382`):

  ```python
      failures = verify_pack_checksums(pack_dir, manifest)
      if failures:
          raise ValueError(f"Pack integrity check failed: {failures}")
  ```

### 3.3 The command is `hachi skill pack install`, not `hachi skill install`

The review's command string is wrong. The community installer is a **sub-app** mounted
under `skill` (`cli/commands/skill.py:18-19`):

```python
# Sub-app for community skill packs (legacy GitHub-based packs).
_community_pack_app = typer.Typer(help="Install and manage community skill packs.")
skill_app.add_typer(_community_pack_app, name="pack")
```

The handler is `pack_install` (`cli/commands/skill.py:78-131`). Its argument help
(`:80-86`) documents the full accepted surface:

```python
    spec: str = typer.Argument(
        ...,
        help=(
            "Pack source: GitHub 'user/repo[@ref]', full archive URL (.tar.gz/.zip), "
            "single .og URL, or local directory path."
        ),
    ),
```

### 3.4 The bypass — both installers write to the SAME directory

**Gated path** — `ogpack_install` (`cli/commands/pack.py:23-110`). It resolves the
skills dir (`:41` → `_get_skills_dir()` → `get_hachi_paths().skills_dir`, `:19-20`),
parses `pack.toml`, runs `safe_extract` for archives (`:55-60`), renders the sheet, and
**requires an explicit yes before any copy** (`:76-83`):

```python
    sheet = render_consent_sheet(manifest_preview, update=is_update)
    console.print(sheet)

    if not yes:
        confirmed = typer.confirm("Proceed?", default=False)
        if not confirmed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)
```

Note `default=False` — an empty answer declines.

**Ungated path** — `pack_install` (`cli/commands/skill.py:98-106`). The entire body
before the copy is three lines:

```python
    from hachi.core.community_packs import install_pack
    from hachi.gateway.workspace import get_skills_dir

    skills_dir = get_skills_dir()
    try:
        info = install_pack(spec, skills_dir)
```

**No manifest parse. No hash check. No scope declaration. No prompt.**

The two `skills_dir` resolutions are the same value: `cli/commands/pack.py:20` calls
`get_hachi_paths().skills_dir` directly, and `gateway/workspace.py:31-36`
(`get_skills_dir`) returns `get_hachi_paths().skills_dir` after an `ensure_workspace()`.

And the two destinations are the same subtree:

- `og_pack.packs_dir` (`core/og_pack.py:262-266`) → `skills_dir / "packs"`, then
  `_pack_install_path` (`:269-270`) → `packs_dir(skills_dir) / pack_id`.
- `community_packs.install_pack` (`core/community_packs.py:385-386`):

  ```python
      packs_root = skills_dir / "packs"
      dest = packs_root / pack_name
  ```

**Identical destination.** And the loader does not distinguish them —
`SkillEngine.load_directory` (`og_engine/engine.py:540-552`) globs recursively:

```python
        for og_file in skills_dir.glob("**/*.og"):
            self.load_file(og_file)
```

called once at boot from `gateway/orchestrator.py:2804`. One gate present, one absent,
same directory, same loader, same agent.

### 3.5 What the ungated path will fetch

`install_pack` (`core/community_packs.py:361-451`) accepts four shapes. Two of them
reach the network:

- GitHub shorthand → `_github_archive_url` (`:110-111`), i.e.
  `https://github.com/{user}/{repo}/archive/refs/heads/{ref}.tar.gz`.
- Any URL, dispatched at `:423-432` to `.og` passthrough, `_extract_zip`, or
  `_extract_tar`.

To its credit the module is **not** careless about transport: `_validate_url`
(`:139-143`) runs `validate_outbound_url` (SSRF guard), `_default_fetcher` (`:151-161`)
uses `follow_redirects=False`, and both extractors enforce path-traversal and
archive-bomb caps (`:196-221`, `:262-320`). The gap is **not** archive safety. The gap
is that after all that careful transport hardening, the user is never asked and the
content is never attested.

### 3.6 Why it survived

`tests/test_pack_security.py` contains `TestZipExtractionSecurity`, `TestNodeProvenance`
and `TestMcpServerGate` (`:37`, `:89`, `:104`) — all about *archive* safety. Nothing
asserts that a community install prompts, and nothing asserts the two install paths
have comparable trust properties. `tests/test_p2_07a_ogpack.py` covers the ogpack side
in isolation.

## 4. Reproduce the failure

The asymmetry is provable from a shell without any network access.

```bash
# 1. The absence is total, not partial. Expect: 0, 0, 52.
grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/community_packs.py
grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/skill_packs.py
grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/og_pack.py

# 2. Only one installer prompts. Expect: exactly one hit, in cli/commands/pack.py.
grep -rn "typer.confirm" src/hachi/cli/commands/pack.py src/hachi/cli/commands/skill.py

# 3. Both resolve the same root and write the same subtree.
grep -n "skills_dir / \"packs\"" src/hachi/core/community_packs.py
grep -n "_PACKS_SUBDIR\|skills_dir / _PACKS_SUBDIR" src/hachi/core/og_pack.py
```

**You will see now:** (1) `0`, `0`, `52`; (2) one `typer.confirm("Proceed?", default=False)`
in `pack.py` and **nothing** in `skill.py`; (3) both modules composing `<skills_dir>/packs`.

**You should see after the fix:** grep (2) returns a consent gate on the community path
too — either its own prompt or, better, the shared one from §5.

**Live confirmation** (uses the local-directory branch — no network, no untrusted code):

```bash
mkdir -p /tmp/fake-pack && printf '@node test\n::dense\nhello\n' > /tmp/fake-pack/x.og
uv run hachi skill pack install /tmp/fake-pack
```

Today this prints `Installed pack fake-pack (1 skill(s))` with **no prompt** and the
file lands in `<skills_dir>/packs/fake-pack/x.og`. After the fix it must show a consent
sheet and refuse to copy without a confirmation.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> A community pack has **no scope declaration to consent to**. `pack.json` carries only
> `name` / `description` / `version` / `author` / `license` (documented at
> `core/community_packs.py:13-23`). So "show a consent sheet" is not a plumbing change —
> you must decide what the user is consenting *to*. Pick before you type:
>
> **(a) Community packs become ogpacks at fetch time — RECOMMENDED, and it is the
> review's own recommendation.** `community_packs` stops being an installer and becomes
> a *fetcher*: it downloads, extracts to a temp dir, synthesises a `pack.toml` from
> whatever `pack.json` provided plus a computed `sha256s` map over the fetched `.og`
> files, and hands the directory to `og_pack.install_ogpack_from_dir`. The CLI then
> renders the same consent sheet and asks the same question.
> *For:* one manifest format, one installer, one consent surface, one integrity story;
> the sha256 map is *computed from what was actually fetched*, so it attests
> "these are the exact bytes you approved" even when upstream declares nothing.
> *Against:* the synthesised manifest declares **no scopes** unless the pack ships them,
> so the sheet says "No integration scopes declared" (already a supported branch —
> `og_pack.py:208-209`). That is honest, not useless: the user still sees name, author,
> version, file count and an explicit yes/no.
>
> **(b) Add a second, simpler consent prompt to the community path only.**
> *For:* smallest diff, lands in a day. *Against:* it leaves three manifest formats and
> now *two* consent implementations to keep in sync — this is the exact generational
> layering CF-14 is about. You would be adding a fourth thing to consolidate later.
>
> **(c) Deprecate `hachi skill pack install` outright** and tell users to use
> `hachi ogpack install`.
> *For:* smallest surface. *Against:* it deletes the only installer that can fetch from
> a URL — `ogpack_install` takes a local path or archive only (`cli/commands/pack.py:25`).
> You would be removing capability, not consolidating it. Do not choose this **unless**
> you first move the fetching into the ogpack path, at which point you are doing (a).
>
> **Recommendation: (a).** The rest of this spec assumes it. If you choose otherwise,
> say so in the commit message and adapt §6/§7.

Target state:

1. A new fetch-only entry point in `core/community_packs.py`, e.g.:

   ```python
   def fetch_pack_to_dir(spec: str, dest: Path, *, fetcher: Any = None) -> Path:
       """Fetch *spec* into *dest* and return the directory holding the .og files.

       Performs no installation and writes nothing under skills_dir. Transport
       safety (net_guard, no-redirect, archive caps) is unchanged.
       """
   ```

   This is a **re-slice** of the existing `install_pack` body, not new logic: the
   URL resolution (`:409-418`), format dispatch (`:423-432`) and extractors are reused
   verbatim.

2. A manifest synthesiser that produces a real `OgPackManifest` from the fetched tree:

   ```python
   def synthesise_pack_manifest(pack_dir: Path, *, source: str) -> OgPackManifest:
       """Build an OgPackManifest for a community pack.

       Reads pack.json when present for id/semver/description/author, declares
       NO scopes (community packs cannot request any), and computes sha256s over
       every .og file actually fetched.
       """
   ```

   The `sha256s` map must be computed with the existing `og_pack._file_sha256`
   (`:309-312`) so `verify_pack_checksums` (`:315`) validates it unchanged.

3. `pack_install` (`cli/commands/skill.py:78`) becomes the same shape as
   `ogpack_install`: fetch → synthesise → `render_consent_sheet` → `typer.confirm` →
   `install_ogpack_from_dir`. It gains a `--yes/-y` option matching
   `cli/commands/pack.py:26` so scripted installs stay possible.

4. `install_pack` is **kept** as a thin wrapper for one release with a deprecation
   note in its docstring, because it is public-ish surface and has tests. Do not delete
   it in this task (§9).

5. Observable outcome: `hachi skill pack install <anything>` prints a consent sheet and
   refuses to copy on a declined prompt; the installed pack carries a `pack.toml` and
   an `.installed.toml`, exactly like an ogpack; `hachi ogpack list` sees it.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Extract `fetch_pack_to_dir(spec, dest, *, fetcher=None)` in `core/community_packs.py`
   by lifting the body of `install_pack` (`:361-451`) up to and including the format
   dispatch. Leave `_validate_url`, `_default_fetcher`, `_extract_tar`, `_extract_zip`
   and `_install_local_dir` **untouched** — they are the safe part.
3. Re-implement `install_pack` as a call to `fetch_pack_to_dir` + the existing
   rename/meta logic, so its behaviour and return type are byte-identical. Run
   `uv run pytest tests/test_p2_12_agent_packs.py -q` to confirm nothing moved.
4. Add `synthesise_pack_manifest(pack_dir, *, source)` — in `core/community_packs.py`,
   importing `OgPackManifest` and `_file_sha256` from `core.og_pack`. (Direction check:
   `core → core` is fine; do not invert it.)
5. Rewrite `pack_install` (`cli/commands/skill.py:78-131`) to the fetch → synthesise →
   consent → install sequence, mirroring `cli/commands/pack.py:41-110`. Add `--yes/-y`.
   Extract the shared "render sheet, confirm or exit" block into one helper rather than
   copy-pasting it — two consent implementations is the bug, not the fix.
6. Keep the existing success output (`skill.py:124-131`) and the `--json` branch
   (`:108-122`) working — the `--json` path must still emit the same keys.
7. Run the regression test — it must now pass.
8. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_community_pack_consent.py` (**new**)
- **Test names:** `test_community_pack_install_refuses_without_consent` and
  `test_community_pack_install_computes_integrity_hashes`
- **It must assert:** the real, observed outcome on disk — that a **declined** prompt
  leaves `<skills_dir>/packs/` with no new `.og` file. Assert on the filesystem, not on
  a mock's call count: the whole finding is that files land on disk without a yes.
- **It must FAIL before your fix** with something like
  `AssertionError: expected no installed .og after declining, found [.../packs/fake-pack/x.og]`
  — because today no prompt is shown and the copy happens unconditionally.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.commands.skill import skill_app


def _make_source_pack(tmp_path: Path) -> Path:
    src = tmp_path / "src-pack"
    src.mkdir()
    (src / "x.og").write_text("@node test\n::dense\nhello\n", encoding="utf-8")
    (src / "pack.json").write_text('{"name": "fake-pack", "version": "1.0.0"}', encoding="utf-8")
    return src


def test_community_pack_install_refuses_without_consent(tmp_path, monkeypatch) -> None:
    """Declining the consent prompt must leave nothing on disk.

    Regression: `hachi skill pack install` copied .og files into the SAME
    <skills_dir>/packs/ tree that the consent-gated ogpack installer uses, with
    no manifest parse, no hash check and no prompt.
    """
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setattr(
        "hachi.gateway.workspace.get_skills_dir", lambda: skills_dir
    )

    src = _make_source_pack(tmp_path)
    # "n" answers the consent prompt. Before the fix there is no prompt at all
    # and the input is simply ignored — which is exactly what this test catches.
    result = CliRunner().invoke(skill_app, ["pack", "install", str(src)], input="n\n")

    installed = list(skills_dir.rglob("*.og"))
    assert installed == [], (
        f"expected no installed .og after declining, found {installed}. "
        "The community pack installer must not write to skills_dir without consent."
    )
    assert result.exit_code == 0


def test_community_pack_install_computes_integrity_hashes(tmp_path, monkeypatch) -> None:
    """An accepted install must leave a verifiable pack.toml behind."""
    from hachi.core.og_pack import get_installed_manifest, verify_pack_checksums

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setattr(
        "hachi.gateway.workspace.get_skills_dir", lambda: skills_dir
    )

    src = _make_source_pack(tmp_path)
    result = CliRunner().invoke(skill_app, ["pack", "install", str(src)], input="y\n")
    assert result.exit_code == 0

    manifest = get_installed_manifest("fake-pack", skills_dir)
    assert manifest is not None, "community install must leave an OgPackManifest"
    assert manifest.sha256s, "sha256s must be computed over the fetched .og files"
    assert verify_pack_checksums(skills_dir / "packs" / "fake-pack", manifest) == []
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> In particular: check you are really pointing `get_skills_dir` at `tmp_path`. If the
> test writes into the developer's real `~/.hachi/skills`, it will pass for the wrong
> reason and pollute the machine.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_community_pack_install_refuses_without_consent` failed before the fix.
- [ ] `grep -c 'sha256\|consent\|scope\|checksum' src/hachi/core/community_packs.py` is **> 0**.
- [ ] Exactly **one** consent-rendering + confirmation implementation exists; both CLI installers call it. `grep -rn "typer.confirm" src/hachi/cli/commands/` shows the shared helper, not two copies.
- [ ] `hachi skill pack install <local dir>` prompts, and declining installs nothing.
- [ ] `hachi skill pack install --yes <local dir>` still installs non-interactively (scripts keep working).
- [ ] A community-installed pack is visible to `hachi ogpack list` and passes `verify_pack_checksums`.
- [ ] `install_pack` still exists and its existing tests pass unchanged.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch `core/skill_packs.py`.** It is the third ecosystem and it *looks* like
  the same problem, so it is exactly what you will drift into. It only copies from
  `src/hachi/default_skills/` — packs this repo ships and the user already installed by
  installing Hachi. There is no untrusted input, so there is nothing to consent to.
  Note it as a follow-up for the manifest-format consolidation and move on. (It is also
  in the mypy strict gate — `mypy-strict-gate.ini` lists `src/hachi/core/skill_packs.py`
  — so an idle edit there can turn the gate red for no benefit.)
- **Do not delete `install_pack`.** It is imported by `cli/commands/skill.py` and
  covered by existing tests; a deprecation wrapper is this task's contract. Deleting it
  is a separate, later change.
- **Do not "improve" the archive extractors.** `_extract_tar` / `_extract_zip` /
  `_validate_url` / `_default_fetcher` are the *hardened* part of this module
  (traversal checks, bomb caps, SSRF guard, no redirects). Touching them widens the
  blast radius of a consent change into a security change with no test coverage of
  your own. Move them, don't edit them.
- **Do not invent a scope vocabulary for community packs.** `describe_scope` and the
  scope ids are an ogpack concept; synthesising fake scopes so the sheet "looks fuller"
  would be fabricating a security claim — the precise failure mode this audit exists to
  stop. "No integration scopes declared" is the honest sheet.
- **Do not add a runtime dependency.** Everything needed (`hashlib`, `tomllib`,
  `typer`, `httpx`) is already imported by one of the two modules.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. This changes an install path that several test modules exercise
(`tests/test_p2_07a_ogpack.py`, `tests/test_p2_07b_pack_index.py`,
`tests/test_p2_12_agent_packs.py`, `tests/test_pack_security.py`); a scoped run will
miss the interaction between the new consent gate and the existing non-interactive
install tests. Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Community pack installs bypassed the entire consent/integrity gate

- **Symptom:** `hachi skill pack install user/repo` fetched an archive from the internet and copied `.og` files into `<skills_dir>/packs/<name>/` with no consent sheet, no confirmation prompt, no declared scopes and no content hashes — while `hachi ogpack install` writing to the *same* directory required all four.
- **Root cause:** Two independently-grown installers. `core/og_pack.py` (`pack.toml`) implemented scopes, `render_consent_sheet`, `typer.confirm(default=False)` and `verify_pack_checksums`; `core/community_packs.py` (`pack.json`) implemented none of them (`grep -c 'sha256|consent|scope|checksum'` returned 0). Both resolved `skills_dir` via `get_hachi_paths().skills_dir` and both wrote to `skills_dir/"packs"`, and `SkillEngine.load_directory` globs `**/*.og`, so consented and unconsented skills loaded identically.
- **Fix:** `community_packs` demoted to a fetcher (`fetch_pack_to_dir`) plus a manifest synthesiser that computes `sha256s` over the fetched files; the CLI now runs the shared consent helper before handing off to `install_ogpack_from_dir`. One consent implementation, used by both commands.
- **Avoid:** when two code paths write to the same destination, they must share the same gate. A security control that guards one of N paths to a shared resource is decoration — assert the *outcome on disk*, not that the prompt function was called.
- **Locked by:** `tests/test_community_pack_consent.py` — `test_community_pack_install_refuses_without_consent`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-5:** `paths.workspace_dir` does not exist — use `paths.skills_dir`. Both
  installers already do; keep it that way.
- **Two different accessors, one value.** `cli/commands/pack.py:19-20` calls
  `get_hachi_paths().skills_dir` directly; `cli/commands/skill.py:99` imports
  `get_skills_dir` from `hachi.gateway.workspace`, which additionally calls
  `ensure_workspace()` when the dir is missing (`gateway/workspace.py:31-36`). If you
  unify the two commands, keep the `ensure_workspace()` side effect on the community
  path or a first-ever install on a clean machine will fail.
- **Monkeypatch the right symbol.** `cli/commands/skill.py` imports `get_skills_dir`
  *inside* the function body (`:99`), so patching
  `hachi.gateway.workspace.get_skills_dir` works, but patching an attribute on the
  `skill` module does not. Get this wrong and your test silently writes to the real
  `~/.hachi`.
- **`typer.confirm` in tests:** `CliRunner().invoke(..., input="n\n")` is the pattern.
  A test that forgets the `input=` will hang or read EOF — mirror how
  `tests/test_p2_07a_ogpack.py` drives `ogpack_install`.
- **The `.installed.toml` sidecar** (`og_pack.py:259`, written at `:273-283`) is what
  `get_installed_manifest` / `list_ogpacks` read. If you install via
  `install_ogpack_from_dir` you get it for free; if you hand-roll the copy you will
  produce a pack that `hachi ogpack list` cannot see.
- **Import direction:** `hachi.core.community_packs` importing `hachi.core.og_pack` is
  fine. Do **not** make `og_pack` import `community_packs` — and neither may import
  `hachi.cli` or `hachi.gateway` (import-linter contract in `pyproject.toml`
  `[tool.importlinter]`). The consent helper you extract must therefore live in the
  **CLI** layer, not in `core`.
