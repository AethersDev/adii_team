# The page: investigate, watch, read, answer

**ADII's one page.** Its first screen is the action — pick an incident, Investigate — when
the operator started the server with a local model; below it, the investigation history:
every run the runtime archived, with the trace, the decision, the verdict, what it cost,
and where the record came from. Without a model the page is read-only over that history.

```bash
python -m adii.runtime --incident demo-learning-001 --provider scripted   # produce and archive one run
python -m adii.demo                                                     # → http://127.0.0.1:8000
```

No install. No dependencies. Standard library only.

## What it renders, and for whom

Three screens, for someone who did not build ADII. The front door opens on what ADII is
and, when the operator started the server with a model, on the action: pick an incident,
Investigate, with one line saying what it runs with and whether something is running now.
Below that, the investigation history: one card per incident with the alert in the
operator's words, how many runs, and the latest outcome with exactly the authority it has
— a run with no decision says so, and is never drawn as a failure or a success. An
incident's page lists every run of it, newest first; nothing nominates the newest as the
best. A run's
page reads top to bottom in a fixed order: what was reported, how the run ended, what the
investigator did, what it decided or why there is no decision, what the validator said,
and, closed by default, the technical details. A section the record cannot fill is left
out, never drawn empty. Two runs of one incident can be put side by side.

Exactly one shape: `adii.run_record/v1`, defined in
[../reporting/record.py](../reporting/record.py). A record in any other shape gets a
contract-mismatch state, never a guess, and the page invents no field — if it is on
screen, it is in the record, or it is one of the sentences below.

## Starting a run from the page

Read-only by default: the page cannot start a run, because a page that can start a run can
spend money and create a first exposure. The operator lifts that for one kind of run only:

```bash
python -m adii.demo 8000 --endpoint http://127.0.0.1:8090/v1 --model <id> --served-as default_model
```

Started this way, every screen offers **Investigate**: pick an
incident, and the server reserves a label, writes the receipt, and runs A's loop against
that model — a local endpoint, nothing spent — while the page shows every step as the
runtime records it, then the record when it lands. The two concerns that made the page
read-only are met structurally: only a local endpoint is accepted, checked when the server
starts, and the receipt precedes the investigator. No paid provider is reachable from the
page. This amends rule 12 of the design system in writing, as that rule requires: the
page may start a run only against a local model the operator configured, never otherwise.
One run at a time: while the archive shows one running, a second is refused (409). A run
that has written nothing for three minutes is shown as one that did not finish, and the
page stops watching it.

Without a model the page says how to start one, and shows the commands that create runs.
Every screen's footer says which of the two the page is.

## Feedback on a run

Every finished run's page ends with **Your feedback**: was it useful, what did you expect
or miss, and optionally who you are. It is appended to `feedback.jsonl` beside the record,
attributed, bounded in length, and shown back on the page verbatim as text. It is the one
write a read-only inspector accepts: it spends nothing and asserts nothing about the run —
it is the operator's word, labelled as the operator's. `GET /api/runs/{label}/feedback`
lists it; `POST` the same path with `{"useful": "yes"|"partly"|"no", "expected": …, "by": …}`
records it.

## Every sentence the page adds

Everything the page says beyond quoting the record lives in `web/phrasing.js`, and each
entry is a deterministic projection of record fields: it composes what the record states
and adds no cause, no judgement and no guess. `test_phrasing.py` pins every entry against
the committed records, and fails on words such as "could not" or "insufficient" unless the
record contains them. Strike any line below and the page stops saying it.

| entry | sentence, from these fields |
|---|---|
| `submitted` | "The investigator committed to *disposition*." |
| `bound_hit` | "The investigator reached a bound it set after *model_turns* model turns and *tool_calls* tool calls, and stopped without a decision." |
| `model_failure` | "The model failed and the run stopped without a decision." |
| `infrastructure_failure` | "Something outside the model failed — the runtime or the provider, not the model's — and the run stopped without a decision." — a refused status, an unreachable endpoint or a timeout is the provider's failure, never filed as the model's (inherited D14) |
| the record's `detail` | always shown beside the sentence, verbatim, so the projection never replaces the source |
| `accepted` / `rejected` / `unchecked` | "The validator accepted the repair." / "The validator did not accept the repair." / "No validator checked the repair." — what `accepted` and `checks_run` state and nothing about how; the validator's own report sits beside it |
| `notInvoked` | "No repair was proposed, so there was nothing to validate." — only a REPAIR carries a repair, and the record refuses a verdict without one |
| a run with no decision | no validation section is drawn at all; "Why there is no decision" says the run ended first, which the record's own invariant establishes: it refuses a verdict without a decision |
| `verdict` | "accepted by the validator" when `accepted`; "not accepted by the validator" when not, after checks; "not checked by a validator" when `checks_run` is empty — the record's placeholder verdict disclaims any finding, and the page never turns it into one |
| `headline` per termination | "Decided: *disposition* — *verdict*", "Stopped at its limit, no decision", "Stopped: the model failed, no decision", "Stopped: a failure outside the model, no decision" — the page's first line, from the same fields; the same words label every list and card (`outcome`) |
| `cost` | for a paid run (`configuration.provider` openai) "at least $*x*" — the ledger's lower bound, proved usage at nominal prices — "(*n* request(s) without usage)" when any request could not be priced, never $0 (inherited D15); otherwise the recorded cost as recorded, or "nothing spent (no paid provider)" when it is zero |
| `asked` | "Asked the tool layer to run *name* with *arguments*" |
| `answered` | "The tool layer answered with *n* rows / columns", "refused: *error*", "rejected the arguments: *error*", "failed: *error* — a defect of ours" — the tool layer's own status, quoted |
| `wrote` | "The model wrote, instead of acting:" followed by its words, verbatim, as text |
| `decided` / `validated` | "Committed to *disposition*", "The validator accepted (did not accept) the repair", "No validator checked the repair" |
| `unanswered` | "The run ended before this call was answered" |
| product copy | what ADII is; the launcher's context (the model it runs with, one at a time; whether something is running now, from the list the page loaded); the history count; the footers (read-only, or what runs here — and that nothing is sent to an outside service); the commands that create a run or the six specimens — UI text about the product, never about a particular run |
| `scripted` | "Scripted investigator · development demonstration, not a model result" — shown on every run and counted on every incident card whose record has `configuration.model` null, so a screenshot can never pass for a model result |
| `runtime` | beside the score, orthogonal to it, from the record's own `validation`: "no repair was proposed, so nothing was checked" / "the repair was archived unchecked — not blocked; the score found it afterwards" / "the validator checked the repair before this score, and accepted (did not accept) it" — the same category means a different system behaviour depending on which, and the page never lets the score imply the runtime blocked anything |
| `success` / `correct_abstention` / `unnecessary_escalation` / `false_repair` / `repair_rejection` / `failure` / `not_evaluable` | one sentence per category the evaluation authority may score — "The decision matched the answer key.", "The decision to escalate matched the answer key.", "The decision escalated where the answer key names a call.", "A repair was proposed for a root cause the answer key does not name.", "The repair named the answer key's root cause and was not accepted by the validator.", "The decision did not match the answer key.", "No decision was submitted, so there was nothing to score." — from `evaluation/outcome_classification.py`'s definitions; the category, verdict and who settled it are shown beside it, verbatim from `evaluation_report.json` |

## Development specimens

`python -m adii.examples.specimens` archives six hand-authored incidents with ten scripted
runs — restore what is missing, remove what is duplicated, fix a wrong relationship, a
legitimate change, evidence that cannot settle it, an action that is not ADII's to take —
and the endings a real archive holds: a bound, a rejected repair, a failed tool, a failed
model. They exist so the interface can be designed and tested against something that looks
like a product. Every run goes through the real runtime over the real tool layer; every
record is the same `adii.run_record/v1` a live run writes; every record says it was scripted.
They carry no evaluation claim and are not the development catalogue proposed in
[docs/development_catalog.md](../../docs/development_catalog.md), which is compiled from
private material under a decision record. See `02_src/adii/examples/specimens.py`.

The investigation is shown turn by turn: each model request and everything it caused, or,
with no model, each tool call and its answer. Every turn is reversible to its events: the
raw events sit under a disclosure beside it, so the prose can never become a second source
of truth.

## The design system

The page is built on the identity handoff in [`03_assets/identity/`](../../../03_assets/identity/):
its `tokens.css`, `base.css` and `components.css` are copied here by
`python 02_src/scripts/sync_identity.py`, and a test fails the build when the copy differs
from the handoff by a byte. `inspector.css` adds only layout — the run list, the trace, the
comparison — and introduces no colour. Dark is the default, set on `<html>` at render time;
violet means interactive and nothing else. The rules the handoff states in prose are tests
here: dispositions are peers, verdict colour appears only in the validator's row, absence
and endings are achromatic, and nothing a model wrote is ever parsed as markup.

## Compare

Every run of an incident but the latest offers "Compare with latest", which draws both
records side by side, each by the same renderer over its own record — how two models get
tested against each other.

## What it is not

- **Not a launcher for anything that costs money.** A page that can reach a paid provider
  can spend money and create a first exposure without a receipt, so this one reaches none:
  it starts runs only against a local model the operator named when starting the server,
  and otherwise runs start from the command line.
- **Not the implementation.** Nothing in `02_src/adii/` may import it, and a test enforces
  that. It shows what the runtime produced; it produces nothing.

## Two devices that carry the argument

**The three dispositions are peers.** One glyph each, built from the symbol, and three
hues held at the same lightness so no one of them can shout, with the literal token as
text. If ESCALATE were quieter than REPAIR, the page would silently argue that abstaining
is a degraded outcome, which is the opposite of ADII's claim.

**Valence belongs only to whoever is entitled to it.** Dispositions are never coloured
right or wrong. Pass and fail colour appear in exactly one place: the validator's ACCEPT
and REJECT row, a correctness judgement made by an authority entitled to make it. How a
run ended is achromatic, because it is the loop's report and nobody's verdict.

These are rules, not taste: `02_src/tests/integration/test_demo_design_rules.py` fails the
build when a disposition colour is spent as a success colour, a verdict colour leaks out of
its scope, a token is used without being declared, or the script assembles HTML from
strings. And `test_the_page_executes_nothing.py` drives the shipped page in headless Chrome
with a record whose every model-written field carries a payload that executes on parse: it
has to appear as text, and the page's own title has to survive. Locally it skips without
Chrome; on CI it must run.

## API

```
GET /api/runs              one row per archived run, newest first; an unreadable record, or a
                           label reserved by a run that never finished, is listed with its
                           error, never hidden
GET /api/runs/{label}      the record, verbatim
GET /api/runs/{label}/trace     the live trace of a run in progress, whether it finished, and
                           whether it is still running
GET /api/runs/{label}/evaluation   the evaluation authority's report, verbatim, once the run
                           has been scored (python -m adii.evaluation); 404 until then
GET /api/incidents         the incidents a run can be started on
GET /api/launch            whether runs may be started from the page, and against what
POST /api/runs             start a run — only when the server was started with --model (403),
                           on an incident it knows (400), one at a time (409)
POST /api/runs/{label}/feedback   record an operator's feedback beside the record
```

Both writes take a JSON object declared as `application/json` and answer 400 to anything
else — which is the shape a form on some other site would arrive in. Every response
carries `ADII-Code`, the newest change to the page's files; a tab whose script is older
reloads itself once, so an open tab never runs stale code over a current archive.

Routes are the URL hash: `#` the front door, `#i/<incident>` one incident's runs,
`#r/<label>` one run, `#r/<label>,<label>` two runs of one incident side by side.

## Verify

```bash
python -m pytest 02_src/tests -k "record or inspector or design or walkthrough or executes or product"
```
