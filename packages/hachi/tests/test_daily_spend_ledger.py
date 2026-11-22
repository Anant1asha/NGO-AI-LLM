"""Tests for the daily spend ledger in SessionStore.

Verifies:
- record_daily_cost accumulates correctly within a date.
- get_daily_spend returns 0.0 when no row exists (rollover scenario).
- Two different date keys are independent (rollover isolation).
- Non-positive deltas are silently ignored.
"""

import pytest

from hachi.core.session_store import SessionStore


@pytest.fixture()
def store(tmp_path):
    """Yield an in-memory-equivalent SessionStore backed by a temp file."""
    db = tmp_path / "test_sessions.db"
    s = SessionStore(db_path=str(db))
    yield s
    s.shutdown()


class TestDailySpendLedger:
    def test_get_daily_spend_missing_date_returns_zero(self, store: SessionStore) -> None:
        """get_daily_spend returns 0.0 for a date with no recorded spend."""
        result = store.get_daily_spend("2026-01-01")
        assert result == 0.0

    def test_record_and_retrieve_single_delta(self, store: SessionStore) -> None:
        """A single record_daily_cost call is retrievable via get_daily_spend."""
        store.record_daily_cost("2026-06-22", 0.001234)
        result = store.get_daily_spend("2026-06-22")
        assert abs(result - 0.001234) < 1e-9

    def test_record_accumulates_multiple_deltas(self, store: SessionStore) -> None:
        """Multiple record_daily_cost calls on the same date accumulate correctly."""
        store.record_daily_cost("2026-06-22", 0.01)
        store.record_daily_cost("2026-06-22", 0.02)
        store.record_daily_cost("2026-06-22", 0.005)
        result = store.get_daily_spend("2026-06-22")
        assert abs(result - 0.035) < 1e-9

    def test_rollover_different_dates_are_independent(self, store: SessionStore) -> None:
        """Spend on one date does not affect a different date (rollover isolation)."""
        store.record_daily_cost("2026-06-22", 1.50)
        store.record_daily_cost("2026-06-23", 0.25)

        assert abs(store.get_daily_spend("2026-06-22") - 1.50) < 1e-9
        assert abs(store.get_daily_spend("2026-06-23") - 0.25) < 1e-9
        # A third date that was never touched returns 0.0 (rollover gives a clean slate).
        assert store.get_daily_spend("2026-06-24") == 0.0

    def test_non_positive_delta_is_ignored(self, store: SessionStore) -> None:
        """record_daily_cost silently ignores zero and negative deltas."""
        store.record_daily_cost("2026-06-22", 0.0)
        store.record_daily_cost("2026-06-22", -0.5)
        assert store.get_daily_spend("2026-06-22") == 0.0

    def test_existing_session_store_operations_unaffected(self, store: SessionStore) -> None:
        """Daily ledger operations do not interfere with regular session operations."""
        sid = store.start_session(model="claude-haiku-4-5")
        store.log_message(sid, "user", "Hello")
        store.record_daily_cost("2026-06-22", 0.001)
        store.record_session_cost(sid, total_tokens=100, total_cost_usd=0.001)

        session = store.get_session(sid)
        assert session is not None
        assert session["total_tokens"] == 100
        assert abs(session["total_cost_usd"] - 0.001) < 1e-9

        daily = store.get_daily_spend("2026-06-22")
        assert abs(daily - 0.001) < 1e-9
