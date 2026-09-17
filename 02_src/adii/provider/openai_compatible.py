"""A's provider seam, served by an OpenAI-compatible chat endpoint over the standard library.

The seam A defines is one call per model turn: `respond(observation=…, observations=…)
-> str`, and A interprets the string by prefix — `<TOOL_CALL>` JSON, `<DECISION>` JSON,
`<STOP>`, or plain text. So this provider keeps the conversation itself: a system message
that states the protocol, the incident and the tools; then, each turn, the newest
observation as a user message, the endpoint's reply as the assistant's, and the reply back
to A untouched. A never sees the endpoint and the endpoint never sees the runtime.

Local endpoints run with no credential and cost nothing. A paid endpoint runs only with a
credential, only once the receipt is on disk (plan D-15), only over https unless on this
machine, with a nominal price and a spend cap so the ledger (D-12) can price every proved
response and stop the run once the lower bound reaches the cap — the request that crosses
it is already paid for, so the overshoot is one request: the prompt so far plus
`max_tokens`. A failure of the endpoint — a refused status, an unreachable host, a
timeout — is the provider's, never the model's, and is raised as `ProviderFailure` carrying
structured fields only: a status, a code, a kind. Never the response body, which a 401
fills with the masked key it was sent.

The credential is held by this object and put on the wire; it is never recorded, never
echoed in an error, and never part of the endpoint string.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ..contracts import IncidentContext, ToolResult
from ..reporting.ledger import Price, aggregate
from ..runtime.run import Recorder

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class ProviderFailure(RuntimeError):
    """The endpoint failed to answer: `kind` is http, unreachable or timeout; `status` and
    `code` are what it said in structure, if anything. No body text, ever."""

    def __init__(self, kind: str, *, status: int | None = None, code: str | None = None):
        self.kind, self.status, self.code = kind, status, code
        said = " ".join(s for s in (f"HTTP {status}" if status else "", code or "") if s)
        super().__init__(f"provider {kind}" + (f": {said}" if said else ""))


class CostBudgetExceeded(RuntimeError):
    """The proved lower bound of what this run has spent reached its cap before a request."""

    def __init__(self, spent: float, cap: float):
        self.spent, self.cap = spent, cap
        super().__init__(f"cost_usd: {spent:.4f} of {cap:.4f} used")

PROTOCOL = """You are ADII, an investigator of data incidents. You see the world only through
the tools listed below, and you answer with exactly one of three message forms, nothing else:

<TOOL_CALL>{"name": "<tool name>", "arguments": {...}}
    to run one tool. You will receive its result as the next message, as JSON.

<DECISION>{"disposition": "REPAIR" | "NO_REPAIR" | "ESCALATE", "root_cause_id": "<ID_OR_NULL>",
           "root_cause_summary": "<what you established, citing what you observed>",
           "repair_id": "<ID, REPAIR only, else null>",
           "patch": {"<permitted path>": "<new content>"}}
    to end the investigation. REPAIR needs a repair_id and a non-empty patch and may write only
    to the permitted paths. NO_REPAIR means the change is legitimate and nothing should change.
    ESCALATE means the evidence cannot settle it or the action is not yours to take; say what
    is missing. REPAIR and NO_REPAIR require that you looked at least once.

Begin with get_schema and no arguments: it lists every table and its columns. Do not guess
a table or column name. Do not narrate. Do not use markdown. One form per message, starting
at the first character."""


def endpoint_is_local(endpoint: str) -> bool:
    return (urlparse(endpoint).hostname or "") in LOCAL_HOSTS


def endpoint_may_carry_a_credential(endpoint: str) -> bool:
    """https unless on this machine, and no query string or userinfo: a secret never
    travels in a URL, and the endpoint string is archived in three files."""
    parts = urlparse(endpoint)
    if parts.query or parts.username or parts.password:
        return False
    return parts.scheme == "https" or endpoint_is_local(endpoint)


class ChatProvider:
    def __init__(self, *, endpoint: str, model: str, context: IncidentContext,
                 tools: list[dict[str, object]], recorder: Recorder, timeout_s: float = 120.0,
                 served_as: str | None = None, credential: str | None = None,
                 receipt: Path | None = None, max_tokens: int | None = None,
                 price: Price | None = None, max_cost_usd: float | None = None):
        """`model` is the identity the record keeps. `served_as` is what the endpoint wants
        on the wire when that differs — mlx-lm's server, for one, loads whatever name a
        request carries unless it is `default_model`. A `credential` makes this a paid
        provider: then `receipt` must already be on disk, and `price` with `max_cost_usd`
        bound what it may spend."""
        paid = credential is not None
        if not paid and not endpoint_is_local(endpoint):
            raise ValueError(f"{endpoint} is not a local endpoint; a paid provider needs a "
                             "credential, the receipt on disk, a price and a spend cap")
        if paid and not (receipt is not None and receipt.is_file()):
            raise ValueError("a paid provider needs the receipt on disk before it is built: "
                             "nothing is spent without a record of what was about to be")
        if paid and (price is None or max_cost_usd is None or not max_cost_usd > 0):
            raise ValueError("a paid provider needs a nominal price and a spend cap above zero")
        if not endpoint_is_local(endpoint) and urlparse(endpoint).scheme != "https":
            raise ValueError(f"{endpoint}: a credential travels only over https")
        self._url = endpoint.rstrip("/") + "/chat/completions"
        self._model, self._recorder, self._timeout = model, recorder, timeout_s
        self._served_as = served_as or model
        self._credential, self._max_tokens = credential, max_tokens
        self._price, self._cap = price, max_cost_usd
        self._turn = 0
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": PROTOCOL},
            {"role": "user", "content": json.dumps({
                "incident_id": context.incident_id, "alert": context.alert, "as_of": context.as_of,
                "permitted_write_paths": list(context.permitted_write_paths),
                "tools": tools}, indent=1)}]

    def respond(self, *, observation: ToolResult | None = None,
                observations: tuple[ToolResult, ...] = ()) -> str:
        """One model turn. The request and the response are recorded here, at the boundary,
        before A parses the reply — never reconstructed later from what A made of it."""
        if observation is not None:
            self._messages.append({"role": "user", "content": json.dumps({
                "tool": observation.name, "status": observation.status,
                "content": observation.content})})
        if self._price is not None and self._cap is not None:
            spent = aggregate(self._recorder.trace, self._price).lower_bound_usd
            if spent >= self._cap:            # checked between requests: the overshoot is one
                raise CostBudgetExceeded(spent, self._cap)
        self._turn += 1
        self._recorder.event("model_requested", {
            "turn": self._turn, "model": self._model, "messages": len(self._messages)})
        request_body: dict[str, object] = {"model": self._served_as, "messages": self._messages,
                                           "temperature": 0}
        if self._max_tokens is not None:
            request_body["max_tokens"] = self._max_tokens
        headers = {"Content-Type": "application/json"}
        if self._credential is not None:
            headers["Authorization"] = f"Bearer {self._credential}"
        request = urllib.request.Request(self._url, data=json.dumps(request_body).encode("utf-8"),
                                         method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as refused:
            raise ProviderFailure("http", status=refused.code,
                                  code=_error_code(refused)) from None
        except urllib.error.URLError as unreachable:
            if isinstance(unreachable.reason, TimeoutError):
                raise ProviderFailure("timeout") from None
            raise ProviderFailure("unreachable") from None
        except TimeoutError:                       # a read that stalled past timeout_s
            raise ProviderFailure("timeout") from None
        text = reply["choices"][0]["message"]["content"].strip()
        self._recorder.event("model_responded", {
            "turn": self._turn, "content": text, "usage": reply.get("usage"),
            "fingerprint": reply.get("system_fingerprint")})
        self._messages.append({"role": "assistant", "content": text})
        return text


def _error_code(refused: urllib.error.HTTPError) -> str | None:
    """The structured `error.code` an OpenAI-shaped refusal carries — and only that. The
    message beside it is discarded unread: a 401's message echoes the key it was sent."""
    try:
        document = json.loads(refused.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError, OSError):
        return None
    error = document.get("error") if isinstance(document, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else None
