# The run inspector

**Read-only over the run archive.** Every run the runtime archives appears here: the trace,
the decision, the verdict, what it cost, and where the record came from.

```bash
python -m adii.runtime --incident demo-learning-001 --provider fake   # produce and archive one run
python -m adii.demo                                                     # → http://127.0.0.1:8000
```

No install. No dependencies. Standard library only.

## What it renders

Exactly one shape: `adii.run_record/v1`, defined in
[../reporting/record.py](../reporting/record.py). A record in any other shape gets a
contract-mismatch state, never a guess, and the page invents no field — if it is on screen,
it is in the record.

A run is drawn as a chain of custody. Each block hangs off a spine owned by whoever
asserted it, and says so in text; where the spine doubles and a handover is named,
authority has passed from the investigator to the validator. A run that ended without a
decision — a model failure, a bound, an infrastructure failure — is labelled in the loop's
own terms, and nothing about it is coloured as a verdict.

## The run list, filters and compare

The list in the rail grows with the archive: label, incident, model, outcome, cost and when
the record was written, newest first, each row carrying its disposition mark. Two filters
narrow it by incident and by model. Every row of the same incident as the run on screen
offers **compare**, which puts the two records side by side, each drawn by the same
renderer over its own record — that is how two models get tested against each other. A
comparison deep-links as `#label,label`.

## What it is not

- **Not a launcher.** Runs start from the command line. A page that can start a run can
  spend money and create a first exposure without a receipt, so this one cannot.
- **Not the implementation.** Nothing in `02_src/adii/` may import it, and a test enforces
  that. It shows what the runtime produced; it produces nothing.

## Two devices that carry the argument

**The three dispositions are peers.** One shape each — circle, square, hexagon — so the
disposition survives colour-blindness and print, and three hues generated at the same
lightness and chroma, so no one of them can shout. If ESCALATE were quieter than REPAIR,
the page would silently argue that abstaining is a degraded outcome, which is the opposite
of ADII's claim.

**Valence belongs only to whoever is entitled to it.** Dispositions are never coloured
right or wrong. Green and rust appear in exactly one place: the validator's ACCEPT and
REJECT, a correctness judgement made by an authority entitled to make it. How a run ended is
achromatic, because it is the loop's report and nobody's verdict.

These are rules, not taste: `02_src/tests/integration/test_demo_design_rules.py` fails the
build when a disposition colour is spent as a success colour, a verdict colour leaks out of
its scope, a token is used without being declared, or the script assembles HTML from
strings.

## API

```
GET /api/runs              one row per archived run, newest first; an unreadable record, or a
                           label reserved by a run that never finished, is listed with its
                           error, never hidden
GET /api/runs/{label}      the record, verbatim
```

Deep-link to a run with `#label`, or to a comparison with `#label,label`.

## Verify

```bash
python -m pytest 02_src/tests -k "record or inspector or design or walkthrough"
```
