"""The cost ledger — plan D-12, as a lower bound that says what it does not know.

A paid run's cost is evidence, and evidence has classes. A response the provider answered
with integer token counts is *proved* usage, priced at the nominal rate pinned here for
that model. A request that got no response, or a response with no usage, is an *unknown*
row: money may have moved, and nothing here pretends to know how much. The aggregate is
therefore a lower bound with the count of unknown rows beside it — never a total, and
never 0.0 for a run whose rows are all unknown (inherited defect D15).

Beside the lower bound, a worst case, for the provider's admission of the next request: the
proved rows at their price, and an unknown row at the reserve the provider recorded when it
admitted that request — the most it could have cost. A request whose reserve was never
recorded cannot be bounded, and the worst case says so: infinity, and nothing further is
admitted against that cap. The arithmetic is exact — `Decimal`, from the price as written —
and rounded only where a number is reported: a six-decimal display could admit what the
exact sum refuses.

Prices are nominal list prices, per token, transcribed by hand and named by table id so a
record can say which table priced it. Transcribe from the provider's price page on the
day and bump the table id; nothing here fetches a price. Cached prompt tokens are priced
at the full input rate — a bound, not a discount. Each price names the encoding the model
bills by: the provider's input bound counts bytes, which is conservative for a byte-level
BPE and for nothing else, so a model priced here with another tokenizer may not run capped.

Usage is read where the trace carries it (`usage` on `model_responded`, matched to
`model_requested` by turn; docs/trace_event_contract.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..contracts import TraceEvent


@dataclass(frozen=True)
class Price:
    input_per_token: Decimal
    output_per_token: Decimal
    table: str
    tokenizer: str       # the encoding the model bills by, as the provider documents it
    reasoning: bool = False   # takes a reasoning effort in place of a temperature


# Encodings in which a token covers at least one byte, so a byte count bounds a token count.
# GPT-6's encoding is not published; it is taken as byte-level on two checks — the
# pre-flight's `reserve_premise` against a real bill, and every bill against its reserve
# (`ReserveBreached`), which ends a run the moment the premise fails.
GPT_6 = "gpt-6 (unpublished; byte-level checked, per bill)"
BYTE_LEVEL_TOKENIZERS = frozenset({"o200k_base", "cl100k_base", GPT_6})


def _per_million(usd: str) -> Decimal:
    return Decimal(usd) / Decimal(1_000_000)


# Nominal list prices — USD per 1M tokens, as written, divided out exactly — with the table
# they came from. Verify against the provider's page before a paid run; a stale nominal
# price is a wrong bound.
_TABLE = "openai-list-2025-04 (verify on the day)"
_TABLE_6 = "openai-list-2026-09-22 (verify on the day)"   # reasoning tokens bill as output
PRICES: dict[str, Price] = {
    "gpt-4o-mini": Price(_per_million("0.15"), _per_million("0.60"), _TABLE, "o200k_base"),
    "gpt-4.1-mini": Price(_per_million("0.40"), _per_million("1.60"), _TABLE, "o200k_base"),
    "gpt-4.1-nano": Price(_per_million("0.10"), _per_million("0.40"), _TABLE, "o200k_base"),
    "gpt-4.1": Price(_per_million("2.00"), _per_million("8.00"), _TABLE, "o200k_base"),
    "gpt-4o": Price(_per_million("2.50"), _per_million("10.00"), _TABLE, "o200k_base"),
    "gpt-6-sol": Price(_per_million("2.00"), _per_million("10.00"), _TABLE_6, GPT_6, True),
    "gpt-6-luna": Price(_per_million("0.10"), _per_million("0.50"), _TABLE_6, GPT_6, True),
}


@dataclass(frozen=True)
class Ledger:
    lower_bound_usd: float   # proved rows at nominal prices, six decimals — the record's number
    worst_case_usd: Decimal  # exact: proved rows at price, unknown rows at their reserve
    proved: int              # requests whose response carried integer token counts
    unknown: int             # requests with no response, or a response without usage


def priced(usage: object, price: Price) -> Decimal | None:
    """What a response's usage cost at nominal prices, exactly — or None when the usage is
    not two integer counts: a null, an empty object, a bool, a float all mean unknown."""
    tokens_in = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    tokens_out = usage.get("completion_tokens") if isinstance(usage, dict) else None
    if isinstance(tokens_in, int) and isinstance(tokens_out, int) \
            and not isinstance(tokens_in, bool) and not isinstance(tokens_out, bool):
        return tokens_in * price.input_per_token + tokens_out * price.output_per_token
    return None


def reserve_for(input_tokens: int, price: Price, max_tokens: int) -> Decimal:
    """The most a request can cost: its input bound at the input rate, the whole completion
    it permits at the output rate — no discount, no early stop assumed."""
    return input_tokens * price.input_per_token + max_tokens * price.output_per_token


def _reserve(request: dict[str, object]) -> Decimal:
    """The most a request could have cost, as the provider recorded before sending it; a
    request without a recorded, finite, non-negative reserve cannot be bounded at all."""
    reserve = request.get("reserve_usd")
    try:
        value = Decimal(reserve) if isinstance(reserve, str) else Decimal("Infinity")
    except InvalidOperation:
        return Decimal("Infinity")
    return value if value.is_finite() and value >= 0 else Decimal("Infinity")


def aggregate(trace: tuple[TraceEvent, ...], price: Price) -> Ledger:
    """One row per model request. Proved when a response of the same turn carries integer
    prompt and completion token counts; unknown otherwise — a missing response, a null,
    an empty object, or counts that are not integers all count as unknown, never as zero."""
    responses = {e.payload.get("turn"): e.payload.get("usage")
                 for e in trace if e.kind == "model_responded"}
    total, worst, proved, unknown = Decimal(0), Decimal(0), 0, 0
    for request in (e for e in trace if e.kind == "model_requested"):
        cost = priced(responses.get(request.payload.get("turn")), price)
        if cost is not None:
            total, worst = total + cost, worst + cost
            proved += 1
        else:
            unknown += 1
            worst += _reserve(request.payload)
    return Ledger(float(round(total, 6)), worst, proved, unknown)
