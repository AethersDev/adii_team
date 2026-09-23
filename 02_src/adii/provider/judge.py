"""The judge's model call — the evaluation authority's one question to a model, asked here
because this package is the only one that speaks to a model (final plan, decision J).

`evaluation/judge.py` builds the prompt and parses the verdict; this supplies the callable
it takes, `prompt -> reply`, and keeps what each call cost and was asked, so the report can
name the judge by model and prompt digest. One request per call through the run's own
transaction (`worker.transact`: no redirect followed, a refusal in structure and never its
body), temperature 0, a bounded reply, a priced model, the credential from the environment
or `.env.local` and nowhere else. A judge that does not answer is a ValueError naming how,
so a run whose case needed one is refused a score rather than given a guessed one.
"""
from __future__ import annotations

import hashlib
import json
import os

from ..reporting.ledger import PRICES, priced
from .credential import load_env_local
from .openai_compatible import endpoint_may_carry_a_credential
from .worker import transact

ENDPOINT = "https://api.openai.com/v1"
MAX_TOKENS = 200          # a verdict word and one sentence of reasoning
TIMEOUT_S = 60.0


class Judge:
    """`judge(prompt) -> reply`, and `calls`: one record per question asked."""

    def __init__(self, model: str, endpoint: str = ENDPOINT) -> None:
        if model not in PRICES:
            raise ValueError(f"the judge's model must have a nominal price in "
                             f"reporting/ledger.py; priced: {', '.join(sorted(PRICES))}")
        if not endpoint_may_carry_a_credential(endpoint):
            raise ValueError(f"{endpoint!r}: a judge's endpoint is https (unless on this "
                             "machine) and carries no query string or credentials")
        load_env_local()
        self._credential = os.environ.get("OPENAI_API_KEY")
        if not self._credential:
            raise ValueError("OPENAI_API_KEY is not set; the judge takes its credential from "
                             "the environment or .env.local and nowhere else")
        self.model, self._url, self.calls = model, endpoint.rstrip("/") + "/chat/completions", []

    def __call__(self, prompt: str) -> str:
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0, "max_tokens": MAX_TOKENS}
        answer = transact({"url": self._url, "body": json.dumps(body), "timeout_s": TIMEOUT_S,
                           "headers": {"Content-Type": "application/json",
                                       "Authorization": f"Bearer {self._credential}"}})
        if not answer["ok"]:
            raise ValueError(f"the judge did not answer: {answer['kind']}"
                             + "".join(f" {v}" for v in (answer.get("status"), answer.get("code"))
                                       if v))
        try:
            reply = json.loads(answer["body"])
            text = reply["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ValueError("the judge answered, but not in the API's shape") from None
        if not isinstance(text, str):
            raise ValueError("the judge answered without text")
        usage = reply.get("usage")
        cost = priced(usage, PRICES[self.model])
        self.calls.append({
            "model": self.model,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "usage": usage, "cost_usd": None if cost is None else format(cost, "f"),
            "price_table": PRICES[self.model].table})
        return text
