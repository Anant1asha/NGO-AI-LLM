"""Tests for daily spend cap enforcement (AUDIT P1-3).

Verifies that AgentSession._daily_cap_exceeded():
  1. Returns a reason string when today's recorded spend >= max_daily_cost_usd.
  2. Returns None (cap not hit) when spend is below the cap.
  3. Returns None when max_daily_cost_usd is unset (None) or zero.
  4. Returns None (safe fail-open) when _session_store.get_daily_spend raises.

And that _chat_impl_inner early-returns the [BUDGET LIMIT REACHED] message and emits the
budget.exceeded event when _daily_cap_exceeded() fires.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hachi.core.cost import today_utc_str
from hachi.core.session_store import SessionStore
from hachi.gateway.orchestrator import AgentSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_with_daily_cap(
    store: SessionStore | None,
    max_daily_cost_usd: float | None,
) -> AgentSession:
    """Minimal AgentSession wired only for _daily_cap_exceeded()."""
    sess = AgentSession.__new__(AgentSession)
    sess._session_store = store
    sess._max_daily_cost_usd = max_daily_cost_usd
    return sess


def _real_store(tmp_path: Path) -> SessionStore:
    return SessionStore(db_path=str(tmp_path / "test.db"))


# ---------------------------------------------------------------------------
# Unit tests for _daily_cap_exceeded()
# ---------------------------------------------------------------------------


class TestDailyCapExceeded:
    def test_returns_none_when_cap_not_set(self) -> None:
        """No cap configured → always returns None (unlimited, fail-open)."""
        sess = _session_with_daily_cap(store=None, max_daily_cost_usd=None)
        assert sess._daily_cap_exceeded() is None

    def test_returns_none_when_cap_is_zero(self) -> None:
        """Zero cap is treated as disabled (falsy) → returns None."""
        sess = _session_with_daily_cap(store=None, max_daily_cost_usd=0.0)
        assert sess._daily_cap_exceeded() is None

    def test_returns_none_when_store_is_none(self) -> None:
        """Cap set but no session store → fail-open, returns None."""
        sess = _session_with_daily_cap(store=None, max_daily_cost_usd=5.0)
        assert sess._daily_cap_exceeded() is None

    def test_returns_none_when_under_cap(self, tmp_path: Path) -> None:
        """Spend below cap → None (turn allowed)."""
        store = _real_store(tmp_path)
        today = today_utc_str()
        store.record_daily_cost(today, 0.50)

        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=5.00)
        assert sess._daily_cap_exceeded() is None
        store.shutdown()

    def test_returns_reason_when_spend_equals_cap(self, tmp_path: Path) -> None:
        """Spend exactly equal to cap → reason string returned (>= comparison)."""
        store = _real_store(tmp_path)
        today = today_utc_str()
        store.record_daily_cost(today, 5.00)

        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=5.00)
        reason = sess._daily_cap_exceeded()
        assert reason is not None
        assert "daily cost cap reached" in reason
        assert "5.00" in reason
        store.shutdown()

    def test_returns_reason_when_spend_exceeds_cap(self, tmp_path: Path) -> None:
        """Spend over cap → reason string returned."""
        store = _real_store(tmp_path)
        today = today_utc_str()
        store.record_daily_cost(today, 2.00)
        store.record_daily_cost(today, 1.00)  # total 3.00, cap 2.50

        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=2.50)
        reason = sess._daily_cap_exceeded()
        assert reason is not None
        assert "daily cost cap reached" in reason
        assert "2.50" in reason
        store.shutdown()

    def test_returns_none_when_zero_spend_and_cap_set(self, tmp_path: Path) -> None:
        """No spend today → 0.0 from get_daily_spend, always under cap."""
        store = _real_store(tmp_path)
        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=1.00)
        assert sess._daily_cap_exceeded() is None
        store.shutdown()

    def test_safe_failopen_on_store_read_error(self, tmp_path: Path) -> None:
        """get_daily_spend error → returns None (safe fail-open, turn runs)."""
        store = _real_store(tmp_path)
        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=5.00)

        # Patch get_daily_spend to raise
        with patch.object(store, "get_daily_spend", side_effect=RuntimeError("db locked")):
            result = sess._daily_cap_exceeded()

        assert result is None
        store.shutdown()

    def test_uses_today_iso_date_matching_record_side(self, tmp_path: Path) -> None:
        """get_daily_spend is called with today's ISO date — same key record_daily_cost uses."""
        store = _real_store(tmp_path)
        today = today_utc_str()
        store.record_daily_cost(today, 10.0)

        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=1.00)

        captured: list[str] = []
        original = store.get_daily_spend

        def _capture(date_str: str) -> float:
            captured.append(date_str)
            return original(date_str)

        with patch.object(store, "get_daily_spend", side_effect=_capture):
            sess._daily_cap_exceeded()

        assert captured == [today]
        store.shutdown()


# ---------------------------------------------------------------------------
# Integration: _chat_impl_inner early-return when cap is hit
# ---------------------------------------------------------------------------


class TestChatImplInnerDailyCapRefusal:
    """Verify that _chat_impl_inner aborts the turn and emits the right event."""

    def _make_session_for_chat_impl(
        self,
        tmp_path: Path,
        *,
        daily_spend: float,
        cap: float,
    ) -> AgentSession:
        """Build a minimal AgentSession that can run _chat_impl_inner up to the cap check."""
        store = _real_store(tmp_path)
        today = today_utc_str()
        if daily_spend > 0:
            store.record_daily_cost(today, daily_spend)

        sess = AgentSession.__new__(AgentSession)
        sess._session_store = store
        sess._max_daily_cost_usd = cap
        sess._session_id = "test-session"

        emitted: list[tuple[str, dict]] = []
        sess._event_emitter = lambda name, payload: emitted.append((name, payload))

        # Attach helper to the test object so assertions can read it
        sess.__dict__["_emitted"] = emitted

        # Stub _drain_job_queue — not under test
        sess._drain_job_queue = lambda: None  # type: ignore[method-assign]

        return sess

    def test_turn_refused_with_budget_message(self, tmp_path: Path) -> None:
        """When daily cap is hit, _chat_impl_inner returns [BUDGET LIMIT REACHED] immediately."""
        sess = self._make_session_for_chat_impl(tmp_path, daily_spend=6.00, cap=5.00)

        result = sess._chat_impl_inner("hello", turn_id="t1", surface="cli")

        assert result.startswith("[BUDGET LIMIT REACHED]")
        assert "daily cost cap reached" in result
        assert "5.00" in result

    def test_budget_exceeded_event_emitted(self, tmp_path: Path) -> None:
        """When daily cap is hit, the budget.exceeded runtime event is emitted."""
        sess = self._make_session_for_chat_impl(tmp_path, daily_spend=6.00, cap=5.00)

        sess._chat_impl_inner("hello", turn_id="t1", surface="cli")

        emitted: list[tuple[str, dict]] = sess.__dict__["_emitted"]
        event_names = [name for name, _ in emitted]
        assert "budget.exceeded" in event_names

        budget_payload = next(p for n, p in emitted if n == "budget.exceeded")
        assert "daily cost cap reached" in budget_payload["reason"]

    def test_turn_runs_when_under_cap(self, tmp_path: Path) -> None:
        """When spend is below the daily cap, _daily_cap_exceeded returns None (no refusal)."""
        sess = self._make_session_for_chat_impl(tmp_path, daily_spend=1.00, cap=5.00)

        # _daily_cap_exceeded must return None — we only test that helper in isolation here
        # rather than running the whole loop (which would need the full session graph).
        reason = sess._daily_cap_exceeded()
        assert reason is None

    def test_turn_runs_when_no_cap_configured(self, tmp_path: Path) -> None:
        """With max_daily_cost_usd=None, _daily_cap_exceeded is always None."""
        store = _real_store(tmp_path)
        today = today_utc_str()
        store.record_daily_cost(today, 999.99)

        sess = _session_with_daily_cap(store=store, max_daily_cost_usd=None)
        assert sess._daily_cap_exceeded() is None
        store.shutdown()
