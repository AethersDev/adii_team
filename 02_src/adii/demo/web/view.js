/* ADII's front door: what the page says, as pure projections of a run record.
 *
 * Every word and number the page shows about a run comes from here, from the record and
 * nothing else, and each function is evaluated in node by test_the_front_door_projects.py
 * exactly as the page runs it. The renderer (app.js) only draws what these return.
 *
 * Three rules hold the story (final plan, decisions F1–F3):
 *   the alerted series (`alert_observed`) is the symptom — what triggered the run, never
 *     evidence, so it is never among what ADII knows;
 *   the rebuilt series is the validator's reading of its own rebuild, and is labelled so;
 *   "How ADII knows" is the observations the decision cited, and only those — everything
 *     the run looked at is "Investigated".
 */
"use strict";

const ANSWERS = {
  REPAIR: { key: "fix", label: "Fix it" },
  NO_REPAIR: { key: "leave", label: "Leave it" },
  ESCALATE: { key: "escalate", label: "Escalate it" },
};
const SLOTS = [["fix", "Fix it"], ["leave", "Leave it"], ["escalate", "Escalate it"]];

function events(record, kind) {
  return (record.trace || []).filter((e) => e.kind === kind).map((e) => e.payload);
}

function admissible(record) {
  const a = record.authorization, v = record.validation;
  return Boolean(a && a.authorized && v && v.accepted);
}

/* The answer, as the record states it: the disposition, and for a repair whether the two
 * authorities let it stand. A run that ended without a decision says how it ended. */
function verdict(record) {
  const d = record.decision;
  if (!d) {
    const ending = {
      bound_hit: (record.detail || "").startsWith("max_cost_usd")
        ? ["Stopped at the spending cap.",
           "The next request could have taken the run past its cap, so ADII didn't send it. " +
           "Nothing was changed."]
        : ["Stopped at a limit.",
           "The run reached one of the limits it was given before it reached an answer. " +
           "Nothing was changed."],
      model_failure: ["The investigator stopped without an answer.",
        "The model ended its work without choosing Fix it, Leave it or Escalate it. That's " +
        "recorded as a model failure, not as an answer. Nothing was changed."],
      infrastructure_failure: ["The run couldn't finish.",
        "Something between ADII and the model failed. This is an infrastructure failure, " +
        "not a finding about your data. Nothing was changed."],
    }[record.termination] || ["No answer.", "The run ended without an answer."];
    return { key: "none", label: "No answer", headline: ending[0], lead: ending[1],
             detail: record.detail || "", summary: null };
  }
  const answer = ANSWERS[d.disposition];
  const summary = d.root_cause_summary || null;
  if (answer.key === "fix") {
    if (admissible(record)) {
      return { ...answer, headline: "Yes. Fix it.", summary, lead:
        "A fix was proposed, it is within what ADII may change here, and an independent " +
        "rebuild accepted it. The AI that proposed it didn't approve it." };
    }
    const a = record.authorization, v = record.validation;
    const why = a && !a.authorized
      ? "It touches something outside what ADII may change for this incident."
      : validatorState(v) === "UNCHECKED" ? "No validator checked it."
      : validatorState(v) === "NOT_CHECKABLE"
        ? "There was no world to rebuild, so it could not be checked."
      : validatorState(v) === "REJECT" ? "The independent rebuild rejected it."
      : "The rebuild accepted it, but this record predates the authorization check, so it " +
        "was never admitted.";
    return { ...answer, headline: "A fix was proposed. It was not approved.", summary,
             lead: why + " Nothing was changed." };
  }
  if (answer.key === "leave") {
    return { ...answer, headline: "No. Leave it.", summary,
             lead: "Nothing needs fixing, so no change was proposed." };
  }
  return { ...answer, headline: "Not yet. Escalate it.", summary,
           lead: "The evidence here can't settle it, so someone with more access should " +
                 "decide. No change was proposed." };
}

function slots(record) {
  const landed = record && record.decision ? ANSWERS[record.decision.disposition].key : null;
  return SLOTS.map(([key, label]) => ({ key, label, landed: key === landed }));
}

/* The validator's state as the contract derives it (contracts/core.py ValidationResult.state):
 * ACCEPT, REJECT, NOT_CHECKABLE, or UNCHECKED — the legacy no-checks shape of old records. */
function validatorState(v) {
  if (!v) return null;
  if (v.accepted) return "ACCEPT";
  if (v.reason_code) return "NOT_CHECKABLE";
  return (v.checks_run || []).length ? "REJECT" : "UNCHECKED";
}

/* Who did what: the investigator proposes, the authorizer permits, the validator checks —
 * each line from that authority's own fact in the record. */
function signoff(record) {
  const d = record.decision, a = record.authorization, v = record.validation;
  const proposed = d && d.disposition === "REPAIR";
  const lines = [{
    who: "Investigator", mark: "AI",
    status: !d ? "No answer" : proposed ? "Proposed a fix" : "No fix proposed",
    note: proposed ? "Proposed this change. Can't approve it." :
          d ? "Decided no change should be made." : "Ended without a decision.",
    tone: "plain",
  }];
  lines.push(!a && proposed ? { who: "Authorizer", mark: "AU", status: "Not recorded",
                               tone: "quiet", note: "This record predates the authorization check." }
    : !a ? { who: "Authorizer", mark: "AU", status: "Not needed", tone: "quiet",
             note: "Checks whether a proposed change is permitted." }
    : a.authorized
      ? { who: "Authorizer", mark: "AU", status: "Allowed", tone: "good",
          note: "Within what ADII may change here: " + a.checked_paths.join(", ") + "." }
      : { who: "Authorizer", mark: "AU", status: "Refused", tone: "bad",
          note: "Outside what ADII may change here: " + a.denied_paths.join(", ") + "." });
  if (!v) {
    lines.push({ who: "Validator", mark: "VA", status: "Not needed", tone: "quiet",
                 note: "Independently rebuilds the data to check a proposed change." });
  } else {
    const state = validatorState(v);
    lines.push({
      who: "Validator", mark: "VA",
      status: { ACCEPT: "Accepted", REJECT: "Rejected", NOT_CHECKABLE: "Couldn't check",
                UNCHECKED: "Not checked" }[state],
      tone: { ACCEPT: "good", REJECT: "bad", NOT_CHECKABLE: "quiet", UNCHECKED: "quiet" }[state],
      note: state === "NOT_CHECKABLE" ? "There was no world to rebuild."
        : state === "UNCHECKED" ? "No validator checked this repair."
        : "Rebuilt the data from a frozen copy, with the change applied, and ran " +
          v.checks_run.length + " checks.",
    });
  }
  return lines;
}

/* The validator's own report, one check per line, as it wrote it. A mark is drawn only for
 * the validator's own form — "rebuild: …; name: holds — …; name: fails — …" — and a report
 * in any other form is shown whole, unmarked: nothing is inferred from prose. */
function checks(record) {
  const v = record.validation;
  if (!v || !v.report) return [];
  if (!v.report.startsWith("rebuild: ")) return [{ name: "report", said: v.report, held: null }];
  return v.report.split(/; (?=[a-z_]+: )/).map((line) => {
    const cut = line.indexOf(": ");
    const name = line.slice(0, cut), said = line.slice(cut + 2);
    const held = name === "rebuild" ? !said.startsWith("patch rejected")
      : said.startsWith("holds") ? true : said.startsWith("fails") ? false : null;
    return { name, said, held };
  });
}

/* The symptom and the rebuild: the runtime's reading of the frozen world before anything
 * was investigated, and the validator's reading of its rebuild. */
function series(record) {
  const [alert] = events(record, "alert_observed");
  const rebuilt = record.validation && record.validation.rebuilt_series;
  return {
    before: alert && alert.rows.length ? { metric: alert.metric, unit: alert.unit,
                                           rows: alert.rows } : null,
    rebuilt: rebuilt && rebuilt.length ? { metric: alert ? alert.metric : "", rows: rebuilt }
                                       : null,
  };
}

function money(value, unit) {
  const n = Number(value);
  if (unit !== "USD") return n.toLocaleString("en-US");
  return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

/* How far the last point stands from the mean of the ones before it, in whole percent. */
function change(rows) {
  const values = rows.map((r) => Number(r[1]));
  const last = values[values.length - 1];
  const before = values.slice(0, -1);
  if (!before.length) return null;
  const mean = before.reduce((a, b) => a + b, 0) / before.length;
  return mean ? Math.round((last / mean - 1) * 100) : null;
}

const TOOL = {
  run_sql: "A query of the data",
  get_transform: "A transformation",
  get_notice: "A notice",
  get_change_history: "The pipeline's change history",
  read_reconciliation: "A reconciliation",
  get_schema: "The tables and their columns",
};

function calls(record) {
  const asked = {};
  events(record, "tool_call").forEach((c) => { asked[c.call_id] = c; });
  return events(record, "tool_result").map((r) => ({ call: asked[r.call_id] || {}, result: r }));
}

/* One observation, by a fixed template for its tool: a title, and either a table or text,
 * each taken from the recorded result and bounded. */
function observation(call, result) {
  const c = result.content || {};
  const tool = result.name;
  const title = {
    get_transform: "The transformation " + (c.transform_id || ""),
    get_notice: "Notice: " + (c.notice_id || ""),
    read_reconciliation: "Reconciliation: " + (c.reconciliation_id || ""),
  }[tool] || TOOL[tool] || tool;
  const table = (columns, rows) => ({ columns, rows: rows.slice(0, 6),
                                      more: Math.max(rows.length - 6, 0) });
  if (tool === "run_sql") {
    return { tool, title, code: (call.arguments || {}).query || "",
             table: table(c.columns || [], c.rows || []) };
  }
  if (tool === "get_change_history") {
    const changes = c.changes || [];
    return { tool, title, table: table(["date", "file", "ticket", "change"],
                                       changes.map((x) => [x.date, x.file, x.ticket, x.change])) };
  }
  if (tool === "get_transform") {
    return { tool, title, code: String(c.source || "").split("\n").slice(0, 14).join("\n") };
  }
  if (tool === "get_notice") {
    return { tool, title, text: String(c.content || "").replace(/^#[^\n]*\n+/, "").trim()
                                                      .slice(0, 400) };
  }
  if (tool === "read_reconciliation") {
    return { tool, title, text: (c.lines || []).slice(0, 8).join("\n") };
  }
  if (tool === "get_schema") {
    return { tool, title, text: (c.tables || []).map((t) => t.name).join(", ") };
  }
  return { tool, title, text: JSON.stringify(c).slice(0, 400) };
}

/* How ADII knows: the observations the decision cited, in the order it cited them. */
function cited(record) {
  const refs = (record.decision && record.decision.evidence_refs) || [];
  const byId = {};
  calls(record).forEach(({ call, result }) => {
    const id = result.content && result.content.evidence_id;
    if (result.status === "OK" && id) byId[id] = observation(call, result);
  });
  return refs.filter((ref) => byId[ref]).map((ref) => ({ ref, ...byId[ref] }));
}

/* Investigated: everything the run looked at, cited or not, refused or not. */
function investigated(record) {
  return calls(record).map(({ call, result }) => {
    const args = call.arguments || {};
    const what = args.query || args.transform_id || args.notice_id || args.history_id ||
                 args.reconciliation_id || args.table || "";
    return { tool: result.name, title: TOOL[result.name] || result.name, what: String(what),
             status: result.status };
  });
}

/* A line diff of a transformation as observed against the patch that replaces it. */
function diff(before, after) {
  const a = before.replace(/\n$/, "").split("\n"), b = after.replace(/\n$/, "").split("\n");
  const n = a.length, m = b.length;
  const lcs = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const out = [];
  let i = 0, j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) { out.push({ op: " ", text: a[i], line: j + 1 }); i++; j++; }
    else if (i < n && (j === m || lcs[i + 1][j] >= lcs[i][j + 1])) {
      out.push({ op: "-", text: a[i], line: i + 1 }); i++;
    } else { out.push({ op: "+", text: b[j], line: j + 1 }); j++; }
  }
  return out;
}

/* The proposed change, per file: against the transformation the run observed when it did,
 * otherwise the new contents alone. */
function proposal(record) {
  const patch = (record.decision && record.decision.patch) || {};
  const seen = {};
  calls(record).forEach(({ result }) => {
    const c = result.content || {};
    if (result.name === "get_transform" && result.status === "OK") seen[c.transform_id] = c.source;
  });
  return Object.keys(patch).sort().map((path) => {
    const id = path.split("/").pop().replace(/\.sql$/, "");
    const before = seen[id];
    return { path, observed: before !== undefined,
             lines: before !== undefined ? diff(before, patch[path])
                                         : diff("", patch[path]).filter((l) => l.op === "+") };
  });
}

/* What a paid run cost, as the ledger can prove it: a lower bound, with every request whose
 * usage was never reported counted rather than priced at zero (requirement D15). */
function spend(record) {
  const c = record.configuration || {};
  if (c.provider === "local") return "Nothing spent: a local model";
  if (c.provider !== "openai") return "Nothing spent: no model was asked";
  const asked = events(record, "model_requested").length;
  const priced = events(record, "model_responded").filter((r) => r.usage &&
    Number.isInteger(r.usage.prompt_tokens) && Number.isInteger(r.usage.completion_tokens)).length;
  const cost = Number((record.counters || {}).api_cost_usd || 0);
  const cap = Number(c.max_cost_usd);
  return "at least $" + cost.toFixed(4) + (Number.isFinite(cap) ? " of a $" + cap.toFixed(2) +
    " cap" : "") + (asked > priced ? "; " + (asked - priced) + " request(s) without usage" : "");
}

/* A row of the investigations list, from the server's index. */
function row(entry, now) {
  const answer = entry.running ? { key: "running", label: "Investigating" }
    : entry.error ? { key: "none", label: entry.error.includes("did not finish")
                                           ? "Did not finish" : "Unreadable" }
    : entry.disposition ? ANSWERS[entry.disposition]
    : { key: "none", label: "No answer" };
  const changed = entry.changed || [];
  return {
    label: entry.label, answer: answer.key, answerLabel: answer.label,
    title: entry.alert || entry.incident_id || entry.label,
    change: entry.running ? "Pending" : !changed.length ? "Nothing"
      : entry.admissible ? changed.length + (changed.length === 1 ? " file" : " files")
      : "Proposed, not approved",
    when: entry.written_at ? ago(entry.written_at, now) : entry.running ? "Just now" : "",
    error: entry.running ? null : entry.error || null,
  };
}

function ago(iso, now) {
  const s = Math.max(0, (now - Date.parse(iso)) / 1000);
  if (s < 60) return "Just now";
  if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " hr ago";
  const d = Math.floor(s / 86400);
  return d === 1 ? "Yesterday" : d + " days ago";
}

const VIEW = { verdict, slots, signoff, checks, series, money, change, cited,
               investigated, proposal, diff, spend, row, ago, admissible, validatorState };
if (typeof module !== "undefined") module.exports = VIEW;
