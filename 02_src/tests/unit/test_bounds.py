"""The run bounds at the provider boundary, as units: the reserve that admits a request, the
exact worst case it is admitted against, the deadline no request is sent past and none waits
past, and the bill held to its reserve afterwards."""
from __future__ import annotations

import json
import threading
import time
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from adii.contracts import TraceEvent
from adii.examples.specimens import ORDERS_MISSING
from adii.provider import (
    BoundExceeded,
    ChatProvider,
    ProviderFailure,
    ReserveBreached,
    initial_messages,
    input_tokens_upper_bound,
)
from adii.provider import openai_compatible as module
from adii.reporting.ledger import PRICES, Ledger, aggregate, reserve_for
from adii.runtime.run import Recorder

PRICE = PRICES["gpt-4.1-mini"]
NOWHERE = "http://127.0.0.1:9/v1"           # a port that refuses: any request made would fail


def local(recorder: Recorder | None = None, **bounds) -> ChatProvider:
    return ChatProvider(endpoint=NOWHERE, model="m", context=ORDERS_MISSING.context, tools=[],
                        recorder=recorder or Recorder(), **bounds)


def paid(tmp_path, recorder: Recorder, endpoint: str = NOWHERE, *, max_cost_usd: float,
         max_tokens: int = 16, **bounds) -> ChatProvider:
    (tmp_path / "receipt.json").write_text("{}", encoding="utf-8")
    return ChatProvider(endpoint=endpoint, model="gpt-4.1-mini", context=ORDERS_MISSING.context,
                        tools=[], recorder=recorder, credential="test-credential",
                        receipt=tmp_path / "receipt.json", price=PRICE, max_tokens=max_tokens,
                        max_cost_usd=max_cost_usd, **bounds)


def event(sequence, kind, **payload):
    return TraceEvent(sequence=sequence, kind=kind, payload=payload)


def test_the_input_bound_is_never_short_of_a_byte_level_tokenizer():
    """A token covers at least one byte, so bytes bound tokens — for multibyte text most of
    all, where a character count would fall short — and the chat format's tokens are
    counted above their real number."""
    messages = [{"role": "system", "content": "é" * 100}, {"role": "user", "content": "日本語"}]
    bytes_of_text = 200 + 9
    assert input_tokens_upper_bound(messages) >= bytes_of_text + 2 * 3 + 3
    assert input_tokens_upper_bound(messages) == bytes_of_text + 2 * 8 + 8
    assert input_tokens_upper_bound([]) == 8


def test_the_ledger_is_exact_and_charges_unknown_rows_at_their_reserve():
    """Proved rows cost what they cost, in exact arithmetic from the price as written; a
    response without usage costs the reserve that admitted it; a request whose reserve was
    never recorded cannot be bounded at all. Only the record's number is rounded."""
    proved = 100 * PRICE.input_per_token + 20 * PRICE.output_per_token
    trace = (
        event(0, "model_requested", turn=1, reserve_usd="0.002"),
        event(1, "model_responded", turn=1, usage={"prompt_tokens": 100, "completion_tokens": 20}),
        event(2, "model_requested", turn=2, reserve_usd="0.0000004"),
        event(3, "model_responded", turn=2, usage=None),
        event(4, "model_requested", turn=3, reserve_usd="0.004"),          # no response at all
    )
    ledger = aggregate(trace, PRICE)
    assert ledger == Ledger(lower_bound_usd=0.000072, worst_case_usd=proved + Decimal("0.0040004"),
                            proved=1, unknown=2)
    assert isinstance(ledger.worst_case_usd, Decimal) and proved == Decimal("0.000072")
    for unbounded in ("not a number", "-1", "Infinity", 0.004, None):
        rows = (*trace, event(5, "model_requested", turn=4, reserve_usd=unbounded))
        assert aggregate(rows, PRICE).worst_case_usd == Decimal("Infinity"), unbounded
    assert aggregate((event(0, "model_requested", turn=1),), PRICE).worst_case_usd.is_infinite()


def test_admission_spends_the_worst_case_not_the_lower_bound(tmp_path):
    """The distinguishing case: a request without usage has cost nothing the ledger can
    prove, and the whole of its reserve for all anyone knows. A cap between the two must
    refuse — admitting against the lower bound would send."""
    recorder = Recorder()
    recorder.event("model_requested", {"turn": 1, "reserve_usd": "0.010"})
    recorder.event("model_responded", {"turn": 1, "content": "x", "usage": None})
    reserve = reserve_for(input_tokens_upper_bound(initial_messages(ORDERS_MISSING.context, [])),
                          PRICE, 16)
    assert Decimal("0.0001") < reserve < Decimal("0.009")
    # a cap between lower + reserve and worst + reserve
    provider = paid(tmp_path, recorder, max_cost_usd=0.0105)
    provider._turn = 1
    assert aggregate(recorder.trace, PRICE).lower_bound_usd == 0.0
    with pytest.raises(BoundExceeded, match=r"max_cost_usd: spent \$0.010 \(1 request\(s\) "
                                            r"without usage charged at their reserve\)") as hit:
        provider.respond()
    assert hit.value.sent is False and len(recorder.trace) == 2     # nothing more recorded
    assert "the request was not sent" in str(hit.value)


def test_the_cap_is_compared_exactly_not_at_six_decimals(tmp_path):
    """A six-decimal display of the worst case would admit what the exact sum refuses."""
    recorder = Recorder()
    recorder.event("model_requested", {"turn": 1, "reserve_usd": "0.0000034"})
    reserve = reserve_for(input_tokens_upper_bound(initial_messages(ORDERS_MISSING.context, [])),
                          PRICE, 16)
    cap = Decimal("0.0000034") + reserve - Decimal("0.0000001")     # short by a tenth of a µ$
    provider = paid(tmp_path, recorder, max_cost_usd=float(cap))
    provider._turn = 1
    with pytest.raises(BoundExceeded, match="max_cost_usd"):
        provider.respond()


def test_no_request_is_sent_past_the_deadline(monkeypatch):
    """Once the wall clock has run out, `respond` raises the bound with the numbers and
    nothing goes on the wire — here against an endpoint that would refuse the connection,
    which is never attempted. The clock is controlled: no waiting, no tick resolution."""
    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    recorder = Recorder()
    provider = local(recorder, max_wall_clock_s=30.0)
    clock[0] += 30.0
    with pytest.raises(BoundExceeded, match=r"max_wall_clock_seconds: 30.000 s elapsed of "
                                            r"30.000 s; the request was not sent") as hit:
        provider.respond()
    assert hit.value.bound == "max_wall_clock_seconds" and hit.value.sent is False
    assert recorder.trace == ()          # no request was recorded, because none was made


class Trickle(BaseHTTPRequestHandler):
    """An endpoint that answers, slowly: headers at once, then the body a few bytes at a
    time. Never late by a socket's measure; only a deadline of the run's own can end it."""

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": "<STOP>"}}],
                           "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        for i in range(0, len(body), 4):
            self.wfile.write(body[i:i + 4])
            self.wfile.flush()
            time.sleep(0.2)

    def log_message(self, *_):
        pass


@pytest.fixture
def trickling():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Trickle)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def test_a_request_in_flight_is_cut_at_the_deadline_and_keeps_its_reserve(tmp_path, trickling):
    """The acceptance case for the wall clock: a body that trickles for seconds against a
    deadline of half a second. The local run is free at the deadline — the worker that made
    the request is killed — the ending names the bound, no response is recorded, and the
    request's full reserve stays charged: the endpoint may have computed and billed it."""
    recorder = Recorder()
    provider = paid(tmp_path, recorder, trickling, max_cost_usd=1.0, max_wall_clock_s=0.5)
    started = time.monotonic()
    with pytest.raises(BoundExceeded) as hit:
        provider.respond()
    elapsed = time.monotonic() - started
    assert hit.value.bound == "max_wall_clock_seconds" and hit.value.sent is True
    assert "the request in flight was cut at the deadline" in str(hit.value)
    assert 0.5 <= elapsed < 1.5, elapsed                  # the body would have taken ~ 4 s
    assert [e.kind for e in recorder.trace] == ["model_requested"]
    [requested] = recorder.trace
    ledger = aggregate(recorder.trace, PRICE)
    assert ledger.unknown == 1 and ledger.lower_bound_usd == 0.0
    assert ledger.worst_case_usd == Decimal(requested.payload["reserve_usd"])
    provider.close()


class Answers(BaseHTTPRequestHandler):
    """An endpoint that answers whatever `reply` holds, at once."""

    reply: dict = {}

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps(Answers.reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


@pytest.fixture
def answering():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Answers)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def test_a_bill_above_its_reserve_ends_the_run_as_the_providers_failure(tmp_path, answering):
    """The reserve was the proof that sending could not exceed the exposure allotted. An
    endpoint that bills more has broken a premise of that proof — max_tokens ignored, a
    tokenizer that is not byte-level — so the response is recorded with its usage, the
    breach is named, and the run ends as the provider's failure: nothing further admitted."""
    recorder = Recorder()
    Answers.reply = {"choices": [{"message": {"role": "assistant", "content": "<STOP>"}}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 5000},
                     "system_fingerprint": "fp"}
    provider = paid(tmp_path, recorder, answering, max_cost_usd=1.0, max_tokens=16)
    with pytest.raises(ReserveBreached) as breach:
        provider.respond()
    provider.close()
    assert isinstance(breach.value, ProviderFailure) and breach.value.kind == "reserve_breached"
    [requested, responded] = recorder.trace
    assert responded.kind == "model_responded" and responded.payload["usage"] == {
        "prompt_tokens": 1, "completion_tokens": 5000}
    billed = 1 * PRICE.input_per_token + 5000 * PRICE.output_per_token
    assert str(breach.value) == (
        f"provider reserve_breached: request 1 billed ${billed:f} against a reserve of "
        f"${Decimal(requested.payload['reserve_usd']):f}; a premise of the cap's admission "
        "failed, and no further request is admitted")
    assert aggregate(recorder.trace, PRICE).proved == 1        # the bill is evidence, kept


def test_a_reply_without_text_keeps_its_usage(tmp_path, answering):
    """`content: null` — a filter, a tool-call-shaped reply — is the model's failure to
    answer in the protocol, but the response's usage is evidence and is recorded before the
    content is read, so the bill is never lost to a null."""
    recorder = Recorder()
    Answers.reply = {"choices": [{"message": {"role": "assistant", "content": None}}],
                     "usage": {"prompt_tokens": 7, "completion_tokens": 0}}
    provider = paid(tmp_path, recorder, answering, max_cost_usd=1.0)
    with pytest.raises(ValueError, match="answered without text content"):
        provider.respond()
    provider.close()
    responded = recorder.trace[-1]
    assert responded.kind == "model_responded" and responded.payload["content"] is None
    assert responded.payload["usage"] == {"prompt_tokens": 7, "completion_tokens": 0}
    assert aggregate(recorder.trace, PRICE).proved == 1


def test_the_request_count_is_a_bound_of_its_own():
    recorder = Recorder()
    provider = local(recorder, max_model_requests=1)
    provider._turn = 1                    # one request already made
    with pytest.raises(BoundExceeded,
                       match="max_model_requests: 1 of 1 used; the request was not sent"):
        provider.respond()
    assert recorder.trace == ()


@pytest.mark.parametrize(("name", "value"), [
    ("max_model_requests", 0), ("max_model_requests", True), ("max_model_requests", 2.0),
    ("max_wall_clock_s", 0.0), ("max_wall_clock_s", float("inf")), ("max_wall_clock_s", -1.0),
    ("max_wall_clock_s", True),
])
def test_a_bound_that_binds_nothing_is_refused_at_construction(name, value):
    with pytest.raises(ValueError, match=f"{name} must be a"):
        local(**{name: value})


def test_a_whole_number_of_seconds_is_a_wall_clock_too():
    assert local(max_wall_clock_s=600)._deadline is not None


def test_a_paid_provider_needs_a_completion_bound_and_a_byte_level_tokenizer(tmp_path):
    (tmp_path / "receipt.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="max_tokens above zero"):
        paid(tmp_path, Recorder(), max_cost_usd=1.0, max_tokens=0)
    from adii.reporting.ledger import Price
    other = Price(PRICE.input_per_token, PRICE.output_per_token, PRICE.table, "sentencepiece")
    with pytest.raises(ValueError, match="not known to be byte-level"):
        ChatProvider(endpoint=NOWHERE, model="x", context=ORDERS_MISSING.context, tools=[],
                     recorder=Recorder(), credential="test-credential",
                     receipt=tmp_path / "receipt.json", price=other, max_tokens=16,
                     max_cost_usd=1.0)
