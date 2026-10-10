"""CMS facility data for one hospital (default RWJUH New Brunswick, CCN 310038):
  1. Provider of Services file (QIES, hospital & other facilities), one row through the data.cms.gov API
  2. "Hospital Provider Cost Report" (CMS's curated summary of HCRIS form 2552-10), one row per fiscal year through the API
  3. raw HCRIS 2552-10 numeric file (HOSP10FY<year>.ZIP, ~135 MB): worksheets S-3 Part I (beds, days, discharges by unit),
     A (direct expense by cost centre), B Part I (cost after overhead allocation), C Part I (costs and charges), G-3
Writes data/processed/cms_pos_<ccn>.json, cms_cost_report_summary_<ccn>.json, hcris_<ccn>_fy<year>_lines.csv, hcris_<ccn>_fy<year>.json
Step 3 is heavy: run on deepstack.   python data/fetch/cms_facility.py [--skip-raw]
"""
from __future__ import annotations

import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile

import pandas as pd

from _common import PROCESSED, RAW, UA, download, write_json

CCN = "310038"
POS_API = "https://data.cms.gov/data-api/v1/dataset/8ba0f9b4-9493-4aa0-9f82-44ea9468d1b5/data"   # POS QIES, 2026 Q2
POS_LANDING = "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/provider-of-services-file-quality-improvement-and-evaluation-system"
CR_API = {2024: "https://data.cms.gov/data-api/v1/dataset/44060663-47d8-4ced-a115-b53b4c270acb/data",
          2023: "https://data.cms.gov/data-api/v1/dataset/f08d4c46-c0e4-4bcb-a54a-c62c87d59251/data"}
CR_LANDING = "https://data.cms.gov/provider-compliance/cost-report/hospital-provider-cost-report"
HCRIS_YEAR = 2024
HCRIS_URL = "https://downloads.cms.gov/FILES/HCRIS/HOSP10FY{}.ZIP"

# form CMS-2552-10 line labels (standard cost centres; subscripted lines keep their own labels in the alpha file)
S3_LINES = {"00100": "adults_and_pediatrics", "00700": "total_adults_peds_excl_obs", "00800": "intensive_care_unit", "00900": "coronary_care_unit",
            "01000": "burn_icu", "01100": "surgical_icu", "01200": "other_special_care", "01300": "nursery", "01400": "total_hospital",
            "01600": "subprovider_ipf", "01700": "subprovider_irf", "02700": "total_facility", "02800": "observation_bed_days"}
S3_COLS = {"00200": "beds", "00300": "bed_days_available", "00800": "inpatient_days_total", "01500": "discharges_total"}
COST_LINES = {"03000": "adults_and_pediatrics", "03100": "intensive_care_unit", "03200": "coronary_care_unit", "03300": "burn_icu", "03400": "surgical_icu",
              "03500": "other_special_care", "04300": "nursery", "05000": "operating_room", "05100": "recovery_room", "05200": "labor_delivery",
              "05300": "anesthesiology", "05400": "radiology_diagnostic", "05500": "radiology_therapeutic", "05600": "radioisotope",
              "05700": "ct_scan", "05800": "mri", "05900": "cardiac_catheterization", "06000": "laboratory", "06500": "respiratory_therapy",
              "06900": "electrocardiology", "07100": "medical_supplies_charged", "07200": "implantable_devices", "07300": "drugs_charged",
              "09000": "clinic", "09100": "emergency", "09200": "observation_beds", "20000": "total"}


def api(url: str, **filters) -> list[dict]:
    q = "&".join(f"filter[{urllib.parse.quote(k)}]={urllib.parse.quote(v)}" for k, v in filters.items())
    req = urllib.request.Request(f"{url}?{q}", headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=120))


def main() -> None:
    pos = api(POS_API, PRVDR_NUM=CCN)
    assert len(pos) == 1, len(pos)
    pos = {k: v for k, v in pos[0].items() if v not in ("", None)}
    write_json({"source": {"dataset": "CMS Provider of Services File - Quality Improvement and Evaluation System (hospital & other facilities), 2026 Q2",
                           "api": POS_API, "landing": POS_LANDING, "filter": f"PRVDR_NUM={CCN}"}, "row": pos}, PROCESSED / f"cms_pos_{CCN}.json")
    print({k: pos[k] for k in pos if any(s in k for s in ("BED", "FAC_NAME", "ST_ADR", "CITY", "ROOM", "CNT"))})

    cr = {}
    for fy, url in CR_API.items():
        rows = api(url, **{"Provider CCN": CCN})
        cr[str(fy)] = [{k: v for k, v in r.items() if v not in ("", None)} for r in rows]
    write_json({"source": {"dataset": "CMS Hospital Provider Cost Report (curated from HCRIS form CMS-2552-10)", "api": CR_API, "landing": CR_LANDING,
                           "filter": f"Provider CCN={CCN}"}, "fiscal_years": cr}, PROCESSED / f"cms_cost_report_summary_{CCN}.json")
    if "--skip-raw" in sys.argv:
        return

    z = download(HCRIS_URL.format(HCRIS_YEAR), RAW / "hcris" / f"HOSP10FY{HCRIS_YEAR}.ZIP", timeout=1800)
    with zipfile.ZipFile(z) as zf:
        names = {n.upper(): n for n in zf.namelist()}
        rpt_name = next(v for k, v in names.items() if k.endswith("_RPT.CSV"))
        nmrc_name = next(v for k, v in names.items() if k.endswith("_NMRC.CSV"))
        alpha_name = next(v for k, v in names.items() if k.endswith("_ALPHA.CSV") or k.endswith("_ALPHNMRC.CSV"))
        rpt = pd.read_csv(zf.open(rpt_name), header=None, dtype=str)
        mine = rpt[rpt[2] == CCN]
        print("reports for CCN:", mine.iloc[:, :8].to_string())
        # col 0 rpt_rec_num, 2 prvdr_num, 4 rpt_stus_cd, 5 fy_bgn_dt, 6 fy_end_dt; take the report covering the longest period, latest
        mine = mine.assign(end=pd.to_datetime(mine[6]), beg=pd.to_datetime(mine[5])).sort_values("end")
        rec = mine.iloc[-1]
        rid = rec[0]
        chunks = []
        for ch in pd.read_csv(zf.open(nmrc_name), header=None, dtype=str, chunksize=2_000_000,
                              names=["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "value"]):
            chunks.append(ch[ch["rpt_rec_num"] == rid])
        nm = pd.concat(chunks)
        al = []
        for ch in pd.read_csv(zf.open(alpha_name), header=None, dtype=str, chunksize=2_000_000,
                              names=["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "text"]):
            al.append(ch[(ch["rpt_rec_num"] == rid) & (ch["wksht_cd"] == "A000000") & (ch["clmn_num"] == "00000")])
        labels = pd.concat(al).set_index("line_num")["text"].to_dict()
    nm["value"] = pd.to_numeric(nm["value"], errors="coerce")
    keep = nm[nm["wksht_cd"].isin(["S300001", "A000000", "B000001", "C000001", "G300000", "G200000"])].copy()
    keep["line_label"] = keep["line_num"].map(labels)
    keep.to_csv(PROCESSED / f"hcris_{CCN}_fy{HCRIS_YEAR}_lines.csv", index=False)

    def cell(ws, line, col):
        r = nm[(nm["wksht_cd"] == ws) & (nm["line_num"] == line) & (nm["clmn_num"] == col)]["value"]
        return float(r.iloc[0]) if len(r) else None

    beds = {name: {cn: cell("S300001", ln, cc) for cc, cn in S3_COLS.items()} for ln, name in S3_LINES.items()}
    beds = {k: v for k, v in beds.items() if any(x is not None for x in v.values())}
    # subscripted special-care lines (e.g. 00801 neonatal ICU) are reported with their own labels
    s3 = nm[(nm["wksht_cd"] == "S300001") & (nm["clmn_num"] == "00200")]
    beds_all_lines = {ln: v for ln, v in zip(s3["line_num"], s3["value"])}
    costs = {}
    lines = sorted(set(nm.loc[nm["wksht_cd"].isin(["A000000", "B000001", "C000001"]), "line_num"]))
    for ln in lines:
        base = ln[:3] + "00"
        if base not in COST_LINES and ln not in COST_LINES:
            continue
        row = {"cms_line": ln, "label_in_report": labels.get(ln), "standard_cost_centre": COST_LINES.get(ln, COST_LINES.get(base) + "_subscript"),
               "salaries_wsA_col1": cell("A000000", ln, "00100"), "other_wsA_col2": cell("A000000", ln, "00200"),
               "direct_expense_wsA_col7": cell("A000000", ln, "00700"),
               "cost_after_overhead_wsB1_col26": cell("B000001", ln, "02600"),
               "total_cost_wsC1_col5": cell("C000001", ln, "00500"), "inpatient_charges_wsC1_col6": cell("C000001", ln, "00600"),
               "outpatient_charges_wsC1_col7": cell("C000001", ln, "00700"), "cost_to_charge_wsC1_col9": cell("C000001", ln, "00900")}
        if any(v is not None for k, v in row.items() if k.startswith(("direct", "cost_after", "total_cost"))):
            costs[ln] = row
    out = {"source": {"dataset": f"CMS HCRIS hospital cost report, form CMS-2552-10, fiscal-year file {HCRIS_YEAR}", "url": HCRIS_URL.format(HCRIS_YEAR),
                      "landing": "https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports/hospital-2552-2010-form"},
           "report": {"rpt_rec_num": rid, "provider_ccn": CCN, "fy_begin": rec[5], "fy_end": rec[6], "report_status_code": rec[4],
                      "n_numeric_cells": int(len(nm))},
           "beds_days_discharges_wsS3_part1": beds, "beds_by_line_wsS3_col2": beds_all_lines, "cost_centres": costs,
           "net_patient_revenue_wsG3_line3": cell("G300000", "00300", "00100"), "total_operating_expense_wsG3_line4": cell("G300000", "00400", "00100")}
    write_json(out, PROCESSED / f"hcris_{CCN}_fy{HCRIS_YEAR}.json")
    print(json.dumps(out["report"])); print(json.dumps(beds, indent=0)); print(beds_all_lines)
    print(pd.DataFrame(costs).T[["label_in_report", "direct_expense_wsA_col7", "cost_after_overhead_wsB1_col26", "total_cost_wsC1_col5", "outpatient_charges_wsC1_col7", "inpatient_charges_wsC1_col6"]].to_string())


if __name__ == "__main__":
    main()
