"""Every sentence the inspector adds to a record is a deterministic projection of record
fields, and lives in one file, phrasing.js. These tests pin each projection against the
committed records — one per way a run can end — by evaluating the dictionary in node, so
the mapping the README lists is the mapping the page uses. A sentence that adds a cause
the record does not state fails here."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "02_src" / "adii" / "demo" / "web"
WALKTHROUGH = ROOT / "01_data" / "walkthrough"
RECORDS = {
    "accepted": WALKTHROUGH / "record.json",
    "rejected": WALKTHROUGH / "endings" / "repair-rejected" / "record.json",
    "bound": WALKTHROUGH / "endings" / "bound-hit" / "record.json",
    "model": WALKTHROUGH / "endings" / "model-failure" / "record.json",
    "infra": WALKTHROUGH / "endings" / "infrastructure-failure" / "record.json",
}
# Words that assert a cause the record does not state. None may appear in a projection.
FORBIDDEN = ("could not", "couldn't", "insufficient", "stuck", "gave up", "unable", "confused")


def node() -> str:
    found = shutil.which("node")
    if not found:
        pytest.skip("node is not installed; the phrasing projections are evaluated in it")
    return found


def phrase(kind: str, key: str, record: dict) -> str:
    """Evaluate PHRASING[kind][key] against a record, in node, exactly as the page does."""
    script = (f"{(WEB / 'phrasing.js').read_text(encoding='utf-8')}\n"
              f"const r = {json.dumps(record)};\n"
              f"const f = PHRASING[{kind!r}][{key!r}];\n"
              "process.stdout.write(typeof f === 'function' ? f(r) : f);")
    return subprocess.run([node(), "-e", script], capture_output=True, text=True,
                          check=True, timeout=30).stdout


def load(name: str) -> dict:
    return json.loads(RECORDS[name].read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "expected"), [
    ("accepted", "The investigator committed to REPAIR."),
    ("bound", "The investigator reached a bound it set after 3 tool calls and stopped without "
              "a decision."),
    ("model", "The model failed and the run stopped without a decision."),
    ("infra", "Something in the runtime failed — a defect of ours, not the model's — and the run "
              "stopped without a decision."),
])
def test_how_a_run_ended_is_a_projection_of_its_fields(name, expected):
    record = load(name)
    assert phrase("ended", record["termination"], record) == expected


@pytest.mark.parametrize(("name", "expected"), [
    ("accepted", "REPAIR · accepted by the validator"),
    ("rejected", "REPAIR · rejected by the validator"),
    ("bound", "Ended at a bound, no decision"),
    ("model", "Ended by a model failure, no decision"),
    ("infra", "Ended by a failure of ours, no decision"),
])
def test_the_short_outcome_inherits_exactly_the_records_authority(name, expected):
    record = load(name)
    assert phrase("outcome", record["termination"], record) == expected


def test_every_trace_step_has_a_sentence_and_quotes_only_the_payload():
    record = load("accepted")
    sentences = [phrase("step", e["kind"], e["payload"]) for e in record["trace"]]
    assert sentences[0] == "The investigator received incident demo-learning-001."
    assert sentences[1] == "It asked the tool layer to run get_schema with table = orders."
    assert sentences[2] == "The tool layer answered get_schema with 3 columns."
    assert any(s.startswith("The tool layer refused delete_table: unknown tool") for s in sentences)
    assert sentences[-2] == "The investigator committed to REPAIR."
    assert sentences[-1] == "The validator accepted the repair."


@pytest.mark.parametrize("name", list(RECORDS))
def test_no_projection_asserts_a_cause_the_record_does_not_state(name):
    record = load(name)
    text = " ".join([phrase("ended", record["termination"], record),
                     phrase("outcome", record["termination"], record),
                     *(phrase("step", e["kind"], e["payload"]) for e in record["trace"])]).lower()
    hits = [w for w in FORBIDDEN if w in text]
    assert not hits, f"a projection asserts a cause the record does not state: {hits}"


def test_the_readme_lists_every_sentence_the_page_adds():
    """The dictionary is reviewable because the README names every entry. A new entry
    without a README line is a sentence the team never saw."""
    readme = (ROOT / "02_src" / "adii" / "demo" / "README.md").read_text(encoding="utf-8")
    source = (WEB / "phrasing.js").read_text(encoding="utf-8")
    for key in ("submitted", "bound_hit", "model_failure", "infrastructure_failure",
                "notInvoked", "neverReached", "incident_received", "tool_call", "tool_result",
                "decision_submitted", "validation_completed"):
        assert key in source, f"phrasing.js lost {key}"
        assert f"`{key}`" in readme, f"README does not list the {key} sentence"
