"""The cost ledger — plan D-12, as a lower bound that says what it does not know.

A paid run's cost is evidence, and evidence has classes. A response the provider answered
with integer token counts is *proved* usage, priced at the nominal rate pinned here for
that model. A request that got no response, or a response with no usage, is an *unknown*
row: money may have moved, and nothing here pretends to know how much. The aggregate is
therefore a lower bound with the count of unknown rows beside it — never a total, and
never 0.0 for a run whose rows are all unknown (inherited defect D15).

Prices are nominal list prices, per token, transcribed by hand and named by table id so a
record can say which table priced it. Transcribe from the provider's price page on the
day and bump the table id; nothing here fetches a price. Cached prompt tokens are priced
at the full input rate — a bound, not a discount.

Where usage lands in the trace is trace-contract row 1, still open; this reads the spike's
placement (`usage` on `model_responded`, matched to `model_requested` by turn), and moves
with the vocabulary when the row is decided.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts import TraceEvent


@dataclass(frozen=True)
class Price:
    input_per_token: float
    output_per_token: float
    table: str


# Nominal list prices per token — USD per 1M, divided out — with the table they came from.
# Verify against the provider's page before a paid run; a stale nominal price is a wrong bound.
_TABLE = "openai-list-2025-04 (verify on the day)"
PRICES: dict[str, Price] = {
    "gpt-4o-mini": Price(0.15 / 1e6, 0.60 / 1e6, _TABLE),
    "gpt-4.1-mini": Price(0.40 / 1e6, 1.60 / 1e6, _TABLE),
    "gpt-4.1-nano": Price(0.10 / 1e6, 0.40 / 1e6, _TABLE),
    "gpt-4.1": Price(2.00 / 1e6, 8.00 / 1e6, _TABLE),
    "gpt-4o": Price(2.50 / 1e6, 10.00 / 1e6, _TABLE),
}


@dataclass(frozen=True)
class Ledger:
    lower_bound_usd: float
    proved: int          # requests whose response carried integer token counts
    unknown: int         # requests with no response, or a response without usage


def aggregate(trace: tuple[TraceEvent, ...], price: Price) -> Ledger:
    """One row per model request. Proved when a response of the same turn carries integer
    prompt and completion token counts; unknown otherwise — a missing response, a null,
    an empty object, or counts that are not integers all count as unknown, never as zero."""
    responses = {e.payload.get("turn"): e.payload.get("usage")
                 for e in trace if e.kind == "model_responded"}
    total, proved, unknown = 0.0, 0, 0
    for request in (e for e in trace if e.kind == "model_requested"):
        usage = responses.get(request.payload.get("turn"))
        tokens_in = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        tokens_out = usage.get("completion_tokens") if isinstance(usage, dict) else None
        if isinstance(tokens_in, int) and isinstance(tokens_out, int) \
                and not isinstance(tokens_in, bool) and not isinstance(tokens_out, bool):
            total += tokens_in * price.input_per_token + tokens_out * price.output_per_token
            proved += 1
        else:
            unknown += 1
    return Ledger(round(total, 6), proved, unknown)
