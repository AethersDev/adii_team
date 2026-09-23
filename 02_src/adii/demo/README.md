# The front door: ADII — Is it broken?

**ADII's one page** (final plan, decisions F1–F3 and W). A number looks wrong; ADII answers
*Fix it*, *Leave it* or *Escalate it* — and the AI that proposes a fix can't approve it.
The page is a view over the run archive and, when the operator started the server with a
model, a starter of runs: every run is the same `python -m adii.runtime` the evaluation
scores, so the benchmark and the page are two readers of the same records.

```bash
python -m adii.demo                                                     # read-only → http://127.0.0.1:8000
python -m adii.demo 8000 --provider openai --model gpt-6-sol --reasoning-effort low \
    --max-tokens 4096 --max-cost-usd 0.50 --max-turns 20               # runs from the page, paid, capped
```

No install. No dependencies. Standard library only, and nothing fetched from anywhere but
this server: the fonts (Newsreader, Public Sans, IBM Plex Mono, under the SIL OFL,
`web/fonts/OFL.txt`) and the logo are served from `web/`, so the page runs offline on a
stage. The previous page is archived whole in `03_assets/archive/front-door-v1/`.

## What it shows

**Investigations** — the composer (*What looks wrong?*, CSV files, Investigate), the three
sample incidents of the demo company, and every archived run: what looked wrong, the
answer, what changed, the record and when. An empty workspace opens on the samples.

**One investigation**, in the order a stranger needs it:

1. **The symptom** — the alerted number as a chart, from `alert_observed`: the runtime's
   own reading of the frozen world before anything was investigated. It is what triggered
   the run, labelled so, and never evidence.
2. **The answer** — *Yes. Fix it.*, *No. Leave it.*, *Not yet. Escalate it.*, or how a run
   ended without one — with the investigator's summary, labelled as its words. A REPAIR is
   *Fix it* only when the authorizer allowed it and the validator accepted it; otherwise
   the page says which authority refused it.
3. **How ADII knows** (*What ADII found* for an escalation) — the observations the decision
   cited, and only those, each by a fixed template from its recorded result.
4. For a fix: **Proposed fix**, the patch against the transformation the run observed, and
   **Independent rebuild** — the validator's reading of its own rebuild
   (`ValidationResult.rebuilt_series`) beside the symptom, with each check it ran. A chart
   that recovers is not yet a repair: the checks decide.
5. **Investigated** — everything the run looked at, cited or not, one disclosure down.
6. **Answer, Sign-off, Record** beside it: the three answer slots; who proposed, who
   permitted, who checked; the record's id, its sha256, the receipt, the model and the spend.

## Where each word comes from

`web/view.js` holds every projection from a record to what the page says; `web/app.js`
only draws what it returns, with `createElement` and text nodes. `test_the_front_door_projects.py`
evaluates `view.js` in node over records the real runtime writes — the fix that stands, a
fix the rebuild rejects, a fix outside what may be changed, the real drop, the undecidable
evidence, and every way a run ends without an answer.

## Rules that fail the build

- `test_demo_design_rules.py`: no string ever becomes markup or code; nothing is fetched
  from elsewhere; every font ships with its licence; the logo is the identity handoff's,
  byte for byte (`python 02_src/scripts/sync_identity.py`); the page reads only the record
  shapes it names.
- `test_the_page_executes_nothing.py`: a record with an executing payload in every
  model-written field renders as text in headless Chrome, and every screen fits 1440 and
  390 pixels without horizontal overflow.
- `test_the_product_path_in_a_browser.py`: a sample incident, picked and investigated in
  the browser against a stand-in model, reaches *Yes. Fix it.* through the real authorizer
  and validator; a visitor's own CSV reaches its answer; and the record the page drew is the
  archive's, by its digest.

Locally the browser tests skip without Chrome; on CI they must run.

## What it is not

- **Not an authority.** It decides no answer, admits no change and executes nothing.
- **Not a place to raise what a run may cost.** It starts runs only within what the
  operator set at the terminal — provider, model, cap, turns, effort — with the credential
  in the server's environment, never in the page's hands.
- **Not the implementation.** Nothing in `02_src/adii/` may import it.

## API

```
GET /api/runs              one row per archived run, newest first — the alert, the answer,
                           the files changed and whether the change was admissible; an
                           unreadable record, or a run that never finished, is listed with
                           its error, never hidden
GET /api/runs/{label}      the record, verbatim
GET /api/runs/{label}/trace     the live trace of a run in progress, whether it finished, and
                           whether its receipt was written
GET /api/runs/{label}/evaluation   the evaluation authority's report, verbatim, once scored
GET /api/incidents         the incidents a run can be started on; the demo company's are
                           samples, each with its alerted series
GET /api/launch            whether runs may be started from the page, and against what
POST /api/runs             start a run on an incident the archive knows — only when the
                           server was started with --model (403), on an incident it knows
                           (400), one at a time (409); {incident, model?, max_turns?,
                           max_cost_usd?}
POST /api/investigations   start a run on the visitor's own incident: {description, files:
                           [{name, text}], …} — the description is the alert, each CSV a
                           table (tools/user_world.py); the body is limited to 12 MB
POST /api/runs/{label}/feedback   record an operator's feedback beside the record
```

Every write takes a JSON object declared as `application/json` and answers 400 to anything
else. Every response carries `ADII-Code`, the newest change to the page's files; a tab whose
script is older reloads itself once. Routes are the URL hash: `#` the investigations,
`#r/<label>` one run.

## Verify

```bash
python -m pytest 02_src/tests -k "record or inspector or design or front_door or executes or product"
```
