# The ADII demonstration world — v0

**Status: specified here, not built here.** A world of this shape exists in the reference
implementation's private catalogue — frozen, and scored against; that is where the worked
examples below come from and why they are stated with confidence. This repository has none
of it. `01_data/demo/world/` is where our version lands, and it is the first operational
environment the whole team shares.

Written because the world ADII lives in is part of the product argument, not a tooling
implementation detail. Choose it badly and ADII reads as an agent that debugs a toy SQL
pipeline. Choose it well and it reads as a layer for deciding when autonomous remediation
is justified.

---

## Domain

Commerce / transaction analytics. Orders arrive from a vendor feed, transforms build a
warehouse, a daily revenue metric is published, and a dashboard alert fires when it moves.

**Why this domain.** Every partner already understands `orders → transactions → revenue`,
so no domain has to be explained before ADII can be. A bank, a retailer, a telecom, a
logistics operator and a marketplace each map onto it in one sentence. The alternative — a
specialised domain — spends the audience's attention on the world instead of on the thesis.

**The domain is not the product boundary.** ADII's core is domain-independent: an
investigator, a controlled tool surface, an independent validator, and an evidence record.
Commerce is the adapter we build deeply. Finance and logistics are extension
*illustrations*, not implementations, and must be described that way — we have validated
one domain, not three.

## Business output

Daily revenue, published to `mart_daily_revenue`.

## The observable system

The rows are one evidence source among eight. This is the point: an agent given only a CSV
is doing data analysis, not incident investigation.

```text
data/orders.csv · customers.csv       source extracts
schemas/*.schema.json                 declared types and units, versioned
transforms/staging, transforms/marts  the transformation logic itself
warehouse/incident.db                 the materialised result
logs/upstream_feed.log                delivery windows, row counts, checksums
logs/manifest.json                    declared logs
logs/vendor_notices.md                business and vendor context
logs/CHANGE_HISTORY.md                deployments, tickets, what changed when
```

## Incident families — the same symptom, three correct actions

This is the product argument. The six below are the reference implementation's frozen
catalogue: not ours, not available here, and reproduced because their *shape* is the
requirement. A world without this property demonstrates nothing, however clean it is.

| Alert | Truth | Correct action |
|---|---|---|
| revenue down ~99% across all history | stale cents→dollars normalisation | **REPAIR** |
| revenue down ~45% since a date | two distributors ended contracts | **NO_REPAIR** |
| revenue down ~half, same day as a deploy | real repricing; deploy is coincidental | **NO_REPAIR** |
| revenue down ~40% since a date | decisive reconciliation log never written | **ESCALATE** |
| one day roughly double | delivery replayed after a timeout | **REPAIR** |
| delivered 18 against a declared 25 | no authoritative export record exists | **ESCALATE** |

Four of six open with substantially the same sentence — *the revenue dashboard shows daily
revenue down …* — and resolve three different ways. An observability system tells you the
metric moved. The operational question is whether there is enough evidence to justify doing
something about it.

The second argument sits inside one incident: the duplicate delivery admits two candidate
repairs. Deduplicating by stable order identity is **ACCEPTED**; halving the day's revenue
passes the agent's own checks and is **REJECTED**, because only 11 of 26 orders were
duplicated. ADII is not valuable because it can generate a fix. It is valuable because the
architecture asks whether the fix is justified and independently verifiable.

## Two invariants for the front door

Any world used for the front-door demo must satisfy both. They are build requirements, not
presentation preferences — a world that fails them cannot be narrated into working.

> **I1 — Inferable.** A new viewer must be able to work out why an example ends in REPAIR,
> NO_REPAIR, or ESCALATE **from the displayed evidence alone**, without prior knowledge of
> data engineering or agent architecture.
>
> **I2 — Mechanistic.** For every REPAIR, the viewer must see *what was changed* and *what
> the independent check verified* — before, action, after, verdict. Not a repair id.

If an example needs five minutes of narration to justify its disposition, it is too
expensive for the front door. Move it to the evaluation catalogue, where difficulty is the
point.

The failure mode I2 prevents is specific. A screen reading `REPAIR · repair_07 · ACCEPT`
has told the viewer nothing: they cannot tell a real fix from a plausible-looking one, which
is the entire distinction the product rests on. Likewise `confidence 0.72 → ESCALATE` would
reduce ADII to a threshold wrapper. The reason must be **concrete missing evidence**, shown.

## Demo scenarios are not evaluation scenarios

Two sets, two questions. Do not make one carry both burdens.

| | Answers | Selected for |
|---|---|---|
| **Demo trio** | *What is ADII?* | instant comprehension |
| **Evaluation catalogue** | *Does ADII work?* | inference geometry and ground truth |

The reference catalogue's six — partial replay, unit change, causal bait, ambiguous filter
semantics, disputed control totals, subtle legitimate change — are deliberately hard, and
hardness is exactly what disqualifies them from a front door.

We build in the other order. The demo trio first, because it is what makes the argument
legible; the evaluation catalogue after, where difficulty is the point and comprehension
is not.

## Design direction

Backwards from comprehension, not forwards from available data:

```text
what must the viewer understand?
        ↓
REPAIR / NO_REPAIR / ESCALATE
        ↓
what evidence would make each obvious?
        ↓
what operational records must exist?
        ↓
build the world
```

The other direction — take a dataset, inspect its columns, ask what demo it supports — lets
the dataset dictate the product story.

## The canonical demo world

Small enough to hold in one screen. Fifty to a hundred rows is enough; the value is in the
*relationships between evidence sources*, never volume.

```text
orders              order_id · timestamp · customer_id · amount · status
delivery_manifest   batch_id · expected_rows · sent_at
pipeline_runs       run_id · batch_id · rows_received · rows_loaded · status · started/finished
business_events     date · event_type · description
daily_revenue       derived from orders
```

Three configurations of that same world, all opening on the same alert — *revenue down 45%*:

| | expected | delivered | loaded | pipeline | other evidence | Correct |
|---|---:|---:|---:|---|---|---|
| **A** | 100 | 100 | 55 | **FAILED** at row 55 | — | **REPAIR** |
| **B** | 56 | 56 | 56 | SUCCESS | promotion ended yesterday | **NO_REPAIR** |
| **C** | 100 | ? | 55 | SUCCESS | manifest service has a known counting fault; source receipt unavailable | **ESCALATE** |

World A is visibly broken: 100 sent, 55 arrived, the loader stopped. World B visibly agrees
with reality: source and warehouse both fell, and a business event explains it. World C is
visibly undecidable: *only 55 orders ever existed* and *100 existed and 45 were lost* both
remain consistent with everything available, and the record that would separate them does
not exist.

World C is the one to get right. Showing both surviving possibilities side by side teaches
abstention better than any definition of it.

## The first build of the world

Not "find a dataset". **Build the smallest operational world in which those three
configurations are executable and legible**, exposed through a realistic tool surface. Then
D renders the relationships, A investigates them, and C knows the truth independently.

## Repair surface

Bounded. An incident declares which files may be written — in practice a staging or mart
transform. Everything else is read-only.

## Validation

A candidate repair is applied to a **clean rebuild from frozen inputs** and checked against
an independent recomputation the agent cannot reach. Structural checks and the revenue
oracle are separate authorities; the agent's own rehearsal is a hypothesis, never a verdict.

This is why the world is synthetic. Independent validation requires ground truth, ground
truth requires controlling the world, and a real corporate dataset supplies neither — while
adding confidentiality constraints, missing operational logs, no authoritative correct
repair, and no ability to author the alternative worlds the table above depends on.

---

## What v0 does not contain

**Adversarial incidents.** The reference investigator scored 18/18 on the six above with
no safety flags — a benchmark everything passes has stopped measuring, and it cannot tell
an excellent investigator from six easy incidents. We inherit that trap unless the
adversarial half is authored *alongside* the legible half rather than after it: incidents
that plausibly bait a false repair, and ones that plausibly bait unsafe certainty. See
[inherited/CONTROLS.md](inherited/CONTROLS.md).

**Partner-informed failure patterns.** v0's incident shapes were reasoned about, not
sourced. The cheapest available improvement is to hand partners the incident taxonomy and
ask *"which of these feel real, and what is missing?"* — which yields more than asking for
raw data, because what ADII needs is realistic failure structure rather than authentic rows.

**More than one domain adapter.** By design.

## Four types of incident, four sets of legal operations

The type of an artifact determines what may be done to it. Confusing them is how earned
evidence gets destroyed by someone trying to be helpful.

| Type | Lives in | Legal operations |
|---|---|---|
| **Demo** | `02_src/adii/demo/` | created and changed freely. Carries **no evaluation claim**. |
| **Development / adversarial** | the evaluation catalogue, additively | authored under the authoring protocol; additive only, never replacing |
| **Frozen evaluation** | the same place, from the moment a reported result is scored against it | none. Never modified, never silently regenerated, **never simplified for presentation**. |
| **Blind** | custodian-controlled | frozen before any investigator sees them; authored by someone who will not run against them |
| **Brought** | the run folder it was investigated in (`incident.json`, `world.sql`), never the catalogue | an operator's own question over their own files, from the page or `--incident-dir`; carries **no evaluation claim** and has no key; kept byte for byte beside its record, never edited there |

Today only the first row exists here as incidents, and the last as a mechanism — no
brought incident is in the repository, since each lives in the run folder of the machine
it was brought to — which is the cheapest moment this rule will ever be to adopt. An incident becomes frozen the instant a number is reported against it, and
nothing is announced when that happens — so the discipline has to be in place before the
first scored run, not after it.

The distinction that matters most: *"make this incident easier to explain"* is legitimate
work on a **demo** incident and destroys a **frozen evaluation** one. Both requests sound
identical.

## What changing this world costs

Right now, nothing — no result has been reported against any of it, which is exactly why
its shape is worth settling today rather than after the first evaluation. From the first
scored run onward, editing an incident invalidates every number measured against it, and
no care taken afterwards recovers them.

So build the habit before it bites: *extend*, do not revise.

---

## Who decides

Not one person. The world is part of the final argument, so its design is a shared
decision upstream of implementation.

| | Question it has to pass |
|---|---|
| **Legibility** | Does this world make ADII's value legible to a partner in five minutes? |
| **Buildability** | Can this world be built cleanly and exposed through a realistic tool surface? |
| **Independence** | Can the correct answer be known independently of the agent, and stay hidden from it? |
| **Reachability** | Can the investigator actually reach the decisive evidence through permitted tools? |

**Whoever implements the world does not choose it alone.** A world that is easy to build but
cannot separate REPAIR from NO_REPAIR from ESCALATE has failed, and that failure is
invisible from inside the component that built it.

Any new incident family needs all four answers before it is built.

## The claim this world enables

> ADII investigates whether intervention is justified. It does not merely detect anomalies.
