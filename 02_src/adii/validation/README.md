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

## What is built (M6, merged 20 September)

`patching.py` rebuilds a brand-new `ReadOnlyDatabase` with the candidate transform run as
the staging step and the mart derived from it, under a build budget — the patch is the
permitted path mapped to the file's new contents, exactly as the protocol has a model send
it, so the walkthrough's own committed repair is the accepted case — never
the investigator's own connection; `checks.py` runs three atomic checks over the rebuild;
`validator.py` gives `Validator.validate(context, decision) -> ValidationResult`, the shape
`runtime/run.py` requires, with no parameter through which a rehearsal claim could arrive.
One frozen world so far, `demo-learning-001`; `_WORLD_BUILDERS` grows one entry per
incident the validator can rebuild. `runtime/live.py` does not call it yet — a live REPAIR
still reads "not checked" — and wiring it is the next integration step (build plan M7).
Whether a target is *permitted* is authorization, a separate question answered before
validation; a PASS here never implies permission.

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
