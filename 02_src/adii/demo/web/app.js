/* ADII run inspector — the operational surface over the run archive.
 *
 * ONE renderer for every record. There is deliberately no renderRepair(), renderBoundHit()
 * or similar: the record changes, the renderer does not. It renders `adii.run_record/v1`
 * and nothing else — a record in any other shape gets the contract-mismatch state, never a
 * guess — and it invents no field: everything on the page is in the record.
 *
 * The page is drawn in the identity's grammar (03_assets/identity/DESIGN_SYSTEM.md). A
 * record is a container with a written owner, and its coloured riser only repeats the
 * text. The three dispositions are chips that are peers. Verdict rows belong to the
 * validator and to nothing else. How a run ended, and everything absent, is achromatic.
 * Dark by default; violet means interactive and nothing else. Two runs of one incident can
 * be put side by side — how models get tested — each side the same renderer over its record.
 *
 * No innerHTML anywhere. Every string here is model-written the day a live provider runs,
 * and a report that executes what the model wrote is inherited defect D12. Text nodes
 * cannot execute. */
const SCHEMA = "adii.run_record/v1";
const INVESTIGATOR = "ADII, the investigator";
const VALIDATOR = "the validator, not ADII";
const GLOSS = {
  REPAIR: "A specific fault exists and the evidence justifies a specific fix.",
  NO_REPAIR: "The pipeline is sound. The metric moved because the business moved.",
  ESCALATE: "The available evidence cannot justify either call. The run completed.",
};
/* chip class and glyph per disposition — three peers */
const CHIP = {
  REPAIR: ["adii-chip--repair", "g-repair"],
  NO_REPAIR: ["adii-chip--no-repair", "g-no-repair"],
  ESCALATE: ["adii-chip--escalate", "g-escalate"],
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

const link = (cls, text, href) => {
  const a = el("a", cls, text);
  a.href = href;
  return a;
};

/* A glyph from the sprite in index.html. Decorative: the text beside it carries the meaning. */
function glyph(id) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "adii-chip__glyph");
  svg.setAttribute("width", "12");
  svg.setAttribute("height", "12");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", `#${id}`);
  svg.append(use);
  return svg;
}

function chip(disposition) {
  const [cls, id] = CHIP[disposition];
  return el("span", `adii-chip ${cls}`, glyph(id), disposition);
}

/* Achromatic: how a run ended and what is absent are nobody's verdict. */
const plain = (text, id) => el("span", "adii-state", glyph(id), text);
const mono = (text) => el("span", "adii-mono", text);
const cost = (usd) => `$${Number(usd).toFixed(4)}`;
const when = (iso) => (iso ? `${iso.slice(0, 16).replace("T", " ")}Z` : "");   /* written in UTC */

async function load(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} answered ${res.status}`);
  return res.json();
}

/* Runs a task; if it rejects, renders the transport-failure state with a retry. A dead
 * backend is a retrieval failure here and establishes nothing about the archive. */
function guard(target, task) {
  return task().catch((err) => {
    const again = el("button", "adii-btn adii-no-print", "Try again");
    again.type = "button";
    again.onclick = () => guard(target, task);
    target.replaceChildren(el("div", "adii-transport",
      el("p", "adii-transport__title", "The run did not load"),
      el("p", null, `${err.message}. This establishes that the request failed here. It does ` +
        "not establish anything about the archive or the run."),
      el("p", "adii-mt-sm", again)));
  });
}

/* ── display preferences: theme and density, nothing else ───────────── */
function preferences() {
  const root = document.documentElement;
  try {
    const theme = localStorage.getItem("adii-theme");
    if (theme) root.dataset.theme = theme;
    const density = localStorage.getItem("adii-density");
    if (density) root.dataset.density = density;
  } catch (e) { /* storage disallowed: the toggles still work for this page */ }
  const themeButton = $("theme-toggle"), densityButton = $("density-toggle");
  const sync = () => {
    const dark = root.dataset.theme !== "light";
    themeButton.setAttribute("aria-pressed", String(dark));
    themeButton.replaceChildren(dark ? "Light theme" : "Dark theme");
    const compact = (root.dataset.density || "compact") === "compact";
    densityButton.setAttribute("aria-pressed", String(compact));
    densityButton.replaceChildren(compact ? "Roomy rows" : "Compact rows");
  };
  themeButton.onclick = () => {
    root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
    remember("adii-theme", root.dataset.theme);
    sync();
  };
  densityButton.onclick = () => {
    root.dataset.density = (root.dataset.density || "compact") === "compact" ? "roomy" : "compact";
    remember("adii-density", root.dataset.density);
    sync();
  };
  sync();
}

function remember(key, value) {
  try { localStorage.setItem(key, value); } catch (e) { /* not persisted; still applied */ }
}

/* ── state, boot and routing ────────────────────────────────────────── */
/* The run list as /api/runs returned it, the run on screen, and the run beside it. The URL
 * hash is the route: #label, or #label,label for two runs of one incident side by side. */
const state = { runs: [], primary: null, against: null };

preferences();
window.addEventListener("hashchange", () => guard($("view"), route));
guard($("view"), boot);

async function boot() {
  state.runs = await load("/api/runs");
  if (!state.runs.length) {
    $("runcount").replaceChildren("none");
    $("view").replaceChildren(el("div", "adii-empty",
      el("p", "adii-empty__title", "No runs archived yet"),
      el("p", null, "Runs are launched from the command line and appear here once archived. " +
        "To see one now:"),
      el("code", "adii-mono", "python -m adii.runtime --incident demo-learning-001 --provider fake")));
    return;
  }
  filters();
  runList();
  await route();
}

async function route() {
  const [a, b] = location.hash.slice(1).split(",");
  const primary = state.runs.find((r) => r.label === a) || state.runs[0];
  const against = state.runs.find((r) => r.label === b && r.label !== primary.label
    && !r.error && r.incident_id === primary.incident_id) || null;
  state.primary = primary;
  state.against = against;
  markSelected();
  if (primary.error) return refused("The archive could not read this record", `${primary.error}.`);
  const first = await load(`/api/runs/${primary.label}`);
  if (first.schema !== SCHEMA) return mismatch(first.schema);
  if (!against) return render(first);
  const second = await load(`/api/runs/${against.label}`);
  if (second.schema !== SCHEMA) return mismatch(second.schema);
  renderCompare(first, second);
}

/* ── the run list: every archived run, filtered by incident and by model ─ */
function filters() {
  const readable = state.runs.filter((r) => !r.error);
  const fill = (id, key, everything, missing) => {
    const values = [...new Set(readable.map((r) => r[key] ?? ""))];
    $(id).replaceChildren(option(ALL, everything), ...values.map((v) => option(v, v || missing)));
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
  li.append(link("run__label adii-mono", r.label, `#${r.label}`));
  if (r.error) {
    li.append(el("span", "run__meta adii-type-meta", `unreadable — ${r.error}`));
    return li;
  }
  const outcome = r.disposition ? chip(r.disposition) : plain(r.termination, "g-unresolved");
  li.append(
    el("span", "run__meta adii-type-meta",
      `${r.incident_id} · ${r.model || "no model"} · ${cost(r.api_cost_usd)} · ${when(r.written_at)}`),
    el("span", "run__outcome", outcome, r.validation ? mono(r.validation) : ""));
  return li;
}

/* The selected row, and a compare link on every other row of the same incident. */
function markSelected() {
  const { primary, against } = state;
  document.querySelectorAll("#runs .run").forEach((li) => {
    const label = li.dataset.label;
    const run = state.runs.find((r) => r.label === label);
    li.setAttribute("aria-current", String(label === primary.label));
    li.querySelector(".run__compare")?.remove();
    if (run.error || label === primary.label || run.incident_id !== primary.incident_id) return;
    const compare = link("run__compare", against && label === against.label
      ? "shown beside" : "compare", `#${primary.label},${label}`);
    compare.title = "Side by side with the run on screen";
    li.querySelector(".run__outcome").append(compare);
  });
}

/* ── refusals: a record this page will not interpret ────────────────── */
function refused(title, ...why) {
  $("steps").replaceChildren();
  $("view").replaceChildren(el("div", "adii-callout",
    el("p", "adii-callout__title", title),
    el("p", null, ...why, " Nothing below is interpreted.")));
}

/* A record in a shape this page does not read. Refused, not guessed at. */
function mismatch(schema) {
  refused("This record is in a shape this inspector does not read",
    "It declares ", mono(String(schema)), " and this page renders ", mono(SCHEMA), ".");
}

/* ── the single renderer ────────────────────────────────────────────── */
function render(r) {
  renderRail(r);
  $("view").replaceChildren(runRecord(r), provenance(r));
  foot(r);
}

/* Two runs of one incident. Each side is the same renderer over its own record; the rail
 * shows the trace of the run on the left and says so. */
function renderCompare(a, b) {
  renderRail(a);
  $("view").replaceChildren(
    el("div", "adii-section__head",
      el("h2", "adii-type-h3", `Two runs of ${a.context.incident_id}, side by side`),
      link("adii-btn adii-no-print", "Close comparison", `#${a.label}`)),
    el("div", "compare", side(a), side(b)));
  foot(a);
}

function side(r) {
  return el("section", "adii-stack-lg", el("h3", "adii-mono", r.label), runRecord(r), provenance(r));
}

function foot(r) {
  $("foot").replaceChildren("Read-only view of ", mono(r.schema),
    " records in 01_data/runs. Runs are launched from the command line; nothing on this " +
    "page can spend money.");
  window.scrollTo({ top: 0 });
}

/* the trace: every event in order, each a native disclosure over its payload */
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
  $("trace-title").replaceChildren(state.against ? `Trace · ${r.label}` : "Trace");
  $("steps").replaceChildren(...r.trace.map((e) => el("li", null, el("details", "trace__event",
    el("summary", null,
      el("span", "trace__n", String(e.sequence).padStart(2, "0")),
      el("span", "trace__kind", e.kind),
      el("span", "trace__head", headline(e)),
      el("span", "trace__status", e.payload.status || "")),
    el("pre", "adii-change__diff trace__payload", JSON.stringify(e.payload, null, 2))))));
}

/* ── records: a container with a written owner ──────────────────────── */
function record(owner, title, ownerLine, ...kids) {
  return el("article", `adii-record adii-record--${owner}`,
    el("div", "adii-record__head",
      el("h3", "adii-record__title", title),
      el("p", "adii-record__owner", ownerLine)),
    ...kids);
}

const meta = (...pairs) => el("div", "adii-record__meta", ...pairs.map(([k, v]) =>
  el("span", null, `${k} `, el("span", "adii-record__meta-value", v))));

const defs = (...pairs) => el("dl", "adii-defs", ...pairs.flatMap(([k, v]) =>
  [el("dt", null, k), el("dd", null, mono(v))]));

/* ── the run record — only what the runtime archived ─────────────────── */
function runRecord(r) {
  const c = r.context, d = r.decision, cfg = r.configuration;
  const ran = `${cfg.provider ?? "provider not recorded"} · ${cfg.model ?? "no model"}`;
  const out = el("div", "adii-stack-lg");

  out.append(record("operator", c.incident_id, `Reported by the operator. Received by ${INVESTIGATOR}.`,
    el("p", "adii-claim__label", "Alert"),
    el("p", "adii-measure", c.alert),
    meta(["As of", c.as_of],
         ["May write", c.permitted_write_paths.length ? c.permitted_write_paths.join(", ") : "nothing"])));

  if (d) {
    out.append(record("system", "Disposition", `Asserted by ${INVESTIGATOR} · ${ran}`,
      el("p", null, chip(d.disposition)),
      el("p", "adii-field__hint adii-measure-narrow adii-mt-2xs", GLOSS[d.disposition]),
      el("p", "adii-claim__label adii-mt-md", "Assertion"),
      el("p", "adii-assertion", d.root_cause_summary),
      d.root_cause_id ? meta(["Root cause", d.root_cause_id]) : ""));
  } else {
    const by = r.termination === "infrastructure_failure" ? "the runtime" : INVESTIGATOR;
    out.append(record("system", "Run ended", `Reported by ${by} · ${ran}`,
      el("p", null, plain(r.termination, "g-unresolved")),
      el("p", "adii-measure adii-mt-sm", r.detail),
      el("p", "adii-field__hint adii-mt-sm", "No decision was submitted.")));
  }

  if (d && d.repair_id) {
    out.append(record("system", "Proposed change", `Proposed by ${INVESTIGATOR}. Not applied.`,
      defs(["Repair", d.repair_id]),
      ...Object.entries(d.patch).flatMap(([path, body]) => [
        el("p", "adii-claim__label adii-mt-md", path),
        el("div", "adii-change__diff", ...body.replace(/\n$/, "").split("\n").map((line) =>
          el("span", "adii-diff__line", el("span", "adii-diff__marker", " "), line, "\n")))])));
  }

  if (r.validation) {
    const v = r.validation;
    const verdict = v.accepted ? "ACCEPT" : "REJECT";
    out.append(record("validator", "Independent validation", `Asserted by ${VALIDATOR}.`,
      el("div", "adii-verdicts", el("div", `adii-check adii-check--${v.accepted ? "pass" : "fail"}`,
        checkMark(v.accepted ? "g-pass" : "g-fail"),
        el("p", "adii-check__body",
          el("span", "adii-check__name", "candidate repair"), " ",
          el("span", "adii-check__verdict", verdict), " ",
          el("span", "adii-check__note", v.report)))),
      el("p", "adii-claim__label adii-mt-md", "Checks run"),
      el("ul", "adii-inline-list", ...v.checks_run.map((check) => el("li", null, mono(check))))));
  } else {
    out.append(record("validator", "Independent validation", `Held by ${VALIDATOR}.`,
      el("p", null, plain("not evaluated", "g-none")),
      el("p", "adii-field__hint adii-mt-sm", d
        ? "No repair was proposed, so there is nothing to validate."
        : "The run ended before a decision was submitted.")));
  }
  return out;
}

function checkMark(id) {
  const mark = glyph(id);
  mark.setAttribute("class", "adii-check__mark");
  return mark;
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
  return el("section", "adii-panel",
    el("h2", "adii-panel__title", "Provenance, configuration and cost"),
    defs(...rows));
}
