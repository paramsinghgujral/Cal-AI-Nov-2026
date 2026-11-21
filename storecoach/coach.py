"""Step 5 — turn detected issues into what people receive.

    c = Coach(prep)
    run = c.build("2026-11-02")      # dict in the output contract (PLAN §3 + D18)

Area managers (D4, D15): one item per weekday Mon–Fri. The day's item is the
highest-₹ Issue not yet sent this week; if none is left, a follow-up visit on an
issue sent 7–13 days ago whose number did not improve; then the highest-₹ Watch
item not yet shown this week; else "no visit needed". Sat/Sun: no AM item.
"Sent this week" is worked out by replaying Mon → today, so no state is saved: the
same morning always gives the same brief.

Salesperson cards (METRICS §4 "Card gap"): every active salesperson in an
established store gets one ≤ 60-word card: one behaviour, the best same-store
peer on it, one action for today.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd

from .detect import detect
from .detect.common import pct
from .followup import FollowUp
from .metrics import compute

DAY = pd.Timedelta(days=1)
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DOW_LONG = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday"}
IST = timezone(timedelta(hours=5, minutes=30))
CARD_MAX_WORDS = 60
FU_VISIT = ("worse", "no change")   # follow-up visits only where the number did not improve


# ---- small text helpers ----------------------------------------------------------
def d_short(ts) -> str:
    return f"{DOW[ts.dayofweek]} {ts.day} {ts:%b}"


def first(name: str) -> str:
    return name.split()[0] if name else name


def names(xs) -> str:
    xs = [x for x in xs if x]
    return "" if not xs else xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def pc(x) -> str:
    """Percent with 1 decimal under 10%, else whole numbers."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if x == 0:
        return "0%"
    return f"{x * 100:.1f}%" if abs(x) < 0.10 else f"{x * 100:.0f}%"


def words(text: str) -> int:
    return len(text.split())


# ---- dates for action text ---------------------------------------------------------
class Dates:
    def __init__(self, prep):
        self.cal = prep.calendar
        self.state = dict(zip(prep.stores.store_id, prep.stores.state))
        self.city_state = dict(zip(prep.stores.city, prep.stores.state))

    def weekend(self, D) -> str:
        wd = D.dayofweek
        if wd == 5:
            return f"today and tomorrow (Sun {(D + DAY).day} {(D + DAY):%b})"
        if wd == 6:
            return f"today (Sun {D.day} {D:%b})"
        sat, sun = D + (5 - wd) * DAY, D + (6 - wd) * DAY
        return f"Sat {sat.day} – Sun {sun.day} {sun:%b}" if sat.month == sun.month else f"Sat {sat.day} {sat:%b} – Sun {sun.day} {sun:%b}"

    def festival(self, store_or_city, D, days=13) -> str:
        """' (Diwali is Sun 8 Nov)' if a festival falls in the next two weeks, else ''."""
        state = self.state.get(store_or_city) or self.city_state.get(store_or_city)
        c = self.cal[(self.cal.state == state) & (self.cal.date >= D) & (self.cal.date <= D + days * DAY) & (self.cal.festival != "")]
        if c.empty:
            return ""
        r = c.sort_values("date").iloc[0]
        return f" ({r.festival} is {d_short(r.date)})"

    @staticmethod
    def next_dow(D, dow) -> str:
        """'Tue 3 Nov' — the next date (after today) with that weekday name."""
        if not dow:
            return "a quiet weekday"
        k = DOW.index(dow)
        d = D + ((k - D.dayofweek) % 7 or 7) * DAY
        return f"{dow} {d.day} {d:%b}"


PAIR = {"sp_sherwani_addon": ("a safa, mojari or mala", "sherwani"), "sp_jacket_addon": ("a matching jacket", "kurta set")}
CAT_HINT = {
    "Sherwani": "show a sherwani to every groom and close-family customer",
    "Kurta Set": "start function shoppers on kurta sets",
    "Jacket": "put a matching jacket on every kurta-set customer at the mirror",
    "Safa": "bring a safa to the trial room with every sherwani",
    "Mojari": "bring matching mojaris to the trial room with every outfit",
    "Mala": "offer a mala with every sherwani",
    "Stole": "drape a stole on every kurta-set customer at the mirror",
    "Indo-Western": "show one Indo-Western option to reception and sangeet shoppers",
}


def _pair_of(meas):
    """(what to offer, with which item) for an add-on / folded category measure."""
    m = meas["metric"]
    if m in PAIR:
        return PAIR[m]
    cat = meas.get("category")
    if cat == "Jacket":
        return PAIR["sp_jacket_addon"]
    if cat in ("Safa", "Mojari", "Mala"):
        return PAIR["sp_sherwani_addon"]
    return (f"a {cat.lower()}" if cat else "the matching piece", "outfit")


# ---- AM actions (who / what / when) ---------------------------------------------------
def _addon_beh(meas):
    """Card-gap behaviour behind an add-on component (a folded jacket share counts as the jacket add-on)."""
    if meas["metric"] == "sp_category_share":
        return "jacket_addon" if meas.get("category") == "Jacket" else "sherwani_addon"
    return BEH_FROM_METRIC.get(meas["metric"])


def action_for(it: dict, D, dates: Dates, peer_of=None) -> dict:
    """`peer_of(sp, behaviour)` → best same-store peer's name for that exact behaviour (from today's card gaps)."""
    typ, sid, fx = it["type"], it["store_id"], it.get("facts") or {}
    wk = dates.weekend(D)
    fest = dates.festival(sid or it["city"], D)
    sellers = [s["name"] for s in fx.get("top_active_sellers", [])]
    quiet = fx.get("quiet_weekday")
    comps = it.get("components") or []
    nm = list(dict.fromkeys(c["name"] for c in comps if c.get("name")))
    peers = fx.get("peers") or {}
    peer_of = peer_of or (lambda sp, beh: None)

    if typ == "leaver":
        lv = fx["leavers"][0]["name"]
        two = names(sellers) or "the two top sellers"
        return {"who": f"Store manager, {sid}",
                "what": (f"Call {lv} today to ask whether {first(lv)} is coming back. Until then {two} cover "
                         f"{first(lv)}'s share of the floor: one greets every walk-in at the entrance, the other takes the "
                         f"sherwani and wedding customers, and both are rostered on {wk}{fest}."),
                "when": f"Today: the call this morning, the floor plan from today through {wk}"}
    if typ == "missing_shifts":
        ms = [x["name"] for x in fx.get("missing_shifts", [])]
        target = (fx.get("staffing") or {}).get("fri_baseline") or (fx.get("staffing") or {}).get("fri")
        return {"who": f"Store manager, {sid}, with {names(ms)}",
                "what": (f"Agree the coming week's roster with {names(ms)} today: weekly offs on "
                         f"{DOW_LONG.get(quiet, 'a quiet weekday')} (the store's quietest weekday, next one {dates.next_dow(D, quiet)}), "
                         f"not Sat/Sun, so {round(target) if target else 'the usual number of'} people are on the floor on {wk}{fest}."),
                "when": f"Today, before the roster for {wk} is fixed"}
    if typ == "understaffed_busy_days":
        st = fx.get("staffing") or {}
        return {"who": f"Store manager, {sid}",
                "what": (f"Move weekend offs to {DOW_LONG.get(quiet, 'a quiet weekday')} so Sat/Sun have as many people on the floor as "
                         f"Fridays ({st.get('fri') or '—'} vs {st.get('weekend_avg') or '—'} now); roster {names(sellers) or 'the top sellers'} "
                         f"on both days{fest}."),
                "when": f"Today, for {wk}"}
    if typ in ("conversion", "busy_days"):
        lead = sellers[0] if sellers else "the store's top seller"
        on = " on Sat/Sun" if typ == "busy_days" else ""
        return {"who": f"Store manager, {sid}, with {lead}",
                "what": (f"{lead} greets every walk-in at the entrance{on} and stays with them until they buy or leave; at closing, "
                         f"each salesperson names the customers who left without buying and why."),
                "when": f"Today{' and ' + wk if typ == 'busy_days' and D.dayofweek < 5 else ''}"}
    if typ == "city_slowdown":
        stores = fx.get("stores", [])
        other = [s for s in stores if s != sid]
        return {"who": f"Area manager with the store managers of {names(stores)}",
                "what": (f"Visit {sid} (the largest shortfall). This is the market, not one team, so no blame: agree one habit for "
                         f"{'both stores' if len(stores) == 2 else 'every store'} — show every buyer the complete look (kurta set, jacket and "
                         f"mojari together) to hold bill value — and keep full staff on {wk}{fest}."),
                "when": f"Today at {sid}" + (f"; phone {names(other)} today" if other else "")}
    if typ == "ipb_drop":
        low = fx.get("lowest_ipb") or []
        best = low[0]["best_peer"] if low else "the store's best seller"
        who_low = names([x["name"] for x in low]) or "every salesperson"
        return {"who": f"Store manager, {sid}",
                "what": (f"At today's opening huddle {best} shows how to add a second piece (jacket, mojari or stole) to a kurta-set "
                         f"sale; {who_low} offer one with every buyer today."),
                "when": "Today, from opening; check items per bill at closing"}
    if typ == "addon":
        parts = []
        for c in comps:
            offer, item = _pair_of(c["measure"])
            pr = peer_of(c["sp"], _addon_beh(c["measure"])) or (peers.get(c["sp"]) or {}).get("name")
            parts.append(f"{c['name']} offers {offer} with every {item}" + (f" ({pr} shows how)" if pr else ""))
        return {"who": f"{names(nm)}, with the store manager", "what": "; ".join(parts) + ".",
                "when": "Today, from the opening huddle; store manager checks their bills at closing"}
    if typ == "category":
        parts = []
        for c in comps:
            cat = c["measure"].get("category", "")
            pr = peer_of(c["sp"], f"share:{cat}") or (peers.get(c["sp"]) or {}).get("name")
            parts.append(f"{c['name']}: {CAT_HINT.get(cat, 'offer it to every customer it suits')}" + (f"; {pr} shows how" if pr else ""))
        return {"who": f"{names(nm)}, with the store manager", "what": "; ".join(parts) + ".",
                "when": "Today, from the opening huddle"}
    if typ == "discount":
        exp = it["measure"].get("expected")
        pr = next((n for c in comps if (n := peer_of(c["sp"], "discount"))), None) or next((p["name"] for p in peers.values() if p), None)
        return {"who": f"Store manager, {sid}, with {names(nm)}",
                "what": (f"From today, any discount by {names(nm)} above the store's usual {pc(exp)} needs the store manager's OK at "
                         f"the till" + (f"; {pr}, who sells closest to MRP, shares how at the huddle." if pr else ".")),
                "when": "Today, from opening"}
    if typ == "low_repeat":
        rm = fx.get("role_model_peer") or {}
        rmn = rm.get("name")
        return {"who": f"{names(nm)}, with the store manager",
                "what": ((f"{names(nm)} {'shadows' if len(nm) == 1 else 'shadow'} {rmn} at billing today and copy how {first(rmn)} "
                          "asks about the family's next function, saves the customer's number, and invites them back for it.") if rmn else
                         (f"{names(nm)} {'asks' if len(nm) == 1 else 'ask'} every buyer about the family's next function, save the "
                          "customer's number, and invite them back for it.")),
                "when": "Today; store manager checks in at closing"}
    return {"who": f"Store manager, {sid}", "what": it["title"], "when": "Today"}


# ---- salesperson cards ------------------------------------------------------------------
BEH_FROM_METRIC = {"sp_sherwani_addon": "sherwani_addon", "sp_jacket_addon": "jacket_addon", "sp_discount": "discount",
                   "sp_repeat": "repeat"}


def _behaviour_key(meas):
    if meas["metric"] == "sp_category_share":
        return f"share:{meas['category']}"
    return BEH_FROM_METRIC.get(meas["metric"])


def _card_lines(beh, own, best, peer, n, since, store_val=None):
    """(behaviour sentence, action sentence) for a gap card."""
    p = first(peer) if peer else None
    if beh == "sherwani_addon":
        return (f"{peer} adds a safa, mojari or mala to {pc(best)} of sherwani bills; you, {pc(own)} ({n:.0f} sherwani bills since {since}).",
                "Today: bring a matching safa and mojari to the trial room with every sherwani.")
    if beh == "jacket_addon":
        return (f"{peer} adds a jacket to {pc(best)} of kurta-set bills; you, {pc(own)} since {since}.",
                "Today: put a matching jacket on every kurta-set customer at the mirror.")
    if beh == "discount":
        return (f"{peer} gives {pc(best)} off MRP on average; you give {pc(own)} since {since}.",
                "Today: quote MRP first, show the fabric and finish, and check with the store manager before any discount.")
    if beh == "ipb":
        return (f"{peer} sells {best:.2f} items per bill; you, {own:.2f} since {since}.",
                "Today: once the main outfit is chosen, show one piece that completes it: a jacket, mojari or stole.")
    if beh == "repeat":
        return (f"{pc(best)} of {peer}'s first-time customers come back; {pc(own)} of yours.",
                f"Today: like {p}, ask each buyer about the family's next function and invite them back for it.")
    cat = beh.split(":", 1)[1]
    label = {"Kurta Set": "kurta sets", "Indo-Western": "Indo-Western outfits"}.get(cat, cat.lower() + "s")
    return (f"{label[0].upper() + label[1:]} are {pc(best)} of {peer}'s items; {pc(own)} of yours since {since}.",
            f"Today: {CAT_HINT.get(cat, 'show one to every customer it suits')}.")


def _keep_lines(beh, own, store_val, since):
    if beh == "sherwani_addon":
        return (f"you add a safa, mojari or mala to {pc(own)} of sherwani bills; the store average is {pc(store_val)}.",
                "Keep it up today with every sherwani, and show a newer colleague how you do it.")
    if beh == "jacket_addon":
        return (f"you add a jacket to {pc(own)} of kurta-set bills; the store average is {pc(store_val)}.",
                "Keep it up today: a matching jacket with every kurta set.")
    if beh == "discount":
        return (f"you give only {pc(own)} off MRP; the store average is {pc(store_val)}.",
                "Keep quoting MRP first today and let the outfit sell itself.")
    if beh == "ipb":
        return (f"you sell {own:.2f} items per bill; the store average is {store_val:.2f}.",
                "Keep completing the look today: one more piece with every main outfit.")
    if beh == "repeat":
        return (f"{pc(own)} of your first-time customers come back; the store average is {pc(store_val)}.",
                "Keep inviting every buyer back for the family's next function today.")
    cat = beh.split(":", 1)[1]
    return (f"{cat.lower()} is {pc(own)} of your items; the store average is {pc(store_val)}.",
            f"Keep it up today: {CAT_HINT.get(cat, 'offer it to every customer it suits')}.")


def cards(m, d) -> list[dict]:
    sp, g = m.salespeople, m.card_gaps
    since = f"{m.windows.salesperson.start.day} {m.windows.salesperson.start:%b}"
    # behaviours already raised to the AM as an Issue for this person → the card backs it up
    linked = {}
    for it in d.issues:
        if it["level"] != "issue":
            continue
        for c in it.get("components") or []:
            if c.get("sp") and c.get("measure"):
                linked.setdefault(c["sp"], _behaviour_key(c["measure"]))
    out = []
    people = sp[sp.active & sp.established].sort_values(["store_id", "sp"])
    for _, r in people.iterrows():
        x = g[(g.sp == r.sp) & g.value.notna()].copy()
        if x.empty:
            continue
        x["is_share"] = x.behaviour.str.startswith("share:")
        x["below_store"] = (x.higher_better & (x.value < x.store_value)) | (~x.higher_better & (x.value > x.store_value))
        gaps = x[(x.gap > 0) & x.best_peer.notna() & (x.gap_rs_week > 0)]
        pick, kind = None, "gap"
        if r.sp in linked and linked[r.sp] in set(gaps.behaviour):
            pick = gaps[gaps.behaviour == linked[r.sp]].iloc[0]
        else:
            # tiers: behaviours below the store average first, add-on/discount/IPB/repeat before category share
            for mask in (~gaps.is_share & gaps.below_store, gaps.is_share & gaps.below_store, gaps.gap > 0):
                t = gaps[mask]
                if len(t):
                    pick = t.sort_values("gap_rs_week", ascending=False).iloc[0]
                    break
        if pick is None:
            kind = "keep_doing"
            good = x[~x.below_store & x.store_value.notna()].copy()
            if good.empty:
                continue
            good["adv"] = (good.value / good.store_value).where(good.higher_better, good.store_value / good.value.clip(lower=1e-6))
            good = good.sort_values(["is_share", "adv"], ascending=[True, False])
            pick = good.iloc[0]
            beh_line, act_line = _keep_lines(pick.behaviour, pick.value, pick.store_value, since)
            text = f"{first(r['name'])}, {beh_line} {act_line}"
            peer = None
        else:
            beh_line, act_line = _card_lines(pick.behaviour, pick.value, pick.best_value, pick.best_peer_name, pick.n, since)
            text = f"{first(r['name'])}, {beh_line} {act_line}"
            peer = {"salesperson_id": pick.best_peer, "name": pick.best_peer_name}
        assert words(text) <= CARD_MAX_WORDS, text
        out.append({
            "salesperson_id": r.sp, "name": r["name"], "store_id": r.store_id, "kind": kind, "lever": pick.lever,
            "behaviour_key": pick.behaviour, "behaviour": beh_line[0].upper() + beh_line[1:], "peer": peer,
            "action": act_line, "text": text, "word_count": words(text),
            "rupees_gap_week": int(round(pick.gap_rs_week)) if kind == "gap" else 0,
            "linked_issue": kind == "gap" and linked.get(r.sp) == pick.behaviour,
        })
    return out


# ---- the coach ---------------------------------------------------------------------------
class Coach:
    def __init__(self, prep):
        self.prep = prep
        self.dates = Dates(prep)
        self.fu = FollowUp(prep)
        self.ams = prep.managers.copy()
        self.ams["store_list"] = self.ams.stores.str.split(",").map(lambda xs: [x.strip() for x in xs])
        self._det, self._pick, self._plan, self._fus = {}, {}, {}, {}

    # detection per morning, cached (replays reuse it)
    def detection(self, D):
        D = pd.Timestamp(D).normalize()
        if D not in self._det:
            m = compute(self.prep, D)
            self._det[D] = (m, detect(m, self.prep))
        return self._det[D]

    @staticmethod
    def monday(D):
        return D - D.dayofweek * DAY

    def _weekdays(self, a, b):
        return [x for x in pd.date_range(a, b) if x.dayofweek < 5]

    # ---- Issue picks (depend only on this week's detections) ----
    def pick_issue(self, am, D):
        """The Issue sent to `am` on weekday D, or None (all this week's Issues already sent)."""
        key = (am, D)
        if key not in self._pick:
            sent = {i["id"] for x in self._weekdays(self.monday(D), D - DAY) if (i := self.pick_issue(am, x))}
            _, d = self.detection(D)
            self._pick[key] = next((i for i in d.for_manager(am, "issue") if i["id"] not in sent), None)
        return self._pick[key]

    def sent_between(self, am, a, b):
        return [(x, i) for x in self._weekdays(a, b) if (i := self.pick_issue(am, x))]

    def followups(self, am, D):
        """Issues sent to `am` 7–13 days before D, re-measured over the 7 days after each was sent."""
        key = (am, D)
        if key not in self._fus:
            latest = {}   # an issue re-sent in consecutive weeks is followed up from its latest sending only
            for d0, it in self.sent_between(am, D - 13 * DAY, D - 7 * DAY):
                latest[it["id"]] = (d0, it)
            rows = [(it, self.fu.check(it, d0, D)) for d0, it in sorted(latest.values(), key=lambda p: p[0])]
            self._fus[key] = rows
        return self._fus[key]

    def day_plan(self, am, D):
        """(type, issue or None, followup row or None) for weekday D."""
        key = (am, D)
        if key in self._plan:
            return self._plan[key]
        it = self.pick_issue(am, D)
        if it:
            res = ("issue", it, None)
        else:
            earlier = [self.day_plan(am, x) for x in self._weekdays(self.monday(D), D - DAY)]
            seen = {(t, i["id"]) for t, i, _ in earlier if i}
            week_ids = {i["id"] for x in self._weekdays(self.monday(D), D) if (i := self.pick_issue(am, x))}
            fus = [(i, f) for i, f in self.followups(am, D)
                   if f["moved"] in FU_VISIT and ("followup", i["id"]) not in seen and i["id"] not in week_ids]
            if fus:
                i, f = max(fus, key=lambda p: (p[1]["moved"] == "worse", p[0]["rupees_at_stake_week"]))
                res = ("followup", i, f)
            else:
                _, d = self.detection(D)
                w = next((i for i in d.for_manager(am, "watch") if ("watch", i["id"]) not in seen), None)
                res = ("watch", w, None) if w else ("no_visit", None, None)
        self._plan[key] = res
        return res

    # ---- one manager's brief ----
    def manager(self, am_row, D, m, d):
        am = am_row.area_manager_id
        mon = self.monday(D)
        weekend = D.dayofweek >= 5
        week_days = self._weekdays(mon, min(D, mon + 4 * DAY))
        plans = [(x, *self.day_plan(am, x)) for x in week_days]
        week = [{"date": f"{x:%Y-%m-%d}", "type": t, "issue_id": i["id"] if i else None, "store_id": i["store_id"] if i else None}
                for x, t, i, _ in plans]
        week_sent = [i["id"] for _, t, i, _ in plans if t == "issue"]

        # history for first_raised: this week and the two before
        hist = self.sent_between(am, mon - 14 * DAY, min(D, mon + 4 * DAY))
        first_sent = {}
        for x, i in hist:
            first_sent.setdefault(i["id"], x)

        # issues: today's detections for this AM, plus anything sent/visited this week that is no longer detected
        items = list(d.for_manager(am))
        have = {i["id"] for i in items}
        for _, t, i, _ in plans:
            if i and i["id"] not in have:
                items.append(i)
                have.add(i["id"])
        g = m.card_gaps.dropna(subset=["best_peer_name"])
        peer_names = dict(zip(zip(g.sp, g.behaviour), g.best_peer_name))
        peer_of = lambda sp, beh: peer_names.get((sp, beh))
        today_ids = {i["id"] for i in d.for_manager(am)}
        out_issues, rank = [], 0
        for it in items:
            ranked = it["level"] == "issue" and it["id"] in today_ids
            rank += ranked
            fr = first_sent.get(it["id"])
            out_issues.append(_public_issue(it, rank if ranked else None,
                                            action_for(it, D, self.dates, peer_of), f"{fr:%Y-%m-%d}" if fr else None))

        fu_rows = [f for _, f in self.followups(am, D)]
        today_type, today_issue, today_note = "weekend", None, None
        if weekend:
            nxt = D + (7 - D.dayofweek) * DAY
            today_note = f"No area-manager issue at weekends. The next one arrives on {d_short(nxt)} morning."
        else:
            today_type, today_issue, f = plans[-1][1], plans[-1][2], plans[-1][3]
            if today_type == "issue":
                fr = first_sent.get(today_issue["id"])
                prev = next((r for i, r in self.followups(am, D) if i["id"] == today_issue["id"]), None)
                if fr is not None and fr < mon:
                    today_note = f"Raised again: first sent {d_short(fr)}." + (
                        f" Last week's follow-up: {prev['moved']} ({prev['note']})" if prev else "")
            elif today_type == "followup":
                today_note = (f"Every issue for this week has been sent. Today: go back to {today_issue['store_id']} — the issue sent on "
                              f"{d_short(pd.Timestamp(f['raised_on']))} has {'got worse' if f['moved'] == 'worse' else 'not moved'}.")
            elif today_type == "watch":
                today_note = ("Every issue for this week has been sent. This is an early signal, not proven — check it on the floor "
                              "before acting.")
            else:
                today_note = "Every issue for this week has been sent and nothing else needs a visit. Use the day for the stores' own priorities."
        rm = [{k: r[k] for k in ("salesperson_id", "name", "store_id", "metric", "value", "store_value", "detail", "z")}
              for r in d.role_models if r["area_manager_id"] == am]
        return {
            "area_manager_id": am, "name": am_row["name"], "city": am_row.city, "stores": am_row.store_list,
            "visit_today": today_issue["store_id"] if today_issue else None,
            "today_issue_id": today_issue["id"] if today_issue else None,
            "today_type": today_type, "today_note": today_note,
            "week_sent": week_sent, "week": week,
            "issues": out_issues, "role_models": rm, "followups": fu_rows,
        }

    def build(self, as_of) -> dict:
        D = pd.Timestamp(as_of).normalize()
        m, d = self.detection(D)
        managers = [self.manager(r, D, m, d) for _, r in self.ams.iterrows()]
        return {
            "as_of": f"{D:%Y-%m-%d}",
            "data_through": f"{m.data_through:%Y-%m-%d}",
            "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
            "managers": managers,
            "cards": cards(m, d),
            "data_issues": [{k: x.get(k) for k in ("type", "store_id", "detail", "dates", "excluded_from", "customer_id") if k in x}
                            for x in d.data_issues],
            "counts": {"issues": sum(i["level"] == "issue" for i in d.issues), "watch": sum(i["level"] == "watch" for i in d.issues),
                       "role_models": len(d.role_models), "data_issues": len(d.data_issues)},
        }


PUBLIC = ("id", "rank", "level", "type", "lever", "scope", "city", "store_id", "salesperson_id", "salesperson_ids",
          "title", "cause", "action", "rupees_at_stake_week", "z", "evidence", "measure", "first_raised")


def _public_issue(it, rank, action, first_raised) -> dict:
    x = dict(it, rank=rank, action=action, first_raised=first_raised)
    return {k: x.get(k) for k in PUBLIC}
