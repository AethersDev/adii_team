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
        for i in range(0, len(body), 4):          # ~ 35 pieces: seven seconds, if let be
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
    """The acceptance case for the wall clock: a body that trickles for seven seconds against
    a deadline of one. The local run is free at the deadline — the worker that made the
    request is killed, waited for, its pipes closed, and it answers nothing afterwards — the
    ending names the bound, no response is recorded, and the request's full reserve stays
    charged: the endpoint may have computed and billed it. The elapsed bound is wide on
    purpose: the claim is that the trickle cannot finish, not that a shared runner schedules
    a process within a hundred milliseconds."""
    recorder = Recorder()
    provider = paid(tmp_path, recorder, trickling, max_cost_usd=1.0, max_wall_clock_s=1.0)
    started = time.monotonic()
    with pytest.raises(BoundExceeded) as hit:
        provider.respond()
    elapsed = time.monotonic() - started
    assert hit.value.bound == "max_wall_clock_seconds" and hit.value.sent is True
    assert "the request in flight was cut at the deadline" in str(hit.value)
    assert 1.0 <= elapsed < 4.0, elapsed                  # the body needs ~ 7 s to arrive
    assert [e.kind for e in recorder.trace] == ["model_requested"]
    [requested] = recorder.trace
    ledger = aggregate(recorder.trace, PRICE)
    assert ledger.unknown == 1 and ledger.lower_bound_usd == 0.0
    assert ledger.worst_case_usd == Decimal(requested.payload["reserve_usd"])
    worker = provider._worker
    assert not worker.alive and worker._process.returncode is not None
    assert worker._process.stdin.closed and worker._process.stdout.closed
    assert not worker._reader.is_alive()
    assert worker.ask({}, wait=1.0) == {"ok": False, "kind": "worker"}   # never reused
    provider.close()


def test_a_worker_that_dies_or_babbles_is_our_failure_never_the_models(tmp_path, answering):
    """A worker gone before it answers, or answering outside its protocol, is filed as the
    provider's failure ("worker") — the run ends as an infrastructure failure, and the model
    is not blamed for it."""
    import queue

    from adii.provider.openai_compatible import RequestWorker
    recorder = Recorder()
    provider = paid(tmp_path, recorder, answering, max_cost_usd=1.0)
    provider._worker = RequestWorker()
    provider._worker._process.kill()
    provider._worker._process.wait()
    with pytest.raises(ProviderFailure, match="provider worker") as failed:
        provider.respond()
    assert failed.value.kind == "worker" and not isinstance(failed.value, ReserveBreached)
    provider.close()

    class Babbling(RequestWorker):
        def __init__(self):
            self._replies = queue.Queue()
            self._replies.put(b"not json at all\n")
            self._ended = False
            self._process = type("P", (), {"stdin": type("S", (), {
                "write": lambda self, b: None, "flush": lambda self: None,
                "closed": True, "close": lambda self: None})(),
                "stdout": None, "poll": lambda self: 0, "wait": lambda self, timeout=None: 0,
                "kill": lambda self: None, "returncode": 0})()
            self._reader = threading.Thread(target=lambda: None)
    provider = paid(tmp_path, Recorder(), answering, max_cost_usd=1.0)
    provider._worker = Babbling()
    with pytest.raises(ProviderFailure, match="provider worker"):
        provider.respond()


def test_the_credential_is_absent_from_the_workers_environment(tmp_path, answering,
                                                                monkeypatch):
    """The credential reaches the wire through the pipe, once per request, and the worker is
    started without it: fewer copies, and a worker crash dump cannot contain it."""
    import subprocess
    seen: list[dict] = []
    real = subprocess.Popen

    def recording(*args, **kwargs):
        seen.append(kwargs["env"])
        return real(*args, **kwargs)
    monkeypatch.setattr(module.subprocess, "Popen", recording)
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key-for-this-test")
    Answers.reply = {"choices": [{"message": {"role": "assistant", "content": "<STOP>"}}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    provider = paid(tmp_path, Recorder(), answering, max_cost_usd=1.0)
    assert provider.respond() == "<STOP>"
    provider.close()
    [environment] = seen
    assert "OPENAI_API_KEY" not in environment and "PATH" in environment


class Answers(BaseHTTPRequestHandler):
    """An endpoint that answers whatever `reply` holds, at once — a dict as JSON, or bytes
    as they are, for a body that is not the API's shape."""

    reply: dict | bytes = {}

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        body = Answers.reply if isinstance(Answers.reply, bytes) \
            else json.dumps(Answers.reply).encode("utf-8")
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


@pytest.mark.parametrize("body", [
    b"<html>502 Bad Gateway</html>",                       # not JSON
    b'"a string"',                                          # JSON, not an object
    b'{"error": {"message": "overloaded", "type": "server_error"}}',
    b'{"choices": []}',
    b'{"choices": [{"message": null}]}',
    b'{"choices": [{"message": {"role": "assistant"}}]}',   # no content key at all
])
def test_a_200_that_is_not_the_apis_shape_is_the_endpoints_failure(tmp_path, answering, body):
    """A 200 is not yet an answer. The provider owns JSON decoding and the response's shape;
    the model is blamed only for what a well-formed response says. Every body here used to
    leave `respond()` as a KeyError, IndexError, TypeError or JSONDecodeError, which A wraps
    and the runtime files as the model's failure."""
    Answers.reply = body
    recorder = Recorder()
    provider = paid(tmp_path, recorder, answering, max_cost_usd=1.0)
    with pytest.raises(ProviderFailure, match="provider malformed: HTTP 200") as failed:
        provider.respond()
    provider.close()
    assert failed.value.kind == "malformed" and failed.value.status == 200
    assert not isinstance(failed.value, ReserveBreached)


def test_a_malformed_reply_keeps_the_usage_it_carries(tmp_path, answering):
    """Usage is extracted before the shape is judged: a body with a bill and no message is
    the endpoint's failure, and the bill is evidence all the same — recorded, priced, proved."""
    Answers.reply = b'{"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 0}}'
    recorder = Recorder()
    provider = paid(tmp_path, recorder, answering, max_cost_usd=1.0)
    with pytest.raises(ProviderFailure, match="provider malformed"):
        provider.respond()
    provider.close()
    [requested, responded] = recorder.trace
    assert responded.kind == "model_responded" and responded.payload["content"] is None
    assert responded.payload["usage"] == {"prompt_tokens": 3, "completion_tokens": 0}
    assert aggregate(recorder.trace, PRICE).proved == 1


def test_a_body_that_is_not_json_carries_no_bill_so_the_reserve_stands(tmp_path, answering):
    """Nothing in a body that does not parse is trustworthy, not even a usage: no response
    is recorded, and the ledger charges the request at its full reserve."""
    Answers.reply = b"<html>502 Bad Gateway</html>"
    recorder = Recorder()
    provider = paid(tmp_path, recorder, answering, max_cost_usd=1.0)
    with pytest.raises(ProviderFailure, match="provider malformed"):
        provider.respond()
    provider.close()
    [requested] = recorder.trace
    ledger = aggregate(recorder.trace, PRICE)
    assert ledger.unknown == 1 and ledger.proved == 0
    assert ledger.worst_case_usd == Decimal(requested.payload["reserve_usd"])


def test_a_worker_that_cannot_be_started_is_the_providers_failure(tmp_path, answering,
                                                                    monkeypatch):
    """No process to make the request is our failure — filed "worker", never the model's."""
    def cannot(*args, **kwargs):
        raise OSError("no interpreter to start")
    monkeypatch.setattr(module.subprocess, "Popen", cannot)
    provider = paid(tmp_path, Recorder(), answering, max_cost_usd=1.0)
    with pytest.raises(ProviderFailure, match="provider worker") as failed:
        provider.respond()
    assert failed.value.kind == "worker"
    provider.close()


class Elsewhere(BaseHTTPRequestHandler):
    """The host a redirect points at. Anything arriving here is a leak."""

    received: list[tuple[str, str | None]] = []

    def do_GET(self):  # noqa: N802
        Elsewhere.received.append(("GET", self.headers.get("Authorization")))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    do_POST = do_GET  # noqa: N815

    def log_message(self, *_):
        pass


class Redirecting(BaseHTTPRequestHandler):
    """The configured endpoint, answering every request with `code` and a Location."""

    code: int = 302
    to: str = ""

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(Redirecting.code)
        self.send_header("Location", Redirecting.to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_):
        pass


@pytest.fixture
def redirecting():
    Elsewhere.received = []
    elsewhere = ThreadingHTTPServer(("127.0.0.1", 0), Elsewhere)
    threading.Thread(target=elsewhere.serve_forever, daemon=True).start()
    Redirecting.to = f"http://127.0.0.1:{elsewhere.server_port}/v1/chat/completions"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Redirecting)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    for server in (httpd, elsewhere):
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_no_redirect_is_followed_and_the_credential_goes_no_further(redirecting, code):
    """`urllib` re-issues a 301, 302 or 303 POST as a GET at whatever host Location names,
    the bearer header still on it and the body gone. The worker follows nothing: a 3xx is
    the endpoint's refusal, reported with its status, and the second host hears nothing."""
    from adii.provider.worker import transact
    Redirecting.code = code
    answer = transact({"url": redirecting.rstrip("/") + "/chat/completions", "body": "{}",
                       "headers": {"Content-Type": "application/json",
                                   "Authorization": "Bearer test-credential"},
                       "timeout_s": 5.0})
    assert answer == {"ok": False, "kind": "http", "status": code, "code": None}
    assert Elsewhere.received == []


def test_a_redirecting_endpoint_ends_the_run_as_the_providers_failure(tmp_path, redirecting):
    """Through the worker process and the provider: the run ends as the provider's http
    failure with the redirect's status, and the credential reached only the configured host."""
    Redirecting.code = 302
    provider = paid(tmp_path, Recorder(), redirecting, max_cost_usd=1.0)
    with pytest.raises(ProviderFailure, match="provider http: HTTP 302") as failed:
        provider.respond()
    provider.close()
    assert failed.value.kind == "http" and failed.value.status == 302
    assert Elsewhere.received == []


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
