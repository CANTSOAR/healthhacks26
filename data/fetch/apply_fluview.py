"""Write CDC ILINet-derived values into catalog/event.yaml (flu_wave) and annotate patient.arrival_month_profile. Run after fluview.py and nhamcs.py."""
import json

from _catalog_edit import set_attr
from _common import PROCESSED

o = json.loads((PROCESSED / "fluview_ili_summary.json").read_text()); h = o["hhs2"]; n = o["nat"]
U = o["source"]["url"]; F = "data/processed/fluview_ili_summary.json"
DS = ("CDC ILINet weekly weighted percent of outpatient visits for influenza-like illness (wILI), HHS Region 2 (NJ, NY, PR, VI), obtained through the Delphi Epidata API mirror; "
      f"{h['n_seasons']} seasons {h['seasons_used'][0]} to {h['seasons_used'][-1]} excluding 2019-20, 2020-21, 2021-22")
E = ["variants", "flu_wave", "attributes"]
print(set_attr("catalog/event.yaml", E + ["duration_days"], {
    "value": int(h["wave_duration_days_median"]), "unit": "days", "source": "measured",
    "citation": f"{DS}; per season, number of weeks with wILI at or above the off-season baseline (mean of weeks 21-39) plus half of the peak excess, x7; median across seasons",
    "url": U, "file": F, "range": h["wave_duration_days_range"],
    "note": f"Width of the wave at half its height; range = shortest to longest season. National median {int(n['wave_duration_days_median'])} days. Weeks above baseline + 2 SD "
            f"(a looser definition) median {h['weeks_above_baseline_plus_2sd_median']:.0f} weeks. Per-season values: data/processed/fluview_ili_seasons.csv. Wave 0 placeholder was 42."}))
print(set_attr("catalog/event.yaml", E + ["respiratory_share_uplift"], {
    "value": h["mean_wave_excess_share_median"], "unit": "absolute share", "source": "measured",
    "citation": f"{DS}; mean excess of wILI over the off-season baseline during the wave weeks (as defined for duration_days), median across seasons, expressed as a share of visits",
    "url": U, "file": F, "range": h["mean_wave_excess_share_range"],
    "note": "PROXY: ILINet measures influenza-like illness as a share of OUTPATIENT-provider visits (it includes some EDs and urgent care), not the respiratory share of this "
            f"hospital's ED arrivals. Peak-week excess median {h['peak_excess_share_median']}; peak wILI is {h['peak_over_baseline_median']}x the off-season baseline "
            f"(range {h['peak_over_baseline_range']}). Wave 0 placeholder was 0.12."}))
print(set_attr("catalog/event.yaml", E + ["frequency_per_year"], {
    "value": 1, "unit": "per year", "source": "measured",
    "citation": f"{DS}; share of seasons with at least 4 weeks of wILI above baseline + 2 SD = {h['seasons_with_wave_share']}; modal peak MMWR week {h['peak_week_mode']}",
    "url": U, "file": F, "note": "One wave every season in the seasons used; the peak falls in late December to February."}))
p = json.loads((PROCESSED / "nhamcs_ed_arrival_profiles.json").read_text())["month"]
print(set_attr("catalog/patient.yaml", ["shared", "arrival_month_profile"], {
    "note": "STILL ASSUMED after checking two sources. (1) NHAMCS cannot support a month profile: each hospital reports one 4-week period, and the pooled 8-year estimate "
            f"{p['arrival_month_profile_jan0']} has a between-year SD of 0.13-0.41 per month (data/processed/nhamcs_ed_arrival_profiles.json) - noise, not seasonality. "
            f"(2) CDC ILINet (HHS Region 2) gives the seasonal SHAPE of influenza-like illness only: monthly mean wILI percent {h['monthly_mean_wili_jan0']} "
            "(data/processed/fluview_ili_summary.json), i.e. a winter excess of roughly 2-4 percent of visits over summer, consistent in direction with the assumed winter "
            "multipliers of 1.02-1.06 but not a measurement of total ED volume."}))
