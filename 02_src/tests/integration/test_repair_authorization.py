"""m7_validation_integration.md row 4, executable: for every REPAIR the runtime establishes
whether the patch's targets were permitted, apart from — never instead of, never gating —
the validator's verdict; admission is derived from both and stored nowhere; nothing executes.

The table the decision record fixed, cell by cell, through the real runtime:

    authorization  validation      admissible
    permitted      ACCEPT          yes
    permitted      REJECT          no      permitted but invalid
    denied         ACCEPT          no      works, but not allowed
    denied         REJECT          no      neither
    permitted      NOT_CHECKABLE   no      the validation side was not established
"""
from __future__ import annotations

import inspect
import json

import pytest
from adii.contracts import Disposition, InvestigationDecision, ValidationResult
from adii.examples.walkthrough import load
from adii.reporting import render_run
from adii.runtime.run import authorize, run_incident
from adii.runtime.scripted import ScriptedInvestigator, ScriptedTools

PERMITTED = "transforms/stg_orders.sql"          # the walkthrough incident permits this one
ELSEWHERE = "jobs/load_orders.yml"
ACCEPT = ValidationResult(accepted=True, report="rebuilt; every check passed",
                          checks_run=("rebuild", "independent_recomputation"))
REJECT = ValidationResult(accepted=False, report="rebuilt; the mart still disagrees",
                          checks_run=("rebuild", "independent_recomputation"))
NOT_CHECKABLE = ValidationResult(accepted=False, report="Not checkable: no world to rebuild",
                                 reason_code="no_rebuildable_world")


class Recording:
    """A validator that answers as told and keeps what it was handed."""

    def __init__(self, result: ValidationResult) -> None:
        self.result, self.seen = result, []

    def validate(self, context, decision):
        self.seen.append(context)
        return self.result


def repair(*paths: str) -> InvestigationDecision:
    return InvestigationDecision(Disposition.REPAIR, "X", "a fault", "R1",
                                 {p: "SELECT 1" for p in paths})


def run(decision: InvestigationDecision, validator):
    context, _ = load()
    return run_incident("t", context, ScriptedInvestigator((), decision), ScriptedTools({}),
                        validator, configuration={})


@pytest.mark.parametrize(("targets", "verdict", "authorized", "admissible"), [
    ((PERMITTED,), ACCEPT, True, True),
    ((PERMITTED,), REJECT, True, False),
    ((ELSEWHERE,), ACCEPT, False, False),
    ((ELSEWHERE,), REJECT, False, False),
    ((PERMITTED,), NOT_CHECKABLE, True, False),
])
def test_the_table_cell_by_cell(targets, verdict, authorized, admissible):
    validator = Recording(verdict)
    record = run(repair(*targets), validator)
    fact = record.authorization
    assert record.termination == "submitted"
    assert fact.authorized is authorized and fact.checked_paths == targets
    assert fact.reason_code == (None if authorized else "target_not_permitted")
    assert record.validation == verdict            # the verdict travels untouched, every cell
    assert record.admissible is admissible
    # validation ran whether or not the patch was authorized: one call, and the trace says so
    assert len(validator.seen) == 1
    assert [e.kind for e in record.trace][-2:] == ["decision_submitted", "validation_completed"]
    # admission is derived, never stored: the record carries the two facts and no third
    assert "admissible" not in json.loads(record.to_json())
    report = render_run(record)
    assert ("  AUTHORIZED" if authorized else "  DENIED") in report
    verdict_line = "  admissible   (authorized and accepted" if admissible else "  not admissible"
    assert verdict_line in report


def test_the_validator_is_never_handed_the_permitted_paths():
    """Permission is the runtime's question. The validator receives the incident without its
    permitted paths, so it cannot decide permission even by accident."""
    context, _ = load()
    assert context.permitted_write_paths == (PERMITTED,)
    validator = Recording(ACCEPT)
    run(repair(PERMITTED), validator)
    assert validator.seen[0].permitted_write_paths == ()
    assert validator.seen[0].incident_id == context.incident_id     # everything else intact


def test_one_target_outside_the_permitted_paths_denies_the_patch_whole():
    """A repair is applied whole or not at all, so it is authorized whole or not at all: the
    permitted target does not make the patch partly authorized. Every target is named as
    checked; only the offending one as denied."""
    fact = run(repair(PERMITTED, ELSEWHERE), Recording(ACCEPT)).authorization
    assert fact.authorized is False and fact.reason_code == "target_not_permitted"
    assert fact.checked_paths == (PERMITTED, ELSEWHERE) and fact.denied_paths == (ELSEWHERE,)


@pytest.mark.parametrize("decision", [
    InvestigationDecision(Disposition.NO_REPAIR, None, "the business moved"),
    InvestigationDecision(Disposition.ESCALATE, None, "the evidence does not settle it"),
])
def test_a_run_that_proposed_no_repair_fabricates_no_authorization(decision):
    record = run(decision, Recording(ACCEPT))
    assert record.authorization is None and record.validation is None
    assert record.admissible is False
    with pytest.raises(ValueError, match="only a REPAIR has targets to authorize"):
        authorize(record.context, decision)


def test_authorization_never_learns_whether_the_patch_works():
    """The check takes the incident and the decision and nothing else — no world, no
    validator, no verdict can reach it — and the same patch is authorized identically
    whatever the validator will say."""
    assert set(inspect.signature(authorize).parameters) == {"context", "decision"}
    context, _ = load()
    assert authorize(context, repair(PERMITTED)) == authorize(context, repair(PERMITTED))
    assert run(repair(ELSEWHERE), Recording(ACCEPT)).authorization == \
        run(repair(ELSEWHERE), Recording(REJECT)).authorization
