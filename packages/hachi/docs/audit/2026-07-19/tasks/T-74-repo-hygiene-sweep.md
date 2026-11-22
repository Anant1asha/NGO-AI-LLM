# T-74 · Repo hygiene: name the seven design trees, narrow the blanket globs, and fix the packaging leak

|  |  |
|---|---|
| **Source finding** | CF-20 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md). **Five of its claims are wrong — read §3.1 first.** |
| **Severity** | P3 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none — listed as **independent, safe to run in parallel with anything** |
| **Blocks** | nothing |
| **Effort** | ~2 days |
| **Difficulty** | Low mechanically · **High in judgement** — several items are irreversible deletions of the user's design source material. Read §9 before you delete anything. |
| **Files you will touch** | `.gitignore`, `pyproject.toml`, root `hachi` / `hachi.bat`, `docs/DECISIONS.md`, `tests/`, `docs/bug-bank.md` |

---

## 1. Brief

Seven design-tool trees totalling **52.6 MB** sit at the repo root, invisible to
`git status` — not because anyone ignored them by name, but because `.gitignore` blanket-ignores
`*.png`/`*.jpg`/`*.jpeg`/`*.gif`/`*.html` and `node_modules/`. That blanket is a standing trap
for any future tracked HTML or image (there is exactly one negation in the whole file). A
tracked `design-system/` duplicates frontend primitives that are 22 days and 452 lines ahead
of it. A stale `dist/` sdist is 45× its own wheel — because it swept in 108 MB of agent
worktrees. And two `[project.optional-dependencies]` extras are character-for-character
no-ops.

When you are done, each design tree is ignored **by name**, the globs are narrowed to where
images actually live, the packaging leak is understood, the no-op extras are resolved, and
**nothing the user still needs has been deleted.**

## 2. Why this matters

Root noise is an onboarding tax and an accidental-commit risk, but the sharp edge here is the
blanket `*.html` / `*.png` rule. It is not filtering noise — it is **silently deciding what
can be tracked**. Today it hides 52.6 MB. Tomorrow it eats a fixture, a golden screenshot, a
docs asset, and the author gets no signal at all: `git add` succeeds, `git status` stays
clean, the file never lands. The single `!frontend/index.html` negation is the fossil of that
happening once already.

The packaging leak is the one with a user-visible consequence: an sdist that ships 108 MB of
agent worktrees is not a distributable artifact.

**Read §9 before you touch anything.** This task's dominant failure mode is not doing too
little — it is deleting a design tree the user still needs. Those trees are *source material*,
not build output.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**

### 3.1 ⚠️ Corrections to the review — read these first

| The review says | Verified reality |
|---|---|
| "~52MB of **untracked** design trees" | They are **IGNORED**, not untracked. Not one appears in `git status --porcelain --untracked-files=all`. **`git clean` and `git status` will never surface them.** |
| four trees | **SEVEN**, totalling **52,598,381 B** |
| `.ds-sync/` "including a node_modules with esbuild/**playwright binaries**" | Playwright is present **only as JS packages + `.bin` shims — no browser binaries**. `esbuild.exe` is the *only* native executable in the tree. |
| `.ds-sync/` is 45MB | 46,304,767 B, and it is **100% `node_modules`** — `lib/` and `storybook/` are empty directories |
| "`frontend/.tanstack/` pollutes status" | **REFUTED.** It contains one empty `tmp/`; `du -sb` = **0 bytes**; it does **not** appear in `git status`. (It *is* unignored — a real forward-looking risk. Say both halves.) |
| "the base wheel ships every edge" | **OVERSTATED.** Base ships fastapi/uvicorn/typer/textual/chromadb/httpx — but **not** playwright, tavily, pypdf, python-docx, openpyxl, opentelemetry-*, python-pptx. **2 of 9 product extras are no-ops, not all.** |
| `dist/` holds "a stale 31MB sdist" | 32,324,009 B sdist **plus a 718,903 B wheel the review omits** |

### 3.2 The seven trees — sizes and the exact rule that hides each

```
.ds-sync/          46,304,767      .gitignore:92   node_modules/
ds-bundle/          3,354,765      .gitignore:59   *.html
.design-bundle/     1,041,223      .gitignore:82   .design-bundle/      <- the only by-name rule
Hachi Web UI/         898,120      .gitignore:59   *.html  (+ :55 *.png)
.stitch-review/       457,243      .gitignore:55   *.png
design-system/        392,995      TRACKED (65 files)
.design-sync/         149,268      .design-sync/.cache/.gitignore:1   *
                   -----------
                   52,598,381 B    (52.60 MB / 50.16 MiB)
```

Note the mechanism precisely: **the directories themselves are not ignored.** `git check-ignore -v .ds-sync` says *not ignored*. Every *file inside* matches a global glob, so the directory is empty as far as git is concerned. That is why they never appear in any status output.

`.ds-sync/` composition — `find .ds-sync -not -path '*/node_modules/*' -type f` returns
**zero** files. Heaviest packages:

```
12,795,822  @ts-morph          <- actually the largest, not playwright
12,701,224  playwright-core
11,671,045  @esbuild           (of which esbuild.exe = 11,670,528 — the only .exe/.dll/.node/.so)
 4,875,435  playwright
 1,481,221  ts-morph
```

`find .ds-sync -iname '*chrome*' -o -iname '*firefox*'` returns only
`reinstall_chrome_*.sh`/`.ps1` scripts and `firefox-*.svg` dashboard icons. **No browsers.**

### 3.3 The blanket globs — `.gitignore:52-60`

```
# ==========================================
# Hachi Runtime (user-generated, not source)
# ==========================================
*.png
*.jpg
*.jpeg
*.gif
*.html
!frontend/index.html
```

**`:60` is the only negation line in the entire file** (`grep -n '^!' .gitignore` → one hit).
Note the globals also silently swallow `*.jpg` / `*.jpeg` / `*.gif`, which the review does not
mention. And they explain only **3 of the 7** trees (`ds-bundle/`, `Hachi Web UI/`,
`.stitch-review/`) — **narrowing them is necessary but not sufficient.**

Other relevant anchors: `:10` `dist/` · `:79` `.hachi/` · `:82` `.design-bundle/` ·
`:83-89` seven `.claude/skills/*` entries · `:92` `node_modules/` · `:93` `frontend/.vite/`.

### 3.4 `design-system/` — tracked, and it is the stale copy

**65 tracked files.** Structure: `components/{core,feedback,hachi}`, `tokens/`, `assets/`,
`templates/leash-prompt/`, `ui_kits/{cli,tui,webapp}/`, `uploads/`. Each component ships as
`.jsx` + `.d.ts` + `.prompt.md`.

**Nine components overlap the frontend.** Seven pair with `frontend/src/components/ui/`:

| Component | design-system `.jsx` | frontend `.tsx` | differ? |
|---|---:|---:|---|
| `Button` | 87 | 87 | **yes** (same LOC, different content; `.jsx` vs `.tsx`) |
| `Input` | 37 | 120 | yes |
| `LoyalLoop` | 23 | 65 | yes |
| `StatusPill` | 36 | 47 | yes |
| `Switch` | 39 | 97 | yes |
| `Terminal` | 43 | 219 | yes |
| `Toast` | 35 | 117 | yes |
| **total** | **300** | **752** | **7 / 7 differ** |

Two more pair with `frontend/src/components/brand/`: `HachiMark`, `LeashPrompt`.
Three have no frontend counterpart at all: `Badge`, `Card`, `RunCard`.

Last commits: `design-system/` → **2026-06-27** (`cf83213` *"chore(structure): consolidate
brand/design assets"*); `frontend/src/components/ui/` → **2026-07-19** (`882852b`). **22 days
of divergence.** The frontend also carries **5** `.test.tsx` files across `ui/`+`brand/`; the
design-system has **0**.

**Conclusion: `frontend/` is the source of truth and the tracked copy is the stale one.**

### 3.5 `dist/` — stale, and the ratio is a real signal

```
dist/hachi_og-0.1.0.tar.gz            32,324,009 B   (30.83 MiB)   2026-06-20
dist/hachi_og-0.1.0-py3-none-any.whl     718,903 B                 2026-06-20
dist/.gitignore                                1 B   (a single `*`)
```

**29 days stale.** Doubly ignored: `.gitignore:10` `dist/` **and** a self-ignoring
`dist/.gitignore` containing `*`.

**⚠️ The 45× sdist-to-wheel ratio is a packaging bug, and it is confirmed.** Inspecting the
sdist's 10,664 files by uncompressed size:

```
113,687,731  .claude/worktrees      <- 97% of the archive's content
  2,336,300  src/hachi
    867,141  frontend/src
    845,882  uv.lock
    805,495  docs/audit
    305,144  docs/uat
    104,440  KNOWLEDGE_TRANSFER.md
```

**108 MB of agent worktrees shipped inside a Python source distribution.** (It also contains
`KNOWLEDGE_TRANSFER.md` and `docs/uat/`, deleted by the 2026-06-27 docs cleanup — more
evidence of staleness.) `pyproject.toml:155` declares only
`[tool.hatch.build.targets.wheel]`; there is **no `[tool.hatch.build.targets.sdist]`**
section, so hatchling defaults to a much broader include. `.claude/worktrees/` **is** ignored
today (via `.claude/.gitignore:4`), so this may already be fixed — **rebuild and measure
before concluding either way** (§6 step 7).

### 3.6 `frontend/.tanstack/` — REFUTED as pollution, real as a risk

```
frontend/.tanstack/
frontend/.tanstack/tmp/      <- empty
du -sb frontend/.tanstack    -> 0
```

Created 2026-06-20. **It does not appear in `git status`** — but only because it currently
holds no files. It is genuinely **unignored**: `.gitignore:93` covers `frontend/.vite/` only,
and `git check-ignore -v frontend/.tanstack` reports *not ignored*. The moment TanStack
Router writes a cache file there, it lands in `git status`. **Valid to fix; do not describe
it as a current problem.**

### 3.7 Root `hachi` shim — broken twice over on POSIX

```bash
#!/bin/bash
# Hachi CLI wrapper - delegates to the installed script in .venv
exec "$(dirname "$0")/.venv/Scripts/hachi" "$@"
```

Two independent failures:

1. **Line 3 hardcodes the Windows `.venv/Scripts/` layout.** POSIX venvs use `.venv/bin/`.
2. **⚠️ The file has CRLF line endings** (`cat -A` shows `^M$` on every line — the review
   misses this). A `#!/bin/bash\r` shebang makes the kernel look for an interpreter literally
   named `/bin/bash\r`, so POSIX fails with `bad interpreter: No such file or directory`
   **before line 3 is ever reached.**

`hachi.bat` is Windows-only by design:

```bat
@echo off
REM Hachi CLI wrapper - delegates to the installed script in .venv
"%~dp0.venv\Scripts\hachi.exe" %*
```

**There is no working POSIX entry point at the repo root.**

### 3.8 Extras — duplication verified exactly; "ships every edge" overstated

Parsed with `tomllib` (§4 gives the script):

```
base dependencies: 17

NO-OP extras (every pin already in base, character-for-character):
  memory        = ['chromadb>=1.5.9']   == pyproject.toml:43
  local-models  = ['httpx>=0.28.0']     == pyproject.toml:41

Extras that genuinely add packages:
  search        +1  tavily-python>=0.3.0
  browser       +1  playwright>=1.48.0
  files         +3  pypdf, python-docx, openpyxl
  tracing       +2  opentelemetry-api, opentelemetry-sdk
  observability +3  opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http
  presentations +1  python-pptx
  unofficial     0  EMPTY MARKER EXTRA  (pyproject.toml:103)

observability ⊇ tracing : True   (strict superset)
```

Anchors: `:41` `httpx>=0.28.0` · `:43` `chromadb>=1.5.9` · `:69-71` `memory` · `:72-74`
`local-models` · `:86-89` `tracing` · `:92-96` `observability` · `:103` `unofficial = []`.

So **2 of 9** product extras leak into base — not all of them. `observability` being a strict
superset of `tracing` is worth a note; `unofficial = []` is a deliberate ToS marker
(`:100-102` explains it) and is **not** a defect.

### 3.9 `.claude/worktrees/` — 15 stale agent worktrees

15 directories (`agent-a103ee9da4e544263`, …), each a **full repo copy** including its own
`.venv/`, `.mypy_cache/`, `.pytest_cache/`. `du -sb` **timed out after 2 minutes** — which is
itself the measurement.

Ignored via `.claude/.gitignore:4:worktrees/`, so `git` and `rg` skip them. **Glob- and
`find`-based tooling does not:** `ls .claude/worktrees/*/pyproject.toml | wc -l` → **15**.
They are what the June sdist swept up (§3.5).

### 3.10 `docs/audit/` retention

Four dated snapshots today: `2026-06-28`, `2026-07-03`, `2026-07-18`, `2026-07-19`. The
2026-06-27 cleanup deleted 57 docs including an entire `docs/audit/**` tree; it has regrown
in three weeks. No retention rule exists.

## 4. Reproduce the failure

Every number above is reproducible. Run from the repo root.

```bash
# 1. The trees are IGNORED, not untracked — none of these appears in status.
git status --porcelain --untracked-files=all | grep -E 'ds-sync|ds-bundle|design|stitch|Hachi Web UI'
echo "^ empty means invisible to git"

# 2. Sizes.
for d in .ds-sync ds-bundle .design-bundle "Hachi Web UI" .stitch-review design-system .design-sync; do
  printf '%-18s %s\n' "$d" "$(du -sb "$d" 2>/dev/null | cut -f1)"
done
du -sbc .ds-sync ds-bundle .design-bundle "Hachi Web UI" .stitch-review design-system .design-sync | tail -1

# 3. WHICH rule hides each one — check a real file inside, not the directory.
for d in .ds-sync ds-bundle .design-bundle "Hachi Web UI" .stitch-review .design-sync; do
  f=$(find "$d" -type f 2>/dev/null | head -1)
  printf '%-16s ' "$d"; git check-ignore -v "$f" || echo "NOT IGNORED"
done

# 4. .ds-sync is 100% node_modules, and esbuild.exe is the only native binary.
find .ds-sync -not -path '*/node_modules/*' -type f | wc -l        # 0
find .ds-sync -type f \( -name '*.exe' -o -name '*.dll' -o -name '*.node' -o -name '*.so' \) -exec du -b {} \;

# 5. The only negation in .gitignore.
grep -n '^!' .gitignore

# 6. design-system is the stale copy.
git log -1 --format='%ad %h %s' --date=short -- design-system/
git log -1 --format='%ad %h %s' --date=short -- frontend/src/components/ui/
for c in Button Input LoyalLoop StatusPill Switch Terminal Toast; do
  printf '%-11s ds=%3s fe=%3s\n' "$c" \
    "$(wc -l < "$(find design-system -name "$c.jsx" | head -1)")" \
    "$(wc -l < "frontend/src/components/ui/$c.tsx")"
done

# 7. dist/ and its 45x ratio.
ls -la dist/
python - <<'PY'
import tarfile, collections
t = tarfile.open("dist/hachi_og-0.1.0.tar.gz")
agg = collections.Counter(); n = 0
for m in t:
    if not m.isfile(): continue
    n += 1
    p = m.name.split("/")
    agg["/".join(p[1:3]) if len(p) > 2 else "/".join(p[1:2])] += m.size
print("files in sdist:", n)
for k, v in agg.most_common(8): print(f"  {v:>12,}  {k}")
PY

# 8. frontend/.tanstack is EMPTY (0 bytes) but UNIGNORED.
find frontend/.tanstack; du -sb frontend/.tanstack
git check-ignore -v frontend/.tanstack || echo "NOT IGNORED"

# 9. The root shim is CRLF — ^M on every line.
cat -A hachi

# 10. The extras.
python - <<'PY'
import tomllib
d = tomllib.load(open("pyproject.toml", "rb"))
base = set(d["project"]["dependencies"])
for name, deps in d["project"]["optional-dependencies"].items():
    if name in ("dev", "security"): continue
    new = [x for x in deps if x not in base]
    if deps and not new: print(f"  {name:15} NO-OP  {deps}")
    elif not deps:       print(f"  {name:15} EMPTY MARKER")
    else:                print(f"  {name:15} adds {len(new)}: {new}")
PY

# 11. Stale worktrees.
ls -A1 .claude/worktrees/ | wc -l
ls .claude/worktrees/*/pyproject.toml | wc -l    # glob tools DO walk in
```

**You will see now:** (1) empty; (2) the seven sizes summing to 52,598,381; (3) each tree
mapped to `node_modules/` / `*.html` / `*.png` / a nested `.gitignore`; (4) `0` and one
11,670,528-byte `esbuild.exe`; (5) a single `60:!frontend/index.html`; (6) 2026-06-27 vs
2026-07-19 and 300 vs 752 LOC; (7) `.claude/worktrees` at 113,687,731 B; (8) `0` bytes and
`NOT IGNORED`; (9) `^M$` on all three lines; (10) `memory` and `local-models` NO-OP;
(11) `15` and `15`.

**You should see after the fix:** (3) each tree ignored **by name**; (5) the image/html
globs scoped to real asset directories; (8) `frontend/.tanstack/` ignored; (9) LF endings and
a path that resolves on POSIX; (10) no NO-OP lines.

## 5. What "fixed" looks like

### (a) Ignore each tree by name — do this first, it is safe and reversible

Append a clearly-labelled block to `.gitignore`. **Ignoring is not deleting** — this is the
change you can make without asking anyone.

```gitignore
# ---------------------------------------------------------------------------
# Design-tool working trees (Claude Design / DesignSync / Stitch exports).
# Source material, NOT build output — see docs/DECISIONS.md before removing any.
# Named explicitly so the *.png / *.html globals above can be narrowed.
# ---------------------------------------------------------------------------
.ds-sync/
ds-bundle/
.design-bundle/
.design-sync/
.stitch-review/
/Hachi Web UI/
```

Then add the one genuinely missing runtime path:

```gitignore
frontend/.tanstack/
```

### (b) Narrow the globals — after (a), never before

`.gitignore:55-60` becomes scoped to where generated assets actually appear, e.g.:

```gitignore
# Generated/runtime assets. Scoped: a blanket *.png / *.html silently swallows
# tracked fixtures and docs images with NO signal (git add succeeds, the file
# never lands). !frontend/index.html was the fossil of exactly that.
/.hachi/**/*.png
docs/**/*.html
```

**Order matters:** (a) makes (b) safe. Narrow the globals first and 52.6 MB appears in
`git status` at once.

**Verify with the negative test.** After narrowing, confirm a representative file that
*should* still be ignorable still is, and that a file that *should* now be trackable is:

```bash
git status --porcelain --untracked-files=all | wc -l   # must not jump by thousands
git check-ignore -v frontend/index.html || echo "trackable — correct"
```

### (c) `design-system/` — 🔷 ASK THE USER. Do not decide this yourself.

§3.4 establishes that `frontend/` is the source of truth and the 65 tracked files are 22 days
stale. **That is a finding to report, not a licence to delete.** The tree also contains
`.prompt.md` files, `tokens/`, `assets/`, `templates/`, and three components (`Badge`,
`Card`, `RunCard`) with **no frontend equivalent** — deleting it destroys work with no copy
elsewhere.

Present the evidence and ask. Options: keep as brand canon and add a README stating
`frontend/` wins on implementation; move out of the product repo; or delete the 9 duplicated
components only. **Record whichever in `docs/DECISIONS.md`.**

### (d) `dist/` — delete the artifacts, then investigate the leak separately

`dist/` is build output and doubly ignored; deleting the two files is safe and needs no
permission. It is regenerable with `uv build`.

**Then flag the packaging bug as its own piece of work** (§3.5): rebuild and measure.

```bash
rm dist/hachi_og-0.1.0.tar.gz dist/hachi_og-0.1.0-py3-none-any.whl
uv build
ls -la dist/    # if the sdist is still ~45x the wheel, the leak is live
```

If it is live, the fix is a `[tool.hatch.build.targets.sdist]` section with an explicit
`include`/`exclude`. **Do not write that config speculatively** — measure first, and if it is
already fixed, say so and stop.

### (e) The root shims — 🔷 DECIDE, then do it properly

The `hachi` shim is broken on every POSIX platform (§3.7). Two honest options:

- **Fix it:** convert to LF endings, and detect the layout —
  `[ -x "$D/.venv/bin/hachi" ] && exec "$D/.venv/bin/hachi" "$@" || exec "$D/.venv/Scripts/hachi" "$@"`.
  Add `hachi text eol=lf` to `.gitattributes` so it cannot regress.
- **Delete both shims.** `uv run hachi` and an activated venv both already work; the shims
  exist for convenience only.

**Recommendation: fix it.** A broken entry point at the repo root is a first-impression bug,
and the fix is four lines. Whichever you pick, `.gitattributes` protection is mandatory if
the file survives — CRLF will come back otherwise.

### (f) Extras — 🔷 DECIDE, then make it true

`memory` and `local-models` are complete no-ops (§3.8). Two coherent positions:

- **Delete the two no-op extras.** `pip install hachi-og[memory]` currently promises
  something base already provides. Smallest change, honest install surface.
- **Make them real** — move `chromadb` and `httpx` out of base into their extras. Honest
  modularity, but it is a **breaking install change** for anyone relying on
  `pip install hachi-og` giving them memory, and `httpx` is used far beyond local models.

**Recommendation: delete the two no-op extras**, and add a comment to `observability`
(`:92-96`) noting it is a strict superset of `tracing` (`:86-89`). Leave `unofficial = []`
alone — `:100-102` explains it is a deliberate ToS marker. Record the decision in
`docs/DECISIONS.md`; the review's "make extras real" framing is a much larger change than it
sounds.

### (g) Worktree + audit retention

- Add a cleanup note to `CONTRIBUTING.md`: stale `.claude/worktrees/agent-*` accumulate (15
  today) and are invisible to `git`/`rg` but **not** to `find`, `ls`, IDE search, or a
  build backend. `git worktree list` then `git worktree remove` is the safe removal path —
  **never `rm -rf` a worktree**, that leaves dangling metadata in `.git/worktrees/`.
- Propose a `docs/audit/` retention rule (§3.10) in `docs/DECISIONS.md` — e.g. keep the two
  most recent dated snapshots, archive the rest. **Propose; do not execute.** The
  2026-07-18 and 2026-07-19 snapshots are the active work of this very task pack.

## 6. Steps

1. Run every §4 command; paste the real numbers into your PR description. Several will have
   drifted.
2. **(a)** Add the by-name ignore block + `frontend/.tanstack/`. Confirm `git status` is
   unchanged.
3. Write the §7 test. Watch it fail.
4. **(b)** Narrow the image/HTML globals. Re-run `git status --porcelain -uall | wc -l` — if
   it jumps by thousands, step (a) is incomplete. Fix, do not proceed.
5. **(d)** Delete the two `dist/` artifacts.
6. **(f)** Remove the two no-op extras; comment the `observability`/`tracing` overlap.
7. **(d cont.)** `uv build`, then re-run the §4 sdist inspector. Report the ratio. **If the
   leak is live, file it as a separate task — do not fix packaging inside a hygiene sweep.**
8. **(e)** Fix or delete the root shims; add `.gitattributes` if you keep them.
9. **(c)** Write up the `design-system/` evidence and **ask**. Do not act until answered.
10. **(g)** Add the CONTRIBUTING note and the retention proposal to `docs/DECISIONS.md`.
11. Run the FULL `uv run python scripts/preflight.py` and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Most of this task has no runtime behaviour, and **a pytest test is the wrong instrument for
"did we delete the right directory"** — do not invent one. But two invariants here are
genuinely mechanical, permanent, and worth locking, and both are exactly the trap that
created this finding:

- **File:** `tests/test_repo_hygiene.py` (**new**)
- **Test names:** `test_no_blanket_asset_globs_in_gitignore`,
  `test_no_no_op_optional_dependencies`
- **It must assert:** against the real `.gitignore` and the real `pyproject.toml` — that no
  unanchored `*.png`/`*.jpg`/`*.jpeg`/`*.gif`/`*.html` rule exists, and that no extra's pins
  are entirely contained in `dependencies`.
- **It must FAIL before your fix** with
  `AssertionError: unanchored asset globs in .gitignore: ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.html']`
  and `AssertionError: no-op extras (every pin already in base): ['memory', 'local-models']`.

```python
# sketch — adapt to the repo's existing fixtures
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLANKET = {"*.png", "*.jpg", "*.jpeg", "*.gif", "*.html"}


def test_no_blanket_asset_globs_in_gitignore() -> None:
    """A repo-wide *.png / *.html rule silently swallows tracked files.

    Regression: these globs hid 52.6 MB of design trees from `git status` and made
    any future tracked HTML or image un-addable with NO signal — `git add` succeeds,
    the file never lands. `!frontend/index.html` was the single fossil of that.
    """
    lines = [
        ln.strip()
        for ln in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    offenders = sorted(BLANKET.intersection(lines))
    assert not offenders, (
        f"unanchored asset globs in .gitignore: {offenders} — scope them to a "
        "directory (e.g. docs/**/*.html) so tracked assets stay trackable"
    )


def test_no_no_op_optional_dependencies() -> None:
    """An extra whose every pin is already in `dependencies` installs nothing."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    base = set(data["project"]["dependencies"])
    extras = data["project"].get("optional-dependencies", {})
    noop = sorted(
        name
        for name, deps in extras.items()
        if name not in {"dev", "security"} and deps and set(deps).issubset(base)
    )
    assert not noop, (
        f"no-op extras (every pin already in base): {noop} — delete them, or move "
        "the dependency out of `dependencies` so the extra means something"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Note `unofficial = []` is deliberately excluded by the `and deps` guard — an empty marker
> extra is not a no-op, it is a ToS gate (`pyproject.toml:100-103`).

## 8. Acceptance criteria

- [ ] The §7 tests exist and both failed before the fix.
- [ ] All seven trees are ignored **by name** in `.gitignore`.
- [ ] The unanchored `*.png`/`*.jpg`/`*.jpeg`/`*.gif`/`*.html` rules are gone or scoped.
- [ ] `git status --porcelain --untracked-files=all | wc -l` did **not** grow by more than a handful — paste before and after.
- [ ] `frontend/.tanstack/` is ignored.
- [ ] `dist/`'s two artifacts are deleted, and the post-`uv build` sdist:wheel ratio is **reported** (leak fixed, or filed as its own task with the measured number).
- [ ] The root `hachi` shim either works on POSIX (LF endings + layout detection + `.gitattributes`) or is deleted along with `hachi.bat`.
- [ ] `memory` and `local-models` are gone from `[project.optional-dependencies]`; `unofficial = []` is untouched.
- [ ] `uv sync --extra dev` still succeeds after the pyproject edit.
- [ ] **Nothing under `design-system/`, `Hachi Web UI/`, `.ds-*` or `.design-*` was deleted without the user answering §5(c).**
- [ ] Decisions for (c), (e), (f) and the audit-retention proposal are recorded in `docs/DECISIONS.md`.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **⚠️ DO NOT DELETE ANYTHING UNDER `design-system/`, `Hachi Web UI/`, `.ds-sync/`,
  `ds-bundle/`, `.design-bundle/`, `.design-sync/`, OR `.stitch-review/` WITHOUT ASKING THE
  USER FIRST.** This is the single most important line in this document. Those trees are
  **design source material, not build output** — Claude Design / DesignSync / Stitch exports
  that may exist nowhere else. `design-system/` alone holds 65 tracked files including
  `.prompt.md` authoring prompts, design tokens, and three components (`Badge`, `Card`,
  `RunCard`) with **no frontend equivalent at all**. "It duplicates the frontend" is true of
  9 of its components and false of the rest. **Ignoring is reversible; deleting is not.**
  Do (a), report the evidence, and wait.
- **Do not delete `.claude/worktrees/` entries with `rm -rf`.** Use `git worktree list` then
  `git worktree remove`. A raw delete leaves dangling metadata in `.git/worktrees/` that
  breaks later worktree commands.
- **Do not delete anything under `docs/audit/`.** The 2026-07-18 and 2026-07-19 snapshots are
  the live task pack you are reading. Propose a retention rule; do not apply it.
- **Do not restructure `pyproject.toml`'s base dependencies** to "make extras real". That is
  a breaking install-UX change (§5f) and needs its own decision and its own release note.
  Removing the two no-op extras is in scope; moving `chromadb`/`httpx` out of base is not.
- **Do not "fix" `frontend/.tanstack/` by deleting it.** It is a tool-managed cache directory
  and is currently empty (§3.6). Ignore it; leave it on disk.
- **Do not write `[tool.hatch.build.targets.sdist]` config speculatively.** Measure with a
  fresh `uv build` first (§5d). The leak may already be fixed by
  `.claude/.gitignore:4`, in which case adding config is unnecessary churn.
- **Do not touch `.gitignore:83-89`** (the seven `.claude/skills/*` entries) or `:79`
  (`.hachi/` — it holds the gateway token secret) or `:65-70` (secrets).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**The task-specific check is the `git status` diff, and it is the one that catches the
dangerous mistake.** Capture the line count before and after; a jump into the thousands means
a narrowed glob exposed a tree that step (a) failed to name.

```bash
git status --porcelain --untracked-files=all | wc -l    # BEFORE
git status --porcelain --untracked-files=all | wc -l    # AFTER — must be ~unchanged
uv sync --extra dev                                     # the pyproject edit must not break the env
uv build && ls -la dist/                                # report the sdist:wheel ratio
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Blanket `*.png` / `*.html` ignores hid 52.6 MB and silently un-track new assets

- **Symptom:** seven design-tool trees totalling 52,598,381 B sat at the repo root and
  appeared in NO git output — not `git status`, not `git status -uall`, not `git clean`.
  Separately, `pip install hachi-og[memory]` and `[local-models]` installed nothing, and the
  built sdist was 45x its own wheel.
- **Root cause:** `.gitignore` carried unanchored `*.png`/`*.jpg`/`*.jpeg`/`*.gif`/`*.html`
  rules plus `node_modules/`. The DIRECTORIES were never ignored — every FILE inside matched
  a global glob, so each tree looked empty to git. The single `!frontend/index.html` negation
  was the fossil of that same rule eating a needed file once before. The extras duplicated
  base pins character-for-character. The sdist swept in 108 MB of `.claude/worktrees/`
  because `pyproject.toml` declares a wheel target but no sdist target.
- **Fix:** named each tree in `.gitignore`, THEN narrowed the globs (that order matters — the
  reverse dumps 52 MB into `git status`); ignored `frontend/.tanstack/`; deleted the stale
  `dist/` artifacts and measured the rebuilt ratio; removed the two no-op extras.
- **Avoid:** never put an unanchored asset glob in `.gitignore`. It does not filter noise —
  it decides what CAN be tracked, and it fails silently: `git add` succeeds, `git status`
  stays clean, the file never lands. Scope every asset rule to a directory. And to find what
  a repo is hiding, use `git check-ignore -v <a file inside the dir>`, not on the directory
  itself — the directory is usually not the thing that is ignored.
- **Locked by:** `tests/test_repo_hygiene.py` — `test_no_blanket_asset_globs_in_gitignore`, `test_no_no_op_optional_dependencies`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **⚠️ `.gitignore` has NO trailing newline and uses CRLF.** Its last line (`:93`,
  `frontend/.vite/`) ends without `\n`. A naive `echo "x" >> .gitignore` produces
  `frontend/.vite/x` — a silently broken rule. **Open the file and edit it; do not append
  from a shell.** Same hazard applies to the CRLF endings — keep them consistent or add
  `.gitattributes`.
- **`git check-ignore -v <dir>` reports "not ignored" for six of the seven trees** and it is
  telling the truth: the directory is not ignored, its contents are. Always check a real file
  inside (§4 command 3), or you will conclude the trees are untracked and go looking for a
  bug that is not there.
- **BB-7 — the directory junction.** `D:\OpenGigantic\hachi` and a sibling `tokoboros` path
  are the same files. A `du`/`find` sweep can double-count or follow the junction into
  itself. Do not add `-L` to any `find` in this task.
- **`du -sb .claude/worktrees` takes minutes** (15 full repo copies, each with a `.venv`). It
  is not hung. Budget for it or skip it.
- **`.design-sync/.cache/` has its OWN `.gitignore` containing `*`.** A nested ignore file
  overrides parent rules for that subtree. If a tree seems ignored for no reason you can find
  in the root `.gitignore`, look for a nested one.
- **`ls`/`find`/`glob` walk into `.claude/worktrees/`; `git` and `rg` do not.** A cleanup
  script written with `Path.rglob` from the repo root will happily process 15 stale copies of
  the repo. Anchor every path explicitly.
- **`hachi` and `hachi.bat` are the repo-root shims, not the installed entry point.** The
  real console script is `pyproject.toml:117` — `hachi = "hachi.cli.main:app"`. Deleting the
  shims does not affect `uv run hachi` or an installed `hachi`.
- **`dist/.gitignore` contains a single `*` with no newline.** If you delete `dist/`'s
  contents, leave that file — it is what keeps a regenerated `dist/` self-ignoring.
