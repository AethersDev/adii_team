"""The six development specimens are produced by the real runtime over the real tool
layer, end the way their scripts say, and say what they are on every record: scripted,
no model, no evaluation claim. Nothing here asserts that a specimen's decision is correct;
that is exactly the claim these carry none of."""
from __future__ import annotations

import json
from collections import Counter

from adii.examples.specimens import SPECIMENS, main, records
from adii.reporting import read_record

EXPECTED = {           # label → (termination, disposition, validation accepted)
    "orders-missing-day-run-1": ("submitted", "REPAIR", True),
    "orders-missing-day-run-2": ("bound_hit", None, None),
    "revenue-after-deploy-run-1": ("submitted", "NO_REPAIR", None),
    "delivery-duplicated-run-1": ("submitted", "REPAIR", False),
    "delivery-duplicated-run-2": ("submitted", "REPAIR", True),
    "shipment-counts-disagree-run-1": ("submitted", "ESCALATE", None),
    "settlement-conflict-run-1": ("submitted", "ESCALATE", None),
    "settlement-conflict-run-2": ("model_failure", None, None),
    "customer-region-misassigned-run-1": ("submitted", "REPAIR", True),
    "customer-region-misassigned-run-2": ("submitted", "ESCALATE", None),
}


def test_six_specimens_cover_the_six_ways_to_reason_and_the_ugly_endings():
    produced = {r.label: r for r in records()}
    assert set(produced) == set(EXPECTED)
    for label, (termination, disposition, accepted) in EXPECTED.items():
        r = produced[label]
        assert r.termination == termination, label
        assert (r.decision.disposition.value if r.decision else None) == disposition, label
        assert (r.validation.accepted if r.validation else None) is accepted, label
    dispositions = Counter(r.decision.disposition.value for r in produced.values() if r.decision)
    assert dispositions == {"REPAIR": 4, "NO_REPAIR": 1, "ESCALATE": 3}


def test_every_observation_is_what_the_tool_layer_returned():
    """Scripted investigator, real tools: every OK result carries B's evidence id, and the
    statuses a script provoked on purpose — a table that is not there, a tool that fails —
    come back as the tool layer classifies them, never as the script says."""
    produced = {r.label: r for r in records()}
    for r in produced.values():
        for e in r.trace:
            if e.kind == "tool_result" and e.payload["status"] == "OK":
                assert e.payload["content"]["evidence_id"].startswith("ev-"), r.label

    def statuses(r):
        return [e.payload["status"] for e in r.trace if e.kind == "tool_result"]
    assert statuses(produced["shipment-counts-disagree-run-1"])[-1] == "REJECTED"   # no such table
    assert statuses(produced["customer-region-misassigned-run-2"])[-1] == "ERROR"    # tool failed
    assert produced["orders-missing-day-run-2"].tool_calls == 2                     # the bound


def test_every_specimen_record_says_what_it_is():
    for r in records():
        assert r.provenance["origin"] == "runtime"
        assert r.configuration["model"] is None
        assert r.configuration["execution_mode"] == "scripted"
        assert r.configuration["visibility"] == "public_development"
        assert r.configuration["blind_evaluation_eligible"] is False
        json.loads(r.to_json())                                   # strict, like every record


def test_specimen_ids_never_collide_with_the_teaching_incident():
    ids = [s.context.incident_id for s in SPECIMENS]
    assert len(ids) == len(set(ids)) == 6 and "demo-learning-001" not in ids


def test_the_command_archives_every_run_once(tmp_path, capsys):
    assert main(["--archive", str(tmp_path)]) == 0
    assert "10 archived, 0 already there" in capsys.readouterr().out
    rejected = read_record(tmp_path / "delivery-duplicated-run-1" / "record.json")
    assert rejected.validation.accepted is False
    assert main(["--archive", str(tmp_path)]) == 0
    assert "0 archived, 10 already there" in capsys.readouterr().out
