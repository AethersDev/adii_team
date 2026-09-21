"""The live path, end to end, with a stand-in model: A's real loop, driven by the real
runtime, over B's real tools, with a `ChatProvider` talking to an OpenAI-compatible endpoint served
here by the standard library. One trace — model requests and responses recorded at the
provider boundary, tool calls and results at the tool boundary, the decision by the
runtime — lands in one `adii.run_record/v1` the inspector renders. No model, no network
beyond the loopback, no money."""
from __future__ import annotations

import hashlib
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


def test_the_pre_flight_costs_nothing_and_classifies_what_it_sees(endpoint, tmp_path,
                                                                  monkeypatch, capsys):
    """Before a cent is spent: one GET of the model list with the credential — from the
    environment, or from the operator's `.env.local` as every entrypoint reads it. The
    answer is classification lines: the status and the structured code on refusal, never
    the body, never the key."""
    from adii.provider.__main__ import main as preflight
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert preflight(["--check", "--model", "gpt-4.1-mini", "--endpoint", endpoint]) == 2
    assert "not set" in capsys.readouterr().out
    # tmp_path is the loader's root for every test (conftest): the operator's file is never read
    (tmp_path / ".env.local").write_text(f"OPENAI_API_KEY={KEY}\n", encoding="utf-8")
    FakeModel.authorization[:] = []
    assert preflight(["--check", "--model", "gpt-4.1-mini", "--endpoint", endpoint]) == 0
    out = capsys.readouterr().out
    assert FakeModel.authorization[-1] == f"Bearer {KEY}" and KEY not in out
    assert out == ("credential: accepted\nmodel: gpt-4.1-mini\nmodels_listed: 2\n"
                   "model_listed: yes\npassive_check: PASS\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env.local").unlink()
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    assert preflight(["--check", "--model", "gpt-9", "--endpoint", endpoint]) == 1
    assert "model_listed: no\npassive_check: FAIL" in capsys.readouterr().out
    FakeModel.refuse = (401, {"error": {"message": f"Incorrect API key: {KEY[:8]}***",
                                        "code": "invalid_api_key"}})
    assert preflight(["--check", "--model", "gpt-4.1-mini", "--endpoint", endpoint]) == 1
    out = capsys.readouterr().out
    assert ("credential: refused\nmodel: gpt-4.1-mini\nprovider_status: 401\n"
            "provider_error_code: invalid_api_key\nclassification: CREDENTIAL\n") in out
    assert out.endswith("passive_check: FAIL\n") and "sk-test" not in out
    assert "Incorrect" not in out
    assert preflight(["--check", "--model", "m", "--endpoint", "http://api.example.com/v1"]) == 2


@pytest.mark.parametrize("kind, status, code, expected", [
    ("http", 401, "invalid_api_key", "CREDENTIAL"),
    ("http", 429, "project_spend_limit_exceeded", "PROJECT_BUDGET"),
    ("http", 429, "organization_spend_limit_exceeded", "PROJECT_BUDGET"),
    ("http", 429, "insufficient_quota", "PROJECT_BUDGET"),
    ("http", 429, "credit_balance_exhausted", "PROJECT_BUDGET"),
    ("http", 429, "rate_limit_exceeded", "RATE_LIMIT"),
    ("http", 404, "model_not_found", "MODEL_ACCESS"),
    ("http", 403, None, "MODEL_ACCESS"),
    ("http", 429, None, "RATE_LIMIT"),
    ("http", 500, None, "PROVIDER_INFRASTRUCTURE"),
    ("http", 429, "a_code_we_have_not_seen", "UNKNOWN_CODE"),
    ("unreachable", None, None, "PROVIDER_INFRASTRUCTURE"),
    ("timeout", None, None, "PROVIDER_INFRASTRUCTURE"),
    ("malformed", 200, None, "PROVIDER_INFRASTRUCTURE"),
])
def test_a_refusal_is_classified_by_the_providers_code_never_by_status_while_a_code_exists(
        kind, status, code, expected):
    """Two 429s can mean two different things — a project at its spend limit is not rate
    limited, and retrying it does nothing. The code decides; the status only when there is
    none; a code not in the tables is preserved, not interpreted."""
    from adii.provider.__main__ import classify
    assert classify(kind, status, code) == expected


def test_the_active_pre_flight_spends_one_token_and_says_so_first(endpoint, monkeypatch, capsys,
                                                                   tmp_path):
    """`--spend`: one completion of one token through the run's own transaction, billable and
    said so before it is sent, the bill and the reserve premise after. Structurally not a
    run: one request, one message, no investigator, no tools, nothing archived."""
    from adii.provider.__main__ import main as preflight
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    monkeypatch.setattr(FakeModel, "usage", {"prompt_tokens": 5, "completion_tokens": 1})
    FakeModel.script[:] = ["pong"]
    before = len(FakeModel.seen)
    code = preflight(["--check", "--spend", "--model", "gpt-4.1-mini", "--endpoint", endpoint])
    out = capsys.readouterr().out
    assert code == 0 and KEY not in out
    assert out == ("credential: accepted\nmodel: gpt-4.1-mini\nmodels_listed: 2\n"
                   "model_listed: yes\npassive_check: PASS\n"
                   "spend_check: BILLABLE — one request, max_tokens=1, "
                   "nominal_max_cost_usd=0.0000096\n"
                   "request_sent: 1\nspend_check: PASS\n"
                   "usage: prompt_tokens=5 completion_tokens=1\n"
                   "cost_usd: 0.0000036 (nominal, openai-list-2025-04 (verify on the day))\n"
                   "reserve_premise: holds — prompt_tokens <= 20, completion_tokens <= 1\n"
                   "completion: succeeded at check time\n")
    [request] = FakeModel.seen[before:]
    assert request["max_tokens"] == 1 and request["messages"] == [
        {"role": "user", "content": "ping"}] and request["model"] == "gpt-4.1-mini"
    assert [p.name for p in tmp_path.iterdir()] == []            # nothing archived anywhere


def test_the_active_pre_flight_tells_a_spend_limit_from_a_rate_limit(endpoint, monkeypatch,
                                                                      capsys):
    """The case the passive check cannot see: 252 models listed, every completion refused.
    The classification is the provider's code, PROJECT_BUDGET, with the retry answer no —
    and the refusal's message, which names the project, never reaches the terminal."""
    from adii.provider.__main__ import main as preflight
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    FakeModel.refuse_completion = (429, {"error": {
        "message": "Project proj_x has exceeded its spend limit", "type": "insufficient_quota",
        "code": "project_spend_limit_exceeded"}})
    code = preflight(["--check", "--spend", "--model", "gpt-4.1-mini", "--endpoint", endpoint])
    out = capsys.readouterr().out
    assert code == 1 and "passive_check: PASS" in out
    assert out.endswith("request_sent: 1\nspend_check: BLOCKED\nprovider_status: 429\n"
                        "provider_error_code: project_spend_limit_exceeded\n"
                        "classification: PROJECT_BUDGET\n"
                        "retry: no — the project's owner must change the limit\n")
    assert "proj_x" not in out and "spend_check: BILLABLE" in out
    FakeModel.refuse_completion = (429, {"error": {"message": "slow down",
                                                   "code": "rate_limit_exceeded"}})
    assert preflight(["--check", "--spend", "--model", "gpt-4.1-mini",
                      "--endpoint", endpoint]) == 1
    out = capsys.readouterr().out
    assert "classification: RATE_LIMIT\nretry: may succeed later" in out and "slow" not in out


def test_the_active_pre_flight_refuses_an_unpriced_model_and_reports_a_broken_premise(
        endpoint, monkeypatch, capsys):
    """A bill needs a price, so `--spend` refuses an unpriced model before any request; and a
    completion whose usage exceeds the reserve's arithmetic succeeds but fails the check —
    the cap could not be trusted for that model."""
    from adii.provider.__main__ import main as preflight
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    before = len(FakeModel.seen)
    assert preflight(["--check", "--spend", "--model", "gpt-9", "--endpoint", endpoint]) == 2
    assert "nominal price" in capsys.readouterr().out and len(FakeModel.seen) == before
    monkeypatch.setattr(FakeModel, "usage", {"prompt_tokens": 1000, "completion_tokens": 1})
    FakeModel.script[:] = ["pong"]
    assert preflight(["--check", "--spend", "--model", "gpt-4.1-mini",
                      "--endpoint", endpoint]) == 1
    out = capsys.readouterr().out
    assert "spend_check: PASS" in out and "reserve_premise: VIOLATED — prompt_tokens 1000" in out


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
    assert cli.main([*PAID, "--max-cost-usd", "inf", "--archive", str(tmp_path)]) == 2
    assert "finite" in capsys.readouterr().out      # inf passes `> 0` and dies in the receipt
    # billed by the name on the wire, priced by --model: a paid run may not split them
    assert cli.main([*PAID, "--served-as", "gpt-4.1", "--archive", str(tmp_path)]) == 2
    assert "on the wire" in capsys.readouterr().out
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


def test_the_operators_env_local_is_read_when_the_shell_has_no_key(tmp_path, endpoint,
                                                                    monkeypatch, capsys):
    """One command for a rehearsal: with no key in the environment, `<repo>/.env.local` is
    read for that one name before the paid preconditions are asked — and the key then goes
    where it always went, the wire, and appears in no artefact and no output. A file that is
    not NAME=value lines is refused before any label, by line number, never by value."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("adii.provider.credential.REPO", tmp_path)   # conftest does too
    FakeModel.authorization[:] = []
    (tmp_path / ".env.local").write_text(f"# operator's\nOPENAI_API_KEY={KEY}\n", encoding="utf-8")
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path / "runs"),
                     "--label", "from-env-local"]) == 0
    assert FakeModel.authorization[0] == f"Bearer {KEY}"
    for path in sorted((tmp_path / "runs" / "from-env-local").iterdir()):
        assert KEY not in path.read_text(encoding="utf-8"), path.name
    assert KEY not in capsys.readouterr().out
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env.local").write_text(f"export OPENAI_API_KEY={KEY}\n", encoding="utf-8")
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path / "runs"),
                     "--label", "refused-file"]) == 2
    said = capsys.readouterr().out
    assert ".env.local line 1: expected NAME=value" in said and KEY not in said
    assert not (tmp_path / "runs" / "refused-file").exists()


def test_the_receipt_gates_the_paid_provider_and_the_cap_is_hard(tmp_path, endpoint,
                                                                monkeypatch):
    """The provider refuses to exist without the receipt on disk. With it, every request is
    admitted against the cap by its worst case — the bytes of the messages the endpoint
    actually receives at the input rate, max_tokens at the output rate — on top of what the
    run has spent, exactly; the request that would cross the cap is not sent, and the run
    ends as a bound hit naming the numbers. No overshoot: what was spent stays within the
    cap, and the receipt and the record say what the cap is and what it assumes."""
    from decimal import Decimal

    from adii.provider import input_tokens_upper_bound
    from adii.reporting.ledger import PRICES, reserve_for
    with pytest.raises(ValueError, match="receipt on disk"):
        ChatProvider(endpoint=endpoint, model="gpt-4.1-mini", context=ORDERS_MISSING.context,
                     tools=[], recorder=Recorder(), credential=KEY,
                     receipt=tmp_path / "missing.json", price=PRICES["gpt-4.1-mini"],
                     max_cost_usd=0.05, max_tokens=512)
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    price = PRICES["gpt-4.1-mini"]
    one_request = 100 * price.input_per_token + 20 * price.output_per_token  # the fake's usage
    # first, under a cap that binds nothing: what each request reserved, pinned to the bytes
    # the endpoint received — a reserve computed from anything but the messages sent would
    # differ once an observation joins them
    FakeModel.script[:] = ['<TOOL_CALL>{"name": "get_schema", "arguments": {}}',
                           '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
                           "nothing useful"]
    FakeModel.seen[:] = []
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path),
                     "--label", "free", "--max-cost-usd", "1.0", "--max-turns", "3"]) == 3
    free = read_record(tmp_path / "free" / "record.json")
    requested = [e.payload for e in free.trace if e.kind == "model_requested"]
    assert len(requested) == len(FakeModel.seen) == 3
    for asked, sent in zip(requested, FakeModel.seen, strict=True):
        assert asked["input_tokens_upper_bound"] == input_tokens_upper_bound(sent["messages"])
        assert Decimal(asked["reserve_usd"]) == \
            reserve_for(asked["input_tokens_upper_bound"], price, 512)
        assert asked["max_output_tokens"] == 512 and sent["max_tokens"] == 512
        assert asked["estimator"].startswith("utf-8 bytes") and "o200k_base" in asked["estimator"]
    reserves = [Decimal(r["reserve_usd"]) for r in requested]
    assert reserves[0] < reserves[1] < reserves[2]           # the prompt grows with each turn
    # then a cap that admits the second request exactly and not the third
    cap = 2 * one_request + reserves[2] - Decimal("0.0000001")
    FakeModel.script[:] = ['<TOOL_CALL>{"name": "get_schema", "arguments": {}}',
                           '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
                           "nothing useful"] * 2
    FakeModel.seen[:] = []
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path),
                     "--label", "capped", "--max-cost-usd", f"{cap:f}"]) == 3
    capped = read_record(tmp_path / "capped" / "record.json")
    assert capped.termination == "bound_hit"
    assert capped.detail == (
        f"max_cost_usd: spent ${2 * one_request:f} (0 request(s) without usage charged at "
        f"their reserve) + next request's worst case ${reserves[2]:f} > cap "
        f"${Decimal(repr(float(cap))):f}; remaining "
        f"${Decimal(repr(float(cap))) - 2 * one_request:f}; the request was not sent")
    assert len(FakeModel.seen) == 2                                # the third was never sent
    assert capped.api_cost_usd == pytest.approx(float(2 * one_request))
    assert Decimal(repr(capped.api_cost_usd)) <= Decimal(repr(float(cap)))
    assert capped.configuration["cap_basis"].startswith("hard by admission:")
    assert "premise: the endpoint honours max_tokens and bills by o200k_base" in \
        capped.configuration["cap_basis"]
    receipt = read_receipt(tmp_path / "capped" / RECEIPT)
    assert "a hard cap — no request is sent whose worst case would cross it" in receipt["reason"]


def test_a_cap_the_first_request_alone_would_cross_is_refused_before_the_label(
        tmp_path, endpoint, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path / "runs"),
                     "--max-cost-usd", "0.0001"]) == 2
    out = capsys.readouterr().out
    assert "the first request alone reserves $" in out and "would not be sent" in out
    assert not (tmp_path / "runs").exists() and FakeModel.seen == []


def test_the_request_count_and_the_wall_clock_are_bounds_of_their_own(tmp_path, endpoint,
                                                                       monkeypatch):
    """`--max-model-requests`, given, ends the run when the provider has made that many
    requests, whatever the turn budget says; omitted, it is as many as the turns, so the
    turn budget an operator set is the one that binds. `--max-wall-clock-seconds` cuts a
    request in flight at the deadline — the wait itself is bounded, not only the next
    request — and the run ends as a bound hit that says so, well inside the endpoint's own
    120 s and the stand-in's 2 s answer."""
    FakeModel.script[:] = ['<TOOL_CALL>{"name": "get_schema", "arguments": {}}'] * 6
    FakeModel.seen[:] = []
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "m", "--archive", str(tmp_path), "--label", "requests",
                     "--max-turns", "12", "--max-model-requests", "2"]) == 3
    r = read_record(tmp_path / "requests" / "record.json")
    assert r.termination == "bound_hit"
    assert r.detail == "max_model_requests: 2 of 2 used; the request was not sent"
    assert len(FakeModel.seen) == 2 and r.model_turns == 2
    assert r.configuration["max_model_requests"] == 2 and r.configuration["max_turns"] == 12

    FakeModel.script[:] = ['<TOOL_CALL>{"name": "get_schema", "arguments": {}}'] * 6
    FakeModel.seen[:] = []
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "m", "--archive", str(tmp_path), "--label", "turns",
                     "--max-turns", "3"]) == 3
    r = read_record(tmp_path / "turns" / "record.json")
    assert r.detail == "model_turns: 3 of 3 used" and len(FakeModel.seen) == 3
    assert r.configuration["max_model_requests"] == 3       # derived: one request per turn

    # the stand-in answers after six seconds; the deadline is one. The run is over well
    # before the answer would have come — the bound is wide on purpose, so a slow runner
    # cannot fail a correct cut — and the worker that made the request is gone.
    monkeypatch.setattr(FakeModel, "delay", 6.0)
    FakeModel.script[:] = ['<TOOL_CALL>{"name": "get_schema", "arguments": {}}'] * 6
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "m", "--archive", str(tmp_path), "--label", "clock",
                     "--max-wall-clock-seconds", "1"]) == 3
    r = read_record(tmp_path / "clock" / "record.json")
    assert r.termination == "bound_hit"
    assert r.detail.startswith("max_wall_clock_seconds: 1.") and r.detail.endswith(
        "s elapsed of 1.000 s; the request in flight was cut at the deadline")
    assert 1000 <= r.latency_ms < 4500 and r.model_turns == 0   # cut, not waited out
    assert r.configuration["max_wall_clock_seconds"] == 1.0
    assert r.configuration["timeout_s"] == 120.0


def test_every_character_survives_the_round_trip_through_the_worker(tmp_path, endpoint):
    """The worker is spoken to over binary pipes in ASCII JSON, so no platform's text encoding
    touches an incident or a reply: Arabic in the alert reaches the endpoint exactly, and
    Arabic in the model's decision reaches the record exactly."""
    brought = tmp_path / "brought"
    brought.mkdir()
    alert = "الإيرادات انخفضت ٤٥٪ بعد النشر — لماذا؟"
    (brought / "incident.json").write_text(json.dumps({
        "incident_id": "brought-1", "alert": alert, "as_of": "2026-09-19",
        "permitted_write_paths": []}, ensure_ascii=False), encoding="utf-8")
    (brought / "world.sql").write_text("CREATE TABLE orders (id INTEGER);", encoding="utf-8")
    summary = "لا خطأ في البيانات: عقدان انتهيا في ٧ آذار. 日本語も。"
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "get_schema", "arguments": {}}',
        json.dumps({"disposition": "NO_REPAIR", "root_cause_id": None, "repair_id": None,
                    "patch": {}, "root_cause_summary": summary}, ensure_ascii=False).join(
            ("<DECISION>", ""))]
    FakeModel.seen[:] = []
    assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                     endpoint, "--model", "m", "--archive", str(tmp_path / "runs")]) == 0
    # the provider hands the incident to the model as a JSON document (ASCII-escaped, as
    # json.dumps writes it); the endpoint received that document character for character
    received = FakeModel.seen[0]["messages"][1]["content"]
    handed = json.loads(received)
    assert handed["alert"] == alert and json.dumps(handed, indent=1) == received
    [folder] = [p for p in (tmp_path / "runs").iterdir() if p.is_dir()]
    r = read_record(folder / "record.json")
    assert r.context.alert == alert and r.decision.root_cause_summary == summary


def test_the_tool_call_budget_is_the_executor_s_and_independent_of_turns(tmp_path, endpoint):
    """`--max-tool-calls` is the executor's budget: the call past it is DENIED, in the
    trace, and the investigator may still decide on what it saw. It is set from the command
    line for an archive's incident and for a brought one alike, recorded, and no longer
    merely implied by the turn budget."""
    script = [
        '<TOOL_CALL>{"name": "get_schema", "arguments": {}}',
        '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
        '<DECISION>{"disposition": "ESCALATE", "root_cause_id": null, "root_cause_summary": '
        '"One look was allowed; the rest needs a person.", "repair_id": null, "patch": {}}']
    brought = tmp_path / "brought"
    brought.mkdir()
    (brought / "incident.json").write_text(json.dumps({
        "incident_id": "brought-1", "alert": "orders differ", "as_of": "2026-09-19",
        "permitted_write_paths": []}), encoding="utf-8")
    (brought / "world.sql").write_text("CREATE TABLE orders (id INTEGER);", encoding="utf-8")
    for label, where in (("calls", ["--incident", INCIDENT]),
                         ("brought-calls", ["--incident-dir", str(brought)])):
        FakeModel.script[:] = list(script)
        assert cli.main([*where, "--provider", "local", "--endpoint", endpoint, "--model", "m",
                         "--archive", str(tmp_path / "runs"), "--label", label,
                         "--max-tool-calls", "1"]) == 0
        r = read_record(tmp_path / "runs" / label / "record.json")
        results = [e.payload for e in r.trace if e.kind == "tool_result"]
        assert [x["status"] for x in results] == ["OK", "DENIED"], label
        assert results[1]["content"]["error"] == "tool-call budget of 1 is spent"
        assert r.tool_calls == 1 and r.configuration["max_tool_calls"] == 1
        assert r.decision.disposition.value == "ESCALATE"


@pytest.mark.parametrize(("flag", "value", "said"), [
    ("--max-tool-calls", "0", "above zero"), ("--max-turns", "-1", "above zero"),
    ("--max-model-requests", "0", "above zero"), ("--max-wall-clock-seconds", "inf", "finite"),
    ("--max-wall-clock-seconds", "0", "finite"),
])
def test_a_bound_that_binds_nothing_is_refused_before_any_label(tmp_path, endpoint, capsys,
                                                               flag, value, said):
    assert cli.main(["--incident", INCIDENT, "--provider", "local", "--endpoint", endpoint,
                     "--model", "m", "--archive", str(tmp_path), flag, value]) == 2
    assert said in capsys.readouterr().out
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_a_completion_bound_that_binds_nothing_is_refused_before_any_label(
        tmp_path, endpoint, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    FakeModel.seen[:] = []
    for value in ("0", "-5"):
        assert cli.main([*PAID, "--endpoint", endpoint, "--archive", str(tmp_path / "runs"),
                         "--max-tokens", value]) == 2
        assert "--max-tokens must be a whole number above zero" in capsys.readouterr().out
    assert not (tmp_path / "runs").exists() and FakeModel.seen == []


def test_a_model_billed_by_an_unknown_tokenizer_may_not_run_capped(endpoint, monkeypatch,
                                                                     tmp_path, capsys):
    from adii.reporting.ledger import PRICES, Price
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    priced = PRICES["gpt-4.1-mini"]
    monkeypatch.setitem(PRICES, "other-model", Price(priced.input_per_token,
                                                     priced.output_per_token, priced.table,
                                                     "sentencepiece"))
    assert cli.main(["--incident", INCIDENT, "--provider", "openai", "--model", "other-model",
                     "--endpoint", endpoint, "--archive", str(tmp_path / "runs")]) == 2
    assert "not known to be byte-level" in capsys.readouterr().out
    assert not (tmp_path / "runs").exists()


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
    from decimal import Decimal
    [reserve] = [e.payload["reserve_usd"] for e in r.trace if e.kind == "model_requested"]
    assert aggregate(struck, PRICES["gpt-4.1-mini"]) == \
        type(ledger)(lower_bound_usd=0.0, worst_case_usd=Decimal(reserve), proved=0, unknown=1)


def test_the_scripted_provider_still_replays_the_walkthrough_only(tmp_path, capsys):
    scripted = ["--provider", "scripted", "--archive", str(tmp_path)]
    assert cli.main(["--incident", INCIDENT, *scripted]) == 2
    assert "replays the walkthrough only" in capsys.readouterr().out
    assert cli.main(["--incident", "nope", *scripted]) == 2
    assert "known: demo-learning-001, orders-missing-day" in capsys.readouterr().out


def test_an_operators_own_incident_runs_over_its_own_world_and_both_are_kept(tmp_path, endpoint,
                                                                             capsys):
    """`--incident-dir`: incident.json is what the investigator is told, world.sql is the
    world behind the tools — the same loader a specimen uses — and both land beside the
    record, so the archive holds what the system saw. A folder that is not that is refused
    before any label is claimed."""
    from adii.tools.user_world import world_from_files
    brought = tmp_path / "brought"
    brought.mkdir()
    (brought / "incident.json").write_text(json.dumps({
        "incident_id": "upload-1", "alert": "Revenue fell 45% after the deploy.",
        "as_of": "2026-09-17T12:00:00+00:00", "permitted_write_paths": []}), encoding="utf-8")
    world = world_from_files([("revenue.csv", "day,revenue\n2026-03-07,1200\n2026-03-08,660\n")])
    (brought / "world.sql").write_text(world, encoding="utf-8")
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "run_sql", "arguments": {"query": "SELECT * FROM revenue"}}',
        '<DECISION>{"disposition": "NO_REPAIR", "root_cause_id": null, "root_cause_summary": '
        '"Two days of revenue, one lower; nothing in the data is malformed.", '
        '"repair_id": null, "patch": {}}']
    assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                     endpoint, "--model", "m", "--archive", str(tmp_path / "runs")]) == 0
    [folder] = [p for p in (tmp_path / "runs").iterdir() if p.is_dir()]
    assert folder.name.startswith("upload-1-")
    r = read_record(folder / "record.json")
    assert (r.context.incident_id, r.context.alert) == \
        ("upload-1", "Revenue fell 45% after the deploy.")
    assert r.decision.disposition.value == "NO_REPAIR"
    seen = [e for e in r.trace if e.kind == "tool_result"][0].payload["content"]
    assert seen["rows"] == [["2026-03-07", 1200], ["2026-03-08", 660]]
    assert (folder / "world.sql").read_text(encoding="utf-8") == world
    kept = json.loads((folder / "incident.json").read_text(encoding="utf-8"))
    assert kept["alert"] == r.context.alert
    receipt = read_receipt(folder / RECEIPT)
    assert receipt["artefacts"]["world"] == "sha256:" + hashlib.sha256(world.encode()).hexdigest()
    # refused before a label: a folder without its world, and a malformed incident
    (brought / "world.sql").unlink()
    assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                     endpoint, "--model", "m", "--archive", str(tmp_path / "runs2")]) == 2
    assert "must hold incident.json and world.sql" in capsys.readouterr().out
    (brought / "world.sql").write_text(world, encoding="utf-8")
    for malformed, said in (('{"incident_id": 5}', "as text"), ("[1, 2]", "as text"),
                            ('"hello"', "as text")):
        (brought / "incident.json").write_text(malformed, encoding="utf-8")
        assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                         endpoint, "--model", "m", "--archive", str(tmp_path / "runs2")]) == 2
        assert said in capsys.readouterr().out
    (brought / "incident.json").write_text(json.dumps({
        "incident_id": "upload-1", "alert": "x", "as_of": "now", "permitted_write_paths": []}),
        encoding="utf-8")
    (brought / "world.sql").write_text("CREATE TABL t (a);", encoding="utf-8")
    assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                     endpoint, "--model", "m", "--archive", str(tmp_path / "runs2")]) == 2
    assert "not one SQLite accepts" in capsys.readouterr().out
    assert not (tmp_path / "runs2").exists() or not list((tmp_path / "runs2").iterdir())


def evidence_package(root):
    """An operator's incident with every evidence bundle: what the page's form would write,
    plus what a curated development case will carry."""
    brought = root / "brought"
    brought.mkdir()
    (brought / "incident.json").write_text(json.dumps({
        "incident_id": "brought-1", "alert": "Order amounts look a hundred times too large.",
        "as_of": "2026-09-19", "permitted_write_paths": ["transforms/stg_orders.sql"]}),
        encoding="utf-8")
    (brought / "world.sql").write_text(
        "CREATE TABLE orders (id INTEGER, amount INTEGER); INSERT INTO orders VALUES (1, 120050);",
        encoding="utf-8")
    files = {
        "transform_map.json": b'{"stg_orders": "orders.sql"}',
        "transform_sources/orders.sql": b"select id, amount from orders -- v1\n",
        "notice_map.json": b'{"vendor-change": "vendor.txt"}',
        "notice_sources/vendor.txt": b"Amounts are in cents from 2026-03-08.\r\n",
        "change_history_map.json": b'{"transform-changes": "CHANGE_HISTORY.md"}',
        "change_history_sources/CHANGE_HISTORY.md":
            b"| date | file | ticket | change |\n| --- | --- | --- | --- |\n"
            b"| 2026-03-08 | orders.sql | DATA-1 | Stopped dividing by 100. |\n",
        "reconciliation_map.json": b'{"upstream-feed": "upstream.log"}',
        "reconciliation_sources/upstream.log": b"delivered=1\n",
        "declared_schema_map.json": b'{"orders": "orders.json"}',
        "declared_schema_sources/orders.json":
            b'{"source": "vendor.orders", "schema_version": 3, '
            b'"fields": {"amount": {"unit": "usd", "note": "Major units since v3."}}}',
    }
    for relative, content in files.items():
        (brought / relative).parent.mkdir(exist_ok=True)
        (brought / relative).write_bytes(content)
    return brought


def test_the_run_s_copy_of_the_package_is_its_only_authority(tmp_path, endpoint, monkeypatch):
    """`--incident-dir` with every evidence bundle. The package is copied into the claimed
    run folder first and the run is loaded from that copy, so the observations in the trace,
    the digests in the receipt and the bytes in the archive are one read of one package —
    here proved by changing the operator's folder the moment the label is claimed: the run
    shows, binds and keeps the changed source, all three agreeing. The archive then attests
    and preserves the package with the record."""
    from adii.reporting.manifest import preserve, verify, write_manifest
    brought = evidence_package(tmp_path)
    claim = cli.reserve

    def reserve_then_change(archive, label):
        folder = claim(archive, label)
        (brought / "transform_sources" / "orders.sql").write_bytes(
            b"select id, amount / 100 from orders -- v2\n")
        return folder
    monkeypatch.setattr(cli, "reserve", reserve_then_change)
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "get_transform", "arguments": {"transform_id": "stg_orders"}}',
        '<TOOL_CALL>{"name": "get_notice", "arguments": {"notice_id": "vendor-change"}}',
        '<TOOL_CALL>{"name": "get_change_history", '
        '"arguments": {"history_id": "transform-changes"}}',
        '<TOOL_CALL>{"name": "read_reconciliation", '
        '"arguments": {"reconciliation_id": "upstream-feed"}}',
        '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
        '<DECISION>{"disposition": "NO_REPAIR", "root_cause_id": null, "root_cause_summary": '
        '"The declared unit is dollars since v3 and the transform divides; the amount is as '
        'delivered.", "repair_id": null, "patch": {}}']
    archive = tmp_path / "runs"
    assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                     endpoint, "--model", "m", "--archive", str(archive)]) == 0
    [folder] = [p for p in archive.iterdir() if p.is_dir()]
    changed = b"select id, amount / 100 from orders -- v2\n"
    # the archive holds the package as it was when the label was claimed, byte for byte
    assert (folder / "transform_sources" / "orders.sql").read_bytes() == changed
    for relative in ("transform_map.json", "notice_sources/vendor.txt",
                     "change_history_sources/CHANGE_HISTORY.md",
                     "reconciliation_sources/upstream.log", "declared_schema_sources/orders.json"):
        assert (folder / relative).read_bytes() == (brought / relative).read_bytes()
    # the model saw that copy — every observation in the trace is the archived file's content
    record = read_record(folder / "record.json")
    seen = {e.payload["name"]: e.payload["content"] for e in record.trace
            if e.kind == "tool_result"}
    assert seen["get_transform"]["source"] == changed.decode("utf-8")
    assert seen["get_notice"]["content"] == "Amounts are in cents from 2026-03-08.\r\n"
    assert seen["get_change_history"]["changes"][0]["ticket"] == "DATA-1"
    assert seen["read_reconciliation"]["lines"] == ["delivered=1"]
    assert seen["get_schema"]["declared_schema"]["fields"]["amount"]["unit"] == "usd"
    assert record.configuration["tools"] == ["get_schema", "run_sql", "get_transform",
                                             "get_notice", "get_change_history",
                                             "read_reconciliation"]
    # the receipt binds that same copy: its digests are recomputed from the archive alone
    receipt = read_receipt(folder / RECEIPT)
    _, _, _, _, evidence = cli.incident_from_dir(folder)
    assert set(evidence) == {"transforms", "notices", "change_history_source",
                             "change_history_observation", "reconciliation_source",
                             "declared_schema_source", "declared_schema_observation"}
    assert {key: receipt["artefacts"][key] for key in evidence} == evidence
    assert receipt["artefacts"]["transforms"] == \
        cli.digest_of(cli.canonical_json({"stg_orders": changed.decode("utf-8")}))
    # and the archive attests and preserves the package with the record
    write_manifest(archive)
    assert verify(archive).ok
    assert preserve(archive, tmp_path / "copy").ok
    assert (tmp_path / "copy" / folder.name / "transform_sources" / "orders.sql").read_bytes() \
        == changed


def test_a_package_that_cannot_be_kept_releases_the_label(tmp_path, endpoint, capsys,
                                                          monkeypatch):
    """A folder that stops being an incident between the check and the copy — a bundle
    directory gone, a file replaced by a link — is refused after the label was claimed: the
    label is released, nothing is archived, no model is spoken to, and the exit code is the
    usage code, not a traceback's."""
    import shutil
    brought = evidence_package(tmp_path)
    claim = cli.reserve

    def reserve_then_break(archive, label):
        folder = claim(archive, label)
        shutil.rmtree(brought / "transform_sources")
        return folder
    monkeypatch.setattr(cli, "reserve", reserve_then_break)
    archive = tmp_path / "runs"
    assert cli.main(["--incident-dir", str(brought), "--provider", "local", "--endpoint",
                     endpoint, "--model", "m", "--archive", str(archive)]) == 2
    assert "not archived: transform_map.json must be a regular file" in capsys.readouterr().out
    assert list(archive.iterdir()) == []       # the label is free again
    assert FakeModel.seen == []                # nothing was spoken to
