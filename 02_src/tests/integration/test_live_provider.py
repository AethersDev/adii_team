"""The live path, end to end, with a stand-in model: A's real loop, driven by the real
runtime, over B's real tools, with a `ChatProvider` talking to an OpenAI-compatible endpoint served
here by the standard library. One trace — model requests and responses recorded at the
provider boundary, tool calls and results at the tool boundary, the decision by the
runtime — lands in one `adii.run_record/v1` the inspector renders. No model, no network
beyond the loopback, no money."""
from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer

import pytest
from adii.contracts import ToolCall
from adii.examples.specimens import ORDERS_MISSING
from adii.provider import ChatProvider, endpoint_is_local
from adii.reporting import read_record
from adii.reporting.receipts import NAME as RECEIPT
from adii.reporting.receipts import read_receipt
from adii.runtime import __main__ as cli
from adii.runtime.run import Recorder
from adii.tools import ReadOnlyDatabase, build_sql_tools

from .fake_model import FakeModel

INCIDENT = "orders-missing-day"
TURNS = [   # what the scripted stand-in model says, in order, in A's protocol
    '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
    '<TOOL_CALL>{"name": "run_sql", "arguments": {"query": "SELECT run_date, status, note '
    'FROM loads WHERE run_date = \'2026-03-12\'"}}',
    "Thinking about the failed load.",
    '<DECISION>{"disposition": "ESCALATE", "root_cause_id": null, "root_cause_summary": '
    '"The 2026-03-12 load failed at row 55 and was rolled back; whether re-running it is '
    'safe needs the source owner.", "repair_id": null, "patch": {}}',
]


@pytest.fixture
def endpoint():
    FakeModel.script, FakeModel.seen = list(TURNS), []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def test_a_live_run_leaves_one_record_with_one_trace(tmp_path, endpoint):
    code = cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "test-model-1", "--archive", str(tmp_path), "--label", "live",
                     "--no-report"])
    assert code == 0
    r = read_record(tmp_path / "live" / "record.json")
    kinds = [e.kind for e in r.trace]
    assert kinds == ["incident_received",
                     "model_requested", "model_responded", "tool_call", "tool_result",
                     "model_requested", "model_responded", "tool_call", "tool_result",
                     "model_requested", "model_responded",              # the plain-text turn
                     "model_requested", "model_responded", "decision_submitted"]
    assert r.decision.disposition.value == "ESCALATE" and r.validation is None
    assert r.model_turns == 4 and r.tool_calls == 2 and r.api_cost_usd == 0.0
    assert r.configuration["model"] == "test-model-1"
    assert r.configuration["execution_mode"] == "live"
    results = [e.payload for e in r.trace if e.kind == "tool_result"]
    assert all(p["status"] == "OK" and p["content"]["evidence_id"].startswith("ev-")
               for p in results)                                   # B's real tools, B's ids
    responded = [e.payload for e in r.trace if e.kind == "model_responded"]
    assert responded[0]["content"] == TURNS[0]                     # recorded before A parsed it
    assert responded[0]["usage"] == {"prompt_tokens": 100, "completion_tokens": 20}


def test_the_receipt_is_on_disk_when_the_first_model_request_arrives(tmp_path, endpoint):
    """D-15, directly: at the instant the model receives its first request, the receipt
    already exists, parses, and names the configuration requested. Observed at the model,
    not inferred from clocks — the stand-in reads the disk as the request arrives."""
    folder = tmp_path / "first"
    FakeModel.probed = []
    FakeModel.probe = lambda: read_receipt(folder / RECEIPT) if (folder / RECEIPT).is_file() \
        else None
    try:
        assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                         "--model", "test-model-1", "--archive", str(tmp_path), "--label",
                         "first", "--no-report"]) == 0
    finally:
        FakeModel.probe = None
    assert FakeModel.probed, "the model was never asked"
    at_first_request = FakeModel.probed[0]
    assert at_first_request is not None, "the first model request arrived before the receipt"
    assert at_first_request["label"] == "first"
    assert at_first_request["configuration"]["model"] == "test-model-1"
    assert at_first_request["configuration"]["endpoint"] == endpoint
    assert all(p == at_first_request for p in FakeModel.probed)   # and it never changed


def test_the_model_is_shown_the_incident_the_tools_and_each_observation(endpoint):
    """Driven directly against the scripted stand-in, to read exactly what the boundary sends."""
    tools = build_sql_tools(ReadOnlyDatabase.in_memory(ORDERS_MISSING.world))
    provider = ChatProvider(endpoint=endpoint, model="test-model-1", context=ORDERS_MISSING.context,
                            tools=tools.advertised(), recorder=Recorder())
    first = provider.respond()
    assert first == TURNS[0]
    sent = FakeModel.seen[-1]
    assert sent["model"] == "test-model-1" and sent["messages"][0]["role"] == "system"
    briefing = json.loads(sent["messages"][1]["content"])
    assert briefing["incident_id"] == INCIDENT
    assert briefing["permitted_write_paths"] == ["jobs/load_orders.yml"]
    assert [t["name"] for t in briefing["tools"]] == ["get_schema", "run_sql"]
    # the one sentence that stops a model guessing table names (R0 of 17 Sep guessed one,
    # was told "no such table", and built a finding on it): discovery is the first move
    assert "Begin with get_schema and no arguments" in sent["messages"][0]["content"]
    listing = tools.execute(ToolCall(call_id="c0", name="get_schema", arguments={}))
    assert listing.status == "OK"
    assert [t["name"] for t in listing.content["tables"]] == ["loads", "orders"]
    assert listing.content["tables"][0]["columns"]
    result = tools.execute(ToolCall("c1", "get_schema", {"table": "orders"}))
    provider.respond(observation=result, observations=(result,))
    fed = json.loads(FakeModel.seen[-1]["messages"][-1]["content"])   # the observation, as JSON
    assert fed["tool"] == "get_schema" and fed["status"] == "OK"
    assert fed["content"]["columns"] == ["order_id", "order_date", "amount_cents"]


def test_a_live_repair_carries_the_only_truthful_verdict(tmp_path, endpoint):
    """No validator exists. A REPAIR must carry a verdict, so it carries: not checked,
    not accepted, no finding — never a crash, never a fabricated ACCEPT."""
    FakeModel.script[:] = ['<TOOL_CALL>{"name": "get_schema", "arguments": {}}',
                           '<DECISION>{"disposition": "REPAIR", "root_cause_id": "X", '
                           '"root_cause_summary": "a fault", "repair_id": "R1", '
                           '"patch": {"jobs/load_orders.yml": "rerun"}}']
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "test-model-1", "--archive", str(tmp_path), "--label", "repair",
                     "--no-report"]) == 0
    r = read_record(tmp_path / "repair" / "record.json")
    assert r.termination == "submitted" and r.decision.disposition.value == "REPAIR"
    assert r.validation.accepted is False and r.validation.checks_run == ()
    assert "not checked" in r.validation.report and "not a finding" in r.validation.report
    assert [e.kind for e in r.trace][-2:] == ["decision_submitted", "validation_completed"]


def test_endings_translate_by_type_never_by_message(tmp_path, endpoint):
    FakeModel.script[:] = ["<STOP>"]                    # the model stops without a decision
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "test-model-1", "--archive", str(tmp_path), "--label", "stopped",
                     "--no-report"]) == 3
    stopped = read_record(tmp_path / "stopped" / "record.json")
    assert stopped.termination == "model_failure" and "row 5" in stopped.detail
    FakeModel.script[:] = ["nothing useful"] * 3       # three plain turns against a bound of 2
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "test-model-1", "--max-turns", "2", "--archive", str(tmp_path),
                     "--label", "bounded", "--no-report"]) == 3
    bounded = read_record(tmp_path / "bounded" / "record.json")
    assert bounded.termination == "bound_hit" and bounded.detail == "model_turns: 2 of 2 used"
    assert bounded.model_turns == 2
    FakeModel.script[:] = []                            # the endpoint answers 500
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "test-model-1", "--archive", str(tmp_path), "--label", "down",
                     "--no-report"]) == 4
    down = read_record(tmp_path / "down" / "record.json")
    # the endpoint failing is not the model failing (inherited D14): infrastructure, exit 4
    assert down.termination == "infrastructure_failure" and "HTTP 500" in down.detail


def test_only_local_endpoints_are_spoken_to_without_a_credential():
    assert endpoint_is_local("http://127.0.0.1:11434/v1")
    assert endpoint_is_local("http://localhost:1234/v1")
    assert not endpoint_is_local("https://api.openai.com/v1")
    with pytest.raises(ValueError, match="credential"):
        ChatProvider(endpoint="https://api.openai.com/v1", model="gpt",
                     context=ORDERS_MISSING.context, tools=[], recorder=Recorder())


# ── the paid path: the same loop, behind the receipt, a price and a cap ──────────────

PAID = ["--incident", INCIDENT, "--provider", "openai", "--model", "gpt-4.1-mini",
        "--max-cost-usd", "0.05", "--no-report"]
KEY = "sk-test-DISTINCTIVE-9f3a1c"


def test_the_pre_flight_costs_nothing_and_says_accepted_refused_or_absent(endpoint,
                                                                            monkeypatch, capsys):
    """Before a cent is spent: one GET of the model list with the credential. The answer
    names the status and the structured code on refusal, never the body, never the key."""
    from adii.provider.__main__ import main as preflight
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert preflight(["--check", "--model", "gpt-4.1-mini", "--endpoint", endpoint]) == 2
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    FakeModel.authorization[:] = []
    assert preflight(["--check", "--model", "gpt-4.1-mini", "--endpoint", endpoint]) == 0
    assert "accepted" in capsys.readouterr().out and FakeModel.authorization[-1] == f"Bearer {KEY}"
    assert preflight(["--check", "--model", "gpt-9", "--endpoint", endpoint]) == 1
    assert "not among them" in capsys.readouterr().out
    FakeModel.refuse = (401, {"error": {"message": f"Incorrect API key: {KEY[:8]}***",
                                        "code": "invalid_api_key"}})
    assert preflight(["--check", "--model", "gpt-4.1-mini", "--endpoint", endpoint]) == 1
    out = capsys.readouterr().out
    assert "refused: HTTP 401 invalid_api_key" in out and "sk-test" not in out
    assert preflight(["--check", "--model", "m", "--endpoint", "http://api.example.com/v1"]) == 2


def test_a_paid_run_is_refused_before_the_label_unless_every_precondition_holds(
        tmp_path, endpoint, monkeypatch, capsys):
    """Inherited D6 and D7: every check before anything irreversible, and the message names
    the thing missing. No folder appears in the archive for any refusal."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    unpriced = ["--incident", INCIDENT, "--provider", "openai", "--model", "no-such-model",
                "--archive", str(tmp_path), "--label", "x"]
    assert cli.main(unpriced) == 2 and "nominal price" in capsys.readouterr().out
    assert cli.main([*PAID, "--max-cost-usd", "0", "--archive", str(tmp_path)]) == 2
    assert "cap" in capsys.readouterr().out
    assert cli.main([*PAID, "--endpoint", "https://api.openai.com/v1?key=x",
                     "--archive", str(tmp_path)]) == 2
    assert "carries no" in capsys.readouterr().out
    assert cli.main([*PAID, "--endpoint", "http://api.example.com/v1",
                     "--archive", str(tmp_path)]) == 2
    assert cli.main([*PAID, "--archive", str(tmp_path)]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().out
    assert [p.name for p in tmp_path.iterdir()] == []          # no label claimed by a refusal


def test_a_paid_run_puts_the_credential_on_the_wire_and_nowhere_else(tmp_path, endpoint,
                                                                       monkeypatch, capsys):
    """The key travels as a bearer header and appears in no artefact, no report and no
    output — including when the endpoint's 401 body echoes a masked form of it."""
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    FakeModel.authorization[:] = []
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path),
                     "--label", "paid"]) == 0
    assert FakeModel.authorization[0] == f"Bearer {KEY}"
    everything = capsys.readouterr()
    for path in sorted((tmp_path / "paid").iterdir()):
        text = path.read_text(encoding="utf-8")
        assert KEY not in text and "sk-test" not in text, path.name
    assert KEY not in everything.out + everything.err
    r = read_record(tmp_path / "paid" / "record.json")
    assert r.configuration["credential"] == "OPENAI_API_KEY (environment)"
    assert r.configuration["provider"] == "openai" and r.configuration["max_cost_usd"] == 0.05
    receipt = read_receipt(tmp_path / "paid" / RECEIPT)
    assert "$0.05" in receipt["reason"] and receipt["configuration"] == r.configuration
    # priced: four responses at 100 in / 20 out tokens, nominal gpt-4.1-mini prices
    assert r.api_cost_usd == pytest.approx(4 * (100 * 0.40e-6 + 20 * 1.60e-6))
    assert [e.payload["fingerprint"] for e in r.trace if e.kind == "model_responded"] \
        == ["fp_fake"] * 4
    # a 401 whose body echoes the masked key: infrastructure, exit 4, the detail names the
    # status and code — never the message
    FakeModel.refuse = (401, {"error": {"message": f"Incorrect API key provided: {KEY[:8]}***",
                                        "type": "invalid_request_error",
                                        "code": "invalid_api_key"}})
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path),
                     "--label", "refused"]) == 4
    refused = read_record(tmp_path / "refused" / "record.json")
    assert refused.termination == "infrastructure_failure"
    assert "HTTP 401" in refused.detail and "invalid_api_key" in refused.detail
    assert "sk-test" not in refused.detail and "Incorrect" not in refused.detail
    assert KEY not in (tmp_path / "refused" / "trace.jsonl").read_text(encoding="utf-8")


def test_the_receipt_gates_the_paid_provider_and_the_cap_ends_the_run(tmp_path, endpoint,
                                                                       monkeypatch):
    """The provider refuses to exist without the receipt on disk; with it, the ledger's
    lower bound is checked between requests and the run ends as a bound hit — the request
    that crosses the cap is already paid for, so the overshoot is exactly one."""
    from adii.reporting.ledger import PRICES
    with pytest.raises(ValueError, match="receipt on disk"):
        ChatProvider(endpoint=endpoint, model="gpt-4.1-mini", context=ORDERS_MISSING.context,
                     tools=[], recorder=Recorder(), credential=KEY,
                     receipt=tmp_path / "missing.json", price=PRICES["gpt-4.1-mini"],
                     max_cost_usd=0.05)
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    FakeModel.script[:] = ["nothing useful"] * 6
    FakeModel.seen[:] = []
    one_request = 100 * 0.40e-6 + 20 * 1.60e-6                   # what the fake reports
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path),
                     "--label", "capped", "--max-cost-usd", f"{2.5 * one_request:.8f}"]) == 3
    capped = read_record(tmp_path / "capped" / "record.json")
    assert capped.termination == "bound_hit" and capped.detail.startswith("cost_usd:")
    assert len(FakeModel.seen) == 3                                # 2 under the cap, 1 over
    assert capped.api_cost_usd == pytest.approx(3 * one_request)
    assert all(m["max_tokens"] == 512 for m in FakeModel.seen)


def test_a_response_without_usage_is_an_unknown_row_never_zero(tmp_path, endpoint,
                                                                monkeypatch):
    """Inherited D15: a paid record never says 0.0 for rows it cannot price. The ledger
    prices what the provider reported and counts the rest."""
    from adii.reporting.ledger import PRICES, aggregate
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    FakeModel.script[:] = ["<STOP>"]
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path),
                     "--label", "one"]) == 3
    r = read_record(tmp_path / "one" / "record.json")
    ledger = aggregate(r.trace, PRICES["gpt-4.1-mini"])
    assert (ledger.proved, ledger.unknown) == (1, 0) and r.api_cost_usd == ledger.lower_bound_usd
    # the same trace with its usage struck out: one unknown row, a bound of zero that is
    # labelled as a bound — not a cost
    struck = tuple(e if e.kind != "model_responded" else type(e)(
        sequence=e.sequence, kind=e.kind, payload={**e.payload, "usage": None}) for e in r.trace)
    assert aggregate(struck, PRICES["gpt-4.1-mini"]) == \
        type(ledger)(lower_bound_usd=0.0, proved=0, unknown=1)


def test_the_scripted_provider_still_replays_the_walkthrough_only(tmp_path, capsys):
    scripted = ["--provider", "scripted", "--archive", str(tmp_path)]
    assert cli.main(["--incident", INCIDENT, *scripted]) == 2
    assert "replays the walkthrough only" in capsys.readouterr().out
    assert cli.main(["--incident", "nope", *scripted]) == 2
    assert "known: demo-learning-001, orders-missing-day" in capsys.readouterr().out
