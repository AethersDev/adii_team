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
python -m adii.demo 8000 --provider openai --model gpt-6-sol --models gpt-6-luna gpt-4.1 \
    --reasoning-effort low --max-tokens 4096 --max-cost-usd 0.50       # …and the page may pick a model
```

No install. No dependencies. Standard library only, and nothing fetched from anywhere but
this server: the fonts (Newsreader, Public Sans, IBM Plex Mono, under the SIL OFL,
`web/fonts/OFL.txt`) and the logo are served from `web/`, so the page runs offline on a
stage.

## What it shows

**Home** — like a chat app's first screen: the mark alone, the question *What looks wrong
in your data?*, and one composer — the number in words, a paperclip for CSV files, the model
button and the send button — with three neutral sample chips beneath. The model button names
the model the next run will use and opens a menu of the ones the operator offered, the
default marked; the page picks among them and never beyond. The word ADII lives alone at the
top of the sidebar, the mark alone on home: each is learnt by itself. **The sidebar** holds past investigations the
way a chat app holds past conversations — titles and times, never answers, so it can stay
open in a room — and closes to a rail of its three actions (open, new, settings); on a
phone it slides over the page. **Settings**, at its foot, shows what the operator started
the server with — model, effort, cost cap, turns, tool calls, time — read-only, and two
choices kept in this browser: open the investigation's steps by default, and keep the mark
still.

**The mark, alive.** The identity's symbol, drawn from its own geometry and unchanged in
shape: at rest its unfilled slot breathes, slowly — evidence not yet in; while ADII
investigates, the three slots rise in turn; with an answer it is still. The system's
reduced-motion setting always stops it, as does *Keep the mark still*.

**One investigation, as a conversation.** Send, and the page stays a chat: what was asked
sits on the right, and ADII's reply grows beneath it.

1. **While it works** — one line, *Investigating · 12s · turn 3 of 20*, the seconds counted
   from the moment in the run's label, so a reload keeps the clock. The line opens to the
   steps as they happen, folded like a model's thinking.
2. **The answer** — *Yes. Fix it.*, *No. Leave it.*, *Not yet. Escalate it.*, or how a run
   ended without one — with the investigator's summary, labelled as its words, and above it
   *Investigated for 46s · 15 steps*, which opens to every step the run took. A REPAIR is
   *Fix it* only when the authorizer allowed it and the validator accepted it; otherwise
   the page says which authority refused it.
3. **Show details** — everything behind the answer, one click away and closed by default:
   the symptom as a chart, from `alert_observed` (what triggered the run, labelled so, never
   evidence); **How ADII knows**, the observations the decision cited and only those; for a
   fix, the **Proposed fix** and the **Independent rebuild** — the validator's reading of its
   own rebuild (`ValidationResult.rebuilt_series`) with each check it ran; then the three
   answer slots, **Sign-off** (who proposed, who permitted, who checked) and the **Record**
   (id, sha256, receipt, model, spend).

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
  operator set at the terminal — provider, cap, turns, effort, and the models it may pick
  among (`--model`, plus `--models`, each priced and checked as the first is) — with the
  credential in the server's environment, never in the page's hands. An effort reaches only
  a reasoning model; gpt-4.1 runs with a temperature.
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
GET /api/incidents         the incidents the page may name; the demo company's are samples
GET /api/launch            whether runs may be started from the page, and the server's settings
POST /api/runs             start a run on a sample or the walkthrough — never a benchmark or
                           held-out case — only when the server was started with --model
                           (403), one at a time (409); {incident, model?} — a model the
                           operator did not offer is 400; nothing else is read
POST /api/investigations   start a run on the visitor's own incident: {description, files:
                           [{name, text}], model?} — the description is the alert, each CSV a table
                           (tools/user_world.py); the body is limited to 12 MB
```

Every write takes a strict JSON object declared as `application/json` and answers 400 to
anything else, NaN and Infinity included. Every response carries `ADII-Code`, the newest
change to the page's files; a tab whose script is older reloads itself once. Routes are the
URL hash: `#` home, `#r/<label>` one investigation.

## Verify

```bash
python -m pytest 02_src/tests -k "record or inspector or design or front_door or executes or product"
```
