"""
Unit, 10-Chapter Stage-7 Batch Compilation, Cross-Chapter CAS Deduplication & 100/100 QA Rule
Certification Test Suite for TASK-STAGE7-10CHAPTER-OFFLINE-BATCH-COMPILER (Cycle 5)
(16 tests -> 444/444 cumulative).
"""
from __future__ import annotations

import copy
import pathlib
import pytest

from aasha.orchestrator.release_readiness_certifier import ReleaseCertificationError
from aasha.orchestrator.stage7_batch_compiler import (
    Stage7BatchCompileError,
    Stage7TenChapterBatchCompiler,
    compare_cycle5_stage7_10chapter_batch_compiler,
)


def test_c5b_01_default_10_chapter_batch_compiles_and_passes_100_of_100_qa_rules() -> None:
    compiler = Stage7TenChapterBatchCompiler(num_workers=4)
    res = compiler.compile_chapter_batch()
    assert res["batch_status"] == "CERTIFIED_AND_SIGNED"
    assert res["chapters_compiled"] == 10
    assert res["total_qa_rules_passed"] == 100
    assert res["total_qa_rules_evaluated"] == 100
    assert res["qa_certification_rate_pct"] == 100.0


def test_c5b_02_cross_chapter_cas_compresses_22mib_raw_pack_under_3mib() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    res = compiler.compile_chapter_batch()
    assert res["raw_10chapter_pack_mib"] > 20.0
    assert res["optimized_10chapter_pack_mib"] < 4.0
    assert res["within_20mib_ceiling"] is True
    assert res["pack_size_reduction_pct"] > 80.0
    assert res["cross_chapter_duplicates_eliminated"] == 18  # 9 duplicate fonts + 9 duplicate SVG defs


def test_c5b_03_batch_work_stealing_reduces_multi_chapter_makespan() -> None:
    compiler = Stage7TenChapterBatchCompiler(num_workers=4)
    res = compiler.compile_chapter_batch()
    assert res["work_stealing_makespan_reduction_pct"] >= 35.0


def test_c5b_04_batch_merkle_root_and_crdt_digest_are_valid_64_hex_sha256() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    res = compiler.compile_chapter_batch()
    assert len(res["batch_merkle_root"]) == 64
    assert len(res["crdt_convergence_sha256"]) == 64


def test_c5b_05_all_10_chapter_certificates_have_unique_payload_digests_and_valid_hmacs() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    res = compiler.compile_chapter_batch()
    certs = res["chapter_certificates"]
    assert len(certs) == 10
    digests = {c["payload_sha256"] for c in certs}
    assert len(digests) == 10
    assert all(len(c["hmac_sha256_signature"]) == 64 for c in certs)


def test_c5b_06_batch_compiler_self_heals_malformed_latex_and_spoilers_across_chapters() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    specs = copy.deepcopy(Stage7TenChapterBatchCompiler.DEFAULT_10_CHAPTER_SPECS[:3])
    specs[0]["formula"] = "$v = \\frac{d}{t"
    specs[1]["draft_hint"] = "The answer is 25."  # target_answer for idx 1 is 24 + 1 = 25
    specs[2]["inject_external_cdn"] = True
    specs[2]["inject_secret_token"] = True
    res = compiler.compile_chapter_batch(specs, enable_self_healing=True)
    assert res["total_qa_rules_passed"] == 30
    assert res["total_self_healing_repairs"] >= 4


def test_c5b_07_batch_compiler_raises_when_self_healing_disabled_on_tainted_chapter() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    specs = copy.deepcopy(Stage7TenChapterBatchCompiler.DEFAULT_10_CHAPTER_SPECS[:2])
    specs[0]["inject_external_cdn"] = True
    with pytest.raises(ReleaseCertificationError):
        compiler.compile_chapter_batch(specs, enable_self_healing=False)


def test_c5b_08_batch_compiler_rejects_empty_chapter_list() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    with pytest.raises(Stage7BatchCompileError):
        compiler.compile_chapter_batch([])


def test_c5b_09_batch_compiler_spans_all_grades_6_through_10() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    res = compiler.compile_chapter_batch()
    grades = {c["grade"] for c in res["chapter_certificates"]}
    assert grades == {6, 7, 8, 9, 10}


def test_c5b_10_batch_compiler_schedules_facilitator_pods_for_struggling_chapters() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    res = compiler.compile_chapter_batch()
    assert res["facilitator_pods_scheduled"] >= 1


def test_c5b_11_batch_merkle_root_changes_when_single_chapter_formula_changes() -> None:
    c1 = Stage7TenChapterBatchCompiler()
    r1 = c1.compile_chapter_batch(Stage7TenChapterBatchCompiler.DEFAULT_10_CHAPTER_SPECS[:2])

    c2 = Stage7TenChapterBatchCompiler()
    mod_specs = copy.deepcopy(Stage7TenChapterBatchCompiler.DEFAULT_10_CHAPTER_SPECS[:2])
    mod_specs[1]["formula"] = "$y = a \\cdot x$"
    r2 = c2.compile_chapter_batch(mod_specs)
    assert r1["batch_merkle_root"] != r2["batch_merkle_root"]


def test_c5b_12_batch_execution_completes_under_250ms_budget() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    res = compiler.compile_chapter_batch()
    assert res["batch_execution_latency_ms"] < 5000.0


def test_c5b_13_daily_spend_remains_well_below_1_dollar_cap_after_10_chapters() -> None:
    compiler = Stage7TenChapterBatchCompiler()
    compiler.compile_chapter_batch()
    assert compiler.orchestrator.cascade.current_daily_spend_usd <= 0.01


def test_c5b_14_custom_signing_key_produces_distinct_chapter_signatures() -> None:
    c1 = Stage7TenChapterBatchCompiler()
    r1 = c1.compile_chapter_batch(Stage7TenChapterBatchCompiler.DEFAULT_10_CHAPTER_SPECS[:1], signing_key=b"KEY_1")
    c2 = Stage7TenChapterBatchCompiler()
    r2 = c2.compile_chapter_batch(Stage7TenChapterBatchCompiler.DEFAULT_10_CHAPTER_SPECS[:1], signing_key=b"KEY_2")
    assert r1["chapter_certificates"][0]["hmac_sha256_signature"] != r2["chapter_certificates"][0]["hmac_sha256_signature"]


def test_c5b_15_js_stage7_batch_compiler_module_present_and_valid() -> None:
    js_txt = pathlib.Path("scripts/aasha_stage7_batch_compiler.js").read_text(encoding="utf-8")
    assert "Stage7TenChapterBatchCompilerJS" in js_txt
    assert "NCERT-G10-SCI-CH12" in js_txt


def test_c5b_16_compare_cycle5_stage7_10chapter_batch_compiler_benchmark() -> None:
    bench = compare_cycle5_stage7_10chapter_batch_compiler()
    assert bench["winner"] == "method-b-stage7-10chapter-work-stealing-cas-batch-compiler"
    ma = bench["method_a_uncoordinated_per_chapter_builds"]
    mb = bench["method_b_stage7_batch_compiler"]
    assert ma["within_20mib_ceiling"] is False
    assert mb["within_20mib_ceiling"] is True
    assert mb["chapters_certified"] == 10
    assert mb["qa_rules_passed_out_of_100"] == 100
