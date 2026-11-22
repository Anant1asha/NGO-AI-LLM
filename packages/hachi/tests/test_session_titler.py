"""Tests for session title generation (core.session_titler).

Covers:
  1. fallback_title — first non-empty line, whitespace-collapsed, length-capped
  2. generate_title — uses the LLM client, cleans its output
  3. generate_title — falls back deterministically when no client / on error
  4. _clean_title — strips wrapping quotes and trailing punctuation
"""

from __future__ import annotations

from hachi.core.session_titler import (
    MAX_TITLE_CHARS,
    UNTITLED,
    _clean_title,
    fallback_title,
    generate_title,
)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeClient:
    """Minimal stand-in for a BaseLLMClient that returns a canned title."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict] = []

    def generate(self, messages, system_prompt=None, tools=None, dynamic_system=None):
        self.calls.append({"messages": messages, "system_prompt": system_prompt})
        return _FakeResponse(self._content)


class _BrokenClient:
    def generate(self, *args, **kwargs):
        raise RuntimeError("provider exploded")


# ---------------------------------------------------------------------------
# 1. fallback_title
# ---------------------------------------------------------------------------


def test_fallback_uses_first_nonempty_line() -> None:
    assert fallback_title("\n\n  Fix the login bug  \nmore text") == "Fix the login bug"


def test_fallback_collapses_whitespace() -> None:
    assert fallback_title("hello     world\ttab") == "hello world tab"


def test_fallback_empty_is_untitled() -> None:
    assert fallback_title("") == UNTITLED
    assert fallback_title("   \n  ") == UNTITLED


def test_fallback_truncates_long_input() -> None:
    title = fallback_title("x" * 200)
    assert len(title) <= MAX_TITLE_CHARS
    assert title.endswith("…")


# ---------------------------------------------------------------------------
# 2. generate_title with a working client
# ---------------------------------------------------------------------------


def test_generate_uses_client_output() -> None:
    client = _FakeClient("Fix Failing Login Tests")
    title = generate_title("the login tests are red", "I'll look", llm_client=client)
    assert title == "Fix Failing Login Tests"
    assert len(client.calls) == 1
    # Both turns are fed to the model.
    prompt = client.calls[0]["messages"][0].content
    assert "the login tests are red" in prompt
    assert "I'll look" in prompt


def test_generate_cleans_quotes_and_punctuation_from_model() -> None:
    client = _FakeClient('"Plan The Q3 Budget."')
    assert generate_title("help me plan q3 budget", llm_client=client) == "Plan The Q3 Budget"


def test_generate_blank_model_output_falls_back() -> None:
    client = _FakeClient("   ")
    assert generate_title("Deploy the staging server", llm_client=client) == (
        "Deploy the staging server"
    )


# ---------------------------------------------------------------------------
# 3. fallbacks: no client / empty input / client error
# ---------------------------------------------------------------------------


def test_generate_no_client_uses_fallback() -> None:
    assert generate_title("Refactor the parser", llm_client=None) == "Refactor the parser"


def test_generate_empty_input_is_untitled() -> None:
    assert generate_title("", llm_client=_FakeClient("ignored")) == UNTITLED


def test_generate_client_error_falls_back() -> None:
    assert generate_title("Write release notes", llm_client=_BrokenClient()) == (
        "Write release notes"
    )


# ---------------------------------------------------------------------------
# 4. _clean_title
# ---------------------------------------------------------------------------


def test_clean_title_strips_wrapping_quotes() -> None:
    assert _clean_title("'Hello World'") == "Hello World"
    assert _clean_title('"Hello World"') == "Hello World"


def test_clean_title_strips_trailing_punctuation() -> None:
    assert _clean_title("Hello World!!!") == "Hello World"


def test_clean_title_takes_first_line() -> None:
    assert _clean_title("\nTitle Here\nexplanation blah") == "Title Here"


def test_clean_title_empty_returns_empty() -> None:
    assert _clean_title("") == ""
    assert _clean_title("   ") == ""
