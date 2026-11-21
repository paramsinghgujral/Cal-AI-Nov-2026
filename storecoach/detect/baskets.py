"""Bigger baskets: store IPB drop (no other cause), missing add-on pair, category
avoidance, high discount (METRICS §4).

Salesperson findings of the same kind in the same store merge into one issue
(METRICS §5 merging: same store + lever, ₹ = the largest gap). A salesperson's
low jacket (or safa/mojari/mala) share is folded into their add-on issue, since
it is the same habit seen twice.
"""
from __future__ import annotations

import pandas as pd

from .bills import _ipb_comp, _comp_view
from .common import (LEVEL_ORDER, cat_lc, component_view, plural, ev, f, group_components, make_issue, names, num, pct, rs, span, strongest)

ADDON = {
    "shw": {"label": "sherwani", "pair": "a safa, mojari or mala", "behaviour": "sherwani_addon", "cats": ("Safa", "Mojari", "Mala"),
            "bills": "sherwani bills with a safa/mojari/mala", "min": "5 sherwani bills"},
    "kur": {"label": "jacket", "pair": "a jacket", "behaviour": "jacket_addon", "cats": ("Jacket",),
            "bills": "kurta-set bills with a jacket", "min": "20 kurta-set bills"},
}


def _best_peer(m, sp, behaviour):
    g = m.card_gaps
    r = g[(g.sp == sp) & (g.behaviour == behaviour)]
    if r.empty or pd.isna(r.iloc[0].best_peer):
        return None
    r = r.iloc[0]
    return {"salesperson_id": r.best_peer, "name": r.best_peer_name, "value": f(r.best_value)}


def ipb_issues(m, skip_stores) -> list[dict]:
    w, out = m.windows, []
    g = m.card_gaps
    for _, s in m.stores[m.stores.ipb_level.notna()].iterrows():
        if s.store_id in skip_stores:
            continue
        c = _ipb_comp(s, w)
        low = g[(g.store_id == s.store_id) & (g.behaviour == "ipb") & (g.gap > 0)].sort_values("gap_rs_week", ascending=False).head(3)
        evidence = c["evidence"] + [ev("Average bill value", rs(s.atv_r), None)]
        out.append(make_issue(
            id=f"{s.store_id}:ipb_drop", level=c["level"], type="ipb_drop", lever="Bigger baskets", scope="store",
            area_manager_id=s.area_manager_id, city=s.city, store_id=s.store_id, salesperson_ids=[],
            title=f"Smaller baskets at {s.store_id}: {num(s.ipb_r)} items per bill vs {num(s.ipb_exp)} expected",
            cause=f"Customers are buying fewer items per bill than same-state stores' trend predicts ({pct(s.ipb_gap_pct)}).",
            rs_week=c["rs"], z=c["z"], evidence=evidence, measure=c["measure"],
            facts={"lowest_ipb": [{"salesperson_id": r.sp, "name": r["name"], "ipb": f(r.value, 3),
                                   "best_peer": r.best_peer_name, "best_ipb": f(r.best_value, 3)} for _, r in low.iterrows()]},
            components=[_comp_view(c)],
        ))
    return out


def _category_comps(m):
    w, c = m.windows, m.categories
    out = []
    for _, r in c[c.level.notna()].iterrows():
        out.append({
            "sp": r.sp, "name": r["name"], "store_id": r.store_id, "level": r.level, "z": r.z, "rs": r.rs_week,
            "category": r.category, "short": f"{int(r.qty)} {plural(r.category, int(r.qty))} vs {r.expected:.0f} expected",
            "what": f"{int(r.qty)} {plural(r.category, int(r.qty))} sold vs {r.expected:.0f} expected at others' share",
            "evidence": [ev(f"{r['name']}: {cat_lc(r.category)} units sold, {span(w.salesperson)}", f"{int(r.qty)} of {int(r['items'])} items ({pct(r.share)})",
                            f"{r.expected:.0f} expected at others' share ({pct(r.peer_share)})")],
            "measure": {"metric": "sp_category_share", "salesperson_id": r.sp, "category": r.category,
                        "expected": f(r.peer_share), "actual": f(r.share), "min_sample": "5 expected units"},
            "peer": _best_peer(m, r.sp, f"share:{r.category}"),
        })
    return out


def addon_and_category_issues(m, store_meta) -> list[dict]:
    w, sp = m.windows, m.salespeople
    cats = _category_comps(m)
    addon = []
    for _, r in sp.iterrows():
        for tag, a in ADDON.items():
            lv = r[f"{tag}_level"]
            if not lv:
                continue
            n, k = int(r[f"{tag}_n"]), int(r[f"{tag}_k"])
            c = {
                "sp": r.sp, "name": r["name"], "store_id": r.store_id, "level": lv, "z": r[f"{tag}_z"], "rs": r[f"{tag}_rs_week"],
                "addon": a["label"], "short": f"{a['label']} add-on {k}/{n}",
                "what": f"{a['label']} add-on {k}/{n} vs {pct(r[f'{tag}_peer_rate'], 0)} for others",
                "evidence": [ev(f"{r['name']}: {a['bills']}, {span(w.salesperson)}", f"{k} of {n} ({pct(r[f'{tag}_rate'], 0)})",
                                f"{pct(r[f'{tag}_peer_rate'], 0)} for others in the store")],
                "measure": {"metric": f"sp_{a['label']}_addon", "salesperson_id": r.sp, "expected": f(r[f"{tag}_peer_rate"]),
                            "actual": f(r[f"{tag}_rate"]), "min_sample": a["min"]},
                "peer": _best_peer(m, r.sp, a["behaviour"]),
            }
            # same habit seen as a low category share → fold it in
            same = [x for x in cats if x["sp"] == r.sp and x["category"] in a["cats"]]
            for x in same:
                c["evidence"] += x["evidence"]
                c["short"] += f", {x['short']}"
                c["what"] += f", {x['what']}"
                if LEVEL_ORDER.get(x["level"], 0) > LEVEL_ORDER.get(c["level"], 0) or (x["level"] == c["level"] and x["rs"] > c["rs"]):
                    # the category gap is the stronger signal: it leads level, ₹, z and follow-up
                    c.update(level=x["level"], z=x["z"], rs=x["rs"], measure=x["measure"])
                cats.remove(x)
            addon.append(c)

    out = []
    for level, mem, watch in group_components(addon):
        sid = mem[0]["store_id"]
        by_sp = {}
        for c in mem:
            by_sp.setdefault(c["sp"], []).append(c)
        parts = [f"{cs[0]['name']} ({'; '.join(c['what'] for c in cs)})" for cs in by_sp.values()]
        nm = [cs[0]["name"] for cs in by_sp.values()]
        if len(by_sp) == 1:
            what = "; ".join(c["short"] for c in mem)
            title = f"{nm[0]} rarely adds the obvious pair ({what})"
        else:
            title = f"{names(nm)} rarely add the obvious pair"
        out.append(_salesperson_issue(m, store_meta, "addon", "Bigger baskets", level, mem, watch, title,
                                      "Not adding the obvious pair: " + "; ".join(parts) + "."))

    for level, mem, watch in group_components(cats):
        nm = list(dict.fromkeys(c["name"] for c in mem))
        if len(mem) == 1:
            title = f"{nm[0]} rarely sells {plural(mem[0]['category'])} ({mem[0]['short']})"
        else:
            title = f"{names(nm)} rarely sell some categories the store's customers buy"
        out.append(_salesperson_issue(m, store_meta, "category", "Bigger baskets", level, mem, watch, title,
                                      "Avoiding a category the store's customers buy: "
                                      + "; ".join(f"{c['name']} ({c['what']})" for c in mem) + "."))
    return out


def discount_issues(m, prep, store_meta) -> list[dict]:
    w, sp = m.windows, m.salespeople
    comps = []
    for _, r in sp[sp.disc_level.notna()].iterrows():
        comps.append({
            "sp": r.sp, "name": r["name"], "store_id": r.store_id, "level": r.disc_level, "z": None, "rs": r.disc_rs_week,
            "what": f"discount {pct(r.disc_pct, 1)} vs {pct(r.peer_disc_pct, 1)} for others",
            "evidence": [ev(f"{r['name']}: discount off MRP, {span(w.salesperson)}", pct(r.disc_pct, 2),
                            f"{pct(r.peer_disc_pct, 2)} for others in the store")]
                        + _monthly_discount(m, prep.bills, r.sp),
            "measure": {"metric": "sp_discount", "salesperson_id": r.sp, "expected": f(r.peer_disc_pct), "actual": f(r.disc_pct),
                        "min_sample": "30 bills"},
            "peer": _best_peer(m, r.sp, "discount"),
            "ratio": r.disc_pct / r.peer_disc_pct if r.peer_disc_pct else None,
        })
    out = []
    for level, mem, watch in group_components(comps):
        nm = [c["name"] for c in mem]
        lo, hi = min(c["ratio"] for c in mem), max(c["ratio"] for c in mem)
        x = f"{lo:.0f}×" if round(lo) == round(hi) else f"{lo:.0f}–{hi:.0f}×"
        out.append(_salesperson_issue(
            m, store_meta, "discount", "Bigger baskets", level, mem, watch,
            f"{names(nm)} {'gives' if len(nm) == 1 else 'give'} {x} the store's usual discount",
            "Discounts well above the store norm: " + "; ".join(f"{c['name']} ({c['what']})" for c in mem) + "."))
    return out


def _monthly_discount(m, bills, sp_id):
    """Discount % by month over the last 6 months — shows when the jump started."""
    b = bills
    last = m.as_of - pd.Timedelta(days=1)
    x = b[(b.sp == sp_id) & (b.date > last - pd.DateOffset(months=6)) & (b.date <= last)]
    if x.empty:
        return []
    g = x.groupby(x.date.dt.to_period("M"))[["disc", "mrpv"]].sum()
    series = ", ".join(f"{p.strftime('%b')} {pct(r.disc / r.mrpv, 1)}" for p, r in g.iterrows() if r.mrpv > 0)
    return [ev("Discount by month", series, None)]


def _salesperson_issue(m, store_meta, typ, lever, level, mem, watch, title, cause):
    sid = mem[0]["store_id"]
    meta = store_meta[sid]
    rs_week, z = strongest(mem)
    lead = max(mem, key=lambda c: c["rs"])
    ids = list(dict.fromkeys(c["sp"] for c in mem))
    evidence = [e for c in mem for e in c["evidence"]]
    facts = {"peers": {c["sp"]: c.get("peer") for c in mem},
             "also_watch": [f"{c['name']}: {c['what']}" for c in watch]}
    return make_issue(
        id=f"{sid}:{typ}", level=level, type=typ, lever=lever, scope="salesperson",
        area_manager_id=meta["area_manager_id"], city=meta["city"], store_id=sid, salesperson_ids=ids,
        title=title, cause=cause, rs_week=rs_week, z=z, evidence=evidence, measure=lead["measure"], facts=facts,
        components=[component_view(c) for c in mem],
    )
