# Contracts — the shared vocabulary

**Purpose.** Eight types every other package speaks: `Disposition`, `IncidentContext`,
`ToolCall`, `ToolResult`, `TraceEvent`, `InvestigationDecision`, `ValidationResult`,
`InvestigationRun`. Read `core.py` before writing anything anywhere else in this
repository — code that invents its own shapes will be plausible, well-named, and
incompatible with everyone else's.

Six-question summary in [system_map.md](../../docs/system_map.md#contracts).

## Invariants

- Standard library only. No third-party import, and no import of another `adii` package.
  A dependency here becomes everybody's dependency.
- Every type is a frozen dataclass or an enum. Contracts are values, not objects with
  behaviour.
- A change here is a change to every other package at once, so it takes the whole team on
  the review.

## How to test it

```bash
pytest 02_src/tests/contract
```

## Related

Everything imports this. Nothing here imports anything.
