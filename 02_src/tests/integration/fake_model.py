"""An OpenAI-compatible /chat/completions served by the standard library, answering from a
script and remembering every request. Shared by the live-provider, launch and browser tests.

`probe`, when a test sets it, is called as each request arrives and its result kept in
`probed`: what was true on disk at the instant the model was spoken to. `delay` holds each
answer back, so a run lasts long enough for a page to be seen watching it — the answer is
taken from the script before the wait, so a handler cut by a deadline and still sleeping
cannot take the next test's turn when it wakes. `refuse`, when
set, answers the next request with that status and JSON body, once — a 401 whose body echoes
a masked key, a 429, a 500 — the way a paid endpoint does; `refuse_completion` does the
same for the next completion only, leaving the model list answered, the way a project at
its spend limit does. `usage` replaces the fixed usage of a reply when a test sets it. `seen`
keeps each request's Authorization header beside its body, so a test can see what a
credential became on the wire."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler

# A script entry the endpoint answers with `content: null` — a reply in the API's shape that
# carries no text, which the runtime files as the model's failure, never the provider's.
NO_TEXT = "<no text>"


class FakeModel(BaseHTTPRequestHandler):
    script: list[str] = []
    seen: list[dict] = []
    probe: Callable[[], object] | None = None
    probed: list[object] = []
    delay: float = 0.0
    refuse: tuple[int, dict] | None = None
    refuse_completion: tuple[int, dict] | None = None
    usage: dict | None = None
    authorization: list[str | None] = []

    def do_GET(self):  # noqa: N802
        """The model list, as a paid endpoint answers it — with the credential checked."""
        FakeModel.authorization.append(self.headers.get("Authorization"))
        if FakeModel.refuse is not None:
            status, error = FakeModel.refuse
            FakeModel.refuse = None
            payload = json.dumps(error).encode("utf-8")
            self.send_response(status)
        else:
            payload = json.dumps({"data": [{"id": "gpt-4.1-mini"}, {"id": "gpt-4o-mini"}]}) \
                .encode("utf-8")
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeModel.seen.append(body)
        FakeModel.authorization.append(self.headers.get("Authorization"))
        if FakeModel.probe is not None:
            FakeModel.probed.append(FakeModel.probe())
        refuse, FakeModel.refuse = FakeModel.refuse, None
        if refuse is None:
            refuse, FakeModel.refuse_completion = FakeModel.refuse_completion, None
        content = FakeModel.script.pop(0) if FakeModel.script and refuse is None else None
        time.sleep(FakeModel.delay)
        if refuse is not None:
            status, error = refuse
            payload = json.dumps(error).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if content is None:
            self.send_response(500)
            self.end_headers()
            return
        text = None if content == NO_TEXT else content
        reply = {"choices": [{"message": {"role": "assistant", "content": text}}],
                 "usage": FakeModel.usage or {"prompt_tokens": 100, "completion_tokens": 20},
                 "system_fingerprint": "fp_fake"}
        payload = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass
