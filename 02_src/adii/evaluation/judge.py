"""Step 2 unit: settle a "needs_judge_review" case.

Only called when the deterministic scorer in scoring.py could not settle a
case alone — right disposition, an accepted repair, but a repair_id that
differs from the answer key's reference. The judge decides whether that
difference is a genuine error or an acceptable alternative reaching the
same correct root cause.

The one rule this module must never break: it judges the DECISION against
the answer key. It never re-opens whether the answer key itself is right.
"""
from __future__ import annotations

from typing import Protocol

JUDGE_PROMPT_TEMPLATE = """You are an independent judge scoring one ADII investigation \
decision against a fixed answer key. The answer key is not in question — you are \
deciding only whether THIS decision counts as correct against it.

You are only ever called when the disposition matched and, if a repair was proposed, \
that repair was independently validated and accepted. The only open question is \
whether a difference from the reference — in root_cause_id, repair_id, or both — is a \
genuine error or a different-but-equally-valid path to the same correct outcome. A \
different repair_id or root_cause_id is NOT automatically wrong: judge the substance \
against the conditions below, not the label.

INCIDENT: {incident_id}

ANSWER KEY
  correct disposition:   {correct_disposition}
  correct root cause id: {correct_root_cause_id}
  root cause, in full:   {root_cause_explanation}
  reference repair id:   {reference_repair_id}
  what the reference repair actually does: {reference_patch_effect}
  what ANY accepted repair must satisfy (an alternative is fine if it meets these):
{repair_requirements}

WHAT THE INVESTIGATOR ACTUALLY DECIDED
  disposition:        {actual_disposition}
  root_cause_id:       {actual_root_cause_id}
  root_cause_summary:  {actual_root_cause_summary}
  repair_id:           {actual_repair_id}
  patch:               {actual_patch}

INDEPENDENT VALIDATION OF THAT REPAIR
  accepted: {validation_accepted}
  report:   {validation_report}

HOW TO JUDGE EACH FIELD THAT DIFFERS
- root_cause_id differs from the reference: compare actual_root_cause_summary against \
"root cause, in full" above. If they describe the same underlying defect in different \
words or granularity, the root cause counts as correct despite the id mismatch. Only \
call it wrong if the summary describes a materially different cause.
- repair_id differs from the reference: check actual patch against every line under \
"what ANY accepted repair must satisfy". All of them must hold — meeting some but not \
all is still incorrect. A repair that reaches the same effect as \
"what the reference repair actually does" through different syntax or a different \
tool call is correct; a repair that reaches a different effect is not, even if it was \
independently accepted (validation checks structural soundness, not whether it is the \
same fix).

WORKED EXAMPLE (not this case — calibration only)
  reference repair divides a doubly-converted amount by 100 once (undoing one of two \
conversions). An alternative that casts to a different numeric type but still divides \
by 100 exactly once, preserves row counts, and touches no other column: correct — same \
effect, different syntax. An alternative that instead multiplies by 100 to "cancel out" \
the second conversion: incorrect — it reaches a different, wrong effect, regardless of \
matching root_cause_id or passing structural validation.

QUESTION
Given everything above, does this decision count as correct against the answer key — \
right root cause (by substance, not just id) and, if REPAIR, a repair that satisfies \
every condition above (by substance, not just id)?

Answer with a verdict of exactly "correct" or "incorrect" as the first word, followed \
by one sentence of reasoning that names which specific condition was met or violated. \
Do not question whether the answer key's correct_disposition, correct_root_cause_id, \
or reference_repair_id is itself right — those are fixed and outside your scope.
"""


REQUIRED_DECISION_FIELDS = ("disposition",)
REQUIRED_VALIDATION_FIELDS = ("accepted", "report")
REQUIRED_ANSWER_KEY_FIELDS = (
    "incident_id",
    "correct_disposition",
    "correct_root_cause_id",
    "root_cause_explanation",
    "repair_must_satisfy",
)
REQUIRED_REPAIR_RULE_FIELDS = ("reference_repair_id", "alternative_repairs_are_acceptable_if")


def _require_fields(obj: dict, fields: tuple, what: str) -> None:
    if not isinstance(obj, dict):
        raise ValueError(f"{what} must be a dict, got {type(obj).__name__}: {obj!r}")
    missing = [f for f in fields if f not in obj]
    if missing:
        raise ValueError(f"{what} is missing required field(s) {missing}: {obj!r}")


def build_judge_prompt(decision: dict, validation: dict, answer_key: dict) -> str:
    """Assemble the judge's prompt from a decision, its validation, and the key.

    A pure function on purpose: the prompt is fully determined by its
    inputs, so it can be unit-tested without calling any model.

    Raises ValueError with a specific field name when decision, validation,
    or answer_key is missing something the prompt needs — a mismatch
    between judge.py and a real InvestigationRun's actual shape should be
    obvious immediately, not a bare KeyError three frames down.
    """
    _require_fields(decision, REQUIRED_DECISION_FIELDS, "decision")
    _require_fields(validation, REQUIRED_VALIDATION_FIELDS, "validation")
    _require_fields(answer_key, REQUIRED_ANSWER_KEY_FIELDS, "answer_key")
    _require_fields(
        answer_key["repair_must_satisfy"],
        REQUIRED_REPAIR_RULE_FIELDS,
        "answer_key['repair_must_satisfy']",
    )

    repair_rules = answer_key["repair_must_satisfy"]
    repair_requirements = "\n".join(
        f"  - {condition}" for condition in repair_rules["alternative_repairs_are_acceptable_if"]
    )
    return JUDGE_PROMPT_TEMPLATE.format(
        incident_id=answer_key["incident_id"],
        correct_disposition=answer_key["correct_disposition"],
        correct_root_cause_id=answer_key["correct_root_cause_id"],
        root_cause_explanation=answer_key["root_cause_explanation"],
        reference_repair_id=repair_rules["reference_repair_id"],
        reference_patch_effect=repair_rules.get("reference_patch_effect"),
        repair_requirements=repair_requirements,
        actual_disposition=decision["disposition"],
        actual_root_cause_id=decision.get("root_cause_id"),
        actual_root_cause_summary=decision.get("root_cause_summary"),
        actual_repair_id=decision.get("repair_id"),
        actual_patch=decision.get("patch"),
        validation_accepted=validation["accepted"],
        validation_report=validation["report"],
    )


class JudgeProvider(Protocol):
    """Whatever calls a model must implement just this."""

    def __call__(self, prompt: str) -> str:
        """Return the model's raw text reply to the prompt."""
        ...


def parse_judge_reply(reply: str) -> tuple[str, str]:
    """Split a judge reply into ("correct"|"incorrect", reasoning).

    Kept separate from the provider call so the parsing logic itself is
    testable against canned replies, independent of any model.
    """
    if reply is None:
        raise ValueError("judge reply was None — provider returned no text")

    text = reply.strip()
    if not text:
        raise ValueError("judge reply was empty after stripping whitespace")

    lowered = text.lower()
    # A word-boundary check, not a bare prefix check: "correct" must be
    # followed by whitespace or punctuation, not more letters — otherwise
    # "Correctish" or "Incorrectly-worded, actually correct" silently
    # parses as a clean verdict instead of failing loudly.
    if lowered == "correct" or lowered.startswith(
        ("correct ", "correct,", "correct.", "correct:", "correct;", "correct-", "correct—")
    ):
        verdict = "correct"
    elif lowered == "incorrect" or lowered.startswith(
        ("incorrect ", "incorrect,", "incorrect.", "incorrect:", "incorrect;", "incorrect-",
         "incorrect—")
    ):
        verdict = "incorrect"
    else:
        raise ValueError(f"judge reply did not start with a clean verdict: {text!r}")

    reasoning = text[len(verdict):].lstrip(" ,.:;-—").strip()
    return verdict, reasoning


def judge_repair(
    decision: dict, validation: dict, answer_key: dict, provider: JudgeProvider
) -> dict:
    """Run the full judge step: build the prompt, call the provider, parse the reply.

    Returns {"verdict": "correct"|"incorrect", "reasoning": str, "prompt": str} —
    the prompt is included so a run can be replayed and audited later.
    """
    prompt = build_judge_prompt(decision, validation, answer_key)
    reply = provider(prompt)
    verdict, reasoning = parse_judge_reply(reply)
    return {"verdict": verdict, "reasoning": reasoning, "prompt": prompt}
