"""Load the Manyavar data pack into typed pandas DataFrames.

IDs stay as text. Packaging lines are kept in `lines` but flagged, so every
metric can drop them explicitly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")


def _csv(data_dir: str, name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(data_dir, f"{name}.csv"), dtype=str, keep_default_na=False)


@dataclass
class Data:
    stores: pd.DataFrame
    managers: pd.DataFrame
    items: pd.DataFrame
    people: pd.DataFrame
    roster: pd.DataFrame
    footfall: pd.DataFrame
    bills: pd.DataFrame
    lines: pd.DataFrame
    calendar: pd.DataFrame


def load(data_dir: str = DEFAULT_DIR) -> Data:
    stores = _csv(data_dir, "stores")
    for c in ("size_sqft", "stock_capacity_units"):
        stores[c] = pd.to_numeric(stores[c], errors="coerce")
    stores["opened_on"] = pd.to_datetime(stores["opened_on"], errors="coerce")

    managers = _csv(data_dir, "area_managers")
    managers["max_alerts_per_week"] = pd.to_numeric(managers["max_alerts_per_week"], errors="coerce").fillna(5).astype(int)

    items = _csv(data_dir, "items")
    for c in ("mrp", "cost_price"):
        items[c] = pd.to_numeric(items[c], errors="coerce")
    items["is_packaging"] = items["is_packaging"].eq("1")

    people = _csv(data_dir, "salespeople")
    people["join_date"] = pd.to_datetime(people["join_date"], errors="coerce")

    roster = _csv(data_dir, "roster_daily")
    roster["date"] = pd.to_datetime(roster["date"], errors="coerce")

    footfall = _csv(data_dir, "footfall_daily")
    footfall["date"] = pd.to_datetime(footfall["date"], errors="coerce")
    footfall["footfall"] = pd.to_numeric(footfall["footfall"], errors="coerce")

    bills = _csv(data_dir, "bills")
    bills["bill_date"] = pd.to_datetime(bills["bill_date"], errors="coerce")

    lines = _csv(data_dir, "bill_lines")
    for c in ("qty", "mrp", "selling_price"):
        lines[c] = pd.to_numeric(lines[c], errors="coerce")
    lines = lines.merge(items[["sku_id", "style_id", "category", "is_packaging"]], on="sku_id", how="left")
    lines["is_packaging"] = lines["is_packaging"].fillna(False).astype(bool)
    lines["revenue"] = lines["qty"] * lines["selling_price"]
    lines["discount"] = lines["qty"] * (lines["mrp"] - lines["selling_price"])
    lines["mrp_value"] = lines["qty"] * lines["mrp"]

    calendar = _csv(data_dir, "calendar")
    calendar["date"] = pd.to_datetime(calendar["date"], errors="coerce")
    calendar["is_wedding_date"] = calendar["is_wedding_date"].eq("1")

    return Data(stores, managers, items, people, roster, footfall, bills, lines, calendar)
