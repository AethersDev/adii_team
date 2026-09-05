/* ADII demonstration layer.
 *
 * ONE render function for all four outcomes. There is deliberately no renderRepairDemo(),
 * renderEscalateDemo(), or similar: the fixture changes, the renderer does not. That is
 * what makes this a demo of the real thing rather than four mockups — when the
 * fixture backend is swapped for the real ADII backend, this page should not need
 * redesigning, only re-pointing.
 *
 * Schema: contracts/demo/v0. It demonstrates information flow. It is NOT frozen.
 */
const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const json = (o) => esc(JSON.stringify(o, null, 2));

const GLOSS = {
  REPAIR: "A specific fault exists and the evidence justifies a specific fix.",
  NO_REPAIR: "The pipeline is sound. The metric moved because the business moved.",
  ESCALATE: "The available evidence cannot justify either call. The run completed.",
};

let RUN = null;
let TAB = "run";

/* ── boot ───────────────────────────────────────────────────────────── */
(async function boot() {
  const runs = await (await fetch("/api/runs")).json();
  runs.forEach((r, i) => {
    const chip = el("button", "runchip");
    chip.setAttribute("role", "tab");
    chip.dataset.slug = r.slug;
    chip.innerHTML =
      `<span class="dot" style="background:var(--${r.disposition.toLowerCase().replace("_", "")})"></span>` +
      `${r.disposition}${r.validation ? " · " + r.validation : ""}`;
    chip.onclick = () => select(r.slug);
    $("runs").append(chip);
    if (i === 0) chip.setAttribute("aria-selected", "true");
  });
  $("tab-run").onclick = () => setTab("run");
  $("tab-eval").onclick = () => setTab("eval");
  $("theme").onclick = () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  };
  await select(runs[0].slug);
})();

async function select(slug) {
  RUN = await (await fetch(`/api/runs/${slug}`)).json();
  document.querySelectorAll(".runchip").forEach((c) =>
    c.setAttribute("aria-selected", String(c.dataset.slug === slug)));
  render(RUN);
}

function setTab(tab) {
  TAB = tab;
  $("tab-run").setAttribute("aria-selected", String(tab === "run"));
  $("tab-eval").setAttribute("aria-selected", String(tab === "eval"));
  render(RUN);
}

/* ── the single renderer ────────────────────────────────────────────── */
function render(run) {
  renderRail(run);
  $("view").replaceChildren(...(TAB === "run" ? runRecord(run) : evaluationView(run)));
  $("foot").innerHTML =
    `Fixture data — no model, no database, no agent loop ran to produce this. ` +
    `Schema <code>${esc(run.schema)}</code>: it demonstrates information flow and is not frozen. ` +
    `Production contracts may change during M1 integration.`;
  window.scrollTo({ top: 0 });
}

/* the trace rail: explorable, never dominant */
function renderRail(run) {
  const list = $("steps");
  list.replaceChildren(...run.trace.map((s) => {
    const li = el("li");
    li.id = `step-${s.id}`;
    const head = el("button", null,
      `<span class="n">${String(s.n).padStart(2, "0")}</span>` +
      `<span>${esc(s.tool)}</span><span class="ok">${s.status === "OK" ? "✓" : s.status}</span>`);
    head.onclick = () => li.classList.toggle("open");
    li.append(head, el("div", "detail",
      `<div class="eyebrow">Request</div><pre>${json(s.request)}</pre>` +
      `<div class="eyebrow">Observation</div><pre>${json(s.observation)}</pre>`));
    return li;
  }));
}

function openStep(id) {
  const li = $(`step-${id}`);
  if (!li) return;
  li.classList.add("open");
  li.scrollIntoView({ behavior: "smooth", block: "center" });
  li.classList.remove("flash");
  void li.offsetWidth;                     // restart the animation
  li.classList.add("flash");
}

/* ── run record — only what the runtime could legitimately know ──────── */
function runRecord(run) {
  const out = [];
  const d = run.decision;

  const incident = el("section");
  incident.append(
    el("div", "eyebrow", "Incident"),
    el("h1", null, esc(run.incident.title)),
    el("p", "lede", esc(run.incident.alert)));
  out.push(incident);

  const disp = el("section");
  disp.append(el("div", "eyebrow", "Disposition"));
  disp.append(el("div", `disposition d-${d.disposition}`,
    `<span class="name">${d.disposition}</span><span class="gloss">${GLOSS[d.disposition]}</span>`));
  disp.append(el("div", "posture",
    `INVESTIGATION POSTURE — ${esc(run.posture.label)}`));
  out.push(disp);

  const claim = el("section");
  claim.append(el("div", "eyebrow", "Claim"), el("p", "claim", esc(d.claim)));
  if (d.root_cause_id)
    claim.append(el("div", "posture", `root_cause_id — ${esc(d.root_cause_id)}`));
  const cites = el("div", "cites");
  d.evidence.forEach((id) => {
    const b = el("button", "cite", `[${id}]`);
    b.onclick = () => openStep(id);          // citation → the actual observation
    cites.append(b);
  });
  claim.append(el("div", "eyebrow", "Supporting evidence"), cites);
  const ul = el("ul", "evlist");
  d.evidence.forEach((id) => {
    const s = run.trace.find((t) => t.id === id);
    if (!s) return;
    const li = el("li", null,
      `<span class="tag">[${id}]</span><span class="what">${esc(s.tool)} — ` +
      `${esc(summarise(s.observation))}</span>`);
    li.style.cursor = "pointer";
    li.onclick = () => openStep(id);
    ul.append(li);
  });
  claim.append(ul);
  out.push(claim);

  if (d.missing_evidence) {
    const miss = el("section");
    miss.append(el("div", "eyebrow", "Decisive evidence that does not exist"));
    miss.append(el("div", "missing", `<p>${esc(d.missing_evidence)}</p>`));
    out.push(miss);
  }

  if (run.candidate_repair) {
    const cr = run.candidate_repair;
    const rep = el("section");
    rep.append(el("div", "eyebrow", "Candidate repair"));
    rep.append(el("div", "diff",
      `<div class="path">${esc(cr.path)} · ${esc(cr.repair_id)}</div>` +
      `<div class="row del">- ${esc(cr.removed)}</div>` +
      `<div class="row add">+ ${esc(cr.added)}</div>`));
    if (run.mechanism) {
      const m = run.mechanism;
      const side = (label, rows) =>
        `<div class="mside"><div class="msidelabel">${label}</div>` +
        rows.map(([k, v]) => `<div class="mrow"><span>${esc(k)}</span><b>${esc(v)}</b></div>`)
          .join("") + `</div>`;
      rep.append(el("div", "mech2",
        side("Before", m.before) + side("After", m.after)));
    }
    rep.append(el("div", "selfcheck",
      `Agent-visible checks: <b>${esc(cr.agent_visible_checks)}</b>. ${esc(cr.agent_check_note)}`));
    out.push(rep);
  }

  const val = el("section");
  val.append(el("div", "eyebrow", "Independent validation — a separate authority"));
  if (run.validation) {
    const v = run.validation;
    const box = el("div", "authority",
      `<div class="verdict v-${v.verdict}">${v.verdict}</div>` +
      `<div class="selfcheck" style="margin-top:.5rem">${esc(v.method)}</div>`);
    const f = el("ul", "findings");
    v.findings.forEach((x) => f.append(el("li", null, esc(x))));
    box.append(f);
    val.append(box);
  } else {
    val.append(el("p", "na", "No repair was proposed, so there is nothing to validate."));
  }
  out.push(val);

  out.push(provenance(run));
  return out;
}

function summarise(o) {
  if (o && o.note) return o.note;
  if (o && o.declared_schema) return `declared schema ${JSON.stringify(o.declared_schema.version || "")}`;
  if (o && o.contents) return String(o.contents).split("\n").find((l) => l.includes("/")) || "transform source";
  if (o && o.lines) return o.lines[0];
  if (o && o.changes && o.changes.length) return o.changes[0].change;
  if (o && o.rows) return `${o.rows.length} row(s)`;
  return Object.keys(o || {}).slice(0, 3).join(", ");
}

/* ── evaluation — explicitly walled off ─────────────────────────────── */
function evaluationView(run) {
  const e = run.evaluation;
  const out = [el("section")];
  out[0].append(
    el("div", "eyebrow", "Evaluation authority"),
    el("h1", null, "Was what happened actually correct?"),
    el("div", "wall",
      "None of this was available to the investigator. It comes from the frozen answer " +
      "key, which lives in a separate repository and is never part of agent context. " +
      "This is the only view in the product where right and wrong are colours."));
  const t = el("table", "scorecard");
  const mark = (v) => ["PASS", "CORRECT", "ACCEPTED"].includes(v) ? "mark-pass"
    : ["FAIL", "INCORRECT", "REJECTED"].includes(v) ? "mark-fail" : "";
  [["Expected disposition", e.expected_disposition],
   ["Observed disposition", e.observed_disposition],
   ["Root cause", e.root_cause],
   ["Repair", e.repair],
   ["Full incident success", e.full_incident_success]]
    .forEach(([k, v]) => t.append(el("tr", null,
      `<td>${k}</td><td class="${mark(v)}">${esc(v)}</td>`)));
  out[0].append(t);
  out[0].append(el("p", "lede", esc(e.note)));
  out.push(provenance(run));
  return out;
}

function provenance(run) {
  const d = el("details", "prov");
  d.append(el("summary", null, "Provenance"));
  const g = el("div", "provgrid");
  Object.entries(run.provenance).forEach(([k, v]) =>
    g.append(el("div", null, `<span class="k">${esc(k)}</span><span class="v">${esc(v)}</span>`)));
  d.append(g);
  return d;
}
