"""Parametric layout for any hospital, from its counts.

Reuses the generator in catalog/hospitals/build_layout.py (the same code that draws the fictional contrast hospitals)
and writes catalog/hospitals/<id>.layout.json (contracts/layout.schema.json).

No interior plan of the hospital is used: EVERY room position is `inferred`. The counts come from the hospital file -
each room's note says whether its count is a public figure or a stated rule - and the picture is a schematic of the
flow, not a map of the building.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

from .sources._common import REPO, atomic_write_text

GEN = REPO / "catalog" / "hospitals" / "build_layout.py"
WARD_UNIT_BEDS = 24
MAX_POD = 18
MAX_FAST_TRACK = 12       # west wing of the generator holds two rows of six
MAX_PEDS = 18
MAX_RESUS = 8


def _gen():
    spec = importlib.util.spec_from_file_location("hg_build_layout", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pods(n_bays: int) -> list[int]:
    """Split the main bays into pods of at most 18 (an even number of pods above one, as in the hand-built layout)."""
    if n_bays <= MAX_POD:
        return [n_bays]
    k = math.ceil(n_bays / MAX_POD)
    k += k % 2
    base, extra = divmod(n_bays, k)
    return [base + (1 if i < extra else 0) for i in range(k)]


def build(hospital_id: str, name: str, counts: dict, count_notes: dict, sources: list[dict]) -> dict:
    """counts: adult_main_bays, resus_bays, fast_track_spaces, peds_ed_spaces, triage_rooms, ct, xray, ultrasound, mri,
    ambulance_slots, ward_units (list of bed counts), icu_beds, stepdown_beds, or_rooms, recovery_beds.
    count_notes: room type -> sentence saying where the count comes from (goes into every room's note)."""
    g = _gen()
    for key, cap in (("fast_track_spaces", MAX_FAST_TRACK), ("peds_ed_spaces", MAX_PEDS), ("resus_bays", MAX_RESUS)):
        if counts[key] > cap:
            raise ValueError(f"{key}={counts[key]} exceeds what the generator can draw ({cap})")
    wards = list(counts["ward_units"])
    per_row = min(len(wards), 5)
    rows = math.ceil(len(wards) / per_row)
    uw, ud = (21.0 if len(wards) >= 3 else 64.0 / len(wards)), 12.0
    iz0 = 6.0
    ez0 = iz0 + rows * (ud + 2.0) - 2.0 + 6.0 + ud + 4.0
    waiting_cap = int(min(120, max(20, round(0.6 * (counts["adult_main_bays"] + counts["fast_track_spaces"])))))
    base = dict(
        hospital_id=hospital_id, name=name, version=1, walk_speed=70, prov={},
        disclaimer=(f"A model built from public information. Not affiliated with or endorsed by the hospital it describes. Room counts come from "
                    f"public data or stated rules; every room position is inferred (no interior plan was used). Patient flows, staffing and outcomes "
                    f"are simulated, not the hospital's operational data. Staff are fictional."),
        ed_origin=(12.0, ez0), inpatient_origin=(12.0, iz0), ward_size=(uw, ud), wards_per_row=per_row,
        adult_bays=counts["adult_main_bays"], pods=pods(counts["adult_main_bays"]), resus=counts["resus_bays"], fast_track=counts["fast_track_spaces"],
        peds=counts["peds_ed_spaces"], triage=counts["triage_rooms"], ct=counts["ct"], xray=counts["xray"], ultrasound=counts["ultrasound"],
        mri=counts["mri"], ambulance_slots=counts["ambulance_slots"], waiting_cap=waiting_cap, waiting_d=13.0 if counts["triage_rooms"] > 2 else 11.0,
        care_init_cap=max(4, round(counts["adult_main_bays"] / 9)), results_cap=max(6, round(counts["adult_main_bays"] / 4)),
        wards=wards, icu_beds=counts["icu_beds"], stepdown_beds=counts["stepdown_beds"], or_rooms=counts["or_rooms"], recovery_beds=counts["recovery_beds"],
        sources=sources)

    def make(site):
        cfg = dict(base, site=site, site_features=g.fict_site(site[0], []))
        lay = g.build(cfg)
        return lay, lay.pop("_ed_rect")

    lay, _ = make((2000.0, 2000.0))
    x1 = max(r["x"] + r["w"] / 2 for r in lay["rooms"])
    z1 = max(r["z"] + r["d"] / 2 for r in lay["rooms"])
    site = (float(math.ceil(x1 + 12.0)), float(math.ceil(z1 + 16.0)))
    lay, ed_rect = make(site)

    generic = "Position inferred: placed by the layout generator following common emergency-department planning practice, not taken from a plan of this hospital."
    for r in lay["rooms"]:
        r["provenance"] = "inferred"
        r["source"] = "No public interior plan. " + generic
        note = count_notes.get(r["type"]) or count_notes.get("_default", "")
        if r["type"] in ("ward_unit", "icu_bed", "stepdown_bed", "operating_room", "recovery", "mri"):
            note = ("Low-detail block drawn at ground level beside the ED for readability; in reality these units are on other floors or in other buildings. " + note).strip()
        if note:
            r["note"] = note
        else:
            r.pop("note", None)
    for e in lay["equipment"]:
        e["provenance"] = "inferred"
        e["source"] = count_notes.get(e["type"], "count by stated rule (see the hospital file); make and model not specified")
    for rd in lay["site"].get("roads", []):
        rd["provenance"] = "inferred"
    lay["site"]["note"] = "Schematic site: the rectangle is fitted around the generated rooms; roads are illustrative. No map data was used."
    problems = g.check(lay)
    if problems:
        raise ValueError(f"generated layout for {hospital_id} is invalid: {problems[:8]}")
    lay["_summary"] = g.summary(lay, ed_rect)
    return lay


def write(layout: dict, hospital_id: str) -> Path:
    layout = dict(layout)
    layout.pop("_summary", None)
    out = REPO / "catalog" / "hospitals" / f"{hospital_id}.layout.json"
    atomic_write_text(out, json.dumps(layout, indent=1) + "\n")
    return out
