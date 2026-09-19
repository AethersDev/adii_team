"""The model boundary: the only package that talks to a model.

    SPIKE placeholders for trace-contract rows 1, 5 and 6 — on main since 16 September;
    D-6b replaces them in place. Paid endpoints since 17 September, behind the receipt,
    a nominal price and a spend cap; the cap hard since 20 September, with a request
    count and a wall clock beside it.

A `ChatProvider` sits behind A's `respond()` seam and speaks A's protocol to an
OpenAI-compatible chat endpoint. Every request and every response is recorded at this
boundary, before A parses anything, into the runtime's trace — the one history a run has.
This writes trace-contract code before the D-1 rows in docs/trace_event_contract.md are
resolved; it exists to make a live run possible and to give that review working evidence,
and it is labelled a spike for that reason.
"""
from .openai_compatible import (
    ESTIMATOR,
    PROTOCOL,
    BoundExceeded,
    ChatProvider,
    ProviderFailure,
    endpoint_is_local,
    endpoint_may_carry_a_credential,
    input_tokens_upper_bound,
)

__all__ = ["ESTIMATOR", "PROTOCOL", "BoundExceeded", "ChatProvider", "ProviderFailure",
           "endpoint_is_local", "endpoint_may_carry_a_credential", "input_tokens_upper_bound"]
