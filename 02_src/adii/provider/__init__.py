"""The model boundary: the only package that talks to a model.

    SPIKE — local endpoints only, not merged to main.

A `ChatProvider` sits behind A's `respond()` seam and speaks A's protocol to an
OpenAI-compatible chat endpoint. Every request and every response is recorded at this
boundary, before A parses anything, into the runtime's trace — the one history a run has.
This writes trace-contract code before the D-1 rows in docs/trace_event_contract.md are
resolved; it exists to make a live run possible and to give that review working evidence,
and it is labelled a spike for that reason.
"""
from .openai_compatible import ChatProvider, endpoint_is_local

__all__ = ["ChatProvider", "endpoint_is_local"]
