# The model boundary

**On main since 16 September, labelled a spike while trace-contract rows 1, 5 and 6 stay
open: the placeholders it writes for them are replaced in place when the rows resolve.
Local endpoints, and since 17 September paid ones behind a receipt, a price and a cap.**

The one package that talks to a model. `ChatProvider` sits behind A's `respond()` seam and
speaks A's protocol — `<TOOL_CALL>` and `<DECISION>` — to an OpenAI-compatible chat
endpoint on this machine, over the standard library. It keeps the conversation A does not:
a system message stating the protocol, the incident and the tools; then, each turn, the
newest observation in, the reply out, untouched.

Every request and every response is recorded at this boundary into the runtime's trace,
before A parses the reply — never reconstructed afterwards from what A made of it. That is
the design the contract proposal asks the D-1 review to approve or reject, running.

## A live run, on this machine, for nothing

```bash
mlx_lm.server --model <a model id, or a local model directory> --port 8090
python -m adii.runtime --incident orders-missing-day --provider local \
    --endpoint http://127.0.0.1:8090/v1 --model <the model's identity> --served-as default_model
python -m adii.demo                                      # the run is in the inspector
```

`--model` is the identity the record keeps. `--served-as` is the name the endpoint wants in
requests when that differs: mlx-lm's server loads whatever name a request carries unless it
is `default_model`, so a run against a model directory on disk records the model's name and
sends `default_model`. Any OpenAI-compatible local server works — Ollama
(`--endpoint http://127.0.0.1:11434/v1`), LM Studio, llama.cpp — and most take the model
name as is. Incidents: the walkthrough's, or any development specimen's. A 4-bit 4B model
runs beside the inspector on 16 GB; an 8B one wants everything else closed.

## What it refuses, and what a paid endpoint needs

Without a credential, a non-local endpoint. With one — the paid path, since 17 September —
the provider refuses to exist unless the receipt is already on disk (plan D-15), a nominal
price and a spend cap above zero are given (D-12), and the endpoint is https unless on
this machine. The credential goes on the wire as a bearer header and nowhere else: not
the receipt, the trace, the record, the report, an error, or the endpoint string — and to
the endpoint configured only: the worker follows no redirect, since `urllib` would re-issue
a 301, 302 or 303 as a GET at whatever host the Location named, bearer header still on it.
A refused status, a redirect, an unreachable host, a timeout, or a 200 whose body is not a
JSON object with `choices[0].message.content` is raised as `ProviderFailure` carrying only
the status and the structured error code — never the body, which a 401 fills with the
masked key — and the runtime files it as an infrastructure failure, not the model's (D-14).
The model is blamed only for what a well-formed response says; a malformed one keeps
whatever usage it carried, and a body that does not parse keeps the request's reserve.

The cap is hard by admission. Before each request the provider reserves that request's
worst case — every byte of every message counted as a token at the input rate (a byte-level
BPE tokenizer, which every priced model bills by and each price names, cannot make more
tokens than bytes; the chat format's own tokens are added as constants above their real
number), and `max_tokens` at the output rate, no discount assumed — and sends it only if the
ledger's exact worst case so far plus that reserve stays within the cap. Otherwise the run
ends as a `bound_hit` naming the spend, the reserve, the cap and the remainder, and the
request is not sent: a hard cap gives up some budget near the boundary rather than crossing
it. The arithmetic is `Decimal` from the price as written; nothing is rounded until the
record reports a number. The worst case spent counts proved usage at nominal prices and a
response without usage at the reserve that admitted it; the reserve is recorded on
`model_requested`, as text, with the estimator's name and its premise. After each reply the
bill is held to the reserve: a bill above it means a premise of the admission failed — the
endpoint ignored `max_tokens`, or tokenises otherwise — and the run ends as the provider's
failure (`ReserveBreached`), the response and its usage recorded, nothing further admitted.
A record still reports the lower bound — never 0.0 for a paid run: at least what was
proved, and the count of requests it could not price.

Two bounds of the run's own are checked here too, because this is where a run waits:
`max_model_requests`, a request count independent of A's turns, and `max_wall_clock_s`, a
deadline from the provider's construction. No request is sent past it. The request itself
is made by `worker.py`, a process of the run's own spoken to by lines, and the provider waits
on it for at most the time the deadline leaves; when that runs out the worker is killed and
the run ends as a `bound_hit` that says the request was cut in flight. So the local run never
waits past its deadline — not for a host that never answers, not for a body that trickles a
byte at a time, which `urllib`'s per-operation timeout would never call late. What killing
the local request cannot do is stop the remote endpoint computing or billing what it
received, so a request cut in flight keeps its full reserve. The endpoint's own patience,
`timeout_s` (120 s per socket operation), is enforced by the worker and is the provider's
failure when it trips, never the run's bound.

```bash
OPENAI_API_KEY=... python -m adii.runtime --incident revenue-after-deploy --provider openai \
    --model gpt-4.1-mini --max-cost-usd 0.25
```

## The pre-flight

`python -m adii.provider --check --model M` is passive: the model list with the credential,
costing nothing, proving the credential is accepted and the model advertised. It cannot
prove the project may spend — on 20 September it listed 252 models for a project whose every
completion was refused with `project_spend_limit_exceeded`. `--check --spend` adds the
active probe: one completion of one token through `worker.transact`, the run's own
transaction, billable and said so before it is sent (the reserve at nominal prices) and
after (the bill). Its output is classification, not prose — the provider's `error.code`
first, the status only when there is no code, an unknown code preserved verbatim:
`CREDENTIAL`, `PROJECT_BUDGET`, `MODEL_ACCESS`, `RATE_LIMIT`, `PROVIDER_INFRASTRUCTURE`,
`UNKNOWN_CODE`, each with whether retrying can help. It is structurally not a run — one
request, no investigator, no tools, nothing archived — and what it proves is that a
completion succeeded at check time, not that one will.

## What the runtime does with it

`runtime/live.py`: the runtime calls `investigate`, which calls A's `run()` with this
provider and the tools the runtime is already watching. A's two ending exceptions map to
two termination classes by type, never by message. There is no stop without a decision:
`<STOP>` is not a form, and a reply of it is rejected like any other that is none of the
two (contract row 5, decided 23 September). The validator (build plan M6) is not
yet wired into `live.py`, so a live REPAIR carries the only truthful verdict: not checked,
not accepted, no finding.

## What the first live runs showed on 15 September

Llama 3.1 8B, 4-bit, on the missing-orders, revenue-after-deploy and shipment-counts
specimens: REPAIR on all three in three calls each, including a repair for a legitimate
decline and a repair for a dispute no evidence can settle, and one patch to a path the
incident never permitted. Qwen3 4B Instruct on missing-orders: three calls rejected by the
tool layer for a guessed table and a guessed column, then a REPAIR that blamed the column
it had guessed wrong. Two models, one incident, two wrong repairs for two different
reasons, side by side in the inspector. Nothing in the loop enforces
`permitted_write_paths` yet. That is the false-repair bait the world specification warns
about, observed, and it is what the inspector exists to make legible.
