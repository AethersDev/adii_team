"""Tests for outcome_classification.py — D-17 / D-19's six report categories.

Every row of the classification table is exercised once: for each
(actual disposition, correct disposition, validation outcome) combination
that can actually arise from scoring.decide_route, the resulting category
(and sub_kind where relevant) is pinned down explicitly.

Consistency check with the rest of eval_authority: this module calls
scoring.score_decision exactly once per classification and must never
duplicate or diverge from decide_route's own routing rules — several
tests below assert that by construction (same inputs into score_decision
directly vs. through classify_outcome must agree on the verdict).
"""
import pytest
from adii.evaluation.outcome_classification import CATEGORIES, FailureSubKind, classify_outcome
from adii.evaluation.scoring import score_decision

ANSWER_KEY_REPAIR = {
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "CAUSE_A",
    "repair_must_satisfy": {"reference_repair_id": "REPAIR_A"},
}
ANSWER_KEY_NO_REPAIR = {"correct_disposition": "NO_REPAIR"}
ANSWER_KEY_ESCALATE = {"correct_disposition": "ESCALATE", "correct_root_cause_id": None}


class TestSuccess:
    def test_repair_matching_everything_is_success(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}
        result = classify_outcome(decision, {"accepted": True}, ANSWER_KEY_REPAIR)
        assert result["category"] == "success"
        assert result["sub_kind"] is None

    def test_no_repair_matching_is_success(self):
        decision = {"disposition": "NO_REPAIR"}
        result = classify_outcome(decision, None, ANSWER_KEY_NO_REPAIR)
        assert result["category"] == "success"


class TestCorrectAbstention:
    def test_escalate_when_escalate_was_right_is_correct_abstention_not_plain_success(self):
        decision = {"disposition": "ESCALATE"}
        result = classify_outcome(decision, None, ANSWER_KEY_ESCALATE)
        assert result["category"] == "correct_abstention"
        assert result["sub_kind"] is None


class TestUnnecessaryEscalation:
    def test_escalate_when_repair_was_warranted_is_unnecessary_escalation(self):
        decision = {"disposition": "ESCALATE"}
        result = classify_outcome(decision, None, ANSWER_KEY_REPAIR)
        assert result["category"] == "unnecessary_escalation"

    def test_escalate_when_no_repair_was_warranted_is_unnecessary_escalation(self):
        decision = {"disposition": "ESCALATE"}
        result = classify_outcome(decision, None, ANSWER_KEY_NO_REPAIR)
        assert result["category"] == "unnecessary_escalation"


class TestFalseRepair:
    def test_repair_with_wrong_root_cause_rejected_by_judge_is_false_repair(self):
        # Diagnosis itself is wrong. decide_route routes a root_cause_id
        # mismatch to the judge (never auto-fails it, since a differently
        # -id'd root cause could still be semantically equivalent) — so
        # false_repair is reached once a judge actually rules it wrong,
        # not merely from the id mismatch alone.
        def judge_says_incorrect(decision, validation, answer_key):
            return {"verdict": "incorrect", "reasoning": "genuinely different, wrong cause"}

        decision = {
            "disposition": "REPAIR", "root_cause_id": "WRONG_CAUSE", "repair_id": "REPAIR_A"
        }
        result = classify_outcome(
            decision, {"accepted": True}, ANSWER_KEY_REPAIR, judge=judge_says_incorrect
        )
        assert result["category"] == "false_repair"
        assert result["sub_kind"] is None

    def test_wrong_root_cause_with_no_judge_available_is_unresolved_not_false_repair(self):
        # Without a judge to confirm the root cause is genuinely wrong
        # (versus a harmless id/summary mismatch), this must not be
        # guessed as false_repair — it is exactly the UNRESOLVED shape.
        decision = {
            "disposition": "REPAIR", "root_cause_id": "WRONG_CAUSE", "repair_id": "REPAIR_A"
        }
        result = classify_outcome(decision, {"accepted": True}, ANSWER_KEY_REPAIR, judge=None)
        assert result["category"] == "failure"
        assert result["sub_kind"] == FailureSubKind.UNRESOLVED


class TestRepairRejection:
    def test_correct_root_cause_but_rejected_validation_is_repair_rejection(self):
        # Diagnosis right, patch wrong — validation caught it before
        # anything was applied. Less severe than false_repair.
        decision = {
            "disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "SOME_OTHER_REPAIR"
        }
        result = classify_outcome(decision, {"accepted": False}, ANSWER_KEY_REPAIR)
        assert result["category"] == "repair_rejection"
        assert result["sub_kind"] is None

    def test_correct_root_cause_no_validation_at_all_is_also_repair_rejection(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}
        result = classify_outcome(decision, None, ANSWER_KEY_REPAIR)
        assert result["category"] == "repair_rejection"


class TestFailureWithSubKinds:
    def test_missed_a_real_defect_is_failure_with_missed_defect_subkind(self):
        decision = {"disposition": "NO_REPAIR"}
        result = classify_outcome(decision, None, ANSWER_KEY_REPAIR)
        assert result["category"] == "failure"
        assert result["sub_kind"] == FailureSubKind.MISSED_DEFECT

    def test_unwarranted_repair_when_no_repair_was_correct_is_failure_with_subkind(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "X", "repair_id": "Y"}
        result = classify_outcome(decision, {"accepted": True}, ANSWER_KEY_NO_REPAIR)
        assert result["category"] == "failure"
        assert result["sub_kind"] == FailureSubKind.UNWARRANTED_REPAIR

    def test_unwarranted_repair_when_escalate_was_correct_is_failure_with_subkind(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "X", "repair_id": "Y"}
        result = classify_outcome(decision, {"accepted": True}, ANSWER_KEY_ESCALATE)
        assert result["category"] == "failure"
        assert result["sub_kind"] == FailureSubKind.UNWARRANTED_REPAIR

    def test_no_repair_when_escalate_was_correct_is_plain_failure_no_subkind(self):
        # NO_REPAIR wrong, correct call was ESCALATE (not REPAIR) — a real
        # miss, but not the "missed a defect" shape specifically.
        decision = {"disposition": "NO_REPAIR"}
        result = classify_outcome(decision, None, ANSWER_KEY_ESCALATE)
        assert result["category"] == "failure"
        assert result["sub_kind"] is None

    def test_needs_judge_review_with_no_judge_is_failure_with_unresolved_subkind(self):
        decision = {
            "disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "SOMETHING_ELSE"
        }
        result = classify_outcome(decision, {"accepted": True}, ANSWER_KEY_REPAIR, judge=None)
        assert result["category"] == "failure"
        assert result["sub_kind"] == FailureSubKind.UNRESOLVED
        assert result["verdict"] == "unresolved"


class TestJudgeRoutedCases:
    def test_judge_approving_an_alternative_repair_is_success(self):
        def judge_says_correct(decision, validation, answer_key):
            return {"verdict": "correct", "reasoning": "valid alternative"}

        decision = {
            "disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "SOMETHING_ELSE"
        }
        result = classify_outcome(
            decision, {"accepted": True}, ANSWER_KEY_REPAIR, judge=judge_says_correct
        )
        assert result["category"] == "success"

    def test_judge_rejecting_an_alternative_repair_is_repair_rejection(self):
        # Root cause matched (only repair_id differed) and the judge ruled
        # it does not satisfy repair_must_satisfy — same shape as an
        # outright rejected validation: right diagnosis, wrong fix.
        def judge_says_incorrect(decision, validation, answer_key):
            return {"verdict": "incorrect", "reasoning": "does not satisfy repair_must_satisfy"}

        decision = {
            "disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "SOMETHING_ELSE"
        }
        result = classify_outcome(
            decision, {"accepted": True}, ANSWER_KEY_REPAIR, judge=judge_says_incorrect
        )
        assert result["category"] == "repair_rejection"


class TestConsistencyWithScoreDecision:
    """classify_outcome must never disagree with score_decision on the
    underlying verdict — it only adds a label on top."""

    @pytest.mark.parametrize("decision,validation,answer_key", [
        (
            {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"},
            {"accepted": True},
            ANSWER_KEY_REPAIR,
        ),
        ({"disposition": "NO_REPAIR"}, None, ANSWER_KEY_REPAIR),
        ({"disposition": "ESCALATE"}, None, ANSWER_KEY_ESCALATE),
        (
            {"disposition": "REPAIR", "root_cause_id": "X", "repair_id": "Y"},
            {"accepted": False},
            ANSWER_KEY_REPAIR,
        ),
    ])
    def test_verdict_matches_score_decision_exactly(self, decision, validation, answer_key):
        direct = score_decision(decision, validation, answer_key)
        via_classify = classify_outcome(decision, validation, answer_key)
        assert via_classify["verdict"] == direct["verdict"]


class TestCategoryIsAlwaysOneOfTheSixOfficialNames:
    @pytest.mark.parametrize("decision,validation,answer_key", [
        (
            {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"},
            {"accepted": True},
            ANSWER_KEY_REPAIR,
        ),
        ({"disposition": "NO_REPAIR"}, None, ANSWER_KEY_NO_REPAIR),
        ({"disposition": "ESCALATE"}, None, ANSWER_KEY_ESCALATE),
        ({"disposition": "ESCALATE"}, None, ANSWER_KEY_REPAIR),
        (
            {"disposition": "REPAIR", "root_cause_id": "WRONG", "repair_id": "REPAIR_A"},
            {"accepted": True},
            ANSWER_KEY_REPAIR,
        ),
        (
            {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "OTHER"},
            {"accepted": False},
            ANSWER_KEY_REPAIR,
        ),
        ({"disposition": "NO_REPAIR"}, None, ANSWER_KEY_REPAIR),
        (
            {"disposition": "REPAIR", "root_cause_id": "X", "repair_id": "Y"},
            {"accepted": True},
            ANSWER_KEY_NO_REPAIR,
        ),
    ])
    def test_category_is_in_the_official_six(self, decision, validation, answer_key):
        result = classify_outcome(decision, validation, answer_key)
        assert result["category"] in CATEGORIES
