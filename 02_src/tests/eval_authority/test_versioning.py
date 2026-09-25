"""Tests for versioning.py — C4: version dispatch is explicit.

Mirrors requirement C4's own test spec verbatim: "a v1 artifact with a
v2 field fails to load rather than being upgraded."

Uses tmp_path throughout — never touches the real answer key files.
"""
import json

import pytest
from adii.evaluation.versioning import (
    CURRENT_VERSION,
    SCHEMA_FIELDS_BY_VERSION,
    load_versioned_answer_key,
)

MINIMAL_V1_KEY = {
    "schema_version": "1",
    "incident_id": "test-incident",
    "correct_disposition": "REPAIR",
}


def write(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class TestVersionIsRequired:
    def test_missing_schema_version_is_refused(self, tmp_path):
        key_path = write(tmp_path / "k.answer.json", {"incident_id": "x"})
        with pytest.raises(ValueError, match="missing"):
            load_versioned_answer_key(key_path)

    def test_present_schema_version_loads(self, tmp_path):
        key_path = write(tmp_path / "k.answer.json", MINIMAL_V1_KEY)
        loaded = load_versioned_answer_key(key_path)
        assert loaded == MINIMAL_V1_KEY


class TestUnknownVersionIsRefused:
    def test_an_unrecognised_version_string_is_refused_not_guessed(self, tmp_path):
        key_path = write(tmp_path / "k.answer.json", dict(MINIMAL_V1_KEY, schema_version="99"))
        with pytest.raises(ValueError, match="not one of the known versions"):
            load_versioned_answer_key(key_path)

    def test_a_non_string_version_is_still_just_an_unknown_version(self, tmp_path):
        key_path = write(tmp_path / "k.answer.json", dict(MINIMAL_V1_KEY, schema_version=1))
        with pytest.raises(ValueError, match="not one of the known versions"):
            load_versioned_answer_key(key_path)


class TestUnexpectedFieldsAreRefused:
    def test_v1_document_with_a_v2_only_field_fails_to_load(self, tmp_path):
        # This is C4's own reproduction case, made concrete: a document
        # declares v1 but carries a field that does not exist in v1's set
        # (as if lifted from a hypothetical v2). It must be refused, never
        # silently treated as "v1 plus an extra, presumably fine, field".
        key_path = write(tmp_path / "k.answer.json", dict(
            MINIMAL_V1_KEY,
            decisive_evidence_refs=["obs-0001"],  # imagine this is v2-only
        ))
        with pytest.raises(ValueError, match="not part of schema_version"):
            load_versioned_answer_key(key_path)

    def test_a_typo_field_name_is_caught_the_same_way_as_a_v2_field(self, tmp_path):
        key_path = write(tmp_path / "k.answer.json", dict(
            MINIMAL_V1_KEY,
            correct_dispositoin="REPAIR",  # typo
        ))
        with pytest.raises(ValueError, match="not part of schema_version"):
            load_versioned_answer_key(key_path)

    def test_error_names_every_unexpected_field_not_just_the_first(self, tmp_path):
        key_path = write(tmp_path / "k.answer.json", dict(
            MINIMAL_V1_KEY,
            extra_one="a",
            extra_two="b",
        ))
        with pytest.raises(ValueError) as exc_info:
            load_versioned_answer_key(key_path)
        assert "extra_one" in str(exc_info.value)
        assert "extra_two" in str(exc_info.value)


class TestFullFieldSetIsAccepted:
    def test_every_field_the_real_answer_keys_use_is_in_v1s_set(self, tmp_path):
        # A full-shaped v1 document, matching every field the real answer
        # keys in this directory actually use (repair_must_satisfy,
        # scoring_notes, test_fixtures, frozen, freeze_note, and so on) —
        # this must load cleanly, or v1's field set is wrong, not the key.
        full_document = dict(
            MINIMAL_V1_KEY,
            authored_by="Person C",
            authored_at="2026-09-15",
            source_of_truth="hand-authored",
            purpose="test coverage",
            correct_root_cause_id="SOME_CAUSE",
            root_cause_explanation="because reasons",
            repair_must_satisfy={"reference_repair_id": "X"},
            why_not_repair="n/a",
            why_not_no_repair="n/a",
            why_not_escalate="n/a",
            scoring_notes={},
            test_fixtures={},
            frozen=True,
            freeze_note="n/a",
        )
        key_path = write(tmp_path / "k.answer.json", full_document)
        loaded = load_versioned_answer_key(key_path)
        assert loaded == full_document


class TestNotADict:
    def test_a_json_array_is_refused_with_a_clear_message(self, tmp_path):
        key_path = tmp_path / "k.answer.json"
        key_path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_versioned_answer_key(key_path)


class TestModuleInvariants:
    def test_current_version_is_itself_a_known_version(self):
        assert CURRENT_VERSION in SCHEMA_FIELDS_BY_VERSION
