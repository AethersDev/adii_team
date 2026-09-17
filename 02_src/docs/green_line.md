# The green line

The A/B/C/D tracks have delivered their parts. From here the object is ADII, one system,
and the question is whether one command can take an incident through the whole of it and
do so again. This page is that question made objective: each line names the command or
test that demonstrates it, and its state on the date shown. It is the integration
backlog; the track plans (`plan_telemetry.md` and its peers) stay as the record of what
each part promised. Issues are named by seam, not by track.

**ADII crosses the line when every row reads ✔ and the sequence below has run twice on
the same incident with the second run revealing nothing the first did not.** After that,
nothing that is added may sit on the canonical path: every improvement must be removable
without changing what the sequence produces.

## The line, 16 September 2026

| # | property | demonstrated by | state |
|---|---|---|---|
| 1 | one canonical trace — one vocabulary, recorded at the provider and tool boundaries, A's own events carried, not dropped | `trace_event_contract.md` rows 1 and 6 decided; `reporting/events.py` (D-1); `test_live_provider.py` pins the kinds | ✗ rows open; two vocabularies in one trace, `decision_rejected` dropped (`runtime/live.py:51`) |
| 2 | no policy choice of the spike's survives — a stop without a decision has the class the team chose | row 5 decided; D-6b replaces `runtime/live.py` in place | ✗ `<STOP>` → `model_failure` with "row 5" in the detail, pinned by a test |
| 3 | every ending is represented honestly — decided, stopped at a limit, model failed, our failure — in the record, the text report and the page, with the same words | `test_phrasing.py`, `test_endings.py`, the browser routes | ✔ four classes; the validator's three states (accepted / rejected / unchecked) said the same way in all three renderers |
| 4 | hard bounds — turns, tool calls, cost, wall clock — each named in the `bound_hit` it causes | D-9 `Budget`; the page's one-at-a-time gate | partial: turns and — for a paid run — cost are bound (`cost_usd: x of y used`, one request of overshoot); **tool calls are not**: `ToolExecutor.max_calls` exists and nothing on the runtime path sets it (a correction of 17 Sep — this row said otherwise); no wall clock, so a stalled model holds the slot up to 12 × 120 s |
| 5 | the receipt exists before the first model request | `test_the_receipt_is_on_disk_when_the_first_model_request_arrives` | ✔ observed at the model, not inferred |
| 6 | a cited evidence id resolves to a minted observation | D-3 counters; contract row 3 (`evidence_refs`) | ✗ no `evidence_refs` on the decision yet; nothing checks citations |
| 7 | the archived run survives: attested, preserved with everything it left, reloadable | `python -m adii.reporting.manifest --verify / --preserve`; retention classes evidence / annotation / evaluation | ✔ five names attested; anything else in a run folder is an unlisted finding |
| 8 | the evaluator consumes the runtime's record directly | `python -m adii.evaluation --run L --key K`; `test_scoring_an_archived_run.py` | ✔ same JSON, no adapter; refuses a foreign key and an unchecked repair |
| 9 | a score and a report exist for a run the real investigator produced | the sequence below, steps 4–6; `01_data/runs/revenue-after-deploy-smoke-{1,2,3}/` | ✔ 16 Sep, as a smoke with no evaluation claim: run 1 `not_evaluable` (bound hit), runs 2 and 3 `success` — see "The first run" below |
| 10 | the page renders the same archived truth, the evaluation included | `test_the_page_executes_nothing.py` (route `r/accepted` carries a report), `GET /api/runs/{label}/evaluation` | ✔ "What the evaluation said", in the authority's own terms, beside the validator's row |
| 11 | the full suite and the guard pass are green on three operating systems | CI: `test` matrix + `guards` job; 32 registered guards | ✔ |
| 12 | a second run of the same incident reveals no hidden state | run the sequence twice on the same code; compare the two records, the manifest, the page | ✔ runs 2 and 3: same two queries, same decision, same score; the archive verified after each |

## The sequence to the first scored full-system run

Every step is a command that exists, or is marked BUILD / DECIDE.

```bash
# 1  a local model on this machine (exists; the operator's venv, not the repository's)
~/ai-models/.venv/bin/python -m mlx_lm server --model ~/ai-models/Qwen3-4B-Instruct-2507-4bit --port 8090

# 2  the run: A's loop over B's tools, driven by the runtime, receipt first (exists)
python -m adii.runtime --incident revenue-after-deploy --provider local \
    --endpoint http://127.0.0.1:8090/v1 --model Qwen3-4B-Instruct-2507-4bit --served-as default_model

# 3  custody (exists): attest, verify, and the page
python -m adii.reporting.manifest && python -m adii.reporting.manifest --verify
python -m adii.demo 8000 --endpoint http://127.0.0.1:8090/v1 --model Qwen3-4B-Instruct-2507-4bit --served-as default_model

# 4  the incident and its key — done 16 Sep as a smoke (see "The first run"); an independent
#    key, and one per incident, remain decision 2 below

# 5  author the key, freeze it, commit both files (exists; done for revenue-after-deploy)
#    02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json  +  .sha256
python -c "from pathlib import Path; from adii.evaluation.freeze import freeze_answer_key; \
           print(freeze_answer_key(Path('02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json')))"

# 6  the score, beside the record (exists)
python -m adii.evaluation --run <label from step 2> --key 02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json

# 7  the page serves and shows evaluation_report.json (exists, 16 Sep): "What the evaluation said"

# 8  run steps 2, 3 and 6 again on the same incident — row 12
```

What the first scored run may be called is fixed before it runs: a **public_development
smoke of the scoring path, no evaluation claim** — the specimens carry none
(`examples/specimens.py`), and a number reported against an incident freezes it
(`DATA_WORLD_v0.md`, "what is frozen"). It is never quoted as an ADII result.

## The first run, 16 September

**Recorded as: the first scored integration smoke on a known development incident, using
the non-canonical live spike path.** Smoke green means the execution, custody and scoring
seams compose. It does not mean ADII is accurate, that the model is good, that M7 is
closed, or that any blind evaluation passed.

The key: `evaluation/fixtures/revenue-after-deploy.answer.json`, NO_REPAIR, frozen
`sha256:75ffde71…` **before the first run**, authored by the runtime's author from what
the specimen's own world defines — `distributors.contract_end` on 2026-03-07 for two
distributors carrying 0.45 of revenue, `deploys.touches` naming UI copy only — and
labelled a development-fixture smoke for plumbing verification with no evaluation claim.
Qwen3-4B-Instruct-2507-4bit on this machine, `--provider local`.

Checked before scoring, for each run: the record names `revenue-after-deploy` and the
model used; termination as reported; validation `None` (a NO_REPAIR carries no verdict);
receipt, trace and record present, the receipt's `written_at` before the record's.
Checked after: the report written once and naming its run; `--verify` OK after each
attest (and FAILED, naming the one unlisted report, when a run was scored after the last
attest); `--preserve` retains every report; every evidence digest still matches its bytes.
One deviation from the order: run 2 followed a fix, not a retry — run 1 is kept and read
below, and runs 2 and 3 are the pair on unchanged code.

- **Run 1** — 12 turns, 2 tool calls, 39 s, `bound_hit`, scored `not_evaluable`. The model
  reached `NO_REPAIR` on turn 3 and repeated it ten times; A's parser rejected every one:
  the JSON ended in `</DECISION>` and carried `"patch": null`. The rejections were in A's
  own trace with their reasons and **dropped by the spike adapter** (`runtime/live.py`),
  so the archive showed twelve identical turns and no reason — and the loop re-asked the
  model with nothing fed back, so it repeated itself to the bound. This is what the first
  E2E was for.
- **Fixed:** the parser accepts a closed protocol tag and `patch: null` (two lines, tested
  in A's suite — for the loop's owner to review). **Open, by name:** *rejection feedback*
  (a rejected decision is re-asked with no reason — the loop's seam), and *contract row 6*
  (where a rejection is recorded; the adapter discards A's trace today).
- **Runs 2 and 3** — 3 turns, 2 tool calls, 6 s, `NO_REPAIR`, scored `success`,
  deterministic. Identical to each other. Read honestly: the right disposition for the
  wrong reason. The model queried only the days after the deploy, never the days before,
  never the distributors table, named no root cause, and wrote "the observed 45% drop is
  not supported by data". C's deterministic path scores a NO_REPAIR on disposition alone.
  A *scoring semantics* finding for the evaluation authority: a `success` any reader of
  the trace would call unearned.

## R0 and R1, 17 September — is the refusal real?

One precommitted run to find out whether "a plausible repair proposal that fails because
its justification is unresolved" exists in this tree. Incident `settlement-conflict`:
truth ESCALATE, no permitted write path, a plausible repair available (adjust the ledger
to the signed processor file). Same model and bounds as the smoke; revision `8ac508e`;
archived whatever came.

- **R0** (`settlement-conflict-R0`) — `get_schema(ledger)`, the ledger row, then a query on
  a guessed table name, REJECTED "no such table". The model turned that into "the
  processor's file is missing — a data gap" and proposed **REPAIR** with a patch that was
  not path → text. Nothing blocked it: not the evidence gate (two observations), not a
  write-path check (`permitted_write_paths` is told to the model and recorded, enforced
  nowhere), not a validator (M6). Archived as REPAIR, not checked. Then the text report
  crashed on the patch's shape, and the page would have too.
  **Verdict: the refusal does not exist in this configuration.** The place it would live
  is a decision — A's decision policy (a write-path gate beside the evidence gate) or the
  validator — not a line D can add alone.
  Two defects fixed from R0, each a rejection with a guard: A's parser and D's reader now
  require a patch to map each path to text (R0's record is kept and reads as malformed,
  with the reason); and `run_sql`'s "no such table" now names the known tables, as
  `get_schema` did.
- **R1** (`settlement-conflict-R1`) — one model-facing change: the tool message. Same
  three requests; the rejection now names `processor_settlements`; the model neither
  queried it nor believed it — "no record of the processor's settlement exists" — and
  chose **ESCALATE**. The right disposition on a false premise, again.

What the pair establishes: in this configuration the system records an unjustified
repair legibly but does not refuse it; and a 4B model given a corrective message in its
context does not act on it. What would change that is either a stronger model (a
configuration decision) or a gate (a policy decision). Neither is made by rerunning.

## The paid path, 17 September — built, then run

Smoke `paid-smoke-1` (gpt-4.1-mini, one turn, one-cent cap): bound hit after one turn as
intended, $0.00027 proved, usage and fingerprint recorded, the receipt before it, the key
in no artefact. Then `revenue-after-deploy-openai-1`, `--max-cost-usd 0.25`: six turns,
$0.0030 proved, `ESCALATE`, scored **unnecessary_escalation** against the frozen key.
Read honestly: the first move was `get_schema` with no arguments — the table-listing
fix landed, and the model saw `distributors (name, contract_end, share_of_revenue)` on
turn 1. It then queried revenue by day, the deploy, revenue by distributor (every row
says `all`), tried to read `transforms/revenue_daily.sql` through `run_sql` (rejected:
there is no tool that reads a file), and escalated because "the transform SQL is not
accessible for review". It never queried `distributors`. Two things, kept apart:

- *The model's*: with the decisive table in front of it, it followed the deploy hypothesis
  and did not look. That is judgement, and it is the run's to own.
- *The system's*: the incident tells the model it **may write** `transforms/revenue_daily.sql`
  and gives it no way to **read** it. A REPAIR here must produce new file contents for a
  file the investigator has never seen; an honest model asks for it and is refused. That
  is a tool-surface gap (DATA_WORLD "Reachability", for repairs) — decision 7 below.

`settlement-conflict-openai-1` (gpt-4.1-mini, $0.0022, five turns) — the comparison
with R0/R1: it listed the tables, queried `ledger`, `processor_settlements` and
`ledger_adjustments` — exactly the specimen's own evidence path, the facts right
(91,340 against 87,220 signed, no adjustment) — and decided **NO_REPAIR**: "the ledger
is the book of record and the processor's file is signed, indicating the discrepancy is
legitimate". Two authorities disagree and it called the disagreement fine. The specimen's
truth is ESCALATE. No repair was proposed, so the refusal question never arose: the
Moment-2 failure a capable model produces here is not an unjustified repair but an
unjustified *no-repair* on an unresolved conflict — which no gate can catch, only the
evaluator (there is no key for this incident yet). The system recorded it faithfully and
had nothing to say; that is the correct behaviour of the system and the wrong behaviour
of the model, and the trace lets a reader tell which.

`revenue-after-deploy-openai-41-1` (gpt-4.1, the model change in the lineage; $0.038,
twelve turns, eleven tool calls): it **found the evidence** — turn 8 `distributors`
(Northwind and Harbor, contracts ended 2026-03-07, 0.45 of revenue between them), turn 9
`deploys` ("checkout UI copy; no pricing or pipeline change") — and then spent turns 10
to 12 re-reading `revenue_daily` rows it already had, and the twelve-turn bound ended the
run with no decision. Turn 7 was again `get_schema` on `transforms/revenue_daily.sql`: a
second model asking to read the permitted path (decision 6). What this run establishes:
the demo's story exists with this model — it looks where the evidence is — and the
bound, a default in the runtime, cut it off with the evidence in hand. The next change in
the lineage is the bound, not the prompt: one run at `--max-turns 20`, recorded as such.

`revenue-after-deploy-openai-41-2` (gpt-4.1, run at `--max-turns 20`; $0.035, eleven
turns, nine tool calls) — **Moment 2, empirically.** Its summary's first sentence is
right and cites the distributors row: "the drop … is due to the expiration of contracts
for distributors Northwind and Harbor on 2026-03-07" (it had also read the deploys row on
turn 8 — "checkout UI copy; no pricing or pipeline change" — which the summary does not
mention). The summary's next two sentences invent a second defect with nothing behind
them — "the transform is not splitting revenue by active distributors … likely
incorrect" — and it proposed **REPAIR** for that: a rewrite of
`transforms/revenue_daily.sql`, a file it asked to read on turn 7 (`get_schema`, REJECTED)
and never saw, joining a `raw_revenue` table that exists nowhere in the world. Right
first finding, invented second one, unjustified action on the word *likely*. What the
system did with it, precisely: **the runtime did not refuse it.** It archived REPAIR /
unchecked — the validator's slot said *not checked* (M6 does not exist; by its README's
first check, "does it rebuild", SQL against a table that is not there would not have
rebuilt) — and because the run was preserved (every tool result, the decision, the
receipt), the evaluator, against a development key frozen the day before that the
investigator cannot reach, established afterwards that the repair was **unwarranted**
(`failure / unwarranted_repair`; disposition alone decides that, no validator needed).
The sequence to keep everywhere — demo, README, spoken: found the real explanation →
proposed REPAIR anyway → runtime archived it unchecked → frozen-key evaluator scored it
unwarranted. Note the shape of it: the permission was told and recorded, the refusal
happened on the *read* path (turn 7), and the *write* proposal for the same file went
through untouched — declaration and enforcement are separate things in this system, and
this run is the cleanest evidence of it. It shows exactly where the missing control
belongs: before an unchecked repair crosses the action boundary. Lineage: 4B smoke →
R0/R1 → 4.1-mini →
4.1 at 12 turns → 4.1 at 20 turns. Every configuration archived under its own label;
nothing rerun to get a different answer (the smoke pair, runs 2 and 3, is row 12's
deliberate repeat). The run lives on one machine: `01_data/runs/` is ignored by git and
the manifest that attests it is untracked — commit `01_data/runs/MANIFEST.json` and
`--preserve` the archive somewhere kept, or "forever" is a hope.

Two provenances the run creates:

- **The turn bound.** 41-1 (bound 12) hit the bound at turn 12 with the evidence in hand
  and no decision. 41-2 was run at 20 so the bound could not be the reason twice — and it
  decided at turn 11, *within* the old bound, on a trajectory that diverged from 41-1's
  at turn 4 (same incident, world and protocol digests, temperature 0, the same
  fingerprint; the bound is not in the prompt). So the 20 bound was never reached. What
  is established: 12 was insufficient for 41-1's trajectory, and gpt-4.1 at temperature 0
  is not deterministic here. What is not established: that 20 was needed, or is the right
  general bound. The runtime's default stays 12; D-9 is where a bound becomes
  per-configuration and named.
- **The evaluation report's second dimension.** The same category means a different
  system behaviour depending on whether the runtime blocked the repair before action or
  only preserved it: `runtime_validation` (state none / unchecked / checked, accepted,
  checks_run) rides beside the verdict in reports written from here on — additive, for
  the evaluation authority's review; 41-2's report, scored before the field existed, does
  not carry it and is never rewritten — and the page says the same thing beside every
  score, derived from the record's own validation, so it does not depend on the report.
  It is what lets "wrong repairs proposed / blocked before action / left unchecked" be
  counted later, which is more operationally meaningful than accuracy.

A refinement the run forced in the scorer's refusal: an unchecked REPAIR is refused only
where the key also says REPAIR — there the validator's verdict would decide between
success and rejection. Where the key says the right call was not a repair, the disposition
alone decides, no validator is consulted, and the run scores as what it is.

And the scoring comparison the pair makes: the 4B model's shallow NO_REPAIR scored
`success`; the 4.1-mini's investigated, stated, honest abstention scored
`unnecessary_escalation`. Disposition-only scoring rewards the lucky guess over the
reasoned abstention. That sharpens the scoring-semantics finding for the evaluation
authority: a NO_REPAIR should have to name the evidence that makes it one.

`--provider openai` exists behind every rule the plan wrote for it: the receipt before the
first call (unchanged), the credential from the environment and in no artefact, a nominal
price and a cap checked between requests, the endpoint's failures filed as the provider's,
the cost a labelled lower bound. Pre-empted as the spike did, and recorded here so D-6b
can move them: trace row 1 (usage and fingerprint on `model_responded`, null when absent);
provider-side failures in the existing `infrastructure_failure` class, phrased "outside
the model"; the cap enforced in the provider and translated by type in the runtime;
unknown rows derived from the trace by the renderers, the record schema unchanged;
`urllib`, no SDK — D-13's floor job does not apply to this path. Nominal prices are
transcribed by hand in `reporting/ledger.py` and named by table id: **verify them against
the provider's page before spending, and bump the table id.**

The first paid run is a smoke of the paid path — the same standing as the local smoke —
on `revenue-after-deploy`, whose key exists; then `settlement-conflict`, whose R0/R1
this compares against (does a capable model query `processor_settlements`?). The runbook:

```bash
export OPENAI_API_KEY=...                                   # the shell's, never the command line
python -m adii.runtime --incident revenue-after-deploy --provider openai \
    --model gpt-4.1-mini --max-cost-usd 0.25 --label revenue-after-deploy-openai-1
python -m adii.reporting.manifest && python -m adii.reporting.manifest --verify
grep -rl "$OPENAI_API_KEY" 01_data/runs/revenue-after-deploy-openai-1/ ; echo "(no output above = the key is in no artefact)"
python -m adii.evaluation --run revenue-after-deploy-openai-1 --key 02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json
python -m adii.demo                                          # read-only: the paid run's page
```

In the record, check: `configuration.credential` is the name `OPENAI_API_KEY (environment)`;
`api_cost_usd` is a lower bound and the report says "at least"; every `model_responded`
carries `usage` and a `fingerprint`; the receipt's reason names the cap.

## Against the previous system, 17 September

The apple-to-apple the reserve rules allow: our archive against what `docs/inherited/`
transfers of the previous system — requirements, reproduced defects, and one results
table with every symbol, count, model id and cost stripped by design. The old archive
itself does not cross (inheritance rule), and a declassified incident would give a
controlled replication on the same world and truth, never a number to quote beside the
old one (CONTROLS.md, "whose numbers these are").

| | previous system, as transferred | ours, as archived |
|---|---|---|
| world | eight evidence sources — extracts, schemas, transforms, a warehouse, logs — addressed by table / log / transform id | two or three SQL tables per incident; two tools |
| discovery | not recorded | `get_schema()` lists tables; the protocol says begin there |
| bounds | a tool budget with a derived turn budget | turns (12), a paid spend cap; tool calls not bound on the runtime path; no wall clock |
| before action | a per-incident write surface; a rehearsal sandbox documented as structural only; a validator that rebuilt from frozen inputs and rejected a rehearsal-green repair; minted ids, unminted citations rejected | permitted paths told and recorded, enforced nowhere; no validator (every live REPAIR *not checked*); no citation check — one Qwen run cited an id one character off a minted one and nothing noticed; the evidence gate counts a REJECTED result as an observation (`delivery-duplicated-qwen4b-1` submitted REPAIR on one refusal) |
| results | 6 frozen incidents × 3 repeats × 3 arms: always-escalate 2/6, alert-only 6/18, full 18/18, zero false repairs — no variance, no failure taxonomy | 26 live runs, 7 hand-authored incidents, 7 code revisions, 2 protocols, 1 key, 0 control arms, 2 identical pairs; gpt-4.1 diverged at temperature 0 |
| custody | first exposure discarded; archive untracked, unversioned, no sampling configuration | receipt before spend, observed at the model; every response's usage and fingerprint; cost as a priced lower bound; a manifest — and three paid runs whose `source_revision` names a commit that is not the code that ran (a dirty tree), recoverable only because the receipt now carries the protocol's digest |

What the new runs show that the old record could not: a priced lower bound per run; the
credential in no artefact; an unchecked-vs-checked dimension beside the verdict; and a
failure taxonomy — table guessing, protocol-shape collapse, a fabricated premise, an
escalation with the decisive table in view, evidence found then bound, right diagnosis
then REPAIR anyway, an unjustified NO_REPAIR on a conflict — that an 18/18 never produced.

What we are missing that the old system had or paid for, ranked by what it changes:

1. **Gate before action** — a write-path gate (patch keys ⊆ `permitted_write_paths`), an
   evidence gate that counts only OK observations, and M6's first check ("does it
   rebuild"); each a refusal at the boundary with a guard. Changes what every archived
   REPAIR means.
2. **Make the numbers mean something** — D-16 freeze (the model-facing surface's own
   digest, so a run's protocol is provable from the record and a dirty tree cannot hide
   behind a commit hash); a key per incident, authored by the evaluation authority; the
   two control arms (alert-only is one configuration away: the same protocol with no
   tools); D-17 repeats, since one run at temperature 0 is one sample; A's own trace
   carried (row 6). Changes what any score can claim.
3. **Close the world gap** — read what may be written (`get_transform` over exactly the
   permitted paths, an allow-listed id, never a path); logs and transforms as evidence
   sources; then the first declassified incident through the catalogue's sequence.
   Changes what future runs can see.

## Decisions the line waits on

1. **Trace contract rows 1, 5, 6** (`trace_event_contract.md`, "What is genuinely open") —
   the vocabulary, the class of a stop without a decision, where a rejected decision is
   recorded. Everything in rows 1, 2 and 6 of the line is gated here.
2. **The first key.** Which incident (a NO_REPAIR or ESCALATE specimen — a REPAIR cannot
   score `success` until a validator exists), where it lives (`evaluation/fixtures/` is
   the only place a test allows today; `evaluation/catalogue/` is development-catalogue
   row 1, open), in which vocabulary (C's `answer_key.schema.json` v1 is the only one a
   loader accepts; the catalogue proposal's field names differ), and authored by whom
   (not the specimen's author). Recommendation: `revenue-after-deploy`, NO_REPAIR, v1,
   under `fixtures/`, authored by the evaluation authority, labelled a smoke.
3. **An unchecked repair.** Today the scoring command refuses it. The alternative is a
   third state in `scoring_semantics.json` under a new version, which is the authority's
   to ratify. The refusal stands until then.
4. **The spike's standing.** `--provider local` and the launcher reached `main` on 16
   September (PRs #20, #21, #23) ahead of the rows. The docs that said "nothing merges
   before" now say what happened; D-6b replaces the spike in place rather than being
   carved from a branch.
5. **The write-path gate.** R0 archived a REPAIR on an incident with no permitted write
   path. Whether a patch outside `permitted_write_paths` is rejected by the loop (a
   sibling of the evidence gate, `decision_policy.md`), refused by the runtime, or left
   to the validator (M6) decides whether Moment 2 can exist before M6.
6. **Reading what may be written.** `permitted_write_paths` names files the investigator
   can never read; the only tools are `get_schema` and `run_sql`. Whether the world carries
   transform sources as a bounded, allow-listed read (`get_transform(path)` over exactly
   the permitted paths — never a filesystem path argument) is a tool-surface and
   DATA_WORLD decision; without it every REPAIR patch is written blind.
7. **The judge over a local endpoint.** Off the first-run path (reached only by a
   validated REPAIR whose ids differ from the key). The only provider needs the `openai`
   SDK and has no base URL; a stdlib one belongs in `provider/`.

## Seams found on the way, by name

| seam | finding | where |
|---|---|---|
| record → evaluator | every field C reads exists under the same name; C's tests never load a D-written record, so a rename in `to_json` would pass C's suite | `evaluation_report.py`, `tests/eval_authority/test_contract_consistency.py` |
| evaluator → custody | the report was invisible to attest/verify/preserve until its retention class existed | `reporting/manifest.py` (fixed 16 Sep) |
| grounding → trace | `check_grounding` reads `call["tool"]`; the trace's `tool_call` payload carries `name` — KeyError on a real trace | `evaluation/grounding.py:141-161` (optional path; one line, the authority's) |
| receipt ↔ key | `get_receipt_artefact` returns `{kind, path, digest}`; `write_receipt` takes `name → "sha256:…"`; the runtime has no `--key` and the receipt is written before the run | join at scoring time, not at the receipt (D-15's wording) |
| key guard | `test_answer_keys_stay_out` matched only the catalogue's vocabulary; C's field names added | fixed 16 Sep |
| docs | `OVERVIEW.md` names `demo-learning-001.answer.json` and two test files that are not in the tree; `evaluation_report.py` says it has no dependency on the package it lives in | the authority's to reconcile |
| protocol → parser | a closed tag and `patch: null` were rejected as malformed decisions; found by run 1 | `investigator/loop.py` (fixed 16 Sep; the loop's owner reviews) |
| loop → model | a rejected decision is re-asked with no reason fed back; the model repeats itself to the bound | `investigator/loop.py` — the seam's owner; a proposal belongs beside row 6 |
| adapter → trace | A's `decision_rejected` events, with reasons, are discarded (`decision, _ = run(...)`) | `runtime/live.py:51`; contract row 6, then D-6b |
| scoring semantics | a NO_REPAIR scores `success` on disposition alone; runs 2–3 are the case | `evaluation/scoring.py` — the authority's |
| decision → permitted paths | `permitted_write_paths` is told to the model and recorded; nothing enforces it — R0 archived a REPAIR where none was permitted | decision 5 |
| loop → evidence gate | a REJECTED result counts as an observation: `delivery-duplicated-qwen4b-1` submitted REPAIR after one refused request and nothing else; `decision_policy.md` says "observed" | the loop's owner; decision 5's sibling |
| decision → evidence ids | nothing checks a cited id against the minted ones: `shipment-counts-disagree-qwen4b-1` cited `ev-ee53eb377d154e4` for minted `ev-ee53eb377d7154e4` | D-3; contract row 3 |
| runtime → tools | `ToolExecutor.max_calls` is never set on the runtime path; the only bounds are turns and, paid, cost | D-9 |
| record → code | three paid runs carry `source_revision 8ac508e` with the protocol digest of `b09dc48`: a dirty working tree; the receipt's protocol artefact is what makes it recoverable | D-16 |
| protocol → parser | a patch that is not path → text was accepted and crashed both renderers (R0) | `investigator/loop.py`, `reporting/record.py` (fixed 17 Sep, two guards) |
| tool → model | `run_sql` "no such table" did not name the known tables, and R0 built a false premise on it | `tools/database.py` (fixed 17 Sep; the tool layer's owner reviews) |
| context → tools | a permitted write path is named to the model and no tool can read it; three runs (`openai-1`, `41-1`, `41-2`) asked for it and were refused; `41-2` then wrote it blind | decision 6 |
| model → schema | **observed cross-model failure mode:** models guess plausible table names — Qwen `card_processor_settlements` before it had listed the schema, under the protocol that did not ask it to (R0); gpt-4.1 `raw_revenue` inside its patch after the schema had been listed to it, under a protocol that says not to guess (41-2). Two runs are a small sample, not a verdict on the tool layer; the principle stands regardless: when the system already knows the valid namespace, do not rely on the model remembering it (the same lesson as `permitted_write_paths`). Directions, not decided: structured table identifiers from `get_schema`; rejections naming canonical tables (done for "no such table"); table references checked against the known schema before execution | reliability backlog |
| provider → trace | `model_requested` records a message *count*; the system prompt and tool schemas the model was sent are not in the record, so custody holds everything the model saw of the data but not everything it was told | `provider/openai_compatible.py:78-79`; contract row 1 |
