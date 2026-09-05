"""The two front-door invariants from docs/DATA_WORLD_v0.md, as assertions.

They are build requirements rather than presentation preferences, so they are checked here
instead of trusted. A demo that fails either has to be narrated into working, which is the
thing the demo exists to avoid.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = (Path(__file__).resolve().parents[3]
            / "01_data" / "demo" / "fixtures")
RUNS = sorted(p for p in FIXTURES.glob("*/run.json"))
IDS = [p.parent.name for p in RUNS]


@pytest.mark.parametrize("path", RUNS, ids=IDS)
def test_i1_every_disposition_is_inferable_from_displayed_evidence(path):
    """I1 — the orientation layer shows the alert, the checks, and the conclusion. A run
    that cannot be reasoned about from those has to be explained instead."""
    run = json.loads(path.read_text(encoding="utf-8"))
    intro = run.get("intro")
    assert intro, f"{path.parent.name} has no intro projection"
    assert intro["alert"].strip() and intro["question"].strip()
    assert intro["decision"].strip() and intro["takeaway"].strip()
    assert intro["checks"], "at least one observation must be shown"
    shown = {s["n"] for s in run["trace"]}
    for n in intro["checks"]:
        assert n in shown, f"cited check {n} is not in the trace"
        step = next(s for s in run["trace"] if s["n"] == n)
        assert step.get("plain"), f"step {n} has no plain-language line to display"


@pytest.mark.parametrize("path", RUNS, ids=IDS)
def test_i2_every_repair_shows_its_mechanism_and_what_was_verified(path):
    """I2 — `REPAIR · repair_07 · ACCEPT` tells a viewer nothing. They must see what
    changed and what the independent check confirmed, or they cannot tell a real fix from
    a plausible-looking one — which is the distinction the product rests on."""
    run = json.loads(path.read_text(encoding="utf-8"))
    if run["decision"]["disposition"] != "REPAIR":
        assert "mechanism" not in run, "only a REPAIR has a mechanism to show"
        return
    m = run.get("mechanism")
    assert m, f"{path.parent.name} is a REPAIR with no mechanism to display"
    assert m["before"] and m["after"], "before and after must both be shown"
    assert m["action"].strip(), "the change itself must be stated in plain language"
    assert m["verified"].strip(), "what the independent check confirmed must be stated"
    assert m["verdict"] in {"ACCEPT", "REJECT"}
    assert m["verdict"] == run["validation"]["verdict"], "mechanism and verdict disagree"


def test_the_escalate_run_names_absent_evidence_not_a_confidence_score():
    """A threshold would make ADII a confidence wrapper. The reason must be a concrete
    record that does not exist."""
    loaded = [json.loads(p.read_text(encoding="utf-8")) for p in RUNS]
    escalate = [r for r in loaded if r["decision"]["disposition"] == "ESCALATE"]
    assert escalate, "the demo set must contain an ESCALATE"
    for run in escalate:
        missing = run["decision"]["missing_evidence"]
        assert missing and len(missing.split()) > 15
        assert "confidence" not in missing.lower() and "threshold" not in missing.lower()


@pytest.mark.parametrize("path", RUNS, ids=IDS)
def test_every_fixture_declares_how_it_was_made(path):
    """Lineage, mechanically. Today these are hand-authored from the evaluation catalogue.
    Once demo/world exists they are generated from it, and a fixture that cannot say which
    it is has been quietly curated into looking like output."""
    run = json.loads(path.read_text(encoding="utf-8"))
    assert run.get("fixture") is True
    provenance = run.get("provenance", "")
    assert provenance, f"{path.parent.name} does not declare its provenance"
    assert "hand-authored" in provenance or "generated" in provenance


def test_evaluation_shaped_data_exists_only_inside_declared_fixtures():
    """Answer keys, oracles, and scoring truth belong to the evaluation authority, not the
    demo.

    A demo fixture may carry an `evaluation` block — showing what the evaluator knows, and
    that the investigator could not see it, is the teaching point. What must never appear
    is a standalone key: evaluation-shaped JSON that does not declare itself a fixture is
    indistinguishable from a copied authority, and a copy here is reachable from the
    runtime.
    """
    root = Path(__file__).resolve().parents[3]
    markers = ("answer_key", "expected_disposition", "evidence_sufficient",
               "revenue_oracle", "accepted_repair_ids", "canonical_root_cause_id")
    for path in root.rglob("*.json"):
        if any(part in (".git", "node_modules", ".venv") for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = [m for m in markers if m in text]
        if not hits:
            continue
        try:
            declared = json.loads(text).get("fixture") is True
        except json.JSONDecodeError:
            declared = False
        assert declared, (
            f"{path.relative_to(root)} contains {hits} but does not declare itself a "
            "fixture. Evaluation authority lives outside anything the investigator can reach.")
