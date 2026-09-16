"""Task 5, part 1: does scoring.py/judge.py's shape assumption match the
real contracts/core.py — not a hand-typed dict imitating it, but an
actual InvestigationDecision/ValidationResult instance, converted the
same way RunRecord.to_json() converts one for the archive?

This test imports adii.contracts directly — not a copy, not a re-typed
dataclass. If A or D ever change a field name in contracts/core.py,
this file is the one that goes red, not eval_authority's own
scoring.py, which has no import-time dependency on the rest of
adii_team at all (and must not gain one — see scoring.py/judge.py's
docstrings on staying independent of A/B's code).

Skipped, not failed, if contracts/core.py cannot be found — this
test's only job is to catch drift when both sides are actually present
to compare.
"""
from pathlib import Path

import pytest

_CONTRACTS_CORE = Path(__file__).resolve().parents[2] / "adii" / "contracts" / "core.py"

if not _CONTRACTS_CORE.exists():
    pytest.skip("adii.contracts.core not found in 02_src — skipping contract consistency check", allow_module_level=True)

from adii.contracts import Disposition, InvestigationDecision, ValidationResult

from adii.evaluation.judge import build_judge_prompt
from adii.evaluation.outcome_classification import classify_outcome
from adii.evaluation.scoring import score_decision


def decision_to_dict(decision: InvestigationDecision) -> dict:
    """The exact conversion RunRecord.to_json() applies (record.py) —
    reproduced here, not imported, so this test does not silently start
    passing because it happens to call the same helper record.py calls;
    it must independently agree with what record.py actually emits."""
    return {
        "disposition": decision.disposition.value,
        "root_cause_id": decision.root_cause_id,
        "root_cause_summary": decision.root_cause_summary,
        "repair_id": decision.repair_id,
        "patch": decision.patch,
    }


def validation_to_dict(validation: ValidationResult) -> dict:
    return {"accepted": validation.accepted, "report": validation.report, "checks_run": list(validation.checks_run)}


ANSWER_KEY = {
    "incident_id": "contract-consistency-test",
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "CAUSE_A",
    "root_cause_explanation": "because reasons",
    "repair_must_satisfy": {
        "reference_repair_id": "REPAIR_A",
        "alternative_repairs_are_acceptable_if": ["it still fixes the cause"],
    },
}


class TestRealInvestigationDecisionShapeMatchesScoringAssumptions:
    def test_a_real_repair_decision_scores_without_a_shape_error(self):
        decision = InvestigationDecision(
            disposition=Disposition.REPAIR,
            root_cause_id="CAUSE_A",
            root_cause_summary="the real reason, from a real dataclass",
            repair_id="REPAIR_A",
            patch={"file.sql": "SELECT 1"},
        )
        validation = ValidationResult(accepted=True, report="rebuilt cleanly", checks_run=("x",))

        result = score_decision(decision_to_dict(decision), validation_to_dict(validation), ANSWER_KEY)
        assert result == {"verdict": "correct", "settled_by": "deterministic"}

    def test_a_real_no_repair_decision_scores_cleanly(self):
        decision = InvestigationDecision(
            disposition=Disposition.NO_REPAIR,
            root_cause_id=None,
            root_cause_summary="nothing is actually wrong",
        )
        answer_key = {"correct_disposition": "NO_REPAIR"}

        result = score_decision(decision_to_dict(decision), None, answer_key)
        assert result == {"verdict": "correct", "settled_by": "deterministic"}

    def test_a_real_escalate_decision_scores_cleanly(self):
        decision = InvestigationDecision(
            disposition=Disposition.ESCALATE,
            root_cause_id=None,
            root_cause_summary="the decisive evidence is unreachable",
        )
        answer_key = {"correct_disposition": "ESCALATE"}

        result = score_decision(decision_to_dict(decision), None, answer_key)
        assert result == {"verdict": "correct", "settled_by": "deterministic"}

    def test_disposition_value_is_the_plain_string_scoring_expects(self):
        # Disposition is a StrEnum — .value must be the bare "REPAIR" string
        # decide_route compares against, not "Disposition.REPAIR" or similar.
        decision = InvestigationDecision(
            disposition=Disposition.REPAIR, root_cause_id="CAUSE_A",
            root_cause_summary="x", repair_id="REPAIR_A", patch={"a": "b"},
        )
        as_dict = decision_to_dict(decision)
        assert as_dict["disposition"] == "REPAIR"
        assert isinstance(as_dict["disposition"], str)

    def test_judge_prompt_builds_from_a_real_decision_and_validation(self):
        decision = InvestigationDecision(
            disposition=Disposition.REPAIR, root_cause_id="CAUSE_A",
            root_cause_summary="real summary", repair_id="A_DIFFERENT_REPAIR_ID",
            patch={"file.sql": "SELECT 2"},
        )
        validation = ValidationResult(accepted=True, report="structurally sound")

        prompt = build_judge_prompt(decision_to_dict(decision), validation_to_dict(validation), ANSWER_KEY)
        assert "real summary" in prompt
        assert "A_DIFFERENT_REPAIR_ID" in prompt

    def test_classify_outcome_handles_a_real_decision_end_to_end(self):
        decision = InvestigationDecision(
            disposition=Disposition.ESCALATE, root_cause_id=None,
            root_cause_summary="cannot confirm without access to a denied table",
        )
        result = classify_outcome(decision_to_dict(decision), None, ANSWER_KEY)
        assert result["category"] == "unnecessary_escalation"

    def test_repair_construction_rules_from_the_contract_still_hold(self):
        # The contract itself refuses a REPAIR with no repair_id/patch —
        # confirming eval_authority's own assumption (that a REPAIR
        # decision always carries both) is backed by a construction-time
        # guarantee upstream, not just a convention this code hopes holds.
        with pytest.raises(ValueError, match="must carry a repair_id and a patch"):
            InvestigationDecision(disposition=Disposition.REPAIR, root_cause_id="X", root_cause_summary="y")

    def test_validation_report_cannot_be_empty_from_the_contract_either(self):
        # judge.py's _require_fields checks "report" is present; the
        # contract goes further and refuses an empty one at construction
        # — so a real ValidationResult never reaches judge.py with a
        # blank report in the first place.
        with pytest.raises(ValueError, match="must explain itself in report"):
            ValidationResult(accepted=True, report="   ")
