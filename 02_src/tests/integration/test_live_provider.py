"""The live path, end to end, with a stand-in model: A's real loop, driven by the real
runtime, over B's real tools, with a `ChatProvider` talking to an OpenAI-compatible endpoint served
here by the standard library. One trace — model requests and responses recorded at the
provider boundary, tool calls and results at the tool boundary, the decision by the
runtime — lands in one `adii.run_record/v1` the inspector renders. No model, no network
beyond the loopback, no money."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from adii.contracts import ToolCall
from adii.examples.specimens import ORDERS_MISSING
from adii.provider import ChatProvider, endpoint_is_local
from adii.reporting import read_record
from adii.runtime import __main__ as cli
from adii.runtime.run import Recorder
from adii.tools import ReadOnlyDatabase, build_sql_tools

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


class FakeModel(BaseHTTPRequestHandler):
    """An OpenAI-compatible /chat/completions that replies from a script and remembers
    every request body it saw."""
    script: list[str] = []
    seen: list[dict] = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeModel.seen.append(body)
        if not FakeModel.script:
            self.send_response(500)
            self.end_headers()
            return
        content = FakeModel.script.pop(0)
        reply = {"choices": [{"message": {"role": "assistant", "content": content}}],
                 "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
        payload = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


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
                     "--no-report"]) == 3
    down = read_record(tmp_path / "down" / "record.json")
    assert down.termination == "model_failure" and "HTTP 500" in down.detail


def test_only_local_endpoints_run_without_a_receipt():
    assert endpoint_is_local("http://127.0.0.1:11434/v1")
    assert endpoint_is_local("http://localhost:1234/v1")
    assert not endpoint_is_local("https://api.openai.com/v1")
    with pytest.raises(ValueError, match="receipt"):
        ChatProvider(endpoint="https://api.openai.com/v1", model="gpt",
                     context=ORDERS_MISSING.context, tools=[], recorder=Recorder())


def test_the_scripted_provider_still_replays_the_walkthrough_only(tmp_path, capsys):
    scripted = ["--provider", "scripted", "--archive", str(tmp_path)]
    assert cli.main(["--incident", INCIDENT, *scripted]) == 2
    assert "replays the walkthrough only" in capsys.readouterr().out
    assert cli.main(["--incident", "nope", *scripted]) == 2
    assert "known: demo-learning-001, orders-missing-day" in capsys.readouterr().out
