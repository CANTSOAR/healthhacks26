"""Offline checks of the public-data twin builder (tracked extracts only, no network):

    .venv/bin/python -m pytest twin/tests/test_build.py -q

Each hospital loads through sim/config.py, runs 24 simulated hours on CPU with a batch of 2, has a schema-valid layout,
a tagged and cited attribute for every value, extracts with a complete `source` block, and no clinician names.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim import HospitalSim, load_scenario  # noqa: E402
from twin.derive import SOURCES, Twin, shared_node  # noqa: E402

HOSPITALS = {"rwjuh_nb": "310038", "mount_sinai": "330024", "mayo_rochester": "240010"}
HOSP = ROOT / "catalog" / "hospitals"
REQUIRED = ["validation_median_ed_time_min", "validation_lwbs_rate", "ed_visits_per_year_cms", "inpatient_occupancy", "ed_direct_cost_per_year",
            "ed_salaries_per_year", "licensed_beds", "icu_beds", "em_physicians", "em_apps", "clinicians_affiliated_total", "residents_fte",
            "ed_visits_per_week_mean", "inpatient_occupancy_hhs", "ed_treatment_spaces", "ward_pool_los_factor", "cms_certification_number"]


def _doc(hid):
    return yaml.safe_load((HOSP / f"{hid}.yaml").read_text())


@pytest.mark.parametrize("hid", HOSPITALS)
def test_hospital_file_is_tagged_and_cited(hid):
    d = _doc(hid)
    attrs = d["variants"][hid]["attributes"]
    assert str(attrs["cms_certification_number"]["value"]) == HOSPITALS[hid]
    for k in REQUIRED:
        assert k in attrs, f"{hid}: missing attribute {k}"
    nodes = {**attrs, **d["catalog_overrides"]}
    for k, n in nodes.items():
        assert n.get("source") in ("measured", "literature", "assumed"), (hid, k)
        assert n.get("citation") and "unit" in n and "value" in n, (hid, k)
        if n["source"] == "measured":
            assert n.get("file") or n.get("url"), f"{hid}.{k}: measured without a file or url"
            if n.get("file"):
                assert (ROOT / n["file"]).exists(), f"{hid}.{k}: cited extract {n['file']} is missing"
    for path in d["catalog_overrides"]:
        f, variant, key = path.split(".")
        assert f in ("patient", "staff", "space", "equipment", "event") and variant and key, path


@pytest.mark.parametrize("hid", HOSPITALS)
def test_extracts_have_provenance_and_no_names(hid):
    ccn = HOSPITALS[hid]
    d = ROOT / "data" / "processed" / "hospitals" / ccn
    total = 0
    for s in SOURCES:
        p = d / f"{s}.json"
        assert p.exists(), f"{ccn}: extract {s} missing"
        total += p.stat().st_size
        src = json.loads(p.read_text())["source"]
        blocks = [src] if "dataset" in src else [v for v in src.values() if isinstance(v, dict) and "dataset" in v]
        assert blocks, (ccn, s)
        for b in blocks:
            assert b.get("url") or b.get("api"), (ccn, s)
            assert b.get("filter") and b.get("fetched_utc"), (ccn, s)
    assert total < 1_000_000, f"{ccn}: tracked extracts are {total} bytes"
    r = json.loads((d / "roster.json").read_text())
    assert r["columns"][0] == "npi" and not any("name" in c.lower() for c in r["columns"])
    assert len(r["rows"]) == r["counts"]["clinicians_affiliated_total"] == len({row[0] for row in r["rows"]})
    assert "Provider Last Name" not in (d / "roster.json").read_text()


@pytest.mark.parametrize("hid", HOSPITALS)
def test_layout_is_schema_valid(hid):
    from jsonschema import Draft202012Validator
    lay = json.loads((HOSP / f"{hid}.layout.json").read_text())
    v = Draft202012Validator(json.loads((ROOT / "contracts" / "layout.schema.json").read_text()))
    assert not [e.message for e in v.iter_errors(lay)]
    assert lay["hospital_id"] == hid
    if hid != "rwjuh_nb":      # generated: nothing may claim to be surveyed or published
        assert {r["provenance"] for r in lay["rooms"]} == {"inferred"}
        a = _doc(hid)["variants"][hid]["attributes"]
        cap = lambda t: sum(r["capacity"] for r in lay["rooms"] if r["type"] == t)  # noqa: E731
        assert cap("treatment_bay") + cap("resus_bay") + cap("fast_track") + cap("peds_ed") == a["ed_treatment_spaces"]["value"]
        assert cap("ward_unit") + cap("icu_bed") + cap("stepdown_bed") == a["ward_pool_beds"]["value"]


@pytest.mark.parametrize("hid", HOSPITALS)
def test_loads_and_runs_24_hours(hid):
    # no_calibration: this checks the public-data build itself; the calibration layer has its own tests
    c = load_scenario("normal_week", {"hospital_id": hid, "no_calibration": True})
    d = _doc(hid)
    assert c.hospital_id == hid and c.size_ratio == 1.0 and not c.fallback_keys
    assert c.layout_source == f"catalog/hospitals/{hid}.layout.json"
    assert c.P["arrivals_per_day"] == float(d["catalog_overrides"]["patient.shared.arrivals_per_day"]["value"])
    assert c.P["wage"]["rn"] == float(d["catalog_overrides"]["staff.rn.wage_per_hour"]["value"])
    sim = HospitalSim(c, batch_size=2, device="cpu", seed=5)
    arrivals = 0.0
    for _ in range(24):
        m = sim.step()
        arrivals += float(m["arrivals"].mean())
    assert int(sim.conservation()["residual"].abs().max()) == 0
    assert 0.6 * c.P["arrivals_per_day"] < arrivals < 1.5 * c.P["arrivals_per_day"]


def test_rwjuh_overrides_are_verbatim_copies_of_the_shared_catalog():
    """The hand-built hospital must simulate exactly as before: its overrides equal the shared nodes."""
    from twin.derive import load_shared
    shared = load_shared()
    d = _doc("rwjuh_nb")
    for path, node in d["catalog_overrides"].items():
        assert node == shared_node(shared, path), path
    a = load_scenario("normal_week", {"hospital_id": "rwjuh_nb", "no_calibration": True})
    saved = dict(d["catalog_overrides"])
    assert a.hospital_overrides.keys() == saved.keys()


def test_derivation_is_deterministic_from_tracked_extracts():
    ex = ["mount sinai", "new york"]
    t1, t2 = Twin("330024", "mount_sinai", expect=ex), Twin("330024", "mount_sinai", expect=ex)
    assert t1.attrs == t2.attrs and t1.overrides == t2.overrides
    assert t1.attrs == _doc("mount_sinai")["variants"]["mount_sinai"]["attributes"], "catalog/hospitals/mount_sinai.yaml is stale: rerun twin.build"
