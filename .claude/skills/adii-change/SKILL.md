---
name: adii-change
description: Use when making ANY code change in the ADII team repository — adding a tool, extending the investigator loop, writing a validator, building a report, or touching contracts. Loads the architectural boundaries, the required order of work, and the checks a change must pass before it can be called done.
---

# Making a change in ADII

## Before writing code

Read, in this order — do not skip because the task looks small:

1. `02_src/docs/architecture.md`
2. `02_src/adii/contracts/core.py`
3. `02_src/adii/<the package you are changing>/README.md`

Then state, in one sentence each, **before implementing**:

- which system capability this change touches (agent-loop / tools / state / evidence /
  decision / validation / evaluation / telemetry / integration) — a change may touch several
- which contract objects cross which boundary
- what the failure modes are

If you cannot answer those, you do not yet understand the change. Ask, don't guess.

## The order of work

1. **Approach first, in prose.** Get it agreed before any code exists.
2. **One small unit.** A function or a class, not a subsystem. Something a teammate can
   read in one sitting.
3. **A test that would fail without the change.** Write it yourself where you can.
4. **Be able to defend it in review** without re-reading it.

A small change its author can explain beats a large one they cannot.

## Boundaries you must not cross

| Rule | Enforced by |
|---|---|
| No `open()`, `sqlite3`, `subprocess`, or network outside `02_src/adii/tools/` | `02_src/tests/architecture/test_boundaries.py` |
| The investigator never imports `validation/` or `evaluation/` | same |
| Nothing imports a private repository (`adii_env`, `adii_eval`, the reference impl) | same |
| `contracts/` imports nothing but the standard library | same |
| Contract changes need cross-boundary human review | `CODEOWNERS` + PR template |

When one of these fails, the error message states the rule. **Relaxing the test is
essentially never the fix** — if the boundary genuinely needs to move, that is a human
architectural decision, not a test edit.

## Task-specific guidance

**Adding a tool (`tools`):** the tool returns a `ToolResult` with an accurate `status`.
`OK` / `DENIED` (refused) / `REJECTED` (the model's arguments were wrong — it may retry) /
`ERROR` (our bug). Conflating `REJECTED` with `ERROR` makes the model look worse than it
is and corrupts the evaluation. Bound every result — row caps, line windows. Never accept
a filesystem path as an argument.

**Extending the loop (`agent-loop`):** emit `ToolCall`, consume `ToolResult`. A `DENIED` or
`REJECTED` result is information to feed back, not an exception. The loop must terminate:
turn budget, tool-call budget, and a terminal action. A `REPAIR` decision requires a
`repair_id` **and** a patch.

**Validation (`validation`):** rebuild from frozen inputs. Never consult the agent's own
rehearsal result — that is a hypothesis, and treating it as a verdict means measuring
nothing.

**Reporting (`telemetry`):** counters come from the trace, never self-reported. The report
must show a false repair and an unnecessary escalation as legibly as a success. Records
are strict JSON — `NaN` and `Infinity` are not JSON.

## Done means

```bash
python -m ruff check 02_src
python -m pytest
```

Both green on your machine, with the syncs and the guard pass for every track touched, and
the human author can answer the five
questions in the PR template.
