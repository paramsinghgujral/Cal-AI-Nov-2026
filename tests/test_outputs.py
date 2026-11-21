"""Step 5 — checks on the written site JSON (output contract, PLAN §3 + D18).

    python run.py --replay-from 2026-10-01      # writes site/data/
    python -m pytest tests/test_outputs.py      # or: python tests/test_outputs.py
"""
import json
import os
from datetime import date

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "data")

RUN_KEYS = {"as_of", "data_through", "managers", "cards", "data_issues"}
AM_KEYS = {"area_manager_id", "name", "city", "stores", "visit_today", "today_issue_id", "today_type", "today_note",
           "week_sent", "week", "issues", "role_models", "followups"}
ISSUE_KEYS = {"id", "rank", "level", "lever", "scope", "store_id", "salesperson_id", "title", "cause", "action",
              "rupees_at_stake_week", "evidence", "first_raised"}
CARD_KEYS = {"salesperson_id", "name", "store_id", "kind", "lever", "behaviour", "peer", "action", "text", "word_count"}
FU_KEYS = {"issue_id", "raised_on", "metric", "at_alert", "now", "moved", "note"}
LEVERS = {"More bills", "Bigger baskets", "More repeat"}
TODAY = {"issue", "followup", "watch", "no_visit", "weekend"}


def _runs():
    idx = json.load(open(os.path.join(DATA, "index.json"), encoding="utf-8"))
    assert idx["latest"] in idx["runs"] and idx["generated_at"]
    for d in idx["runs"]:
        yield json.load(open(os.path.join(DATA, "runs", f"{d}.json"), encoding="utf-8"))


def test_contract_and_rules():
    n = 0
    for run in _runs():
        n += 1
        D = date.fromisoformat(run["as_of"])
        weekend = D.weekday() >= 5
        assert RUN_KEYS <= run.keys() and "sample" not in run
        assert run["data_through"] < run["as_of"], "no look-ahead"
        for m in run["managers"]:
            assert AM_KEYS <= m.keys(), m.keys()
            assert m["today_type"] in TODAY
            ids = {i["id"] for i in m["issues"]}
            if weekend:
                assert m["today_type"] == "weekend" and m["visit_today"] is None and m["today_issue_id"] is None
            else:
                assert m["today_type"] != "weekend"
                assert m["week"][-1]["date"] == run["as_of"] and m["week"][-1]["type"] == m["today_type"]
            if m["today_type"] in ("no_visit", "weekend"):
                assert m["visit_today"] is None and m["today_issue_id"] is None
            else:
                assert m["today_issue_id"] in ids and m["visit_today"]
            if m["today_type"] == "followup":
                assert any(f["issue_id"] == m["today_issue_id"] for f in m["followups"])
            # D4: one item per weekday Mon → today, an Issue is never sent twice in a week
            assert len(m["week"]) <= 5 and all(date.fromisoformat(w["date"]).weekday() < 5 for w in m["week"])
            assert len(m["week_sent"]) == len(set(m["week_sent"])) <= 5
            assert m["week_sent"] == [w["issue_id"] for w in m["week"] if w["type"] == "issue"]
            assert all(w["issue_id"] in ids for w in m["week"] if w["issue_id"])
            ranks = [i["rank"] for i in m["issues"] if i["rank"] is not None]
            assert ranks == list(range(1, len(ranks) + 1))
            for i in m["issues"]:
                assert ISSUE_KEYS <= i.keys(), i.keys()
                assert i["level"] in ("issue", "watch") and i["lever"] in LEVERS
                assert i["level"] == "issue" or i["rank"] is None
                a = i["action"]
                assert a and all(a[k] and a[k].strip() for k in ("who", "what", "when")), i["id"]
                assert isinstance(i["rupees_at_stake_week"], int)
            assert len({f["issue_id"] for f in m["followups"]}) == len(m["followups"])
            for f in m["followups"]:
                assert FU_KEYS <= f.keys()
                assert f["moved"] in ("better", "worse", "no change", "too few bills to tell", "too early to tell")
        for c in run["cards"]:
            assert CARD_KEYS <= c.keys()
            assert c["word_count"] == len(c["text"].split()) <= 60, c["text"]
            assert c["kind"] in ("gap", "keep_doing") and (c["peer"] is None) == (c["kind"] == "keep_doing")
            if c["peer"]:
                assert c["peer"]["salesperson_id"] != c["salesperson_id"]
        assert len({c["salesperson_id"] for c in run["cards"]}) == len(run["cards"])
        for x in run["data_issues"]:
            assert {"type", "store_id", "detail", "dates", "excluded_from"} <= x.keys()
    assert n > 0


def test_latest_morning_findings():
    """2 Nov: the Monday issue for Lucknow / Bengaluru is the leaver / missing-shift issue (F1, F2)."""
    run = json.load(open(os.path.join(DATA, "runs", "2026-11-02.json"), encoding="utf-8"))
    by_city = {m["city"]: m for m in run["managers"]}
    assert by_city["Lucknow"]["today_issue_id"] == "LKO-02:leaver:SP1018"
    assert by_city["Bengaluru"]["today_issue_id"] == "BLR-03:missing_shifts"
    assert by_city["Mysuru"]["today_issue_id"] == "Mysuru:city_slowdown"
    assert not any(c["store_id"] == "BLR-05" for c in run["cards"])


if __name__ == "__main__":
    test_contract_and_rules()
    test_latest_morning_findings()
    print("ok")
