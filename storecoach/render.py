"""Step 5 — write the site's JSON (output contract, PLAN §3 + D18).

    site/data/runs/<as_of>.json    one morning
    site/data/index.json           {"latest", "runs", "generated_at"}
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime

import numpy as np

from .coach import IST

SITE_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "data")


def _clean(x):
    """numpy → plain Python, NaN → None, so the JSON is strict."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) else float(x)
    return x


def write_run(run: dict, out_dir: str = SITE_DATA) -> str:
    os.makedirs(os.path.join(out_dir, "runs"), exist_ok=True)
    path = os.path.join(out_dir, "runs", f"{run['as_of']}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_clean(run), fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


def write_index(latest: str, out_dir: str = SITE_DATA) -> str:
    runs = sorted(f[:-5] for f in os.listdir(os.path.join(out_dir, "runs")) if f.endswith(".json"))
    idx = {"latest": latest, "runs": runs, "generated_at": datetime.now(IST).isoformat(timespec="seconds")}
    path = os.path.join(out_dir, "index.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=1)
    return path
