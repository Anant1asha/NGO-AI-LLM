"""
Unit Tests for Phase G: Chunk G22 (Autonomous Offline Rural Solar Cold-Storage & Post-Harvest
Physics Lab, Vernacular Community Radio Lesson Compiler & 25,000,000-Learner Perpetual Sovereign Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g22_solar_cold_storage_and_radio_compiler import (
    OfflineSolarColdStoragePostHarvestPhysicsLab,
    TwentyFiveMillionLearnerPerpetualSovereignSeal,
    VernacularCommunityRadioLessonCompiler,
    execute_chunk_g22_solar_cold_storage_and_radio_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g22_01_offline_solar_cold_storage_post_harvest_physics_lab() -> None:
    lab = OfflineSolarColdStoragePostHarvestPhysicsLab()
    results = lab.run_cold_storage_labs()
    assert len(results) == 3
    assert round(sum(r.temp_drop_c for r in results) / len(results), 4) == 21.6667
    assert sum(r.shelf_life_extension_days for r in results) == 48
    assert sum(r.seva_cooling_credits for r in results) == 690
    assert all(r.zero_pii_verified for r in results)


def test_g22_02_vernacular_community_radio_lesson_compiler() -> None:
    episodes = VernacularCommunityRadioLessonCompiler.compile_radio_episodes()
    assert len(episodes) == 3
    assert sum(e.socratic_pauses_count for e in episodes) == 16
    assert sum(e.estimated_household_listeners for e in episodes) == 33000
    assert all(e.zero_pii_verified for e in episodes)


def test_g22_03_twenty_five_million_learner_seal_and_html5_qa() -> None:
    seal = TwentyFiveMillionLearnerPerpetualSovereignSeal(REPO_ROOT)
    summary = seal.execute_chunk_g22_cold_storage_and_radio_cycle()
    assert summary["chunk_id"] == "G22"
    assert summary["twenty_five_million_learner_sovereign_seal"]["learners_certified"] == 25000000
    assert summary["twenty_five_million_learner_sovereign_seal"]["completed_chunks_count"] == 40
    assert summary["cold_storage_radio_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["cold_storage_radio_html_bundle"]["under_20mib_ceiling"] is True


def test_g22_04_end_to_end_chunk_g22_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g22_solar_cold_storage_and_radio_sync(REPO_ROOT)
    assert summary["status"] == "G22_SOLAR_COLD_STORAGE_LAB_COMMUNITY_RADIO_AND_25M_LEARNER_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G23:")
