"""Store Coach CLI — the daily run.

    python run.py                              # latest morning (first weekday after the data ends) → site/data/
    python run.py --as-of 2026-11-02           # one morning → site/data/runs/2026-11-02.json + index.json
    python run.py --replay-from 2026-10-01     # every morning from 1 Oct to the latest (or --as-of)
    python run.py --as-of 2026-11-02 --summary # print the Step 2a metrics summary instead

A run "as of D" sees only data dated <= D-1. No state is saved between runs: each
morning's AM brief replays its own week from Monday.
"""
from __future__ import annotations

import argparse
import sys
import time

import pandas as pd

from storecoach.coach import Coach
from storecoach.load import load
from storecoach.metrics import compute
from storecoach.prep import prepare
from storecoach.render import SITE_DATA, write_index, write_run

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)


def pct(x, d=1):
    return "—" if pd.isna(x) else f"{x * 100:.{d}f}%"


def rs(x):
    return "—" if pd.isna(x) else f"₹{x:,.0f}"


def num(x, d=2):
    return "—" if pd.isna(x) else f"{x:.{d}f}"


def summary(m) -> str:
    w = m.windows
    out = [
        f"Store Coach metrics — as of {m.as_of:%a %d %b %Y} (data through {m.data_through:%Y-%m-%d})",
        f"  Recent {w.recent} | Baseline {w.baseline} | Salesperson {w.salesperson} | Shifts {w.shifts}",
        f"  Activity {w.activity} | Year ago {w.year_ago} | Repeat cohort {w.cohort}",
        f"  Placeholder customers: {', '.join(m.placeholders) or 'none'}",
        "",
        "STORES (Recent vs peer-relative expected)",
    ]
    s = m.stores
    t = pd.DataFrame({
        "store": s.store_id, "est": s.established.map({True: "", False: "NEW"}),
        "bills": s.bills_r.astype(int), "conv": s.conv_r.map(pct), "exp": s.conv_exp.map(pct), "z": s.conv_z.map(lambda v: num(v)),
        "₹/wk": s.conv_rs_week.map(rs), "lvl": s.conv_level.fillna(""),
        "busy": s.busy_conv_r.map(pct), "b_exp": s.busy_conv_exp.map(pct), "b_z": s.busy_conv_z.map(lambda v: num(v)), "b_lvl": s.busy_conv_level.fillna(""),
        "ipb": s.ipb_r.map(num), "i_exp": s.ipb_exp.map(num), "i_z": s.ipb_z.map(lambda v: num(v)), "i_lvl": s.ipb_level.fillna(""),
        "atv": s.atv_r.map(rs), "disc": s.disc_pct_r.map(pct), "repeat": s.rep_rate.map(pct), "bad": s.bad_days_r,
        "cause": s.cause.fillna(""),
    })
    out.append(t.to_string(index=False))

    c = m.cities
    out += ["", "CITIES (Recent vs Year ago, vs all other cities)"]
    out.append(pd.DataFrame({
        "city": c.city, "rpf": c.rpf_r.map(rs), "rpf_exp": c.rpf_exp.map(rs), "rpf_gap": c.rpf_gap_pct.map(pct),
        "z": c.rpf_z.map(num), "conv_gap": c.conv_gap_pct.map(pct), "ipb_gap": c.ipb_gap_pct.map(pct),
        "atv_gap": c.atv_gap_pct.map(pct), "₹/wk": c.rpf_rs_week.map(rs), "lvl": c.city_level.fillna(""),
    }).to_string(index=False))

    sp = m.salespeople
    out += ["", "SALESPERSON FLAGS (issue / watch / role model / leaver / missing shifts)"]
    rows = []
    for _, r in sp.iterrows():
        tag = f"{r.sp} {r['name']:<12} {r.store_id}"
        if r.leaver:
            rows.append(f"  LEAVER         {tag}  {pct(r.share_store_bills_b)} of Baseline store bills, last bill {r.last_bill:%d %b}")
        if r.missing_shifts:
            rows.append(f"  MISSING SHIFTS {tag}  off-rate {pct(r.off_r, 0)} ({r.roster_days_r} days) vs {pct(r.off_b, 0)} Baseline")
        if r.disc_level:
            rows.append(f"  DISCOUNT       {tag}  {pct(r.disc_pct, 2)} vs peers {pct(r.peer_disc_pct, 2)}  {rs(r.disc_rs_week)}/wk  [{r.disc_level}]")
        for tag2, lab in (("shw", "SHERWANI ADD-ON"), ("kur", "JACKET ADD-ON  ")):
            lv = r[f"{tag2}_level"]
            if lv:
                n, k = int(r[f"{tag2}_n"]), int(r[f"{tag2}_k"])
                rows.append(f"  {lab} {tag}  {k}/{n} vs peers {pct(r[f'{tag2}_peer_rate'], 0)}  z {num(r[f'{tag2}_z'])}  {rs(r[f'{tag2}_rs_week'])}/wk  [{lv}]")
        if r.rep_level or r.role_model:
            lab = "ROLE MODEL     " if r.role_model else "LOW REPEAT     "
            rows.append(f"  {lab}{tag}  {int(r.rep_k)}/{int(r.rep_n)} = {pct(r.rep_rate)} vs peers {pct(r.rep_peer_rate)}  z {num(r.rep_z)}"
                        + (f"  {rs(r.rep_rs_week)}/wk  [{r.rep_level}]" if r.rep_level else ""))
    out += rows

    cat = m.categories[m.categories.level.notna()].sort_values("rs_week", ascending=False)
    out += ["", "CATEGORY AVOIDANCE (issue / watch)"]
    for _, r in cat.iterrows():
        out.append(f"  {r.sp} {r['name']:<12} {r.store_id} {r.category:<12} {int(r.qty)} vs expected {r.expected:.1f}  z {num(r.z)}  {rs(r.rs_week)}/wk  [{r.level}]")

    st = m.staffing.set_index("store_id")
    out += ["", "STAFF ON FLOOR (avg present, Recent window)"]
    out.append(st.round(1).to_string())

    g = m.card_gaps
    top = g[g.gap_rs_week > 0].sort_values("gap_rs_week", ascending=False).groupby("sp").head(1)
    n_active = int(m.salespeople.active.sum())
    out += ["", f"CARD GAPS: {top.sp.nunique()} of {n_active} active salespeople have a ₹ gap vs a same-store peer. Top 10:"]
    for _, r in top.head(10).iterrows():
        out.append(f"  {r.sp} {r['name']:<12} {r.store_id} {r.behaviour:<18} own {num(r.value, 3)} vs {r.best_peer} {num(r.best_value, 3)}  {rs(r.gap_rs_week)}/wk")

    bd = m.bad_days
    out += ["", f"BAD FOOTFALL DAYS: {len(bd)}"]
    for st_id, gg in bd.groupby("store_id"):
        out.append(f"  {st_id}: {gg.date.min():%Y-%m-%d} → {gg.date.max():%Y-%m-%d} ({len(gg)} days)")
    return "\n".join(out)


def latest_morning(prep) -> pd.Timestamp:
    """First weekday after the last day of data (data ends Sat 31 Oct 2026 → Mon 2 Nov, D6)."""
    d = prep.data_end + pd.Timedelta(days=1)
    while d.dayofweek >= 5:
        d += pd.Timedelta(days=1)
    return d


def main():
    ap = argparse.ArgumentParser(description="Store Coach daily run")
    ap.add_argument("--as-of", default=None, help="morning of the run (sees data up to the day before); default = latest")
    ap.add_argument("--replay-from", default=None, help="also write every morning from this date up to --as-of")
    ap.add_argument("--out", default=SITE_DATA, help="output folder (default site/data)")
    ap.add_argument("--summary", action="store_true", help="print the metrics summary for --as-of instead of writing JSON")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    prep = prepare(load())
    as_of = pd.Timestamp(args.as_of) if args.as_of else latest_morning(prep)
    t1 = time.time()
    if args.summary:
        m = compute(prep, as_of)
        print(summary(m))
        print(f"\nload+prep {t1 - t0:.1f}s, metrics {time.time() - t1:.1f}s")
        return
    days = pd.date_range(args.replay_from, as_of) if args.replay_from else [as_of]
    coach = Coach(prep)
    for D in days:
        run = coach.build(D)
        write_run(run, args.out)
        n = run["counts"]
        today = ", ".join(f"{x['city']}:{x['today_type']}" for x in run["managers"])
        print(f"{D:%a %Y-%m-%d}  {n['issues']} issues, {n['watch']} watch, {len(run['cards'])} cards  |  {today}")
    write_index(f"{as_of:%Y-%m-%d}", args.out)
    print(f"wrote {len(days)} run(s) to {args.out}  (load+prep {t1 - t0:.1f}s, runs {time.time() - t1:.1f}s)")

if __name__ == "__main__":
    main()
