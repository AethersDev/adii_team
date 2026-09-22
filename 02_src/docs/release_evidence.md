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

## 6. The line to the submission — revised 22 September (evening)

The prototype has served its purpose: it told us what to build. From here the project
closes the product rather than hardening the prototype. Sacred: frozen evaluation
evidence stays historically true, archived runs are never rewritten, a scored protocol is
never changed silently. Not sacred: the current page, the specimen layout, the demo
narrative, development fixtures — all replaceable by the final system. Run 2 is no longer
a milestone; a development run is a development run. The milestone is:

```text
FINAL ADII → FROZEN → FRESH CONTROLLED EVALUATION → FINAL RESULTS
           → FINAL PRODUCT → PRESENTATION + FILM
```

One straight line, 22 September to 18 October, by unit and dependency:

```text
1  FINISH ADII                         no cosmetic work except what operating the system needs
   1a  row 6 — an invalid submission (any form that is not <TOOL_CALL>, <DECISION>, <STOP>)
       is a durable decision_rejected event with a class and a bounded reason, the reason
       returned to the model once, no special case for any tag; the investigator emits
       into the runtime's recorder as it runs — one history, no second trace translated
       or discarded                                                     (decided; build)
   1b  m7 rows 3–4 — reason_code, NOT_CHECKABLE, the closed state space; the authorization
       fact recorded by the runtime, admission derived    (marks recorded, then the contract)
   1c  grounding — evidence_refs on the decision, resolved against minted ids where the
       record is built; unresolved refs rejected                       (contract row 3)
   1d  trace rows 1 and 5 — the canonical vocabulary; the class of a stop without a decision
   1e  the validator beyond one world — rebuild from an incident's own build script and
       transform, checks declared per incident, so a REPAIR on any development case can
       be ACCEPT or REJECT, not only NOT_CHECKABLE
   1f  CI cost — Ubuntu and Windows on pull requests, macOS and the guard pass on main
2  THE FINAL DEVELOPMENT SET          the six geometries, expressed under the final contracts:
       world with transform bundles, incident.json, a development key per case in the
       final key schema (missing-evidence and grounding fields included), authored by the
       evaluation authority; the walkthrough stays the teaching fixture
3  CONTROL AND EVALUATION MACHINERY   always-escalate · alert-only · full ADII on the same
       cases, model, bounds, scorer, repeats; semantics v2 (grounded NO_REPAIR and ESCALATE,
       unsafe certainty, false refusal); the grid runner materialising every repeat; the
       report generator reading records only
4  FREEZE                              one code SHA, one protocol, one tool surface, one
       validator, one scorer, one catalogue, one price table, one bounds configuration —
       digests in every receipt; any engineering change after this is a new version
5  THE FRESH BENCHMARK                 the frozen system against its controls with the new
       key, rehearsed on the local model first; whatever it says is the result
6  THE EVALUATION REPORT               from those records only: protocol, denominators,
       repeats, per-disposition results, control comparison, failure taxonomy, grounding,
       validation, cost, latency, limitations — the page and the report read the same records
7  THE FINAL PRODUCT SURFACE           designed around what step 5 proved; the benchmark a
       first-class view; the prototype page kept only where its code saves time
8  PRESENTATION                        problem → ordinary agent failure → authority separation
       → live incident → proposal ≠ acceptance → controlled benchmark → failures and limits
       → what was earned
9  FILM                                last: the finished interface, the final numbers, the
       final language, one canonical run
10 SUBMISSION QUALIFICATION            clean clone, Windows install and run, exact
       requirements, final manifest and preserved archive, no secrets, tagged commit
```

Two kinds of key, never called by one name:

```text
DEVELOPMENT KEYS   evaluation-authority authored · frozen before the evaluated runs
UNSEEN KEYS        custody-controlled · inaccessible before the run · different custodian
```

The capstone ships whatever step 5 says. The predecessor's 18/18, the 48-run census, the
scripted verdicts and the prototype's screenshots are engineering history, cited as such
if asked, never on the stage.

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
