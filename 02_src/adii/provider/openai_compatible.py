"""A's provider seam, served by an OpenAI-compatible chat endpoint over the standard library.

The seam A defines is one call per model turn: `respond(observation=…, observations=…)
-> str`, and A interprets the string by prefix — `<TOOL_CALL>` JSON, `<DECISION>` JSON,
`<STOP>`, or plain text. So this provider keeps the conversation itself: a system message
that states the protocol, the incident and the tools; then, each turn, the newest
observation as a user message, the endpoint's reply as the assistant's, and the reply back
to A untouched. A never sees the endpoint and the endpoint never sees the runtime.

Local endpoints only. A model on this machine has no nominal price, so a run costs nothing
and needs no receipt; a paid provider waits for the receipt (plan D-15) and the ledger
(D-12), because a record that says a paid run cost 0.0 is inherited defect D15.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from ..contracts import IncidentContext, ToolResult
from ..runtime.run import Recorder

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

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

Do not narrate. Do not use markdown. One form per message, starting at the first character."""


def endpoint_is_local(endpoint: str) -> bool:
    return (urlparse(endpoint).hostname or "") in LOCAL_HOSTS


class ChatProvider:
    def __init__(self, *, endpoint: str, model: str, context: IncidentContext,
                 tools: list[dict[str, object]], recorder: Recorder, timeout_s: float = 120.0,
                 served_as: str | None = None):
        """`model` is the identity the record keeps. `served_as` is what the endpoint wants
        on the wire when that differs — mlx-lm's server, for one, loads whatever name a
        request carries unless it is `default_model`."""
        if not endpoint_is_local(endpoint):
            raise ValueError(f"{endpoint} is not a local endpoint; a paid provider waits for the "
                             "receipt (plan D-15) and the ledger (D-12)")
        self._url = endpoint.rstrip("/") + "/chat/completions"
        self._model, self._recorder, self._timeout = model, recorder, timeout_s
        self._served_as = served_as or model
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
        self._turn += 1
        self._recorder.event("model_requested", {
            "turn": self._turn, "model": self._model, "messages": len(self._messages)})
        body = json.dumps({"model": self._served_as, "messages": self._messages,
                           "temperature": 0}).encode("utf-8")
        request = urllib.request.Request(self._url, data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as refused:        # A files both as a provider failure
            raise RuntimeError(
                f"endpoint {self._url}: HTTP {refused.code} {refused.reason}") from refused
        except urllib.error.URLError as unreachable:
            raise RuntimeError(f"endpoint {self._url}: {unreachable.reason}") from unreachable
        text = reply["choices"][0]["message"]["content"].strip()
        self._recorder.event("model_responded", {
            "turn": self._turn, "content": text, "usage": reply.get("usage") or {}})
        self._messages.append({"role": "assistant", "content": text})
        return text
