# Release evidence — what ADII has earned the right to claim

**Written 21 September 2026, from a seven-phase adversarial review of the tree at that
date, corrected on the advisor's review the same day; the gates re-sequenced that evening
so that the decisive test pack, not a single paid run, is the event the paid model is
used for. This page is the decision, not the review: it holds the surviving thesis, the
release ladder, the claim boundary, what is
demonstrated, what is missing, the gates in order and the falsification condition. It is
updated when a gate passes, never rewritten to look as if it had always held the answer.
The seven review artefacts are supporting material outside the repository; they may be
preserved under a research archive later if the team decides they are worth keeping.**

## 1. The thesis

ADII is a harness that makes an LLM agent's investigation of a data incident bounded,
receipted and attributable by construction: the agent reaches the world only through
tools that can refuse, must end in one of three structured dispositions, and its costs,
counters, record and score are produced by code it cannot influence or import — so no
repair it proposes is ever accepted on its own word. Acceptance by an independent rebuild
exists for one world and is not yet on the live path. No claim of accuracy,
generalisation, safety or usefulness is made until a blind run with control arms has
been scored.

In one line: the model does not need to be trusted for the system to know what it may
legitimately conclude or do. Today only some of the authorities that decide that are on
the live path, and this page says which.

## 2. The release ladder

One word, five meanings, kept apart. The state is the state on the date above.

| level | what exists | may claim | may not claim | state |
|---|---|---|---|---|
| **DEMO** | the page over the archive; six hand-authored specimens with scripted runs; local-model runs; the gpt-4.1 run `revenue-after-deploy-openai-41-2` | an investigating agent that reaches data only through refusing tools, ends in one of three structured dispositions, and leaves a receipt, a trace and a record for every run; a repair it proposes is applied by no one and, on live runs, checked by no one yet | validation of live repairs; enforcement of permitted paths; accuracy; that the examples' verdicts came from the validator | **LIMITED RELEASE** — gates 0A and 0B landed 21 September (CI green, merged); the page no longer attributes a preset verdict to the validator |
| **DEVELOPMENT** | runtime, provider, the validator on one world (tests), the scoring command, one frozen key, the guard registry | the mechanism runs end to end on development incidents with a computed verdict on at least one | any rate, generalisation or model comparison | **HOLD** until Gate 1 and the development keys |
| **EVALUATED** | the category machinery, scoring semantics v1, the checked/unchecked dimension; no arms, no repeats | on N development incidents under a frozen protocol, the full investigator's scorecard against always-escalate and alert-only, with repeats, including where it loses | unseen performance; that one model beats another unless run on the same frozen cases, protocol, scorer and repetition policy | **HOLD** until B0 exists and P1 re-runs its exact protocol |
| **UNSEEN-EVALUATED** | freeze, versioning and reserve-commitment machinery, dormant | one blind, one-shot run on custodian-compiled incidents the team never saw, scored by frozen code, all six categories reported | anything beyond that run's N | **HOLD** |
| **DOMAIN / CUSTOMER** | the CSV front door and `--incident-dir` packages; no customer, connector or permission model | nothing about usefulness | usefulness, market, price | **HOLD**; hypotheses only |

## 3. The claim boundary — what must not be said

- That ADII validates live repairs, or that "any repair it proposes is validated by a
  separate authority" (the README's line; false on the live path today).
- That it refuses unjustified action. It records it: `settlement-conflict-R0` archived a
  REPAIR with no permitted path; `41-2` rewrote a permitted file it had been refused.
  `permitted_write_paths` is told to the model and enforced by nothing.
- Any accuracy, generalisation or safety figure. One key; seven hand-authored incidents;
  zero control arms; zero repeats.
- That the examples' verdicts are the validator's. Every ACCEPT and REJECT in the archive
  is a scripted preset; every model-produced REPAIR is `not checked`.
- That the one frozen key is independent truth: it was written by the runtime's author
  from the specimen's own scripted truth, and says so.
- That the canonical A/B/C world or the development catalogue exists.
- That cost figures are totals. They are lower bounds with the unknown count beside them.
- That the predecessor's results (18/18) are ours. A test enforces the label.
- Anything about customers, market, novelty or IP. Nothing proprietary was found.
- Until the preserved archive is somewhere another reviewer can open it (21 Sep: a second
  copy on the same machine, verified): that any run-based claim has been verified by anyone
  but its author.

## 4. Evidence demonstrated

- **Boundaries as build-failing tests**: no `sqlite3`, `subprocess`, `urllib` or `open()`
  outside the tool layer's allow-list; the investigator never imports validation or
  evaluation; key-shaped JSON only under the evaluation package; nothing imports the demo.
- **119 guards killed** on three operating systems: every refusal, bound and validation
  in the code is demonstrated by a test that fails when it is removed.
- **Receipt before the first model request**, observed at the endpoint by a test, not
  inferred; every archived run has one.
- **The hard cost cap** by exact worst-case admission and unknown usage never counted as
  zero — proved against a fake endpoint; on the real provider, five paid runs with
  proved lower bounds and three refusals classified and charged as unknown. The cap has
  never bound a real request; every live bound hit was on turns.
- **Every ending classified**: 48 archived runs across nine code revisions, each one of
  four terminations, each with receipt, trace and record.
- **In the deterministic/test runtime path**, the independent validator accepts and
  rejects on the one rebuildable teaching world, through `run_incident`, with no input
  through which a rehearsal claim could arrive.
- **Five evaluation reports** from the runtime's own record against one frozen
  development key, including an unwarranted repair by gpt-4.1 and an unnecessary
  escalation by gpt-4.1-mini.
- **A failure taxonomy** of 21 seams from 26 live runs, at least seven closed with guards.
- **A negative result**: disposition-only scoring rewarded an unearned NO_REPAIR (two
  4B runs scored `success` without querying the decisive table, while a reasoned
  escalation scored `unnecessary_escalation`). Correct label ≠ correct investigation. It
  is why the evaluation eventually needs disposition correctness plus decisive evidence,
  grounding, authority and validation where applicable. Preserve it.
- **The development archive census** of 21 September — terminations, dispositions,
  validation states, authorization violations, tool statuses, bound names, provider
  failures, costs, latencies over 48 runs and nine revisions — is pre-registration
  evidence that informs the B0 experiment. It is not the experiment and is never
  reported as one.

## 5. Evidence missing

- A model-generated REPAIR receiving a computed verdict through the live runtime path in
  an archived run. The live path wires `NoValidatorYet`.
- Any key authored by the evaluation authority; any frozen ESCALATE key.
- Any control arm (always-escalate; alert-only: same model, same protocol, zero tools).
- Any repeat; any frozen protocol digest; any unseen material.
- A citation check: the decision has no evidence field; one run cited an id one character
  off a minted one and nothing noticed.
- Enforcement of `permitted_write_paths`; an evidence gate that counts only answered
  requests (today a refused request satisfies it).
- Custody: the exact messages sent are not in the record (a count is); three paid runs
  carry a source revision that is not the code that ran; the archive is on one machine.
- Three records of 16 September carry `model_failure` for a connection refusal to the
  local endpoint — misfiled by the code of that day, preserved because labels are.

## 6. The gates, in order

Nothing evaluated runs against an architecture that is still changing, and nothing about
presentation changes before the evidence it describes is preserved.

```text
0A  PRESERVE THE EVIDENCE      done 21 Sep — archive available to another reviewer; manifest
                               re-attested and verified; historical runs immutable; the three
                               misfiled records annotated beside the record, never rewritten
0B  DEMO TRUTHFULNESS          done 21 Sep — scripted, model and computed verdicts visibly
                               distinguished;
                               "may write" labelled as declared, not enforced; the key
                               labelled a team-authored development key; refusals counted;
                               no page implies validator authority where none existed
1   M7 VALIDATION INTEGRATION  the validator on the live path (m7_validation_integration.md,
                               four rows marked, eight items); evidence gate on answered
                               requests only; the first archived model-generated REPAIR
                               with a computed ACCEPT, REJECT or NOT_CHECKABLE
2   D-1 AND AUTHORIZATION      the canonical trace representation decided; authorization
                               recorded as its own fact, admission derived — before another
                               generation of records that cannot express permission
3   GROUNDING / CITATIONS      evidence_refs on the decision, resolved against minted ids
                               where the record is built; grounding predicates for the keys
4   CANONICAL WORLD            configuration A first — source → transform → mart, readable
                               through the package surface, rebuildable with a candidate
                               patch substituted — then B and C on the same schema and alert
                               with the same permitted paths; development keys for all three
5   DECISIVE PROTOCOL FROZEN   DECISIVE_TESTS_v0.md: model, prompt, tools, bounds, worlds,
                               keys, repeats, code — one identity, in every receipt
6   DECISIVE TESTS             D1–D5 on the local model as rehearsal, then --check,
                               --check --spend, and the pack once on the paid model; the
                               pack is the event, the paid run only the model it runs on
7   B0                         protocol frozen, then always-escalate · alert-only · full ADII,
                               same cases × repeats; failure taxonomy from its records
8   P1                         grounded NO_REPAIR/ESCALATE semantics (v2, ratified); the
                               write-path decision; re-run on the EXACT B0 protocol; must
                               reduce false REPAIR and unnecessary escalation without
                               reducing correct ESCALATE
9   M9 FREEZE                  model-facing surface digest in every receipt; scorer and
                               validator frozen; reserve commitment before any declassified
                               incident
10  M10 UNSEEN                 custodian ≠ runner; commit before exposure; one shot; three arms
11  HIGHER RELEASE LEVEL       EVALUATED or UNSEEN-EVALUATED, with the scorecard — or HOLD
```

Two kinds of key, never called by one name:

```text
DEVELOPMENT KEYS   evaluation-authority authored · frozen before the evaluated runs
UNSEEN KEYS        custody-controlled · inaccessible before the run · different custodian
```

Demo and frontend work may progress around gates 1–4, provided nothing changes a frozen
protocol after it is registered. The first paid run is not a smoke: the paid path has
been exercised by five runs, three refusals, fault injection and the guard pass; the
new key is scarce evidence and is spent on the decisive pack
([DECISIVE_TESTS_v0.md](DECISIVE_TESTS_v0.md)) against the world we intend to present.
The capstone (18 October 2026) ships at DEMO, limited, with gate 1 if it has landed; M10
is not needed for that.

## 7. The falsification condition

- **Custody**: one live run in which the record disagrees with what happened — a model
  request before the receipt exists, a tool result that reached the model without landing
  in the trace, a bill above the cap, a credential in any artefact. Tests assert each; a
  live counterexample kills the clause outright.
- **Acceptance**: if, once the validator is generalised and wired, every rebuildable
  incident still requires hand-coding its answer into the validator, the clause is dropped
  and the thesis becomes custody, bounds and after-the-fact evaluation only.
- **The product argument**: if, with development keys, repeats and the alert-only arm, the
  full investigator does not beat alert-only, then investigation does not convert blanket
  abstention into correct action or non-action, and ADII is an audit harness, not an
  investigator worth deploying.

The one experiment that tests all three is the first unseen run with the two arms and a
live validator. Until it runs, the thesis is stated so that none of the three is assumed.

Related: [build_plan.md](build_plan.md) (milestone marks), [green_line.md](green_line.md)
(the integration backlog and the runs cited above),
[m7_validation_integration.md](m7_validation_integration.md) (gate 1's decision record),
[inherited/CONTROLS.md](inherited/CONTROLS.md) (why the arms exist and whose numbers the
predecessor's are).
