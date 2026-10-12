"""Medicare payment rates for one hospital.

  IPPS FY 2027 final rule + correction notice: Tables 1A/1D (standardized amounts), Table 5 (MS-DRG weights) and the Impact
  File row of the hospital (wage index, teaching and disproportionate-share factors, capital GAF, case-mix index,
  uncompensated-care amount, labour market area, county).
  OPPS July 2026 Addendum B: ED visit levels and common ED imaging codes, wage-adjusted with the same wage index.
Generalises data/fetch/cms_rates.py (which was written for CCN 310038). The descriptor column of Addendum B is AMA CPT text
and is deliberately not copied into the tracked extract.
"""
from __future__ import annotations

import warnings
import zipfile

import pandas as pd

from ._common import RAW, SourceUnavailable, clean, download, norm_ccn, out_dir, write_json

NAME = "cms_rates"
BASE = "https://www.cms.gov/files/zip/"
FILES = {"table5": "fy2027-ipps-fr-table-5.zip", "table1": "fy2027-ipps-fr-table-1a-1e.zip", "impact": "fy2027-ipps-fr-impact-file.zip",
         "opps": "july-2026-opps-addendum-b.zip"}
IPPS_PAGE = "https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2027-ipps-final-rule-home-page"
OPPS_PAGE = "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/addendum-a-b-updates"
RAWDIR = RAW / "cms_rates"
OPPS_CODES = {"ed_visit": ["99281", "99282", "99283", "99284", "99285", "99291", "G0380", "G0381", "G0382", "G0383", "G0384"],
              "ct": ["70450", "70496", "70498", "71250", "71260", "71275", "72125", "74176", "74177", "74178"],
              "xray": ["71045", "71046", "72100", "73030", "73110", "73130", "73562", "73610", "73630"],
              "ultrasound": ["76700", "76705", "76770", "76830", "76856", "76870", "93970", "93971"],
              "mri": ["70551", "70553", "72141", "72148"]}
FORMULA = ("operating = (labor*wage_index + nonlabor) * (1 + TCHOP + DSHOPP); capital = capital_rate * GAF * (1 + TCHCP + DSHCPP); "
           "payment(weight) = (operating + capital) * weight + UCP per claim. Outliers, VBP/readmission/HAC adjustments, new-technology add-ons, "
           "transfers and any hospital-specific (sole community / Medicare-dependent) rate are ignored.")


def _xlsx(key: str, contains: str = "", force: bool = False):
    rec = download(BASE + FILES[key], RAWDIR / FILES[key], force=force)
    d = RAWDIR / FILES[key][:-4]
    with zipfile.ZipFile(RAWDIR / FILES[key]) as zf:
        zf.extractall(d)
    f = [p for p in sorted(d.rglob("*.xlsx")) if contains.lower() in p.name.lower()][0]
    return pd.ExcelFile(f), rec


def _national(force: bool) -> dict:
    """Parse the four workbooks once; cache as CSV/JSON next to the downloads."""
    import json
    warnings.filterwarnings("ignore")
    cache = RAWDIR / "parsed"
    cache.mkdir(parents=True, exist_ok=True)
    meta_f, imp_f, opps_f = cache / "national.json", cache / "impact.csv", cache / "opps_selected.csv"
    if meta_f.exists() and imp_f.exists() and opps_f.exists() and not force:
        return json.loads(meta_f.read_text())
    recs = {}
    x, recs["table5"] = _xlsx("table5", force=force)
    t5 = x.parse([s for s in x.sheet_names if "CN" in s][0], header=1, dtype=str)
    t5.columns = ["ms_drg", "post_acute_drg", "special_pay_drg", "mdc", "type", "title", "weight_before_cap", "weight", "geometric_mean_los", "arithmetic_mean_los"][:len(t5.columns)]
    t5 = t5[t5["ms_drg"].str.fullmatch(r"\d{3}", na=False)]
    for c in ["weight", "arithmetic_mean_los"]:
        t5[c] = pd.to_numeric(t5[c], errors="coerce")
    med = t5[t5["type"] == "MED"]
    x, recs["table1"] = _xlsx("table1", force=force)
    t1 = x.parse([s for s in x.sheet_names if "CN" in s][0], header=None)
    rows = [[v for v in r if pd.notna(v)] for r in t1.values.tolist()]
    i1a = next(i for i, r in enumerate(rows) if r and str(r[0]).startswith("TABLE 1A"))
    amounts = next(r for r in rows[i1a + 1:] if len(r) >= 8 and all(isinstance(v, (int, float)) for v in r[:8]))
    i1d = next(i for i, r in enumerate(rows) if r and str(r[0]).startswith("TABLE 1D"))
    capital = next(float(r[1]) for r in rows[i1d + 1:] if r and str(r[0]).strip() == "National")
    x, recs["impact"] = _xlsx("impact", force=force)
    imp = x.parse([s for s in x.sheet_names if "CN" in s][0], header=1, dtype={"Provider Number": str})
    imp["Provider Number"] = imp["Provider Number"].astype(str).str.zfill(6)
    imp.to_csv(imp_f, index=False)
    x, recs["opps"] = _xlsx("opps", "addendum b", force=force)
    ab = x.parse(x.sheet_names[0], header=None, dtype=str)
    hdr = next(i for i in range(30) if str(ab.iloc[i, 0]).strip() == "HCPCS Code")
    ab.columns = [str(c).strip() for c in ab.iloc[hdr]]
    ab = ab.iloc[hdr + 1:]
    want = {c: g for g, cs in OPPS_CODES.items() for c in cs}
    sel = ab[ab["HCPCS Code"].isin(want)][["HCPCS Code", "SI", "APC", "Relative Weight", "Payment Rate"]].copy()
    sel.columns = ["hcpcs", "status_indicator", "apc", "relative_weight", "payment_rate_national_unadjusted"]
    sel["group"] = sel["hcpcs"].map(want)
    sel.sort_values(["group", "hcpcs"]).to_csv(opps_f, index=False)
    meta = {"labor": float(amounts[0]), "nonlabor": float(amounts[1]), "capital": capital, "n_ms_drgs": int(len(t5)), "n_medical_drgs": int(len(med)),
            "unweighted_mean_weight_medical_drgs": round(float(med["weight"].mean()), 4), "files": {k: {"url": v["url"], "sha256": v["sha256"], "bytes": v["bytes"],
                                                                                                      "fetched_utc": v["fetched_utc"]} for k, v in recs.items()}}
    write_json(meta, meta_f)
    return meta


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    nat = _national(force)
    imp = pd.read_csv(RAWDIR / "parsed" / "impact.csv", dtype={"Provider Number": str})
    r = imp[imp["Provider Number"].str.zfill(6) == ccn]
    if r.empty:
        raise SourceUnavailable(f"CCN {ccn} is not in the FY 2027 IPPS Impact File (not paid under IPPS: critical access, Maryland, cancer, children's ... hospital)")
    row = {k: clean(v) for k, v in r.iloc[0].items() if clean(v) is not None}
    wi, cmi = row["FY 2027 Wage Index"], row["TACMIV44"]
    labor, nonlabor, capital = nat["labor"], nat["nonlabor"], nat["capital"]
    operating = (labor * wi + nonlabor) * (1 + row.get("TCHOP", 0) + row.get("DSHOPP", 0))
    cap = capital * row["GAF"] * (1 + row.get("TCHCP", 0) + row.get("DSHCPP", 0))
    ucp = row.get("UCP Per Claim Amount", 0.0)
    adj = round(0.6 * wi + 0.4, 4)
    op = pd.read_csv(RAWDIR / "parsed" / "opps_selected.csv", dtype={"hcpcs": str, "apc": str})
    op["payment_rate_national_unadjusted"] = pd.to_numeric(op["payment_rate_national_unadjusted"], errors="coerce")
    op["payment_rate_wage_adjusted"] = (op["payment_rate_national_unadjusted"] * adj).round(2)
    f0 = nat["files"]["impact"]
    out = {"source": {"dataset": "CMS IPPS FY 2027 final rule + correction notice (Tables 1A-1E, Table 5, Impact File) and OPPS Addendum B, July 2026 update",
                      "dataset_id": "fy2027-ipps-fr / july-2026-opps-addendum-b", "release": "IPPS FY 2027 final rule correction-notice (CN) sheets; OPPS July 2026",
                      "url": BASE + FILES["impact"], "landing": IPPS_PAGE, "opps_landing": OPPS_PAGE, "raw_file": f"data/raw/cms_rates/{FILES['impact']}",
                      "sha256": f0["sha256"], "bytes": f0["bytes"], "fetched_utc": f0["fetched_utc"], "files": {k: {"url": BASE + FILES[k], **v} for k, v in nat["files"].items()},
                      "filter": f"Impact File 'Provider Number' == '{ccn}'; Addendum B 'HCPCS Code' in the selected ED visit and imaging codes"},
           "ccn": ccn, "impact_file_row": row,
           "table_1a_full_update_wage_index_gt_1": {"labor_related": labor, "nonlabor_related": nonlabor}, "table_1d_capital_rate": capital,
           "computed": {"formula": FORMULA, "operating_per_unit_weight": round(operating, 2), "capital_per_unit_weight": round(cap, 2),
                        "uncompensated_care_per_claim": ucp, "case_mix_index_TACMIV44": cmi,
                        "payment_at_weight_1": round(operating + cap + ucp, 2), "payment_at_hospital_cmi": round((operating + cap) * cmi + ucp, 2),
                        "opps_wage_adjustment": adj},
           "table5_summary": {k: nat[k] for k in ["n_ms_drgs", "n_medical_drgs", "unweighted_mean_weight_medical_drgs"]},
           "opps_codes": op.to_dict("records")}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
