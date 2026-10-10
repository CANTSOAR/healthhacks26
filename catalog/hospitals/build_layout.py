"""Generates the hospital layout files in this directory. Deterministic: no randomness, no network.

    .venv/bin/python catalog/hospitals/build_layout.py            # write all layouts, print summaries
    .venv/bin/python catalog/hospitals/build_layout.py --check    # build + validate only, write nothing

Outputs (all conform to contracts/layout.schema.json):
    rwjuh_nb.layout.json         Robert Wood Johnson University Hospital, New Brunswick (model)
    community_small.layout.json  fictional small community hospital (contrast)
    midsize.layout.json          fictional mid-size hospital (contrast)

Conventions (contracts/README.md): metres, x east, z south, origin at the north-west corner of the
site; rooms are axis-aligned rectangles given by centre x,z and size w,d.

Provenance per room:
    surveyed   traced from a real plan or map data (only exterior footprints/roads, from OpenStreetMap)
    published  the hospital has publicly stated this zone or count (its position here is still our placement)
    inferred   placed by us to be consistent with the above
No interior floor plan of the hospital is public; the ED interior is a reconstruction, not a survey.
See research/hospital-layout-rwjuh.md for what was fetched and what could not be found.
"""
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CONTRACTS = ROOT / "contracts"

DISCLAIMER_RWJ = (
    "A model built from public information. Not affiliated with or endorsed by Robert Wood Johnson "
    "University Hospital. Patient flows, staffing and outcomes are simulated, not the hospital's "
    "operational data. Staff are fictional."
)
DISCLAIMER_FICTIONAL = (
    "A fictional hospital generated for comparison. It does not represent any real facility. "
    "Patient flows, staffing and outcomes are simulated. Staff are fictional."
)

# Source strings reused on rooms -------------------------------------------------------------
ED_PAGE = "https://www.rwjbh.org/rwj-university-hospital-new-brunswick/treatment-care/emergency-services/"
SRC_INFER = "No public interior plan. Placed by the layout generator following common ED planning practice"


class Builder:
    """Collects rooms and equipment; every room is an axis-aligned rectangle."""

    def __init__(self):
        self.rooms = []
        self.equipment = []

    def rect(self, id, type, label, x0, z0, x1, z1, cap, zone, prov="inferred", source=SRC_INFER, note="", floor=0):
        """Add a room from its corner coordinates (x0,z0 north-west; x1,z1 south-east)."""
        assert x1 > x0 and z1 > z0, id
        r = dict(id=id, type=type, label=label, zone=zone,
                 x=round((x0 + x1) / 2, 2), z=round((z0 + z1) / 2, 2), w=round(x1 - x0, 2), d=round(z1 - z0, 2),
                 floor=floor, capacity=cap, physical=True, catalog_ref=f"space/{type}", provenance=prov, source=source)
        if note:
            r["note"] = note
        self.rooms.append(r)
        return r

    def equip(self, id, type, label, room, prov="inferred", source=""):
        self.equipment.append(dict(id=id, type=type, label=label, room=room, catalog_ref=f"equipment/{type}",
                                   provenance=prov, source=source))


def letters(i):
    return "abcdefghijklmnopqrstuvwxyz"[i]


def build(cfg):
    """Build one layout dict from a configuration (see CONFIGS)."""
    b = Builder()
    P = cfg["prov"]            # provenance + source per element kind
    ex0, ez0 = cfg["ed_origin"]

    def pv(kind):
        return dict(prov=P[kind][0], source=P[kind][1]) if kind in P else {}

    # ---- ED west section: pediatric ED, fast track, care initiation, results waiting, waiting, triage
    bay_w, bay_d, pitch = 3.2, 4.0, 3.4
    wx = ex0 + 1.0
    z = ez0 + 1.0
    n_peds = cfg["peds"]
    west_w = 29.0
    if n_peds:
        per = math.ceil(n_peds / 2)
        k = 0
        for row in range(2):
            rz = z if row == 0 else z + 10.0
            for c in range(per):
                if k >= n_peds:
                    break
                k += 1
                b.rect(f"peds-{k:02d}", "peds_ed", f"Pediatric ED {k}", wx + c * pitch, rz, wx + c * pitch + bay_w, rz + bay_d,
                       1, "Pediatric ED", **pv("peds"),
                       note="Separate pediatric emergency department is published; room count and position are assumed. Pediatric stream is not simulated in v1.")
        b.rect("station-peds", "nurse_station", "Pediatric ED nurse station", wx + 4, z + 5.5, wx + min(per * pitch, west_w) - 4, z + 8.5,
               0, "Pediatric ED")
        z += 16.0
    n_ft = cfg["fast_track"]
    per = math.ceil(n_ft / 2)
    k = 0
    for row in range(2):
        rz = z + 1.0 if row == 0 else z + 6.6
        for c in range(per):
            if k >= n_ft:
                break
            k += 1
            b.rect(f"ft-{k:02d}", "fast_track", f"Fast track {k}", wx + c * 3.2, rz, wx + c * 3.2 + 3.0, rz + 3.6,
                   1, "Fast track", **pv("fast_track"),
                   note="Fast-track area is published; the number of spaces and their position are assumed.")
    ftx = wx + per * 3.2 + 1.0
    b.rect("station-ft", "nurse_station", "Fast track station", ftx, z + 3.0, max(ftx + 6, ex0 + west_w), z + 8.2, 0, "Fast track")
    z += 12.0
    b.rect("care-init", "support", "Care initiation area", wx, z, wx + 14, z + 7, cfg["care_init_cap"], "ED front", **pv("care_init"),
           note="Area where a provider starts orders right after triage. Published as a zone; size and position assumed.")
    b.rect("results", "results_waiting", "Results waiting", wx + 15, z, wx + 28, z + 7, cfg["results_cap"], "ED front", **pv("results"),
           note="Seated area for patients waiting on results, freeing treatment spaces. Published as a zone; size and position assumed.")
    z += 9.0
    wait_d = cfg["waiting_d"]
    b.rect("waiting", "waiting_room", "Waiting room", wx, z, wx + 20, z + wait_d, cfg["waiting_cap"], "ED front", **pv("waiting"))
    tri_d = min(4.0, (wait_d - 0.5 * (cfg["triage"] - 1)) / cfg["triage"])
    for i in range(cfg["triage"]):
        tz = z + i * (tri_d + 0.5)
        b.rect(f"triage-{i+1}", "triage", f"Triage {i+1}", wx + 22.5, tz, wx + 27.5, tz + tri_d, 1, "ED front", **pv("triage"))
    z += wait_d + 1.0
    b.rect("entrance", "entrance", "Walk-in entrance", wx + 6, z, wx + 14, z + 3, 0, "ED front", **pv("entrance"))
    west_z1 = z + 3.0

    # ---- main pods east of the spine corridor
    sx0 = ex0 + west_w + 1.0          # spine corridor
    px0 = sx0 + 3.0
    n_bays = cfg["adult_bays"]
    pod_sizes = cfg["pods"]
    assert sum(pod_sizes) == n_bays
    col_len = max(math.ceil(s / 2) for s in pod_sizes) * pitch
    col_x = [px0, px0 + col_len + 3.4]
    pod_d = 16.0                      # 4 m bays + 8 m core + 4 m bays
    band_d = 8.0                      # imaging / support band
    pz = ez0 + 1.0
    bay_n = 0
    n_rows = math.ceil(len(pod_sizes) / 2)
    pods_x1 = col_x[1] + col_len if len(pod_sizes) > 1 else col_x[0] + col_len
    img_w = cfg["ct"] * 8.0 + cfg["xray"] * 7.0 + cfg["ultrasound"] * 5.0
    pods_x1 = max(pods_x1, px0 + img_w + 8.0 + 1.0 + 10.0)   # the imaging band must fit pharmacy and lab too
    band_z = None
    for i, size in enumerate(pod_sizes):
        row, col = divmod(i, 2)
        z0 = ez0 + 1.0 + row * (pod_d + 2.6) + (band_d + 1.4 if row >= 1 else 0)
        x0 = col_x[col]
        name = letters(i).upper()
        north = math.ceil(size / 2)
        for j in range(size):
            bay_n += 1
            r, c = (0, j) if j < north else (1, j - north)
            bz = z0 if r == 0 else z0 + 12.0
            b.rect(f"bay-{bay_n:03d}", "treatment_bay", f"Bay {bay_n}", x0 + c * pitch, bz, x0 + c * pitch + bay_w, bz + bay_d,
                   1, f"ED main, pod {name}", **pv("bay"),
                   note="Private treatment room. 'More than 100 private treatment areas' is published for the whole department; the split into pods and each position are assumed."
                   if cfg["hospital_id"] == "rwjuh_nb" else "")
        b.rect(f"station-{letters(i)}", "nurse_station", f"Nurse station {name}", x0 + 3, z0 + 6.5, x0 + north * pitch - 3.2, z0 + 9.5,
               0, f"ED main, pod {name}")
        pz = max(pz, z0 + pod_d)
        if col == 0 and i + 1 < len(pod_sizes):
            b.rect(f"corr-ns-{row+1}", "corridor", "Cross corridor", x0 + col_len + 0.2, z0, x0 + col_len + 2.4, z0 + pod_d, 0, "Circulation")
    b.rect("corr-spine", "corridor", "Main corridor", sx0, ez0 + 1, sx0 + 2, max(pz, west_z1 - 1), 0, "Circulation")

    # imaging + support band after the first pod row
    bz0 = ez0 + 1.0 + pod_d + 2.6
    b.rect("corr-ew-1", "corridor", "Imaging corridor (north)", px0, bz0 - 2.2, pods_x1, bz0 - 0.4, 0, "Circulation")
    x = px0
    img = []
    for i in range(cfg["ct"]):
        img.append((f"ct-{i+1}", "ct", f"CT {i+1}", 7.0, 1))
    for i in range(cfg["xray"]):
        img.append((f"xray-{i+1}", "xray", f"X-ray {i+1}", 6.0, 1))
    for i in range(cfg["ultrasound"]):
        img.append((f"us-{i+1}", "ultrasound", f"Ultrasound {i+1}", 4.0, 1))
    for id, type, label, w, cap in img:
        b.rect(id, type, label, x, bz0, x + w, bz0 + band_d - 1.0, cap, "ED imaging", **pv("imaging"),
               note="Radiology inside the emergency department is published; the number of rooms and their position are assumed."
               if cfg["hospital_id"] == "rwjuh_nb" else "")
        b.equip(f"{id}-unit", type, {"ct": "CT scanner", "xray": "X-ray unit", "ultrasound": "Ultrasound machine"}[type] + f" {id.split('-')[1]}",
                id, source="count assumed (catalog/hospitals); make and model not specified")
        x += w + 1.0
    pw = 8.0
    b.rect("pharmacy", "pharmacy", "ED pharmacy", x, bz0, x + pw, bz0 + band_d - 1.0, 0, "Support")
    b.rect("lab", "lab", "Lab", x + pw + 1, bz0, x + pw + 11, bz0 + band_d - 1.0, 0, "Support",
           note="Stat lab / specimen receiving for the ED. The main laboratory is elsewhere in the hospital.")
    lx1 = x + pw + 11
    if pods_x1 - lx1 >= 5:
        b.rect("staff-room", "support", "Staff room", lx1 + 1, bz0, pods_x1, bz0 + band_d - 1.0, 0, "Support")
    if n_rows > 1:
        b.rect("corr-ew-2", "corridor", "Imaging corridor (south)", px0, bz0 + band_d - 0.6, pods_x1, bz0 + band_d + 1.0, 0, "Circulation")
        south_z0 = pz + 2.2
        b.rect("corr-ew-3", "corridor", "Resuscitation corridor", px0, pz + 0.3, pods_x1, pz + 1.9, 0, "Circulation")
    else:
        south_z0 = bz0 + band_d + 1.2
        b.rect("corr-ew-2", "corridor", "Resuscitation corridor", px0, bz0 + band_d - 0.6, pods_x1, bz0 + band_d + 0.9, 0, "Circulation")

    # ---- south band: resuscitation next to the ambulance entrance, decontamination, registration
    n_resus = cfg["resus"]
    rw, rd = 6.0, 6.5
    rx1 = pods_x1
    for i in range(n_resus):
        x1 = rx1 - i * (rw + 0.4)
        b.rect(f"resus-{i+1}", "resus_bay", f"Resuscitation {i+1}", x1 - rw, south_z0, x1, south_z0 + rd, 1, "Resuscitation", **pv("resus"),
               note="Resuscitation / trauma bay next to the ambulance entrance. " + cfg.get("resus_note", ""))
    rx0 = rx1 - n_resus * (rw + 0.4)
    if rx0 - px0 >= 9:
        b.rect("station-resus", "nurse_station", "Resuscitation station", max(px0, rx0 - 8.5), south_z0, rx0, south_z0 + rd, 0, "Resuscitation")
    if rx0 - 9.5 - px0 >= 6:
        b.rect("registration", "support", "Registration and security", px0, south_z0, min(px0 + 15, rx0 - 9.5), south_z0 + rd, 0, "ED front")
    ed_x1 = pods_x1 + 6.5
    b.rect("decon", "decon", "Decontamination", pods_x1 + 1.5, south_z0, ed_x1 - 0.5, south_z0 + rd, 1, "Resuscitation", **pv("decon"),
           note="Decontamination area with outside access. Published as a zone; size and position assumed.")
    b.rect("ems-room", "support", "EMS and staff support", pods_x1 + 1.5, ez0 + 1, ed_x1 - 0.5, south_z0 - 1.0, 0, "Support")
    ed_z1 = max(south_z0 + rd + 0.5, west_z1)

    # ---- outside: ambulance entrance and bay
    amb_w = cfg["ambulance_slots"] * 5.0
    ax1 = min(pods_x1 + 2, ed_x1)
    ax0 = ax1 - amb_w
    b.rect("amb-entrance", "entrance", "Ambulance entrance", (ax0 + ax1) / 2 - 4, ed_z1, (ax0 + ax1) / 2 + 4, ed_z1 + 3, 0, "Ambulance",
           **pv("amb_entrance"))
    b.rect("amb-bay", "ambulance_bay", "Ambulance bay", ax0, ed_z1 + 4, ax1, ed_z1 + 12, cfg["ambulance_slots"], "Ambulance", **pv("ambulance"),
           note=cfg.get("ambulance_note", ""))

    # ---- inpatient block (low detail). In the real hospital these are on upper floors and in other
    # buildings; they are drawn at grade next to the ED so the whole flow is visible in one view.
    ix0, iz0 = cfg["inpatient_origin"]
    inp_note = "Low-detail block. Drawn at ground level beside the ED for readability; in reality inpatient units are on upper floors."
    uw, ud = cfg["ward_size"]
    x = ix0
    for i, beds in enumerate(cfg["wards"]):
        b.rect(f"ward-{letters(i)}", "ward_unit", f"Inpatient unit {letters(i).upper()}", x, iz0, x + uw, iz0 + ud, beds, "Inpatient", **pv("ward"),
               note=inp_note + " Beds counted here are the modelled pool available to ED admissions, not the hospital's licensed beds.")
        x += uw + 2.0
    ix1 = x - 2.0
    z2 = iz0 + ud + 6.0
    ctx = [("icu", "icu_bed", "Intensive care unit", cfg["icu_beds"], 0.24), ("stepdown", "stepdown_bed", "Step-down unit", cfg["stepdown_beds"], 0.2),
           ("or", "operating_room", "Operating rooms", cfg["or_rooms"], 0.24), ("recovery", "recovery", "Recovery (PACU)", cfg["recovery_beds"], 0.16)]
    span = ix1 - ix0 - 12.0
    x = ix0
    for id, type, label, cap, frac in ctx:
        w = span * frac
        b.rect(id, type, label, x, z2, x + w - 2.0, z2 + ud, cap, "Inpatient", **pv("context"), note=inp_note + " Capacity is assumed.")
        x += w
    for i in range(cfg["mri"]):
        b.rect(f"mri-{i+1}", "mri", f"MRI {i+1}", ix1 - 9.0, z2 + i * 8, ix1, z2 + 7 + i * 8, 1, "Main radiology", **pv("context"),
               note="Main radiology MRI, outside the ED. Count assumed.")
        b.equip(f"mri-{i+1}-unit", "mri", f"MRI scanner {i+1}", f"mri-{i+1}", source="count assumed (catalog/hospitals)")
    lcx = col_x[0] + col_len + 0.2
    link_z0 = z2 + ud + 0.5
    if ez0 - link_z0 > 1:
        b.rect("corr-link", "corridor", "Corridor to inpatient units and elevators", lcx, link_z0, lcx + 2.2, ez0 + 0.8, 0, "Circulation")
    b.rect("corr-inpatient", "corridor", "Inpatient corridor", ix0, iz0 + ud + 1.5, ix1, iz0 + ud + 4.5, 0, "Circulation")

    site = dict(w=cfg["site"][0], d=cfg["site"][1], roads=cfg["roads"](ax0, ax1, ed_z1, wx), buildings=cfg["buildings"])
    layout = dict(
        schema_version=1, hospital_id=cfg["hospital_id"], name=cfg["name"], disclaimer=cfg["disclaimer"], version=cfg["version"],
        site=site, rooms=b.rooms, equipment=b.equipment, walk_speed_m_per_min=cfg["walk_speed"], sources=cfg["sources"],
    )
    layout["_ed_rect"] = [ex0, ez0, ed_x1, ed_z1]
    return layout


def poly(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


# ---------------------------------------------------------------------------------------------
# Configurations
# ---------------------------------------------------------------------------------------------
PUB = lambda what: f"{ED_PAGE} ({what}); exact position inferred"

RWJ = dict(
    hospital_id="rwjuh_nb",
    name="Robert Wood Johnson University Hospital, New Brunswick (model)",
    disclaimer=DISCLAIMER_RWJ, version=1, walk_speed=70,
    site=(220, 160), ed_origin=(40, 66), inpatient_origin=(40, 8), ward_size=(26, 14),
    adult_bays=68, pods=[18, 18, 16, 16], resus=6, fast_track=10, peds=16, triage=3,
    ct=2, xray=2, ultrasound=2, mri=1, ambulance_slots=8,
    waiting_cap=60, waiting_d=13.0, care_init_cap=8, results_cap=16,
    wards=[24, 24, 24, 24, 24], icu_beds=24, stepdown_beds=24, or_rooms=12, recovery_beds=16,
    resus_note="Phase one of the expansion added three resuscitation bays (published); a total of six is assumed.",
    ambulance_note="Ambulance bay for eight ambulances is published; position inferred.",
    prov=dict(
        peds=("published", PUB("separate pediatric emergency department; count assumed")),
        fast_track=("published", PUB("fast-track area; count assumed")),
        care_init=("published", PUB("care-initiation area added in phase one")),
        results=("published", PUB("results-waiting area added in phase one")),
        entrance=("published", PUB("new walk-in entrance")),
        bay=("published", PUB("more than 100 private treatment areas across the department; split assumed")),
        imaging=("published", PUB("radiology inside the department; counts assumed")),
        resus=("published", PUB("three resuscitation bays added in phase one; total of six assumed")),
        decon=("published", PUB("decontamination area added in phase one")),
        ambulance=("published", PUB("ambulance bay for eight ambulances")),
    ),
    roads=lambda ax0, ax1, z1, wx: [
        dict(id="road-access", label="Access road", width=7, points=[[0, z1 + 18], [220, z1 + 18]], provenance="inferred"),
        dict(id="road-ambulance", label="Ambulance drive", width=6,
             points=[[ax0 - 6, z1 + 18], [ax0 - 6, z1 + 13.5], [ax1 + 6, z1 + 13.5], [ax1 + 6, z1 + 18]], provenance="inferred"),
        dict(id="road-dropoff", label="Walk-in drop-off", width=5, points=[[wx + 2, z1 + 18], [wx + 2, z1 + 4], [wx + 18, z1 + 4], [wx + 18, z1 + 18]],
             provenance="inferred"),
    ],
    buildings=[
        dict(id="parking-deck", label="Parking deck", height=18, polygon=poly(4, 70, 32, 124), provenance="inferred", source="first-cut placeholder"),
        dict(id="childrens", label="Children's hospital", height=24, polygon=poly(160, 62, 214, 112), provenance="inferred", source="first-cut placeholder"),
        dict(id="cancer-institute", label="Cancer institute", height=24, polygon=poly(186, 8, 216, 50), provenance="inferred", source="first-cut placeholder"),
        dict(id="med-school", label="Medical education building", height=20, polygon=poly(4, 8, 32, 56), provenance="inferred", source="first-cut placeholder"),
    ],
    sources=[
        dict(title="RWJUH emergency department expansion description (published counts and zones, as recorded in HANDOFF.md)",
             url=ED_PAGE, used_for="ED area, zones and counts tagged 'published'", accessed="2026-10-10"),
    ],
)

FICT = dict(disclaimer=DISCLAIMER_FICTIONAL, version=1, walk_speed=70, prov={},
            sources=[dict(title="Generated by catalog/hospitals/build_layout.py; fictional, all rooms inferred",
                          url="catalog/hospitals/build_layout.py", used_for="everything")])


def simple_roads(ax0, ax1, z1, wx, w):
    return [
        dict(id="road-access", label="Access road", width=7, points=[[0, z1 + 18], [w, z1 + 18]], provenance="inferred"),
        dict(id="road-ambulance", label="Ambulance drive", width=6,
             points=[[ax0 - 6, z1 + 18], [ax0 - 6, z1 + 13.5], [ax1 + 6, z1 + 13.5], [ax1 + 6, z1 + 18]], provenance="inferred"),
    ]


SMALL = dict(
    FICT, hospital_id="community_small", name="Small community hospital (fictional contrast)",
    site=(120, 110), ed_origin=(14, 40), inpatient_origin=(14, 6), ward_size=(30, 12),
    adult_bays=14, pods=[14], resus=2, fast_track=4, peds=0, triage=1,
    ct=1, xray=1, ultrasound=1, mri=1, ambulance_slots=2,
    waiting_cap=24, waiting_d=9.0, care_init_cap=4, results_cap=6,
    wards=[20, 20], icu_beds=8, stepdown_beds=6, or_rooms=3, recovery_beds=4,
    roads=lambda ax0, ax1, z1, wx: simple_roads(ax0, ax1, z1, wx, 120),
    buildings=[dict(id="medical-office", label="Medical office building", height=10, polygon=poly(90, 6, 114, 30), provenance="inferred", source="fictional")],
)

MID = dict(
    FICT, hospital_id="midsize", name="Mid-size hospital (fictional contrast)",
    site=(170, 140), ed_origin=(20, 48), inpatient_origin=(20, 6), ward_size=(28, 14),
    adult_bays=36, pods=[12, 12, 12], resus=3, fast_track=6, peds=6, triage=2,
    ct=1, xray=2, ultrasound=1, mri=1, ambulance_slots=4,
    waiting_cap=40, waiting_d=11.0, care_init_cap=6, results_cap=10,
    wards=[24, 24, 24], icu_beds=14, stepdown_beds=12, or_rooms=6, recovery_beds=8,
    roads=lambda ax0, ax1, z1, wx: simple_roads(ax0, ax1, z1, wx, 170),
    buildings=[dict(id="parking", label="Parking deck", height=12, polygon=poly(132, 6, 164, 40), provenance="inferred", source="fictional")],
)

CONFIGS = {"rwjuh_nb": RWJ, "community_small": SMALL, "midsize": MID}


# ---------------------------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------------------------
def validator():
    from jsonschema import Draft202012Validator
    return Draft202012Validator(json.loads((CONTRACTS / "layout.schema.json").read_text()))


def check(layout):
    """Schema, enums, unique ids, bounds, no overlapping rooms. Returns a list of problems."""
    import yaml
    enums = yaml.safe_load((CONTRACTS / "enums.yaml").read_text())
    problems = [e.message for e in validator().iter_errors(layout)]
    rooms = layout["rooms"]
    ids = [r["id"] for r in rooms]
    problems += [f"duplicate room id {i}" for i, n in Counter(ids).items() if n > 1]
    W, D = layout["site"]["w"], layout["site"]["d"]
    box = {}
    for r in rooms:
        if r["type"] not in enums["room_type"]:
            problems.append(f"{r['id']}: unknown room type {r['type']}")
        x0, x1, z0, z1 = r["x"] - r["w"] / 2, r["x"] + r["w"] / 2, r["z"] - r["d"] / 2, r["z"] + r["d"] / 2
        box[r["id"]] = (x0, x1, z0, z1, r.get("floor", 0))
        if x0 < 0 or z0 < 0 or x1 > W or z1 > D:
            problems.append(f"{r['id']}: outside the site")
    eps = 1e-6
    for i, a in enumerate(ids):
        for c in ids[i + 1:]:
            A, B = box[a], box[c]
            if A[4] == B[4] and A[0] < B[1] - eps and B[0] < A[1] - eps and A[2] < B[3] - eps and B[2] < A[3] - eps:
                problems.append(f"overlap: {a} and {c}")
    for e in layout["equipment"]:
        if e["room"] not in box:
            problems.append(f"equipment {e['id']}: unknown room {e['room']}")
        if e["type"] not in enums["equipment_type"]:
            problems.append(f"equipment {e['id']}: unknown type {e['type']}")
    for road in layout["site"].get("roads", []):
        for x, z in road["points"]:
            if not (0 <= x <= W and 0 <= z <= D):
                problems.append(f"road {road['id']}: point outside the site")
    for bld in layout["site"].get("buildings", []):
        for x, z in bld["polygon"]:
            if not (-1e-6 <= x <= W and -1e-6 <= z <= D):
                problems.append(f"building {bld['id']}: point outside the site")
    return problems


def summary(layout, ed_rect):
    rooms = layout["rooms"]
    by = Counter((r["type"], r["provenance"]) for r in rooms)
    cap = Counter()
    for r in rooms:
        cap[r["type"]] += r["capacity"]
    tags = ["surveyed", "published", "inferred"]
    lines = [f"{layout['hospital_id']}: {len(rooms)} rooms, {len(layout['equipment'])} equipment, site {layout['site']['w']} x {layout['site']['d']} m",
             f"  {'type':<16}{'rooms':>6}{'capacity':>9}" + "".join(f"{t:>10}" for t in tags)]
    for t in sorted({r["type"] for r in rooms}):
        n = sum(by[(t, g)] for g in tags)
        lines.append(f"  {t:<16}{n:>6}{cap[t]:>9}" + "".join(f"{by[(t, g)]:>10}" for g in tags))
    lines.append(f"  {'TOTAL':<16}{len(rooms):>6}{sum(cap.values()):>9}" + "".join(f"{sum(by[(t, g)] for t in {r['type'] for r in rooms}):>10}" for g in tags))
    x0, z0, x1, z1 = ed_rect
    lines.append(f"  ED envelope {x1 - x0:.1f} x {z1 - z0:.1f} m = {(x1 - x0) * (z1 - z0):.0f} m2 ({(x1 - x0) * (z1 - z0) * 10.7639:.0f} sq ft)")
    bt = Counter(b.get("provenance") for b in layout["site"].get("buildings", []))
    rt = Counter(r.get("provenance") for r in layout["site"].get("roads", []))
    lines.append(f"  site buildings by provenance: {dict(bt)}; roads: {dict(rt)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="build and validate, write nothing")
    ap.add_argument("--only", help="one hospital id")
    args = ap.parse_args()
    bad = False
    for hid, cfg in CONFIGS.items():
        if args.only and hid != args.only:
            continue
        layout = build(cfg)
        ed_rect = layout.pop("_ed_rect")
        problems = check(layout)
        print(summary(layout, ed_rect))
        if problems:
            bad = True
            print("  PROBLEMS:\n   " + "\n   ".join(problems[:40]))
            continue
        if not args.check:
            out = HERE / f"{hid}.layout.json"
            out.write_text(json.dumps(layout, indent=1) + "\n")
            print(f"  wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
