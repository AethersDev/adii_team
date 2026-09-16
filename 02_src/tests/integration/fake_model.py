"""An OpenAI-compatible /chat/completions served by the standard library, answering from a
script and remembering every request. Shared by the live-provider, launch and browser tests.

`probe`, when a test sets it, is called as each request arrives and its result kept in
`probed`: what was true on disk at the instant the model was spoken to. `delay` holds each
answer back, so a run lasts long enough for a page to be seen watching it."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler


class FakeModel(BaseHTTPRequestHandler):
    script: list[str] = []
    seen: list[dict] = []
    probe: Callable[[], object] | None = None
    probed: list[object] = []
    delay: float = 0.0

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeModel.seen.append(body)
        if FakeModel.probe is not None:
            FakeModel.probed.append(FakeModel.probe())
        time.sleep(FakeModel.delay)
        if not FakeModel.script:
            self.send_response(500)
            self.end_headers()
            return
        content = FakeModel.script.pop(0)
        reply = {"choices": [{"message": {"role": "assistant", "content": content}}],
                 "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
        payload = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass
