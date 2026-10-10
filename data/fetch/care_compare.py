"""CMS Care Compare (Provider Data Catalog): ED timeliness measures as VALIDATION TARGETS.

Downloads "Timely and Effective Care - Hospital" (dataset yv7e-xc69) and "Hospital General Information"
(xubh-q36u), resolving the current CSV URL through the Provider Data Catalog metastore API, then writes
  data/processed/care_compare_ed_rwjuh.json        the RWJUH New Brunswick rows + identity check
  data/processed/care_compare_ed_peer_groups.csv   OP-18b / OP-18c / OP-22 distribution by ED-volume category
  data/processed/care_compare_ed_nj_hospitals.csv  the same measures for every NJ hospital
Run: .venv/bin/python data/fetch/care_compare.py
"""
from __future__ import annotations

import json
import urllib.request

import pandas as pd

from _common import PROCESSED, RAW, UA, download, write_json

API = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{}"
DATASETS = {"timely": "yv7e-xc69", "general": "xubh-q36u"}
MEASURES = ["OP_18b", "OP_18c", "OP_22", "EDV"]
RAWDIR = RAW / "care_compare"


def resolve(dataset_id: str) -> dict:
    req = urllib.request.Request(API.format(dataset_id), headers=UA)
    meta = json.load(urllib.request.urlopen(req, timeout=60))
    return {"title": meta["title"], "modified": meta.get("modified"), "released": meta.get("released"),
            "url": meta["distribution"][0]["downloadURL"], "landing": f"https://data.cms.gov/provider-data/dataset/{dataset_id}"}


def num(s):
    return pd.to_numeric(s, errors="coerce")


def main() -> None:
    meta = {k: resolve(v) for k, v in DATASETS.items()}
    te = pd.read_csv(download(meta["timely"]["url"], RAWDIR / "Timely_and_Effective_Care-Hospital.csv"), dtype=str)
    gi = pd.read_csv(download(meta["general"]["url"], RAWDIR / "Hospital_General_Information.csv"), dtype=str)
    write_json(meta, RAWDIR / "resolved_urls.json")

    # identify RWJUH New Brunswick by name + city, then verify address
    cand = gi[gi["Facility Name"].str.contains("ROBERT WOOD JOHNSON", case=False, na=False)]
    print(cand[["Facility ID", "Facility Name", "Address", "City/Town", "State", "ZIP Code"]].to_string())
    rw = cand[(cand["City/Town"].str.upper() == "NEW BRUNSWICK")]
    assert len(rw) == 1, rw
    rw = rw.iloc[0]
    ccn = rw["Facility ID"]

    ed = te[te["Measure ID"].isin(MEASURES)].copy()
    wide_score = ed.pivot_table(index="Facility ID", columns="Measure ID", values="Score", aggfunc="first")
    wide_n = ed.pivot_table(index="Facility ID", columns="Measure ID", values="Sample", aggfunc="first")
    w = wide_score.join(wide_n.add_suffix("_sample"))
    w = w.join(ed.drop_duplicates("Facility ID").set_index("Facility ID")[["Facility Name", "City/Town", "State", "Start Date", "End Date"]])
    for m in ["OP_18b", "OP_18c", "OP_22"]:
        w[m] = num(w[m])
    w = w.join(gi.set_index("Facility ID")[["Hospital Type", "Hospital Ownership", "Emergency Services"]])
    periods = (ed.groupby("Measure ID")[["Start Date", "End Date"]].agg(lambda s: s.mode().iat[0])).to_dict("index")

    rows = []
    def summarize(label, sub):
        for m in ["OP_18b", "OP_18c", "OP_22"]:
            x = sub[m].dropna()
            if len(x) == 0:
                continue
            rows.append({"group": label, "measure": m, "n_hospitals": int(len(x)),
                         "p10": float(x.quantile(.10)), "p25": float(x.quantile(.25)), "median": float(x.median()),
                         "p75": float(x.quantile(.75)), "p90": float(x.quantile(.90)), "mean": round(float(x.mean()), 2)})
    summarize("all_hospitals", w)
    for cat in ["low", "medium", "high", "very high"]:
        summarize(f"edv_{cat.replace(' ', '_')}", w[w["EDV"] == cat])
    acute = w[w["Hospital Type"] == "Acute Care Hospitals"]
    summarize("edv_very_high_acute_care", acute[acute["EDV"] == "very high"])
    summarize("nj_all", w[w["State"] == "NJ"])
    summarize("nj_edv_very_high", w[(w["State"] == "NJ") & (w["EDV"] == "very high")])
    peers = pd.DataFrame(rows)
    peers.to_csv(PROCESSED / "care_compare_ed_peer_groups.csv", index=False)

    nj = w[w["State"] == "NJ"].reset_index()[["Facility ID", "Facility Name", "City/Town", "EDV", "OP_18b", "OP_18b_sample",
                                               "OP_18c", "OP_18c_sample", "OP_22", "OP_22_sample"]]
    nj.to_csv(PROCESSED / "care_compare_ed_nj_hospitals.csv", index=False)

    mine = ed[ed["Facility ID"] == ccn][["Measure ID", "Measure Name", "Score", "Sample", "Footnote", "Start Date", "End Date"]]
    out = {
        "source": meta, "accessed": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "facility": {k: rw[k] for k in ["Facility ID", "Facility Name", "Address", "City/Town", "State", "ZIP Code", "County/Parish",
                                         "Hospital Type", "Hospital Ownership", "Emergency Services", "Hospital overall rating"] if k in rw},
        "measures": mine.to_dict("records"),
        "measure_periods": periods,
        "edv_category_counts": w["EDV"].value_counts().to_dict(),
        "n_hospitals_in_file": int(te["Facility ID"].nunique()),
    }
    write_json(out, PROCESSED / "care_compare_ed_rwjuh.json")
    print(json.dumps(out["facility"], indent=1)); print(mine.to_string()); print(peers.to_string())


if __name__ == "__main__":
    main()
