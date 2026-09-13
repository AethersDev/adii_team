/* ADII run inspector — the operational surface over the run archive.
 *
 * ONE renderer for every record. There is deliberately no renderRepair(), renderBoundHit()
 * or similar: the record changes, the renderer does not. It renders `adii.run_record/v1`
 * and nothing else — a record in any other shape gets the contract-mismatch state, never a
 * guess — and it invents no field: everything on the page is in the record.
 *
 * The record is drawn as a chain of custody. Every block hangs off a spine owned by whoever
 * asserted it, and says so in text; where the spine doubles, authority has changed hands.
 *
 * No innerHTML anywhere. Every string here is model-written the day a live provider runs,
 * and a report that executes what the model wrote is inherited defect D12. Text nodes
 * cannot execute. */
const SCHEMA = "adii.run_record/v1";
const INVESTIGATOR = "ADII, the investigator";
const VALIDATOR = "an independent validator, not ADII";
const ASSERTED = `Asserted by ${INVESTIGATOR}`;
const GLOSS = {
  REPAIR: "A specific fault exists and the evidence justifies a specific fix.",
  NO_REPAIR: "The pipeline is sound. The metric moved because the business moved.",
  ESCALATE: "The available evidence cannot justify either call. The run completed.",
};
/* How a run ended, each in its own terms. Only "submitted" carries a decision. */
const ENDED = {
  model_failure: "Ended by a model failure",
  bound_hit: "Ended by a bound",
  infrastructure_failure: "Ended by an infrastructure failure",
};

/* ── helpers ────────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

/* el("p", "lede", "text ", el("b", null, "bold")) — strings become text nodes. */
const el = (tag, cls, ...kids) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  n.append(...kids);
  return n;
};

/* Shape carries the disposition; hue reinforces it. Under deuteranopia the teal and the
 * iris are the same colour, so the mark is not decoration. Symbols live in index.html. */
function mark(kind) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "mark");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", `#m-${kind.toLowerCase()}`);
  svg.append(use);
  return svg;
}

async function load(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} answered ${res.status}`);
  return res.json();
}

/* Runs a task; if it rejects, renders the error state with a retry. A dead backend is a
 * frontend failure, not a verdict: achromatic, and it says what to do. */
function guard(target, task) {
  return task().catch((err) => {
    const again = el("button", "btn btn--primary", "Try again");
    again.onclick = () => guard(target, task);
    target.replaceChildren(el("div", "state state--error",
      el("h2", null, "The run did not load"),
      el("p", null, `${err.message}.`),
      again));
  });
}

/* ── boot ───────────────────────────────────────────────────────────── */
$("theme").onclick = () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
};
guard($("view"), boot);

async function boot() {
  const runs = await load("/api/runs");
  if (!runs.length) {
    $("view").replaceChildren(el("div", "state",
      el("h2", null, "No runs archived yet"),
      el("p", null, "Runs are launched from the command line and appear here once archived. " +
        "To see one now:"),
      el("pre", null, "python -m adii.runtime --incident demo-learning-001 --provider fake")));
    return;
  }
  $("runs").replaceChildren(...runs.map((r) => {
    const chip = el("button", "runchip");
    if (r.error) chip.append(el("span", "chiplabel", r.label), " · unreadable");
    else chip.append(r.disposition ? mark(r.disposition) : "", el("span", "chiplabel", r.label),
      ` · ${r.disposition || r.termination}${r.validation ? ` · ${r.validation}` : ""}`);
    chip.dataset.label = r.label;
    chip.onclick = () => guard($("view"), () => select(r.label));
    return chip;
  }));
  const linked = runs.find((r) => r.label === location.hash.slice(1));
  await select((linked || runs[0]).label);
}

async function select(label) {
  const record = await load(`/api/runs/${label}`);
  history.replaceState(null, "", `#${label}`);
  document.querySelectorAll(".runchip").forEach((c) =>
    c.setAttribute("aria-pressed", String(c.dataset.label === label)));
  if (record.schema !== SCHEMA) return mismatch(record.schema);
  render(record);
}

/* A record in a shape this page does not read. Refused, not guessed at. */
function mismatch(schema) {
  $("steps").replaceChildren();
  $("view").replaceChildren(el("div", "state state--error",
    el("h2", null, "This record is in a shape this inspector does not read"),
    el("p", null, "It declares ", el("code", null, String(schema)), " and this page renders ",
      el("code", null, SCHEMA), ". Nothing below is interpreted.")));
}

/* ── the single renderer ────────────────────────────────────────────── */
function render(r) {
  renderRail(r.trace);
  $("view").replaceChildren(runRecord(r), provenance(r));
  $("foot").replaceChildren("Read-only view of ", el("code", null, r.schema),
    " records in 01_data/runs. Runs are launched from the command line; nothing on this " +
    "page can spend money.");
  window.scrollTo({ top: 0 });
}

/* the trace rail: every event in order, explorable, never dominant */
function headline(e) {
  const p = e.payload;
  switch (e.kind) {
    case "incident_received": return p.incident_id;
    case "tool_call": case "tool_result": return p.name;
    case "decision_submitted": return p.disposition;
    case "validation_completed": return p.accepted ? "ACCEPT" : "REJECT";
    default: return "";
  }
}

function renderRail(trace) {
  $("steps").replaceChildren(...trace.map((e) => {
    const li = el("li");
    const head = el("button", null,
      el("span", "n", String(e.sequence).padStart(2, "0")),
      el("span", "kind", e.kind),
      el("span", "tool", headline(e)),
      el("span", "status", e.payload.status || ""));
    head.onclick = () => setOpen(li, li.dataset.open !== "true");
    li.append(head, el("div", "detail", el("pre", null, JSON.stringify(e.payload, null, 2))));
    setOpen(li, false);
    return li;
  }));
}

function setOpen(li, open) {
  li.dataset.open = String(open);
  li.querySelector("button").setAttribute("aria-expanded", String(open));
}

/* ── custody: a block is one spine segment and who owns it ──────────── */
function block(owner, what, ownerLine, ...kids) {
  const spine = el("div", "spine");
  spine.setAttribute("aria-hidden", "true");
  const s = el("section", `block block--${owner}`, spine,
    el("div", "body", el("p", "owner-line", ownerLine), ...kids));
  s.dataset.authority = owner;
  s.setAttribute("aria-label", `${what} — ${ownerLine}`);
  return s;
}

function handover(text) {
  const knot = el("div", "knot");
  knot.setAttribute("aria-hidden", "true");
  const h = el("div", "handover", knot, el("div", "who", text));
  h.setAttribute("role", "separator");
  h.setAttribute("aria-label", text);
  return h;
}

const kv = (...pairs) => el("dl", "kv", ...pairs.flatMap(([k, v]) =>
  [el("dt", null, k), el("dd", null, v)]));

/* ── the run record — only what the runtime archived ─────────────────── */
function runRecord(r) {
  const c = r.context;
  const d = r.decision;
  const out = el("div", null);

  out.append(block("investigator", "Incident", `Received by ${INVESTIGATOR}, from the operator`,
    el("span", "label", "Incident"),
    el("h1", null, c.incident_id),
    el("p", "lede", c.alert),
    kv(["As of", c.as_of],
       ["May write", c.permitted_write_paths.length ? c.permitted_write_paths.join(", ") : "nothing"])));

  if (d) {
    const facts = d.root_cause_id ? kv(["Root cause", d.root_cause_id]) : "";
    out.append(block("investigator", "Disposition", ASSERTED,
      el("div", `disposition d-${d.disposition}`, mark(d.disposition),
        el("span", null, el("span", "name", d.disposition), el("span", "gloss", GLOSS[d.disposition]))),
      facts));
    out.append(block("investigator", "Claim", ASSERTED,
      el("span", "label", "Claim"),
      el("p", "claim", d.root_cause_summary)));
  } else {
    out.append(block("investigator", "Run ended", `Reported by ${INVESTIGATOR}`,
      el("div", "terminated",
        el("span", "name", ENDED[r.termination] || r.termination),
        el("span", "gloss", r.detail))));
  }

  if (d && d.repair_id) {
    out.append(block("investigator", "Proposed change", `Proposed by ${INVESTIGATOR}`,
      el("span", "label", "Proposed change"),
      kv(["Repair", d.repair_id]),
      ...Object.entries(d.patch).map(([path, body]) => el("div", "diff",
        el("div", "path", el("span", null, path)),
        ...body.replace(/\n$/, "").split("\n").map((line) => el("div", "row", line))))));
  }

  if (r.validation) {
    const v = r.validation;
    const verdict = v.accepted ? "ACCEPT" : "REJECT";
    out.append(handover("Authority passes to the validator"));
    out.append(block("validator", "Independent validation", `Asserted by ${VALIDATOR}`,
      el("span", "label", "Independent validation"),
      el("div", "authority",
        el("span", `verdict v-${verdict}`, mark(v.accepted ? "pass" : "fail"), verdict),
        el("p", "selfcheck", v.report),
        el("ul", "findings", ...v.checks_run.map((check) => el("li", null, check))))));
  } else {
    const why = d ? ["not invoked", "No repair was proposed, so there is nothing to validate."]
                  : ["never reached", "The run ended before a decision was submitted."];
    out.append(block("validator", "Independent validation", `Held by ${VALIDATOR} — ${why[0]}`,
      el("span", "label", "Independent validation"),
      el("p", "na", why[1])));
  }
  return out;
}

/* What the archive knows about the run itself: identity, how it ended, what it cost, what
 * it ran under, and where the record came from. Counters are telemetry's, from the trace. */
function provenance(r) {
  const rows = [
    ["schema", r.schema], ["label", r.label], ["termination", r.termination],
    ["detail", r.detail],
    ...Object.entries(r.provenance),
    ...Object.entries(r.configuration).map(([k, v]) => [`configuration.${k}`, v]),
    ...Object.entries(r.counters),
  ];
  return el("details", "prov", el("summary", null, "Provenance, configuration and cost"),
    el("div", "provgrid", ...rows.map(([k, v]) =>
      el("div", null, el("span", "k", k), el("span", "v", v === null ? "null" : String(v))))));
}
