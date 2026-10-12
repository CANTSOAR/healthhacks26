"""BLS Occupational Employment and Wage Statistics (OEWS) hourly wages for the catalog's staff roles in the hospital's
metropolitan statistical area and state, through the BLS public API v1 (no key: 25 queries a day, 25 series a query, so
every area is cached under data/raw/bls/ and never re-queried). The county -> metropolitan area step uses the Census
Bureau's 2023 core-based statistical area delineation file.
"""
from __future__ import annotations

import json

import pandas as pd

from ._common import PROCESSED, RAW, SourceUnavailable, download, http_get, norm_ccn, now, out_dir, write_json

NAME = "bls_oews"
API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
CBSA_URL = "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx"
DATATYPES = {"03": "hourly_mean", "08": "hourly_median", "07": "hourly_p25", "09": "hourly_p75"}
# catalog staff role -> SOC 2018 code(s); same mapping as data/fetch/bls_oews.py
ROLE_SOC = {
    "attending": ["291214"], "app": ["291171", "291071"], "rn": ["291141"], "charge_rn": ["291141"], "tech": ["292042", "311131"],
    "registration": ["434111"], "pharmacist": ["291051"], "imaging_tech": ["292034"], "transport": ["311132"], "evs": ["372011"]}
SOC_NAME = {"291214": "Emergency Medicine Physicians", "291171": "Nurse Practitioners", "291071": "Physician Assistants", "291141": "Registered Nurses",
            "292042": "Emergency Medical Technicians", "311131": "Nursing Assistants", "434111": "Interviewers, Except Eligibility and Loan",
            "291051": "Pharmacists", "292034": "Radiologic Technologists and Technicians", "311132": "Orderlies",
            "372011": "Janitors and Cleaners, Except Maids and Housekeeping Cleaners"}
ROLE_BASIS = {"attending": "hourly_median", "charge_rn": "hourly_p75"}       # every other role uses the hourly mean
STATE_FIPS = {"AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
              "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
              "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
              "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
              "WV": "54", "WI": "55", "WY": "56", "PR": "72"}
SEED = {"S3400000": "nj_state", "M0035620": "ny_newark_metro"}      # areas already in data/processed/bls_oews_staff_wages.csv


def cbsa_of_county(fips5: str) -> dict:
    rec = download(CBSA_URL, RAW / "bls" / "census_cbsa_list1_2023.xlsx")
    t = pd.read_excel(RAW / "bls" / "census_cbsa_list1_2023.xlsx", skiprows=2, dtype=str)
    t["fips"] = t["FIPS State Code"].str.zfill(2) + t["FIPS County Code"].str.zfill(3)
    r = t[t["fips"] == fips5]
    if r.empty:
        return {"cbsa": None, "county_fips": fips5, "delineation_url": CBSA_URL, "note": "county is not in a core-based statistical area"}
    r = r.iloc[0]
    return {"cbsa": r["CBSA Code"], "cbsa_title": r["CBSA Title"], "kind": r["Metropolitan/Micropolitan Statistical Area"],
            "metropolitan_division": None if pd.isna(r["Metropolitan Division Code"]) else r["Metropolitan Division Code"],
            "county": r["County/County Equivalent"], "county_fips": fips5, "delineation_url": CBSA_URL, "delineation_sha256": rec["sha256"]}


def _sid(area: str, soc: str, dt: str) -> str:
    return f"OEU{area}000000{soc}{dt}"


def _area_series(area: str, force: bool = False) -> dict:
    """{series_id: [year, value, footnote]} for every SOC x datatype of one area ('S3400000' or 'M0035620'); cached."""
    cache = RAW / "bls" / f"oews_{area}.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text())
    socs = sorted({s for v in ROLE_SOC.values() for s in v})
    got = {}
    seed = PROCESSED / "bls_oews_staff_wages.csv"
    if area in SEED and seed.exists() and not force:
        df = pd.read_csv(seed)
        df = df[df["area"] == SEED[area]]
        for _, r in df.iterrows():
            for lab in DATATYPES.values():
                v = r[lab]
                got[r["series_" + lab]] = [str(int(r["year"])), None if pd.isna(v) else str(v), r.get("footnote") if isinstance(r.get("footnote"), str) else ""]
        out = {"area": area, "fetched_utc": "2026-10-10 (by data/fetch/bls_oews.py)", "via": "tracked extract data/processed/bls_oews_staff_wages.csv (same API, no new query)",
               "series": got}
        write_json(out, cache)
        return out
    ids = [_sid(area, s, d) for s in socs for d in DATATYPES]
    for i in range(0, len(ids), 25):
        body = json.dumps({"seriesid": ids[i:i + 25]}).encode()
        resp = json.loads(http_get(API, data=body, headers={"Content-Type": "application/json"}, timeout=120))
        if resp.get("status") != "REQUEST_SUCCEEDED":
            raise SourceUnavailable(f"BLS API: {resp.get('status')} {resp.get('message')}")
        for s in resp["Results"]["series"]:
            if s["data"]:
                d = s["data"][0]
                got[s["seriesID"]] = [d["year"], d["value"], "; ".join(f.get("text", "") for f in d.get("footnotes", []) if f)]
            else:
                got[s["seriesID"]] = [None, None, "no data returned (series does not exist or estimate not released for this area)"]
    out = {"area": area, "fetched_utc": now(), "via": API, "series": got}
    write_json(out, cache)
    return out


def _val(series: dict, area: str, soc: str, col: str):
    dt = next(k for k, v in DATATYPES.items() if v == col)
    y, v, fn = series.get(_sid(area, soc, dt), [None, None, ""])
    try:
        return float(v), y, fn
    except (TypeError, ValueError):
        return None, y, fn


def fetch(ccn, state: str, county_fips: str, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    geo = cbsa_of_county(str(county_fips).zfill(5))
    areas = {}
    if geo.get("cbsa") and "Metropolitan" in (geo.get("kind") or ""):
        areas["metro"] = "M00" + geo["cbsa"]
    if state.upper() in STATE_FIPS:
        areas["state"] = "S" + STATE_FIPS[state.upper()] + "00000"
    if not areas:
        raise SourceUnavailable(f"no BLS area for state {state}, county {county_fips}")
    series, meta, errors = {}, {}, {}
    for kind, area in areas.items():
        try:
            a = _area_series(area, force)
            series[kind] = a["series"]
            meta[kind] = {"area_code": area, "fetched_utc": a["fetched_utc"], "via": a["via"]}
        except SourceUnavailable as e:
            errors[kind] = str(e)
    if not series:
        raise SourceUnavailable("; ".join(errors.values()))
    table = []
    for kind in series:
        for soc in sorted(SOC_NAME):
            row = {"area": kind, "area_code": areas[kind], "soc": f"{soc[:2]}-{soc[2:]}", "occupation": SOC_NAME[soc]}
            for col in DATATYPES.values():
                v, y, fn = _val(series[kind], areas[kind], soc, col)
                row[col] = v
                row["year"] = y or row.get("year")
                if fn:
                    row["footnote"] = fn
            table.append(row)
    roles = {}
    for role, socs in ROLE_SOC.items():
        col = ROLE_BASIS.get(role, "hourly_mean")
        for kind in [k for k in ("metro", "state") if k in series]:
            vals = [_val(series[kind], areas[kind], s, col) for s in socs]
            used_col = col
            if any(v[0] is None for v in vals) and col != "hourly_mean":
                alt = [_val(series[kind], areas[kind], s, "hourly_mean") for s in socs]
                if all(v[0] is not None for v in alt):
                    vals, used_col = alt, "hourly_mean"
            if all(v[0] is not None for v in vals):
                roles[role] = {"value": round(sum(v[0] for v in vals) / len(vals), 2), "area": kind, "area_code": areas[kind], "statistic": used_col,
                               "statistic_wanted": col, "year": vals[0][1],
                               "components": [{"soc": f"{s[:2]}-{s[2:]}", "occupation": SOC_NAME[s], "value": v[0]} for s, v in zip(socs, vals)]}
                break
        else:
            roles[role] = {"value": None, "note": "no published estimate in the metropolitan area or the state for " + ", ".join(SOC_NAME[s] for s in socs)}
    year = next((r["year"] for r in table if r.get("year")), None)
    out = {"source": {"dataset": "BLS Occupational Employment and Wage Statistics (OEWS), all industries, latest annual estimates through the BLS public API v1",
                      "dataset_id": "OEU series", "release": f"May {year} estimates" if year else None, "url": API, "landing": "https://www.bls.gov/oes/",
                      "fetched_utc": "; ".join(f"{k}: {v['fetched_utc']}" for k, v in meta.items()), "sha256": None,
                      "filter": "series OEU<area type><area code>000000<SOC><datatype>, area codes " + ", ".join(f"{k}={v}" for k, v in areas.items())
                                + f"; datatypes {DATATYPES}", "areas": meta, "errors": errors,
                      "note": "API responses, cached per area under data/raw/bls/; no bulk file, so no file hash. Role -> occupation mapping is ours."},
           "ccn": ccn, "geography": geo, "state": state, "areas": areas, "role_to_soc": {k: [f"{s[:2]}-{s[2:]} {SOC_NAME[s]}" for s in v] for k, v in ROLE_SOC.items()},
           "role_wages": roles, "table": table}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
