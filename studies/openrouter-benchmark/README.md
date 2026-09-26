# OpenRouter benchmark — an exploratory study

A comparison run by a teammate before the final evaluation was registered, kept here so it can
be reproduced and cited by its commit. **It is not ADII's registered evaluation** (final plan,
decision E); its numbers are never blended with the final packs' and are reported, if at all,
as this study, with its own method and caveats.

## What it compares

On ten incidents authored for it (`case_specimens.py`, each with a surface reading that is
wrong and evidence one or two steps deeper that contradicts it):

| System | What it sees |
|---|---|
| gpt-4o-mini | the alert only: no tools, no data |
| claude-sonnet-5 | the alert only: no tools, no data |
| claude-sonnet-5 with ADII | ADII's own runtime (`python -m adii.runtime`), via OpenRouter: the real loop, tool layer, authorizer and validator |

Six metrics, per run: accuracy (the decision against the case's authored answer), faithfulness,
boundary compliance, tool precision, trajectory efficiency (these four judged by gpt-4o, anchored
by facts from the trace), and cost efficiency (computed).

## What it is not

- **Not decision E's evaluation:** different models, different cases, different metrics, and not
  registered before it ran.
- **Its answers are authored by the same team** that wrote the cases (`case_specimens.py`), not by
  an independent key-holder.
- **One of the two baselines changes the model as well as the tools** (gpt-4o-mini), so a
  difference against it cannot be attributed to ADII alone.
- **Its results are not in this repository.** They sit beside it on the machine that ran them
  (`../adii_case_specimens_data/`, `../benchmark_results_v2.json`). A number from this study is
  quoted only with the run records it came from.

`run_evaluation.py` and `run_evaluation_specimens.py` drive a custom tool-calling loop over
ADII's tool layer, not ADII's runtime, and say so in their own docstrings.

## Running it

It needs the `openai` Python SDK, which ADII itself does not depend on, so it runs in its own
environment, never ADII's:

```bash
python3.12 -m venv .venv-study && source .venv-study/bin/activate
pip install -r ../../requirements.txt "openai>=1.30"
python build_benchmark_incidents.py     # the ten incidents, beside the repository
python adii_benchmark_v2.py --offline-judge
```

Keys go in the environment or the repository's git-ignored `.env.local`
(`OPENAI_API_KEY` for the judge and gpt-4o-mini, `OPENROUTER_API_KEY` for Claude), never in a
file here.

## What it contributed to ADII

Two changes the study needed, reviewed and kept in the product: the provider hands a reply
with no text to the loop as an invalid envelope to reject and ask again, instead of ending the
run (`provider/openai_compatible.py`); and a price row for `anthropic/claude-sonnet-5`
(`reporting/ledger.py`), so Claude can be run through ADII's paid path with its hard cap.
