"""Write Care Compare validation values into catalog/hospitals/rwjuh_nb.yaml (targeted edits only).
Run after care_compare.py: .venv/bin/python data/fetch/apply_care_compare.py"""
import json

import pandas as pd

from _catalog_edit import set_attr
from _common import PROCESSED

H = "catalog/hospitals/rwjuh_nb.yaml"
A = ["variants", "rwjuh_nb", "attributes"]
d = json.loads((PROCESSED / "care_compare_ed_rwjuh.json").read_text())
peers = pd.read_csv(PROCESSED / "care_compare_ed_peer_groups.csv").set_index(["group", "measure"])
m = {r["Measure ID"]: r for r in d["measures"]}
url = d["source"]["timely"]["landing"]
rel = d["source"]["timely"]["released"]
F = "data/processed/care_compare_ed_rwjuh.json"
ccn = d["facility"]["Facility ID"]
base = f"CMS Care Compare 'Timely and Effective Care - Hospital' (Provider Data Catalog yv7e-xc69, release {rel}), Facility ID (CCN) {ccn} " \
       f"{d['facility']['Facility Name']}, {d['facility']['Address']}, {d['facility']['City/Town']} {d['facility']['State']}"

p = peers.loc[("edv_very_high", "OP_18b")]
print(set_attr(H, A + ["validation_median_ed_time_min"], {
    "value": int(m["OP_18b"]["Score"]), "unit": "minutes", "source": "measured",
    "citation": f"{base}; measure OP_18b score, sample {m['OP_18b']['Sample']} sampled visits, period {m['OP_18b']['Start Date']}-{m['OP_18b']['End Date']}",
    "url": url, "file": F,
    "range": [round(float(p["p10"]), 1), round(float(p["p90"]), 1)],
    "note": "Median minutes from ED arrival to ED departure for DISCHARGED patients only (excludes admitted, transferred and psychiatric patients). "
            f"range = 10th-90th percentile of OP_18b across the {int(p['n_hospitals'])} hospitals in the same 'very high' ED-volume category "
            f"(median {p['median']:.0f}); see data/processed/care_compare_ed_peer_groups.csv. Compare with the simulator's median length of visit of discharged patients.",
    "validation_only": True}))
p = peers.loc[("edv_very_high", "OP_22")]
print(set_attr(H, A + ["validation_lwbs_rate"], {
    "value": round(float(m["OP_22"]["Score"]) / 100, 4), "unit": "fraction", "source": "measured",
    "citation": f"{base}; measure OP_22 score {m['OP_22']['Score']} percent, denominator {m['OP_22']['Sample']} ED visits, period {m['OP_22']['Start Date']}-{m['OP_22']['End Date']}",
    "url": url, "file": F,
    "range": [float(p["p10"]) / 100, float(p["p90"]) / 100],
    "note": "CMS publishes OP_22 as a whole-number percent, so 0.01 means between 0.5% and 1.5%. range = 10th-90th percentile across "
            f"{int(p['n_hospitals'])} 'very high' ED-volume hospitals (median {p['median']:.0f}%).",
    "validation_only": True}))
n = int(m["OP_22"]["Sample"])
print(set_attr(H, A + ["ed_visits_per_year_cms"], {
    "value": n, "unit": "visits/year", "source": "measured",
    "citation": f"{base}; denominator ('Sample') of measure OP_22 = total ED visits reported for {m['OP_22']['Start Date']}-{m['OP_22']['End Date']}",
    "url": url, "file": F,
    "note": f"{n} visits / 366 days = {n/366:.0f} per day. The hospital's own page says 'more than 95,000 emergency and trauma patients a year' "
            "(ed_visits_per_year); the two differ in year and possibly in what is counted (the CCN-level count vs. a marketing figure)."}, create=True))
print(set_attr(H, A + ["ed_volume_category_cms"], {
    "value": m["EDV"]["Score"], "unit": "category", "source": "measured",
    "citation": f"{base}; measure EDV, period {m['EDV']['Start Date']}-{m['EDV']['End Date']}", "url": url, "file": F,
    "note": "CMS EDV categories: low <20,000; medium 20,000-39,999; high 40,000-59,999; very high >=60,000 visits/year"}, create=True))
print(set_attr(H, A + ["cms_certification_number"], {
    "value": ccn, "unit": "identifier", "source": "measured",
    "citation": "CMS Hospital General Information (Provider Data Catalog xubh-q36u), matched on facility name and verified on street address "
                f"({d['facility']['Address']}, {d['facility']['City/Town']}, {d['facility']['State']} {d['facility']['ZIP Code']})",
    "url": d["source"]["general"]["landing"], "file": F}, create=True))

P = "catalog/patient.yaml"
print(set_attr(P, ["shared", "arrivals_per_day"], {
    "value": round(n / 366), "unit": "patients/day", "source": "measured",
    "citation": f"{base}; OP_22 denominator {n} ED visits in {m['OP_22']['Start Date']}-{m['OP_22']['End Date']} / 366 days",
    "url": url, "file": F, "range": [round(n / 366), 260],
    "note": "All ED visits billed under the CMS number, pediatric ED included. Upper end of range = the hospital's own 'more than 95,000 emergency and trauma "
            "patients a year' / 365 (Wave 0 value 260). Hourly, weekday and seasonal variation come from the arrival_*_profile attributes."}))
