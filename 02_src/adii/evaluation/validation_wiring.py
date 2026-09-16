"""STEP 2 · Wire in the validator.

"A REPAIR only counts if the fix itself is independently accepted, too."

The rule itself already exists as scoring.score_repair_validation — this
module is STEP 2 made explicit: a named place that owns the fake
ValidationResult standing in for the real validation/ package, so the
swap to the real thing later is a one-line change, not a redesign.

Fake now, real later — same principle as judge.py's fake model provider.
validation/ is someone else's package to build; this module only defines
the shape score_decision expects from it and a fake that produces it.
"""
from __future__ import annotations

from typing import Protocol


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
