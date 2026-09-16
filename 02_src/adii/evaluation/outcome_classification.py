"""D-17 / D-19: classify a scored decision into the six report categories.

build_plan.md M10 and plan_telemetry.md D-19 both name the same six
categories, verbatim, as the required shape of C's scoring output for the
final report: "success, failure, false repair, correct abstention,
unnecessary escalation and repair rejection". D-19 says explicitly this
comes "from C's scoring output" — the categories are a team decision
already made; this module is C's job of computing them.

This is a layer ON TOP of scoring.score_decision, never a replacement for
it: score_decision's correct/incorrect/unresolved verdict is unchanged
and still what every existing test in this directory exercises.
classify_outcome takes that verdict plus the same (decision, validation,
answer_key) inputs and refines "incorrect" into which of the specific
failure shapes it was — because a single "failure" bucket cannot tell a
missed real defect from a proposed-but-rejected repair, and a grid report
that cannot tell them apart cannot say what to fix next.

The six required categories are always one of the values in CATEGORIES.
A `sub_kind` rides alongside for cases the six categories alone would
blur together (see FailureSubKind) — this is additive detail, never a
seventh category and never a disagreement with D-19's six names.
"""
from __future__ import annotations

CATEGORIES = (
    "success",
    "failure",
    "false_repair",
    "correct_abstention",
    "unnecessary_escalation",
    "repair_rejection",
)


class FailureSubKind:
    """Named reasons a "failure" is a failure, for cases the six official
    categories alone cannot distinguish. Never returned as the primary
    category — only ever in the "sub_kind" field alongside "failure".
    """

    MISSED_DEFECT = "missed_defect"  # said NO_REPAIR; a real defect existed
    UNWARRANTED_REPAIR = "unwarranted_repair"  # said REPAIR; nothing was wrong
    UNRESOLVED = "unresolved"  # needed a judge call that was never made


def classify_outcome(decision: dict, validation: dict | None, answer_key: dict, judge=None) -> dict:
    """Classify a decision into one of the six M10/D-19 report categories.

    Returns {"category": one of CATEGORIES, "sub_kind": str | None,
    "verdict": ..., "settled_by": ...} — the last two are score_decision's
    own fields, passed through unchanged. `category` is always one of the
    six required names; `sub_kind` is set only for "failure" cases whose
    shape is worth telling apart in the grid report (see FailureSubKind)
    and is None otherwise.

    This function does not re-implement any scoring rule — every
    correct/incorrect decision comes from scoring.decide_route via
    scoring.score_decision, called exactly once. It only adds the
    category label on top of that existing, unchanged verdict.
    """
    from .scoring import score_decision

    actual_disposition = decision["disposition"]
    correct_disposition = answer_key["correct_disposition"]
    scored = score_decision(decision, validation, answer_key, judge=judge)
    verdict = scored["verdict"]
    settled_by = scored["settled_by"]

    def result(category: str, sub_kind: str | None) -> dict:
        return {
            "category": category,
            "sub_kind": sub_kind,
            "verdict": verdict,
            "settled_by": settled_by,
        }

    if verdict == "unresolved":
        return result("failure", FailureSubKind.UNRESOLVED)

    if verdict == "correct":
        if actual_disposition == "ESCALATE":
            return result("correct_abstention", None)
        return result("success", None)

    # verdict == "incorrect" from here on.
    if actual_disposition == "ESCALATE":
        return result("unnecessary_escalation", None)

    if actual_disposition == "REPAIR":
        if correct_disposition != "REPAIR":
            return result("failure", FailureSubKind.UNWARRANTED_REPAIR)

        root_cause_matches = decision.get("root_cause_id") == answer_key.get(
            "correct_root_cause_id"
        )
        if not root_cause_matches:
            return result("false_repair", None)

        # Root cause matched, disposition matched REPAIR, yet the verdict
        # is incorrect: the only remaining reason decide_route rejects a
        # REPAIR with a matching root cause is a validation that never
        # accepted it (see scoring.score_repair_validation).
        return result("repair_rejection", None)

    # actual_disposition == "NO_REPAIR" and verdict == "incorrect":
    # the correct call was something else — most importantly, a real
    # defect this decision said nothing was wrong with.
    if correct_disposition == "REPAIR":
        return result("failure", FailureSubKind.MISSED_DEFECT)

    return result("failure", None)
