# T-71 · Convert the ten wall-clock tests to injected clocks so `-n auto` works — and guard sequential until it does

|  |  |
|---|---|
| **Source finding** | CF-18 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none. **Collides with [T-70](T-70-test-tree-mirroring.md)** — it moves the ten files you edit. Sequence them; never run both at once. |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | 7 files under `tests/`, `scripts/preflight.py`, `pyproject.toml`, possibly `src/hachi/core/notifier.py` + `src/hachi/core/memory.py` (injection points), `docs/bug-bank.md` |

---

## 1. Brief

The full suite must run sequentially because ten tests assert on wall-clock duration or
cross-thread timestamp ordering, and parallel workers starve them. That is a hard ceiling on
gate latency that worsens with every test added — and **it is enforced by omission only**:
`pytest-xdist` is installed, `--dist=loadfile` is already in `addopts`, and `pyproject.toml`
actively documents `-n auto`. Anyone who follows the config's own instructions breaks the
gate.

When you are done, those ten tests assert on injected clocks and thread coordination
primitives instead of `time.monotonic()` deltas, `uv run pytest -n auto` is green, and
preflight uses it. Until then, preflight names sequential execution **explicitly** instead
of relying on nobody typing `-n`.

## 2. Why this matters

The suite is the contract ([CLAUDE.md](../../../../CLAUDE.md) Rule 2), and the rule is "run
the FULL suite before claiming done". A rule people follow only when it is cheap is a rule
that erodes. At 4,100+ tests growing under agent-velocity authorship, sequential-only is a
straight line to a gate people skip — which is precisely the behaviour the project's rules
exist to prevent.

The second reason is subtler and is why you must add the guard *first*. Today's sequential
execution is not a decision the tooling holds — it is the absence of a flag. The docstring
says "deliberately NOT `-n auto`" while the config three files away says "Pass `-n <N>` or
`-n auto` on the CLI". One of those is wrong, and neither is enforced. A future contributor
who wants a faster gate will find the invitation, not the prohibition, and will get two
mysterious failures with no explanation attached.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The prohibition — `scripts/preflight.py:20-23`, verbatim

```python
- pytest runs the **full** suite (the contract, CLAUDE.md Rule 2) **sequentially**, exactly
  like CI — deliberately NOT `-n auto`. Parallel workers starve the wall-clock timing tests
  (e.g. `test_two_sessions_run_concurrently`, the notifier non-blocking test) and make the gate
  flaky; the plan's rule is "run tests sequentially to kill time-based flakiness."
```

**Both tests named in that docstring are on the §3.4 list** — a good sign the list is
complete.

### 3.2 ⚠️ Sequential is enforced by OMISSION ONLY

`scripts/preflight.py:133` — the actual step:

```python
    Step("pytest (full suite)", [["uv", "run", "pytest", "-q"]], in_quick=False),
```

No `-n 0`. No `-p no:xdist`. Nothing that would make a parallel run impossible or even
noisy. Meanwhile the config invites the opposite:

- `pyproject.toml:58` — `"pytest-xdist>=3.6.1",` in the `dev` extra. **Verified installed:
  xdist 3.8.0 under `uv run`.**
- `pyproject.toml:151-153`:

  ```toml
  # --dist=loadfile keeps all tests from the same file on the same worker, preventing
  # module-level singleton / patch.dict conflicts. Pass -n <N> or -n auto on the CLI.
  addopts = "--dist=loadfile"
  ```

`--dist=loadfile` is **already active on every run**. The config documents the exact flag the
preflight docstring forbids. **Add a hard guard; do not merely convert the clocks.**

### 3.3 ⚠️ The obvious guard does not work — verified

`-p no:xdist` disables the plugin, which makes `--dist=loadfile` from `addopts` unparseable:

```
$ uv run python -m pytest tests/test_obs_sink.py -q -p no:xdist --collect-only
python.exe -m pytest: error: unrecognized arguments: --dist=loadfile
  inifile: D:\OpenGigantic\hachi\pyproject.toml
```

`-n 0` **works** and leaves `addopts` alone:

```
$ uv run python -m pytest tests/test_obs_sink.py -q -n 0 --collect-only
10 tests collected in 0.63s
```

**Use `-n 0`.** (`-p no:xdist` only becomes viable if you also remove `--dist=loadfile` from
`addopts`, which is a bigger change for no gain.)

### 3.4 The convert list — 8 duration assertions + 2 cross-thread ordering

| File:line | Test | Assertion |
|---|---|---|
| `tests/test_os_tools_hardening.py:410` | `test_notifier_windows_dispatch_is_non_blocking` (def `:391`) | `assert elapsed < 0.05` — **tightest** |
| `tests/test_g3_compaction.py:109` | `test_prepare_for_turn_does_not_block_on_llm` (def `:85`) | `assert elapsed < 0.1` |
| `tests/test_os_tools_hardening.py:462` | `test_notifier_prewarm_does_not_block` (def `:452`) | `assert elapsed < 0.1` |
| `tests/test_g3_turn_lock.py:155` | `TestDifferentSessionsConcurrent::test_two_sessions_run_concurrently` (def `:112`) | `assert wall_time < 1.7 * SLEEP` — `SLEEP = 0.05` at `:25`, so 85 ms |
| `tests/test_p4_03_parallel_tools.py:165` | `test_parallel_execution_is_faster_than_sequential` (def `:146`) | `assert elapsed < DELAY * len(tcs) * 0.8` — `DELAY = 0.10` at `:150` |
| `tests/test_obs_sink.py:112` | `test_sink_does_not_block` (def `:101`) | `assert elapsed < 1.0` |
| `tests/test_shared_services_mcp.py:319` | `TestMcpStartTimeout::test_hanging_start_fails_within_timeout` (def `:296`) | `assert elapsed < 1.0` |
| `tests/test_mcp_client_timeout.py:34` | `test_send_request_times_out_without_stdout_responses` (def `:25`) | `assert elapsed < 2.0` |
| `tests/test_g3_turn_lock.py:100` | **`TestSameSessionSerialized::test_two_concurrent_chats_do_not_overlap`** (class `:66`, def `:67`) | `assert first_exit <= second_entry` — cross-thread ordering |
| `tests/test_g3_turn_lock.py:210` | `TestDifferentSessionsConcurrent::test_interleaving_of_entry_exit_timestamps` (def `:160`) | `assert second_entry_t < first_exit_t` — cross-thread ordering |

> **⚠️ Name correction.** The tenth row is often cited as `test_same_session_calls_are_serialized`.
> **No test by that name exists.** The line number `:100` is right; the name is
> `test_two_concurrent_chats_do_not_overlap`, inside the class `TestSameSessionSerialized`
> (`:66`) — the *class* name is what got remembered. Grep for the class, not the phantom
> function.

The two ordering tests are a different problem from the eight duration tests. See §5.

### 3.5 EXCLUDE — `tests/test_p2_03c_cost_latency.py:227,229`

```python
def test_m4_produces_reasonable_latency():          # :218
    ...
    m4 = compute_m4(engine, probes, rtt_per_pass_ms=800.0)      # :225
    assert m4.n_queries == 1                                    # :226
    assert m4.avg_engine_ms >= 0.0                              # :227
    assert m4.rtt_estimate_ms == pytest.approx(2400.0, rel=0.01) # :228
    assert m4.total_estimate_ms >= m4.rtt_estimate_ms            # :229
```

These are **structural invariants on model-computed values**, not wall clock. `avg_engine_ms`
and `total_estimate_ms` come out of `compute_m4`, and the assertions state relationships that
hold at any speed. **Leave them alone.**

### 3.6 EXCLUDE — the 48 bare `time.sleep()` calls

`rg -o "time\.sleep\(" tests/ | wc -l` → **48 calls across 25 files**. They make the suite
*slow*; none of them is *parallel-hostile*, because none is paired with a duration assertion.
**Do not churn them.** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3.)

## 4. Reproduce the failure

Fully reproducible, in under a minute, on five files. Run from the repo root.

```bash
# Baseline — sequential. This is what the gate does today.
uv run python -m pytest -q -n 0 \
  tests/test_g3_turn_lock.py tests/test_g3_compaction.py \
  tests/test_os_tools_hardening.py tests/test_p4_03_parallel_tools.py tests/test_obs_sink.py

# The failure — the exact invocation pyproject.toml:152 tells you to use.
uv run python -m pytest -q -n auto \
  tests/test_g3_turn_lock.py tests/test_g3_compaction.py \
  tests/test_os_tools_hardening.py tests/test_p4_03_parallel_tools.py tests/test_obs_sink.py
```

**You will see now** (measured 2026-07-19):

```
-n 0    :  49 passed, 1 warning in 8.81s
-n auto :  2 failed, 47 passed, 13 warnings in 50.38s
          FAILED tests/test_p4_03_parallel_tools.py::test_parallel_execution_is_faster_than_sequential
          FAILED tests/test_g3_turn_lock.py::TestDifferentSessionsConcurrent::test_two_sessions_run_concurrently
                 tests\test_g3_turn_lock.py:155: AssertionError
```

Two things to notice, and be honest about both:

1. **The failure set is load-dependent.** On this five-file subset the two *concurrency-proving*
   tests fail (they need real parallelism, which xdist has taken). The *non-blocking* tests
   (`elapsed < 0.05`, `elapsed < 0.1`) survive here and fail under full-suite load. Do not
   conclude from a green subset that a test is fine — verify against the full run.
2. **`-n auto` was 5.7× SLOWER on this subset** (50.38 s vs 8.81 s) — worker startup dominates
   on five files. Parallelism only pays across all 308. **Measure the full suite both ways
   before you claim a speedup** (§8).

**You should see after the fix:** `uv run pytest -n auto` green across the full suite, and
`scripts/preflight.py` using it.

Confirm the enabling conditions for yourself:

```bash
uv run python -c "import xdist; print('xdist', xdist.__version__)"   # 3.8.0
sed -n '150,153p' pyproject.toml                                     # the -n auto invitation
sed -n '133p'    scripts/preflight.py                                # no guard
```

## 5. What "fixed" looks like

### Phase 0 — the guard, FIRST (~30 minutes, ship it on its own)

Before converting anything, make the current rule real. `scripts/preflight.py:133`:

```python
    # -n 0 pins sequential execution explicitly. Ten tests still assert on wall-clock
    # duration / cross-thread ordering and starve under parallel workers (see T-71).
    # NOT -p no:xdist: that disables the plugin and makes --dist=loadfile in addopts
    # an unrecognized argument. Flip to -n auto once T-71 lands.
    Step("pytest (full suite)", [["uv", "run", "pytest", "-q", "-n", "0"]], in_quick=False),
```

And correct `pyproject.toml:151-152`, which currently advertises the broken thing:

```toml
# --dist=loadfile keeps all tests from the same file on the same worker, preventing
# module-level singleton / patch.dict conflicts. NOTE: `-n auto` is NOT safe yet —
# ten tests assert on wall-clock duration and starve under parallel workers (T-71).
# The gate pins `-n 0`.
```

**This phase is independently valuable and independently shippable.** If you get pulled off
this task after phase 0, the repo is strictly better than it was.

### Phase 1 — the eight duration assertions

Replace "the wall clock said it was fast" with "the slow thing was never awaited". The
duration assertion is a *proxy* for a structural property, and the structural property is
what you should assert.

Two shapes cover all eight:

**(a) "did not block" → assert the slow work was handed off.** `test_sink_does_not_block`,
both notifier tests, and `test_prepare_for_turn_does_not_block_on_llm` all really mean *the
call returned before the slow collaborator finished*. Give the fake collaborator a
`threading.Event` the test controls: call the function while the event is unset, assert it
returned, **then** set the event and join. No clock at all — and it is a *stronger*
assertion, because a machine slow enough to blow `elapsed < 0.05` cannot make it pass
spuriously.

Note `test_g3_compaction.py:112` already does exactly this alongside the timing assertion:

```python
    assert slow_client.call_count == 0, "LLM was called synchronously inside _sliding_window_compact"
```

That line is the real test. `:109` is the redundant proxy. **Several of these convert by
deleting the timing assertion and keeping what is already there.** Check each before writing
new machinery.

**(b) "timed out within N" → inject the clock.** `test_hanging_start_fails_within_timeout`,
`test_send_request_times_out_without_stdout_responses`,
`test_parallel_execution_is_faster_than_sequential`. These assert the *production code's*
timeout/concurrency behaviour, so they need the production code to take its clock as a
seam — a `time_fn: Callable[[], float] = time.monotonic` parameter, defaulted so no caller
changes. Then the test drives virtual time and asserts the timeout fired at the right
virtual instant.

> **⚠️ Judgement call, and the reason this task is High difficulty.** (b) means editing
> **production** code to add a seam. That is legitimate — an injected clock is a normal,
> testable design — but it is a real change to `src/`, so keep each seam minimal (one
> defaulted parameter, no new abstraction) and cover it with the existing tests. If a
> particular seam looks like it wants a scheduler abstraction, stop: leave that test on the
> exclusion list, document why, and move on. **Nine of ten converted is a success.**

### Phase 2 — the two cross-thread ordering tests

`test_two_concurrent_chats_do_not_overlap` (`:100`) and
`test_interleaving_of_entry_exit_timestamps` (`:210`) do **not** assert duration. They
compare timestamps captured on different threads to prove a lock does (or does not)
serialize. An injected clock does not help — the property under test is genuine concurrency.

Rewrite with explicit coordination instead of timestamps: `threading.Barrier` /
`threading.Event` to force the interleaving, and assert on the *recorded sequence* of
enter/exit events rather than on their clock values. The recorder at
`tests/test_g3_turn_lock.py:29` (`class _CallRecord`) already collects entries and exits —
have it append ordered markers rather than `time.monotonic()` values.

These two are the hardest of the ten. Do them last.

### Phase 3 — flip the gate

`scripts/preflight.py:133` → `["uv", "run", "pytest", "-q", "-n", "auto"]`; update the
module docstring at `:20-23`, which currently states the opposite as policy; update the CI
pytest step to match; correct `pyproject.toml:151-152` again.

## 6. Steps

1. Land phase 0 (`-n 0` + comment corrections). Full suite. Green. **Commit and stop here if
   you are out of time.**
2. Write the §7 test. Watch it fail under `-n auto`.
3. For each of the eight duration tests, in the §3.4 order (tightest first — it is the one
   most likely to be a pure proxy): read what it really asserts, convert per §5 shape (a) or
   (b), and re-run **that file** under both `-n 0` and `-n auto`.
4. After each conversion, run the FULL suite sequentially. A converted test must still catch
   the regression it was written for — verify by breaking the production code on purpose and
   watching it go red. **Do this. A test that no longer fails when the bug returns is worse
   than the flaky one you replaced.**
5. Do phase 2 (the two ordering tests) last.
6. Full suite under `-n auto`, three times. All three green, or you are not done.
7. Phase 3: flip preflight, the docstring, CI, and the pyproject comment.
8. Report both timings (§8).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

**Here the "test" is the suite running in a mode it cannot survive today** — that is the
regression, and §4 reproduces it in 50 seconds. That check belongs in CI, not in a pytest
file: a test that shells out to a parallel pytest run from inside a pytest run is a recursion
hazard and will time out.

- **Instrument:** a CI job — `.github/workflows/ci.yml`, alongside the existing test job.
- **Name:** `pytest (parallel)` — `uv run pytest -q -n auto`.
- **It must assert:** the real full suite is green under parallel workers.
- **It must FAIL before your fix** with at least
  `FAILED tests/test_g3_turn_lock.py::TestDifferentSessionsConcurrent::test_two_sessions_run_concurrently`.

Add it **non-blocking** (`continue-on-error: true`) in phase 0 so the burn-down has a live
signal, and flip it to blocking in phase 3. If you add it non-blocking, put the ratchet
condition in the comment — [T-67](T-67-governance-drift-cleanup.md) exists because
non-blocking gates without a stated ratchet become permanent.

There **is** one thing worth a real pytest test — that the two duration assertions you must
*not* touch stay untouched, and that no new wall-clock assertion sneaks in:

- **File:** `tests/test_test_suite_hygiene.py` (**new**)
- **Test name:** `test_no_new_wall_clock_duration_assertions`
- **It must assert:** scanning the real `tests/` tree, no file outside a known allowlist
  contains an `elapsed <` / `wall_time <` assertion.
- **It must FAIL before your fix** listing the eight sites from §3.4.

```python
# sketch — adapt to the repo's existing fixtures
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PATTERN = re.compile(r"assert\s+(elapsed|wall_time)\s*<")

# Shrink this to the empty set as you convert. It may never grow.
# tests/test_p2_03c_cost_latency.py is deliberately absent: its :227/:229 assertions are
# structural invariants on model-computed values, not wall clock (T-71 section 3.5).
KNOWN_WALL_CLOCK = {
    "test_os_tools_hardening.py",
    "test_g3_compaction.py",
    "test_g3_turn_lock.py",
    "test_p4_03_parallel_tools.py",
    "test_obs_sink.py",
    "test_shared_services_mcp.py",
    "test_mcp_client_timeout.py",
}


def test_no_new_wall_clock_duration_assertions() -> None:
    """Wall-clock duration assertions starve under `-n auto` and gate the whole suite.

    Regression: eight such assertions forced the entire 4,100-test suite to run
    sequentially, and nothing stopped a ninth being added.
    """
    offenders = sorted(
        p.name
        for p in TESTS.rglob("test_*.py")
        if p.name not in KNOWN_WALL_CLOCK and PATTERN.search(p.read_text(encoding="utf-8"))
    )
    assert not offenders, (
        "new wall-clock duration assertions (assert an injected clock or a "
        f"threading.Event handoff instead — see T-71): {offenders}"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Remove each filename from `KNOWN_WALL_CLOCK` in the same commit that converts it. That
> shrinking set is your progress bar.

## 8. Acceptance criteria

- [ ] The §7 CI job and hygiene test exist, and the parallel job failed before the fix.
- [ ] `uv run pytest -n auto` is green on the FULL suite, **three consecutive runs** (this class of failure is probabilistic — one green run proves nothing).
- [ ] `scripts/preflight.py:133` uses `-n auto`, and its `:20-23` docstring no longer forbids it.
- [ ] `pyproject.toml:151-152`'s comment matches what the gate actually does.
- [ ] `KNOWN_WALL_CLOCK` in the §7 test is empty (or every remaining entry has a written reason).
- [ ] **Each converted test still fails when its original bug is reintroduced.** State which ones you verified this way.
- [ ] `tests/test_p2_03c_cost_latency.py` is **untouched**.
- [ ] The 48 bare `time.sleep()` calls are **untouched**.
- [ ] Full-suite wall time reported **both ways** (`-n 0` and `-n auto`) so the speedup is a measurement, not a claim.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch the 48 bare `time.sleep()` calls across 25 files.** They are slow, not
  parallel-hostile. Converting them is a 25-file diff with zero effect on the goal
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 3). This is the single most likely place for this
  task to sprawl.
- **Do not touch `tests/test_p2_03c_cost_latency.py:227,229`.** §3.5 — structural invariants,
  not wall clock.
- **Do not weaken a timing assertion to make it pass.** Raising `elapsed < 0.05` to
  `elapsed < 0.5` is exactly the "weaken a test to go green" that Rule 2 forbids, and it
  destroys the property the test exists to protect. Convert or leave alone — never loosen.
- **Do not delete a test because converting it is hard.** Leave it, document why, keep it on
  the allowlist.
- **Do not run this concurrently with [T-70](T-70-test-tree-mirroring.md).** It moves all ten
  files you are editing. Rename-plus-edit is an unmergeable conflict. Agree an order first.
- **Do not "fix" the timing tests by adding `@pytest.mark.flaky` or retries.** No such plugin
  is installed, adding one needs approval, and it hides the problem rather than solving it.
- **Do not turn on `-n auto` before all ten convert.** A green subset is not evidence — §4
  shows the failure set is load-dependent.
- **Do not restructure production concurrency** (the turn lock, the notifier thread pool, the
  parallel tool executor) to make a test easier. Adding a defaulted clock parameter is in
  scope; changing what the code *does* is not.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done

# The task-specific gate — run the FULL suite both ways and report both.
uv run pytest -q -n 0    2>&1 | tail -1
uv run pytest -q -n auto 2>&1 | tail -1
uv run pytest -q -n auto 2>&1 | tail -1
uv run pytest -q -n auto 2>&1 | tail -1
```

**Three parallel runs, not one.** Starvation failures are probabilistic and depend on host
load; a single green run is not evidence. If any of the three is red, you are not done —
and note *which* test failed, because a different one each time means you have found a
genuine race rather than a test artefact.

Report the **actual** pass/fail counts and both wall times. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Ten wall-clock tests forced the whole suite sequential; nothing enforced it

- **Symptom:** `uv run pytest -n auto` failed with
  `test_two_sessions_run_concurrently` and `test_parallel_execution_is_faster_than_sequential`
  — reproducible on a five-file subset. The gate therefore ran 4,100+ tests sequentially.
- **Root cause:** eight tests asserted on `time.monotonic()` deltas (tightest:
  `elapsed < 0.05`) and two compared cross-thread timestamps. Under xdist, workers steal the
  CPU the assertion assumes. Worse, sequential execution was enforced by OMISSION: preflight
  simply did not pass `-n`, while `pyproject.toml` shipped `pytest-xdist`, kept
  `--dist=loadfile` in `addopts`, and its comment told readers to "Pass -n <N> or -n auto on
  the CLI" — the exact thing the preflight docstring forbade.
- **Fix:** pinned `-n 0` explicitly first (note: `-p no:xdist` does NOT work — it makes
  `--dist=loadfile` an unrecognized argument), then replaced duration assertions with
  `threading.Event` handoffs and injected clocks, and the two ordering tests with explicit
  `Barrier` coordination over recorded sequences. Then flipped the gate to `-n auto`.
- **Avoid:** never assert on wall-clock duration to prove "did not block" — assert the slow
  collaborator was never awaited (a counter, or an Event the test controls). A duration
  assertion is a proxy that fails on a loaded machine and passes on a fast one. And when a
  gate depends on a mode, name the mode in the command; a rule enforced by omission is not
  enforced.
- **Locked by:** `tests/test_test_suite_hygiene.py` — `test_no_new_wall_clock_duration_assertions`; CI job `pytest (parallel)`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`. Every command in this spec already does.
- **`-p no:xdist` is a dead end.** §3.3 — verified. `-n 0` is the working flag.
- **`--dist=loadfile` is already in `addopts`,** so it applies to *every* run including
  yours. Any test relying on module-level singletons is already protected by same-file
  worker affinity. Do not remove it "to simplify" — `pyproject.toml:151` explains what it
  prevents.
- **BB-3 — chromadb.** `tests/conftest.py` warms chromadb at import so the PyO3 extension
  loads once. Under xdist this happens **once per worker**, which is fine — but never
  `patch.dict(sys.modules)` over chromadb while chasing a parallel failure. That is a
  different, worse bug.
- **`-n auto` is slower on small subsets** — 50.38 s vs 8.81 s on five files, measured. Worker
  startup dominates. Judge only against the full suite.
- **The failure set is load-dependent.** The "non-blocking" tests (`elapsed < 0.05`, `< 0.1`)
  pass on a small parallel subset and fail under full-suite load; the "concurrency-proving"
  ones fail immediately. Never conclude a test is converted from a green subset run.
- **`test_g3_turn_lock.py` has a phantom test name in circulation.** There is no
  `test_same_session_calls_are_serialized`. Grep the class `TestSameSessionSerialized` (`:66`)
  → `test_two_concurrent_chats_do_not_overlap` (`:67`, assertion `:100`).
- **`SLEEP` and `DELAY` are module/function constants** (`test_g3_turn_lock.py:25`,
  `test_p4_03_parallel_tools.py:150`), not literals in the assertion. Lowering them is *not*
  a conversion — it just narrows the window and makes the flake more likely.
