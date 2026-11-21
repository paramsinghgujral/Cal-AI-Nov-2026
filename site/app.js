// Store Coach site: reads data/index.json and data/runs/<as_of>.json (see PLAN.md §3).
// No build step, no libraries. State lives in the URL hash: #d=2026-11-02&t=am&am=AM-01&s=LKO-02
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const view = $("#view");
  const state = { d: null, t: "am", am: null, s: null };
  let index = null;
  let run = null;
  const cache = {};

  // ---------- helpers ----------
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const rupees = (n) => (n == null ? "" : "₹" + Math.round(n).toLocaleString("en-IN"));
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const parseDate = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); };
  const fmtDate = (s, withDay = true) => {
    if (!s) return "";
    const d = parseDate(s);
    return (withDay ? DAYS[d.getUTCDay()] + " " : "") + d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
  };
  const dayName = (s) => DAYS[parseDate(s).getUTCDay()];
  const isWeekend = (s) => [0, 6].includes(parseDate(s).getUTCDay());

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    for (const k of Object.keys(state)) if (p.get(k)) state[k] = p.get(k);
  }
  function writeHash() {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(state)) if (v) p.set(k, v);
    history.replaceState(null, "", "#" + p.toString());
  }

  async function getJSON(url) {
    if (cache[url]) return cache[url];
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(url + " → HTTP " + r.status);
    return (cache[url] = await r.json());
  }

  // ---------- boot ----------
  async function boot() {
    readHash();
    try {
      index = await getJSON("data/index.json");
    } catch (e) {
      view.innerHTML = `<p class="error">Could not load data/index.json (${esc(e.message)}).<br>
        If you opened this file directly, serve it instead: <code>python -m http.server -d site 8000</code>
        and open http://localhost:8000.</p>`;
      return;
    }
    const runs = [...index.runs].sort().reverse();
    if (!state.d || !runs.includes(state.d)) state.d = index.latest || runs[0];
    const picker = $("#run-picker");
    picker.innerHTML = runs.map((r) =>
      `<option value="${esc(r)}">${esc(fmtDate(r))}${r === index.latest ? " (latest)" : ""}</option>`).join("");
    picker.value = state.d;
    picker.addEventListener("change", () => { state.d = picker.value; loadRun(); });

    document.querySelectorAll(".tabs button").forEach((b) =>
      b.addEventListener("click", () => { state.t = b.dataset.tab; render(); }));

    $("#foot").textContent = index.generated_at
      ? `Generated ${index.generated_at.replace("T", " ").slice(0, 16)} IST by the daily run.`
      : "";
    loadRun();
  }

  async function loadRun() {
    view.innerHTML = `<p class="empty">Loading ${esc(fmtDate(state.d))}…</p>`;
    try {
      run = await getJSON(`data/runs/${state.d}.json`);
    } catch (e) {
      view.innerHTML = `<p class="error">No run for ${esc(state.d)} (${esc(e.message)}).</p>`;
      return;
    }
    $("#sample-banner").hidden = !run.sample;
    $("#run-meta").textContent =
      `Brief for ${fmtDate(run.as_of)} · uses data up to ${fmtDate(run.data_through)}`;
    const ams = run.managers.map((m) => m.area_manager_id);
    if (!ams.includes(state.am)) state.am = ams[0] || null;
    render();
  }

  function render() {
    document.querySelectorAll(".tabs button").forEach((b) =>
      b.setAttribute("aria-selected", String(b.dataset.tab === state.t)));
    const fn = { am: renderAM, sp: renderSP, fu: renderFU, di: renderDI }[state.t] || renderAM;
    view.innerHTML = fn();
    view.querySelectorAll("[data-am]").forEach((b) =>
      b.addEventListener("click", () => { state.am = b.dataset.am; render(); }));
    view.querySelectorAll("[data-store]").forEach((b) =>
      b.addEventListener("click", () => { state.s = b.dataset.store; render(); }));
    writeHash();
  }

  // ---------- pieces ----------
  function issueCard(it, opts = {}) {
    const watch = it.level === "watch";
    const cls = ["card", watch ? "watch" : "", opts.today ? "today" : ""].join(" ");
    const where = it.scope === "city" ? "City-wide" : esc(it.store_id) + (it.salesperson_id ? " · " + esc(it.salesperson_id) : "");
    const ev = (it.evidence || []).map((e) =>
      `<tr><td>${esc(e.label)}</td><td class="num">${esc(e.value)}</td><td class="num quiet">${esc(e.baseline ?? "")}</td></tr>`).join("");
    const a = it.action || {};
    return `<article class="${cls}">
      <div class="row">
        ${watch ? `<span class="tag watch">Early signal: check, not proven</span>` : `<span class="tag">Issue${it.rank ? " #" + esc(it.rank) : ""}</span>`}
        <span class="tag plain">${esc(it.lever)}</span>
        <span class="tag plain">${where}</span>
        ${opts.status ? `<span class="tag plain">${esc(opts.status)}</span>` : ""}
        <span class="rupees">${rupees(it.rupees_at_stake_week)}<span class="small"> /week</span></span>
      </div>
      <p class="title">${esc(it.title)}</p>
      <p class="cause"><span class="quiet">Why: </span>${esc(it.cause)}</p>
      ${it.action ? `<div class="action"><dl>
        <dt>Who</dt><dd>${esc(a.who)}</dd>
        <dt>What</dt><dd>${esc(a.what)}</dd>
        <dt>When</dt><dd>${esc(a.when)}</dd></dl></div>` : ""}
      ${ev ? `<table class="ev"><thead><tr><th>Evidence</th><th class="num">Now</th><th class="num">Normal</th></tr></thead><tbody>${ev}</tbody></table>` : ""}
      ${it.first_raised ? `<p class="small">First raised ${esc(fmtDate(it.first_raised))}</p>` : ""}
    </article>`;
  }

  function movedTag(m) {
    const cls = m === "better" ? "good" : m === "worse" ? "bad" : "plain";
    return `<span class="tag ${cls}">${esc(m)}</span>`;
  }

  function followupCard(f, issues) {
    const it = issues.find((i) => i.id === f.issue_id);
    return `<article class="card">
      <div class="row">${movedTag(f.moved)}<span class="tag plain">raised ${esc(fmtDate(f.raised_on))}</span></div>
      <p class="title">${esc(it ? it.title : f.issue_id)}</p>
      <table class="ev"><thead><tr><th>Measure</th><th class="num">At alert</th><th class="num">Now</th></tr></thead>
        <tbody><tr><td>${esc(f.metric)}</td><td class="num">${esc(f.at_alert)}</td><td class="num">${esc(f.now)}</td></tr></tbody></table>
      ${f.note ? `<p class="small">${esc(f.note)}</p>` : ""}
    </article>`;
  }

  // ---------- Area manager tab ----------
  function todayBlock(m) {
    const t = m.today_type || (m.today_issue_id ? "issue" : isWeekend(run.as_of) ? "weekend" : "no_visit");
    const it = m.issues.find((i) => i.id === m.today_issue_id);
    if (t === "weekend") {
      return `<div class="card"><h3>No AM issue today</h3>
        <p class="quiet">${esc(m.today_note || "Weekends are for the stores. Next issue arrives Monday morning.")}</p></div>`;
    }
    if (t === "no_visit") {
      return `<div class="card"><h3>No visit needed today</h3>
        <p class="quiet">${esc(m.today_note || "Every issue this week has been sent and nothing new crossed the line.")}</p></div>`;
    }
    const label = { issue: "Today's issue", followup: "Follow-up", watch: "Early-signal check" }[t] || "Today";
    let extra = "";
    if (t === "followup") {
      const f = (m.followups || []).find((x) => x.issue_id === m.today_issue_id);
      if (f) extra = followupCard(f, m.issues);
    }
    return `<div class="today-head"><span class="quiet">${label} · visit</span>
        <span class="store">${esc(m.visit_today || "—")}</span></div>
      ${m.today_note ? `<p class="quiet">${esc(m.today_note)}</p>` : ""}
      ${extra}
      ${it ? issueCard(it, { today: true }) : ""}`;
  }

  function weekBlock(m) {
    const byId = Object.fromEntries(m.issues.map((i) => [i.id, i]));
    let rows;
    if (Array.isArray(m.week) && m.week.length) {
      rows = m.week.map((w) => {
        const it = byId[w.issue_id];
        const title = it ? it.title : w.issue_id || "";
        const store = w.store_id && !title.includes(w.store_id) ? `<b>${esc(w.store_id)}</b> ` : "";
        const what = w.type === "no_visit" ? `<span class="quiet">No visit needed</span>`
          : store + esc(title) +
            (w.type === "followup" ? ` <span class="tag plain">follow-up</span>` : "") +
            (w.type === "watch" ? ` <span class="tag watch">early signal</span>` : "");
        return `<li><span class="day">${esc(dayName(w.date))}</span><span>${what}</span></li>`;
      });
    } else {
      rows = (m.week_sent || []).map((id) =>
        `<li><span class="day">·</span><span>${esc(byId[id] ? byId[id].title : id)}</span></li>`);
    }
    if (!rows.length) return "";
    return `<h2>This week so far</h2><div class="card"><ul class="week">${rows.join("")}</ul></div>`;
  }

  function renderAM() {
    if (!run.managers.length) return `<p class="empty">No area managers in this run.</p>`;
    const chips = run.managers.map((m) =>
      `<button class="chip" data-am="${esc(m.area_manager_id)}" aria-pressed="${m.area_manager_id === state.am}">${esc(m.city)}</button>`).join("");
    const m = run.managers.find((x) => x.area_manager_id === state.am) || run.managers[0];
    const sent = new Set(m.week_sent || []);
    const others = m.issues.filter((i) => i.id !== m.today_issue_id);
    const next = others.filter((i) => !sent.has(i.id));
    const issuesNext = next.filter((i) => i.level !== "watch").sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
    const watchNext = next.filter((i) => i.level === "watch");
    const rm = (m.role_models || []).map((r) =>
      `<article class="card keep"><div class="row"><span class="tag good">Role model</span><span class="tag plain">${esc(r.store_id)}</span></div>
        <p class="title">${esc(r.name)} <span class="small">${esc(r.salesperson_id)}</span></p>
        <p>${esc(r.metric)}: <b>${esc(r.value)}</b> <span class="quiet">vs store ${esc(r.store_value)}</span></p></article>`).join("");
    return `<div class="chips">${chips}</div>
      <p class="quiet">${esc(m.name)} · ${esc(m.area_manager_id)} · ${esc((m.stores || []).join(", "))}</p>
      ${todayBlock(m)}
      ${weekBlock(m)}
      ${issuesNext.length ? `<h2>Next in line</h2>${issuesNext.map((i) => issueCard(i, { status: "not sent yet" })).join("")}` : ""}
      ${watchNext.length ? `<h2>Watch list</h2>${watchNext.map((i) => issueCard(i)).join("")}` : ""}
      ${rm ? `<h2>Role models</h2>${rm}` : ""}`;
  }

  // ---------- Salesperson tab ----------
  function renderSP() {
    const cards = run.cards || [];
    if (!cards.length) return `<p class="empty">No salesperson cards in this run.</p>`;
    const stores = [...new Set(cards.map((c) => c.store_id))].sort();
    if (!stores.includes(state.s)) state.s = stores[0];
    const chips = stores.map((s) =>
      `<button class="chip" data-store="${esc(s)}" aria-pressed="${s === state.s}">${esc(s)}</button>`).join("");
    const list = cards.filter((c) => c.store_id === state.s).map((c) => {
      const keep = c.kind === "keep_doing";
      return `<article class="card ${keep ? "keep" : "gap"}">
        <div class="row">
          <span class="tag ${keep ? "good" : ""}">${keep ? "Keep doing this" : "Today's nudge"}</span>
          <span class="tag plain">${esc(c.lever)}</span>
        </div>
        <p class="title">${esc(c.name)} <span class="small">${esc(c.salesperson_id)}</span></p>
        <p class="cardtext">${esc(c.text)}</p>
        <p class="small">${esc(c.word_count)} words${c.peer && c.peer.name ? " · peer: " + esc(c.peer.name) : ""}</p>
      </article>`;
    }).join("");
    return `<div class="chips">${chips}</div>${list}`;
  }

  // ---------- Follow-ups tab ----------
  function renderFU() {
    const blocks = run.managers.filter((m) => (m.followups || []).length).map((m) =>
      `<h2>${esc(m.city)} <span class="small">${esc(m.name)}</span></h2>` +
      m.followups.map((f) => followupCard(f, m.issues)).join(""));
    return blocks.length ? blocks.join("")
      : `<p class="empty">Nothing to follow up this morning. Follow-ups appear 7 days after an issue is sent.</p>`;
  }

  // ---------- Data issues tab ----------
  function renderDI() {
    const list = run.data_issues || [];
    const head = `<p class="quiet">Things in the data that look wrong. These are kept out of the numbers and are never sent to area managers.</p>`;
    if (!list.length) return head + `<p class="empty">No data issues found.</p>`;
    return head + list.map((d) => `<article class="card">
      <div class="row"><span class="tag plain">${esc(d.type)}</span>${d.store_id ? `<span class="tag plain">${esc(d.store_id)}</span>` : ""}</div>
      <p>${esc(d.detail)}</p>
      <p class="small">${d.dates ? esc(d.dates) + " · " : ""}${d.excluded_from ? "left out of " + esc(d.excluded_from) : ""}</p>
    </article>`).join("");
  }

  window.addEventListener("hashchange", () => {
    const before = state.d;
    readHash();
    if (state.d !== before) { $("#run-picker").value = state.d; loadRun(); } else if (run) render();
  });
  boot();
})();
