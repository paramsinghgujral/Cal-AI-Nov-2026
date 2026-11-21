# Store Coach — Build Plan

Vibe Coders Hackathon Ed. 3 · Sat 21 Nov 2026 · Manyavar "Store Coach" statement.
**Hard stop: no commits/pushes after 4:45 pm. Our last push: 4:30 pm.**

> Each step below is built in its own chat window. Start the window with the
> "Paste this to start" prompt for that step. When a step finishes, update the
> Status table and add anything important to `planning/KNOWLEDGE_LOG.md`.

---

## Status

| Step | What | Planned time | Lane | Depends on | Status |
|---|---|---|---|---|---|
| 0 | Data exploration + findings | 11:00–11:40 | — | — | ✅ Done |
| 1 | Metric definitions (`METRICS.md`) | 11:45–12:05 | A | 0 | ✅ Done 12:25 (windows/thresholds refined — see KNOWLEDGE_LOG D10–D14) |
| 2a | Metrics engine | 12:05–1:05 | A | 1 | ✅ Done 12:45 (all METRICS §7 check values match; 2 s per run) |
| 2b | Site skeleton (runs locally; hosting deferred — D2) | 12:05–12:50 | B | output contract (below) | ✅ Done 12:45 (sample runs 30 Oct / 31 Oct / 2 Nov; contract additions in KNOWLEDGE_LOG D18). Pages + daily Action live 13:25 (D2 decided): https://paramsinghgujral.github.io/Cal-AI-Nov-2026/ |
| 3 | Independent number validation | 1:05–1:30 | C | 2a | ✅ Done 1:46 (`tests/independent.py` re-derives from raw CSVs without `storecoach`; `tests/test_numbers.py` 73 tests pass — every METRICS §7 value + whole store/salesperson/city/category tables match the engine; D23) |
| 4 | Issue detectors | 1:05–2:05 | A | 2a | ✅ Done 1:15 (F1–F7 + false-alarm checks 10/10 on 2 Nov; all 32 replay mornings run; D19–D22) |
| 5 | Outputs: AM briefs, cards, follow-ups → JSON | 2:05–2:45 | A | 4 | ⬜ |
| 6 | Final site + hosting + daily run (decide D2 by 2:30) | 2:45–3:20 | B | 2b, 5 | ⬜ |
| 7 | End-to-end check, README, video, submit | 3:20–4:30 | — | all | ⬜ |

Lanes A, B and C can run in parallel chat windows (see "Parallel work" at the bottom).

---

## 1. What we are building

**Store Coach**: a pipeline that runs on its own every morning, reads data up to
last night, and publishes a website with:

1. **Area manager brief** — **one issue per weekday (Mon–Fri) = 5 per week** (D4).
   The AM visits one store per day, so each morning's issue says *which store to
   visit today* and what to do there. Pick = highest ₹ at stake among issues not
   already sent this week. No AM issue on Sat/Sun. Each issue: lever (More bills /
   Bigger baskets / More repeat), cause, ONE action naming who, what and when,
   plus the evidence numbers. The site also shows the week so far (Mon → today).
2. **Salesperson cards** — ≤ 60 words: one behaviour, one peer from the *same store*,
   one action for *today*.
3. **Follow-up** — for each issue raised a week ago: did the number move? Say so.
4. **Data issues panel** — things that look wrong in the data. Never sent to AMs.
5. **Role models** — salespeople whose customers come back (or who attach well), named.

Delivery: static site on **GitHub Pages**, rebuilt by a **GitHub Action on a daily
cron** (≈ 6:00 am IST). A date picker replays every morning from 1 Oct to 2 Nov
2026, so judges can see daily runs and follow-ups. The data ends 31 Oct 2026, so
the "latest morning" is **Mon 2 Nov 2026** (D6; Sun 1 Nov has no data).

Numbers and causes come from deterministic Python. AI wording/translation only if
time is left after Step 6 (decision D7).

## 2. How we are judged (from the Manyavar brief) → how we answer

| Judge says | Our answer |
|---|---|
| "We know what's hidden in the data. We check whether your system found it and named the right cause." | Step 4 must surface all findings in §4 with the right cause. |
| "We spot-check your numbers. Wrong numbers cost more than missing features." | Step 1 fixes definitions; Step 3 re-computes numbers independently; tests in repo. |
| "We check that every action is one a store could carry out today." | Actions use real names, real dates, existing staff/stock. No budget/approval. |
| "We check that it runs on its own." | Daily GitHub Action; nobody asks it anything. |
| Hackathon: Demo & pitch = 25 marks; no video → max 10. | Step 7 video, 2 min max, shows the real build. |

## 3. Architecture

```
data/raw/*.csv  (gitignored; see decision D1)
storecoach/
  load.py       typed loading (IDs stay text)                 [draft exists]
  prep.py       bill-level basket facts, footfall flags,       [draft exists]
                placeholder customers, first-bill per customer
  metrics.py    Step 2a: metrics per store / salesperson / city for any as_of + window
  detect/       Step 4: one module per detector family
    bills.py      leaver, missing shifts, understaffed busy days, conversion drop, city slowdown
    baskets.py    missing add-ons, category avoidance, high discount
    repeat.py     low repeat, role models
    data_issues.py
  coach.py      Step 5: ranking, 5/week cap, action text, cards, follow-up
  render.py     Step 5: writes site/data/*.json
run.py          CLI: python run.py --as-of 2026-11-02 [--replay-from 2026-10-01]
tests/          Step 3: hand-checked numbers as pytest asserts
site/           Step 2b/6: index.html + app.js + style.css reading site/data/*.json
.github/workflows/daily.yml   Step 2b: cron → run.py → deploy Pages
```

### Output contract (lets Step 2b build the site before the engine exists)

`site/data/index.json`
```json
{ "latest": "2026-11-02", "runs": ["2026-10-01", "...", "2026-11-02"], "generated_at": "2026-11-21T06:00:00+05:30" }
```

`site/data/runs/<as_of>.json`
```json
{
  "as_of": "2026-11-02",
  "data_through": "2026-10-31",
  "managers": [{
    "area_manager_id": "AM-01", "name": "Rakesh Srivastava", "city": "Lucknow",
    "stores": ["LKO-01", "LKO-02", "LKO-03", "LKO-04"],
    "visit_today": "LKO-02",            // null on Sat/Sun
    "today_issue_id": "LKO-02:leaver:SP1018",  // null on Sat/Sun
    "week_sent": ["…issue ids sent Mon → today…"],
    "issues": [{   // today's issue + this week's sent issues + next candidates, ranked by ₹
      "id": "LKO-02:leaver:SP1018", "rank": 1,
      "lever": "More bills", "scope": "store | salesperson | city",
      "store_id": "LKO-02", "salesperson_id": "SP1018",
      "title": "Top seller Imran C. has not billed since 13 Sep",
      "cause": "…", "action": { "who": "…", "what": "…", "when": "…" },
      "rupees_at_stake_week": 85000,
      "evidence": [{ "label": "Store conversion, last 28 days", "value": "10.6%", "baseline": "13.0%" }],
      "first_raised": "2026-09-20"
    }],
    "role_models": [{ "salesperson_id": "SP1110", "name": "Karthik J.", "store_id": "BLR-01",
                      "metric": "Repeat rate", "value": "18.4%", "store_value": "7.5%" }],
    "followups": [{ "issue_id": "…", "raised_on": "2026-10-25", "metric": "…",
                    "at_alert": "…", "now": "…", "moved": "better | worse | no change", "note": "…" }]
  }],
  "cards": [{
    "salesperson_id": "SP1083", "name": "Aman B.", "store_id": "PAT-02",
    "lever": "Bigger baskets", "behaviour": "…", "peer": { "salesperson_id": "…", "name": "…" },
    "action": "…", "text": "≤60 words, the whole card", "word_count": 42
  }],
  "data_issues": [{ "type": "camera_zero", "store_id": "PAT-03", "detail": "…", "dates": "2026-10-05 → 2026-10-16", "excluded_from": "conversion" }]
}
```

## 4. What the data hides (Step 0 findings — Step 4 must find these generically)

Full numbers are in `planning/KNOWLEDGE_LOG.md` §3.

| # | Lever | Finding | Right cause |
|---|---|---|---|
| F1 | More bills | LKO-02: top seller **Imran C. (SP1018)** last billed 13 Sep 2026 (≈ ₹24 L since May). Store items/bill and conversion fall after. | A good salesperson has left |
| F2 | More bills | BLR-03: **SP1141, SP1142** off-rate ~20% → ~50% in Sep–Oct; weekend staff ~6 vs ~7.7 Fri; weekend conversion ~8% vs 11–15% weekdays; store conversion ~13% → ~10.5%. | Missing shifts → too few on the floor on busy days |
| F3 | More bills | **Mysuru** (both stores): conversion, items/bill and bill value all falling together. | Market problem, not one store |
| F4 | Bigger baskets | PAT-01: **Manoj N. (SP1064)** 7.1%, **Sanjay K. (SP1065)** 6.2% discount vs store ~1–1.5%, jump from Jul 2026. | Discounts well above store norm |
| F5 | Bigger baskets | **Venkatesh Y. (SP1128, BLR-02)** 0 add-ons on sherwanis since Aug; **Aman B. (SP1083, PAT-02)** ~5% kurta→jacket vs store 16%, 0/7 sherwani add-ons since Jul. | Not adding the obvious pair |
| F6 | More repeat | Role model **Karthik J. (SP1110, BLR-01)** 18.4% repeat vs store 7.5%. Low: **Manjunath C. (SP1114)**, **Suresh V. (SP1120)** BLR-01; **Faizan K. (SP1072)** PAT-01. | Name role models; low-repeat salespeople |
| F7 | Data issue | PAT-03 footfall = 0 on 5–16 Oct with bills; customer **C99999999** has 1,833 bills (placeholder); **BLR-05** opened 10 Oct 2026. | Flag, don't alert |

Possible extras to check in Step 4 (not confirmed): category avoidance (e.g. Hemant M. SP1089 PAT-02 sells 0 sherwani), Sunil T. SP1122 BLR-01 rising discount, Muzaffarpur Oct dip.
**Not problems:** Oct 2026 < Oct 2025 everywhere (Diwali 20 Oct 2025 vs 8 Nov 2026); Mysuru sells few sherwanis (regional taste).

## 5. Watch-outs (apply in every step)

- Packaging rows (`is_packaging=1`, Rs 0) never count as items.
- Exclude placeholder customer `C99999999` from repeat/customer metrics.
- Skip "bad" footfall days (0 footfall or bills > footfall) in conversion.
- IDs are text. Dates are YYYY-MM-DD. Money includes GST. Revenue = qty × selling_price.
- `min_display`/stock files are for Stock Mover; we don't need them.
- Roster covers only 1 May – 31 Oct 2026; sales go back to Nov 2024.
- No exit date exists → say "hasn't billed since 13 Sep", never "resigned".
- No hourly data → never invent time slots like "4–8 pm".
- Compare fairly: salesperson vs peers in the same store; store vs same city/state; cancel festival swings by comparing to peers over the same days.
- New store (< 90 days) excluded from comparisons.
- No look-ahead: a run as of D only sees data ≤ D−1.
- Every action: who + what + when, doable today with existing people and stock. No action → no alert.
- Cards ≤ 60 words (enforced by a test). AM: exactly 1 issue per weekday, none on weekends (D4).
- Data CSVs may be committed (D1) — un-ignore `data/raw/*.csv` when setting up the daily run; zips/PDFs stay out.
- Commit at the end of every step. Never commit `data/raw`, zips or PDFs. Last push 4:30 pm.

---

## 6. Steps in detail

### Step 1 — Metric definitions (20 min) · Lane A
**Goal:** one page that fixes every formula, so all later steps agree and judges can audit.
**Deliverable:** `METRICS.md` at repo root.
**Must cover (starting draft — refine, don't invent new scope):**
- Windows: recent = last 28 days (D−28 … D−1); baseline = D−182 … D−57. Follow-up window = the 7 days after an alert.
- Conversion = bills ÷ footfall (good footfall days only). Peer-relative index = store conversion ÷ conversion of other same-state stores over the same days (cancels festivals).
- Items per bill (IPB) = non-packaging qty ÷ bills.
- Average bill value (ATV) = revenue ÷ bills.
- Discount % = Σ qty×(mrp − selling_price) ÷ Σ qty×mrp, non-packaging.
- Add-on rates: sherwani bills with a safa/mojari/mala; kurta-set bills with a jacket.
- Category share = category qty ÷ all non-packaging qty, vs same-store peers.
- Repeat: customer = hashed mobile number (`customer_id`). First bill in cohort window D−365 … D−120; repeat = another bill at **any Manyavar store** (D3) 30–120 days after the first. Attributed to the first bill's store and salesperson. Placeholder excluded.
- Leaver: salesperson with ≥ 8% of store bills in baseline, no bills and no "Present" roster days in the last 14 days.
- Missing shifts: off-rate last 28 days ≥ 35% and ≥ 2× own baseline.
- Significance: binomial/Poisson z ≤ −2.5 (or chosen threshold) + minimum sample sizes.
- ₹ at stake per week for each issue type (gap × volume × value), e.g. conversion: (expected − actual conversion) × weekly footfall × ATV.
**Done when:** user has read it and said OK. Commit "Step 1: metric definitions".

### Step 2a — Metrics engine (60 min) · Lane A
**Goal:** correct numbers for any store/salesperson/city as of any morning.
**Deliverable:** review/finish `storecoach/load.py`, `storecoach/prep.py`; write `storecoach/metrics.py`; `run.py --as-of D` prints a metrics summary.
**Done when:** metrics for as_of 2026-11-02 print in < 30 s and match the Step 0 numbers in KNOWLEDGE_LOG §3 (e.g. PAT-01 Manoj N. Aug–Oct discount ≈ 7.1%, Karthik J. repeat clearly above store). Commit.

### Step 2b — Site skeleton (45 min) · Lane B
> **11:50 update (D2 deferred):** build the site so it opens locally only. Skip the
> GitHub Pages and Action parts here; they move to Step 6, using the simplest
> option the user picks. A working link and a daily auto-run are still required
> for submission, so D2 must be decided by ~2:30 pm.

**Goal (original):** prove the public link and the daily auto-run work *early*.
**Deliverable:** `site/index.html`, `site/app.js`, `site/style.css` rendering a hand-written sample `site/data/runs/2026-11-02.json` that follows the output contract; `.github/workflows/daily.yml` (cron ~00:30 UTC + manual trigger) that runs `python run.py` (or just copies `site/` while the engine isn't ready) and deploys with `actions/deploy-pages`. Pages must use **"GitHub Actions" as source** (user enables in repo Settings → Pages). The Action must NOT commit to the repo (deploy artefact only), so it never breaks the "no commits after 4:45" rule.
**UI:** AM tab (pick AM → up to 5 ranked issue cards with ₹, lever, cause, action, evidence), Salesperson tab (pick store → cards), Follow-ups, Data issues, date picker. Mobile-friendly; AMs read on phones.
**Done when:** public URL loads in an incognito window. Commit.

### Step 3 — Independent validation (25 min) · Lane C
**Goal:** catch wrong numbers before judges do.
**How:** a separate window that does NOT read `metrics.py`. Re-derive 6–8 numbers straight from the CSVs with fresh pandas (e.g. LKO-02 Oct conversion, Manoj N. discount %, Karthik J. repeat %, BLR-03 weekend staffing, SP1018 last bill date, PAT-03 zero-footfall dates, BLR-01 IPB Oct). Write them as `tests/test_numbers.py` asserting the engine matches within tolerance.
**Done when:** `pytest` passes, or mismatches are explained and fixed. Commit.

### Step 4 — Detectors (60 min) · Lane A
**Goal:** find the problems in the brief generically and name the right cause.
**Deliverable:** `storecoach/detect/*.py`; each returns issue dicts (contract fields except rank/action text).
- **More bills:** leaver; missing shifts; understaffed busy days (Sat/Sun, festival/wedding dates); walk-ins steady but fewer buying; city slowdown (all stores in a city fall together vs company → market issue, suppress store-level alerts there).
- **Bigger baskets:** missing add-on pair; avoiding a category the city buys; discount ≥ 2× store-peer norm and ≥ +2 pp.
- **More repeat:** low-repeat salespeople/stores; role models (high repeat).
- **Data issues:** zero/impossible footfall; placeholder customers; new stores; anything that "can't be right".
- Cause merging: a store conversion drop explained by a leaver or missing shifts becomes ONE issue with that cause.
**Done when:** for as_of 2026-11-02 all of F1–F7 come out with the right cause, and a skim of the rest shows no obvious false alarms (e.g. no festival or Mysuru-sherwani alerts, nothing for BLR-05). Commit.

### Step 5 — Outputs (40 min) · Lane A
**Goal:** turn issues into what people actually receive.
**Deliverable:** `storecoach/coach.py`, `storecoach/render.py`; `run.py` writes `site/data/runs/<D>.json` + `index.json`; `--replay-from` writes every morning 1 Oct → 2 Nov.
- Rank by ₹/week. **One issue per AM per weekday, Mon–Fri** (D4): the day's issue = highest-₹ issue not yet sent this week; it sets `visit_today`. Sat/Sun: no AM issue. Work out "sent this week" by replaying Mon → today deterministically (no saved state needed).
- Action text with real names and dates: next Sat/Sun dates, the store's lowest-footfall weekday for moved offs, the festival from `calendar` (Diwali Sun 8 Nov 2026).
- Cards: each active salesperson's biggest gap; peer = best in the same store on that behaviour; ≤ 60 words (test).
- Follow-up: re-run detection as of D−7, re-measure each issue's metric over the 7 days since, say better / worse / no change.
**Done when:** JSON validates against the contract; spot-read 3 AM briefs and 5 cards — every action has who/what/when. Commit.

### Step 6 — Final site (35 min) · Lane B
**Goal:** the site judges and the video see.
**Deliverable:** site reads real JSON; date picker replays mornings; "Generated at … by the daily run" stamp; Action runs the real pipeline; manual run succeeds.
**Done when:** incognito check of the public URL on phone width; Action run is green. Commit.

### Step 7 — Ship (3:20–4:30)
- 3:20–3:35 fresh clone → run → tests → site. README: what it does, how it runs daily, metric definitions link, findings.
- 3:35–4:05 video (≤ 2 min, user records on Loom): problem → AM Monday brief → salesperson card → last week's follow-up → "the Action ran at 6 am, no one asked". Check link opens signed-out.
- 4:05–4:20 submit on calaiclub.com/vch3/live: repo, link, video, one line.
- **4:30 last push.** 4:30–4:45 buffer only.
- 4:45–6:00 pitch to Manyavar (optional; doesn't affect score).

---

## 7. Parallel work

The core (Lane A: 1 → 2a → 4 → 5) is sequential: each step uses the previous one.
Safe parallel lanes:

| Lane | Steps | Why it can run alongside |
|---|---|---|
| A — Engine | 1, 2a, 4, 5 | The critical path. |
| B — Delivery | 2b, then 6 | Builds against the output contract + sample JSON; touches only `site/` and `.github/`. |
| C — Checker | 3 | Should be independent of the engine code anyway; touches only `tests/`. |

Rules for parallel windows:
- At most **2 windows at once** (A + B, then A + C). More is hard to keep track of. *(Confirmed by user, 11:50 — solo, sequential.)*
- Each window edits only its own files (listed in its step). Shared files (`PLAN.md`, `KNOWLEDGE_LOG.md`) — only append, and only at the end of the step.
- Only commit your own files (`git add <paths>`), never `git add -A`. Pull/rebase before pushing.
- If a step needs a change in another lane's files, write it in KNOWLEDGE_LOG "Open questions" instead.

## 8. "Paste this to start" prompts

- **Step 1:** "Read CLAUDE.md, planning/PLAN.md and planning/KNOWLEDGE_LOG.md. Do Step 1 (metric definitions) only. Show me METRICS.md before committing."
- **Step 2a:** "Read CLAUDE.md, planning/PLAN.md, planning/KNOWLEDGE_LOG.md and METRICS.md. Do Step 2a (metrics engine) only."
- **Step 2b:** "Read CLAUDE.md, planning/PLAN.md and planning/KNOWLEDGE_LOG.md. Do Step 2b (site skeleton, GitHub Pages, daily Action) only. Touch only site/ and .github/."
- **Step 3:** "Read CLAUDE.md, planning/PLAN.md, planning/KNOWLEDGE_LOG.md and METRICS.md. Do Step 3 (independent validation). Do NOT read storecoach/metrics.py until your own numbers are computed."
- **Step 4:** "Read CLAUDE.md, planning/PLAN.md, planning/KNOWLEDGE_LOG.md and METRICS.md. Do Step 4 (detectors) only."
- **Step 5:** "Read CLAUDE.md, planning/PLAN.md, planning/KNOWLEDGE_LOG.md and METRICS.md. Do Step 5 (outputs) only."
- **Step 6:** "Read CLAUDE.md, planning/PLAN.md and planning/KNOWLEDGE_LOG.md. Do Step 6 (final site) only."
- **Step 7:** "Read CLAUDE.md, planning/PLAN.md and planning/KNOWLEDGE_LOG.md. Do Step 7: end-to-end check, README, video script. Remind me of the 4:30 push deadline."
