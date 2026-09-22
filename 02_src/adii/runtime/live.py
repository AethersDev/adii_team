"""A's loop, driven by the runtime, with a real model behind it.

    SPIKE — see adii/provider. Not merged to main until the D-1 rows resolve.

The runtime calls `investigate(context, tools)`; this class calls A's `run()` with a
`ChatProvider`, the tools the runtime is already watching, and the runtime's recorder as
the loop's sink: tool calls and results land in the runtime's trace on the way through,
model requests and responses from the provider boundary, a rejected submission from the
loop the moment it rejects it (trace contract row 6). One history, recorded where each
thing happened. The trace `run()` returns is the loop's local account and agrees with the
record on every durable fact; nothing in it is translated into the record afterwards.

Endings translate, they are not interpreted: A's two exception types map to two
termination classes by type, never by message. A stop with no decision has no class yet
(D-1 row 5, open); it is mapped to `model_failure` here with the detail saying so, which
is exactly the policy choice the adapter must not make on main.
"""
from __future__ import annotations

from ..contracts import IncidentContext, InvestigationDecision, ValidationResult
from ..investigator.loop import ProviderFailureError, TurnBudgetExceededError, run
from ..provider import BoundExceeded, ChatProvider, ProviderFailure
from ..validation.validator import UnknownIncident, Validator
from .run import Recorder, Terminated, Tools


class ValidatorOnLivePath:
    """The runtime adapter in `run_incident`'s validator slot (m7_validation_integration.md,
    rows 1–3): the real validator, asked by attempt, and exactly one translation —
    `UnknownIncident`, the validator's own statement that it has no world to rebuild, becomes
    NOT_CHECKABLE in structure (`reason_code`), neither a verdict nor an infrastructure
    failure that would lose the decision. Every other exception is the runtime's to classify."""

    def __init__(self) -> None:
        self._validator = Validator()

    def validate(self, context: IncidentContext,
                 decision: InvestigationDecision) -> ValidationResult:
        try:
            return self._validator.validate(context, decision)
        except UnknownIncident as why:
            return ValidationResult(
                accepted=False, checks_run=(), reason_code="no_rebuildable_world",
                report=f"Not checkable: {why}. The candidate repair was neither accepted nor "
                       "rejected; this is not a finding about the repair.")


class LoopInvestigator:
    def __init__(self, *, endpoint: str, model: str, max_turns: int, recorder: Recorder,
                 served_as: str | None = None, max_model_requests: int | None = None,
                 max_wall_clock_s: float | None = None, **paid: object) -> None:
        """`max_model_requests` and `max_wall_clock_s` are the provider's bounds, distinct
        from A's turn budget. `paid`, when given, is what ChatProvider needs for a paid
        endpoint — credential, receipt, max_tokens, price, max_cost_usd — passed through
        untouched."""
        self._endpoint, self._model, self._max_turns = endpoint, model, max_turns
        self._recorder, self._served_as, self._paid = recorder, served_as, paid
        self._max_requests, self._wall_clock = max_model_requests, max_wall_clock_s

    def investigate(self, context: IncidentContext, tools: Tools) -> InvestigationDecision:
        provider = ChatProvider(endpoint=self._endpoint, model=self._model, context=context,
                                tools=tools.advertised(), recorder=self._recorder,
                                served_as=self._served_as, max_model_requests=self._max_requests,
                                max_wall_clock_s=self._wall_clock, **self._paid)
        try:
            decision, _ = run(context, provider, tools, max_turns=self._max_turns,
                              sink=self._recorder)
        except TurnBudgetExceededError as bound:
            provider.close()
            raise Terminated("bound_hit",
                             f"model_turns: {bound.limit} of {bound.limit} used") from None
        except ProviderFailureError as failed:
            # A wraps whatever the provider raised and chains it; the class is read from the
            # type of the cause, never from the message. The endpoint failing is not the
            # model failing (inherited D14); a spend cap is a bound like any other.
            provider.close()
            cause = failed.__cause__
            if isinstance(cause, BoundExceeded):
                raise Terminated("bound_hit", str(cause)) from None
            if isinstance(cause, ProviderFailure):
                raise Terminated("infrastructure_failure", str(cause)) from None
            raise Terminated("model_failure", failed.reason) from None
        provider.close()
        if decision is None:
            raise Terminated("model_failure", "the model stopped without a decision "
                             "(no termination class for this yet: trace contract row 5)")
        return decision
