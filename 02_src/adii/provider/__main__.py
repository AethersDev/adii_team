"""The pre-flight, before anything is spent — and, asked for, the smallest thing that spends.

    python -m adii.provider --check --model gpt-4.1-mini [--endpoint URL]
    python -m adii.provider --check --spend --model gpt-4.1-mini [--endpoint URL]

`--check` is passive: one GET of the endpoint's model list with the credential as a bearer
header, a request that costs nothing. It proves the credential is accepted and the model is
advertised — and nothing about whether this project may spend, which no listing can show:
a project at its spend limit lists 252 models and refuses every completion.

`--spend` adds the active probe: one completion, one word in, `max_tokens` 1, through the
run's own transaction (`worker.transact` — no redirect, structured codes, never the body of
a refusal). A project whose spend limit is reached, a model this key may not call, a rate
limit, an unreachable host are told apart by the provider's `error.code` — never by the
status alone while a code exists, since two 429s can mean two different things — before
an audience is in the room. It is billable and says so before it sends: a few
ten-thousandths of a cent at nominal prices, printed as the reserve and then as the bill.
It is structurally not a run: one request, no investigator, no tools, no record, no
archive. Its result is these lines and its exit status; what it proves is that a
completion succeeded at check time, not that one will.

Output is classification, not prose — `key: value` lines: `credential`, `models_listed`,
`model`, `model_listed`, `passive_check`; with `--spend`, `spend_check` (BILLABLE before the
request; PASS or BLOCKED after), `request_sent`, `usage`, `cost_usd`, `reserve_premise`;
on any refusal `provider_status`, `provider_error_code`, `classification` and `retry`. The
credential is read from the environment — or from the repository's `.env.local` when the
environment lacks it, as the runtime and the demo read it — and printed nowhere.

Exit 0: the passive check passed — with `--spend`, a completion succeeded at check time and
the reserve premise held. 1: refused, blocked, unreachable, malformed, or the model absent.
2: usage.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

from ..reporting.ledger import PRICES, Price, priced, reserve_for
from .credential import load_env_local
from .openai_compatible import endpoint_may_carry_a_credential, input_tokens_upper_bound
from .worker import error_code as _error_code
from .worker import transact

TIMEOUT_S = 30.0
PROBE = [{"role": "user", "content": "ping"}]     # one word in, one token out

# The provider's structured codes, grouped by what an operator must do about them. A code
# not listed is preserved verbatim under UNKNOWN_CODE, never guessed at from the status.
BUDGET_CODES = frozenset({"project_spend_limit_exceeded", "organization_spend_limit_exceeded",
                          "organization_usage_limit_exceeded", "credit_balance_exhausted",
                          "insufficient_quota", "billing_hard_limit_reached"})
ACCESS_CODES = frozenset({"model_not_found", "model_not_supported", "insufficient_permissions"})
RETRY = {"CREDENTIAL": "no — the credential is refused",
         "PROJECT_BUDGET": "no — the project's owner must change the limit",
         "MODEL_ACCESS": "no — this key may not call this model here",
         "RATE_LIMIT": "may succeed later — rate limited",
         "PROVIDER_INFRASTRUCTURE": "may succeed later — the endpoint did not answer in the API",
         "UNKNOWN_CODE": "unknown — the code above is the provider's, preserved as sent"}


def classify(kind: str, status: int | None, code: str | None) -> str:
    """What kind of refusal this is: the provider's structured code first; the status only
    when there is no code; anything not in the tables preserved, not interpreted."""
    if kind != "http":                      # unreachable, timeout, malformed, worker
        return "PROVIDER_INFRASTRUCTURE"
    if code is not None:
        if code == "invalid_api_key":
            return "CREDENTIAL"
        if code in BUDGET_CODES:
            return "PROJECT_BUDGET"
        if code in ACCESS_CODES:
            return "MODEL_ACCESS"
        if code == "rate_limit_exceeded":
            return "RATE_LIMIT"
        return "UNKNOWN_CODE"
    return {401: "CREDENTIAL", 403: "MODEL_ACCESS", 404: "MODEL_ACCESS",
            429: "RATE_LIMIT"}.get(status or 0, "PROVIDER_INFRASTRUCTURE")


def listing(endpoint: str, model: str, credential: str) -> dict[str, object]:
    """The passive check: GET the model list with the credential. Returns what was seen, in
    structure — a status and a code on refusal, never the body."""
    request = urllib.request.Request(endpoint.rstrip("/") + "/models", method="GET",
                                     headers={"Authorization": f"Bearer {credential}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            listed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as refused:
        return {"credential": "refused", "kind": "http", "status": refused.code,
                "code": _error_code(refused)}
    except urllib.error.URLError as unreachable:
        kind = "timeout" if isinstance(unreachable.reason, TimeoutError) else "unreachable"
        return {"credential": kind, "kind": kind, "status": None, "code": None}
    except (TimeoutError, ValueError, UnicodeDecodeError):
        return {"credential": "malformed", "kind": "malformed", "status": None, "code": None}
    data = listed.get("data") if isinstance(listed, dict) else None
    ids = [m.get("id") for m in data if isinstance(m, dict)] if isinstance(data, list) else []
    return {"credential": "accepted", "models_listed": len(ids), "model_listed": model in ids}


def probe(endpoint: str, model: str, credential: str, price: Price) -> dict[str, object]:
    """The active check: one completion of one token, by the run's own transaction. Returns
    the bill and whether the reserve premise held, or the refusal in structure."""
    body = {"model": model, "messages": PROBE, "max_tokens": 1, "temperature": 0}
    request = {"url": endpoint.rstrip("/") + "/chat/completions", "body": json.dumps(body),
               "headers": {"Content-Type": "application/json",
                           "Authorization": f"Bearer {credential}"},
               "timeout_s": TIMEOUT_S}
    answer = transact(request)
    if not answer["ok"]:
        return {"ok": False, "kind": answer["kind"], "status": answer.get("status"),
                "code": answer.get("code")}
    try:
        reply = json.loads(answer["body"])
    except ValueError:
        reply = None
    if not isinstance(reply, dict):
        return {"ok": False, "kind": "malformed", "status": answer.get("status"), "code": None}
    usage = reply.get("usage") if isinstance(reply.get("usage"), dict) else {}
    bound = input_tokens_upper_bound(PROBE)
    tokens_in, tokens_out = usage.get("prompt_tokens"), usage.get("completion_tokens")
    holds = (isinstance(tokens_in, int) and isinstance(tokens_out, int)
             and tokens_in <= bound and tokens_out <= 1)
    return {"ok": True, "usage": usage, "cost": priced(usage, price), "bound": bound,
            "premise": holds}


def say(key: str, value: object) -> None:
    print(f"{key}: {value}")


def refusal(seen: dict[str, object]) -> None:
    kind = classify(str(seen["kind"]), seen.get("status"), seen.get("code"))
    say("provider_status", seen.get("status") if seen.get("status") else "none")
    say("provider_error_code", seen.get("code") or "none")
    say("classification", kind)
    say("retry", RETRY[kind])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.provider", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", required=True,
                        help="the passive check: the model list, with the credential")
    parser.add_argument("--spend", action="store_true",
                        help="the active check too: one completion of one token — billable")
    parser.add_argument("--model", required=True, help="the model id the run will ask for")
    parser.add_argument("--endpoint", default="https://api.openai.com/v1")
    args = parser.parse_args(argv)
    if not endpoint_may_carry_a_credential(args.endpoint):
        print(f"{args.endpoint!r}: https (unless on this machine), no query string, no userinfo")
        return 2
    if args.spend and args.model not in PRICES:
        print(f"--spend needs a model with a nominal price in reporting/ledger.py, so the bill "
              f"can be named; priced: {', '.join(sorted(PRICES))}")
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

    seen = listing(args.endpoint, args.model, credential)
    say("credential", seen["credential"])
    say("model", args.model)
    if seen["credential"] != "accepted":
        refusal(seen)
        say("passive_check", "FAIL")
        return 1
    say("models_listed", seen["models_listed"])
    say("model_listed", "yes" if seen["model_listed"] else "no")
    say("passive_check", "PASS" if seen["model_listed"] else "FAIL")
    if not args.spend:
        return 0 if seen["model_listed"] else 1

    price = PRICES[args.model]
    reserve = reserve_for(input_tokens_upper_bound(PROBE), price, 1)
    say("spend_check", f"BILLABLE — one request, max_tokens=1, nominal_max_cost_usd={reserve:f}")
    result = probe(args.endpoint, args.model, credential, price)
    say("request_sent", 1)
    if not result["ok"]:
        say("spend_check", "BLOCKED")
        refusal(result)
        return 1
    usage, cost = result["usage"], result["cost"]
    say("spend_check", "PASS")
    say("usage", f"prompt_tokens={usage.get('prompt_tokens')} "
                 f"completion_tokens={usage.get('completion_tokens')}")
    say("cost_usd", f"{cost:f} (nominal, {price.table})" if cost is not None
        else "unknown — no integer usage in the reply")
    say("reserve_premise", (f"holds — prompt_tokens <= {result['bound']}, completion_tokens <= 1")
        if result["premise"] else
        (f"VIOLATED — prompt_tokens {usage.get('prompt_tokens')} against a bound of "
         f"{result['bound']}, completion_tokens {usage.get('completion_tokens')} against 1; "
         "the cap's arithmetic would not hold for this model"))
    say("completion", "succeeded at check time")
    return 0 if result["premise"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
