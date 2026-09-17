# ADII — briefing for Claude Code

A four-person project on a six-week clock. Code arrives faster than it can be reviewed,
so the constraints below are load-bearing rather than stylistic.

**This file is generated from `02_src/docs/agent_briefing.md`. Edit that, not this — a test
asserts they match.**

<!-- BEGIN ADII BRIEFING -->
## For any AI assistant working in this repository

Vendor-neutral on purpose. Whichever assistant you are, this is the contract.

1. Read `README.md`, then `02_src/docs/system_map.md`, then
   `02_src/docs/build_plan.md`, then `02_src/docs/current_status.md`.
2. Read the `README.md` of every package you will modify.
3. Run the relevant tests **before** changing code, so you know what was already failing.
4. Do not cross the investigator/evaluation boundary in either direction.
5. Never expose hidden evaluation material to agent-facing code.
6. Do not introduce per-person ownership of a subsystem. Folders organise the system;
   tasks organise the team's work.
7. Preserve existing public contracts unless the task explicitly changes them.
8. After changing anything, run the tests and report exactly what changed.

When explaining this code to a teammate: purpose before implementation; name the inputs
and outputs; map every concept to a concrete file; separate what exists from what you are
proposing; and finish with the exact command that verifies it.

`02_src/docs/current_status.md` is generated — it says what is actually built. Trust it
over any assumption about what a package name implies.

## Read these before writing anything

1. `02_src/docs/system_map.md` — what each package is, and what it must never do.
2. `02_src/docs/architecture.md` — the boundaries, and why they are where they are.
3. `02_src/adii/contracts/core.py` — the shared vocabulary. Eight types.
4. `02_src/docs/inherited/CONFORMANCE.md` — defects already found and paid for, as requirements.
   Read the section for the capability you are touching. Several are invisible until a
   paid run, and one of them silently misfiles a model error as a platform error.
5. `01_data/walkthrough/README.md` — one complete run, narrated.
6. The `README.md` of the package you are about to touch.
7. If the change touches incidents or the tool surface, `02_src/docs/DATA_WORLD_v0.md`.
8. Unsure what a word means here? `02_src/docs/glossary.md`. Validation and evaluation
   are not synonyms, and confusing them is the most common mistake in this codebase.

An agent that has not read the contracts will invent its own. They will be plausible,
well-named, and incompatible with everyone else's.

## The three boundaries — non-negotiable

**1. The investigator sees the world only through the tool layer.**
No `open()`, no `sqlite3`, no `subprocess`, no network — anywhere outside `02_src/adii/tools/`.
Reading the file directly is always simpler and always wrong: a component that can open a
file can open the answer key.

**2. The agent is not the validator.**
The investigator may rehearse a repair; that produces a *hypothesis*. Only
`02_src/adii/validation/` returns a *verdict*, by rebuilding from frozen inputs. Never let
the investigator import `validation/` or `evaluation/`.

**3. The judge is a different program.**
Incidents, answer keys, and scoring are the evaluation authority's, and live in
`02_src/adii/evaluation/`.
The investigator never imports it. This is not boundary 2 again: validation asks *does this repair work*,
the judge asks *was this the right call at all*.

These are enforced by `02_src/tests/architecture/test_boundaries.py`. If one fails, the fix is
essentially never to relax the test.

## Never do these

- **Invent or edit a contract** in `02_src/adii/contracts/`. That is a human decision needing
  cross-boundary review — it is the one thing all four people share.
- **Copy the reference implementation's loop.** Its *tests* are our requirements; its
  *code* is not our code. `02_src/docs/inherited/` is the transfer.
- **Freeze an artifact you know is incomplete.** An authority frozen early cannot be
  finished — see boundary 4 in `02_src/docs/architecture.md`.
- **Touch a frozen incident.** What is legal depends on the *type*: the teaching incident
  under `01_data/walkthrough/` carries no evaluation claim and may be changed freely; development and adversarial
  incidents are additive only; anything a reported result was scored against is frozen
  permanently; blind incidents are custodian-controlled. See `02_src/docs/DATA_WORLD_v0.md`.
- **Import a private repository.** `adii_env`, `adii_eval`, and the reference
  implementation are not on anyone else's machine. What we inherited from them is
  `02_src/docs/inherited/`; the code did not come with it, and their measured results are not
  ours to quote as our own.
- **Add a dependency** silently. No Docker, Redis, Postgres, Make, or shell scripts —
  the team develops on Windows and macOS, and no machine is canonical.
- **Write a shell script.** Anything that matters runs as `python -m ...`.
- **Claim a run succeeded without a trace.** If it is not in the trace, it did not happen.

## Before you say it is done

```bash
python -m ruff check 02_src
python -m pytest
```

Both must pass, and CI must be green on Windows *and* macOS. If you added a guard — a
check that rejects, bounds or validates — it is not done until its row is in
`02_src/scripts/guard_check.py` and the pass reports it killed: a guard is demonstrated
when removing it makes a test fail, not when a test passes.

## The author-understanding gate

The author must be able to answer, unaided:

1. What problem does this change solve?
2. What are its inputs and outputs?
3. What important failure modes does it have?
4. How did you test it?
5. What did you generate, and what did you have to correct?

So: agree the approach before writing code, implement one unit, test it. A perfect
implementation nobody can defend in review is not done — prefer a small change its author
can explain to a large one they cannot.
<!-- END ADII BRIEFING -->

## Where things live

```text
02_src/adii/contracts/     shared vocabulary — read first, change only with review
02_src/adii/investigator/  the agent loop and investigation state
02_src/adii/tools/         tool execution — the ONLY door to the outside world
02_src/adii/validation/    the validation boundary — the other authority
02_src/adii/evaluation/    incidents, answer keys, scoring, baselines
02_src/adii/reporting/     telemetry — traces, artifacts, reports
02_src/adii/runtime/       one incident end to end — the harness that owns the trace
02_src/adii/demo/          ADII's page over the archive — the rest of adii/ may never import it
02_src/tests/architecture/ the boundaries, executable
01_data/demo/world/        the shared operational world (work order; not built)
01_data/demo/csv/          the specimens' worlds as CSV — the data to bring to the page's form
01_data/runs/              the archive: one record per run, what the inspector reads
01_data/walkthrough/       the teaching fixture
```

Top-level `01_data/ 02_src/ 03_assets/` is the submission structure, used from day one so
there is no packaging migration at the deadline. Code goes in `02_src/`, data the system
reads goes in `01_data/`, and nothing that states an answer goes in either.
