"""CMS HCRIS hospital cost report (form CMS-2552-10), raw fiscal-year file HOSP10FY<year>.ZIP (~135 MB each).

For one CMS number: Worksheet S-3 Part I (beds, bed days, inpatient days, discharges, FTEs, interns and residents by unit),
Worksheet A (direct expense and salaries by cost centre), Worksheet B Part I (cost after overhead step-down),
Worksheet C Part I (charges, cost-to-charge ratio), Worksheet G-3 (net patient revenue, operating expense).
Heavy: parsing the numeric file takes a minute or two and ~3 GB of memory - run on a workstation, not a laptop.
"""
from __future__ import annotations

import zipfile

import pandas as pd

from ._common import RAW, SourceUnavailable, download, norm_ccn, out_dir, write_json

NAME = "hcris"
URL = "https://downloads.cms.gov/FILES/HCRIS/HOSP10FY{}.ZIP"
LANDING = "https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports/hospital-2552-2010-form"
YEARS = (2024, 2023)       # newest first; the first file with a full-year report for the hospital is used
S3_LINES = {"00100": "adults_and_pediatrics", "00700": "total_adults_peds_excl_obs", "00800": "intensive_care_unit", "00900": "coronary_care_unit",
            "01000": "burn_icu", "01100": "surgical_icu", "01200": "other_special_care", "01300": "nursery", "01400": "total_hospital",
            "01600": "subprovider_ipf", "01700": "subprovider_irf", "02700": "total_facility", "02800": "observation_bed_days"}
S3_COLS = {"00200": "beds", "00300": "bed_days_available", "00600": "inpatient_days_title_xviii", "00700": "inpatient_days_title_xix",
           "00800": "inpatient_days_total", "00900": "interns_residents_fte", "01000": "employees_on_payroll_fte",
           "01300": "discharges_title_xviii", "01500": "discharges_total"}
COST_LINES = {"03000": "adults_and_pediatrics", "03100": "intensive_care_unit", "03200": "coronary_care_unit", "03300": "burn_icu", "03400": "surgical_icu",
              "03500": "other_special_care", "04300": "nursery", "05000": "operating_room", "05100": "recovery_room", "05200": "labor_delivery",
              "05300": "anesthesiology", "05400": "radiology_diagnostic", "05500": "radiology_therapeutic", "05600": "radioisotope",
              "05700": "ct_scan", "05800": "mri", "05900": "cardiac_catheterization", "06000": "laboratory", "06500": "respiratory_therapy",
              "06900": "electrocardiology", "07100": "medical_supplies_charged", "07200": "implantable_devices", "07300": "drugs_charged",
              "09000": "clinic", "09100": "emergency", "09200": "observation_beds", "20000": "total"}
S3_TO_A = {"008": "031", "009": "032", "010": "033", "011": "034", "012": "035"}     # special-care S-3 line -> Worksheet A cost-centre line
WORKSHEETS = ["S300001", "A000000", "B000001", "C000001", "G300000", "G200000"]


def _load_report(year: int, ccn: str, force: bool):
    """(report row dict, numeric cells DataFrame, Worksheet A labels dict, download record) or None when the year has no report."""
    z = RAW / "hcris" / f"HOSP10FY{year}.ZIP"
    rec = download(URL.format(year), z, force=force)
    cache = RAW / "hcris" / "reports"
    cache.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        names = {n.upper(): n for n in zf.namelist()}
        rpt = pd.read_csv(zf.open(next(v for k, v in names.items() if k.endswith("_RPT.CSV"))), header=None, dtype=str)
        mine = rpt[rpt[2] == ccn]
        if mine.empty:
            return None
        mine = mine.assign(end=pd.to_datetime(mine[6]), beg=pd.to_datetime(mine[5]))
        mine["days"] = (mine["end"] - mine["beg"]).dt.days + 1
        full = mine[mine["days"] >= 300]
        r = (full if len(full) else mine).sort_values("end").iloc[-1]
        rid = r[0]
        info = {"rpt_rec_num": rid, "provider_ccn": ccn, "fy_begin": r[5], "fy_end": r[6], "fy_days": int(r["days"]), "report_status_code": r[4],
                "process_date": r[7] if len(r) > 7 else None, "hcris_file_year": year,
                "reports_for_ccn_in_file": [{"rpt_rec_num": a, "fy_begin": b, "fy_end": c, "status": d} for a, b, c, d in zip(mine[0], mine[5], mine[6], mine[4])]}
        fn, fa = cache / f"{year}_{rid}_nmrc.csv", cache / f"{year}_{rid}_alpha.csv"
        if fn.exists() and fa.exists() and not force:
            nm = pd.read_csv(fn, dtype=str)
            al = pd.read_csv(fa, dtype=str)
        else:
            cols = ["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "value"]
            nm = pd.concat([ch[ch["rpt_rec_num"] == rid] for ch in pd.read_csv(
                zf.open(next(v for k, v in names.items() if k.endswith("_NMRC.CSV"))), header=None, dtype=str, chunksize=4_000_000, names=cols)])
            al = pd.concat([ch[ch["rpt_rec_num"] == rid] for ch in pd.read_csv(
                zf.open(next(v for k, v in names.items() if k.endswith("_ALPHA.CSV") or k.endswith("_ALPHNMRC.CSV"))), header=None, dtype=str,
                chunksize=4_000_000, names=cols[:4] + ["text"])])
            nm.to_csv(fn, index=False)
            al.to_csv(fa, index=False)
    info["n_numeric_cells"] = int(len(nm))
    nm["value"] = pd.to_numeric(nm["value"], errors="coerce")
    labels = al[(al["wksht_cd"] == "A000000") & (al["clmn_num"] == "00000")].set_index("line_num")["text"].to_dict()
    return info, nm, labels, rec


def fetch(ccn, force: bool = False, years=YEARS) -> dict:
    ccn = norm_ccn(ccn)
    got, tried = None, []
    for y in years:
        got = _load_report(y, ccn, force)
        tried.append(y)
        if got and got[0]["fy_days"] >= 300:
            break
    if not got:
        raise SourceUnavailable(f"no HCRIS 2552-10 report for CCN {ccn} in fiscal-year files {tried}")
    info, nm, labels, rec = got
    year = info["hcris_file_year"]
    idx = {(a, b, c): v for a, b, c, v in zip(nm["wksht_cd"], nm["line_num"], nm["clmn_num"], nm["value"])}

    def cell(ws, line, col):
        v = idx.get((ws, line, col))
        return None if v is None or pd.isna(v) else float(v)

    beds = {name: {cn: cell("S300001", ln, cc) for cc, cn in S3_COLS.items()} for ln, name in S3_LINES.items()}
    beds = {k: v for k, v in beds.items() if any(x is not None for x in v.values())}
    s3 = nm[(nm["wksht_cd"] == "S300001") & (nm["clmn_num"] == "00200")]
    beds_all_lines = {ln: float(v) for ln, v in zip(s3["line_num"], s3["value"])}
    special = []
    for ln in sorted(beds_all_lines):
        if ln[:3] in S3_TO_A:
            a_line = S3_TO_A[ln[:3]] + ln[3:]
            special.append({"s3_line": ln, "worksheet_a_line": a_line, "label_in_report": labels.get(a_line), "standard_unit": S3_LINES.get(ln[:3] + "00"),
                            "beds": beds_all_lines[ln], "inpatient_days_total": cell("S300001", ln, "00800"),
                            "cost_after_overhead_wsB1_col26": cell("B000001", a_line, "02600")})
    costs = {}
    for ln in sorted(set(nm.loc[nm["wksht_cd"].isin(["A000000", "B000001", "C000001"]), "line_num"])):
        base = ln[:3] + "00"
        if base not in COST_LINES and ln not in COST_LINES:
            continue
        row = {"cms_line": ln, "label_in_report": labels.get(ln), "standard_cost_centre": COST_LINES.get(ln, COST_LINES.get(base, "") + "_subscript"),
               "salaries_wsA_col1": cell("A000000", ln, "00100"), "other_wsA_col2": cell("A000000", ln, "00200"),
               "direct_expense_wsA_col7": cell("A000000", ln, "00700"), "cost_after_overhead_wsB1_col26": cell("B000001", ln, "02600"),
               "total_cost_wsC1_col5": cell("C000001", ln, "00500"), "inpatient_charges_wsC1_col6": cell("C000001", ln, "00600"),
               "outpatient_charges_wsC1_col7": cell("C000001", ln, "00700"), "cost_to_charge_wsC1_col9": cell("C000001", ln, "00900")}
        if any(v is not None for k, v in row.items() if k.startswith(("direct", "cost_after", "total_cost"))):
            costs[ln] = row
    out = {"source": {"dataset": f"CMS HCRIS hospital cost report, form CMS-2552-10, fiscal-year file {year}", "dataset_id": f"HOSP10FY{year}",
                      "release": f"fiscal-year file {year} as downloaded", "url": URL.format(year), "landing": LANDING,
                      "raw_file": f"data/raw/hcris/HOSP10FY{year}.ZIP", "bytes": rec["bytes"], "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"],
                      "filter": f"RPT file column 3 (provider number) == '{ccn}', latest report covering >= 300 days -> rpt_rec_num {info['rpt_rec_num']}; "
                                f"numeric cells of worksheets {WORKSHEETS}"},
           "ccn": ccn, "report": info, "beds_days_discharges_wsS3_part1": beds, "beds_by_line_wsS3_col2": beds_all_lines, "special_care_units": special,
           "cost_centres": costs,
           "total_patient_revenue_wsG3_line1": cell("G300000", "00100", "00100"),
           "net_patient_revenue_wsG3_line3": cell("G300000", "00300", "00100"), "total_operating_expense_wsG3_line4": cell("G300000", "00400", "00100"),
           "inpatient_revenue_wsG2_line28_col1": cell("G200000", "02800", "00100"), "outpatient_revenue_wsG2_line28_col2": cell("G200000", "02800", "00200"),
           "total_revenue_wsG2_line28_col3": cell("G200000", "02800", "00300")}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
