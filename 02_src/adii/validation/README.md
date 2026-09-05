# The validation boundary

The other authority. The one that actually decides whether a repair is real.

**You own:** rebuilding from frozen inputs, applying the candidate patch, returning
`ACCEPT` / `REJECT`.

**Not yours to trust:** the agent's rehearsal tool. That belongs to the tool layer, and
it proves nothing here.

## The whole point

The investigator can test its own patch and will tell you it passes. That is a
*hypothesis*. You rebuild independently and return the *verdict*. The agent never sees
how you reached it.

If validation used the agent's own sandbox, a repair could make the data agree with
itself and we would have measured nothing.

## First build

Take fixture decisions and produce `ValidationResult`s. Start structural — does it
rebuild, are row counts preserved — before anything semantic.

## The question this component answers

The agent's sandbox says its patch passes structural tests. Is the repair accepted?

## Invariants

- Rebuilds from frozen inputs. It never asks the investigator whether the repair worked,
  and never trusts a sandbox result the investigator reports about itself.
- It never reads evaluation answer keys.
- It is deterministic code, not part of the model's reasoning loop.
- `REJECT` is a normal, reachable outcome with machine-readable reasons.

## How to test it

```bash
pytest 02_src/tests -k validation
```

## Related

Runs after `investigator/` commits, reports through `reporting/`. Distinct from
`evaluation/` — see the glossary if that distinction is not yet sharp.
Six-question summary in [system_map.md](../../docs/system_map.md#validation).
