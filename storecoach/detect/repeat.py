"""More repeat: low-repeat salespeople (merged per store) and named role models
(METRICS §4: z ≤ −2.5 / z ≥ +2.5 vs same-store peers, ≥ 50 cohort customers).

Role models are also named for add-ons when someone is z ≥ +2.5 above their
same-store peers ("or who attach well", PLAN §1).
"""
from __future__ import annotations

from .baskets import _salesperson_issue
from .common import Z_ROLE_DEFAULT, ev, f, group_components, pct, span


def _role_peer(m, sid, exclude):
    """Best active repeat peer in the same store: a named role model if there is one."""
    s = m.salespeople
    x = s[(s.store_id == sid) & s.active & (s.rep_n >= 50) & ~s.sp.isin(exclude)]
    if x.empty:
        return None
    rm = x[x.role_model]
    r = (rm if len(rm) else x).sort_values("rep_rate", ascending=False).iloc[0]
    return {"salesperson_id": r.sp, "name": r["name"], "value": f(r.rep_rate), "role_model": bool(r.role_model)}


def low_repeat_issues(m, store_meta) -> list[dict]:
    w, s = m.windows, m.salespeople
    comps = []
    for _, r in s[s.rep_level.notna()].iterrows():
        comps.append({
            "sp": r.sp, "name": r["name"], "store_id": r.store_id, "level": r.rep_level, "z": r.rep_z, "rs": r.rep_rs_week,
            "what": f"{int(r.rep_k)} of {int(r.rep_n)} customers came back, {pct(r.rep_rate)} vs {pct(r.rep_peer_rate)} for others",
            "evidence": [ev(f"{r['name']}: customers who came back 30+ days later (first bill {span(w.cohort)})",
                            f"{int(r.rep_k)} of {int(r.rep_n)} ({pct(r.rep_rate)})", f"{pct(r.rep_peer_rate)} for others in the store")],
            "measure": {"metric": "sp_repeat", "salesperson_id": r.sp, "expected": f(r.rep_peer_rate), "actual": f(r.rep_rate),
                        "min_sample": "50 cohort customers"},
        })
    out = []
    for level, mem, watch in group_components(comps):
        sid = mem[0]["store_id"]
        ids = [c["sp"] for c in mem]
        peer = _role_peer(m, sid, ids)
        for c in mem:
            c["peer"] = peer
        nm = [c["name"] for c in mem]
        title = (f"{nm[0]}'s customers rarely come back" if len(nm) == 1
                 else f"Customers of {', '.join(nm[:-1])} and {nm[-1]} rarely come back")
        cause = "Customers don't come back: " + "; ".join(f"{c['name']} ({c['what']})" for c in mem) + "."
        if peer:
            cause += f" {peer['name']} in the same store gets {pct(peer['value'])} back."
        iss = _salesperson_issue(m, store_meta, "low_repeat", "More repeat", level, mem, watch, title, cause)
        iss["facts"]["role_model_peer"] = peer
        out.append(iss)
    return out


def role_models(m, store_meta, z_min=Z_ROLE_DEFAULT) -> list[dict]:
    s = m.salespeople
    out = []
    for _, r in s[s.role_model].sort_values("rep_z", ascending=False).iterrows():
        out.append({
            "salesperson_id": r.sp, "name": r["name"], "store_id": r.store_id, "area_manager_id": store_meta[r.store_id]["area_manager_id"],
            "metric": "Repeat rate", "value": pct(r.rep_rate), "store_value": pct(r.rep_peer_rate),
            "detail": f"{int(r.rep_k)} of {int(r.rep_n)} first-time customers came back 30+ days later; others in the store: {pct(r.rep_peer_rate)}",
            "z": round(float(r.rep_z), 2),
        })
    for tag, label, mn in (("shw", "Sherwani add-on rate", 5), ("kur", "Jacket add-on rate", 20)):
        ok = s.active & s.established & (s[f"{tag}_n"] >= mn) & (s[f"{tag}_z"] >= z_min)
        for _, r in s[ok].sort_values(f"{tag}_z", ascending=False).iterrows():
            out.append({
                "salesperson_id": r.sp, "name": r["name"], "store_id": r.store_id, "area_manager_id": store_meta[r.store_id]["area_manager_id"],
                "metric": label, "value": pct(r[f"{tag}_rate"]), "store_value": pct(r[f"{tag}_peer_rate"]),
                "detail": f"{int(r[f'{tag}_k'])} of {int(r[f'{tag}_n'])} bills; others in the store: {pct(r[f'{tag}_peer_rate'])}",
                "z": round(float(r[f"{tag}_z"]), 2),
            })
    return out
