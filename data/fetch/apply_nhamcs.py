"""Write NHAMCS-derived values into catalog/patient.yaml (one targeted attribute edit at a time).
Subset rule: 'metro_teaching' (metropolitan hospitals with an EM residency) when the unweighted cell has >= 100 visits,
otherwise 'all_hospitals'. Arrival hour / weekday profiles use all hospitals. Run after nhamcs.py."""
import json

import pandas as pd

from _catalog_edit import set_attr
from _common import PROCESSED

P = "catalog/patient.yaml"
URL = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/nhamcs/stata/"
DS = "CDC/NCHS NHAMCS Emergency Department public-use microdata, 2019+2021+2022 pooled (51,713 sampled visits; 2020 excluded), weighted by PATWT"
MT = "metropolitan hospitals with an emergency medicine residency (MSA==1 & EMEDRES==1; 19,992 sampled visits)"
MIN_N = 100

prof = json.loads((PROCESSED / "nhamcs_ed_arrival_profiles.json").read_text())
mix = json.loads((PROCESSED / "nhamcs_ed_mix.json").read_text())
acu = pd.read_csv(PROCESSED / "nhamcs_ed_by_acuity.csv", dtype={"acuity": str}).set_index(["subset", "acuity"])
tm = json.loads((PROCESSED / "nhamcs_ed_treatment_time_model.json").read_text())


def norm(d: dict) -> dict:
    t = sum(d.values())
    out = {k: round(v / t, 4) for k, v in d.items()}
    k = max(out, key=out.get)
    out[k] = round(out[k] + (1 - sum(out.values())), 4)
    return out


def normlist(x):
    out = [round(v / sum(x), 4) for v in x]
    i = out.index(max(out)); out[i] = round(out[i] + 1 - sum(out), 4)
    return out


def S(path, **f):
    print(path[-1], set_attr(P, path, f))


a = prof["all_hospitals"]
S(["shared", "arrival_hour_profile"], value=[round(v, 3) for v in a["arrival_hour_profile"]], source="measured",
  citation=f"{DS}; variable ARRTIME (arrival time, hour part), all hospitals, {a['hour_n_unweighted']} visits with a recorded time; weighted visits per hour divided by the 24-hour mean",
  url=URL, file="data/processed/nhamcs_ed_arrival_profiles.json",
  note="National shape, not this hospital's. 2.7% of weighted visits have no arrival time and are excluded.")
S(["shared", "arrival_dow_profile"], value=[round(v, 3) for v in a["arrival_dow_profile_mon0"]], source="measured",
  citation=f"{DS}; variable VDAYR (1=Sunday..7=Saturday) re-indexed Monday first, all hospitals; weighted visits per weekday divided by the 7-day mean",
  url=URL, file="data/processed/nhamcs_ed_arrival_profiles.json",
  note="National shape. Each sampled hospital reports a 4-week period, so weekdays are evenly represented.")

m = mix["metro_teaching"]
S(["shared", "acuity_mix"], value=normlist(m["acuity_mix_among_triaged"]), source="measured",
  citation=f"{DS}; variable IMMEDR (triage level 1 immediate .. 5 nonurgent), {MT}; shares among visits with a recorded level 1-5 (unweighted n by level {m['acuity_n_unweighted']})",
  url=URL, file="data/processed/nhamcs_ed_mix.json",
  note=f"IMMEDR is not imputed: only {m['triage_share_with_level_1_to_5']:.0%} of weighted visits in this subset carry a level 1-5 "
       "(the rest are unknown, blank, 'no triage', or in an ED without nursing triage) and are EXCLUDED, i.e. assumed to have the same mix. "
       "NHAMCS rescales hospitals' 3- and 4-level scales to 5 levels, so level 1 is noisier than a true ESI 1. "
       f"All-hospital mix for comparison: {mix['all_hospitals']['acuity_mix_among_triaged']}.")
S(["shared", "condition_mix"], value=norm(m["condition_mix"]), source="measured",
  citation=f"{DS}; variable RFV13D (first-listed reason for visit, NCHS Reason for Visit Classification) mapped by us to nine groups, {MT}",
  url=URL, file="data/processed/nhamcs_ed_mix.json",
  note="The code-range -> condition_group mapping is ours (listed under condition_mapping in the extract and in research/operations-data-sources.md); "
       "groups are by presenting complaint, not final diagnosis. Mix by acuity: data/processed/nhamcs_ed_condition_by_acuity.csv.")
S(["shared", "arrival_mode_mix"], value=norm(m["arrival_mode_mix"]), source="measured",
  citation=f"{DS}; variables ARREMS (arrival by ambulance) and AMBTRANSFER (ambulance arrival transferred from another hospital or urgent care), {MT}",
  url=URL, file="data/processed/nhamcs_ed_mix.json",
  note="transfer = ambulance arrivals transferred from another facility; transfers arriving by other means are not identifiable and sit in walk_in. "
       f"{m['arrival_mode_unknown_share']:.1%} unknown arrival mode excluded.")
amb, amb_src = [], []
for i in range(1, 6):
    sub = "metro_teaching" if acu.loc[("metro_teaching", str(i)), "n_unweighted"] >= MIN_N else "all_hospitals"
    amb.append(round(float(acu.loc[(sub, str(i)), "p_ambulance"]), 3)); amb_src.append(sub)
S(["shared", "ambulance_share_by_acuity"], value=amb, source="measured",
  citation=f"{DS}; share with ARREMS==1 among visits with known arrival mode, by IMMEDR level, {MT}",
  url=URL, file="data/processed/nhamcs_ed_by_acuity.csv",
  note="Includes inter-facility transfers by ambulance. Level 5 is not lower than level 4 in the data (small cell: "
       f"{int(acu.loc[('metro_teaching', '5'), 'n_unweighted'])} visits). All-hospital values: "
       f"{[round(float(acu.loc[('all_hospitals', str(i)), 'p_ambulance']), 3) for i in range(1, 6)]}.")
S(["shared", "age_band_mix"], value=norm(m["age_band_mix"]), source="measured",
  citation=f"{DS}; variable AGE, {MT}", url=URL, file="data/processed/nhamcs_ed_mix.json",
  note="All ages, including children (this subset contains children's hospitals; the all-hospital share under 18 is "
       f"{mix['all_hospitals']['age_band_mix']['age_0_17']:.3f}). RWJUH runs a separate pediatric ED under the same CMS number; "
       "if the simulated stream is adults only, renormalise the three adult bands.")
S(["shared", "payer_mix"], value=norm(m["payer_mix"]), source="measured",
  citation=f"{DS}; variable PAYTYPER (recoded primary expected source of payment), {MT}",
  url=URL, file="data/processed/nhamcs_ed_mix.json",
  note="Mapping: private->commercial; Medicaid/CHIP->medicaid; self-pay + no charge/charity->self_pay; workers' compensation + other->other. "
       f"{m['payer_unknown_share']:.1%} unknown/blank payer excluded. National teaching-hospital mix, not New Jersey's or this hospital's.")

lo = tm["inpatient_los_of_ed_admissions_days"]
S(["shared", "inpatient_los_days"], value=lo["mean"], dist={"mean": lo["mean"], "cv": lo["cv"]}, source="measured",
  citation=f"{DS}; variable LOS (length of hospital stay in days for visits admitted to this hospital, ADMITHOS==1), all hospitals, n={lo['n_unweighted']} "
           f"admissions with a known stay; mean capped at 60 days",
  url=URL, file="data/processed/nhamcs_ed_treatment_time_model.json", range=[lo["p25"], lo["p75"]],
  note=f"Median {lo['median']:.0f} days, 90th percentile {lo['p90']:.0f}. range is the interquartile range. Stays of patients admitted through the ED only.")

names = {"p_imaging": ("ANYIMAGE (any imaging ordered or provided)", "p_imaging", "n_unweighted"),
         "p_ct_given_imaging": ("CATSCAN==1 among visits with ANYIMAGE==1", "p_ct_given_imaging", "n_imaging_unweighted"),
         "p_lab": ("any of 22 blood/urine/culture/toxicology items (CBC, BMP, CMP, cardiac enzymes, urinalysis, cultures ...); rapid flu/COVID/pregnancy/HIV tests not counted", "p_lab", "n_unweighted"),
         "p_admit": ("ADMITHOS==1 or OBSHOS==1 (admitted to this hospital, directly or via observation unit)", "p_admit", "n_unweighted")}
for i in range(1, 6):
    for attr, (desc, col, ncol) in names.items():
        n_t = int(acu.loc[("metro_teaching", str(i)), ncol])
        sub = "metro_teaching" if n_t >= MIN_N else "all_hospitals"
        n = int(acu.loc[(sub, str(i)), ncol])
        other = "all_hospitals" if sub == "metro_teaching" else "metro_teaching"
        note = f"National estimate for triage level {i}; {other} value {float(acu.loc[(other, str(i)), col]):.3f}. Visits that left without being seen and DOA excluded."
        if attr == "p_admit" and i in (1, 5):
            note += (" NHAMCS level 1 mixes true ESI 1 with rescaled 3-/4-level 'immediate' categories, so this is lower than single-site ESI 1 admission rates in the literature."
                     if i == 1 else " Level 5 is not lower than level 4 in the data (small, heterogeneous 'nonurgent' cell).")
        S(["variants", f"esi{i}", "attributes", attr], value=round(float(acu.loc[(sub, str(i)), col]), 3), source="measured",
          citation=f"{DS}; {desc}; IMMEDR=={i}, " + (MT if sub == "metro_teaching" else "all hospitals (teaching-metro cell under 100 visits)") + f", n={n}",
          url=URL, file="data/processed/nhamcs_ed_by_acuity.csv", note=note)
    sub = "metro_teaching" if tm["metro_teaching"]["by_acuity"][f"esi{i}"]["n"] >= MIN_N else "all_hospitals"
    t = tm[sub]; b = t["by_acuity"][f"esi{i}"]; c = t["coefficients_min"]
    S(["variants", f"esi{i}", "attributes", "treatment_min"], value=round(c[f"esi{i}"]), dist={"mean": round(c[f"esi{i}"]), "cv": b["cv"]},
      source="measured",
      citation=f"{DS}; weighted least-squares of (LOV - WAITTIME - BOARDED) minutes on triage-level dummies + X-ray, CT, MRI, ultrasound, lab and admission indicators, "
               f"{MT if sub == 'metro_teaching' else 'all hospitals'}, n={t['n_unweighted']} visits ({b['n']} at level {i}); value = the level-{i} coefficient "
               "= mean minutes from first provider contact to leaving the ED for a visit with no imaging and no lab",
      url=URL, file="data/processed/nhamcs_ed_treatment_time_model.json",
      note=f"Model-derived, R2={t['r2_weighted']}; outcome winsorized at the 99th percentile; cv is the raw coefficient of variation of the outcome at this level. "
           f"Test-attributable minutes in the same model: X-ray {c['xray']}, CT {c['ct']}, MRI {c['mri']}, ultrasound {c['ultrasound']}, lab {c['lab']}, admitted {c['admitted']}. "
           f"Observed mean after provider contact at this level incl. tests: {b['mean_after_provider_min']} (median {b['median_after_provider_min']}). "
           "The value includes provider re-evaluation and discharge processing, so if the simulator adds those separately it should be recalibrated against the "
           "length-of-visit targets in catalog/validation_targets.yaml.")
