# Tool execution and evidence grounding

The agent's entire view of the world. Also the thing that stops it seeing too much.

**You own:** tool schemas, SQL execution, observations, permissions, the candidate-repair
sandbox.

**You do not own:** when tools get called (A), whether a repair is truly good (C).

## What is built

The first build: `get_schema` plus a **read-only** `run_sql` against a tiny local
database, behind an executor that keeps the four statuses apart.

| File | What it is |
|---|---|
| `errors.py` | `Denied` and `Rejected` — the two ways a handler declines, kept distinct from a bug |
| `schemas.py` | `ToolSpec` / `Parameter`, and `validate_arguments`, which runs before any handler |
| `executor.py` | `ToolExecutor`: registry, dispatch, the status decision, the evidence id |
| `database.py` | `ReadOnlyDatabase`: SQLite behind an **authorizer**; row caps, cell caps, a step budget |
| `sql_tools.py` | the two tool handlers, and `build_sql_tools(database)` to wire them up |
| `walkthrough_world.py` | the `demo-learning-001` world as SQL, so the fixture can be replayed live |

```python
from adii.contracts import ToolCall
from adii.tools import build_sql_tools, open_walkthrough_world

executor = build_sql_tools(open_walkthrough_world(), max_calls=20)
executor.advertised()            # the schemas the loop shows the model
result = executor.execute(ToolCall(call_id="c1", name="run_sql", arguments={
    "query": "SELECT order_date, count(*) FROM orders GROUP BY 1"}))
result.status                    # "OK" — and result.content["evidence_id"] is stable
```

To run against a real database file, `ReadOnlyDatabase.from_file(path)` — the path is
configuration the runtime holds, never something a tool accepts.

**How a call is decided, in order.** Unknown tool → `DENIED`. Budget spent → `DENIED`.
Arguments fail the advertised schema → `REJECTED`, with every problem named. Then the
handler runs: it may raise `Denied` or `Rejected`; anything else it raises is `ERROR`.
An `OK` observation is stamped with `evidence_id`, a hash of the tool, its arguments and
what it returned — the same observation always gets the same id.

**Not built yet.** The candidate-repair sandbox; the canonical three-configuration world
from `docs/DATA_WORLD_v0.md` (a shared decision, not this package's alone); tools over
logs, manifests and transforms.

## What to get right early

- **You are a boundary, not a helper.** Refusing is your job. `DENIED` is you working.
- **Distinguish the four statuses.** `OK` / `DENIED` / `REJECTED` / `ERROR`. A wrong
  argument from the model is `REJECTED` and the model may retry; a bug in your tool is
  `ERROR` and it is ours to fix. Conflating them makes the model look worse than it is.
- **Bound every result.** Row caps, line windows. An unbounded result becomes an
  unbounded context.
- **No path arguments.** Ever. A tool that takes a filesystem path can be pointed at the
  answer key. `Parameter` refuses a path-shaped name at registration; the real defence is
  that no handler here opens one.
- **Read-only at the database.** `ReadOnlyDatabase` allows four authorizer actions —
  SELECT, READ, FUNCTION, RECURSIVE — and denies the rest, so `INSERT`, `PRAGMA`, and
  `ATTACH` fail whatever the query text looks like. A regex on SQL is a suggestion, an
  authorizer is a boundary.

## The question this component answers

Why is `DENIED` a success rather than a failure?

## Invariants

- This is the only package in `adii/` permitted to touch the filesystem, a database, a
  subprocess or the network.
- Every call returns a `ToolResult` with an accurate status. `DENIED` is a successful
  outcome — a boundary that cannot refuse is not a boundary.
- A tool never returns more than the caller asked for, and never silently widens scope.
  `run_sql`'s row cap is the harness's, not the model's to raise.
- Observations carry a stable evidence id, so a decision can cite something that happened.
- The trace is not kept here. The loop records each call and result; counters come from
  that trace, never from this package.

*Enforced by* `test_only_the_tool_layer_touches_the_outside_world`.

## How to test it

```bash
pytest 02_src/tests -k tool
```

`tests/unit/test_tools_executor.py` pins the statuses and the schema validation,
`tests/unit/test_tools_database.py` tries to get past the authorizer, and
`tests/integration/test_tools_replay_walkthrough.py` replays every call in the walkthrough
fixture through the real tools and expects the recorded statuses back.

## Related

Called by `investigator/`, speaks `contracts/`.
Six-question summary in [system_map.md](../../docs/system_map.md#tools).
