/* ADII's front door: what the page says, as pure projections of a run record.
 *
 * Every word and number the page shows about a run comes from here, from the record and
 * nothing else, and each function is evaluated in node by test_the_front_door_projects.py
 * exactly as the page runs it. The renderer (app.js) only draws what these return.
 *
 * These rules hold the story (final plan, decisions F1–F3):
 *   the alerted series (`alert_observed`) is the symptom — what triggered the run, never
 *     evidence, so it is never among what the decision cites;
 *   the rebuilt series is the validator's reading of its own rebuild, and is labelled so;
 *   "What the decision cites" is the observations the decision cited, and only those —
 *     everything the run looked at is "Investigated";
 *   a decision is the investigator's recommendation, never the page's own finding: the page
 *     says what the record holds about it and does not judge whether it is right;
 *   a compact view of an observation says what it leaves out, and the rest is one click away.
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

/* The decision, as the record states it: what the investigator recommended, what the record
 * holds about its observations, and for a repair what the two authorities did with it. The
 * words do not depend on whether the decision is right, which the page cannot know. A run
 * that ended without a decision says how it ended. */
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
             detail: record.detail || "", summary: null, basis: null };
  }
  const said = { ...ANSWERS[d.disposition], summary: d.root_cause_summary || null,
                 headline: "Investigator recommended " + d.disposition, basis: basis(record) };
  if (said.key !== "fix") {
    return { ...said, lead: "It proposed no change, so the authorizer and validator checked " +
                            "nothing." };
  }
  if (admissible(record)) {
    return { ...said, lead:
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
  return { ...said, lead: why + " Nothing was changed." };
}

/* What the record holds about a decision's footing: counts, never a judgment of it. A
 * citation says the observation exists; it does not say the observation warrants the
 * decision, and an older record that has no citations is not one that cited nothing. */
function basis(record) {
  const got = calls(record).filter(({ result }) => result.status === "OK").length;
  if (!got) return "This run collected no tool observations.";
  const held = got + " tool observation" + (got === 1 ? "" : "s");
  if (!record.decision.evidence_refs) {
    return "This run collected " + held + ". Its record predates citations, so it doesn't " +
           "say which ones the decision cites.";
  }
  const n = cited(record).length;
  return n ? "The decision cites " + n + " of the " + held + " this run collected."
           : "This run collected " + held + ", and the decision cites none of them.";
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
          d ? "Recommended " + d.disposition + ". Proposed no change."
            : "Ended without a decision.",
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

/* The compact view of recorded rows or lines: what it shows, everything it came from, and
 * what it says when it leaves anything out. Nothing is cut without saying so. */
function compact(all, keep, noun, fromEnd) {
  const shown = fromEnd ? all.slice(-keep) : all.slice(0, keep);
  if (shown.length === all.length) return { shown, all, note: null, expand: null };
  return { shown, all,
           note: (fromEnd ? "The last " : "The first ") + keep + " of " + all.length + " " + noun +
                 ". The other " + (all.length - keep) + " are not shown here.",
           expand: "Show all " + all.length + " " + noun };
}

/* Lines with the numbers they have at the source, however little of it was read. */
function numbered(lines, first) {
  return lines.map((text, i) => ({ n: first + i, text }));
}

/* One observation, by a fixed template for its tool: a title, and a table, numbered lines or
 * text, each taken from the recorded result. `received` says what the tool kept from the run,
 * a different limit from what a compact view leaves out: no click on this page can show it. */
function observation(call, result) {
  const c = result.content || {};
  const tool = result.name;
  const title = {
    get_transform: "The transformation " + (c.transform_id || ""),
    get_notice: "Notice: " + (c.notice_id || ""),
    read_reconciliation: "Reconciliation: " + (c.reconciliation_id || ""),
  }[tool] || TOOL[tool] || tool;
  const table = (columns, rows) => ({ columns, ...compact(rows, 6, "returned rows", false) });
  if (tool === "run_sql") {
    const rows = c.rows || [];
    const received = c.truncated
      ? "The tool stopped at " + rows.length + " rows. The query had more, and the run never " +
        "received them."
      : null;
    return { tool, title, received, code: (call.arguments || {}).query || "",
             table: table(c.columns || [], rows) };
  }
  if (tool === "get_change_history") {
    const changes = c.changes || [];
    return { tool, title, table: table(["date", "file", "ticket", "change"],
                                       changes.map((x) => [x.date, x.file, x.ticket, x.change])) };
  }
  if (tool === "get_transform") {
    const source = String(c.source || "").replace(/\n$/, "").split("\n");
    return { tool, title, lines: compact(numbered(source, 1), 14, "lines", false) };
  }
  if (tool === "get_notice") {
    return { tool, title, text: String(c.content || "").replace(/^#[^\n]*\n+/, "").trim() };
  }
  if (tool === "read_reconciliation") {
    // a log's outcome is at its end. What the run never read is not what the page left out.
    const lines = c.lines || [], first = (c.offset || 0) + 1;
    const total = c.total_lines === undefined ? lines.length : c.total_lines;
    const received = lines.length === total ? null
      : lines.length ? "The run read lines " + first + "–" + (first + lines.length - 1) +
                       " of " + total + "."
      : "The run read none of the log's " + total + " lines.";
    return { tool, title, received,
             lines: compact(numbered(lines, first), 8, "lines read", true) };
  }
  if (tool === "get_schema") {
    return { tool, title, text: (c.tables || []).map((t) => t.name).join(", ") };
  }
  return { tool, title, text: JSON.stringify(c) };
}

/* What the decision cites: the observations it cited, in the order it cited them, each as a
 * result of the tool layer and never as anything the investigator said. */
function cited(record) {
  const refs = (record.decision && record.decision.evidence_refs) || [];
  const byId = {};
  calls(record).forEach(({ call, result }) => {
    const id = result.content && result.content.evidence_id;
    if (result.status === "OK" && id) {
      byId[id] = { ...observation(call, result), origin: "Returned by the tool layer" };
    }
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
