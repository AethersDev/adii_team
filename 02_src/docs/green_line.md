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
| 9 | a score and a report exist for a run the real investigator produced | the sequence below, steps 4–6 | ✗ no frozen key exists for any incident the runtime can investigate |
| 10 | the page renders the same archived truth, the evaluation included | `test_the_page_executes_nothing.py`, `test_the_product_path_in_a_browser.py`; D-19 | partial: record, trace, receipt, feedback rendered; the evaluation report is not yet served or shown |
| 11 | the full suite and the guard pass are green on three operating systems | CI: `test` matrix + `guards` job; 32 registered guards | ✔ |
| 12 | a second run of the same incident reveals no hidden state | run the sequence twice; compare the two records' shapes, the manifest, the page | ✗ not yet attempted |

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

# 4  DECIDE: the incident and its key — see "Decisions" below

# 5  BUILD (the evaluation authority): author the key, freeze it, commit both files
#    02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json  +  .sha256
python -c "from pathlib import Path; from adii.evaluation.freeze import freeze_answer_key; \
           print(freeze_answer_key(Path('02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json')))"

# 6  the score, beside the record (exists)
python -m adii.evaluation --run <label from step 2> --key 02_src/adii/evaluation/fixtures/revenue-after-deploy.answer.json

# 7  BUILD (D-19): the page serves and shows evaluation_report.json; the text report names the category

# 8  run steps 2, 3 and 6 again on the same incident — row 12
```

What the first scored run may be called is fixed before it runs: a **public_development
smoke of the scoring path, no evaluation claim** — the specimens carry none
(`examples/specimens.py`), and a number reported against an incident freezes it
(`DATA_WORLD_v0.md`, "what is frozen"). It is never quoted as an ADII result.

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
