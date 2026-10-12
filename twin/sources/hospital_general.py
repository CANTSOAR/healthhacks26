"""CMS Hospital General Information (Provider Data Catalog xubh-q36u): identity, address, type, ownership,
emergency services, overall star rating. The row is the identity check for every other source."""
from __future__ import annotations

import pandas as pd

from ._common import SourceUnavailable, clean, norm_ccn, out_dir, pdc_dataset, write_json

NAME = "hospital_general"
DATASET_ID = "xubh-q36u"


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    path, src = pdc_dataset(DATASET_ID, force)
    gi = pd.read_csv(path, dtype=str)
    row = gi[gi["Facility ID"] == ccn]
    if len(row) != 1:
        raise SourceUnavailable(f"Hospital General Information has {len(row)} rows for Facility ID {ccn}")
    r = {k: clean(v) for k, v in row.iloc[0].items()}
    src["filter"] = f"Facility ID == '{ccn}'"
    out = {"source": src, "ccn": ccn, "facility": {k: v for k, v in r.items() if v is not None},
           "n_hospitals_in_file": int(len(gi))}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
