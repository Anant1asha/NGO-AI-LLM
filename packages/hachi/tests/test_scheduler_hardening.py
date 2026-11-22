"""Hardening tests for the scheduler: file lock, timezone correctness, atomic save,
and deliver_result webhook delivery.

All time-sensitive tests use injected ``now`` so they are deterministic.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hachi.core.file_lock import file_lock
from hachi.jobs.scheduler import (
    Schedule,
    ScheduleKind,
    Scheduler,
    ScheduleStore,
    cron_next,
    deliver_result,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scheduler(tmp_path: Path) -> Scheduler:
    return Scheduler(ScheduleStore(tmp_path / "schedules.json"))


# ---------------------------------------------------------------------------
# Fix MR-9 / UC-PERF-003 / ADV-021 — cross-process file lock
# ---------------------------------------------------------------------------


class TestFileLock:
    """file_lock serializes concurrent access across threads (and, where feasible, processes)."""

    def test_same_thread_lock_and_unlock(self, tmp_path: Path) -> None:
        """The lock can be acquired and released without error."""
        target = tmp_path / "data.json"
        with file_lock(target):
            target.write_text("hello", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "hello"

    def test_two_threads_serialize(self, tmp_path: Path) -> None:
        """Two threads contending on the same file see mutually exclusive critical sections."""
        target = tmp_path / "counter.json"
        target.write_text("0", encoding="utf-8")

        errors: list[str] = []

        def worker(tid: int, iterations: int) -> None:
            for _ in range(iterations):
                try:
                    with file_lock(target):
                        val = int(target.read_text(encoding="utf-8"))
                        # Tiny sleep to give the other thread a chance to interfere
                        # if the lock were absent.
                        time.sleep(0.002)
                        target.write_text(str(val + 1), encoding="utf-8")
                except Exception as exc:
                    errors.append(f"Thread {tid}: {exc}")

        t1 = threading.Thread(target=worker, args=(1, 10))
        t2 = threading.Thread(target=worker, args=(2, 10))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert errors == [], f"Errors in worker threads: {errors}"
        final = int(target.read_text(encoding="utf-8"))
        assert final == 20, f"Expected 20 increments, got {final} (lock contention lost writes)"

    def test_subprocess_serialization(self, tmp_path: Path) -> None:
        """Two subprocesses contending on the same file each complete without corrupting it."""
        target = tmp_path / "shared.json"
        target.write_text("0", encoding="utf-8")

        # Each subprocess atomically increments the counter N times under the lock.
        # Use a script file (not -c) and no PIPE handles to avoid the Windows
        # handle-inheritance quirk in Python 3.14 when combining -c with PIPE.
        script_path = tmp_path / "lock_worker.py"
        script_path.write_text(
            """\
import sys
import time

sys.path.insert(0, sys.argv[1])
from pathlib import Path

from hachi.core.file_lock import file_lock

target = Path(sys.argv[2])
for _ in range(int(sys.argv[3])):
    with file_lock(target):
        val = int(target.read_text(encoding="utf-8"))
        time.sleep(0.001)
        target.write_text(str(val + 1), encoding="utf-8")
""",
            encoding="utf-8",
        )
        src_root = str(Path(__file__).parent.parent / "src")
        n = 5
        # Launch both processes, then wait for both (sequential wait is fine; the
        # real test is that the *counter* is exact, not that they ran in parallel).
        procs = [
            subprocess.Popen(
                [sys.executable, str(script_path), src_root, str(target), str(n)],
            )
            for _ in range(2)
        ]
        for p in procs:
            rc = p.wait(timeout=30)
            if rc != 0:
                pytest.fail(f"Lock-worker subprocess exited with code {rc}")

        final = int(target.read_text(encoding="utf-8"))
        assert final == n * 2, f"Expected {n * 2}, got {final} (cross-process lock failed)"


# ---------------------------------------------------------------------------
# Fix UC-RSCH-001 — cron timezone correctness
# ---------------------------------------------------------------------------


class TestCronTimezone:
    """cron_next honours the configured timezone for local-hour semantics."""

    def test_utc_default_unchanged(self) -> None:
        """Default UTC behaviour is preserved (regression guard)."""
        after = datetime(2026, 6, 5, 9, 30, tzinfo=UTC)
        nxt = cron_next("0 9 * * *", after, tz_name="utc")
        assert nxt == datetime(2026, 6, 6, 9, 0, tzinfo=UTC)

    def test_local_tz_returns_aware_utc(self) -> None:
        """'local' timezone returns timezone-aware UTC regardless of system tz."""
        after = datetime(2026, 6, 5, 0, 0, tzinfo=UTC)
        nxt = cron_next("0 9 * * *", after, tz_name="local")
        # Result must be UTC-aware.
        assert nxt.tzinfo is not None
        assert nxt.utcoffset() is not None

    def test_named_tz_new_york(self) -> None:
        """America/New_York (UTC-4 in summer): 09:00 local = 13:00 UTC."""
        pytest.importorskip("zoneinfo")
        after = datetime(2026, 6, 5, 8, 0, tzinfo=UTC)
        nxt = cron_next("0 9 * * *", after, tz_name="America/New_York")
        # In EDT (UTC-4) on 2026-06-05, 09:00 local = 13:00 UTC.
        assert nxt.hour == 13, f"Expected 13:00 UTC for 09:00 EDT, got {nxt.isoformat()}"
        assert nxt.tzinfo is not None

    def test_named_tz_not_naive_utc(self) -> None:
        """Firing hour in a non-UTC timezone must NOT equal the UTC hour."""
        pytest.importorskip("zoneinfo")
        after = datetime(2026, 6, 5, 0, 0, tzinfo=UTC)
        nxt_utc = cron_next("0 9 * * *", after, tz_name="utc")
        nxt_ny = cron_next("0 9 * * *", after, tz_name="America/New_York")
        # They fire at different UTC times.
        assert nxt_utc != nxt_ny, (
            "NYC and UTC schedules fired at the same UTC time — tz was ignored"
        )

    def test_schedule_timezone_flows_through_compute_next(self, tmp_path: Path) -> None:
        """Schedule.timezone is used by compute_next for cron schedules."""
        pytest.importorskip("zoneinfo")
        store = ScheduleStore(tmp_path / "s.json")
        sched = Scheduler(store)
        created = datetime(2026, 6, 5, 8, 0, tzinfo=UTC)
        s = sched.add(
            name="local-daily",
            task="briefing",
            kind="cron",
            cron="0 9 * * *",
            timezone="America/New_York",
            now=created,
        )
        # next_run should be 13:00 UTC (= 09:00 EDT)
        nxt = datetime.fromisoformat(s.next_run)  # type: ignore[arg-type]
        assert nxt.hour == 13, f"Expected next_run at 13:00 UTC, got {nxt.isoformat()}"


# ---------------------------------------------------------------------------
# Fix UC-RSCH-003 — missed-run logging (collapse-to-one)
# ---------------------------------------------------------------------------


class TestMissedRunLogging:
    """Missed runs collapse to one catch-up and that collapse is logged."""

    def test_missed_interval_runs_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        sched = _scheduler(tmp_path)
        t0 = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
        sched.add(name="poll", task="check", kind="interval", interval_seconds=60, now=t0)

        # Tick 5 hours later — many occurrences missed.
        import logging

        with caplog.at_level(logging.INFO, logger="hachi.jobs.scheduler"):
            fired = sched.tick(lambda _: None, now=t0 + timedelta(hours=5))

        assert len(fired) == 1, "Should fire exactly once (collapse-to-one)"
        # A log message mentioning missed occurrences should appear.
        missed_logs = [
            r for r in caplog.records if "collapsed" in r.message and "missed" in r.message
        ]
        assert missed_logs, (
            f"Expected a 'collapsed N missed' log entry but got: "
            f"{[r.message for r in caplog.records]}"
        )

    def test_missed_cron_runs_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        sched = _scheduler(tmp_path)
        created = datetime(2026, 6, 5, 8, 0, tzinfo=UTC)
        sched.add(name="hourly", task="check", kind="cron", cron="0 * * * *", now=created)

        import logging

        # Tick 3 hours after first expected fire.
        with caplog.at_level(logging.INFO, logger="hachi.jobs.scheduler"):
            fired = sched.tick(lambda _: None, now=created + timedelta(hours=4))

        assert len(fired) == 1
        missed_logs = [r for r in caplog.records if "collapsed" in r.message]
        assert missed_logs, "Expected collapsed-missed log for cron"


# ---------------------------------------------------------------------------
# Fix for atomic save (part of MR-9)
# ---------------------------------------------------------------------------


class TestAtomicSave:
    """save() uses temp+replace — a mid-write crash never corrupts the store."""

    def test_save_produces_valid_json(self, tmp_path: Path) -> None:
        store = ScheduleStore(tmp_path / "schedules.json")
        sched = Scheduler(store)
        t0 = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
        sched.add(name="x", task="t", kind="interval", interval_seconds=60, now=t0)

        path = tmp_path / "schedules.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert data[0]["name"] == "x"

    def test_no_temp_files_left_after_save(self, tmp_path: Path) -> None:
        """Temp files should be atomically renamed; none should linger after save."""
        store = ScheduleStore(tmp_path / "schedules.json")
        sched = Scheduler(store)
        t0 = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
        for i in range(5):
            sched.add(name=f"s{i}", task="t", kind="interval", interval_seconds=60, now=t0)

        leftovers = list(tmp_path.glob(".schedules-*.tmp"))
        assert leftovers == [], f"Temp files not cleaned up: {leftovers}"

    def test_concurrent_saves_do_not_corrupt(self, tmp_path: Path) -> None:
        """Multiple threads saving simultaneously should leave valid JSON."""
        path = tmp_path / "schedules.json"
        store = ScheduleStore(path)

        t0 = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
        schedules = [
            Schedule(
                schedule_id=str(i),
                name=f"s{i}",
                task="t",
                kind=ScheduleKind.INTERVAL,
                interval_seconds=60,
                created_at=t0.isoformat(),
            )
            for i in range(20)
        ]

        errors: list[str] = []

        def saver(batch: list[Schedule]) -> None:
            try:
                for _ in range(5):
                    store.save(batch)
                    time.sleep(0.001)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=saver, args=(schedules[:10],)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Save errors: {errors}"
        # File must still be valid JSON after all threads finish.
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Fix UC-RSCH-002 — deliver_result webhook POST with secret redaction
# ---------------------------------------------------------------------------


class TestDeliverResult:
    """deliver_result posts to the webhook URL and redacts secrets."""

    def _make_schedule(
        self,
        *,
        deliver_to: str = "webhook",
        webhook_url: str | None = "https://example.com/hook",
    ) -> Schedule:
        return Schedule(
            schedule_id="test-sched-1",
            name="my-schedule",
            task="do something",
            kind=ScheduleKind.INTERVAL,
            interval_seconds=3600,
            deliver_to=deliver_to,
            webhook_url=webhook_url,
            created_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC).isoformat(),
        )

    def test_webhook_posts_json(self) -> None:
        """deliver_result performs a POST with the expected JSON payload."""
        schedule = self._make_schedule()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            mock_post.return_value = FakeResponse()
            deliver_result(schedule, "The agent did the thing.")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs.args[0] == "https://example.com/hook"
            payload = call_kwargs.kwargs["json"]
            assert payload["schedule_id"] == "test-sched-1"
            assert payload["name"] == "my-schedule"
            assert "The agent did the thing." in payload["result"]

    def test_webhook_redacts_secrets(self) -> None:
        """Secrets in the result are redacted before the POST."""
        schedule = self._make_schedule()

        secret_result = "Here is your API key: sk-ant-api03-ThisIsAFakeSecretKey1234567890abcdef"

        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
            deliver_result(schedule, secret_result)
            payload = mock_post.call_args.kwargs["json"]
            # The raw secret must not appear in the posted result.
            assert "sk-ant-api03" not in payload["result"], (
                "Secret was not redacted from webhook payload"
            )
            assert "[REDACTED SECRET]" in payload["result"]

    def test_chat_mode_is_noop(self) -> None:
        """deliver_to='chat' does not make any HTTP call."""
        schedule = self._make_schedule(deliver_to="chat")
        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            deliver_result(schedule, "result text")
            mock_post.assert_not_called()

    def test_log_mode_does_not_post(self) -> None:
        """deliver_to='log' logs the result without an HTTP call."""
        schedule = self._make_schedule(deliver_to="log", webhook_url=None)
        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            deliver_result(schedule, "logged result")
            mock_post.assert_not_called()

    def test_missing_webhook_url_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """deliver_to='webhook' with no webhook_url logs a warning and does not crash."""
        import logging

        schedule = self._make_schedule(webhook_url=None)
        with caplog.at_level(logging.WARNING, logger="hachi.jobs.scheduler"):
            deliver_result(schedule, "some result")
        warnings = [r for r in caplog.records if "webhook_url" in r.message]
        assert warnings, "Expected a warning about missing webhook_url"

    def test_webhook_http_error_logged_not_raised(self) -> None:
        """An HTTP error from the webhook does not propagate — it is logged."""
        schedule = self._make_schedule()
        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")
            # Must not raise.
            deliver_result(schedule, "result")

    def test_allow_outbound_secrets_env_disables_redaction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting HACHI_ALLOW_OUTBOUND_SECRETS=1 bypasses redaction."""
        monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", "1")
        schedule = self._make_schedule()
        secret_result = "key: sk-ant-api03-FakeSecret1234567890abcdefghij"

        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
            deliver_result(schedule, secret_result)
            payload = mock_post.call_args.kwargs["json"]
            # With opt-out, the raw secret must be present.
            assert "sk-ant-api03" in payload["result"]

    def test_ssrf_unsafe_webhook_url_is_not_posted(self) -> None:
        """BB-53: deliver_result must route through net_guard.validate_outbound_url
        before POSTing — a webhook_url pointing at a link-local/loopback/internal
        address (that validate_outbound_url would reject) must never be requested."""
        schedule = self._make_schedule(webhook_url="http://169.254.169.254/latest/meta-data/")

        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            deliver_result(schedule, "result text")
            mock_post.assert_not_called()

    def test_loopback_webhook_url_is_not_posted(self) -> None:
        """BB-53: a loopback webhook_url must also be rejected before the POST."""
        schedule = self._make_schedule(webhook_url="http://127.0.0.1:9999/hook")

        with patch("hachi.jobs.scheduler.httpx.post") as mock_post:
            deliver_result(schedule, "result text")
            mock_post.assert_not_called()

    def test_ssrf_unsafe_webhook_url_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A rejected webhook URL must be logged, not silently dropped."""
        import logging

        schedule = self._make_schedule(webhook_url="http://169.254.169.254/latest/meta-data/")
        with (
            patch("hachi.jobs.scheduler.httpx.post") as mock_post,
            caplog.at_level(logging.WARNING, logger="hachi.jobs.scheduler"),
        ):
            deliver_result(schedule, "result text")
        mock_post.assert_not_called()
        assert any(
            "blocked" in r.message.lower()
            or "ssrf" in r.message.lower()
            or "not allowed" in r.message.lower()
            or "non-public" in r.message.lower()
            for r in caplog.records
        ), "Expected a warning explaining the webhook was blocked"


# ---------------------------------------------------------------------------
# UC-RSCH-004 — slow task doesn't block the tick loop (ScheduleRunner timing)
# ---------------------------------------------------------------------------


class TestTickLoopTiming:
    """ScheduleRunner measures inter-tick gap from tick completion, not start.

    We verify this by checking that mark_fired is called for all due schedules
    even when fire() is slow.
    """

    def test_slow_fire_does_not_skip_other_due_schedules(self, tmp_path: Path) -> None:
        """All due schedules in one tick are processed even if some fire() calls are slow."""
        sched = _scheduler(tmp_path)
        t0 = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
        sched.add(name="slow", task="t1", kind="interval", interval_seconds=60, now=t0)
        sched.add(name="fast", task="t2", kind="interval", interval_seconds=60, now=t0)
        sched.add(name="also-fast", task="t3", kind="interval", interval_seconds=60, now=t0)

        call_order: list[str] = []

        def fire(s: Schedule) -> None:
            call_order.append(s.name)
            if s.name == "slow":
                time.sleep(0.05)  # simulate a slow task

        fired = sched.tick(fire, now=t0 + timedelta(minutes=2))
        assert len(fired) == 3, (
            f"Expected 3 schedules fired, got {len(fired)}: {[s.name for s in fired]}"
        )
        assert "slow" in call_order
        assert "fast" in call_order
        assert "also-fast" in call_order
