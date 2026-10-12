"""Fetch every public source for one hospital and write the tracked extracts.

    python -m twin.fetch --ccn 330024                  # all sources (cached raw files are reused)
    python -m twin.fetch --ccn 330024 --only hcris,roster --force

Heavy sources (hcris ~135 MB zip, roster: 0.8 GB + 3 GB + 1 GB downloads) are best run on a workstation; copy
data/processed/hospitals/<ccn>/ back afterwards. A source that cannot be reached is recorded in
data/processed/hospitals/<ccn>/_fetch_log.json and the build marks the attributes that depend on it as assumed.
"""
from __future__ import annotations

import argparse
import traceback

from . import sources
from .sources._common import SourceUnavailable, norm_ccn, now, out_dir, read_extract, write_json


def fetch_all(ccn, only=None, force: bool = False, skip_existing: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    log = read_extract(ccn, "_fetch_log") or {"ccn": ccn, "sources": {}}
    state = county = None

    def run(name, fn):
        if only and name not in only:
            return read_extract(ccn, name)
        if skip_existing and read_extract(ccn, name) is not None:
            return read_extract(ccn, name)
        try:
            out = fn()
            log["sources"][name] = {"status": "ok", "at": now()}
            print(f"[{ccn}] {name}: ok")
            return out
        except SourceUnavailable as e:
            log["sources"][name] = {"status": "unavailable", "at": now(), "error": str(e)}
            print(f"[{ccn}] {name}: UNAVAILABLE - {e}")
        except Exception as e:  # noqa: BLE001 - one broken source must not stop the others
            log["sources"][name] = {"status": "error", "at": now(), "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}
            print(f"[{ccn}] {name}: ERROR - {type(e).__name__}: {e}")
        return read_extract(ccn, name)

    gi = run("hospital_general", lambda: sources.hospital_general.fetch(ccn, force))
    if gi:
        state = gi["facility"].get("State")
    run("care_compare", lambda: sources.care_compare.fetch(ccn, force))
    run("hcris", lambda: sources.hcris.fetch(ccn, force))
    run("pos", lambda: sources.pos.fetch(ccn, force))
    hhs = run("hhs_capacity", lambda: sources.hhs_capacity.fetch(ccn, force))
    rates = run("cms_rates", lambda: sources.cms_rates.fetch(ccn, force))
    run("roster", lambda: sources.roster.fetch(ccn, force))
    run("quality", lambda: sources.quality.fetch(ccn, force))
    if rates:
        county = str(rates["impact_file_row"].get("FIPS County Code", "")).split(".")[0] or None
    if not county and hhs:
        county = hhs["facility_in_file"].get("fips_code")
    if state and county:
        run("bls_oews", lambda: sources.bls_oews.fetch(ccn, state, county, force))
    elif not only or "bls_oews" in only:
        log["sources"]["bls_oews"] = {"status": "unavailable", "at": now(), "error": "state or county unknown (hospital_general / cms_rates / hhs_capacity missing)"}
    if state:
        run("fluview", lambda: sources.fluview.fetch(ccn, state, force))
    write_json(log, out_dir(ccn) / "_fetch_log.json")
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ccn", required=True, nargs="+")
    ap.add_argument("--only", help="comma-separated source names")
    ap.add_argument("--force", action="store_true", help="re-download raw files and re-query APIs")
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()
    for c in a.ccn:
        fetch_all(c, set(a.only.split(",")) if a.only else None, a.force, a.skip_existing)


if __name__ == "__main__":
    main()
