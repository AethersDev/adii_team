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
    what: "A bounded autonomous investigator for data incidents. Its job is not to repair " +
      "everything: it determines what action, if any, the evidence justifies — repair, no " +
      "repair, or escalate — reading the data only through tools it is allowed to use, " +
      "recording every step, and never grading its own work.",
    readOnly: "This page is read-only. It shows runs the runtime archived and can start " +
      "none: a page that can start a run can spend money.",
    /* the launcher's one line of context: the model, where it runs and the bounds — the
     * server's, or chosen under Run settings within them; a paid provider is named as such */
    runsWith: (model, provider, cost, turns) => `Runs with ${model} ${provider === "openai"
      ? `at a paid provider · up to $${Number(cost).toFixed(2)}` : "on this machine"}` +
      ` · ${turns} turns. One investigation at a time.`,
    /* the product form: what looks wrong, over the visitor's own files — or an example */
    ask: "What looks wrong?",
    askFor: "e.g. Revenue dropped 45% after yesterday's deploy. Product wants a rollback.",
    yourData: "Your data",
    dataHint: "CSV files, one table each, named after the file. ADII reads them through its " +
      "tools and changes nothing.",
    needBoth: "Say what looks wrong and attach at least one CSV file — or try an example below.",
    tryExample: "No data handy? Try an example",
    exampleWhat: "The incidents ADII was built and tested on, each over its own data.",
    /* the run in progress, and what it has looked at */
    soFar: (requests, answered) => `${requests} request${requests === 1 ? "" : "s"} so far · ` +
      `${answered} answered.`,
    looked: (n) => `${n} observation${n === 1 ? "" : "s"}`,
    lookedAtNothing: "It looked at nothing before deciding: no request was answered.",
    idle: "Nothing is running now.",
    busy: (label) => `Investigating now: ${label}`,
    history: (incidents, runs) => `${incidents} incident${incidents === 1 ? "" : "s"} · ` +
      `${runs} run${runs === 1 ? "" : "s"}`,
    liveHow: "To allow runs from the page, start the server with a local model:",
    liveCommand: "python -m adii.demo 8000 --endpoint http://127.0.0.1:8090/v1 " +
      "--model <model id> --served-as default_model",
    running: "Investigating. Every turn appears here as it happens; the record lands when the " +
      "run ends.",
    /* the footer of every screen: what this page can start, and what it never reaches */
    footReadOnly: "Read-only: runs are started from the command line. Nothing is sent to an " +
      "outside service.",
    footLive: (provider) => (provider === "openai"
      ? "Investigations run at a paid provider, one at a time; each is receipted and " +
        "capped before it starts."
      : "Investigations run on this machine, one at a time. Nothing is sent to an " +
        "outside service."),
    empty: "An incident appears here once the runtime has investigated it and archived the run.",
    /* feedback: the operator's assertion about a run, kept beside the record, attributed */
    feedbackAsk: "Was this investigation useful to you?",
    feedbackExpected: "What did you expect to see, or what was missing?",
    feedbackBy: "Your name (optional)",
    feedbackRecorded: "Feedback recorded. It is kept beside this run's record, in your words.",
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
  /* what the disposition asks of the person reading it — the contract's meaning, as an
   * instruction, and nothing the record does not say */
  action: {
    REPAIR: "A change was proposed. Nobody has applied it; it is shown below, and until a " +
      "validator accepts it, it stays a proposal.",
    NO_REPAIR: "Do not change the data or the pipeline.",
    ESCALATE: "Hand this to a person. The evidence gathered does not settle it.",
  },

  /* ── how a run ended: one sentence per termination class ──────────────
   * Inputs are record fields only. `detail` is the loop's own words and is always shown
   * beside the sentence, verbatim, so the projection never replaces the source. */
  ended: {
    submitted: (r) => `The investigator committed to ${r.decision.disposition}.`,
    bound_hit: (r) => `The investigator reached a bound it set after ${r.counters.model_turns} ` +
      `model turn${r.counters.model_turns === 1 ? "" : "s"} and ${r.counters.tool_calls} tool ` +
      `call${r.counters.tool_calls === 1 ? "" : "s"}, and stopped without a decision.`,
    model_failure: () => "The model failed and the run stopped without a decision.",
    infrastructure_failure: () => "Something outside the model failed — the runtime or the " +
      "provider, not " +
      "the model's — and the run stopped without a decision.",
  },

  /* the validator's verdict as the record states it: accepted; not accepted after checks;
   * or not checked at all — `checks_run` empty — which is not a finding about the repair */
  verdict: {
    ACCEPT: "accepted by the validator",
    REJECT: "not accepted by the validator",
    UNCHECKED: "not checked by a validator",
  },
  verdictOf: (v) => (v.accepted ? "ACCEPT" : v.checks_run.length ? "REJECT" : "UNCHECKED"),

  /* the outcome as a headline, from the same fields: what an operator reads first */
  headline: {
    submitted: (r) => `Decided: ${r.decision.disposition}` + (r.validation
      ? ` — ${PHRASING.verdict[PHRASING.verdictOf(r.validation)]}` : ""),
    bound_hit: () => "Stopped at its limit, no decision",
    model_failure: () => "Stopped: the model failed, no decision",
    infrastructure_failure: () => "Stopped: a failure outside the model, no decision",
  },

  /* the same classes as a short label for lists and cards */
  outcome: {
    submitted: (r) => r.decision.disposition + (r.validation
      ? ` · ${PHRASING.verdict[PHRASING.verdictOf(r.validation)]}` : ""),
    bound_hit: () => "Stopped at its limit, no decision",
    model_failure: () => "Stopped: the model failed, no decision",
    infrastructure_failure: () => "Stopped: a failure outside the model, no decision",
  },

  /* what the run cost: nothing without a paid provider; otherwise the ledger's lower bound
   * — proved usage at nominal prices — with the requests it could not price counted */
  cost: (r) => {
    if (!r.configuration || r.configuration.provider !== "openai") {
      return r.counters.api_cost_usd ? `$${r.counters.api_cost_usd}` : "nothing spent (no paid provider)";
    }
    const asked = r.trace.filter((e) => e.kind === "model_requested").length;
    const priced = r.trace.filter((e) => e.kind === "model_responded" && e.payload.usage
      && Number.isInteger(e.payload.usage.prompt_tokens)).length;
    return `at least $${r.counters.api_cost_usd.toFixed(4)}` +
      (asked > priced ? ` (${asked - priced} request(s) without usage)` : "");
  },

  /* ── a turn: the model's request and everything it caused, in one sentence each ──── */
  turn: {
    asked: (name, args) => `Asked the tool layer to run ${name}${describeArgs(args)}`,
    answered: (p) => ({
      OK: `answered${describeContent(p.content)}`,
      DENIED: `refused${describeError(p.content)}`,
      REJECTED: `rejected the arguments${describeError(p.content)}`,
      ERROR: `failed${describeError(p.content)} — a defect of ours`,
    })[p.status] || `returned ${p.status}`,
    wrote: "The model wrote, instead of acting:",
    decided: (disposition) => `Committed to ${disposition}`,
    validated: (v) => ({ ACCEPT: "The validator accepted the repair",
      REJECT: "The validator did not accept the repair",
      UNCHECKED: "No validator checked the repair" })[PHRASING.verdictOf(v)],
    unanswered: "The run ended before this call was answered",
  },

  /* ── the evaluation authority's category: one sentence each, from its own definitions
   * (evaluation/outcome_classification.py); the category itself is shown beside it ── */
  evaluation: {
    success: "The decision matched the answer key.",
    correct_abstention: "The decision to escalate matched the answer key.",
    unnecessary_escalation: "The decision escalated where the answer key names a call.",
    false_repair: "A repair was proposed for a root cause the answer key does not name.",
    repair_rejection: "The repair named the answer key's root cause and was not accepted by " +
      "the validator.",
    failure: "The decision did not match the answer key.",
    not_evaluable: "No decision was submitted, so there was nothing to score.",
    settledBy: { deterministic: "the scoring rules", judge: "the judge", none: "no one" },
    /* orthogonal to the score: what the runtime did with the decision before anyone scored
     * it — from the record's own validation, so every archived run says it */
    runtime: {
      none: "no repair was proposed, so nothing was checked",
      unchecked: "the repair was archived unchecked — not blocked; the score found it afterwards",
      accepted: "the validator checked the repair before this score, and accepted it",
      rejected: "the validator checked the repair before this score, and did not accept it",
    },
  },

  /* ── the validator's row ─────────────────────────────────────────── */
  validation: {
    accepted: "The validator accepted the repair.",
    rejected: "The validator did not accept the repair.",
    unchecked: "No validator checked the repair.",
    notInvoked: "No repair was proposed, so there was nothing to validate.",
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
