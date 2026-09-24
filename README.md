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

**Investigate from the page** (paid; the key in `.env.local`, copied from `.env.example` —
it is read from there or the environment and appears in no receipt, trace, record or log):

```bash
python -m adii.demo 8000 --provider openai --model gpt-6-sol --reasoning-effort low \
    --max-tokens 4096 --max-cost-usd 0.50 --max-turns 20
```

Open **New investigation**: describe what looks wrong and attach CSV files, or pick one of
the three samples — the same alert over three different states of the data. Every run from
the page is the same `python -m adii.runtime` the evaluation scores, capped at $0.50.

## How it was evaluated

The evaluation is designed and registered before any final run
([final_plan.md](02_src/docs/final_plan.md), decision E), on synthetic incidents the team
generated and labelled ([canonical_world.py](02_src/adii/examples/canonical_world.py)):

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

## Repository map

```text
01_data/
  incidents/     the generated incident packages: worlds and evidence, never answers
  packs/         each evaluation pack's receipt and report
  runs/          the archive: one folder per run — receipt, trace, record
  demo/csv/      sample data to bring to the page as CSV
  walkthrough/   the teaching incident and its recorded run

02_src/
  adii/contracts/     the shared vocabulary every package speaks
  adii/investigator/  the agent loop: the model's messages, refused or accepted
  adii/tools/         the only door to the data: read-only, bounded, every result cited by id
  adii/validation/    the validator: rebuild from frozen inputs, check invariants
  adii/evaluation/    answer keys, scoring, the grid runner, the freeze
  adii/runtime/       one incident end to end: receipt, trace, record
  adii/provider/      the only code that speaks to a model: hard cost caps, no redirects
  adii/reporting/     the record, the ledger, the archive manifest
  adii/examples/      the incident generator and the walkthrough
  adii/demo/          the front door: a page over the archive, a starter of runs
  tests/              the suite: contracts, architecture boundaries, units, integration, browser
  scripts/            environment check, guard pass, syncs, the submission packager, the
                      admissibility square
  docs/               architecture, system map, the final plan and its decisions, glossary

03_assets/
  identity/      the logo and design system
  archive/       the first page, kept whole as provenance
  diagrams/  screenshots/
```

The architecture's three boundaries are tested, not asserted: the investigator reaches the
data only through the tool layer; the investigator never imports the validator or the
evaluation; the evaluation is a separate program
([architecture.md](02_src/docs/architecture.md),
`02_src/tests/architecture/test_boundaries.py`). Every check that refuses, bounds or
validates is registered in `02_src/scripts/guard_check.py` and demonstrated by removing it
and watching a test fail.

## Read more

| | |
|---|---|
| [system_map.md](02_src/docs/system_map.md) | what each package is, and what it must never do |
| [architecture.md](02_src/docs/architecture.md) | the boundaries, and why they are where they are |
| [final_plan.md](02_src/docs/final_plan.md) | the final phases and every decision, with its reason |
| [glossary.md](02_src/docs/glossary.md) | the words; validation and evaluation are not the same thing |
| [inherited/](02_src/docs/inherited/) | requirements learned from an earlier, private implementation; its code and results did not cross |

## Submission packaging

The deliverable is `ADII_Group05_Code_v1.zip`, one `ADII_Group05_Code_v1/` folder inside,
built from a tagged commit by `python 02_src/scripts/package_submission.py --ref <tag>
--packs <the final packs> --runs <the admissibility square's runs>` and qualified by extracting it on clean Windows and macOS machines.
It holds `01_data/`, `02_src/`, `03_assets/`, `README.md`, `requirements.txt`,
`pyproject.toml`, the final packs' run folders, the admissibility square's four runs, and `SUBMISSION.json` listing every file by
sha256. The team's working files stay in GitHub and out of the ZIP (`export-ignore` in
`.gitattributes`): `.github/`, `.claude/`, `CLAUDE.md`, `AGENTS.md`, `TEAM.md`.
