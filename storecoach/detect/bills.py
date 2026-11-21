"""More bills: leaver, missing shifts, understaffed busy days, conversion drop,
city slowdown — plus cause merging (METRICS §4–5, PLAN Step 4).

A store's conversion / busy-day / IPB gaps are merged into ONE issue carrying the
named cause (leaver beats missing shifts). Stores in a city with a city-slowdown
Issue have their conversion / busy-day / IPB alerts folded into the city issue.
"""
from __future__ import annotations

import pandas as pd

from .common import day, ev, f, iso, make_issue, names, num, pct, rs, span, top_level

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class StoreFacts:
    """Per-store facts Step 5 needs for action text, computed once per run."""

    def __init__(self, m, prep):
        w, last = m.windows, m.as_of - pd.Timedelta(days=1)
        self.m, self.w = m, w
        foot = prep.footfall[(prep.footfall.date <= last) & ~prep.footfall.bad]
        self.foot = foot
        ro = prep.roster[(prep.roster.date <= last) & prep.roster.status.eq("Present")]
        self.staff = m.staffing.set_index("store_id")
        rb = ro[w.baseline.mask(ro.date)].groupby(["store_id", "date"]).size().rename("n").reset_index()
        rb["wkend"] = rb.date.dt.dayofweek >= 5
        self.staff_b_weekend = rb[rb.wkend].groupby("store_id").n.mean()
        self.staff_b_fri = rb[rb.date.dt.dayofweek == 4].groupby("store_id").n.mean()
        fr = foot[w.recent.mask(foot.date)].copy()
        fr["dow"] = fr.date.dt.dayofweek
        self.dow_foot = fr.groupby(["store_id", "dow"]).footfall.mean()
        self.daily_foot_r = fr.groupby("store_id").footfall.mean()
        self.daily_foot_b = foot[w.baseline.mask(foot.date)].groupby("store_id").footfall.mean()

    def quiet_weekday(self, sid):
        s = self.dow_foot.get(sid)
        if s is None or s.empty:
            return None
        s = s[s.index < 5]
        return DOW[int(s.idxmin())] if len(s) else None

    def staffing(self, sid) -> dict:
        st = self.staff.loc[sid] if sid in self.staff.index else None
        g = (lambda k: f(st[k], 2) if st is not None and k in st else None)
        return {"fri": g("Fri"), "sat": g("Sat"), "sun": g("Sun"), "weekday_avg": g("weekday_avg"),
                "weekend_avg": g("weekend_avg"), "weekend_avg_baseline": f(self.staff_b_weekend.get(sid), 2),
                "fri_baseline": f(self.staff_b_fri.get(sid), 2)}

    def short_on_weekends(self, sid) -> bool:
        s = self.staffing(sid)
        we, fri, web = s["weekend_avg"], s["fri"], s["weekend_avg_baseline"]
        if we is None:
            return False
        return (fri is not None and we < 0.9 * fri) or (web is not None and we < 0.9 * web)

    def footfall_vs_peers(self, sid, peer_ids):
        """Store's daily footfall change (Recent ÷ Baseline) relative to its peers'."""
        r, b = self.daily_foot_r, self.daily_foot_b
        if sid not in r or sid not in b or not len(peer_ids):
            return None
        own = r[sid] / b[sid]
        pr = r.reindex(peer_ids).sum() / b.reindex(peer_ids).sum()
        return own / pr - 1

    def top_sellers(self, sid, exclude=(), k=2):
        sp = self.m.salespeople
        x = sp[(sp.store_id == sid) & sp.active & ~sp.sp.isin(exclude)].sort_values("rev", ascending=False).head(k)
        return [{"salesperson_id": r.sp, "name": r["name"]} for _, r in x.iterrows()]

    def base(self, sid, exclude=()) -> dict:
        return {"quiet_weekday": self.quiet_weekday(sid), "staffing": self.staffing(sid),
                "top_active_sellers": self.top_sellers(sid, exclude)}


# ---- store components ---------------------------------------------------------
def _conv_comp(s, w):
    return {
        "kind": "conversion", "level": s.conv_level, "rs": s.conv_rs_week, "z": s.conv_z,
        "what": f"conversion {pct(s.conv_r)} vs {pct(s.conv_exp)} expected",
        "evidence": [ev(f"Store conversion, {span(w.recent)}", pct(s.conv_r), f"{pct(s.conv_exp)} expected from same-state stores")],
        "measure": {"metric": "store_conv", "store_id": s.store_id, "expected": f(s.conv_exp), "actual": f(s.conv_r),
                    "min_sample": "100 bills"},
    }


def _busy_comp(s, w):
    return {
        "kind": "busy_days", "level": s.busy_conv_level, "rs": s.busy_conv_rs_week, "z": s.busy_conv_z,
        "what": f"Sat/Sun conversion {pct(s.busy_conv_r)} vs {pct(s.busy_conv_exp)} expected",
        "evidence": [ev(f"Sat + Sun conversion, {span(w.recent)}", pct(s.busy_conv_r), f"{pct(s.busy_conv_exp)} expected from same-state stores")],
        "measure": {"metric": "store_busy_conv", "store_id": s.store_id, "expected": f(s.busy_conv_exp), "actual": f(s.busy_conv_r),
                    "min_sample": "300 walk-ins"},
    }


def _ipb_comp(s, w):
    return {
        "kind": "ipb", "level": s.ipb_level, "rs": s.ipb_rs_week, "z": s.ipb_z,
        "what": f"items per bill {num(s.ipb_r)} vs {num(s.ipb_exp)} expected",
        "evidence": [ev(f"Items per bill, {span(w.recent)}", num(s.ipb_r), f"{num(s.ipb_exp)} expected from same-state stores")],
        "measure": {"metric": "store_ipb", "store_id": s.store_id, "expected": f(s.ipb_exp), "actual": f(s.ipb_r),
                    "min_sample": "100 bills"},
    }


def _comp_view(c):
    return {"kind": c["kind"], "level": c["level"], "what": c["what"], "rupees_at_stake_week": int(max(c["rs"], 0)),
            "z": round(float(c["z"]), 2), "measure": c["measure"]}


def _merge(comps):
    """Level = strongest member; ₹ = largest member gap (never the sum)."""
    lv = top_level(c["level"] for c in comps)
    lead = max([c for c in comps if c["level"] == lv], key=lambda c: c["rs"]) if lv else None
    return lv, lead


# ---- city slowdown --------------------------------------------------------------
def _store_rpf_yoy(m, sf, city):
    """Each store's revenue per walk-in vs what it would be had it moved like the
    other cities since the same days a year ago."""
    w, st = m.windows, m.stores
    comparable = st[st.opened_on <= w.year_ago.start]
    foot = sf.foot[sf.foot.store_id.isin(comparable.store_id)]

    def agg(win):
        x = foot[win.mask(foot.date)]
        return x.groupby("store_id")[["footfall", "rev"]].sum()

    r, y = agg(w.recent), agg(w.year_ago)
    in_city = comparable.loc[comparable.city == city, "store_id"]
    others = comparable.loc[comparable.city != city, "store_id"]
    move = (r.reindex(others).rev.sum() / r.reindex(others).footfall.sum()) / (y.reindex(others).rev.sum() / y.reindex(others).footfall.sum())
    out = []
    for sid in in_city:
        if sid not in r.index or sid not in y.index:
            continue
        act = r.rev[sid] / r.footfall[sid]
        exp = y.rev[sid] / y.footfall[sid] * move
        out.append({"store_id": sid, "rpf": act, "rpf_exp": exp, "gap_pct": act / exp - 1,
                    "rs_week": (exp - act) * r.footfall[sid] / w.recent.weeks})
    return out


def city_issues(m, sf, am_by_city) -> list[dict]:
    w, out = m.windows, []
    for _, c in m.cities[m.cities.city_level.notna()].iterrows():
        per_store = _store_rpf_yoy(m, sf, c.city)
        all_down = bool(per_store) and all(s["gap_pct"] < 0 for s in per_store)
        focus = max(per_store, key=lambda s: s["rs_week"])["store_id"] if per_store else None
        n = len(per_store)
        where = ("both stores" if n == 2 else f"all {n} stores") if all_down and n > 1 else None
        # D19: a market problem means every store falls together. If one store is up,
        # the city drop is not proven to be the market → Watch, and nothing is folded.
        level = c.city_level if all_down else "watch"
        down = [s["store_id"] for s in per_store if s["gap_pct"] < 0]
        evidence = [
            ev(f"{c.city} revenue per walk-in, {span(w.recent)}", rs(c.rpf_r),
               f"{rs(c.rpf_exp)} if it had moved like other cities since last year ({rs(c.rpf_ya)} then)"),
            ev("Conversion", pct(c.conv_r), f"{pct(c.conv_exp)} expected ({pct(c.conv_gap_pct)})"),
            ev("Items per bill", num(c.ipb_r), f"{num(c.ipb_exp)} expected ({pct(c.ipb_gap_pct)})"),
            ev("Average bill value", rs(c.atv_r), f"{rs(c.atv_exp)} expected ({pct(c.atv_gap_pct)})"),
        ] + [ev(f"{s['store_id']} revenue per walk-in", rs(s["rpf"]), f"{rs(s['rpf_exp'])} expected ({pct(s['gap_pct'])})")
             for s in per_store]
        out.append(make_issue(
            id=f"{c.city}:city_slowdown", level=level, type="city_slowdown", lever="More bills", scope="city",
            area_manager_id=am_by_city.get(c.city), city=c.city, store_id=focus, salesperson_ids=[],
            title=f"{c.city} is slowing down" + (f" in {where}" if where else f" ({len(down)} of {n} stores)"),
            cause=(f"Market slowdown, not one store: conversion, items per bill and bill value are all below "
                   f"what other cities' trend since last year predicts, in {where} at once." if where else
                   f"City revenue per walk-in is below other cities' trend since last year, but only {names(down)} "
                   f"{'is' if len(down) == 1 else 'are'} down — not proven to be the market."),
            rs_week=c.rpf_rs_week, z=c.rpf_z, evidence=evidence,
            measure={"metric": "city_rpf", "city": c.city, "expected": f(c.rpf_exp, 2), "actual": f(c.rpf_r, 2),
                     "min_sample": "100 bills"},
            facts={"stores": [s["store_id"] for s in per_store], "per_store": [
                {k: (f(v, 4) if k != "store_id" else v) for k, v in s.items()} for s in per_store],
                "focus_store": focus, "all_stores_down": all_down, "folded": []},
        ))
    return out


# ---- store issues (More bills, with cause merging) --------------------------------
def store_issues(m, sf, folded_cities, city_by_name) -> list[dict]:
    w, sp, st = m.windows, m.salespeople, m.stores
    out = []
    for _, s in st[st.established].iterrows():
        sid, folded = s.store_id, s.city in folded_cities
        comps = []
        if s.conv_level:
            comps.append(_conv_comp(s, w))
        if s.busy_conv_level:
            comps.append(_busy_comp(s, w))
        if s.ipb_level:
            comps.append(_ipb_comp(s, w))
        if folded:   # METRICS §4: folded into the city slowdown
            city_by_name[s.city]["facts"]["folded"] += [f"{sid}: {c['what']} ({c['level']})" for c in comps]
            comps = []
        leavers = sp[(sp.store_id == sid) & sp.leaver].sort_values("share_store_bills_b", ascending=False)
        shifts = sp[(sp.store_id == sid) & sp.missing_shifts].sort_values("off_r", ascending=False)
        peers = st[st.established & (st.state == s.state) & (st.store_id != sid)].store_id.tolist()
        base = dict(area_manager_id=s.area_manager_id, city=s.city, store_id=sid, lever="More bills")

        if len(leavers):
            out.append(_leaver_issue(m, sf, s, leavers, comps, base))
        elif len(shifts):
            out.append(_shifts_issue(m, sf, s, shifts, comps, base))
        else:
            bill_comps = [c for c in comps if c["kind"] in ("conversion", "busy_days")]
            if bill_comps:
                out.append(_conversion_issue(m, sf, s, bill_comps, peers, base))
            # IPB with no cause stays a Bigger-baskets issue (baskets.py)
    return out


def _evidence_of(comps):
    return [e for c in comps for e in c["evidence"]]


def _leaver_issue(m, sf, s, leavers, comps, base):
    w, sid = m.windows, s.store_id
    lv = leavers.iloc[0]
    sp_store = m.salespeople[m.salespeople.store_id == sid]
    is_top = lv.bills_b >= sp_store.bills_b.max()
    who = f"Top seller {lv['name']}" if is_top else f"{lv['name']} ({pct(lv.share_store_bills_b, 0)} of store bills)"
    level, lead = _merge(comps)
    gaps = " and ".join(c["what"] for c in comps if c["level"])
    evidence = [
        ev(f"{lv['name']}'s share of store bills, {span(w.baseline)}", pct(lv.share_store_bills_b), None),
        ev(f"{lv['name']}'s last bill", day(lv.last_bill), f"last shift {day(lv.last_present)}" if pd.notna(lv.last_present) else None),
    ] + _evidence_of(comps)
    ids = leavers.sp.tolist()
    return make_issue(
        id=f"{sid}:leaver:{'+'.join(ids)}", level=level or "watch", type="leaver", scope="store", salesperson_ids=ids,
        title=f"{who} has not billed since {day(lv.last_bill)}",
        cause=(f"A good salesperson has left the floor: {lv['name']} made {pct(lv.share_store_bills_b, 0)} of the store's bills "
               f"in {span(w.baseline)} and hasn't billed since {day(lv.last_bill)}"
               + (f"; since then {gaps}." if gaps else "; the store's numbers have not dropped significantly yet.")),
        rs_week=lead["rs"] if lead else 0, z=lead["z"] if lead else None, evidence=evidence,
        measure=lead["measure"] if lead else {"metric": "store_conv", "store_id": sid, "expected": f(s.conv_exp), "actual": f(s.conv_r)},
        facts=sf.base(sid, exclude=ids) | {"leavers": [
            {"salesperson_id": r.sp, "name": r["name"], "last_bill": iso(r.last_bill), "last_present": iso(r.last_present),
             "share_store_bills_baseline": f(r.share_store_bills_b)} for _, r in leavers.iterrows()]},
        components=[_comp_view(c) for c in comps], **base,
    )


def _shifts_issue(m, sf, s, shifts, comps, base):
    w, sid = m.windows, s.store_id
    level, lead = _merge(comps)
    stf = sf.staffing(sid)
    short = sf.short_on_weekends(sid)
    nm = names(shifts["name"].tolist())
    offs = "; ".join(f"{r['name']} off {pct(r.off_r, 0)} of days (was {pct(r.off_b, 0)})" for _, r in shifts.iterrows())
    evidence = [ev(f"{r['name']} off-rate, {span(w.shifts)}", f"{int(round(r.off_r * r.roster_days_r))} of {r.roster_days_r} days ({pct(r.off_r, 0)})",
                   f"{pct(r.off_b, 0)} in {span(w.baseline)}") for _, r in shifts.iterrows()]
    if stf["weekend_avg"] is not None:
        evidence.append(ev(f"Staff on the floor Sat / Sun, {span(w.recent)}", f"{num(stf['sat'], 1)} / {num(stf['sun'], 1)}",
                           f"Fri {num(stf['fri'], 1)}; weekends {num(stf['weekend_avg_baseline'], 1)} in {span(w.baseline)}"))
    evidence += _evidence_of(comps)
    busy = next((c for c in comps if c["kind"] == "busy_days" and c["level"]), None)
    tail = (f" On Sat/Sun only {num(stf['weekend_avg'], 1)} people are on the floor vs {num(stf['fri'], 1)} on Fridays"
            + (f", and {busy['what']}." if busy else ".")) if short else ""
    ids = shifts.sp.tolist()
    return make_issue(
        id=f"{sid}:missing_shifts", level=level or "watch", type="missing_shifts", scope="store", salesperson_ids=ids,
        title=f"{nm} {'is' if len(ids) == 1 else 'are'} missing shifts" + (" — weekends are short-staffed" if short else ""),
        cause=f"Missing shifts leave too few people on the floor on busy days: {offs}.{tail}",
        rs_week=lead["rs"] if lead else 0, z=lead["z"] if lead else None, evidence=evidence,
        measure=lead["measure"] if lead else {"metric": "store_conv", "store_id": sid, "expected": f(s.conv_exp), "actual": f(s.conv_r)},
        facts=sf.base(sid) | {"short_on_weekends": short, "missing_shifts": [
            {"salesperson_id": r.sp, "name": r["name"], "off_rate": f(r.off_r), "off_rate_baseline": f(r.off_b),
             "roster_days": int(r.roster_days_r)} for _, r in shifts.iterrows()]},
        components=[_comp_view(c) for c in comps], **base,
    )


def _conversion_issue(m, sf, s, comps, peers, base):
    """No leaver / missing shifts. Busy-day drop with thin weekend staffing → understaffed
    busy days; otherwise walk-ins steady but fewer buying."""
    w, sid = m.windows, s.store_id
    level, lead = _merge(comps)
    stf, short = sf.staffing(sid), sf.short_on_weekends(sid)
    foot = sf.footfall_vs_peers(sid, peers)
    busy_led = lead["kind"] == "busy_days"
    evidence = _evidence_of(comps)
    if foot is not None:
        evidence.append(ev("Walk-ins per day vs same-state stores (change since baseline)", pct(foot), "0% = moved with peers"))
    if busy_led and short:
        typ = "understaffed_busy_days"
        evidence.append(ev(f"Staff on the floor Sat / Sun, {span(w.recent)}", f"{num(stf['sat'], 1)} / {num(stf['sun'], 1)}", f"Fri {num(stf['fri'], 1)}"))
        title = f"Too few people on the floor at weekends in {sid}"
        cause = (f"Too few on the floor on busy days: {num(stf['weekend_avg'], 1)} staff on Sat/Sun vs {num(stf['fri'], 1)} on Fridays, "
                 f"and {lead['what']}.")
    else:
        typ = "busy_days" if busy_led else "conversion"
        steady = foot is None or foot > -0.10
        when = "on Sat/Sun " if busy_led else ""
        title = f"Fewer walk-ins are buying {when}at {sid}"
        cause = ((f"Walk-ins are steady but fewer of them buy {when}" if steady else f"Fewer walk-ins buy {when}(and walk-ins are down {pct(-foot, 0)} vs peers) ")
                 .rstrip() + f": {lead['what']}.")
    return make_issue(
        id=f"{sid}:{typ}", level=level, type=typ, scope="store", salesperson_ids=[], title=title, cause=cause,
        rs_week=lead["rs"], z=lead["z"], evidence=evidence, measure=lead["measure"],
        facts=sf.base(sid) | {"short_on_weekends": short, "footfall_vs_peers": f(foot)},
        components=[_comp_view(c) for c in comps], **base,
    )
