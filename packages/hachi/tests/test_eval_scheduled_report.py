"""Tests for src/hachi/core/eval/scheduled_report.py (E5).

All tests are real (no mocking of core logic):
- EvalReport is built from real SessionStore rows.
- Markdown is rendered and checked for key strings.
- Artifact generation writes real files and is verified by parsing them.
- Marker helpers round-trip correctly and handle corruption gracefully.
- maybe_generate_report exercises the full due-check / generate / emit pipeline.
- eval snapshot CLI is exercised via typer.testing.CliRunner with a monkeypatched
  _open_store so the test never touches the real sessions.db.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from hachi.core.eval.report import EvalReport, PerModelStats, RecentFailure
from hachi.core.eval.scheduled_report import (
    due_for_report,
    generate_failure_report_artifact,
    maybe_generate_report,
    read_last_report_at,
    render_report_markdown,
    write_last_report_at,
)
from hachi.core.session_store import SessionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> SessionStore:
    """Return a fresh SessionStore backed by a temp SQLite file."""
    db = tmp_path / "test_sessions.db"
    return SessionStore(db_path=str(db))


def _insert_rows(
    store: SessionStore,
    *,
    session_id: str,
    n_up: int = 2,
    n_down: int = 1,
    n_unrated: int = 1,
    n_errored: int = 0,
) -> None:
    """Insert a mix of rated/unrated/errored interactions into *store*."""
    for i in range(n_up):
        store.log_interaction(
            session_id=session_id,
            turn_id=f"t-up-{i}",
            user_input=f"up question {i}",
            agent_output="great answer",
            tool_calls=["search"],
            model_used="claude-haiku",
            token_cost=0.001,
            tokens=100,
            rating="up",
        )
    for i in range(n_down):
        store.log_interaction(
            session_id=session_id,
            turn_id=f"t-down-{i}",
            user_input=f"bad question {i}",
            agent_output="wrong answer",
            tool_calls=["read_file", "search"],
            model_used="claude-haiku",
            token_cost=0.002,
            tokens=200,
            rating="down",
            notes="regression",
        )
    for i in range(n_unrated):
        store.log_interaction(
            session_id=session_id,
            turn_id=f"t-unrated-{i}",
            user_input=f"meh question {i}",
            agent_output="fine",
            model_used="claude-opus",
            token_cost=0.005,
            tokens=500,
            rating=None,
        )
    for i in range(n_errored):
        store.log_interaction(
            session_id=session_id,
            turn_id=f"t-err-{i}",
            user_input=f"error question {i}",
            agent_output="[error] something went wrong",
            model_used="claude-haiku",
            token_cost=0.001,
            tokens=50,
            rating=None,
        )


# ---------------------------------------------------------------------------
# render_report_markdown
# ---------------------------------------------------------------------------


class TestRenderReportMarkdown:
    def test_empty_report_contains_no_rows_message(self) -> None:
        report = EvalReport()
        md = render_report_markdown(report)
        assert "No interaction rows found" in md

    def test_totals_appear_in_output(self) -> None:
        report = EvalReport(
            total_turns=42,
            rated_up=30,
            rated_down=5,
            unrated=7,
            failure_rate=5 / 35,
            errored_turns=3,
            total_cost=0.1234,
            avg_cost_per_turn=0.00294,
        )
        md = render_report_markdown(report)
        assert "42" in md
        assert "30" in md
        assert "5" in md
        assert "7" in md
        assert "$0.1234" in md
        # Failure rate expressed as %
        assert "14.3%" in md

    def test_per_model_section_present(self) -> None:
        report = EvalReport(
            total_turns=10,
            per_model={"claude-haiku": PerModelStats(count=8, total_cost=0.008, down_count=1)},
        )
        md = render_report_markdown(report)
        assert "Per-model breakdown" in md
        assert "claude-haiku" in md
        assert "8" in md

    def test_top_failing_tools_section(self) -> None:
        report = EvalReport(
            total_turns=5,
            rated_down=2,
            top_failing_tools=[("search", 3), ("read_file", 1)],
        )
        md = render_report_markdown(report)
        assert "Top tools in down-rated turns" in md
        assert "search" in md
        assert "read_file" in md

    def test_recent_failures_section(self) -> None:
        rf = RecentFailure(
            id="abc123",
            session_id="sess001",
            ts="2026-06-20T10:00:00",
            user_input="what is 2+2?",
            agent_output_head="[error] math failed",
            tool_calls=["calculator"],
            notes="flaky",
        )
        report = EvalReport(total_turns=1, rated_down=1, recent_failures=[rf])
        md = render_report_markdown(report)
        assert "Recent failures" in md
        assert "what is 2+2?" in md
        assert "calculator" in md

    def test_since_filter_shown_in_title(self) -> None:
        report = EvalReport(since="2026-06-01")
        md = render_report_markdown(report)
        assert "2026-06-01" in md

    def test_markdown_starts_with_h1(self) -> None:
        md = render_report_markdown(EvalReport())
        assert md.startswith("# Hachi Weekly Failure Report")


# ---------------------------------------------------------------------------
# generate_failure_report_artifact
# ---------------------------------------------------------------------------


class TestGenerateFailureReportArtifact:
    def test_files_are_created(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        sid = store.start_session()
        _insert_rows(store, session_id=sid, n_up=3, n_down=1)

        out_dir = tmp_path / "reports"
        artifact = generate_failure_report_artifact(store, out_dir=out_dir)

        assert artifact.markdown_path.exists()
        assert artifact.json_path.exists()

    def test_json_is_parseable(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        sid = store.start_session()
        _insert_rows(store, session_id=sid, n_up=2, n_down=2)

        out_dir = tmp_path / "reports"
        artifact = generate_failure_report_artifact(store, out_dir=out_dir)

        data = json.loads(artifact.json_path.read_text(encoding="utf-8"))
        assert "total_turns" in data
        assert "failure_rate" in data
        assert isinstance(data["top_failing_tools"], list)

    def test_aggregates_match(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        sid = store.start_session()
        _insert_rows(store, session_id=sid, n_up=3, n_down=1, n_unrated=1, n_errored=1)

        out_dir = tmp_path / "reports"
        artifact = generate_failure_report_artifact(store, out_dir=out_dir)
        r = artifact.report

        assert r.total_turns == 6  # 3up + 1down + 1unrated + 1errored
        assert r.rated_up == 3
        assert r.rated_down == 1
        assert r.unrated == 2  # unrated + errored (both have rating=None)
        # failure_rate = 1 / (3+1) = 0.25
        assert abs(r.failure_rate - 0.25) < 1e-9

    def test_out_dir_created_automatically(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        out_dir = tmp_path / "deep" / "nested" / "reports"
        generate_failure_report_artifact(store, out_dir=out_dir)
        assert out_dir.exists()

    def test_injected_now_controls_filename_stamp(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        fixed = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)
        artifact = generate_failure_report_artifact(
            store, out_dir=tmp_path / "r", now=fixed
        )
        assert "20260624-120000" in artifact.markdown_path.name
        assert "20260624-120000" in artifact.json_path.name

    def test_empty_store_still_writes_files(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        out_dir = tmp_path / "reports"
        artifact = generate_failure_report_artifact(store, out_dir=out_dir)
        assert artifact.report.total_turns == 0
        assert artifact.markdown_path.exists()
        assert artifact.json_path.exists()

    def test_top_failing_tools_serialised_as_lists_not_tuples(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        sid = store.start_session()
        _insert_rows(store, session_id=sid, n_down=2)

        out_dir = tmp_path / "reports"
        artifact = generate_failure_report_artifact(store, out_dir=out_dir)

        data = json.loads(artifact.json_path.read_text(encoding="utf-8"))
        for entry in data["top_failing_tools"]:
            assert isinstance(entry, list), "each tool entry must be a list (not a tuple)"


# ---------------------------------------------------------------------------
# due_for_report
# ---------------------------------------------------------------------------


class TestDueForReport:
    def test_none_last_run_is_always_due(self) -> None:
        now = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)
        assert due_for_report(None, now, interval_seconds=604800) is True

    def test_exactly_at_interval_is_due(self) -> None:
        last = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)
        now = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)  # exactly 7 days
        assert due_for_report(last, now, interval_seconds=604800) is True

    def test_just_under_interval_is_not_due(self) -> None:
        last = datetime(2026, 6, 17, 12, 0, 1, tzinfo=UTC)
        now = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)  # 1s short
        assert due_for_report(last, now, interval_seconds=604800) is False

    def test_well_over_interval_is_due(self) -> None:
        last = datetime(2026, 1, 1, tzinfo=UTC)
        now = datetime(2026, 6, 24, tzinfo=UTC)
        assert due_for_report(last, now, interval_seconds=604800) is True

    def test_same_time_with_zero_interval_is_due(self) -> None:
        t = datetime(2026, 6, 24, tzinfo=UTC)
        assert due_for_report(t, t, interval_seconds=0) is True

    def test_naive_datetimes_work(self) -> None:
        last = datetime(2026, 6, 17, 12, 0, 0)
        now = datetime(2026, 6, 24, 12, 0, 0)
        assert due_for_report(last, now, interval_seconds=604800) is True


# ---------------------------------------------------------------------------
# Marker helpers
# ---------------------------------------------------------------------------


class TestMarkerHelpers:
    def test_round_trip(self, tmp_path: Path) -> None:
        marker = tmp_path / ".last_report.json"
        when = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)
        write_last_report_at(marker, when)
        result = read_last_report_at(marker)
        assert result is not None
        # Both strip tzinfo for comparison to avoid offset-tz vs UTC ambiguity
        assert result.replace(tzinfo=None) == when.replace(tzinfo=None)

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        marker = tmp_path / "no_such_file.json"
        assert read_last_report_at(marker) is None

    def test_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        marker = tmp_path / ".corrupt.json"
        marker.write_text("not json{{{", encoding="utf-8")
        assert read_last_report_at(marker) is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        marker = tmp_path / ".empty.json"
        marker.write_text("", encoding="utf-8")
        assert read_last_report_at(marker) is None

    def test_missing_key_returns_none(self, tmp_path: Path) -> None:
        marker = tmp_path / ".bad_key.json"
        marker.write_text(json.dumps({"other_key": "2026-06-24T12:00:00"}), encoding="utf-8")
        assert read_last_report_at(marker) is None

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        marker = tmp_path / "deep" / "dir" / ".last_report.json"
        write_last_report_at(marker, datetime(2026, 6, 24, tzinfo=UTC))
        assert marker.exists()

    def test_atomic_write_is_idempotent(self, tmp_path: Path) -> None:
        marker = tmp_path / ".last_report.json"
        t1 = datetime(2026, 6, 24, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 6, 24, 11, 0, 0, tzinfo=UTC)
        write_last_report_at(marker, t1)
        write_last_report_at(marker, t2)
        result = read_last_report_at(marker)
        assert result is not None
        assert result.replace(tzinfo=None) == t2.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# maybe_generate_report
# ---------------------------------------------------------------------------


class TestMaybeGenerateReport:
    def test_first_call_generates_report(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        sid = store.start_session()
        _insert_rows(store, session_id=sid, n_up=2, n_down=1)

        out_dir = tmp_path / "reports"
        marker_path = out_dir / ".last_report.json"
        emitted: list[tuple[str, dict]] = []

        artifact = maybe_generate_report(
            store,
            out_dir=out_dir,
            marker_path=marker_path,
            interval_seconds=604800,
            limit=1000,
            emit=lambda name, payload: emitted.append((name, payload)),
        )

        assert artifact is not None
        assert artifact.markdown_path.exists()
        assert artifact.json_path.exists()

    def test_first_call_emits_event(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        out_dir = tmp_path / "reports"
        marker_path = out_dir / ".last_report.json"
        emitted: list[tuple[str, dict]] = []

        maybe_generate_report(
            store,
            out_dir=out_dir,
            marker_path=marker_path,
            interval_seconds=604800,
            limit=1000,
            emit=lambda name, payload: emitted.append((name, payload)),
        )

        assert len(emitted) == 1
        event_name, payload = emitted[0]
        assert event_name == "eval.report.generated"
        assert "markdown_path" in payload
        assert "json_path" in payload
        assert "total_turns" in payload
        assert "failure_rate" in payload
        assert "generated_at" in payload

    def test_second_immediate_call_returns_none_and_does_not_emit(
        self, tmp_path: Path
    ) -> None:
        store = _make_store(tmp_path)
        out_dir = tmp_path / "reports"
        marker_path = out_dir / ".last_report.json"
        emitted: list[tuple[str, dict]] = []
        emit = lambda name, payload: emitted.append((name, payload))  # noqa: E731

        # First call — due (no marker)
        fixed_now = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)
        maybe_generate_report(
            store,
            out_dir=out_dir,
            marker_path=marker_path,
            interval_seconds=604800,
            limit=1000,
            emit=emit,
            now=fixed_now,
        )
        assert len(emitted) == 1

        # Second call at same time — not yet due
        result = maybe_generate_report(
            store,
            out_dir=out_dir,
            marker_path=marker_path,
            interval_seconds=604800,
            limit=1000,
            emit=emit,
            now=fixed_now,
        )
        assert result is None
        assert len(emitted) == 1  # no second emit

    def test_no_emit_arg_is_safe(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        out_dir = tmp_path / "reports"
        marker_path = out_dir / ".last_report.json"
        # Should not raise even without emit
        artifact = maybe_generate_report(
            store,
            out_dir=out_dir,
            marker_path=marker_path,
            interval_seconds=604800,
            limit=1000,
            emit=None,
        )
        assert artifact is not None

    def test_marker_written_after_generation(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        out_dir = tmp_path / "reports"
        marker_path = out_dir / ".last_report.json"
        fixed_now = datetime(2026, 6, 24, 15, 0, 0, tzinfo=UTC)

        maybe_generate_report(
            store,
            out_dir=out_dir,
            marker_path=marker_path,
            interval_seconds=604800,
            limit=1000,
            now=fixed_now,
        )

        last = read_last_report_at(marker_path)
        assert last is not None
        assert last.replace(tzinfo=None) == fixed_now.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# CLI — hachi eval snapshot
# ---------------------------------------------------------------------------


class TestEvalSnapshotCLI:
    def test_exit_zero_and_prints_path(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from hachi.cli.commands.eval import eval_app

        db_path = tmp_path / "test.db"
        test_store = SessionStore(db_path=str(db_path))

        runner = CliRunner()
        with patch("hachi.cli.commands.eval._open_store", return_value=test_store):
            result = runner.invoke(
                eval_app,
                ["snapshot", "--out", str(tmp_path / "snap_out")],
            )

        assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"
        assert "Snapshot written" in result.output

    def test_writes_md_file(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from hachi.cli.commands.eval import eval_app

        db_path = tmp_path / "test.db"
        test_store = SessionStore(db_path=str(db_path))
        out_dir = tmp_path / "snap_out"

        runner = CliRunner()
        with patch("hachi.cli.commands.eval._open_store", return_value=test_store):
            runner.invoke(eval_app, ["snapshot", "--out", str(out_dir)])

        md_files = list(out_dir.glob("eval-report-*.md"))
        assert len(md_files) == 1

    def test_writes_json_file(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from hachi.cli.commands.eval import eval_app

        db_path = tmp_path / "test.db"
        test_store = SessionStore(db_path=str(db_path))
        out_dir = tmp_path / "snap_out"

        runner = CliRunner()
        with patch("hachi.cli.commands.eval._open_store", return_value=test_store):
            runner.invoke(eval_app, ["snapshot", "--out", str(out_dir)])

        json_files = list(out_dir.glob("eval-report-*.json"))
        assert len(json_files) == 1
        # Verify parseable
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "total_turns" in data

    def test_marker_file_written(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from hachi.cli.commands.eval import eval_app

        db_path = tmp_path / "test.db"
        test_store = SessionStore(db_path=str(db_path))
        out_dir = tmp_path / "snap_out"

        runner = CliRunner()
        with patch("hachi.cli.commands.eval._open_store", return_value=test_store):
            runner.invoke(eval_app, ["snapshot", "--out", str(out_dir)])

        marker = out_dir / ".last_report.json"
        assert marker.exists()
        last = read_last_report_at(marker)
        assert last is not None

    def test_output_mentions_turns_and_failure_rate(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from hachi.cli.commands.eval import eval_app

        db_path = tmp_path / "test.db"
        test_store = SessionStore(db_path=str(db_path))

        runner = CliRunner()
        with patch("hachi.cli.commands.eval._open_store", return_value=test_store):
            result = runner.invoke(
                eval_app, ["snapshot", "--out", str(tmp_path / "out")]
            )

        assert "turns=" in result.output
        assert "failure_rate=" in result.output
