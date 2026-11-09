"""
Unit Tests for Phase G: Chunk G10 (Multi-Modal Braille/Sign-Language Accessibility Compiler,
Offline Olympiad Challenge Generator & Perpetual 24/7 Self-Evolving Ecosystem Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g10_braille_sign_accessibility_and_olympiad_engine import (
    MultiModalBrailleSignAccessibilityCompiler,
    OfflineOlympiadChallengeGenerator,
    PerpetualSelfEvolvingEcosystemSeal,
    execute_chunk_g10_braille_sign_and_olympiad_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g10_01_bharati_braille_and_isl_compiler() -> None:
    pack = MultiModalBrailleSignAccessibilityCompiler.compile_accessibility_pack()
    assert len(pack) == 3
    assert all(d.wcag_aaa_contrast_ratio >= 7.0 for d in pack)
    assert all(d.zero_external_assets for d in pack)
    assert sum(d.isl_keyframe_count for d in pack) == 21
    assert any("⠋⠗⠁⠉⠞⠊⠕⠝" in d.bharati_braille_unicode for d in pack)


def test_g10_02_offline_olympiad_challenge_generator() -> None:
    gen = OfflineOlympiadChallengeGenerator()
    challenges = gen.generate_olympiad_challenges()
    assert len(challenges) == 3
    assert all(c.constructive_steps_required >= 3 for c in challenges)
    assert round(sum(c.difficulty_index for c in challenges) / len(challenges), 4) == 0.8833
    assert any(c.olympiad_tier == "OLYMPIAD_GOLD_READY" for c in challenges)


def test_g10_03_perpetual_ecosystem_seal_and_html5_qa() -> None:
    seal = PerpetualSelfEvolvingEcosystemSeal(REPO_ROOT)
    summary = seal.execute_chunk_g10_braille_sign_and_olympiad_cycle()
    assert summary["chunk_id"] == "G10"
    assert summary["perpetual_ecosystem_seal"]["completed_chunks_count"] == 28
    assert summary["braille_sign_olympiad_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["braille_sign_olympiad_html_bundle"]["under_20mib_ceiling"] is True


def test_g10_04_end_to_end_chunk_g10_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g10_braille_sign_and_olympiad_sync(REPO_ROOT)
    assert summary["status"] == "G10_MULTI_MODAL_BRAILLE_SIGN_ACCESSIBILITY_AND_OLYMPIAD_ENGINE_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G11:")
