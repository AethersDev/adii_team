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
| 4 | hard bounds — turns, tool calls, wall clock — each named in the `bound_hit` it causes | D-9 `Budget`; the page's one-at-a-time gate | partial: turns and tool calls bound; no wall clock, so a stalled model holds the slot up to 12 × 120 s |
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
5. **The judge over a local endpoint.** Off the first-run path (reached only by a
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
| provider → trace | `model_requested` records a message *count*; the system prompt and tool schemas the model was sent are not in the record, so custody holds everything the model saw of the data but not everything it was told | `provider/openai_compatible.py:78-79`; contract row 1 |
