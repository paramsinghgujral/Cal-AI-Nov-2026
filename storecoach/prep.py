"""Turn raw tables into analysis-ready tables, once per run.

Everything here is a fact about a single bill or a single store-day, so it does
not depend on the run date. Anything that looks across days (placeholder
customers, first bills, windows) is done per run in `metrics.context`, so a run
"as of" any morning only ever sees data up to the night before.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .load import Data

ADDON_CATS = ["Safa", "Mojari", "Mala"]
CATEGORIES = ["Sherwani", "Kurta Set", "Jacket", "Safa", "Mojari", "Mala", "Stole", "Indo-Western"]


@dataclass
class Prep:
    bills: pd.DataFrame       # one row per bill, with basket facts
    footfall: pd.DataFrame    # store x day, with bills and a bad-day flag
    roster: pd.DataFrame
    stores: pd.DataFrame
    people: pd.DataFrame
    managers: pd.DataFrame
    calendar: pd.DataFrame
    data_start: pd.Timestamp
    data_end: pd.Timestamp


def prepare(d: Data) -> Prep:
    lines = d.lines[~d.lines.is_packaging]
    per_bill = lines.groupby("bill_id").agg(
        items=("qty", "sum"), rev=("revenue", "sum"), disc=("discount", "sum"), mrpv=("mrp_value", "sum")
    )
    qty = lines.pivot_table(index="bill_id", columns="category", values="qty", aggfunc="sum", fill_value=0)
    rev = lines.pivot_table(index="bill_id", columns="category", values="revenue", aggfunc="sum", fill_value=0)
    qty = qty.reindex(columns=CATEGORIES, fill_value=0)
    rev = rev.reindex(columns=CATEGORIES, fill_value=0).add_prefix("rev_")

    b = d.bills.rename(columns={"bill_date": "date", "salesperson_id": "sp"})
    b = b.join(per_bill, on="bill_id").join(qty, on="bill_id").join(rev, on="bill_id")
    num = ["items", "rev", "disc", "mrpv"] + CATEGORIES + list(rev.columns)
    b[num] = b[num].fillna(0)
    b["rev_sq"] = b["rev"] ** 2
    b["items_sq"] = b["items"] ** 2
    b["shw"] = b["Sherwani"] > 0
    b["shw_acc"] = b["shw"] & (b[ADDON_CATS].sum(axis=1) > 0)
    b["kur"] = b["Kurta Set"] > 0
    b["kur_jkt"] = b["kur"] & (b["Jacket"] > 0)
    b["addon_rev"] = b[[f"rev_{c}" for c in ADDON_CATS]].sum(axis=1)  # safa + mojari + mala ₹ on the bill

    st = d.stores.merge(d.managers[["area_manager_id", "name"]].rename(columns={"name": "am_name"}), on="area_manager_id", how="left")
    b = b.merge(st[["store_id", "city", "state"]], on="store_id", how="left")

    f = d.footfall.merge(st[["store_id", "city", "state"]], on="store_id", how="left")
    daily = b.groupby(["store_id", "date"]).agg(bills=("bill_id", "size"), rev=("rev", "sum"), rev_sq=("rev_sq", "sum"))
    f = f.merge(daily.reset_index(), on=["store_id", "date"], how="left").fillna({"bills": 0, "rev": 0.0, "rev_sq": 0.0})
    # A camera that reads 0 (or fewer walk-ins than bills) is broken, not a quiet day.
    f["bad"] = (f.footfall <= 0) | (f.bills > f.footfall)
    f["weekend"] = f.date.dt.dayofweek >= 5

    return Prep(
        bills=b, footfall=f, roster=d.roster.copy(), stores=st, people=d.people.copy(), managers=d.managers.copy(),
        calendar=d.calendar.copy(), data_start=b.date.min(), data_end=b.date.max(),
    )
