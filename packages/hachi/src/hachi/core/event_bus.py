"""EventBus — publish/subscribe over the Hachi runtime event taxonomy.

Sync subscribers run inline in publish order, wrapped in log-and-continue (never
propagate exceptions into the loop).  A sync subscriber must NOT re-enter
publish() — doing so risks infinite recursion; enqueue a job instead.

Async subscribers dispatch via the job queue as named handler jobs so they are
durable across restarts.

Pattern matching uses the dotted taxonomy:
  "*"           — matches everything
  "session.*"   — matches any event whose name starts with "session."
  "tool.call.*" — matches any event whose name starts with "tool.call."
  Exact strings — exact match only
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from hachi.core.runtime_events import RuntimeEvent

logger = logging.getLogger(__name__)

Handler = Callable[[RuntimeEvent], None]


@dataclass
class Subscription:
    """A registered subscriber on the EventBus."""

    pattern: str
    handler: Handler
    mode: Literal["sync", "async"]
    name: str | None
    # async-mode jobs need access to the job queue at dispatch time; injected
    # by EventBus._dispatch_async when mode=="async".
    _job_queue: Any = field(default=None, repr=False, compare=False)


def _pattern_matches(pattern: str, event_name: str) -> bool:
    """Return True if *pattern* matches *event_name*.

    Supported forms:
    - ``"*"``           — matches any event
    - ``"prefix.*"``    — matches any event whose name starts with ``"prefix."``
    - exact string      — literal equality
    """
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-1]  # e.g. "tool.call."
        return event_name.startswith(prefix)
    return pattern == event_name


class EventBus:
    """Lightweight in-process publish/subscribe bus.

    Thread-safe.  Publish assigns a monotonic sequence number before fan-out so
    ordering is preserved even under concurrent publishers.

    Async subscribers are dispatched via the injected *job_queue* (if any) using
    ``handler_name`` so they survive process restarts.  If no queue is injected,
    async subscribers run synchronously (useful in tests).
    """

    def __init__(self, job_queue: Any = None) -> None:
        """
        Args:
            job_queue: Optional :class:`~hachi.jobs.JobQueue` for async dispatch.
                       When ``None``, async subscribers run inline (sync fallback).
        """
        self._lock = threading.Lock()
        self._subscriptions: list[Subscription] = []
        self._sequence: int = 0
        self._job_queue = job_queue

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(
        self,
        pattern: str,
        handler: Handler,
        mode: Literal["sync", "async"] = "sync",
        name: str | None = None,
    ) -> Subscription:
        """Register *handler* to receive events matching *pattern*.

        Args:
            pattern: Dotted event pattern (``"*"``, ``"session.*"``, exact name).
            handler: Callable accepting a :class:`~hachi.core.runtime_events.RuntimeEvent`.
            mode:    ``"sync"`` — run inline during :meth:`publish`;
                     ``"async"`` — dispatch as a named job via the job queue.
            name:    Optional stable handler name (required for async durability).

        Returns:
            The created :class:`Subscription` (keep it to call :meth:`unsubscribe`).
        """
        sub = Subscription(pattern=pattern, handler=handler, mode=mode, name=name)
        with self._lock:
            self._subscriptions.append(sub)
        return sub

    def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a previously registered subscription.

        No-op if the subscription is not found (safe to call after bus reset).
        """
        with self._lock:
            try:
                self._subscriptions.remove(subscription)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, event: RuntimeEvent) -> int:
        """Fan-out *event* to all matching subscribers.

        Assigns a monotonic sequence number before fan-out.  Sync subscribers run
        in registration order.  Exceptions in sync handlers are caught, logged, and
        swallowed — they never propagate into the caller.

        Args:
            event: The event to publish.

        Returns:
            The monotonic sequence number assigned to this event.
        """
        with self._lock:
            self._sequence += 1
            seq = self._sequence
            # Snapshot so we can release the lock before calling handlers.
            subs = list(self._subscriptions)

        for sub in subs:
            if not _pattern_matches(sub.pattern, event.name):
                continue
            if sub.mode == "async":
                self._dispatch_async(sub, event, seq)
            else:
                try:
                    sub.handler(event)
                except Exception:
                    logger.exception(
                        "EventBus: sync subscriber %r raised for event %r — continuing",
                        sub.name or repr(sub.handler),
                        event.name,
                    )
        return seq

    def _dispatch_async(self, sub: Subscription, event: RuntimeEvent, seq: int) -> None:
        """Dispatch *event* to an async subscriber via the job queue (or inline)."""
        queue = self._job_queue
        if queue is None:
            # No queue injected — run inline as sync fallback (useful in tests).
            try:
                sub.handler(event)
            except Exception:
                logger.exception(
                    "EventBus: async subscriber %r raised (inline fallback) for event %r",
                    sub.name or repr(sub.handler),
                    event.name,
                )
            return

        handler_name = sub.name or "react"
        payload = {
            "event_name": event.name,
            "event_payload": event.payload,
            "event_timestamp": event.timestamp,
            "event_sequence": seq,
        }
        try:
            from hachi.jobs import Job, JobStatus

            job = Job(
                job_id="",
                name=f"bus.{handler_name}.{event.name}",
                handler_name=handler_name,
                payload=payload,
                status=JobStatus.PENDING,
            )
            queue.enqueue(job)
        except Exception:
            logger.exception(
                "EventBus: failed to enqueue async job for subscriber %r, event %r",
                handler_name,
                event.name,
            )

    def clear(self) -> None:
        """Remove all subscriptions (useful for test teardown)."""
        with self._lock:
            self._subscriptions.clear()

    @property
    def subscription_count(self) -> int:
        """Number of active subscriptions."""
        with self._lock:
            return len(self._subscriptions)
