# Inherited conformance requirements

Derived from defects found in a separate private reference implementation of the same
system. This document is self-contained: it is the whole of what crosses. Nothing else from
that implementation — no source, no test file, no run archive, no answer key, no corpus, no
report — is part of this inheritance.

Thirty-eight requirements, each stated so it can be satisfied independently. Implementation
is deliberately unspecified.

## The boundary

The sending side maintains a provenance rule, restated here in full because it governs how
this document may be used:

> Requirements may be inherited. Implementations may be deliberately ported.
> **Evidence is never inherited.**

| Crosses | Does not cross |
|---|---|
| requirements and invariants | accuracy, success rates |
| architecture lessons | defect and escalation rates |
| failure modes and their reproductions | cost and latency results |
| test ideas | model comparison results |
| provider facts | run outcomes, archives, keys, corpora |
| public mechanism descriptions | coverage and mutation scores |

> **Knowledge crosses. Numbers do not.**
> The mechanism and the test cross. The artifact instance does not.
>
> **A ported implementation does not inherit the measurement it was written to produce.**

The private work can make the team system **better designed on day one**. It cannot make it
**already validated on day one**.

## How to read this

Every requirement is stated in five fields, deliberately free of private symbol names:

- **Requirement** — the invariant to satisfy.
- **Reproduction** — the concrete failure it prevents, expressed so it can be re-created
  from nothing.
- **Expected** — the behaviour that replaces the failure.
- **Test** — what must be written, and what it must assert.
- **Depends on** — the interface this needs from another member, or `none`.

Implementation is deliberately unspecified. Satisfy the requirement independently; do not
reproduce an architecture you have not evaluated. Private file and symbol names are
provenance for the sending side and are not part of this document.

**Stripped on purpose:** every count, rate, score, cost, latency and version number
produced by measuring the private system. Where a lesson previously carried such a number,
the number has been removed and the lesson restated. Facts about third-party software
(published SDK versions, browser behaviour) are not measurements of either system and do
cross.

---

# X — cross-cutting

## X1. Every safety guard must have a test that fails when the guard is removed.

- **Requirement:** for each guard that rejects, bounds, or validates, there exists a test
  that goes red when that guard alone is neutralised. Run known-covered guards as
  **controls** in the same pass; if a control survives neutralisation, the harness is
  broken and no result from it means anything.
- **Reproduction:** take a module with a passing suite and good line coverage. Replace one
  guard's condition with a constant false. Run the suite. If it stays green, the guard was
  detected but never demonstrated, and any later refactor that drops it fails silently.
- **Expected:** a guard whose removal changes no test outcome is treated as untested,
  regardless of coverage. Coverage says a line ran; it does not say anything depended on
  its outcome.
- **Test:** an automated neutralise-run-restore pass over the guard set, reporting killed
  and surviving guards by name, with controls. Survivors are listed explicitly, never
  summarised into a percentage alone.
- **Depends on:** X4. Applies to A, B, C and D equally. **D owns enforcement at
  integration** as the final hardening pass before freeze.

> A guard is not demonstrated because a test passes. It is demonstrated when removing the
> guard makes a test fail.

### X1a. The oracle must be independent of the code it is checking.

A check that asks the implementation whether the implementation is right proves nothing.

- **Reproduction:** a component is instrumented to verify its own invariant, and the
  instrumentation evaluates the same predicate the component uses to decide. When that
  predicate is the defect, the check confirms it. The run reports zero violations and the
  bug is still there.
- **Expected:** state the invariant **behaviourally** — in terms of an observable outcome
  the component must not produce — and check that, not the internal expression. Where a
  reference result is needed, compute it a different way.
- **Test:** for each invariant check, confirm it fails when the invariant is genuinely
  broken. If both the correct and the defective implementation pass the same check, the
  check is measuring nothing.

### X1b. Volume is not coverage.

- **Reproduction:** a randomised campaign of very many cases reports no failures, and a
  single hand-chosen case fails immediately. The generator never visited the region where
  the code is wrong — boundaries, near-equal values, empty and maximal inputs — so the
  large number measured only the region that already worked.
- **Expected:** adversarial cases are chosen deliberately at boundaries in addition to any
  randomised sweep, and a sweep's reach is stated rather than implied by its size.
- **Test:** boundary cases are enumerated explicitly as named tests. A count of trials is
  never reported as evidence of coverage without saying which regions were sampled.

### X1c. Detection is not prevention.

A check that notices a bad outcome after it happened is not a guard that stops it, and a
receipt must never report the one as the other.

- **Reproduction:** an admission boundary validates a *witness* of the proposed write — a
  checkpoint, a summary, a declared target — instead of the written value itself. A correct
  witness escorts an arbitrary write through. Downstream state-property checks flag the
  corruption on every run, so the run reports no violation surviving and the receipt records
  the boundary as sound. The invariant checks were working; the boundary never was; the two
  claims were reported as one.
- **Expected:** a prevention claim is established by attempting the violation *at the
  boundary* and observing refusal, over an enumerated grid of admitted and rejected
  transactions — not by prose, and not by the absence of surviving violations downstream.
- **Test:** for every boundary described as preventing something, one test submits the
  forbidden write with a correct witness and asserts rejection at the boundary, with the
  downstream checks disabled so they cannot mask the result. A receipt that claims
  prevention names that test.

## X2. A declared dependency range must be able to run the configuration you pinned.

- **Requirement:** every version permitted by a declared constraint must support the
  parameters the code actually sends. An extra that advertises a capability must import.
- **Reproduction:** pin sampling parameters and record them in a receipt, then declare a
  floor old enough that those parameters do not exist. Install the floor in a clean
  environment: the first call raises `TypeError` and the frozen-configuration guarantee is
  unsatisfiable for anyone who resolves the constraint rather than the lockfile. Separately,
  declare an extra whose module imports a package the distribution does not ship — the
  extra installs and the capability cannot start.
- **Expected:** the floor is the earliest version that carries every parameter sent, found
  by bisection rather than assumed; extras are importable from a built artifact.
- **Test:** in an **isolated environment built from the declared floor**, assert every
  pinned parameter is accepted and the advertised modules import. Abort on install failure
  rather than inspecting whatever was already present, and compare versions with a version
  parser — `1.58` and `1.58.0` are the same version spelled differently, and string
  equality rejects a correct floor.
- **Also:** **every third-party module imported directly must be declared directly.**
  Relying on a package arriving transitively through another dependency works until that
  dependency drops it, and the failure appears as a missing module in code nobody changed.
  Test: compare the set of non-stdlib top-level imports against the declared dependency set
  and fail on any import that is not declared.
- **Provider fact (crosses):** on the OpenAI Python SDK, `seed`, `reasoning_effort` and
  `max_completion_tokens` are absent from chat completions before **1.58.0**. Verify this
  yourselves rather than taking it from here.
- **Depends on:** D7's pinned configuration.

## X3. Server state keyed on a caller-controlled value must be bounded — by admission control, not eviction. *(only if the team system has caller-keyed server state)*

- **Requirement:** any per-client map must have a hard size bound. When it is full, refuse
  **new** keys rather than evicting existing ones.
- **Reproduction:** a per-client token bucket that writes an entry on every call and never
  removes one grows without limit under rotating source addresses. Then add a hard cap that
  evicts: because an absent key defaults to a *full* bucket, whoever is evicted is handed a
  free reset. With more throttled clients than slots, eviction must drop someone, so the
  limiter can be bypassed by filling it.
- **Expected:** only entries that have provably refilled to capacity are reclaimed — such an
  entry is indistinguishable from an absent one, so dropping it changes nothing. When that
  frees no slot, the new key is refused. The limiter fails closed.
- **Test:** four properties together — storage stays bounded under many distinct keys
  (checked after *every* request, with genuinely distinct keys); a client over its rate is
  still throttled; a flood of new keys does not reset a throttled client; and **more
  exhausted clients than slots still does not reset one**. The last is the regression that
  catches eviction-based bounds.
- **Accepted cost, which must be documented rather than discovered:** while occupants keep
  consuming at their permitted rate they never refill, so new-client admission can be
  unavailable **indefinitely**. One refill interval suffices only once they go quiet.
- **Depends on:** none.

## X4. The conformance suite runs automatically on every change.

- **Requirement:** the tests that encode these requirements — including the X1
  guard-removal pass — run without anyone remembering to run them, and a failure blocks the
  change.
- **Reproduction:** a fast, fully offline suite exists and is green. Nothing invokes it on
  a change. Tests written to encode a requirement drift out of the default run, or live
  outside the configured test path and are never collected at all. Months later the suite
  still passes and the requirement no longer holds, because nothing has asked in between.
- **Expected:** one command runs everything, that command runs on every change, and the
  configured test path includes every directory that holds conformance tests. The
  guard-removal pass runs at least before each freeze.
- **Test:** the runner collects a known count of tests and fails if a test directory is
  unreachable from the configured path; a deliberately broken guard fails the pipeline, not
  just a local run.
- **Also:** **a hung test must fail, not block.** Set a per-test timeout, and choose a
  timeout mechanism that can actually interrupt the work your tests do — a signal-based
  timer cannot unwind a thread blocked in a native call or a worker pool, and does not
  exist on Windows. Use a thread- or process-based timeout that every platform the team
  develops on supports. A test that exceeds its budget is refactored; the budget is not
  raised.
- **Depends on:** none. Without this, X1 is inert.

---

# A — Agent loop: the investigator

## A1. A wrong-typed tool argument is a REJECTED result, not a crash.

- **Reproduction:** a tool declared to take a string is called with an integer. Binding
  succeeds — arity matches — and the wrong type reaches the tool body, which raises. That
  exception is indistinguishable from a genuine platform fault, so the run aborts and is
  archived as infrastructure failure: a **model** error filed as a **platform** error, in
  the artifact used to judge tool-use reliability.
- **Expected:** arguments are validated against the advertised schema **before** dispatch;
  a mismatch returns `REJECTED` to the model, which may retry.
- **Test:** for each declared parameter type, call with several wrong-typed values and
  assert the run survives, the result is `REJECTED`, and the archived classification is not
  infrastructure failure.
- **Depends on:** B's schema declarations.

## A2. The guard belongs in the loop, not in one executor.

- **Reproduction:** the type check is added to the executor where the bug was found. A
  second executor is written later and reintroduces the whole class.
- **Expected:** whoever advertises the schemas owes the check. Placing it in the loop closes
  the class for every executor.
- **Test:** a second, minimal executor that declares a typed schema and performs no
  validation of its own is still protected.
- **Depends on:** B's executor interface.

## A3. A schema form you cannot validate must be refused, not waved through.

- **Reproduction:** a validator silently ignores a keyword it does not understand —
  a boolean type, nested properties, an enum. The tool surface now advertises a constraint
  nothing enforces, and the model is blamed for violating it.
- **Expected:** an unsupported schema form is rejected loudly at the boundary, when the
  surface is advertised, not when a call arrives.
- **Test:** advertise schemas containing each unsupported form and assert construction
  fails with a message naming the offending path.
- **Also:** a hand-written validator is the densest branch cluster in a loop and the place
  example-based tests miss most. Add **property tests**: generate a value, derive a schema
  it should satisfy, assert acceptance; then mutate the value's type and assert rejection.
  Assert the equality rule the validator relies on — in particular that boolean and numeric
  values are never treated as equal, which is the comparison most languages get wrong by
  default.
- **Depends on:** none.

## A4. The loop terminates, and every bound is enforced after the request as well as before.

- **Reproduction:** bounds are checked only before issuing a request. The request that
  crosses the ceiling returns, and its completion goes on to submit a decision — so a run
  exceeds its deadline and still produces a scored result.
- **Expected:** every bound is re-checked after the response is received and appended, so
  the transcript retains the evidence of what was cut off. The turn budget is finite and
  derived from the tool budget.
- **Test:** an injected clock that crosses the deadline exactly during a request; assert no
  decision is produced and the transcript still contains the final assistant turn.
- **Also:** **enforcing a bound must not cost more than the bound saves.** A context bound
  implemented by re-serialising the whole conversation on every check is quadratic in turns,
  and it runs on the request path, so the guard meant to protect the run becomes the
  dominant cost of the run. Keep a running total as the conversation grows rather than
  recomputing it. Test with a long run: enforcement cost must not grow super-linearly in
  turns, compared against the same workload with the bound unset.
- **Depends on:** none.

## A5. A bound is not a model failure.

- **Reproduction:** an operator ceiling stops a run and the archive records "the model
  failed to submit". The two are then indistinguishable in aggregate.
- **Expected:** a distinct error type carrying **which** bound was hit, classified
  separately from a model failure everywhere downstream.
- **Test:** each bound raises the distinct type with its own identifier; the archived
  classification differs from a model-failure run.
- **Depends on:** D's classification vocabulary.

## A6. A public API enforces its own invariants; a CLI check is not enough.

- **Reproduction:** a budget is validated at the command line only. Every other caller
  reaches the loop unchecked. Worse than a crash: small negative values produce a *scored*
  record indistinguishable from a legitimate control arm.
- **Expected:** the constructor validates; the CLI is one caller among several.
- **Test:** call the public constructor directly with each invalid value and assert it
  raises rather than producing a run.
- **Depends on:** none.

## A7. Reject at construction anything that would silently disable a bound.

- **Reproduction:** NaN, infinity, negatives, booleans. Every comparison against NaN is
  false, so an unvalidated NaN ceiling produces an unbounded run that **looks** bounded.
  Comparison-based guards (`x < 1`, `x <= 0`) admit NaN by construction.
- **Expected:** ceilings are validated for finiteness and sign at construction; booleans are
  rejected rather than coerced.
- **Test:** each non-finite and out-of-range value raises at construction; a NaN ceiling
  never yields a run that completes unbounded.
- **Depends on:** none.

## A8. A caller-supplied bound is clamped by the service, and the default is the safe one.

- **Requirement:** every bound a request may set has a server-side maximum, and its default
  is the value that is safe on the **paid** path, not the convenient one for an offline
  fake.
- **Reproduction:** three request bounds are exposed. Two are clamped; the third is
  validated only as positive. A caller sets it enormous and the bound is effectively
  disabled while appearing configured — the same failure as A7's NaN, reintroduced at the
  request boundary. Separately, a cost ceiling defaults to "unbounded" because that suited
  the offline stub, and that default is what every request gets once a live provider is
  configured.
- **Expected:** each caller-settable bound carries both a floor and a ceiling; defaults are
  chosen for the paid path and a comment says why.
- **Test:** for each bound, a request above the ceiling is rejected or clamped, not
  honoured; the default configuration of a live adapter has every ceiling set.
- **Depends on:** D9's bound vocabulary.

## A9. The exception type is part of the contract.

- **Requirement:** where control flow distinguishes "reject this and let the model retry"
  from "abort, this is our fault", the exception **type** carries that distinction, and it
  is documented as load-bearing so it is not refactored away.
- **Reproduction:** validation raises a value error, and the caller catches exactly that to
  return `REJECTED` to the model. A linter observes that a type error is more idiomatic for
  a type problem and recommends the change. Taking the advice makes those errors escape the
  handler, so a **model** error is archived as a **platform** error — the same corruption as
  A1, arriving through a style rule rather than a bug.
- **Expected:** the reject-versus-abort boundary is expressed in types, documented at both
  the raise and the catch, and any lint rule that would alter it is suppressed **with the
  reason recorded**.
- **Test:** each invalid submission shape produces `REJECTED` and a continuing run; an
  injected genuine platform fault aborts. Apply X1: change one raise to the "idiomatic"
  type and a test must fail.
- **Depends on:** D's classification vocabulary.

## A10. Messages the loop generates itself must be ones the provider will accept.

- **Requirement:** every message shape the loop can produce — including on its own recovery
  paths — round-trips through the provider adapter.
- **Reproduction:** the model returns a turn with neither text nor tool calls — a refusal, a
  content filter, an empty completion. The loop appends a nudge and continues. That appended
  assistant message has null content and no tool calls, which the provider rejects, so the
  recovery path breaks on the very message it wrote to recover.
- **Expected:** the adapter's conversion is total over the shapes the loop can emit, and the
  degenerate shapes are the ones tested first.
- **Test:** construct each loop-generated message shape, convert it, and assert the result
  satisfies the provider's documented constraints — in particular the empty-turn case,
  reached without a network call.
- **Depends on:** D7's adapter configuration.

---

# B — Tool execution: the tool boundary

## B1. `DENIED`, `REJECTED` and `ERROR` are three different things.

- **Reproduction:** the model's bad arguments are recorded as `ERROR`. The model now looks
  worse than it is, and platform reliability looks worse than it is, in the same number.
- **Expected:** refused by policy or budget (`DENIED`), the model's arguments were wrong
  (`REJECTED`), our fault (`ERROR`). Distinct at the source and preserved end to end.
- **Test:** produce one of each and assert the status that arrives at the archive is the
  status the tool layer emitted.
- **Depends on:** D's record contract.

## B2. Bound every result.

- **Reproduction:** an unbounded query result becomes unbounded context. The run fails far
  from the cause, and the diagnosis lands on the wrong component.
- **Expected:** row caps and line windows declared in the schema, with an explicit
  truncation flag in the result so the model knows it saw a prefix.
- **Test:** a result larger than the cap is truncated, flagged, and the flag reaches the
  archive.
- **Depends on:** none.

## B3. No tool takes a filesystem path.

- **Reproduction:** a tool accepting a path can be pointed at the answer key.
- **Expected:** tools address declared logical identifiers — table, log id, transform id —
  resolved internally.
- **Test:** no declared schema contains a path-shaped parameter; traversal attempts through
  every identifier parameter fail closed.
- **Depends on:** none.

## B4. Read-only is enforced by the database or connection authority, never by parsing SQL text.

- **Reproduction:** a regex or prefix check over query text is a suggestion. Comments,
  case, whitespace, compound statements and vendor syntax all defeat it, and each bypass is
  discovered one at a time.
- **Expected:** the connection itself cannot write — an authorizer callback, a read-only
  connection or an unprivileged role. The boundary is enforced below the query text, so
  what the text says stops mattering.
- **Test:** attempt writes through the tool surface using several syntactic forms and assert
  each is refused **by the database layer**, not by a text check; then neutralise any
  text-level check and assert the writes are still refused (this is X1 applied to B4).
- **Depends on:** none. **Build this independently — do not depend on the private
  evaluation harness for it.**

---

# C — Validation and evaluation

## C1. Independent validation rebuilds from frozen inputs and never consults the agent's own rehearsal.

- **Reproduction:** the agent rehearses a candidate repair in its own sandbox and its checks
  report PASS. The repair is nevertheless wrong: in one observed case a repair that
  deduplicated on the wrong key removed genuine records as well as duplicates, halving a
  day's totals. The agent's own checks were green throughout; independent validation
  rejected it. Right disposition, right root cause, wrong repair — and nothing visible to
  the agent would have revealed it.
- **Expected:** validation rebuilds the world from frozen inputs, applies the candidate
  patch, and evaluates against the frozen authority. The agent's rehearsal output is
  evidence about the agent, never an input to scoring. Structural checks available to the
  agent must be documented as structural only, so a passing rehearsal is never read as
  authorisation.
- **Test:** buildable **now**, against a fake frozen world and a fake candidate repair, with
  no model and no real incident: (a) a patch whose rehearsal passes and whose independent
  rebuild fails is scored as a failure; (b) validation produces the same verdict when the
  rehearsal output is withheld entirely; (c) a patch with the correct record *count* and the
  wrong record *identities* is rejected — count-based oracles pass it, identity-based
  oracles catch it.
- **Depends on:** B's patch-application surface; D's record contract for the verdict.

## C2. Answer keys are frozen by hash and never edited.

- **Reproduction:** evidence scored against a key that can move afterwards means nothing;
  the score cannot be reproduced and the change leaves no trace.
- **Expected:** each key is pinned by digest and loaded through a function that refuses on
  mismatch. A correction is a **new file**, never an in-place edit.
- **Test:** a mutated key fails to load; loading verifies the digest rather than trusting
  the filename; a correction produces a new artifact and the old one still loads.
- **Depends on:** none.

## C3. Authorities that freeze at different times must be different artifacts.

- **Reproduction:** incident truth, grounding authority and scoring definition are bundled
  into one file. One of them must change before first exposure, so the whole bundle is
  re-frozen, silently re-dating the parts that were already committed.
- **Expected:** one artifact per freezing lifecycle, each independently hash-bound, each
  naming what it does and does not govern.
- **Test:** changing one authority does not alter the digest of another; each load path
  verifies its own artifact.
- **Depends on:** none.
- **If the team repo is a single repository:** the separation between the system under test
  and the scoring authority must be recreated **logically and by hash**, or C2 and C3
  collapse back into one mutable authority. Put this in the task brief, not the appendix.

## C4. Version dispatch is explicit.

- **Reproduction:** a v1 artifact carrying a v2 field is treated as an implicit upgrade. Two
  readers now disagree about what the artifact means, and neither is wrong.
- **Expected:** the version is read first and dispatched on; an unexpected field for the
  declared version is an error.
- **Test:** a v1 artifact with a v2 field fails to load rather than being upgraded.
- **Depends on:** none.

## C5. A published schema and the validating code are checked against each other by a test.

- **Reproduction:** a schema is published for readers and validation is hand-written in
  code. They drift, because nothing ever loads the published file. Documentation with no
  test is a statement about the past.
- **Expected:** the published schema is the one the validator uses, or a test asserts they
  accept and reject exactly the same documents.
- **Test:** a corpus of valid and invalid documents produces identical verdicts from the
  published schema and the code path.
- **Depends on:** none.

## C6. Scoring semantics changes are pre-registered, never post-hoc.

- **Reproduction:** changing what "success" means after seeing results turns a real finding
  into an unfalsifiable one.
- **Expected:** a versioned successor document, ratified **before** the first exposure it
  governs, never an in-place edit. If a correction is needed after exposure, the exposure
  is what moves, not the definition.
- **Test:** the scoring definition carries a version and a freeze date; a test asserts the
  frozen definition is the one the scorer implements.
- **Depends on:** none.

---

# D — Telemetry: the experimental record

**Mission:** make every run **reconstructable, attributable, bounded, versioned, preserved,
and impossible to accidentally misreport.**

**D is passive.** D records what happened; D must not silently change what A, B or C mean.
If A says a bound was exceeded, D must not archive "model failed". If B says `REJECTED`, D
must not flatten it to `ERROR`. If C says reject, D records reject and does not reinterpret.

**Interface D consumes:**

```text
A -> investigation events / termination reason
B -> tool executions + typed statuses
C -> validation / scoring result
                  |
                  v
D -> immutable experiment record
```

**Integration question D owns:** can `OK`, `DENIED`, `REJECTED`, `ERROR`, a bound hit, a
validator rejection, and a successful submission each travel from source to archive
**without changing meaning**? When the answer is yes, the spine is becoming trustworthy.

## Build order

1. **Run record contract (D3, D4).** Define one strict versioned record that can hold A/B/C
   outputs without depending on their implementations. Do this before wiring anything.
2. **Failure-preserving sink (D1, D3, D5, D6).** Success, model rejection, bound hit,
   validator rejection and infrastructure failure must each leave an honest record. The
   archive must never become the thing that destroys the original error.
3. **First-exposure protection (D8) and preservation (D13).** Both must exist before anyone
   spends a real frozen world or generates a corpus later work will bind to.
4. **Provider provenance (D7).** Requested and effective configuration, one fingerprint slot
   **per response**. Generate your own evidence about what your provider returns.

## D1. The archive is self-contained.

- **Reproduction:** a run proposes a repair, has it validated, and passes — and leaves no
  record of **what the repair was**. Digests prove a call happened; they cannot reconstruct
  it. Neither replay nor a report is buildable from that.
- **Expected:** messages, tool arguments, tool results, the rationale and the patch. The
  transcript is a **caller-owned passive sink** written through, not a callback: the caller
  holds the interaction on every exit path — success, model failure, bound, infrastructure
  exception — and a recording failure cannot mask the error that ended the run.
- **Test:** end a run three ways and assert the transcript survives each with the messages
  produced up to that point.
- **Depends on:** A's turn events, B's execution results.

## D2. Counters come from the trace, never self-reported.

- **Reproduction:** an agent that reports its own tool-call count can flatter its own
  efficiency, and the efficiency metric silently becomes a measure of honesty.
- **Expected:** the harness owns the counters and the citation identifiers. Identifiers are
  minted by the execution layer and bound to its authoritative trace; the model may only
  reference them.
- **Test:** a model that claims fewer calls than it made is recorded at the true count; a
  citation to an identifier the harness never minted is rejected.
- **Depends on:** B's execution trace.

## D3. Records are strict RFC-8259 JSON, or they are archived as failures.

- **Reproduction:** a non-finite cost writes literal `Infinity` while reporting a scored
  status and exiting zero — an archive no conforming parser will read, reported as success.
  Then the naive fix: adding strictness at the write itself only trades an invalid archive
  for a **missing** one, because it raises outside the classification boundary.
- **Expected:** serialise with non-finite values rejected and **no permissive fallback hook**
  — a fallback turns the first foreign object into silently altered archive data. Validate
  the payload **before** it reaches the sink, so a bad payload becomes an archived
  infrastructure failure rather than an exception at the sink.
- **Test:** a non-finite value produces an archived failure record, exits non-zero, and the
  run's other records still exist.
- **Depends on:** none.

## D4. Every record carries a schema version.

- **Reproduction:** the record shape changes and a reader has to infer which shape it holds
  by probing for keys. Worse, older archives silently lack fields added later, so a feature
  cannot be demonstrated from the archive that predates it.
- **Expected:** a version field bumped whenever the shape changes; readers dispatch on it.
- **Test:** a reader refuses an unknown version rather than guessing; a fixture of each
  historical shape loads under its declared version.
- **Depends on:** none.

## D5. One failed unit must not abandon the run.

- **Reproduction:** one unloadable key aborts an entire grid and archives nothing —
  including for the units that would have succeeded.
- **Expected:** archive it, classify it, continue. Materialise **every promised repeat** as
  an explicit failure record, so a missing record never looks like a vanished archive.
- **Test:** a failing unit mid-grid leaves a classified record for every promised repeat and
  the remaining units still run.
- **Depends on:** C's failure signals.

## D6. A partial failure must not consume a name that cannot be reused.

- **Reproduction:** a provenance failure leaves an empty directory behind, and the
  never-overwrite rule then refuses every retry under the pre-registered label.
- **Expected:** reserve the name only after every non-I/O precondition passes. Archive-sink
  I/O failure stays deliberately terminal — a failed sink cannot preserve its own failure —
  and that asymmetry is documented where the contract is stated, so the docstring does not
  over-promise.
- **Test:** a precondition failure leaves the label reusable; a sink failure is terminal and
  says so.
- **Depends on:** none.

## D7. Pin the model configuration and record it, including a per-response backend fingerprint.

- **Reproduction:** runs execute at whatever the provider defaults to that day, and the
  archive cannot state what that was.
- **Expected:** sampling parameters pinned as constants and reported in every receipt;
  **one fingerprint slot per response**, not one value for the run — a single trailing value
  is exactly what would hide a backend change mid-run. Record requested *and* effective
  configuration where they can differ.
- **Provider fact (crosses):** `seed` is documented by the provider as best-effort. It
  constrains sampling and is not proof of determinism. Backend fingerprints **may be null**,
  so record one per response and do not infer reproducibility from `seed` alone.
- **Evidence that does NOT cross:** what any particular provider returned in our runs.
  Generate your own.
- **Test:** the receipt contains every pinned parameter; a run with several responses stores
  one fingerprint entry per response; a null fingerprint is recorded as null rather than
  omitted.
- **Also:** **validate every piece of experiment configuration before constructing the
  provider client.** Otherwise a missing credential fails first and masks a missing or
  invalid model id, an absent pricing coefficient, or a malformed parameter — and the
  operator is handed guidance for the wrong failed precondition. Test: with the credential
  absent *and* the model id absent, the error names the model id.
- **Depends on:** X2.

## D8. An irreversible action is archived before it is spent, including on the failure path.

- **Reproduction:** the first exposure of an incident to a model runs inside a temporary
  directory and leaves only a timestamp and terminal scrollback. There is no second first
  exposure.
- **Expected:** the receipt naming what is about to be spent — the artefact, the
  configuration, the source revisions, the reason it is permitted — is written **and
  flushed** before the irreversible call, and is retained whether the call succeeds or
  fails.
- **Test:** kill the process immediately after the receipt write and before the call; the
  receipt exists and names what was about to be spent.
- **Depends on:** C's freeze identifiers.

## D9. Cost, context and wall-clock are three separate bounds.

- **Reproduction:** one bound is assumed to imply the others. A run bounded only by turns
  spends without limit; a run bounded only by cost runs for hours.
- **Expected:** three independent ceilings, each optional, each named in the failure. A cost
  cap compared **between** requests is **soft and post-spend** — it cannot prevent the
  request that crosses the line, only the one after it. Say so in the contract rather than
  implying a hard cap, and state the worst-case overshoot.
- **Test:** each bound trips independently with the others unset; the soft cost cap's
  documented overshoot is asserted, not assumed.
- **Depends on:** A's bound reporting.

## D10. Never publish an unbound dependency name.

- **Reproduction:** an extra names a package the project does not own, and a non-lockfile
  install resolves it from a public index.
- **Expected:** distributable metadata names only packages the project controls or that
  exist on the index under the intended identity.
- **Test:** assert no extra names an undistributed or unowned package.
- **Depends on:** X2.

## D11. Report success and failure with equal legibility.

- **Reproduction:** a report that only reads well when the agent was right is marketing.
- **Expected:** the same view renders a success, a model failure, a bound, and a validator
  rejection, each labelled in its own terms. Pair each call with the result the model saw,
  in order, and distinguish a terminal submission from an unanswered call — "pending" is
  the wrong word for a call that ended the run.
- **Test:** render one archive of each outcome class and assert each is labelled distinctly
  and completely.
- **Depends on:** A, B and C status vocabularies.

## D12. The report must not execute what the model wrote.

- **Reproduction:** model-controlled text reaches a UI and is interpolated into markup. A
  tool name the model invented is refused by the loop but **still recorded and still
  rendered**, so a payload short enough to survive any display truncation executes in the
  viewer's browser. Confirmed executing in a current browser before the fix. The relevant
  threat is not a hostile provider but **prompt injection from the data the agent reads by
  design** — source extracts, transforms and operational logs it does not control.
- **Expected:** everything drawn from the record is escaped before insertion, so the
  invariant is "nothing from the record is interpolated raw" rather than a per-field
  judgement about which values happen to be model-controlled today. A truncation budget is a
  layout constraint and is **never** a security boundary.
- **Test:** a browser regression driving the **shipped** rendering code — extracted at test
  time, not copied — asserting the payload renders as text and no handler executes.
  Reverting the escape must turn it red. Keep a source-level assertion that runs without a
  browser so the requirement is enforced even where one is unavailable.
- **Depends on:** D11's rendering surface.

## D13. Data that downstream work binds to by hash must have a verified second copy and a tracked manifest.

- **Requirement:** any artefact that later work attests to by digest is preserved as a
  **second, independently verified copy**, and a manifest of what exists — path, size,
  digest — is tracked in version control even when the payload is not.
- **Reproduction:** a large corpus is generated once, at real cost, and left in a working
  directory that is neither tracked nor ignored. Downstream analyses pin files inside it by
  digest. Losing the directory leaves every receipt intact and every object it attests to
  gone — the chain becomes **unverifiable** rather than detectably broken, which is the
  worse failure. Adding the path to the ignore list makes it invisible, which is what let a
  single copy go unnoticed in the first place.
- **Expected:** three distinct mechanisms, never confused with one another —
  **preservation** (a verified copy), **attestation** (a tracked manifest), and **hygiene**
  (ignore rules that keep bulk out of history). Ignoring is not preserving, and the document
  that states the ignore rules should say so where the next person will read it.
- **Test:** preservation is **manifest-first** — hash the source, copy, then re-hash the
  destination against the manifest made *before* the copy. A copy verified only against
  itself is a second chance to have the same corruption twice. Verification re-runs from the
  manifest alone. The original is never deleted on the strength of an unverified copy, and a
  payload change without a manifest change fails a test.
- **Also — retention:** a successful run need not retain material that can be rebuilt from
  recorded identifiers; a failed run keeps its working state as diagnostic evidence. State
  which class each artefact is in rather than retaining everything by default or discarding
  by accident.
- **Depends on:** C's freeze identifiers.

## D14. A record carries no machine-specific paths, and its provenance is captured per record.

- **Requirement:** archived records reference artefacts by repository-relative path or
  logical identifier, and any recorded source revision is read at write time rather than
  cached for the life of the process.
- **Reproduction:** a receipt embeds absolute paths from the machine that produced it, so
  the record cannot be verified anywhere else and leaks the local layout. Separately, the
  source revision is resolved once and memoised: correct for a one-shot script, silently
  stale in a long-lived server, which then stamps every record with the revision it started
  at rather than the one it is running.
- **Expected:** paths are relative to a declared root; provenance is captured at the moment
  the record is written.
- **Test:** no archived record matches an absolute-path pattern; a process whose source
  revision changes between two records writes two different revisions.
- **Depends on:** none.

## D15. Unknown provider work is recorded as unknown, never as zero.

- **Requirement:** a provider interaction that may have executed remotely without returning
  a usage object — a client-side timeout, a transport exception after send, a submitted
  batch job whose result was never collected — is recorded with usage *unknown* and an open
  reconciliation status. A cost total states how many such rows it excludes and is reported
  as a lower bound while any remain.
- **Reproduction:** a generation sweep times out client-side on many attempts and keeps one
  file per attempt. The files carry no provider response, so summing them yields zero
  tokens, and the number of attempt files is later read as the number of requests
  transmitted. Separately, batch jobs are created successfully and never polled; the local
  record shows creation only. Both are folded into a spend figure as if they cost nothing,
  and the true figure is indeterminate from local evidence.
- **Expected:** every ledger keeps three evidence classes apart: proved usage (a
  per-response usage object), provider-confirmed without usage (an error or resource
  record), and failed before the provider (affirmative evidence the request never left). A
  timeout is never placed in the third class. A submitted job gets a record at creation
  carrying its remote identifier and stays open until its outcome is fetched or explicitly
  written off.
- **Test:** the aggregate over a synthetic ledger holding one proved response, one timed-out
  attempt and one uncollected job returns a value tagged as a lower bound with two unknown
  rows; an aggregate that returns an untagged total for that input fails the test.
- **Depends on:** D8, D9.

---

# Assignments

| Member | Scope |
|---|---|
| **A** | A1–A10, plus X1 applied to every A guard |
| **B** | B1–B4, plus X1, including a real read-only-**authority** test |
| **C** | **C1–C6**, C1 first and buildable now against fakes, plus X1; brief includes the single-repository authority-separation warning |
| **D** | D1–D15, provider and freeze integration, X2, X4, X3 if applicable, and **enforcement of X1 (with X1a/X1b/X1c) across A/B/C/D as the final hardening pass before freeze** |

# What must not cross

No accuracy or full-incident-success figure. No false-repair, unsafe-certainty or
escalation rate. No cost or latency result. No model comparison or ranking. No run archive,
answer key, incident, or corpus. No coverage or mutation score.

If the team system measures something different from the private one, the team number is
the answer. The gap is a finding worth investigating — a lesson one implementation encoded
and the other did not, a harder environment, or a reference result that was less general
than it looked. It is not a discrepancy to average away.

---

# Traceability

Every defect behind this document maps to a requirement. Nothing is carried forward as a
number; the mapping exists so a reader can ask "which failure is this requirement for?" and
get an answer, and so a later reviewer can check nothing was quietly dropped.

## The original fifteen

| # | Defect | Requirement |
|---|---|---|
| 1 | wrong-typed tool argument aborts the run, misfiled as infrastructure | A1, A2 |
| 2 | archive not self-contained: no transcript, arguments, results, rationale | D1 |
| 3 | an unloadable answer key aborts the remainder of the grid | D5 |
| 4 | archive written without strict-JSON enforcement | D3 |
| 5 | the loop's own recovery path emits a provider-invalid message | A10 |
| 6 | negative tool budget accepted, with two distinct wrong behaviours | A6 |
| 7 | a provenance failure permanently burns the grid label | D6 |
| 8 | no sampling configuration set or recorded | D7 |
| 9 | the first live model traversal is discarded | D8 |
| 10 | record schema drifted with no version field | D4 |
| 11 | an undistributed dependency name resolved from a public index | D10, X2 |
| 12 | permissive serialisation fallback duck-types on an attribute | D3 |
| 13 | no cost, context, or wall-clock ceiling on a paid loop | D9 |
| 14 | archives untracked; full working state retained per run | D13 |
| 15 | adapter config errors bypass the explanatory failure message | D7 |

## Found while auditing, or while fixing

| Defect | Requirement |
|---|---|
| executor-contract guards present but no test depends on them | X1 |
| model-controlled text executes in the report UI | D12 |
| declared dependency floor cannot send the pinned configuration | X2 |
| an advertised extra cannot import | X2 |
| a direct import relied on arriving transitively | X2 |
| unbounded per-client server state | X3 |
| eviction-based bound resets throttled clients | X3 |
| enforcing a bound costs more than the bound saves | A4 |
| one request-settable bound has no server-side ceiling | A8 |
| an unbounded default that is wrong on the paid path | A8 |
| a lint rule would reclassify model errors as platform errors | A9 |
| non-finite values accepted by a comparison-based guard | A7 |
| policy and decision-shape guards present but unproven | X1 |
| verification instrumented with the predicate it was validating | X1a |
| a large randomised sweep that never reached the boundary | X1b |
| a patch validated against a reconstruction, not the real module | X1, X4 |
| version compared as a string, rejecting a correct floor | X2 |
| no automation: the suite runs only when someone remembers | X4 |
| archives embed machine-specific absolute paths | D14 |
| recorded source revision cached for the process lifetime | D14 |
| a docstring promising more than the function delivers | D6 |
| a hand-written validator with no property tests | A3 |
| no per-test timeout; a hung test blocks rather than fails | X4 |
| a correct checkpoint escorted an arbitrary write; downstream checks detected it and the receipt reported detection as prevention | X1c |
| client-side timeouts and uncollected batch jobs summed as zero spend; attempt files counted as transmissions | D15 |

## Inherited from the team conformance document

A5, B1, B2, B3, B4, C1, C2, C3, C4, C5, C6, D2 and D11 originate in the team's own
conformance document rather than in the private implementation's audit. Their reproductions
are stated in the requirement bodies above and are not re-derived here. Two are worth
calling out because they are the ones most easily lost:

- **C1** is the requirement with the largest gap between "looks satisfied" and "is
  satisfied", and it is buildable now against fakes. Do not defer it until a model exists.
- **B4** must be built independently. The private evaluation harness is provenance for it,
  never a dependency.

## Deliberately not carried

Typing-annotation defects, unused imports, formatting, a licence file, a stale build
artifact, a linter false positive, and a weak-hash warning on a git blob digest. These were
real findings in the private implementation and are matters of local hygiene, not
conformance requirements for an independent implementation.
