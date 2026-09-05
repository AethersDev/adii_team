# Tool execution and evidence grounding

The agent's entire view of the world. Also the thing that stops it seeing too much.

**You own:** tool schemas, SQL execution, observations, permissions, the candidate-repair
sandbox.

**You do not own:** when tools get called (A), whether a repair is truly good (C).

## First build

`get_schema` plus a **read-only** `run_sql` against a tiny local database. Read-only
enforced by the database, not by inspecting the query text — a regex on SQL is a
suggestion, an authorizer is a boundary.

## What to get right early

- **You are a boundary, not a helper.** Refusing is your job. `DENIED` is you working.
- **Distinguish the four statuses.** `OK` / `DENIED` / `REJECTED` / `ERROR`. A wrong
  argument from the model is `REJECTED` and the model may retry; a bug in your tool is
  `ERROR` and it is ours to fix. Conflating them makes the model look worse than it is.
- **Bound every result.** Row caps, line windows. An unbounded result becomes an
  unbounded context.
- **No path arguments.** Ever. A tool that takes a filesystem path can be pointed at the
  answer key.

## The question this component answers

Why is `DENIED` a success rather than a failure?

## Invariants

- This is the only package in `adii/` permitted to touch the filesystem, a database, a
  subprocess or the network.
- Every call returns a `ToolResult` with an accurate status. `DENIED` is a successful
  outcome — a boundary that cannot refuse is not a boundary.
- A tool never returns more than the caller asked for, and never silently widens scope.
- Observations carry a stable evidence id, so a decision can cite something that happened.

*Enforced by* `test_only_the_tool_layer_touches_the_outside_world`.

## How to test it

```bash
pytest 02_src/tests -k tool
```

## Related

Called by `investigator/`, speaks `contracts/`.
Six-question summary in [system_map.md](../../docs/system_map.md#tools).
