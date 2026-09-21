"""Step 1 tests — every STEP 1 test in one file.

"Given a call — REPAIR, NO_REPAIR, or ESCALATE — say if it was right."

The single test file for STEP 1: every part (disposition matching,
validation checking, routing logic, the judge agent, and the final
score_decision wrapper) is gathered here instead of spread across several
files, and tested against the same three cases the answer keys were
built for.
"""
import json
from pathlib import Path

import pytest
from adii.evaluation.judge import build_judge_prompt, judge_repair, parse_judge_reply
from adii.evaluation.scoring import (
    decide_route,
    score_decision,
    score_disposition,
    score_repair_validation,
)

# The keys live with the evaluation authority — test_answer_keys_stay_out confines them
# there. These two are development keys for the walkthrough, whose truth is public; no
# unseen key is in the repository (evaluation/fixtures/README.md).
HERE = Path(__file__).resolve().parents[3] / "02_src" / "adii" / "evaluation" / "fixtures"

if not (HERE / "demo-learning-001.answer.json").exists():
    pytest.skip(
        "blind answer keys not present — added post-freeze, kept out of the repo "
        "so the system under evaluation can never read them (see eval_authority "
        "OVERVIEW.md)",
        allow_module_level=True,
    )


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def key_001():
    return load("demo-learning-001.answer.json")


@pytest.fixture(scope="module")
def key_drill():
    return load("demo-learning-002-mismatch-drill.answer.json")


def fake_model_provider(prompt: str) -> str:
    """Stands in for a real model call — no API key exists yet, same
    principle as ADII's own fake provider for the investigator loop."""
    if "amount_cents / 100" in prompt and "/ 100.0) * 100" not in prompt:
        return "correct — single conversion preserved, satisfies repair_must_satisfy."
    return "incorrect — the patch does not satisfy repair_must_satisfy."


def real_judge(decision, validation, answer_key):
    return judge_repair(decision, validation, answer_key, fake_model_provider)


# ---------------------------------------------------------------------------
# 1a. Disposition matching — the first, smallest question.
# ---------------------------------------------------------------------------

class TestDispositionMatching:
    def test_correct_disposition_passes(self, key_001):
        assert score_disposition("REPAIR", key_001) == "correct"

    def test_wrong_disposition_fails(self, key_001):
        assert score_disposition("NO_REPAIR", key_001) == "incorrect"
        assert score_disposition("ESCALATE", key_001) == "incorrect"


# ---------------------------------------------------------------------------
# 1b. Repair validation gating — a REPAIR only counts if independently accepted.
# ---------------------------------------------------------------------------

class TestRepairValidationGate:
    def test_non_repair_dispositions_skip_this_check(self):
        assert score_repair_validation("NO_REPAIR", None) == "correct"
        assert score_repair_validation("ESCALATE", None) == "correct"

    def test_repair_missing_a_validation_result_is_incorrect(self):
        assert score_repair_validation("REPAIR", None) == "incorrect"

    def test_accepted_repair_passes(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        assert (
            score_repair_validation(case["decision"]["disposition"], case["validation"])
            == "correct"
        )

    def test_rejected_repair_fails_despite_correct_root_cause(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]
        assert (
            score_repair_validation(case["decision"]["disposition"], case["validation"])
            == "incorrect"
        )


# ---------------------------------------------------------------------------
# 1c. Routing — deciding correct / incorrect / needs_judge_review.
# ---------------------------------------------------------------------------

class TestRouting:
    def test_wrong_disposition_settles_immediately(self, key_001):
        assert decide_route({"disposition": "NO_REPAIR"}, None, key_001) == "incorrect"

    def test_rejected_validation_settles_immediately(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]
        assert decide_route(case["decision"], case["validation"], key_drill) == "incorrect"

    def test_exact_repair_id_match_settles_without_a_judge(self, key_001):
        decision = {
            "disposition": "REPAIR",
            "root_cause_id": key_001["correct_root_cause_id"],
            "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
        }
        assert decide_route(decision, {"accepted": True}, key_001) == "correct"

    def test_different_repair_id_needs_the_judge(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        assert decide_route(case["decision"], case["validation"], key_drill) == "needs_judge_review"


# ---------------------------------------------------------------------------
# 1d. The judge agent — settles the cases the deterministic scorer can't.
# ---------------------------------------------------------------------------

class TestJudgeAgent:
    def test_prompt_carries_both_the_reference_and_the_actual_repair(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        prompt = build_judge_prompt(case["decision"], case["validation"], key_drill)
        assert key_drill["repair_must_satisfy"]["reference_repair_id"] in prompt
        assert case["decision"]["repair_id"] in prompt

    def test_prompt_puts_the_answer_key_itself_out_of_scope(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]
        prompt = build_judge_prompt(case["decision"], case["validation"], key_drill)
        assert "outside your scope" in prompt

    @pytest.mark.parametrize(
        "reply,expected",
        [("correct — fine.", "correct"), ("Incorrect: nope.", "incorrect")],
    )
    def test_reply_parsing_reads_the_leading_verdict(self, reply, expected):
        verdict, reasoning = parse_judge_reply(reply)
        assert verdict == expected
        assert reasoning

    def test_reply_with_no_verdict_is_rejected_not_guessed(self):
        with pytest.raises(ValueError):
            parse_judge_reply("hard to say.")

    def test_judge_approves_the_plausible_alternative(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        result = judge_repair(case["decision"], case["validation"], key_drill, fake_model_provider)
        assert result["verdict"] == "correct"

    def test_judge_rejects_the_real_error(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]
        result = judge_repair(case["decision"], case["validation"], key_drill, fake_model_provider)
        assert result["verdict"] == "incorrect"


# ---------------------------------------------------------------------------
# 1e. score_decision — the whole step, wired together.
# ---------------------------------------------------------------------------

class TestScoreDecisionWholeStep:
    def test_exact_match_is_settled_deterministically_and_never_calls_the_judge(self, key_001):
        decision = {
            "disposition": "REPAIR",
            "root_cause_id": key_001["correct_root_cause_id"],
            "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
        }
        validation = {"accepted": True}

        def judge_that_must_not_run(decision, validation, answer_key):
            raise AssertionError("an exact match must never reach the judge")

        result = score_decision(decision, validation, key_001, judge=judge_that_must_not_run)
        assert result == {"verdict": "correct", "settled_by": "deterministic"}

    def test_rejected_validation_is_also_settled_without_the_judge(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]

        def judge_that_must_not_run(decision, validation, answer_key):
            raise AssertionError("a rejected validation must settle before the judge is asked")

        result = score_decision(
            case["decision"], case["validation"], key_drill, judge=judge_that_must_not_run
        )
        assert result["verdict"] == "incorrect"
        assert result["settled_by"] == "deterministic"

    def test_ambiguous_case_is_deferred_to_the_judge_and_carries_its_reasoning(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        result = score_decision(case["decision"], case["validation"], key_drill, judge=real_judge)
        assert result["verdict"] == "correct"
        assert result["settled_by"] == "judge"
        assert result["reasoning"]

    def test_ambiguous_case_with_no_judge_wired_is_reported_unresolved_not_guessed(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        result = score_decision(case["decision"], case["validation"], key_drill, judge=None)
        assert result == {"verdict": "unresolved", "settled_by": "none"}


# ---------------------------------------------------------------------------
# 1f. Acceptance: the exact claim STEP 1 makes, all three cases at once.
# ---------------------------------------------------------------------------

def test_step1_acceptance_all_three_cases_get_the_right_final_verdict(key_001, key_drill):
    """This is the sentence on the journey map, made executable:
    given a call, say if it was right — for a match, a rejected repair,
    and a genuine ambiguous alternative, all in one assertion block.
    """
    exact_match_decision = {
        "disposition": "REPAIR",
        "root_cause_id": key_001["correct_root_cause_id"],
        "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
    }
    exact_match_validation = {"accepted": True}

    plausible = key_drill["test_fixtures"]["case_plausible_alternative"]
    real_error = key_drill["test_fixtures"]["case_real_error"]

    results = {
        "exact_match": score_decision(
            exact_match_decision, exact_match_validation, key_001, judge=real_judge
        ),
        "plausible_alternative": score_decision(
            plausible["decision"], plausible["validation"], key_drill, judge=real_judge
        ),
        "real_error": score_decision(
            real_error["decision"], real_error["validation"], key_drill, judge=real_judge
        ),
    }

    assert results["exact_match"]["verdict"] == "correct"
    assert results["plausible_alternative"]["verdict"] == "correct"
    assert results["real_error"]["verdict"] == "incorrect"
