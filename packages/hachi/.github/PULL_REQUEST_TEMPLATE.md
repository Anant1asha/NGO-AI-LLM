## Summary

<!-- What does this PR change, and why? -->

## Test plan

<!-- How did you verify this works? Include actual command output where relevant
     (e.g. `uv run pytest -q` pass/fail counts), not "should work". -->

- [ ] `uv run python scripts/preflight.py` (or `--quick` for an inner loop) is green
- [ ] For a bug fix: a failing regression test was added first, then the fix, then
      a `docs/bug-bank.md` entry
- [ ] No unrelated files changed (see `CONTRIBUTING.md`)

## Checklist

- [ ] I've read `CONTRIBUTING.md`
- [ ] This PR does not introduce a new runtime dependency without prior discussion
- [ ] Any gateway route change regenerates `openapi/hachi-openapi.json` and the
      frontend's generated API types (`npm run --prefix frontend generate:api`)
