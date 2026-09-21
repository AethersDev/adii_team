"""Tests for failure_signal.py — D-17's grid-runner-facing record shape.

D-17's own wording: "N incidents x R repeats; every promised repeat is
materialised as a record, success or classified failure; one failing
unit does not abort the rest." build_grid_batch's contract is exercised
directly against that: R (decision, validation) pairs in, exactly R
records out, in order, success and failure recorded the same shape.
"""
import json

from failure_signal import build_failure_signal, build_grid_batch

ANSWER_KEY = {
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "CAUSE_A",
    "repair_must_satisfy": {"reference_repair_id": "REPAIR_A"},
}


class TestBuildFailureSignal:
    def test_success_case_has_the_full_field_set(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}
        signal = build_failure_signal("inc-1", 0, decision, {"accepted": True}, ANSWER_KEY)

        assert signal == {
            "incident_id": "inc-1",
            "repeat_index": 0,
            "category": "success",
            "sub_kind": None,
            "verdict": "correct",
            "settled_by": "deterministic",
        }

    def test_failure_case_has_the_same_field_set_as_success(self):
        decision = {"disposition": "NO_REPAIR"}
        signal = build_failure_signal("inc-1", 3, decision, None, ANSWER_KEY)

        assert set(signal) == {"incident_id", "repeat_index", "category", "sub_kind", "verdict", "settled_by"}
        assert signal["category"] == "failure"
        assert signal["repeat_index"] == 3

    def test_judge_settled_case_reports_settled_by_judge(self):
        def judge_says_correct(decision, validation, answer_key):
            return {"verdict": "correct", "reasoning": "valid alternative"}

        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "OTHER"}
        signal = build_failure_signal("inc-1", 0, decision, {"accepted": True}, ANSWER_KEY, judge=judge_says_correct)

        assert signal["category"] == "success"
        assert signal["settled_by"] == "judge"

    def test_signal_is_strict_json_serialisable(self):
        decision = {"disposition": "ESCALATE"}
        signal = build_failure_signal("inc-1", 0, decision, None, ANSWER_KEY)
        # Round-trips cleanly with allow_nan effectively off by construction —
        # every value here is a plain str, int, or None, never float/NaN.
        round_tripped = json.loads(json.dumps(signal))
        assert round_tripped == signal


class TestBuildGridBatch:
    def test_r_repeats_in_produces_exactly_r_records_out(self):
        runs = [
            ({"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}, {"accepted": True}),
            ({"disposition": "NO_REPAIR"}, None),
            ({"disposition": "ESCALATE"}, None),
        ]
        batch = build_grid_batch("inc-1", runs, ANSWER_KEY)

        assert len(batch) == 3
        assert [r["repeat_index"] for r in batch] == [0, 1, 2]
        assert [r["incident_id"] for r in batch] == ["inc-1"] * 3

    def test_repeat_order_is_preserved_not_sorted_by_outcome(self):
        runs = [
            ({"disposition": "NO_REPAIR"}, None),  # failure
            ({"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}, {"accepted": True}),  # success
        ]
        batch = build_grid_batch("inc-1", runs, ANSWER_KEY)

        assert batch[0]["category"] == "failure"
        assert batch[1]["category"] == "success"

    def test_one_failing_repeat_does_not_prevent_the_others_from_being_recorded(self):
        # D-17: "one failing unit does not abort the rest" — a repeat
        # scored as a failure is still a complete record, and subsequent
        # repeats in the same batch are still built.
        runs = [
            ({"disposition": "NO_REPAIR"}, None),  # failure: missed a real defect
            ({"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}, {"accepted": True}),
            ({"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "REPAIR_A"}, {"accepted": True}),
        ]
        batch = build_grid_batch("inc-1", runs, ANSWER_KEY)

        assert len(batch) == 3
        assert batch[0]["category"] == "failure"
        assert batch[1]["category"] == "success"
        assert batch[2]["category"] == "success"

    def test_empty_runs_produces_empty_batch(self):
        assert build_grid_batch("inc-1", [], ANSWER_KEY) == []
