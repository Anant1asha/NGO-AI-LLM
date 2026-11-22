"""GATE-FAILOVER tests for the resilience layer (Slice 2.1).

Covers:
  - ResilientClient retries transient errors (429/5xx/timeout) bounded by max_attempts.
  - Circuit breaker opens at threshold; half-open hysteresis.
  - ModelRouter fallback chain re-issues against next candidate on terminal primary failure.
  - Provider.failover signal emitted on failover.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

import pytest

from hachi.core.llm import BaseLLMClient, LLMResponse, Message, TokenUsage
from hachi.core.resilience import (
    HealthRecorder,
    ResilientClient,
    RetryPolicy,
    _is_transient,
    resilient_call,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeClient(BaseLLMClient):
    """Fake LLM client with configurable failure sequence."""

    def __init__(
        self,
        responses: list[LLMResponse | Exception],
        model: str = "fake",
    ) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.model = model

    def generate(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        if self._call_count >= len(self._responses):
            return LLMResponse(content="ok", usage=TokenUsage())
        r = self._responses[self._call_count]
        self._call_count += 1
        if isinstance(r, Exception):
            raise r
        return r

    def generate_stream(  # type: ignore[override]
        self, messages: list[Message], **kwargs: Any
    ) -> Generator[str, None, LLMResponse]:
        resp = self.generate(messages, **kwargs)
        if resp.content:
            yield resp.content
        return resp


class _TransientError(Exception):
    """Simulates a 429/5xx transient error."""

    status_code = 429


class _PermanentError(Exception):
    """Simulates a permanent (non-retryable) error."""

    status_code = 400


def _ok_response() -> LLMResponse:
    return LLMResponse(content="ok", usage=TokenUsage(input_tokens=1, output_tokens=1))


def _make_recorder(provider: str = "test", max_attempts: int = 3) -> HealthRecorder:
    return HealthRecorder(provider, RetryPolicy(max_attempts=max_attempts, backoff_base_s=0.0))


# ---------------------------------------------------------------------------
# _is_transient
# ---------------------------------------------------------------------------


class TestIsTransient:
    def test_transient_by_status_code(self) -> None:
        assert _is_transient(_TransientError("rate limited"))

    def test_non_transient_by_status_code(self) -> None:
        assert not _is_transient(_PermanentError("bad request"))

    def test_transient_by_class_name(self) -> None:
        class TimeoutError(Exception):  # noqa: N818
            pass

        assert _is_transient(TimeoutError("timed out"))

    def test_generic_exception_not_transient(self) -> None:
        assert not _is_transient(ValueError("invalid"))


# ---------------------------------------------------------------------------
# resilient_call
# ---------------------------------------------------------------------------


class TestResilientCall:
    def test_success_on_first_attempt(self) -> None:
        policy = RetryPolicy(max_attempts=3, backoff_base_s=0.0)
        recorder = _make_recorder()
        result = resilient_call(lambda: "ok", policy, recorder)
        assert result == "ok"

    def test_retries_transient_error(self) -> None:
        attempts = [0]

        def _fn():
            attempts[0] += 1
            if attempts[0] < 3:
                raise _TransientError("retry me")
            return "ok"

        policy = RetryPolicy(max_attempts=3, backoff_base_s=0.0)
        recorder = _make_recorder()
        result = resilient_call(_fn, policy, recorder)
        assert result == "ok"
        assert attempts[0] == 3

    def test_raises_after_max_attempts(self) -> None:
        policy = RetryPolicy(max_attempts=2, backoff_base_s=0.0)
        recorder = _make_recorder(max_attempts=2)

        def _fn():
            raise _TransientError("always fail")

        with pytest.raises(_TransientError):
            resilient_call(_fn, policy, recorder)

    def test_non_transient_error_not_retried(self) -> None:
        calls = [0]

        def _fn():
            calls[0] += 1
            raise _PermanentError("permanent")

        policy = RetryPolicy(max_attempts=3, backoff_base_s=0.0)
        recorder = _make_recorder()
        with pytest.raises(_PermanentError):
            resilient_call(_fn, policy, recorder)
        assert calls[0] == 1  # No retry for permanent errors.

    def test_open_breaker_raises_immediately(self) -> None:
        # Use a policy with breaker_threshold=1 for both the call and the recorder.
        policy = RetryPolicy(max_attempts=3, backoff_base_s=0.0, breaker_threshold=1)
        recorder = HealthRecorder("test", policy)
        # Record enough failures to open the breaker (threshold=1 → opens on first failure).
        recorder.record_failure()
        snap = recorder.snapshot()
        assert snap.breaker == "open"

        calls = [0]

        def _fn():
            calls[0] += 1
            return "should not be called"

        with pytest.raises((RuntimeError, Exception)):
            resilient_call(_fn, policy, recorder)
        # Fn should not have been called since breaker is open.
        assert calls[0] == 0


# ---------------------------------------------------------------------------
# HealthRecorder / circuit breaker
# ---------------------------------------------------------------------------


class TestHealthRecorder:
    def test_success_closes_breaker(self) -> None:
        policy = RetryPolicy(breaker_threshold=3, backoff_base_s=0.0)
        recorder = HealthRecorder("p", policy)
        # Open the breaker.
        for _ in range(3):
            recorder.record_failure()
        assert recorder.snapshot().breaker == "open"
        # Record a success — breaker should close.
        recorder.record_success(100.0)
        snap = recorder.snapshot()
        assert snap.breaker == "closed"
        assert snap.consecutive_failures == 0

    def test_breaker_opens_at_threshold(self) -> None:
        policy = RetryPolicy(breaker_threshold=3, backoff_base_s=0.0)
        recorder = HealthRecorder("p", policy)
        for _i in range(3):
            recorder.record_failure()
        snap = recorder.snapshot()
        assert snap.breaker == "open"
        assert snap.consecutive_failures == 3

    def test_half_open_after_cooldown(self) -> None:
        policy = RetryPolicy(breaker_threshold=1, backoff_base_s=0.0, breaker_cooldown_s=0.01)
        recorder = HealthRecorder("p", policy)
        recorder.record_failure()
        assert recorder.snapshot().breaker == "open"
        # Wait past cooldown.
        time.sleep(0.05)
        snap = recorder.snapshot()
        assert snap.breaker == "half_open"

    def test_error_rate_calculation(self) -> None:
        policy = RetryPolicy()
        recorder = HealthRecorder("p", policy)
        recorder.record_success(10.0)
        recorder.record_failure()
        snap = recorder.snapshot()
        # 1 failure out of 2 = 50%
        assert abs(snap.recent_error_rate - 0.5) < 0.01

    def test_p50_latency_tracked(self) -> None:
        policy = RetryPolicy()
        recorder = HealthRecorder("p", policy)
        for ms in [100.0, 200.0, 300.0]:
            recorder.record_success(ms)
        snap = recorder.snapshot()
        assert snap.p50_latency_ms == 200.0  # median of [100, 200, 300]

    def test_half_open_probe_failure_reopens_breaker(self) -> None:
        """H7: a failed probe during the half-open trial must reopen the breaker
        immediately — previously only closed->open existed, so a still-flapping
        provider stuck in half-open let every subsequent probe through instead of
        backing off again.
        """
        policy = RetryPolicy(breaker_threshold=1, backoff_base_s=0.0, breaker_cooldown_s=0.01)
        recorder = HealthRecorder("p", policy)
        recorder.record_failure()
        assert recorder.snapshot().breaker == "open"
        time.sleep(0.05)
        assert recorder.snapshot().breaker == "half_open"

        recorder.record_failure()  # the half-open probe itself fails
        assert recorder.snapshot().breaker == "open"

    def test_on_update_sink_invoked_after_every_outcome(self) -> None:
        """H7: HealthRecorder must call an injected on_update sink after every
        success/failure so a caller (the router) can wire real outcomes into its
        own provider-health view instead of it staying permanently default.
        """
        seen = []
        policy = RetryPolicy(breaker_threshold=5, backoff_base_s=0.0)
        recorder = HealthRecorder("p", policy, on_update=seen.append)

        recorder.record_success(10.0)
        recorder.record_failure()

        assert len(seen) == 2
        assert seen[0].recent_error_rate == 0.0
        assert seen[1].consecutive_failures == 1

    def test_p50_latency_even_count_uses_nearest_rank(self) -> None:
        # Nearest-rank p50 over 4 sorted samples [100, 200, 300, 400] must
        # pick the lower-middle value (200), matching standard percentile
        # semantics (e.g. rank = ceil(0.5 * n) = 2 -> 0-indexed 1 -> 200.0).
        # The naive `lats[len(lats) // 2]` formula picks index 2 (300.0),
        # which is off by one for even-length datasets.
        policy = RetryPolicy()
        recorder = HealthRecorder("p", policy)
        for ms in [400.0, 100.0, 300.0, 200.0]:
            recorder.record_success(ms)
        snap = recorder.snapshot()
        assert snap.p50_latency_ms == 200.0


# ---------------------------------------------------------------------------
# ResilientClient
# ---------------------------------------------------------------------------


class TestResilientClient:
    def test_generate_success_on_first_try(self) -> None:
        inner = _FakeClient([_ok_response()])
        policy = RetryPolicy(max_attempts=3, backoff_base_s=0.0)
        recorder = _make_recorder()
        client = ResilientClient(inner=inner, policy=policy, recorder=recorder)
        result = client.generate([Message(role="user", content="hi")])
        assert result.content == "ok"

    def test_generate_retries_transient_error(self) -> None:
        inner = _FakeClient([_TransientError("rate limit"), _ok_response()])
        policy = RetryPolicy(max_attempts=3, backoff_base_s=0.0)
        recorder = _make_recorder()
        client = ResilientClient(inner=inner, policy=policy, recorder=recorder)
        result = client.generate([Message(role="user", content="hi")])
        assert result.content == "ok"
        assert inner._call_count == 2

    def test_generate_raises_after_max_attempts(self) -> None:
        inner = _FakeClient([_TransientError("fail")] * 5)
        policy = RetryPolicy(max_attempts=2, backoff_base_s=0.0)
        recorder = _make_recorder(max_attempts=2)
        client = ResilientClient(inner=inner, policy=policy, recorder=recorder)
        with pytest.raises(_TransientError):
            client.generate([Message(role="user", content="hi")])
        assert inner._call_count == 2

    def test_fallback_chain_triggered_on_terminal_failure(self) -> None:
        """GATE-FAILOVER: fallback client is tried when primary fails terminally."""
        primary = _FakeClient([_TransientError("always")] * 5, model="primary")
        fallback = _FakeClient([_ok_response()], model="fallback")
        policy = RetryPolicy(max_attempts=2, backoff_base_s=0.0)
        primary_rec = _make_recorder("primary", max_attempts=2)
        fallback_rec = _make_recorder("fallback", max_attempts=2)
        client = ResilientClient(
            inner=primary,
            policy=policy,
            recorder=primary_rec,
            fallbacks=[(fallback, fallback_rec)],
        )
        result = client.generate([Message(role="user", content="hi")])
        assert result.content == "ok"
        assert fallback._call_count == 1

    def test_stream_failover_does_not_reinvoke_primary(self) -> None:
        """H7: a mid-stream primary failure must fail over to the NEXT client in
        the chain, never re-invoke the same primary that just failed — retrying
        the identical primary risks a double-print/double-bill of a stream that
        may have already emitted partial output before it broke.
        """
        primary = _FakeClient([_TransientError("stream broke")], model="primary")
        fallback = _FakeClient([_ok_response()], model="fallback")
        policy = RetryPolicy(max_attempts=1, backoff_base_s=0.0)
        client = ResilientClient(
            inner=primary,
            policy=policy,
            recorder=_make_recorder("primary", 1),
            fallbacks=[(fallback, _make_recorder("fallback", 1))],
        )

        gen = client.generate_stream([Message(role="user", content="hi")])
        chunks = list(gen)

        assert primary._call_count == 1  # only the initial failed stream attempt
        assert fallback._call_count == 1  # the fallback, exactly once
        assert chunks == ["ok"]

    def test_all_fallbacks_exhausted_raises(self) -> None:
        primary = _FakeClient([_TransientError("fail")] * 5, model="p")
        fallback = _FakeClient([_TransientError("fail")] * 5, model="f")
        policy = RetryPolicy(max_attempts=2, backoff_base_s=0.0)
        client = ResilientClient(
            inner=primary,
            policy=policy,
            recorder=_make_recorder("p", 2),
            fallbacks=[(fallback, _make_recorder("f", 2))],
        )
        with pytest.raises(_TransientError):
            client.generate([Message(role="user", content="hi")])

    def test_list_models_delegates_to_inner(self) -> None:
        inner = _FakeClient([])
        inner.list_models = lambda: ["model-x"]  # type: ignore[method-assign]
        policy = RetryPolicy(max_attempts=1, backoff_base_s=0.0)
        client = ResilientClient(inner=inner, policy=policy, recorder=_make_recorder())
        assert client.list_models() == ["model-x"]

    def test_model_attribute_exposed(self) -> None:
        inner = _FakeClient([], model="claude-haiku-4-5")
        policy = RetryPolicy(max_attempts=1, backoff_base_s=0.0)
        client = ResilientClient(inner=inner, policy=policy, recorder=_make_recorder())
        assert client.model == "claude-haiku-4-5"
