"""CDC ILINet (FluView) weekly percent of outpatient visits for influenza-like illness, national and HHS Region 2 (NJ, NY, PR, VI).
CDC's own FluView download endpoint (gis.cdc.gov/grasp/flu2/PostPhase02DataDownload) answered 404 on 2026-10-10, so the series is
taken from the Delphi Epidata API (Carnegie Mellon), which mirrors CDC ILINet: https://api.delphi.cmu.edu/epidata/fluview/
Writes data/processed/fluview_ili_weekly.csv, fluview_ili_seasons.csv, fluview_ili_summary.json.   Run: .venv/bin/python data/fetch/fluview.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from _common import PROCESSED, RAW, download, write_json

URL = "https://api.delphi.cmu.edu/epidata/fluview/?regions=nat,hhs2&epiweeks=201440-202639"
PANDEMIC_SEASONS = {"2019-20", "2020-21", "2021-22"}   # ILI signal dominated or suppressed by COVID-19; excluded from the summary


def main() -> None:
    f = download(URL, RAW / "fluview" / "delphi_fluview_nat_hhs2.json")
    d = pd.DataFrame(json.loads(f.read_text())["epidata"])[["region", "epiweek", "wili", "ili", "num_ili", "num_patients", "num_providers", "release_date"]]
    d["year"] = d["epiweek"] // 100; d["week"] = d["epiweek"] % 100
    d["season_start"] = np.where(d["week"] >= 40, d["year"], d["year"] - 1)
    d["season"] = d["season_start"].astype(str) + "-" + ((d["season_start"] + 1) % 100).astype(str).str.zfill(2)
    d = d.sort_values(["region", "epiweek"])
    d.to_csv(PROCESSED / "fluview_ili_weekly.csv", index=False)

    rows = []
    for (reg, season), g in d.groupby(["region", "season"]):
        if len(g) < 48:
            continue
        off = g[(g["week"] >= 21) & (g["week"] <= 39)]["wili"]
        base, sd = off.mean(), off.std()
        thr = base + 2 * sd
        epi = g[g["wili"] > thr]
        # longest run of consecutive weeks above threshold
        above = (g["wili"] > thr).to_numpy(); best = run = 0
        for a in above:
            run = run + 1 if a else 0; best = max(best, run)
        pk = g.loc[g["wili"].idxmax()]
        half = g[g["wili"] >= base + 0.5 * (pk["wili"] - base)]
        rows.append({"region": reg, "season": season, "offseason_baseline_wili": round(base, 3), "threshold_baseline_plus_2sd": round(thr, 3),
                     "peak_wili": round(pk["wili"], 3), "peak_epiweek": int(pk["epiweek"]), "peak_over_baseline": round(pk["wili"] / base, 2),
                     "peak_excess_pp": round(pk["wili"] - base, 3), "weeks_above_threshold": int(len(epi)), "longest_run_weeks": int(best),
                     "weeks_above_half_peak_excess": int(len(half)),
                     "mean_excess_pp_weeks_above_half_peak": round(float((half["wili"] - base).mean()), 3),
                     "pandemic_affected": season in PANDEMIC_SEASONS})
    s = pd.DataFrame(rows)
    s.to_csv(PROCESSED / "fluview_ili_seasons.csv", index=False)

    out = {"source": {"dataset": "CDC ILINet weighted percent of outpatient visits for influenza-like illness (wILI), via Delphi Epidata fluview endpoint",
                      "url": URL, "cdc_page": "https://www.cdc.gov/fluview/", "excluded_seasons": sorted(PANDEMIC_SEASONS),
                      "definitions": "season = MMWR week 40 to week 39; baseline = mean wILI of weeks 21-39 of that season; wave = weeks with wILI at or above baseline + half the peak excess"}}
    for reg in ["hhs2", "nat"]:
        r = s[(s["region"] == reg) & (~s["pandemic_affected"])]
        dd = d[(d["region"] == reg) & (~d["season"].isin(PANDEMIC_SEASONS)) & d["season"].isin(r["season"])].copy()
        dd["month"] = pd.to_datetime(dd["year"].astype(str) + "-1-1") .dt.month  # placeholder, replaced below
        # MMWR week -> approximate calendar month via the Thursday of that week
        dd["month"] = (pd.to_datetime(dd["year"].astype(str) + "0104") + pd.to_timedelta((dd["week"] - 1) * 7, unit="D")).dt.month
        mon = dd.groupby("month")["wili"].mean().reindex(range(1, 13))
        out[reg] = {"seasons_used": r["season"].tolist(), "n_seasons": int(len(r)),
                    "wave_duration_days_median": float(r["weeks_above_half_peak_excess"].median() * 7),
                    "wave_duration_days_range": [int(r["weeks_above_half_peak_excess"].min() * 7), int(r["weeks_above_half_peak_excess"].max() * 7)],
                    "weeks_above_baseline_plus_2sd_median": float(r["weeks_above_threshold"].median()),
                    "peak_over_baseline_median": float(r["peak_over_baseline"].median()),
                    "peak_over_baseline_range": [float(r["peak_over_baseline"].min()), float(r["peak_over_baseline"].max())],
                    "peak_excess_share_median": round(float(r["peak_excess_pp"].median()) / 100, 4),
                    "mean_wave_excess_share_median": round(float(r["mean_excess_pp_weeks_above_half_peak"].median()) / 100, 4),
                    "mean_wave_excess_share_range": [round(float(r["mean_excess_pp_weeks_above_half_peak"].min()) / 100, 4), round(float(r["mean_excess_pp_weeks_above_half_peak"].max()) / 100, 4)],
                    "seasons_with_wave_share": round(float((r["weeks_above_threshold"] >= 4).mean()), 2),
                    "peak_week_mode": int((r["peak_epiweek"] % 100).mode().iat[0]),
                    "monthly_mean_wili_jan0": [round(float(x), 3) for x in mon],
                    "monthly_wili_relative_jan0": [round(float(x), 3) for x in mon / mon.mean()]}
    write_json(out, PROCESSED / "fluview_ili_summary.json")
    print(s[s.region == "hhs2"].to_string()); print(json.dumps({k: out[k] for k in ("hhs2", "nat")}, indent=1))


if __name__ == "__main__":
    main()
