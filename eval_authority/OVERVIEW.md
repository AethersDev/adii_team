# eval_authority — how the evaluation agent thinks

**Read this first.** It explains the whole design without requiring you to open
any other file. Cross-references below point at the real file if you need the
exact code, but the reasoning here stands on its own.

## What this is

This is Person C's part of ADII: the **evaluation authority** — the code that
decides whether the investigator (A) got an incident right, and the code that
guarantees that decision itself can be trusted. It lives outside the `adii_team`
repository on purpose (see "Why a separate directory" below) and has zero
import-time dependency on A's or B's code.

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
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                  failure_signal.py  evaluation_report.py  receipt_artefacts.py
                  (→ D's grid runner) (→ D's M10 report)   (→ D's spend receipt)
```

## Domain 1 — is this decision correct?

**Files:** `scoring.py`, `judge.py`, `validation_wiring.py`, `openai_provider.py`

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
  calls a model (fake in tests, openai_provider.py for real) →
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

**`validation_wiring.py`** is the seam where the real `validation/` package
(built by whoever owns it) plugs in later — today it's a fake that checks
patch text structurally. **`openai_provider.py`** is the equivalent seam for a
real model behind the judge — built and hand-verified, not yet wired into
anything, kept ready for the day a real judge call is needed.

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

## The output layer — handing results to D

**Files:** `outcome_classification.py`, `failure_signal.py`, `evaluation_report.py`,
`receipt_artefacts.py`

Domain 1's raw verdict (`correct`/`incorrect`/`unresolved`) is too coarse for
the final report the team agreed on (`build_plan.md` M10 / `plan_telemetry.md`
D-19): *success, failure, false repair, correct abstention, unnecessary
escalation, repair rejection.* `outcome_classification.py` is the one place
that turns a verdict into one of those six names — every other module in this
layer calls it rather than re-deriving the mapping:

```
outcome_classification.classify_outcome()
        │
        ├──▶ failure_signal.py        one JSON record per (incident, repeat),
        │                             for D's grid runner (D-17)
        │
        ├──▶ evaluation_report.py     one adii.evaluation_report/v1 document
        │                             built from a real RunRecord + an answer
        │                             key — sits BESIDE record.json, does not
        │                             modify D's RunRecord schema (D-19)
        │
        └──▶ receipt_artefacts.py     {"kind": "answer_key", "digest": ...}
                                      entries D's receipts.py names before
                                      any irreversible model call (D-15)
```

Each of these three is a thin, separately-testable adapter aimed at one named
integration point D owns — none of them duplicate `classify_outcome`'s logic,
and none of them touch A's or B's code.

## Why a separate directory, not inside `adii_team`

`01_data/README.md` (in `adii_team`) states answer keys must never ship inside
the ADII repository itself — if they did, the system under evaluation could
read its own answer key. `eval_authority/` is a sibling directory
(`adii-practice/eval_authority`, next to `adii-practice/adii_team`), not a
subfolder, not tracked by `adii_team`'s git history, and no file in this
directory imports anything from `adii_team` at import time. The one exception
is `test_contract_consistency.py`, which deliberately reads `adii_team`'s real
`contracts/core.py` at test time to catch drift early — it skips itself
cleanly if `adii_team` isn't present on the machine.

## File-by-file map

```
Domain 1 — per-decision scoring
  scoring.py                    the deterministic router (decide_route, score_decision)
  judge.py                      the model-backed tiebreaker for ambiguous cases
  validation_wiring.py          fake independent-validator seam (real one: validation/)
  openai_provider.py            real-model seam for judge.py (built, not yet wired in)

Domain 2 — trusting the answer key and the rules
  freeze.py                     C2: hash-freeze / verified-load for any JSON file
  versioning.py                 C4: schema_version dispatch, rejects unknown fields
  grounding.py                  C3: answer-key / decisive-evidence pairing by digest
  answer_key.schema.json        C5: the published shape of an answer key
  schema_validator.py           C5: dependency-free validator checked against the schema
  scoring_semantics.json        C6: frozen definition of what "correct" means, by rule id
  test_independent_validation.py C1: proves independent validation ignores rehearsal claims

Output layer — handing results to D
  outcome_classification.py     verdict → one of the six M10/D-19 category names
  failure_signal.py             per-repeat record for D's grid runner (D-17)
  evaluation_report.py          per-run report built from a real RunRecord (D-19)
  receipt_artefacts.py          digest entries for D's spend receipt (D-15)

Cross-cutting
  test_contract_consistency.py  checks Domain 1 against A/B's real contracts/core.py

Answer keys and fixtures
  demo-learning-001.answer.json (+ .sha256, + .grounding.json)  the real, frozen walkthrough case
  demo-learning-002-mismatch-drill.answer.json                  hand-built judge-routing drill
  fixtures/synthetic-no-repair-001.answer.json                  covers the NO_REPAIR path
  fixtures/synthetic-escalate-001.answer.json                   covers the ESCALATE path

Docs
  OVERVIEW.md                   this file
  RECEIPT_ARTEFACTS.md           integration guide for D-15, aimed at whoever builds receipts.py
```

## How to verify all of this yourself

```bash
cd eval_authority
pytest -q          # 195 tests, all of Domain 1 + Domain 2 + the output layer
```

Every claim above has a test behind it — if something here turns out wrong,
the test suite is what to trust over this document.
