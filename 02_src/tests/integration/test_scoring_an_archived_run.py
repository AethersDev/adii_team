"""The seam between the runtime's record and the evaluation authority, as one command:
`python -m adii.evaluation --run <label> --key PATH`. The record D writes is what C scores,
read through D's own reader; the key is frozen; the incident is checked; a repair nobody
checked is refused, not filed as rejected; the report lands beside the record once."""
from __future__ import annotations

import hashlib
import json

import pytest
from adii.evaluation.__main__ import NAME, main
from adii.evaluation.freeze import freeze_answer_key
from adii.evaluation.grounding import build_grounding_key
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
    doc["validation"]["reason_code"] = "no_rebuildable_world"    # m7 row 3: said in structure
    record.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 2
    assert "reason_code no_rebuildable_world" in capsys.readouterr().out
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


def grounding_file(key, *predicates):
    path = key.with_name(key.name.replace(".answer.json", ".grounding.json"))
    path.write_text(json.dumps(build_grounding_key(key, [
        {"tool": tool, "argument_contains": needle} for tool, needle in predicates])),
        encoding="utf-8")
    return path


def test_a_correct_disposition_without_the_decisive_observation_reads_as_both(archive, tmp_path):
    """DECISIVE_TESTS D5b: disposition scoring says success; the grounding key says the
    decisive observation was never made; the report carries both and folds neither."""
    key = key_file(tmp_path)
    freeze_answer_key(key)
    grounding = grounding_file(key, ("run_sql", "mart_daily"), ("get_transform", "stg_orders"))
    args = ["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]
    assert main([*args, "--grounding-key", str(grounding)]) == 0
    report = json.loads((archive / "demo-learning-001" / NAME).read_text(encoding="utf-8"))
    assert report["category"] == "success"
    assert report["grounding"]["grounded"] is True
    assert report["grounding"]["decisive"] == {
        "observed": False, "cited": False,
        "missing": [{"tool": "get_transform", "argument_contains": "stg_orders"}]}


def test_a_grounding_key_bound_to_another_answer_key_is_refused(archive, tmp_path, capsys):
    key = key_file(tmp_path)
    other = key_file(tmp_path, incident_id="another-incident")
    freeze_answer_key(key)
    freeze_answer_key(other)
    grounding = grounding_file(other, ("run_sql", "orders"))
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive),
                 "--grounding-key", str(grounding)]) == 2
    assert "grounded against its own key" in capsys.readouterr().out
    assert not (archive / "demo-learning-001" / NAME).exists()


# ── decision J: the judge on the scoring path ─────────────────────────────────────────────
JUDGE_KEY = "sk-judge-test-0123456789abcdefghij"


@pytest.fixture
def judge_endpoint(monkeypatch):
    import threading
    from http.server import ThreadingHTTPServer

    from .fake_model import FakeModel
    monkeypatch.setenv("OPENAI_API_KEY", JUDGE_KEY)
    FakeModel.script, FakeModel.seen, FakeModel.usage = [], [], None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def a_key_the_run_does_not_match_by_id(tmp_path):
    """The walkthrough's repair is correct and accepted, but its repair id is not the key's:
    the deterministic path cannot settle it, which is exactly what the judge is for."""
    satisfy = {**KEY["repair_must_satisfy"], "reference_repair_id": "ANOTHER_NAME_FOR_THE_FIX"}
    key = key_file(tmp_path, repair_must_satisfy=satisfy)
    freeze_answer_key(key)
    return key


def test_without_a_judge_a_case_it_would_settle_stays_unresolved(archive, tmp_path):
    key = a_key_the_run_does_not_match_by_id(tmp_path)
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]) == 0
    report = json.loads((archive / "demo-learning-001" / NAME).read_text(encoding="utf-8"))
    assert (report["category"], report["sub_kind"], report["settled_by"]) == \
        ("failure", "unresolved", "none")
    assert "judge" not in report


def test_the_judge_settles_it_and_the_report_says_which_judge_said_what(
        archive, tmp_path, judge_endpoint, capsys):
    from .fake_model import FakeModel
    key = a_key_the_run_does_not_match_by_id(tmp_path)
    FakeModel.script[:] = ["correct — it removes exactly one of the two conversions."]
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive),
                 "--judge-model", "gpt-4.1-mini", "--judge-endpoint", judge_endpoint]) == 0
    assert "settled by judge" in capsys.readouterr().out
    text = (archive / "demo-learning-001" / NAME).read_text(encoding="utf-8")
    report = json.loads(text)
    assert (report["category"], report["settled_by"]) == ("success", "judge")
    [asked] = FakeModel.seen
    prompt = asked["messages"][0]["content"]
    assert asked["model"] == "gpt-4.1-mini" and asked["temperature"] == 0
    judge = report["judge"]
    assert judge["model"] == "gpt-4.1-mini" and judge["verdict"] == "correct"
    assert judge["prompt_sha256"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert judge["usage"] == {"prompt_tokens": 100, "completion_tokens": 20}
    assert judge["cost_usd"] and judge["price_table"]
    assert judge["justification"] == "it removes exactly one of the two conversions."
    assert "reasoning" not in judge
    assert JUDGE_KEY not in text                          # the credential is in no artefact


def test_a_judge_that_does_not_give_a_verdict_scores_nothing(
        archive, tmp_path, judge_endpoint, capsys):
    from .fake_model import FakeModel
    key = a_key_the_run_does_not_match_by_id(tmp_path)
    FakeModel.script[:] = ["Perhaps; it is hard to say."]
    assert main(["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive),
                 "--judge-model", "gpt-4.1-mini", "--judge-endpoint", judge_endpoint]) == 2
    assert "not scored" in capsys.readouterr().out
    assert not (archive / "demo-learning-001" / NAME).exists()


def test_a_judge_must_be_priced_and_have_its_credential(archive, tmp_path, monkeypatch, capsys):
    key = a_key_the_run_does_not_match_by_id(tmp_path)
    args = ["--run", "demo-learning-001", "--key", str(key), "--archive", str(archive)]
    assert main([*args, "--judge-model", "an-unpriced-model"]) == 2
    assert "nominal price" in capsys.readouterr().out
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main([*args, "--judge-model", "gpt-4.1-mini"]) == 2
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().out
