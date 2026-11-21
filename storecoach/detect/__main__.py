"""Print the detected issues for one morning.

    python -m storecoach.detect --as-of 2026-11-02 [--watch] [--check]
"""
from __future__ import annotations

import argparse
import sys
import time

from ..load import load
from ..metrics import compute
from ..prep import prepare
from . import detect


def show(d, prep, watch=False) -> str:
    out = [f"Store Coach detections — as of {d.as_of}"]
    n_i = sum(i["level"] == "issue" for i in d.issues)
    out.append(f"  {n_i} issues, {len(d.issues) - n_i} watch items, {len(d.role_models)} role models, {len(d.data_issues)} data issues")
    for _, am in prep.managers.iterrows():
        items = [i for i in d.for_manager(am.area_manager_id) if watch or i["level"] == "issue"]
        out += ["", f"== {am.area_manager_id} {am['name']} ({am.city}) =="]
        for i in items:
            out.append(f"  [{i['level']:<5}] ₹{i['rupees_at_stake_week']:>7,}/wk  z {i['z'] if i['z'] is not None else '—':>6}  "
                       f"{i['lever']:<14} {i['id']}")
            out.append(f"           {i['title']}")
            if i["level"] == "issue":
                out.append(f"           cause: {i['cause']}")
                for e in i["evidence"]:
                    out.append(f"             · {e['label']}: {e['value']}" + (f"  (vs {e['baseline']})" if e["baseline"] else ""))
                if i["facts"].get("folded"):
                    out.append(f"             folded: {'; '.join(i['facts']['folded'])}")
                if i["facts"].get("also_watch"):
                    out.append(f"             also watch: {'; '.join(i['facts']['also_watch'])}")
    out += ["", "ROLE MODELS"]
    out += [f"  {r['salesperson_id']} {r['name']:<14} {r['store_id']}  {r['metric']}: {r['value']} vs {r['store_value']}  (z {r['z']})"
            for r in d.role_models]
    out += ["", "DATA ISSUES"]
    out += [f"  {x['type']:<22} {x['store_id'] or '':<7} {x['dates']}  {x['detail']}" for x in d.data_issues]
    return "\n".join(out)


def check_findings(d) -> list[tuple[str, bool]]:
    """PLAN §4 findings F1–F7 (as of 2026-11-02) + the false alarms Step 4 must avoid."""
    iss = [i for i in d.issues if i["level"] == "issue"]
    by_id = {i["id"]: i for i in iss}
    has = lambda typ, sid, sp=None: any(i["type"] == typ and i["store_id"] == sid and (sp is None or sp in i["salesperson_ids"]) for i in iss)
    rm = {r["salesperson_id"] for r in d.role_models if r["metric"] == "Repeat rate"}
    dt = {(x["type"], x["store_id"]) for x in d.data_issues}
    return [
        ("F1 LKO-02 leaver SP1018 (cause: leaver)", "LKO-02:leaver:SP1018" in by_id),
        ("F2 BLR-03 missing shifts SP1141+SP1142, weekends short", has("missing_shifts", "BLR-03", "SP1141") and has("missing_shifts", "BLR-03", "SP1142")
         and by_id.get("BLR-03:missing_shifts", {}).get("facts", {}).get("short_on_weekends", False)),
        ("F3 Mysuru city slowdown, no MYS store bills/IPB alerts", "Mysuru:city_slowdown" in by_id
         and not any(i["store_id"] in ("MYS-01", "MYS-02") and i["type"] in ("conversion", "busy_days", "ipb_drop", "understaffed_busy_days") for i in d.issues)),
        ("F4 PAT-01 discount SP1064+SP1065", has("discount", "PAT-01", "SP1064") and has("discount", "PAT-01", "SP1065")),
        ("F5 add-on SP1128 BLR-02 + SP1083 PAT-02", has("addon", "BLR-02", "SP1128") and has("addon", "PAT-02", "SP1083")),
        ("F6 role model SP1110; low repeat SP1114, SP1120, SP1072", "SP1110" in rm and has("low_repeat", "BLR-01", "SP1114")
         and has("low_repeat", "BLR-01", "SP1120") and has("low_repeat", "PAT-01", "SP1072")),
        ("F7 data: PAT-03 camera, C99999999, BLR-05 new", ("camera_zero", "PAT-03") in dt and ("placeholder_customer", None) in dt and ("new_store", "BLR-05") in dt),
        ("no alerts for BLR-05", not any(i["store_id"] == "BLR-05" for i in d.issues)),
        ("no Mysuru sherwani alerts", not any(i["city"] == "Mysuru" and "herwani" in i["title"] for i in d.issues)),
        ("no festival/company-wide footfall flagged (25 Oct)", not any(x["type"].startswith("footfall_") and x["dates"] == "2026-10-25" for x in d.data_issues)),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-11-02")
    ap.add_argument("--watch", action="store_true", help="also list watch items")
    ap.add_argument("--check", action="store_true", help="check findings F1–F7 (as of 2026-11-02)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    prep = prepare(load())
    d = detect(compute(prep, a.as_of), prep)
    print(show(d, prep, a.watch))
    if a.check:
        res = check_findings(d)
        print("\nFINDINGS CHECK")
        for name, ok in res:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"  {sum(ok for _, ok in res)}/{len(res)} pass")
    print(f"\n{time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
