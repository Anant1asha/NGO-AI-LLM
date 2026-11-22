"""Tests for the IdempotencyGuard dedup primitive (AUDIT Theme A — P0-3).

Covers the three-call begin/finish/abort protocol, concurrent-duplicate suppression,
TTL expiry (via an injected fake clock — no real sleeping), thread-safety under a burst
of concurrent begins, and the key composer.
"""

from __future__ import annotations

import threading

from hachi.core.idempotency import IdempotencyGuard, make_idempotency_key


class FakeClock:
    """Deterministic monotonic clock for TTL tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# -- begin / finish / abort protocol ----------------------------------------


def test_first_begin_reserves_and_reports_not_duplicate() -> None:
    guard = IdempotencyGuard()
    is_dup, prior = guard.begin("k")
    assert is_dup is False
    assert prior is None
    assert len(guard) == 1  # reserved


def test_concurrent_duplicate_before_finish_has_no_prior() -> None:
    guard = IdempotencyGuard()
    guard.begin("k")  # reserve, still in flight
    is_dup, prior = guard.begin("k")
    assert is_dup is True
    assert prior is None  # nothing to replay yet


def test_finished_result_is_replayed_for_duplicates() -> None:
    guard = IdempotencyGuard()
    guard.begin("k")
    guard.finish("k", "Sent message to Slack (#ops).")
    is_dup, prior = guard.begin("k")
    assert is_dup is True
    assert prior == "Sent message to Slack (#ops)."


def test_abort_releases_pending_so_a_retry_can_proceed() -> None:
    guard = IdempotencyGuard()
    guard.begin("k")
    guard.abort("k")
    assert len(guard) == 0
    # A genuine retry after a failure must be allowed through.
    is_dup, prior = guard.begin("k")
    assert is_dup is False and prior is None


def test_abort_does_not_clear_a_finished_result() -> None:
    guard = IdempotencyGuard()
    guard.begin("k")
    guard.finish("k", "done")
    guard.abort("k")  # late failure after success must not erase the dedup record
    is_dup, prior = guard.begin("k")
    assert is_dup is True and prior == "done"


def test_abort_on_unknown_key_is_safe() -> None:
    guard = IdempotencyGuard()
    guard.abort("never-seen")  # must not raise
    assert len(guard) == 0


# -- TTL expiry --------------------------------------------------------------


def test_entry_expires_after_ttl() -> None:
    clock = FakeClock()
    guard = IdempotencyGuard(ttl_seconds=120.0, clock=clock)
    guard.begin("k")
    guard.finish("k", "done")

    clock.advance(119.0)  # still inside the window
    is_dup, prior = guard.begin("k")
    assert is_dup is True and prior == "done"

    clock.advance(2.0)  # now past 120s
    is_dup, prior = guard.begin("k")
    assert is_dup is False and prior is None  # treated as a fresh send


def test_len_purges_expired_entries() -> None:
    clock = FakeClock()
    guard = IdempotencyGuard(ttl_seconds=10.0, clock=clock)
    guard.finish("a", "x")
    guard.finish("b", "y")
    assert len(guard) == 2
    clock.advance(11.0)
    assert len(guard) == 0


# -- key composition ---------------------------------------------------------


def test_make_key_is_stable_and_discriminating() -> None:
    k1 = make_idempotency_key("send_slack_message", "#ops", "hello")
    k2 = make_idempotency_key("send_slack_message", "#ops", "hello")
    assert k1 == k2
    assert k1.startswith("send_slack_message:#ops:")
    # Any component changing yields a different key.
    assert make_idempotency_key("send_slack_message", "#ops", "hello!") != k1
    assert make_idempotency_key("send_slack_message", "#eng", "hello") != k1
    assert make_idempotency_key("send_discord_message", "#ops", "hello") != k1


def test_make_key_hashes_long_payload_to_bounded_length() -> None:
    key = make_idempotency_key("scope", "target", "x" * 100_000)
    # scope + target + 16-hex digest + two separators — far shorter than the payload.
    assert len(key) < 100


# -- thread-safety -----------------------------------------------------------


def test_only_one_of_many_concurrent_begins_wins() -> None:
    """Under a race on one key, exactly one begin reserves; the rest see a duplicate."""
    guard = IdempotencyGuard()
    winners: list[bool] = []
    lock = threading.Lock()
    start = threading.Event()

    def worker() -> None:
        start.wait()
        is_dup, _ = guard.begin("hot-key")
        if not is_dup:
            with lock:
                winners.append(True)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert len(winners) == 1  # exactly one non-duplicate reservation
