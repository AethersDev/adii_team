"""Tests for receipt_artefacts.py — D-15/D8: C's one field in D's receipt.

D8's own test spec: "kill the process immediately after the receipt
write and before the call; the receipt exists and names what was about
to be spent." This module's part of that is narrower and testable in
isolation: given a frozen answer key (and, optionally, a bound grounding
key), produce the exact {"kind", "path", "digest"} entries a receipt
would name — nothing about the kill-and-check protocol itself, which is
D's own receipts.py to build and test.

Uses tmp_path throughout — never touches the real answer key files.
"""
import json

import pytest

from freeze import freeze_answer_key
from grounding import build_grounding_key
from receipt_artefacts import get_receipt_artefact, get_receipt_artefact_with_grounding

ANSWER_KEY = {"schema_version": "1", "incident_id": "t-1", "correct_disposition": "REPAIR"}


def write_answer_key(tmp_path, name="incident.answer.json", data=None):
    path = tmp_path / name
    path.write_text(json.dumps(data or ANSWER_KEY, indent=2), encoding="utf-8")
    return path


class TestGetReceiptArtefact:
    def test_frozen_key_produces_a_receipt_entry(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        digest = freeze_answer_key(answer_key_path)

        entry = get_receipt_artefact(answer_key_path)

        assert entry == {"kind": "answer_key", "path": "incident.answer.json", "digest": digest}

    def test_unfrozen_key_is_refused_not_silently_receipted(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        with pytest.raises(FileNotFoundError, match="never been frozen"):
            get_receipt_artefact(answer_key_path)

    def test_mutated_key_is_refused_a_receipt(self, tmp_path):
        # D8's whole point: a receipt must vouch for the artefact truthfully.
        # An answer key that changed since freezing cannot be receipted as
        # if it were still the frozen one.
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        answer_key_path.write_text(json.dumps(dict(ANSWER_KEY, correct_disposition="ESCALATE")), encoding="utf-8")

        with pytest.raises(ValueError, match="changed since it was frozen"):
            get_receipt_artefact(answer_key_path)

    def test_path_in_the_entry_is_a_filename_not_an_absolute_path(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path, "demo-learning-001.answer.json")
        freeze_answer_key(answer_key_path)

        entry = get_receipt_artefact(answer_key_path)

        assert entry["path"] == "demo-learning-001.answer.json"
        assert "/" not in entry["path"] and "\\" not in entry["path"]

    def test_entry_is_strict_json_serialisable(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        entry = get_receipt_artefact(answer_key_path)

        assert json.loads(json.dumps(entry)) == entry


class TestGetReceiptArtefactWithGrounding:
    def test_bound_pair_produces_two_entries(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(answer_key_path, [{"tool": "run_sql", "argument_contains": "x"}])
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        entries = get_receipt_artefact_with_grounding(answer_key_path, grounding_path)

        assert len(entries) == 2
        kinds = {e["kind"] for e in entries}
        assert kinds == {"answer_key", "grounding_key"}

    def test_answer_key_entry_matches_the_standalone_call(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(answer_key_path, [])
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        entries = get_receipt_artefact_with_grounding(answer_key_path, grounding_path)
        answer_key_entry = next(e for e in entries if e["kind"] == "answer_key")

        assert answer_key_entry == get_receipt_artefact(answer_key_path)

    def test_broken_pairing_is_refused_not_silently_receipted(self, tmp_path):
        # The answer key changed after the grounding key was authored
        # against it — grounding.load_grounding_key's own C3 check must
        # be the thing that refuses this, and receipt_artefacts must not
        # swallow that refusal.
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(answer_key_path, [])
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        (tmp_path / "incident.answer.json.sha256").unlink()
        answer_key_path.write_text(json.dumps(dict(ANSWER_KEY, correct_disposition="NO_REPAIR")), encoding="utf-8")
        freeze_answer_key(answer_key_path)  # re-frozen at a new digest

        with pytest.raises(ValueError, match="changed since this grounding key was authored"):
            get_receipt_artefact_with_grounding(answer_key_path, grounding_path)

    def test_grounding_entry_digest_is_the_grounding_files_own_digest(self, tmp_path):
        # Not to be confused with the answer_key_digest carried INSIDE the
        # grounding key document for C3's pairing check — this is a
        # digest of the grounding key file itself, a distinct artefact.
        from freeze import compute_digest

        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(answer_key_path, [])
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        entries = get_receipt_artefact_with_grounding(answer_key_path, grounding_path)
        grounding_entry = next(e for e in entries if e["kind"] == "grounding_key")

        assert grounding_entry["digest"] == compute_digest(grounding_path)
        assert grounding_entry["digest"] != grounding["answer_key_digest"]
