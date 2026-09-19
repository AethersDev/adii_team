"""A's provider seam, served by an OpenAI-compatible chat endpoint over the standard library.

The seam A defines is one call per model turn: `respond(observation=…, observations=…)
-> str`, and A interprets the string by prefix — `<TOOL_CALL>` JSON, `<DECISION>` JSON,
`<STOP>`, or plain text. So this provider keeps the conversation itself: a system message
that states the protocol, the incident and the tools; then, each turn, the newest
observation as a user message, the endpoint's reply as the assistant's, and the reply back
to A untouched. A never sees the endpoint and the endpoint never sees the runtime.

Local endpoints run with no credential and cost nothing. A paid endpoint runs only with a
credential, only once the receipt is on disk (plan D-15), only over https unless on this
machine, with a nominal price and a spend cap. The cap is hard: before each request the
provider reserves that request's worst case — every byte of the messages priced as a token
at the input rate, `max_tokens` at the output rate, no discount assumed — and if what the
run has spent plus that reserve would cross the cap, the request is not sent and the run
ends as a bound hit. What has been spent is the ledger's worst case: proved usage at
nominal prices, and a response without usage charged at the reserve that admitted it.

The run's other bounds are checked here too, because this is where a run waits: a request
count of its own (`max_model_requests`, independent of A's turns), and a wall clock — no
request is sent past the deadline, and a request in flight waits no longer than the
deadline allows. Each names itself in the `BoundExceeded` it raises, with the numbers.

A failure of the endpoint — a refused status, an unreachable host, a timeout short of the
deadline — is the provider's, never the model's, and is raised as `ProviderFailure`
carrying structured fields only: a status, a code, a kind. Never the response body, which
a 401 fills with the masked key it was sent.

The credential is held by this object and put on the wire; it is never recorded, never
echoed in an error, and never part of the endpoint string.
"""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ..contracts import IncidentContext, ToolResult
from ..reporting.ledger import Price, aggregate
from ..runtime.run import Recorder

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

# The chat format's own tokens — role markers, separators, the reply's priming — counted as
# constants well above their real number (about 3 per message and 3 per request), so that the
# bound below is a bound.
TOKENS_PER_MESSAGE, TOKENS_PER_REQUEST = 8, 8
ESTIMATOR = "utf-8 bytes of every message + 8 per message + 8 per request"


class ProviderFailure(RuntimeError):
    """The endpoint failed to answer: `kind` is http, unreachable or timeout; `status` and
    `code` are what it said in structure, if anything. No body text, ever."""

    def __init__(self, kind: str, *, status: int | None = None, code: str | None = None):
        self.kind, self.status, self.code = kind, status, code
        said = " ".join(s for s in (f"HTTP {status}" if status else "", code or "") if s)
        super().__init__(f"provider {kind}" + (f": {said}" if said else ""))


class BoundExceeded(RuntimeError):
    """A run bound the next request would cross, so it was not sent — or, for the wall clock,
    the request in flight was cut at the deadline. `bound` names it; the message carries the
    numbers the decision was made on, for the record's detail."""

    def __init__(self, bound: str, detail: str, *, sent: bool = False):
        self.bound, self.sent = bound, sent
        super().__init__(f"{bound}: {detail}; "
                         + ("the request in flight was cut at the deadline" if sent
                            else "the request was not sent"))


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


def input_tokens_upper_bound(messages: list[dict[str, str]]) -> int:
    """More tokens than any byte-level BPE tokenizer — every OpenAI chat model's — can make
    of these messages: a token covers at least one byte, so the bytes bound the tokens, and
    the chat format's own tokens are added as constants above their real count. No
    tokenizer is needed, and no model's vocabulary is assumed beyond that."""
    return sum(len(m["content"].encode("utf-8")) + TOKENS_PER_MESSAGE for m in messages) \
        + TOKENS_PER_REQUEST


def _positive(name: str, value: object, kind: type) -> None:
    if isinstance(value, bool) or not isinstance(value, kind) \
            or not value > 0 or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite {kind.__name__} above zero, got {value!r}")


class ChatProvider:
    def __init__(self, *, endpoint: str, model: str, context: IncidentContext,
                 tools: list[dict[str, object]], recorder: Recorder, timeout_s: float = 120.0,
                 served_as: str | None = None, credential: str | None = None,
                 receipt: Path | None = None, max_tokens: int | None = None,
                 price: Price | None = None, max_cost_usd: float | None = None,
                 max_model_requests: int | None = None,
                 max_wall_clock_s: float | None = None):
        """`model` is the identity the record keeps. `served_as` is what the endpoint wants
        on the wire when that differs — mlx-lm's server, for one, loads whatever name a
        request carries unless it is `default_model`. A `credential` makes this a paid
        provider: then `receipt` must already be on disk, and `price`, `max_cost_usd` and
        `max_tokens` bound what it may spend. `max_model_requests` and `max_wall_clock_s`
        bound any provider; the wall clock starts now."""
        paid = credential is not None
        if not paid and not endpoint_is_local(endpoint):
            raise ValueError(f"{endpoint} is not a local endpoint; a paid provider needs a "
                             "credential, the receipt on disk, a price and a spend cap")
        if paid and not (receipt is not None and receipt.is_file()):
            raise ValueError("a paid provider needs the receipt on disk before it is built: "
                             "nothing is spent without a record of what was about to be")
        if paid and (price is None or max_cost_usd is None or not max_cost_usd > 0):
            raise ValueError("a paid provider needs a nominal price and a spend cap above zero")
        if paid and (isinstance(max_tokens, bool) or not isinstance(max_tokens, int)
                     or max_tokens <= 0):
            raise ValueError("a paid provider needs max_tokens above zero: a request's reserve "
                             "prices the whole completion it permits")
        if not endpoint_is_local(endpoint) and urlparse(endpoint).scheme != "https":
            raise ValueError(f"{endpoint}: a credential travels only over https")
        if max_model_requests is not None:
            _positive("max_model_requests", max_model_requests, int)
        if max_wall_clock_s is not None:
            _positive("max_wall_clock_s", max_wall_clock_s, float)
        self._url = endpoint.rstrip("/") + "/chat/completions"
        self._model, self._recorder, self._timeout = model, recorder, timeout_s
        self._served_as = served_as or model
        self._credential, self._max_tokens = credential, max_tokens
        self._price, self._cap = price, max_cost_usd
        self._max_requests, self._wall_clock = max_model_requests, max_wall_clock_s
        self._deadline = None if max_wall_clock_s is None else time.monotonic() + max_wall_clock_s
        self._turn = 0
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": PROTOCOL},
            {"role": "user", "content": json.dumps({
                "incident_id": context.incident_id, "alert": context.alert, "as_of": context.as_of,
                "permitted_write_paths": list(context.permitted_write_paths),
                "tools": tools}, indent=1)}]

    def _admit(self) -> tuple[float | None, dict[str, object]]:
        """Every bound, before a request is built: the request count, the wall clock, and
        for a paid provider the cost — spent so far plus this request's worst case against
        the cap. Returns the time this request may wait and what the trace records of the
        reservation; raises BoundExceeded with the numbers, and nothing has been sent."""
        if self._max_requests is not None and self._turn >= self._max_requests:
            raise BoundExceeded("max_model_requests",
                                f"{self._turn} of {self._max_requests} used")
        remaining = None
        if self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise BoundExceeded("max_wall_clock_seconds",
                                    f"{self._wall_clock:.1f} s elapsed of {self._wall_clock:.1f} s")
        timeout = self._timeout if remaining is None else min(self._timeout, remaining)
        reserved: dict[str, object] = {}
        if self._price is not None and self._cap is not None:
            ledger = aggregate(self._recorder.trace, self._price)
            input_bound = input_tokens_upper_bound(self._messages)
            reserve = (input_bound * self._price.input_per_token
                       + self._max_tokens * self._price.output_per_token)
            if ledger.worst_case_usd + reserve > self._cap:
                raise BoundExceeded("max_cost_usd", (
                    f"spent ${ledger.worst_case_usd:.4f} ({ledger.unknown} request(s) without "
                    f"usage charged at their reserve) + next request's worst case "
                    f"${reserve:.4f} > cap ${self._cap:.4f}; remaining "
                    f"${self._cap - ledger.worst_case_usd:.4f}"))
            reserved = {"reserve_usd": round(reserve, 6), "input_tokens_upper_bound": input_bound,
                        "max_output_tokens": self._max_tokens, "estimator": ESTIMATOR}
        return timeout, reserved

    def respond(self, *, observation: ToolResult | None = None,
                observations: tuple[ToolResult, ...] = ()) -> str:
        """One model turn. The request and the response are recorded here, at the boundary,
        before A parses the reply — never reconstructed later from what A made of it."""
        if observation is not None:
            self._messages.append({"role": "user", "content": json.dumps({
                "tool": observation.name, "status": observation.status,
                "content": observation.content})})
        timeout, reserved = self._admit()
        self._turn += 1
        self._recorder.event("model_requested", {
            "turn": self._turn, "model": self._model, "messages": len(self._messages), **reserved})
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
            with urllib.request.urlopen(request, timeout=timeout) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as refused:
            raise ProviderFailure("http", status=refused.code,
                                  code=_error_code(refused)) from None
        except urllib.error.URLError as unreachable:
            if isinstance(unreachable.reason, TimeoutError):
                raise self._timed_out() from None
            raise ProviderFailure("unreachable") from None
        except TimeoutError:                       # a read that stalled past its timeout
            raise self._timed_out() from None
        text = reply["choices"][0]["message"]["content"].strip()
        self._recorder.event("model_responded", {
            "turn": self._turn, "content": text, "usage": reply.get("usage"),
            "fingerprint": reply.get("system_fingerprint")})
        self._messages.append({"role": "assistant", "content": text})
        return text

    def _timed_out(self) -> RuntimeError:
        """A request that waited too long: the run's deadline if that is what cut it — a
        bound, in flight — otherwise the endpoint's failure."""
        if self._deadline is not None and time.monotonic() >= self._deadline:
            return BoundExceeded("max_wall_clock_seconds",
                                 f"{self._wall_clock:.1f} s elapsed of {self._wall_clock:.1f} s",
                                 sent=True)
        return ProviderFailure("timeout")


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
