# eval_authority — how the evaluation agent thinks

**Read this first.** It explains the whole design without requiring you to open
any other file. Cross-references below point at the real file if you need the
exact code, but the reasoning here stands on its own.

## What this is

This is ADII's **evaluation authority**: the code that decides whether the investigator
got an incident right, and the code that guarantees that decision itself can be trusted.
It lives in `02_src/adii/evaluation/`, and the investigator may never import it — a test
in `tests/architecture/test_boundaries.py` fails the build if it does (see "Where it lives"
below). These tests are in `02_src/tests/eval_authority/`.

## The one idea that explains everything else

**Two different questions, two different halves of the code.**

1. **"Was this specific decision correct?"** — given one investigator decision,
   score it against the answer key. This is the everyday, per-decision engine.
2. **"Can I trust the answer I just got?"** — the answer key itself, the scoring
   rules, the judge's prompt: are *those* trustworthy, frozen, versioned, and
   internally consistent? This runs once per answer key / once per rule change,
   not once per decision.

Everything in this directory is one of these two things. Confusing them is the
most common way to misread this codebase: domain 2 does not produce a
correctness verdict, and domain 1 does not check whether its own inputs are
safe to trust — each assumes the other has already done its job.

```
                    ┌─────────────────────────────┐
                    │  DOMAIN 2 — is the judge     │
                    │  trustworthy? (runs rarely,  │
                    │  at authoring/freeze time)   │
                    │                              │
                    │  freeze.py • versioning.py   │
                    │  grounding.py • schema_*     │
                    │  scoring_semantics.json      │
                    └──────────────┬───────────────┘
                                   │ produces a
                                   │ trusted, frozen
                                   │ answer_key.json
                                   ▼
   InvestigationDecision   ┌─────────────────────────────┐
   (from A, via D)  ──────▶│  DOMAIN 1 — is this decision │
                           │  correct? (runs once per     │
                           │  scored decision)             │
                           │                                │
                           │  scoring.py • judge.py         │
                           │  outcome_classification.py     │
                           └──────────────┬─────────────────┘
                                          │
                                          ▼
                                  evaluation_report.py
                                  (beside each run's record; the grid
                                   runner reads these to report a pack)
```

## Domain 1 — is this decision correct?

**Files:** `scoring.py`, `judge.py`; the model call is `provider/judge.py`

**The flow for one decision:**

```
InvestigationDecision + ValidationResult + answer_key
        │
        ▼
scoring.decide_route()  ──────────────────────────────────
  1. disposition matches the answer key exactly?  no → "incorrect", done
  2. if REPAIR: was it independently validated (accepted)?  no → "incorrect", done
  3. if REPAIR: does root_cause_id AND repair_id both match the reference?
        both match  → "correct", done — no model call, ever
        either differs → "needs_judge_review"
        │
        ▼ (only for needs_judge_review)
judge.judge_repair()
  builds a prompt naming the reference repair, what any acceptable
  alternative must satisfy, and what the investigator actually did →
  calls a model (fake in tests, provider/judge.py for real) →
  parses a "correct"/"incorrect" verdict at a word boundary
        │
        ▼
{"verdict": "correct"|"incorrect"|"unresolved", "settled_by": "deterministic"|"judge"|"none"}
```

**The one rule that matters most:** the deterministic check in step 3 requires
*both* root_cause_id and repair_id to match before auto-passing. Matching only
one routes to the judge instead of guessing — this was a real bug caught and
fixed during development (see the git history around `decide_route`), because
a decision that reaches the right patch through a wrong diagnosis (or vice
versa) must never slip through as "correct" with nobody looking at it.

**Why a judge exists at all:** an investigator can reach the same correct
outcome by a differently-worded root cause or a differently-written patch.
Exact-string matching would fail those as "wrong" when they're actually fine.
The judge's only job is telling a genuine error apart from a valid
alternative — it never re-opens whether the answer key itself is right.

The validation verdict comes from the record: the runtime hands every REPAIR to the real
validator and records its result. For tests that score decisions held as plain dicts,
`validation_fakes.py` here holds a stand-in validator and an adapter from the real one. The
real model behind the judge is `02_src/adii/provider/judge.py`, standard library only,
wired into `python -m adii.evaluation --judge-model ID` (final plan, decision J).

## Domain 2 — can I trust the answer key and the rules?

**Files:** `freeze.py`, `versioning.py`, `grounding.py`, `answer_key.schema.json`
+ `schema_validator.py`, `scoring_semantics.json`, `test_independent_validation.py`

This domain answers six specific integrity questions, each one a documented
requirement from the team's own `CONFORMANCE.md` (labeled C1–C6 there):

| # | Question | Answered by |
|---|---|---|
| C1 | Does independent validation actually rebuild from scratch, rather than trusting the investigator's own claim? | `test_independent_validation.py` |
| C2 | Can an answer key be edited after it's been used to score something? | `freeze.py` — SHA-256, refuses to load on any mismatch |
| C3 | Are "what's correct" and "what evidence must have been used" kept as separate, independently-frozen files? | `grounding.py` — a grounding key binds to one exact frozen answer key by digest |
| C4 | Can an old-format file be silently misread as a newer format? | `versioning.py` — an unlisted field is a load error, never an upgrade |
| C5 | Does the published schema actually match what the code checks? | `answer_key.schema.json` + `schema_validator.py`, cross-tested |
| C6 | Can "what counts as correct" be redefined after seeing results? | `scoring_semantics.json` — frozen, versioned, code checked against it |

**Why this exists as its own domain, concretely:** a previous ADII
implementation lost the ability to add "which evidence a decision must cite"
to an already-frozen answer key — the two things had been bundled into one
file, and the file was frozen before the second thing was even designed (full
story in `adii_team/02_src/docs/inherited/AUTHORITY_LIFECYCLE.md`). Domain 2 is
built specifically so that mistake cannot repeat: every one-way freezing
decision here is its own artifact, hash-bound to whatever it depends on.

**The freeze workflow, concretely:**

```
1. author demo-learning-001.answer.json
2. freeze.freeze_answer_key() → writes demo-learning-001.answer.json.sha256
3. (optional) grounding.build_grounding_key() → demo-learning-001.grounding.json,
   which embeds the answer key's digest at build time
4. from here on, load_frozen_answer_key() / load_grounding_key() refuse to
   load either file if a single byte changed — no silent drift, ever
```

## The output layer

**Files:** `outcome_classification.py`, `evaluation_report.py`

Domain 1's raw verdict (`correct`/`incorrect`/`unresolved`) is too coarse for the final
report: *success, failure, false repair, correct abstention, unnecessary escalation,
repair rejection.* `outcome_classification.py` is the one place that turns a verdict into
one of those six names. `evaluation_report.py` builds one `adii.evaluation_report/v1`
document from a real run record and a frozen key, written beside `record.json`; the grid
runner (`grid.py`) reads those reports to report a whole pack.

## Where it lives

The evaluation authority and its catalogue of keys live in this repository, as the
bootcamp brief allows for a team-generated, team-labelled development set: the keys are
under `02_src/adii/evaluation/catalogue/`, frozen by digest, and the investigator is kept
from them by the tool layer (its only door to the world is a read-only database built from
an incident's own package) and by the boundary tests. Nothing in `adii/investigator/`
imports `adii/evaluation/` or `adii/validation/`.

## File-by-file map

```
Domain 1 — per-decision scoring
  scoring.py                    the deterministic router (decide_route, score_decision)
  judge.py                      the model-backed tiebreaker for ambiguous cases

Domain 2 — trusting the answer key and the rules
  freeze.py                     C2: hash-freeze / verified-load for any JSON file
  versioning.py                 C4: schema_version dispatch, rejects unknown fields
  grounding.py                  C3: answer-key / decisive-evidence pairing by digest
  answer_key.schema.json        C5: the published shape of an answer key
  schema_validator.py           C5: dependency-free validator checked against the schema
  scoring_semantics.json        C6: frozen definition of what "correct" means, by rule id
  test_independent_validation.py C1: proves independent validation ignores rehearsal claims

Output layer
  outcome_classification.py     verdict → one of the six M10/D-19 category names
  evaluation_report.py          per-run report built from a real run record (D-19)

Cross-cutting
  test_contract_consistency.py  checks Domain 1 against A/B's real contracts/core.py

Answer keys and fixtures (02_src/adii/evaluation/)
  fixtures/demo-learning-001.answer.json (+ .sha256)   the frozen walkthrough case
  fixtures/demo-learning-002-mismatch-drill.answer.json a hand-built judge-routing drill
  fixtures/synthetic-no-repair-001.answer.json          covers the NO_REPAIR path
  fixtures/synthetic-escalate-001.answer.json           covers the ESCALATE path
  catalogue/                                            the development set's keys, grounding
                                                        keys, partition and burned list

Test helpers
  validation_fakes.py           a stand-in validator and the real validator's dict adapter
```

## How to verify all of this yourself

```bash
python -m pytest 02_src/tests/eval_authority -q
```

Every claim above has a test behind it — if something here turns out wrong,
the test suite is what to trust over this document.
