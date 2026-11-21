"""Step 4 — issue detectors.

    from storecoach.detect import detect
    d = detect(m, prep)      # m = metrics.compute(prep, as_of)
    d.issues        list of issue dicts, level "issue" first, then "watch"; each sorted by ₹/week
    d.role_models   named role models (repeat z ≥ +2.5; add-on z ≥ +2.5)
    d.data_issues   Data panel rows (never sent to AMs)

Issue dicts follow the output contract (PLAN §3, D18) minus `rank`, `action` and
`first_raised`, which Step 5 fills. Extra keys for Step 5: `type`, `z`,
`area_manager_id`, `city`, `salesperson_ids`, `measure` (what the follow-up
re-measures), `facts` (names/dates/staffing for action text) and `components`
(the merged findings).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import baskets, bills, data_issues as di, repeat
from .common import LEVEL_ORDER


@dataclass
class Detection:
    as_of: str
    issues: list = field(default_factory=list)
    role_models: list = field(default_factory=list)
    data_issues: list = field(default_factory=list)

    def for_manager(self, am_id, level=None):
        return [i for i in self.issues if i["area_manager_id"] == am_id and (level is None or i["level"] == level)]


def detect(m, prep) -> Detection:
    am_by_city = dict(zip(prep.managers.city, prep.managers.area_manager_id))
    store_meta = {r.store_id: {"area_manager_id": r.area_manager_id, "city": r.city} for _, r in m.stores.iterrows()}
    sf = bills.StoreFacts(m, prep)

    city = bills.city_issues(m, sf, am_by_city)
    folded = {c["city"] for c in city if c["level"] == "issue"}
    city_by_name = {c["city"]: c for c in city}
    store = bills.store_issues(m, sf, folded, city_by_name)

    # IPB: merged into the leaver / missing-shift issue where there is one; folded into a
    # city slowdown; otherwise its own Bigger-baskets issue.
    caused = set(m.stores.loc[m.stores.cause.notna(), "store_id"])
    folded_stores = set(m.stores.loc[m.stores.city.isin(folded), "store_id"])
    issues = (city + store + baskets.ipb_issues(m, caused | folded_stores)
              + baskets.addon_and_category_issues(m, store_meta)
              + baskets.discount_issues(m, prep, store_meta)
              + repeat.low_repeat_issues(m, store_meta))
    # ranking order only (Step 5 assigns `rank`): level, then ₹, then stronger |z|
    issues.sort(key=lambda i: (-LEVEL_ORDER[i["level"]], -i["rupees_at_stake_week"], -abs(i["z"] or 0)))
    return Detection(
        as_of=f"{m.as_of:%Y-%m-%d}", issues=issues,
        role_models=repeat.role_models(m, store_meta), data_issues=di.data_issues(m, prep),
    )
