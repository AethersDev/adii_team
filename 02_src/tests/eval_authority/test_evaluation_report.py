"""Tests for evaluation_report.py — D-19's M10 report, built from a real
RunRecord shape plus an answer key.

Fixture shapes below mirror RunRecord.to_json()'s exact output in
02_src/adii/reporting/record.py (the real, current code, read directly
before writing this test) — "context", "decision", "validation" fields,
verbatim key names — so these tests fail if the real schema ever drifts
from what this module assumes, rather than only failing once a real
archived record is fed through it for the first time.
"""
import json

import pytest
from adii.evaluation.evaluation_report import SCHEMA, build_evaluation_report, to_json

ANSWER_KEY = {
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "CAUSE_A",
    "repair_must_satisfy": {"reference_repair_id": "REPAIR_A"},
}


def submitted_run_record(decision: dict, validation: dict | None) -> dict:
    """A RunRecord.to_json()-shaped dict for a submitted run — the fields
    this module reads, in the real field names record.py emits."""
    return {
        "schema": "adii.run_record/v1",
        "label": "run-042",
        "termination": "submitted",
        "detail": "the investigator committed to a disposition",
        "context": {"incident_id": "demo-learning-001", "alert": "revenue dropped",
                    "as_of": "2026-09-15T00:00:00Z", "permitted_write_paths": []},
        "trace": [],
        "decision": decision,
        "validation": validation,
        "counters": {"tool_calls": 2, "model_turns": 3, "api_cost_usd": 0.0, "latency_ms": 100},
        "configuration": {},
        "provenance": {
            "origin": "test", "written_at": "2026-09-15T00:00:00Z", "source_revision": None
        },
    }


def non_submitted_run_record(termination: str) -> dict:
    return {
        "schema": "adii.run_record/v1",
        "label": "run-013",
        "termination": termination,
        "detail": "budget exhausted",
        "context": {"incident_id": "demo-learning-001", "alert": "x",
                    "as_of": "2026-09-15T00:00:00Z", "permitted_write_paths": []},
        "trace": [],
        "decision": None,
        "validation": None,
        "counters": {"tool_calls": 0, "model_turns": 0, "api_cost_usd": 0.0, "latency_ms": 0},
        "configuration": {},
        "provenance": {
            "origin": "test", "written_at": "2026-09-15T00:00:00Z", "source_revision": None
        },
    }


class TestSubmittedRuns:
    def test_success_run_produces_a_success_report(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "root_cause_summary": "x",
                    "repair_id": "REPAIR_A", "patch": {"a": "b"}}
        validation = {"accepted": True, "report": "ok", "checks_run": []}
        report = build_evaluation_report(submitted_run_record(decision, validation), ANSWER_KEY)

        assert report == {
            "schema": SCHEMA,
            "run_label": "run-042",
            "incident_id": "demo-learning-001",
            "category": "success",
            "sub_kind": None,
            "verdict": "correct",
            "settled_by": "deterministic",
            "runtime_validation": {"state": "checked", "accepted": True, "checks_run": []},
        }

    def test_runtime_validation_is_a_dimension_orthogonal_to_the_verdict(self):
        """The same category — an unwarranted repair — means a different system behaviour
        depending on whether the runtime blocked it before action or only preserved it for
        this scorer to find afterwards. The report keeps both, separately."""
        decision = {"disposition": "REPAIR", "root_cause_id": "X", "root_cause_summary": "x",
                    "repair_id": "R", "patch": {"a": "b"}}
        key = {**ANSWER_KEY, "correct_disposition": "NO_REPAIR"}
        unchecked = build_evaluation_report(submitted_run_record(decision, {
            "accepted": False, "report": "No independent validator exists yet.",
            "checks_run": []}), key)
        rejected = build_evaluation_report(submitted_run_record(decision, {
            "accepted": False, "report": "rebuilt; wrong", "checks_run": ["rebuild"]}), key)
        assert unchecked["category"] == rejected["category"] == "failure"
        assert unchecked["sub_kind"] == rejected["sub_kind"] == "unwarranted_repair"
        assert unchecked["runtime_validation"] == {"state": "unchecked", "accepted": False,
                                                   "checks_run": []}
        assert rejected["runtime_validation"] == {"state": "checked", "accepted": False,
                                                  "checks_run": ["rebuild"]}
        no_repair = build_evaluation_report(submitted_run_record(
            {**decision, "disposition": "NO_REPAIR", "repair_id": None, "patch": {}}, None), key)
        assert no_repair["runtime_validation"] == {"state": "none", "accepted": None,
                                                   "checks_run": []}

    def test_escalate_run_that_should_have_repaired_is_unnecessary_escalation(self):
        decision = {
            "disposition": "ESCALATE", "root_cause_id": None,
            "root_cause_summary": "not enough evidence", "repair_id": None, "patch": {},
        }
        report = build_evaluation_report(submitted_run_record(decision, None), ANSWER_KEY)

        assert report["category"] == "unnecessary_escalation"

    def test_rejected_repair_is_repair_rejection(self):
        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "root_cause_summary": "x",
                    "repair_id": "WRONG_REPAIR", "patch": {"a": "b"}}
        validation = {"accepted": False, "report": "does not fix it", "checks_run": []}
        report = build_evaluation_report(submitted_run_record(decision, validation), ANSWER_KEY)

        assert report["category"] == "repair_rejection"

    def test_uses_judge_when_supplied_for_an_ambiguous_case(self):
        def judge_says_correct(decision, validation, answer_key):
            return {"verdict": "correct", "reasoning": "valid alternative"}

        decision = {"disposition": "REPAIR", "root_cause_id": "CAUSE_A", "root_cause_summary": "x",
                    "repair_id": "SOME_OTHER_REPAIR", "patch": {"a": "b"}}
        validation = {"accepted": True, "report": "structurally sound", "checks_run": []}
        report = build_evaluation_report(
            submitted_run_record(decision, validation), ANSWER_KEY, judge=judge_says_correct
        )

        assert report["category"] == "success"
        assert report["settled_by"] == "judge"


class TestNonSubmittedRuns:
    @pytest.mark.parametrize(
        "termination", ["model_failure", "bound_hit", "infrastructure_failure"]
    )
    def test_non_submitted_run_is_not_evaluable_not_a_guessed_category(self, termination):
        report = build_evaluation_report(non_submitted_run_record(termination), ANSWER_KEY)

        assert report["category"] == "not_evaluable"
        assert termination in report["reason"]
        assert "verdict" not in report  # nothing was ever scored


class TestMalformedRunRecord:
    def test_missing_label_raises(self):
        record = submitted_run_record({"disposition": "REPAIR"}, None)
        del record["label"]
        with pytest.raises(ValueError, match="label"):
            build_evaluation_report(record, ANSWER_KEY)

    def test_missing_termination_raises(self):
        record = submitted_run_record({"disposition": "REPAIR"}, None)
        del record["termination"]
        with pytest.raises(ValueError, match="termination"):
            build_evaluation_report(record, ANSWER_KEY)

    def test_missing_context_raises(self):
        record = submitted_run_record({"disposition": "REPAIR"}, None)
        del record["context"]
        with pytest.raises(ValueError, match="context"):
            build_evaluation_report(record, ANSWER_KEY)


class TestJsonSerialisation:
    def test_report_round_trips_through_to_json(self):
        decision = {"disposition": "NO_REPAIR", "root_cause_id": None, "root_cause_summary": "fine",
                    "repair_id": None, "patch": {}}
        answer_key = {"correct_disposition": "NO_REPAIR"}
        report = build_evaluation_report(submitted_run_record(decision, None), answer_key)

        text = to_json(report)
        assert json.loads(text) == report
        assert text.endswith("\n")
