"""idempotency.py — short-TTL dedup guard for side-effecting operations.

Theme A of the architecture audit (the "idempotency deficit"): Hachi acts on the
user's behalf, but nothing stops a side effect from happening *twice*. An LLM retry,
the 4-worker tool pool re-dispatching, a client reconnect, or a turn resume can all
re-run the same outbound send — producing a duplicate Slack/Discord/WhatsApp/Telegram
message or a duplicate recurring schedule. For an assistant whose entire promise is
*acting safely on your behalf*, duplicate side effects are the single most corrosive
trust failure.

``IdempotencyGuard`` is a tiny in-process, thread-safe, TTL-bounded table that records
the **successful** result of an operation keyed by its identity, and replays that result
(without re-executing the side effect) if the same key is seen again inside the window.
It mirrors the house style of :class:`hachi.core.lease_manager.LeaseManager` (a
``threading.Lock`` + ``time.monotonic`` + ``_expire_stale`` purge) but with
result-caching semantics instead of mutual-exclusion semantics.

Scope (deliberate, smallest-correct-first):
  - **In-process** only. This covers the dominant automatic retry paths — LLM retry,
    tool-pool re-dispatch, reconnect — which all happen within the same gateway process,
    seconds apart. Cross-process / post-restart dedup of *outbound* effects is out of
    scope here (the short window makes it moot); chat *ingress* idempotency, which must
    survive restarts, is handled durably at the gateway/``SessionStore`` layer instead.
  - **Successful effects only.** A failed attempt releases its reservation
    (:meth:`abort`) so a genuine retry is still allowed to go through.
  - **Single-operator trust model.** One process serves one principal, so the key need
    not include an account id today. When multi-tenancy lands, fold ``account_id`` into
    the key (see AUDIT P1-1).

Scope of one guard instance: construct **one per session** (e.g. per
``register_messaging_tools`` call) and share it across that session's side-effecting
tools. That covers every in-session retry path while never suppressing a genuinely
distinct send from a *different* concurrent session.

Usage::

    guard = IdempotencyGuard()
    key = make_idempotency_key("send_slack_message", channel, text)
    is_dup, prior = guard.begin(key)
    if is_dup:
        return prior or "duplicate suppressed"   # prior is None while a dup is in flight
    try:
        result = do_the_side_effect()
    except Exception:
        guard.abort(key)        # failed — let a retry try again
        raise
    guard.finish(key, result)   # success — replay this for any duplicate in the window
    return result
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

# Default dedup window for outbound side effects. Long enough to absorb retry/reconnect/
# resume storms (which fire within seconds), short enough that a user deliberately
# repeating the identical message to the identical target is not mistaken for a retry.
_OUTBOUND_TTL_SECONDS = 120.0


@dataclass
class _Entry:
    """One tracked operation.

    ``result is None`` means the operation is **reserved / in flight** (a concurrent
    duplicate should be suppressed but has no prior result to replay yet). A ``str``
    ``result`` means the operation **completed successfully** and that string is replayed
    for any duplicate seen before ``expiry``.
    """

    expiry: float
    result: str | None


class IdempotencyGuard:
    """Thread-safe, TTL-bounded dedup table that replays prior successful results.

    Each gateway process shares one guard per side-effect domain (see
    :func:`default_outbound_guard`). The contract is a three-call protocol —
    :meth:`begin` to reserve, then exactly one of :meth:`finish` (success) or
    :meth:`abort` (failure). ``begin`` is atomic, so two threads racing on the same key
    cannot both reserve it.
    """

    def __init__(
        self,
        ttl_seconds: float = _OUTBOUND_TTL_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def begin(self, key: str) -> tuple[bool, str | None]:
        """Atomically reserve *key* for a side effect.

        Returns ``(is_duplicate, prior_result)``:

        - ``(False, None)`` — first time inside the window. The key is now **reserved**;
          the caller MUST follow with exactly one :meth:`finish` or :meth:`abort`.
        - ``(True, "<result>")`` — a prior call already completed successfully; replay
          ``<result>`` and do **not** perform the side effect.
        - ``(True, None)`` — a concurrent call holds the reservation but hasn't finished;
          suppress this duplicate (there is no result to replay yet).
        """
        now = self._clock()
        with self._lock:
            self._expire_stale(now)
            entry = self._entries.get(key)
            if entry is not None:
                return True, entry.result
            self._entries[key] = _Entry(expiry=now + self._ttl, result=None)
            return False, None

    def finish(self, key: str, result: str) -> None:
        """Record the successful *result* for *key*, replayable until the TTL expires."""
        now = self._clock()
        with self._lock:
            self._entries[key] = _Entry(expiry=now + self._ttl, result=result)

    def abort(self, key: str) -> None:
        """Release a reservation made by :meth:`begin` because the side effect failed.

        Only clears a still-pending reservation — a key that already :meth:`finish`-ed
        (e.g. a late failure after a successful send) is left intact so its result keeps
        replaying. Safe to call on an unknown key.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.result is None:
                del self._entries[key]

    def __len__(self) -> int:
        """Number of live (non-expired) tracked keys — for tests/diagnostics."""
        now = self._clock()
        with self._lock:
            self._expire_stale(now)
            return len(self._entries)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _expire_stale(self, now: float) -> None:
        """Drop entries past their TTL. Must be called while holding ``self._lock``."""
        stale = [k for k, e in self._entries.items() if e.expiry <= now]
        for k in stale:
            del self._entries[k]


def make_idempotency_key(scope: str, target: str, payload: str) -> str:
    """Compose a stable dedup key from a scope, a target, and a payload.

    ``scope`` (e.g. the tool name) and ``target`` (e.g. the channel / recipient) are kept
    readable; ``payload`` (which may be long) is hashed so the key stays bounded. Two
    calls dedup iff all three match exactly.
    """
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{scope}:{target}:{digest}"
