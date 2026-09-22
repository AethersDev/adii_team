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

The current `InvestigationDecision` contract has no `evidence_ids` field, and this policy
does not change the shared contract. `root_cause_summary` should describe how the decision
is grounded in observed evidence. Task A enforces only the objective minimum-observation
rule; it does not claim that the model's prose is semantically true.
