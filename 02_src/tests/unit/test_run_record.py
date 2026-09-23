"""The run record is the shape the archive stores and the inspector renders. These pin the
two refusals that make it a record rather than a dump: an unknown schema is never guessed
at, and a value that is not JSON never reaches a sink."""
from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path

import pytest
from adii.contracts import RepairAuthorization, TraceEvent, ValidationResult
from adii.examples.walkthrough import load
from adii.reporting.record import (
    SCHEMA,
    V1,
    RunRecord,
    from_json,
    read_record,
    reserve,
    strict,
    write_record,
)
from adii.runtime.run import authorize

COMMITTED = Path(__file__).resolve().parents[3] / "01_data" / "walkthrough" / "record.json"


def walkthrough_record() -> RunRecord:
    context, run = load()
    return RunRecord.from_run("demo-learning-001", context, run,
                              configuration={"provider": "fixture", "model": None},
                              origin="walkthrough",
                              authorization=authorize(context, run.decision))


def test_a_record_round_trips_through_strict_json():
    record = walkthrough_record()
    assert from_json(record.to_json()) == record


def test_the_committed_v1_fixture_loads_under_its_declared_version():
    """When v2 exists this file stays: a fixture of every historical shape must keep loading
    under the version it declares. Provenance is the only part that legitimately differs."""
    assert json.loads(COMMITTED.read_text(encoding="utf-8"))["schema"] == V1
    committed, fresh = read_record(COMMITTED), walkthrough_record()
    assert json.loads(fresh.to_json())["schema"] == SCHEMA == "adii.run_record/v2"
    assert replace(committed, provenance={}) == replace(fresh, provenance={})


def test_a_verdict_that_could_not_be_established_round_trips_and_older_records_load():
    """Row 3: `reason_code` travels in the record. A record written before the field existed
    has none and loads as the legacy placeholder — loadable, and never produced anew."""
    record = walkthrough_record()
    not_checkable = replace(record, validation=ValidationResult(
        accepted=False, report="Not checkable: no world", reason_code="no_rebuildable_world"))
    back = from_json(not_checkable.to_json())
    assert back == not_checkable and back.validation.state == "NOT_CHECKABLE"
    doc = json.loads(record.to_json())
    doc["validation"] = {"accepted": False, "checks_run": [], "report": "no validator yet"}
    with pytest.raises(ValueError, match="record is missing 'reason_code'"):
        from_json(json.dumps(doc))          # inherited D4: v2 has the field, always
    assert from_json(json.dumps({**doc, "schema": V1})).validation.state == "UNCHECKED"


def test_the_authorization_fact_round_trips_and_records_before_it_load_without_one():
    """Row 4: the runtime's fact travels in the record; a record written before it existed
    has no such key and loads with none — which the page and the report say, rather than
    implying a fact nobody established. It is never carried by a run without a repair."""
    record = walkthrough_record()
    assert record.authorization.authorized is True and record.admissible is True
    denied = replace(record, authorization=RepairAuthorization(
        authorized=False, checked_paths=("transforms/stg_orders.sql",),
        denied_paths=("transforms/stg_orders.sql",), reason_code="target_not_permitted"))
    assert from_json(denied.to_json()) == denied and denied.admissible is False
    doc = json.loads(record.to_json())
    del doc["authorization"]
    with pytest.raises(ValueError, match="record is missing 'authorization'"):
        from_json(json.dumps(doc))
    older = from_json(json.dumps({**doc, "schema": V1}))
    assert older.authorization is None and older.admissible is False
    doc = json.loads(record.to_json())
    doc["decision"] = {"disposition": "NO_REPAIR", "root_cause_id": None,
                       "root_cause_summary": "the business moved", "repair_id": None, "patch": {},
                       "evidence_refs": []}
    doc["validation"] = None
    with pytest.raises(ValueError, match="only a REPAIR decision has targets to authorize"):
        from_json(json.dumps(doc))


def test_citations_round_trip_and_a_record_never_cites_what_its_trace_never_minted():
    """Trace contract row 3: the decision's citations travel in the record; a record written
    before the field loads citing nothing; and a record whose decision cites an id its own
    trace never minted is refused where the record is built — a hand-edited archive cannot
    manufacture grounding."""
    record = walkthrough_record()
    assert len(record.decision.evidence_refs) == 3
    assert from_json(record.to_json()).decision.evidence_refs == record.decision.evidence_refs
    doc = json.loads(record.to_json())
    del doc["decision"]["evidence_refs"]
    with pytest.raises(ValueError, match="record is missing 'evidence_refs'"):
        from_json(json.dumps(doc))
    assert from_json(json.dumps({**doc, "schema": V1})).decision.evidence_refs == ()
    doc = json.loads(record.to_json())
    doc["decision"]["evidence_refs"] = [doc["decision"]["evidence_refs"][0], "ev-never-minted"]
    with pytest.raises(ValueError, match="cites evidence its trace never minted: ev-never-minted"):
        from_json(json.dumps(doc))
    with pytest.raises(ValueError, match="never minted"):
        replace(record, decision=replace(record.decision, evidence_refs=("ev-never-minted",)))


def test_an_unknown_schema_is_refused_not_guessed():
    doc = json.loads(walkthrough_record().to_json())
    doc["schema"] = "adii.run_record/v3"
    with pytest.raises(ValueError, match="unknown record schema"):
        from_json(json.dumps(doc))


def test_a_record_missing_a_field_says_which():
    doc = json.loads(walkthrough_record().to_json())
    del doc["counters"]
    with pytest.raises(ValueError, match="missing 'counters'"):
        from_json(json.dumps(doc))


def test_a_non_finite_value_never_reaches_a_sink(tmp_path):
    """NaN written into an archive is a record no conforming parser reads back, so it is
    refused before the directory is even reserved."""
    record = walkthrough_record()
    poisoned = replace(record, trace=record.trace + (
        TraceEvent(sequence=99, kind="tool_result", payload={"cost": math.inf}),))
    with pytest.raises(ValueError):
        poisoned.to_json()
    with pytest.raises(ValueError):
        write_record(poisoned, tmp_path)
    assert not (tmp_path / record.label).exists()
    with pytest.raises(ValueError, match="finite"):
        replace(record, api_cost_usd=math.nan)


def test_strict_on_the_way_in_too():
    text = walkthrough_record().to_json().replace('"api_cost_usd": 0.0142',
                                                  '"api_cost_usd": NaN')
    with pytest.raises(ValueError, match="not JSON"):
        from_json(text)


def test_a_record_of_the_wrong_shape_is_refused_with_a_message():
    """The schema line alone proves nothing. A hand-edited record with a string where the
    trace should be is refused as unreadable, not left to crash whoever lists the archive."""
    doc = json.loads(walkthrough_record().to_json())
    doc["trace"] = "oops"
    with pytest.raises(ValueError, match="malformed"):
        from_json(json.dumps(doc))
    # a patch that is not path -> text (R0 of 17 Sep archived one and crashed both renderers)
    doc = json.loads(walkthrough_record().to_json())
    doc["decision"]["patch"] = {"ledger": {"day": "2026-03-09", "settled_usd": 91340.0}}
    with pytest.raises(ValueError, match="patch must map each path"):
        from_json(json.dumps(doc))


def test_a_label_is_one_path_segment():
    """The label names the run's directory and its URL. Anything that could leave the
    archive, nest inside it, or fail to survive a URL is refused at construction."""
    record = walkthrough_record()
    for bad in ("", "../escape", "nested/run", "with space", ".hidden", "back\\slash"):
        with pytest.raises(ValueError, match="one path segment"):
            replace(record, label=bad)
    assert replace(record, label="demo-learning-001-20260913T132843Z")


def test_a_record_carries_no_machine_specific_path():
    """A record is verified on another machine or not at all."""
    assert not re.search(r"(/Users/|/home/|[A-Za-z]:\\)", walkthrough_record().to_json())


def test_only_a_submitted_run_carries_a_decision():
    record = walkthrough_record()
    with pytest.raises(ValueError, match="submitted"):
        replace(record, termination="bound_hit", detail="tool_calls: 40 of 40 used")
    with pytest.raises(ValueError, match="termination must be one of"):
        replace(record, termination="gave_up", decision=None, validation=None)


def test_a_poisoned_record_is_salvaged_as_an_infrastructure_failure():
    """The event that is not JSON is dropped and named; every other event stays; the result
    is a record that writes. A clean record passes through untouched."""
    record = walkthrough_record()
    poisoned = replace(record, trace=record.trace + (
        TraceEvent(sequence=99, kind="tool_result", payload={"cost": math.inf}),))
    salvaged = strict(poisoned)
    assert salvaged.termination == "infrastructure_failure"
    assert "not strict JSON" in salvaged.detail
    assert salvaged.trace == record.trace and salvaged.decision is None
    assert from_json(salvaged.to_json()) == salvaged
    assert strict(record) is record


def test_a_label_is_reserved_once_and_only_when_valid(tmp_path):
    assert reserve(tmp_path, "one") == tmp_path / "one"
    with pytest.raises(FileExistsError, match="a label names one run"):
        reserve(tmp_path, "one")
    with pytest.raises(ValueError, match="one path segment"):
        reserve(tmp_path, "../two")
    assert not (tmp_path.parent / "two").exists()


def test_a_label_names_one_run_forever(tmp_path):
    record = walkthrough_record()
    path = write_record(record, tmp_path)
    assert read_record(path) == record
    with pytest.raises(FileExistsError):
        write_record(record, tmp_path)
