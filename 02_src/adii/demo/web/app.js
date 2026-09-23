/* ADII — Is it broken? The front door over the run archive.
 *
 * Draws what view.js projects from the records the server serves, and nothing else: every
 * run is the same `python -m adii.runtime` the evaluation scores, started here only when the
 * operator configured a model. The page is a view and a starter, never an authority: it
 * decides no answer, admits no change and executes nothing.
 *
 * No innerHTML anywhere. Every string a model wrote reaches the page as a text node, which
 * cannot execute (inherited D12; test_the_page_executes_nothing.py).
 */
"use strict";

const V = VIEW;   // view.js, loaded first
const SVG = "http://www.w3.org/2000/svg";
const SCHEMAS = ["adii.run_record/v3", "adii.run_record/v2", "adii.run_record/v1"];
const state = { launch: { enabled: false }, incidents: [], runs: [], filter: "all",
                query: "", pick: null, desc: "", files: [], note: "", timer: null, code: null };

function el(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return node;
}

function svg(tag, attrs, ...kids) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, String(value));
  for (const kid of kids.flat(Infinity)) if (kid) node.append(kid);
  return node;
}

async function json(url, options) {
  const answer = await fetch(url, { cache: "no-store", ...options });
  // every response names the page's code as served: a tab running older code reloads once
  const served = answer.headers.get("ADII-Code");
  if (served && state.code && served !== state.code) location.reload();
  state.code = state.code || served;
  const body = await answer.json().catch(() => ({ error: "the server's answer was not JSON" }));
  if (!answer.ok) throw new Error(body.error || "the server refused: " + answer.status);
  return body;
}

function stop() {
  if (state.timer) clearTimeout(state.timer);
  state.timer = null;
}

/* ── the shell ─────────────────────────────────────────────────────────────────────── */

function brand() {
  return el("a", { class: "brand", href: "#", "aria-label": "ADII — Is it broken?" },
    el("span", { class: "brand__mark", role: "img", "aria-label": "ADII" }),
    el("span", { class: "brand__question", text: "Is it broken?" }));
}

function side() {
  const l = state.launch;
  return el("nav", { class: "side", "aria-label": "Workspace" },
    brand(),
    el("button", { type: "button", class: "btn btn--primary side__new",
                   onclick: () => { state.pick = null; state.desc = ""; state.files = [];
                                    go("#new"); } }, "New investigation"),
    el("a", { class: "side__item", href: "#", "aria-current": "page" },
      el("span", { text: "Investigations" }),
      el("span", { class: "side__count", text: String(state.runs.length) })),
    el("dl", { class: "side__foot" },
      el("dt", { text: "Investigator" }),
      el("dd", { text: l.enabled ? String(l.model) : "Read-only: no model configured" }),
      l.enabled && l.max_cost_usd !== undefined
        ? [el("dt", { text: "Cost cap per run" }),
           el("dd", { class: "mono", text: "$" + Number(l.max_cost_usd).toFixed(2) })]
        : null));
}

function page(header, main) {
  const root = document.getElementById("app");
  root.replaceChildren(el("div", { class: "app" }, side(),
    el("div", { class: "pane" }, header, el("div", { class: "pane__scroll" }, main))));
  // what the fit test reads: the document's width against the viewport's — reading them
  // lays the page out, so the measurement is of what was just drawn
  const doc = document.documentElement;
  doc.dataset.measured = doc.scrollWidth + "," + doc.clientWidth;
}

function go(hash) {
  if (location.hash === hash || (hash === "#" && !location.hash)) route();
  else location.hash = hash;
}

/* ── the investigations list ──────────────────────────────────────────────────────── */

function sparkline(rows, width, height) {
  const c = V.chart(rows, width, height, 6);
  return svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "spark", "aria-hidden": "true" },
    svg("polyline", { points: c.points, class: "spark__line" }),
    svg("circle", { cx: c.last[0].toFixed(1), cy: c.last[1].toFixed(1), r: 4,
                    class: "spark__dot" }));
}

function composer(neutral) {
  const samples = state.incidents.filter((i) => i.sample);
  const ready = state.launch.enabled && (state.pick || (state.desc.trim() && state.files.length));
  const read = (list) => Promise.all([...list].map((file) => file.text().then((text) => (
    { name: file.name, text, size: file.size })))).then((files) => {
    state.files = files; state.pick = null; list.value = ""; render();
  });
  const input = el("input", { id: "attach", type: "file", accept: ".csv", multiple: true,
                              class: "visually-hidden",
                              onchange: (e) => read(e.target.files) });
  return el("section", { class: "composer", "aria-label": "New investigation" },
    el("label", { for: "composer", class: "visually-hidden", text: "What looks wrong?" }),
    el("textarea", { id: "composer", rows: 2, class: "composer__text",
                     placeholder: "What looks wrong? For example: daily revenue fell sharply " +
                                  "on Tuesday.",
                     oninput: (e) => { state.desc = e.target.value;
                                       if (state.pick) state.pick = null; } },
      state.desc),
    el("div", { class: "composer__bar" },
      el("div", { class: "composer__files" },
        el("label", { for: "attach", class: "btn btn--quiet" }, "Attach CSV files"), input,
        state.files.map((f) => el("span", { class: "chip mono" }, f.name,
          el("span", { class: "chip__size", text: Math.ceil(f.size / 1024) + " KB" }),
          el("button", { type: "button", class: "chip__x", "aria-label": "Remove " + f.name,
                         onclick: () => { state.files = state.files.filter((x) => x !== f);
                                          render(); } }, "×"))),
        state.pick ? el("span", { class: "chip" }, "Sample incident",
          el("button", { type: "button", class: "chip__x", "aria-label": "Clear the sample",
                         onclick: () => { state.pick = null; state.desc = ""; render(); } },
             "×")) : null),
      el("button", { type: "button", id: "investigate", class: "btn btn--primary",
                     "aria-disabled": ready ? "false" : "true", onclick: investigate },
         "Investigate")),
    state.note ? el("p", { class: "composer__note", role: "status", text: state.note }) : null,
    el("p", { class: "composer__pitch", text: "ADII investigates a number that looks wrong in " +
      "your data and decides whether to fix it, leave it alone, or escalate it. The AI that " +
      "proposes a fix can’t approve it." }),
    samples.length && state.runs.length && !neutral
      ? el("div", { class: "samples" }, el("span", { text: "Try a sample incident:" }),
          samples.map((s, i) => el("button", { type: "button", class: "pill", title: s.alert,
            "data-incident": s.incident_id,
            "aria-pressed": state.pick === s.incident_id ? "true" : "false",
            onclick: () => pick(s) }, "Sample " + (i + 1))),
          el("span", { class: "samples__note", text: "The same alert over three different " +
                                                     "states of the data. Is it broken?" }))
      : null);
}

function pick(sample) {
  state.pick = sample.incident_id; state.desc = sample.alert; state.files = []; state.note = "";
  render();
}

async function investigate() {
  if (!state.launch.enabled) {
    state.note = "This page is read-only: start it with a model to investigate.";
    return render();
  }
  try {
    const started = state.pick
      ? await json("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ incident: state.pick }) })
      : state.desc.trim() && state.files.length
        ? await json("/api/investigations", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ description: state.desc,
                                   files: state.files.map((f) => ({ name: f.name, text: f.text })) }) })
        : null;
    if (!started) {
      state.note = "Say what looks wrong and attach the CSV files behind it, or pick a sample.";
      return render();
    }
    state.pick = null; state.desc = ""; state.files = []; state.note = "";
    go("#r/" + encodeURIComponent(started.label));
  } catch (why) {
    state.note = why.message;
    render();
  }
}

const TABS = [["all", "All"], ["running", "Running"], ["fix", "Fix it"], ["leave", "Leave it"],
              ["escalate", "Escalate it"], ["none", "No answer"]];

function glyph(key) {
  return el("span", { class: "glyph glyph--" + key, "aria-hidden": "true" });
}

/* A neutral launch view, for a room: what looks wrong and the samples, and no earlier
 * answer anywhere on the screen — a sample's past outcome shown before it runs would give
 * the answer away. The history is one click away, under Investigations. */
function launch() {
  const samples = state.incidents.filter((i) => i.sample);
  page(el("header", { class: "bar" }, el("h1", { class: "serif bar__title", text: "New investigation" })),
    el("main", { class: "list" }, composer(true),
      samples.length ? el("section", { class: "empty", "aria-label": "Sample incidents" },
        el("p", { text: "The same alert over three different states of the data. Is it broken?" }),
        el("div", { class: "empty__samples" }, samples.map((s, i) =>
          el("button", { type: "button", class: "sample", "data-incident": s.incident_id,
                         "aria-pressed": state.pick === s.incident_id ? "true" : "false",
                         onclick: () => pick(s) },
            el("span", { class: "tag", text: "Sample " + (i + 1) }),
            s.series ? sparkline(s.series.rows, 300, 64) : null,
            el("span", { class: "sample__title", text: s.alert }))))) : null));
}

function list() {
  const rows = state.runs.map((r) => V.row(r, Date.now()));
  const counts = {};
  rows.forEach((r) => { counts[r.answer] = (counts[r.answer] || 0) + 1; });
  const shown = rows.filter((r) => (state.filter === "all" || r.answer === state.filter) &&
    r.title.toLowerCase().includes(state.query.toLowerCase()));
  const samples = state.incidents.filter((i) => i.sample);
  const empty = !state.runs.length;
  const header = el("header", { class: "bar" },
    el("h1", { class: "serif bar__title", text: "Investigations" }),
    el("label", { class: "search" }, el("span", { class: "visually-hidden",
                                                  text: "Search investigations" }),
      el("input", { type: "search", placeholder: "Search investigations", value: state.query,
                    oninput: (e) => { state.query = e.target.value; render();
                                      const again = document.querySelector(".search input");
                                      again.focus();
                                      again.setSelectionRange(state.query.length,
                                                              state.query.length); } })));
  const main = el("main", { class: "list" }, composer(),
    empty
      ? el("section", { class: "empty", "aria-labelledby": "empty-h" },
          el("h2", { id: "empty-h", class: "serif", text: "No investigations yet" }),
          el("p", { text: "Describe a number that looks wrong and attach the CSV files behind " +
                          "it. No data at hand? Start from a sample incident." }),
          el("div", { class: "empty__samples" }, samples.map((s, i) =>
            el("button", { type: "button", class: "sample", "data-incident": s.incident_id,
                           onclick: () => pick(s) },
              el("span", { class: "tag", text: "Sample " + (i + 1) }),
              s.series ? sparkline(s.series.rows, 300, 64) : null,
              el("span", { class: "sample__title", text: s.alert })))))
      : el("section", { class: "runs", "aria-label": "All investigations" },
          el("div", { class: "tabs", role: "tablist", "aria-label": "Filter by answer" },
            TABS.map(([key, label]) => el("button", {
              type: "button", role: "tab", class: "tab",
              "aria-selected": state.filter === key ? "true" : "false",
              onclick: () => { state.filter = key; render(); } },
              label, el("span", { class: "tab__count",
                                  text: String(key === "all" ? rows.length : counts[key] || 0) })))),
          el("div", { class: "runs__head", "aria-hidden": "true" },
            ["What looks wrong", "Answer", "Change", "Record", "Started"].map((t) =>
              el("span", { text: t }))),
          el("ul", { class: "runs__list" }, shown.map((r) => el("li", null,
            el("a", { class: "run", href: "#r/" + encodeURIComponent(r.label) },
              el("span", { class: "run__title", text: r.title }),
              el("span", { class: "answer answer--" + r.answer }, glyph(r.answer), r.answerLabel),
              el("span", { class: "run__change", text: r.change }),
              el("span", { class: "run__rec mono", text: r.label }),
              el("span", { class: "run__when", text: r.when })))))));
  page(header, main);
  if (rows.some((r) => r.answer === "running")) {
    state.timer = setTimeout(() => refresh().then(render), 2000);
  }
}

/* ── one investigation ─────────────────────────────────────────────────────────────── */

function dayLabel(day) {
  const d = new Date(String(day) + "T00:00:00Z");
  return isNaN(d) ? String(day) : d.toLocaleDateString("en-US", { month: "short", day: "numeric",
                                                                  timeZone: "UTC" });
}

function lineChart(lines, rows, caption) {
  const W = 1200, H = 220, pad = 24;
  const all = lines.flatMap((l) => l.rows);
  const top = Math.max(...all.map((r) => Number(r[1]))) * 1.1 || 1;
  const x = (i, n) => pad + i * ((W - 2 * pad) / Math.max(n - 1, 1));
  const y = (v) => H - pad - (Number(v) / top) * (H - 2 * pad);
  const drawn = lines.map((l) => {
    const pts = l.rows.map((r, i) => x(i, l.rows.length).toFixed(1) + "," + y(r[1]).toFixed(1));
    const last = l.rows[l.rows.length - 1];
    return [svg("polyline", { points: pts.join(" "), class: "line line--" + l.kind }),
            svg("circle", { cx: x(l.rows.length - 1, l.rows.length).toFixed(1),
                            cy: y(last[1]).toFixed(1), r: 9, class: "dot dot--" + l.kind })];
  });
  return el("figure", { class: "chart" },
    el("div", { class: "chart__legend" }, lines.map((l) =>
      el("span", { class: "legend legend--" + l.kind }, el("span", { class: "legend__swatch" }),
         l.label))),
    svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart__svg", role: "img",
                 "aria-label": caption },
      svg("line", { x1: 0, y1: H - pad, x2: W, y2: H - pad, class: "axis" }), drawn),
    el("div", { class: "chart__days", "aria-hidden": "true",
                style: `grid-template-columns: repeat(${rows.length}, minmax(0, 1fr))` },
      rows.map((r, i) => el("span", { class: i === rows.length - 1 ? "is-last" : null,
                                      text: i === rows.length - 1 || i % 3 === 0
                                        ? dayLabel(r[0]) : "" }))),
    el("figcaption", { text: caption }));
}

function symptom(series) {
  if (!series.before) return null;
  const b = series.before, moved = V.change(b.rows);
  const last = b.rows[b.rows.length - 1];
  return el("section", { class: "symptom", "aria-labelledby": "symptom-h" },
    el("div", { class: "symptom__head" },
      el("h2", { id: "symptom-h", class: "symptom__metric", text: b.metric }),
      el("span", { class: "symptom__value" }, V.money(last[1], b.unit),
         moved !== null ? el("span", { class: "symptom__move",
           text: (moved > 0 ? " ↑" : " ↓") + Math.abs(moved) + "% " + b.metric.toLowerCase() +
                 " against the " + (b.rows.length - 1) + " days before" })
                        : null)),
    lineChart([{ kind: "before", label: b.metric + ", as the system read it before " +
                 "anything was investigated", rows: b.rows }], b.rows,
      "What looked wrong: the alerted number, read from the data when the run began. It " +
      "is the symptom, not evidence."));
}

function observationCard(o) {
  return el("li", { class: "obs" + (o.table && o.table.columns.length > 3 ? " obs--wide" : "") },
    el("span", { class: "obs__title", text: o.title }),
    o.code ? el("pre", { class: "obs__code mono", text: o.code }) : null,
    o.text ? el("p", { class: "obs__text", text: o.text }) : null,
    o.table ? el("table", { class: "obs__table" },
      el("thead", null, el("tr", null, o.table.columns.map((c) => el("th", { text: String(c) })))),
      el("tbody", null, o.table.rows.map((r) => el("tr", null,
        r.map((v) => el("td", { class: "mono", text: String(v) })))))) : null,
    o.table && o.table.more ? el("span", { class: "obs__more",
                                           text: o.table.more + " more rows" }) : null);
}

function knows(record, v) {
  const cites = V.cited(record);
  const heading = v.key === "escalate" ? "What ADII found" : "How ADII knows";
  return el("section", { class: "knows", "aria-labelledby": "knows-h" },
    el("h2", { id: "knows-h", class: "serif", text: heading }),
    el("p", { class: "muted", text: "The observations the decision cites, as the tool layer " +
                                    "returned them." }),
    cites.length ? el("ul", { class: "obs-list" }, cites.map(observationCard))
                 : el("p", { text: "The decision cites no observations." }));
}

function fix(record) {
  return el("section", { class: "fix", "aria-labelledby": "fix-h" },
    el("h2", { id: "fix-h", class: "serif", text: "Proposed fix" }),
    V.proposal(record).map((p) => el("div", { class: "diff" },
      el("div", { class: "diff__head" }, el("span", { class: "mono", text: p.path }),
         p.observed ? null : el("span", { class: "muted", text: "new contents" })),
      el("div", { class: "diff__body mono" }, p.lines.map((l) =>
        el("div", { class: "diff__line diff__line--" + ({ "+": "add", "-": "del" }[l.op] || "same") },
          el("span", { class: "diff__n", text: String(l.line) }),
          el("span", { class: "diff__op", "aria-hidden": "true", text: l.op === " " ? "" : l.op }),
          el("span", { class: "visually-hidden", text: { "+": "Added: ", "-": "Removed: " }[l.op] || "" }),
          el("span", { class: "diff__text", text: l.text })))))));
}

function rebuild(record, series) {
  const lines = V.checks(record);
  return el("section", { class: "rebuild", "aria-labelledby": "rebuild-h" },
    el("h2", { id: "rebuild-h", class: "serif", text: "Independent rebuild" }),
    el("p", { class: "muted", text: "The validator is a separate program. It rebuilt the data " +
      "from a frozen copy with the change applied and read the number again. The investigator " +
      "never sees this." }),
    series.rebuilt && series.before
      ? lineChart([{ kind: "before", label: "Before", rows: series.before.rows },
                   { kind: "rebuilt", label: "The validator's rebuild", rows: series.rebuilt.rows }],
          series.rebuilt.rows, "A chart that recovers is not yet a repair: the validator's " +
          "checks below decide.")
      : null,
    el("ul", { class: "checks" }, lines.map((c) => el("li", { class: c.held ? "is-held" : "is-failed" },
      el("span", { class: "checks__mark", "aria-hidden": "true", text: c.held ? "✓" : "✕" }),
      el("span", { class: "checks__name mono", text: c.name }),
      el("span", { class: "checks__said", text: c.said })))));
}

function lookedAt(record) {
  const all = V.investigated(record);
  return el("details", { class: "looked" },
    el("summary", null, "Investigated: ADII looked at " + all.length +
       (all.length === 1 ? " thing" : " things")),
    el("ol", null, all.map((i) => el("li", null,
      el("span", { class: "looked__title", text: i.title }),
      i.what ? el("span", { class: "mono looked__what", text: i.what }) : null,
      i.status !== "OK" ? el("span", { class: "looked__status", text: i.status }) : null))));
}

function slots(record) {
  const all = V.slots(record);
  return el("section", { class: "aside__block", "aria-labelledby": "ans-h" },
    el("h2", { id: "ans-h", class: "aside__h", text: "Answer" }),
    el("div", { class: "slots", role: "img", "aria-label": record && record.decision
      ? "Answer: " + all.find((s) => s.landed).label + "." : "No answer yet." },
      all.map((s) => el("span", { class: "slot" + (s.landed ? " is-landed" : "") + (record ? "" : " is-waiting") },
        el("span", { class: "slot__glyph glyph--" + s.key }),
        el("span", { class: "slot__label", text: s.label })))));
}

function signoff(record) {
  return el("section", { class: "aside__block", "aria-labelledby": "sign-h" },
    el("h2", { id: "sign-h", class: "aside__h", text: "Sign-off" }),
    el("p", { class: "aside__note", text: "The AI that proposes a fix can’t approve it." }),
    el("ul", { class: "signoff" }, V.signoff(record).map((g) => el("li", null,
      el("span", { class: "signoff__mark", "aria-hidden": "true", text: g.mark }),
      el("span", { class: "signoff__body" },
        el("span", { class: "signoff__row" }, el("span", { class: "signoff__who", text: g.who }),
          el("span", { class: "signoff__status tone--" + g.tone, text: g.status })),
        el("span", { class: "signoff__note", text: g.note }))))));
}

function recordPanel(record, label, fingerprint, receipt, v) {
  const known = state.incidents.some((i) => i.incident_id === record.context.incident_id);
  const cta = {
    fix: V.admissible(record) ? ["Download the fix", () => {
      const patch = record.decision.patch;
      const text = Object.keys(patch).sort().map((p) => "-- " + p + "\n" + patch[p]).join("\n");
      save(label + ".fix.sql", text);
    }] : null,
    leave: ["Copy summary", () => copy(v.headline + "\n" + (v.summary || "") + "\nRecord " + label)],
    escalate: ["Copy handoff note", () => copy(v.headline + "\n" + (v.summary || "") +
                                               "\nRecord " + label)],
    none: known && state.launch.enabled ? ["Try again", () => {
      state.pick = record.context.incident_id; investigate(); }] : null,
  }[v.key];
  return el("section", { class: "aside__block", "aria-labelledby": "rec-h" },
    el("h2", { id: "rec-h", class: "aside__h", text: "Record" }),
    el("dl", { class: "facts" },
      el("dt", { text: "Record" }), el("dd", { class: "mono", text: label }),
      el("dt", { text: "Fingerprint" }),
      el("dd", { class: "mono", title: fingerprint, text: fingerprint
        ? "sha256 " + fingerprint.slice(0, 4) + "…" + fingerprint.slice(-4) : "—" }),
      el("dt", { text: "Receipt" }),
      el("dd", { text: receipt ? "Written before the first model request" : "—" }),
      el("dt", { text: "Investigator" }),
      el("dd", { text: String((record.configuration || {}).model || "No model") }),
      el("dt", { text: "Spend" }), el("dd", { class: "mono", text: V.spend(record) })),
    el("div", { class: "aside__actions" },
      el("a", { class: "btn btn--quiet", href: "/api/runs/" + encodeURIComponent(label),
                download: label + ".record.json" }, "Download record"),
      cta ? el("button", { type: "button", class: "btn btn--primary", onclick: cta[1] }, cta[0])
          : null));
}

function save(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  el("a", { href: url, download: name }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function copy(text) {
  if (navigator.clipboard) navigator.clipboard.writeText(text);
}

function crumbs(label) {
  return el("header", { class: "bar" },
    el("nav", { class: "crumbs", "aria-label": "Breadcrumb" },
      el("a", { href: "#", text: "Investigations" }), el("span", { "aria-hidden": "true", text: "/" }),
      el("span", { class: "mono", text: label })));
}

function answer(record, label, fingerprint, receipt) {
  const v = V.verdict(record), series = V.series(record);
  const secs = Math.round(Number((record.counters || {}).latency_ms || 0) / 1000);
  const main = el("main", { class: "detail" },
    el("div", { class: "detail__intro" },
      el("h1", { class: "serif detail__title", text: record.context.alert }),
      el("div", { class: "detail__meta" },
        el("span", { class: "mono", text: record.context.incident_id }),
        el("span", { text: "Investigated in " + secs + " s" }))),
    el("div", { class: "detail__grid" },
      el("div", { class: "detail__main" },
        symptom(series),
        el("article", { class: "verdict verdict--" + v.key, "aria-labelledby": "verdict-h" },
          el("div", { class: "verdict__band", "aria-hidden": "true" }),
          el("h2", { id: "verdict-h", class: "serif verdict__headline", text: v.headline }),
          el("p", { class: "verdict__lead", text: v.lead }),
          v.summary ? el("div", { class: "verdict__words" },
            el("span", { class: "verdict__who", text: "In the investigator’s words" }),
            el("p", { text: v.summary })) : null,
          v.key === "none" && v.detail ? el("p", { class: "verdict__detail mono",
                                                   text: "The record says: " + v.detail }) : null),
        v.key === "none" ? null : knows(record, v),
        v.key === "fix" ? [fix(record), rebuild(record, series)]
          : v.key === "none" ? null
          : el("p", { class: "nochange", text: "No change proposed. Nothing was touched." }),
        lookedAt(record)),
      el("aside", { class: "aside" }, slots(record), signoff(record),
         recordPanel(record, label, fingerprint, receipt, v))));
  page(crumbs(label), main);
}

function running(label, trace) {
  const events = trace.events || [];
  const pseudo = { trace: events.map((e) => ({ kind: e.kind, payload: e.payload })) };
  const series = V.series(pseudo);
  const received = events.find((e) => e.kind === "incident_received");
  const incident = received ? received.payload.incident_id : "";
  const known = state.incidents.find((i) => i.incident_id === incident);
  const turns = events.filter((e) => e.kind === "model_requested").length;
  const most = state.launch.max_turns;
  const looked = V.investigated(pseudo);
  const main = el("main", { class: "detail" },
    el("div", { class: "detail__intro" },
      el("h1", { class: "serif detail__title", text: known ? known.alert : "Your investigation" }),
      el("div", { class: "detail__meta" }, el("span", { class: "mono", text: incident }),
         el("span", { text: trace.running === false ? "Not running" : "Investigating" }))),
    el("div", { class: "detail__grid" },
      el("div", { class: "detail__main" }, symptom(series),
        el("section", { class: "checking", "aria-labelledby": "run-h" },
          el("div", { class: "checking__head" },
            el("h2", { id: "run-h", class: "serif", text: "Investigating" }),
            el("span", { role: "status", class: "checking__status",
                         text: most ? "Turn " + turns + " of " + most : "Turn " + turns })),
          looked.length ? el("ol", { class: "checking__list" }, looked.map((i) => el("li", null,
            el("span", { class: "looked__title", text: i.title }),
            i.what ? el("span", { class: "mono looked__what", text: i.what }) : null,
            i.status !== "OK" ? el("span", { class: "looked__status", text: i.status }) : null)))
            : el("p", { class: "muted", text: "Starting: the receipt is written before the " +
                                              "first request to the model." }))),
      el("aside", { class: "aside" }, slots(null))));
  page(crumbs(label), main);
}

async function detail(label, waited = 0) {
  const base = "/api/runs/" + encodeURIComponent(label);
  let trace;
  try {
    trace = await json(base + "/trace");
  } catch (why) {
    // a run just started is answered with its label a moment before the runtime reserves
    // its folder: keep asking for a few seconds before calling it unreadable
    if (waited < 10) {
      running(label, { events: [] });
      state.timer = setTimeout(() => detail(label, waited + 1), 1000);
      return;
    }
    return page(crumbs(label), el("main", { class: "detail" },
      el("p", { class: "problem", role: "alert", text: "This run could not be read: " + why.message })));
  }
  if (!trace.finished) {
    running(label, trace);
    if (trace.running !== false) state.timer = setTimeout(() => detail(label), 1000);
    return;
  }
  const answerText = await (await fetch(base, { cache: "no-store" })).text();
  const record = JSON.parse(answerText);
  if (!SCHEMAS.includes(record.schema)) {
    return page(crumbs(label), el("main", { class: "detail" }, el("p", { class: "problem",
      role: "alert", text: "This record is in a shape this page does not read: it declares " +
      record.schema + " and this page reads " + SCHEMAS.join(", ") + ". Nothing is interpreted." })));
  }
  const bytes = new TextEncoder().encode(answerText);
  const fingerprint = crypto.subtle
    ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
        .map((b) => b.toString(16).padStart(2, "0")).join("")
    : "";
  answer(record, label, fingerprint, trace.receipt);
}

/* ── boot and routing ──────────────────────────────────────────────────────────────── */

async function refresh() {
  state.runs = await json("/api/runs").catch(() => state.runs);
}

function render() {
  stop();
  const hash = decodeURIComponent(location.hash || "");
  if (hash.startsWith("#r/")) return detail(hash.slice(3));
  return hash === "#new" ? launch() : list();
}

async function route() {
  stop();
  await refresh();
  render();
}

async function boot() {
  document.title = "ADII — Is it broken?";
  [state.launch, state.incidents] = await Promise.all([
    json("/api/launch").catch(() => ({ enabled: false })),
    json("/api/incidents").catch(() => [])]);
  window.addEventListener("hashchange", route);
  await route();
}

boot();
