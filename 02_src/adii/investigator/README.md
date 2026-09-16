# Agent loop and investigation state

The agent. It decides what to look at, asks for it, and eventually commits.

**You own:** model messages, tool calling, the loop, state, budgets, stopping conditions,
structured submission.

**You do not own:** what the tools return (B), whether a repair is accepted (C), how the
run is persisted (D).

## What exists, as merged on 14 September

`loop.py` — `run(incident, provider, executor, *, max_turns)` returns `(decision or None,
trace)`. The provider seam is `respond(observation=…, observations=…) -> str`, and the
response is interpreted by prefix: `<TOOL_CALL>` JSON, `<DECISION>` JSON, `<STOP>`, or
plain text. `provider.py` — `ScriptedProvider`, deterministic, for tests; no model, no
network. `state.py` — `InvestigationState`, the observations accumulated so far, a frozen
value. Endings are two exceptions carrying the trace so far, `TurnBudgetExceededError` and
`ProviderFailureError`. The loop writes its own trace of eight kinds;
`docs/trace_event_contract.md` records what each means and what the runtime needs from
them. The decision policy — REPAIR and NO_REPAIR need an observation, ESCALATE does not —
is `docs/decision_policy.md`. It runs against the tool layer's real `get_schema` and
`run_sql` in `02_src/tests/integration/`.

## What to get right early

- **Emit `ToolCall`, receive `ToolResult`.** Never touch a file or a database yourself.
- **A `DENIED` or `REJECTED` result is information, not a crash.** Feed it back to the
  model and let it retry.
- **The loop must terminate.** Turn budget, tool-call budget, and a final action.
- **`REPAIR` requires a `repair_id` and a patch.** The contract enforces it; you should
  fail closed before you get there.

## What the runtime expects of it

The runtime in `02_src/adii/runtime/run.py` calls `investigate(context, tools)` on an
`Investigator` and records every tool call and result on the way through, so the loop
never counts anything. It maps an ending to a termination class and archives the run
however it ended. Today the runtime still drives the scripted stand-in in
`02_src/adii/runtime/scripted.py`; nothing outside this package imports the loop yet. The
adapter between `run()` and `investigate()` — one canonical trace recorded at the provider
boundary, A's two exceptions mapped to two termination classes, a decided meaning for a
stop without a decision — is the next unit, and it waits on the decision rows in
`docs/trace_event_contract.md`. A keeps its exceptions; the runtime does the mapping.

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
