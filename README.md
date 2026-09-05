# Autonomous Data Incident Investigator (ADII)

ADII is an agentic AI system that investigates data incidents using controlled tools and
produces one structured decision:

```text
REPAIR        the defect is real, and here is the bounded intervention
NO_REPAIR     the world is legitimately like this; change nothing
ESCALATE      the decision is not this actor's to make, and here is why
```

Any repair it proposes is validated by a **separate authority** — the investigator never
grades its own work.

## Quick Start

Six steps. One Python version for everyone: **3.12**. No Docker, no Make, no shell
scripts — anything that matters runs as `python -m ...`, so it behaves identically on
Windows and macOS.

**1. Create the environment**

```bash
python3.12 -m venv .venv            # Windows:  py -3.12 -m venv .venv
source .venv/bin/activate           # Windows:  .\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

**2. Install requirements**

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**3. Configure the API key**

Not needed yet. The system currently runs with no model and no network; when the agent
loop lands, this step becomes `export ANTHROPIC_API_KEY=...` and `check_env.py` starts
checking for it.

**4. Run the environment check**

```bash
python 02_src/scripts/check_env.py
```

If it prints `Ready.`, your machine is done. Nobody needs to touch your laptop.

**5. Run the demo**

```bash
python -m adii.demo                 # → http://127.0.0.1:8000
```

Five complete runs — a repair accepted, a repair *rejected*, a sound pipeline left alone,
and an abstention — through one interface. It is an executable specification, not an
implementation: no model, no database, no agent. See
[02_src/adii/demo/README.md](02_src/adii/demo/README.md).

Then the same architecture in one command:

```bash
python -m adii.examples.walkthrough --step
```

**6. Run the tests**

```bash
pytest
```

Then read [02_src/docs/architecture.md](02_src/docs/architecture.md). Demo, walkthrough,
architecture — in that order.

## Everyday commands

```bash
pytest                                        # all tests
python -m ruff check 02_src                   # lint
python -m adii.examples.walkthrough --step    # the walkthrough, one stage at a time
python 02_src/scripts/check_env.py            # is my machine ready?
```

## Repository map

The top-level folders are the submission structure, used from day one so there is no
packaging migration at the deadline.

```text
01_data/                     data the system reads. Team-visible, never evaluation-only
  demo/world/                the operational world the whole team shares
  demo/fixtures/             the five recorded runs the demo serves
  walkthrough/               the teaching fixture

02_src/                      the system, its tests, its tools, its technical docs
  adii/contracts/            the shared vocabulary — read this first
  adii/investigator/         agent loop, investigation state
  adii/tools/                tool execution, evidence grounding
  adii/validation/           the validation boundary
  adii/evaluation/           scoring and answer keys
  adii/reporting/            telemetry — traces, artifacts, reports
  adii/demo/                 the orientation layer — explanation, never implementation
  tests/contract/            the contracts are pinned here
  tests/architecture/        the boundaries, as tests that fail the build
  scripts/                   check_env.py, sync_briefing.py, sync_status.py
  docs/                      system map, build plan, status, glossary, architecture

03_assets/                   diagrams, screenshots, and design prototypes
```

The split between `adii/` and `adii/demo/` is an authority boundary, not housekeeping:
the demo may be changed freely because it claims nothing, and a test forbids the rest of
`adii/` from importing it.

## New contributor? Read these four, in this order

| | |
|---|---|
| [system_map.md](02_src/docs/system_map.md) | what you are looking at, and where every concept lives in the code |
| [build_plan.md](02_src/docs/build_plan.md) | the milestones, what each one has to do, and what "done" means |
| [current_status.md](02_src/docs/current_status.md) | what is actually built right now — **generated**, so it does not go stale |
| [glossary.md](02_src/docs/glossary.md) | the words, kept short. Validation and evaluation are not the same thing |

Twenty minutes with those four and the walkthrough should leave you knowing what ADII
does, what exists, what does not, where each idea lives, what we build next, and how to
prove your contribution works.

Then take a task, or write one with
[task_template.md](02_src/docs/task_template.md). Nobody owns a subsystem here, so there
is no queue to join; [TEAM.md](TEAM.md) says how we work and
[architecture.md](02_src/docs/architecture.md#your-first-contribution) has the longer
path in.

**Working with an AI assistant?** Point it at [AGENTS.md](AGENTS.md) — it is
vendor-neutral, and it tells any assistant the same reading order and the same
boundaries. "Read AGENTS.md, system_map.md and build_plan.md, then explain the
investigator package to me as a beginner" is a reasonable first prompt.

## One repository

This is the whole project. Nothing to obtain elsewhere, no second checkout, no path on
disk that has to exist. If `pytest` passes here, the system works — not "works on the
machine that has the other repository".

An earlier implementation of ADII proved the architecture feasible, ran a real evaluation,
and was then audited. It is private and stays private. What crossed into this repository
is in [02_src/docs/inherited/](02_src/docs/inherited/): requirements, failure modes, and
one measurement problem. Its code did not cross, and neither did its results — those were
measured on a different system and stay attached to it.

## What we already know

[02_src/docs/inherited/](02_src/docs/inherited/) carries what a previous implementation of
ADII cost to learn. Read it before building the component it covers.

| | |
|---|---|
| [CONFORMANCE.md](02_src/docs/inherited/CONFORMANCE.md) | fifteen audited defects, restated as requirements per capability |
| [AUTHORITY_LIFECYCLE.md](02_src/docs/inherited/AUTHORITY_LIFECYCLE.md) | boundary 4, and the freeze-ordering mistake that produced it |
| [CONTROLS.md](02_src/docs/inherited/CONTROLS.md) | how we know investigating beats guessing — and why 18/18 is a problem |

[02_src/docs/DATA_WORLD_v0.md](02_src/docs/DATA_WORLD_v0.md) specifies the operational
world the incidents come from, why it is synthetic, and who decides changes to it.

Their tests are our requirements. Their implementation is not our implementation.

## Working with coding agents

Agents produce code faster than four people can review it. Three pieces of infrastructure
keep that from becoming a codebase nobody can defend:

| Piece | What it does |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | auto-loaded briefings — both generated from `02_src/docs/agent_briefing.md`, kept identical by a test |
| `.claude/skills/adii-change/` | the procedure for making a change here: read order, work order, boundaries, per-capability guidance |
| `02_src/tests/architecture/` | the boundaries as executable tests — they fail the build, not a review comment |

Edit `02_src/docs/agent_briefing.md`, then run `python 02_src/scripts/sync_briefing.py`.

## Contributing

Read [02_src/docs/review_playbook.md](02_src/docs/review_playbook.md) before your first
PR, [02_src/docs/task_template.md](02_src/docs/task_template.md) before starting a piece
of work, and [AGENTS.md](AGENTS.md) before pointing a coding agent at this repository.
The short version: **a perfect generated implementation that nobody can debug is not
done.**

## Submission packaging

The final deliverable is `ADII_Group05_Code_v1.zip`, containing this repository's
contents under a single `ADII_Group05_Code_v1/` folder. The structure above is already
that structure, so packaging is a copy and a zip — not a migration.

Kept in GitHub, excluded from the ZIP, because they coordinate development rather than
deliver the system:

```text
.github/          CI, CODEOWNERS, PR template
.claude/          agent skill definitions
CLAUDE.md         auto-loaded agent briefing
AGENTS.md         auto-loaded agent briefing
TEAM.md           how the team works
```

Everything required to install, run, test and understand the project stays in the ZIP:
`01_data/`, `02_src/`, `03_assets/`, `requirements.txt`, `README.md`.
