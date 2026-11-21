"""Independent re-derivation of Store Coach check numbers (Step 3).

Written straight from METRICS.md with plain pandas on data/raw/*.csv.
It deliberately does NOT import anything from `storecoach`, so a bug in the
engine cannot hide here too.

    python tests/independent.py            # prints every number for as_of 2026-11-02
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
AS_OF = pd.Timestamp("2026-11-02")
DAY = pd.Timedelta(days=1)


def win(a: int, b: int, as_of=AS_OF):
    """Days D-a … D-b (inclusive)."""
    return as_of - a * DAY, as_of - b * DAY


RECENT = win(56, 1)
BASELINE = win(182, 57)
SALES = win(91, 1)
SHIFTS = win(28, 1)
ACTIVITY = win(14, 1)
COHORT = win(540, 121)
YEAR_AGO = (RECENT[0] - 364 * DAY, RECENT[1] - 364 * DAY)


def inwin(s: pd.Series, w) -> pd.Series:
    return (s >= w[0]) & (s <= w[1])


@lru_cache(maxsize=1)
def raw():
    t = lambda f, **kw: pd.read_csv(RAW / f, dtype=str, **kw)
    bills = t("bills.csv")
    bills["bill_date"] = pd.to_datetime(bills["bill_date"])
    bills = bills[bills.bill_date <= AS_OF - DAY]  # no look-ahead
    lines = t("bill_lines.csv")
    for c in ("qty", "mrp", "selling_price"):
        lines[c] = lines[c].astype(float)
    items = t("items.csv")[["sku_id", "category", "is_packaging"]]
    lines = lines.merge(items, on="sku_id", how="left")
    lines = lines[lines.is_packaging == "0"]  # items only
    lines = lines[lines.bill_id.isin(bills.bill_id)]
    lines["rev"] = lines.qty * lines.selling_price
    lines["mrpv"] = lines.qty * lines.mrp
    foot = t("footfall_daily.csv")
    foot["date"] = pd.to_datetime(foot["date"])
    foot["footfall"] = foot["footfall"].astype(float)
    foot = foot[foot.date <= AS_OF - DAY]
    roster = t("roster_daily.csv")
    roster["date"] = pd.to_datetime(roster["date"])
    roster = roster[roster.date <= AS_OF - DAY]
    stores = t("stores.csv")
    stores["opened_on"] = pd.to_datetime(stores["opened_on"])
    sp = t("salespeople.csv")
    return bills, lines, foot, roster, stores, sp


@lru_cache(maxsize=1)
def bill_facts() -> pd.DataFrame:
    """One row per bill: items, revenue, mrp value."""
    bills, lines, *_ = raw()
    agg = lines.groupby("bill_id").agg(items=("qty", "sum"), rev=("rev", "sum"), mrpv=("mrpv", "sum"))
    return bills.merge(agg, left_on="bill_id", right_index=True, how="left")


@lru_cache(maxsize=1)
def day_table() -> pd.DataFrame:
    """Store-day: footfall, bills, revenue, good-day flag."""
    b = bill_facts()
    _, _, foot, *_ = raw()
    d = b.groupby(["store_id", "bill_date"]).agg(bills=("bill_id", "size"), rev=("rev", "sum")).reset_index()
    d = d.rename(columns={"bill_date": "date"})
    t = foot.merge(d, on=["store_id", "date"], how="left").fillna({"bills": 0, "rev": 0.0})
    t["good"] = (t.footfall > 0) & (t.bills <= t.footfall)
    return t


def established(as_of=AS_OF):
    stores = raw()[4]
    return set(stores.loc[stores.opened_on <= as_of - 90 * DAY, "store_id"])


def state_peers(store: str) -> list[str]:
    stores = raw()[4]
    st = stores.set_index("store_id").state[store]
    est = established()
    return [s for s in stores.store_id if s != store and s in est and stores.set_index("store_id").state[s] == st]


def conv(stores_, w, weekend_only=False):
    t = day_table()
    t = t[t.store_id.isin(stores_) & t.good & inwin(t.date, w)]
    if weekend_only:
        t = t[t.date.dt.dayofweek >= 5]
    return t.bills.sum(), t.footfall.sum()


def rate_z(k, n, p0):
    if n == 0 or not 0 < p0 < 1:
        return float("nan")  # no spread → no z
    return (k - n * p0) / math.sqrt(n * p0 * (1 - p0))


def store_conversion(store: str, weekend_only=False) -> dict:
    peers = state_peers(store)
    kb, nb = conv([store], BASELINE, weekend_only)
    kr, nr = conv([store], RECENT, weekend_only)
    pkb, pnb = conv(peers, BASELINE, weekend_only)
    pkr, pnr = conv(peers, RECENT, weekend_only)
    exp = (kb / nb) / (pkb / pnb) * (pkr / pnr)
    act = kr / nr
    b = bill_facts()
    br = b[(b.store_id == store) & inwin(b.bill_date, RECENT)]
    atv = br.rev.sum() / len(br)
    weeks = 56 / 7
    return dict(actual=act, expected=exp, z=rate_z(kr, nr, exp), bills=kr, footfall=nr,
                rs_week=(exp - act) * (nr / weeks) * atv, peers=peers)


def store_ipb(store: str) -> dict:
    b = bill_facts()
    peers = state_peers(store)
    ipb = lambda s, w: (lambda x: x["items"].sum() / len(x))(b[b.store_id.isin(s) & inwin(b.bill_date, w)])
    exp = ipb([store], BASELINE) * ipb(peers, RECENT) / ipb(peers, BASELINE)
    x = b[(b.store_id == store) & inwin(b.bill_date, RECENT)]["items"]
    return dict(actual=x.mean(), expected=exp, z=(x.mean() - exp) / (x.std(ddof=1) / math.sqrt(len(x))), bills=len(x))


def leaver_facts(sp_id: str, store: str) -> dict:
    b = bill_facts()
    roster = raw()[3]
    bb = b[(b.store_id == store) & inwin(b.bill_date, BASELINE)]
    mine = b[b.salesperson_id == sp_id]
    present = roster[(roster.salesperson_id == sp_id) & (roster.status == "Present")]
    return dict(share_baseline=(bb.salesperson_id == sp_id).mean(), last_bill=mine.bill_date.max(),
                last_present=present.date.max(),
                active=bool(inwin(mine.bill_date, ACTIVITY).any() or inwin(present.date, ACTIVITY).any()))


def off_rate(sp_id: str, w) -> tuple[int, int]:
    r = raw()[3]
    r = r[(r.salesperson_id == sp_id) & inwin(r.date, w)]
    return int((r.status == "Off").sum()), len(r)


def discount(store: str) -> pd.DataFrame:
    """Discount % per salesperson vs the rest of the store, Salesperson window."""
    b = bill_facts()
    x = b[(b.store_id == store) & inwin(b.bill_date, SALES)]
    g = x.groupby("salesperson_id").agg(rev=("rev", "sum"), mrpv=("mrpv", "sum"), bills=("bill_id", "size"))
    tot = g.sum()
    g["disc"] = 1 - g.rev / g.mrpv
    g["peer_disc"] = 1 - (tot.rev - g.rev) / (tot.mrpv - g.mrpv)
    return g


def addon(store: str, kind: str) -> pd.DataFrame:
    """Add-on k/n per salesperson vs the rest of the store, Salesperson window."""
    bills, lines, *_ = raw()
    base, adds = ("Sherwani", {"Safa", "Mojari", "Mala"}) if kind == "sherwani" else ("Kurta Set", {"Jacket"})
    b = bills[(bills.store_id == store) & inwin(bills.bill_date, SALES)]
    l = lines[lines.bill_id.isin(b.bill_id)]
    has_base = set(l.loc[l.category == base, "bill_id"])
    has_add = set(l.loc[l.category.isin(adds), "bill_id"])
    b = b[b.bill_id.isin(has_base)].copy()
    b["k"] = b.bill_id.isin(has_add)
    g = b.groupby("salesperson_id").k.agg(["sum", "size"]).rename(columns={"sum": "k", "size": "n"})
    tot = g.sum()
    g["rate"] = g.k / g.n
    g["peer_rate"] = (tot.k - g.k) / (tot.n - g.n)
    g["z"] = [rate_z(r.k, r.n, r.peer_rate) for r in g.itertuples()]
    return g


def category_share(store: str) -> pd.DataFrame:
    """Per salesperson × category: qty, own items, peer share, expected = items × peer share, z."""
    bills, lines, *_ = raw()
    b = bills[(bills.store_id == store) & inwin(bills.bill_date, SALES)][["bill_id", "salesperson_id"]]
    l = lines.merge(b, on="bill_id")
    q = l.pivot_table(index="salesperson_id", columns="category", values="qty", aggfunc="sum", fill_value=0)
    items = q.sum(axis=1)
    rows = []
    for cat in q.columns:
        peer_share = (q[cat].sum() - q[cat]) / (items.sum() - items)
        for p in q.index:
            k, n, p0 = q.loc[p, cat], items[p], peer_share[p]
            rows.append(dict(sp=p, category=cat, qty=k, items=n, peer_share=p0, expected=n * p0, z=rate_z(k, n, p0)))
    return pd.DataFrame(rows).set_index(["sp", "category"])


@lru_cache(maxsize=1)
def repeat_cohort() -> pd.DataFrame:
    """One row per cohort customer: first-bill store/salesperson, repeated?"""
    bills = raw()[0]
    cnt = bills.customer_id.value_counts()
    placeholders = set(cnt[cnt >= 50].index)
    b = bills[~bills.customer_id.isin(placeholders)].sort_values(["bill_date", "bill_id"])
    first = b.groupby("customer_id").first()
    first = first[inwin(first.bill_date, COHORT)]
    later = b.merge(first[["bill_date"]].rename(columns={"bill_date": "first_date"}),
                    left_on="customer_id", right_index=True)
    rep = later[later.bill_date >= later.first_date + 30 * DAY].customer_id.unique()
    first["repeat"] = first.index.isin(rep)
    first.attrs["placeholders"] = placeholders
    return first


def repeat_by_sp(store: str) -> pd.DataFrame:
    c = repeat_cohort()
    c = c[c.store_id == store]
    g = c.groupby("salesperson_id").repeat.agg(["sum", "size"]).rename(columns={"sum": "k", "size": "n"})
    tot = g.sum()
    g["rate"] = g.k / g.n
    g["peer_rate"] = (tot.k - g.k) / (tot.n - g.n)
    g["z"] = [rate_z(r.k, r.n, r.peer_rate) for r in g.itertuples()]
    return g


def city_vs_company(city: str) -> dict:
    """City Recent vs Year ago, against all other cities (stores open before the Year-ago window)."""
    stores = raw()[4]
    old = stores[stores.opened_on < YEAR_AGO[0]]
    mine = list(old.loc[old.city == city, "store_id"])
    others = list(old.loc[old.city != city, "store_id"])
    t = day_table()
    b = bill_facts()

    def agg(s, w):
        d = t[t.store_id.isin(s) & t.good & inwin(t.date, w)]
        bb = b[b.store_id.isin(s) & inwin(b.bill_date, w)]
        good = d[["store_id", "date"]].rename(columns={"date": "bill_date"})
        bg = bb.merge(good, on=["store_id", "bill_date"])  # bills on good days, for RPF/conv
        return dict(foot=d.footfall.sum(), bills_g=len(bg), rev_g=bg.rev.sum(),
                    bills=len(bb), rev=bb.rev.sum(), items=bb["items"].sum(), bill_revs=bg.rev.values)

    c_r, c_y, o_r, o_y = agg(mine, RECENT), agg(mine, YEAR_AGO), agg(others, RECENT), agg(others, YEAR_AGO)
    out = {}
    fns = dict(rpf=lambda a: a["rev_g"] / a["foot"], conv=lambda a: a["bills_g"] / a["foot"],
               ipb=lambda a: a["items"] / a["bills"], atv=lambda a: a["rev"] / a["bills"])
    for k, f in fns.items():
        exp = f(c_y) * f(o_r) / f(o_y)
        out[k] = f(c_r)
        out[k + "_exp"] = exp
        out[k + "_gap"] = f(c_r) / exp - 1
    n = c_r["foot"]
    vals = np.concatenate([c_r["bill_revs"], np.zeros(int(n - c_r["bills_g"]))])
    out["rpf_z"] = (vals.mean() - out["rpf_exp"]) / (vals.std(ddof=1) / math.sqrt(n))
    out["rs_week"] = (out["rpf_exp"] - out["rpf"]) * n / 8
    return out


def bad_days(store: str) -> list[pd.Timestamp]:
    t = day_table()
    return list(t[(t.store_id == store) & ~t.good].date)


def weekday_present(store: str, start: str, end: str) -> pd.Series:
    r = raw()[3]
    r = r[(r.store_id == store) & (r.status == "Present") & inwin(r.date, (pd.Timestamp(start), pd.Timestamp(end)))]
    per_day = r.groupby("date").size()
    return per_day.groupby(per_day.index.day_name()).mean()


def monthly_ipb(store: str, month: str) -> float:
    b = bill_facts()
    x = b[(b.store_id == store) & (b.bill_date.dt.strftime("%Y-%m") == month)]
    return x["items"].sum() / len(x)


def overall_repeat() -> float:
    return repeat_cohort().repeat.mean()


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    p = lambda *a: print(*a)
    p("Windows", RECENT, BASELINE, SALES, SHIFTS, ACTIVITY, COHORT, YEAR_AGO)
    for s in ("LKO-02", "BLR-03"):
        p(s, "conv", {k: v for k, v in store_conversion(s).items()})
        p(s, "busy", {k: v for k, v in store_conversion(s, weekend_only=True).items()})
        p(s, "ipb", store_ipb(s))
    p("SP1018", leaver_facts("SP1018", "LKO-02"))
    for sp in ("SP1141", "SP1142"):
        p(sp, "off recent", off_rate(sp, SHIFTS), "baseline", off_rate(sp, BASELINE))
    p("PAT-01 discount\n", discount("PAT-01"))
    p("BLR-01 discount\n", discount("BLR-01"))
    p("BLR-02 sherwani\n", addon("BLR-02", "sherwani"))
    p("PAT-02 sherwani\n", addon("PAT-02", "sherwani"))
    p("PAT-02 jacket\n", addon("PAT-02", "jacket"))
    p("BLR-01 repeat\n", repeat_by_sp("BLR-01"))
    p("PAT-01 repeat\n", repeat_by_sp("PAT-01"))
    p("overall repeat", overall_repeat(), "placeholders", repeat_cohort().attrs["placeholders"])
    p("Mysuru", city_vs_company("Mysuru"))
    p("PAT-03 bad days", [d.strftime("%Y-%m-%d") for d in bad_days("PAT-03")])
    p("BLR-03 present Sep-Oct", weekday_present("BLR-03", "2026-09-01", "2026-10-31").round(2).to_dict())
    p("BLR-01 IPB Oct 2026", monthly_ipb("BLR-01", "2026-10"), "LKO-02 IPB Oct", monthly_ipb("LKO-02", "2026-10"))
    p("established", sorted(established()))
