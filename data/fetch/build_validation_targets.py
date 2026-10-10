"""Build catalog/validation_targets.yaml (owned by the data workstream; regenerated whole) from data/processed extracts.
Every attribute is validation_only: a range the simulator's baseline output should land in, never a simulator input."""
import json

import pandas as pd
import yaml

from _common import PROCESSED, REPO

cc = json.loads((PROCESSED / "care_compare_ed_rwjuh.json").read_text())
peers = pd.read_csv(PROCESSED / "care_compare_ed_peer_groups.csv").set_index(["group", "measure"])
acu = pd.read_csv(PROCESSED / "nhamcs_ed_by_acuity.csv", dtype={"acuity": str}).set_index(["subset", "acuity"])
mix = json.loads((PROCESSED / "nhamcs_ed_mix.json").read_text())
m = {r["Measure ID"]: r for r in cc["measures"]}
CC_URL = cc["source"]["timely"]["landing"]
CC = f"CMS Care Compare 'Timely and Effective Care - Hospital' (Provider Data Catalog yv7e-xc69, release {cc['source']['timely']['released']})"
NH_URL = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/nhamcs/stata/"
NH = "CDC/NCHS NHAMCS ED public-use microdata 2019+2021+2022 pooled, weighted by PATWT"


def cc_attr(group, measure, unit, scale=1.0, note=""):
    p = peers.loc[(group, measure)]
    return {"value": round(float(p["median"]) * scale, 4), "unit": unit, "source": "measured",
            "citation": f"{CC}; median of {measure} across {int(p['n_hospitals'])} hospitals in group '{group}' (computed from the hospital-level file)",
            "url": CC_URL, "file": "data/processed/care_compare_ed_peer_groups.csv",
            "range": [round(float(p["p10"]) * scale, 4), round(float(p["p90"]) * scale, 4)],
            "note": ("range = 10th-90th percentile across the group; interquartile range "
                     f"{round(float(p['p25']) * scale, 4)}-{round(float(p['p75']) * scale, 4)}. " + note).strip(),
            "validation_only": True}


def cc_group(group):
    return {
        "median_ed_time_discharged_min": cc_attr(group, "OP_18b", "minutes", note="OP-18b: median minutes arrival to departure for discharged ED patients, excluding psychiatric and transferred patients."),
        "median_ed_time_psych_min": cc_attr(group, "OP_18c", "minutes", note="OP-18c: same, psychiatric/mental-health patients."),
        "lwbs_rate": cc_attr(group, "OP_22", "fraction", 0.01, note="OP-22 is published as a whole-number percent."),
    }


def nh_list(subset, col, unit, what):
    vals = [float(acu.loc[(subset, str(i)), col]) for i in range(1, 6)]
    return {"value": vals, "unit": unit, "index": "acuity_1_to_5", "source": "measured",
            "citation": f"{NH}; {what}; subset {subset}; unweighted visits by level {[int(acu.loc[(subset, str(i)), 'n_unweighted']) for i in range(1, 6)]}",
            "url": NH_URL, "file": "data/processed/nhamcs_ed_by_acuity.csv", "validation_only": True}


def nh_scalar(subset, col, unit, what, lo=None, hi=None, row="all_visits"):
    a = {"value": float(acu.loc[(subset, row), col]), "unit": unit, "source": "measured",
         "citation": f"{NH}; {what}; subset {subset}, {row}, n={int(acu.loc[(subset, row), 'n_unweighted'])}",
         "url": NH_URL, "file": "data/processed/nhamcs_ed_by_acuity.csv", "validation_only": True}
    if lo is not None:
        a["range"] = [float(acu.loc[(subset, row), lo]), float(acu.loc[(subset, row), hi])]
        a["note"] = "range = the other reported quantiles of the same distribution (see citation), not a confidence interval"
    return a


def nh_group(subset):
    return {
        "wait_to_provider_median_min_by_acuity": nh_list(subset, "wait_median", "minutes", "WAITTIME (minutes from arrival to first physician/APRN/PA contact), weighted median"),
        "wait_to_provider_p90_min_by_acuity": nh_list(subset, "wait_p90", "minutes", "WAITTIME, weighted 90th percentile"),
        "length_of_visit_median_min_by_acuity": nh_list(subset, "lov_all_median", "minutes", "LOV (minutes arrival to ED departure, includes boarding), all dispositions, weighted median"),
        "length_of_visit_discharged_median_min_by_acuity": nh_list(subset, "lov_discharged_median", "minutes", "LOV for visits discharged from the ED, weighted median"),
        "length_of_visit_discharged_p90_min_by_acuity": nh_list(subset, "lov_discharged_p90", "minutes", "LOV for visits discharged from the ED, weighted 90th percentile"),
        "length_of_visit_admitted_median_min_by_acuity": nh_list(subset, "lov_admitted_median", "minutes", "LOV for visits admitted to the hospital, weighted median"),
        "wait_to_provider_median_min": nh_scalar(subset, "wait_median", "minutes", "WAITTIME weighted median (range: median to 90th percentile)", "wait_median", "wait_p90"),
        "length_of_visit_median_min": nh_scalar(subset, "lov_all_median", "minutes", "LOV weighted median (range: median to 90th percentile)", "lov_all_median", "lov_all_p90"),
        "length_of_visit_discharged_median_min": nh_scalar(subset, "lov_discharged_median", "minutes", "LOV of discharged visits, weighted median (range: median to 90th percentile)", "lov_discharged_median", "lov_discharged_p90"),
        "boarding_median_min": nh_scalar(subset, "boarded_median", "minutes", "BOARDED (minutes boarded in the ED) among admitted visits with a recorded value, weighted median (range: median to 90th percentile)", "boarded_median", "boarded_p90"),
        "boarding_mean_min": nh_scalar(subset, "boarded_mean", "minutes", "BOARDED among admitted visits with a recorded value, weighted mean"),
        "lwbs_rate": nh_scalar(subset, "p_lwbs", "fraction", "LWBS==1 share of all visits"),
        "left_before_complete_any_rate": nh_scalar(subset, "p_left_any", "fraction", "LWBS, left before treatment complete, or left AMA, share of all visits"),
        "admission_rate": nh_scalar(subset, "p_admit", "fraction", "admitted to this hospital (ADMITHOS or OBSHOS) among visits not LWBS/DOA"),
        "imaging_rate": nh_scalar(subset, "p_imaging", "fraction", "any imaging among visits not LWBS/DOA"),
        "ct_rate": nh_scalar(subset, "p_ct", "fraction", "CT among visits not LWBS/DOA"),
    }


b = (f"{CC}; Facility ID (CCN) {cc['facility']['Facility ID']} {cc['facility']['Facility Name']}, "
     f"{cc['facility']['Address']}, {cc['facility']['City/Town']} {cc['facility']['State']}")
pv = peers.loc[("edv_very_high", "OP_18b")]; pl = peers.loc[("edv_very_high", "OP_22")]; pc = peers.loc[("edv_very_high", "OP_18c")]
rw = {
    "median_ed_time_discharged_min": {
        "value": int(m["OP_18b"]["Score"]), "unit": "minutes", "source": "measured",
        "citation": f"{b}; OP_18b, {m['OP_18b']['Sample']} sampled visits, {m['OP_18b']['Start Date']}-{m['OP_18b']['End Date']}",
        "url": CC_URL, "file": "data/processed/care_compare_ed_rwjuh.json", "range": [float(pv["p10"]), float(pv["p90"])],
        "note": "This hospital's own reported value; range = 10th-90th percentile of 'very high' volume peers. Discharged, non-psychiatric, non-transferred patients only.",
        "validation_only": True},
    "median_ed_time_psych_min": {
        "value": int(m["OP_18c"]["Score"]), "unit": "minutes", "source": "measured",
        "citation": f"{b}; OP_18c, {m['OP_18c']['Sample']} sampled visits, {m['OP_18c']['Start Date']}-{m['OP_18c']['End Date']}",
        "url": CC_URL, "file": "data/processed/care_compare_ed_rwjuh.json", "range": [float(pc["p10"]), float(pc["p90"])],
        "note": f"Only {m['OP_18c']['Sample']} sampled visits - a weak target.", "validation_only": True},
    "lwbs_rate": {
        "value": round(float(m["OP_22"]["Score"]) / 100, 4), "unit": "fraction", "source": "measured",
        "citation": f"{b}; OP_22 = {m['OP_22']['Score']} percent of {m['OP_22']['Sample']} ED visits, {m['OP_22']['Start Date']}-{m['OP_22']['End Date']}",
        "url": CC_URL, "file": "data/processed/care_compare_ed_rwjuh.json", "range": [float(pl["p10"]) / 100, float(pl["p90"]) / 100],
        "note": "Published as a whole-number percent: 0.01 means 0.5%-1.5%. range = 10th-90th percentile of 'very high' volume peers.",
        "validation_only": True},
    "ed_visits_per_year": {
        "value": int(m["OP_22"]["Sample"]), "unit": "visits/year", "source": "measured",
        "citation": f"{b}; OP_22 denominator, {m['OP_22']['Start Date']}-{m['OP_22']['End Date']}", "url": CC_URL,
        "file": "data/processed/care_compare_ed_rwjuh.json",
        "note": "Used as the arrival-rate calibration anchor (patient.shared.arrivals_per_day), so it validates only that the simulator reproduces its own input volume.",
        "validation_only": True},
}

doc = {
    "schema_version": 1,
    "entity_type": "validation_target",
    "description": "Validation targets, NOT simulator inputs. Baseline-management simulator output should land inside these ranges; the report shows whether it does. "
                   "rwjuh_nb = the hospital's own CMS-reported values; cms_* = Care Compare peer groups by ED volume; nhamcs_* = national survey estimates. "
                   "Generated by data/fetch/build_validation_targets.py.",
    "variants": {
        "rwjuh_nb": {"label": "RWJUH New Brunswick, CMS Care Compare (CCN 310038)", "attributes": rw},
        "cms_edv_very_high": {"label": "CMS peer group: very high ED volume (60,000+ visits/year)", "attributes": cc_group("edv_very_high")},
        "cms_edv_high": {"label": "CMS peer group: high ED volume (40,000-59,999)", "attributes": cc_group("edv_high")},
        "cms_edv_medium": {"label": "CMS peer group: medium ED volume (20,000-39,999)", "attributes": cc_group("edv_medium")},
        "cms_edv_low": {"label": "CMS peer group: low ED volume (under 20,000)", "attributes": cc_group("edv_low")},
        "cms_nj_edv_very_high": {"label": "CMS peer group: New Jersey hospitals with very high ED volume", "attributes": cc_group("nj_edv_very_high")},
        "cms_all_hospitals": {"label": "CMS: all reporting hospitals", "attributes": cc_group("all_hospitals")},
        "nhamcs_metro_teaching": {"label": "NHAMCS national: metropolitan hospitals with an EM residency", "attributes": nh_group("metro_teaching")},
        "nhamcs_all_hospitals": {"label": "NHAMCS national: all hospitals", "attributes": nh_group("all_hospitals")},
    },
}
hdr = ("# Catalog file. Shape: contracts/catalog.schema.json. VALIDATION TARGETS ONLY (every attribute has validation_only: true).\n"
       "# Generated by data/fetch/build_validation_targets.py from data/processed/ extracts - edit the script, not this file.\n")
(REPO / "catalog" / "validation_targets.yaml").write_text(hdr + yaml.safe_dump(doc, sort_keys=False, width=140, allow_unicode=True))
print("attributes:", sum(len(v["attributes"]) for v in doc["variants"].values()))
