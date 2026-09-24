"""Scoring a decision against its frozen answer key.

The disposition first (REPAIR, NO_REPAIR or ESCALATE, right or wrong), then for a repair
the validator's verdict and the key's reference, routed deterministically where the key
settles it and to the judge where only a judgement can (decide_route, score_decision).
"""
from __future__ import annotations

VALID_DISPOSITIONS = ("REPAIR", "NO_REPAIR", "ESCALATE")


def _require_fields(obj: dict, fields: tuple, what: str) -> None:
    if not isinstance(obj, dict):
        raise ValueError(f"{what} must be a dict, got {type(obj).__name__}: {obj!r}")
    missing = [f for f in fields if f not in obj]
    if missing:
        raise ValueError(f"{what} is missing required field(s) {missing}: {obj!r}")


def score_disposition(actual_disposition: str, answer_key: dict) -> str:
    """Compare a decision's disposition against the answer key's correct one.

    Returns "correct" or "incorrect". Nothing in between at this step —
    routing to a judge agent only becomes meaningful once repair matching
    exists, in a later step.

    Raises ValueError if actual_disposition is not one of the three
    contract dispositions — a typo or a malformed InvestigationDecision
    (e.g. "REPAIRED", None, "") must fail loudly here, not silently score
    as an ordinary wrong answer indistinguishable from a real ESCALATE-
    when-REPAIR-was-correct miss.
    """
    if actual_disposition not in VALID_DISPOSITIONS:
        raise ValueError(
            f"actual_disposition must be one of {VALID_DISPOSITIONS}, got {actual_disposition!r}"
        )
    _require_fields(answer_key, ("correct_disposition",), "answer_key")

    correct = answer_key["correct_disposition"]
    if actual_disposition == correct:
        return "correct"
    return "incorrect"


def score_repair_validation(disposition: str, validation: dict | None) -> str:
    """A REPAIR only counts if the repair itself was independently accepted.

    A right diagnosis with a rejected repair is a failure, not a partial
    success — this is repair_must_satisfy.validation_requirement in the
    answer key, checked here as its own step, before any repair-content
    comparison happens.

    Non-REPAIR dispositions have nothing to validate, so this check does
    not apply to them: "correct" here means "not disqualified by this
    rule", not "the disposition itself was right".

    Raises ValueError if disposition is REPAIR and validation is a dict
    missing "accepted" — a ValidationResult without that field is
    malformed, not merely "not accepted".
    """
    if disposition != "REPAIR":
        return "correct"
    if validation is None:
        return "incorrect"
    _require_fields(validation, ("accepted",), "validation")
    if validation["accepted"]:
        return "correct"
    return "incorrect"


def decide_route(decision: dict, validation: dict | None, answer_key: dict) -> str:
    """Combine the two checks above and decide what happens to this decision.

    Returns one of:
      "correct"            — settled here, no model call needed
      "incorrect"           — settled here, no model call needed
      "needs_judge_review"  — disposition and validation both passed, but the
                              root_cause_id or the repair itself differs from
                              the reference and only a judge agent can tell
                              alternative from error

    This is the routing logic the whole two-tier design rests on: the
    deterministic scorer must be the one deciding whether a case is even
    ambiguous, not the judge agent guessing whether it should look.

    root_cause_id is checked, not just repair_id: every answer key's own
    scoring_notes.root_cause_match says a root_cause_id mismatch must route
    to the judge rather than auto-fail, since a semantically equivalent
    root_cause_summary under a different id can still be correct. Auto-passing
    on an exact repair_id match while ignoring a root_cause_id mismatch would
    let a decision that reached the right patch by the wrong diagnosis slip
    through as "correct" with no judge ever looking at it.

    Raises ValueError if decision has no "disposition", or — once a REPAIR
    actually needs the reference comparison — if answer_key is missing
    "correct_root_cause_id" or answer_key["repair_must_satisfy"] has no
    "reference_repair_id". These are contract violations that must surface
    immediately rather than as a bare KeyError from a real A/B run.
    """
    _require_fields(decision, ("disposition",), "decision")
    disposition = decision["disposition"]

    if score_disposition(disposition, answer_key) == "incorrect":
        return "incorrect"

    if score_repair_validation(disposition, validation) == "incorrect":
        return "incorrect"

    if disposition != "REPAIR":
        return "correct"

    _require_fields(answer_key, ("correct_root_cause_id", "repair_must_satisfy"), "answer_key")
    _require_fields(
        answer_key["repair_must_satisfy"],
        ("reference_repair_id",),
        "answer_key['repair_must_satisfy']",
    )

    root_cause_matches = decision.get("root_cause_id") == answer_key["correct_root_cause_id"]
    reference_repair_id = answer_key["repair_must_satisfy"]["reference_repair_id"]
    repair_matches = decision.get("repair_id") == reference_repair_id

    if root_cause_matches and repair_matches:
        return "correct"

    return "needs_judge_review"


def score_decision(decision: dict, validation: dict | None, answer_key: dict, judge=None) -> dict:
    """The complete Step 1 answer: given a call, say if it was right.

    Runs the deterministic route first. If it settles the case, the judge
    is never called — this is the whole point of the two-tier design: the
    cheap, reproducible check is the ground floor, and a model call only
    happens for the cases it cannot settle alone.

    `judge` is optional so this stays callable — and testable — before any
    judge agent exists; a "needs_judge_review" case with no judge supplied
    is reported as unresolved rather than silently guessed at.

    Returns a dict with at least:
      "verdict": "correct" | "incorrect" | "unresolved"
      "settled_by": "deterministic" | "judge" | "none"
    plus "reasoning" when the judge was the one who settled it.
    """
    route = decide_route(decision, validation, answer_key)

    if route != "needs_judge_review":
        return {"verdict": route, "settled_by": "deterministic"}

    if judge is None:
        return {"verdict": "unresolved", "settled_by": "none"}

    judged = judge(decision, validation, answer_key)
    return {
        "verdict": judged["verdict"],
        "settled_by": "judge",
        "reasoning": judged["reasoning"],
    }
