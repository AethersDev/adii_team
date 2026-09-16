# The demo

Four minutes, one incident, one screen, one reveal. The machinery is shown only once it
answers a question the audience already has. Every line below the presenter is told to
say is true of the tree as of 17 September; the lines that would not be are in "What is
not said", with the honest form.

What it is called: **a bounded autonomous investigator for data incidents.** Not "a
multi-agent system", not "a root-cause agent", not "data quality" — those name pieces and
put the project in the wrong comparison class.

## Layer 1 — thirty seconds, for anyone

Open on the incident, not on ADII.

> Daily revenue fell 45% the morning a release went out. Product wants the release rolled
> back.
>
> A root-cause agent hands you a recommendation, and a prompt asking it to be careful.
> Here the caution is enforced, not requested — that is the difference you are about to
> watch. ADII starts one step earlier than "fix it". It asks: what actually happened —
> and are we justified in changing anything?

The three outcomes, on one line:

```text
The system that produces the number is broken   → REPAIR
The business really changed                     → NO_REPAIR
We cannot know safely yet                       → ESCALATE
```

Then the sentence everything hangs from, spoken once:

> ADII separates "I found something suspicious" from "I am justified in changing the
> system."

## Layer 2 — two minutes, ADII operating

Click **Investigate** on `revenue-after-deploy`. Narrate the screen, not the code.

| when the page shows | say |
|---|---|
| the first tool request | "Watch what it asks for. It can only look through a small set of tools, and every request is on the record — so afterwards you can tell whether it looked or guessed." |
| the answer (with its id) | "Everything it saw of the data was written down the moment it saw it, with an id, before it answered." |
| a rejected request *(only if one appears)* | "It asked for something it is not allowed to do, or asked wrongly, and was told no. That is on the record too." |
| the decision | "Notice it is allowed to say *do nothing*, or *I cannot justify a decision*. Those are outcomes, not failures." |
| the story | **Say the finding out loud.** If the run found it: "Two distributor contracts ended that week — 45% of revenue between them. The release only changed screen text. The drop is real. Rolling back would have destroyed correct data. That is NO_REPAIR." If the run did not find it, see "The risk", below. |

Nothing else is narrated in Layer 2. The validator's row is not on this incident's page
(a NO_REPAIR proposes nothing to check), and the evaluation's row is empty until Layer 3.

## Layer 3 — one minute, the reveal

The reveal is the finding: the instinct was rollback, and the evidence said no. Then one
question:

> How do we know it was right for the right reason?

Answer it on screen, not with a diagram:

1. Open the turn-by-turn. "Every query it made is here. It found the distributors, or it
   did not; you can see which. It cannot claim to have seen what is not in the record."
2. Say: "The judge is a different program — watch me run it." In the terminal:
   `python -m adii.evaluation --run <label> --key 02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json`
   Reload the run. "This key was written and frozen before the run. The investigator
   cannot reach it — a test fails if it ever could. Here is the score."
3. Close on the partner line:

> The hard problem in enterprise agents is not getting them to act. It is knowing when
> they are justified in acting.

If asked "so what is around the model?", the picture is in the presenter's pocket, not on
a slide:

```text
                INCIDENT
                   │
             INVESTIGATE        "What actually happened?"
                   │  evidence, recorded as it is seen
               DECIDE
       ┌───────────┼───────────┐
    REPAIR     NO_REPAIR    ESCALATE
       │           │           │
     CHECK         │           │      "Is this change allowed?"  (a slot: today it
       │           │           │       answers 'not checked' — the checker is next)
       └───────────┴───────────┘
                   │
               PRESERVE          "What did it see and do?"
                   │
               EVALUATE          "Was it right?"  (a different program, a key it cannot reach)
```

And the question every engineer on the panel asks first — *"so it is a 4B chat model
with function calling and a log?"* — gets a yes:

> Yes. The model is the cheapest part. The product is the list of things it is not
> allowed to do, and the record of what it did.

## What is not said, and why

| tempting line | why not | say instead |
|---|---|---|
| "its action is independently checked" | no validator exists (M6); every live REPAIR reads *not checked by a validator* | "a repair it proposes is not applied — today by anyone; the checker that would decide is the next thing built" |
| "it cannot invent evidence" | citations are not checked against minted ids yet (D-3) | "every request and answer is on the record; you can tell whether it looked" |
| "custody preserves exactly what the system saw" | the record holds every tool result, but `model_requested` records a message *count*: the prompt and tool schemas sent are not in the record (contract row 1) | "everything it saw of the data is in the record" |
| "scored against truth the investigator never saw" | the key is authored from the specimen's own world, which the investigator could have queried; what it cannot reach is the key file | "scored by a different program against a key it cannot reach" |
| "the archive has REPAIR and ESCALATE runs too" | the only such records are scripted specimen replays (`orders-missing-day-run-1`, `settlement-conflict-run-1`), labelled *not a model result* on the page; no model run has reached either | "the archive has authored specimens of the other two outcomes, labelled as such" |

Hashes, schema versions, event kinds, token counts, receipts, manifests, revisions,
endpoint and bounds stay under **Details for engineers**, the per-turn **Raw events**, and
in the archive. They are proof, not story. The model's name is on the page, and stays.

## The risk, decided now

No model run of `revenue-after-deploy` has yet queried the distributors table. The 16
September smoke runs reached NO_REPAIR by querying only the days after the deploy — right
for the wrong reason — and the same model has also archived a live REPAIR on this incident
(`revenue-after-deploy-qwen4b-1`): the rollback instinct itself, which the scorer then
refuses because no validator has checked it, so there is no evaluation row to show.

So the demo runs the mechanism live and does not depend on the live result:

- **Found it:** say the finding; Layer 3 as written.
- **NO_REPAIR, shallow:** "It decided correctly — and shallowly: it never looked at the
  distributors." Open the archived specimen run `revenue-after-deploy-run-1` (the page
  labels it scripted): "This is what the evidence shows when it is all looked at." Then
  Layer 3 with the live run; the score is real either way.
- **REPAIR:** "That is the rollback instinct, and it is exactly what ADII exists to
  question. The scorer refuses to grade it because no checker has run — the page says so."
  Then the specimen run for the finding.

Rehearse with the model that will be used. `green_line.md` is the current state; read it
the morning of.

## Running it

```bash
~/ai-models/.venv/bin/python -m mlx_lm server --model ~/ai-models/Qwen3-4B-Instruct-2507-4bit --port 8090
python -m adii.demo 8000 --endpoint http://127.0.0.1:8090/v1 --model Qwen3-4B-Instruct-2507-4bit --served-as default_model
```

Open http://127.0.0.1:8000, choose `revenue-after-deploy`, press Investigate. Rehearsed
runs took 6 s; the bound-hit run took 39 s; there is no wall-clock bound yet, so a stalled
model can hold the page for minutes (D-9). Then, for Layer 3:

```bash
python -m adii.evaluation --run <label> --key 02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json
```

and reload the run.
