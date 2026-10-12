"""One module per public dataset. Each exposes NAME and fetch(ccn, ...) -> dict and writes
data/processed/hospitals/<ccn>/<NAME>.json with a `source` block (url, release, fetched_utc, sha256, filter)."""
from . import bls_oews, care_compare, cms_rates, fluview, hcris, hhs_capacity, hospital_general, pos, quality, roster  # noqa: F401

ORDER = ["hospital_general", "care_compare", "hcris", "pos", "hhs_capacity", "cms_rates", "roster", "quality", "bls_oews", "fluview"]
