# The runtime

One command takes an incident to an archived run and a readable report.

```bash
python -m adii.runtime --incident demo-learning-001 --provider fake
python -m adii.demo                     # the run is in the inspector
```

## What it does

```text
incident → investigator → decision → (REPAIR only) validator → verdict
        → the public run, counters from the trace → record → archive → report
```

It knows A, B and C only as three protocols in `run.py` — `Investigator.investigate(context,
tools)`, `Tools.execute(call)`, `Validator.validate(context, decision)` — expressed in
contract types. Anything that satisfies them runs. Today `fakes.py` scripts all three from
the walkthrough's recorded run; that is what `--provider fake` means, and it costs nothing.

## The harness owns the trace

The runtime is the only component that sees every boundary crossing, so it writes the
trace: the incident handed over, every tool call and its result on the way through, the
decision, the verdict. `tool_calls` is counted from that trace. The investigator has no
channel through which to report a number.

The five event kinds are the walkthrough's — the only vocabulary that exists.
[docs/trace_event_contract.md](../../docs/trace_event_contract.md) proposes their
successors; `Recorder` in `run.py` is the one place that changes when it is agreed.

## What it does not do yet

- **Record model turns or cost.** No model runs. Both are zero until the event vocabulary
  is agreed and a provider exists (plan D-11, D-12); a number now would be invented.
- **Archive a run that failed.** An exception propagates. The failure-preserving sink,
  where a model failure, a bound and an infrastructure failure each leave a classified
  record, is plan D-4.
- **Run a real provider.** That arrives with a receipt written before the first call
  (plan D-15).

## How to test it

```bash
pytest 02_src/tests -k runtime
```
