# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest on `main` | Yes |

Hachi is currently pre-1.0 (development release). Security fixes are applied
to the `main` branch only; no backport branches exist yet.

## Reporting a Vulnerability

**Do not report security issues in public GitHub issues.**

Email: **security@opengigantic.com**

Please include:
- A clear description of the vulnerability
- Steps to reproduce (or a minimal proof-of-concept)
- The affected component (e.g., `gateway/fastapi_app.py`, permission gate, credential store)
- The potential impact

We aim to acknowledge reports within **48 hours** and will communicate a triage
decision within **7 days**. Critical issues (remote code execution, credential leak,
permission-gate bypass) are treated as P0 and patched on an accelerated track.

## Responsible Disclosure

We follow coordinated disclosure. Please give us **90 days** to investigate and ship
a fix before public disclosure. We will credit researchers (by name or alias, your
choice) in the release notes unless you request anonymity.

## Scope

Security issues we consider in-scope:

- **Permission gate bypass** — any path that executes an OS command or filesystem
  write outside the declared roots in `device-permissions.og`
  (`src/hachi/tools/permissions.py`)
- **Credential/secret exposure** — credentials leaking via logs, API responses,
  error messages, or the session transcript (`src/hachi/core/session_store.py`)
- **Gateway authentication bypass** — `src/hachi/gateway/fastapi_app.py`
  bearer-token gate skipped under any condition
- **Session isolation failures** — one user's session data readable by another
  session or by the gateway's event stream
- **Sub-agent privilege escalation** — a delegated sub-agent exceeding its declared
  scope (`src/hachi/core/sub_agent.py` `PermissionScope`)
- **Dependency confusion / supply-chain** — malicious `.ogpack` installable without
  user consent (when the pack marketplace ships in P2)

Out of scope (use regular GitHub issues):

- Rate limiting / DoS against a locally-hosted gateway
- Issues requiring physical access to the machine
- Social-engineering attacks against the user (Hachi is a local-first tool)

## Trust model

**Hachi is a single-operator product.** One trusted operator per machine / VPS. It is NOT
multi-tenant. Do NOT expose a shared Hachi gateway to multiple distinct users or tenants.

### Memory isolation (AUDIT P1-1)

All ChromaDB collections (`core_memory`, `user_profile`, `agent_profile`, `delegation_log`) are
shared per install. The `MemoryVault` accepts an `account_id` parameter that namespaces
collections with a per-account prefix (ADV-023), but this parameter is **intentionally unplumbed**
in the current release — `boot_agent` constructs the vault with no `account_id`, and the
`principal` field in `TraceContext` is a hardcoded `"session"` placeholder
(`src/hachi/gateway/orchestrator.py`).

**Under the single-operator trust model this is safe** because only one authenticated principal
exists in a normal install.

**It becomes unsafe the moment a second user is added.** Two principals sharing one install would
share one `user_profile` / `core_memory` collection, enabling cross-user PII recall and profile
contamination.

**Do NOT add a second principal/tenant without:**
1. Plumbing the authenticated principal → `account_id` into `MemoryVault` construction.
2. Updating the `ProcessSharedServices` fingerprint to include the account key so each account
   gets a separate shared-vault singleton.

The `account_id` seam is already built into `MemoryVault.__init__` — it just needs to be wired
from the authentication layer. See `src/hachi/core/memory_vault.py` docstring (ADV-023) and
`DECISIONS.md` "P1-1 — document the single-tenant constraint" for the full design note.

Multi-tenant account isolation is tracked as a 12-month roadmap item (AUDIT P1-1 action b).

## Security Architecture Notes

- **No remote code execution path in skill install** — `.og` files are data files parsed
  by a pure-Python parser; they do not execute code at install time. This is a
  deliberate design constraint (`docs/strategy/05-agent-platform.md` §6).
- **PermissionGate** enforces filesystem roots and shell-command allowlists at
  call time, not at prompt time (`src/hachi/tools/permissions.py`).
- **Credentials** are stored in the system keyring via `keyring`; the `.env`
  fallback path is documented as development-only (`src/hachi/core/llm.py:50–52`).
- **Memory quarantine** — writes from untrusted content are quarantined and require
  explicit user approval before entering long-term storage
  (`src/hachi/core/memory_vault.py` `MemoryGuard`).
- **Docker non-root runtime** — the published container image runs as UID 10001
  (`hachi` user, no supplementary groups). The gateway process never requires root
  and has no `sudo`/`setuid` paths.

## CI Security Gates

Every push and pull request runs the following automated security checks:

| Check | Tool | Trigger | Failure behaviour |
|-------|------|---------|-------------------|
| Dependency CVE scan | `pip-audit` | push + PR | Advisory on `main`; **blocking on PRs** |
| SAST (medium+ severity) | `bandit -ll` | push + PR | Advisory until src/ medium findings resolved |
| Application security audit | `hachi security-audit` | push + PR | Blocking on `--fail-on-high`; `--fail-on-medium` on PRs |

### Dependency CVE posture (last audited 2026-11-16)

| Package | Version | Advisory status |
|---------|---------|-----------------|
| `aiohttp` | **3.14.5** (was 3.13.5) | Resolved — OSV reports 31 advisories against 3.13.5 (12 HIGH, 14 moderate, 5 low); the high-severity class is fixed in 3.14.x |
| `cryptography` | **50.0.2** (was 49.0.0) | Resolved — `CVE-2026-69247` (HIGH, PKCS#7 Bleichenbacher) fixed in 50.0.0 |
| `starlette` | **1.3.1** | No outstanding advisories reported for this version |
| `chromadb` | **1.5.9 — no fixed release exists** | Four unpatched advisories; see scope analysis below |

`aiohttp` is transitive (chromadb → kubernetes) and is held by `uv.lock`; Hachi
never imports it. `cryptography` is a direct dependency and its declared floor
was raised to `>=50.0.0` so the **published metadata** excludes the vulnerable
version, not merely our own lock file.

#### chromadb advisory scope — scoped acceptance, not dismissal

`chromadb` 1.5.9 is the newest release on PyPI and carries four unpatched
advisories, two of them critical:

| Advisory | What it is |
|---|---|
| `CVE-2026-45829` | Pre-auth code injection via a model repository supplied to a **server** endpoint with `trust_remote_code` |
| `CVE-2026-45833` | Code injection via the same **server** endpoint (authenticated) |
| `CVE-2026-45830` | Cross-**tenant** read/write/delete on a server deployment |
| `CVE-2026-45831` | `SimpleRBACAuthorizationProvider` does not scope permissions by tenant/database/collection |

**All four are defects in chromadb's HTTP server API (`/api/v2/...`).** Hachi
does not use that surface:

- it constructs **`chromadb.PersistentClient` only** — embedded, in-process, no
  listener, and no `/api/v2` route ever exposed;
- it never imports `chromadb.HttpClient` and never runs `chroma run`;
- it never sets `trust_remote_code`;
- it is **single-tenant** by design, so the two tenant-isolation advisories have
  no subject here.

`tests/test_dependency_policy.py` locks the first three properties
structurally — adding server mode, an HTTP client, or `trust_remote_code` fails
CI rather than silently widening exposure.

This does not mean the dependency is safe in general: the vulnerable code is
still present in the tree, and an advisory affecting **embedded** mode would
apply immediately. Re-audit on every chromadb release, and prefer moving it
behind an optional extra if an embedded-mode advisory ever lands.

To suppress a CVE in CI once a justified exception is needed, add
`--ignore-vuln <ID>` to the `pip-audit` step in `.github/workflows/ci.yml` with a
comment that references the tracking issue. Do not add ignores without a public issue.
