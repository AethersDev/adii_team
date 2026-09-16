/* The phrasing dictionary: every sentence the inspector adds to a record.
 *
 * Each function here is a deterministic projection of record fields. It composes what the
 * record states and adds no cause, no judgement and no guess: never "it could not decide",
 * never "the evidence was insufficient", unless those words are in the record. Every entry
 * is listed in the package README and tested in test_phrasing.py, so plain language is a
 * presentation function the team can read in one place and strike, not editorial copy
 * scattered through templates.
 *
 * Product copy — what ADII is, how to create a run — is UI text, not run data. It describes
 * the product, never a particular execution, and it also lives here so there is one place. */

const PHRASING = {
  /* ── product copy ─────────────────────────────────────────────────── */
  product: {
    name: "Autonomous Data Incident Investigator",
    what: "ADII investigates data incidents using bounded tools, records the evidence it " +
      "observes, and produces a structured decision when the evidence supports one. Any " +
      "repair it proposes is checked by a separate validator; it never grades its own work.",
    readOnly: "This inspector is read-only. It shows runs the runtime archived and can start " +
      "none: a page that can start a run can spend money.",
    createRun: "python -m adii.runtime --incident demo-learning-001 --provider scripted",
    specimens: "python -m adii.examples.specimens",
    specimensWhat: "Six development incidents with scripted example runs — made up, no model, " +
      "no evaluation claim:",
    thenOpen: "python -m adii.demo",
    /* shown wherever a record's model is null: a scripted run, never a model result */
    scripted: "Scripted investigator · development demonstration, not a model result",
  },

  /* ── dispositions: the contract's own definitions ─────────────────── */
  disposition: {
    REPAIR: "A specific fault exists and the evidence justifies a specific fix.",
    NO_REPAIR: "The pipeline is sound. The metric moved because the business moved.",
    ESCALATE: "The available evidence cannot justify either call. The run completed.",
  },

  /* ── how a run ended: one sentence per termination class ──────────────
   * Inputs are record fields only. `detail` is the loop's own words and is always shown
   * beside the sentence, verbatim, so the projection never replaces the source. */
  ended: {
    submitted: (r) => `The investigator committed to ${r.decision.disposition}.`,
    bound_hit: (r) => `The investigator reached a bound it set after ${r.counters.tool_calls} ` +
      `tool call${r.counters.tool_calls === 1 ? "" : "s"} and stopped without a decision.`,
    model_failure: () => "The model failed and the run stopped without a decision.",
    infrastructure_failure: () => "Something in the runtime failed — a defect of ours, not " +
      "the model's — and the run stopped without a decision.",
  },

  /* the same classes as a short label for lists and cards */
  outcome: {
    submitted: (r) => r.decision.disposition + (r.validation
      ? ` · ${r.validation.accepted ? "accepted" : "not accepted"} by the validator` : ""),
    bound_hit: () => "Ended at a bound, no decision",
    model_failure: () => "Ended by a model failure, no decision",
    infrastructure_failure: () => "Ended by a failure of ours, no decision",
  },

  /* ── the validator's row ─────────────────────────────────────────── */
  validation: {
    accepted: "The validator accepted the repair.",
    rejected: "The validator did not accept the repair.",
    notInvoked: "No repair was proposed, so there was nothing to validate.",
  },

  /* ── trace steps: one sentence per event kind, from its payload ────────
   * Every step is reversible to its event: the raw payload sits beside it. Unknown kinds
   * fall through to the kind's own name — the page never guesses at a vocabulary it does
   * not know. */
  step: {
    incident_received: (p) => `The investigator received incident ${p.incident_id}.`,
    tool_call: (p) => `It asked the tool layer to run ${p.name}${describeArgs(p.arguments)}.`,
    tool_result: (p) => ({
      OK: `The tool layer answered ${p.name}${describeContent(p.content)}.`,
      DENIED: `The tool layer refused ${p.name}${describeError(p.content)}.`,
      REJECTED: `The tool layer rejected the arguments to ${p.name}${describeError(p.content)}.`,
      ERROR: `The tool ${p.name} failed${describeError(p.content)} — a defect of ours.`,
    })[p.status] || `The tool layer returned ${p.status} for ${p.name}.`,
    decision_submitted: (p) => `The investigator committed to ${p.disposition}.`,
    validation_completed: (p) => `The validator ${p.accepted ? "accepted" : "did not accept"} the repair.`,
    /* the provider boundary (spike, pending the trace event contract): what the model was
     * asked, and what it said — its words, as text */
    model_requested: (p) => `The model was asked for turn ${p.turn}.`,
    model_responded: (p) => `The model answered: ${p.content}`,
  },
};

/* helpers that quote the payload — text only, never interpretation */
function describeArgs(args) {
  if (!args || typeof args !== "object") return "";
  const entries = Object.entries(args);
  if (!entries.length) return "";
  return " with " + entries.map(([k, v]) => `${k} = ${short(v)}`).join(", ");
}
function describeContent(c) {
  if (!c || typeof c !== "object") return "";
  if (Array.isArray(c.rows)) return ` with ${c.rows.length} row${c.rows.length === 1 ? "" : "s"}`;
  if (Array.isArray(c.columns)) return ` with ${c.columns.length} column${c.columns.length === 1 ? "" : "s"}`;
  return "";
}
function describeError(c) {
  return c && typeof c === "object" && typeof c.error === "string" ? `: ${c.error}` : "";
}
function short(v) {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > 72 ? `${s.slice(0, 69)}…` : s;
}
