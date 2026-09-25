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

## What is built (M6, 20 September; generalised 23 September, final plan 1.5)

A mechanism, not a fixture. An incident is rebuildable when it has an oracle beside the
validator, `oracles/<incident_id>.json` (`adii.validation_oracle/v1`), the validator's own
authority and a closed shape: the **pipeline** its world is derived by — each derived table
from a transform in the incident's bundle, which a patch may replace, or from the pipeline's
own SQL, which no patch reaches — and the **invariants** a valid repaired world satisfies,
each two queries that must agree row for row, one over the rebuilt world and one over the
frozen world. The oracle states what must hold, never a patch, a repair id or a disposition;
a document carrying anything else is refused.

`patching.py` rebuilds a brand-new `ReadOnlyDatabase` from the incident's frozen world and
its pipeline with the patch applied — the patch is what the protocol has a model send, a
transform's path mapped to the file's new contents — under a build budget, never the
investigator's own connection; a patch the world cannot apply is REJECT by the check named
`rebuild`. `checks.py` is the one check, an invariant compared row for row, so a world with
the right count and the wrong rows fails (C1c). `validator.py` gives
`Validator.validate(context, decision) -> ValidationResult`, the shape `runtime/run.py`
requires, with no parameter a rehearsal claim could arrive through. The frozen inputs are the
incident's own: the walkthrough's world and bundle, or `01_data/incidents/<id>/` once the
development catalogue lands (phase 2); an incident with no oracle raises `UnknownIncident`,
which the live path reads as NOT_CHECKABLE. Today one oracle exists, the walkthrough's;
`tests/integration/test_validation_is_a_mechanism.py` proves the four outcomes of
DECISIVE_TESTS D3 on an incident the validator has never seen, through the real runtime.

Whether a target is *permitted* is authorization, the runtime's own fact (`runtime/run.py`,
`authorize`, row 4), established for every REPAIR beside this verdict and never through it:
the validator is handed the incident without its permitted paths, and a PASS here never
implies permission.

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
`evaluation/`: validation asks whether a repair works, evaluation whether the call was right.
