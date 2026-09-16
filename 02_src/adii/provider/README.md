# The model boundary — SPIKE

**Local endpoints only. Not merged to main until the trace event contract's rows resolve.**

The one package that talks to a model. `ChatProvider` sits behind A's `respond()` seam and
speaks A's protocol — `<TOOL_CALL>`, `<DECISION>`, `<STOP>` — to an OpenAI-compatible chat
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

## What it refuses

A non-local endpoint. A model on this machine has no nominal price, so a run costs nothing;
the runtime writes its receipt anyway, before the investigator runs. A paid provider needs
the receipt to be a precondition of the first call (plan D-15) and the ledger that makes
cost evidence (D-12); until then a record saying a paid run cost 0.0 would be inherited
defect D15, and this package will not produce one.

## What the runtime does with it

`runtime/live.py`: the runtime calls `investigate`, which calls A's `run()` with this
provider and the tools the runtime is already watching. A's two ending exceptions map to
two termination classes by type, never by message. A stop with no decision has no class
yet (contract row 5) and is mapped to `model_failure` with the detail saying so — the one
policy choice this spike makes that main must not. No validator exists (build plan M6), so
a live REPAIR carries the only truthful verdict: not checked, not accepted, no finding.

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
