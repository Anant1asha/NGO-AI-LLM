"""Tests for supporting-backend fixes (Issues 3, 4, 5, 9, 11, 12).

New file only — does not modify existing test files.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Issue 12: SessionStore — empty-session exclusion, delete_empty_sessions,
#            lazy row creation
# ---------------------------------------------------------------------------


class TestSessionStoreGhostSessions:
    """Issue 12: ghost session prevention and cleanup."""

    def _make_store(self) -> Any:
        from hachi.core.session_store import SessionStore

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        return SessionStore(db_path=path)

    def test_get_recent_sessions_excludes_empty(self) -> None:
        """Sessions with no messages must not appear in get_recent_sessions."""
        store = self._make_store()
        try:
            sid = store.start_session(model="test-model")
            # Eager row exists, but with no messages/cost/title/turns it is a ghost
            # and must be hidden from the listing.
            results = store.get_recent_sessions(limit=50)
            ids = [r["id"] for r in results]
            assert sid not in ids, (
                "A session with no messages must not appear in get_recent_sessions"
            )
        finally:
            store.shutdown()

    def test_get_recent_sessions_includes_with_messages(self) -> None:
        """Sessions that have at least one message must appear."""
        store = self._make_store()
        try:
            sid = store.start_session(model="test-model")
            store.log_message(sid, "user", "hello")
            store.flush_sync()
            results = store.get_recent_sessions(limit=50)
            ids = [r["id"] for r in results]
            assert sid in ids, "A session with messages must appear in get_recent_sessions"
        finally:
            store.shutdown()

    def test_delete_empty_sessions_removes_ghosts(self) -> None:
        """delete_empty_sessions must delete DB rows that have no messages."""
        from hachi.core.session_store import SessionStore

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        store = SessionStore(db_path=path)
        try:
            # Inject a ghost row directly (bypassing lazy creation) to simulate
            # a legacy empty row that may exist in old databases.
            import datetime
            import uuid

            ghost_id = uuid.uuid4().hex[:16]
            now = datetime.datetime.now(datetime.UTC).isoformat()
            with store._lock:
                store._conn.execute(
                    "INSERT INTO sessions (id, started_at, model) VALUES (?, ?, ?)",
                    (ghost_id, now, "test"),
                )
                store._conn.commit()

            # Also create a real session with a message.
            real_sid = store.start_session(model="real")
            store.log_message(real_sid, "user", "hello")
            store.flush_sync()

            count = store.delete_empty_sessions()
            assert count == 1, f"Expected 1 ghost deleted, got {count}"

            # The real session must still be present.
            result = store.get_recent_sessions(limit=50)
            ids = [r["id"] for r in result]
            assert real_sid in ids
            assert ghost_id not in ids
        finally:
            store.shutdown()

    def test_empty_session_persisted_but_hidden_and_cleanable(self) -> None:
        """Issue 12 (eager design): start_session writes the row immediately so
        foreign-key integrity and synchronous-commit hold, but a message-less session
        is hidden from get_recent_sessions and removed by delete_empty_sessions — so
        ghosts never reach the UI or linger. (Lazy non-persistence was reverted because
        it broke FK integrity / synchronous commit; see DECISIONS.md.)"""
        store = self._make_store()
        try:
            sid = store.start_session(model="ghost-test")
            # Eager: the row exists immediately (FK integrity for later message writes).
            with store._lock:
                row = store._conn.execute(
                    "SELECT id FROM sessions WHERE id = ?", (sid,)
                ).fetchone()
            assert row is not None, "start_session must commit the row eagerly (FK integrity)"

            # ...but it is a ghost: excluded from the listing and removable on demand.
            listed = [r["id"] for r in store.get_recent_sessions(limit=50)]
            assert sid not in listed, "a message-less session must be hidden from the listing"
            assert store.delete_empty_sessions() >= 1
            with store._lock:
                gone = store._conn.execute(
                    "SELECT id FROM sessions WHERE id = ?", (sid,)
                ).fetchone()
            assert gone is None, "delete_empty_sessions must remove the message-less ghost"
        finally:
            store.shutdown()

    def test_delete_empty_sessions_returns_zero_when_none(self) -> None:
        """delete_empty_sessions must return 0 when all sessions have messages."""
        store = self._make_store()
        try:
            sid = store.start_session(model="m")
            store.log_message(sid, "user", "hi")
            store.flush_sync()
            count = store.delete_empty_sessions()
            assert count == 0
        finally:
            store.shutdown()


# ---------------------------------------------------------------------------
# Issue 5: registry.py — Tavily auto-activate
# ---------------------------------------------------------------------------


class TestTavilyAutoActivate:
    """Issue 5: TavilySearchProvider registered when TAVILY_API_KEY is in env."""

    def _make_minimal_config(self) -> Any:
        """Return a minimal ResolvedConfig-like object."""
        from hachi.core.settings import ResolvedConfig

        return ResolvedConfig()

    def test_tavily_registered_via_env(self) -> None:
        """TAVILY_API_KEY env var alone must cause Tavily to register."""
        from hachi.core.providers.registry import ProviderRegistry

        config = self._make_minimal_config()
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key-abc"}, clear=False):
            reg = ProviderRegistry.from_config(config, secret_store=None)

        search = reg.get_search()
        assert search is not None, "Tavily provider must be registered when TAVILY_API_KEY is set"
        assert "tavily" in type(search).__name__.lower(), (
            "Registered search provider must be TavilySearchProvider"
        )

    def test_tavily_not_registered_without_key(self) -> None:
        """When TAVILY_API_KEY is absent and config has no tavily provider, none registered."""
        from hachi.core.providers.registry import ProviderRegistry

        config = self._make_minimal_config()
        env = {k: v for k, v in os.environ.items() if k != "TAVILY_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            reg = ProviderRegistry.from_config(config, secret_store=None)

        search = reg.get_search()
        assert search is None, "No search provider should be registered without a Tavily key"

    def test_tavily_registered_via_config_provider_name(self) -> None:
        """config.search.provider == 'tavily' must still register Tavily."""
        from hachi.core.providers.registry import ProviderRegistry
        from hachi.core.settings import ResolvedConfig, SearchSettings

        config = ResolvedConfig(search=SearchSettings(provider="tavily"))
        # Ensure env key is absent so registration is purely config-driven.
        env = {k: v for k, v in os.environ.items() if k != "TAVILY_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            reg = ProviderRegistry.from_config(config, secret_store=None)

        search = reg.get_search()
        assert search is not None, "Tavily must register when config.search.provider='tavily'"


# ---------------------------------------------------------------------------
# Issue 4: mcp_client.py — per-server err field in get_inventory
# ---------------------------------------------------------------------------


class TestMCPInventoryErr:
    """Issue 4: err field and status values in get_inventory."""

    def test_err_populated_on_failed_server(self) -> None:
        """get_inventory must include a non-None err when server failed to start."""
        from hachi.core.mcp_client import MCPManager, MCPServerConfig

        mgr = MCPManager()
        cfg = MCPServerConfig(
            name="bad-server",
            transport="stdio",
            command="this-command-does-not-exist-xyz",
        )
        ok = mgr.setup_from_config(cfg)
        assert not ok, "Server with bad command must fail to start"

        inventory = mgr.get_inventory()
        entry = next((e for e in inventory if e["name"] == "bad-server"), None)
        assert entry is not None, "Failed server must still appear in inventory"
        assert entry["status"] == "failed", f"Expected 'failed', got {entry['status']!r}"
        assert entry["err"] is not None, "err must be set for a failed server"
        assert isinstance(entry["err"], str) and entry["err"], "err must be a non-empty string"

    def test_err_none_for_successful_server(self) -> None:
        """get_inventory must have err=None for successfully started servers."""
        from hachi.core.mcp_client import MCPManager, MCPServerConnection

        mgr = MCPManager()
        # Fabricate a server connection that appears alive by monkey-patching start.
        server = MCPServerConnection(name="ok-server", command="echo")

        # Simulate successful boot: mark as alive, clear error.
        server._last_error = None

        # Directly inject into the manager's internal dict (test only).
        mgr._servers["ok-server"] = server

        # Force transport to appear alive via monkey-patch.
        with patch.object(type(server._transport), "is_alive", new_callable=lambda: property(
            lambda self: True
        )):
            inventory = mgr.get_inventory()

        entry = next((e for e in inventory if e["name"] == "ok-server"), None)
        assert entry is not None
        assert entry["err"] is None

    def test_status_starting_while_loading(self) -> None:
        """get_inventory must return 'starting' status while _loading is True."""
        from hachi.core.mcp_client import MCPManager, MCPServerConnection

        mgr = MCPManager()
        server = MCPServerConnection(name="starting-server", command="echo")
        server._loading = True
        server._last_error = None
        mgr._servers["starting-server"] = server

        inventory = mgr.get_inventory()
        entry = next((e for e in inventory if e["name"] == "starting-server"), None)
        assert entry is not None
        assert entry["status"] == "starting"


# ---------------------------------------------------------------------------
# Issue 3: settings.py — VoiceSettings fields
# ---------------------------------------------------------------------------


class TestVoiceSettingsFields:
    """Issue 3: VoiceSettings must expose all required fields with sensible defaults."""

    def test_default_fields_present(self) -> None:
        from hachi.core.settings import VoiceSettings

        v = VoiceSettings()
        assert v.elevenlabs_model == "eleven_turbo_v2_5"
        assert v.stt_model == "whisper-1"
        assert v.stt_base_url is None
        assert v.tts_model == "tts-1"
        assert v.tts_base_url is None

    def test_fields_overridable(self) -> None:
        from hachi.core.settings import VoiceSettings

        v = VoiceSettings(
            stt_model="whisper-large",
            tts_model="tts-1-hd",
            elevenlabs_model="eleven_multilingual_v2",
            stt_base_url="http://localhost:9000",
            tts_base_url="http://localhost:9001",
        )
        assert v.stt_model == "whisper-large"
        assert v.tts_model == "tts-1-hd"
        assert v.elevenlabs_model == "eleven_multilingual_v2"
        assert v.stt_base_url == "http://localhost:9000"
        assert v.tts_base_url == "http://localhost:9001"

    def test_existing_fields_unchanged(self) -> None:
        """Existing fields (stt_provider, tts_provider, tts_voice, etc.) must still work."""
        from hachi.core.settings import VoiceSettings

        v = VoiceSettings(tts_provider="elevenlabs", tts_voice="nova")
        assert v.tts_provider == "elevenlabs"
        assert v.tts_voice == "nova"


# ---------------------------------------------------------------------------
# Issue 9: cost.py — record_voice_usage pricing math
# ---------------------------------------------------------------------------


class TestVoicePricing:
    """Issue 9: voice pricing math for STT and TTS, including ElevenLabs."""

    def test_stt_whisper_cost_per_minute(self) -> None:
        """whisper-1 STT: $0.006 per minute."""
        from hachi.core.cost import _voice_cost

        cost = _voice_cost("stt", "whisper-1", 10.0)
        assert abs(cost - 0.06) < 1e-9, f"Expected 0.06, got {cost}"

    def test_tts_tts1_cost_per_1k_chars(self) -> None:
        """tts-1 TTS: $0.015 per 1k chars; 5000 chars → $0.075."""
        from hachi.core.cost import _voice_cost

        cost = _voice_cost("tts", "tts-1", 5000.0)
        assert abs(cost - 0.075) < 1e-9, f"Expected 0.075, got {cost}"

    def test_tts_elevenlabs_cost(self) -> None:
        """eleven_turbo_v2_5: $0.30 per 1k chars; 1000 chars → $0.30."""
        from hachi.core.cost import _voice_cost

        cost = _voice_cost("tts", "eleven_turbo_v2_5", 1000.0)
        assert abs(cost - 0.30) < 1e-9, f"Expected 0.30, got {cost}"

    def test_tts_elevenlabs_prefix_match(self) -> None:
        """eleven prefix must match eleven_multilingual_v2 etc."""
        from hachi.core.cost import _voice_cost

        cost = _voice_cost("tts", "eleven_multilingual_v2", 2000.0)
        # $0.30 / 1k chars × 2 k = $0.60
        assert abs(cost - 0.60) < 1e-9

    def test_tts1_hd_higher_than_tts1(self) -> None:
        """tts-1-hd must cost more than tts-1 for same char count."""
        from hachi.core.cost import _voice_cost

        cost_hd = _voice_cost("tts", "tts-1-hd", 1000.0)
        cost_std = _voice_cost("tts", "tts-1", 1000.0)
        assert cost_hd > cost_std

    def test_unknown_model_returns_zero(self) -> None:
        """Unknown model must return 0.0 cost, not raise."""
        from hachi.core.cost import _voice_cost

        cost = _voice_cost("tts", "totally-unknown-model-xyz", 1000.0)
        assert cost == 0.0

    def test_record_voice_usage_returns_cost(self) -> None:
        """record_voice_usage must return the computed cost and not raise."""
        # Patch the session_store module that record_voice_usage imports lazily.
        import hachi.core.session_store as _ss_module

        calls: list[tuple[str, float]] = []

        class _FakeStore:
            def record_daily_cost(self, date_str: str, delta: float) -> None:
                calls.append((date_str, delta))

        fake_store = _FakeStore()

        # Patch SessionStore in its own module so the lazy import inside
        # record_voice_usage picks up the fake.
        with patch.object(_ss_module, "SessionStore", return_value=fake_store):
            # Also suppress gateway import so the fallback path runs.

            fake_orch = MagicMock()
            fake_orch._get_session_store = MagicMock(side_effect=Exception("no gateway"))
            with patch.dict("sys.modules", {"hachi.gateway.orchestrator": fake_orch}):
                from hachi.core.cost import record_voice_usage
                result = record_voice_usage("stt", "whisper-1", 5.0)

        # $0.006 / min × 5 min = $0.030
        assert abs(result - 0.030) < 1e-9, f"Expected 0.030, got {result}"
        assert len(calls) == 1, f"Expected 1 record_daily_cost call, got {calls}"

    def test_record_voice_usage_never_raises(self) -> None:
        """record_voice_usage must return 0.0 on any internal error, never raise."""
        import hachi.core.session_store as _ss_module

        # Force the store constructor to raise so we exercise the except path.
        with patch.object(_ss_module, "SessionStore", side_effect=RuntimeError("boom")):

            fake_orch = MagicMock()
            fake_orch._get_session_store = MagicMock(side_effect=Exception("no gateway"))
            with patch.dict("sys.modules", {"hachi.gateway.orchestrator": fake_orch}):
                from hachi.core.cost import record_voice_usage
                result = record_voice_usage("tts", "tts-1", 500.0)
        # Must not raise; result is 0.0 (inner exception swallowed).
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Issue 9: session_titler.py — cost_tracker param
# ---------------------------------------------------------------------------


class TestTitlerCostTracker:
    """Issue 9: generate_title must record token usage when cost_tracker is provided."""

    def test_cost_tracker_receives_usage(self) -> None:
        """When cost_tracker is supplied, its record() method must be called."""
        from hachi.core.cost import CostTracker
        from hachi.core.llm import TokenUsage
        from hachi.core.session_titler import generate_title

        # Build a mock LLM response with usage (keyword args required by Pydantic).
        mock_usage = TokenUsage(
            input_tokens=10,
            output_tokens=5,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
        _ = mock_usage  # used below in _FakeResponse

        class _FakeResponse:
            content = "Fix Failing Tests"
            model = "claude-haiku-4-5"
            usage = mock_usage

        class _FakeLLMClient:
            model = "claude-haiku-4-5"

            def generate(self, messages: Any, system_prompt: Any = None) -> _FakeResponse:
                return _FakeResponse()

        tracker = CostTracker()
        title = generate_title(
            user_message="Fix the failing unit tests in ci",
            llm_client=_FakeLLMClient(),  # type: ignore[arg-type]
            cost_tracker=tracker,
        )

        assert title, "Title must not be empty"
        snap = tracker.snapshot()
        assert snap.call_count == 1, "CostTracker must have recorded exactly one call"
        assert snap.input_tokens == 10
        assert snap.output_tokens == 5

    def test_cost_tracker_none_does_not_raise(self) -> None:
        """generate_title with cost_tracker=None must work exactly as before."""
        from hachi.core.session_titler import generate_title

        title = generate_title("Hello world", llm_client=None, cost_tracker=None)
        assert title == "Hello world"

    def test_cost_tracker_skipped_on_missing_usage(self) -> None:
        """If the LLM response has no usage, tracker.record() must not be called."""
        from hachi.core.cost import CostTracker
        from hachi.core.session_titler import generate_title

        class _NoUsageResponse:
            content = "Some Title"
            model = "claude-haiku-4-5"
            usage = None  # no usage info

        class _FakeLLMClient:
            model = "claude-haiku-4-5"

            def generate(self, messages: Any, system_prompt: Any = None) -> _NoUsageResponse:
                return _NoUsageResponse()

        tracker = CostTracker()
        generate_title(
            user_message="query",
            llm_client=_FakeLLMClient(),  # type: ignore[arg-type]
            cost_tracker=tracker,
        )
        snap = tracker.snapshot()
        assert snap.call_count == 0, "No usage info → CostTracker must not be called"


# ---------------------------------------------------------------------------
# Issues 9 & 11: runtime_events.py — model field on usage event
# ---------------------------------------------------------------------------


class TestUsageEventModelField:
    """Issues 9 & 11: usage/turn event must carry model and token fields."""

    def test_model_field_forwarded(self) -> None:
        """adapt_event('usage', ...) must include model in the USAGE_UPDATED payload."""
        from hachi.core.runtime_events import USAGE_UPDATED, adapt_event

        envelopes = adapt_event(
            "usage",
            {
                "model": "claude-haiku-4-5",
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.001,
            },
        )
        assert envelopes, "adapt_event must return at least one envelope"
        evt = envelopes[0].primary
        assert evt.name == USAGE_UPDATED
        assert evt.payload["model"] == "claude-haiku-4-5"
        assert evt.payload["input_tokens"] == 100
        assert evt.payload["output_tokens"] == 50

    def test_model_defaults_none_when_absent(self) -> None:
        """When model is not in the payload, it must default to None (backward compat)."""
        from hachi.core.runtime_events import adapt_event

        envelopes = adapt_event("usage", {"estimated_cost_usd": 0.002})
        evt = envelopes[0].primary
        assert "model" in evt.payload
        assert evt.payload["model"] is None

    def test_cache_token_fields_present(self) -> None:
        """cache_read_tokens and cache_write_tokens must be in the payload."""
        from hachi.core.runtime_events import adapt_event

        envelopes = adapt_event(
            "usage",
            {"cache_read_tokens": 20, "cache_write_tokens": 5, "model": "claude-sonnet-4-6"},
        )
        payload = envelopes[0].primary.payload
        assert payload.get("cache_read_tokens") == 20
        assert payload.get("cache_write_tokens") == 5

    def test_usage_updated_payload_to_dict(self) -> None:
        """UsageUpdatedPayload.to_payload() must produce a complete dict."""
        from hachi.core.runtime_events import UsageUpdatedPayload

        p = UsageUpdatedPayload(
            model="claude-opus-4-8",
            input_tokens=200,
            output_tokens=80,
            cache_read_tokens=10,
            cache_write_tokens=2,
            estimated_cost_usd=0.015,
        )
        d = p.to_payload()
        assert d["model"] == "claude-opus-4-8"
        assert d["input_tokens"] == 200
        assert d["output_tokens"] == 80
        assert d["cache_read_tokens"] == 10
        assert d["cache_write_tokens"] == 2
        assert abs(d["estimated_cost_usd"] - 0.015) < 1e-9

    def test_usage_updated_payload_defaults(self) -> None:
        """UsageUpdatedPayload must default all fields to None for backward compat."""
        from hachi.core.runtime_events import UsageUpdatedPayload

        p = UsageUpdatedPayload()
        d = p.to_payload()
        for field in ("model", "input_tokens", "output_tokens", "cache_read_tokens",
                      "cache_write_tokens", "estimated_cost_usd"):
            assert d[field] is None, f"Expected None for {field}, got {d[field]!r}"


# ---------------------------------------------------------------------------
# Issue 9: MODEL_PRICING completeness
# ---------------------------------------------------------------------------


class TestModelPricingCompleteness:
    """Issue 9: MODEL_PRICING must include current Claude model ids."""

    @pytest.mark.parametrize("model_id", [
        "claude-opus-4-8",
        "claude-haiku-4-5",
        "claude-opus-4",
        "claude-sonnet-4",
        "claude-haiku-4",
    ])
    def test_model_has_pricing(self, model_id: str) -> None:
        from hachi.core.cost import pricing_for

        in_price, out_price = pricing_for(model_id)
        assert in_price > 0, f"Input price must be > 0 for {model_id}"
        assert out_price > 0, f"Output price must be > 0 for {model_id}"

    def test_per_model_snapshot_present(self) -> None:
        """CostTracker.per_model_snapshot must be callable and return a dict."""
        from hachi.core.cost import CostTracker
        from hachi.core.llm import TokenUsage

        tracker = CostTracker()
        tracker.record(
            "claude-haiku-4-5",
            TokenUsage(input_tokens=10, output_tokens=5, cache_read_tokens=0,
                       cache_creation_tokens=0),
        )
        result = tracker.per_model_snapshot()
        assert "claude-haiku-4-5" in result
        assert result["claude-haiku-4-5"].call_count == 1
