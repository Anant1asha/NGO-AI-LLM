# T-61 · Decide the authz model: delete the C1 ownership machinery or finish it

|  |  |
|---|---|
| **Source finding** | CF-15 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | 2–4 days **either way** (the ADR itself: half a day) |
| **Difficulty** | High — **this is a decision task first and a code task second** |
| **Files you will touch** | `docs/DECISIONS.md`, `docs/architecture/adr/0006-*.md` (new), then either `src/hachi/gateway/fastapi_app.py` + `src/hachi/gateway/control_plane.py` (delete path) or those plus a persistence layer (finish path) |
| **See also** | [T-62](T-62-session-messages-ownership-check.md) — the cheap fix worth doing **regardless of what you decide here** |

---

## 1. Brief

The gateway carries a per-session ownership system ("C1"): sha256 token digests, owner
maps, 403 paths, owner-filtered list endpoints. It cannot discriminate between callers,
because **exactly one bearer token exists per process**. Every authenticated caller
hashes to the same digest, so every ownership comparison compares a value to itself.

It is also incomplete in ways that matter if a second principal ever appears: the owner
map is in-memory only, `set_session_owner` is a **silent no-op** when the session isn't
in the live-connection map, and a missing owner is documented as *allow*.

Your job is to **write the ADR and pick a side**: delete the machinery and be honestly
single-principal, or finish it. Both are defensible. The current middle is not.

## 2. Why this matters

This is the worst state a security control can be in: enough ceremony that readers
believe it works, not enough capability to do anything. Every future contributor —
human or agent — will read `_check_session_ownership`, `owner_token_hash` and the 403
branch and reasonably conclude that Hachi enforces per-caller session isolation. It
does not. It cannot.

That misreading has a cost even before a second token exists. It is why
[T-62](T-62-session-messages-ownership-check.md)'s missing check went unnoticed: when a
control is decorative, an inconsistency in it doesn't look like a bug. And the day
someone adds a second token — a shared team gateway, a service account, an API key per
integration — the decorative control becomes a real hole in whichever routes were
never wired, with an owner map that evaporates on restart.

An honest "Hachi is single-principal; the bearer token *is* the identity" is a
perfectly good v1 posture and matches the repo's stated stance
([CLAUDE.md](../../../../CLAUDE.md): multi-tenant is out of scope, "single-tenant is
load-bearing"). Half-built multi-principal is not.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 There is exactly one token per process

`create_gateway_app` takes a single token as a factory parameter
(`gateway/fastapi_app.py:441-447`):

```python
def create_gateway_app(
    control_plane: GatewayControlPlane,
    auth_token: str | None = None,
    *,
    bind_host: str | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
```

and there is exactly **one** comparison against it, inside `_require_auth`
(`:556`), at `:592-599`:

```python
        expected = f"Bearer {auth_token}"
        received = request.headers.get("Authorization", "")
        if not secrets.compare_digest(received.strip(), expected):
            raise _AuthRequired()
        raw_token = received.strip()[len("Bearer ") :].strip()
        # C1: return the sha256 digest so routes can compare ownership without
        # storing or comparing the raw bearer value.
        return hashlib.sha256(raw_token.encode()).hexdigest()
```

Because `:594` rejects anything that isn't the one configured token, **every** caller
that reaches `:599` produces the **same** digest. `_check_session_ownership` can
therefore only ever compare a value to itself.

**Complexity without capability.** That is the finding, stated precisely.

### 3.2 The owner map is in-memory — `gateway/control_plane.py:370-383`

```python
    def set_session_owner(self, session_id: str, owner_token_hash: str) -> None:
        """Record the sha256(bearer_token) digest as the owner of this session.

        C1 — called by the FastAPI layer immediately after create_session returns,
        using the digest of the validated bearer token.  Stored in-memory for
        fast O(1) ownership checks on every subsequent request.
        ...
        """
        with self._connections_lock:
            if session_id in self._connections:
                self._connections[session_id]["owner_token_hash"] = owner_token_hash
```

The digest is a key on the live-connection dict. Nothing persists it.

### 3.3 ⚠️ Two extra traps the review missed

**(a) `set_session_owner` is a silent no-op.** Look at `:382` above: if `session_id`
is not already in `self._connections`, the assignment simply doesn't happen. No raise,
no log, no return value. The caller — `create_session` at `fastapi_app.py:787-788` —
cannot tell:

```python
        if caller_hash is not None:
            control_plane.set_session_owner(result["session_id"], caller_hash)
```

**(b) No owner means allow.** `get_session_owner` (`control_plane.py:385-396`)
documents it as policy:

```python
    def get_session_owner(self, session_id: str) -> str | None:
        """Return the stored owner_token_hash for a session, or None if not set.

        C1 — None means a legacy / no-auth session; callers MUST allow access
        (backward-compat policy: NULL owner = allow).
        ...
        """
```

and `_check_session_ownership` implements it (`fastapi_app.py:762-770`):

```python
        if caller_hash is None:
            # No-auth mode or unconfigured token: skip ownership check.
            return
        owner = control_plane.get_session_owner(session_id)
        if owner is not None and not secrets.compare_digest(owner, caller_hash):
            raise HTTPException(
                status_code=403,
                detail="access denied: session is owned by another caller",
            )
```

Compose (a) and (b): **after any restart, `_connections` is empty, so every persisted
session has no owner, so every session is open to any authenticated caller.** The
ownership system's steady state across a process lifetime is "off".

### 3.4 Enforcement is also inconsistent

Two session routes perform no ownership check at all —
`POST /sessions/cleanup-empty` (`fastapi_app.py:1003-1030`) and
`GET /sessions/{session_id}/messages` (`:1036-1067`) — for a structural reason
documented in [T-62](T-62-session-messages-ownership-check.md) §3. Both **are**
bearer-authenticated via the router-level dependency (`:710`, `:713`); it is the
per-session owner comparison they skip.

Full inventory of the routes that **do** check, for the "finish it" option:

| Route | Anchor |
|---|---|
| `GET /sessions` (owner-filters inline) | `:791-813`, filter at `:803-812` |
| `GET /sessions/{id}` | `:817` |
| `POST /sessions/{id}/messages` | `:953` |
| `DELETE /sessions/{id}` | `:977` |
| `POST /sessions/{id}/interrupt` | `:997` |
| `POST /sessions/{id}/permissions/always-allow` | `:1089` (skipped for the `"current"` sentinel, `:1087-1088`) |
| `GET /sessions/{id}/events` | `:1099` |
| `GET /sessions/{id}/stream` | `:1124` |
| `GET /runs` (inline owner filter) | `:2521`, filter at `:2529-2535` |
| `GET /runs/{run_id}` | `:2548` via `_check_run_ownership` (`:2510`) |
| `POST /runs/{run_id}/wake` | `:2575` |
| (fourth run route) | `:2634` |
| `GET /interactions` | `:2944`, plus inline filter `:2949-2955` |
| `PUT /interactions/{id}/rating` | `:2987` |

Note: the review labelled the last two "approvals" — they are **interactions** routes
(`interactions_router`, `:2914-2918`).

### 3.5 Token rotation orphans everything

Combining §3.1 and §3.2: the owner digest is `sha256(bearer)`. Rotate the token and
every in-memory owner digest becomes unmatchable. In practice §3.3 masks this — the map
is empty after the restart that rotation implies — but it is a real property of the
design that any "finish it" option must solve (identities must not be derived from the
credential).

## 4. Reproduce the failure

There is no runtime failure to reproduce — the machinery is inert, not broken. Prove
the inertness instead, and say so rather than inventing a command.

```bash
# 1. One token per process: one parameter, one comparison.
grep -n "auth_token" src/hachi/gateway/fastapi_app.py

# 2. The owner map is a key on the live-connection dict; nothing persists it.
grep -n "owner_token_hash" src/hachi/gateway/control_plane.py src/hachi/gateway/fastapi_app.py

# 3. No persistence layer knows about owners.
grep -rn "owner" src/hachi/core/session_store.py

# 4. How many routes check vs. how many session routes exist.
grep -c "_check_session_ownership(" src/hachi/gateway/fastapi_app.py
grep -c "@sessions\." src/hachi/gateway/fastapi_app.py
```

**You will see now:** (1) one factory parameter at `:443`, one comparison at `:592`,
one digest at `:599`; (2) writes only into `self._connections[...]`; (3) **nothing** —
the durable session store has no owner column; (4) 7 checks against 11 session routes.

**You should see after the fix:** under the delete option, greps (1)–(2) show no digest
plumbing at all; under the finish option, grep (3) returns an owner column and grep (4)
shows every route covered.

**A live demonstration of §3.3** (only if you already have a gateway running — do not
set one up just for this): create a session, restart the gateway, then
`GET /sessions/{id}` with the same token. It succeeds — as it should, single-principal
— but it succeeds because the owner is `None`, not because you matched. There is no
observable difference between "correctly authorised" and "authorisation absent", which
is the whole problem.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> **This task's primary deliverable is the ADR, not the diff.** Do not start deleting
> or building until the decision is written down and agreed. Per
> [CLAUDE.md](../../../../CLAUDE.md), multi-tenancy is explicitly out of scope and must
> be *flagged for a decision*, not auto-built — this is that flag.
>
> **(a) DELETE — be honestly single-principal. RECOMMENDED.**
> Remove the digest return from `_require_auth` (it goes back to `-> None` or a bool),
> delete `_check_session_ownership`, `_check_run_ownership`, `set_session_owner`,
> `get_session_owner`, the `owner_token_hash` key, the inline owner filters at
> `:803-812` / `:2529-2535` / `:2949-2955`, and the 403 branch. The bearer token is the
> identity; possession of it is full authority; say so in one sentence in the API docs.
> *For:* the code then matches reality; ~200 lines of misleading ceremony disappear;
> [T-62](T-62-session-messages-ownership-check.md)'s inconsistency stops mattering;
> no future contributor is misled. Aligns with the repo's declared single-tenant stance.
> *Against:* it *feels* like losing work, and if multi-principal ever arrives it must be
> rebuilt. That is the right trade: rebuilding it properly later is cheaper than
> maintaining a decoy now, and the deleted code is in git.
> *Risk:* the delete touches ~14 route handlers. Mechanical, but wide.
>
> **(b) FINISH — make it real.** Requires all four of:
> 1. **Persisted owners** — an owner column on the durable session store (`grep -rn "owner" src/hachi/core/session_store.py` returns nothing today), not a key on `_connections`.
> 2. **Token identities** — a principal id that is *not* `sha256(bearer)`, so rotation doesn't orphan sessions (§3.5). That means a token table, which means token issuance, which means token management UI or CLI.
> 3. **Uniform enforcement** — including the two routes in §3.4 and any future one; ideally a dependency, not a per-handler call, so "forgot to check" is structurally impossible.
> 4. **Fail-closed default** — `None` owner must stop meaning *allow*, which requires a migration for existing ownerless rows.
> *For:* real isolation; a prerequisite if a shared/team gateway is ever on the roadmap.
> *Against:* this is multi-tenancy's front door, which CLAUDE.md puts out of scope. 2–4 days
> is honest only for the mechanism, not for the token-management product surface around it.
>
> **(c) Keep the middle.** Not an option. Say why in the ADR so it is settled.
>
> **Recommendation: (a).** Ship an honest single-principal gateway, record the decision,
> and let a future ADR supersede it if a second principal is ever needed.

Target state, either way:

1. **`docs/architecture/adr/0006-<kebab-title>.md` exists** with the repo's required
   sections — `scripts/check_adrs.py:27` enforces `## Context`, `## Decision`,
   `## Consequences`, and the filename must be `NNNN-kebab-case.md`. Follow
   `0005-observability-correlation-and-injected-exporter.md` for the header block
   (`**Status:**`, `**Date:**`, `**Related:**`).
2. It is **indexed** in `docs/architecture/adr/README.md` (the linter fails orphans).
3. A summary entry is added to `docs/DECISIONS.md`.
4. The code matches the ADR. No third state.
5. Observable outcome: a reader of `fastapi_app.py` can tell, in under a minute, whether
   Hachi enforces per-caller session isolation — and the answer the code gives is true.

## 6. Steps

1. **Write the ADR first.** Context (§3 of this file is your evidence), Decision,
   Consequences. Get it agreed before writing code. If you cannot get agreement, stop
   here and hand over the ADR — a written, unresolved decision is a better deliverable
   than an unwritten resolved one.
2. Add it to `docs/architecture/adr/README.md` and run
   `uv run python scripts/check_adrs.py`.
3. Append a summary to `docs/DECISIONS.md`.
4. Write the regression test from §7 and watch it **fail**.
5. **Do [T-62](T-62-session-messages-ownership-check.md) first if you chose (b)** —
   it is 2 hours and it is a prerequisite for "uniform enforcement". If you chose (a),
   T-62 is superseded; say so in its file and in your commit message.
6. Execute the chosen option. Under (a), work route by route from the §3.4 table; under
   (b), do the persistence layer before touching any route.
7. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**

This task is unusual: under option (a) you are removing a control, so the test pins the
*decision* rather than a fixed bug. Write it anyway — an undocumented deliberate
removal is indistinguishable from an accidental one.

- **File:** `tests/test_session_authz_model.py` (**new**)
- **Test name (option a):** `test_gateway_is_single_principal_by_decision`
- **Test name (option b):** `test_session_owner_survives_restart`
- **It must assert:** the real, observed behaviour of a running app via `TestClient` —
  not the presence or absence of a function.
- **It must FAIL before your change:** under (a), because the ownership plumbing still
  exists; under (b), because a fresh control plane has no owner for a persisted session.

```python
# sketch — OPTION (b). Adapt to the repo's existing gateway fixtures.
def test_session_owner_survives_restart() -> None:
    """Ownership must be durable, not a key on the live-connection dict.

    Regression: set_session_owner() wrote into control_plane._connections and was
    a SILENT NO-OP when the session wasn't there; get_session_owner() returning
    None was documented as "allow". So after any restart every persisted session
    was ownerless and open to any authenticated caller.
    """
    cp = _build_control_plane()
    app = create_gateway_app(cp, auth_token="token-a", bind_host="127.0.0.1")
    client = TestClient(app)
    sid = client.post("/sessions", json={...}, headers=_bearer("token-a")).json()["session_id"]

    # Simulate a restart: brand-new control plane over the same durable store.
    cp2 = _build_control_plane()
    assert cp2.get_session_owner(sid) is not None, (
        "session owner did not survive a control-plane restart; ownership is "
        "in-memory only and every session is ownerless (=allowed) after a restart"
    )


# sketch — OPTION (a). The assertion is that the misleading machinery is gone.
def test_gateway_is_single_principal_by_decision() -> None:
    """ADR-0006: the bearer token IS the identity; there is no per-session owner.

    This test exists so the removal reads as deliberate. If you are reintroducing
    per-caller ownership, supersede ADR-0006 first — do not just delete this test.
    """
    from hachi.gateway import control_plane as cp_mod
    from hachi.gateway import fastapi_app as app_mod

    assert not hasattr(cp_mod.GatewayControlPlane, "set_session_owner")
    assert not hasattr(cp_mod.GatewayControlPlane, "get_session_owner")
    assert "owner_token_hash" not in Path(app_mod.__file__).read_text(encoding="utf-8")
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] `docs/architecture/adr/0006-*.md` exists, has `## Context` / `## Decision` / `## Consequences`, and states which option was chosen **and why the other was rejected**.
- [ ] `uv run python scripts/check_adrs.py` passes and the ADR is linked from `docs/architecture/adr/README.md` (no orphan).
- [ ] `docs/DECISIONS.md` has a summary entry.
- [ ] The regression test from §7 exists and failed before the change.
- [ ] **Option (a):** `grep -rn "owner_token_hash\|_check_session_ownership\|_check_run_ownership" src/` returns nothing; `_require_auth` no longer returns a digest.
- [ ] **Option (b):** `grep -rn "owner" src/hachi/core/session_store.py` shows a persisted column; every route in §3.4 plus the two in [T-62](T-62-session-messages-ownership-check.md) is covered; a missing owner is **denied**, not allowed.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not build multi-tenancy.** This is the thing you will drift into, because option
  (b) looks like the "complete" answer and multi-tenancy is its natural next step.
  [CLAUDE.md](../../../../CLAUDE.md) puts it explicitly out of scope: *"Multi-tenant
  support (single-tenant is load-bearing) — flag for a decision."* Even option (b) is
  **per-principal isolation within one tenant**, not tenancy. If your design grows an
  org/workspace concept, stop and escalate.
- **Do not change the authentication path while changing the authorisation path.**
  `_require_auth`'s bearer comparison (`:592-595`), the `HACHI_GATEWAY_NO_AUTH` opt-out
  (`:584`), and the startup guards (`:490`, `:503`) are separate, tested, security-
  critical machinery with their own audit history (MR-2 / UC-AUTH-001 / ADV-014 /
  CRIT-001 are all named in that docstring). Touch ownership only.
- **Do not "fix" the `"current"` sentinel** at `:1087-1088`. It is a deliberate,
  commented exception for a frontend convention (`:1069-1074`). It becomes moot under
  (a) and needs its own design under (b).
- **Do not leave the middle state.** Partially deleting (say, removing the checks but
  keeping `set_session_owner`) is strictly worse than either endpoint.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). Tests that assert the *old* ownership behaviour under option (a) are a contract change, not a weakening: rewrite them to assert the new contract and say so explicitly in the commit message.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/check_adrs.py          # ADR well-formed + indexed
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. Under either option you are touching ~14 route handlers and the
control plane's connection map, which every gateway test exercises. Report the
**actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Session-ownership checks could never discriminate, and were off after every restart

- **Symptom:** The gateway appeared to enforce per-caller session isolation (token digests, 403 paths, owner-filtered lists) while enforcing nothing. Two session routes skipped the check entirely, and after any restart *every* persisted session was ownerless — which the policy defines as "allow".
- **Root cause:** Exactly one bearer token exists per process (`fastapi_app.py:443`, compared once at `:592`), so every authenticated caller hashed to the same digest at `:599` and `_check_session_ownership` compared a value to itself. Ownership was stored as a key on the in-memory live-connection dict (`control_plane.py:381-383`), and `set_session_owner` was a **silent no-op** when the session wasn't in `_connections`. `get_session_owner` returning `None` is documented as allow (`:388-389`).
- **Fix:** ADR-0006 settled the model. <Record which option was taken and the resulting code state.>
- **Avoid:** never ship a security control that cannot fail. If a comparison can only ever compare a value to itself, it is documentation, not enforcement — and readers will trust it. Either give it a second principal to discriminate, or delete it and state the model plainly.
- **Locked by:** `tests/test_session_authz_model.py` — `test_gateway_is_single_principal_by_decision` (or `test_session_owner_survives_restart`)
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-4:** any gateway route change ⇒ regenerate the OpenAPI spec **and** the frontend
  API types, or CI fails. `scripts/preflight.py:124-131` runs
  `hachi gateway-openapi` + `npm run check:api` as a blocking step. Removing a 403
  response or changing a signature changes the schema.
- **`src/hachi/gateway/fastapi_app.py` IS in the strict mypy gate**
  (`mypy-strict-gate.ini`). Every edit must be strict-clean — including the return-type
  change to `_require_auth` under option (a), which ripples into ~14 handlers.
- **`_require_auth` has two legitimate `None` returns** (`:584-591`): no-auth mode and
  the unit-test/OpenAPI-export path with `auth_token=None`. Under option (b), do not
  "tighten" those into denials without reading the docstring at `:556-583` — the export
  command and a large number of unit tests depend on them.
- **The router-level dependency discards the digest.** `protected_dependencies` at
  `:710` is `[Depends(_require_auth)]`; FastAPI runs it for auth but the return value is
  thrown away. That is *why* handlers re-call `_require_auth(request)` themselves. Any
  "make it a dependency" design under option (b) must return the principal into the
  handler (e.g. `caller: Annotated[str, Depends(_require_auth)]`), not just run it.
- **`GET /sessions` and `GET /interactions` filter inline, they do not raise**
  (`:803-812`, `:2949-2955`). Under option (a) those filters must be removed too, or
  you will leave dead per-item lookups; under (b) they must be reconciled with the
  fail-closed default, since "owner is None → include" is the opposite policy.
