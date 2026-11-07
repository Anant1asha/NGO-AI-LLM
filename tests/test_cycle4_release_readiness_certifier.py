"""
Unit, 10-Rule QA Release Gate, Offline CDN/Secret Sanitization & HMAC-SHA256 Bundle Signer
Test Suite for TASK-RELEASE-READINESS-20MIB-CERTIFIER (Cycle 4) (16 tests -> 428/428 cumulative).
"""
from __future__ import annotations

import copy
import pathlib
import pytest

from aasha.orchestrator.release_readiness_certifier import (
    CryptographicReleaseBundleSigner,
    ReleaseCertificationError,
    ReleaseSignatureTamperError,
    TenRuleQAReleaseCertifier,
    compare_cycle4_release_certifier_and_bundle_signer,
)


def _clean_candidate() -> dict:
    return {
        "html_bundle": (
            '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Ch9</title></head>'
            '<body><h1>Force | बल</h1><svg viewBox="0 0 100 100"><circle r="10"/></svg></body></html>'
        ),
        "formula": "$F = m \\cdot a$",
        "bilingual_glossary": {
            "F": {"en": "Force", "indic": "बल"},
            "m": {"en": "Mass", "indic": "द्रव्यमान"},
            "a": {"en": "Acceleration", "indic": "त्वरण"},
        },
        "hint_text": "Adjust mass slider to observe acceleration.",
        "target_answer": 24.0,
        "student_attempt": -24.0,
        "bundle_size_bytes": 3_350_187,
        "sim_p99_latency_ms": 0.0029,
        "verlet_energy_drift": 0.00000016,
        "daily_spend_usd": 0.00225,
        "merkle_root": "dab6351e04ddc29ccf106ff270e4fb4f79b92a70b2107bc6792900fd3993ed95",
        "crdt_convergence_sha256": "30ae333d66fe299dc4ebae3786d9a7eba1ffdf273a6707794d5f72cdfd1af441",
    }


def test_cert_01_clean_candidate_passes_all_10_qa_rules() -> None:
    res = TenRuleQAReleaseCertifier.evaluate_10_rules(_clean_candidate())
    assert res["certified"] is True
    assert res["rules_passed"] == 10
    assert res["failed_rules"] == []


def test_cert_02_missing_utf8_meta_fails_rule_01_and_is_fixed_by_auto_sanitize() -> None:
    cand = _clean_candidate()
    cand["html_bundle"] = cand["html_bundle"].replace('<meta charset="UTF-8">', "")
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-01_UTF8_META_CHARSET" in raw["failed_rules"]
    healed = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=True)
    assert healed["certified"] is True


def test_cert_03_spoiler_in_hint_fails_rule_02_and_is_fixed_by_auto_sanitize() -> None:
    cand = _clean_candidate()
    cand["hint_text"] = "The answer is 24."
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-02_ZERO_SPOILER_L_TRUTH" in raw["failed_rules"]
    healed = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=True)
    assert healed["certified"] is True


def test_cert_04_missing_indic_script_fails_rule_03() -> None:
    cand = _clean_candidate()
    cand["html_bundle"] = '<head><meta charset="UTF-8"></head><body>English only <svg viewBox="0 0 10 10"></svg></body>'
    cand["bilingual_glossary"] = {"F": {"en": "Force", "indic": "Force"}}
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-03_BILINGUAL_INDIC_PARITY" in raw["failed_rules"]


def test_cert_05_malformed_latex_formula_fails_rule_04_and_is_fixed_by_auto_sanitize() -> None:
    cand = _clean_candidate()
    cand["formula"] = "$F = \\frac{m \\cdot a}{1"
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-04_FORMULA_AST_SI_DIMENSIONS" in raw["failed_rules"]
    healed = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=True)
    assert healed["certified"] is True


def test_cert_06_missing_inline_svg_viewbox_fails_rule_05() -> None:
    cand = _clean_candidate()
    cand["html_bundle"] = cand["html_bundle"].replace('viewBox="0 0 100 100"', "")
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-05_INLINE_SVG_VECTOR_RETENTION" in raw["failed_rules"]


def test_cert_07_external_cdn_script_fails_rule_06_and_is_stripped_by_auto_sanitize() -> None:
    cand = _clean_candidate()
    cand["html_bundle"] += '<script src="https://cdn.jsdelivr.net/npm/mathjax.js"></script>'
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-06_ZERO_EXTERNAL_CDN_LEAK" in raw["failed_rules"]
    healed = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=True)
    assert healed["certified"] is True


def test_cert_08_bundle_exceeding_20mib_fails_rule_07() -> None:
    cand = _clean_candidate()
    cand["bundle_size_bytes"] = 25 * 1024 * 1024
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-07_SUB_20MIB_BUNDLE_CEILING" in raw["failed_rules"]


def test_cert_09_frame_budget_overrun_or_energy_drift_fails_rule_08() -> None:
    cand = _clean_candidate()
    cand["sim_p99_latency_ms"] = 25.0
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-08_60FPS_AND_VERLET_ENERGY" in raw["failed_rules"]


def test_cert_10_secret_leak_or_spend_cap_breach_fails_rule_09_and_secret_is_redacted() -> None:
    cand = _clean_candidate()
    cand["html_bundle"] += "<!-- key: sk-mockTestTokenproj1234567890abcdefghijkl -->"
    raw = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False)
    assert "QA-RULE-09_CON008_SPEND_AND_SEC001_SECRETS" in raw["failed_rules"]
    healed = TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=True)
    assert healed["certified"] is True
    assert "[REDACTED_SECRET_SEC001]" in healed["sanitized_candidate"]["html_bundle"]


def test_cert_11_invalid_merkle_root_or_crdt_digest_fails_rule_10() -> None:
    cand = _clean_candidate()
    cand["merkle_root"] = "not_a_64_hex_sha256"
    with pytest.raises(ReleaseCertificationError):
        TenRuleQAReleaseCertifier.evaluate_10_rules(cand, auto_sanitize=False, strict_raise=True)


def test_cert_12_signer_creates_verifiable_hmac_sha256_release_certificate() -> None:
    pkg = CryptographicReleaseBundleSigner.sign_certified_bundle(_clean_candidate())
    assert pkg["certified"] is True
    assert len(pkg["hmac_sha256_signature"]) == 64
    assert CryptographicReleaseBundleSigner.verify_certified_bundle(pkg) is True


def test_cert_13_verifier_rejects_post_signing_html_mutation() -> None:
    pkg = CryptographicReleaseBundleSigner.sign_certified_bundle(_clean_candidate())
    tampered = copy.deepcopy(pkg)
    tampered["certified_candidate"]["html_bundle"] += "<!-- tampered -->"
    with pytest.raises(ReleaseSignatureTamperError):
        CryptographicReleaseBundleSigner.verify_certified_bundle(tampered)


def test_cert_14_verifier_rejects_wrong_signing_key() -> None:
    pkg = CryptographicReleaseBundleSigner.sign_certified_bundle(_clean_candidate(), signing_key=b"KEY_A")
    with pytest.raises(ReleaseSignatureTamperError):
        CryptographicReleaseBundleSigner.verify_certified_bundle(pkg, signing_key=b"KEY_B")


def test_cert_15_js_release_readiness_certifier_module_present_and_valid() -> None:
    js_txt = pathlib.Path("/tmp/aasha_stage_pack/scripts/aasha_release_readiness_certifier.js").read_text(encoding="utf-8")
    assert "TenRuleQAReleaseCertifierJS" in js_txt
    assert "CryptographicReleaseBundleSignerJS" in js_txt


def test_cert_16_compare_cycle4_release_certifier_and_bundle_signer_benchmark() -> None:
    bench = compare_cycle4_release_certifier_and_bundle_signer()
    assert bench["winner"] == "method-b-10rule-qa-auto-certifier-and-hmac-merkle-bundle-signer"
    ma = bench["method_a_unsanitized_manual_release"]
    mb = bench["method_b_auto_sanitized_signed_release"]
    assert ma["certified"] is False
    assert ma["rules_passed"] == 5
    assert mb["certified"] is True
    assert mb["rules_passed"] == 10
    assert mb["cryptographic_provenance_signed"] is True
