"""Step 2a — metrics engine. Implements METRICS.md for any run date.

A run "as of D" is the morning of day D and sees only data dated <= D-1.

    m = compute(prep, "2026-11-02")
    m.stores       one row per store      (conversion, busy days, IPB, ATV, RPF, discount, repeat)
    m.cities       one row per city       (Recent vs Year ago, vs all other cities)
    m.salespeople  one row per salesperson (add-ons, discount, IPB, repeat, off-rate, leaver, active)
    m.categories   salesperson x category (share vs same-store peers)
    m.staffing     store x weekday        (avg staff present, Recent window)
    m.card_gaps    salesperson x behaviour (vs best active same-store peer; METRICS §4 "Card gap")
    m.bad_days     store-days left out of conversion

Each Issue metric carries its z, its gap, its ₹/week (METRICS §5) and a `*_level`
of "issue", "watch" or None (METRICS §4, D15). Salesperson levels need an
active, established-store salesperson (METRICS §1). Merging issues, folding store
alerts into a city slowdown and writing text are Step 4/5, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .prep import ADDON_CATS, CATEGORIES, Prep

# ---- thresholds (METRICS §1, §4) -------------------------------------------
Z_ISSUE = -2.5          # on its own
Z_CAUSE = -2.0          # store gap when a leaver / missing shifts is found; cities
Z_WATCH = -1.5          # D15: between -1.5 and the Issue threshold = "watch"
Z_ROLE = 2.5            # role model
PLACEHOLDER_MIN_BILLS = 50
ESTABLISHED_DAYS = 90
MIN_CONV_DAYS, MIN_CONV_BILLS, MIN_BUSY_FOOT = 28, 100, 300
MIN_IPB_BILLS = 100
MIN_CITY_BILLS = 100
MIN_SHW, MIN_KUR = 5, 20
MIN_CAT_EXPECTED = 5
MIN_DISC_BILLS = 30
MIN_SP_IPB_BILLS = 30   # salesperson IPB (card only) — not set in METRICS, same as discount
MIN_REPEAT = 50
MIN_ROSTER_DAYS = 20
LEAVER_SHARE = 0.08
OFF_RATE_MIN, OFF_RATE_RISE = 0.35, 0.15
REPEAT_GAP_DAYS = 30


# ---- windows (METRICS §2) ---------------------------------------------------
@dataclass(frozen=True)
class Window:
    start: pd.Timestamp
    end: pd.Timestamp     # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def weeks(self) -> float:
        return self.days / 7

    def mask(self, dates: pd.Series) -> pd.Series:
        return (dates >= self.start) & (dates <= self.end)

    def __str__(self) -> str:
        return f"{self.start:%Y-%m-%d} … {self.end:%Y-%m-%d}"


@dataclass(frozen=True)
class Windows:
    as_of: pd.Timestamp
    recent: Window
    baseline: Window
    salesperson: Window
    shifts: Window
    activity: Window
    year_ago: Window
    cohort: Window


def windows(as_of) -> Windows:
    D = pd.Timestamp(as_of).normalize()

    def w(a: int, b: int) -> Window:  # D-a … D-b
        return Window(D - pd.Timedelta(days=a), D - pd.Timedelta(days=b))

    return Windows(
        as_of=D, recent=w(56, 1), baseline=w(182, 57), salesperson=w(91, 1), shifts=w(28, 1),
        activity=w(14, 1), year_ago=w(56 + 364, 1 + 364), cohort=w(540, 121),
    )


# ---- statistics (METRICS §4) ------------------------------------------------
def rate_z(k, n, p0):
    """Binomial z = (k - n p0) / sqrt(n p0 (1 - p0))."""
    k, n, p0 = (np.asarray(x, dtype=float) for x in (k, n, p0))
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (k - n * p0) / np.sqrt(n * p0 * (1 - p0))
    return np.where(np.isfinite(z), z, np.nan)


def mean_z(sum_x, sum_x2, n, expected):
    """z = (mean - expected) / (sd / sqrt n), sd from the per-unit values."""
    s, s2, n, e = (np.asarray(x, dtype=float) for x in (sum_x, sum_x2, n, expected))
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = s / n
        var = (s2 - n * mean ** 2) / (n - 1)
        z = (mean - e) / np.sqrt(var / n)
    return np.where(np.isfinite(z), z, np.nan)


def level(z, ok, threshold=Z_ISSUE):
    """'issue' if z <= threshold, 'watch' if z <= -1.5, else None — only where `ok`
    (minimum sample and minimum gap size both met)."""
    z = np.asarray(z, dtype=float)
    thr = np.broadcast_to(np.asarray(threshold, dtype=float), z.shape)
    ok = np.asarray(ok, dtype=bool) & np.isfinite(z)
    out = np.where(ok & (z <= thr), "issue", np.where(ok & (z <= Z_WATCH), "watch", None))
    return pd.Series(out, dtype=object).where(lambda s: s.notna(), None).values


def _div(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = a / b
    return np.where(np.isfinite(r), r, np.nan)


# ---- context: everything a run may see --------------------------------------
@dataclass
class Ctx:
    as_of: pd.Timestamp
    w: Windows
    bills: pd.DataFrame       # bills <= D-1, with `placeholder`
    foot: pd.DataFrame        # footfall rows <= D-1
    roster: pd.DataFrame      # roster rows <= D-1
    stores: pd.DataFrame      # with `established`
    people: pd.DataFrame
    placeholders: list
    active: set


def context(prep: Prep, as_of) -> Ctx:
    w = windows(as_of)
    last = w.as_of - pd.Timedelta(days=1)
    b = prep.bills[prep.bills.date <= last].copy()
    counts = b.customer_id.value_counts()
    placeholders = sorted(counts[counts >= PLACEHOLDER_MIN_BILLS].index)
    b["placeholder"] = b.customer_id.isin(placeholders)
    f = prep.footfall[prep.footfall.date <= last]
    r = prep.roster[prep.roster.date <= last]
    st = prep.stores.copy()
    st["established"] = st.opened_on <= w.as_of - pd.Timedelta(days=ESTABLISHED_DAYS)
    active = set(b.loc[w.activity.mask(b.date), "sp"]) | set(
        r.loc[w.activity.mask(r.date) & r.status.eq("Present"), "salesperson_id"]
    )
    return Ctx(w.as_of, w, b, f, r, st, prep.people, placeholders, active)


# ---- store metrics -----------------------------------------------------------
_BILL_COLS = ["bills", "items", "items_sq", "rev", "disc", "mrpv"]
_FOOT_COLS = ["foot", "fbills", "frev", "frev_sq", "days"]


def _bill_agg(b: pd.DataFrame, key="store_id") -> pd.DataFrame:
    return b.groupby(key).agg(
        bills=("bill_id", "size"), items=("items", "sum"), items_sq=("items_sq", "sum"),
        rev=("rev", "sum"), disc=("disc", "sum"), mrpv=("mrpv", "sum"),
    )


def _foot_agg(f: pd.DataFrame, key="store_id") -> pd.DataFrame:
    g = f[~f.bad]
    return g.groupby(key).agg(
        foot=("footfall", "sum"), fbills=("bills", "sum"), frev=("rev", "sum"), frev_sq=("rev_sq", "sum"), days=("date", "nunique"),
    )


def _peers(df: pd.DataFrame, stores: pd.DataFrame) -> pd.DataFrame:
    """For each store: sums over the other *established* stores in the same state."""
    est = stores[stores.established]
    out = {}
    for _, s in stores.iterrows():
        ids = est.loc[(est.state == s.state) & (est.store_id != s.store_id), "store_id"]
        out[s.store_id] = df.reindex(ids).fillna(0).sum()
    return pd.DataFrame(out).T


def store_metrics(ctx: Ctx, causes: pd.Series | None = None) -> pd.DataFrame:
    w, b, f, st = ctx.w, ctx.bills, ctx.foot, ctx.stores
    ids = st.store_id
    br = _bill_agg(b[w.recent.mask(b.date)]).reindex(ids).fillna(0)
    bb = _bill_agg(b[w.baseline.mask(b.date)]).reindex(ids).fillna(0)
    fr = _foot_agg(f[w.recent.mask(f.date)]).reindex(ids).fillna(0)
    fb = _foot_agg(f[w.baseline.mask(f.date)]).reindex(ids).fillna(0)
    wr = _foot_agg(f[w.recent.mask(f.date) & f.weekend]).reindex(ids).fillna(0)
    wb = _foot_agg(f[w.baseline.mask(f.date) & f.weekend]).reindex(ids).fillna(0)
    pbr, pbb, pfr, pfb, pwr, pwb = (_peers(x, st).reindex(ids) for x in (br, bb, fr, fb, wr, wb))

    o = st[["store_id", "city", "state", "tier", "opened_on", "area_manager_id", "established"]].set_index("store_id").copy()
    o["bills_r"], o["items_r"], o["rev_r"] = br.bills, br["items"], br.rev
    o["ipb_r"] = _div(br["items"], br.bills)
    o["atv_r"] = _div(br.rev, br.bills)
    o["avg_item_price_r"] = _div(br.rev, br["items"])
    o["disc_pct_r"] = _div(br.disc, br.mrpv)
    o["bills_b"], o["ipb_b"], o["atv_b"] = bb.bills, _div(bb["items"], bb.bills), _div(bb.rev, bb.bills)

    # Conversion, peer-relative: expected = (store ÷ peers in Baseline) × peers in Recent
    o["good_days_r"], o["foot_r"], o["fbills_r"] = fr.days, fr.foot, fr.fbills
    o["conv_r"], o["conv_b"] = _div(fr.fbills, fr.foot), _div(fb.fbills, fb.foot)
    o["peer_conv_r"], o["peer_conv_b"] = _div(pfr.fbills, pfr.foot), _div(pfb.fbills, pfb.foot)
    o["conv_exp"] = o.conv_b / o.peer_conv_b * o.peer_conv_r
    o["conv_gap_pct"] = o.conv_r / o.conv_exp - 1
    o["conv_z"] = rate_z(fr.fbills, fr.foot, o.conv_exp)
    o["conv_rs_week"] = (o.conv_exp - o.conv_r) * (fr.foot / w.recent.weeks) * o.atv_r
    o["conv_sample_ok"] = (fr.days >= MIN_CONV_DAYS) & (fr.fbills >= MIN_CONV_BILLS)
    o["conv_size_ok"] = o.conv_r <= 0.9 * o.conv_exp

    # Busy days (Sat + Sun)
    o["busy_foot_r"], o["busy_bills_r"] = wr.foot, wr.fbills
    o["busy_conv_r"], o["busy_conv_b"] = _div(wr.fbills, wr.foot), _div(wb.fbills, wb.foot)
    o["busy_conv_exp"] = o.busy_conv_b / _div(pwb.fbills, pwb.foot) * _div(pwr.fbills, pwr.foot)
    o["busy_conv_gap_pct"] = o.busy_conv_r / o.busy_conv_exp - 1
    o["busy_conv_z"] = rate_z(wr.fbills, wr.foot, o.busy_conv_exp)
    o["busy_conv_rs_week"] = (o.busy_conv_exp - o.busy_conv_r) * (wr.foot / w.recent.weeks) * o.atv_r
    o["busy_sample_ok"] = wr.foot >= MIN_BUSY_FOOT
    o["busy_size_ok"] = o.busy_conv_r <= 0.9 * o.busy_conv_exp

    # IPB: expected = store Baseline IPB × (peer Recent ÷ peer Baseline)
    o["peer_ipb_r"], o["peer_ipb_b"] = _div(pbr["items"], pbr.bills), _div(pbb["items"], pbb.bills)
    o["ipb_exp"] = o.ipb_b * o.peer_ipb_r / o.peer_ipb_b
    o["ipb_gap_pct"] = o.ipb_r / o.ipb_exp - 1
    o["ipb_z"] = mean_z(br["items"], br.items_sq, br.bills, o.ipb_exp)
    o["ipb_rs_week"] = (o.ipb_exp - o.ipb_r) * (br.bills / w.recent.weeks) * o.avg_item_price_r
    o["ipb_sample_ok"] = br.bills >= MIN_IPB_BILLS
    o["ipb_size_ok"] = o.ipb_r < o.ipb_exp  # METRICS sets no minimum size for IPB

    # Revenue per walk-in (good days, non-buyers count as ₹0)
    o["rpf_r"] = _div(fr.frev, fr.foot)
    o["bad_days_r"] = f[w.recent.mask(f.date) & f.bad].groupby("store_id").size().reindex(ids).fillna(0).astype(int)

    # Levels. Thresholds relax to -2.0 where a leaver / missing shifts was found.
    o["cause"] = (causes.reindex(ids) if causes is not None else pd.Series(None, index=ids)).values
    thr = np.where(o.cause.notna(), Z_CAUSE, Z_ISSUE)
    est = o.established.values
    o["conv_level"] = level(o.conv_z, est & o.conv_sample_ok & o.conv_size_ok, thr)
    o["busy_conv_level"] = level(o.busy_conv_z, est & o.busy_sample_ok & o.busy_size_ok, thr)
    o["ipb_level"] = level(o.ipb_z, est & o.ipb_sample_ok & o.ipb_size_ok, thr)
    return o.reset_index()


# ---- city metrics (D13) -------------------------------------------------------
def city_metrics(ctx: Ctx) -> pd.DataFrame:
    """City vs all other cities, Recent vs the same days 364 days earlier.
    Only stores open since the start of the Year-ago window are compared."""
    w, st = ctx.w, ctx.stores
    comparable = set(st.loc[st.opened_on <= w.year_ago.start, "store_id"])
    b = ctx.bills[ctx.bills.store_id.isin(comparable)]
    f = ctx.foot[ctx.foot.store_id.isin(comparable)]

    def agg(win):
        x = _bill_agg(b[win.mask(b.date)], "city").join(_foot_agg(f[win.mask(f.date)], "city"))
        return x.fillna(0)

    r, y = agg(w.recent), agg(w.year_ago)
    cities = sorted(st.city.unique())
    r, y = r.reindex(cities).fillna(0), y.reindex(cities).fillna(0)
    ro, yo = r.sum() - r, y.sum() - y  # all other cities

    def m(x):
        return {
            "conv": _div(x.fbills, x.foot), "ipb": _div(x["items"], x.bills),
            "atv": _div(x.rev, x.bills), "rpf": _div(x.frev, x.foot),
        }

    mr, my, mro, myo = m(r), m(y), m(ro), m(yo)
    o = pd.DataFrame(index=pd.Index(cities, name="city"))
    o["state"] = st.groupby("city").state.first().reindex(cities)
    o["bills_r"], o["foot_r"], o["bills_ya"], o["foot_ya"] = r.bills, r.foot, y.bills, y.foot
    for k in ("conv", "ipb", "atv", "rpf"):
        o[f"{k}_r"], o[f"{k}_ya"] = mr[k], my[k]
        o[f"{k}_exp"] = my[k] * mro[k] / myo[k]
        o[f"{k}_gap_pct"] = o[f"{k}_r"] / o[f"{k}_exp"] - 1
    o["rpf_z"] = mean_z(r.frev, r.frev_sq, r.foot, o.rpf_exp)
    o["rpf_rs_week"] = (o.rpf_exp - o.rpf_r) * (r.foot / w.recent.weeks)
    o["all_three_below"] = (o.conv_gap_pct < 0) & (o.ipb_gap_pct < 0) & (o.atv_gap_pct < 0)
    o["city_level"] = level(o.rpf_z, (o.bills_r >= MIN_CITY_BILLS) & o.all_three_below, Z_CAUSE)
    return o.reset_index()


# ---- repeat (D3, D12) ----------------------------------------------------------
def repeat_cohort(ctx: Ctx) -> pd.DataFrame:
    """One row per cohort customer: first bill's store/salesperson, repeat flag,
    revenue of the bills 30+ days after the first."""
    w = ctx.w
    real = ctx.bills[~ctx.bills.placeholder].sort_values(["customer_id", "date", "bill_id"])
    first = real.drop_duplicates("customer_id")[["customer_id", "date", "store_id", "sp"]].rename(columns={"date": "first_date"})
    first = first[w.cohort.mask(first.first_date)]
    x = real[["customer_id", "date", "rev"]].merge(first[["customer_id", "first_date"]], on="customer_id")
    later = x[x.date >= x.first_date + pd.Timedelta(days=REPEAT_GAP_DAYS)].groupby("customer_id").rev.agg(["size", "sum"])
    first = first.join(later, on="customer_id")
    first["repeat"] = first["size"].fillna(0) > 0
    first["later_rev"] = first["sum"].fillna(0.0)
    return first.drop(columns=["size", "sum"])


# ---- salesperson metrics --------------------------------------------------------
def _sp_agg(b: pd.DataFrame) -> pd.DataFrame:
    return b.groupby("sp").agg(
        store_id=("store_id", "first"), bills=("bill_id", "size"), items=("items", "sum"), items_sq=("items_sq", "sum"),
        rev=("rev", "sum"), disc=("disc", "sum"), mrpv=("mrpv", "sum"),
        shw_n=("shw", "sum"), shw_k=("shw_acc", "sum"), kur_n=("kur", "sum"), kur_k=("kur_jkt", "sum"),
    )


def _minus_self(df: pd.DataFrame, cols, key="store_id") -> pd.DataFrame:
    """Sum over the other salespeople in the same store."""
    tot = df.groupby(key)[cols].transform("sum")
    return tot - df[cols]


def salesperson_metrics(ctx: Ctx, cohort: pd.DataFrame) -> pd.DataFrame:
    w, b, ppl = ctx.w, ctx.bills, ctx.people
    bs = b[w.salesperson.mask(b.date)]
    s = ppl.rename(columns={"salesperson_id": "sp"}).set_index("sp")[["name", "store_id", "join_date"]]
    a = _sp_agg(bs).drop(columns="store_id")
    s = s.join(a).fillna({c: 0 for c in a.columns})
    s = s.join(ctx.stores.set_index("store_id")[["city", "state", "established"]], on="store_id")
    s["active"] = s.index.isin(ctx.active)

    # Store-level ₹ factors (Salesperson window, whole store)
    sb = bs.groupby("store_id")
    store_addon_rs = bs[bs.shw_acc].groupby("store_id").addon_rev.mean()  # ₹ of safa/mojari/mala per add-on bill
    store_jkt_rs = bs[bs.kur_jkt].groupby("store_id").rev_Jacket.mean()
    store_item_price = sb.rev.sum() / sb["items"].sum()
    s["store_addon_rs"] = s.store_id.map(store_addon_rs)
    s["store_jacket_rs"] = s.store_id.map(store_jkt_rs)
    s["store_item_price"] = s.store_id.map(store_item_price)

    # Peers = other salespeople with bills in the same store, same window (pooled)
    has = s[s.bills > 0]
    cols = ["bills", "items", "disc", "mrpv", "shw_n", "shw_k", "kur_n", "kur_k"]
    peer = _minus_self(has, cols).add_prefix("peer_")
    s = s.join(peer)

    s["ipb"] = _div(s["items"], s.bills)
    s["peer_ipb"] = _div(s.peer_items, s.peer_bills)
    s["disc_pct"] = _div(s.disc, s.mrpv)
    s["peer_disc_pct"] = _div(s.peer_disc, s.peer_mrpv)
    s["disc_rs_week"] = (s.disc_pct - s.peer_disc_pct) * s.mrpv / w.salesperson.weeks
    disc_ok = (s.bills >= MIN_DISC_BILLS) & (s.disc_pct >= 2 * s.peer_disc_pct) & (s.disc_pct >= s.peer_disc_pct + 0.02)
    s["disc_level"] = np.where(disc_ok & s.established & s.active, "issue", None)  # no z for discount → no watch

    for tag, n, k, mn, rs in (("shw", "shw_n", "shw_k", MIN_SHW, "store_addon_rs"), ("kur", "kur_n", "kur_k", MIN_KUR, "store_jacket_rs")):
        s[f"{tag}_rate"] = _div(s[k], s[n])
        s[f"{tag}_peer_rate"] = _div(s[f"peer_{k}"], s[f"peer_{n}"])
        s[f"{tag}_z"] = rate_z(s[k], s[n], s[f"{tag}_peer_rate"])
        s[f"{tag}_rs_week"] = (s[f"{tag}_peer_rate"] - s[f"{tag}_rate"]) * s[n] / w.salesperson.weeks * s[rs]
        ok = s.established & s.active & (s[n] >= mn) & (s[f"{tag}_rate"] <= 0.5 * s[f"{tag}_peer_rate"])
        s[f"{tag}_level"] = level(s[f"{tag}_z"], ok)

    # Repeat (cohort credited to the first bill's salesperson)
    rc = cohort.groupby("sp").agg(rep_n=("repeat", "size"), rep_k=("repeat", "sum"), rep_store=("store_id", "first"))
    rep_store = cohort.groupby("store_id").agg(n=("repeat", "size"), k=("repeat", "sum"))
    later = cohort[cohort.repeat].groupby("store_id").later_rev.mean()
    s = s.join(rc[["rep_n", "rep_k"]]).fillna({"rep_n": 0, "rep_k": 0})
    # peers = other salespeople whose cohort customers first billed at this store
    rc2 = rc.rename(columns={"rep_store": "store_id"})
    rp = _minus_self(rc2, ["rep_n", "rep_k"]).add_prefix("peer_")
    s = s.join(rp)
    st_n = s.store_id.map(rep_store.n)
    st_k = s.store_id.map(rep_store.k)
    s["peer_rep_n"] = s.peer_rep_n.fillna(st_n - s.rep_n)
    s["peer_rep_k"] = s.peer_rep_k.fillna(st_k - s.rep_k)
    s["rep_rate"] = _div(s.rep_k, s.rep_n)
    s["rep_peer_rate"] = _div(s.peer_rep_k, s.peer_rep_n)
    s["rep_z"] = rate_z(s.rep_k, s.rep_n, s.rep_peer_rate)
    s["store_repeat_rs"] = s.store_id.map(later)
    s["rep_rs_week"] = (s.rep_peer_rate - s.rep_rate) * s.rep_n / w.cohort.weeks * s.store_repeat_rs
    rep_ok = s.established & (s.rep_n >= MIN_REPEAT)
    s["rep_level"] = level(s.rep_z, rep_ok & s.active)
    s["role_model"] = rep_ok & s.active & (s.rep_z >= Z_ROLE)

    # Shifts: off-rate, Shifts window vs Baseline
    r = ctx.roster
    def off(win):
        x = r[win.mask(r.date)]
        return x.groupby("salesperson_id").agg(days=("status", "size"), off=("status", lambda v: (v == "Off").sum()))
    orr, ob = off(w.shifts), off(w.baseline)
    s["roster_days_r"] = orr.days.reindex(s.index).fillna(0).astype(int)
    s["off_r"] = _div(orr.off.reindex(s.index), orr.days.reindex(s.index))
    s["roster_days_b"] = ob.days.reindex(s.index).fillna(0).astype(int)
    s["off_b"] = _div(ob.off.reindex(s.index), ob.days.reindex(s.index))
    s["missing_shifts"] = (s.roster_days_r >= MIN_ROSTER_DAYS) & (s.off_r >= OFF_RATE_MIN) & (s.off_r - s.off_b >= OFF_RATE_RISE)

    # Leaver: ≥ 8% of store Baseline bills; last bill in D-90 … D-15; nothing in D-14 … D-1
    bb = b[w.baseline.mask(b.date)]
    sp_b = bb.groupby("sp").size()
    st_b = bb.groupby("store_id").size()
    s["bills_b"] = sp_b.reindex(s.index).fillna(0).astype(int)
    s["share_store_bills_b"] = _div(s.bills_b, s.store_id.map(st_b))
    s["last_bill"] = b.groupby("sp").date.max().reindex(s.index)
    s["last_present"] = r[r.status.eq("Present")].groupby("salesperson_id").date.max().reindex(s.index)
    D = w.as_of
    s["leaver"] = (
        s.established & (s.share_store_bills_b >= LEAVER_SHARE)
        & (s.last_bill >= D - pd.Timedelta(days=90)) & (s.last_bill <= D - pd.Timedelta(days=15))
        & ~s.active
    )
    return s.reset_index()


def store_causes(sp: pd.DataFrame) -> pd.Series:
    """'leaver' / 'missing shifts' per store (leaver wins when both)."""
    out = {}
    for st, g in sp.groupby("store_id"):
        if g.leaver.any():
            out[st] = "leaver"
        elif g.missing_shifts.any():
            out[st] = "missing shifts"
    return pd.Series(out, dtype=object)


# ---- category share --------------------------------------------------------------
def category_metrics(ctx: Ctx, sp: pd.DataFrame) -> pd.DataFrame:
    w, b = ctx.w, ctx.bills
    bs = b[w.salesperson.mask(b.date)]
    q = bs.groupby("sp")[CATEGORIES].sum()
    rv = bs.groupby("sp")[[f"rev_{c}" for c in CATEGORIES]].sum()
    q = q.join(sp.set_index("sp")[["store_id", "items", "active", "established", "name"]], how="inner")
    long = q.reset_index().melt(id_vars=["sp", "store_id", "items", "active", "established", "name"], value_vars=CATEGORIES,
                                var_name="category", value_name="qty")
    long["cat_rev"] = rv.reset_index().melt(id_vars="sp", var_name="c", value_name="r").r.values
    g = long.groupby(["store_id", "category"])
    long["peer_qty"] = g.qty.transform("sum") - long.qty
    long["peer_items"] = long.groupby(["store_id", "category"])["items"].transform("sum") - long["items"]
    long["share"] = _div(long.qty, long["items"])
    long["peer_share"] = _div(long.peer_qty, long.peer_items)
    long["expected"] = long["items"] * long.peer_share
    long["z"] = rate_z(long.qty, long["items"], long.peer_share)
    cat_price = _div(g.cat_rev.transform("sum"), g.qty.transform("sum"))
    long["store_cat_price"] = cat_price
    long["rs_week"] = (long.expected - long.qty) / w.salesperson.weeks * long.store_cat_price
    ok = long.established & long.active & (long.expected >= MIN_CAT_EXPECTED) & (long.qty <= 0.5 * long.expected)
    long["level"] = level(long.z, ok)
    return long


# ---- staffing ---------------------------------------------------------------------
def staffing(ctx: Ctx) -> pd.DataFrame:
    """Average staff present per store and weekday, Recent window (roster ends 31 Oct 2026)."""
    r = ctx.roster[ctx.w.recent.mask(ctx.roster.date) & ctx.roster.status.eq("Present")]
    daily = r.groupby(["store_id", "date"]).size().rename("present").reset_index()
    daily["dow"] = daily.date.dt.day_name().str[:3]
    t = daily.pivot_table(index="store_id", columns="dow", values="present", aggfunc="mean")
    order = [d for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] if d in t]
    t = t[order]
    t["weekday_avg"] = daily[daily.date.dt.dayofweek < 5].groupby("store_id").present.mean()
    t["weekend_avg"] = daily[daily.date.dt.dayofweek >= 5].groupby("store_id").present.mean()
    return t.reset_index()


# ---- card gaps (D15) ----------------------------------------------------------------
LEVER = {"sherwani_addon": "Bigger baskets", "jacket_addon": "Bigger baskets", "discount": "Bigger baskets",
         "ipb": "Bigger baskets", "repeat": "More repeat"}


def card_gaps(sp: pd.DataFrame, cats: pd.DataFrame, w: Windows) -> pd.DataFrame:
    """Each active salesperson × behaviour vs the best active same-store peer with the
    same minimum sample. gap_rs_week > 0 means the peer is ahead (METRICS §4/§5)."""
    s = sp[sp.bills > 0]
    wk, cwk = w.salesperson.weeks, w.cohort.weeks
    parts = []

    def add(beh, value, store_value, peer_ok, vol_unit, higher=True, n=None):
        parts.append(pd.DataFrame({
            "sp": s.sp.values, "name": s.name.values, "store_id": s.store_id.values, "active": s.active.values,
            "behaviour": beh, "value": np.asarray(value, float), "store_value": np.asarray(store_value, float),
            "n": np.asarray(n, float), "own_ok": np.asarray(peer_ok, bool), "peer_ok": np.asarray(peer_ok, bool),
            "vol_unit": np.asarray(vol_unit, float), "higher_better": higher,
        }))

    st_rate = lambda k, n: s.store_id.map(s.groupby("store_id")[k].sum() / s.groupby("store_id")[n].sum())
    add("sherwani_addon", s.shw_rate, st_rate("shw_k", "shw_n"), s.shw_n >= MIN_SHW, s.shw_n / wk * s.store_addon_rs, n=s.shw_n)
    add("jacket_addon", s.kur_rate, st_rate("kur_k", "kur_n"), s.kur_n >= MIN_KUR, s.kur_n / wk * s.store_jacket_rs, n=s.kur_n)
    add("discount", s.disc_pct, st_rate("disc", "mrpv"), s.bills >= MIN_DISC_BILLS, s.mrpv / wk, higher=False, n=s.bills)
    add("ipb", s.ipb, st_rate("items", "bills"), s.bills >= MIN_SP_IPB_BILLS, s.bills / wk * s.store_item_price, n=s.bills)
    add("repeat", s.rep_rate, st_rate("rep_k", "rep_n"), s.rep_n >= MIN_REPEAT, s.rep_n / cwk * s.store_repeat_rs, n=s.rep_n)

    c = cats[cats.sp.isin(s.sp)]
    st_share = c.groupby(["store_id", "category"]).qty.transform("sum") / c.groupby(["store_id", "category"])["items"].transform("sum")
    parts.append(pd.DataFrame({
        "sp": c.sp.values, "name": c.name.values, "store_id": c.store_id.values, "active": c.active.values,
        "behaviour": "share:" + c.category.values, "value": c.share.values, "store_value": st_share.values,
        "n": c["items"].values.astype(float), "own_ok": (c["items"] > 0).values, "peer_ok": (c.qty >= MIN_CAT_EXPECTED).values,
        "vol_unit": (c["items"] / wk * c.store_cat_price).values, "higher_better": True,
    }))
    g = pd.concat(parts, ignore_index=True)

    # best eligible active peer (not self) per store × behaviour
    elig = g[g.active & g.peer_ok & g.value.notna()].copy()
    elig["key"] = np.where(elig.higher_better, elig.value, -elig.value)
    elig = elig.sort_values("key", ascending=False)
    top2 = elig.groupby(["store_id", "behaviour"]).head(2)
    top2 = top2.assign(r=top2.groupby(["store_id", "behaviour"]).cumcount())
    t1 = top2[top2.r == 0].set_index(["store_id", "behaviour"])[["sp", "name", "value"]]
    t2 = top2[top2.r == 1].set_index(["store_id", "behaviour"])[["sp", "name", "value"]]
    g = g.join(t1.add_prefix("b1_"), on=["store_id", "behaviour"]).join(t2.add_prefix("b2_"), on=["store_id", "behaviour"])
    self_best = g.sp.eq(g.b1_sp)
    g["best_peer"] = np.where(self_best, g.b2_sp, g.b1_sp)
    g["best_peer_name"] = np.where(self_best, g.b2_name, g.b1_name)
    g["best_value"] = np.where(self_best, g.b2_value, g.b1_value)
    g = g.drop(columns=[c for c in g.columns if c.startswith(("b1_", "b2_"))])

    # category share: own minimum sample = expected units at the peer's share ≥ 5
    is_share = g.behaviour.str.startswith("share:")
    g.loc[is_share, "own_ok"] = g.loc[is_share, "own_ok"] & (g.loc[is_share, "n"] * g.loc[is_share, "best_value"] >= MIN_CAT_EXPECTED)
    gap = np.where(g.higher_better, g.best_value - g.value, g.value - g.best_value)
    g["gap"] = gap
    g["gap_rs_week"] = gap * g.vol_unit
    g["lever"] = g.behaviour.map(LEVER).fillna("Bigger baskets")
    g = g[g.active & g.own_ok & g.value.notna()]
    return g.drop(columns=["own_ok", "peer_ok", "vol_unit"]).reset_index(drop=True)


# ---- bundle -------------------------------------------------------------------------
@dataclass
class Metrics:
    as_of: pd.Timestamp
    windows: Windows
    data_through: pd.Timestamp
    stores: pd.DataFrame
    cities: pd.DataFrame
    salespeople: pd.DataFrame
    categories: pd.DataFrame
    staffing: pd.DataFrame
    cohort: pd.DataFrame
    card_gaps: pd.DataFrame
    bad_days: pd.DataFrame
    placeholders: list


def compute(prep: Prep, as_of) -> Metrics:
    ctx = context(prep, as_of)
    cohort = repeat_cohort(ctx)
    sp = salesperson_metrics(ctx, cohort)
    causes = store_causes(sp)
    stores = store_metrics(ctx, causes)
    # store repeat (info; METRICS rates repeat vs same-store peers for salespeople)
    rs = cohort.groupby("store_id").agg(rep_n=("repeat", "size"), rep_k=("repeat", "sum"))
    stores = stores.join(rs, on="store_id")
    stores["rep_rate"] = _div(stores.rep_k, stores.rep_n)
    cats = category_metrics(ctx, sp)
    bad = ctx.foot[ctx.foot.bad][["store_id", "date", "footfall", "bills"]].reset_index(drop=True)
    return Metrics(
        as_of=ctx.as_of, windows=ctx.w, data_through=ctx.bills.date.max(), stores=stores, cities=city_metrics(ctx),
        salespeople=sp, categories=cats, staffing=staffing(ctx), cohort=cohort,
        card_gaps=card_gaps(sp, cats, ctx.w), bad_days=bad, placeholders=ctx.placeholders,
    )
