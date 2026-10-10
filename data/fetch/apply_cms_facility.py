"""Write CMS POS / HCRIS values into catalog/hospitals/rwjuh_nb.yaml and the cost-derived fixed costs into catalog/space.yaml.
Run after cms_facility.py and apply_care_compare.py."""
import json

import yaml

from _catalog_edit import set_attr
from _common import PROCESSED, REPO

H = "catalog/hospitals/rwjuh_nb.yaml"
A = ["variants", "rwjuh_nb", "attributes"]
SP = "catalog/space.yaml"
h = json.loads((PROCESSED / "hcris_310038_fy2024.json").read_text())
pos = json.loads((PROCESSED / "cms_pos_310038.json").read_text())
cr = json.loads((PROCESSED / "cms_cost_report_summary_310038.json").read_text())["fiscal_years"]["2024"][0]
cc = json.loads((PROCESSED / "care_compare_ed_rwjuh.json").read_text())
visits = int({r["Measure ID"]: r for r in cc["measures"]}["OP_22"]["Sample"])
HOURS = 366 * 24  # FY2024 is a leap year
HC = (f"CMS HCRIS hospital cost report (form CMS-2552-10), FY2024 file, report {h['report']['rpt_rec_num']} for CCN 310038, "
      f"fiscal year {h['report']['fy_begin']}-{h['report']['fy_end']}")
HU = h["source"]["url"]; HF = "data/processed/hcris_310038_fy2024.json"
PC = "CMS Provider of Services file (QIES, hospital & other facilities), 2026 Q2, PRVDR_NUM 310038"
PU = pos["source"]["landing"]; PF = "data/processed/cms_pos_310038.json"
b = h["beds_days_discharges_wsS3_part1"]; bl = h["beds_by_line_wsS3_col2"]; c = h["cost_centres"]; p = pos["row"]


def HS(name, create=True, **f):
    print(name, set_attr(H, A + [name], f, create=create))


tot = b["total_hospital"]
HS("licensed_beds", create=False, value=int(tot["beds"]), unit="beds", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 14 column 2 (total hospital beds available)", url=HU, file=HF,
   note=f"Beds available for use as reported on the cost report, not the state licence. The Provider of Services file lists {p['BED_CNT']} certified beds "
        "(data/processed/cms_pos_310038.json); the FY2023 cost report listed 630. Includes pediatric and neonatal beds (same CMS number).")
adult_icu = int(b["intensive_care_unit"]["beds"] + b["coronary_care_unit"]["beds"] + b["surgical_icu"]["beds"])
HS("icu_beds", value=adult_icu, unit="beds", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I column 2, lines 8 intensive care ({int(b['intensive_care_unit']['beds'])}) + 9 coronary care "
            f"({int(b['coronary_care_unit']['beds'])}) + 11 surgical intensive care ({int(b['surgical_icu']['beds'])})", url=HU, file=HF,
   note="Adult critical care only; neonatal and pediatric ICU are separate attributes.")
HS("nicu_beds", value=int(bl["01200"]), unit="beds", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 12 column 2 (other special care; labelled NEONATAL ICU on Worksheet A line 35)", url=HU, file=HF)
HS("picu_beds", value=int(bl["01201"]), unit="beds", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 12.01 column 2 (labelled PEDIATRIC ICU on Worksheet A line 35.01)", url=HU, file=HF)
HS("routine_beds", value=int(b["adults_and_pediatrics"]["beds"]), unit="beds", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 1 column 2 (adults & pediatrics routine beds)", url=HU, file=HF)
HS("operating_rooms", value=int(p["OPRTG_ROOM_CNT"]), unit="rooms", source="measured", citation=f"{PC}; OPRTG_ROOM_CNT", url=PU, file=PF)
HS("cath_lab_rooms", value=int(p["CRDC_CTHRTZTN_PRCDR_ROOMS_CNT"]), unit="rooms", source="measured", citation=f"{PC}; CRDC_CTHRTZTN_PRCDR_ROOMS_CNT", url=PU, file=PF)
HS("inpatient_discharges_per_year", value=int(tot["discharges_total"]), unit="discharges/year", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 14 column 15", url=HU, file=HF)
HS("inpatient_days_per_year", value=int(tot["inpatient_days_total"]), unit="patient-days/year", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 14 column 8", url=HU, file=HF)
HS("inpatient_alos_days", value=round(tot["inpatient_days_total"] / tot["discharges_total"], 2), unit="days", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 14: total inpatient days {int(tot['inpatient_days_total'])} / total discharges {int(tot['discharges_total'])}", url=HU, file=HF,
   note="All inpatients of this hospital (not only ED admissions). patient.shared.inpatient_los_days uses the national NHAMCS stay length of ED admissions.")
HS("inpatient_occupancy", value=round(tot["inpatient_days_total"] / tot["bed_days_available"], 3), unit="fraction", source="measured",
   citation=f"{HC}; Worksheet S-3 Part I line 14: inpatient days {int(tot['inpatient_days_total'])} / bed days available {int(tot['bed_days_available'])}", url=HU, file=HF,
   note="Annual average occupancy of available beds; a calibration anchor for boarding (little slack downstream).")
e = c["09100"]
HS("ed_direct_cost_per_year", value=int(e["direct_expense_wsA_col7"]), unit="usd/year", source="measured",
   citation=f"{HC}; Worksheet A line 91 (Emergency) column 7, net expenses for allocation; of which salaries (column 1) {int(e['salaries_wsA_col1'])}", url=HU, file=HF)
HS("ed_cost_after_overhead_per_year", value=int(e["cost_after_overhead_wsB1_col26"]), unit="usd/year", source="measured",
   citation=f"{HC}; Worksheet B Part I line 91 (Emergency) column 26, cost after step-down allocation of general service (overhead) cost centres", url=HU, file=HF,
   note="Excludes ancillary departments used by ED patients (laboratory, imaging, pharmacy) and physician professional fees.")
HS("ed_cost_per_visit", value=round(e["cost_after_overhead_wsB1_col26"] / visits, 0), unit="usd/visit", source="measured",
   citation=f"{HC}; Worksheet B Part I line 91 column 26 ({int(e['cost_after_overhead_wsB1_col26'])}) / {visits} ED visits (CMS Care Compare OP-22 denominator, calendar 2024)", url=HU, file=HF,
   note=f"Direct cost only: {e['direct_expense_wsA_col7'] / visits:.0f} usd/visit. ED cost centre only, no ancillaries.")
HS("ed_gross_charges_per_year", value=int(e["inpatient_charges_wsC1_col6"] + e["outpatient_charges_wsC1_col7"]), unit="usd/year", source="measured",
   citation=f"{HC}; Worksheet C Part I line 91 columns 6+7 (inpatient + outpatient charges); cost-to-charge ratio column 9 = {e['cost_to_charge_wsC1_col9']}", url=HU, file=HF,
   note="List charges, not payments.")
r = c["03000"]
HS("routine_cost_per_patient_day", value=round(r["cost_after_overhead_wsB1_col26"] / b["adults_and_pediatrics"]["inpatient_days_total"], 0), unit="usd/patient-day", source="measured",
   citation=f"{HC}; Worksheet B Part I line 30 column 26 ({int(r['cost_after_overhead_wsB1_col26'])}) / Worksheet S-3 Part I line 1 column 8 "
            f"({int(b['adults_and_pediatrics']['inpatient_days_total'])} adults & pediatrics days)", url=HU, file=HF, note="Routine (room, board, nursing) cost only; no ancillaries.")
icu_cost = sum(c[k]["cost_after_overhead_wsB1_col26"] for k in ("03100", "03200", "03400"))
icu_days = sum(b[k]["inpatient_days_total"] for k in ("intensive_care_unit", "coronary_care_unit", "surgical_icu"))
HS("icu_cost_per_patient_day", value=round(icu_cost / icu_days, 0), unit="usd/patient-day", source="measured",
   citation=f"{HC}; Worksheet B Part I lines 31+32+34 column 26 ({int(icu_cost)}) / Worksheet S-3 Part I lines 8+9+11 column 8 ({int(icu_days)} days)", url=HU, file=HF)
HS("net_patient_revenue_per_year", value=int(h["net_patient_revenue_wsG3_line3"]), unit="usd/year", source="measured",
   citation=f"{HC}; Worksheet G-3 line 3; total operating expense (line 4) {int(h['total_operating_expense_wsG3_line4'])}", url=HU, file=HF)
HS("fte_employees", value=float(cr["FTE - Employees on Payroll"]), unit="FTE", source="measured",
   citation="CMS Hospital Provider Cost Report 2024 (curated HCRIS summary), CCN 310038, 'FTE - Employees on Payroll'; interns and residents FTE "
            f"{cr['Number of Interns and Residents (FTE)']}", url="https://data.cms.gov/provider-compliance/cost-report/hospital-provider-cost-report",
   file="data/processed/cms_cost_report_summary_310038.json", note=f"Provider of Services file lists {p['RN_CNT']} registered-nurse FTE hospital-wide.")

# ---- space.yaml: inpatient and OR fixed cost per hour, straight division of a cost centre by its capacity
def SS(variant, **f):
    print(variant, set_attr(SP, ["variants", variant, "attributes", "fixed_cost_per_hour"], f))

ward_bed_hr = r["cost_after_overhead_wsB1_col26"] / b["adults_and_pediatrics"]["beds"] / HOURS
sp = yaml.safe_load((REPO / SP).read_text())
cap = sp["variants"]["ward_unit"]["attributes"]["capacity"]["value"]
SS("ward_unit", value=round(ward_bed_hr * cap, 1), source="measured",
   citation=f"{HC}; Worksheet B Part I line 30 (adults & pediatrics) column 26 = {int(r['cost_after_overhead_wsB1_col26'])} usd / "
            f"{int(b['adults_and_pediatrics']['beds'])} beds / {HOURS} hours = {ward_bed_hr:.1f} usd per bed-hour, times the unit capacity of {cap} beds",
   url=HU, file=HF, note="Fully allocated routine cost INCLUDING ward nursing salaries and overhead (ward staff are not modelled separately); excludes ancillaries. "
                         "Wave 0 placeholder was 58.3.")
icu_bed_hr = icu_cost / adult_icu / HOURS
SS("icu_bed", value=round(icu_bed_hr, 1), source="measured",
   citation=f"{HC}; Worksheet B Part I lines 31+32+34 column 26 = {int(icu_cost)} usd / {adult_icu} adult ICU beds (Worksheet S-3 Part I) / {HOURS} hours",
   url=HU, file=HF, note="Fully allocated cost including ICU nursing salaries and overhead; excludes ancillaries. Wave 0 placeholder was 7.5.")
orc = c["05000"]["cost_after_overhead_wsB1_col26"]
SS("operating_room", value=round(orc / int(p["OPRTG_ROOM_CNT"]) / HOURS, 1), source="measured",
   citation=f"{HC}; Worksheet B Part I line 50 (operating room) column 26 = {int(orc)} usd / {p['OPRTG_ROOM_CNT']} operating rooms (CMS Provider of Services file OPRTG_ROOM_CNT) / {HOURS} hours",
   url=HU, file=HF, note="Averaged over all hours of the year including unstaffed nights; includes OR staff salaries, excludes anaesthesia, recovery, implants. Wave 0 placeholder was 37.5.")

# ---- ED spaces: measured overhead pool, split with the Wave 0 relative weights (the split is an assumption -> stays 'assumed')
hosp = yaml.safe_load((REPO / H).read_text())["variants"]["rwjuh_nb"]["attributes"]
counts = {"triage": hosp["triage_rooms"]["value"], "treatment_bay": hosp["adult_main_bays"]["value"], "resus_bay": hosp["resus_bays"]["value"],
          "fast_track": hosp["fast_track_spaces"]["value"], "peds_ed": hosp["peds_ed_spaces"]["value"], "results_waiting": 1}
W0 = {"triage": 1.0417, "treatment_bay": 2.5, "resus_bay": 6.6667, "fast_track": 1.4583, "peds_ed": 2.5, "results_waiting": 0.4167, "hallway_overflow": 0.8333}
pool = e["cost_after_overhead_wsB1_col26"] - e["direct_expense_wsA_col7"]
k = pool / HOURS / sum(counts[s] * W0[s] for s in counts)
for s, w in W0.items():
    SS(s, value=round(w * k, 1), source="assumed",
       citation=f"Calibrated, split assumed: overhead allocated to the Emergency cost centre = Worksheet B Part I line 91 column 26 minus Worksheet A line 91 column 7 = "
                f"{int(pool)} usd/year ({HC}), spread over the modelled ED spaces {counts} for {HOURS} hours using the Wave 0 relative weights "
                f"(this space type {w}); scale factor {k:.2f}",
       url=HU, file=HF, note="The annual total is measured; how it divides between space types is assumed, hence the 'assumed' tag. Overhead includes employee-benefit, "
                             "administration, plant and housekeeping allocations and so overlaps staff.benefits_load. ED staff salaries are NOT included (staff are costed by wage). "
                             f"Wave 0 placeholder was {w}.")
