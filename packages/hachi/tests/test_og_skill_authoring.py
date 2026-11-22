"""Tests for autonomous skill authoring (SkillEngine.upsert_skill).

Proves the agent can persist a new .og skill, that it is hot-loaded and usable
immediately, that oversized dense blocks are rejected, that re-saving refines
(changelog + version), and that names can't escape the skills directory.
"""

from __future__ import annotations

from pathlib import Path

from hachi.og_engine.engine import DENSE_TOKEN_BUDGET, SkillEngine
from hachi.og_engine.parser import parse_og_file


def _engine(tmp_path: Path) -> SkillEngine:
    engine = SkillEngine()
    engine.load_directory(tmp_path)  # sets _skills_dir, indexes nothing
    return engine


def test_create_writes_loads_and_indexes(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    result = engine.upsert_skill(
        name="Rotate API Keys",
        keywords=["rotate", "api keys", "vault"],
        dense="rotate|api keys|vault|zero-downtime",
        full="Stage the new key before retiring the old one.",
        steps=["Generate new key.", "Deploy.", "Retire old key."],
        reason="learned during incident",
    )

    assert result["status"] == "created"
    assert result["name"] == "rotate_api_keys"
    path = Path(result["path"])
    assert path.exists()
    assert path.parent == tmp_path / "learned"

    # The written file is valid ObjectGraph.
    parse_og_file(str(path))

    # Hot-loaded: immediately searchable and loadable in the same session.
    assert "rotate_api_keys" in {r["name"] for r in engine.search("rotate")}
    loaded = engine.resolve_node("rotate_api_keys")
    assert "Stage the new key" in loaded


def test_oversized_dense_is_rejected(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    bloated = "This is a long winded dense block written as full prose sentences " * 5
    result = engine.upsert_skill(
        name="bad_skill",
        keywords=["bad"],
        dense=bloated,
    )

    assert result["status"] == "rejected"
    assert result["dense_tokens"] > DENSE_TOKEN_BUDGET
    # Nothing was written.
    assert not (tmp_path / "learned" / "bad_skill.og").exists()
    assert engine.get_node("bad_skill") is None


def test_resave_refines_with_changelog_and_version_bump(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.upsert_skill(name="deploy_thing", keywords=["deploy"], dense="deploy|thing", reason="v1")
    second = engine.upsert_skill(
        name="deploy_thing",
        keywords=["deploy", "ship"],
        dense="deploy|thing|ship",
        reason="added rollback",
    )

    assert second["status"] == "updated"
    assert second["version"] == "1.0.1"

    reparsed = parse_og_file(second["path"])
    actions = [e.action for e in reparsed.changelog]
    assert actions == ["added", "updated"]
    assert reparsed.meta.version == "1.0.1"


def test_well_formed_skill_has_no_lint_advisories(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    result = engine.upsert_skill(
        name="Rotate API Keys",
        keywords=["rotate", "api keys"],
        dense="rotate|api keys|vault",
        full="Stage the new key before retiring the old one.",
        steps=["Generate new key.", "Retire old key."],
    )
    assert result["status"] == "created"
    # Searchable + has Pass-3 content -> nothing to advise.
    assert "lint_advisories" not in result


def test_save_surfaces_lint_advisories_for_thin_skill(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    # No keywords (unsearchable) and no Pass-3 content (empty) -> advisory feedback,
    # but still saved (advisories are not rejections).
    result = engine.upsert_skill(
        name="thin_skill",
        keywords=[],
        dense="thin|skill",
    )
    assert result["status"] == "created"
    advisories = result.get("lint_advisories", [])
    joined = " ".join(advisories)
    assert "no-keywords" in joined
    assert "empty-node" in joined
    # The skill is still written and loadable despite the advisories.
    assert engine.get_node("thin_skill") is not None


def test_name_cannot_escape_skills_dir(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    result = engine.upsert_skill(
        name="../../etc/passwd",
        keywords=["evil"],
        dense="evil|payload",
    )
    path = Path(result["path"])
    assert result["name"] == "etc_passwd"
    assert path.parent == tmp_path / "learned"  # stayed inside the learned dir
    assert ".." not in path.parts


def test_lint_errors_reject_the_write(tmp_path: Path) -> None:
    """A skill whose ::dense block is empty trips a lint ERROR ("missing-dense" for a
    skill-role node) and must never be committed to disk — the whole 3-pass model
    depends on every skill having a routable dense block. Regression for M2: lint
    previously ran only *after* the write and only surfaced warnings/info, so a
    lint-invalid skill would land on disk and be hot-loaded anyway.
    """
    engine = _engine(tmp_path)
    result = engine.upsert_skill(
        name="silent skill",
        keywords=["silent"],
        dense="",  # empty dense passes the token-budget check (0 <= 30) but fails lint
        full="Some Pass-3 content.",
    )

    assert result["status"] == "rejected"
    assert not (tmp_path / "learned" / "silent_skill.og").exists()
    assert "silent_skill" not in {r["name"] for r in engine.search("silent")}
