"""Step 5: the real validation/ package, adapted to evaluation/'s
ValidatorProvider shape and driven through get_validation_for exactly as the
existing fake was — proving the "one-line swap" validation_wiring.py's
docstring promises actually holds.
"""
from __future__ import annotations

from adii.contracts import IncidentContext
from adii.evaluation.validation_wiring import get_validation_for
from adii.validation.validator import as_dict_validator

CONTEXT = IncidentContext(
    incident_id="demo-learning-001",
    alert="daily revenue is 1/100th of what it should be",
    as_of="2026-01-15",
)


def repair_decision(patch: dict[str, str]) -> dict:
    return {
        "disposition": "REPAIR",
        "root_cause_id": "double-division",
        "root_cause_summary": "stg_orders.sql divides amount_cents by 100 twice",
        "repair_id": "fix-double-division",
        "patch": patch,
    }


def test_the_real_validator_accepts_a_correct_repair_through_get_validation_for():
    validator = as_dict_validator(CONTEXT)
    decision = repair_decision({"stg_orders.sql": "count * 100 / 100"})
    result = get_validation_for(decision, validator)
    assert result == {
        "accepted": True,
        "report": result["report"],
        "checks_run": result["checks_run"],
    }
    assert result["accepted"] is True
    assert set(result) == {"accepted", "report", "checks_run"}


def test_the_real_validator_rejects_a_wrong_repair_through_get_validation_for():
    validator = as_dict_validator(CONTEXT)
    decision = repair_decision({"stg_orders.sql": "count * 100 / 100 / 100"})
    result = get_validation_for(decision, validator)
    assert result["accepted"] is False


def test_non_repair_dispositions_never_reach_the_real_validator_either():
    validator = as_dict_validator(CONTEXT)
    no_repair = {"disposition": "NO_REPAIR", "root_cause_id": None,
                 "root_cause_summary": "the metric moved because the business moved",
                 "repair_id": None, "patch": {}}
    assert get_validation_for(no_repair, validator) is None
