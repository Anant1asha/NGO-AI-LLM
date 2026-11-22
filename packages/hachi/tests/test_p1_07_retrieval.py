"""Tests for P1-07: BM25 retrieval regression suite.

Verifies that the BM25 + stopword-guarded tokenization achieves P@5 ≥ 0.8
against the shipped default skill library, and that the tokenizer correctly
filters stopwords while preserving meaningful terms.

Probe queries cover a representative cross-section of skill domains to catch
regressions when new skills are added or keywords change.
"""

from __future__ import annotations

import pytest

from hachi.core.skill_packs import _default_skills_root
from hachi.og_engine.engine import SkillEngine, _tokenize

# ---------------------------------------------------------------------------
# Tokenizer unit tests
# ---------------------------------------------------------------------------

def test_tokenize_removes_stopwords() -> None:
    tokens = _tokenize("how do I translate text to French")
    assert "how" not in tokens
    assert "do" not in tokens
    assert "to" not in tokens
    assert "translate" in tokens
    assert "text" in tokens
    assert "french" in tokens


def test_tokenize_lowercases_and_strips_punctuation() -> None:
    tokens = _tokenize("GitHub Pull-Request CI/CD")
    assert "github" in tokens
    assert "pull" in tokens
    assert "request" in tokens
    assert "ci" in tokens
    assert "cd" in tokens
    # No original-case tokens
    assert "GitHub" not in tokens
    assert "Pull-Request" not in tokens


def test_tokenize_empty_string() -> None:
    assert _tokenize("") == []


def test_tokenize_all_stopwords() -> None:
    """A query of only stopwords returns empty list — caller should handle gracefully."""
    assert _tokenize("the a an is are") == []


def test_tokenize_preserves_skill_relevant_terms() -> None:
    tokens = _tokenize("weather forecast temperature")
    assert "weather" in tokens
    assert "forecast" in tokens
    assert "temperature" in tokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shipped_engine() -> SkillEngine:
    """Load the shipped default skills once per test module."""
    eng = SkillEngine()
    eng.load_directory(_default_skills_root())
    return eng


def _top5_names(engine: SkillEngine, query: str) -> set[str]:
    return {r["name"] for r in engine.search(query)[:5]}


# ---------------------------------------------------------------------------
# P@5 probe regression suite
# ---------------------------------------------------------------------------

# Each probe: (query, [expected skill names — at least one must be in top-5])
_PROBES = [
    ("currency exchange", ["core_currency"]),
    ("weather forecast", ["core_weather"]),
    ("translate text", ["core_translator"]),
    ("github pull request", ["core_github"]),
    ("slack standup", ["daily_standup"]),
    ("qr code generate", ["core_qr_creator"]),
    ("flight status", ["core_flight_radar"]),
    ("math calculation", ["core_math_engine"]),
    ("notion project", ["project_kickoff", "notion_brain_dump"]),
    ("email inbox", ["inbox_sentinel", "morning_briefing"]),
    ("dictionary lookup", ["core_dictionary"]),
    ("financial data", ["core_finance"]),
    ("network diagnostics", ["core_network"]),
    # Prefix-stemming probe: "deployment" should hit skills with "deploy" keyword
    ("deployment", ["core_github"]),
    # Multi-word natural language probe
    ("check the weather in London", ["core_weather"]),
    ("send a standup to Slack", ["daily_standup"]),
]

# Minimum hits to pass the suite
_P_AT_5_THRESHOLD = 0.80


def test_p_at_5_meets_threshold(shipped_engine: SkillEngine) -> None:
    """P@5 over all probe queries must be ≥ 0.80."""
    hits = 0
    misses = []
    for query, expected in _PROBES:
        top5 = _top5_names(shipped_engine, query)
        if any(e in top5 for e in expected):
            hits += 1
        else:
            misses.append(f"MISS: {query!r} → top5={sorted(top5)}, expected one of {expected}")

    p_at_5 = hits / len(_PROBES)
    assert p_at_5 >= _P_AT_5_THRESHOLD, (
        f"P@5 = {p_at_5:.2f} < {_P_AT_5_THRESHOLD} threshold.\n"
        + "\n".join(misses)
    )


# Individual smoke tests for critical queries (fast to run, easy to debug)
def test_search_currency(shipped_engine: SkillEngine) -> None:
    assert "core_currency" in _top5_names(shipped_engine, "currency exchange")


def test_search_weather(shipped_engine: SkillEngine) -> None:
    assert "core_weather" in _top5_names(shipped_engine, "weather forecast")


def test_search_github(shipped_engine: SkillEngine) -> None:
    assert "core_github" in _top5_names(shipped_engine, "github pull request")


def test_search_standup(shipped_engine: SkillEngine) -> None:
    assert "daily_standup" in _top5_names(shipped_engine, "slack standup")


def test_search_no_match_returns_empty(shipped_engine: SkillEngine) -> None:
    assert shipped_engine.search("zzzznotarealkeyword") == []


def test_search_only_stopwords_returns_empty(shipped_engine: SkillEngine) -> None:
    """Query consisting entirely of stopwords must return empty, not error."""
    assert shipped_engine.search("how do i the a an") == []


def test_search_ranking_most_relevant_first(shipped_engine: SkillEngine) -> None:
    """The most on-target skill should rank in the top 3 for a precise query."""
    results = shipped_engine.search("currency convert exchange rate")
    top3 = [r["name"] for r in results[:3]]
    assert "core_currency" in top3, f"core_currency not in top 3: {top3}"


def test_search_results_have_required_fields(shipped_engine: SkillEngine) -> None:
    """Each result dict must contain name, role, keywords, source_file."""
    results = shipped_engine.search("weather")
    assert results, "Expected at least one result for 'weather'"
    for r in results:
        assert "name" in r
        assert "role" in r
        assert "keywords" in r
        assert "source_file" in r
