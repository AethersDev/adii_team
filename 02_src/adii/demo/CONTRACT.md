# contracts/demo/v0

> **This is a demo schema.** It exists to demonstrate information flow through the
> architecture. It is **not** the team contract and it is **not** frozen. The real
> contracts live in `02_src/adii/contracts/` and the two are expected to diverge during M1
> integration. Do not treat a field here as a requirement — some exist purely because the
> interface needed something to render.
>
> What *is* intentional is the **shape**: which component produces each part, and which
> boundary it crosses.

```jsonc
{
  "schema": "contracts/demo/v0",
  "fixture": true,                       // this run was not produced by anything

  "incident":  { "incident_id", "title", "alert", "as_of" },        // → A
  "posture":   { "label", "max_tool_calls", "evidence_gated" },     // disclosure, not a control

  "trace": [                                                        // A ⇄ B, observed by D
    { "n", "id": "E3", "tool", "status", "request", "observation" }
  ],

  "decision": {                                                     // investigator → validation
    "disposition": "REPAIR | NO_REPAIR | ESCALATE",
    "root_cause_id", "claim",
    "evidence": ["E3", "E6"],            // citations INTO the trace — this is the
                                         // grounding idea, prefigured
    "missing_evidence"                   // ESCALATE only: what is absent and why decisive
  },

  "candidate_repair": {                                             // investigator → validation, REPAIR only
    "repair_id", "path", "removed", "added",
    "agent_visible_checks",              // the agent's own rehearsal — a HYPOTHESIS
    "agent_check_note"
  },

  "validation": {                                                   // validation → telemetry, REPAIR only
    "verdict": "ACCEPT | REJECT",        // the VERDICT. different authority.
    "method", "findings": []
  },

  "usage":       { "tool_calls", "model_turns", "input_tokens", "output_tokens",
                   "api_cost_usd", "latency_ms" },                  // D
  "provenance":  { "run_id", "scenario_id", "model", "provider", "seed",
                   "team_repo_sha", "evaluation_authority_sha", ... },

  "evaluation": {                                                   // NOT from the runtime
    "available_to_investigator": false,  // the whole point of the flag
    "expected_disposition", "observed_disposition",
    "root_cause", "repair", "full_incident_success", "note"
  }
}
```

## Presentation-only fields

`intro` and each trace step's `plain` exist so the orientation layer can render a run
without identifiers or jargon. They are **not** part of any real contract — a production
run would carry no such thing. They live in the fixture because hardcoding the copy
into the page would have made the orientation layer a set of mockups rather than one
renderer over the same data.

```jsonc
"intro": { "alert", "question", "checks": [1,2,3], "decision", "fix", "takeaway" },
"trace": [ { ..., "plain": "Counted unique order IDs — only 26." } ]
```

## The one field that matters most

`evaluation.available_to_investigator: false`. Everything under `evaluation` comes from
the frozen answer key in a separate repository. It is in this document only so the
interface can render a view that says, in as many words, *the investigator could not see
this*. In the real system it never travels alongside a run at all.
