"""The contracts are what four people and many coding-agent sessions share. If these
break, everybody's assumptions break at once, so they are pinned first."""
from __future__ import annotations

import pytest
from adii.contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    InvestigationRun,
    ToolCall,
    ToolResult,
    TraceEvent,
    ValidationResult,
)

SUMMARY = "the mart disagrees with the source by exactly 100x"


def decision(**overrides) -> InvestigationDecision:
    base = {"disposition": Disposition.ESCALATE, "root_cause_id": None,
            "root_cause_summary": SUMMARY}
    return InvestigationDecision(**{**base, **overrides})


def test_a_decision_must_explain_itself():
    with pytest.raises(ValueError, match="explain itself"):
        decision(root_cause_summary="   ")


def test_repair_requires_a_repair_id_and_a_patch():
    """The frozen judge's invariant, enforced here so a malformed decision cannot travel."""
    with pytest.raises(ValueError, match="repair_id and a patch"):
        decision(disposition=Disposition.REPAIR)
    with pytest.raises(ValueError, match="repair_id and a patch"):
        decision(disposition=Disposition.REPAIR, repair_id="FIX", patch={})
    ok = decision(disposition=Disposition.REPAIR, repair_id="FIX", patch={"a.sql": "SELECT 1"})
    assert ok.disposition is Disposition.REPAIR


@pytest.mark.parametrize("disposition", [Disposition.NO_REPAIR, Disposition.ESCALATE])
def test_only_a_repair_may_carry_a_patch(disposition):
    with pytest.raises(ValueError, match="only a REPAIR"):
        decision(disposition=disposition, patch={"a.sql": "SELECT 1"})
    with pytest.raises(ValueError, match="only a REPAIR"):
        decision(disposition=disposition, repair_id="FIX")


def test_a_repair_run_must_carry_independent_validation():
    """The agent's own rehearsal is a hypothesis. A run is not complete without a verdict
    from the other authority."""
    repair = decision(disposition=Disposition.REPAIR, repair_id="FIX", patch={"a.sql": "x"})
    with pytest.raises(ValueError, match="independent ValidationResult"):
        InvestigationRun(incident_id="demo", decision=repair)
    with pytest.raises(ValueError, match="only a REPAIR run"):
        InvestigationRun(incident_id="demo", decision=decision(),
                         validation=ValidationResult(accepted=True, report="r"))


def test_a_validation_result_is_one_of_four_states_and_says_which():
    """m7_validation_integration.md row 3: the state space is closed. Accepted; rejected after
    named checks; not checkable, said in structure by a reason code from the closed set; or
    the legacy placeholder of records before 22 September, loadable and never produced.
    A result that cannot be one of the four is refused at construction."""
    assert ValidationResult(accepted=True, report="r", checks_run=("rebuild",)).state == "ACCEPT"
    assert ValidationResult(accepted=False, report="r", checks_run=("rebuild",)).state == "REJECT"
    assert ValidationResult(accepted=False, report="r",
                            reason_code="no_rebuildable_world").state == "NOT_CHECKABLE"
    assert ValidationResult(accepted=False, report="r").state == "UNCHECKED"
    with pytest.raises(ValueError, match="unknown reason_code"):
        ValidationResult(accepted=False, report="r", reason_code="the_dog_ate_it")
    with pytest.raises(ValueError, match="cannot be accepted"):
        ValidationResult(accepted=True, report="r", reason_code="no_rebuildable_world")
    with pytest.raises(ValueError, match="names no checks"):
        ValidationResult(accepted=False, report="r", checks_run=("rebuild",),
                         reason_code="no_rebuildable_world")
    with pytest.raises(ValueError, match="explain itself"):
        ValidationResult(accepted=False, report="  ", reason_code="no_rebuildable_world")


def test_tool_result_status_is_a_closed_set():
    """A refusal must be distinguishable from an answer, or the investigator cannot retry."""
    assert ToolResult(call_id="c1", name="run_sql", status="OK").ok
    assert not ToolResult(call_id="c1", name="run_sql", status="DENIED").ok
    with pytest.raises(ValueError, match="status must be one of"):
        ToolResult(call_id="c1", name="run_sql", status="probably_fine")


def test_run_counters_cannot_be_negative():
    with pytest.raises(ValueError, match="non-negative"):
        InvestigationRun(incident_id="demo", decision=decision(), tool_calls=-1)
    with pytest.raises(ValueError, match="non-negative"):
        InvestigationRun(incident_id="demo", decision=decision(), api_cost_usd=-0.01)


def test_the_empty_shapes_are_rejected():
    with pytest.raises(ValueError):
        IncidentContext(incident_id="", alert="a", as_of="t")
    with pytest.raises(ValueError):
        IncidentContext(incident_id="i", alert="  ", as_of="t")
    with pytest.raises(ValueError):
        ToolCall(call_id="", name="run_sql")
    with pytest.raises(ValueError):
        TraceEvent(sequence=-1, kind="tool_call")
