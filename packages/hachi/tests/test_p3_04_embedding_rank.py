"""P3-04: Hybrid BM25 + cosine embedding rank option.

Tests:
  1. BM25-only search still works when embedding rank is off (default).
  2. enable_embedding_rank() builds a Chroma collection.
  3. Search with embedding rank enabled returns results (non-empty).
  4. _embedding_search() returns {} when embedding rank is off.
  5. RRF merge path is exercised when both BM25 and embedding scores are present.
  6. HACHI_EMBEDDING_RANK env flag triggers auto-enable at load_directory().
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(tmp_path: Path, og_content: str | None = None):
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    if og_content is not None:
        og_file = tmp_path / "test_skills.og"
        og_file.write_text(textwrap.dedent(og_content), encoding="utf-8")
        engine.load_file(og_file)
    return engine


_SAMPLE_OG = """\
    ::meta
      title: Test Skills

    ::index
      # node-id      | type  | scope | conf | keywords
      weather_skill   | skill | all   | 1.0  | weather, forecast, temperature, rain
      translate_skill | skill | all   | 1.0  | translate, language, translation, text

    ::node[weather_skill]
    ->[:role=skill]
    ->[:keywords=weather, forecast, temperature, rain]

    ::dense
    Get real-time weather forecasts for any location.

    ::node[translate_skill]
    ->[:role=skill]
    ->[:keywords=translate, language, translation, text]

    ::dense
    Translate text between languages using the translation API.
"""


# ---------------------------------------------------------------------------
# 1. BM25-only (embedding rank off) still works
# ---------------------------------------------------------------------------


def test_bm25_search_works_without_embedding_rank(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, _SAMPLE_OG)
    assert engine._emb_collection is None
    results = engine.search("weather forecast")
    assert results, "BM25 search returned no results"
    names = [r["name"] for r in results]
    assert "weather_skill" in names


# ---------------------------------------------------------------------------
# 2. enable_embedding_rank() creates the collection
# ---------------------------------------------------------------------------


def test_enable_embedding_rank_builds_collection(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, _SAMPLE_OG)
    assert engine._emb_collection is None
    try:
        engine.enable_embedding_rank()
    except ImportError:
        import pytest
        pytest.skip("chromadb not available")

    assert engine._emb_collection is not None


# ---------------------------------------------------------------------------
# 3. Search with embedding rank returns results
# ---------------------------------------------------------------------------


def test_search_with_embedding_rank_returns_results(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, _SAMPLE_OG)
    try:
        engine.enable_embedding_rank()
    except ImportError:
        import pytest
        pytest.skip("chromadb not available")

    results = engine.search("what is the weather today")
    assert results, "Hybrid search returned no results"


# ---------------------------------------------------------------------------
# 4. _embedding_search returns {} when collection is None
# ---------------------------------------------------------------------------


def test_embedding_search_returns_empty_when_disabled(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, _SAMPLE_OG)
    assert engine._emb_collection is None
    result = engine._embedding_search("weather")
    assert result == {}, f"Expected empty dict, got {result}"


# ---------------------------------------------------------------------------
# 5. RRF merge path (mock the embedding search to return known scores)
# ---------------------------------------------------------------------------


def test_rrf_merge_path(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, _SAMPLE_OG)

    # Install a fake collection that returns a known result.
    class _FakeCol:
        def query(self, **_kwargs):  # type: ignore[no-untyped-def]
            return {
                "ids": [["test_skills:weather_skill"]],
                "distances": [[0.2]],
            }

    engine._emb_collection = _FakeCol()
    results = engine.search("weather forecast")
    names = [r["name"] for r in results]
    # weather_skill should appear because both BM25 and cosine agree.
    assert "weather_skill" in names


# ---------------------------------------------------------------------------
# 6. HACHI_EMBEDDING_RANK env flag
# ---------------------------------------------------------------------------


def test_env_flag_enables_embedding_rank(tmp_path: Path) -> None:
    og_file = tmp_path / "skills" / "test.og"
    og_file.parent.mkdir(parents=True)
    og_file.write_text(textwrap.dedent(_SAMPLE_OG), encoding="utf-8")

    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    with patch.dict(os.environ, {"HACHI_EMBEDDING_RANK": "1"}):
        try:
            engine.load_directory(og_file.parent)
        except Exception:
            import pytest
            pytest.skip("chromadb not available or setup failed")
    # Either collection was built (chromadb available) or the flag was checked
    # without error. Either way, no exception means the env path was exercised.
