"""Tests for EventBus — publish/subscribe, pattern matching, exception isolation."""

from __future__ import annotations

import threading
from typing import Any

from hachi.core.event_bus import EventBus, Subscription, _pattern_matches
from hachi.core.runtime_events import RuntimeEvent, now_iso

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(name: str, payload: dict[str, Any] | None = None) -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())


# ---------------------------------------------------------------------------
# Pattern matching unit tests
# ---------------------------------------------------------------------------


class TestPatternMatches:
    def test_wildcard_matches_anything(self):
        assert _pattern_matches("*", "session.chat.started")
        assert _pattern_matches("*", "tool.call.started")
        assert _pattern_matches("*", "x")

    def test_prefix_wildcard_matches_prefix(self):
        assert _pattern_matches("session.*", "session.chat.started")
        assert _pattern_matches("session.*", "session.persisted")
        assert _pattern_matches("tool.call.*", "tool.call.started")
        assert _pattern_matches("tool.call.*", "tool.call.completed")

    def test_prefix_wildcard_no_false_positive(self):
        assert not _pattern_matches("session.*", "tool.call.started")
        assert not _pattern_matches("session.*", "sessions.foo")  # must start with "session."

    def test_exact_match(self):
        assert _pattern_matches("session.chat.started", "session.chat.started")
        assert not _pattern_matches("session.chat.started", "session.chat.completed")

    def test_exact_no_partial(self):
        assert not _pattern_matches("session", "session.chat.started")


# ---------------------------------------------------------------------------
# EventBus: subscribe / unsubscribe
# ---------------------------------------------------------------------------


class TestSubscribe:
    def test_subscribe_returns_subscription(self):
        bus = EventBus()
        sub = bus.subscribe("*", lambda e: None)
        assert isinstance(sub, Subscription)
        assert bus.subscription_count == 1

    def test_unsubscribe_removes(self):
        bus = EventBus()
        sub = bus.subscribe("*", lambda e: None)
        bus.unsubscribe(sub)
        assert bus.subscription_count == 0

    def test_unsubscribe_noop_when_already_removed(self):
        bus = EventBus()
        sub = bus.subscribe("*", lambda e: None)
        bus.unsubscribe(sub)
        bus.unsubscribe(sub)  # second call must not raise
        assert bus.subscription_count == 0

    def test_clear_removes_all(self):
        bus = EventBus()
        bus.subscribe("*", lambda e: None)
        bus.subscribe("session.*", lambda e: None)
        bus.clear()
        assert bus.subscription_count == 0


# ---------------------------------------------------------------------------
# EventBus: publish fan-out
# ---------------------------------------------------------------------------


class TestPublish:
    def test_sync_subscriber_receives_event(self):
        bus = EventBus()
        received: list[RuntimeEvent] = []
        bus.subscribe("*", received.append)

        ev = _event("tool.call.started")
        seq = bus.publish(ev)

        assert len(received) == 1
        assert received[0] is ev
        assert seq == 1

    def test_sequence_numbers_monotonic(self):
        bus = EventBus()
        seqs: list[int] = []
        bus.subscribe("*", lambda e: None)

        for _ in range(5):
            seqs.append(bus.publish(_event("x")))

        assert seqs == list(range(1, 6))

    def test_pattern_filtering(self):
        bus = EventBus()
        session_events: list[RuntimeEvent] = []
        tool_events: list[RuntimeEvent] = []

        bus.subscribe("session.*", session_events.append)
        bus.subscribe("tool.*", tool_events.append)

        bus.publish(_event("session.chat.started"))
        bus.publish(_event("tool.call.started"))
        bus.publish(_event("boot.complete"))

        assert len(session_events) == 1
        assert len(tool_events) == 1

    def test_multiple_subscribers_all_receive(self):
        bus = EventBus()
        calls: list[int] = []

        bus.subscribe("*", lambda e: calls.append(1))
        bus.subscribe("*", lambda e: calls.append(2))
        bus.subscribe("*", lambda e: calls.append(3))

        bus.publish(_event("anything"))
        assert calls == [1, 2, 3]

    def test_no_subscribers_does_not_raise(self):
        bus = EventBus()
        seq = bus.publish(_event("some.event"))
        assert seq == 1


# ---------------------------------------------------------------------------
# EventBus: exception isolation (GATE requirement)
# ---------------------------------------------------------------------------


class TestExceptionIsolation:
    def test_sync_exception_does_not_propagate(self):
        bus = EventBus()
        bad_calls = []
        good_calls = []

        def bad_handler(e: RuntimeEvent) -> None:
            bad_calls.append(e)
            raise RuntimeError("intentional failure")

        bus.subscribe("*", bad_handler)
        bus.subscribe("*", good_calls.append)

        # Must not raise
        seq = bus.publish(_event("test.event"))

        assert seq == 1
        assert len(bad_calls) == 1  # bad handler was called
        assert len(good_calls) == 1  # good handler still ran

    def test_multiple_exceptions_all_continue(self):
        bus = EventBus()
        order: list[str] = []

        def handler_a(e: RuntimeEvent) -> None:
            order.append("a")
            raise ValueError("a fails")

        def handler_b(e: RuntimeEvent) -> None:
            order.append("b")
            raise TypeError("b fails")

        def handler_c(e: RuntimeEvent) -> None:
            order.append("c")

        bus.subscribe("*", handler_a)
        bus.subscribe("*", handler_b)
        bus.subscribe("*", handler_c)

        bus.publish(_event("x"))
        assert order == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# EventBus: async dispatch (inline fallback — no queue)
# ---------------------------------------------------------------------------


class TestAsyncDispatch:
    def test_async_fallback_runs_inline_when_no_queue(self):
        bus = EventBus(job_queue=None)
        received: list[RuntimeEvent] = []
        bus.subscribe("*", received.append, mode="async", name="test_handler")

        bus.publish(_event("session.chat.started"))

        assert len(received) == 1

    def test_async_exception_inline_does_not_propagate(self):
        bus = EventBus(job_queue=None)

        def bad(e: RuntimeEvent) -> None:
            raise RuntimeError("async inline fail")

        bus.subscribe("*", bad, mode="async", name="bad_handler")
        bus.publish(_event("x"))  # must not raise


# ---------------------------------------------------------------------------
# EventBus: thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_publish_sequence_unique(self):
        bus = EventBus()
        sequences: list[int] = []
        lock = threading.Lock()

        def record(e: RuntimeEvent) -> None:
            pass

        bus.subscribe("*", record)

        def publish_many() -> None:
            for _ in range(50):
                seq = bus.publish(_event("concurrent"))
                with lock:
                    sequences.append(seq)

        threads = [threading.Thread(target=publish_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(sequences) == 200
        assert len(set(sequences)) == 200  # all unique

    def test_subscribe_unsubscribe_concurrent(self):
        bus = EventBus()
        subs: list[Subscription] = []
        lock = threading.Lock()

        def add_sub() -> None:
            for _ in range(20):
                sub = bus.subscribe("*", lambda e: None)
                with lock:
                    subs.append(sub)

        threads = [threading.Thread(target=add_sub) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert bus.subscription_count == 100
