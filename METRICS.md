# Store Coach — Metric definitions

Every number Store Coach shows comes from one of the formulas below. A run "as of D"
is the morning of day D and sees only data dated **≤ D−1**. The latest run is
**Mon 2 Nov 2026** (data ends Sat 31 Oct). Column names are exactly as in `data/raw/*.csv`.

## 1. Basic rules

- **Item** = a `bill_lines` row whose `items.is_packaging = 0`. Packaging rows (₹0) are never counted.
- **Revenue** = Σ `qty × selling_price` (₹, GST included). **MRP value** = Σ `qty × mrp`.
- **Placeholder customer** = a `customer_id` with ≥ 50 bills (only `C99999999`). Left out of all customer metrics.
- **Bad footfall day** = a `footfall_daily` row with `footfall` ≤ 0, or more bills than `footfall` (PAT-03, 5–16 Oct 2026). Left out of conversion and revenue-per-walk-in for that store: the day's bills and walk-ins are both dropped, since bills ÷ a broken camera count is meaningless. Metrics that don't use footfall (IPB, ATV, discount) keep these days, because the bills are real. Shown in the Data issues panel.
- **Established store** = `stores.opened_on` ≤ D−90. Newer stores (BLR-05, opened 10 Oct 2026) get no alerts and are not used as peers.
- **Active salesperson** = has a bill, or a `roster_daily.status = "Present"` day, in D−14 … D−1. Only active people are named on cards, as role models or as low performers.
- **Peers.** Store → other established stores in the **same state**. Salesperson → the other salespeople with bills in the **same store** over the same window. City → **all other cities**.
- **Bill credit** goes to `bills.salesperson_id`.

## 2. Windows (as of D)

| Window | Days | For D = 2 Nov 2026 | Used for |
|---|---|---|---|
| Recent | D−56 … D−1 | 7 Sep – 1 Nov | Store metrics |
| Baseline | D−182 … D−57 | 3 May – 6 Sep | Store "normal" level |
| Salesperson | D−91 … D−1 | 3 Aug – 1 Nov | Add-ons, discount, category share |
| Shifts | D−28 … D−1 | 5 Oct – 1 Nov | Off-rate (baseline as above) |
| Activity | D−14 … D−1 | 19 Oct – 1 Nov | Leaver, active |
| Year ago | Recent − 364 days | 8 Sep – 2 Nov 2025 | City slowdown (same weekdays) |
| Repeat cohort | first bills D−540 … D−121 | 10 May 2025 – 4 Jul 2026 | Repeat (repeats counted up to D−1) |
| Follow-up | D0 … D0+6 | — | 7 days after an alert sent on D0 |

## 3. Metrics

| Metric | Formula |
|---|---|
| Conversion | bills ÷ `footfall`, good days only (Σ over the window, not an average of days) |
| Peer-relative conversion | **expected** = (store ÷ peers in Baseline) × peers in Recent. Gap = expected − actual. Festivals and seasons hit the store and its peers on the same days, so they cancel. |
| Busy-day conversion | The same, using only Saturdays and Sundays |
| Staff on floor | number of `salesperson_id` with `status = "Present"` per store-day (roster covers 1 May – 31 Oct 2026 only) |
| Items per bill (IPB) | items ÷ bills. Expected = store Baseline IPB × (peer Recent ÷ peer Baseline) |
| Average bill value (ATV) | revenue ÷ bills |
| Revenue per walk-in (RPF) | revenue ÷ `footfall`, good days only (= conversion × ATV) |
| Discount % | Σ `qty × (mrp − selling_price)` ÷ Σ `qty × mrp`, items only |
| Sherwani add-on rate | bills with a `Sherwani` item that also have a `Safa`, `Mojari` or `Mala` item ÷ bills with a `Sherwani` item |
| Jacket add-on rate | bills with a `Kurta Set` item that also have a `Jacket` item ÷ bills with a `Kurta Set` item |
| Category share | Σ `qty` in a `category` ÷ Σ item `qty`, compared with same-store peers |
| Repeat rate | Customer = `customer_id` (hashed mobile number). Cohort = customers whose first bill since 1 Nov 2024 falls in the Repeat cohort window. **Repeat** = any later bill at **any Manyavar store** 30 or more days after the first bill, up to D−1 (D3). Credit goes to the store and salesperson of the first bill. |
| Off-rate | roster days with `status = "Off"` ÷ roster days, per salesperson |

## 4. When something counts as an issue

Significance is a z-score. For rates (conversion, add-on, category share, repeat): z = (k − n·p₀) ÷ √(n·p₀(1−p₀)). For averages (IPB, RPF; non-buyers count as ₹0 in RPF): z = (mean − expected) ÷ (sd ÷ √n).
**Thresholds:** z ≤ **−2.5** on its own. z ≤ **−2.0** when a cause has been found (a leaver or missing shifts in that store), and for cities (only 6 of them). Role model: z ≥ **+2.5**.
Families walk in together, so walk-ins are not fully independent. The z-score is used to screen issues; it is not an exact p-value.

> **In plain words.** Numbers wobble by luck. z = (what happened − what we expected from fair peers) ÷ (how much it normally wobbles by luck).
> z = 0 means as expected. z = −2.5 means the shortfall is 2.5 times the normal wobble, which luck alone produces only about 1 time in 160.
> *Example:* SP1128 had 6 sherwani bills. Peers add a safa/mojari/mala 83% of the time, so we expect ≈ 5 add-ons. He made 0, with a normal wobble of ≈ 1, so z ≈ −5.5: a habit, not luck.
> **Why the bar is strict:** we run hundreds of checks (≈ 150 salespeople × several behaviours, plus 20 stores). At −2.0 luck would raise about a dozen false alarms; at −2.5, a handful. Those few then rank low on ₹ and fall outside the 5 issues a week.
> **Why minimum samples:** 0 out of 2 also looks like 0%, but with 2 bills that easily happens by chance.
> **Why a minimum size too:** with lots of data, even a tiny gap can be "certain". The ≥ 10% / ≤ ½ rules keep trivial gaps away from AMs.
> **Why −2.0 when a cause is found:** a hard fact, such as Imran C. not billing since 13 Sep, is separate evidence, so the store's drop needs less proof on its own.

| Issue (lever) | Raised when | Min. sample |
|---|---|---|
| Leaver (More bills) | ≥ 8% of the store's Baseline bills; last bill in D−90 … D−15; no bill and no "Present" day in D−14 … D−1. Wording: "hasn't billed since ⟨date⟩". | — |
| Missing shifts (More bills) | Off-rate ≥ 35% **and** ≥ 15 points above own Baseline off-rate | ≥ 20 roster days |
| Conversion drop / busy-day drop (More bills) | Peer-relative gap with z beyond the threshold, **and** actual ≥ 10% below expected | ≥ 28 good days, ≥ 100 bills; busy days ≥ 300 walk-ins |
| City slowdown (More bills) | City RPF vs all other cities, Recent vs Year ago: z ≤ −2.0, **and** conversion, IPB and ATV are all below expected. Store alerts for conversion, IPB or ATV in that city are folded into this one issue. | ≥ 100 bills |
| IPB drop (Bigger baskets) | Store IPB below expected, z beyond the threshold | ≥ 100 bills |
| Missing add-on (Bigger baskets) | Salesperson rate ≤ ½ of the peer rate, z ≤ −2.5 | ≥ 5 sherwani bills / ≥ 20 kurta-set bills |
| Category avoidance (Bigger baskets) | Category qty ≤ ½ of expected (n·p₀), z ≤ −2.5 | expected ≥ 5 units |
| High discount (Bigger baskets) | Discount % ≥ 2× peers **and** ≥ 2 points above peers | ≥ 30 bills |
| Low repeat / role model (More repeat) | z ≤ −2.5 / z ≥ +2.5 vs same-store peers | ≥ 50 cohort customers |

A leaver or missing shifts with no significant store gap is not sent to the AM (₹0; the site shows it as "watch").

## 5. ₹ at stake per week (lost sales, revenue incl. GST)

Weekly volumes are window totals ÷ (days in window ÷ 7): 8 weeks for Recent, 13 for Salesperson, 60 for the Repeat cohort.

| Issue | ₹ / week |
|---|---|
| Conversion drop (incl. leaver / missing-shift cause) | (expected − actual conversion) × weekly good-day footfall × store ATV |
| Busy-day drop | (expected − actual Sat/Sun conversion) × weekly Sat+Sun footfall × store ATV |
| IPB drop | (expected − actual IPB) × weekly bills × store avg item price (revenue ÷ items) |
| City slowdown | (expected − actual RPF) × weekly city footfall |
| Missing add-on | (peer − own rate) × own weekly sherwani (or kurta-set) bills × store avg add-on ₹ per add-on bill |
| Category avoidance | (expected − actual qty) per week × store avg `selling_price` of that category |
| High discount | (own − peer discount %) × own weekly MRP value |
| Low repeat | (peer − own repeat rate) × own new customers per week × store avg revenue of a repeat customer's later bills |

**Merging:** issues for the same store and lever become one issue, carrying the named cause. The merged ₹ is the **largest** gap, never the sum. AMs see issues ranked by ₹/week; ties go to the stronger |z|.

## 6. Follow-up

For an issue sent on D0, re-measure the same metric over D0 … D0+6 and compare the gap with the gap at the time of the alert. **Better**: gap ≤ 75% of the alert gap. **Worse**: gap ≥ 125%. Otherwise **no change**. If fewer than ¼ of the minimum sample came in, the result is "too few bills to tell".

## 7. Check values (as of 2 Nov 2026, from rough pandas checks — Step 3 confirms them)

| Check | Value |
|---|---|
| BLR-03 conversion, Recent | 10.5% vs expected 12.4%, z −3.16, ≈ ₹69k/wk. Busy days 8.1% vs 12.1%, z −4.16 |
| BLR-03 off-rate (SP1141 / SP1142) | 11/27 = 41% vs 21% Baseline / 12/27 = 44% vs 21% |
| LKO-02 conversion, Recent | 10.7% vs expected 12.1%, z −2.17, ≈ ₹45k/wk. IPB 1.82 vs 1.97, z −2.18. Leaver SP1018: 21.7% of Baseline bills, last bill 13 Sep |
| Mysuru vs company, Recent vs Year ago | RPF −18.5% (z −2.45); conversion −5%, IPB −5%, ATV −14% |
| PAT-01 discount (Salesperson window) | SP1064 7.11%, SP1065 6.04% vs peers ≈ 1.9–2.0% |
| Add-ons | SP1128 sherwani 0/6 vs peers 83% (z −5.5); SP1083 sherwani 0/5 vs 67%, jacket 2/57 vs 18% (z −2.9) |
| Repeat | SP1110 44/427 = 10.3% vs peers 4.2% (z +6.3); low: SP1114 −3.3, SP1072 −3.3, SP1120 −2.6 |

**Changes from the Step 0 numbers (KNOWLEDGE_LOG §3):**
- Recent is 56 days, not 28. A 10% conversion drop in 28 days is only z ≈ −1.6, too weak to detect, and 56 days also makes Recent run straight on from Baseline.
- Repeat rates are lower (overall 4.0% vs 7.3%). The cohort now ends at D−121 and needs about 6 months of history before it, so recent first-time buyers have had less time to come back. A fixed 30–120-day window gave only 1.2% (the median gap before a repeat is 166 days), so it was dropped.
- Discounts are compared with peers excluding the salesperson, over 3 Aug – 1 Nov.
- City slowdown is compared year-over-year against the rest of the company. Each state has only two cities, so state peers just mirror each other, and Mysuru's decline started before the Baseline window.
