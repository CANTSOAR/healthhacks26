"""CDC ILINet (FluView) weekly percent of outpatient visits for influenza-like illness for the hospital's HHS region,
through the Delphi Epidata API (Carnegie Mellon), which mirrors CDC ILINet. Same season definitions as data/fetch/fluview.py."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from ._common import RAW, SourceUnavailable, http_get, norm_ccn, now, out_dir, write_json

NAME = "fluview"
API = "https://api.delphi.cmu.edu/epidata/fluview/?regions=nat,hhs{}&epiweeks=201440-202639"
PANDEMIC_SEASONS = {"2019-20", "2020-21", "2021-22"}
HHS_REGION = {1: "CT ME MA NH RI VT", 2: "NJ NY PR VI", 3: "DE DC MD PA VA WV", 4: "AL FL GA KY MS NC SC TN", 5: "IL IN MI MN OH WI",
              6: "AR LA NM OK TX", 7: "IA KS MO NE", 8: "CO MT ND SD UT WY", 9: "AZ CA HI NV AS GU MP", 10: "AK ID OR WA"}


def region_of(state: str) -> int:
    for r, sts in HHS_REGION.items():
        if state.upper() in sts.split():
            return r
    raise SourceUnavailable(f"no HHS region for state {state!r}")


def fetch(ccn, state: str, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    reg = region_of(state)
    key = f"hhs{reg}"
    url = API.format(reg)
    raw = RAW / "fluview" / f"delphi_fluview_nat_{key}.json"
    if raw.exists() and not force:
        body = raw.read_bytes()
        fetched = json.loads(raw.with_suffix(".meta.json").read_text())["fetched_utc"]
    else:
        body = http_get(url, timeout=180)
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(body)
        fetched = now()
        write_json({"url": url, "fetched_utc": fetched}, raw.with_suffix(".meta.json"))
    epi = json.loads(body).get("epidata")
    if not epi:
        raise SourceUnavailable(f"Delphi Epidata returned no fluview rows for {key}")
    d = pd.DataFrame(epi)[["region", "epiweek", "wili", "release_date"]]
    d["year"] = d["epiweek"] // 100
    d["week"] = d["epiweek"] % 100
    d["season_start"] = np.where(d["week"] >= 40, d["year"], d["year"] - 1)
    d["season"] = d["season_start"].astype(str) + "-" + ((d["season_start"] + 1) % 100).astype(str).str.zfill(2)
    d = d.sort_values(["region", "epiweek"])
    rows = []
    for (rg, season), g in d.groupby(["region", "season"]):
        if len(g) < 48:
            continue
        off = g[(g["week"] >= 21) & (g["week"] <= 39)]["wili"]
        base, sd = off.mean(), off.std()
        thr = base + 2 * sd
        pk = g.loc[g["wili"].idxmax()]
        half = g[g["wili"] >= base + 0.5 * (pk["wili"] - base)]
        rows.append({"region": rg, "season": season, "offseason_baseline_wili": round(base, 3), "peak_wili": round(pk["wili"], 3),
                     "peak_epiweek": int(pk["epiweek"]), "peak_over_baseline": round(pk["wili"] / base, 2), "peak_excess_pp": round(pk["wili"] - base, 3),
                     "weeks_above_threshold": int((g["wili"] > thr).sum()), "weeks_above_half_peak_excess": int(len(half)),
                     "mean_excess_pp_weeks_above_half_peak": round(float((half["wili"] - base).mean()), 3), "pandemic_affected": season in PANDEMIC_SEASONS})
    s = pd.DataFrame(rows)
    out = {"source": {"dataset": "CDC ILINet weighted percent of outpatient visits for influenza-like illness (wILI), via the Delphi Epidata fluview endpoint",
                      "dataset_id": "delphi-epidata/fluview", "release": f"issue of {d['release_date'].max()}, epiweeks 201440-202639", "url": url,
                      "landing": "https://www.cdc.gov/fluview/", "raw_file": f"data/raw/fluview/{raw.name}", "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(), "fetched_utc": fetched,
                      "filter": f"regions nat and {key} (HHS Region {reg}: {HHS_REGION[reg]}); seasons {sorted(PANDEMIC_SEASONS)} excluded from the summary",
                      "definitions": "season = MMWR week 40 to week 39; baseline = mean wILI of weeks 21-39 of that season; wave = weeks with wILI at or above baseline + half the peak excess"},
           "ccn": ccn, "state": state, "hhs_region": reg, "hhs_region_states": HHS_REGION[reg], "region_key": key,
           "seasons": [r for r in rows if r["region"] == key]}
    for rg in [key, "nat"]:
        r = s[(s["region"] == rg) & (~s["pandemic_affected"])]
        dd = d[(d["region"] == rg) & d["season"].isin(r["season"])].copy()
        dd["month"] = (pd.to_datetime(dd["year"].astype(str) + "0104") + pd.to_timedelta((dd["week"] - 1) * 7, unit="D")).dt.month
        mon = dd.groupby("month")["wili"].mean().reindex(range(1, 13))
        out["region" if rg == key else "nat"] = {
            "seasons_used": r["season"].tolist(), "n_seasons": int(len(r)),
            "wave_duration_days_median": float(r["weeks_above_half_peak_excess"].median() * 7),
            "wave_duration_days_range": [int(r["weeks_above_half_peak_excess"].min() * 7), int(r["weeks_above_half_peak_excess"].max() * 7)],
            "weeks_above_baseline_plus_2sd_median": float(r["weeks_above_threshold"].median()),
            "peak_over_baseline_median": float(r["peak_over_baseline"].median()),
            "peak_over_baseline_range": [float(r["peak_over_baseline"].min()), float(r["peak_over_baseline"].max())],
            "peak_excess_share_median": round(float(r["peak_excess_pp"].median()) / 100, 4),
            "mean_wave_excess_share_median": round(float(r["mean_excess_pp_weeks_above_half_peak"].median()) / 100, 4),
            "mean_wave_excess_share_range": [round(float(r["mean_excess_pp_weeks_above_half_peak"].min()) / 100, 4),
                                             round(float(r["mean_excess_pp_weeks_above_half_peak"].max()) / 100, 4)],
            "seasons_with_wave_share": round(float((r["weeks_above_threshold"] >= 4).mean()), 2),
            "peak_week_mode": int((r["peak_epiweek"] % 100).mode().iat[0]),
            "monthly_mean_wili_jan0": [round(float(x), 3) for x in mon]}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
