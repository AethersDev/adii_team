# Agent loop and investigation state

The agent. It decides what to look at, asks for it, and eventually commits.

**You own:** model messages, tool calling, the loop, state, budgets, stopping conditions,
structured submission.

**You do not own:** what the tools return (B), whether a repair is accepted (C), how the
run is persisted (D).

## First build

A minimal loop against a **fake provider** — a scripted object that returns canned turns.
No API key, no network:

```text
model → one tool → observation → model → structured decision
```

Then swap the fake tool for the tool layer's `get_schema` and `run_sql`. Do not start with thirteen
tools.

## What to get right early

- **Emit `ToolCall`, receive `ToolResult`.** Never touch a file or a database yourself.
- **A `DENIED` or `REJECTED` result is information, not a crash.** Feed it back to the
  model and let it retry.
- **The loop must terminate.** Turn budget, tool-call budget, and a final action.
- **`REPAIR` requires a `repair_id` and a patch.** The contract enforces it; you should
  fail closed before you get there.

## What the runtime expects of it

The runtime in `02_src/adii/runtime/run.py` calls one method and records everything
around it:

```text
investigate(context: IncidentContext, tools) -> InvestigationDecision
```

`tools.execute(ToolCall) -> ToolResult` is the only door to the world, and the runtime
watches it: every call and result lands in the trace on the way through, so the loop
never counts anything itself. To end a run without a decision — a bound hit, a model
failure — raise `Terminated("bound_hit" | "model_failure", detail)` from that module. The
classification travels to the record unchanged; the runtime adds no interpretation. Any
other exception is archived as an infrastructure failure, ours. The scripted stand-in the
runtime uses today is `02_src/adii/runtime/fakes.py`; the real loop replaces it.

## The question this component answers

How does a model *request* a tool, how does the result get back to it, and what ends the
loop?

## Invariants

- No `open()`, no `sqlite3`, no `subprocess`, no network. Everything this package sees
  arrives as a `ToolResult` from a boundary that was allowed to refuse.
- It never imports `validation/` or `evaluation/`. The contestant does not see the judge.
- It never certifies its own repair, and never reports its own counters — those come from
  the trace.
- The loop stops on a stated condition, not by running out of turns or raising.

*Enforced by* `test_the_investigator_and_contracts_do_no_file_io`,
`test_only_the_tool_layer_touches_the_outside_world`,
`test_the_investigator_cannot_reach_the_judge`.

## How to test it

```bash
pytest 02_src/tests -k investigator
```

## Related

Speaks `contracts/`, calls `tools/`, is judged by `validation/` and `evaluation/`.
Six-question summary in [system_map.md](../../docs/system_map.md#investigator).
