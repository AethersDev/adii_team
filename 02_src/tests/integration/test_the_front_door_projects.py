"""What the front door says about a run is a projection of the run's record, and nothing else.

view.js is evaluated in node, exactly as the page runs it, over records the real runtime
writes for the demo company's incidents: the fix that stands, a fix the rebuild rejects, a
fix outside what may be changed, the drop that is real, the evidence that cannot decide,
and a run that ended without an answer. The rules of decisions F1–F3 are held here: the
symptom is never evidence, the rebuild is the validator's, and "What the decision cites" is
the cited observations only. So are two more: a decision is the investigator's recommendation
and never the page's finding, and an observation is never cut without saying so.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
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
    """Evaluate one projection of view.js in node. The record goes through a file, not stdin:
    reading stdin as a file (`readFileSync(0)`) is fragile on Windows pipes; and node's own
    error is reported when it fails, never only its exit status."""
    with tempfile.TemporaryDirectory() as folder:
        given = Path(folder) / "record.json"
        given.write_text(json.dumps(record), encoding="utf-8")
        script = (f"const V = require({json.dumps(str(VIEW))});"
                  f"const r = JSON.parse(require('fs').readFileSync("
                  f"{json.dumps(str(given))}, 'utf8'));"
                  f"const out = V[{json.dumps(fn)}](r, ...{json.dumps(args)});"
                  f"process.stdout.write(JSON.stringify(out));")
        done = subprocess.run([node(), "-e", script], capture_output=True, text=True,
                              encoding="utf-8")
    assert done.returncode == 0, f"node failed on {fn}:\n{done.stderr.strip()}"
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


def results(record: dict) -> list[dict]:
    return [e["payload"] for e in record["trace"] if e["kind"] == "tool_result"]


def cited_card(record: dict, tool: str) -> dict:
    return next(c for c in view("cited", record) if c["tool"] == tool)


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


@pytest.mark.parametrize(("name", "key", "disposition"), [
    ("fix", "fix", "REPAIR"),
    ("rejected", "fix", "REPAIR"),
    ("denied", "fix", "REPAIR"),
    ("leave", "leave", "NO_REPAIR"),
    ("escalate", "escalate", "ESCALATE"),
])
def test_the_headline_is_the_recorded_disposition_as_the_investigators_recommendation(
        runs, name, key, disposition):
    said = view("verdict", runs[name])
    assert (said["key"], said["headline"]) == (key, f"Investigator recommended {disposition}")
    assert said["summary"] == runs[name]["decision"]["root_cause_summary"]


NO_GATE = "It proposed no change, so the authorizer and validator checked nothing."


@pytest.mark.parametrize(("state", "wrong"), [
    ("cannot-decide", InvestigationDecision(Disposition.NO_REPAIR, None, "The fall is real.")),
    ("business-changed", InvestigationDecision(Disposition.ESCALATE, None, "I cannot tell.")),
])
def test_a_wrong_decision_reads_like_a_right_one_because_the_page_cannot_tell_them_apart(
        state, wrong):
    """The audit of 6 Nov: "Nothing needs fixing" and "The evidence here can't settle it" were
    fixed sentences, drawn over decisions the keys mark wrong and over runs that looked at
    nothing. The page's words come from the record, and the record does not say who was
    right: a decision against its case's truth gets what any other decision of its kind gets,
    citing everything it saw, and the investigator's own sentence is labelled as its own."""
    record = recorded(state, wrong)
    collected = sum(r["status"] == "OK" for r in results(record))
    said = view("verdict", record)
    assert said["headline"] == f"Investigator recommended {wrong.disposition.value}"
    assert said["lead"] == NO_GATE
    assert said["summary"] == wrong.root_cause_summary
    assert said["basis"] == (f"The decision cites {collected} of the {collected} tool "
                             "observations this run collected.")


def test_the_page_does_not_state_a_decision_as_its_own_finding(runs):
    for name in ("leave", "escalate"):
        assert view("verdict", runs[name])["lead"] == NO_GATE
        investigator = view("signoff", runs[name])[0]
        disposition = runs[name]["decision"]["disposition"]
        assert investigator["note"] == f"Recommended {disposition}. Proposed no change."
    assert view("verdict", runs["fix"])["lead"].startswith("A fix was proposed, it is within")


def test_a_run_with_no_tool_observations_says_so(runs):
    """44 archived escalations made no tool call. Refused calls mint nothing, so a run whose
    every call was refused has collected nothing either."""
    tool_events = ("tool_call", "tool_result")
    bare = {**runs["escalate"], "trace": [e for e in runs["escalate"]["trace"]
                                          if e["kind"] not in tool_events]}
    assert view("verdict", bare)["basis"] == "This run collected no tool observations."
    refused = json.loads(json.dumps(runs["escalate"]))
    for result in results(refused):
        result["status"] = "REJECTED"
    assert view("verdict", refused)["basis"] == "This run collected no tool observations."
    assert view("verdict", bare)["headline"] == "Investigator recommended ESCALATE"


def test_the_basis_is_counted_from_the_record_and_never_called_support(runs):
    collected = sum(r["status"] == "OK" for r in results(runs["leave"]))
    record = json.loads(json.dumps(runs["leave"]))
    record["decision"]["evidence_refs"] = record["decision"]["evidence_refs"][:1]
    assert view("verdict", record)["basis"] == \
        f"The decision cites 1 of the {collected} tool observations this run collected."
    record["decision"]["evidence_refs"] = []
    assert view("verdict", record)["basis"] == \
        f"This run collected {collected} tool observations, and the decision cites none of them."
    del record["decision"]["evidence_refs"]      # a record written before citations existed
    assert "predates citations" in view("verdict", record)["basis"]


def test_the_deciding_receipt_is_reachable_numbered_and_the_tool_layers(runs):
    """The audit of 6 Nov: the receipt that decides the undecidable case is the log's last
    line, and the card stopped at line 8 without saying so. The compact view keeps the end,
    says what it leaves out, opens to all of it, keeps the source's line numbers, and calls
    the card what it is: the tool layer's result, which the investigator did not write."""
    record = runs["escalate"]
    [log] = [r for r in results(record) if r["name"] == "read_reconciliation"]
    lines = log["content"]["lines"]
    assert "not received" in lines[-1] and len(lines) > 8, "the world this test is about changed"
    card = cited_card(record, "read_reconciliation")
    assert card["origin"] == "Returned by the tool layer"
    assert card["ref"] == log["content"]["evidence_id"] and log["status"] == "OK"
    assert lines[-1] not in record["decision"]["root_cause_summary"]
    block = card["lines"]
    assert block["shown"][-1] == {"n": len(lines), "text": lines[-1]}
    assert [line["n"] for line in block["shown"]] == list(range(len(lines) - 7, len(lines) + 1))
    assert block["all"] == [{"n": i + 1, "text": text} for i, text in enumerate(lines)]
    assert block["note"] == (f"The last 8 of {len(lines)} lines read. The other "
                             f"{len(lines) - 8} are not shown here.")
    assert block["expand"] == f"Show all {len(lines)} lines read"
    assert card["received"] is None


def test_a_log_the_run_read_only_part_of_says_so_and_keeps_its_line_numbers(runs):
    """What the page left out and what the run never read are different facts."""
    [log] = [r for r in results(runs["escalate"]) if r["name"] == "read_reconciliation"]
    window = log["content"]["lines"][5:8]
    total = len(log["content"]["lines"])
    part = json.loads(json.dumps(runs["escalate"]))
    [got] = [r for r in results(part) if r["name"] == "read_reconciliation"]
    got["content"].update(offset=5, lines=window, returned=3, truncated=True)
    card = next(c for c in view("cited", part) if c["tool"] == "read_reconciliation")
    assert card["received"] == f"The run read lines 6–8 of {total}."
    assert card["lines"]["all"] == [{"n": 6 + i, "text": text} for i, text in enumerate(window)]
    assert card["lines"]["note"] is None
    got["content"].update(offset=total, lines=[], returned=0, truncated=False)
    card = next(c for c in view("cited", part) if c["tool"] == "read_reconciliation")
    assert card["received"] == f"The run read none of the log's {total} lines."


def test_a_long_table_says_what_it_leaves_out_and_opens_to_all_of_it():
    query = "SELECT day, orders FROM mart_daily_revenue ORDER BY day"
    record = recorded("cannot-decide", calls=[("run_sql", {"query": query})])
    rows = next(r["content"]["rows"] for r in results(record)
                if r["name"] == "run_sql")
    assert len(rows) > 6, "the world this test is about changed"
    card = cited_card(record, "run_sql")
    table = card["table"]
    assert (table["shown"], table["all"]) == (rows[:6], rows)
    assert table["note"] == (f"The first 6 of {len(rows)} returned rows. The other "
                             f"{len(rows) - 6} are not shown here.")
    assert table["expand"] == f"Show all {len(rows)} returned rows"
    assert card["received"] is None


def test_rows_the_tool_withheld_are_said_even_when_the_page_cuts_nothing(runs):
    """The review of 6 Nov: what the page hides and what the tool withheld are different
    limits. A result short enough for the page to show whole carries no page note, so nothing
    else on the card could stand in for this sentence."""
    short = json.loads(json.dumps(runs["escalate"]))
    got = next(r for r in results(short) if r["name"] == "run_sql")
    got["content"].update(columns=["a"], rows=[[1], [2]], row_count=2, max_rows=2, truncated=True)
    card = next(c for c in view("cited", short) if c["ref"] == got["content"]["evidence_id"])
    assert (card["table"]["note"], card["table"]["expand"]) == (None, None)
    assert card["received"] == ("The tool stopped at 2 rows. The query had more, and the run "
                                "never received them.")


def test_the_real_tool_stopping_a_query_is_said_beside_the_pages_own_note():
    """Through the real tool layer. The two limits appear together and say different things."""
    record = recorded("cannot-decide", calls=[("run_sql", {"query": "SELECT * FROM raw_orders"})])
    got = next(r["content"] for r in results(record) if r["name"] == "run_sql")
    assert got["truncated"] is True, "the world this test is about changed"
    limit = got["max_rows"]
    card = cited_card(record, "run_sql")
    assert card["received"].startswith(f"The tool stopped at {limit} rows.")
    assert card["table"]["expand"] == f"Show all {limit} returned rows"
    assert len(card["table"]["all"]) == limit


def test_short_observations_are_whole_and_say_nothing_about_being_cut(runs):
    card = cited_card(runs["fix"], "get_transform")
    source = next(r["content"]["source"] for r in results(runs["fix"])
                  if r["name"] == "get_transform")
    assert [line["text"] for line in card["lines"]["all"]] == source.rstrip("\n").split("\n")
    assert card["lines"]["note"] is None and card["lines"]["expand"] is None
    notice = cited_card(runs["fix"], "get_notice")
    assert notice["text"] and "note" not in notice


def test_a_long_transform_and_a_long_notice_are_not_cut_silently(runs):
    """These limits never fired in the archive; a limit that fires silently the first time it
    does is the defect the receipt had."""
    longer = json.loads(json.dumps(runs["fix"]))
    for result in results(longer):
        if result["name"] == "get_transform":
            result["content"]["source"] = "\n".join(f"-- line {i}" for i in range(1, 31))
        if result["name"] == "get_notice":
            result["content"]["content"] = "x" * 900
    cards = {c["tool"]: c for c in view("cited", longer)}
    block = cards["get_transform"]["lines"]
    assert len(block["shown"]) == 14 and len(block["all"]) == 30
    assert block["note"] == "The first 14 of 30 lines. The other 16 are not shown here."
    assert cards["get_notice"]["text"] == "x" * 900


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


def test_what_the_decision_cites_is_what_it_cited_and_investigated_is_everything(runs):
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
    assert said["headline"] == "Investigator recommended REPAIR"
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
