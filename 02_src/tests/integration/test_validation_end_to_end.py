"""Step 4/5, end to end: the real validation/ package, called by the real
runtime (`run_incident`), exactly as `runtime/__main__.py` will call it once
wired in — not through ScriptedValidator, and not through a fake.
"""
from __future__ import annotations

from adii.contracts import Disposition, IncidentContext, InvestigationDecision
from adii.runtime.run import run_incident
from adii.runtime.scripted import ScriptedInvestigator, ScriptedTools
from adii.validation.validator import Validator

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


def repair(patch: dict[str, str]) -> InvestigationDecision:
    return InvestigationDecision(
        disposition=Disposition.REPAIR,
        root_cause_id="double-division",
        root_cause_summary="stg_orders.sql divides amount_cents by 100 twice",
        repair_id="fix-double-division",
        patch=patch,
    )


def test_a_correct_repair_runs_through_the_real_runtime_and_is_accepted():
    investigator = ScriptedInvestigator((), repair(CORRECT))
    tools = ScriptedTools({})
    record = run_incident("e2e-accept", CONTEXT, investigator, tools, Validator(),
                           configuration={})

    assert record.termination == "submitted"
    assert record.decision.disposition is Disposition.REPAIR
    assert record.validation is not None
    assert record.validation.accepted is True
    # m7 row 4, the "works, but not allowed" cell: CONTEXT permits no path, so the target
    # is denied by the runtime while the validator, asked regardless, accepts the repair
    assert record.authorization.authorized is False
    assert record.authorization.denied_paths == (TRANSFORM,)
    assert record.admissible is False
    # The runtime's own trace records the validation boundary being crossed —
    # the investigator never sees how the verdict was reached.
    kinds = [e.kind for e in record.trace]
    assert "validation_completed" in kinds


def test_a_wrong_repair_runs_through_the_real_runtime_and_is_rejected():
    investigator = ScriptedInvestigator((), repair(STILL_BROKEN))
    tools = ScriptedTools({})
    record = run_incident("e2e-reject", CONTEXT, investigator, tools, Validator(),
                           configuration={})

    assert record.termination == "submitted"
    assert record.validation is not None
    assert record.validation.accepted is False
    assert record.validation.checks_run  # rejection still names which checks ran


def test_non_repair_dispositions_never_reach_the_validator():
    no_repair = InvestigationDecision(
        disposition=Disposition.NO_REPAIR, root_cause_id=None,
        root_cause_summary="the metric moved because the business moved")
    investigator = ScriptedInvestigator((), no_repair)
    tools = ScriptedTools({})
    record = run_incident("e2e-no-repair", CONTEXT, investigator, tools, Validator(),
                           configuration={})

    assert record.validation is None and record.authorization is None
    assert "validation_completed" not in [e.kind for e in record.trace]
