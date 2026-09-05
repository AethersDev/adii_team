# demo-learning-001 — the walkable incident

A deliberately trivial incident whose only job is to make the architecture concrete.

**This is not a scientific scenario and it is not one of the frozen development
incidents.** Nothing here has an answer key. You may read every file.

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
| `expected_report.txt` | what the telemetry layer renders — a committed regression test |

## What this run establishes

Four questions it should leave answerable without reopening `02_src/docs/architecture.md`:

1. The agent requests `run_sql`. **Which object crosses which boundary, who executes it,
   and what comes back?**
2. The agent's sandbox says its patch passes structural tests. **Is the repair accepted?**
3. May the investigator read the frozen answer key? **Who owns it, when is it consulted,
   and why would exposing it invalidate the evaluation?**
4. `tool_calls` says 3, but the trace has 4 calls. **Why?**

These are the same four that come up in review.
