"""What the front door says about a run is a projection of the run's record, and nothing else.

view.js is evaluated in node, exactly as the page runs it, over records the real runtime
writes for the demo company's incidents: the fix that stands, a fix the rebuild rejects, a
fix outside what may be changed, the drop that is real, the evidence that cannot decide,
and a run that ended without an answer. The three rules of decisions F1–F3 are held here:
the symptom is never evidence, the rebuild is the validator's, and "How ADII knows" is the
cited observations only.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from adii.contracts import Disposition, InvestigationDecision
from adii.evaluation.scale import Ideal, ideal, scale_to_the_total
from adii.examples.canonical_world import DEMO, INCIDENTS, incident_id, staging
from adii.runtime.__main__ import alerted_series, incident_from_dir
from adii.runtime.run import run_incident
from adii.validation.patching import path_of
from adii.validation.validator import Validator

VIEW = Path(__file__).resolve().parents[2] / "adii" / "demo" / "web" / "view.js"
STG = path_of("stg_orders")
MORE = [("get_change_history", {"history_id": "pipeline-changes"}),
        ("get_notice", {"notice_id": "commercial-bulletin"})]


def node() -> str:
    found = shutil.which("node")
    if not found:
        pytest.skip("node is not installed; the page's projections are evaluated in it")
    return found


def view(fn: str, record: dict, *args):
    script = (f"const V = require({json.dumps(str(VIEW))});"
              f"const r = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              f"const out = V[{json.dumps(fn)}](r, ...{json.dumps(args)});"
              f"process.stdout.write(JSON.stringify(out));")
    done = subprocess.run([node(), "-e", script], input=json.dumps(record), capture_output=True,
                          text=True, encoding="utf-8", check=True)
    return json.loads(done.stdout)


def recorded(state: str, decision=None, calls=None) -> dict:
    case = incident_id(DEMO, state)
    context, tools, *_ = incident_from_dir(INCIDENTS / case)
    wanted, ideal_decision = ideal(DEMO, state)
    record = run_incident("t", context, Ideal([*(calls or wanted), *MORE],
                                              decision or ideal_decision),
                          tools, Validator(), configuration={"provider": "scripted"},
                          alert=alerted_series(INCIDENTS / case))
    return json.loads(record.to_json())


@pytest.fixture(scope="module")
def runs() -> dict:
    fake = scale_to_the_total(DEMO.day, staging(DEMO, "transform-defect"))
    return {
        "fix": recorded("transform-defect"),
        "rejected": recorded("transform-defect", InvestigationDecision(
            Disposition.REPAIR, None, "Scale the day up.", "SCALE", {STG: fake})),
        "denied": recorded("transform-defect", InvestigationDecision(
            Disposition.REPAIR, None, "Patch the mart.", "MART",
            {path_of("mart_daily_revenue"): "SELECT 1"})),
        "leave": recorded("business-changed"),
        "escalate": recorded("cannot-decide"),
    }


@pytest.mark.parametrize(("name", "key", "headline"), [
    ("fix", "fix", "Yes. Fix it."),
    ("rejected", "fix", "A fix was proposed. It was not approved."),
    ("denied", "fix", "A fix was proposed. It was not approved."),
    ("leave", "leave", "No. Leave it."),
    ("escalate", "escalate", "Not yet. Escalate it."),
])
def test_the_answer_is_the_records_and_a_fix_stands_only_when_both_authorities_let_it(
        runs, name, key, headline):
    said = view("verdict", runs[name])
    assert (said["key"], said["headline"]) == (key, headline)
    assert said["summary"] == runs[name]["decision"]["root_cause_summary"]


def test_a_refused_fix_says_which_authority_refused_it(runs):
    assert view("verdict", runs["rejected"])["lead"].startswith("The independent rebuild rejected")
    assert view("verdict", runs["denied"])["lead"].startswith("It touches something outside")
    denied = {s["who"]: s["status"] for s in view("signoff", runs["denied"])}
    assert denied["Authorizer"] == "Refused"
    fixed = {s["who"]: s["status"] for s in view("signoff", runs["fix"])}
    assert fixed == {"Investigator": "Proposed a fix", "Authorizer": "Allowed",
                     "Validator": "Accepted"}
    left = {s["who"]: s["status"] for s in view("signoff", runs["leave"])}
    assert left == {"Investigator": "No fix proposed", "Authorizer": "Not needed",
                    "Validator": "Not needed"}


@pytest.mark.parametrize(("termination", "detail", "headline"), [
    ("bound_hit", "max_cost_usd: spent $0.24 ...", "Stopped at the spending cap."),
    ("bound_hit", "model_turns: 20 of 20 used", "Stopped at a limit."),
    ("model_failure", "the model stopped", "The investigator stopped without an answer."),
    ("infrastructure_failure", "provider unreachable", "The run couldn't finish."),
])
def test_a_run_without_an_answer_says_how_it_ended_and_that_nothing_changed(
        runs, termination, detail, headline):
    ended = {**runs["leave"], "decision": None, "validation": None, "authorization": None,
             "termination": termination, "detail": detail}
    said = view("verdict", ended)
    assert (said["key"], said["headline"], said["detail"]) == ("none", headline, detail)
    assert said["lead"].endswith("Nothing was changed.")
    assert not any(s["landed"] for s in view("slots", ended))


def test_the_symptom_is_the_runtimes_reading_and_never_evidence(runs):
    """F1: the chart's 'before' is `alert_observed`; the cited evidence never includes it,
    and holds exactly the decision's refs, in their order."""
    record = runs["leave"]
    alert = next(e["payload"] for e in record["trace"] if e["kind"] == "alert_observed")
    assert view("series", record)["before"]["rows"] == alert["rows"]
    cited = view("cited", record)
    assert [c["ref"] for c in cited] == record["decision"]["evidence_refs"]
    assert all(c["tool"] != "alert_observed" for c in cited)
    assert len(view("investigated", record)) >= len(cited)


def test_how_adii_knows_is_what_the_decision_cited_and_investigated_is_everything(runs):
    """F3: a decision that cites only some of what it saw is shown citing only those."""
    record = json.loads(json.dumps(runs["leave"]))
    record["decision"]["evidence_refs"] = record["decision"]["evidence_refs"][:1]
    assert len(view("cited", record)) == 1
    assert len(view("investigated", record)) == len(view("investigated", runs["leave"]))


def test_after_validation_is_the_validators_series_and_a_recovered_chart_can_still_fail(runs):
    """F2: the rebuild is drawn from `rebuilt_series`; the fake recovers the chart and its
    checks still say it failed."""
    fixed, faked = view("series", runs["fix"]), view("series", runs["rejected"])
    assert fixed["rebuilt"]["rows"] == runs["fix"]["validation"]["rebuilt_series"]
    assert faked["rebuilt"]["rows"][-1][1] == pytest.approx(fixed["rebuilt"]["rows"][-1][1])
    assert any(not c["held"] for c in view("checks", runs["rejected"]))
    assert all(c["held"] for c in view("checks", runs["fix"]))
    assert view("series", runs["leave"])["rebuilt"] is None


def test_the_proposed_fix_is_diffed_against_the_transformation_the_run_observed(runs):
    [change] = view("proposal", runs["fix"])
    assert change["path"] == STG and change["observed"]
    removed = [line["text"] for line in change["lines"] if line["op"] == "-"]
    assert any("DATA-97" in text for text in removed)
    assert any("Juniper" in text for text in removed)


def test_a_row_of_the_list_is_the_indexs_facts():
    now = 1_000_000_000_000
    row = {"label": "x", "alert": "Revenue fell.", "disposition": "REPAIR", "admissible": False,
           "changed": ["transforms/stg_orders.sql"], "written_at": "2001-09-09T01:46:40+00:00"}
    said = view("row", row, now)
    assert (said["answer"], said["title"], said["change"], said["when"]) == \
        ("fix", "Revenue fell.", "Proposed, not approved", "Just now")
    assert view("row", {"label": "y", "running": True}, now)["answer"] == "running"
    assert view("row", {"label": "z", "termination": "model_failure", "changed": []},
                now)["answer"] == "none"


def test_an_older_record_is_read_for_what_it_holds_never_as_a_rejection(runs):
    """The audit of 24 Sep: a record written before the authorization fact existed, or before
    any validator ran, was shown as "the independent rebuild rejected it". It says what it
    holds instead."""
    before = {**runs["fix"], "authorization": None}
    said = view("verdict", before)
    assert said["headline"] == "A fix was proposed. It was not approved."
    assert "predates the authorization check" in said["lead"]
    assert {s["who"]: s["status"] for s in view("signoff", before)}["Authorizer"] == "Not recorded"
    unchecked = {**runs["fix"], "validation": {"accepted": False, "report": "not checked",
                                               "checks_run": [], "reason_code": None}}
    assert view("verdict", unchecked)["lead"].startswith("No validator checked it.")
    assert {s["who"]: s["status"] for s in view("signoff", unchecked)}["Validator"] == \
        "Not checked"


def test_a_check_is_marked_only_where_the_validator_stated_it(runs):
    prose = {**runs["rejected"], "validation": {**runs["rejected"]["validation"],
                                                "report": "Rejected: totals drift; see log"}}
    assert view("checks", prose) == [{"name": "report", "said": "Rejected: totals drift; see log",
                                      "held": None}]
    marked = view("checks", runs["rejected"])
    assert marked[0]["name"] == "rebuild" and marked[0]["held"] is True
    assert [c["held"] for c in marked[1:]].count(False) >= 1


def test_spend_is_a_lower_bound_that_counts_what_was_never_priced(runs):
    paid = {**runs["leave"], "configuration": {"provider": "openai", "max_cost_usd": 0.5},
            "counters": {**runs["leave"]["counters"], "api_cost_usd": 0.0123},
            "trace": [{"kind": "model_requested", "payload": {}},
                      {"kind": "model_responded", "payload": {"usage": {"prompt_tokens": 5,
                                                                        "completion_tokens": 2}}},
                      {"kind": "model_requested", "payload": {}},
                      {"kind": "model_responded", "payload": {"usage": None}}]}
    assert view("spend", paid) == "at least $0.0123 of a $0.50 cap; 1 request(s) without usage"
    assert view("spend", {**runs["leave"], "configuration": {"provider": "fixture"}}) == \
        "Nothing spent: no model was asked"
    assert view("row", {"label": "x", "running": False,
                        "error": "a receipt was written, but no record; the run did not finish"},
                1)["answerLabel"] == "Did not finish"
