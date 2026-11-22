# Contributing to Hachi

Thanks for being here. Hachi is pre-release and the surface is still moving, which means
contributions land fast and the maintainers are motivated to review them quickly.

---

## First fifteen minutes

No API key is needed to develop or to run the test suite. Everything below works offline.

```bash
git clone https://github.com/OpenGigantic/hachi && cd hachi
uv sync --extra dev                      # Python 3.11+; uv provisions it for you
uv run pytest -q                         # ~4,300 tests, a couple of minutes
uv run python scripts/preflight.py --quick   # the fast gate: ruff, mypy, skill lint, eval
```

That last command is the loop you will actually live in. The **full** gate — which CI runs — is
`uv run python scripts/preflight.py`.

You only need a provider key if you want to *use* the agent:
`uv run hachi quickstart` walks you through it.

See [README.md](README.md) for what the project actually is.

---

## Where to ask

- **Questions / ideas** → GitHub Discussions (once enabled) or an issue with the `question` label
- **Bugs** → [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Security vulnerabilities** → **do not open an issue**; use [SECURITY.md](SECURITY.md)
- **Conduct concerns** → <conduct@opengigantic.com>

---

## Finding something to work on

The lowest-friction contribution is a **new `.og` skill** — around 30 lines, no Python, linted
in CI. Look at `src/hachi/default_skills/` for the shape, then `docs/reference/objectgraph-spec.md`
for the tag reference.

Issues labelled `good first issue` are scoped and have a file path plus an acceptance criterion.
If you want to take something larger, open an issue first so we can agree the shape before you
write a lot of code.

---

## Branch and PR model

**Branch from `main`. Every PR is one logical change.**

```
main                     protected; never commit to it directly
feat/<short-name>        new capability
fix/<short-name>         bug fix
docs/<short-name>        documentation only
chore/<short-name>       tooling, deps, CI
```

- **Conventional Commits**, imperative mood: `fix(net-guard): reject CGNAT addresses`.
- Keep the diff to what the title says. Drive-by refactors, renames and reformats make review
  harder and will usually be asked to split.
- **One PR = one thing a reviewer can hold in their head.** If your change needs three unrelated
  paragraphs in the description, it is three PRs.

Before opening a PR:

```bash
uv run python scripts/preflight.py     # must be green
```

---

## Tests are the contract

- **Bug fixes start with a failing test.** Write the test, watch it fail for the right reason,
  then fix the code. A fix without a regression test will be asked for one.
- **Do not weaken, skip or delete a test to make CI green.** If a test is wrong, say so in the PR
  and change it deliberately.
- **Run the full suite before claiming done** — `uv run pytest -q`, not a subset. Cross-module
  regressions are the normal failure mode here.
- **Verify the claim, not the intent.** A green test proves what it asserts, nothing more. If your
  commit message says "the gate now catches X", the test must actually exercise X.

That last point is not theoretical — see `docs/bug-bank.md`, where several entries exist because a
correct code change was described by an incorrect sentence.

---

## The Rails

`import-linter` enforces module layering and is **blocking**:

```
edges    cli, tui, channels            (entry adapters)
service  gateway, client, sdk          (REST surface)
engine   core, og_engine, tools, jobs  (foundation)
```

Higher layers may import lower ones, never the reverse. A new cross-layer import that is not on
the allowlist fails the gate. Route the call through an existing seam — or, if a genuinely new
boundary is justified, add a commented `ignore_imports` entry in `pyproject.toml` and explain why
in the PR.

`deptry`, `vulture` and the ruff complexity counts are advisory for now. Fix what you can.

---

## Code style

- PEP 8, 100-character lines, enforced by `ruff`.
- Type hints on all function signatures; public functions and classes get docstrings.
- `pathlib.Path` for filesystem paths, never raw strings.
- One responsibility per module.
- **Never run repo-wide `ruff format`** — it reflows ~100 files and buries the real diff. Format
  the files you touched (`uv run ruff format <paths>`).

---

## Contributing `.og` skills

1. Use the full tag set (`::meta`, `::index`, `::dense`, `::full`, `::steps`, `::assertion`, …).
2. Every node needs `keywords` for search indexing.
3. Include `::assertion` blocks where the skill has preconditions — they are executed before the
   skill runs.
4. Keep `::dense` inside the budget; lint rejects an over-long summary.
5. Lint it: `uv run hachi skill lint src/hachi/default_skills/`.

See [docs/reference/objectgraph-spec.md](docs/reference/objectgraph-spec.md).

---

## Architecture decisions

Settled decisions go in [`docs/DECISIONS.md`](docs/DECISIONS.md). A major architectural choice
that warrants alternatives analysis gets a numbered ADR under
[`docs/architecture/adr/`](docs/architecture/adr/) — copy `0000-template.md` and add it to the
index.

If you find a bug worth remembering, add an entry to [`docs/bug-bank.md`](docs/bug-bank.md):
symptom, root cause, the one-line rule, and the test that locks it.

---

## About this repository's tooling

This project is developed with AI agents, so `CLAUDE.md`, `AGENTS.md` and `.claude/` are tracked
on purpose. They describe how the maintainers work, and the hooks in `.claude/` (push-lock, secret
scan) apply to maintainer workflows. You do **not** need any of it to contribute — `preflight.py`
is the gate that matters.

## License

By contributing you agree that your contributions are licensed under the **Apache License 2.0**
— see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Section 5 of the licence means no separate CLA is required: a contribution intentionally
submitted for inclusion is licensed under the same terms, automatically.

Contributing code does not grant any rights in the project's **name or logo** — the Apache
licence explicitly withholds trademark rights (§6). See [TRADEMARK.md](TRADEMARK.md).
