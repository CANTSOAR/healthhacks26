"""CMS Provider of Services file (QIES, hospital & other facilities) and the curated 'Hospital Provider Cost Report'
summary, one row each through the data.cms.gov API. POS gives certified beds, operating rooms, cardiac catheterisation
rooms and hospital-wide staffing counts (registered nurses, physicians, ...) as recorded at the last survey."""
from __future__ import annotations

import urllib.parse

from ._common import SourceUnavailable, http_json, norm_ccn, now, out_dir, write_json

NAME = "pos"
POS_VINTAGE = "2026 Q2 (data.cms.gov distribution dated 2026-04-01)"
POS_API = "https://data.cms.gov/data-api/v1/dataset/8ba0f9b4-9493-4aa0-9f82-44ea9468d1b5/data"
POS_LANDING = "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/provider-of-services-file-quality-improvement-and-evaluation-system"
CR_API = {"2024": "https://data.cms.gov/data-api/v1/dataset/44060663-47d8-4ced-a115-b53b4c270acb/data",
          "2023": "https://data.cms.gov/data-api/v1/dataset/f08d4c46-c0e4-4bcb-a54a-c62c87d59251/data"}
CR_LANDING = "https://data.cms.gov/provider-compliance/cost-report/hospital-provider-cost-report"


def _api(url: str, **filters) -> list[dict]:
    q = "&".join(f"filter[{urllib.parse.quote(k)}]={urllib.parse.quote(v)}" for k, v in filters.items())
    return http_json(f"{url}?{q}", timeout=120)


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    rows = _api(POS_API, PRVDR_NUM=ccn)
    if len(rows) != 1:
        raise SourceUnavailable(f"Provider of Services API returned {len(rows)} rows for PRVDR_NUM {ccn}")
    row = {k: v for k, v in rows[0].items() if v not in ("", None)}
    out = {"source": {"dataset": "CMS Provider of Services File - Quality Improvement and Evaluation System (hospital & other facilities)",
                      "dataset_id": "8ba0f9b4-9493-4aa0-9f82-44ea9468d1b5", "release": POS_VINTAGE, "url": POS_API, "landing": POS_LANDING,
                      "filter": f"PRVDR_NUM={ccn}", "fetched_utc": now(), "sha256": None,
                      "note": "API response for one provider; no bulk file was downloaded, so there is no file hash"},
           "ccn": ccn, "row": row, "cost_report_summary": {}}
    cr_src = {"dataset": "CMS Hospital Provider Cost Report (curated from HCRIS form CMS-2552-10)", "api": CR_API, "landing": CR_LANDING,
              "filter": f"Provider CCN={ccn}", "fetched_utc": now()}
    try:
        for fy, url in CR_API.items():
            out["cost_report_summary"][fy] = [{k: v for k, v in r.items() if v not in ("", None)} for r in _api(url, **{"Provider CCN": ccn})]
        out["source"]["cost_report_summary"] = cr_src
    except SourceUnavailable as e:
        out["source"]["cost_report_summary"] = {**cr_src, "unavailable": str(e)}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
