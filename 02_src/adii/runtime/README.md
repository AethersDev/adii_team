# The runtime

One command takes an incident to an archived run and a readable report.

```bash
python -m adii.runtime --incident demo-learning-001 --provider scripted
python -m adii.runtime --incident-dir DIR --provider local --model <id>   # the operator's own incident
python -m adii.demo                     # the run is in the inspector
```

`--incident-dir` takes a folder holding `incident.json` — the fields of `IncidentContext`:
what the investigator is told — and `world.sql`, the build script of its world, as a
specimen declares one — and, optionally, the evidence bundles below. The folder is checked
first, so one that is not an incident is refused before any label is claimed; then it is
copied into the claimed run folder, regular files only, and **the run is loaded from that
copy**: the tools, the digests in the receipt and the bytes the archive keeps are one read
of one package, and nothing that happens to the operator's folder afterwards can make them
disagree. A package that cannot be copied or loaded in that window releases the label:
nothing is archived, no model is spoken to, exit 2. The page's own form writes such a
folder from a description and CSV files (`tools/user_world.py`) and starts the run
through this command.

Every bundle is a map file beside a directory — `tools/packages.py` holds the one rule:
the map is strict JSON (a key bound twice is refused), every filename is package-local,
the directory holds exactly the declared files and no link, and each file's bytes are read
as UTF-8 exactly as they are. The archive attests and preserves the map files and every
file under the bundle directories as evidence, with the record.

An incident may carry transform evidence as `transform_map.json` plus
`transform_sources/`. The map is `logical transform id → package-local filename`. The
runtime loads the complete, closed bundle before the run, gives the investigator only the
logical IDs through `get_transform`, keeps the map and source bytes beside the record, and
binds the logical-ID/source-content digest into the pre-run receipt. No filename reaches
the model.

Operational notices use the same narrow convention: `notice_map.json` binds logical notice
IDs to exact UTF-8 bytes under `notice_sources/`. The model sees those IDs and complete
contents through `get_notice`; the archive keeps the package bytes and the receipt binds
the logical-ID/content mapping. Notice files are observations, never evaluator truth.

Transform change history uses `change_history_map.json` and `change_history_sources/`.
The archive retains the original source bytes; the receipt separately binds the source
artifact and the deterministic complete parsed observation returned by
`get_change_history`.

Reconciliation evidence uses `reconciliation_map.json` and
`reconciliation_sources/`. `read_reconciliation` exposes bounded raw-line windows in
physical source order — a line ends at CR, LF or CRLF and at nothing else, for the
per-line bound and the window alike. The archive retains the map and original bytes exactly, while the
receipt binds the canonical logical-ID/source-content mapping as `reconciliation_source`.
Individual window identities belong to their canonical traced tool results rather than a
made-up pre-run observation digest.

Declared operational schemas use `declared_schema_map.json` and
`declared_schema_sources/`. Each table binding augments that table's existing `get_schema`
observation with a parsed `declared_schema` object; SQLite remains the independent source
of physical columns and DDL. The archive keeps the map and JSON source bytes exactly. The
receipt binds source content as `declared_schema_source` and the deterministic exposed
objects separately as `declared_schema_observation`.

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

## The bounds

Six, each its own resource, each a flag with a default, each in the receipt and the record,
each named in the `bound_hit` it causes:

| flag | binds | where |
|---|---|---|
| `--max-turns` (12) | the investigator's model turns | A's loop |
| `--max-tool-calls` (30) | tool calls the executor runs; the call past it is DENIED and the investigator may still decide | the tool layer |
| `--max-model-requests` (20) | requests the provider makes — a count of its own, not the turn budget by another name | the provider |
| `--max-wall-clock-seconds` (600) | a deadline from the provider's first request: no request is sent past it, and one in flight waits no longer than it allows | the provider |
| `--max-cost-usd` (0.25, paid) | hard: a request is sent only if the worst case spent so far plus its own reserve — every byte of the messages at the input rate, `--max-tokens` at the output rate — stays within the cap; the record's cost is the ledger's lower bound | the provider |
| `--max-tokens` (512, paid) | the completion per request, priced in full in every reserve | the provider |

A bound at or below zero is refused before any label is claimed.

## What it does not do yet

- **Validate.** No independent validator exists (build plan M6); a live REPAIR carries the
  one truthful verdict — not checked, therefore not accepted.

## How to test it

```bash
pytest 02_src/tests -k runtime
```
