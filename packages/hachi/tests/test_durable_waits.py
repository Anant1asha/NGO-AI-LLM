"""Tests for WaitConditionRegistry — arm/resolve/disarm, idempotency (GATE-RESUME)."""

from __future__ import annotations

import threading

from hachi.core.runtime.state import WaitCondition, WaitKind
from hachi.core.runtime.waits import WaitConditionRegistry, get_wait_registry
from hachi.core.runtime_events import now_iso

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait(kind: WaitKind = WaitKind.USER, key: str = "key-001") -> WaitCondition:
    return WaitCondition(kind=kind, key=key, created_at=now_iso())


# ---------------------------------------------------------------------------
# Basic arm / resolve
# ---------------------------------------------------------------------------


class TestArmResolve:
    def test_arm_then_resolve_returns_run_id(self):
        reg = WaitConditionRegistry()
        wait = _wait(key="approval-001")
        reg.arm("run-001", wait)

        run_id = reg.resolve("approval-001", {"decision": "approved"})
        assert run_id == "run-001"

    def test_resolve_unknown_key_returns_none(self):
        reg = WaitConditionRegistry()
        result = reg.resolve("nonexistent-key", {})
        assert result is None

    def test_arm_registers_condition(self):
        reg = WaitConditionRegistry()
        wait = _wait(key="evt-pattern")
        reg.arm("run-xyz", wait)

        condition = reg.get_condition("run-xyz")
        assert condition is not None
        assert condition.key == "evt-pattern"

    def test_resolve_clears_armed_entry(self):
        reg = WaitConditionRegistry()
        wait = _wait(key="k1")
        reg.arm("run-A", wait)
        reg.resolve("k1", {})

        # After resolve, key is gone from armed and condition is cleared
        assert reg.get_condition("run-A") is None
        assert ("k1", "run-A") not in reg.list_armed()


# ---------------------------------------------------------------------------
# Idempotency (GATE-RESUME: double-wake is no-op)
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_double_resolve_returns_none_second_time(self):
        reg = WaitConditionRegistry()
        wait = _wait(key="event-key")
        reg.arm("run-001", wait)

        first = reg.resolve("event-key", {})
        second = reg.resolve("event-key", {})  # double-wake

        assert first == "run-001"
        assert second is None  # idempotent: already resolved

    def test_triple_resolve_still_none(self):
        reg = WaitConditionRegistry()
        reg.arm("run-001", _wait(key="k"))
        reg.resolve("k", {})
        assert reg.resolve("k", {}) is None
        assert reg.resolve("k", {}) is None

    def test_different_keys_independent(self):
        reg = WaitConditionRegistry()
        reg.arm("run-A", _wait(key="key-A"))
        reg.arm("run-B", _wait(key="key-B"))

        assert reg.resolve("key-A", {}) == "run-A"
        assert reg.resolve("key-B", {}) == "run-B"

        # Both now resolved; double-wake returns None
        assert reg.resolve("key-A", {}) is None
        assert reg.resolve("key-B", {}) is None


# ---------------------------------------------------------------------------
# Disarm (cancel path)
# ---------------------------------------------------------------------------


class TestDisarm:
    def test_disarm_removes_condition(self):
        reg = WaitConditionRegistry()
        wait = _wait(key="k-cancel")
        reg.arm("run-C", wait)
        reg.disarm("run-C")

        assert reg.get_condition("run-C") is None
        assert reg.resolve("k-cancel", {}) is None

    def test_disarm_unknown_run_noop(self):
        reg = WaitConditionRegistry()
        reg.disarm("nonexistent-run")  # must not raise

    def test_disarm_after_resolve_noop(self):
        reg = WaitConditionRegistry()
        wait = _wait(key="k2")
        reg.arm("run-D", wait)
        reg.resolve("k2", {})
        reg.disarm("run-D")  # already gone — must not raise


# ---------------------------------------------------------------------------
# list_armed
# ---------------------------------------------------------------------------


class TestListArmed:
    def test_list_armed_empty(self):
        reg = WaitConditionRegistry()
        assert reg.list_armed() == []

    def test_list_armed_returns_all_active(self):
        reg = WaitConditionRegistry()
        reg.arm("run-1", _wait(key="k1"))
        reg.arm("run-2", _wait(key="k2"))

        armed = dict(reg.list_armed())
        assert armed == {"k1": "run-1", "k2": "run-2"}

    def test_list_armed_after_resolve_excludes_resolved(self):
        reg = WaitConditionRegistry()
        reg.arm("run-1", _wait(key="k1"))
        reg.arm("run-2", _wait(key="k2"))
        reg.resolve("k1", {})

        armed = dict(reg.list_armed())
        assert "k1" not in armed
        assert "k2" in armed


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_arm_and_resolve(self):
        reg = WaitConditionRegistry()
        results: list[str | None] = []
        lock = threading.Lock()

        # Arm 50 runs
        for i in range(50):
            reg.arm(f"run-{i}", _wait(key=f"key-{i}"))

        def resolve_many() -> None:
            for i in range(50):
                result = reg.resolve(f"key-{i}", {})
                with lock:
                    results.append(result)

        threads = [threading.Thread(target=resolve_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each key should have been resolved exactly once
        non_none = [r for r in results if r is not None]
        assert len(non_none) == 50


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_wait_registry_returns_same_instance(self):
        r1 = get_wait_registry()
        r2 = get_wait_registry()
        assert r1 is r2
