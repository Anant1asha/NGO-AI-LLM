"""
Unit, Contrastive Misconception Distractor Mapping, Degenerate Collision Resolution,
SHA-256 Answer-Key Hashing & 9-Script Phoneme Feedback Test Suite for
TASK-BILINGUAL-VOICE-CONTRASTIVE-QUIZ-GENERATOR (Cycle 6) (16 tests -> 476/476 cumulative).
"""
from __future__ import annotations

import hashlib
import pathlib
import pytest

from aasha.f27_sim.contrastive_quiz_synthesizer import (
    ContrastiveMisconceptionQuizSynthesizer,
    ContrastiveQuizSynthesisError,
    compare_cycle6_bilingual_contrastive_quiz_synthesizer,
)
from aasha.f27_sim.f27_sim_benchmark import LTruthAntiSpoilerVerifier


def test_c6q_01_synthesizes_4_distinct_options_with_3_misconception_tags() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-01", "$F = m \\cdot a$", 12.0, 4.0, "mul", "F", "N"
    )
    assert item["options_count"] == 4
    assert item["unique_numeric_values_count"] == 4
    assert item["misconception_tags_covered"] == [
        "OPERATOR_INVERSION_MUL_VS_DIV",
        "SIGN_INVERSION",
        "UNIT_SCALE_MISMATCH",
    ]


def test_c6q_02_resolves_degenerate_b_equals_1_collision_cleanly() -> None:
    # When operand_b == 1.0, a * b == a / b == 8.0; collision resolver must produce 4 unique numbers!
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-DEG-1", "$F = m \\cdot a$", 8.0, 1.0, "mul", "F", "N"
    )
    assert item["unique_numeric_values_count"] == 4


def test_c6q_03_resolves_degenerate_zero_target_collision_cleanly() -> None:
    # When operand_a == 0.0, target == 0.0 and -target == 0.0; collision resolver must produce 4 unique numbers!
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-DEG-0", "$F = m \\cdot a$", 0.0, 5.0, "mul", "F", "N"
    )
    assert item["unique_numeric_values_count"] == 4


def test_c6q_04_correct_option_hash_matches_sha256_of_winning_option() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-HASH", "$F = m \\cdot a$", 10.0, 5.0, "mul", "F", "N"
    )
    winning_opt = next(o for o in item["options"] if o["numeric_value"] == 50.0)
    expected_hash = hashlib.sha256(f"Q-HASH:{winning_opt['option_id']}".encode("utf-8")).hexdigest()
    assert item["correct_option_sha256"] == expected_hash


def test_c6q_05_dom_html_does_not_leak_plaintext_data_answer_attribute() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-DOM", "$F = m \\cdot a$", 6.0, 7.0, "mul", "F", "N"
    )
    assert "data-answer=" not in item["dom_html"]
    assert f'data-correct-sha256="{item["correct_option_sha256"]}"' in item["dom_html"]


def test_c6q_06_all_distractor_feedback_strings_are_100_percent_spoiler_free() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-SPOIL", "$F = m \\cdot a$", 9.0, 3.0, "mul", "F", "N"
    )
    assert item["all_feedback_spoiler_free"] is True
    for o in item["options"]:
        audit = LTruthAntiSpoilerVerifier.verify_payload(
            f"{o['feedback_en']} | {o['feedback_hi']}", target_answer="27"
        )
        assert audit["spoiler_free"] is True


def test_c6q_07_supports_division_addition_and_subtraction_operations() -> None:
    div_item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-DIV", "$v = \\frac{d}{t}$", 40.0, 8.0, "div", "v", "m/s"
    )
    add_item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-ADD", "$v = u + a \\cdot t$", 10.0, 15.0, "add", "v", "m/s"
    )
    sub_item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-SUB", "$y = a - b$", 25.0, 9.0, "sub", "y", "m"
    )
    assert div_item["unique_numeric_values_count"] == 4
    assert add_item["unique_numeric_values_count"] == 4
    assert sub_item["unique_numeric_values_count"] == 4


def test_c6q_08_phoneme_sync_tracks_achieve_zero_timing_drift_on_all_options() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-VTT", "$F = m \\cdot a$", 14.0, 2.0, "mul", "F", "N"
    )
    assert item["max_phoneme_timing_drift_ms"] == 0.0
    assert all(o["phoneme_cue_count"] >= 5 for o in item["options"])


def test_c6q_09_rejects_empty_question_id_or_unsupported_operation() -> None:
    with pytest.raises(ContrastiveQuizSynthesisError):
        ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item("", "$F = m \\cdot a$", 2.0, 3.0)
    with pytest.raises(ContrastiveQuizSynthesisError):
        ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item("Q1", "$F = m \\cdot a$", 2.0, 3.0, "pow")


def test_c6q_10_rejects_division_by_zero_or_non_finite_operands() -> None:
    with pytest.raises(ContrastiveQuizSynthesisError):
        ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item("Q1", "$v = \\frac{d}{t}$", 10.0, 0.0, "div")
    with pytest.raises(ContrastiveQuizSynthesisError):
        ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item("Q1", "$F = m \\cdot a$", float("nan"), 2.0)


def test_c6q_11_options_are_sorted_deterministically_by_numeric_value() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-SORT", "$F = m \\cdot a$", 12.0, 3.0, "mul", "F", "N"
    )
    vals = [o["numeric_value"] for o in item["options"]]
    assert vals == sorted(vals)


def test_c6q_12_each_distractor_contains_bilingual_english_and_hindi_socratic_prompts() -> None:
    item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
        "Q-BI", "$F = m \\cdot a$", 12.0, 3.0, "mul", "F", "N"
    )
    distractors = [o for o in item["options"] if o["misconception_tag"] != "CANONICAL_MASTERY"]
    assert len(distractors) == 3
    for d in distractors:
        assert "Counterfactual check:" in d["feedback_en"]
        assert "प्रति-तथ्यात्मक जाँच:" in d["feedback_hi"]


def test_c6q_13_validates_governing_formula_ast_before_synthesizing_options() -> None:
    from aasha.f27_sim.f27_sim_benchmark import FormulaASTValidationError
    with pytest.raises(FormulaASTValidationError):
        ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
            "Q-BAD-AST", "$F = \\frac{m}{0}$", 10.0, 2.0
        )


def test_c6q_14_supports_all_9_indic_scripts_in_prompt_narration() -> None:
    for idx, prompt in enumerate([
        "बल और त्वरण", "বল এবং ত্বরণ", "ਬਲ ਅਤੇ ਪ੍ਰਵੇਗ", "બળ અને પ્રવેગ", "ବଳ ଏବଂ ତ୍ୱରଣ",
        "விசை மற்றும் முடுக்கம்", "బలం మరియు త్వరణం", "ಬಲ ಮತ್ತು ವೇಗೋತ್ಕರ್ಷ", "ബലവും ത്വരണവും"
    ]):
        item = ContrastiveMisconceptionQuizSynthesizer.synthesize_diagnostic_item(
            f"Q-IND-{idx}", "$F = m \\cdot a$", 5.0 + idx, 2.0, "mul", "F", "N", prompt
        )
        assert item["max_phoneme_timing_drift_ms"] == 0.0


def test_c6q_15_js_contrastive_quiz_synthesizer_module_present_and_valid() -> None:
    js_txt = pathlib.Path("/tmp/aasha_stage_pack/scripts/aasha_contrastive_quiz_synthesizer.js").read_text(encoding="utf-8")
    assert "ContrastiveMisconceptionQuizSynthesizerJS" in js_txt
    assert "hashOptionKey" in js_txt


def test_c6q_16_compare_cycle6_bilingual_contrastive_quiz_synthesizer_benchmark() -> None:
    bench = compare_cycle6_bilingual_contrastive_quiz_synthesizer()
    assert bench["winner"] == "method-b-contrastive-misconception-quiz-and-phoneme-feedback-synthesizer"
    mb = bench["method_b_contrastive_misconception_quiz"]
    assert mb["items_generated"] == 9
    assert mb["degenerate_collision_free_rate_pct"] == 100.0
    assert mb["misconception_diagnostic_coverage_pct"] == 100.0
    assert mb["dom_answer_key_spoiler_free"] is True
    assert mb["max_phoneme_timing_drift_ms"] == 0.0
