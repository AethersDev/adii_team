"""A's loop, driven by the runtime, with a real model behind it.

    SPIKE — see adii/provider. Not merged to main until the D-1 rows resolve.

The runtime calls `investigate(context, tools)`; this class calls A's `run()` with a
`ChatProvider` and the tools the runtime is already watching, so tool calls and results
land in the runtime's trace on the way through, model requests and responses land there
from the provider boundary, and A's own returned trace is not used: one history, recorded
where each thing happened, never two merged afterwards.

Endings translate, they are not interpreted: A's two exception types map to two
termination classes by type, never by message. A stop with no decision has no class yet
(D-1 row 5, open); it is mapped to `model_failure` here with the detail saying so, which
is exactly the policy choice the adapter must not make on main.
"""
from __future__ import annotations

from ..contracts import IncidentContext, InvestigationDecision, ValidationResult
from ..investigator.loop import ProviderFailureError, TurnBudgetExceededError, run
from ..provider import ChatProvider, CostBudgetExceeded, ProviderFailure
from .run import Recorder, Terminated, Tools


class NoValidatorYet:
    """The validator's slot until one exists (build plan M6). A live REPAIR must carry a
    verdict — the contract says so — and the only truthful one is: nothing checked this,
    so nothing accepted it. `accepted` is False and the report says why; no check is
    claimed. The real validator replaces this class and nothing else."""

    def validate(self, context: IncidentContext,
                 decision: InvestigationDecision) -> ValidationResult:
        return ValidationResult(
            accepted=False,
            report="No independent validator exists yet (build plan M6). The candidate repair "
                   "was not checked, so nothing accepted it. This is not a finding about the "
                   "repair.",
            checks_run=())


class LoopInvestigator:
    def __init__(self, *, endpoint: str, model: str, max_turns: int, recorder: Recorder,
                 served_as: str | None = None, **paid: object) -> None:
        """`paid`, when given, is what ChatProvider needs for a paid endpoint — credential,
        receipt, max_tokens, price, max_cost_usd — passed through untouched."""
        self._endpoint, self._model, self._max_turns = endpoint, model, max_turns
        self._recorder, self._served_as, self._paid = recorder, served_as, paid

    def investigate(self, context: IncidentContext, tools: Tools) -> InvestigationDecision:
        provider = ChatProvider(endpoint=self._endpoint, model=self._model, context=context,
                                tools=tools.advertised(), recorder=self._recorder,
                                served_as=self._served_as, **self._paid)
        try:
            decision, _ = run(context, provider, tools, max_turns=self._max_turns)
        except TurnBudgetExceededError as bound:
            raise Terminated("bound_hit",
                             f"model_turns: {bound.limit} of {bound.limit} used") from None
        except ProviderFailureError as failed:
            # A wraps whatever the provider raised and chains it; the class is read from the
            # type of the cause, never from the message. The endpoint failing is not the
            # model failing (inherited D14); a spend cap is a bound like any other.
            cause = failed.__cause__
            if isinstance(cause, CostBudgetExceeded):
                raise Terminated("bound_hit", str(cause)) from None
            if isinstance(cause, ProviderFailure):
                raise Terminated("infrastructure_failure", str(cause)) from None
            raise Terminated("model_failure", failed.reason) from None
        if decision is None:
            raise Terminated("model_failure", "the model stopped without a decision "
                             "(no termination class for this yet: trace contract row 5)")
        return decision
