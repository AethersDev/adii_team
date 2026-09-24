# Evaluation: scoring and answer keys

Whether the answer was right, and how we know that independently of the thing that
answered.

**You own:** the incidents' correct answers, the scoring rules, the baseline arms, and the
construction that keeps all of it unreachable from the investigator.

**You do not own:** the investigation (A), the tool surface (B). And you do not adopt an
answer key from anywhere else — we hold our own, or we are not measuring anything.

## The separation that matters

Contestant and judge are different programs with different authority. The agent must never
be able to reach the answer key, the oracle, or the scoring code — not by convention, by
construction. `02_src/tests/architecture/` enforces the import direction; the rest is your design.

## Two boundaries, not one — and this package is only the first

**This package is an authority boundary inside the team implementation. It is not a
confidentiality boundary.** An import rule guards against accidental leakage; it is not
secrecy when the investigator and an answer key share a checkout. So:

```text
may live here                                   never enters this repository
─────────────────────────────────────────       ─────────────────────────────────────────
the contracts and the deterministic scorer      the final blind worlds
the freezing, versioning and grounding          the final blind answer keys
  machinery for keys                            hidden authority state
the development authority                       the final evaluator configuration
PUBLIC / DEVELOPMENT answer keys only
development scoring fixtures, under 02_src/tests/
```

A key that is meant to become blind truth does not move in here to make CI pass; the
machinery moves, and a development key stands in for it. `test_answer_keys_stay_out`
confines evaluation-shaped data to this package — that is the first boundary, enforced.
The second is custodial: [DATA_WORLD_v0.md](../../docs/DATA_WORLD_v0.md) names blind
incidents custodian-controlled, and
[development_catalog.md](../../docs/development_catalog.md) records how the private
reserve is committed before any development case is exposed. Nothing here can enforce
the second boundary, which is exactly why it has to be written down.

Note this is a *different* boundary from validation, which you also own. Validation asks
**does this repair work**. Scoring asks **was this the right call at all** — including for
the two dispositions that propose no repair, where there is nothing to validate.

## The staged build

Each stage is useful on its own, and each is a real measurement before the next exists.

1. **Disposition scoring.** Fixture decision in, `correct` / `incorrect` out. Write down
   what correct means for each disposition first. `ESCALATE` when the evidence really is
   insufficient is a **success**, not a dodge — that distinction is most of the research
   question, and a scorer that treats abstention as failure measures the wrong thing.
2. **Repair verdicts.** Wire in the independent validator. `REPAIR` is only correct if the
   repair is *also* accepted; a right diagnosis with a wrong fix is not a pass.
3. **Baseline arms.** Same incidents, weaker systems: always-escalate (no model at all),
   and alert-only (same model, same prompt, **zero tools**). Without these, a score is a
   number with nothing to attribute it to. See
   [../../../02_src/docs/inherited/CONTROLS.md](../../../02_src/docs/inherited/CONTROLS.md) — it also
   explains why a perfect score is a problem rather than a result.

## Two rules to build in before there is anything to protect

Both are cheap now and impossible to retrofit once a result exists.

- **An answer key is frozen by hash and never edited.** A correction is a *new file*.
  Evidence scored against a key means nothing if the key can move afterwards.
- **Scoring semantics are pre-registered.** Deciding what counts as success after seeing
  results is how a real finding becomes an unfalsifiable one.

## The question this component answers

Who owns the correct answer, when is it consulted, and why would exposing it to the agent
invalidate everything we report?

## Invariants

- Never appears in agent context, and is never importable from `investigator/`. An
  investigator that can reach the answer key has not investigated anything.
- Scores a completed run against hidden truth, offline — not on the path an investigation
  takes.
- Answers whether the investigator was *right*. Whether a proposed action is *acceptable*
  is `validation/`'s question, and they are not the same question.

*Enforced by* `test_the_investigator_cannot_reach_the_judge`.

## Capacity: the scale ladder

```bash
python -m adii.evaluation.scale                          # 10k, 100k and 1M orders
python -m adii.evaluation.scale --rows 10000 5000000     # any sizes, smallest first
```

Decision quality is measured on incidents; capacity on rows. The ladder regenerates the
canonical world's first family at each size — the same causal facts and ids, so the same
frozen keys — investigates its three worlds through the real runtime with the ideal
investigator in `scale.py`, puts the correct repair and the scale-to-the-total fake through
the real validator, scores every decision, and reports build, investigation and validation
time and peak memory. What grows is only the data behind the tools; the model's evidence
stays bounded, because every tool result is. The suite runs its smallest rung, 30,000 orders.

## Scoring an archived run

The development set's labels are in `catalogue/`: for each generated incident under
`01_data/incidents/`, its answer key (frozen, `.sha256` beside it) and its grounding key,
authored by the team from the generated worlds and frozen before any run.

```bash
python -m adii.evaluation --run <label> --key 02_src/adii/evaluation/fixtures/<incident>.answer.json
```

The record the runtime wrote is read through the runtime's own reader and scored as it
is — every field `build_evaluation_report` reads is in `RunRecord.to_json()` under the
same name, so there is no adapter. The key must be frozen (`freeze.py`); it must name the
run's incident; a REPAIR nobody checked (`checks_run` empty — the runtime's placeholder
until a validator exists) is refused rather than filed as a rejection; and the report
lands once, as `evaluation_report.json` beside the record, in the archive's `evaluation`
retention class. Each refusal is a registered guard. Beside the category the report carries
`runtime_validation` (what the runtime's validator did) and `grounding` (what the decision
cites, from `evidence_refs`; `grounded` means at least one observation the run minted is
cited) — dimensions, never inputs to the category: a correct disposition citing nothing
scores as its category and reads as ungrounded. Whether the cited observations are the
decisive ones is a grounding key's question (`grounding.py`).
With `--grounding-key PATH`, a key bound by digest to the very answer key given, the
report's `grounding` also carries `decisive`: `observed` (every required call was made and
answered OK; a refused call observes nothing), `cited` (the decision names one of each
required call's evidence ids) and `missing`, read from the archived trace, beside the
category and never inside it.

## How to test it

```bash
pytest 02_src/tests -k "evaluation or scoring"
```

## Related

Consumes `contracts/`. Consumed by offline analysis only.
Six-question summary in [system_map.md](../../docs/system_map.md#evaluation).
