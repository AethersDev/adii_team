"""Tests for freeze.py — C2: answer keys are frozen by hash and never edited.

Mirrors CONFORMANCE.md C2's own test spec verbatim:
  "a mutated key fails to load; loading verifies the digest rather than
  trusting the filename; a correction produces a new artifact and the old
  one still loads."

Uses tmp_path fixtures throughout — never touches the real answer key files
in this directory, so this suite cannot accidentally freeze or corrupt them.
"""
import json

import pytest

from adii.evaluation.freeze import (
    compute_digest,
    digest_path_for,
    freeze_answer_key,
    load_frozen_answer_key,
)

SAMPLE_KEY = {
    "incident_id": "test-incident",
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "TEST_CAUSE",
}


def write_key(path, data=None):
    path.write_text(json.dumps(data or SAMPLE_KEY, indent=2), encoding="utf-8")
    return path


class TestFreezing:
    def test_freezing_writes_a_digest_file_next_to_the_key(self, tmp_path):
        key_path = write_key(tmp_path / "incident-001.answer.json")
        digest = freeze_answer_key(key_path)

        digest_path = digest_path_for(key_path)
        assert digest_path.exists()
        assert digest_path.read_text(encoding="utf-8").strip() == digest

    def test_digest_matches_a_plain_sha256_of_the_exact_bytes(self, tmp_path):
        key_path = write_key(tmp_path / "incident-001.answer.json")
        digest = freeze_answer_key(key_path)
        assert digest == compute_digest(key_path)
        assert len(digest) == 64  # hex sha256

    def test_freezing_twice_is_refused_not_silently_repinned(self, tmp_path):
        key_path = write_key(tmp_path / "incident-001.answer.json")
        freeze_answer_key(key_path)

        with pytest.raises(FileExistsError, match="already frozen"):
            freeze_answer_key(key_path)


class TestLoadingAFrozenKey:
    def test_unfrozen_key_refuses_to_load(self, tmp_path):
        key_path = write_key(tmp_path / "incident-001.answer.json")
        with pytest.raises(FileNotFoundError, match="never been frozen"):
            load_frozen_answer_key(key_path)

    def test_frozen_key_loads_its_content_unchanged(self, tmp_path):
        key_path = write_key(tmp_path / "incident-001.answer.json")
        freeze_answer_key(key_path)

        loaded = load_frozen_answer_key(key_path)
        assert loaded == SAMPLE_KEY

    def test_mutated_key_fails_to_load(self, tmp_path):
        # This is C2's core reproduction case: a key frozen, then edited
        # in place. Loading must refuse, not silently serve the new bytes.
        key_path = write_key(tmp_path / "incident-001.answer.json")
        freeze_answer_key(key_path)

        mutated = dict(SAMPLE_KEY, correct_disposition="NO_REPAIR")
        write_key(key_path, mutated)

        with pytest.raises(ValueError, match="changed since it was frozen"):
            load_frozen_answer_key(key_path)

    def test_loading_verifies_the_digest_not_the_filename(self, tmp_path):
        # Two different files, same name pattern, different content and
        # different digests — the loader must not simply trust that a
        # same-named .sha256 file existing means "this content is fine".
        key_a = write_key(tmp_path / "incident-001.answer.json", SAMPLE_KEY)
        freeze_answer_key(key_a)

        different_content = dict(SAMPLE_KEY, correct_root_cause_id="SOMETHING_ELSE")
        write_key(key_a, different_content)

        with pytest.raises(ValueError):
            load_frozen_answer_key(key_a)

    def test_a_correction_is_a_new_file_and_the_old_one_still_loads(self, tmp_path):
        original_path = write_key(tmp_path / "incident-001.answer.json", SAMPLE_KEY)
        freeze_answer_key(original_path)

        corrected_data = dict(SAMPLE_KEY, correct_disposition="ESCALATE")
        corrected_path = write_key(tmp_path / "incident-001-v2.answer.json", corrected_data)
        freeze_answer_key(corrected_path)

        # The old file is untouched and still loads exactly as frozen.
        assert load_frozen_answer_key(original_path) == SAMPLE_KEY
        # The correction lives at its own name with its own digest.
        assert load_frozen_answer_key(corrected_path) == corrected_data


class TestByteLevelSensitivity:
    def test_whitespace_only_change_still_fails_the_digest(self, tmp_path):
        # A hash over bytes, not over parsed JSON semantics: reformatting
        # (even with identical logical content) must still be caught,
        # because "the file changed" is the whole point of C2 — not "the
        # meaning changed".
        key_path = tmp_path / "incident-001.answer.json"
        key_path.write_text(json.dumps(SAMPLE_KEY, indent=2), encoding="utf-8")
        freeze_answer_key(key_path)

        key_path.write_text(json.dumps(SAMPLE_KEY, indent=4), encoding="utf-8")

        with pytest.raises(ValueError, match="changed since it was frozen"):
            load_frozen_answer_key(key_path)
