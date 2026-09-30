# The local extension pack: Qwen3-4B on the frozen contract

**Status: registered, not run.** Written before the freeze that carries it and before any run
of the pack. It is not decision E's evaluation, it changes none of decision E's packs, reports
or claims, and nothing in it is re-read under another freeze.

## The question

Does the contract decision E froze — the tool layer, the evidence gate, the authorizer, the
validator, the scorer, the bounds — hold when the subject is a small open-weight model served
on this machine and frozen by its weights? A test of the checks across subjects, not a test of
generalisation: the twelve benchmark cases only, the six held-out cases untouched.

## Why this subject

The four final packs held no incorrect model-proposed repair (10 proposals, all right), so
rejection is shown only by the scripted admissibility square. Qwen3-4B is the only local model
run through ADII. In its one run on these worlds (`film-local-qwen3-4b-929623`, before the
freeze) it made both corrective violations — a malformed tool call and a citation of an id it
never received — and was refused both times; in four of its five earlier submitted decisions,
on older incident families, it proposed a fix, none ever checked (they predate the validator).
It is the likeliest subject to bring a wrong fix to the authorizer and the validator. On these
revenue-drop worlds its one run answered NO_REPAIR, correctly: a reason, not a prediction.

## The terms — `local-qwen3-4b` in `02_src/adii/evaluation/lock.py`

| term | value |
|---|---|
| subject | `Qwen3-4B-Instruct-2507-4bit`, served as `default_model` at `http://127.0.0.1:8090/v1` |
| weights | sha256 `a483aa1606625203ae84261d9fcb87495caeddc8d8f66f58da33582244cf7c60` over every non-hidden file of the model's directory (`grid.weights_digest`); its `model.safetensors` is `2a73c6c2…`, as the directory's own manifest of 8 June 2026 says |
| incidents | the twelve benchmark cases; arm `full`; three repeats |
| bounds | decision E's: 20 turns, 4,096 completion tokens sent to the endpoint on every request, 30 tool calls, 600 s |
| sampling | temperature 0, the provider's rule for a model with no reasoning setting; no seed |
| judge | none: no model but the subject takes part, and nothing is paid for |

Without a judge one case goes unsettled, and it is not this pack's question: a fix with the
right disposition that the validator accepted, whose repair or root-cause id differs from the
key's reference. The scorer reports it *unresolved* — neither right nor wrong, never guessed.
Every wrong fix, every refusal, and every NO_REPAIR and ESCALATE is settled by code alone.

The weights are a pack term: the grid digests `--weights` and refuses a registered pack whose
terms differ from the frozen ones, so the pack runs on these bytes or not at all. The digest
names what was on disk, not what the server loaded; the server is started from that directory,
by the command below, and nothing else.

## How it runs

```bash
~/ai-models/.venv/bin/python -m mlx_lm server --model ~/ai-models/Qwen3-4B-Instruct-2507-4bit --port 8090
python -m adii.evaluation.grid --pack local-qwen3-4b --provider local \
    --model Qwen3-4B-Instruct-2507-4bit --endpoint http://127.0.0.1:8090/v1 \
    --served-as default_model --weights ~/ai-models/Qwen3-4B-Instruct-2507-4bit \
    --arms full --repeats 3 --max-tokens 4096
python 02_src/scripts/layer_counts.py --pack local-qwen3-4b
```

The server: mlx-lm 0.31.3 on MLX 0.31.2, Python 3.13.0. `test_the_freeze.py` holds the grid
command to the frozen terms, with no credential in the environment.

## What is counted

- **Right or not:** the grid's report against the frozen keys, the categories of decision E,
  with *unresolved* as above.
- **What the checks caught** (`02_src/scripts/layer_counts.py`): *protocol* and *evidence*
  refusals, which are corrective — the loop tells the model why and it may try again; and
  *entitlement* and *validity* refusals, which are terminal — nothing goes back. A refusal
  counts under the check that fired, as the record names it, and is never reclassified. A run
  with no corrective refusal is unaided. Beside them: fixes proposed, refused by a terminal
  check, and admitted by both authorities.
- **Determinism:** at temperature 0 the three repeats of each case are predicted to decide
  alike; the grid's report names every case whose repeats disagreed.

## What each outcome will mean — stated before any run

1. **A wrong fix is proposed and a check refuses it** (denied, rejected, or both): the first
   refusal of a model's own proposal on the live path, reported as that — a small local subject
   proposed an incorrect fix during a registered run, and the independent checks refused it.
   No other model is anywhere in that claim: the subject proposed it, deterministic code
   refused it, and the trace shows both.
2. **A wrong fix is admitted** (authorized and accepted where the key says it is wrong): a
   failure of the checks, reported first.
3. **No wrong fix is proposed:** the contract ran unchanged with a local 4B subject frozen by
   its weights. It says nothing about rejection, which stays with the square.
4. **The runs end mostly in bounds, malformed calls or refused citations:** where the contract
   strains when the subject changes, reported by layer, never as a verdict on the model alone.
5. **Repeats disagree:** the local stack is not deterministic at temperature 0; the cases are
   named and the determinism claim is withdrawn.

In no case does the pack say that Qwen matches the hosted models, or anything about the
held-out six.

## Before the report is regenerated

`02_src/scripts/evaluation_report.py` stamps the newest freeze on decision E's four packs. After
this freeze it must name each pack's freeze from the pack's own receipt, or the report would say
decision E ran on a freeze it did not.

## Order

1. Review this change; commit it.
2. `python -m adii.evaluation.lock --name freeze-<date>`; commit the freeze file; tag it.
3. The gate on Python 3.12, the version the submission was qualified on.
4. Start the server, run the grid, run the counts — once, and report whatever they say.
