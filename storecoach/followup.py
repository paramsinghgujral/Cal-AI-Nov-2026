"""Step 5 — follow-up: did the number move? (METRICS §6)

For an issue sent on D0, re-measure the issue's `measure` (set by Step 4) over the
7 days D0 … D0+6 and compare the gap with the gap at the time of the alert:
better ≤ 75% of the alert gap, worse ≥ 125%, otherwise no change. Fewer than ¼ of
the minimum sample → "too little data to tell". Repeat needs 30+ days to show, so a
low-repeat issue is always "too early to tell".

The "expected" value is re-derived for the follow-up week the same way the alert
did it (peer-relative / year-over-year), so festival weeks such as Dussehra
(20 Oct) cancel out instead of looking like progress.
"""
from __future__ import annotations

import math

import pandas as pd

from .detect.common import cat_lc
from .metrics import ESTABLISHED_DAYS, Window

DAY = pd.Timedelta(days=1)

# ¼ of each metric's minimum sample (METRICS §4), rounded up
MIN_FU = {"store_conv": 25, "store_busy_conv": 75, "store_ipb": 25, "city_rpf": 25,
          "sp_sherwani_addon": 2, "sp_jacket_addon": 5, "sp_discount": 8, "sp_category_share": 2}
LABEL = {"store_conv": "Store conversion", "store_busy_conv": "Sat + Sun conversion", "store_ipb": "Store items per bill",
         "city_rpf": "City revenue per walk-in", "sp_sherwani_addon": "Sherwani add-on rate",
         "sp_jacket_addon": "Jacket add-on rate", "sp_discount": "Discount off MRP", "sp_repeat": "Repeat rate",
         "sp_category_share": "{category} share of items"}
LOWER_IS_BETTER = {"sp_discount"}


def fmt(metric, x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if metric == "store_ipb":
        return f"{x:.2f}"
    if metric == "city_rpf":
        return f"₹{x:,.0f}"
    if metric in ("store_conv", "store_busy_conv", "sp_discount", "sp_category_share", "sp_repeat"):
        return f"{x * 100:.1f}%"
    return f"{x * 100:.0f}%"


def _gap(metric, expected, actual):
    return (actual - expected) if metric in LOWER_IS_BETTER else (expected - actual)


def _ratio(a, b):
    return a / b if b else float("nan")


class FollowUp:
    def __init__(self, prep):
        self.p = prep
        self.foot = prep.footfall[~prep.footfall.bad]
        self.bills = prep.bills

    # ---- helpers ---------------------------------------------------------------
    def _peers(self, sid, d0):
        st = self.p.stores
        state = st.loc[st.store_id == sid, "state"].iloc[0]
        est = st[st.opened_on <= d0 - pd.Timedelta(days=ESTABLISHED_DAYS)]
        return est.loc[(est.state == state) & (est.store_id != sid), "store_id"].tolist()

    def _conv(self, ids, win, weekend=False):
        f = self.foot[self.foot.store_id.isin(ids) & win.mask(self.foot.date)]
        if weekend:
            f = f[f.weekend]
        return f.bills.sum(), f.footfall.sum()

    def _ipb(self, ids, win):
        b = self.bills[self.bills.store_id.isin(ids) & win.mask(self.bills.date)]
        return b["items"].sum(), len(b)

    def _sp_bills(self, sp_id, win):
        b = self.bills[win.mask(self.bills.date)]
        sid = b.loc[b.sp == sp_id, "store_id"]
        sid = sid.iloc[0] if len(sid) else self.p.people.set_index("salesperson_id").store_id.get(sp_id)
        store = b[b.store_id == sid]
        return store[store.sp == sp_id], store[store.sp != sp_id]

    # ---- re-measure ------------------------------------------------------------
    def remeasure(self, meas, d0):
        """(expected_now, actual_now, sample_n) over D0 … D0+6, or None if not measurable."""
        metric = meas["metric"]
        fu = Window(d0, d0 + 6 * DAY)
        recent = Window(d0 - 56 * DAY, d0 - DAY)        # the alert's Recent window
        if metric in ("store_conv", "store_busy_conv"):
            sid, wk = meas["store_id"], metric == "store_busy_conv"
            peers = self._peers(sid, d0)
            b, n = self._conv([sid], fu, wk)
            pb_fu, pn_fu = self._conv(peers, fu, wk)
            pb_r, pn_r = self._conv(peers, recent, wk)
            exp = meas["expected"] * _ratio(_ratio(pb_fu, pn_fu), _ratio(pb_r, pn_r))
            return exp, _ratio(b, n), (n if wk else b)
        if metric == "store_ipb":
            sid = meas["store_id"]
            peers = self._peers(sid, d0)
            i, n = self._ipb([sid], fu)
            pi_fu, pn_fu = self._ipb(peers, fu)
            pi_r, pn_r = self._ipb(peers, recent)
            exp = meas["expected"] * _ratio(_ratio(pi_fu, pn_fu), _ratio(pi_r, pn_r))
            return exp, _ratio(i, n), n
        if metric == "city_rpf":
            ya = Window(fu.start - 364 * DAY, fu.end - 364 * DAY)
            st = self.p.stores
            comp = st[st.opened_on <= ya.start]
            city = comp.loc[comp.city == meas["city"], "store_id"]
            other = comp.loc[comp.city != meas["city"], "store_id"]

            def rpf(ids, win):
                f = self.foot[self.foot.store_id.isin(ids) & win.mask(self.foot.date)]
                return _ratio(f.rev.sum(), f.footfall.sum()), f.bills.sum()
            act, n = rpf(city, fu)
            exp = rpf(city, ya)[0] * _ratio(rpf(other, fu)[0], rpf(other, ya)[0])
            return exp, act, n
        if metric in ("sp_sherwani_addon", "sp_jacket_addon"):
            own, peers = self._sp_bills(meas["salesperson_id"], fu)
            has, hit = ("shw", "shw_acc") if metric == "sp_sherwani_addon" else ("kur", "kur_jkt")
            o, p = own[own[has]], peers[peers[has]]
            return _ratio(p[hit].sum(), len(p)), _ratio(o[hit].sum(), len(o)), len(o)
        if metric == "sp_discount":
            own, peers = self._sp_bills(meas["salesperson_id"], fu)
            return _ratio(peers.disc.sum(), peers.mrpv.sum()), _ratio(own.disc.sum(), own.mrpv.sum()), len(own)
        if metric == "sp_category_share":
            own, peers = self._sp_bills(meas["salesperson_id"], fu)
            cat = meas["category"]
            exp = _ratio(peers[cat].sum(), peers["items"].sum())
            return exp, _ratio(own[cat].sum(), own["items"].sum()), own["items"].sum() * (exp if exp == exp else 0)
        return None

    def check(self, issue, d0, as_of) -> dict:
        """Follow-up row for the output contract. `issue` is the issue as sent on d0."""
        meas = issue["measure"]
        metric = meas["metric"]
        assert d0 + 6 * DAY <= as_of - DAY, "follow-up window must be before the run date (no look-ahead)"
        label = LABEL.get(metric, metric).format(category=cat_lc(meas.get("category", "")))
        who = issue["salesperson_ids"][0] if issue.get("salesperson_ids") and metric.startswith("sp_") else None
        if who:
            name = next((c.get("name") for c in issue.get("components", []) if c.get("sp") == who), who)
            label = f"{name}: {label[0].lower() + label[1:] if not label.startswith('Indo') else label}"
        exp_a, act_a = meas["expected"], meas["actual"]
        at_alert = f"{fmt(metric, act_a)} (expected {fmt(metric, exp_a)})"
        row = {"issue_id": issue["id"], "raised_on": f"{d0:%Y-%m-%d}", "metric": label, "at_alert": at_alert,
               "window": f"{d0:%Y-%m-%d} → {d0 + 6 * DAY:%Y-%m-%d}", "rupees_at_stake_week": issue["rupees_at_stake_week"],
               "store_id": issue["store_id"]}
        if metric == "sp_repeat":
            return row | {"now": "—", "moved": "too early to tell",
                          "note": "A repeat visit needs 30+ days, so one week can't show it. Check again next month."}
        r = self.remeasure(meas, d0)
        if r is None:
            return row | {"now": "—", "moved": "too little data to tell", "note": "This measure can't be re-checked in one week."}
        exp_n, act_n, n = r
        row["now"] = f"{fmt(metric, act_n)} (expected {fmt(metric, exp_n)})"
        if n < MIN_FU.get(metric, 0) or any(isinstance(x, float) and math.isnan(x) for x in (exp_n, act_n)):
            if metric == "sp_category_share":
                cat = cat_lc(meas.get("category", ""))
                note = f"Too few items sold in the week after the alert to judge the {cat} share yet."
            else:
                one, many = {"store_busy_conv": ("weekend walk-in", "weekend walk-ins"), "sp_sherwani_addon": ("sherwani bill", "sherwani bills"),
                             "sp_jacket_addon": ("kurta-set bill", "kurta-set bills")}.get(metric, ("bill", "bills"))
                k = int(round(n))
                note = (f"No {many} in the week after the alert, so it can't be judged yet." if k == 0 else
                        f"Only {k} {one if k == 1 else many} in the week after the alert (need {MIN_FU[metric]}), so it can't be judged yet.")
            return row | {"moved": "too little data to tell", "note": note}
        g_a, g_n = _gap(metric, exp_a, act_a), _gap(metric, exp_n, act_n)
        moved = "better" if g_n <= 0.75 * g_a else "worse" if g_n >= 1.25 * g_a else "no change"
        unit = (lambda g: f"₹{g:,.0f}") if metric == "city_rpf" else (lambda g: f"{g:.2f}") if metric == "store_ipb" \
            else (lambda g: f"{g * 100:.1f} pts")
        if g_n <= 0:
            note = f"Gap closed: was {unit(g_a)} short of expected, at or above it in the 7 days after ({d0.day}–{(d0 + 6 * DAY).day} {(d0 + 6 * DAY):%b})." if d0.month == (d0 + 6 * DAY).month else                 f"Gap closed: was {unit(g_a)} short of expected, at or above it in the 7 days after ({d0.day} {d0:%b} – {(d0 + 6 * DAY).day} {(d0 + 6 * DAY):%b})."
        else:
            note = (f"Gap {unit(g_a)} at the alert, {unit(g_n)} in the 7 days after "
                    f"({'closing' if moved == 'better' else 'widening' if moved == 'worse' else 'about the same'}).")
        return row | {"moved": moved, "note": note, "gap_at_alert": round(float(g_a), 4), "gap_now": round(float(g_n), 4)}
