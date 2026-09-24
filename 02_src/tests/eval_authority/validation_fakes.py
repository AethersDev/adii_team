"""Test doubles for the scoring tests: the shape score_decision takes a validator in, a
stand-in that answers it without rebuilding anything, and an adapter from the real validator
to that shape. Moved here from evaluation/validation_wiring.py and validation/validator.py
by the audit of 24 Sep: none of it is the evaluated system — the runtime hands the real
Validator a REPAIR, and the evaluation scores the record it wrote.
"""
from __future__ import annotations

from typing import Protocol

from adii.contracts import Disposition, IncidentContext, InvestigationDecision
from adii.validation.validator import Validator


class ValidatorProvider(Protocol):
    """Whatever validation/ eventually is, this is the shape score_decision needs.

    A real validator/ implementation rebuilds from frozen inputs and
    returns ACCEPT/REJECT with reasons — see 02_src/adii/validation/README.md.
    This module only needs it to answer one call.
    """

    def __call__(self, decision: dict) -> dict:
        """Given a REPAIR decision, return a ValidationResult-shaped dict:
        {"accepted": bool, "report": str, "checks_run": list[str]}.
        """
        ...


def fake_validator_accepts_everything_structurally_sound(decision: dict) -> dict:
    """Stands in for validation/ before it exists.

    Deliberately simple and honest about being fake: it accepts a repair
    only if the patch still divides amount_cents by 100 exactly once — the
    same repair_must_satisfy rule the answer key states, applied here as a
    stub so score_decision has something real to call today.

    This is NOT how the real validator will decide — the real one rebuilds
    from frozen inputs and never inspects the SQL text like this. It exists
    only so the wiring (score_decision -> validator -> ValidationResult) is
    provably correct before validation/ is built.
    """
    patch = decision.get("patch") or {}
    patch_text = " ".join(patch.values())

    divides_once = "amount_cents / 100" in patch_text and "/ 100.0) * 100" not in patch_text

    if divides_once:
        return {
            "accepted": True,
            "report": "fake validator: single conversion detected, structurally sound.",
            "checks_run": ["fake_structural_check"],
        }
    return {
        "accepted": False,
        "report": "fake validator: patch does not look like a single, correct conversion.",
        "checks_run": ["fake_structural_check"],
    }


def get_validation_for(decision: dict, validator: ValidatorProvider) -> dict | None:
    """The one thing STEP 2 promises: a REPAIR decision always goes through
    a validator before scoring continues. Non-REPAIR dispositions have
    nothing to validate — see repair_must_satisfy.validation_requirement.
    """
    if decision["disposition"] != "REPAIR":
        return None
    return validator(decision)


def as_dict_validator(context: IncidentContext):
    """Adapt `validate()` to the `ValidatorProvider` shape
    (`decision: dict -> {"accepted", "report", "checks_run", "reason_code"}`), for offline
    scoring over decisions held as dicts; the runtime path uses `Validator` directly."""
    def provider(decision: dict) -> dict:
        real_decision = InvestigationDecision(
            disposition=Disposition(decision["disposition"]),
            root_cause_id=decision.get("root_cause_id"),
            root_cause_summary=decision.get("root_cause_summary", ""),
            repair_id=decision.get("repair_id"),
            patch=decision.get("patch") or {},
        )
        result = Validator().validate(context, real_decision)
        return {"accepted": result.accepted, "report": result.report,
                "checks_run": list(result.checks_run), "reason_code": result.reason_code}
    return provider
