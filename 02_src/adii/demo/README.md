# ADII — demonstration layer

**An executable explanation, not an implementation.**

```bash
python -m adii.demo                      # → http://127.0.0.1:8000
```

No install. No dependencies. Standard library only.

## Two layers

| Layer | Shows | Density |
|---|---|---|
| **`/`** | what ADII does and why the boundaries exist | nine chapters, one idea each. No identifiers, no hashes, no jargon. |
| **`/inspector.html`** | one run in full | trace, citations, tool arguments, validation detail, evaluation, provenance |

Same fixtures underneath, two densities. `/` is the front door; the inspector is a link at
the end.

## What this is

Five complete ADII runs, rendered by one interface, so the architecture can be *seen*
before it is built. It exists to make four ideas impossible to miss:

1. Investigation produces a **trace**
2. Claims are tied to **evidence**
3. **REPAIR / NO_REPAIR / ESCALATE** are three equally legitimate outcomes
4. The investigator and the validator are **separate authorities**

If someone understands those four after five minutes of clicking, it has done its job.

## What this is not

- **Not the implementation.** No model, no SQL execution, no agent loop, no evaluator. The
  backend reads JSON from `fixtures/` and serves it. That is the entire logic.
- **Not a codebase to inherit.** Nothing in `02_src/adii/` may import from here, and a test
  enforces that. The team builds the real components; this only shows what they must
  eventually produce.
- **Not a product.** No accounts, no settings, no notifications, no chat. Those would
  communicate the wrong thing about what ADII is.

## The runs, in teaching order

| Run | Teaches |
|---|---|
| **duplicate-accepted** — REPAIR → ACCEPT | the whole idea, on the most obvious possible fault: the same batch was delivered twice. Count each order once. |
| **repair-rejected** — REPAIR → REJECT | *the same incident*, a different fix. ADII's own rehearsal passed; the independent check still said no, because only 11 of 26 orders were duplicated. |
| **no-repair** — NO_REPAIR | doing nothing is a *result*. Fixing this data would have created an error. |
| **escalate** — ESCALATE | abstention is a completed run. No warning triangle, no resume button, same visual weight as the other two. |
| **repair-accepted** — REPAIR → ACCEPT | a subtler fault for the inspector: the vendor changed cents to dollars and the pipeline still divides by 100. |

The first two are deliberately the *same incident*. Showing one alert with two candidate
repairs — one accepted, one rejected — teaches the validator boundary better than any
paragraph about authority separation, and it does it before the words are introduced.

## Fixture provenance

These five runs are drawn from the **evaluation** catalogue, not from a purpose-built demo
world. They satisfy the front-door invariants in
[DATA_WORLD_v0.md](../../docs/DATA_WORLD_v0.md) — every disposition is inferable from
the displayed evidence, and every REPAIR shows what changed and what was verified — but the
canonical demo world specified there does not exist yet. When B builds it, these fixtures
should be regenerated from it rather than kept.

## Two design decisions that carry the argument

**The three dispositions are peers.** Gold, teal, iris — different hues, same weight, no
ranking. If ESCALATE were amber next to a green REPAIR, the interface would silently argue
that abstaining is a degraded outcome, which is precisely the opposite of ADII's claim.

**Valence belongs only to whoever is entitled to it.** The three dispositions are never
coloured right or wrong — a run that escalates has not done anything worse than a run that
repairs. Green and rust appear in exactly two places: the validator's ACCEPT/REJECT, and
the Evaluation view. Both are correctness judgements made by an authority entitled to make
them. The Evaluation tab says so in as many words: *none of this was available to the
investigator.*

## Showing it to the team

Say this, then open `/` and let them click:

> Imagine revenue suddenly doubles. We don't know whether the business really doubled or
> the data is wrong. ADII is an AI investigator: instead of guessing from the alert, it can
> inspect the database, the schema, the logs, and the transformation code. If the data is
> broken it says REPAIR and proposes a fix. If the data is correct it says NO_REPAIR. If
> the available information can't safely tell us which is true, it says ESCALATE instead of
> guessing. And when it proposes a repair, a separate validator checks it — the AI doesn't
> approve its own work. That's the entire project.

The architecture diagram is chapter 8, not chapter 1. It lands because they have already
watched the thing it describes.

## Whether it works

Open it cold — no spoken introduction, not even the script above. Then answer:

| Question | Chapter responsible |
|---|---|
| 1. What problem does ADII solve? | 1 |
| 2. What are the three possible outcomes? | 1 |
| 3. Why isn't ESCALATE a failure? | 6 |
| 4. Why is there a separate validator? | 3–4 |
| 5. What does the agent actually do during an investigation? | 7 |

Use the answers diagnostically, not as a pass mark. One miss is reading speed. The signal
is repetition:

> If several fresh viewers fail the *same* question, simplify the chapter responsible.
> Do not add explanation somewhere else.

Two specific failures are worth watching for, because each names a chapter that did not do
its job: *"ESCALATE means it crashed"* (chapter 6), and *"the candidate test passed, so the
repair was accepted"* (chapters 3–4).

A cold run tells you more than another round of design refinement.

## API

```
GET /api/runs                      the four runs
GET /api/runs/{slug}               one complete run
GET /api/runs/{slug}/trace         just the trace
GET /api/runs/{slug}/validation    just the verdict
```

Schema is `contracts/demo/v0` — see [CONTRACT.md](CONTRACT.md). It demonstrates
information flow and is **not frozen**.
