"""The model boundary: the only package that talks to a model.

    Paid endpoints behind the receipt, a nominal price and a hard spend cap, with a
    request count and a wall clock beside it, the request made by a killable worker that
    follows no redirect.

A `ChatProvider` sits behind A's `respond()` seam and speaks A's protocol to an
OpenAI-compatible chat endpoint. Every request and every response is recorded at this
boundary, before A parses anything, into the runtime's trace — the one history a run has
(docs/trace_event_contract.md).
"""
from .credential import ENV_LOCAL, load_env_local
from .openai_compatible import (
    PROTOCOL,
    REASONING_EFFORTS,
    TIMEOUT_S,
    BoundExceeded,
    ChatProvider,
    ProviderFailure,
    ReserveBreached,
    endpoint_is_local,
    endpoint_may_carry_a_credential,
    estimator,
    initial_messages,
    input_tokens_upper_bound,
)

__all__ = ["ENV_LOCAL", "PROTOCOL", "REASONING_EFFORTS", "TIMEOUT_S", "BoundExceeded",
           "ChatProvider", "ProviderFailure", "ReserveBreached", "endpoint_is_local",
           "endpoint_may_carry_a_credential", "estimator", "initial_messages",
           "input_tokens_upper_bound", "load_env_local"]
