"""Recurring schedules for proactive agents.

The job queue (:mod:`hachi.jobs.queue`) already handles one-shot delayed work
with retries/backoff. This module adds the missing piece for proactive agents:
**recurring** schedules — ``once`` at a time, ``every`` N seconds, or a ``cron``
expression — persisted across restarts so the agent can act without being asked.

The cron matcher is a dependency-free implementation of the common 5-field subset
(``*``, ``*/n``, ``a,b``, ``a-b``, ``a-b/n``) for minute / hour / day-of-month /
month / day-of-week. Day-of-week uses cron numbering (0 or 7 = Sunday).

Timezone handling
-----------------
Cron schedules are evaluated in the timezone specified by a schedule's ``timezone``
field (default ``"local"`` which means the system local timezone).  ``next_run`` and
``last_run`` are always stored as UTC ISO-8601 strings; the timezone is only used
when computing the next cron match.  Interval and once schedules remain UTC-only
(they are duration-based, not "fire at 09:00 local time" semantics).

The :class:`Scheduler` is pure logic over an injected ``now``, so it is fully
testable without a clock, network, or running agent. Execution/delivery is wired
in by passing a ``fire`` callback to :meth:`Scheduler.tick`.

Delivery
--------
:func:`deliver_result` performs webhook POST / notification delivery for a fired
schedule and redacts outbound secrets.  The resident runner in
``gateway/orchestrator.py`` should call this immediately after firing::

    def _fire_schedule(s: Schedule) -> None:
        result_text = session.chat(s.task)
        deliver_result(s, result_text)

Missed-run semantics
--------------------
When the tick loop wakes up late (process slept, system suspended) and a schedule
is overdue by N occurrences, **exactly one catch-up run fires**; missed occurrences
are dropped.  This is the ``collapse-to-one`` strategy.  The choice is logged at
INFO level so operators can tell that N-1 occurrences were silently skipped.

Tick serialization
------------------
Each due schedule is run by the ``fire`` callback **synchronously** inside
:meth:`Scheduler.tick`.  The tick method does not spawn background threads; the
caller (:class:`ScheduleRunner`) runs inside a dedicated daemon thread.  A slow
``fire`` callback will delay subsequent schedules within the *same* tick but will
NOT delay the *next* tick (because :class:`ScheduleRunner` measures wall-clock
time from the *end* of each tick).

The serialization guarantee: schedules within one tick are executed sequentially,
one-at-a-time, and each is ``mark_fired`` before the next is evaluated.  This
prevents the same schedule from firing twice in concurrent ticks even if the
previous tick ran long (``is_due`` checks the persisted ``next_run``).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from hachi.core.file_lock import file_lock
from hachi.core.net_guard import validate_outbound_url
from hachi.core.secret_scanner import redact_outbound

logger = logging.getLogger(__name__)


class ScheduleKind(StrEnum):
    """How a schedule recurs."""

    ONCE = "once"  # fire a single time at run_at
    INTERVAL = "interval"  # fire every interval_seconds
    CRON = "cron"  # fire on a 5-field cron expression


# ==========================================
# Cron matching (dependency-free, 5-field)
# ==========================================

# day-of-week upper bound is 7 because cron allows both 0 and 7 for Sunday.
_FIELD_BOUNDS = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]  # min hr dom mon dow


def _parse_cron_field(field_expr: str, lo: int, hi: int) -> set[int]:
    """Expand a single cron field into the concrete set of values it matches."""
    values: set[int] = set()
    for part in field_expr.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            base, _, step_str = part.partition("/")
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"cron step must be >= 1, got {step} in {part!r}")
        else:
            base = part
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            start_str, _, end_str = base.partition("-")
            start, end = int(start_str), int(end_str)
        else:
            start = end = int(base)
        # Reject out-of-range values instead of silently accepting a field that
        # can never match (e.g. minute "99" would otherwise create a dead schedule).
        if start < lo or end > hi or start > end:
            raise ValueError(f"cron field {part!r} out of range [{lo}, {hi}]")
        for v in range(start, end + 1):
            if (v - start) % step == 0:
                values.add(v)
    return values


def _parse_cron(expr: str) -> list[set[int]]:
    """Parse a 5-field cron expression into per-field value sets."""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"cron expression must have 5 fields, got {len(fields)}: {expr!r}")
    return [_parse_cron_field(f, lo, hi) for f, (lo, hi) in zip(fields, _FIELD_BOUNDS, strict=True)]


def cron_matches(expr: str, dt: datetime) -> bool:
    """Return True if ``dt`` (minute resolution) satisfies the cron expression.

    ``dt`` may be in any timezone (including naive, which is treated as UTC).  The
    match is performed on the *fields* of ``dt`` as-is; callers wanting local-time
    semantics should convert before calling.
    """
    minute, hour, dom, mon, dow = _parse_cron(expr)
    # cron day-of-week: 0/7 = Sunday; Python isoweekday() is Mon=1..Sun=7
    cron_dow = dt.isoweekday() % 7
    if dt.minute not in minute or dt.hour not in hour or dt.month not in mon:
        return False
    # Standard cron OR semantics between day-of-month and day-of-week when both
    # are restricted; if one is a full wildcard it does not constrain.
    dom_full = dom == set(range(1, 32))
    # dow is unrestricted only when it covers every weekday (Sun-Sat); `*` expands
    # to {0..7}, so test superset of {0..6} (a lone {7} is Sunday-only, NOT full).
    dow_full = set(range(0, 7)) <= dow
    dom_ok = dt.day in dom
    dow_ok = cron_dow in dow or (7 in dow and cron_dow == 0)
    if dom_full and dow_full:
        return True
    if dom_full:
        return dow_ok
    if dow_full:
        return dom_ok
    return dom_ok or dow_ok


def _resolve_tz(tz_name: str) -> timezone | Any:
    """Resolve a timezone name to a :class:`datetime.timezone` or
    :mod:`zoneinfo.ZoneInfo` instance.

    Accepts:
    - ``"utc"`` / ``"UTC"`` → :data:`datetime.UTC`
    - ``"local"`` → the system local timezone (via :meth:`datetime.astimezone`)
    - Any IANA name understood by :mod:`zoneinfo` (Python 3.9+), e.g.
      ``"America/New_York"``

    Args:
        tz_name: Timezone designator string.

    Returns:
        A :class:`tzinfo` subclass.

    Raises:
        ValueError: If the name is not recognised.
    """
    if tz_name.lower() in ("utc", "z"):
        return UTC
    if tz_name.lower() == "local":
        # datetime.now().astimezone().tzinfo gives the local tzinfo on all platforms.
        return datetime.now().astimezone().tzinfo
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+

        return ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError(f"Unknown timezone {tz_name!r}: {exc}") from exc


def cron_next(expr: str, after: datetime, tz_name: str = "utc") -> datetime:
    """Return the next datetime strictly after ``after`` that matches ``expr``.

    The cron expression is evaluated in the timezone given by ``tz_name``
    (default ``"utc"`` for backwards-compatibility).  The returned datetime is
    always **timezone-aware UTC**.

    When ``tz_name`` is ``"local"`` or a named IANA zone the search iterates in
    local time so that DST transitions are handled correctly — e.g. a ``0 2 * * *``
    schedule in ``"America/New_York"`` will fire at wall-clock 02:00 local time
    (the ambiguous / missing 2 AM during DST transitions will be handled by
    :meth:`datetime.fold` semantics).

    Args:
        expr:    5-field cron expression.
        after:   Lower bound (exclusive).  Must be timezone-aware.
        tz_name: Timezone in which to evaluate the cron fields.

    Returns:
        Next matching UTC datetime (timezone-aware).

    Raises:
        ValueError: On malformed expression or if no match found within 4 years.
    """
    _parse_cron(expr)  # validate early

    tz = _resolve_tz(tz_name)

    # Convert ``after`` to the target timezone for field matching.
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    after_local = after.astimezone(tz)

    candidate_local = after_local.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Cap the search at ~4 years to bound pathological/invalid expressions.
    for _ in range(4 * 366 * 24 * 60):
        if cron_matches(expr, candidate_local):
            # Convert back to UTC before returning.
            return candidate_local.astimezone(UTC)
        candidate_local += timedelta(minutes=1)
    raise ValueError(f"no cron match found within 4 years for {expr!r}")


# ==========================================
# Schedule model
# ==========================================


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value: str) -> datetime:
    """Parse an ISO datetime, assuming UTC if no timezone is present."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


# A retried create_schedule (LLM retry, tool-pool re-dispatch, turn resume) with the same
# logical identity inside this window returns the EXISTING schedule instead of minting a
# duplicate recurring job (AUDIT P0-3 / Theme A: no duplicate side effects on retry). The
# window is short — long enough to absorb retry storms, short enough that a genuinely
# intentional re-creation much later is still honored.
_DEDUP_WINDOW_SECONDS = 60.0


@dataclass(slots=True)
class Schedule:
    """A recurring (or one-shot) proactive task."""

    schedule_id: str
    name: str
    task: str  # the instruction handed to the proactive agent when it fires
    kind: ScheduleKind

    # kind-specific timing
    run_at: str | None = None  # ONCE: ISO datetime
    interval_seconds: int | None = None  # INTERVAL
    cron: str | None = None  # CRON: 5-field expression

    # Timezone for cron evaluation (IANA name, "local", or "utc").
    # "utc" preserves existing behaviour; "local" fires at the local wall clock.
    timezone: str = "utc"

    # delivery of the result
    deliver_to: str = "chat"  # "chat" | "webhook" | "log"
    webhook_url: str | None = None

    # optional condition — name of a haiku-class skill that must return "true" before firing
    condition_skill: str | None = None

    # bookkeeping
    enabled: bool = True
    created_at: str = field(default_factory=lambda: _now().isoformat())
    last_run: str | None = None
    next_run: str | None = None
    run_count: int = 0
    max_retries: int = 3

    def compute_next(self, after: datetime) -> datetime | None:
        """Compute the next fire time strictly after ``after`` (None if finished).

        For CRON schedules the next time is computed in the schedule's ``timezone``
        so that the cron fields are matched against local wall-clock time.
        """
        if self.kind == ScheduleKind.ONCE:
            if self.run_count > 0 or not self.run_at:
                return None
            return _parse_dt(self.run_at)
        if self.kind == ScheduleKind.INTERVAL:
            if not self.interval_seconds:
                return None
            base = _parse_dt(self.last_run) if self.last_run else _parse_dt(self.created_at)
            nxt = base + timedelta(seconds=self.interval_seconds)
            # Catch up without firing in a storm if ticks were missed.
            while nxt <= after:
                nxt += timedelta(seconds=self.interval_seconds)
            return nxt
        if self.kind == ScheduleKind.CRON and self.cron:
            return cron_next(self.cron, after, tz_name=self.timezone)
        return None

    def is_due(self, now: datetime) -> bool:
        return self.enabled and self.next_run is not None and _parse_dt(self.next_run) <= now

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Schedule:
        data = dict(data)
        data["kind"] = ScheduleKind(data["kind"])
        # Tolerate persisted records from before condition_skill/timezone were added.
        data.setdefault("condition_skill", None)
        data.setdefault("timezone", "utc")
        return cls(**data)


# ==========================================
# Persistent store
# ==========================================


class ScheduleStore:
    """JSON-backed persistence for schedules (survives restart).

    **Cross-process safety**: reads and writes are serialized with a cross-process
    advisory file lock (:func:`hachi.core.file_lock.file_lock`) in addition to
    the in-process :class:`threading.RLock`.  This prevents the TUI process and a
    background daemon that share the same ``schedules.json`` from racing each other
    (last-write-wins corruption, double-fires on stale ``next_run``).

    **Atomic saves**: :meth:`save` writes to a sibling temp file and uses
    :func:`os.replace` (atomic on Windows and POSIX when source/dest are on the
    same filesystem) so a crash mid-write never leaves a partial/corrupt JSON file.
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.RLock()

    def load(self) -> list[Schedule]:
        """Load schedules from disk, acquiring both the in-process and file locks."""
        with self._lock:
            with file_lock(self._path):
                if not self._path.exists():
                    return []
                try:
                    raw = json.loads(self._path.read_text(encoding="utf-8"))
                    return [Schedule.from_dict(d) for d in raw]
                except Exception as e:
                    logger.warning("Failed to load schedules from %s: %s", self._path, e)
                    return []

    def save(self, schedules: list[Schedule]) -> None:
        """Persist schedules atomically via temp-file + os.replace."""
        with self._lock:
            with file_lock(self._path):
                self._path.parent.mkdir(parents=True, exist_ok=True)
                payload = json.dumps([s.to_dict() for s in schedules], indent=2)
                # Write to a sibling temp file first; os.replace is atomic when
                # source and destination are on the same filesystem volume.
                fd, tmp_name = tempfile.mkstemp(
                    dir=self._path.parent,
                    prefix=".schedules-",
                    suffix=".tmp",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(payload)
                    os.replace(tmp_name, self._path)
                except Exception:
                    # Best-effort cleanup of the temp file on failure.
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
                    raise


# ==========================================
# Delivery (UC-RSCH-002)
# ==========================================


def deliver_result(schedule: Schedule, result: str) -> None:
    """Deliver the result of a fired schedule per its ``deliver_to`` / ``webhook_url``.

    This function encapsulates the complete delivery logic so both the CLI path
    (``hachi schedule run-due``) and the resident runner in
    ``gateway/orchestrator.py`` produce identical delivery behaviour.

    **Signature for the orchestrator owner to wire up:**

    .. code-block:: python

        from hachi.jobs.scheduler import deliver_result, Schedule

        def _fire_schedule(s: Schedule) -> None:
            result_text = session.chat(s.task)
            deliver_result(s, result_text)   # <-- add this line

    Delivery modes
    ~~~~~~~~~~~~~~
    - ``deliver_to == "chat"`` — no-op here; the result is already in the chat
      history via ``session.chat()``.
    - ``deliver_to == "webhook"`` — POST a JSON body to ``schedule.webhook_url``
      with ``{"schedule_id": ..., "name": ..., "result": <redacted>}``.  Secrets
      in the result are redacted via :func:`hachi.core.secret_scanner.redact_outbound`
      before transmission.  Uses :mod:`httpx` (already a project dependency) with a
      10 s timeout; errors are logged but not re-raised so one bad webhook does not
      kill other schedules.
    - ``deliver_to == "log"`` — emit ``result`` at INFO level (useful for headless
      / CI deployments where chat is not available).
    - Any other value — logged as a warning and dropped.

    Outbound secret redaction is applied for ``webhook`` and ``log`` modes.

    Args:
        schedule: The :class:`Schedule` that just fired.
        result:   The text result produced by the agent task.
    """
    mode = (schedule.deliver_to or "chat").lower()

    if mode == "chat":
        # Result already delivered through session.chat(); nothing to do.
        return

    if mode == "webhook":
        url = schedule.webhook_url
        if not url:
            logger.warning(
                "Schedule %s (%s) has deliver_to='webhook' but no webhook_url — dropping result.",
                schedule.schedule_id,
                schedule.name,
            )
            return

        # BB-53: apply the same SSRF guard the CLI path (`hachi schedule run-due`)
        # already uses before making any outbound request — a schedule's
        # webhook_url is user-configured, so it must be treated as untrusted.
        validation = validate_outbound_url(url)
        if not validation.ok:
            logger.warning(
                "deliver_result: webhook POST to %s blocked for schedule %s (%s)",
                url,
                schedule.schedule_id,
                validation.reason,
            )
            return

        safe_result, redacted_count = redact_outbound(result)
        if redacted_count:
            logger.info(
                "deliver_result: redacted %d secret(s) from schedule %s payload before POST",
                redacted_count,
                schedule.schedule_id,
            )
        payload = {
            "schedule_id": schedule.schedule_id,
            "name": schedule.name,
            "task": schedule.task,
            "result": safe_result,
        }
        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info(
                "deliver_result: webhook POST to %s succeeded (status %d) for schedule %s",
                url,
                resp.status_code,
                schedule.schedule_id,
            )
        except Exception as exc:
            logger.error(
                "deliver_result: webhook POST to %s failed for schedule %s: %s",
                url,
                schedule.schedule_id,
                exc,
            )
        return

    if mode == "log":
        safe_result, _ = redact_outbound(result)
        logger.info(
            "Schedule %s (%s) result: %s",
            schedule.schedule_id,
            schedule.name,
            safe_result,
        )
        return

    logger.warning(
        "Schedule %s (%s) has unknown deliver_to=%r — result dropped.",
        schedule.schedule_id,
        schedule.name,
        schedule.deliver_to,
    )


# ==========================================
# Scheduler
# ==========================================


class Scheduler:
    """Manage recurring schedules over an injected clock.

    All time-dependent methods accept an explicit ``now`` (defaulting to the real
    UTC clock) so behaviour is deterministic and unit-testable.

    Missed-run semantics
    --------------------
    When :meth:`tick` wakes and a schedule is overdue by N occurrences, **exactly
    one catch-up run fires** (the ``collapse-to-one`` strategy).  The N-1 skipped
    occurrences are logged at INFO level.  This is intentional: a burst of catch-up
    work from a long-sleeping daemon would likely hammer downstream systems and confuse
    users.  Callers that need different semantics (e.g. replay every missed occurrence)
    should call :meth:`due` and :meth:`mark_fired` directly.

    Tick serialization guarantee
    ----------------------------
    :meth:`tick` processes due schedules **sequentially** (one-at-a-time) inside the
    caller's thread.  A slow ``fire`` callback delays subsequent schedules within the
    *same* tick but the ``ScheduleRunner`` loop measures time from tick completion, so
    the *next* tick is not shortened.  Each schedule's ``next_run`` is advanced via
    :meth:`mark_fired` before the next schedule is evaluated — preventing double-fire
    even when two ticks overlap (which cannot happen inside ``ScheduleRunner`` but can
    occur if callers invoke :meth:`tick` from two threads).
    """

    def __init__(self, store: ScheduleStore):
        self._store = store
        self._schedules: dict[str, Schedule] = {s.schedule_id: s for s in store.load()}

    # ---- queries ----

    def list_schedules(self) -> list[Schedule]:
        return list(self._schedules.values())

    def get(self, schedule_id: str) -> Schedule | None:
        """Return a schedule by exact id, or by unique prefix."""
        if schedule_id in self._schedules:
            return self._schedules[schedule_id]
        matches = [s for sid, s in self._schedules.items() if sid.startswith(schedule_id)]
        return matches[0] if len(matches) == 1 else None

    def due(self, now: datetime | None = None) -> list[Schedule]:
        now = now or _now()
        return [s for s in self._schedules.values() if s.is_due(now)]

    # ---- mutations ----

    def add(
        self,
        *,
        name: str,
        task: str,
        kind: ScheduleKind | str,
        run_at: str | None = None,
        interval_seconds: int | None = None,
        cron: str | None = None,
        timezone: str = "utc",
        deliver_to: str = "chat",
        webhook_url: str | None = None,
        condition_skill: str | None = None,
        now: datetime | None = None,
        dedup_window_seconds: float = _DEDUP_WINDOW_SECONDS,
    ) -> Schedule:
        now = now or _now()
        kind = ScheduleKind(kind)
        self._validate(kind, run_at, interval_seconds, cron)
        # Idempotency (AUDIT P0-3): a retried create with the same logical identity inside
        # the dedup window returns the existing schedule rather than a duplicate. Scanning
        # the live store keeps the dedup record and the source of truth in sync (no parallel
        # bookkeeping that could drift from what is actually scheduled).
        duplicate = self._find_recent_duplicate(
            name=name,
            task=task,
            kind=kind,
            run_at=run_at,
            interval_seconds=interval_seconds,
            cron=cron,
            timezone=timezone,
            deliver_to=deliver_to,
            webhook_url=webhook_url,
            condition_skill=condition_skill,
            now=now,
            window_seconds=dedup_window_seconds,
        )
        if duplicate is not None:
            return duplicate
        schedule = Schedule(
            schedule_id=str(uuid.uuid4()),
            name=name,
            task=task,
            kind=kind,
            run_at=run_at,
            interval_seconds=interval_seconds,
            cron=cron,
            timezone=timezone,
            deliver_to=deliver_to,
            webhook_url=webhook_url,
            condition_skill=condition_skill,
            created_at=now.isoformat(),
        )
        nxt = schedule.compute_next(after=now - timedelta(seconds=1))
        schedule.next_run = nxt.isoformat() if nxt else None
        self._schedules[schedule.schedule_id] = schedule
        self._persist()
        return schedule

    def _find_recent_duplicate(
        self,
        *,
        name: str,
        task: str,
        kind: ScheduleKind,
        run_at: str | None,
        interval_seconds: int | None,
        cron: str | None,
        timezone: str,
        deliver_to: str,
        webhook_url: str | None,
        condition_skill: str | None,
        now: datetime,
        window_seconds: float,
    ) -> Schedule | None:
        """Return an existing schedule with the same logical identity created within
        ``window_seconds`` of ``now``, else None.

        Suppresses duplicate creations from a retried ``create_schedule`` (Theme A). A
        non-positive window disables dedup. Identity is the full set of user-meaningful
        fields — two schedules that differ in *any* of them are genuinely distinct.
        """
        if window_seconds <= 0:
            return None
        for s in self._schedules.values():
            if (
                s.name == name
                and s.task == task
                and s.kind == kind
                and s.run_at == run_at
                and s.interval_seconds == interval_seconds
                and s.cron == cron
                and s.timezone == timezone
                and s.deliver_to == deliver_to
                and s.webhook_url == webhook_url
                and s.condition_skill == condition_skill
            ):
                if not s.created_at:
                    continue
                age = abs((now - _parse_dt(s.created_at)).total_seconds())
                if age <= window_seconds:
                    return s
        return None

    def cancel(self, schedule_id: str) -> bool:
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            self._persist()
            return True
        return False

    def set_enabled(self, schedule_id: str, enabled: bool) -> bool:
        s = self._schedules.get(schedule_id)
        if not s:
            return False
        s.enabled = enabled
        self._persist()
        return True

    def mark_fired(self, schedule: Schedule, now: datetime) -> None:
        """Record a fire and advance (or retire) the schedule.

        Missed-run logging: if the schedule's ``next_run`` was long in the past,
        we log how many occurrences were implicitly skipped so operators can see
        that the scheduler is collapsing missed runs rather than silently losing them.
        """
        # Calculate and log missed occurrences before advancing.
        if schedule.next_run and schedule.kind in (ScheduleKind.INTERVAL, ScheduleKind.CRON):
            scheduled_at = _parse_dt(schedule.next_run)
            if schedule.kind == ScheduleKind.INTERVAL and schedule.interval_seconds:
                elapsed = max(0.0, (now - scheduled_at).total_seconds())
                missed = int(elapsed // schedule.interval_seconds)
                if missed > 0:
                    logger.info(
                        "Schedule %s (%s): collapsed %d missed interval occurrence(s) into one "
                        "catch-up run (interval=%ds, overdue by %.1fs).",
                        schedule.schedule_id,
                        schedule.name,
                        missed,
                        schedule.interval_seconds,
                        elapsed,
                    )
            elif schedule.kind == ScheduleKind.CRON and schedule.cron:
                # Count missed cron occurrences by walking forward from scheduled_at.
                missed = 0
                try:
                    probe = scheduled_at
                    while True:
                        nxt_probe = cron_next(schedule.cron, probe, tz_name=schedule.timezone)
                        if nxt_probe > now:
                            break
                        missed += 1
                        probe = nxt_probe
                        if missed >= 1440:  # safety: don't iterate forever
                            break
                except Exception:
                    pass
                if missed > 0:
                    logger.info(
                        "Schedule %s (%s): collapsed %d missed cron occurrence(s) into one "
                        "catch-up run (expr=%r).",
                        schedule.schedule_id,
                        schedule.name,
                        missed,
                        schedule.cron,
                    )

        schedule.last_run = now.isoformat()
        schedule.run_count += 1
        if schedule.kind == ScheduleKind.ONCE:
            schedule.enabled = False
            schedule.next_run = None
        else:
            nxt = schedule.compute_next(after=now)
            schedule.next_run = nxt.isoformat() if nxt else None
        self._persist()

    def tick(
        self,
        fire: Callable[[Schedule], None],
        now: datetime | None = None,
        *,
        condition_evaluator: Callable[[str], bool] | None = None,
    ) -> list[Schedule]:
        """Fire every due schedule via ``fire`` and advance each. Returns those fired.

        Semantics
        ---------
        - A ``fire`` callback that raises does **not** advance the schedule (so it
          stays due and is retried on the next tick); other schedules are unaffected.
        - Schedules are processed **one at a time** (no concurrent dispatch).  A slow
          ``fire`` callback will delay others in the same tick but will not suppress
          them — all due schedules within a single :meth:`tick` call are eventually
          processed.
        - If a schedule becomes overdue by multiple occurrences between ticks, only
          **one** catch-up run fires (see class docstring for rationale).

        Args:
            fire:                Callback invoked for each due schedule.
            now:                 Override the current time (for testing).
            condition_evaluator: Optional callable that takes a skill name and returns
                                 ``True`` if the condition passes.  If a schedule has
                                 a ``condition_skill`` and the evaluator returns ``False``,
                                 the schedule is skipped (not advanced) for this tick.

        Returns:
            List of schedules that were successfully fired and advanced.
        """
        now = now or _now()
        fired: list[Schedule] = []
        for schedule in self.due(now):
            # Evaluate optional condition before firing.
            if schedule.condition_skill and condition_evaluator is not None:
                try:
                    if not condition_evaluator(schedule.condition_skill):
                        logger.debug(
                            "Schedule %s condition '%s' not met — skipping",
                            schedule.schedule_id,
                            schedule.condition_skill,
                        )
                        continue
                except Exception as cond_err:
                    logger.warning(
                        "Schedule %s condition evaluation failed: %s",
                        schedule.schedule_id,
                        cond_err,
                    )
                    continue
            try:
                fire(schedule)
            except Exception as e:
                logger.error(
                    "Schedule %s (%s) fire failed: %s", schedule.schedule_id, schedule.name, e
                )
                continue
            self.mark_fired(schedule, now)
            fired.append(schedule)
        return fired

    def run_now(
        self,
        schedule_id: str,
        fire: Callable[[Schedule], None],
        now: datetime | None = None,
    ) -> bool:
        """Force-fire one schedule immediately, regardless of its ``next_run``.

        Mirrors the per-schedule body of :meth:`tick` (same ``fire`` +
        :meth:`mark_fired` sequencing) but bypasses the ``due()`` gate and the
        condition-skill evaluator — this is an explicit user-triggered run, not
        an automatic tick, so it always executes.

        A ``fire`` callback that raises does **not** advance the schedule (same
        semantics as :meth:`tick`) and the exception propagates to the caller so
        a manual "run now" surfaces failures instead of silently swallowing them.

        Args:
            schedule_id: Exact id or unique prefix (see :meth:`get`).
            fire:        Callback invoked with the resolved :class:`Schedule`.
            now:         Override the current time (for testing).

        Returns:
            ``True`` if the schedule was found and fired; ``False`` if no
            schedule matches ``schedule_id``.
        """
        schedule = self.get(schedule_id)
        if schedule is None:
            return False
        now = now or _now()
        fire(schedule)
        self.mark_fired(schedule, now)
        return True

    # ---- internals ----

    @staticmethod
    def _validate(
        kind: ScheduleKind,
        run_at: str | None,
        interval_seconds: int | None,
        cron: str | None,
    ) -> None:
        if kind == ScheduleKind.ONCE:
            if not run_at:
                raise ValueError("kind 'once' requires run_at (ISO datetime)")
            _parse_dt(run_at)
        elif kind == ScheduleKind.INTERVAL:
            if not interval_seconds or interval_seconds <= 0:
                raise ValueError("kind 'interval' requires a positive interval_seconds")
        elif kind == ScheduleKind.CRON:
            if not cron:
                raise ValueError("kind 'cron' requires a cron expression")
            _parse_cron(cron)  # raises on malformed expressions

    def _persist(self) -> None:
        self._store.save(list(self._schedules.values()))


class ScheduleRunner:
    """Background thread that calls ``scheduler.tick()`` on a fixed interval.

    Start it once at session boot; stop it on shutdown. The tick interval
    defaults to 30 s so sub-minute interval schedules fire on time without
    hammering the agent.

    The runner measures wall-clock time from the **end** of each tick so a slow
    ``fire`` callback never causes the *next* tick to run immediately after the
    previous one finishes — the full ``tick_interval_seconds`` gap is always
    honoured between tick completions.
    """

    def __init__(
        self,
        scheduler: Scheduler,
        fire: Callable[[Schedule], None],
        tick_interval_seconds: int = 30,
    ):
        self._scheduler = scheduler
        self._fire = fire
        self._interval = tick_interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="schedule-runner")

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the runner to exit and join its thread."""
        self._stop.set()
        self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._scheduler.tick(self._fire)
            except Exception:
                logger.exception("ScheduleRunner tick error")
