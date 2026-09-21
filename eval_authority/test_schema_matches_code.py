"""C5: a published schema and the validating code are checked against each
other by a test.

CONFORMANCE.md C5 — "the published schema is the one the validator uses,
or a test asserts they accept and reject exactly the same documents...
a corpus of valid and invalid documents produces identical verdicts from
the published schema and the code path."

versioning.py's load_versioned_answer_key is the code path. This module
does not import it as its schema source (it hand-checks schema_version
and a fixed field set) — so this test is the "or" branch of C5: a shared
corpus, run through both, asserting the same accept/reject verdict every
time. If they ever drift, this is the test that goes red.
"""
import json

import pytest

from schema_validator import is_valid
from versioning import load_versioned_answer_key

with open("answer_key.schema.json", encoding="utf-8") as f:
    PUBLISHED_SCHEMA = json.load(f)


VALID_MINIMAL = {
    "schema_version": "1",
    "incident_id": "x",
    "correct_disposition": "REPAIR",
}

VALID_FULL = {
    "schema_version": "1",
    "incident_id": "demo-learning-001",
    "authored_by": "Person C",
    "authored_at": "2026-09-15",
    "source_of_truth": "hand-authored",
    "purpose": "test",
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "SOME_CAUSE",
    "root_cause_explanation": "because",
    "repair_must_satisfy": {"reference_repair_id": "X"},
    "why_not_repair": "n/a",
    "why_not_no_repair": "n/a",
    "why_not_escalate": "n/a",
    "scoring_notes": {},
    "test_fixtures": {},
    "frozen": True,
    "freeze_note": "n/a",
}

VALID_NULL_ROOT_CAUSE = dict(VALID_MINIMAL, correct_root_cause_id=None)  # ESCALATE case

# Each entry: (label, document). "valid" ones must pass both checkers;
# "invalid" ones must fail both.
VALID_DOCUMENTS = [
    ("minimal", VALID_MINIMAL),
    ("full", VALID_FULL),
    ("null_root_cause_for_escalate", VALID_NULL_ROOT_CAUSE),
    ("no_repair_disposition", dict(VALID_MINIMAL, correct_disposition="NO_REPAIR")),
    ("escalate_disposition", dict(VALID_MINIMAL, correct_disposition="ESCALATE")),
]

INVALID_DOCUMENTS = [
    ("missing_schema_version", {"incident_id": "x", "correct_disposition": "REPAIR"}),
    ("missing_incident_id", {"schema_version": "1", "correct_disposition": "REPAIR"}),
    ("missing_correct_disposition", {"schema_version": "1", "incident_id": "x"}),
    ("wrong_schema_version", dict(VALID_MINIMAL, schema_version="2")),
    ("bogus_disposition", dict(VALID_MINIMAL, correct_disposition="MAYBE")),
    ("empty_incident_id", dict(VALID_MINIMAL, incident_id="")),
    ("unexpected_field", dict(VALID_MINIMAL, decisive_evidence_refs=["obs-1"])),
    ("typo_field", dict(VALID_MINIMAL, correct_dispositoin="REPAIR")),
]


def code_path_accepts(document: dict, tmp_path) -> bool:
    key_path = tmp_path / "doc.answer.json"
    key_path.write_text(json.dumps(document), encoding="utf-8")
    try:
        load_versioned_answer_key(key_path)
        return True
    except ValueError:
        return False


class TestPublishedSchemaAndCodeAgree:
    @pytest.mark.parametrize("label,document", VALID_DOCUMENTS)
    def test_valid_document_accepted_by_both(self, label, document, tmp_path):
        assert is_valid(document, PUBLISHED_SCHEMA), f"{label}: schema rejected a document it should accept"
        assert code_path_accepts(document, tmp_path), f"{label}: code rejected a document it should accept"

    @pytest.mark.parametrize("label,document", INVALID_DOCUMENTS)
    def test_invalid_document_rejected_by_both(self, label, document, tmp_path):
        assert not is_valid(document, PUBLISHED_SCHEMA), f"{label}: schema accepted a document it should reject"
        assert not code_path_accepts(document, tmp_path), f"{label}: code accepted a document it should reject"

    def test_every_real_answer_key_in_this_directory_is_schema_valid(self):
        # The published schema must actually describe the real files, not
        # just a hand-picked corpus — this is the drift check C5 exists for.
        import glob
        real_files = glob.glob("*.answer.json") + glob.glob("fixtures/*.answer.json")
        assert real_files, "expected at least one real answer key file to check"
        for path in real_files:
            with open(path, encoding="utf-8") as f:
                document = json.load(f)
            errors = []
            from schema_validator import validate_against_schema
            errors = validate_against_schema(document, PUBLISHED_SCHEMA)
            assert not errors, f"{path} fails the published schema: {errors}"
