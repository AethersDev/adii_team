# demo-learning-001 — the walkable incident

A deliberately trivial incident whose only job is to make the architecture concrete.

**This is not a scientific scenario and it is not one of the frozen development
incidents.** You may read every file: its truth is in this folder for everyone. The
evaluation authority holds a *development* key for it
(`02_src/adii/evaluation/fixtures/demo-learning-001.answer.json`, authored by C, frozen
15 September), which carries no evaluation claim: it exists so the scoring path can be
exercised on the one world the validator can rebuild. It is a teaching
fixture that demonstrates and tests the runtime's mechanics; it is not the canonical ADII
demo world (`01_data/demo/world/`) and produces no product or evaluation claim.

```bash
python -m adii.examples.walkthrough --step
```

## What happens, and which object crosses which boundary

| # | What happens | Boundary |
|---|---|---|
| 1 | An alert arrives: 3 orders/day where there were 300 | operator → `IncidentContext` |
| 2 | The investigator is handed the incident — no path, no DB handle, no key | → **A** |
| 3 | It asks what the data looks like: `get_schema(table='orders')` | **A** → `ToolCall` → **B** |
| 4 | The tool layer answers with columns | **B** → `ToolResult` → **A** |
| 5 | It checks the **source**: counts steady at ~300/day | `ToolCall` / `ToolResult` |
| 6 | It checks the **mart**: 2.97 where the source says 297 | a 100× gap, located |
| 7 | It tries `delete_table`. **DENIED** — B refuses | **B** is a boundary, not a helper |
| 8 | It commits: `REPAIR` with a `repair_id` **and** a patch | **A** → `InvestigationDecision` → **C** |
| 9 | The validator rebuilds from frozen inputs and returns **ACCEPT** | **C** → `ValidationResult` |
| 10 | Everything observable is persisted and rendered | → `TraceEvent` → **D** |

## Files

| File | What it is |
|---|---|
| `incident.json` | what the investigator was told |
| `trace.jsonl` | every event, in order — including the refused call |
| `decision.json` | the disposition, the reasoning, the patch |
| `validation.json` | the independent verdict |
| `transform_map.json`, `transform_sources/stg_orders.sql` | the transform the incident permits the investigator to change, as it is before the repair — served through `get_transform("stg_orders")`, so a repair is never written blind; applied as-is it reproduces the defect, and the committed patch is what fixes it |
| `expected_report.txt` | what the telemetry layer renders — a committed regression test |
| `record.json` | the same run as one `adii.run_record/v1` document — what `--archive` writes and the inspector renders; a committed fixture of the v1 shape |
| `endings/` | the same incident ended every other way — a rejected repair, a model failure, a bound, an infrastructure failure — each a record the runtime produced and the report it renders to; `python -m adii.examples.endings` regenerates them |

## What this run establishes

Four questions it should leave answerable without reopening `02_src/docs/architecture.md`:

1. The agent requests `run_sql`. **Which object crosses which boundary, who executes it,
   and what comes back?**
2. The agent's sandbox says its patch passes structural tests. **Is the repair accepted?**
3. May the investigator read the frozen answer key? **Who owns it, when is it consulted,
   and why would exposing it invalidate the evaluation?**
4. `tool_calls` says 3, but the trace has 4 calls. **Why?**

These are the same four that come up in review.
