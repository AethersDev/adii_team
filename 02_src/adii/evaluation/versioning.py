"""C4: version dispatch is explicit.

requirement C4 — "the version is read first and dispatched on; an
unexpected field for the declared version is an error." A v1 answer key
carrying a v2-only field must fail to load, never be silently treated as
an implicit upgrade: "two readers now disagree about what the artifact
means, and neither is wrong" is exactly the failure mode this closes.

This module owns one version today, v1, and the exact field set that
version means. Adding v2 later means adding a second entry to
SCHEMA_FIELDS_BY_VERSION and a second branch in load_versioned_answer_key
— never widening v1's set to quietly accept what v2 will need.
"""
from __future__ import annotations

import json
from pathlib import Path

CURRENT_VERSION = "1"

# The complete field set schema_version "1" answer keys may carry. A field
# outside this set — whether a typo or a field that belongs to a version
# not yet declared — is refused at load time, not guessed at.
SCHEMA_FIELDS_BY_VERSION = {
    "1": frozenset({
        "schema_version",
        "incident_id",
        "authored_by",
        "authored_at",
        "source_of_truth",
        "purpose",
        "correct_disposition",
        "correct_root_cause_id",
        "root_cause_explanation",
        "repair_must_satisfy",
        "why_not_repair",
        "why_not_no_repair",
        "why_not_escalate",
        "scoring_notes",
        "test_fixtures",
        "frozen",
        "freeze_note",
    }),
}

# Required fields and disposition enum, kept in lockstep with
# answer_key.schema.json's own "required" and "correct_disposition.enum" —
# test_schema_matches_code.py (C5) is what catches the two drifting apart.
REQUIRED_FIELDS_BY_VERSION = {
    "1": frozenset({"schema_version", "incident_id", "correct_disposition"}),
}

VALID_DISPOSITIONS = ("REPAIR", "NO_REPAIR", "ESCALATE")


def load_versioned_answer_key(path: Path) -> dict:
    """Load an answer key's JSON only after its declared version is checked.

    Raises ValueError if:
      - "schema_version" is missing entirely (every answer key must declare one);
      - the declared version is not one this module knows how to read;
      - the document carries any field outside that version's field set.

    Does not check digests — that is freeze.py's job (C2). This function
    is about what the *shape* of the document is allowed to mean, not
    whether these particular bytes were the ones frozen.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(
            f"{path.name}: answer key must be a JSON object, got {type(data).__name__}"
        )

    if "schema_version" not in data:
        raise ValueError(
            f"{path.name}: missing \"schema_version\" — every answer key must declare "
            f"which version's field set it uses, explicitly, so a reader never has to guess"
        )

    version = data["schema_version"]
    if version not in SCHEMA_FIELDS_BY_VERSION:
        known = sorted(SCHEMA_FIELDS_BY_VERSION)
        raise ValueError(
            f"{path.name}: schema_version {version!r} is not one of the known versions {known} — "
            f"an unrecognised version is refused, never guessed at as the closest known one"
        )

    allowed_fields = SCHEMA_FIELDS_BY_VERSION[version]
    unexpected = set(data) - allowed_fields
    if unexpected:
        raise ValueError(
            f"{path.name}: field(s) {sorted(unexpected)} are not part of schema_version "
            f"{version!r}'s field set — a field from a later version (or a typo) is an error, "
            f"never an implicit upgrade"
        )

    missing = REQUIRED_FIELDS_BY_VERSION[version] - set(data)
    if missing:
        raise ValueError(f"{path.name}: missing required field(s) {sorted(missing)}")

    if not isinstance(data["incident_id"], str) or not data["incident_id"]:
        raise ValueError(
            f"{path.name}: \"incident_id\" must be a non-empty string, "
            f"got {data['incident_id']!r}"
        )

    if data["correct_disposition"] not in VALID_DISPOSITIONS:
        raise ValueError(
            f"{path.name}: \"correct_disposition\" must be one of {VALID_DISPOSITIONS}, "
            f"got {data['correct_disposition']!r}"
        )

    return data
