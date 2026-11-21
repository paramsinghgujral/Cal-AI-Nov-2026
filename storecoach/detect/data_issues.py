"""Data issues: things that look wrong in the data. Shown on the site's Data panel,
never sent to AMs (brief: "a number that can't be right → flag, don't alert").
"""
from __future__ import annotations

import pandas as pd

from .common import day, iso

SPIKE = 3.0   # a store's share of company footfall ≥ 3× (or ≤ ⅓ of) its usual share that day


def _runs(dates):
    """Consecutive-day runs: [(start, end, n), ...]."""
    d = sorted(pd.to_datetime(dates))
    out, start, prev = [], None, None
    for x in d:
        if start is None:
            start = prev = x
        elif (x - prev).days == 1:
            prev = x
        else:
            out.append((start, prev))
            start = prev = x
    if start is not None:
        out.append((start, prev))
    return out


def bad_footfall(m) -> list[dict]:
    out = []
    bd = m.bad_days
    for sid, g in bd.groupby("store_id"):
        g = g.sort_values("date")
        for a, b in _runs(g.date):
            x = g[(g.date >= a) & (g.date <= b)]
            zero = bool((x.footfall <= 0).all())
            n, bills = len(x), int(x.bills.sum())
            out.append({
                "type": "camera_zero" if zero else "footfall_below_bills", "store_id": sid,
                "detail": (f"Footfall camera reads 0 on {n} day{'s' * (n > 1)} while {bills} bills were made — camera fault, not an empty store."
                           if zero else f"Fewer walk-ins counted than bills on {n} day{'s' * (n > 1)} ({bills} bills) — the count can't be right."),
                "dates": f"{iso(a)} → {iso(b)}" if n > 1 else iso(a),
                "excluded_from": "conversion and revenue per walk-in (bills still count for basket metrics)",
            })
    return out


def placeholders(m, prep) -> list[dict]:
    last = m.as_of - pd.Timedelta(days=1)
    b = prep.bills[prep.bills.date <= last]
    out = []
    for cid in m.placeholders:
        x = b[b.customer_id == cid]
        out.append({
            "type": "placeholder_customer", "store_id": None, "customer_id": cid,
            "detail": (f"Customer {cid} has {len(x):,} bills at {x.store_id.nunique()} stores — a dummy mobile number typed at the till, "
                       f"not a real regular."),
            "dates": f"{iso(x.date.min())} → {iso(x.date.max())}",
            "excluded_from": "repeat and customer metrics",
        })
    return out


def new_stores(m) -> list[dict]:
    out = []
    for _, s in m.stores[~m.stores.established].iterrows():
        days = (m.as_of - s.opened_on).days
        if days < 0:
            continue
        ago = "yesterday" if days <= 1 else f"{days} days ago"
        out.append({
            "type": "new_store", "store_id": s.store_id,
            "detail": f"{s.store_id} opened on {day(s.opened_on)} {s.opened_on.year} ({ago}) — too new to compare fairly.",
            "dates": f"{iso(s.opened_on)} → {iso(m.as_of - pd.Timedelta(days=1))}",
            "excluded_from": "store comparisons, peer groups and AM alerts (until 90 days open)",
        })
    return out


def footfall_spikes(m, prep) -> list[dict]:
    """A store-day whose share of company footfall is ≥ 3× (or ≤ ⅓ of) the store's usual
    share. Company-wide busy days (festivals, pre-Diwali Sundays) move every store
    together, so they cancel out and are not flagged."""
    w, last = m.windows, m.as_of - pd.Timedelta(days=1)
    f = prep.footfall[(prep.footfall.date <= last) & ~prep.footfall.bad].copy()
    f = f[f.store_id.isin(m.stores.loc[m.stores.established, "store_id"])]
    f["share"] = f.footfall / f.groupby("date").footfall.transform("sum")
    f = f.sort_values("date")
    f["usual"] = f.groupby("store_id").share.transform(lambda s: s.rolling(57, center=True, min_periods=15).median())
    r = f[w.recent.mask(f.date) & ((f.share >= SPIKE * f.usual) | (f.share <= f.usual / SPIKE))]
    return [{
        "type": "footfall_spike" if x.share > x.usual else "footfall_dip", "store_id": x.store_id,
        "detail": f"{int(x.footfall)} walk-ins on {day(x.date)} — {x.share / x.usual:.1f}× the store's usual share of company footfall.",
        "dates": iso(x.date), "excluded_from": "nothing (kept; check the camera)",
    } for _, x in r.iterrows()]


def off_day_bills(m, prep) -> list[dict]:
    """Bills credited to a salesperson whose roster says Off that day (Recent window)."""
    w, last = m.windows, m.as_of - pd.Timedelta(days=1)
    b = prep.bills[w.recent.mask(prep.bills.date)]
    r = prep.roster[(prep.roster.date <= last) & prep.roster.status.eq("Off")][["salesperson_id", "date"]]
    x = b.merge(r, left_on=["sp", "date"], right_on=["salesperson_id", "date"])
    names = prep.people.set_index("salesperson_id").name
    out = []
    for sp, g in x.groupby("sp"):
        out.append({
            "type": "billed_on_off_day", "store_id": g.store_id.iloc[0], "salesperson_id": sp,
            "detail": f"{names.get(sp, sp)} ({sp}) is credited with {len(g)} bill{'s' * (len(g) > 1)} on rostered Off days — roster or bill credit is wrong.",
            "dates": ", ".join(sorted({iso(d) for d in g.date})),
            "excluded_from": "nothing (bills kept)",
        })
    return out


def data_issues(m, prep) -> list[dict]:
    return bad_footfall(m) + placeholders(m, prep) + new_stores(m) + footfall_spikes(m, prep) + off_day_bills(m, prep)
