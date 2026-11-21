# Knowledge Log — Store Coach

The single place for facts, decisions and clarifications. Every chat window reads
this at the start and appends to it at the end. Newest entries at the bottom of
each section. Keep entries short and dated (time is enough — it's all 21 Nov 2026).

---

## 1. Hackathon rules (source: VCH3-1-rules.pdf)

- Public GitHub repo, created after 11:00 am: https://github.com/paramsinghgujral/Cal-AI-Nov-2026 (local `origin`). Link on the hackathon page by 11:30 am.
- Work before 11:00 am doesn't count; git history is checked. Local branch `main` is a fresh orphan branch; `old-main` (has a 20 Nov commit) must never be pushed.
- **No commits or pushes after 4:45 pm. Page locks 4:45 pm.** Our own last push: 4:30 pm.
- Submission (one per team, on calaiclub.com/vch3/live): public repo + working link + demo video + one line on what it does. No submission → no top 10.
- Video: ≤ 2 min; Loom / unlisted YouTube / Drive ("Anyone with the link"); must show the real submitted build working; must open without sign-in. No video → max 10 of 25 Demo & pitch marks.
- Any AI tool allowed on own account. Sarvam credits available if Sarvam email confirmed.
- Pick can be switched until 1:00 pm if the other statement has a slot. Picked: **Manyavar Store Coach**.
- Company pitch 4:45–6:00 pm: separate from grading. Ownership of the build is between team and Manyavar — ask before putting it in a portfolio.

## 2. Brief essentials (source: A_Store_Coach_brief.pdf)

- Goal: every morning, without anyone asking, tell each area manager which stores need attention and why; tell each salesperson one thing to do better today.
- Levers: **More bills** (conversion = bills ÷ footfall), **Bigger baskets** (items per bill), **More repeat** (customer bills again 30+ days after first bill).
- Compare fairly: salesperson vs peers in own store, city, state — not whole country.
- Problems to find — More bills: good salesperson left / keeps missing shifts; too few on floor on busy days; walk-ins steady but fewer buying; whole city slowing (market problem). Bigger baskets: not adding obvious pair (safa/mojari/mala with sherwani; jacket with kurta); avoiding a category the city buys; discounts well above store norm. More repeat: stores/salespeople whose customers don't come back; role models whose customers do — name them.
- Not a problem: normal festival/season swings; regional taste; a number that can't be right → flag as data issue, don't alert the AM.
- Actions: doable today with existing people and stock; no budget, approval or new system; name who, what, when.
- AMs: ≤ 5 issues/week, ranked by ₹ at stake; each names lever, cause, one action. Salespeople: card ≤ 60 words — one behaviour, a peer from the same store, one action for today. Follow up a week later: did the number move?
- Judging: found hidden issues + right cause; numbers spot-checked ("wrong numbers cost more than missing features"); actions doable today; runs on its own.

## 3. Data facts and Step 0 findings

**Data pack:** 20 stores, 6 cities, 3 states; warehouse WH-KOL. Sales 1 Nov 2024 – 31 Oct 2026. "Today" = close of 31 Oct 2026 → first morning to coach = Sun 1 Nov 2026. Synthetic. Raw CSVs in `data/raw/` (gitignored). The three Manyavar zips in the folder are byte-identical.

**Cleanliness checks (all passed):** no duplicate bill IDs, no blank fields in bills, no unknown SKUs/salespeople, no qty ≤ 0 (max 3), no selling_price > mrp, line MRP = item MRP, every bill has non-packaging lines, salesperson's store always = bill's store.

**Data issues found:**
- PAT-03 footfall = 0 on 5–16 Oct 2026 (12 days) while 1–3 bills/day were made → camera fault. Exclude from conversion.
- Customer `C99999999`: 1,833 bills across 19 stores, Nov 2024 – Oct 2026 → placeholder mobile number. Exclude from repeat.
- BLR-05 opened 10 Oct 2026 (22 days of data) → exclude from comparisons; don't alert.
- One footfall spike: BLR-03 2025-10-12 = 304 (festival season, plausible).

**Seasonality:** Diwali 20 Oct 2025 vs 8 Nov 2026 → Oct 2026 revenue/footfall ~35–40% below Oct 2025 in every city. Not a problem. Footfall moves together across all stores.

**Findings (numbers as of data end, 31 Oct 2026):**
- F1 LKO-02 leaver: Imran C. SP1018, joined 2017; 1,250 bills total; ₹24.06 L revenue May–Sep 2026 (138 bills); last bill 13 Sep, last roster day 14 Sep. LKO-02 IPB ~2.1–2.2 → 1.77 (Sep), 1.83 (Oct); conversion 0.141 (Jul) → 0.118 (Sep), 0.106 (Oct).
- F2 BLR-03 shifts/staffing: SP1141 off-rate 0.13–0.27 (May–Aug) → 0.50 (Sep), 0.42 (Oct); SP1142 0.16–0.23 → 0.50, 0.45. Sep–Oct avg present: Fri 7.7, Sat 6.0, Sun 5.9. Weekend conv 0.087 / 0.077 vs weekdays 0.108–0.150. Store conversion ~0.13 → 0.104 (Sep), 0.108 (Oct).
- F3 Mysuru: city conv ~0.09 → 0.075 (Aug–Oct); IPB 1.70 → 1.46 (Oct); ATV ~₹8,800 (late 2025) → ₹6,703 (Oct). Muzaffarpur Oct also dips (IPB 1.48, ATV ₹6,682) — check in Step 4 if it's real or noise.
- F4 PAT-01 discounts (Aug–Oct): Manoj N. SP1064 7.14%, Sanjay K. SP1065 6.17%; store 2.41% incl. them. Monthly: SP1064 ≤ 2% until Jun → 7.3 / 6.3 / 12.2 / 4.9% (Jul–Oct); SP1065 → 6.7 / 8.1 / 7.5 / 3.9%. Milder: Sunil T. SP1122 BLR-01 3.8% vs store 1.4%.
- F5 add-ons: Venkatesh Y. SP1128 BLR-02 sherwani add-on 0/6 since Aug (3/9 May–Oct vs store 76%). Aman B. SP1083 PAT-02 kurta→jacket 12/124 (May–Oct), 3/60 Aug–Oct vs store 15.8%; sherwani add-on 0/7 since Jul.
- F6 repeat (cohort first bill Jan 2025 – Apr 2026, repeat = any later bill 30+ days after first): Karthik J. SP1110 BLR-01 18.4% (n=511) vs store 7.5% (z≈+9.4). Low: Manjunath C. SP1114 BLR-01 3.1% (n=647), Faizan K. SP1072 PAT-01 2.7% (n=639), Suresh V. SP1120 BLR-01 3.7% (n=618). Several high-repeat people have left (Kumar D., Prakash Y., Ashish G.) — only name active ones. Overall repeat 7.3%; most customers bill once.
- Category share (May–Oct): Kurta Set ~54–58%, Jacket ~15%, Mojari ~11–13%, Sherwani 0.8% (Mysuru) – 3.7% (Patna). Low-share candidates: Hemant M. SP1089 PAT-02 (0 sherwani, low safa/mala), Saurabh P. SP1088 PAT-02 (sherwani 11% of city rate).
- Earlier leavers (2025 – Jul 2026) are normal churn; only recent, high-share leavers matter.

## 4. Decisions

| # | Decision | Status | Choice |
|---|---|---|---|
| D1 | Can raw CSVs go in the public repo? | DECIDED (user, 11:50) | Yes — commit the CSVs. `.gitignore` currently ignores `data/`; the step that sets up the daily run must un-ignore `data/raw/*.csv` (zips/PDFs stay ignored). bill_lines.csv is 7.4 MB, fine for GitHub. |
| D2 | Hosting | DEFERRED (user, 11:50) | User wants the simplest option; decide by ~2:30 pm at the latest (a working link and "runs on its own" are both required). Leading candidate: GitHub Pages + daily GitHub Action. |
| D3 | Repeat = same store or any store? | DECIDED (user, 11:50) | Any Manyavar store. Credit goes to the store & salesperson of the customer's first bill. |
| D4 | How AMs receive issues | DECIDED (user, 11:50) | **1 issue per day, Mon–Fri** (= 5/week). The AM visits **one store per day**, so each morning's issue tells the AM which store to visit today and what to do there. No AM issue on Sat/Sun. An issue already sent this week is not re-sent; the next-highest ₹ issue goes instead. Open sub-question Q1 below. |
| D5 | Numbers/causes from code, not LLM | Agreed in plan | Deterministic Python. |
| D6 | Latest "morning" shown | DECIDED (user, 11:58) | Latest run = **Mon 2 Nov 2026**, using data up to Sat 31 Oct (Sun 1 Nov has no data). Demo opens on Monday's AM issue + Monday's cards. Replay every morning 1 Oct → 2 Nov. Salesperson cards: every day the person works, incl. weekends (Q3 default); after the roster ends (31 Oct), "working" = worked in the last 14 days. |
| D7 | Use AI for wording / Hindi-Kannada cards? | DEFERRED (user, 11:50) | Figure out later; not before Step 6. |
| D8 | Planning docs public in repo? | Proposed | Yes (shows process). |
| D9 | Team & way of working | DECIDED (user, 11:50) | Solo. Build sequentially, max 2 chat windows at a time. Focus on the product first, hosting later. |
| D10 | Store recent window | DECIDED (Step 1, user OK 12:24) | 56 days (D−56…D−1), running straight on from the baseline (D−182…D−57). Over 28 days a 10% conversion drop only reaches z ≈ −1.6. Salesperson window = 91 days; off-rate = 28 days. |
| D11 | Significance thresholds | DECIDED (Step 1) | z ≤ −2.5 on its own; z ≤ −2.0 when a cause is found (leaver / missing shifts) and for cities; role model z ≥ +2.5; plus minimum samples and minimum gap size. Discount: ≥ 2× peers and ≥ +2 pp, ≥ 30 bills. |
| D12 | Repeat window | DECIDED (Step 1) | Cohort = first bills D−540…D−121; repeat = any bill at any store ≥ 30 days later, up to D−1. 30–120 days gave only 1.2% (median gap before a repeat is 166 days). |
| D13 | City slowdown comparison | DECIDED (Step 1) | City vs all other cities, recent 56 days vs the same days 364 days earlier. Same-state peers fail: 2 cities per state mirror each other. |
| D14 | Leaver / missing-shift rules | DECIDED (Step 1) | Leaver: last bill must be in D−90…D−15 (keeps July churn out). Missing shifts: off-rate ≥ 35% and ≥ +15 pp above own baseline (with "2×", SP1141 just misses). |

## 5. Clarifications & Q&A log

- 11:10 — User picked Store Coach over Lumino.
- 11:35 — User wants sequential, organised build; each step in its own chat window; plan + this log as files.
- 11:50 — User is solo. Max 2 windows at once. AI wording and hosting deferred; product first. Asking Manyavar contact D1, D3, D4.
- 11:50 — Answers: CSVs can be committed (D1); repeat = any Manyavar store (D3); AM gets 1 issue per weekday and visits 1 store per day (D4).
- 12:00 — **Plan approved by user.** Defaults accepted for Q1–Q3 (see §6). Step 1 starts in a new window.
- 11:58 — Weekly rhythm agreed: AM 1 issue Mon–Fri (Friday's can target the coming weekend; Monday's can react to the past weekend); salespeople get a card every working day incl. Sat/Sun. Latest demo morning = Mon 2 Nov (D6).
- 11:50 — How repeat customers are identified: `bills.customer_id` = the customer's **mobile number, hashed** (not name, not card). Same number → same ID across visits and stores. Limits: a store typing a dummy number creates fake "regulars" (C99999999, 1,833 bills — excluded); a family sharing one phone counts as one customer; a customer giving a different number looks new.
- 12:24 — User asked why some metrics say "good days only" and how the z-scores/thresholds work, assuming no stats background. The plain-language answer is now in METRICS.md (§1 bad footfall day, §4 "In plain words" box). Use the same framing in the README and video. User approved METRICS.md.
- 12:24 — Changed from the Step 0 numbers on purpose (see METRICS.md §7): overall repeat 4.0% (was 7.3%) and Karthik J. 10.3% vs peers 4.2% (was 18.4% vs store 7.5%), because the cohort definition changed; PAT-01 discounts are now vs peers without the salesperson (SP1064 7.11%, SP1065 6.04% vs ~1.9–2.0%). Muzaffarpur's Oct dip is not flagged under the year-over-year city rule (conversion +9.5%), so it's treated as noise.

## 6. Open questions

- ~~D1, D3, D4~~ answered 11:50.
- Q1–Q3 closed 12:00 — user accepted the defaults: Store Coach picks the store the AM visits each day; ₹ at stake = lost **sales** (revenue incl. GST); salesperson cards every working day incl. Sat/Sun.
- Is GitHub CLI (`gh`) installed and logged in? Needed only if Claude should enable Pages; otherwise user enables Pages in the browser (Settings → Pages → Source: GitHub Actions).

## 7. Step log (append one line per finished step)

- 11:40 — Step 0 done: data explored, findings F1–F7 recorded. Drafts `storecoach/load.py`, `storecoach/prep.py` exist (uncommitted, unreviewed).
- 12:25 — Step 1 done: `METRICS.md` (windows, formulas, issue rules, ₹/week per issue type, follow-up, check values as of 2 Nov 2026). Rules checked with scratch pandas: F1–F6 come out; no conversion alert without a cause. Decisions D10–D14. Note for Step 2a: `prep.py` picks placeholders from the full data; METRICS says bills ≤ D−1. Same result (only C99999999), but keep it in mind.
