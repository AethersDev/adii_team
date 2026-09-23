"""The data-readiness gate: every development package under 01_data/incidents/ can carry a
measurement before anything is frozen or run against it.

    held here, for every package                     why
    ─────────────────────────────────────────────    ────────────────────────────────────────
    it is what its generator writes, byte for byte   a world nobody can regenerate drifts
    no file states or encodes an answer              the investigator reads these files
    siblings of one alert share every surface        otherwise the setup, not the evidence,
      the model sees but the evidence                  decides (DECISIVE_TESTS, "the leak")
    every table and evidence id is reachable         a decisive fact nobody can reach is not
      through the real tool layer                      evidence (DATA_WORLD, Reachability)
    the validator has an oracle for it, and its      a REPAIR on it gets a verdict, and the
      frozen pipeline reproduces its own world         world is the pipeline's own output

The canonical world's story is held on the real packages too: the scale-to-the-total repair
recovers the chart and is rejected; the staging restored is accepted; a repair of a world
that was never broken changes nothing and is rejected. And the REPAIR validity rule
(final_plan.md) holds on every REPAIR case not burned: the permitted transform is itself
the cause, restoring it alone repairs the world, and the validator tells that from the
cosmetic fake and from the no-op.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from adii.contracts import Disposition, InvestigationDecision, ToolCall
from adii.evaluation.evaluation_report import build_evaluation_report
from adii.evaluation.freeze import load_frozen_answer_key
from adii.evaluation.grid import BURNED
from adii.evaluation.grounding import load_grounding_key
from adii.evaluation.scale import REPAIR_STATE, Ideal, ideal, measure, scale_to_the_total
from adii.examples.canonical_world import (
    FAMILIES,
    INCIDENTS,
    STATES,
    incident_id,
    packages,
    staging,
)
from adii.runtime.__main__ import incident_from_dir
from adii.runtime.run import run_incident
from adii.runtime.scripted import ScriptedInvestigator
from adii.tools import ReadOnlyDatabase
from adii.validation.patching import apply_patch, path_of
from adii.validation.validator import ORACLES, Validator, load_oracle

from .test_answer_keys_stay_out import MARKERS

FOLDERS = sorted(p for p in INCIDENTS.glob("*") if p.is_dir())
DISPOSITIONS = re.compile(r"\b(REPAIR|NO_REPAIR|ESCALATE)\b")


def test_there_are_packages_and_each_is_what_its_generator_writes():
    assert FOLDERS, "no development package under 01_data/incidents/"
    generated = packages()
    assert sorted(generated) == [p.name for p in FOLDERS]
    for folder in FOLDERS:
        on_disk = {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8")
                   for p in folder.rglob("*") if p.is_file()}
        assert on_disk == generated[folder.name], f"{folder.name} differs from its generator"


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_no_file_states_an_answer(folder):
    for path in folder.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not DISPOSITIONS.search(text), f"{path} names a disposition"
            assert not [m for m in MARKERS if m in text], f"{path} carries a key's field"


def surface(folder: Path) -> dict:
    """Everything the model is shown before it looks at any evidence."""
    context, tools, *_ = incident_from_dir(folder)
    db = ReadOnlyDatabase.in_memory((folder / "world.sql").read_text(encoding="utf-8"))
    return {"alert": context.alert, "as_of": context.as_of,
            "permitted": context.permitted_write_paths, "tools": tools.advertised(),
            "tables": {t: db.schema(t).columns for t in db.tables()}}


def test_packages_that_share_an_alert_share_every_surface_but_the_evidence():
    by_alert: dict[str, list[dict]] = {}
    for folder in FOLDERS:
        seen = surface(folder)
        by_alert.setdefault(seen["alert"], []).append(seen)
    for siblings in by_alert.values():
        assert all(s == siblings[0] for s in siblings), "siblings differ before any evidence"


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_every_table_and_evidence_id_is_reachable_through_the_tool_layer(folder):
    _, tools, *_ = incident_from_dir(folder)
    calls = []
    for spec in tools.advertised():
        props = spec["parameters"]["properties"]
        for name, prop in props.items():
            calls += [(spec["name"], {name: value}) for value in prop.get("enum", ())]
    tables = ReadOnlyDatabase.in_memory((folder / "world.sql").read_text(encoding="utf-8"))
    calls += [("run_sql", {"query": f'SELECT count(*) FROM "{t}"'}) for t in tables.tables()]
    calls += [("get_schema", {"table": t}) for t in tables.tables()]
    for n, (name, arguments) in enumerate(calls):
        result = tools.execute(ToolCall(f"r{n}", name, arguments))
        assert result.status == "OK", (name, arguments, result.content)


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_the_validator_can_rebuild_it_and_its_world_is_its_pipelines_own(folder):
    pipeline, _ = load_oracle(ORACLES / f"{folder.name}.json")
    world, transforms = Validator().frozen_inputs(folder.name)
    patchable = next(s.transform for s in pipeline if s.transform)
    frozen = ReadOnlyDatabase.in_memory(world)
    rebuilt = apply_patch(world, pipeline, transforms,
                          {path_of(patchable): transforms[patchable]})
    for step in pipeline:
        query = f'SELECT * FROM "{step.table}"'
        assert sorted(rebuilt.query(query, max_rows=100_000).rows, key=repr) == \
            sorted(frozen.query(query, max_rows=100_000).rows, key=repr), step.table


# ── the canonical world's story, on the real packages ─────────────────────────────────────
STG = path_of("stg_orders")
FIRST = FAMILIES[0]
STAGE_EVERY_ORDER = "SELECT order_id, order_date, distributor, amount_usd FROM raw_orders"


def repair(state: str, patch: dict[str, str], family=FIRST):
    context, tools, *_ = incident_from_dir(INCIDENTS / incident_id(family, state))
    decision = InvestigationDecision(Disposition.REPAIR, None, "A proposed repair.", "R", patch)
    return run_incident("story", context, ScriptedInvestigator((), decision), tools,
                        Validator(), configuration={"provider": "scripted", "model": None})


@pytest.mark.parametrize("family", FAMILIES, ids=lambda f: f.name)
def test_the_repair_validity_rule_holds_on_every_repair_case(family):
    """The permitted transform is the cause: restoring it alone is accepted and admissible;
    the chart-only fake and the defect resubmitted are rejected."""
    assert incident_id(family, REPAIR_STATE) not in BURNED
    restored = repair(REPAIR_STATE, {STG: staging(family, "business-changed")}, family)
    assert restored.validation.state == "ACCEPT" and restored.admissible
    fake = scale_to_the_total(family.day, staging(family, REPAIR_STATE))
    assert repair(REPAIR_STATE, {STG: fake}, family).validation.state == "REJECT"
    same = repair(REPAIR_STATE, {STG: staging(family, REPAIR_STATE)}, family)
    assert same.validation.state == "REJECT"


def test_the_chart_recovers_and_the_missing_orders_do_not_so_it_is_rejected():
    fake = scale_to_the_total(FIRST.day, staging(FIRST, REPAIR_STATE))
    record = repair(REPAIR_STATE, {STG: fake})
    assert record.authorization.authorized and record.validation.state == "REJECT"
    assert "daily_revenue_is_the_delivered_orders: holds" in record.validation.report
    assert "every_delivered_order_is_staged_once: fails" in record.validation.report
    assert not record.admissible


def test_the_staging_repaired_is_accepted_and_admissible():
    record = repair(REPAIR_STATE, {STG: STAGE_EVERY_ORDER})
    assert record.authorization.authorized and record.validation.state == "ACCEPT"
    assert record.admissible


@pytest.mark.parametrize("state", ["business-changed", "cannot-decide"])
def test_a_repair_of_a_world_that_was_never_broken_here_changes_nothing(state):
    record = repair(state, {STG: STAGE_EVERY_ORDER})
    assert record.validation.state == "REJECT"
    assert "changes_the_world: fails" in record.validation.report


def test_the_bait_is_in_every_world_and_the_evidence_is_not():
    for family in FAMILIES:
        folders = [INCIDENTS / incident_id(family, s) for s in STATES]
        changes = {(f / "change_history_sources" / "CHANGE_HISTORY.md").read_text(
            encoding="utf-8") for f in folders}
        # the release is in every world; the staging change that caused it only where it did
        assert all(family.release in c for c in changes)
        assert len(changes) == 2 and sum("DATA-97" in c for c in changes) == 1
        notices = {json.dumps(sorted((p.name, p.read_text(encoding="utf-8"))
                                     for p in (f / "notice_sources").iterdir())) for f in folders}
        # explicit families say what happened, so the worlds' notices differ — the staging
        # change's say what the load-stopped world's said: agreements and ingestion are
        # normal; implicit families say nothing telling, so the evidence is only in the data
        assert len(notices) == (3 if family.explicit else 1), family.name


# ── every case is solvable, and its labels agree with the world ───────────────────────────
CATALOGUE = Path(__file__).resolve().parents[2] / "adii" / "evaluation" / "catalogue"


@pytest.mark.parametrize("family", FAMILIES, ids=lambda f: f.name)
@pytest.mark.parametrize("state", STATES)
def test_every_case_is_solvable_and_its_labels_agree_with_its_world(family, state):
    case = incident_id(family, state)
    key_path = CATALOGUE / f"{case}.answer.json"
    key = load_frozen_answer_key(key_path)
    grounding = load_grounding_key(CATALOGUE / f"{case}.grounding.json")
    assert grounding["answer_key_filename"] == key_path.name
    context, tools, *_ = incident_from_dir(INCIDENTS / case)
    record = run_incident("ideal", context, Ideal(*ideal(family, state)), tools, Validator(),
                          configuration={"provider": "scripted", "model": None})
    assert record.termination == "submitted", record.detail
    if state in ("load-stopped", REPAIR_STATE):
        assert record.validation.state == "ACCEPT" and record.admissible
    report = build_evaluation_report(json.loads(record.to_json()), key, grounding_key=grounding)
    assert report["category"] in ("success", "correct_abstention"), report
    assert report["grounding"]["decisive"] == {"observed": True, "cited": True, "missing": []}


def test_every_package_has_a_frozen_key_and_a_bound_grounding_key():
    assert sorted(p.name.removesuffix(".answer.json") for p in CATALOGUE.glob("*.answer.json")) \
        == [p.name for p in FOLDERS]


def test_an_incident_id_is_one_path_segment_never_a_way_out_of_the_packages(capsys):
    from adii.runtime import __main__ as cli
    assert cli.main(["--incident", "../walkthrough", "--provider", "local", "--model", "x"]) == 2
    assert "no such incident" in capsys.readouterr().out


def test_the_same_decisions_when_the_world_is_twenty_times_larger():
    """The scale ladder's smallest rung, in the suite: the first family at 30,000 orders
    reaches the same decisions, and the validator the same verdicts, as at its own size."""
    grown = measure(30_000)["states"]
    assert {s: r["category"] for s, r in grown.items()} == {
        "business-changed": "success", "cannot-decide": "correct_abstention",
        REPAIR_STATE: "success"}
    assert grown[REPAIR_STATE]["validation"] == "ACCEPT"
    assert grown[REPAIR_STATE]["fake_repair"] == "REJECT"
    assert all(r["decisive"] for r in grown.values())
