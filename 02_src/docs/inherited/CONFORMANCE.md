# Conformance requirements

Fifteen defects found by audit in a working ADII implementation, plus seven more in the
fixes for them. Restated as requirements, grouped by the capability they constrain. Each is a
test worth writing.

Format: **the requirement**, then *why* — the concrete failure it prevents.

---

## Agent loop — the investigator

**A1. A wrong-typed tool argument is a REJECTED result, not a crash.**
Validate arguments against the schema you advertised *before* dispatch. Binding checks
arity; it never checks types.
*Why:* `run_sql(query=123)` binds fine, then raises inside the tool. That exception is
indistinguishable from a real platform fault, so the run dies and gets archived as
*infrastructure failure* — a **model** error filed as a **platform** error, in the very
artifact used to judge tool-use reliability. Four of six probed shapes killed the run.

**A2. The guard belongs in the loop, not in one executor.**
*Why:* the loop advertises the schemas, so the loop owes the check — and putting it there
closes the class for every executor rather than the one where it was found.

**A3. A schema form you cannot validate must be refused, not waved through.**
*Why:* a validator that silently ignores `boolean`, nested `properties`, or `enum`
advertises a constraint it does not enforce. Fail loudly at the boundary instead.

**A4. The loop must terminate, and every bound must be enforced *after* the request too.**
*Why:* checking only before a request lets the completion that breaks the ceiling go on to
submit a decision — so a run exceeds its deadline and still produces a scored result.

**A5. A bound is not a model failure.** Raise a distinct error carrying which bound was hit.
*Why:* an archive that records "the model failed to submit" when the operator's ceiling
stopped it misreports model behaviour.

**A6. A public API enforces its own invariants; a CLI check is not enough.**
*Why:* `max_tool_calls` was validated at the CLI only. Negative values reached the loop
through every other caller. Worse, `-1..-3` did not crash — they produced a *scored*
record, indistinguishable from a legitimate control arm.

**A7. Reject at construction anything that would silently disable a bound.**
NaN, infinity, negatives, booleans.
*Why:* every comparison against NaN is false, so an unvalidated NaN produces an unbounded
run that looks bounded.

---

## Tool execution — the tools

**B1. `DENIED`, `REJECTED`, and `ERROR` are three different things.**
Refused / the model's arguments were wrong / our bug.
*Why:* conflating `REJECTED` with `ERROR` makes the model look worse than it is and
corrupts the measurement.

**B2. Bound every result.** Row caps, line windows.
*Why:* an unbounded result becomes an unbounded context, and the failure appears far away
from its cause.

**B3. No tool takes a filesystem path.**
*Why:* a tool that accepts a path can be pointed at the answer key.

**B4. Enforce read-only at the database, not by inspecting the query text.**
*Why:* a regex over SQL is a suggestion. An authorizer is a boundary.

---

## Validation and evaluation

**C1. Independent validation rebuilds from frozen inputs and never consults the agent's
own rehearsal.**
*Why:* the agent's sandbox reports PASS on repairs that are wrong. In a real run it halved
a day's revenue after seeing 11 of 26 orders duplicated; its own checks were green and
independent validation rejected it. Right disposition, right root cause, wrong repair —
and nothing the agent could see would have told it.

**C2. Answer keys are frozen by hash and never edited.** A correction is a **new file**.
*Why:* evidence scored against a key means nothing if the key can move afterwards.

**C3. Authorities that freeze at different times must be different artifacts.**
See [AUTHORITY_LIFECYCLE.md](AUTHORITY_LIFECYCLE.md).

**C4. Version dispatch must be explicit.** A v1 artifact carrying a v2 field is an error,
never an implicit upgrade.

**C5. A published schema and the code that validates must be checked against each other by
a test.**
*Why:* they drifted silently, because nothing loaded the published schema. Documentation
with no test is a statement about the past.

**C6. Scoring semantics changes are pre-registered, never post-hoc.**
*Why:* changing what "success" means after seeing results is how a real finding becomes an
unfalsifiable one.

---

## Telemetry — platform and observability

**D1. The archive must be self-contained.** Messages, tool arguments, tool results, the
rationale, and the patch.
*Why:* a run that proposed a repair, had it validated, and passed left **no record of what
the repair was**. Digests prove a call happened; they cannot reconstruct it. Neither replay
nor a report is buildable from that.

**D2. Counters come from the trace, never self-reported.**
*Why:* an agent must not be able to flatter its own efficiency.

**D3. Records are strict RFC-8259 JSON, or they are archived as failures.**
Validate the payload *before* it reaches the sink.
*Why:* a non-finite cost wrote literal `Infinity` while reporting `status: scored` and
exiting 0. And adding strictness at the write itself only trades an invalid archive for a
**missing** one, since it raises outside the classification boundary.

**D4. Every record carries a schema version.**
*Why:* the record shape changed once already, and a reader had to infer it by probing keys.

**D5. One failed unit must not abandon the run.** Archive it, classify it, continue.
*Why:* one unloadable answer key aborted an entire grid and archived nothing — including
for the scenario that would have succeeded.

**D6. A partial failure must not consume a name that cannot be reused.**
*Why:* a provenance failure left an empty directory behind, and the never-overwrite rule
then refused every retry under the pre-registered label.

**D7. Pin the model configuration and record it, including a per-response backend
fingerprint.**
*Why:* runs otherwise execute at whatever the provider defaults to that day, and the
archive cannot state what that was. `seed` is best-effort by the provider's own
documentation; the fingerprint is the only signal the serving stack moved.

**D8. An irreversible action must be archived before it is spent, including on the failure
path.**
*Why:* the first exposure of an incident to a model ran inside a temporary directory and
left only a timestamp and terminal scrollback. There is no second first exposure.

**D9. Cost, context, and wall-clock are three separate bounds.** None supplies the others,
and a cost cap compared between requests is *soft* — say so rather than implying otherwise.

**D10. Never publish an unbound dependency name.**
*Why:* an extra resolved a name the project does not own from a public index.

**D11. Report success and failure with equal legibility.**
*Why:* a report that only reads well when the agent was right is marketing.
