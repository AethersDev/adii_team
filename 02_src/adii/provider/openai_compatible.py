"""A's provider seam, served by an OpenAI-compatible chat endpoint over the standard library.

The seam A defines is one call per model turn: `respond(observation=…, observations=…)
-> str`, and A interprets the string by prefix — `<TOOL_CALL>` JSON, `<DECISION>` JSON,
`<STOP>`, or plain text. So this provider keeps the conversation itself: a system message
that states the protocol, the incident and the tools; then, each turn, the newest
observation as a user message, the endpoint's reply as the assistant's, and the reply back
to A untouched. A never sees the endpoint and the endpoint never sees the runtime.

Local endpoints run with no credential and cost nothing. A paid endpoint runs only with a
credential, only once the receipt is on disk (plan D-15), only over https unless on this
machine, with a nominal price and a spend cap. The cap is hard by admission: before each
request the provider reserves that request's worst case — every byte of the messages
counted as a token at the input rate (a byte-level BPE, every priced model's, cannot make
more tokens than bytes), `max_tokens` at the output rate, no discount assumed — and sends
it only if the ledger's exact worst case so far plus that reserve stays within the cap.
Otherwise the run ends as a bound hit and nothing is sent. After each reply, what the
endpoint billed is held to the reserve that admitted it; a bill above it means a premise of
the admission failed — the endpoint ignored `max_tokens`, or tokenises otherwise — and the
run ends as the provider's failure, nothing further admitted.

The run's other bounds are checked here too, because this is where a run waits: a request
count of its own (`max_model_requests`, independent of A's turns), and a wall clock. No
request is sent past the deadline, and the request itself is made by a worker process
(`worker.py`) the provider waits on for at most the time the deadline leaves; when that
runs out the worker is killed and the run ends as a bound hit — the local run never waits
past its deadline, whatever the endpoint does. The endpoint may still have computed and
billed what it received, so a request cut in flight keeps its full reserve in the ledger.

A failure of the endpoint — a refused status, a redirect, an unreachable host, a socket that
stalled past the endpoint's own timeout, a 200 whose body is not the API's shape — is the
provider's, never the model's, and is raised as `ProviderFailure` carrying structured fields
only: a status, a code, a kind. Never the response body, which a 401 fills with the masked
key it was sent; the body of a refusal is read in the worker and does not cross to this
process. The model is blamed only for what a well-formed response says.

The credential is held by this object and put on the wire by the worker; it is never
recorded, never echoed in an error, and never part of the endpoint string.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from ..contracts import IncidentContext, ToolResult
from ..reporting.ledger import BYTE_LEVEL_TOKENIZERS, Price, aggregate, priced, reserve_for
from ..runtime.run import Recorder

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
TIMEOUT_S = 120.0     # the endpoint's own patience: one connect, one read

# The chat format's own tokens — role markers, separators, the reply's priming — counted as
# constants well above their real number (about 3 per message and 3 per request), so that the
# bound below is a bound.
TOKENS_PER_MESSAGE, TOKENS_PER_REQUEST = 8, 8


class ProviderFailure(RuntimeError):
    """The endpoint failed to answer: `kind` is http, unreachable, timeout, malformed or
    worker; `status` and `code` are what it said in structure, if anything. No body text."""

    def __init__(self, kind: str, *, status: int | None = None, code: str | None = None):
        self.kind, self.status, self.code = kind, status, code
        said = " ".join(s for s in (f"HTTP {status}" if status else "", code or "") if s)
        super().__init__(f"provider {kind}" + (f": {said}" if said else ""))


class ReserveBreached(ProviderFailure):
    """The endpoint billed a request above the reserve that admitted it. The reserve was the
    proof that sending could not exceed the exposure allotted; a bill above it means a
    premise of that proof failed — `max_tokens` ignored, a tokeniser that is not byte-level,
    a request altered on the way — and the run ends as the provider's failure, with nothing
    further admitted against a cap whose arithmetic the endpoint has contradicted."""

    def __init__(self, turn: int, billed: Decimal, reserve: Decimal):
        self.turn, self.billed, self.reserve = turn, billed, reserve
        RuntimeError.__init__(
            self, f"provider reserve_breached: request {turn} billed ${billed:f} against a "
                  f"reserve of ${reserve:f}; a premise of the cap's admission failed, and no "
                  "further request is admitted")
        self.kind, self.status, self.code = "reserve_breached", None, None


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


def initial_messages(context: IncidentContext,
                     tools: list[dict[str, object]]) -> list[dict[str, str]]:
    """The conversation before the first turn: the protocol, then the incident and the tools
    as one document. What the first request's reserve is computed from — here and, before
    any label is claimed, in the runtime."""
    return [{"role": "system", "content": PROTOCOL},
            {"role": "user", "content": json.dumps({
                "incident_id": context.incident_id, "alert": context.alert, "as_of": context.as_of,
                "permitted_write_paths": list(context.permitted_write_paths),
                "tools": tools}, indent=1)}]


def input_tokens_upper_bound(messages: list[dict[str, str]]) -> int:
    """More tokens than a byte-level BPE tokenizer can make of these messages: a token covers
    at least one byte, so the bytes bound the tokens, and the chat format's own tokens are
    added as constants above their real count. No tokenizer is needed; the premise is the
    price's `tokenizer`, refused at the runtime's door when it is not byte-level."""
    return sum(len(m["content"].encode("utf-8")) + TOKENS_PER_MESSAGE for m in messages) \
        + TOKENS_PER_REQUEST


def estimator(price: Price) -> str:
    return (f"utf-8 bytes of every message + {TOKENS_PER_MESSAGE} per message + "
            f"{TOKENS_PER_REQUEST} per request; conservative for {price.tokenizer}, a byte-level "
            "BPE in which a token covers at least one byte")


_NO_MESSAGE = object()     # the reply has no choices[0].message.content to read


def _content_of(reply: dict) -> object:
    """`choices[0].message.content` as the API promises it — a string, or null when the
    model answered with no text — or `_NO_MESSAGE` when the body has no such place: the
    endpoint's failure to answer in the API's shape, which is never the model's."""
    choices = reply.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict) or "content" not in message:
        return _NO_MESSAGE
    return message["content"]


def _positive(name: str, value: object, whole: bool) -> None:
    kinds = int if whole else int | float
    if isinstance(value, bool) or not isinstance(value, kinds) or not value > 0 \
            or value == float("inf"):
        what = "a whole number" if whole else "a finite number"
        raise ValueError(f"{name} must be {what} above zero, got {value!r}")


class RequestWorker:
    """`worker.py` as a process of this run's own, spoken to by lines of ASCII JSON over
    binary pipes (so no platform's text encoding touches them — every character of an
    incident or a reply survives the round trip exactly); killable, so the run's deadline
    can end a request the endpoint will not. One wait decides: the answer that arrives
    within it wins, and once the wait has expired the worker is killed and any answer that
    was on its way is discarded — the decision is never revisited by re-reading a clock."""

    def __init__(self) -> None:
        # The credential travels the pipe, once per request, and not the environment.
        environment = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        self._process = subprocess.Popen(
            [sys.executable, "-B", "-m", "adii.provider.worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=environment,
            cwd=str(Path(__file__).resolve().parents[2]))
        self._replies: queue.Queue[bytes | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self._ended = False

    def _read(self) -> None:
        for line in self._process.stdout:
            self._replies.put(line)
        self._replies.put(None)                        # the worker is gone

    def ask(self, request: dict[str, object], *, wait: float | None) -> dict | None:
        """The worker's answer to `request`, or None when `wait` seconds passed without one —
        the request is then in flight, and the caller decides what that means. A worker that
        is gone, or answers with something that is not its protocol, is a failure of ours,
        filed as the provider's ("worker"), never as the model's."""
        if self._ended:
            return {"ok": False, "kind": "worker"}
        try:
            self._process.stdin.write(json.dumps(request).encode("utf-8") + b"\n")
            self._process.stdin.flush()
        except OSError:                                # the worker died before it was asked
            return {"ok": False, "kind": "worker"}
        try:
            line = self._replies.get(timeout=wait)
        except queue.Empty:
            return None
        if line is None:
            return {"ok": False, "kind": "worker"}
        try:
            answer = json.loads(line)
        except ValueError:
            return {"ok": False, "kind": "worker"}
        return answer if isinstance(answer, dict) and "ok" in answer \
            else {"ok": False, "kind": "worker"}

    def kill(self) -> None:
        """End the worker now — and everything the parent holds of it: the process waited
        for, the reader joined at the pipe's end, both pipes closed. Nothing reuses it."""
        self._ended = True
        self._process.kill()
        self._release()

    def close(self) -> None:
        """Let the worker finish and leave; kill it if it will not."""
        self._ended = True
        try:
            self._process.stdin.close()
            self._process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()
        self._release()

    def _release(self) -> None:
        self._process.wait()
        self._reader.join(timeout=5)
        for pipe in (self._process.stdin, self._process.stdout):
            if pipe is not None and not pipe.closed:
                pipe.close()

    @property
    def alive(self) -> bool:
        return self._process.poll() is None


class ChatProvider:
    def __init__(self, *, endpoint: str, model: str, context: IncidentContext,
                 tools: list[dict[str, object]], recorder: Recorder, timeout_s: float = TIMEOUT_S,
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
        bound any provider; the wall clock starts now. `timeout_s` is the endpoint's own
        patience per socket operation — the deadline is enforced apart from it."""
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
        if paid and price.tokenizer not in BYTE_LEVEL_TOKENIZERS:
            raise ValueError(f"{model} bills by {price.tokenizer}, which is not known to be "
                             "byte-level; the input bound would not be a bound")
        if not endpoint_is_local(endpoint) and urlparse(endpoint).scheme != "https":
            raise ValueError(f"{endpoint}: a credential travels only over https")
        if max_model_requests is not None:
            _positive("max_model_requests", max_model_requests, whole=True)
        if max_wall_clock_s is not None:
            _positive("max_wall_clock_s", max_wall_clock_s, whole=False)
        self._url = endpoint.rstrip("/") + "/chat/completions"
        self._model, self._recorder, self._timeout = model, recorder, timeout_s
        self._served_as = served_as or model
        self._credential, self._max_tokens = credential, max_tokens
        self._price = price
        self._cap = None if max_cost_usd is None else Decimal(repr(max_cost_usd))
        self._max_requests, self._wall_clock = max_model_requests, max_wall_clock_s
        self._started = time.monotonic()
        self._deadline = None if max_wall_clock_s is None else self._started + max_wall_clock_s
        self._turn = 0
        self._worker: RequestWorker | None = None
        self._messages = initial_messages(context, tools)

    def _elapsed(self) -> str:
        return (f"{time.monotonic() - self._started:.3f} s elapsed of "
                f"{self._wall_clock:.3f} s")

    def _admit(self) -> tuple[float | None, Decimal | None, dict[str, object]]:
        """Every bound, before a request is built: the request count, the wall clock, and
        for a paid provider the cost — the exact worst case spent so far plus this request's
        reserve against the cap. Returns how long this request may be waited for, its
        reserve, and what the trace records of the reservation; raises BoundExceeded with
        the numbers, and nothing has been sent."""
        if self._max_requests is not None and self._turn >= self._max_requests:
            raise BoundExceeded("max_model_requests",
                                f"{self._turn} of {self._max_requests} used")
        remaining = None
        if self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise BoundExceeded("max_wall_clock_seconds", self._elapsed())
        if self._price is None or self._cap is None:
            return remaining, None, {}
        ledger = aggregate(self._recorder.trace, self._price)
        input_bound = input_tokens_upper_bound(self._messages)
        reserve = reserve_for(input_bound, self._price, self._max_tokens)
        if ledger.worst_case_usd + reserve > self._cap:
            raise BoundExceeded("max_cost_usd", (
                f"spent ${ledger.worst_case_usd:f} ({ledger.unknown} request(s) without usage "
                f"charged at their reserve) + next request's worst case ${reserve:f} > cap "
                f"${self._cap:f}; remaining ${self._cap - ledger.worst_case_usd:f}"))
        return remaining, reserve, {
            "reserve_usd": format(reserve, "f"), "input_tokens_upper_bound": input_bound,
            "max_output_tokens": self._max_tokens, "estimator": estimator(self._price)}

    def respond(self, *, observation: ToolResult | None = None,
                observations: tuple[ToolResult, ...] = (),
                rejection: dict[str, str] | None = None) -> str:
        """One model turn. The request and the response are recorded here, at the boundary,
        before A parses the reply — never reconstructed later from what A made of it.
        `rejection` is the loop's word on the previous reply — its class and reason — sent
        back as the next message, once; the durable fact of it is the loop's event."""
        if observation is not None:
            self._messages.append({"role": "user", "content": json.dumps({
                "tool": observation.name, "status": observation.status,
                "content": observation.content})})
        if rejection is not None:
            self._messages.append({"role": "user", "content": json.dumps({
                "rejected": rejection})})
        remaining, reserve, reserved = self._admit()
        self._turn += 1
        self._recorder.event("model_requested", {
            "turn": self._turn, "model": self._model, "messages": len(self._messages), **reserved})
        body: dict[str, object] = {"model": self._served_as, "messages": self._messages,
                                   "temperature": 0}
        if self._max_tokens is not None:
            body["max_tokens"] = self._max_tokens
        headers = {"Content-Type": "application/json"}
        if self._credential is not None:
            headers["Authorization"] = f"Bearer {self._credential}"
        if self._worker is None:
            try:
                self._worker = RequestWorker()
            except OSError as failed:       # no process to ask: ours, never the model's
                raise ProviderFailure("worker") from failed
        answer = self._worker.ask({"url": self._url, "body": json.dumps(body), "headers": headers,
                                   "timeout_s": self._timeout}, wait=remaining)
        if answer is None:                 # the deadline passed with the request in flight
            self._worker.kill()
            raise BoundExceeded("max_wall_clock_seconds", self._elapsed(), sent=True)
        if not answer["ok"]:
            raise ProviderFailure(answer["kind"], status=answer.get("status"),
                                  code=answer.get("code"))
        # A 200 is not yet an answer. A body that is not a JSON object carries nothing to
        # trust, not even a bill: no response is recorded and the request keeps its reserve.
        try:
            reply = json.loads(answer["body"])
        except ValueError:
            reply = None
        if not isinstance(reply, dict):
            raise ProviderFailure("malformed", status=answer.get("status"))
        # The response is evidence before it is text: its usage and fingerprint are recorded
        # whatever the content turns out to be, so a bill is never lost to a null or to a
        # body whose shape is wrong.
        content = _content_of(reply)
        self._recorder.event("model_responded", {
            "turn": self._turn, "content": content if isinstance(content, str) else None,
            "usage": reply.get("usage"), "fingerprint": reply.get("system_fingerprint")})
        if reserve is not None:
            billed = priced(reply.get("usage"), self._price)
            if billed is not None and billed > reserve:
                raise ReserveBreached(self._turn, billed, reserve)
        if content is _NO_MESSAGE:          # the API's shape, not the model's answer, is missing
            raise ProviderFailure("malformed", status=answer.get("status"))
        if not isinstance(content, str):
            raise ValueError("the endpoint answered without text content")
        text = content.strip()
        self._messages.append({"role": "assistant", "content": text})
        return text

    def close(self) -> None:
        """The run is over: let the worker go."""
        if self._worker is not None:
            self._worker.close()
            self._worker = None
