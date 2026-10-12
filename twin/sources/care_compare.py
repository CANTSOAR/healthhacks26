"""CMS Care Compare 'Timely and Effective Care - Hospital' (Provider Data Catalog yv7e-xc69).

Keeps every measure row of the hospital (ED timeliness OP-18b / OP-18c, left-without-being-seen OP-22, ED volume
category EDV, sepsis bundle, ...) and the peer-group percentiles of the ED measures that the catalog uses as ranges:
all hospitals, each ED-volume category, the hospital's state, and state x the hospital's volume category.
"""
from __future__ import annotations

import pandas as pd

from ._common import SourceUnavailable, clean, norm_ccn, out_dir, pdc_dataset, write_json

NAME = "care_compare"
DATASET_ID = "yv7e-xc69"
ED_MEASURES = ["OP_18b", "OP_18c", "OP_22"]


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    path, src = pdc_dataset(DATASET_ID, force)
    te = pd.read_csv(path, dtype=str)
    mine = te[te["Facility ID"] == ccn]
    if mine.empty:
        raise SourceUnavailable(f"Timely and Effective Care has no rows for Facility ID {ccn}")
    state = mine["State"].iloc[0]
    ed = te[te["Measure ID"].isin(ED_MEASURES + ["EDV"])]
    w = ed.pivot_table(index="Facility ID", columns="Measure ID", values="Score", aggfunc="first")
    for m in ED_MEASURES:
        w[m] = pd.to_numeric(w.get(m), errors="coerce")
    w = w.join(ed.drop_duplicates("Facility ID").set_index("Facility ID")[["State"]])
    my_edv = w.loc[ccn, "EDV"] if ccn in w.index and isinstance(w.loc[ccn, "EDV"], str) else None

    rows = []

    def summarize(label, sub):
        for m in ED_MEASURES:
            x = sub[m].dropna()
            if len(x) < 5:
                continue
            rows.append({"group": label, "measure": m, "n_hospitals": int(len(x)), "p10": float(x.quantile(.10)), "p25": float(x.quantile(.25)),
                         "median": float(x.median()), "p75": float(x.quantile(.75)), "p90": float(x.quantile(.90)), "mean": round(float(x.mean()), 2)})

    summarize("all_hospitals", w)
    for cat in ["low", "medium", "high", "very high"]:
        summarize(f"edv_{cat.replace(' ', '_')}", w[w["EDV"] == cat])
    summarize(f"state_{state}", w[w["State"] == state])
    if my_edv:
        summarize(f"state_{state}_edv_{my_edv.replace(' ', '_')}", w[(w["State"] == state) & (w["EDV"] == my_edv)])

    keep = ["Measure ID", "Measure Name", "Condition", "Score", "Sample", "Footnote", "Start Date", "End Date"]
    src["filter"] = f"Facility ID == '{ccn}' (all measures); peer groups from Measure ID in {ED_MEASURES + ['EDV']} over every hospital in the file"
    out = {"source": src, "ccn": ccn,
           "facility_in_file": {k: clean(mine[k].iloc[0]) for k in ["Facility ID", "Facility Name", "Address", "City/Town", "State", "ZIP Code"]},
           "measures": [{k: clean(v) for k, v in r.items()} for r in mine[keep].to_dict("records")],
           "edv_category": my_edv, "peer_group_key": f"edv_{my_edv.replace(' ', '_')}" if my_edv else "all_hospitals",
           "peer_groups": rows, "edv_category_counts": {k: int(v) for k, v in w["EDV"].value_counts().items()},
           "n_hospitals_in_file": int(te["Facility ID"].nunique())}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
