"""An OpenAI-compatible /chat/completions served by the standard library, answering from a
script and remembering every request. Shared by the live-provider and launch tests."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler


class FakeModel(BaseHTTPRequestHandler):
    script: list[str] = []
    seen: list[dict] = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeModel.seen.append(body)
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
