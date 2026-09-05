/* The orientation layer.
 *
 * Nine short chapters, one idea each, over the same fixtures the inspector uses, projected
 * at a lower density: no trace ids, no SHAs, no scoring vocabulary. Those are one click
 * away in the inspector.
 *
 * The order is the argument. A repair before who approves it; an approved repair before a
 * rejected one; the word "agent" only after the loop has been watched running.
 */
const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

const RUNS = {};
let at = 0;

const CHAPTERS = [
  { label: "What does ADII do?", build: c1 },
  { label: "See a REPAIR", build: () => outcomeChapter("duplicate-accepted", "See a REPAIR") },
  { label: "Who approves the fix?", build: c3 },
  { label: "Why a separate checker?", build: c4 },
  { label: "See NO_REPAIR", build: () => outcomeChapter("no-repair", "Not every alert needs a repair") },
  { label: "See ESCALATE", build: () => outcomeChapter("escalate", "When the evidence cannot answer") },
  { label: "Is this better than guessing?", build: c7 },
  { label: "How does it work?", build: c8 },
  { label: "What are we building?", build: c9 },
];

(async function boot() {
  const list = await (await fetch("/api/runs")).json();
  await Promise.all(list.map(async (r) => { RUNS[r.slug] = await (await fetch(`/api/runs/${r.slug}`)).json(); }));

  $("rail").replaceChildren(...CHAPTERS.map((c, i) => {
    const b = el("button", null, `<span class="num">${i + 1}</span><span>${c.label}</span>`);
    b.onclick = () => go(i);
    return b;
  }));
  $("on").onclick = () => go(at + 1);
  $("back").onclick = () => go(at - 1);
  $("theme").onclick = () => {
    const r = document.documentElement;
    r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark";
  };
  addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") go(at + 1);
    if (e.key === "ArrowLeft") go(at - 1);
  });
  go(0);
})();

function go(i) {
  at = Math.max(0, Math.min(CHAPTERS.length - 1, i));
  $("stage").replaceChildren(...CHAPTERS[at].build());
  [...$("rail").children].forEach((b, k) => b.setAttribute("aria-current", String(k === at)));
  $("back").disabled = at === 0;
  $("on").disabled = at === CHAPTERS.length - 1;
  $("pos").textContent = `${at + 1} of ${CHAPTERS.length}`;
  window.scrollTo({ top: 0 });
}

/* 1 — the whole project in fifteen seconds */
function c1() {
  const three = el("div", "three");
  [["REPAIR", "The data is broken."],
   ["NO_REPAIR", "The data is correct."],
   ["ESCALATE", "We cannot safely tell."]].forEach(([name, what]) =>
    three.append(el("div", `d-${name}`, `<span class="name">${name}</span><span class="what">${what}</span>`)));
  return [
    el("h1", null, "Something looks wrong in the data. What should we do about it?"),
    el("p", "kicker",
      "ADII investigates a data incident and decides whether to fix it, leave it alone, " +
      "or ask a human for help."),
    three,
    el("p", "say",
      "Those three are <b>equally legitimate answers</b>. Notice they look the same as each " +
      "other — that is deliberate. Deciding not to touch the data is a result, not a failure."),
  ];
}

/* 2, 5, 6 — one run, told plainly */
function outcomeChapter(slug, heading) {
  const run = RUNS[slug];
  const intro = run.intro;
  const d = run.decision.disposition;
  const nodes = [
    el("h1", null, heading),
    el("div", "alertbox",
      `<div class="eyebrow">The alert</div><div class="text">${esc(intro.alert)}</div>`),
    el("p", "say", esc(intro.question)),
    el("div", "eyebrow", "What ADII checked"),
  ];
  const ul = el("ul", "checks");
  intro.checks.forEach((n) => {
    const s = run.trace.find((t) => t.n === n);
    if (s) ul.append(el("li", null, `<span class="tick">✓</span><span>${esc(s.plain)}</span>`));
  });
  nodes.push(ul);

  const box = el("div", `outcome d-${d}`,
    `<span class="name">${d}</span><span class="why">${esc(intro.decision)}</span>`);
  if (intro.fix) box.append(el("div", "fixline", `<span class="k">Proposed fix — </span>${esc(intro.fix)}`));
  nodes.push(box);
  if (run.mechanism) nodes.push(mechanism(run.mechanism, { verdict: false }));
  nodes.push(el("p", "takeaway", esc(intro.takeaway)));
  return nodes;
}

/* Before, action, after — the same rows on both sides so the change is the only difference.
 * A screen reading "REPAIR · repair_07 · ACCEPT" tells a viewer nothing: they cannot tell a
 * real fix from a plausible-looking one, which is the distinction the product rests on. */
function mechanism(m, { verdict = true } = {}) {
  const side = (label, rows, cls) =>
    `<div class="side ${cls}"><div class="sidelabel">${label}</div>` +
    rows.map(([k, v]) => `<div class="mrow"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") +
    `</div>`;
  const wrap = el("div", "mech",
    side("Before", m.before, "") +
    `<div class="mechact"><div class="acthead">The change</div>${esc(m.action)}</div>` +
    side("After", m.after, verdict && m.verdict === "REJECT" ? "bad" : "good"));
  const out = el("div", null);
  out.append(el("div", "eyebrow", "What the repair actually changes"), wrap);
  if (verdict) out.append(el("p", "verified",
    `<b>What the independent check verified — </b>${esc(m.verified)}`));
  return out;
}

/* 3 — who approves the fix */
function c3() {
  const run = RUNS["duplicate-accepted"];
  return [
    el("h1", null, "ADII does not approve its own fix"),
    el("p", "say",
      "It proposed removing the repeated rows. That is a <b>suggestion</b>. " +
      "Something else has to check whether it actually works."),
    authorityChain(run, "PASS — the pipeline rebuilds and nothing errors."),
    mechanism(run.mechanism),
    el("p", "takeaway", "Finding the problem and proving the fix are two different jobs."),
  ];
}

/* 4 — why that separation earns its keep */
function c4() {
  const run = RUNS["repair-rejected"];
  return [
    el("h1", null, "Why does the checker have to be separate?"),
    el("p", "say",
      "Same incident. Same evidence. Same diagnosis. Only the <b>repair</b> is different: " +
      "this time ADII decides to halve the day's revenue."),
    authorityChain(run, "PASS — the pipeline rebuilds and nothing errors."),
    mechanism(run.mechanism),
    el("p", "takeaway",
      "Only 11 of the 26 orders were duplicated — not the whole delivery. ADII had no way " +
      "to see that. A correct diagnosis does not make a repair correct."),
  ];
}

/* Two bands, because the point is not the sequence — it is that authority changes hands.
 * Each stage carries its QUESTION, so "candidate test" cannot be misread as a weaker
 * rehearsal of the check that follows. They ask different things:
 *   candidate test        — does this change run safely?
 *   independent validation — does this change produce the correct result? */
function authorityChain(run, candidateAnswer) {
  const cr = run.candidate_repair;
  const v = run.validation;
  const stage = (what, q, ans, ansCls) =>
    `<div class="stage"><div class="what">${what}</div><div class="q">${q}</div>` +
    (ans ? `<div class="ans ${ansCls || ""}">${ans}</div>` : "") + `</div>`;

  const wrap = el("div", "authority-chain");
  wrap.append(el("div", "band investigator",
    `<div class="owner">ADII · the investigator</div>` +
    stage("PROPOSES", "What change would fix this?", `&ldquo;${esc(run.intro.fix)}&rdquo;`) +
    stage("CANDIDATE TEST", "Does this change run safely?", esc(candidateAnswer))));
  wrap.append(el("div", "handover", "↓ &nbsp;authority changes hands&nbsp; ↓"));
  wrap.append(el("div", "band validator",
    `<div class="owner">An independent validator</div>` +
    stage("CORRECTNESS CHECK", "Does this change produce the correct result?",
          `<span class="verdictname ${v.verdict === "ACCEPT" ? "v-ok" : "v-no"}">` +
          `${v.verdict}</span>`, "verdict-line")));
  return wrap;
}

/* 7 — the question the whole project answers. Real measured numbers, not the fixtures. */
function c7() {
  const arms = [
    ["Answer ESCALATE every time", "no model at all", "2 / 6", "dim"],
    ["Read the alert, decide", "same model, NO tools", "6 / 18", "dim"],
    ["Investigate, then decide", "same model, WITH tools", "18 / 18", "win"],
  ];
  const table = el("div", "arms");
  arms.forEach(([what, how, score, cls]) =>
    table.append(el("div", `arm ${cls}`,
      `<div class="armwhat">${what}</div><div class="armhow">${how}</div>` +
      `<div class="armscore">${score}</div>`)));
  return [
    el("h1", null, "How would we know it is better than guessing?"),
    el("p", "say",
      "Suppose ADII gets every incident right. Good system? <b>You cannot tell.</b> Maybe " +
      "the alert text alone was enough and the tools were decoration. A score with nothing " +
      "to compare it against is a number, not evidence."),
    el("p", "say",
      "So the same model is run three ways on the same incidents. Only one thing changes: " +
      "<b>whether it can look at the data.</b>"),
    table,
    el("p", "say",
      "The middle row is the interesting one. Every single one of its eighteen answers was " +
      "ESCALATE — it never discriminated at all. It made <b>zero</b> false repairs, because " +
      "it never repaired anything."),
    el("p", "takeaway",
      "So the claim is not \u201cwe are more accurate\u201d. It is: guessing from the alert was " +
      "maximally safe and maximally useless, and investigation kept the safety while turning " +
      "12 of those 18 blanket abstentions into a correct call."),
  ];
}

/* 8 — only now do we say what an agent is */
function c8() {
  const run = RUNS["duplicate-accepted"];
  const ex = el("div", "exchange");
  const beats = [
    ["ADII", "How many orders are there for that day?"],
    ["tool", `run_sql(...)  →  ${esc(JSON.stringify(run.trace[0].observation.rows))} — 37 rows`],
    ["ADII", "How many of them are unique?"],
    ["tool", `run_sql(...)  →  26 unique order IDs`],
    ["ADII", "Show me the delivery log."],
    ["tool", `read_log(...)  →  the same batch was sent twice`],
    ["ADII", "That is enough. The delivery was duplicated."],
  ];
  beats.forEach(([who, said]) =>
    ex.append(el("div", `turn ${who === "tool" ? "tool" : ""}`,
      `<span class="who">${who === "tool" ? "TOOL" : "ADII"}</span><span class="said">${said}</span>`)));
  return [
    el("h1", null, "What ADII is actually doing"),
    el("p", "say",
      "It cannot open files or query the database directly. It can only <b>ask</b>, through " +
      "a fixed set of functions someone built for it. It reads the answer, then decides what " +
      "to look at next."),
    ex,
    el("p", "takeaway",
      "That loop — ask, observe, decide what to ask next, and eventually stop — is what " +
      "makes this an agent rather than a script."),
  ];
}

/* 9 — and now the letters mean something */
function c9() {
  const tracks = el("ul", "tracks");
  [["A", "makes the AI investigate."],
   ["B", "gives it safe tools to inspect the data."],
   ["C", "checks whether decisions and repairs are actually correct."],
   ["D", "makes every run visible, reproducible and understandable."]].forEach(([l, r]) =>
    tracks.append(el("li", null, `<span class="letter">${l}</span><span class="role">${r}</span>`)));
  const done = el("div", "done");
  const a = el("a", "linkbtn", "Open the technical run inspector →");
  a.href = "/inspector.html";
  done.append(a);
  return [
    el("h1", null, "What we are building"),
    el("div", "arch",
`             INCIDENT
                 │
        ┌────────▼────────┐
        │  A  Investigator│
        └────────┬────────┘
                 │ asks
        ┌────────▼────────┐
        │  B  Data tools  │
        └────────┬────────┘
                 │ evidence
   REPAIR  /  NO_REPAIR  /  ESCALATE
                 │ if REPAIR
        ┌────────▼────────┐
        │  C  Validator   │
        └─────────────────┘

   D makes the whole run visible.`),
    tracks,
    el("p", "takeaway",
      "Everything you just watched is those four pieces. Each of us builds one of them."),
    done,
  ];
}
