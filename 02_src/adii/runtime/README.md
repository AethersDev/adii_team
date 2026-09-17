# The runtime

One command takes an incident to an archived run and a readable report.

```bash
python -m adii.runtime --incident demo-learning-001 --provider scripted
python -m adii.runtime --incident-dir DIR --provider local --model <id>   # the operator's own incident
python -m adii.demo                     # the run is in the inspector
```

`--incident-dir` takes a folder holding `incident.json` — the fields of `IncidentContext`:
what the investigator is told — and `world.sql`, the build script of its world, as a
specimen declares one; both are kept beside the record, byte for byte, so the archive
holds what the system saw. The page's own form writes such a folder from a description
and CSV files (`tools/user_world.py`) and starts the run through this command.

## What it does

```text
incident → investigator → decision → (REPAIR only) validator → verdict
        → the public run, counters from the trace → record → archive → report
```

It knows A, B and C only as three protocols in `run.py` — `Investigator.investigate(context,
tools)`, `Tools.execute(call)`, `Validator.validate(context, decision)` — expressed in
contract types. Anything that satisfies them runs. Today the tools are the real executor
over the walkthrough world, and `scripted.py` scripts the investigator and the validator from
the walkthrough's recorded run; that is what `--provider scripted` means, and it costs nothing.

## The harness owns the trace

The runtime is the only component that sees every boundary crossing, so it writes the
trace: the incident handed over, every tool call and its result on the way through, the
decision, the verdict. `tool_calls` is counted from that trace. The investigator has no
channel through which to report a number.

The five event kinds are the walkthrough's — the only vocabulary that exists.
[docs/trace_event_contract.md](../../docs/trace_event_contract.md) proposes their
successors; `Recorder` in `run.py` is the one place that changes when it is agreed.

## Every way a run ends leaves a record

The label is claimed after every precondition that needs no I/O has passed and before the
run starts, so a taken label is refused before anything is spent and a refused run leaves
its label reusable. Then, however the run ends, one record lands under that label with the
trace so far:

| the run | `termination` | exit |
|---|---|---|
| committed to a disposition | `submitted`, with the decision and any verdict | 0 |
| was ended by the loop — it raised `Terminated(kind, detail)` | `model_failure` or `bound_hit`, the loop's words, unchanged | 3 |
| escaped with anything else | `infrastructure_failure`, naming the exception; traceback on stderr | 4 |

A payload that is not strict JSON — `NaN` from a tool, say — is our defect, not the model's:
the record is archived as an infrastructure failure naming the poison, keeping every event
that is JSON on its own. Sink I/O failure is terminal: if the archive cannot be written,
the process fails with the traceback and nothing pretends otherwise.

## What it does not do yet

- **Record model turns or cost.** No model runs. Both are zero until the event vocabulary
  is agreed and a provider exists (plan D-11, D-12); a number now would be invented.
- **Run a real provider.** That arrives with a receipt written before the first call
  (plan D-15).

## How to test it

```bash
pytest 02_src/tests -k runtime
```
