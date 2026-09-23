"""C3: authorities that freeze at different times must be different artifacts.

CONFORMANCE.md C3, and the incident it is drawn from in
02_src/docs/inherited/AUTHORITY_LIFECYCLE.md: an answer key (disposition,
root cause, repair) and a grounding key (which tool calls a correct
decision must actually have made) freeze at different times. The answer
key is frozen the moment a scenario is first scored. The grounding key is
authored later, once it is known what grounding needs to measure — often
only once real tool call shapes exist. Merging them into one file means
the whole bundle re-freezes the moment the later part is ready, silently
re-dating the answer key that was already committed.

The fix from AUTHORITY_LIFECYCLE.md, applied here: two files, hash-bound.
A grounding key names the answer key it belongs to and carries that
answer key's frozen SHA-256 digest (from freeze.py, C2). Loading a
grounding key re-verifies that digest against the answer key's current
frozen digest — if they disagree, the pairing is refused, not guessed at.

What "decisive evidence" means, concretely, here: a list of required tool
calls, each a (tool name, a substring one of its text arguments must contain) pair.
It is checked against the trace the runtime archived, as the record holds it: a
predicate is observed only when a matching call was answered OK, so a refused or
failed call observes nothing, and its evidence is the evidence_id the tool layer
minted on that result. Whether the decision cited it is read from the decision's
evidence_refs (trace contract row 3). Observed and cited are dimensions beside the
category, never inside it.
"""
from __future__ import annotations

import json
from pathlib import Path

from .freeze import compute_digest, digest_path_for

GROUNDING_SCHEMA_VERSION = "1"

REQUIRED_GROUNDING_FIELDS = frozenset({
    "schema_version",
    "answer_key_filename",
    "answer_key_digest",
    "required_tool_calls",
})


def _require_answer_key_is_frozen(answer_key_path: Path) -> str:
    digest_path = digest_path_for(answer_key_path)
    if not digest_path.exists():
        raise FileNotFoundError(
            f"{answer_key_path.name} has no frozen digest ({digest_path.name} not found) — "
            f"a grounding key can only be authored against an answer key that is already "
            f"frozen (C2), so the pairing has something stable to bind to"
        )
    return digest_path.read_text(encoding="utf-8").strip()


def build_grounding_key(answer_key_path: Path, required_tool_calls: list[dict]) -> dict:
    """Construct a grounding key document bound to a frozen answer key.

    required_tool_calls: a list of {"tool": str, "argument_contains": str}
    predicates. A decision's trace satisfies one predicate if it contains
    a tool_requested call for that tool whose arguments (stringified)
    contain that substring.

    Raises FileNotFoundError if the named answer key is not itself frozen
    yet — grounding is authored against a stable answer key, never a
    moving one, so the freeze order in AUTHORITY_LIFECYCLE.md holds.
    """
    answer_key_path = Path(answer_key_path)
    answer_key_digest = _require_answer_key_is_frozen(answer_key_path)

    for predicate in required_tool_calls:
        missing = {"tool", "argument_contains"} - set(predicate)
        if missing:
            raise ValueError(
                f"tool call predicate {predicate!r} is missing field(s) {sorted(missing)}"
            )

    return {
        "schema_version": GROUNDING_SCHEMA_VERSION,
        "answer_key_filename": answer_key_path.name,
        "answer_key_digest": answer_key_digest,
        "required_tool_calls": required_tool_calls,
    }


def load_grounding_key(grounding_key_path: Path, answer_key_dir: Path | None = None) -> dict:
    """Load a grounding key only if it still agrees with its answer key.

    Six ways this refuses to load, matching AUTHORITY_LIFECYCLE.md's own
    list almost verbatim:
      - the file is missing a required field
      - the named answer key file does not exist
      - the named answer key is not itself frozen (no .sha256 beside it)
      - the answer key's current digest does not match answer_key_digest
        (the answer key changed after this grounding key was authored)
      - the grounding key's own schema_version is not recognised
      - (implicitly) a grounding key naming the wrong answer key filename
        is simply a grounding key for a different scenario, caught by the
        digest check above disagreeing

    None of these is a warning — every one raises.
    """
    grounding_key_path = Path(grounding_key_path)
    data = json.loads(grounding_key_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"{grounding_key_path.name}: grounding key must be a JSON object")

    missing = REQUIRED_GROUNDING_FIELDS - set(data)
    if missing:
        raise ValueError(f"{grounding_key_path.name}: missing required field(s) {sorted(missing)}")

    if data["schema_version"] != GROUNDING_SCHEMA_VERSION:
        raise ValueError(
            f"{grounding_key_path.name}: schema_version {data['schema_version']!r} is not "
            f"the known grounding schema version {GROUNDING_SCHEMA_VERSION!r}"
        )

    answer_key_dir = (
        Path(answer_key_dir) if answer_key_dir is not None else grounding_key_path.parent
    )
    answer_key_path = answer_key_dir / data["answer_key_filename"]

    if not answer_key_path.exists():
        raise FileNotFoundError(
            f"{grounding_key_path.name} names answer key {data['answer_key_filename']!r}, "
            f"which does not exist at {answer_key_path}"
        )

    current_digest = compute_digest(answer_key_path)
    if current_digest != data["answer_key_digest"]:
        raise ValueError(
            f"{grounding_key_path.name} is bound to {data['answer_key_filename']} at digest "
            f"{data['answer_key_digest']}, but that file's current digest is {current_digest} — "
            f"the answer key changed since this grounding key was authored against it, or this "
            f"grounding key was never actually paired with this exact answer key version"
        )

    return data


def check_grounding(trace: list[dict], grounding_key: dict,
                    evidence_refs: list[str] | tuple[str, ...] = ()) -> dict:
    """The grounding key's predicates read against a run's archived trace.

    trace: the record's `trace`, events of {"kind", "payload"} exactly as archived. A
    predicate is satisfied by a `tool_call` naming its tool, with a text argument that
    contains `argument_contains` (compared case-insensitively, since SQL is), whose result
    was OK; the evidence ids are those results'. A call that was refused or failed
    observed nothing, whatever it asked for.

    Returns {"observed": every predicate satisfied, "cited": every predicate has one of
    its evidence ids among `evidence_refs`, "missing": the predicates never observed}.
    """
    answered = {e["payload"].get("call_id"): e["payload"] for e in trace
                if e.get("kind") == "tool_result" and e["payload"].get("status") == "OK"}
    calls = [e["payload"] for e in trace if e.get("kind") == "tool_call"]
    cited_refs = set(evidence_refs)
    missing, uncited = [], []
    for predicate in grounding_key["required_tool_calls"]:
        needle = predicate["argument_contains"].casefold()
        ids = {(answered[call["call_id"]].get("content") or {}).get("evidence_id")
               for call in calls
               if call.get("name") == predicate["tool"] and call.get("call_id") in answered
               and any(isinstance(value, str) and needle in value.casefold()
                       for value in (call.get("arguments") or {}).values())}
        if not ids:
            missing.append(predicate)
        if not ids & cited_refs:
            uncited.append(predicate)
    return {"observed": not missing, "cited": not uncited, "missing": missing}
