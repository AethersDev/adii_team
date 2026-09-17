"""The seam between the runtime's record and the evaluation authority, as one command:
`python -m adii.evaluation --run <label> --key PATH`. The record D writes is what C scores,
read through D's own reader; the key is frozen; the incident is checked; a repair nobody
checked is refused, not filed as rejected; the report lands beside the record once."""
from __future__ import annotations

import json

import pytest
from adii.evaluation.__main__ import NAME, main
from adii.evaluation.freeze import freeze_answer_key
from adii.examples.walkthrough import main as walkthrough
from adii.reporting.manifest import RETENTION, verify, write_manifest

KEY = {
    "schema_version": "1",
    "incident_id": "demo-learning-001",
    "correct_disposition": "REPAIR",
    "correct_root_cause_id": "DEMO_DOUBLE_UNIT_CONVERSION",
    "root_cause_explanation": "stg_orders.sql divides amount_cents by 100 twice.",
    "repair_must_satisfy": {
        "reference_repair_id": "DEMO_REMOVE_SECOND_CONVERSION",
        "reference_patch_effect": "one conversion from cents to dollars",
        "alternative_repairs_are_acceptable_if": [],
        "must_be_validated": True,
        "validation_requirement": "rebuild from frozen inputs",
    },
    "frozen": True,
}


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "runs"
    assert walkthrough(["--archive", str(root)]) == 0        # demo-learning-001: REPAIR, accepted
    return root


def key_file(tmp_path, **changes):
    path = tmp_path / "keys" / f"{changes.get('incident_id', KEY['incident_id'])}.answer.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({**KEY, **changes}, indent=2), encoding="utf-8")
    return path


def test_the_record_the_runtime_writes_is_scored_as_it_is_and_the_report_kept_once(
        archive, tmp_path, capsys):
    key = key_file(tmp_path)
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 2
    assert "never been frozen" in capsys.readouterr().out         # an unfrozen key scores nothing
    freeze_answer_key(key)
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 0
    out = capsys.readouterr().out
    assert "scored demo-learning-001: success" in out and "sha256:" in out
    report = json.loads((archive / "demo-learning-001" / NAME).read_text(encoding="utf-8"))
    assert report["schema"] == "adii.evaluation_report/v1"
    assert report["category"] == "success" and report["settled_by"] == "deterministic"
    assert report["run_label"] == "demo-learning-001"
    # scored once: a second scoring is refused, and the first report is untouched
    before = (archive / "demo-learning-001" / NAME).read_bytes()
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 1
    assert (archive / "demo-learning-001" / NAME).read_bytes() == before
    # and the archive's custody knows the report by its class
    write_manifest(archive)
    assert verify(archive).ok and RETENTION[NAME] == "evaluation"


def test_a_run_is_scored_against_its_own_incidents_key_only(archive, tmp_path, capsys):
    key = key_file(tmp_path, incident_id="some-other-incident")
    freeze_answer_key(key)
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 2
    assert "some-other-incident" in capsys.readouterr().out
    assert not (archive / "demo-learning-001" / NAME).exists()


def test_a_repair_nobody_checked_is_refused_not_filed_as_rejected(archive, tmp_path, capsys):
    """Every live REPAIR carries the runtime's placeholder verdict until a validator exists:
    accepted=False, checks_run=(). Scored as it stands it would file as a rejection — a
    finding the record itself disclaims. So it is not scored."""
    record = archive / "demo-learning-001" / "record.json"
    doc = json.loads(record.read_text(encoding="utf-8"))
    doc["validation"] = {"accepted": False, "checks_run": [],
                         "report": "No independent validator exists yet."}
    record.write_text(json.dumps(doc), encoding="utf-8")
    key = key_file(tmp_path)
    freeze_answer_key(key)
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 2
    assert "never checked" in capsys.readouterr().out
    assert not (archive / "demo-learning-001" / NAME).exists()
    # but where the key says the right call was not a repair, the disposition alone decides
    # and no validator is consulted: an unchecked REPAIR scores as what it is
    satisfy = {**KEY["repair_must_satisfy"], "reference_repair_id": None}
    other = key_file(tmp_path, correct_disposition="NO_REPAIR", repair_must_satisfy=satisfy)
    other = other.rename(other.with_name("no-repair.answer.json"))
    freeze_answer_key(other)
    assert main(["--run", "demo-learning-001", "--key", str(other), "--archive", str(archive)]) == 0
    report = json.loads((archive / "demo-learning-001" / NAME).read_text(encoding="utf-8"))
    assert (report["category"], report["sub_kind"]) == ("failure", "unwarranted_repair")


def test_an_unknown_run_or_schema_is_refused_before_any_key_is_read(archive, tmp_path, capsys):
    key = key_file(tmp_path)
    freeze_answer_key(key)
    assert main(["--run", "nope", "--key", str(key), "--archive", str(archive)]) == 2
    (archive / "demo-learning-001" / "record.json").write_text(
        '{"schema": "adii.run_record/v9"}', encoding="utf-8")
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 2
    assert "unknown record schema" in capsys.readouterr().out
