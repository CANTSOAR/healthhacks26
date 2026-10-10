"""Medicare payment tables.
  IPPS FY2027 final rule + correction notice: Table 5 (MS-DRG weights, geometric/arithmetic mean LOS), Tables 1A-1E
  (standardized amounts), Impact File (hospital-specific wage index, case-mix index, teaching and DSH factors).
  OPPS July 2026 Addendum B (payment by HCPCS code): ED visit levels and common ED imaging codes.
Writes data/processed/ipps_fy2027_table5_msdrg.csv, ipps_fy2027_hospital_310038.json, opps_2026jul_selected_codes.csv
Run: python data/fetch/cms_rates.py   (downloads ~4.5 MB; the impact workbook is slow to parse - fine locally, quicker on deepstack)
"""
from __future__ import annotations

import warnings
import zipfile

import pandas as pd

from _common import PROCESSED, RAW, download, write_json

warnings.filterwarnings("ignore")
CCN = "310038"
BASE = "https://www.cms.gov/files/zip/"
FILES = {"table5": "fy2027-ipps-fr-table-5.zip", "table1": "fy2027-ipps-fr-table-1a-1e.zip", "impact": "fy2027-ipps-fr-impact-file.zip",
         "opps": "july-2026-opps-addendum-b.zip"}
IPPS_PAGE = "https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2027-ipps-final-rule-home-page"
OPPS_PAGE = "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/addendum-a-b-updates"
RAWDIR = RAW / "cms_rates"
# HCPCS/CPT codes pulled from Addendum B (code numbers only; descriptors come from the CMS file's short descriptor column)
OPPS_CODES = {"ed_visit": ["99281", "99282", "99283", "99284", "99285", "99291", "G0380", "G0381", "G0382", "G0383", "G0384"],
              "ct": ["70450", "70496", "70498", "71250", "71260", "71275", "72125", "74176", "74177", "74178"],
              "xray": ["71045", "71046", "72100", "73030", "73110", "73130", "73562", "73610", "73630"],
              "ultrasound": ["76700", "76705", "76770", "76830", "76856", "76870", "93970", "93971"],
              "mri": ["70551", "70553", "72141", "72148"]}


def xlsx(key: str, contains: str = "") -> pd.ExcelFile:
    z = download(BASE + FILES[key], RAWDIR / FILES[key])
    d = RAWDIR / FILES[key][:-4]
    with zipfile.ZipFile(z) as zf:
        zf.extractall(d)
    f = [p for p in sorted(d.rglob("*.xlsx")) if contains.lower() in p.name.lower()][0]
    return pd.ExcelFile(f)


def main() -> None:
    # ---- Table 5 (correction notice sheet)
    x = xlsx("table5")
    sh = [s for s in x.sheet_names if "CN" in s][0]
    t5 = x.parse(sh, header=1, dtype=str)
    t5.columns = ["ms_drg", "post_acute_drg", "special_pay_drg", "mdc", "type", "title", "weight_before_cap", "weight", "geometric_mean_los", "arithmetic_mean_los"][:len(t5.columns)]
    t5 = t5[t5["ms_drg"].str.fullmatch(r"\d{3}", na=False)]
    for c in ["weight_before_cap", "weight", "geometric_mean_los", "arithmetic_mean_los"]:
        t5[c] = pd.to_numeric(t5[c], errors="coerce")
    t5.to_csv(PROCESSED / "ipps_fy2027_table5_msdrg.csv", index=False)

    # ---- Table 1A / 1D
    x = xlsx("table1")
    t1 = x.parse([s for s in x.sheet_names if "CN" in s][0], header=None)
    rows = [[v for v in r if pd.notna(v)] for r in t1.values.tolist()]
    i1a = next(i for i, r in enumerate(rows) if r and str(r[0]).startswith("TABLE 1A"))
    amounts = next(r for r in rows[i1a + 1:] if len(r) >= 8 and all(isinstance(v, (int, float)) for v in r[:8]))
    i1d = next(i for i, r in enumerate(rows) if r and str(r[0]).startswith("TABLE 1D"))
    capital = next(float(r[1]) for r in rows[i1d + 1:] if r and str(r[0]).strip() == "National")
    labor, nonlabor = float(amounts[0]), float(amounts[1])

    # ---- Impact file row
    x = xlsx("impact")
    imp = x.parse([s for s in x.sheet_names if "CN" in s][0], header=1, dtype={"Provider Number": str})
    r = imp[imp["Provider Number"].astype(str).str.zfill(6) == CCN].iloc[0]
    row = {k: (v.item() if hasattr(v, "item") else v) for k, v in r.items() if pd.notna(v)}
    wi, cmi = row["FY 2027 Wage Index"], row["TACMIV44"]
    operating_unit = (labor * wi + nonlabor) * (1 + row["TCHOP"] + row["DSHOPP"])
    capital_unit = capital * row["GAF"] * (1 + row["TCHCP"] + row["DSHCPP"])
    ucp = row["UCP Per Claim Amount"]
    med = t5[t5["type"] == "MED"]
    out = {"source": {"ipps_page": IPPS_PAGE, "files": {k: BASE + v for k, v in FILES.items() if k != "opps"},
                      "sheets": "correction-notice (CN) sheets of the FY 2027 final rule workbooks"},
           "impact_file_row": row,
           "table_1a_full_update_wage_index_gt_1": {"labor_related": labor, "nonlabor_related": nonlabor}, "table_1d_capital_rate": capital,
           "computed": {
               "formula": "operating = (labor*wage_index + nonlabor) * (1 + TCHOP + DSHOPP); capital = capital_rate * GAF * (1 + TCHCP + DSHCPP); "
                          "payment(weight) = (operating + capital) * weight + UCP per claim. Outliers, VBP/readmission/HAC adjustments, new-technology add-ons and transfers ignored.",
               "operating_per_unit_weight": round(operating_unit, 2), "capital_per_unit_weight": round(capital_unit, 2),
               "uncompensated_care_per_claim": ucp, "case_mix_index_TACMIV44": cmi,
               "payment_at_weight_1": round(operating_unit + capital_unit + ucp, 2),
               "payment_at_hospital_cmi": round((operating_unit + capital_unit) * cmi + ucp, 2)},
           "table5_summary": {"n_ms_drgs": int(len(t5)), "n_medical_drgs": int(len(med)),
                              "unweighted_mean_weight_medical_drgs": round(float(med["weight"].mean()), 4),
                              "unweighted_mean_arithmetic_los_medical_drgs": round(float(med["arithmetic_mean_los"].mean()), 2),
                              "note": "unweighted across DRGs (Table 5 has no case counts), so not a case-mix average"}}
    write_json(out, PROCESSED / f"ipps_fy2027_hospital_{CCN}.json")

    # ---- OPPS Addendum B
    x = xlsx("opps", "addendum b")
    ab = x.parse(x.sheet_names[0], header=None, dtype=str)
    hdr = next(i for i in range(30) if str(ab.iloc[i, 0]).strip() == "HCPCS Code")
    ab.columns = [str(c).strip() for c in ab.iloc[hdr]]
    ab = ab.iloc[hdr + 1:]
    want = {c: g for g, cs in OPPS_CODES.items() for c in cs}
    sel = ab[ab["HCPCS Code"].isin(want)][["HCPCS Code", "SI", "APC", "Relative Weight", "Payment Rate"]].copy()
    # the file's descriptor column is AMA CPT text and is deliberately NOT copied into the tracked extract
    sel.columns = ["hcpcs", "status_indicator", "apc", "relative_weight", "payment_rate_national_unadjusted"]
    sel["group"] = sel["hcpcs"].map(want)
    sel["payment_rate_national_unadjusted"] = pd.to_numeric(sel["payment_rate_national_unadjusted"], errors="coerce")
    adj = 0.6 * wi + 0.4
    sel["payment_rate_wage_adjusted_310038"] = (sel["payment_rate_national_unadjusted"] * adj).round(2)
    sel["wage_adjustment"] = round(adj, 4)
    sel.sort_values(["group", "hcpcs"]).to_csv(PROCESSED / "opps_2026jul_selected_codes.csv", index=False)
    print(out["computed"], out["table5_summary"]); print(sel.sort_values(["group", "hcpcs"]).to_string())


if __name__ == "__main__":
    main()
