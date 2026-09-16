"""Inherited D13 as tests: attestation, verification from the manifest alone, and
manifest-first preservation. The archive lives in a temporary directory here; the tracked
archive's manifest is whatever the last attestation on that machine wrote."""
from __future__ import annotations

import json
import shutil

import pytest
from adii.examples.walkthrough import main as walkthrough
from adii.reporting.manifest import NAME, SCHEMA, main, preserve, verify, write_manifest


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "runs"
    assert walkthrough(["--archive", str(root)]) == 0
    (root / "README.md").write_text("the archive", encoding="utf-8")   # beside the runs, not a run
    return root


def test_attestation_lists_every_record_with_path_size_digest_and_retention(archive):
    path = write_manifest(archive)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema"] == SCHEMA and path.name == NAME
    [entry] = manifest["entries"]
    assert entry["path"] == "demo-learning-001/record.json"
    assert entry["bytes"] == (archive / entry["path"]).stat().st_size
    assert entry["digest"].startswith("sha256:") and entry["retention"] == "evidence"
    assert verify(archive).ok


def test_a_payload_change_without_a_manifest_change_fails(archive):
    write_manifest(archive)
    record = archive / "demo-learning-001" / "record.json"
    record.write_text(record.read_text(encoding="utf-8").replace("REPAIR", "ESCALATE"),
                      encoding="utf-8")
    result = verify(archive)
    assert result.altered == ("demo-learning-001/record.json",) and not result.ok
    assert main(["--archive", str(archive), "--verify"]) == 1


def test_absence_and_the_unlisted_are_findings_not_exemptions(archive):
    """Losing a payload leaves the receipt intact and the object gone — the unverifiable
    failure D13 names as the worse one. A record the manifest never saw is the other half."""
    write_manifest(archive)
    shutil.rmtree(archive / "demo-learning-001")
    (archive / "later").mkdir()
    (archive / "later" / "record.json").write_text("{}", encoding="utf-8")
    result = verify(archive)
    assert result.missing == ("demo-learning-001/record.json",)
    assert result.unlisted == ("later/record.json",) and not result.ok


def test_preservation_is_manifest_first_and_never_deletes_the_original(archive, tmp_path):
    copy = tmp_path / "copy"
    result = preserve(archive, copy)
    assert result.ok and result.checked == 1
    assert (copy / "demo-learning-001" / "record.json").read_bytes() == \
        (archive / "demo-learning-001" / "record.json").read_bytes()
    assert (archive / "demo-learning-001" / "record.json").is_file()      # the original stays
    # the copy is held to the manifest made before the copy, so a corrupted copy is caught
    (copy / "demo-learning-001" / "record.json").write_text("corrupted", encoding="utf-8")
    assert not verify(copy).ok
    assert main(["--archive", str(archive), "--preserve", str(tmp_path / "copy2")]) == 0
    assert (tmp_path / "copy2" / NAME).is_file()


def test_an_unknown_manifest_schema_is_refused(archive):
    (archive / NAME).write_text('{"schema": "adii.archive_manifest/v9", "entries": []}',
                                encoding="utf-8")
    with pytest.raises(ValueError, match="unknown manifest schema"):
        verify(archive)
