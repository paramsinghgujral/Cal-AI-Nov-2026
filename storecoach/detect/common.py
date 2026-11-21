"""Shared helpers for the detectors: formatting, issue dicts, grouping."""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

LEVEL_ORDER = {"issue": 2, "watch": 1}
Z_ROLE_DEFAULT = 2.5   # METRICS §4 role model


# ---- formatting -------------------------------------------------------------
def isnum(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x)) and not pd.isna(x)


def pct(x, d=1) -> str:
    return f"{x * 100:.{d}f}%" if isnum(x) else "—"


def rs(x) -> str:
    return f"₹{x:,.0f}" if isnum(x) else "—"


def num(x, d=2) -> str:
    return f"{x:.{d}f}" if isnum(x) else "—"


def day(ts) -> str:
    return f"{ts.day} {ts:%b}" if isnum(ts) else "—"


def iso(ts):
    return f"{ts:%Y-%m-%d}" if isnum(ts) else None


def span(win) -> str:
    """'3 May – 6 Sep' for a metrics Window."""
    return f"{day(win.start)} – {day(win.end)}"


def zf(z):
    return round(float(z), 2) if isnum(z) else None


def rupees(x) -> int:
    return int(round(float(x))) if isnum(x) and x > 0 else 0


def names(xs) -> str:
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


SINGULAR = {"Kurta Set": "kurta set", "Indo-Western": "Indo-Western outfit"}


def plural(category: str, n=None) -> str:
    one = SINGULAR.get(category, category.lower())
    return one if n == 1 else one + "s"


def ev(label, value, baseline=None) -> dict:
    return {"label": label, "value": value, "baseline": baseline}


def f(x, d=4):
    """Plain float for JSON (None for NaN)."""
    return round(float(x), d) if isnum(x) else None


# ---- issue dict -------------------------------------------------------------
def make_issue(*, id, level, type, lever, scope, area_manager_id, city, store_id, salesperson_ids,
               title, cause, rs_week, z, evidence, measure, facts, components=None) -> dict:
    """Contract fields (PLAN §3 + D18) except rank/action text, which Step 5 adds."""
    return {
        "id": id, "level": level, "type": type, "lever": lever, "scope": scope,
        "area_manager_id": area_manager_id, "city": city, "store_id": store_id,
        "salesperson_id": salesperson_ids[0] if salesperson_ids else None,
        "salesperson_ids": list(salesperson_ids),
        "title": title, "cause": cause,
        "rupees_at_stake_week": rupees(rs_week), "z": zf(z),
        "evidence": evidence, "measure": measure, "facts": facts,
        "components": components or [],
        "rank": None, "action": None, "first_raised": None,   # Step 5
    }


def top_level(levels) -> str | None:
    levels = [l for l in levels if l]
    return max(levels, key=LEVEL_ORDER.get) if levels else None


def group_components(comps, key=lambda c: c["store_id"]):
    """Group salesperson components by store. Within a group, Issue members form the
    issue; Watch members join it as 'also watch' notes. A group with no Issue member
    becomes one Watch item. Yields (level, members, also_watch)."""
    groups = defaultdict(list)
    for c in comps:
        groups[key(c)].append(c)
    for k, cs in groups.items():
        issue = sorted([c for c in cs if c["level"] == "issue"], key=lambda c: -c["rs"])
        watch = sorted([c for c in cs if c["level"] == "watch"], key=lambda c: -c["rs"])
        if issue:
            yield "issue", issue, watch
        elif watch:
            yield "watch", watch, []


def strongest(members):
    """Merged ₹ is the largest gap, never the sum (METRICS §5); z of that member."""
    best = max(members, key=lambda c: (c["rs"], -(c["z"] or 0)))
    return best["rs"], best["z"]


def component_view(c) -> dict:
    """JSON-safe summary of one merged member (for Step 5 wording and follow-up)."""
    return {k: c[k] for k in ("sp", "name", "level", "what", "measure") if k in c} | {
        "rupees_at_stake_week": rupees(c["rs"]), "z": zf(c["z"])}
