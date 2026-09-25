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
| `packages.py` | one closed evidence bundle — a strict-JSON map beside a directory of exactly the declared files, read byte for byte — the shape the five evidence kinds share |
| `declared_schema_tools.py` | frozen operational meaning that SQLite types cannot express |
| `change_history_tools.py` | complete newest-first transform-change records parsed from one frozen artifact |
| `notice_tools.py` | bounded, read-only operational notices by declared logical identifier |
| `reconciliation_tools.py` | bounded raw-line windows over frozen reconciliation sources |
| `sql_tools.py` | the SQL handlers, and `build_sql_tools(database)` to wire the surface up |
| `transform_tools.py` | bounded, read-only transform source by declared logical identifier |
| `walkthrough_world.py` | the `demo-learning-001` world as SQL, so the fixture can be replayed live |
| `user_world.py` | an operator's CSV files as the same kind of world: one typed table per file, bounded, refused with the reason — pure text, the build script `in_memory` runs |

```python
from adii.contracts import ToolCall
from adii.tools import build_sql_tools, open_walkthrough_world

executor = build_sql_tools(open_walkthrough_world(), max_calls=20)
executor.advertised()            # the schemas the loop shows the model
result = executor.execute(ToolCall(call_id="c1", name="run_sql", arguments={
    "query": "SELECT order_date, count(*) FROM orders GROUP BY 1"}))
result.status                    # "OK" — and result.content["evidence_id"] is stable
```

When an incident has frozen transform source, the harness may add it without exposing a
path. `build_sql_tools(database, transform_sources={"stg_orders": source})` advertises
`get_transform(transform_id)` with the allowed logical IDs as its enum. The mapping is
copied when the executor is built. Every source must fit the harness's character bound in
full; construction fails instead of giving the investigator a partial transform.
`load_transform_sources(folder)` supplies that mapping from an incident package containing
`transform_map.json` and `transform_sources/`. The package is closed: missing, extra,
duplicate, nested, or symlinked sources are refused before a run, and so is a map that
binds one id twice (`packages.py` reads every map as strict JSON).

Operational notices are a separate primitive rather than a generic file reader.
`notice_map.json` plus `notice_sources/` is loaded by `load_notice_sources(folder)` and
advertised as `get_notice(notice_id)`. It has the same closed-inventory, exact-byte and
complete-observation rules, and returns `content` rather than a filename.

Transform change history is also separate. An optional incident package declares exactly
one logical history in `change_history_map.json`, backed by one exact UTF-8 artifact under
`change_history_sources/`. `get_change_history(history_id)` returns the complete parsed
collection in explicit `NEWEST_FIRST` order with the historical `date`, `file`, `ticket`
and `change` fields unchanged. Malformed rows, duplicate tickets, non-newest-first rows,
extra files and collections over the package bound fail before model execution; no result
is truncated and no filename is exposed through the tool input.

Reconciliation evidence uses `reconciliation_map.json` and
`reconciliation_sources/`. `read_reconciliation(reconciliation_id, offset=0, limit=200)`
returns raw lines in physical source order with total/returned counts and an explicit
continuation offset. A line ends at CR, LF or CRLF and at nothing else — a form feed or
U+2028 stays inside its line — and the same split serves the per-line bound at load time
and the window the model reads. It does not parse events or accept dates, fields, searches,
or paths.
The source is bounded in total bytes and per-line bytes before a run; each call is bounded
to 200 lines. A valid window beyond the end is successful empty evidence. An undeclared ID
is rejected, an unconfigured incident has no such tool, and a broken configured package
fails incident loading. Statements that some interval was never written remain ordinary
source lines rather than becoming a special status.

`get_schema(table)` may also expose a frozen operational declaration when an incident
provides `declared_schema_map.json` plus `declared_schema_sources/`. The map binds a SQLite
table name to one package-local JSON artifact carrying source identity, schema version,
field meaning, units and operational notes. Physical columns and DDL still come from
SQLite; no declaration is inferred. The optional package is closed, symlink-free and
validated before execution. Original source bytes and the parsed model-visible mapping
have separate receipt identities.

Every world is built in memory from a script, so no file path exists for a tool to accept.
To run over an operator's own CSV files, `user_world.world_from_files([(name, text), …])` gives the
build script for `in_memory`: one table per file named after it, every column typed from
its values (INTEGER, REAL, else TEXT; a blank cell is NULL) and never altered by the typing
— a leading zero, a non-ASCII numeral, an integer past 64 bits or a number past a float's
range keeps the column text — cells are stripped, a row with no content is skipped, a
header alone is an empty table; at most 8 files, 64 columns, 20,000 rows and 2,000,000
characters each; a file that is not a table is refused with the reason — a row of the
wrong width with its file line named, no header, a name SQLite reserves, text the CSV
reader cannot parse. The same door, the same
authorizer, the same caps; nothing downstream knows the world was brought.

**How a call is decided, in order.** Unknown tool → `DENIED`. Budget spent → `DENIED`.
Arguments fail the advertised schema → `REJECTED`, with every problem named. Then the
handler runs: it may raise `Denied` or `Rejected`; anything else it raises is `ERROR`.
An `OK` observation is stamped with `evidence_id`, a hash of the tool, its arguments and
what it returned — the same observation always gets the same id.

**Not built.** A candidate-repair sandbox: the investigator cannot run a repair it
proposes. Only the validator rebuilds, from frozen inputs, outside the investigator's reach.

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
