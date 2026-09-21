"""Edge-case hardening for scoring.py and judge.py — ambiguous judge replies,
partial conflicts, ESCALATE paths, and malformed/missing input.

Separate from test_step1_all.py / test_step2_all.py (the happy-path,
walkthrough-driven acceptance tests) and from fixtures/test_synthetic_fixtures.py
(the NO_REPAIR / ESCALATE answer-key drills). This file exists to pin down
failure behavior: what raises, what it says, and what must never be
silently guessed.
"""
import json
from pathlib import Path

import pytest

from judge import build_judge_prompt, judge_repair, parse_judge_reply
from scoring import (
    decide_route,
    score_decision,
    score_disposition,
    score_repair_validation,
)

HERE = Path(__file__).parent


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def key_001():
    return load("demo-learning-001.answer.json")


@pytest.fixture(scope="module")
def key_escalate():
    return load(str(Path("fixtures") / "synthetic-escalate-001.answer.json"))


# ---------------------------------------------------------------------------
# Ambiguous judge replies — a model saying something that merely starts
# with "correct"/"incorrect" as a word-fragment, not a clean verdict.
# ---------------------------------------------------------------------------

class TestAmbiguousJudgeReplies:
    @pytest.mark.parametrize("reply", [
        "Correctish, but I'm not fully sure.",
        "Incorrectly worded question, but the repair is fine.",
        "correctable if you squint",
    ])
    def test_verdict_word_used_as_a_fragment_is_rejected_not_guessed(self, reply):
        with pytest.raises(ValueError, match="clean verdict"):
            parse_judge_reply(reply)

    def test_empty_reply_is_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            parse_judge_reply("   ")

    def test_none_reply_is_rejected(self):
        with pytest.raises(ValueError, match="None"):
            parse_judge_reply(None)

    def test_verdict_followed_by_punctuation_still_parses(self):
        assert parse_judge_reply("correct.") == ("correct", "")
        assert parse_judge_reply("correct—it satisfies every condition.") == (
            "correct", "it satisfies every condition."
        )
        assert parse_judge_reply("incorrect: wrong direction entirely") == (
            "incorrect", "wrong direction entirely"
        )

    def test_bare_verdict_with_no_reasoning_parses_to_empty_string(self):
        assert parse_judge_reply("correct") == ("correct", "")
        assert parse_judge_reply("incorrect") == ("incorrect", "")


# ---------------------------------------------------------------------------
# Partial conflicts — right disposition, but other fields tell contradictory
# stories (root cause mismatch alongside an exact repair_id match, etc).
# ---------------------------------------------------------------------------

class TestPartialConflicts:
    def test_matching_repair_id_but_wrong_root_cause_id_needs_the_judge(self, key_001):
        # root_cause_id is compared alongside repair_id (scoring.py's own
        # answer keys require this: a root_cause_id mismatch must route to
        # the judge, never auto-pass just because the repair_id happens to
        # match). A differently-worded root_cause_summary under a wrong id
        # might still be semantically equivalent — only the judge can tell.
        decision = {
            "disposition": "REPAIR",
            "root_cause_id": "SOME_OTHER_ID",
            "root_cause_summary": "a completely different explanation",
            "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
        }
        assert decide_route(decision, {"accepted": True}, key_001) == "needs_judge_review"

    def test_matching_root_cause_and_repair_id_settles_correct(self, key_001):
        decision = {
            "disposition": "REPAIR",
            "root_cause_id": key_001["correct_root_cause_id"],
            "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
        }
        assert decide_route(decision, {"accepted": True}, key_001) == "correct"

    def test_right_disposition_wrong_repair_and_rejected_validation_fails_on_validation_first(self, key_001):
        # Two independent reasons to fail at once (repair_id differs AND
        # validation was rejected) — validation gating must win before the
        # repair-id branch is ever reached, so this never reaches
        # needs_judge_review.
        decision = {
            "disposition": "REPAIR",
            "repair_id": "SOME_OTHER_REPAIR",
        }
        assert decide_route(decision, {"accepted": False}, key_001) == "incorrect"

    def test_repair_disposition_with_no_repair_id_at_all_needs_the_judge(self, key_001):
        # decision.get("repair_id") is None, which never equals a real
        # reference_repair_id — this must route to the judge, not silently
        # pass or crash on a missing key.
        decision = {"disposition": "REPAIR"}
        assert decide_route(decision, {"accepted": True}, key_001) == "needs_judge_review"


# ---------------------------------------------------------------------------
# ESCALATE paths — previously uncovered by any test in this repo.
# ---------------------------------------------------------------------------

class TestEscalatePaths:
    def test_correct_escalate_settles_deterministically(self, key_escalate):
        case = key_escalate["test_fixtures"]["case_correct_escalate"]
        assert decide_route(case["decision"], case["validation"], key_escalate) == "correct"

    def test_escalate_never_consults_validation_even_if_one_is_supplied_by_mistake(self, key_escalate):
        # If an ESCALATE decision is accompanied by a validation dict (it
        # shouldn't be, but a buggy caller might), score_repair_validation
        # must still short-circuit to "correct" on this axis rather than
        # inspecting a validation that logically doesn't apply.
        assert score_repair_validation("ESCALATE", {"accepted": False}) == "correct"

    def test_escalate_that_should_have_been_a_repair_is_incorrect(self, key_001):
        assert decide_route({"disposition": "ESCALATE"}, None, key_001) == "incorrect"

    def test_no_repair_that_should_have_been_escalate_is_incorrect(self, key_escalate):
        case = key_escalate["test_fixtures"]["case_guessed_instead_of_escalating"]
        assert decide_route(case["decision"], case["validation"], key_escalate) == "incorrect"


# ---------------------------------------------------------------------------
# Malformed / missing input — every required field, one at a time.
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_unknown_disposition_string_raises_instead_of_silently_scoring_incorrect(self, key_001):
        with pytest.raises(ValueError, match="must be one of"):
            score_disposition("REPAIRED", key_001)

    def test_none_disposition_raises(self, key_001):
        with pytest.raises(ValueError, match="must be one of"):
            score_disposition(None, key_001)

    def test_empty_string_disposition_raises(self, key_001):
        with pytest.raises(ValueError, match="must be one of"):
            score_disposition("", key_001)

    def test_answer_key_missing_correct_disposition_raises_with_field_name(self):
        with pytest.raises(ValueError, match="correct_disposition"):
            score_disposition("REPAIR", {})

    def test_decision_missing_disposition_raises_with_field_name(self, key_001):
        with pytest.raises(ValueError, match="disposition"):
            decide_route({}, None, key_001)

    def test_decision_that_is_not_a_dict_raises(self, key_001):
        with pytest.raises(ValueError, match="must be a dict"):
            decide_route(None, None, key_001)

    def test_repair_validation_missing_accepted_field_raises(self):
        with pytest.raises(ValueError, match="accepted"):
            score_repair_validation("REPAIR", {"report": "looks fine, but no verdict field"})

    def test_answer_key_missing_repair_must_satisfy_raises(self):
        decision = {"disposition": "REPAIR"}
        answer_key = {"correct_disposition": "REPAIR", "correct_root_cause_id": "X"}
        with pytest.raises(ValueError, match="repair_must_satisfy"):
            decide_route(decision, {"accepted": True}, answer_key)

    def test_answer_key_missing_correct_root_cause_id_raises(self):
        decision = {"disposition": "REPAIR"}
        answer_key = {"correct_disposition": "REPAIR", "repair_must_satisfy": {"reference_repair_id": "X"}}
        with pytest.raises(ValueError, match="correct_root_cause_id"):
            decide_route(decision, {"accepted": True}, answer_key)

    def test_repair_must_satisfy_missing_reference_repair_id_raises(self):
        decision = {"disposition": "REPAIR"}
        answer_key = {
            "correct_disposition": "REPAIR",
            "correct_root_cause_id": "X",
            "repair_must_satisfy": {},
        }
        with pytest.raises(ValueError, match="reference_repair_id"):
            decide_route(decision, {"accepted": True}, answer_key)

    def test_judge_prompt_missing_answer_key_fields_raises_with_field_name(self):
        decision = {"disposition": "REPAIR", "repair_id": "X"}
        validation = {"accepted": True, "report": "ok"}
        with pytest.raises(ValueError, match="correct_disposition"):
            build_judge_prompt(decision, validation, {})

    def test_judge_prompt_missing_validation_report_raises(self, key_001):
        decision = {"disposition": "REPAIR", "repair_id": "X"}
        with pytest.raises(ValueError, match="report"):
            build_judge_prompt(decision, {"accepted": True}, key_001)

    def test_judge_repair_surfaces_malformed_input_before_ever_calling_the_provider(self, key_001):
        calls = []

        def provider_that_should_never_run(prompt):
            calls.append(prompt)
            return "correct — fine"

        with pytest.raises(ValueError):
            judge_repair({"disposition": "REPAIR"}, {}, key_001, provider_that_should_never_run)

        assert calls == [], "provider must not be called when the inputs are malformed"


# ---------------------------------------------------------------------------
# score_decision — the full wrapper must propagate the same clear errors,
# not swallow them into "unresolved".
# ---------------------------------------------------------------------------

class TestScoreDecisionPropagatesErrors:
    def test_malformed_decision_raises_rather_than_returning_unresolved(self, key_001):
        with pytest.raises(ValueError):
            score_decision({}, None, key_001)
