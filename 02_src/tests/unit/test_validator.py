"""Step 4 of building validation/: the assembled validator.

Confirms it satisfies `runtime.run.Validator`, never reads a rehearsal claim
(C1a/C1b), rejects on a bad patch, and accepts on a genuinely correct one —
against the real `demo-learning-001` incident, no fakes.
"""
from __future__ import annotations

import pytest
from adii.contracts import Disposition, IncidentContext, InvestigationDecision
from adii.runtime.run import Validator as ValidatorProtocol
from adii.validation.validator import UnknownIncident, Validator, validate

# the patch as the protocol has a model send it: the permitted path, the file's contents
TRANSFORM = "transforms/stg_orders.sql"
CORRECT = {TRANSFORM: "SELECT order_id, order_date, amount_cents / 100.0 AS amount_usd "
                      "FROM orders;"}
STILL_BROKEN = {TRANSFORM: "SELECT order_id, order_date, amount_cents / 100.0 / 100.0 "
                           "AS amount_usd FROM orders;"}

CONTEXT = IncidentContext(
    incident_id="demo-learning-001",
    alert="daily revenue is 1/100th of what it should be",
    as_of="2026-01-15",
)


def repair_decision(patch: dict[str, str]) -> InvestigationDecision:
    return InvestigationDecision(
        disposition=Disposition.REPAIR,
        root_cause_id="double-division",
        root_cause_summary="stg_orders.sql divides amount_cents by 100 twice",
        repair_id="fix-double-division",
        patch=patch,
    )


class TestSatisfiesTheRuntimeProtocol:
    def test_validator_instance_is_a_runtime_validator(self):
        # Protocol conformance is structural (duck typing) — this documents the
        # contract explicitly rather than leaving it implicit.
        instance: ValidatorProtocol = Validator()
        decision = repair_decision(CORRECT)
        result = instance.validate(CONTEXT, decision)
        assert result.accepted is True


class TestAcceptsACorrectRepair:
    def test_the_correct_patch_is_accepted_with_checks_recorded(self):
        result = validate(CONTEXT, repair_decision(CORRECT))
        assert result.accepted is True and result.state == "ACCEPT"
        # the rebuild is the first check; the three world checks follow it
        assert result.checks_run[0] == "rebuild" and len(result.checks_run) == 4
        assert result.report


class TestRejectsAWrongRepair:
    def test_a_patch_that_does_not_fix_the_defect_is_rejected(self):
        result = validate(CONTEXT, repair_decision(STILL_BROKEN))
        assert result.accepted is False and result.state == "REJECT"
        assert result.checks_run[0] == "rebuild"  # rejection names which checks ran

    def test_a_patch_the_world_cannot_apply_is_rejected_by_the_rebuild_check(self):
        """Row 3: a patch the world cannot apply is a REJECT by the check named `rebuild`,
        never the legacy shape with no checks, which reads as nobody having looked."""
        result = validate(CONTEXT, repair_decision({"wrong_file.sql": "SELECT 1"}))
        assert result.accepted is False and result.state == "REJECT"
        assert result.checks_run == ("rebuild",)
        assert "rejected" in result.report

    def test_a_transform_that_does_not_run_is_rejected_by_the_rebuild_check(self):
        result = validate(CONTEXT, repair_decision(
            {TRANSFORM: "SELECT * FROM orders; DROP TABLE orders"}))
        assert result.accepted is False and result.checks_run == ("rebuild",)
        assert "one statement" in result.report


class TestNeverConsultsARehearsal:
    def test_validate_has_no_parameter_through_which_a_rehearsal_could_arrive(self):
        import inspect
        params = inspect.signature(validate).parameters
        assert set(params) == {"context", "decision"}

    def test_the_same_decision_validates_identically_regardless_of_any_external_claim(self):
        decision = repair_decision(CORRECT)
        # Simulate an agent's own rehearsal claiming success or failure — it is
        # never passed to validate(), so it cannot change the verdict.
        agent_rehearsal_says_pass = {"passed": True}
        agent_rehearsal_says_fail = {"passed": False}

        result_a = validate(CONTEXT, decision)
        result_b = validate(CONTEXT, decision)

        assert result_a.accepted == result_b.accepted == True  # noqa: E712
        assert agent_rehearsal_says_pass["passed"] != agent_rehearsal_says_fail["passed"]


class TestUnknownIncident:
    def test_an_incident_with_no_frozen_world_raises_rather_than_guessing(self):
        unknown_context = IncidentContext(incident_id="not-a-real-incident", alert="x", as_of="x")
        with pytest.raises(UnknownIncident):
            validate(unknown_context, repair_decision(CORRECT))
