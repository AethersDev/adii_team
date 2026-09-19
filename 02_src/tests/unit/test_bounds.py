"""The run bounds at the provider boundary, as units: the reserve that admits a request, the
ledger's worst case it is admitted against, and the deadline no request is sent past."""
from __future__ import annotations

import math

import pytest
from adii.contracts import TraceEvent
from adii.examples.specimens import ORDERS_MISSING
from adii.provider import BoundExceeded, ChatProvider, input_tokens_upper_bound
from adii.reporting.ledger import PRICES, Ledger, aggregate
from adii.runtime.run import Recorder


def test_the_input_bound_is_never_short_of_a_byte_level_tokenizer():
    """A token covers at least one byte, so bytes bound tokens — for multibyte text most of
    all, where a character count would fall short — and the chat format's tokens are
    counted above their real number."""
    messages = [{"role": "system", "content": "é" * 100}, {"role": "user", "content": "日本語"}]
    bytes_of_text = 200 + 9
    assert input_tokens_upper_bound(messages) >= bytes_of_text + 2 * 3 + 3
    assert input_tokens_upper_bound(messages) == bytes_of_text + 2 * 8 + 8
    assert input_tokens_upper_bound([]) == 8


def event(sequence, kind, **payload):
    return TraceEvent(sequence=sequence, kind=kind, payload=payload)


def test_the_ledger_s_worst_case_charges_unknown_rows_at_their_reserve():
    """Proved rows cost what they cost; a response without usage costs the reserve that
    admitted it; a request whose reserve was never recorded cannot be bounded at all."""
    price = PRICES["gpt-4.1-mini"]
    proved = 100 * price.input_per_token + 20 * price.output_per_token
    trace = (
        event(0, "model_requested", turn=1, reserve_usd=0.002),
        event(1, "model_responded", turn=1, usage={"prompt_tokens": 100, "completion_tokens": 20}),
        event(2, "model_requested", turn=2, reserve_usd=0.003),
        event(3, "model_responded", turn=2, usage=None),
        event(4, "model_requested", turn=3, reserve_usd=0.004),          # no response at all
    )
    assert aggregate(trace, price) == Ledger(lower_bound_usd=round(proved, 6),
                                             worst_case_usd=round(proved + 0.007, 6),
                                             proved=1, unknown=2)
    unbounded = (*trace, event(5, "model_requested", turn=4))
    assert aggregate(unbounded, price).worst_case_usd == math.inf
    assert aggregate(unbounded, price).lower_bound_usd == round(proved, 6)


def test_no_request_is_sent_past_the_deadline(monkeypatch):
    """The wall clock starts when the provider does; once it has run out, `respond` raises
    the bound with the numbers and nothing goes on the wire — here against an endpoint that
    would refuse the connection, which is never attempted."""
    recorder = Recorder()
    provider = ChatProvider(endpoint="http://127.0.0.1:9/v1", model="m",
                            context=ORDERS_MISSING.context, tools=[], recorder=recorder,
                            max_wall_clock_s=1e-6)
    with pytest.raises(BoundExceeded, match=r"max_wall_clock_seconds: 0.0 s elapsed of 0.0 s; "
                                            r"the request was not sent") as hit:
        provider.respond()
    assert hit.value.bound == "max_wall_clock_seconds" and hit.value.sent is False
    assert recorder.trace == ()          # no request was recorded, because none was made


def test_the_request_count_is_a_bound_of_its_own():
    recorder = Recorder()
    provider = ChatProvider(endpoint="http://127.0.0.1:9/v1", model="m",
                            context=ORDERS_MISSING.context, tools=[], recorder=recorder,
                            max_model_requests=1)
    provider._turn = 1                    # one request already made
    with pytest.raises(BoundExceeded,
                       match="max_model_requests: 1 of 1 used; the request was not sent"):
        provider.respond()
    assert recorder.trace == ()


@pytest.mark.parametrize(("name", "value"), [
    ("max_model_requests", 0), ("max_model_requests", True), ("max_model_requests", 2.0),
    ("max_wall_clock_s", 0.0), ("max_wall_clock_s", math.inf), ("max_wall_clock_s", -1.0),
])
def test_a_bound_that_binds_nothing_is_refused_at_construction(name, value):
    with pytest.raises(ValueError, match=f"{name} must be a finite"):
        ChatProvider(endpoint="http://127.0.0.1:9/v1", model="m", context=ORDERS_MISSING.context,
                     tools=[], recorder=Recorder(), **{name: value})
