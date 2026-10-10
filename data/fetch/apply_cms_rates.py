"""Write Medicare IPPS / OPPS payment values into catalog/patient.yaml and catalog/equipment.yaml. Run after cms_rates.py."""
import json

import pandas as pd

from _catalog_edit import set_attr
from _common import PROCESSED

ip = json.loads((PROCESSED / "ipps_fy2027_hospital_310038.json").read_text())
op = pd.read_csv(PROCESSED / "opps_2026jul_selected_codes.csv", dtype={"hcpcs": str, "apc": str}).set_index("hcpcs")
c = ip["computed"]; r = ip["impact_file_row"]
OU = "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/addendum-a-b-updates"
OF = "data/processed/opps_2026jul_selected_codes.csv"
adj = float(op["wage_adjustment"].iloc[0])
OD = (f"CMS OPPS Addendum B, July 2026 update (national unadjusted payment rate by HCPCS code), wage-adjusted for CCN 310038 as rate x (0.6 x wage index "
      f"{r['FY 2027 Wage Index']} + 0.4) = x{adj}")

print(set_attr("catalog/patient.yaml", ["shared", "inpatient_revenue"], {
    "value": round(c["payment_at_hospital_cmi"]), "unit": "usd/stay", "source": "measured",
    "citation": "CMS IPPS FY 2027 final rule + correction notice: Tables 1A/1D standardized amounts (labor "
                f"{ip['table_1a_full_update_wage_index_gt_1']['labor_related']}, nonlabor {ip['table_1a_full_update_wage_index_gt_1']['nonlabor_related']}, capital {ip['table_1d_capital_rate']}) "
                f"and Impact File row for CCN 310038 (wage index {r['FY 2027 Wage Index']}, teaching factor {r['TCHOP']}, DSH factor {r['DSHOPP']}, capital GAF {r['GAF']}, "
                f"transfer-adjusted case-mix index {c['case_mix_index_TACMIV44']}, uncompensated-care amount per claim {c['uncompensated_care_per_claim']}); {c['formula']}",
    "url": ip["source"]["ipps_page"], "file": "data/processed/ipps_fy2027_hospital_310038.json",
    "range": [round(c["payment_at_weight_1"]), round(c["payment_at_hospital_cmi"])],
    "note": f"Medicare fee-for-service basis (other payers through payer_revenue_multiplier). BASE-RATE ASSUMPTION: the stay is paid at this hospital's average Medicare case-mix "
            f"index ({c['case_mix_index_TACMIV44']}, all Medicare discharges including transplant and cardiac surgery); medical admissions through the ED are on average lighter, so this is an upper "
            f"estimate - lower end of range = a DRG weight of 1.0 ({round(c['payment_at_weight_1'])} usd). Payment per unit of DRG weight = {round(c['operating_per_unit_weight'] + c['capital_per_unit_weight'])} usd. "
            "Cross-check: the hospital's FY2024 cost report gives net patient revenue 1,665,310,131 usd x inpatient share of charges 0.689 / 36,561 discharges = about 31,400 usd per discharge, all payers. "
            "MS-DRG weights and mean LOS: data/processed/ipps_fy2027_table5_msdrg.csv."}))

ESI_CODE = {1: "99291", 2: "99285", 3: "99284", 4: "99283", 5: "99282"}
for i, code in ESI_CODE.items():
    row = op.loc[code]
    print(set_attr("catalog/patient.yaml", ["variants", f"esi{i}", "attributes", "revenue_ed_visit"], {
        "value": float(row["payment_rate_wage_adjusted_310038"]), "unit": "usd/visit", "source": "measured",
        "citation": f"{OD}; HCPCS {code} (APC {row['apc']}), national rate {row['payment_rate_national_unadjusted']}",
        "url": OU, "file": OF,
        "note": f"MAPPING ASSUMPTION: triage level {i} is billed as visit code {code} "
                "(level 1 -> critical care first hour, levels 2-5 -> ED visit levels 5-2; the lowest visit level 99281 is not used). In practice the billed level follows documented "
                "resources, not the triage level. Hospital facility payment on the Medicare basis only: no physician professional fee; many ancillaries are packaged into it."}))

groups = {"ct": ("ct", "5522/5571/5523/5572"), "xray": ("xray", None), "ultrasound": ("ultrasound", None), "mri": ("mri", None)}
pick = {"xray": "71046", "ultrasound": "76700", "mri": "70551"}
for eq in ["ct", "xray", "ultrasound", "mri"]:
    g = op[op["group"] == eq]
    lo, hi = float(g["payment_rate_wage_adjusted_310038"].min()), float(g["payment_rate_wage_adjusted_310038"].max())
    if eq == "ct":
        val = round(float(g["payment_rate_wage_adjusted_310038"].mean()), 2)
        how = f"unweighted mean over {len(g)} common ED CT codes ({', '.join(g.index)}; APCs {', '.join(sorted(set(g['apc'])))})"
        note = "Unweighted across codes (no ED volume by code was obtained); range = cheapest to dearest of those codes. "
    else:
        row = g.loc[pick[eq]]
        val = float(row["payment_rate_wage_adjusted_310038"])
        how = f"HCPCS {pick[eq]} (APC {row['apc']}), national rate {row['payment_rate_national_unadjusted']}"
        note = "One representative code; range = the other fetched codes of this modality. "
    si = sorted(set(g["status_indicator"]))
    note += (f"Status indicators {si}: Q1 services are PACKAGED (no separate payment) when billed on the same claim as an ED visit, Q3 services may be paid as a composite - "
             "so this is the stand-alone rate and an upper bound on the marginal Medicare payment during an ED visit. Facility payment only, no radiologist fee.")
    print(set_attr("catalog/equipment.yaml", ["variants", eq, "attributes", "revenue_per_use"], {
        "value": val, "unit": "usd", "source": "measured", "citation": f"{OD}; {how}", "url": OU, "file": OF, "range": [lo, hi], "note": note}))

import yaml
from _common import REPO
sp = yaml.safe_load((REPO / "catalog/space.yaml").read_text())["variants"]
w = sp["ward_unit"]["attributes"]; ward_bed = w["fixed_cost_per_hour"]["value"] / w["capacity"]["value"]; icu = sp["icu_bed"]["attributes"]["fixed_cost_per_hour"]["value"]
print(set_attr("catalog/space.yaml", ["variants", "stepdown_bed", "attributes", "fixed_cost_per_hour"], {
    "value": round((ward_bed * icu) ** 0.5, 1), "source": "assumed",
    "citation": f"Assumed: geometric mean of the measured ward cost per bed-hour ({ward_bed:.1f}) and ICU cost per bed-hour ({icu}); the hospital's cost report has no step-down cost centre",
    "note": "Re-based so that step-down sits between ward and ICU after those were replaced by cost-report values. Wave 0 placeholder was 4.58."}))
