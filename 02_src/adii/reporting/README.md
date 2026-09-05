# Telemetry: traces, artifacts, reports

Makes the agent understandable. If a behaviour is not in the trace, nobody can debug it,
and we cannot claim it.

**You own:** `TraceEvent`, run artifacts, reproducibility, the report, cost and latency
instrumentation, CI, and the environment.

## First build

`render_run()` is already here — it turns a run into something a human reads. Extend it.
Then the run-artifact format: what gets persisted so a run can be replayed months later.

## What to get right early

- **The report must be honest in both directions.** It has to show a false repair, an
  unnecessary escalation, and a rejected repair as legibly as a success. A report that
  only looks good when the agent was right is marketing.
- **Counters come from the trace.** `tool_calls` is counted, never self-reported — an
  agent must not be able to flatter its own efficiency.
- **Records are strict JSON or they are not records.** `NaN` and `Infinity` are not JSON;
  an archive a conforming parser rejects is not an archive.
- **Cost is nominal provider cost**, regardless of who pays the bill. A sponsored key does
  not make a run free.

## The question this component answers

If a behaviour is not in the trace, what can you prove about it?

## Invariants

- Counters come from the trace, never from a component's self-report. If a behaviour is
  not in the trace, nobody can prove it happened.
- A run artifact is complete enough to be read months later without the code that made it.
- Rendering never changes what happened; it only presents it.

## How to test it

```bash
pytest 02_src/tests -k report or pytest 02_src/tests/integration
```

## Related

Consumes `contracts/` and the trace produced by every other package.
Six-question summary in [system_map.md](../../docs/system_map.md#reporting).
