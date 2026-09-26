# ADII — Is it broken?

A number in your data looks wrong. ADII investigates it and answers one of three things:

```text
Fix it        REPAIR      the number is wrong, here is why, and here is the change that fixes it
Leave it      NO_REPAIR   the number is right: the world changed, and nothing should be touched
Escalate it   ESCALATE    the evidence here cannot settle it; someone with more access should decide
```

**The AI that proposes a fix can't approve it.** An investigator model looks at the data
only through a read-only tool layer and submits a decision. A proposed change must then pass
two authorities it has no part in: an **authorizer** (is this change permitted here?) and an
independent **validator**, which rebuilds the data from a frozen copy with the change applied
and checks it against the data's own invariants. Every run writes a receipt before anything
is spent, a trace as it happens, and a record at the end; the page shows only what the
record says.

**What this is, precisely.** ADII is a complete, locally running reference implementation.
We engineered and qualified the authority boundaries as if they mattered in production; we
have not deployed it into a production customer environment. It claims no high availability,
single sign-on, managed secrets, enterprise connectors, operations or data-residency story.

## Quick start

Python **3.12**, Windows or macOS. No Docker, no Make, no shell scripts: everything runs as
`python -m …`.

```bash
python3.12 -m venv .venv            # Windows:  py -3.12 -m venv .venv
source .venv/bin/activate           # Windows:  .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python 02_src/scripts/check_env.py  # prints Ready.
pytest                              # the whole suite
```

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

**See one investigation, free.** The scripted path replays a recorded investigation through
the real runtime, tools and validator — no model, no key, no cost:

```bash
python -m adii.runtime --incident demo-learning-001 --provider scripted
python -m adii.demo                                  # → http://127.0.0.1:8000, read-only
python -m adii.examples.walkthrough --step           # the architecture, one stage at a time
```

**Investigate from the page** (paid). Put your OpenAI key in the environment as
`OPENAI_API_KEY`, or in a file named `.env.local` at the root holding the one line
`OPENAI_API_KEY=<your key>`. It is read from there and appears in no receipt, trace, record
or log:

```bash
python -m adii.demo 8000 --provider openai --model gpt-6-sol --reasoning-effort low \
    --max-tokens 4096 --max-cost-usd 0.50 --max-turns 20
```

Open **New investigation**: describe what looks wrong and attach CSV files, or pick one of
the three samples — the same alert over three different states of the data. Every run from
the page is the same `python -m adii.runtime` the evaluation scores, capped at $0.50.

## How it was evaluated

The evaluation is designed and registered before any final run, on synthetic incidents the
team generated and labelled ([canonical_world.py](02_src/adii/examples/canonical_world.py)):

| set | cases | used for |
|---|---|---|
| benchmark | 12 — four companies, two per answer and per explicit/implicit tier | three investigators: gpt-6-sol, gpt-6-luna, gpt-4.1 |
| held-out | 6 — two companies no model had run | the declared configuration, gpt-6-sol, once |
| controls | the 12 benchmark cases | the same model shown only the alert, and a floor that always escalates |

Three questions are answered apart: does the architecture hold across investigators; do
the tools add information beyond the alert; and what the declared system does on cases
nobody tuned on — six cases, a demonstration and not a statistic. The evaluated system is
frozen by digest before the final runs (`python -m adii.evaluation.lock`); nothing in it
changes because of a result. The results will be in `02_src/docs/evaluation_report.md`,
written from the run records once the final packs have run.

## What is in this folder

```text
01_data/
  incidents/     the generated incident packages: data and evidence, never answers
  packs/         each final evaluation pack's receipt and report
  runs/          the archive: one folder per run — receipt, trace, record
  demo/csv/      sample data to bring to the page as CSV
  walkthrough/   the teaching incident and its recorded run

02_src/
  adii/          the system — one package per part (see docs/architecture.md)
  tests/         the suite: contracts, architecture boundaries, units, integration, browser
  scripts/       check_env.py (is this machine ready?), admissibility_square.py (the four
                 archived runs that show both authorities at work), evaluation_report.py
                 (the evaluation report, from the packs' records)
  docs/          architecture.md, and the evaluation report

03_assets/       the logo, diagrams and screenshots
```

The architecture's boundaries are tested, not asserted: the investigator reaches the data
only through the tool layer, never imports the validator or the evaluation, and the
evaluation is a separate program (`02_src/tests/architecture/test_boundaries.py`).

## Submitted with this folder

Four files, uploaded side by side: this code ZIP; `ADII_Group05_Presentation_v1.pptx`, the
presentation; `ADII_Group05_Final_Report_v1.docx`, the final project report; and
`ADII_Group05_Video_v1.mp4`, a short demonstration: the page answering the three samples,
input and output.

## Read more

| | |
|---|---|
| [architecture.md](02_src/docs/architecture.md) | the system in one diagram, its four boundaries, one run end to end |
| `02_src/docs/evaluation_report.md` | the results, written from the run records |
| `02_src/adii/*/README.md` | what each package is for |
