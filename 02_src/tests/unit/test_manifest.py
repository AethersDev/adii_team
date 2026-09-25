"""Requirement D13 as tests: attestation, verification from the manifest alone, and
manifest-first preservation. The archive lives in a temporary directory here; the tracked
archive's manifest is whatever the last attestation on that machine wrote."""
from __future__ import annotations

import json
import shutil

import pytest
from adii.examples.walkthrough import main as walkthrough
from adii.reporting.manifest import NAME, RETENTION, SCHEMA, main, preserve, verify, write_manifest


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


def test_every_artefact_of_a_run_is_attested_in_its_retention_class(archive, tmp_path):
    """A run leaves its receipt, its trace and its record — and, when the operator brought
    the incident, that incident and its world; a person may leave feedback beside them; the
    authority may leave its report. All of these are attested and preserved — the evidence,
    what was said about it, and what it scored, each in its own class — and a file under
    any other name is a finding verification names, never silently archived."""
    run = archive / "demo-learning-001"
    (run / "receipt.json").write_text('{"schema": "adii.receipt/v1"}', encoding="utf-8")
    (run / "trace.jsonl").write_text('{"kind": "incident_received"}\n', encoding="utf-8")
    (run / "incident.json").write_text('{"incident_id": "demo-learning-001"}', encoding="utf-8")
    (run / "world.sql").write_text('CREATE TABLE t (x);\n', encoding="utf-8")
    (run / "feedback.jsonl").write_text('{"useful": "yes"}\n', encoding="utf-8")
    (run / "evaluation_report.json").write_text('{"category": "success"}\n', encoding="utf-8")
    manifest = json.loads(write_manifest(archive).read_text(encoding="utf-8"))
    assert {e["path"]: e["retention"] for e in manifest["entries"]} == {
        "demo-learning-001/receipt.json": "evidence",
        "demo-learning-001/trace.jsonl": "evidence",
        "demo-learning-001/record.json": "evidence",
        "demo-learning-001/incident.json": "evidence",
        "demo-learning-001/world.sql": "evidence",
        "demo-learning-001/feedback.jsonl": "annotation",
        "demo-learning-001/evaluation_report.json": "evaluation"}
    assert set(RETENTION.values()) == {"evidence", "annotation", "evaluation"}
    assert verify(archive).ok
    (run / "notes.txt").write_text("not archived", encoding="utf-8")
    assert verify(archive).unlisted == ("demo-learning-001/notes.txt",)
    (run / "notes.txt").unlink()
    (run / "feedback.jsonl").unlink()
    assert verify(archive).missing == ("demo-learning-001/feedback.jsonl",)
    (run / "feedback.jsonl").write_text('{"useful": "yes"}\n', encoding="utf-8")
    copy = tmp_path / "copy"
    assert preserve(archive, copy).ok
    for entry in manifest["entries"]:
        assert (copy / entry["path"]).read_bytes() == (archive / entry["path"]).read_bytes()


def test_a_brought_incident_s_evidence_bundles_are_attested_and_preserved(archive, tmp_path):
    """The run's copy of the operator's package — each map file beside the record and every
    file under a bundle's directory — is evidence: attested with the record, preserved with
    it, and a file inside a folder the archive does not know is unlisted, not invisible."""
    from adii.tools import EVIDENCE_BUNDLES as TOOL_BUNDLES
    run = archive / "demo-learning-001"
    (run / "transform_map.json").write_text('{"stg_orders": "orders.sql"}', encoding="utf-8")
    (run / "transform_sources").mkdir()
    (run / "transform_sources" / "orders.sql").write_bytes(b"select id\r\nfrom orders\r\n")
    (run / "declared_schema_map.json").write_text('{"orders": "orders.json"}', encoding="utf-8")
    (run / "declared_schema_sources").mkdir()
    (run / "declared_schema_sources" / "orders.json").write_text("{}", encoding="utf-8")
    manifest = json.loads(write_manifest(archive).read_text(encoding="utf-8"))
    assert {e["path"]: e["retention"] for e in manifest["entries"]} == {
        "demo-learning-001/record.json": "evidence",
        "demo-learning-001/transform_map.json": "evidence",
        "demo-learning-001/transform_sources/orders.sql": "evidence",
        "demo-learning-001/declared_schema_map.json": "evidence",
        "demo-learning-001/declared_schema_sources/orders.json": "evidence"}
    assert verify(archive).ok
    copy = tmp_path / "copy"
    assert preserve(archive, copy).ok
    assert (copy / "demo-learning-001" / "transform_sources" / "orders.sql").read_bytes() == \
        b"select id\r\nfrom orders\r\n"
    (run / "notes").mkdir()
    (run / "notes" / "scratch.txt").write_text("not archived", encoding="utf-8")
    assert verify(archive).unlisted == ("demo-learning-001/notes/scratch.txt",)
    assert set(RETENTION.values()) == {"evidence", "annotation", "evaluation"}
    from adii.reporting.manifest import EVIDENCE_BUNDLES
    assert EVIDENCE_BUNDLES == TOOL_BUNDLES      # the same names, without reporting importing tools


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


def test_a_brought_packages_declared_series_is_evidence_and_verifies(archive):
    """The audit of 24 Sep: the runtime copies a package's alert_series.json beside the record;
    the manifest keeps it as evidence, so a run from a brought package verifies."""
    run = archive / "demo-learning-001"
    (run / "alert_series.json").write_text('{"metric": "m", "unit": "u", "query": "q"}',
                                           encoding="utf-8")
    manifest = json.loads(write_manifest(archive).read_text(encoding="utf-8"))
    kept = {e["path"]: e["retention"] for e in manifest["entries"]}
    assert kept["demo-learning-001/alert_series.json"] == "evidence"
    assert verify(archive).ok
