"""Tests for per-session token accounting and cost estimation (B2)."""

from __future__ import annotations

import pytest

from hachi.core.cost import CostTracker, pricing_for
from hachi.core.llm import LLMResponse, TokenUsage
from hachi.core.runtime_events import USAGE_UPDATED, adapt_event


def test_pricing_longest_prefix_match() -> None:
    # Dated model ids resolve to their family price.
    assert pricing_for("claude-opus-4-8-20260101") == (5.0, 25.0)
    assert pricing_for("claude-haiku-4-5") == (1.0, 5.0)
    assert pricing_for("gpt-4o-mini") == (0.15, 0.60)
    # BB-56 (M14): unknown models fall back to $0, not a fictional nonzero
    # guess — a genuinely unpriced/local model must never fabricate a bill.
    assert pricing_for("some-unknown-model") == (0.0, 0.0)


def test_opus_4_family_priced_at_current_rate_not_legacy() -> None:
    # BB-27 regression: the Opus-4 family was mispriced at the legacy
    # Claude-3-Opus $15/$75 rate, inflating every Opus user's displayed cost 3x.
    # Current Opus (4.5+) is $5/$25 per MTok (Anthropic public pricing).
    assert pricing_for("claude-opus-4-8") == (5.0, 25.0)
    assert pricing_for("claude-opus-4-8-20260101") == (5.0, 25.0)
    assert pricing_for("claude-opus-4") == (5.0, 25.0)
    # Cheaper tiers must stay unchanged.
    assert pricing_for("claude-sonnet-4") == (3.0, 15.0)
    assert pricing_for("claude-haiku-4-5") == (1.0, 5.0)


def test_llm_response_usage_defaults_to_zero() -> None:
    resp = LLMResponse(content="hi")
    assert resp.usage.input_tokens == 0
    assert resp.usage.output_tokens == 0


def test_cost_tracker_accumulates_tokens_and_cost() -> None:
    tracker = CostTracker()
    # 1M input + 1M output on haiku ($1/$5 per M) = $6.00 exactly.
    tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000))
    snap = tracker.snapshot()
    assert snap.input_tokens == 1_000_000
    assert snap.output_tokens == 1_000_000
    assert snap.total_tokens == 2_000_000
    assert snap.call_count == 1
    assert abs(snap.estimated_cost_usd - 6.0) < 1e-9


def test_cost_tracker_discounts_cached_input() -> None:
    tracker = CostTracker()
    # All input served from cache (fresh input_tokens=0): priced at 0.1x the rate.
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=0, cache_read_tokens=1_000_000),
    )
    snap = tracker.snapshot()
    # 1M cached input * $1/M * 0.1 = $0.10
    assert abs(snap.estimated_cost_usd - 0.10) < 1e-9
    assert snap.cache_read_tokens == 1_000_000
    assert snap.total_tokens == 1_000_000  # cache tokens count toward total


def test_cost_tracker_cache_tokens_are_additive_not_subtracted() -> None:
    tracker = CostTracker()
    # 1M fresh input + 1M cache-read on haiku ($1/M in): 1M*1 + 1M*1*0.1 = $1.10.
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=1_000_000, cache_read_tokens=1_000_000),
    )
    snap = tracker.snapshot()
    assert abs(snap.estimated_cost_usd - 1.10) < 1e-9
    assert snap.total_tokens == 2_000_000


def test_cost_tracker_uses_per_model_cache_multiplier_from_registry() -> None:
    # BB-28 regression: OpenAI cached input is ~50% off (0.5x), NOT Anthropic's
    # 90% off (0.1x). With a registry, record() must honor each model's
    # cache_read_mult so the OpenAI cached-token discount is priced correctly.
    from hachi.core.routing.registry import ModelRegistry

    reg = ModelRegistry.build(object(), None)
    tracker = CostTracker(registry=reg)
    # 1M cached-read tokens on gpt-4o ($2.50/M in): 0.5x => $1.25 (was $0.25 at 0.1x).
    tracker.record("gpt-4o", TokenUsage(input_tokens=0, cache_read_tokens=1_000_000))
    assert abs(tracker.snapshot().estimated_cost_usd - 1.25) < 1e-9
    # Anthropic still gets the 0.1x discount via its descriptor default.
    tracker2 = CostTracker(registry=reg)
    tracker2.record("claude-haiku-4-5", TokenUsage(input_tokens=0, cache_read_tokens=1_000_000))
    assert abs(tracker2.snapshot().estimated_cost_usd - 0.10) < 1e-9


def test_record_background_usage_writes_to_daily_ledger(tmp_path) -> None:
    # BB-31 regression: background work (fact extraction, durable titling) runs
    # outside the per-session CostTracker. Its spend must still hit the durable daily
    # ledger so /spend and the daily spend cap (which read this ledger) account for it.
    from hachi.core.cost import record_background_usage, today_utc_str
    from hachi.core.session_store import SessionStore

    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    # haiku $1/M in, $5/M out: 1000 in + 100 out = $0.001 + $0.0005 = $0.0015
    cost = record_background_usage(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=1000, output_tokens=100),
        store=store,
    )
    assert abs(cost - 0.0015) < 1e-9
    today = today_utc_str()
    assert abs(store.get_daily_spend(today) - 0.0015) < 1e-9


def test_extract_facts_records_background_spend(monkeypatch) -> None:
    # BB-31: extract_facts must report its LLM spend to the ledger via
    # record_background_usage (otherwise the extraction call is invisible spend).
    import hachi.core.memory as mem

    captured: dict[str, object] = {}

    def _fake_record(model: str, usage: TokenUsage, **_kw: object) -> float:
        captured["model"] = model
        captured["input_tokens"] = usage.input_tokens
        return 0.0

    monkeypatch.setattr("hachi.core.cost.record_background_usage", _fake_record)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _FakeLLM:
        model = "claude-haiku-4-5"

        def generate(self, **_kwargs: object) -> LLMResponse:
            return LLMResponse(
                content='{"user_facts": [], "workspace_facts": [], "agent_facts": []}',
                usage=TokenUsage(input_tokens=1234, output_tokens=56),
            )

    class _FakeVault:
        def upsert_user_fact(self, *_a: object, **_k: object) -> None: ...
        def upsert_fact(self, *_a: object, **_k: object) -> None: ...
        def upsert_agent_fact(self, *_a: object, **_k: object) -> None: ...

    mem.extract_facts(
        "The user said their name is Aditya and they prefer Python.",
        vault=_FakeVault(),
        llm_client=_FakeLLM(),
    )
    assert captured.get("model") == "claude-haiku-4-5"
    assert captured.get("input_tokens") == 1234


def test_cost_tracker_sums_across_calls() -> None:
    tracker = CostTracker()
    tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=100, output_tokens=50))
    tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=200, output_tokens=10))
    snap = tracker.snapshot()
    assert snap.input_tokens == 300
    assert snap.output_tokens == 60
    assert snap.call_count == 2


def test_snapshot_to_dict_is_serializable() -> None:
    tracker = CostTracker()
    tracker.record("gpt-4o", TokenUsage(input_tokens=10, output_tokens=5))
    data = tracker.snapshot().to_dict()
    assert set(data) >= {
        "total_tokens",
        "estimated_cost_usd",
        "call_count",
        "cache_read_tokens",
    }
    assert data["total_tokens"] == 15


def test_usage_event_adapts_to_stable_taxonomy() -> None:
    envelopes = adapt_event("usage", {"total_tokens": 42, "estimated_cost_usd": 0.01})
    assert len(envelopes) == 1
    assert envelopes[0].primary.name == USAGE_UPDATED
    assert envelopes[0].primary.payload["total_tokens"] == 42
    assert "usage" in envelopes[0].legacy_aliases


# ---------------------------------------------------------------------------
# Phase 4 — R10: per-feature cost attribution
# ---------------------------------------------------------------------------


def test_record_accepts_feature_kwarg() -> None:
    """feature= kwarg is accepted without error."""
    tracker = CostTracker()
    tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=10, output_tokens=5), feature="chat")


def test_per_feature_snapshot_returns_dict_keyed_by_feature() -> None:
    tracker = CostTracker()
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=100, output_tokens=50),
        feature="chat",
    )
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=200, output_tokens=20),
        feature="titling",
    )
    result = tracker.per_feature_snapshot()
    assert "chat" in result
    assert "titling" in result
    assert result["chat"]["call_count"] == 1
    assert result["titling"]["call_count"] == 1


def test_per_feature_snapshot_totals_add_up() -> None:
    tracker = CostTracker()
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=100, output_tokens=50),
        feature="chat",
    )
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=200, output_tokens=30),
        feature="extraction",
    )
    overall = tracker.snapshot()
    pf = tracker.per_feature_snapshot()
    feature_total_tokens = sum(v["total_tokens"] for v in pf.values())
    assert feature_total_tokens == overall.total_tokens


def test_record_without_feature_is_attributed_as_unattributed() -> None:
    """Calls without feature= go into a sentinel bucket, not silently dropped."""
    tracker = CostTracker()
    tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=10, output_tokens=5))
    pf = tracker.per_feature_snapshot()
    # Some bucket must hold the unattributed call.
    assert sum(v["call_count"] for v in pf.values()) == 1


def test_per_feature_snapshot_cost_is_non_negative() -> None:
    tracker = CostTracker()
    tracker.record(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=50, output_tokens=25),
        feature="chat",
    )
    pf = tracker.per_feature_snapshot()
    assert pf["chat"]["estimated_cost_usd"] >= 0.0


def test_record_background_usage_accepts_feature_kwarg() -> None:
    """record_background_usage gains a feature= kwarg (Phase 4 contract)."""
    from hachi.core.cost import record_background_usage

    cost = record_background_usage(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=10, output_tokens=5),
        feature="extraction",
    )
    assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# BB-42 regression — background-usage recording must not leak a SQLite connection
# ---------------------------------------------------------------------------


def test_record_background_usage_closes_fallback_store_connection(monkeypatch, tmp_path) -> None:
    """BB-42: when no shared session store is available, record_background_usage
    opens a fresh fallback SessionStore(). That fallback store must be shut down
    (its sqlite3 connection closed) before the call returns — otherwise every
    background job (fact extraction, titling) leaks a WAL connection forever.
    """
    import sqlite3

    from hachi.core.cost import record_background_usage
    from hachi.core.session_store import SessionStore

    created: list[SessionStore] = []
    real_init = SessionStore.__init__

    def _tracking_init(self, db_path=None):  # type: ignore[no-untyped-def]
        real_init(self, db_path=db_path or str(tmp_path / "sessions.db"))
        created.append(self)

    monkeypatch.setattr(SessionStore, "__init__", _tracking_init)

    cost = record_background_usage(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=1000, output_tokens=100),
    )

    assert cost > 0.0
    assert len(created) == 1, "expected exactly one fallback SessionStore to be opened"
    leaked_store = created[0]
    # A closed sqlite3 connection raises ProgrammingError on any further use.
    with pytest.raises(sqlite3.ProgrammingError):
        leaked_store._conn.execute("SELECT 1")


def test_record_voice_usage_closes_fallback_store_connection(monkeypatch, tmp_path) -> None:
    """BB-42: same leak, but for record_voice_usage's fallback SessionStore()."""
    import sqlite3

    from hachi.core.cost import record_voice_usage
    from hachi.core.session_store import SessionStore

    created: list[SessionStore] = []
    real_init = SessionStore.__init__

    def _tracking_init(self, db_path=None):  # type: ignore[no-untyped-def]
        real_init(self, db_path=db_path or str(tmp_path / "sessions.db"))
        created.append(self)

    monkeypatch.setattr(SessionStore, "__init__", _tracking_init)

    cost = record_voice_usage("stt", "whisper-1", 2.0)

    assert cost > 0.0
    assert len(created) == 1, "expected exactly one fallback SessionStore to be opened"
    leaked_store = created[0]
    with pytest.raises(sqlite3.ProgrammingError):
        leaked_store._conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# BB-56 regression — M14 cost-accounting edges
# ---------------------------------------------------------------------------


def test_unknown_model_prices_at_zero_not_a_fictional_default() -> None:
    """M14 sub-bug 1: a genuinely unrecognised model id (e.g. an Ollama-served
    local model with no real per-token cost) must price at $0, not the old
    fictional _DEFAULT_PRICING guess (1.0, 5.0) — that guess could trip a
    user's daily spend cap on usage that cost nothing.
    """
    assert pricing_for("llama3.1:8b") == (0.0, 0.0)
    assert pricing_for("some-unknown-model") == (0.0, 0.0)


def test_cost_tracker_records_zero_cost_for_unknown_local_model() -> None:
    """End-to-end: recording usage against an unrecognised/local model id
    accumulates tokens but contributes $0 to the estimated cost — it must not
    silently bill at a fictional per-token rate that could trip a spend cap.
    """
    tracker = CostTracker()
    tracker.record("llama3.1:8b", TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000))
    snap = tracker.snapshot()
    assert snap.total_tokens == 2_000_000
    assert snap.estimated_cost_usd == 0.0


def test_today_utc_str_uses_utc_not_local_date(monkeypatch) -> None:
    """M14 sub-bug 2: the daily-spend date key must be derived from UTC, not the
    host's local timezone — otherwise spend near midnight is misattributed to
    the wrong day for any user not in UTC.
    """
    import datetime as real_datetime

    from hachi.core import cost as cost_mod

    # Simulate a host in UTC+14 (Kiribati) where it is already the next day in
    # local time but still "yesterday" in UTC.
    fixed_utc = real_datetime.datetime(2026, 7, 4, 23, 30, tzinfo=real_datetime.UTC)

    class _FixedDateTime(real_datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return fixed_utc.astimezone(tz)
            # "Local" now (no tz) — simulate local time already past midnight.
            return real_datetime.datetime(2026, 7, 5, 13, 30)

    monkeypatch.setattr(cost_mod.datetime, "datetime", _FixedDateTime)

    assert cost_mod.today_utc_str() == "2026-07-04"


def test_record_background_usage_keys_daily_ledger_by_utc_date(monkeypatch, tmp_path) -> None:
    """M14 sub-bug 2, end-to-end: record_background_usage must bucket spend under
    the UTC date, not whatever datetime.date.today() (local) resolves to.
    """
    import datetime as real_datetime

    from hachi.core import cost as cost_mod
    from hachi.core.cost import record_background_usage
    from hachi.core.session_store import SessionStore

    fixed_utc = real_datetime.datetime(2026, 7, 4, 23, 30, tzinfo=real_datetime.UTC)

    class _FixedDateTime(real_datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return fixed_utc.astimezone(tz)
            # Local wall-clock already past midnight the next day.
            return real_datetime.datetime(2026, 7, 5, 13, 30)

    class _FixedDate(real_datetime.date):
        @classmethod
        def today(cls):  # type: ignore[override]
            # A pre-fix implementation keyed on date.today() (local) would see the
            # NEXT day relative to the true UTC date — proves the ledger key
            # actually comes from UTC, not this (wrong) local value.
            return real_datetime.date(2026, 7, 5)

    monkeypatch.setattr(cost_mod.datetime, "datetime", _FixedDateTime)
    monkeypatch.setattr(cost_mod.datetime, "date", _FixedDate)

    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    record_background_usage(
        "claude-haiku-4-5",
        TokenUsage(input_tokens=1000, output_tokens=100),
        store=store,
    )
    # Spend must land on the UTC date, not the (later, local-only) 2026-07-05.
    assert store.get_daily_spend("2026-07-04") > 0.0
    assert store.get_daily_spend("2026-07-05") == 0.0


def test_clamp_nonnegative_cost_delta_clamps_and_logs(caplog) -> None:
    """M14 sub-bug 3: a negative per-turn cost delta (e.g. after a tracker reset
    mid-session) must be clamped to 0.0 AND logged — not silently dropped with
    no trace.
    """
    import logging

    from hachi.core.cost import clamp_nonnegative_cost_delta

    with caplog.at_level(logging.WARNING, logger="hachi.core.cost"):
        result = clamp_nonnegative_cost_delta(-0.05, context="test-session")

    assert result == 0.0
    assert any("negative" in rec.message.lower() for rec in caplog.records)


def test_clamp_nonnegative_cost_delta_passes_through_positive() -> None:
    """A normal, non-negative delta is returned unchanged (no clamping, no log)."""
    from hachi.core.cost import clamp_nonnegative_cost_delta

    assert clamp_nonnegative_cost_delta(0.5, context="test-session") == 0.5
    assert clamp_nonnegative_cost_delta(0.0, context="test-session") == 0.0
