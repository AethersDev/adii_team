"""The request worker: one HTTP transaction per line, in a process the provider can kill.

    python -m adii.provider.worker      # started by ChatProvider, never by hand

`urllib`'s timeout bounds a connect and each socket read, not a response: an endpoint that
trickles its body a byte at a time is never late by that measure and would hold a run past
its deadline. So the provider does not make requests itself. It starts this process once
per run and hands it each request as one JSON line on stdin — the URL, the body, the
headers (the credential among them: it travels this pipe and no further; the process is
started without it in its environment) and the endpoint's per-operation timeout — and
reads one JSON line back: the status and body text of the response, or the failure in
structure — its kind, status and error code, never the body of a refusal, which a 401
fills with the masked key it was sent. The provider waits at most the run's remaining
wall clock for that line and kills this process when it does not come. Killing the local
request cannot stop the remote endpoint computing or billing what it already received,
which is why a request cut in flight keeps its full reserve in the ledger.

No redirect is followed. The endpoint contacted is the endpoint configured, and the
credential goes to it and nowhere else: `urllib` would otherwise re-issue a 301, 302 or 303
as a GET at whatever host the Location header named, the bearer header still on it and the
body gone. Any 3xx is the endpoint's refusal to answer, reported as `http` with its status.
"""
from __future__ import annotations

import http.client
import json
import sys
import urllib.error
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Every 3xx is left as the HTTPError it arrived as; nothing is re-sent anywhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def transact(request: dict) -> dict:
    """One request as the provider described it, one structured answer."""
    sent = urllib.request.Request(request["url"], data=request["body"].encode("utf-8"),
                                  method="POST", headers=request["headers"])
    try:
        with _OPENER.open(sent, timeout=request["timeout_s"]) as response:
            return {"ok": True, "status": response.status,
                    "body": response.read().decode("utf-8")}
    except urllib.error.HTTPError as refused:
        return {"ok": False, "kind": "http", "status": refused.code, "code": error_code(refused)}
    except urllib.error.URLError as unreachable:
        kind = "timeout" if isinstance(unreachable.reason, TimeoutError) else "unreachable"
        return {"ok": False, "kind": kind}
    except TimeoutError:                       # a read that stalled past the timeout
        return {"ok": False, "kind": "timeout"}
    except (OSError, http.client.HTTPException):   # the connection broke mid-body
        return {"ok": False, "kind": "unreachable"}
    except UnicodeDecodeError:
        return {"ok": False, "kind": "malformed"}


def error_code(refused: urllib.error.HTTPError) -> str | None:
    """The structured `error.code` an OpenAI-shaped refusal carries — and only that. The
    message beside it is discarded unread: a 401's message echoes the key it was sent."""
    try:
        document = json.loads(refused.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError, OSError):
        return None
    error = document.get("error") if isinstance(document, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else None


def main() -> int:
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    for line in iter(stdin.readline, b""):
        stdout.write(json.dumps(transact(json.loads(line))).encode("utf-8") + b"\n")
        stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
