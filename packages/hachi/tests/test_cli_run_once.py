"""Tests for `hachi run --once` — the non-interactive one-shot CLI mode.

Regression guard for the doc-vs-CLI drift where the cookbook documented
`hachi run --once "<task>"` and `echo … | hachi run --once` (the whole
"Run a one-shot task from the CLI" recipe) but the flag did not exist — the
command errored with ``No such option: --once`` and there was no one-shot code
path anywhere in the CLI. This locks the implemented behaviour:

  * ``hachi run --once "<task>"`` boots an agent, runs one turn, prints the reply
  * ``echo "<task>" | hachi run --once`` reads the prompt from stdin
  * a bare positional prompt (``hachi run "<task>"``) also runs one-shot
  * empty one-shot input exits non-zero with a helpful message (no agent boot)
  * a boot/chat failure exits 1 and still shuts the agent down
  * only the reply reaches stdout (no interactive boot banner) so it pipes cleanly
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


def _fake_agent(reply: str = "one-shot reply") -> MagicMock:
    agent = MagicMock()
    agent.chat.return_value = reply
    agent.shutdown.return_value = None
    return agent


def test_run_once_arg_runs_single_turn() -> None:
    agent = _fake_agent(reply="42 files changed")
    with patch("hachi.cli.main.boot_agent", return_value=agent) as boot:
        result = runner.invoke(app, ["run", "--once", "how many files changed?"])

    assert result.exit_code == 0, result.output
    assert "42 files changed" in result.output
    boot.assert_called_once()
    agent.chat.assert_called_once_with("how many files changed?")
    agent.shutdown.assert_called_once()


def test_run_once_reads_stdin_when_no_arg() -> None:
    agent = _fake_agent(reply="stdin answer")
    with patch("hachi.cli.main.boot_agent", return_value=agent):
        result = runner.invoke(app, ["run", "--once"], input="summarise the changelog\n")

    assert result.exit_code == 0, result.output
    assert "stdin answer" in result.output
    agent.chat.assert_called_once_with("summarise the changelog")


def test_positional_prompt_implies_one_shot() -> None:
    agent = _fake_agent(reply="pos answer")
    with patch("hachi.cli.main.boot_agent", return_value=agent):
        result = runner.invoke(app, ["run", "do the thing"])

    assert result.exit_code == 0, result.output
    assert "pos answer" in result.output
    agent.chat.assert_called_once_with("do the thing")


def test_run_once_empty_input_exits_2_without_booting() -> None:
    # --once with no argument and empty stdin → helpful error, and we must NOT
    # boot an agent (nothing to ask it).
    with patch("hachi.cli.main.boot_agent") as boot:
        result = runner.invoke(app, ["run", "--once"], input="")

    assert result.exit_code == 2, result.output
    boot.assert_not_called()
    assert "one-shot" in result.output.lower() or "prompt" in result.output.lower()


def test_run_once_agent_error_exits_1_and_shuts_down() -> None:
    agent = MagicMock()
    agent.chat.side_effect = RuntimeError("LLM unavailable")
    agent.shutdown.return_value = None
    with patch("hachi.cli.main.boot_agent", return_value=agent):
        result = runner.invoke(app, ["run", "--once", "hello"])

    assert result.exit_code == 1
    assert "LLM unavailable" in result.output
    # Even on a chat error the agent must be shut down cleanly.
    agent.shutdown.assert_called_once()


def test_run_once_boot_failure_exits_1() -> None:
    with patch("hachi.cli.main.boot_agent", side_effect=RuntimeError("no api key")):
        result = runner.invoke(app, ["run", "--once", "hello"])

    assert result.exit_code == 1
    lowered = result.output.lower()
    assert "no api key" in lowered or "failed to boot" in lowered


def test_run_once_stdout_is_only_the_reply() -> None:
    agent = _fake_agent(reply="clean output")
    with patch("hachi.cli.main.boot_agent", return_value=agent):
        result = runner.invoke(app, ["run", "--once", "hi"])

    assert result.exit_code == 0
    assert "clean output" in result.output
    # The interactive boot banner must NOT appear in one-shot mode.
    assert "Hachi is online" not in result.output
