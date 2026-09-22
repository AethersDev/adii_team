# Investigation decision policy

Task A produces one structured `InvestigationDecision`. The disposition records what the
investigator can justify from controlled evidence; it does not grant validation or
evaluation authority.

## REPAIR

- Requires at least one observed `ToolResult`.
- Carries a concrete repair proposal through the existing `repair_id` and `patch` fields.
- Means that Task A proposes a bounded intervention for independent validation.
- Does not mean that the repair has been validated or accepted.

## NO_REPAIR

- Requires at least one observed `ToolResult`.
- Means the evidence supports that intervention is not justified.
- Must not be used to mean "I don't know" or to stand in for insufficient evidence.

## ESCALATE

- Does not require a prior `ToolResult`.
- Applies when evidence is unavailable or insufficient, authority is lacking, or no safe
  decision can be made.
- Should identify the concrete missing evidence or constraint, not rely on vague confidence
  wording.

## Validation boundary

- Task A proposes; Task C validates independently.
- Task A never fabricates a `ValidationResult`.
- Task A never claims that a proposed repair was accepted.

## Invalid submissions

- A reply that is none of the three message forms, a decision that fails the contract, or
  one the evidence gate refuses is an invalid submission: recorded as `decision_rejected`
  with a class and a bounded reason, the reason returned to the model once, the loop
  continuing under its bounds. No form is special-cased and nothing is reinterpreted as a
  decision — the closed grammar stays closed.

## Evidence grounding

Decided 22 September 2026 (trace contract row 3): a decision names the observations it
rests on in `evidence_refs`, by the evidence ids the tool layer minted on successful
results. The gate is mechanical and objective: every cited id must be one the model
received in this run, or the decision is an invalid submission (`decision_rejected`,
class `evidence_gate`, the ids named, the reason returned once) — an id one character off
a minted one is one the model never saw. The minimum-observation rule stays as it is:
REPAIR and NO_REPAIR need an observation, ESCALATE does not, and none of the three is
required to cite. `root_cause_summary` still describes the reasoning in prose. Neither the
gate nor this policy claims the cited observations warrant the conclusion: cited means
observed, and whether it was the decisive observation is the evaluation authority's
question, answered by a grounding key.
