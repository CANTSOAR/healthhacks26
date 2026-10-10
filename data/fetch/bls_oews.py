"""BLS Occupational Employment and Wage Statistics (OEWS) hourly wages for the catalog's staff roles, through the
BLS public API v1 (no key; the bulk zip files on www.bls.gov answer 403 to scripted clients).
Areas: New Jersey statewide (S3400000) and New York-Newark-Jersey City metro (M0035620), all industries.
Writes data/raw/bls/oews_api_response_*.json and data/processed/bls_oews_staff_wages.csv
Run: .venv/bin/python data/fetch/bls_oews.py     (uses 4 of the 25 unkeyed API queries allowed per day)
"""
from __future__ import annotations

import json
import urllib.request

import pandas as pd

from _common import PROCESSED, RAW, write_json

API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
AREAS = {"nj_state": ("S", "3400000"), "ny_newark_metro": ("M", "0035620")}
DATATYPES = {"03": "hourly_mean", "08": "hourly_median", "07": "hourly_p25", "09": "hourly_p75"}
# catalog staff role -> SOC 2018 code(s). The mapping is ours; see research/operations-data-sources.md.
ROLE_SOC = {
    "attending": [("291214", "Emergency Medicine Physicians")],
    "app": [("291171", "Nurse Practitioners"), ("291071", "Physician Assistants")],
    "rn": [("291141", "Registered Nurses")],
    "charge_rn": [("291141", "Registered Nurses (75th percentile used as the charge-nurse proxy)")],
    "tech": [("292042", "Emergency Medical Technicians"), ("311131", "Nursing Assistants")],
    "registration": [("434111", "Interviewers, Except Eligibility and Loan (includes hospital admitting/registration interviewers)")],
    "pharmacist": [("291051", "Pharmacists")],
    "imaging_tech": [("292034", "Radiologic Technologists and Technicians")],
    "transport": [("311132", "Orderlies")],
    "evs": [("372011", "Janitors and Cleaners, Except Maids and Housekeeping Cleaners")],
}


def sid(area_key: str, soc: str, dt: str) -> str:
    t, code = AREAS[area_key]
    return f"OEU{t}{code}000000{soc}{dt}"


def main() -> None:
    socs = sorted({s for v in ROLE_SOC.values() for s, _ in v})
    ids = [sid(a, s, d) for a in AREAS for s in socs for d in DATATYPES]
    got = {}
    for i in range(0, len(ids), 25):
        body = json.dumps({"seriesid": ids[i:i + 25]}).encode()
        req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
        resp = json.load(urllib.request.urlopen(req, timeout=120))
        write_json(resp, RAW / "bls" / f"oews_api_response_{i // 25}.json")
        assert resp["status"] == "REQUEST_SUCCEEDED", resp.get("message")
        for s in resp["Results"]["series"]:
            if s["data"]:
                d = s["data"][0]
                got[s["seriesID"]] = (d["year"], d["value"], "; ".join(f.get("text", "") for f in d.get("footnotes", []) if f))
    names = {s: n for v in ROLE_SOC.values() for s, n in v}
    rows = []
    for a in AREAS:
        for s in socs:
            r = {"area": a, "soc": f"{s[:2]}-{s[2:]}", "occupation": names[s].split(" (")[0]}
            for d, lab in DATATYPES.items():
                y, v, fn = got.get(sid(a, s, d), (None, None, ""))
                r[lab] = pd.to_numeric(v, errors="coerce")
                r["year"] = y or r.get("year")
                r["series_" + lab] = sid(a, s, d)
                if fn:
                    r["footnote"] = fn
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(PROCESSED / "bls_oews_staff_wages.csv", index=False)
    write_json({"api": API, "role_to_soc": {k: [f"{s[:2]}-{s[2:]} {n}" for s, n in v] for k, v in ROLE_SOC.items()}, "areas": AREAS,
                "datatypes": DATATYPES}, PROCESSED / "bls_oews_role_mapping.json")
    print(df[["area", "soc", "occupation", "year", "hourly_mean", "hourly_median", "hourly_p25", "hourly_p75"]].to_string())


if __name__ == "__main__":
    main()
