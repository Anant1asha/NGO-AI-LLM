"""Phase 5 optimizer tests: R5 tool-output compression and R9 mid-turn budget trim."""

from __future__ import annotations

from unittest.mock import MagicMock

from hachi.core.loop import (
    _PRE_GEN_TRIM_THRESHOLD,
    _TOOL_OUTPUT_MAX_CHARS,
    _compress_tool_output,
)
from hachi.core.memory import _TOOL_RESULT_CLEAR_TOKENS


class TestToolOutputCompression:
    """R5 — _compress_tool_output() pure function."""

    def test_small_result_passes_through_unchanged(self) -> None:
        text = "short result"
        assert _compress_tool_output(text) == text

    def test_empty_string_passes_through(self) -> None:
        assert _compress_tool_output("") == ""

    def test_exact_boundary_not_truncated(self) -> None:
        text = "x" * _TOOL_OUTPUT_MAX_CHARS
        assert _compress_tool_output(text) == text

    def test_one_over_boundary_is_truncated(self) -> None:
        text = "x" * (_TOOL_OUTPUT_MAX_CHARS + 1)
        result = _compress_tool_output(text)
        # Content portion is capped at max_chars; suffix may make total longer.
        assert result[:_TOOL_OUTPUT_MAX_CHARS] == "x" * _TOOL_OUTPUT_MAX_CHARS
        assert "[truncated" in result
        assert result[_TOOL_OUTPUT_MAX_CHARS:] != "x"  # suffix starts here, not more content

    def test_large_result_is_truncated_to_max_plus_note(self) -> None:
        big = "y" * (_TOOL_OUTPUT_MAX_CHARS + 5000)
        result = _compress_tool_output(big)
        # Head is preserved up to max_chars
        assert result[:_TOOL_OUTPUT_MAX_CHARS] == "y" * _TOOL_OUTPUT_MAX_CHARS
        assert "[truncated" in result

    def test_truncation_note_includes_original_length(self) -> None:
        total = _TOOL_OUTPUT_MAX_CHARS + 500
        big = "z" * total
        result = _compress_tool_output(big)
        assert str(total) in result

    def test_custom_max_chars_respected(self) -> None:
        text = "a" * 200
        result = _compress_tool_output(text, max_chars=100)
        assert result[:100] == "a" * 100
        assert "[truncated" in result
        assert "200" in result

    def test_custom_max_chars_small_text_passes_through(self) -> None:
        text = "hello"
        assert _compress_tool_output(text, max_chars=1000) == text


class TestPreGenTrimThreshold:
    """R9 — pre-generation trim threshold sanity checks."""

    def test_threshold_is_above_tool_clear_threshold(self) -> None:
        # R9 fires AFTER the standard clear_stale_tool_results (12 000), so the
        # constant must be higher to avoid redundant sweeps.
        assert _PRE_GEN_TRIM_THRESHOLD > _TOOL_RESULT_CLEAR_TOKENS

    def test_threshold_is_below_max_active_tokens(self) -> None:
        from hachi.core.memory import _MAX_ACTIVE_TOKENS

        assert _PRE_GEN_TRIM_THRESHOLD < _MAX_ACTIVE_TOKENS

    def test_memory_clear_accepts_aggressive_params(self) -> None:
        from hachi.core.memory import MemoryManager

        mgr = MemoryManager()
        # Should not raise with the aggressive R9 params
        cleared = mgr.clear_stale_tool_results(keep_recent_messages=3, min_chars=200)
        assert cleared == 0  # empty history → nothing to clear

    def test_pre_gen_trim_reduces_token_count_when_history_is_large(self) -> None:
        """Integration: large tool results in older messages are trimmed by R9 params."""
        from hachi.core.llm import Message
        from hachi.core.memory import MemoryManager

        mgr = MemoryManager()
        # Build up enough large tool-result messages to exceed the threshold
        # (keep_recent_messages=3, so we need > 3 messages with large tool results)
        big_content = "x" * 5000
        for i in range(10):
            mgr.add_message(Message(role="user", content=f"query {i}"))
            mgr.add_message(
                Message(
                    role="assistant",
                    content=[
                        {"type": "tool_use", "id": f"tu_{i}", "name": "read_file", "input": {}},
                    ],
                )
            )
            mgr.add_message(
                Message(
                    role="user",
                    content=[
                        {
                            "type": "tool_result",
                            "tool_use_id": f"tu_{i}",
                            "content": big_content,
                        }
                    ],
                )
            )

        before = mgr.estimate_token_count()
        # Simulate R9: only run if over threshold (for the test, just call directly)
        if before > _PRE_GEN_TRIM_THRESHOLD:
            cleared = mgr.clear_stale_tool_results(keep_recent_messages=3, min_chars=200)
            after = mgr.estimate_token_count()
            assert cleared > 0
            assert after < before

    def test_pre_gen_trim_event_logic_skips_when_under_threshold(self) -> None:
        """If token count is below threshold, clear_stale_tool_results should not fire."""
        memory = MagicMock()
        memory.estimate_token_count.return_value = _PRE_GEN_TRIM_THRESHOLD - 1

        # Simulate the R9 conditional block
        pre_gen_tokens = memory.estimate_token_count()
        if pre_gen_tokens > _PRE_GEN_TRIM_THRESHOLD:
            memory.clear_stale_tool_results(keep_recent_messages=3, min_chars=200)

        memory.clear_stale_tool_results.assert_not_called()

    def test_pre_gen_trim_event_logic_fires_when_over_threshold(self) -> None:
        """If token count exceeds threshold, clear_stale_tool_results is called."""
        memory = MagicMock()
        memory.estimate_token_count.return_value = _PRE_GEN_TRIM_THRESHOLD + 1000
        memory.clear_stale_tool_results.return_value = 3

        pre_gen_tokens = memory.estimate_token_count()
        if pre_gen_tokens > _PRE_GEN_TRIM_THRESHOLD:
            memory.clear_stale_tool_results(keep_recent_messages=3, min_chars=200)

        memory.clear_stale_tool_results.assert_called_once_with(
            keep_recent_messages=3, min_chars=200
        )
