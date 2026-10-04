# ADII — Is it broken?

**The paper:** *Permission Is Not Justification: Evaluating the Decision to Act in
Data-Incident Agents* — [PDF](https://github.com/AethersDev/adii_team/blob/main/paper/permission-is-not-justification.pdf) ·
[source](https://github.com/AethersDev/adii_team/blob/main/paper/paper.md) · the exact repository state it reports on is the tag
[`paper-v1`](https://github.com/AethersDev/adii_team/tree/paper-v1).

**In one sentence:** a clean safety record can hide a bad agent, so the evidence for giving an
agent more authority has to score its decisions against independent ground truth, including
its decisions not to act.

## The evidence, first

| What we found | The number | Where to check it |
|---|---|---|
| With its tools, gpt-6-sol tells apart three cases that share one alert | right on 12/12 benchmark and 6/6 held-out cases | [evaluation report, claims 1 and 3](https://github.com/AethersDev/adii_team/blob/main/02_src/docs/evaluation_report.md#claim-1--the-architecture-across-three-investigators) |
| Shown only the alert, it does no better than a rule that always escalates | 4/12, the always-escalate floor | [claim 2](https://github.com/AethersDev/adii_team/blob/main/02_src/docs/evaluation_report.md#claim-2--do-the-tools-add-information-beyond-the-alert) |
| That rule is wrong on 8 of 12 cases, with a spotless admission record: it never proposes anything to refuse | 8/12 wrong; nothing admitted, nothing refused | [claim 2](https://github.com/AethersDev/adii_team/blob/main/02_src/docs/evaluation_report.md#claim-2--do-the-tools-add-information-beyond-the-alert) |
| The gates refused every wrong repair a model proposed | Qwen3-4B: 27 of 27 rejected | [local extension report](https://github.com/AethersDev/adii_team/blob/main/01_data/packs/local-qwen3-4b.report.md) |
| So its record, zero wrong decisions admitted, is the same as that of gpt-6-sol, right on every case | 0 wrong admitted for both | [paper, §7.6](https://github.com/AethersDev/adii_team/blob/main/paper/paper.md#76-a-clean-admission-record-does-not-establish-entitlement) |
| Wrong decisions not to act never reach a gate | the hosted models' 7 errors: all NO_REPAIR or ESCALATE | [every run that was not right](https://github.com/AethersDev/adii_team/blob/main/02_src/docs/evaluation_report.md#every-run-that-was-not-right-by-name) |
| The validator accepts a patch that corrupts every amount but keeps the checked totals | admitted in 18 of 18 worlds | [the test that holds it](https://github.com/AethersDev/adii_team/blob/main/02_src/tests/integration/test_incident_packages_are_ready.py#L183) |

**Check it yourself:** a few minutes, no API key, nothing spent.

```bash
git clone https://github.com/AethersDev/adii_team.git && cd adii_team
python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python 02_src/scripts/paper_claims.py   # recomputes every result in the paper from the published runs
python -m pytest                        # the full test suite
```

The frozen evidence is [`ADII_final_packs.zip`](https://github.com/AethersDev/adii_team/blob/main/ADII_final_packs.zip) (66 hosted runs,
`freeze-2026-09-26`) and [`ADII_local_qwen_pack.zip`](https://github.com/AethersDev/adii_team/blob/main/ADII_local_qwen_pack.zip) (36 local runs,
`freeze-2026-09-30`), both checked entry by entry against
[`01_data/runs/MANIFEST.json`](https://github.com/AethersDev/adii_team/blob/main/01_data/runs/MANIFEST.json) by the script above.
`ADII_final_packs.zip` was written on Windows and names its entries with backslashes; it is kept
byte for byte because the paper cites it, and the script reads it on any system. To report a
result that disagrees with the evidence, [open an issue](https://github.com/AethersDev/adii_team/issues/new/choose)
with the form provided.

## What ADII is

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
| held-out | 6 — two further companies; none of the six ran before its final pack | the declared configuration, gpt-6-sol, once |
| controls | the 12 benchmark cases | the same model shown only the alert, and a floor that always escalates |

Three questions are answered apart: does the architecture hold across investigators; do
the tools add information beyond the alert; and what the declared system does on cases
nobody tuned on — six cases, a demonstration and not a statistic. The evaluated system is
frozen by digest before the final runs (`python -m adii.evaluation.lock`); nothing in it
changes because of a result. The results are in `02_src/docs/evaluation_report.md`, written
from the run records. A registered extension ran a small local model, Qwen3-4B, on the same
twelve cases (`02_src/docs/qwen_local_extension.md`); its report is
`01_data/packs/local-qwen3-4b.report.md`.

## What is in this folder

```text
paper/           the manuscript's source, a PDF for reading, and the LaTeX build
ADII_final_packs.zip, ADII_local_qwen_pack.zip
                 the frozen run archives the paper's results are computed from

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

## Read more

| | |
|---|---|
| [architecture.md](02_src/docs/architecture.md) | the system in one diagram, its four boundaries, one run end to end |
| `02_src/docs/evaluation_report.md` | the results, written from the run records |
| `paper/paper.md` | the paper; `02_src/scripts/paper_claims.py` holds it to the evidence |
| `02_src/adii/*/README.md` | what each package is for |

## License

Copyright 2026 Malek Alhazmi, Joorie Alsakran, Ibrahem Altowalah and Nasser Alzaid.

| | |
|---|---|
| Everything not listed below: the code, tests, scripts and docs | [AGPL-3.0-only](LICENSE) |
| The data: `01_data/`; the answer and grounding keys in `02_src/adii/evaluation/catalogue/` and `02_src/adii/evaluation/fixtures/`; the run archives `ADII_final_packs.zip` and `ADII_local_qwen_pack.zip`; and `03_assets/`, apart from the logos | [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt) |
| The fonts in `02_src/adii/demo/web/fonts/` | the SIL Open Font License 1.1, [as their authors released them](02_src/adii/demo/web/fonts/OFL.txt) |
| The ADII name and logos, in `03_assets/identity/assets/logo/` and `02_src/adii/demo/web/logo/` | not licensed: neither license above grants any right to them |
| The manuscript in `paper/` | © the authors; not covered by the licenses above |

To use the code on terms other than the AGPL, contact the authors.
