# .og Security Model — Tiered Trust

This document describes the tiered trust model for ObjectGraph (`.og`) files, how
permissions are enforced, and the correctness guarantees introduced by the append-only
version history and atomic-write changes.

---

## 1. Verified enforcement model

Permission checks are **engine-enforced**, not advisory.

`PermissionGate.check_command()` and `PermissionGate.check_path()` run *before* any
OS tool call executes.  Blocked paths and commands are compared there; only a compact
tier/folder summary is injected into the agent's system prompt.  The full blocked-path
and blocked-command policy is **never placed in the prompt**, so the agent cannot
reason around or override it through prompt manipulation.

**Audit finding**: a scan of every `.og` file in the repository (config, brain, bundled
skills, example files) found **no secrets** — no API keys, tokens, or credentials.
Sensitive values are stored in the secret store or referenced by environment variable
name only.

---

## 2. Tier definitions

### Tier 1 — Engine-enforced, never agent-writable

These files define the agent's operating envelope.  The engine refuses any
`upsert_skill` call whose target name resolves to a Tier-1 path.

| File | Role |
|------|------|
| `device-permissions.og` | Filesystem roots, allowed/blocked shell commands, MCP toggles, integration scopes |
| `brain.og` (and `brain-<role>.og`) | Role personality, delegation rules, system-prompt scaffold |

**Rules for Tier 1:**
- Owned by the human operator; edited only via the setup wizard or direct file edit.
- World-writable mode is a security violation; the config loader warns (or aborts under
  `HACHI_CONFIG_STRICT=1`) when it detects this on POSIX.
- Not indexed by the engine for agent retrieval — they are loaded once at session boot.

### Tier 2 — Advisory bundled skills

Skills shipped with Hachi (`~/.hachi/skills/*.og` files installed by the package, not
`learned/`).  The agent can read these via `search_skill` / `load_skill` but cannot
overwrite them through `upsert_skill` (the tool only writes to `learned/`).

These files are distributed as part of the package, lint-checked by `scripts/lint_skills.py`,
and reviewed in the same CI pipeline as source code.

### Tier 3 — Agent-writable learned skills

Files under `<skills_dir>/learned/` and `<skills_dir>/mcp-*.og` are created and refined
by the agent at runtime.

**Guards applied on every write:**
1. `validate_dense()` — dense block must be within the token budget.
2. `lint_og_file()` — structural lint check; warnings surface as `lint_advisories` in
   the result so the agent can self-correct.
3. Atomic write (see §4) — crash-safe replacement via `os.replace`.
4. Append-only version history (see §5) — every write is recorded and is not erasable
   by the agent.

The engine should formally refuse `upsert_skill` calls targeting names that shadow
Tier-1 or Tier-2 skills (wave-2 enforcement; tracked as a follow-up).

---

## 3. No secrets in .og files

`.og` files must never contain literal API keys, passwords, tokens, or other credentials.

- Reference credentials by **environment variable name** (e.g. `api_key_env = "ANTHROPIC_API_KEY"`).
- Store secrets in the secret store (`hachi secrets --set <name>`) and reference by key name.
- **Correction (2026-11-16):** an earlier revision of this section claimed the CI
  `security` job "scans all tracked files including `.og` files for secret
  patterns". **It does not.** `hachi security-audit` inspects the process
  environment and resolved config; it never opens a file. Its
  `oauth.google_client_secret_embedded` check fires on a `GOOGLE_CLIENT_SECRET`
  exported into the environment, not on a key committed to a `.og` file or any
  other source file. There is currently **no** tree secret-scan step in CI, so a
  pull request that commits a credential is not blocked by this gate.
  Tracked as PRODUCT-AUDIT P-30 (wire `core/secret_scanner.py` over the tracked
  files with a fixture allowlist). Until that lands, the rule above is a
  convention enforced by review, not by CI.

---

## 4. Atomic upsert — correctness guarantee

Before this change, `upsert_skill` called `path.write_text(...)` directly.  A crash
(power loss, OOM kill, `KeyboardInterrupt`) mid-write would leave a partially written,
corrupt `.og` file with no way to recover the previous state.

`upsert_skill` now:
1. Serializes the full `.og` content to a sibling temp file
   (`<slug>_<random>.og.tmp`) using `tempfile.mkstemp` inside the same directory.
2. Calls `os.replace(tmp, path)` — atomic on POSIX (rename syscall) and best-effort
   atomic on Windows (moves within the same volume).
3. On any error before `os.replace`, the temp file is unlinked (best-effort); the
   original `.og` file is untouched.
4. No stray `.og.tmp` files survive a successful write.

---

## 5. Append-only version history

`src/hachi/core/og_history.py` implements a Tier-1 append-only sidecar store.

**Storage:** `<skills_dir>/.og-history/<slug>.jsonl` — one JSON line per version.

Each line:
```json
{
  "version": 3,
  "timestamp": "2026-06-23T10:00:00+00:00",
  "author": "agent",
  "summary": "added caching step",
  "sha256": "abc123…",
  "content": "::meta\ntitle: my-skill\n…"
}
```

**Guarantees:**
- File is opened in `"a"` (append) mode only — existing lines are never rewritten.
- Version numbers are monotonically increasing (count of non-empty lines + 1).
- `list_versions()` excludes `content` to keep memory bounded.
- `get_version(name, n)` returns the full snapshot for version `n`.
- The history directory (`.og-history/`) lives outside `learned/` and is not reachable
  via normal tool paths — the agent cannot delete history through its tool registry.

**Wave-2 CLI integration (`hachi og rollback`):**
```python
from hachi.core.og_history import record_version, list_versions, get_version

# Record a human-authored rollback
record_version(name, content, author="human", summary="rollback to v2", skills_dir=skills_dir)

# List available versions (no content)
versions = list_versions(name, skills_dir=skills_dir)

# Retrieve a specific snapshot
snapshot = get_version(name, 2, skills_dir=skills_dir)
```

---

## 6. Settings file security

`settings.toml` may contain API key environment variable names and, in legacy
configurations, direct credential references.  It is listed in `.gitignore` at repo
root and for project-local files (`**/.hachi/settings.toml`).

On POSIX the config loader checks that `settings.toml` is not world-writable.  A
world-writable settings file means any unprivileged process on the machine can inject
a rogue provider URL or escalate permissions.  Under `HACHI_CONFIG_STRICT=1` (or the
`strict=True` parameter), the loader raises `PermissionError` immediately rather than
logging a warning.

See `docs/guides/configuration.md` for the full settings reference.
