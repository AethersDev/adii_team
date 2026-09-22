# ADII — briefing for Claude Code

A four-person project on a six-week clock. Code arrives faster than it can be reviewed,
so the constraints below are load-bearing rather than stylistic.

**The block between the BEGIN/END markers is generated from
`02_src/docs/agent_briefing.md` and shared with `AGENTS.md`. Edit that, then run
`python 02_src/scripts/sync_briefing.py` — a test asserts they match. The sections after
the block are this file's own.**

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

Both must pass on your machine, with the syncs and the guard pass for every track you
touched. CI is optional assistance, not a gate: cross-platform correctness is established
by qualifying the exact submission ZIP on clean Windows and macOS machines
(`02_src/docs/final_plan.md`, decision CI). If you added a guard — a
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

## Commands

```bash
python -m pytest                                                # the suite; pyproject sets pythonpath=02_src
python -m pytest 02_src/tests/unit/test_env_local.py -k twice   # one file, one test by name
python -m pytest 02_src/tests/architecture -q                   # the boundaries alone — run these first
python -m ruff check 02_src                                     # rules E F I UP B, line length 100
python 02_src/scripts/guard_check.py --only D                   # one track's guards; --list prints the registry
python -m adii.examples.walkthrough                             # end to end without a model
python -m adii.demo 8000 --model <id> --endpoint http://127.0.0.1:8090/v1 --served-as default_model
```

- Every test has a 60 s thread-based timeout. A test over budget is refactored; the budget
  is not raised.
- `guard_check.py` rewrites source files in place and restores them byte for byte. Never run
  it while pytest or an editor may touch the tree. Exit 0 only when every guard is KILLED.
- The browser tests find Chrome through `ADII_CHROME` or on PATH; without it they skip.
  Run the gate with Chrome present. They occasionally flake in a full local run and pass alone; rerun
  the file by itself before blaming a change.
- `02_src/tests/eval_authority/test_step1_all.py` and `test_step2_all.py` are gitignored on
  purpose: they need blind answer keys that are not in the repository.

## Generated files — edit the source, run the sync

| Generated | Source | Sync |
|---|---|---|
| the briefing block of `CLAUDE.md` and `AGENTS.md` | `02_src/docs/agent_briefing.md` | `python 02_src/scripts/sync_briefing.py` |
| `02_src/docs/current_status.md` | the `- [x]` marks in `02_src/docs/build_plan.md`, plus the packages' line counts | `python 02_src/scripts/sync_status.py` |
| `02_src/adii/demo/web/{tokens,base,components}.css` | `03_assets/identity/css/` | `python 02_src/scripts/sync_identity.py` |

A test fails on any drift between a generated file and its source, so the local gate catches it.

## How a run flows — what no single file says

- **The runtime is the harness.** `run_incident` in `02_src/adii/runtime/run.py` drives three
  protocols (Investigator, Tools, Validator), wraps the tools so every call and result lands
  in the trace as it happens, lets only a REPAIR reach the validator, and archives every
  ending under `01_data/runs/<label>/`: `receipt.json` before anything runs, `trace.jsonl`
  as it happens, `record.json` at the end. Termination is one of four closed values:
  `submitted`, `model_failure`, `bound_hit`, `infrastructure_failure`. A label names one
  run forever; a taken label is refused, never overwritten.
- **Three providers on `python -m adii.runtime`.** `scripted` replays the walkthrough over
  the real tool layer with no model. `local` runs the investigator loop against an
  OpenAI-compatible endpoint on this machine and spends nothing. `openai` is the paid path:
  a receipt on disk first, a nominal price in `reporting/ledger.py`, a hard cap enforced by
  worst-case reserve before each request, the credential from the environment or from the
  ignored `.env.local` (`.env.example` names it) and nowhere in any artefact.
- **`02_src/adii/provider/` is the only package that speaks to a model.** It is absent from
  `system_map.md`'s table; `stack.md` describes it. `ChatProvider` records `model_requested`
  and `model_responded` at the boundary, before the loop parses anything. HTTP runs in a
  killable subprocess (`worker.py`) started without the key in its environment; no redirect
  is followed; a failure comes back as `ProviderFailure` with kind, status and error code,
  never a body. `runtime/live.py` classifies endings by exception type only:
  `BoundExceeded` is `bound_hit`, `ProviderFailure` is `infrastructure_failure`, anything
  else is `model_failure`. Never classify by message text.
- **Cost is two numbers.** The record carries the lower bound (proved usage at nominal
  prices). Admission uses the exact worst case (unknown rows at the reserve that admitted
  them, `Decimal`). Neither is ever called a total, and a run of unknown rows is never 0.0.
- **The validator is on the live path, by decision record.** `runtime/live.py` hands every
  REPAIR to the real validator through `ValidatorOnLivePath`, which translates exactly one
  exception: an incident with no rebuildable world (today, everything but
  `demo-learning-001`) is NOT_CHECKABLE, said in structure by `reason_code`, never a lost
  decision and never a verdict. A verdict is ACCEPT or REJECT, and a REJECT always names
  the checks that ran; a validator returning the legacy no-checks shape is an
  infrastructure failure. Beside the verdict, and never gating it, the runtime records its
  own fact for every REPAIR: `authorize` in `runtime/run.py` checks the patch's targets
  against the incident's permitted paths, whole or not at all, and the validator is handed
  the incident without those paths. `RunRecord.admissible` derives authorized-and-ACCEPT and
  is stored nowhere. Nothing executes. M7 is closed; the record is
  `02_src/docs/m7_validation_integration.md`.
- **A decision cites what it observed, or it is refused.** `evidence_refs` on the decision
  names observations by the ids the tool layer minted on successful results. The loop
  refuses a citation the model never received, with the ids named and the reason returned
  once; a record is never built citing what its trace never minted. Cited means observed,
  never warranted: the evaluation report carries grounding beside the category, and
  whether the decisive observation was cited is a grounding key's question.
- **The trace vocabulary is a contract in progress.** `02_src/docs/trace_event_contract.md`
  lists the open rows; placeholders such as `usage` on `model_responded` move when a row
  resolves. Do not invent event kinds.
- **The guard registry is per track.** Rows are named `A.`, `B.`, `C.`, `D.` for the loop,
  the tools, evaluation, and telemetry/runtime/provider. Each names a file and an exact
  snippet; a snippet that moved fails the pass, so refactor guarded lines with the registry
  open.

## Conventions this team holds beyond the briefing

- A change to a contract or to shared vocabulary is written up as a proposal with a per-row
  decision table (APPROVED / REVISE / DEFER; see `02_src/docs/green_line.md` and
  `02_src/docs/m7_validation_integration.md`). The resolution is a new commit; history is
  never amended.
- Nothing committed contains an absolute path.
- Windows and macOS parity is enforced: LF line endings via `.gitattributes`, Python 3.12
  only (`>=3.12,<3.13`), `pytest` and `ruff` pinned in `requirements.txt`.
