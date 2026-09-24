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
const state = { launch: { enabled: false }, incidents: [], runs: [],
                side: stored("side", window.innerWidth > 900), still: stored("still", false),
                stepsOpen: stored("stepsOpen", false),
                pick: null, desc: "", files: [], note: "", timer: null, code: null,
                gen: 0, problem: null, asked: {}, detailsOpen: false };

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
  let body;
  try {
    body = await answer.json();
  } catch (notJson) {
    throw new Error("the server's answer was not JSON (" + answer.status + ")");
  }
  if (!answer.ok) throw new Error(body.error || "the server refused: " + answer.status);
  return body;
}

function stop() {
  if (state.timer) clearTimeout(state.timer);
  state.timer = null;
}

/* ── the mark, alive ──────────────────────────────────────────────────────────────────
 * The identity's symbol, drawn from its own geometry (IDENTITY.md, "Geometry"), unchanged in
 * shape: a riser crossing a rule, and support slots below, one of them unfilled. At rest the
 * unfilled slot breathes — evidence not yet in; while ADII investigates the slots rise in
 * turn; it is still when there is an answer, and still for anyone who asks for less motion. */
function mark(mode, size) {
  const rect = (x, y, w, h, cls) => svg("rect", { x, y, width: w, height: h, class: cls || "" });
  return svg("svg", { viewBox: "0 0 32 32", width: size, height: size, role: "img",
                      "aria-label": "ADII", class: "mark mark--" + mode },
    rect(4, 4, 4, 24), rect(4, 12, 24, 4),
    rect(12, 20, 4, 8, "mark__slot mark__slot--1"),
    rect(18, 24, 4, 4, "mark__slot mark__slot--open"),
    rect(24, 20, 4, 8, "mark__slot mark__slot--3"));
}

/* Icons, drawn as strokes: a panel, a plus, a gear, a cross. */
const ICONS = {
  panel: ["M4 5h16v14H4z", "M9 5v14"],
  plus: ["M12 5v14", "M5 12h14"],
  gear: ["M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
         "M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 0 " +
         "0-2 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 " +
         "2.6h4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  clip: ["M20 11.5l-8.2 8.2a5 5 0 0 1-7.1-7.1l8.9-8.9a3.4 3.4 0 0 1 4.8 4.8l-8.9 8.9a1.7 1.7 " +
         "0 0 1-2.4-2.4l8.2-8.2"],
  up: ["M12 19V5", "M6 11l6-6 6 6"],
  down: ["M7 10l5 5 5-5"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
};

function icon(name) {
  return svg("svg", { viewBox: "0 0 24 24", width: 20, height: 20, "aria-hidden": "true",
                      class: "icon" },
    ICONS[name].map((d) => svg("path", { d })));
}

/* ── preferences: kept per browser, never needed for the page to work ─────────────── */

function stored(key, fallback) {
  try {
    const kept = localStorage.getItem("adii." + key);
    return kept === null ? fallback : kept === "true";
  } catch (blocked) { return fallback; }          // storage refused: the default stands
}

function keep(key, value) {
  state[key] = value;
  try { localStorage.setItem("adii." + key, String(value)); }
  catch (blocked) { /* the choice lasts this visit only */ }
}

function toggleSide() {
  keep("side", !state.side);
  render();
}

/* ── the sidebar: past investigations, as a chat app keeps past conversations ──────── */

function newInvestigation() {
  state.pick = null; state.desc = ""; state.files = []; state.note = "";
  if (window.innerWidth <= 900 && state.side) keep("side", false);
  go("#");
}

/* The history: titles and when, never answers — an answer is read by opening it, so the
 * sidebar can stay on show in a room without giving a sample's outcome away. */
function side(current) {
  const rows = state.runs.map((r) => V.row({ ...r, alert: r.alert || asked(r.label) },
                                           Date.now()));
  return el("nav", { class: "side", "aria-label": "Investigations" },
    el("div", { class: "side__top" },
      el("a", { class: "side__brand", href: "#", "aria-label": "ADII, home" },
        el("span", { class: "side__wordmark", role: "img", "aria-label": "ADII" })),
      el("button", { type: "button", class: "icon-btn", "aria-label": "Close sidebar",
                     title: "Close sidebar", onclick: toggleSide }, icon("panel"))),
    el("button", { type: "button", class: "side__new", onclick: newInvestigation },
      icon("plus"), "New investigation"),
    el("h2", { class: "side__h", text: "Recent" }),
    rows.length ? el("ul", { class: "history" }, rows.map((r) => el("li", null,
      el("a", { class: "history__item", href: "#r/" + encodeURIComponent(r.label),
                title: r.error || r.title,
                "aria-current": r.label === current ? "page" : null },
        el("span", { class: "history__title", text: r.title }),
        el("span", { class: "history__when" },
          r.answer === "running" ? el("span", { class: "history__live", text: "Investigating · " })
            : r.error ? el("span", { class: "history__live", text: r.answerLabel + " · " }) : null,
          r.when)))))
      : el("p", { class: "side__empty", text: "Your investigations will appear here." }),
    el("button", { type: "button", class: "side__settings", onclick: openSettings },
      icon("gear"),
      el("span", { class: "side__settings-text" }, el("span", { text: "Settings" }),
        el("span", { class: "side__model", text: state.problem ? "Server unreachable"
          : state.launch.enabled ? String(state.model) : "Read-only" }))));
}

/* Closed, on a desk: a rail of the same three actions, as chat apps keep it. */
function rail() {
  return el("nav", { class: "rail", "aria-label": "Investigations" },
    el("button", { type: "button", class: "icon-btn", "aria-label": "Open sidebar",
                   title: "Open sidebar", onclick: toggleSide }, icon("panel")),
    el("button", { type: "button", class: "icon-btn", "aria-label": "New investigation",
                   title: "New investigation", onclick: newInvestigation }, icon("plus")),
    el("button", { type: "button", class: "icon-btn rail__settings", "aria-label": "Settings",
                   title: "Settings", onclick: openSettings }, icon("gear")));
}

/* ── settings: what the operator set, and what this browser prefers ────────────────── */

function openSettings() {
  const l = state.launch;
  const fact = (term, value) => [el("dt", { text: term }), el("dd", { text: value })];
  const choice = (key, label, hint) => el("label", { class: "pref" },
    el("input", { type: "checkbox", checked: state[key] ? true : null,
                  onchange: (e) => { keep(key, e.target.checked); render(); } }),
    el("span", null, el("span", { class: "pref__label", text: label }),
       el("span", { class: "pref__hint", text: hint })));
  const dialog = el("dialog", { class: "settings", "aria-labelledby": "settings-h",
                                onclose: () => dialog.remove() },
    el("div", { class: "settings__head" },
      el("h2", { id: "settings-h", class: "serif", text: "Settings" }),
      el("button", { type: "button", class: "icon-btn", "aria-label": "Close settings",
                     onclick: () => dialog.close() }, icon("close"))),
    el("section", null,
      el("h3", { class: "settings__h", text: "Investigator" }),
      el("p", { class: "muted", text: "Set by the operator when the server was started; " +
        "every investigation from this page runs with exactly these." }),
      state.problem ? el("p", { class: "problem", text: "Could not reach the server: " +
                                                        state.problem })
        : !l.enabled ? el("p", { text: "Read-only: this server was started without a model, " +
                                       "so the page shows the archive and starts nothing." })
        : el("dl", { class: "facts" },
            fact("Model", String(l.model)),
            (l.models || []).length > 1 ? fact("Models offered", l.models.join(", ")) : null,
            l.reasoning_effort ? fact("Reasoning effort", String(l.reasoning_effort)) : null,
            fact("Provider", l.provider === "openai" ? "Paid, capped" : "Local, nothing spent"),
            l.max_cost_usd !== undefined ? fact("Cost cap per run",
                                                "$" + Number(l.max_cost_usd).toFixed(2)) : null,
            fact("Turns per run", String(l.max_turns)),
            l.max_tool_calls ? fact("Tool calls per run", String(l.max_tool_calls)) : null,
            l.max_wall_clock_seconds ? fact("Time per run",
                                            Math.round(l.max_wall_clock_seconds / 60) + " min")
              : null)),
    el("section", null,
      el("h3", { class: "settings__h", text: "This browser" }),
      choice("stepsOpen", "Show how ADII investigated, opened",
             "The steps behind every answer, unfolded instead of folded away."),
      choice("still", "Keep the mark still",
             "No motion in the logo. Your system's reduced-motion setting is always honoured.")));
  document.body.append(dialog);
  dialog.showModal();
}

function topbar(...items) {
  return el("header", { class: "bar" },
    state.side ? null : el("button", { type: "button", class: "icon-btn bar__open",
                                       "aria-label": "Open sidebar", onclick: toggleSide },
                           icon("panel")),
    items);
}

function page(header, main, current) {
  const root = document.getElementById("app");
  const was = root.querySelector(".pane__scroll");
  const top = was && root.dataset.current === String(current) ? was.scrollTop : 0;
  root.dataset.current = String(current);
  root.replaceChildren(el("div", { class: "app" + (state.side ? " is-side-open" : "") +
                                          (state.still ? " is-still" : "") },
    state.side ? side(current) : rail(),
    state.side ? el("div", { class: "scrim", "aria-hidden": "true", onclick: toggleSide }) : null,
    el("div", { class: "pane" }, header, el("div", { class: "pane__scroll" }, main))));
  root.querySelector(".pane__scroll").scrollTop = top;
  // what the fit test reads: the document's width against the viewport's — reading them
  // lays the page out, so the measurement is of what was just drawn
  const doc = document.documentElement;
  doc.dataset.measured = doc.scrollWidth + "," + doc.clientWidth;
}

function go(hash) {
  if (location.hash === hash || (hash === "#" && !location.hash)) route();
  else location.hash = hash;
}

/* ── home: the question, the composer, the samples ─────────────────────────────────── */

/* The composer, sized as a chat app's: a box that grows with what is typed, files and the
 * model at its foot, one round button to send — and the samples beneath, as suggestions. */
function composer() {
  const models = state.launch.models || [];
  const ready = state.launch.enabled && (state.pick || (state.desc.trim() && state.files.length));
  const read = (list) => Promise.all([...list].map((file) => file.text().then((text) => (
    { name: file.name, text, size: file.size })))).then((files) => {
    state.files = files; state.pick = null; list.value = ""; render();
  });
  const grow = (box) => { box.style.height = "auto";
                          box.style.height = Math.min(box.scrollHeight, 240) + "px"; };
  const text = el("textarea", { id: "composer", rows: 1, class: "composer__text",
    placeholder: "Describe the number that looks wrong, and attach the CSV files behind it",
    oninput: (e) => { state.desc = e.target.value; if (state.pick) state.pick = null;
                      grow(e.target); } }, state.desc);
  requestAnimationFrame(() => grow(text));
  return el("section", { class: "composer", "aria-label": "New investigation" },
    el("label", { for: "composer", class: "visually-hidden", text: "What looks wrong?" }), text,
    state.files.length || state.pick ? el("div", { class: "composer__files" },
      state.files.map((f) => el("span", { class: "chip mono" }, f.name,
        el("span", { class: "chip__size", text: Math.ceil(f.size / 1024) + " KB" }),
        el("button", { type: "button", class: "chip__x", "aria-label": "Remove " + f.name,
                       onclick: () => { state.files = state.files.filter((x) => x !== f);
                                        render(); } }, "×"))),
      state.pick ? el("span", { class: "chip" }, "Sample incident",
        el("button", { type: "button", class: "chip__x", "aria-label": "Clear the sample",
                       onclick: () => { state.pick = null; state.desc = ""; render(); } },
           "×")) : null) : null,
    el("div", { class: "composer__bar" },
      el("label", { for: "attach", class: "icon-btn", title: "Attach CSV files" }, icon("clip"),
         el("span", { class: "visually-hidden", text: "Attach CSV files" })),
      el("input", { id: "attach", type: "file", accept: ".csv", multiple: true,
                    class: "visually-hidden", onchange: (e) => read(e.target.files) }),
      el("span", { class: "composer__spacer" }),
      state.launch.enabled ? modelMenu(models.length ? models : [state.launch.model]) : null,
      el("button", { type: "button", id: "investigate", class: "send",
                     "aria-disabled": ready ? "false" : "true", title: "Investigate",
                     onclick: investigate }, icon("up"),
         el("span", { class: "visually-hidden", text: "Investigate" }))),
    state.note ? el("p", { class: "composer__note", role: "status", text: state.note }) : null);
}

/* The model button, as chat apps keep it: the model this run will use, and a menu of the
 * ones the operator offered — the page picks among them and never beyond. Opened and closed
 * in place, so what the visitor was typing keeps its focus. */
function modelMenu(models) {
  const label = el("span", { class: "model__name", text: String(state.model) });
  const button = el("button", { type: "button", class: "model", "aria-haspopup": "menu",
    "aria-expanded": "false", title: "Choose the model",
    onclick: (e) => { e.stopPropagation(); show(menu.hidden); } }, label, icon("down"));
  const items = models.map((m) => el("button", { type: "button", role: "menuitemradio",
    class: "model__item", "aria-checked": m === state.model ? "true" : "false",
    onclick: () => { state.model = m; label.textContent = m;
                     for (const shown of document.querySelectorAll(".side__model")) {
                       shown.textContent = m; }
                     items.forEach((i) => i.setAttribute("aria-checked",
                       String(i.dataset.model === m)));
                     show(false); button.focus(); }, "data-model": m },
    el("span", { class: "model__item-text" }, el("span", { text: m }),
      m === state.launch.model ? el("span", { class: "model__hint",
                                              text: "The operator’s default" }) : null),
    icon("check")));
  const menu = el("div", { class: "model__menu", role: "menu", "aria-label": "Models" },
    items, el("p", { class: "model__foot", text: models.length > 1
      ? "The models offered on this server."
      : "The only model offered on this server." }));
  menu.hidden = true;
  const away = (e) => { if (e.type === "keydown" ? e.key === "Escape" : !menu.contains(e.target))
    show(false); };
  const show = (open) => {
    menu.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    for (const kind of ["click", "keydown"]) {
      if (open) document.addEventListener(kind, away);
      else document.removeEventListener(kind, away);
    }
    if (open) (items.find((i) => i.getAttribute("aria-checked") === "true") || items[0]).focus();
  };
  return el("div", { class: "model-pick" }, button, menu);
}

function suggestions() {
  const samples = state.incidents.filter((i) => i.sample);
  return samples.length ? el("div", { class: "samples", "aria-label": "Sample incidents" },
    samples.map((s, i) => el("button", { type: "button", class: "pill", title: s.alert,
      "data-incident": s.incident_id,
      "aria-pressed": state.pick === s.incident_id ? "true" : "false",
      onclick: () => pick(s) }, "Sample " + (i + 1)))) : null;
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
  const model = state.model || state.launch.model;
  try {
    const started = state.pick
      ? await json("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ incident: state.pick, model }) })
      : state.desc.trim() && state.files.length
        ? await json("/api/investigations", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ description: state.desc, model,
                                   files: state.files.map((f) => ({ name: f.name, text: f.text })) }) })
        : null;
    if (!started) {
      state.note = "Say what looks wrong and attach the CSV files behind it, or pick a sample.";
      return render();
    }
    state.asked[started.label] = state.desc.trim();
    state.pick = null; state.desc = ""; state.files = []; state.note = "";
    go("#r/" + encodeURIComponent(started.label));
  } catch (why) {
    state.note = why.message;
    render();
  }
}

/* Home is the question and nothing else: no earlier answer is anywhere on it, so a room
 * sees the samples neutral; the history is in the sidebar, titles only. */
function home() {
  page(topbar(), el("main", { class: "home" },
    el("div", { class: "home__hero" },
      el("div", { class: "home__mark" }, mark("idle", 56)),
      el("h1", { class: "home__prompt", text: "What looks wrong in your data?" })),
    composer(), suggestions(),
    el("p", { class: "home__note", text: "ADII decides whether to fix it, leave it alone, or " +
      "escalate it. The AI that proposes a fix can’t approve it." })));
  if (state.runs.some((r) => r.running)) {
    const gen = state.gen;
    state.timer = setTimeout(() => refresh().then(() => gen === state.gen && render()), 2000);
  }
}

/* ── one investigation ─────────────────────────────────────────────────────────────── */

function dayLabel(day) {
  const d = new Date(String(day) + "T00:00:00Z");
  return isNaN(d) ? String(day) : d.toLocaleDateString("en-US", { month: "short", day: "numeric",
                                                                  timeZone: "UTC" });
}

function lineChart(lines, caption) {
  const W = 1200, H = 220, pad = 24;
  lines = lines.filter((l) => l.rows.length);
  if (!lines.length) return null;
  // every point is placed by its day, on the days any line has: a line missing a day is
  // drawn with a gap in time, never stretched against the other
  const days = [...new Set(lines.flatMap((l) => l.rows.map((r) => String(r[0]))))].sort();
  const rows = days.map((d) => [d]);
  const top = Math.max(...lines.flatMap((l) => l.rows.map((r) => Number(r[1])))) * 1.1 || 1;
  const step = (W - 2 * pad) / Math.max(days.length - 1, 1);
  const x = (day) => pad + days.indexOf(String(day)) * step;
  const y = (v) => H - pad - (Number(v) / top) * (H - 2 * pad);
  const drawn = lines.map((l) => {
    const pts = l.rows.map((r) => x(r[0]).toFixed(1) + "," + y(r[1]).toFixed(1));
    const last = l.rows[l.rows.length - 1];
    return [svg("polyline", { points: pts.join(" "), class: "line line--" + l.kind }),
            svg("circle", { cx: x(last[0]).toFixed(1), cy: y(last[1]).toFixed(1), r: 9,
                            class: "dot dot--" + l.kind })];
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
                 "anything was investigated", rows: b.rows }],
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
          "A chart that recovers is not yet a repair: the validator's " +
          "checks below decide.")
      : null,
    el("ul", { class: "checks" }, lines.map((c) => el("li", {
      class: c.held === null ? "is-unmarked" : c.held ? "is-held" : "is-failed" },
      el("span", { class: "checks__mark", "aria-hidden": "true",
                   text: c.held === null ? "" : c.held ? "✓" : "✕" }),
      el("span", { class: "checks__name mono", text: c.name }),
      el("span", { class: "checks__said", text: c.said })))));
}

/* The investigation, turn by turn, folded away like a model's thinking: open for whoever
 * wants it, and it stays as they left it while a live run redraws. */
function steps(looked, summary) {
  return el("details", { class: "looked", open: state.stepsOpen,
                         ontoggle: (e) => { state.stepsOpen = e.target.open; } },
    el("summary", { class: "looked__head" }, summary),
    looked.length ? el("ol", null, looked.map((i) => el("li", null,
      el("span", { class: "looked__title", text: i.title }),
      i.what ? el("span", { class: "mono looked__what", text: i.what }) : null,
      i.status !== "OK" ? el("span", { class: "looked__status", text: i.status }) : null)))
      : el("p", { class: "muted", text: "Starting: the receipt is written before the first " +
                                        "request to the model." }));
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

function crumbs(title) {
  return topbar(el("span", { class: "bar__title", text: title }));
}

/* What a run in progress was asked, before its record can say: the words typed in this tab,
 * or the sample's alert — its label begins with the incident's id. */
function asked(label) {
  const known = state.incidents.find((i) => label.startsWith(i.incident_id + "-"));
  return state.asked[label] || (known ? known.alert : "");
}

/* When a run from the page started: its label carries the moment, to the millisecond, so
 * the clock survives a reload. A run named any other way shows no clock. */
function startedAt(label) {
  const m = /(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})-(\d{3})Z$/.exec(label);
  return m ? Date.UTC(m[1], m[2] - 1, m[3], m[4], m[5], m[6], m[7]) : null;
}

function clock(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? s + "s" : Math.floor(s / 60) + "m " + String(s % 60).padStart(2, "0") + "s";
}

/* One investigation as a conversation: what was asked, on the right; ADII's reply beneath —
 * while it works, a line that says so and counts the seconds, the steps folded inside it;
 * then the answer, plain, and everything behind it one click away. */
function thread(label, asked, reply) {
  page(crumbs(asked), el("main", { class: "thread" },
    el("div", { class: "ask" }, el("p", { class: "ask__text", text: asked })),
    el("section", { class: "reply", "aria-label": "ADII’s answer" }, reply)), label);
}

function answer(record, label, fingerprint, receipt) {
  const v = V.verdict(record), series = V.series(record);
  const all = V.investigated(record);
  const took = clock(Number((record.counters || {}).latency_ms || 0));
  thread(label, record.context.alert, [
    steps(all, [mark("still", 20), el("span", { text: "Investigated for " + took + " · " +
      all.length + (all.length === 1 ? " step" : " steps") })]),
    el("article", { class: "verdict verdict--" + v.key, "aria-labelledby": "verdict-h" },
      el("div", { class: "verdict__band", "aria-hidden": "true" }),
      el("h2", { id: "verdict-h", class: "serif verdict__headline", text: v.headline }),
      el("p", { class: "verdict__lead", text: v.lead }),
      v.summary ? el("div", { class: "verdict__words" },
        el("span", { class: "verdict__who", text: "In the investigator’s words" }),
        el("p", { text: v.summary })) : null,
      v.key === "none" && v.detail ? el("p", { class: "verdict__detail mono",
                                               text: "The record says: " + v.detail }) : null),
    el("details", { class: "more", open: state.detailsOpen,
                    ontoggle: (e) => { state.detailsOpen = e.target.open; } },
      el("summary", { class: "more__toggle" },
        el("span", { class: "more__show", text: "Show details" }),
        el("span", { class: "more__hide", text: "Hide details" }), icon("down")),
      el("div", { class: "more__body" },
        symptom(series),
        v.key === "none" ? null : knows(record, v),
        v.key === "fix" ? [fix(record), rebuild(record, series)]
          : v.key === "none" ? null
          : el("p", { class: "nochange", text: "No change proposed. Nothing was touched." }),
        el("div", { class: "aside" }, slots(record), signoff(record),
           recordPanel(record, label, fingerprint, receipt, v)))),
  ]);
}

function running(label, trace) {
  const events = trace.events || [];
  const pseudo = { trace: events.map((e) => ({ kind: e.kind, payload: e.payload })) };
  const turns = events.filter((e) => e.kind === "model_requested").length;
  const most = state.launch.max_turns;
  const since = startedAt(label);
  const looked = V.investigated(pseudo);
  thread(label, asked(label) || "Your investigation", [
    steps(looked, [mark("working", 20), el("span", { class: "reply__status", role: "status",
      text: "Investigating" + (since ? " · " + clock(Date.now() - since) : "") +
            " · turn " + turns + (most ? " of " + most : "") })]),
  ]);
}

function problem(label, text) {
  page(crumbs(label), el("main", { class: "thread" },
    el("p", { class: "problem", role: "alert", text })), label);
}

/* One run. Every await is followed by a check that this screen is still the one on show:
 * `gen` is the screen's, and a later navigation has moved state.gen on. */
async function detail(label, gen, waited = 0) {
  const base = "/api/runs/" + encodeURIComponent(label);
  const current = () => gen === state.gen;
  let trace;
  try {
    trace = await json(base + "/trace");
  } catch (why) {
    if (!current()) return;
    // a run just started is answered with its label a moment before the runtime reserves
    // its folder: keep asking for a few seconds before calling it unreadable
    if (waited < 10) {
      running(label, { events: [] });
      state.timer = setTimeout(() => detail(label, gen, waited + 1), 1000);
      return;
    }
    return problem(label, "This run could not be read: " + why.message);
  }
  if (!current()) return;
  if (!trace.finished && trace.running === false) {
    return problem(label, "This run did not finish: its trace stopped without a record, so " +
                          "it has no answer. Nothing was changed.");
  }
  if (!trace.finished) {
    running(label, trace);
    state.timer = setTimeout(() => detail(label, gen), 1000);
    return;
  }
  let answerText, record;
  try {
    answerText = await (await fetch(base, { cache: "no-store" })).text();
    record = JSON.parse(answerText);
  } catch (why) {
    return current() && problem(label, "This record could not be read: " + why.message);
  }
  if (!current()) return;
  if (!SCHEMAS.includes(record.schema)) {
    return page(crumbs(label), el("main", { class: "thread" }, el("p", { class: "problem",
      role: "alert", text: "This record is in a shape this page does not read: it declares " +
      record.schema + " and this page reads " + SCHEMAS.join(", ") + ". Nothing is interpreted." })));
  }
  const bytes = new TextEncoder().encode(answerText);
  const fingerprint = crypto.subtle
    ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
        .map((b) => b.toString(16).padStart(2, "0")).join("")
    : "";
  if (current()) answer(record, label, fingerprint, trace.receipt);
}

/* ── boot and routing ──────────────────────────────────────────────────────────────── */

async function refresh() {
  try {
    state.runs = await json("/api/runs");
    state.problem = null;
  } catch (why) {           // the list keeps what it last read, and says it could not reach
    state.problem = why.message;
  }
}

function render() {
  stop();
  const gen = ++state.gen;
  const hash = decodeURIComponent(location.hash || "");
  if (hash.startsWith("#r/")) return detail(hash.slice(3), gen);
  return home();
}

async function route() {
  stop();
  await refresh();
  render();
}

async function boot() {
  document.title = "ADII — Is it broken?";
  try {
    [state.launch, state.incidents] = await Promise.all([json("/api/launch"),
                                                        json("/api/incidents")]);
  } catch (why) {           // said, never shown as "read-only"
    state.problem = why.message;
  }
  state.model = state.launch.model;
  window.addEventListener("hashchange", route);
  await route();
}

boot();
