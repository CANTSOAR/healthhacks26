"""Optional facility-level quality context, cheap to fetch from the CMS Provider Data Catalog:
HCAHPS patient survey (dgck-syfz; star ratings and top-box percentages) and the Hospital Readmissions Reduction
Program file (9n3s-kdb3; excess readmission ratios). Not simulator inputs; reported in DATA.md only."""
from __future__ import annotations

import pandas as pd

from ._common import SourceUnavailable, clean, norm_ccn, out_dir, pdc_dataset, write_json

NAME = "quality"


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    out = {"ccn": ccn, "source": {}, "unavailable": {}}
    try:
        path, src = pdc_dataset("dgck-syfz", force)
        h = pd.read_csv(path, dtype=str)
        h = h[h["Facility ID"] == ccn]
        src["filter"] = f"Facility ID == '{ccn}'"
        keep = ["HCAHPS Measure ID", "HCAHPS Answer Description", "Patient Survey Star Rating", "HCAHPS Answer Percent", "HCAHPS Linear Mean Value",
                "Number of Completed Surveys", "Survey Response Rate Percent", "Start Date", "End Date"]
        rows = [{k: clean(v) for k, v in r.items() if clean(v) not in (None, "Not Applicable")} for r in h[[c for c in keep if c in h.columns]].to_dict("records")]
        out["source"]["hcahps"] = src
        out["hcahps"] = rows
    except SourceUnavailable as e:
        out["unavailable"]["hcahps"] = str(e)
    try:
        path, src = pdc_dataset("9n3s-kdb3", force)
        r = pd.read_csv(path, dtype=str)
        idc = "Facility ID" if "Facility ID" in r.columns else "Facility Id"
        r = r[r[idc].str.zfill(6) == ccn]
        src["filter"] = f"{idc} == '{ccn}'"
        out["source"]["hrrp"] = src
        out["hrrp"] = [{k: clean(v) for k, v in row.items() if k not in (idc, "Facility Name", "State")} for row in r.to_dict("records")]
    except SourceUnavailable as e:
        out["unavailable"]["hrrp"] = str(e)
    if "hcahps" not in out and "hrrp" not in out:
        raise SourceUnavailable("; ".join(out["unavailable"].values()))
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
