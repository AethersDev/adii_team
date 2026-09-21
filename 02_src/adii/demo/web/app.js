/* ADII's one page: investigate, watch, read, answer.
 *
 * Three screens, one route each, all from the URL hash: the front door (#), which opens on
 * the product — what looks wrong, over the visitor's own CSV files, Investigate — when the
 * operator allowed it, with the archive's incidents one disclosure down as examples, then
 * the previous investigations; an incident's runs (#i/<incident>); and one run as a story
 * (#r/<label>), or two runs of one incident side by side (#r/<label>,<label>). The
 * hierarchy on every run page is fixed — the answer first: how it ended, the question,
 * what it concluded and the action that asks, what it looked at; then, one disclosure
 * down, the incident and every turn; then validation, evaluation, feedback, technical
 * details — and a section the record cannot fill is left out, never drawn empty.
 *
 * ONE renderer for every record. It renders `adii.run_record/v1` and nothing else — a record
 * in any other shape gets the contract-mismatch state, never a guess — and it invents no
 * field: everything on the page is in the record, or is one of the sentences in
 * phrasing.js, each a deterministic projection of record fields, each tested.
 *
 * The page starts a run only when the operator started the server with a model — a page
 * that can start a run can spend money, so what it may ask for is at most what the
 * operator's flags allow, and otherwise it says how a run is started, on every screen.
 * Its footer says which it is.
 *
 * No innerHTML anywhere. Every string here is model-written the day a live provider runs,
 * and a report that executes what the model wrote is inherited defect D12. Text nodes
 * cannot execute. */
const SCHEMA = "adii.run_record/v1";
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
const option = (value, text) => { const o = el("option", null, text); o.value = value; return o; };
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
  if (row.running) return plain("running", "g-unresolved");
  if (row.error) return plain("unreadable", "g-unresolved");
  if (row.disposition) {
    return el("span", "run__outcome", chip(row.disposition),
      row.validation ? PHRASING.verdictLabelOf(row.validation, row.model) : "");
  }
  return plain(PHRASING.outcome[row.termination]?.() ?? row.termination, "g-unresolved");
}

async function load(url, init) {
  const res = await fetch(url, init);
  const code = res.headers.get("ADII-Code");         /* the page's code, as served right now */
  if (code && state.code && code !== state.code) location.reload();   /* this tab's script is older */
  state.code = state.code ?? code;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.error || `${url} answered ${res.status}`);
    err.refused = res.status < 500;            /* the server said no, with a reason */
    throw err;
  }
  return body;
}

/* Runs a task; if it rejects, renders the transport-failure state with a retry. A dead
 * backend is a retrieval failure here and establishes nothing about the archive. */
function guard(target, task) {
  return task().catch((err) => {
    if (err.refused) {                          /* refused with a reason: say it, no retry */
      target.replaceChildren(el("div", "adii-transport",
        el("p", "adii-transport__title", "Not started"),
        el("p", null, `${err.message}.`)));
      return;
    }
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
/* the run list; whether runs may start; the code version this tab loaded; a run this tab just started */
const state = { runs: [], launch: { enabled: false }, code: null, starting: null };

preferences();
window.addEventListener("hashchange", () => guard($("view"), route));
guard($("view"), async () => {
  [state.runs, state.launch] = await Promise.all([load("/api/runs"), load("/api/launch")]);
  await route();
});

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

/* every screen's footer says whether this page can start a run, and where; the model is
 * the launcher's line and each run's own page, since a visitor may choose it */
const footer = (prefix = "") => foot(prefix + (state.launch.enabled
  ? PHRASING.product.footLive(state.launch.provider) : PHRASING.product.footReadOnly));

function foot(text) {
  $("foot").replaceChildren(text);
  window.scrollTo({ top: 0 });
  /* The page measures itself once rendered, so a browser test can assert it never scrolls
   * sideways at any width. Two integers on the root element; nothing else reads them.
   * Synchronous: a headless dump under a virtual-time budget may never paint a frame. */
  document.documentElement.dataset.measured =
    `${document.documentElement.scrollWidth},${document.documentElement.clientWidth}`;
}

/* how a run is created — on every screen. A launcher when the operator allowed it, the
 * commands otherwise; never a disabled button. */
function howto(incident) {
  if (state.launch.enabled) return launcher(incident);
  return el("section", "adii-panel howto",
    el("h2", "adii-panel__title", "Creating a run"),
    el("p", "adii-type-sm", PHRASING.product.readOnly),
    el("p", "adii-type-sm", "To investigate an incident and archive the run, then see it here:"),
    el("pre", null, `${PHRASING.product.createRun}\n${PHRASING.product.thenOpen}`),
    el("p", "adii-type-sm", PHRASING.product.specimensWhat),
    el("pre", null, PHRASING.product.specimens),
    el("p", "adii-type-sm", PHRASING.product.liveHow),
    el("pre", null, PHRASING.product.liveCommand));
}

/* Run settings a visitor may ask for, one layer down: presets at most the operator's
 * ceiling, the ceiling itself the default. Requests, not authority — the server checks
 * each against the flags it was started with and refuses more, never clamps. */
const COST_PRESETS = [0.05, 0.10, 0.25, 0.50];
const TURN_PRESETS = [12, 20, 30];
const within = (presets, ceiling) =>
  [...new Set([...presets.filter((v) => v <= ceiling), ceiling])].sort((a, b) => a - b);
const choice = (id, label, options, chosen) => {
  const select = el("select", "adii-select", ...options.map(([v, text]) => option(v, text)));
  select.id = id;
  select.value = chosen;
  return [select, el("div", "adii-field", el("label", "adii-field__label", label), select)];
};

/* The product form. What looks wrong, in the visitor's words, over their own CSV files —
 * or, one layer down, one of the archive's incidents. Either way the server answers with
 * the label at once and runs the investigation; the page goes to the run and watches. The
 * model, cap and turn budget come from Run settings within the operator's ceilings. */
function launcher(preset) {
  const running = state.runs.find((r) => r.running);
  const paid = state.launch.provider === "openai";
  const ask = el("textarea", "adii-input");
  ask.id = "launch-description";
  ask.rows = 3;
  ask.maxLength = 2000;                       /* the server's limit, said here first */
  ask.placeholder = PHRASING.product.askFor;
  const askCount = el("p", "adii-field__hint adii-char-count");
  const updateAskCount = () =>
    askCount.replaceChildren(`${ask.value.length} / ${ask.maxLength}`);
  ask.oninput = updateAskCount;
  updateAskCount();
  const files = el("input", "adii-upload__input");
  files.type = "file";
  files.id = "launch-files";
  files.accept = ".csv,text/csv";
  files.multiple = true;
  const fileList = el("ul", "adii-upload__list");
  /* the input's own FileList cannot be edited in place, so a removal is written back as a
   * fresh DataTransfer with that one file left out — the input stays the source of truth */
  const removeFile = (name) => {
    const rest = [...files.files].filter((f) => f.name !== name);
    const transfer = new DataTransfer();
    rest.forEach((f) => transfer.items.add(f));
    files.files = transfer.files;
    updateFileList();
  };
  const updateFileList = () => fileList.replaceChildren(
    ...[...files.files].map((f) => {
      const remove = el("button", "adii-upload__remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${f.name}`);
      remove.onclick = () => removeFile(f.name);
      return el("li", "adii-upload__item",
        el("span", "adii-upload__name", f.name), remove);
    }));
  files.onchange = updateFileList;
  const select = el("select", "adii-select");
  select.id = "launch-incident";
  const examples = el("details", "settings example");
  const fill = async () => {
    const incidents = await load("/api/incidents");
    select.replaceChildren(...incidents.map((i) => option(i.incident_id, i.incident_id)));
    /* on an incident's own page the example is that incident — when it is one the
     * archive offers; a brought incident is not, and the picker stays closed */
    if (preset && incidents.some((i) => i.incident_id === preset)) {
      select.value = preset;
      examples.open = true;
    }
  };
  const models = state.launch.models || [state.launch.model];
  const [model, modelField] = models.length > 1
    ? choice("launch-model", "Model", models.map((m) => [m, shortModel(m)]), state.launch.model)
    : [null, null];
  const [cost, costField] = paid
    ? choice("launch-cost", "Maximum spend",
      within(COST_PRESETS, state.launch.max_cost_usd).map((c) => [String(c), `$${c.toFixed(2)}`]),
      String(state.launch.max_cost_usd))
    : [null, null];
  const [turns, turnsField] = choice("launch-turns", "Turn budget",
    within(TURN_PRESETS, state.launch.max_turns).map((n) => [String(n), `${n} turns`]),
    String(state.launch.max_turns));
  const chosen = () => ({ model: model ? model.value : state.launch.model,
    max_turns: Number(turns.value), ...(cost ? { max_cost_usd: Number(cost.value) } : {}) });
  const summary = el("p", "adii-type-sm");
  const describe = () => {
    const c = chosen();
    summary.replaceChildren(PHRASING.product.runsWith(shortModel(c.model), state.launch.provider,
      c.max_cost_usd, c.max_turns));
  };
  [model, cost, turns].filter(Boolean).forEach((s) => { s.onchange = describe; });
  describe();
  const status = el("p", "adii-field__hint");
  /* one run starts: the body is assembled, the server answers the label, the page goes
   * there and watches; the button is back whatever happened */
  const start = (button, path, assemble) => guard(status, async () => {
    button.disabled = true;
    try {
      status.replaceChildren("Starting…");
      const answer = await load(path, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...(await assemble()), ...chosen() }) });
      state.starting = answer.label;
      location.hash = `#r/${encodeURIComponent(answer.label)}`;
    } finally {
      button.disabled = false;
    }
  });
  const investigate = el("button", "adii-btn adii-btn--primary", "Investigate");
  investigate.type = "button";
  investigate.id = "launch-investigate";
  investigate.onclick = () => {
    if (!ask.value.trim() || !files.files.length) {
      status.replaceChildren(PHRASING.product.needBoth);
      return;
    }
    /* the files are read here, in the browser, and sent as text: the server takes JSON
     * and nothing else, and what it takes is bounded there */
    start(investigate, "/api/investigations", async () => ({ description: ask.value,
      files: await Promise.all([...files.files].map(async (f) => ({ name: f.name, text: await f.text() }))) }));
  };
  const example = el("button", "adii-btn", "Investigate this example");
  example.type = "button";
  example.id = "launch-example";
  example.onclick = () => start(example, "/api/runs", async () => ({ incident: select.value }));
  guard(status, fill);
  examples.append(el("summary", null, PHRASING.product.tryExample),
    el("p", "adii-type-sm adii-mt-sm", PHRASING.product.exampleWhat),
    el("div", "adii-toolbar",
      el("div", "adii-field", el("label", "adii-field__label", "Incident"), select), example));
  /* whether a run can start right now, next to the question that starts one — not buried
   * in the footer, several screens' worth of scroll from the button it answers */
  const runningNote = el("p", "launcher__status", ...(running
    ? [plain("busy", "g-unresolved"), " ",
       link("adii-nav__link", PHRASING.product.busy(running.label), `#r/${encodeURIComponent(running.label)}`)]
    : [plain("idle", "g-none"), " ", PHRASING.product.idle]));
  return el("section", "adii-panel howto launcher",
    el("div", "launcher__head",
      el("h2", "adii-panel__title", PHRASING.product.ask),
      runningNote),
    el("div", "adii-field",
      ask,
      askCount),
    el("div", "adii-field",
      el("label", "adii-field__label", PHRASING.product.yourData),
      el("div", "adii-upload",
        files,
        fileList,
        el("p", "adii-upload__hint", PHRASING.product.dataHint))),
    summary,
    el("div", "adii-toolbar", investigate),
    status,
    el("details", "settings", el("summary", null, "Run settings"),
      el("div", "adii-toolbar", ...[modelField, costField, turnsField].filter(Boolean))),
    examples);
}

/* A run with no model was scripted. Said wherever such a run is shown, so a screenshot can
 * never pass for a model result. Projected from one record field: configuration.model. */
const scriptedNote = (model) => (model === null || model === undefined
  ? el("p", "adii-field__hint scripted", plain("scripted", "g-none"), " ", PHRASING.product.scripted)
  : "");

/* ── the front door: what ADII is, what to do here, and what happened before ── */
function incidents() {
  const byId = new Map();
  for (const r of state.runs) {
    if (r.error || r.running) continue;
    if (!byId.has(r.incident_id)) byId.set(r.incident_id, []);
    byId.get(r.incident_id).push(r);
  }
  return byId;
}

async function frontDoor() {
  crumbs();
  const cards = [];
  const byActivity = [...incidents()].sort(([, a], [, b]) =>
    (b[0].written_at || "").localeCompare(a[0].written_at || ""));   /* most recent activity first */
  for (const [incident, runs] of byActivity) {
    const latest = runs[0];                          /* the list is newest first */
    const first = await load(`/api/runs/${latest.label}`);
    cards.push(el("article", "adii-record adii-record--operator incident",
      el("div", "adii-record__head", el("h3", "adii-record__title", incident)),
      el("p", "incident__alert", first.schema === SCHEMA ? first.context.alert : "(record not readable)"),
      el("div", "incident__facts",
        el("span", null, el("b", null, String(runs.length)), ` run${runs.length === 1 ? "" : "s"}`
          + (runs.every((r) => r.model === null || r.model === undefined) ? ", all scripted" : "")
          + ` · latest ${when(latest.written_at)}`),
        el("span", null, outcome(latest))),
      el("p", null, link("adii-btn", "View runs", `#i/${encodeURIComponent(incident)}`))));
  }
  const unreadable = state.runs.filter((r) => r.error).length;
  $("view").replaceChildren(el("div", "door",
    el("div", null,
      el("h1", null, "ADII"),
      el("p", "adii-eyebrow", PHRASING.product.name),
      el("p", "door__lede adii-mt-sm", PHRASING.product.what)),
    state.launch.enabled ? launcher() : "",        /* the action first, when allowed */
    el("section", null,
      el("div", "adii-section__head", el("h2", null, "Previous investigations"),
        el("span", "adii-eyebrow", cards.length
          ? PHRASING.product.history(cards.length, state.runs.length - unreadable) +
            (unreadable ? ` · ${unreadable} unreadable` : "")
          : "none archived yet")),
      cards.length ? el("div", "incidents", ...cards)
        : el("div", "adii-empty",
            el("p", "adii-empty__title", "No runs archived yet"),
            el("p", null, PHRASING.product.empty))),
    state.launch.enabled ? "" : howto()));
  footer();
}

/* ── an incident: every run of it, in time order, each in its own words ── */
async function incidentPage(incident) {
  const runs = incidents().get(incident);
  if (!runs) return refused("No such incident", `Nothing in the archive is labelled ${incident}.`);
  crumbs([incident]);
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
        el("span", "adii-eyebrow", `${runs.length}, newest first`)),
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
    howto(incident));
  footer();
}

/* ── one run, as a story; or two of one incident, side by side ──────── */
async function runPage(label, against) {
  let row = state.runs.find((r) => r.label === label);
  /* not in the list this tab loaded: reload it — and for a run this tab just started, wait
   * for the runtime to reserve the label, which it does a moment after the server answers */
  for (let i = 0; !row && (i === 0 || (state.starting === label && i < 20)); i++) {
    if (i) await new Promise((resolve) => setTimeout(resolve, 500));
    state.runs = await load("/api/runs");
    row = state.runs.find((r) => r.label === label);
  }
  if (!row) return refused("No such run", `Nothing in the archive is labelled ${label}.`);
  if (row.error) return refused("The archive could not read this record", `${row.error}.`);
  if (row.running) return watch(label);
  const a = await load(`/api/runs/${label}`);
  if (a.schema !== SCHEMA) return mismatch(a.schema);
  const evaluation = row.evaluation ? await load(`/api/runs/${label}/evaluation`) : null;
  const other = against && state.runs.find((r) => r.label === against && !r.error
    && r.incident_id === row.incident_id);
  crumbs([a.context.incident_id, `#i/${encodeURIComponent(a.context.incident_id)}`],
    [other ? "Two runs, side by side" : label]);
  if (!other) {
    $("view").replaceChildren(story(a, false, label, evaluation), howto(a.context.incident_id));
  } else {
    const b = await load(`/api/runs/${against}`);
    if (b.schema !== SCHEMA) return mismatch(b.schema);
    $("view").replaceChildren(
      el("div", "story__nav",
        el("span", "adii-eyebrow", `Two runs of ${a.context.incident_id}, side by side`),
        link("adii-btn", "Close comparison", `#r/${encodeURIComponent(label)}`)),
      el("div", "compare", story(a, true), story(b, true)));
  }
  footer();
}

/* ── the run page: outcome first, then the investigation turn by turn ─────────────
 * What an operator reads, in the order they need it: what came of the run, what it looked
 * at and what came back, the change it proposed, what the validator said. The machinery —
 * ids, revisions, counters — is one closed disclosure at the end. A section the record
 * cannot fill is left out. */
const seconds = (ms) => (ms >= 1000 ? `${Math.round(ms / 1000)} s` : `${ms} ms`);
const shortModel = (model) => (model ? String(model).split("/").pop() : "no model");

function story(r, compact = false, label = r.label, evaluation = null) {
  const c = r.context, d = r.decision, cfg = r.configuration, n = r.counters;
  const out = el("div", "story");
  const ran = cfg.model ? `${shortModel(cfg.model)} · ` : "";
  const requests = r.trace.filter((e) => e.kind === "tool_call").length;

  /* the outcome, first */
  out.append(el("header", "outcome",
    el("p", "adii-eyebrow", compact ? r.label
      : `${c.incident_id} · ${ran}${requests} tool request${requests === 1 ? "" : "s"} · ${seconds(n.latency_ms)}`),
    el("h1", "outcome__headline", d ? chip(d.disposition) : plain(PHRASING.outcome[r.termination]?.(r) ?? r.termination, "g-unresolved"),
      " ", PHRASING.headline[r.termination]?.(r) ?? r.termination),
    el("p", "outcome__asked", c.alert),          /* the question, above its answer */
    scriptedNote(cfg.model)));

  if (d) {
    out.append(record("system", "What it concluded", PHRASING.by.investigator(r),
      el("p", "adii-assertion", d.root_cause_summary),
      el("p", "adii-field__hint adii-mt-sm", PHRASING.disposition[d.disposition]),
      el("p", "adii-mt-sm", el("b", null, "Action "), PHRASING.action[d.disposition]),
      d.root_cause_id ? meta(["Root cause id", d.root_cause_id]) : ""));
  } else {
    out.append(record("system", "Why there is no decision",
      r.termination === "infrastructure_failure" ? PHRASING.by.runtime : PHRASING.by.investigator(r),
      el("p", "adii-measure", PHRASING.ended[r.termination]?.(r) ?? r.termination),
      el("p", "adii-field__hint adii-mt-2xs", "In the record's words: ", mono(r.detail))));
  }

  /* what it looked at: every answered request, one line each — a projection of the trace,
   * so a decision reached without looking reads as exactly that */
  const results = r.trace.filter((e) => e.kind === "tool_result");
  const looked = results.filter((e) => e.payload.status === "OK");
  const refused = results.filter((e) => e.payload.status === "DENIED" || e.payload.status === "REJECTED").length;
  const failed = results.filter((e) => e.payload.status === "ERROR").length;
  const asked = Object.fromEntries(r.trace.filter((e) => e.kind === "tool_call")
    .map((e) => [e.payload.call_id, e.payload]));
  /* every attempt counted, the refused ones beside the answered: a correct refusal is the
   * boundary working, and a list of observations alone would hide that it happened */
  out.append(record("system", "What it looked at",
    `${PHRASING.by.runtime} · ${PHRASING.product.attempts(requests, looked.length, refused, failed)}`,
    looked.length
      ? el("ul", "looked", ...looked.map((e) => el("li", "looked__item",
          el("span", null, `${e.payload.name}${describeArgs(asked[e.payload.call_id]?.arguments)}`),
          " — ", PHRASING.turn.answered(e.payload),
          ...(e.payload.content && e.payload.content.evidence_id
            ? [" ", mono(e.payload.content.evidence_id)] : []))))
      : el("p", "adii-field__hint", requests
          ? PHRASING.product.nothingAnswered(requests) : PHRASING.product.lookedAtNothing)));

  const rounds = turns(r.trace);
  out.append(el("details", "adii-panel tech investigation",
    el("summary", null, "View the investigation"),
    record("operator", "The incident", "Reported by the operator",
      el("p", "adii-measure", c.alert),
      meta(["As of", c.as_of],
           [PHRASING.product.declaredPaths, c.permitted_write_paths.length
             ? c.permitted_write_paths.join(", ") : PHRASING.product.declaredNone]),
      el("p", "adii-field__hint adii-mt-2xs", PHRASING.product.declaredPathsHint)),
    record("system", "The investigation, turn by turn",
      `${PHRASING.by.runtime} as it happened · ${rounds.length} turn${rounds.length === 1 ? "" : "s"}`,
      el("ol", "turns", ...rounds.map((turn, i) =>
        turnCard(turn, i, r.validation, PHRASING.scriptedRun(r)))))));

  if (d && d.repair_id) {
    out.append(record("system", "The change it proposed", PHRASING.by.proposed(r),
      defs(["Repair", d.repair_id]),
      ...Object.entries(d.patch).flatMap(([path, body]) => [
        el("p", "adii-claim__label adii-mt-md", path),
        el("div", "adii-change__diff", ...body.replace(/\n$/, "").split("\n").map((line) =>
          el("span", "adii-diff__line", el("span", "adii-diff__marker", " "), line, "\n")))])));
  }

  if (r.validation) {
    const v = r.validation, verdict = PHRASING.verdictOf(v), scripted = PHRASING.scriptedRun(r);
    /* verdict colour belongs to the validator alone: a scripted preset is drawn achromatic,
     * like an absence, and its word says it was scripted */
    const mark = scripted || verdict === "UNCHECKED" ? ["none", "g-none"]
      : { ACCEPT: ["pass", "g-pass"], REJECT: ["fail", "g-fail"] }[verdict];
    out.append(record("validator", PHRASING.validation.title(r), PHRASING.by.validator(r),
      el("p", null, PHRASING.validation.said(r)),
      el("div", "adii-verdicts", el("div", `adii-check adii-check--${mark[0]}`,
        glyph(mark[1], "adii-check__mark"),
        el("p", "adii-check__body",
          el("span", "adii-check__name", "candidate repair"), " ",
          el("span", "adii-check__verdict", scripted && verdict !== "UNCHECKED" ? `${verdict} · scripted` : verdict), " ",
          el("span", "adii-check__note", v.report)))),
      v.checks_run.length ? el("p", "adii-field__hint adii-mt-sm", "Checks run: ",
        ...v.checks_run.flatMap((check, i) => [i ? ", " : "", mono(check)])) : ""));
  } else if (d) {
    out.append(record("validator", "Validation", PHRASING.by.runtime,
      el("p", null, plain("not evaluated", "g-none")),
      el("p", "adii-field__hint adii-mt-sm", PHRASING.validation.notInvoked)));
  }

  /* the evaluation authority's category, when the run has been scored: its report,
   * verbatim in the mono values, with one sentence from the dictionary beside it */
  if (evaluation) {
    const e = evaluation;
    const v = r.validation;
    const atRuntime = v === null ? "none" : v.accepted ? "accepted" : v.checks_run.length ? "rejected" : "unchecked";
    out.append(record(null, "What the evaluation said", PHRASING.evaluation.by,
      el("p", "adii-assertion", PHRASING.evaluation[e.category] ?? e.category),
      meta(["category", e.category], ...(e.sub_kind ? [["sub kind", e.sub_kind]] : []),
        ...(e.verdict ? [["verdict", e.verdict]] : []),
        ...(e.settled_by ? [["settled by", PHRASING.evaluation.settledBy[e.settled_by] ?? e.settled_by]] : []),
        ...(e.reason ? [["reason", e.reason]] : [])),
      el("p", "adii-field__hint adii-mt-sm", `At runtime: ${PHRASING.evaluation.runtime[atRuntime]}.`),
      el("p", "adii-field__hint adii-mt-2xs", PHRASING.evaluation.keys)));
  }

  if (!compact) out.append(feedbackBlock(label));

  out.append(el("details", "adii-panel tech",
    el("summary", null, "Details for engineers"),
    defs(["Run", r.label], ["Model", cfg.model ?? "none"], ["Endpoint", cfg.endpoint ?? "none"],
         ["Provider", cfg.provider ?? "not recorded"], ["Turns", String(n.model_turns)],
         ["Tool calls", String(n.tool_calls)], ["Duration", seconds(n.latency_ms)],
         ["Cost", PHRASING.cost(r)],
         ["Ended", `${r.termination}: ${r.detail}`], ["Recorded", r.provenance.written_at ?? ""],
         ["Code revision", r.provenance.source_revision ?? "unknown"],
         ["Record schema", r.schema])));
  return out;
}

/* The operator's feedback on a run: recorded beside the record, attributed, shown back
 * verbatim as text. The one write a read-only inspector accepts, because it spends nothing
 * and asserts nothing about the run — it is the operator's word, labelled as such. */
function feedbackBlock(label) {
  const list = el("div", "feedback__list");
  const show = (entries) => list.replaceChildren(...entries.map((f) =>
    el("blockquote", "turn__quote",
      el("p", "adii-field__hint", `${f.by}, ${when(f.written_at)} — useful: ${f.useful}`),
      f.expected ? el("p", null, f.expected) : "")));
  guard(list, async () => show(await load(`/api/runs/${encodeURIComponent(label)}/feedback`)));
  const useful = el("fieldset", "adii-fieldset-plain feedback__useful",
    el("legend", "adii-field__label", PHRASING.product.feedbackAsk),
    ...["yes", "partly", "no"].map((v) => {
      const input = el("input"); input.type = "radio"; input.name = "useful"; input.value = v;
      return el("label", "feedback__option", input, ` ${v}`);
    }));
  const expected = el("textarea", "adii-input"); expected.rows = 3; expected.maxLength = 2000;
  const by = el("input", "adii-input"); by.maxLength = 80;
  const button = el("button", "adii-btn", "Record feedback"); button.type = "button";
  const status = el("p", "adii-field__hint");
  button.onclick = () => guard(status, async () => {
    const chosen = useful.querySelector("input:checked");
    if (!chosen) throw new Error("say whether it was useful first");
    await load(`/api/runs/${encodeURIComponent(label)}/feedback`, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ useful: chosen.value, expected: expected.value, by: by.value }) });
    status.replaceChildren(PHRASING.product.feedbackRecorded);
    button.replaceChildren("Feedback recorded");
    button.disabled = true;
    show(await load(`/api/runs/${encodeURIComponent(label)}/feedback`));
  });
  return record("operator", "Your feedback", "Written by whoever leaves it, kept beside this record",
    list, useful,
    el("div", "adii-field adii-mt-md", el("label", "adii-field__label", PHRASING.product.feedbackExpected), expected),
    el("div", "adii-field adii-mt-sm", el("label", "adii-field__label", PHRASING.product.feedbackBy), by),
    el("p", "adii-mt-md", button), status);
}

/* Group the trace into turns: each model request and everything it caused, or, for a
 * scripted run with no model events, each tool call and its answer. Nothing is dropped —
 * every event lands in exactly one turn, in order — and nothing is interpreted: the turn
 * says what was asked and what came back. */
function turns(trace) {
  const live = trace.some((e) => e.kind === "model_requested");
  const starts = live ? ["model_requested"] : ["tool_call", "decision_submitted", "validation_completed"];
  const rounds = [];
  for (const e of trace) {
    if (e.kind === "incident_received") continue;              /* the header says it */
    if (starts.includes(e.kind) || !rounds.length) rounds.push({ events: [] });
    rounds[rounds.length - 1].events.push(e);
  }
  return rounds;
}

/* One turn as a card: what was asked and what came back, what was committed, what the
 * validator said, or — when the model did none of those — what it wrote instead. */
/* `validation` is the record's: the trace event says only whether the repair was accepted,
 * and the verdict's third state — not checked — is stated by the record's `checks_run`. The
 * live view has no record yet, so it leaves that line to the story that replaces it. */
function turnCard(turn, i, validation, scripted = false) {
  const by = (kind) => turn.events.find((e) => e.kind === kind);
  const call = by("tool_call"), result = by("tool_result"), said = by("model_responded");
  const decided = by("decision_submitted"), validated = by("validation_completed");
  const body = el("div", "turn__body");
  if (call) {
    body.append(el("p", "turn__what", PHRASING.turn.asked(call.payload.name, call.payload.arguments)));
    /* the observation's own id, minted by the tool layer as it answered — shown beside
     * the sentence so a viewer can see what the decision may later cite */
    const minted = result && result.payload.content && result.payload.content.evidence_id;
    body.append(result
      ? el("p", "turn__result", `The tool layer ${PHRASING.turn.answered(result.payload)}.`,
          result.payload.status !== "OK" ? " " : "",
          result.payload.status !== "OK" ? plain(result.payload.status, "g-unresolved") : "",
          minted ? " " : "", minted ? mono(minted) : "")
      : el("p", "turn__result", PHRASING.turn.unanswered));
  }
  if (decided) body.append(el("p", "turn__what", PHRASING.turn.decided(decided.payload.disposition)));
  if (validated && validation) body.append(el("p", "turn__what", PHRASING.turn.validated(validation, scripted)));
  if (!call && !decided && !validated) {
    body.append(said
      ? el("div", null, el("p", "turn__what", PHRASING.turn.wrote), el("blockquote", "turn__quote", said.payload.content))
      : el("p", "turn__what", turn.events.map((e) => e.kind).join(", ")));
  }
  body.append(el("details", "step__raw", el("summary", null, `Raw events (${turn.events.length})`),
    el("pre", null, turn.events.map((e) =>
      JSON.stringify({ sequence: e.sequence, kind: e.kind, payload: e.payload }, null, 2)).join("\n"))));
  return el("li", "turn", el("span", "turn__n", String(i + 1)), body);
}

/* A run in progress: the live trace, polled until the record lands, then the story. */
async function watch(label) {
  crumbs([label]);
  const list = el("ol", "turns");
  const status = el("p", "adii-field__hint", PHRASING.product.running);
  const headline = el("h1", "outcome__headline", plain("running", "g-unresolved"), " Investigating");
  $("view").replaceChildren(el("div", "story",
    el("header", "outcome", el("p", "adii-eyebrow", label), headline),
    record("system", "The investigation, turn by turn", "Recorded by the runtime as it happens",
      status, list)));
  footer("A run in progress. ");
  let events = [];
  while (location.hash === `#r/${encodeURIComponent(label)}`) {
    const live = await load(`/api/runs/${label}/trace`);
    if (live.events.length !== events.length) {
      events = live.events;
      const received = events.find((e) => e.kind === "incident_received");
      if (received) headline.replaceChildren(plain("running", "g-unresolved"),
        ` Investigating ${received.payload.incident_id}`);
      const requests = events.filter((e) => e.kind === "tool_call").length;
      const answered = events.filter((e) => e.kind === "tool_result" && e.payload.status === "OK").length;
      status.replaceChildren(`${PHRASING.product.running} ${PHRASING.product.soFar(requests, answered)}`);
      list.replaceChildren(...turns(events).map((turn, i) => turnCard(turn, i)));
    }
    if (live.finished || !live.running) {     /* the record landed — or the run went silent */
      state.runs = await load("/api/runs");
      return route();
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

/* ── refusals: something this page will not interpret ───────────────── */
function refused(title, why) {
  crumbs();
  $("view").replaceChildren(el("div", "adii-callout",
    el("p", "adii-callout__title", title),
    el("p", null, `${why} Nothing below is interpreted.`)),
    el("p", "adii-mt-md", link("adii-btn", "Back to ADII", "#")));
}
function mismatch(schema) {
  refused("This record is in a shape this inspector does not read",
    `It declares ${schema} and this page renders ${SCHEMA}.`);
}

/* ── records: a container with a written owner ──────────────────────── */
/* `owner` picks the identity's riser colour; an owner the identity has no colour for —
 * the evaluation authority — is named in text only, which is the rule anyway. */
function record(owner, title, ownerLine, ...kids) {
  return el("article", owner ? `adii-record adii-record--${owner}` : "adii-record",
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
