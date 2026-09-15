# The run inspector

**Read-only over the run archive.** Every run the runtime archives appears here: the trace,
the decision, the verdict, what it cost, and where the record came from.

```bash
python -m adii.runtime --incident demo-learning-001 --provider fake   # produce and archive one run
python -m adii.demo                                                     # → http://127.0.0.1:8000
```

No install. No dependencies. Standard library only.

## What it renders, and for whom

Three screens, for someone who did not build ADII. The front door opens on the incidents:
what ADII is, one card per incident with the alert in the operator's words, how many runs,
and the latest outcome with exactly the authority it has — a run with no decision says so,
and is never drawn as a failure or a success. An incident's page lists every run of it,
newest first, each ended in its own way; nothing nominates the newest as the best. A run's
page reads top to bottom in a fixed order: what was reported, how the run ended, what the
investigator did, what it decided or why there is no decision, what the validator said,
and, closed by default, the technical details. A section the record cannot fill is left
out, never drawn empty. Two runs of one incident can be put side by side.

Exactly one shape: `adii.run_record/v1`, defined in
[../reporting/record.py](../reporting/record.py). A record in any other shape gets a
contract-mismatch state, never a guess, and the page invents no field — if it is on
screen, it is in the record, or it is one of the sentences below.

The page cannot start a run, because a page that can start a run can spend money. It says
so, and it shows the command that does, on every screen.

## Every sentence the page adds

Everything the page says beyond quoting the record lives in `web/phrasing.js`, and each
entry is a deterministic projection of record fields: it composes what the record states
and adds no cause, no judgement and no guess. `test_phrasing.py` pins every entry against
the committed records, and fails on words such as "could not" or "insufficient" unless the
record contains them. Strike any line below and the page stops saying it.

| entry | sentence, from these fields |
|---|---|
| `submitted` | "The investigator committed to *disposition*." |
| `bound_hit` | "The investigator reached a bound it set after *tool_calls* tool calls and stopped without a decision." |
| `model_failure` | "The model failed and the run stopped without a decision." |
| `infrastructure_failure` | "Something in the runtime failed — a defect of ours, not the model's — and the run stopped without a decision." |
| the record's `detail` | always shown beside the sentence, verbatim, so the projection never replaces the source |
| `accepted` / `rejected` | "The validator rebuilt from frozen inputs and accepted (rejected) the repair." |
| `notInvoked` | "No repair was proposed, so there was nothing to validate." — only a REPAIR carries a repair, and the record refuses a verdict without one |
| a run with no decision | no validation section is drawn at all; "Why there is no decision" says the run ended first, which the record's own invariant establishes: it refuses a verdict without a decision |
| `incident_received` | "The investigator received incident *id*." |
| `tool_call` | "It asked the tool layer to run *name* with *arguments*." |
| `tool_result` | "The tool layer answered / refused / rejected the arguments to *name*", with the row or column count, or the error, quoted |
| `decision_submitted` | "The investigator committed to *disposition*." |
| `validation_completed` | "The validator accepted (rejected) the repair." |
| product copy | what ADII is, that the page is read-only, and the commands that create a run or the six specimens — UI text about the product, never about a particular run |
| `scripted` | "Scripted investigator · development demonstration, not a model result" — shown on every run and counted on every incident card whose record has `configuration.model` null, so a screenshot can never pass for a model result |

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

Every step sentence is reversible to its event: the raw payload sits under a disclosure
beside it, so the prose can never become a second source of truth.

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

- **Not a launcher.** Runs start from the command line. A page that can start a run can
  spend money and create a first exposure without a receipt, so this one cannot.
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
```

Routes are the URL hash: `#` the incidents, `#i/<incident>` one incident's runs,
`#r/<label>` one run, `#r/<label>,<label>` two runs of one incident side by side.

## Verify

```bash
python -m pytest 02_src/tests -k "record or inspector or design or walkthrough or executes"
```
