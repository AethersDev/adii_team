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
 * The page starts a run only when the operator started the server with a local model — a
 * page that can start a run can spend money, so otherwise it says how a run is started,
 * on every screen. Its footer says which it is.
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
      row.validation ? `${row.validation === "ACCEPT" ? "accepted" : "not accepted"} by the validator` : "");
  }
  return plain(PHRASING.outcome[row.termination]?.() ?? row.termination, "g-unresolved");
}

async function load(url, init) {
  const res = await fetch(url, init);
  const code = res.headers.get("ADII-Code");         /* the page's code, as served right now */
  if (code && state.code && code !== state.code) location.reload();   /* this tab's script is older */
  state.code = state.code ?? code;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `${url} answered ${res.status}`);
  return body;
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

/* every screen's footer says whether this page can start a run, and against what */
const footer = (prefix = "") => foot(prefix + (state.launch.enabled
  ? PHRASING.product.footLive(state.launch.model) : PHRASING.product.footReadOnly));

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

/* Start a run against the local model the server was started with. The server answers
 * with the label at once and runs the investigation; the page goes to the run and watches. */
function launcher(preset) {
  const select = el("select", "adii-select");
  select.id = "launch-incident";
  const fill = async () => {
    const incidents = await load("/api/incidents");
    select.replaceChildren(...incidents.map((i) => option(i.incident_id, i.incident_id)));
    if (preset) select.value = preset;
  };
  const button = el("button", "adii-btn adii-btn--primary", "Investigate");
  button.type = "button";
  const status = el("p", "adii-field__hint");
  button.onclick = () => guard(status, async () => {
    button.disabled = true;
    status.replaceChildren("Starting…");
    const answer = await load("/api/runs", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ incident: select.value }) });
    state.starting = answer.label;
    location.hash = `#r/${encodeURIComponent(answer.label)}`;
  });
  guard(status, fill);
  return el("section", "adii-panel howto",
    el("h2", "adii-panel__title", "Investigate an incident"),
    el("p", "adii-type-sm", PHRASING.product.liveAllowed(state.launch.model)),
    el("div", "adii-toolbar",
      el("div", "adii-field", el("label", "adii-field__label", "Incident"), select),
      button),
    status);
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
    if (r.error || r.running) continue;
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
    state.launch.enabled ? launcher() : "",        /* the main action first, when allowed */
    el("section", null,
      el("div", "adii-section__head", el("h2", null, "Incidents"),
        el("span", "adii-eyebrow", cards.length
          ? `${cards.length} incident${cards.length === 1 ? "" : "s"}, ${state.runs.length - unreadable} run${state.runs.length - unreadable === 1 ? "" : "s"}` +
            (unreadable ? `, ${unreadable} unreadable` : "")
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
  const other = against && state.runs.find((r) => r.label === against && !r.error
    && r.incident_id === row.incident_id);
  crumbs(["Incidents", "#"], [a.context.incident_id, `#i/${encodeURIComponent(a.context.incident_id)}`],
    [other ? "Two runs, side by side" : label]);
  if (!other) {
    $("view").replaceChildren(story(a, false, label), howto());
  } else {
    const b = await load(`/api/runs/${against}`);
    if (b.schema !== SCHEMA) return mismatch(b.schema);
    $("view").replaceChildren(
      el("div", "story__nav",
        el("span", "adii-eyebrow", `Two runs of ${a.context.incident_id}, side by side`),
        link("adii-btn", "Close comparison", `#r/${encodeURIComponent(label)}`)),
      el("div", "compare", story(a, true), story(b, true)));
  }
  footer(`An ${SCHEMA} record, shown as archived. `);
}

/* ── the run page: outcome first, then the investigation turn by turn ─────────────
 * What an operator reads, in the order they need it: what came of the run, what it looked
 * at and what came back, the change it proposed, what the validator said. The machinery —
 * ids, revisions, counters — is one closed disclosure at the end. A section the record
 * cannot fill is left out. */
const seconds = (ms) => (ms >= 1000 ? `${Math.round(ms / 1000)} s` : `${ms} ms`);
const shortModel = (model) => (model ? String(model).split("/").pop() : "no model");

function story(r, compact = false, label = r.label) {
  const c = r.context, d = r.decision, cfg = r.configuration, n = r.counters;
  const out = el("div", "story");
  const ran = cfg.model ? `${shortModel(cfg.model)} · ` : "";

  /* the outcome, first */
  out.append(el("header", "outcome",
    el("p", "adii-eyebrow", compact ? r.label
      : `${c.incident_id} · ${ran}${n.tool_calls} tool call${n.tool_calls === 1 ? "" : "s"} · ${seconds(n.latency_ms)}`),
    el("h1", "outcome__headline", d ? chip(d.disposition) : plain(PHRASING.outcome[r.termination]?.(r) ?? r.termination, "g-unresolved"),
      " ", PHRASING.headline[r.termination]?.(r) ?? r.termination),
    scriptedNote(cfg.model)));

  if (d) {
    out.append(record("system", "What it concluded", `Asserted by ${INVESTIGATOR}`,
      el("p", "adii-assertion", d.root_cause_summary),
      el("p", "adii-field__hint adii-mt-sm", PHRASING.disposition[d.disposition]),
      d.root_cause_id ? meta(["Root cause", d.root_cause_id]) : ""));
  } else {
    out.append(record("system", "Why there is no decision",
      `Reported by ${r.termination === "infrastructure_failure" ? "the runtime" : INVESTIGATOR}`,
      el("p", "adii-measure", PHRASING.ended[r.termination]?.(r) ?? r.termination),
      el("p", "adii-field__hint adii-mt-2xs", "In the record's words: ", mono(r.detail))));
  }

  out.append(record("operator", "The incident", "Reported by the operator",
    el("p", "adii-measure", c.alert),
    meta(["As of", c.as_of],
         ["May write", c.permitted_write_paths.length ? c.permitted_write_paths.join(", ") : "nothing"])));

  const rounds = turns(r.trace);
  out.append(record("system", "The investigation, turn by turn",
    `Recorded by the runtime as it happened · ${rounds.length} turn${rounds.length === 1 ? "" : "s"}`,
    el("ol", "turns", ...rounds.map(turnCard))));

  if (d && d.repair_id) {
    out.append(record("system", "The change it proposed", `Proposed by ${INVESTIGATOR}. Not applied by anyone.`,
      defs(["Repair", d.repair_id]),
      ...Object.entries(d.patch).flatMap(([path, body]) => [
        el("p", "adii-claim__label adii-mt-md", path),
        el("div", "adii-change__diff", ...body.replace(/\n$/, "").split("\n").map((line) =>
          el("span", "adii-diff__line", el("span", "adii-diff__marker", " "), line, "\n")))])));
  }

  if (r.validation) {
    const v = r.validation, verdict = v.accepted ? "ACCEPT" : "REJECT";
    out.append(record("validator", "What the validator said", `Asserted by ${VALIDATOR}`,
      el("div", "adii-verdicts", el("div", `adii-check adii-check--${v.accepted ? "pass" : "fail"}`,
        glyph(v.accepted ? "g-pass" : "g-fail", "adii-check__mark"),
        el("p", "adii-check__body",
          el("span", "adii-check__name", "candidate repair"), " ",
          el("span", "adii-check__verdict", verdict), " ",
          el("span", "adii-check__note", v.report)))),
      v.checks_run.length ? el("p", "adii-field__hint adii-mt-sm", "Checks run: ",
        ...v.checks_run.flatMap((check, i) => [i ? ", " : "", mono(check)])) : ""));
  } else if (d) {
    out.append(record("validator", "Validation", `Held by ${VALIDATOR}`,
      el("p", null, plain("not evaluated", "g-none")),
      el("p", "adii-field__hint adii-mt-sm", PHRASING.validation.notInvoked)));
  }

  if (!compact) out.append(feedbackBlock(label));

  out.append(el("details", "adii-panel tech",
    el("summary", null, "Details for engineers"),
    defs(["Run", r.label], ["Model", cfg.model ?? "none"], ["Endpoint", cfg.endpoint ?? "none"],
         ["Provider", cfg.provider ?? "not recorded"], ["Turns", String(n.model_turns)],
         ["Tool calls", String(n.tool_calls)], ["Duration", seconds(n.latency_ms)],
         ["Cost", n.api_cost_usd ? `$${n.api_cost_usd}` : "nothing (no paid provider)"],
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
  return record("operator", "Your feedback", "Asserted by whoever writes it, kept beside this record",
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
function turnCard(turn, i) {
  const by = (kind) => turn.events.find((e) => e.kind === kind);
  const call = by("tool_call"), result = by("tool_result"), said = by("model_responded");
  const decided = by("decision_submitted"), validated = by("validation_completed");
  const body = el("div", "turn__body");
  if (call) {
    body.append(el("p", "turn__what", PHRASING.turn.asked(call.payload.name, call.payload.arguments)));
    body.append(result
      ? el("p", "turn__result", `The tool layer ${PHRASING.turn.answered(result.payload)}.`,
          result.payload.status !== "OK" ? " " : "",
          result.payload.status !== "OK" ? plain(result.payload.status, "g-unresolved") : "")
      : el("p", "turn__result", PHRASING.turn.unanswered));
  }
  if (decided) body.append(el("p", "turn__what", PHRASING.turn.decided(decided.payload.disposition)));
  if (validated) body.append(el("p", "turn__what", PHRASING.turn.validated(validated.payload.accepted)));
  if (!call && !decided && !validated) {
    body.append(said
      ? el("div", null, el("p", "turn__what", PHRASING.turn.wrote), el("blockquote", "turn__quote", said.payload.content))
      : el("p", "turn__what", turn.events.map((e) => e.kind).join(", ")));
  }
  const kinds = turn.events.map((e) => e.kind).join(", ");
  body.append(el("details", "step__raw", el("summary", null, `raw events · ${kinds}`),
    el("pre", null, turn.events.map((e) =>
      JSON.stringify({ sequence: e.sequence, kind: e.kind, payload: e.payload }, null, 2)).join("\n"))));
  return el("li", "turn", el("span", "turn__n", String(i + 1)), body);
}

/* A run in progress: the live trace, polled until the record lands, then the story. */
async function watch(label) {
  crumbs(["Incidents", "#"], [label]);
  const list = el("ol", "turns");
  const status = el("p", "adii-field__hint", PHRASING.product.running);
  $("view").replaceChildren(el("div", "story",
    el("header", "outcome", el("p", "adii-eyebrow", label),
      el("h1", "outcome__headline", plain("running", "g-unresolved"), " Investigating")),
    record("system", "The investigation, turn by turn", "Recorded by the runtime as it happens",
      status, list)));
  footer("A run in progress. ");
  let events = [];
  while (location.hash === `#r/${encodeURIComponent(label)}`) {
    const live = await load(`/api/runs/${label}/trace`);
    if (live.events.length !== events.length) {
      events = live.events;
      list.replaceChildren(...turns(events).map(turnCard));
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
