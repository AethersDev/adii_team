"""The pre-flight, before anything is spent: is the credential accepted, is the model there?

    OPENAI_API_KEY=... python -m adii.provider --check --model gpt-4.1-mini [--endpoint URL]

One GET of the endpoint's model list with the credential as a bearer header — a request
that costs nothing — and a plain answer: accepted or refused (by status and structured
code, never the body), and whether the model id is among those listed. The credential is
read from the environment — or from the repository's `.env.local` when the environment
lacks it, as the runtime and the demo read it — and printed nowhere. Exit 0 accepted and
the model listed; 1 refused, unreachable, or the model absent; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

from .credential import load_env_local
from .openai_compatible import endpoint_may_carry_a_credential
from .worker import error_code as _error_code


def check(endpoint: str, model: str, credential: str, timeout_s: float = 30.0) -> tuple[int, str]:
    """(exit status, what to print)."""
    request = urllib.request.Request(endpoint.rstrip("/") + "/models", method="GET",
                                     headers={"Authorization": f"Bearer {credential}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            listed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as refused:
        code = _error_code(refused)
        return 1, f"credential refused: HTTP {refused.code}" + (f" {code}" if code else "")
    except urllib.error.URLError as unreachable:
        return 1, f"endpoint unreachable: {type(unreachable.reason).__name__}"
    except TimeoutError:
        return 1, "endpoint timed out"
    ids = [m.get("id") for m in listed.get("data", []) if isinstance(m, dict)]
    if model in ids:
        return 0, f"credential accepted; {len(ids)} models listed; {model} available"
    return 1, f"credential accepted; {len(ids)} models listed; {model} is not among them"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.provider", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", required=True,
                        help="ask the endpoint for its model list with the credential")
    parser.add_argument("--model", required=True, help="the model id the run will ask for")
    parser.add_argument("--endpoint", default="https://api.openai.com/v1")
    args = parser.parse_args(argv)
    if not endpoint_may_carry_a_credential(args.endpoint):
        print(f"{args.endpoint!r}: https (unless on this machine), no query string, no userinfo")
        return 2
    try:
        load_env_local()                 # the operator's file, when the shell has no key
    except ValueError as bad:
        print(bad)
        return 2
    credential = os.environ.get("OPENAI_API_KEY")
    if not credential:
        print("OPENAI_API_KEY is not set")
        return 2
    status, said = check(args.endpoint, args.model, credential)
    print(said)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
