# ADII architecture

A number in the data looks wrong. ADII investigates it and answers **Fix it** (REPAIR),
**Leave it** (NO_REPAIR) or **Escalate it** (ESCALATE). The model that investigates can
propose a fix; it cannot approve one. This page is the system in one diagram, four
boundaries, and one run end to end.

```text
                          INCIDENT  (the alert, and a frozen copy of the data)
                             │
                             ▼
              ┌──────────────────────────────┐
              │   INVESTIGATOR               │   a model, in a bounded loop:
              │   decides what to look at    │   turns, tool calls, time, a cost cap
              └──────────────────────────────┘
                    │  ToolCall      ▲  ToolResult (every observation gets an id)
                    ▼                │
              ┌──────────────────────────────┐
              │   CONTROLLED TOOLS           │   read-only, bounded results,
              │   the ONLY way to see data   │   no file paths, nothing written
              └──────────────────────────────┘
                             │
                             ▼
              REPAIR   /   NO_REPAIR   /   ESCALATE      — citing the observations it used
                 │
                 └── a REPAIR carries a patch, and two authorities judge it:
                              │
              ┌───────────────┴──────────────┐
              ▼                              ▼
   ┌─────────────────────┐       ┌──────────────────────────┐
   │ AUTHORIZER          │       │ INDEPENDENT VALIDATOR     │
   │ may this incident's │       │ rebuild from frozen       │
   │ files be changed?   │       │ inputs, check invariants  │
   └─────────────────────┘       └──────────────────────────┘
              └───────────────┬──────────────┘
                              ▼
               ADMISSIBLE = authorized AND ACCEPT      (derived, never stored)

   THE RUNTIME writes a receipt before anything is spent, a trace as it happens,
   and a record at the end:  01_data/runs/<label>/

  ══════════════════════════════════════════════════════════════════
   EVALUATION AUTHORITY — answer keys and scoring, a separate program
   never in the investigator's context, never importable by it
  ══════════════════════════════════════════════════════════════════
```

## The four boundaries

**1. The investigator sees the data only through the tool layer.**
It has no file path, no database handle, no shell and no network. If it could read files
it could read an answer key, and every number reported about it would be meaningless. The
tool layer decides what the investigator may do and refuses the rest; a `DENIED` result is
the boundary working. Only `02_src/adii/tools/` may open the data.

**2. The investigator is not the validator.**
A model will happily tell itself a patch works; that is a hypothesis. The validator
rebuilds the data from a frozen copy with the patch applied and checks it against the
data's own invariants — identities, never only counts — and returns the verdict. The
investigator never imports the validator and never sees how it decided.

**3. The judge is a different program.**
Each incident's correct answer is held by the evaluation authority, in
`02_src/adii/evaluation/`, which the investigator cannot import. This is not boundary 2
restated: validation asks *does this repair work*, the judge asks *was this the right call
at all*. Two questions, two authorities, both out of the investigator's reach.

**4. What is evaluated is frozen first.**
Before any final run, `python -m adii.evaluation.lock` names every file of the evaluated
system by sha256, with the terms of every evaluation pack. From then on a test fails if a
frozen file changes, and the evaluation refuses to run on a tree that does not match. An
authority that changes after its results exist is not an authority.

## Admission: two facts about every proposed fix

| authorizer | validator | meaning |
|---|---|---|
| permitted | ACCEPT | admissible — *Fix it* |
| permitted | REJECT | allowed, but it does not work |
| denied | ACCEPT | works, but not allowed |
| denied | REJECT | neither |

The authorizer checks the patch's targets against the files the incident permits, whole
or not at all. The validator is asked regardless and is never told what is permitted: the
two facts are independent, and neither gates the other. Nothing is executed on real data
in any cell. `01_data/runs/square-*` holds one archived run for each cell.

## One run, end to end

`python -m adii.runtime` (`02_src/adii/runtime/`) is the harness, and the page and the
evaluation start runs only through it:

1. **Receipt.** Before any model request: the incident and data by digest, the
   configuration, the reason the spend is permitted — flushed to disk.
2. **Investigation.** The loop sends the alert and the tool list to the model and executes
   each tool call it asks for through the tool layer, within its bounds. A paid request is
   admitted only if its worst-case cost fits under the run's hard cap.
3. **Decision.** The model submits a disposition that cites observation ids. A citation of
   something it never observed is refused.
4. **Authorities.** A REPAIR goes to the authorizer and the validator.
5. **Record.** One strict, versioned JSON record (`adii.run_record/v3`): the decision, both
   facts, the trace, the counters, the cost as a proved lower bound. A run ends in exactly
   one of four ways — `submitted`, `model_failure`, `bound_hit`, `infrastructure_failure` —
   and every ending is archived as legibly as a success.

`02_src/adii/provider/` is the only code that speaks to a model: HTTP runs in a separate
process started without the key, no redirect is followed, and a failure comes back as a
kind and a status, never a response body.

## Where the code is

```text
02_src/adii/contracts/     the shared vocabulary: eight types every package speaks
02_src/adii/investigator/  the loop, the protocol, the model's messages refused or accepted
02_src/adii/tools/         the only door to the data
02_src/adii/validation/    rebuild from frozen inputs, check invariants
02_src/adii/runtime/       one incident end to end: receipt, trace, authorities, record
02_src/adii/provider/      the model boundary and its cost caps
02_src/adii/reporting/     the record, the ledger, the archive's manifest
02_src/adii/evaluation/    answer keys, scoring, the evaluation grid, the freeze
02_src/adii/examples/      the incident generator and the walkthrough
02_src/adii/demo/          the page: a view over the archive and a starter of runs
02_src/tests/              the boundaries above, as executable tests
```

Each package has a README saying what it is for. The boundaries are tests, not prose:
`02_src/tests/architecture/test_boundaries.py` fails the build if the investigator imports
the validator or the evaluation, or if anything outside the tool layer opens the data.

```bash
python -m adii.examples.walkthrough --step    # the architecture, one stage at a time, no model
python -m pytest 02_src/tests/architecture    # the boundaries alone
```
