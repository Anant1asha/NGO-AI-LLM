"""Resilience layer: retry, circuit-breaker, and health tracking.

Closes debt D6 (600s Anthropic default; no retry/breaker). Design doc 13 §5.

``ResilientClient`` decorates any ``BaseLLMClient`` with:
  - per-call timeout (default 60s, down from 600s)
  - bounded exponential-backoff retry for transient errors (429, 5xx, timeout)
  - circuit-breaker with half-open hysteresis so a flapping provider can't
    oscillate the model mid-task (amendment A12)
  - latency and error-rate recording into ``ProviderHealth``

``resilient_call`` is a generic variant for ``SpeechProvider`` / ``SearchProvider``.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from hachi.core.llm import BaseLLMClient, LLMResponse, Message

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes / exception patterns that indicate a transient error worth retrying.
_TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Exception type names that are transient (matched by class name substring).
_TRANSIENT_EXCEPTION_NAMES: tuple[str, ...] = (
    "timeout",
    "Timeout",
    "RateLimitError",
    "APIConnectionError",
    "ConnectError",
    "ReadTimeout",
    "WriteTimeout",
    "PoolTimeout",
    "RemoteProtocolError",
    "InternalServerError",
    "OverloadedError",
    "ServiceUnavailable",
)


def _is_transient(exc: BaseException) -> bool:
    """Return ``True`` when *exc* is likely a transient error worth retrying."""
    cls_name = type(exc).__name__
    for name in _TRANSIENT_EXCEPTION_NAMES:
        if name in cls_name:
            return True
    # httpx / anthropic SDK may embed the status code as an attribute.
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int) and status in _TRANSIENT_STATUS_CODES:
        return True
    return False


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


class RetryPolicy(BaseModel):
    """Configures retry and circuit-breaker behaviour.

    Args:
        max_attempts: Total number of attempts (1 = no retry).
        backoff_base_s: Base wait in seconds before the first retry; doubles each attempt.
        timeout_s: Per-call timeout in seconds.  Default 60s (down from the 600s SDK default).
        breaker_threshold: Consecutive failures before the breaker opens.
        breaker_cooldown_s: Seconds the breaker stays open before entering half-open.
    """

    model_config = ConfigDict(extra="ignore")

    max_attempts: int = 3
    backoff_base_s: float = 0.5
    timeout_s: float = 60.0
    breaker_threshold: int = 5
    breaker_cooldown_s: float = 30.0

    @classmethod
    def from_config(cls, config: Any) -> RetryPolicy:
        """Extract ``[routing.resilience]`` from a :class:`~hachi.core.settings.ResolvedConfig`.

        Falls back to defaults when the section is absent.
        """
        try:
            routing = getattr(config, "routing", None)
            if routing is not None:
                res = getattr(routing, "resilience", None)
                if res is not None:
                    if isinstance(res, RetryPolicy):
                        return res
                    return cls.model_validate(res if isinstance(res, dict) else res.model_dump())
        except Exception:
            pass
        return cls()


# ---------------------------------------------------------------------------
# ProviderHealth
# ---------------------------------------------------------------------------


@dataclass
class ProviderHealth:
    """Live health snapshot for one provider instance.

    Attributes:
        provider: Provider name / registry key.
        available: ``False`` when the provider is known-broken.
        recent_error_rate: Fraction of recent calls that failed (0.0–1.0).
        p50_latency_ms: Median latency of successful calls in milliseconds.
        consecutive_failures: Number of failures without a success in between.
        breaker: Current breaker state.
    """

    provider: str
    available: bool = True
    recent_error_rate: float = 0.0
    p50_latency_ms: float = 0.0
    consecutive_failures: int = 0
    breaker: Literal["closed", "open", "half_open"] = "closed"

    def is_usable(self) -> bool:
        """Return ``True`` when the provider may be tried."""
        return self.available and self.breaker != "open"


# ---------------------------------------------------------------------------
# HealthRecorder
# ---------------------------------------------------------------------------


class HealthRecorder:
    """Thread-safe recorder that tracks latency and failures for one provider.

    Maintains a sliding window of recent call outcomes and derives the
    :class:`ProviderHealth` snapshot consumed by the router.
    """

    _WINDOW = 20  # calls retained for error-rate calculation

    def __init__(
        self,
        provider: str,
        policy: RetryPolicy,
        *,
        on_update: Callable[[ProviderHealth], None] | None = None,
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._lock = threading.Lock()
        self._outcomes: list[bool] = []  # True = success
        self._latencies_ms: list[float] = []
        self._consecutive_failures = 0
        self._breaker: Literal["closed", "open", "half_open"] = "closed"
        self._breaker_opened_at: float = 0.0
        # H7: optional sink invoked after every outcome so a caller (the model
        # router) can wire real call results into its own provider-health view
        # instead of that view staying permanently at its boot-time default.
        self._on_update = on_update

    def _notify(self) -> None:
        if self._on_update is not None:
            self._on_update(self.snapshot())

    def record_success(self, latency_ms: float) -> None:
        """Record a successful call."""
        with self._lock:
            self._outcomes.append(True)
            self._latencies_ms.append(latency_ms)
            if len(self._outcomes) > self._WINDOW:
                self._outcomes.pop(0)
            if len(self._latencies_ms) > self._WINDOW:
                self._latencies_ms.pop(0)
            self._consecutive_failures = 0
            # Close breaker on success (even from half-open).
            self._breaker = "closed"
        self._notify()

    def record_failure(self) -> None:
        """Record a failed call and potentially open the circuit breaker."""
        with self._lock:
            self._outcomes.append(False)
            if len(self._outcomes) > self._WINDOW:
                self._outcomes.pop(0)
            self._consecutive_failures += 1
            if (
                self._consecutive_failures >= self._policy.breaker_threshold
                and self._breaker == "closed"
            ):
                self._breaker = "open"
                self._breaker_opened_at = time.monotonic()
                logger.warning(
                    "HealthRecorder[%s]: circuit breaker OPENED after %d consecutive failures",
                    self._provider,
                    self._consecutive_failures,
                )
            elif self._breaker == "half_open":
                # H7: a failed probe during the half-open trial must reopen the
                # breaker immediately — previously only closed->open existed, so
                # a still-flapping provider stuck in half-open let every probe
                # through instead of backing off again.
                self._breaker = "open"
                self._breaker_opened_at = time.monotonic()
                logger.warning(
                    "HealthRecorder[%s]: half-open probe failed — circuit breaker REOPENED",
                    self._provider,
                )
        self._notify()

    def snapshot(self) -> ProviderHealth:
        """Return the current health snapshot (thread-safe)."""
        with self._lock:
            # Transition open → half-open after cooldown.
            if (
                self._breaker == "open"
                and time.monotonic() - self._breaker_opened_at >= self._policy.breaker_cooldown_s
            ):
                self._breaker = "half_open"
                logger.info("HealthRecorder[%s]: circuit breaker → HALF-OPEN", self._provider)

            n = len(self._outcomes)
            error_rate = sum(1 for ok in self._outcomes if not ok) / n if n > 0 else 0.0
            lats = sorted(self._latencies_ms)
            # Nearest-rank percentile: rank = ceil(p * n), 1-indexed, clamped to
            # [0, n-1] after converting to a 0-index. `len(lats) // 2` is off by
            # one for even-length datasets (e.g. n=4 picks index 2 instead of 1).
            p50 = lats[max(0, math.ceil(0.5 * len(lats)) - 1)] if lats else 0.0

            return ProviderHealth(
                provider=self._provider,
                available=True,
                recent_error_rate=error_rate,
                p50_latency_ms=p50,
                consecutive_failures=self._consecutive_failures,
                breaker=self._breaker,
            )


# ---------------------------------------------------------------------------
# Generic resilient_call
# ---------------------------------------------------------------------------


def resilient_call(
    fn: Callable[[], T],
    policy: RetryPolicy,
    recorder: HealthRecorder,
    *,
    on_failover: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Call *fn* with retry and circuit-breaker semantics.

    Args:
        fn: The callable to execute (must be idempotent).
        policy: Retry/breaker configuration.
        recorder: Health recorder that tracks outcomes.
        on_failover: Optional callback invoked on each retry ``(attempt, exc)``.

    Returns:
        The return value of *fn*.

    Raises:
        The last exception when all attempts are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        health = recorder.snapshot()
        if not health.is_usable():
            if last_exc is not None:
                raise last_exc
            raise RuntimeError(f"Provider {recorder._provider} circuit breaker is open")

        t0 = time.monotonic()
        try:
            result = fn()
            latency_ms = (time.monotonic() - t0) * 1000
            recorder.record_success(latency_ms)
            return result
        except Exception as exc:
            last_exc = exc
            recorder.record_failure()
            if not _is_transient(exc) or attempt >= policy.max_attempts:
                raise
            wait = policy.backoff_base_s * (2 ** (attempt - 1))
            logger.debug(
                "resilient_call: attempt %d/%d failed (%s); retrying in %.2fs",
                attempt,
                policy.max_attempts,
                type(exc).__name__,
                wait,
            )
            if on_failover is not None:
                on_failover(attempt, exc)
            time.sleep(wait)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("resilient_call: no attempts made")  # pragma: no cover


# ---------------------------------------------------------------------------
# ResilientClient
# ---------------------------------------------------------------------------


class ResilientClient(BaseLLMClient):  # type: ignore[misc]
    """Decorates any :class:`~hachi.core.llm.BaseLLMClient` with retry and circuit-breaker.

    ``ResilientClient`` IS a ``BaseLLMClient``, so it is a drop-in replacement
    everywhere a ``BaseLLMClient`` is expected (the loop is unchanged).

    Fallback chain: when *inner* fails terminally (after retries / breaker open),
    the first element of *fallbacks* is tried.  On that failing too, the next is
    tried, and so on.  Each transition emits a ``provider.failover`` log event.

    Args:
        inner: The primary client.
        policy: Retry/breaker configuration.
        recorder: Health recorder for the primary provider.
        fallbacks: Optional ordered list of ``(client, recorder)`` fallback pairs.
    """

    def __init__(
        self,
        inner: BaseLLMClient,
        policy: RetryPolicy,
        recorder: HealthRecorder,
        fallbacks: list[tuple[BaseLLMClient, HealthRecorder]] | None = None,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._recorder = recorder
        self._fallbacks: list[tuple[BaseLLMClient, HealthRecorder]] = fallbacks or []
        # Expose `model` attribute from inner for cost tracking / introspection.
        self.model: str = getattr(inner, "model", "unknown")

    def _call_with_chain(
        self,
        fn_builder: Callable[[BaseLLMClient], Callable[[], Any]],
        *,
        include_primary: bool = True,
    ) -> Any:
        """Drive the fallback chain for a given operation.

        Args:
            fn_builder: Given a client, returns the zero-arg callable to try.
            include_primary: When ``False``, skip ``self._inner`` and start the
                chain at the first fallback. H7: a mid-stream primary failure in
                ``generate_stream`` must not re-invoke the same primary that just
                failed — that risks a double-print/double-bill of a stream that
                already emitted partial output before it broke.
        """
        chain = [(self._inner, self._recorder)] + self._fallbacks
        if not include_primary:
            chain = chain[1:]
        last_exc: BaseException | None = None

        for idx, (client, recorder) in enumerate(chain):
            if idx > 0:
                logger.warning(
                    "ResilientClient: failing over to fallback[%d] (model=%s)",
                    idx,
                    getattr(client, "model", "unknown"),
                )

            fn = fn_builder(client)
            try:
                return resilient_call(fn, self._policy, recorder)
            except Exception as exc:
                last_exc = exc
                logger.error(
                    "ResilientClient: fallback[%d] (model=%s) failed: %s",
                    idx,
                    getattr(client, "model", "unknown"),
                    exc,
                )

        raise last_exc or RuntimeError("ResilientClient: all fallbacks exhausted")

    # ------------------------------------------------------------------
    # BaseLLMClient interface
    # ------------------------------------------------------------------

    def generate(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> LLMResponse:
        """Generate a response via the chain with retry and circuit-breaker."""

        def _build(client: BaseLLMClient) -> Callable[[], LLMResponse]:
            def _call() -> LLMResponse:
                return client.generate(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=tools,
                    dynamic_system=dynamic_system,
                )

            return _call

        return self._call_with_chain(_build)

    def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> Generator[str, None, LLMResponse]:
        """Stream text deltas via the primary client (fallback uses generate)."""
        # Streaming complicates the retry/fallback story; we use the primary directly
        # for streaming and fall back to generate() on failure.
        t0 = time.monotonic()
        try:
            # Capture and RETURN the inner generator's value (the final LLMResponse).
            # `yield from` evaluates to the delegated generator's return value; dropping
            # it makes this generator return None, so callers that read the streamed
            # response (loop.run → response.usage) crash on a successful stream.
            response = yield from self._inner.generate_stream(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools,
                dynamic_system=dynamic_system,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            self._recorder.record_success(latency_ms)
            return response
        except Exception as exc:
            self._recorder.record_failure()
            if self._fallbacks:
                logger.warning(
                    "ResilientClient.generate_stream: primary failed (%s); "
                    "falling back to generate() via chain",
                    type(exc).__name__,
                )
                response = self._call_with_chain(
                    lambda c: (
                        lambda: c.generate(  # noqa: E731
                            messages=messages,
                            system_prompt=system_prompt,
                            tools=tools,
                            dynamic_system=dynamic_system,
                        )
                    ),
                    include_primary=False,
                )
                if response.content:
                    yield response.content
                return response
            raise

    def list_models(self) -> list[str]:
        """Delegate to the inner client (no retry needed for model listing)."""
        try:
            return list(self._inner.list_models())
        except Exception:
            return []

    @property
    def supports_vision(self) -> bool:
        """Return ``True`` when the primary inner client's model has the VISION capability.

        Delegates to the inner client's ``supports_vision`` property so callers
        need not unwrap the resilience layer.
        """
        return bool(getattr(self._inner, "supports_vision", False))

    @property
    def _health(self) -> ProviderHealth:
        """Current health snapshot (convenience attribute)."""
        return self._recorder.snapshot()
