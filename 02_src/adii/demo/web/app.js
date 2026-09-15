/* ADII run inspector — the read-only surface over the run archive.
 *
 * Three screens, one route each, all from the URL hash: the front door (#), which opens on
 * the incidents; an incident's runs (#i/<incident>); and one run as a story (#r/<label>),
 * or two runs of one incident side by side (#r/<label>,<label>). The hierarchy on every
 * run page is fixed — incident, run, investigation, decision, validation, technical
 * details — and a section the record cannot fill is left out, never drawn empty.
 *
 * ONE renderer for every record. It renders `adii.run_record/v1` and nothing else — a record
 * in any other shape gets the contract-mismatch state, never a guess — and it invents no
 * field: everything on the page is in the record, or is one of the sentences in
 * phrasing.js, each a deterministic projection of record fields, each tested.
 *
 * The page cannot start a run. A page that can start a run can spend money. It says so, and
 * it says how a run is started, on every screen.
 *
 * No innerHTML anywhere. Every string here is model-written the day a live provider runs,
 * and a report that executes what the model wrote is inherited defect D12. Text nodes
 * cannot execute. */
const SCHEMA = "adii.run_record/v1";
const INVESTIGATOR = "ADII, the investigator";
const VALIDATOR = "the validator, not ADII";
const CHIP = {
  REPAIR: ["adii-chip--repair", "g-repair"],
  NO_REPAIR: ["adii-chip--no-repair", "g-no-repair"],
  ESCALATE: ["adii-chip--escalate", "g-escalate"],
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
const link = (cls, text, href) => { const a = el("a", cls, text); a.href = href; return a; };
const mono = (text) => el("span", "adii-mono", text);
const when = (iso) => (iso ? `${iso.slice(0, 16).replace("T", " ")} UTC` : "");

/* A glyph from the sprite in index.html. Decorative: the text beside it carries the meaning. */
function glyph(id, cls = "adii-chip__glyph") {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", cls);
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

/* the outcome of a run-list row, with the authority it inherits and nothing more */
function outcome(row) {
  if (row.error) return plain("unreadable", "g-unresolved");
  if (row.disposition) {
    return el("span", "run__outcome", chip(row.disposition),
      row.validation ? `${row.validation === "ACCEPT" ? "accepted" : "rejected"} by the validator` : "");
  }
  return plain(PHRASING.outcome[row.termination]?.() ?? row.termination, "g-unresolved");
}

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
      el("p", "adii-transport__title", "The page did not load"),
      el("p", null, `${err.message}. This establishes that the request failed here. It does ` +
        "not establish anything about the archive or any run."),
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
const state = { runs: [] };   /* the run list as /api/runs returned it */

preferences();
window.addEventListener("hashchange", () => guard($("view"), route));
guard($("view"), async () => { state.runs = await load("/api/runs"); await route(); });

async function route() {
  const hash = location.hash.slice(1);
  const [kind, rest] = hash.includes("/") ? hash.split("/", 2) : ["", ""];
  if (kind === "i") return incidentPage(decodeURIComponent(rest));
  if (kind === "r") {
    const [a, b] = rest.split(",").map(decodeURIComponent);
    return runPage(a, b);
  }
  return frontDoor();
}

function crumbs(...items) {
  const nav = $("crumbs");
  nav.replaceChildren(...items.flatMap(([text, href], i) => [
    i ? el("span", "adii-nav__sep", "/") : "",
    href ? link("adii-nav__link", text, href) : el("span", "adii-nav__link", text)]));
}

function foot(text) {
  $("foot").replaceChildren(text);
  window.scrollTo({ top: 0 });
  /* The page measures itself once rendered, so a browser test can assert it never scrolls
   * sideways at any width. Two integers on the root element; nothing else reads them.
   * Synchronous: a headless dump under a virtual-time budget may never paint a frame. */
  document.documentElement.dataset.measured =
    `${document.documentElement.scrollWidth},${document.documentElement.clientWidth}`;
}

/* how a run is created — on every screen, never a disabled button */
function howto() {
  return el("section", "adii-panel howto",
    el("h2", "adii-panel__title", "Creating a run"),
    el("p", "adii-type-sm", PHRASING.product.readOnly),
    el("p", "adii-type-sm", "To investigate an incident and archive the run, then see it here:"),
    el("pre", null, `${PHRASING.product.createRun}\n${PHRASING.product.thenOpen}`),
    el("p", "adii-type-sm", PHRASING.product.specimensWhat),
    el("pre", null, PHRASING.product.specimens));
}

/* A run with no model was scripted. Said wherever such a run is shown, so a screenshot can
 * never pass for a model result. Projected from one record field: configuration.model. */
const scriptedNote = (model) => (model === null || model === undefined
  ? el("p", "adii-field__hint scripted", plain("scripted", "g-none"), " ", PHRASING.product.scripted)
  : "");

/* ── the front door: what ADII is, and the incidents ────────────────── */
function incidents() {
  const byId = new Map();
  for (const r of state.runs) {
    if (r.error) continue;
    if (!byId.has(r.incident_id)) byId.set(r.incident_id, []);
    byId.get(r.incident_id).push(r);
  }
  return byId;
}

async function frontDoor() {
  crumbs(["Incidents"]);
  const cards = [];
  const byActivity = [...incidents()].sort(([, a], [, b]) =>
    (b[0].written_at || "").localeCompare(a[0].written_at || ""));   /* most recent activity first */
  for (const [incident, runs] of byActivity) {
    const latest = runs[0];                          /* the list is newest first */
    const first = await load(`/api/runs/${latest.label}`);
    cards.push(el("article", "adii-record adii-record--operator incident",
      el("div", "adii-record__head",
        el("h3", "adii-record__title", incident),
        el("p", "adii-record__owner", "Reported by the operator")),
      el("p", "incident__alert", first.schema === SCHEMA ? first.context.alert : "(record not readable)"),
      el("div", "incident__facts",
        el("span", null, el("b", null, String(runs.length)), ` recorded run${runs.length === 1 ? "" : "s"}`
          + (runs.every((r) => r.model === null || r.model === undefined) ? ", all scripted" : "")),
        el("span", null, "Latest: ", outcome(latest), " · ", when(latest.written_at))),
      el("p", null, link("adii-btn", "View the investigation history", `#i/${encodeURIComponent(incident)}`))));
  }
  const unreadable = state.runs.filter((r) => r.error).length;
  $("view").replaceChildren(el("div", "door",
    el("div", null,
      el("h1", null, "ADII"),
      el("p", "adii-eyebrow", PHRASING.product.name),
      el("p", "door__lede adii-mt-sm", PHRASING.product.what)),
    el("section", null,
      el("div", "adii-section__head", el("h2", null, "Incidents"),
        el("span", "adii-eyebrow", cards.length
          ? `${cards.length} incident${cards.length === 1 ? "" : "s"}, ${state.runs.length - unreadable} run${state.runs.length - unreadable === 1 ? "" : "s"}` +
            (unreadable ? `, ${unreadable} unreadable` : "")
          : "none archived yet")),
      cards.length ? el("div", "incidents", ...cards)
        : el("div", "adii-empty",
            el("p", "adii-empty__title", "No runs archived yet"),
            el("p", null, "An incident appears here once the runtime has investigated it and archived the run."))),
    howto()));
  foot("Read-only. Runs are launched from the command line; nothing on this page can spend money.");
}

/* ── an incident: every run of it, in time order, each in its own words ── */
async function incidentPage(incident) {
  const runs = incidents().get(incident);
  if (!runs) return refused("No such incident", `Nothing in the archive is labelled ${incident}.`);
  crumbs(["Incidents", "#"], [incident]);
  const first = await load(`/api/runs/${runs[0].label}`);
  $("view").replaceChildren(
    el("article", "adii-record adii-record--operator",
      el("div", "adii-record__head",
        el("h1", "adii-record__title", incident),
        el("p", "adii-record__owner", "Reported by the operator")),
      el("p", "adii-claim__label", "What was reported"),
      el("p", "adii-measure", first.schema === SCHEMA ? first.context.alert : "(record not readable)")),
    el("section", null,
      el("div", "adii-section__head", el("h2", null, "Runs"),
        el("span", "adii-eyebrow", `${runs.length}, newest first · each ended in its own way`)),
      el("div", "runs", ...runs.map((r) => el("div", "run",
        el("div", "run__main",
          el("span", "adii-mono adii-type-sm", r.label),
          el("span", "run__when", `${when(r.written_at)} · ${r.provider ?? "provider not recorded"} · ${r.model ?? "no model"}`),
          outcome(r)),
        el("div", "run__open",
          link("adii-btn", "Open", `#r/${encodeURIComponent(r.label)}`),
          " ",
          runs.length > 1 && r !== runs[0] ? link("adii-btn", "Compare with latest",
            `#r/${encodeURIComponent(runs[0].label)},${encodeURIComponent(r.label)}`) : ""))))),
    howto());
  foot("Read-only. Runs are launched from the command line; nothing on this page can spend money.");
}

/* ── one run, as a story; or two of one incident, side by side ──────── */
async function runPage(label, against) {
  const row = state.runs.find((r) => r.label === label);
  if (!row) return refused("No such run", `Nothing in the archive is labelled ${label}.`);
  if (row.error) return refused("The archive could not read this record", `${row.error}.`);
  const a = await load(`/api/runs/${label}`);
  if (a.schema !== SCHEMA) return mismatch(a.schema);
  const other = against && state.runs.find((r) => r.label === against && !r.error
    && r.incident_id === row.incident_id);
  crumbs(["Incidents", "#"], [a.context.incident_id, `#i/${encodeURIComponent(a.context.incident_id)}`],
    [other ? "Two runs, side by side" : label]);
  if (!other) {
    $("view").replaceChildren(story(a), howto());
  } else {
    const b = await load(`/api/runs/${against}`);
    if (b.schema !== SCHEMA) return mismatch(b.schema);
    $("view").replaceChildren(
      el("div", "story__nav",
        el("span", "adii-eyebrow", `Two runs of ${a.context.incident_id}, side by side`),
        link("adii-btn", "Close comparison", `#r/${encodeURIComponent(label)}`)),
      el("div", "compare", story(a, true), story(b, true)));
  }
  foot(`Read-only view of an ${SCHEMA} record. Runs are launched from the command line; nothing on this page can spend money.`);
}

/* The hierarchy is fixed: incident, run, investigation, decision (or why there is none),
 * validation, technical details. A section the record cannot fill is left out. */
function story(r, compact = false) {
  const c = r.context, d = r.decision, cfg = r.configuration;
  const ran = `${cfg.provider ?? "provider not recorded"} · ${cfg.model ?? "no model"}`;
  const out = el("div", "story");

  out.append(scriptedNote(cfg.model));
  out.append(record("operator", compact ? r.label : c.incident_id,
    compact ? `Run of ${c.incident_id}` : "Reported by the operator",
    el("p", "adii-claim__label", "What was reported"),
    el("p", "adii-measure", c.alert),
    meta(["As of", c.as_of],
         ["May write", c.permitted_write_paths.length ? c.permitted_write_paths.join(", ") : "nothing"])));

  out.append(record("system", "How the run ended", `Reported by ${r.termination === "infrastructure_failure" ? "the runtime" : INVESTIGATOR} · ${ran}`,
    el("p", "adii-measure", PHRASING.ended[r.termination]?.(r) ?? r.termination),
    el("p", "adii-field__hint adii-mt-2xs", "In the record's words: ", mono(r.detail))));

  out.append(record("system", "What the investigator did", `Recorded by the runtime as it happened · ${r.trace.length} step${r.trace.length === 1 ? "" : "s"}`,
    el("ol", "steps", ...r.trace.map((e) => el("li", "step",
      el("span", "step__n", String(e.sequence + 1)),
      el("div", "step__body",
        el("p", "step__text", PHRASING.step[e.kind]?.(e.payload) ?? `${e.kind}`),
        el("details", "step__raw", el("summary", null, `raw event · ${e.kind}`),
          el("pre", null, JSON.stringify(e.payload, null, 2)))))))));

  if (d) {
    out.append(record("system", "What it decided", `Asserted by ${INVESTIGATOR}`,
      el("p", null, chip(d.disposition)),
      el("p", "adii-field__hint adii-measure-narrow adii-mt-2xs", PHRASING.disposition[d.disposition]),
      el("p", "adii-claim__label adii-mt-md", "In its own words"),
      el("p", "adii-assertion", d.root_cause_summary),
      d.root_cause_id ? meta(["Root cause", d.root_cause_id]) : ""));
    if (d.repair_id) {
      out.append(record("system", "The change it proposed", `Proposed by ${INVESTIGATOR}. Not applied by anyone.`,
        defs(["Repair", d.repair_id]),
        ...Object.entries(d.patch).flatMap(([path, body]) => [
          el("p", "adii-claim__label adii-mt-md", path),
          el("div", "adii-change__diff", ...body.replace(/\n$/, "").split("\n").map((line) =>
            el("span", "adii-diff__line", el("span", "adii-diff__marker", " "), line, "\n")))])));
    }
  } else {
    out.append(record("system", "Why there is no decision", `Reported by ${INVESTIGATOR}`,
      el("p", "adii-measure", "The run ended before the investigator committed to a disposition, " +
        "so there is no decision to show and nothing was proposed.")));
  }

  if (r.validation) {
    const v = r.validation, verdict = v.accepted ? "ACCEPT" : "REJECT";
    out.append(record("validator", "What the validator said", `Asserted by ${VALIDATOR}`,
      el("p", "adii-measure", v.accepted ? PHRASING.validation.accepted : PHRASING.validation.rejected),
      el("div", "adii-verdicts adii-mt-md", el("div", `adii-check adii-check--${v.accepted ? "pass" : "fail"}`,
        glyph(v.accepted ? "g-pass" : "g-fail", "adii-check__mark"),
        el("p", "adii-check__body",
          el("span", "adii-check__name", "candidate repair"), " ",
          el("span", "adii-check__verdict", verdict), " ",
          el("span", "adii-check__note", v.report)))),
      el("p", "adii-claim__label adii-mt-md", "Checks run"),
      el("ul", "adii-inline-list", ...v.checks_run.map((check) => el("li", null, mono(check))))));
  } else if (d) {
    out.append(record("validator", "Validation", `Held by ${VALIDATOR}`,
      el("p", null, plain("not evaluated", "g-none")),
      el("p", "adii-field__hint adii-mt-sm", PHRASING.validation.notInvoked)));
  }
  /* no decision → no validation section: the record refuses a verdict without a decision,
   * and "Why there is no decision" already says the run ended first */

  out.append(el("details", "adii-panel tech",
    el("summary", null, "Technical details: how exactly this run was executed"),
    defs(["schema", r.schema], ["label", r.label], ["termination", r.termination],
         ["detail", r.detail],
         ...flat("", r.provenance), ...flat("configuration", r.configuration), ...flat("", r.counters))));
  return out;
}

/* ── refusals: something this page will not interpret ───────────────── */
function refused(title, why) {
  crumbs(["Incidents", "#"]);
  $("view").replaceChildren(el("div", "adii-callout",
    el("p", "adii-callout__title", title),
    el("p", null, `${why} Nothing below is interpreted.`)),
    el("p", "adii-mt-md", link("adii-btn", "Back to the incidents", "#")));
}
function mismatch(schema) {
  refused("This record is in a shape this inspector does not read",
    `It declares ${schema} and this page renders ${SCHEMA}.`);
}

/* ── records: a container with a written owner ──────────────────────── */
function record(owner, title, ownerLine, ...kids) {
  return el("article", `adii-record adii-record--${owner}`,
    el("div", "adii-record__head",
      el("h2", "adii-record__title", title),
      el("p", "adii-record__owner", ownerLine)),
    ...kids);
}
const meta = (...pairs) => el("div", "adii-record__meta", ...pairs.map(([k, v]) =>
  el("span", null, `${k} `, el("span", "adii-record__meta-value", v))));
const defs = (...pairs) => el("dl", "adii-defs", ...pairs.flatMap(([k, v]) =>
  [el("dt", null, k), el("dd", null, mono(v))]));
const flat = (prefix, value) => Object.entries(value ?? {}).flatMap(([k, v]) => {
  const key = prefix ? `${prefix}.${k}` : k;
  if (v && typeof v === "object" && !Array.isArray(v)) return flat(key, v);
  return [[key, v === null ? "null" : Array.isArray(v) ? v.join(", ") : String(v)]];
});
