/* ADII run inspector — the operational surface over the run archive.
 *
 * ONE renderer for every record. There is deliberately no renderRepair(), renderBoundHit()
 * or similar: the record changes, the renderer does not. It renders `adii.run_record/v1`
 * and nothing else — a record in any other shape gets the contract-mismatch state, never a
 * guess — and it invents no field: everything on the page is in the record.
 *
 * The record is drawn as a chain of custody. Every block hangs off a spine owned by whoever
 * asserted it, and says so in text; where the spine doubles, authority has changed hands.
 * Two runs of one incident can be put side by side — that is how models get tested — and
 * each side is the same renderer over its own record.
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
const ALL = "*";   /* the filter value that matches every run */

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

const cost = (usd) => `$${Number(usd).toFixed(4)}`;
const when = (iso) => (iso ? `${iso.slice(0, 16).replace("T", " ")}Z` : "");   /* written in UTC */

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

/* ── state and boot ─────────────────────────────────────────────────── */
/* The run list as /api/runs returned it, the run on screen, and the run beside it. */
const state = { runs: [], primary: null, against: null };

$("theme").onclick = () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
};
guard($("view"), boot);

async function boot() {
  state.runs = await load("/api/runs");
  if (!state.runs.length) {
    $("runcount").replaceChildren("none");
    $("view").replaceChildren(el("div", "state",
      el("h2", null, "No runs archived yet"),
      el("p", null, "Runs are launched from the command line and appear here once archived. " +
        "To see one now:"),
      el("pre", null, "python -m adii.runtime --incident demo-learning-001 --provider fake")));
    return;
  }
  filters();
  runList();
  const [a, b] = location.hash.slice(1).split(",");
  const primary = state.runs.find((r) => r.label === a) || state.runs[0];
  const against = state.runs.find((r) => r.label === b && r.label !== primary.label
    && !r.error && r.incident_id === primary.incident_id);
  await show(primary, against || null);
}

/* ── the run list: every archived run, filtered by incident and by model ─ */
function filters() {
  const readable = state.runs.filter((r) => !r.error);
  const fill = (id, key, everything, missing) => {
    const values = [...new Set(readable.map((r) => r[key] ?? ""))];
    $(id).replaceChildren(option(ALL, everything),
      ...values.map((v) => option(v, v || missing)));
    $(id).onchange = runList;
  };
  fill("f-incident", "incident_id", "Every incident", "no incident");
  fill("f-model", "model", "Every model", "no model");
}

function option(value, text) {
  const o = el("option", null, text);
  o.value = value;
  return o;
}

function runList() {
  const incident = $("f-incident").value, model = $("f-model").value;
  const visible = state.runs.filter((r) => !r.error
    && (incident === ALL || r.incident_id === incident)
    && (model === ALL || (r.model ?? "") === model)
    || r.error && incident === ALL && model === ALL);
  $("runs").replaceChildren(...visible.map(row));
  $("runcount").replaceChildren(`${visible.length} of ${state.runs.length}`);
  if (state.primary) markSelected();
}

function row(r) {
  const li = el("li", "run");
  li.dataset.label = r.label;
  const open = el("button", "run-open");
  if (r.error) {
    open.append(el("span", "run-head", el("span", "chiplabel", r.label)),
      el("span", "run-meta", `unreadable — ${r.error}`));
  } else {
    const outcome = r.disposition
      ? `${r.disposition}${r.validation ? ` · ${r.validation}` : ""}` : r.termination;
    open.append(
      el("span", "run-head", r.disposition ? mark(r.disposition) : "", el("span", "chiplabel", r.label)),
      el("span", "run-meta", `${r.incident_id} · ${r.model || "no model"} · ${outcome}`),
      el("span", "run-meta", `${cost(r.api_cost_usd)} · ${when(r.written_at)}`));
  }
  open.onclick = () => guard($("view"), () => show(r, null));
  li.append(open);
  if (!r.error) {
    const vs = el("button", "run-vs", "compare");
    vs.title = "Side by side with the run on screen — same incident only";
    vs.onclick = () => guard($("view"), () => show(state.primary, r));
    li.append(vs);
  }
  return li;
}

function markSelected() {
  const { primary, against } = state;
  document.querySelectorAll("#runs .run").forEach((li) => {
    const label = li.dataset.label;
    li.querySelector(".run-open").setAttribute("aria-pressed", String(label === primary.label));
    const vs = li.querySelector(".run-vs");
    if (!vs) return;
    const run = state.runs.find((r) => r.label === label);
    vs.hidden = label === primary.label;
    vs.disabled = run.incident_id !== primary.incident_id;
    vs.setAttribute("aria-pressed", String(Boolean(against) && label === against.label));
  });
}

/* ── showing a run, or two ──────────────────────────────────────────── */
/* `primary` and `against` are run-list rows. A record the archive could not read is never
 * fetched: the backend refused it, and rendering the bytes anyway would be the guess this
 * page never makes. */
async function show(primary, against) {
  state.primary = primary;
  state.against = against;
  history.replaceState(null, "", `#${[primary.label, against && against.label].filter(Boolean).join(",")}`);
  markSelected();
  if (primary.error) return refused("The archive could not read this record", `${primary.error}.`);
  const a = await load(`/api/runs/${primary.label}`);
  if (a.schema !== SCHEMA) return mismatch(a.schema);
  if (!against) return render(a);
  const b = await load(`/api/runs/${against.label}`);
  if (b.schema !== SCHEMA) return mismatch(b.schema);
  renderCompare(a, b);
}

/* A record in a shape this page does not read. Refused, not guessed at. */
function mismatch(schema) {
  refused("This record is in a shape this inspector does not read",
    "It declares ", el("code", null, String(schema)), " and this page renders ",
    el("code", null, SCHEMA), ".");
}

function refused(title, ...why) {
  $("steps").replaceChildren();
  $("view").className = "";
  $("view").replaceChildren(el("div", "state state--error", el("h2", null, title),
    el("p", null, ...why, " Nothing below is interpreted.")));
}

/* ── the single renderer ────────────────────────────────────────────── */
function render(r) {
  renderRail(r);
  $("view").className = "";
  $("view").replaceChildren(runRecord(r), provenance(r));
  foot(r);
}

/* Two runs of one incident. Each side is the same renderer over its own record; the rail
 * shows the trace of the run on the left and says so. */
function renderCompare(a, b) {
  renderRail(a);
  const close = el("button", "btn", "Close comparison");
  close.onclick = () => guard($("view"), () => show(state.primary, null));
  $("view").className = "wide";
  $("view").replaceChildren(
    el("div", "compare-bar",
      el("span", "label", `Two runs of ${a.context.incident_id}, side by side`), close),
    el("div", "compare", side(a), side(b)));
  foot(a);
}

function side(r) {
  const c = r.configuration;
  return el("section", "side",
    el("h2", "side-title", r.label),
    el("p", "owner-line", `${c.provider ?? "provider not recorded"} · ${c.model ?? "no model"}`),
    runRecord(r), provenance(r));
}

function foot(r) {
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

function renderRail(r) {
  $("trace-label").replaceChildren(state.against ? `Trace · ${r.label}` : "Trace");
  $("steps").replaceChildren(...r.trace.map((e) => {
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
 * it ran under, and where the record came from. Counters are telemetry's, from the trace.
 * Nested configuration — requested and effective, one day — flattens to dotted keys. */
const flat = (prefix, value) => Object.entries(value ?? {}).flatMap(([k, v]) => {
  const key = prefix ? `${prefix}.${k}` : k;
  if (v && typeof v === "object" && !Array.isArray(v)) return flat(key, v);
  return [[key, v === null ? "null" : Array.isArray(v) ? v.join(", ") : String(v)]];
});

function provenance(r) {
  const rows = [
    ["schema", r.schema], ["label", r.label], ["termination", r.termination],
    ["detail", r.detail],
    ...flat("", r.provenance), ...flat("configuration", r.configuration), ...flat("", r.counters),
  ];
  return el("details", "prov", el("summary", null, "Provenance, configuration and cost"),
    el("div", "provgrid", ...rows.map(([k, v]) =>
      el("div", null, el("span", "k", k), el("span", "v", v)))));
}
