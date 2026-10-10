"""Builds layout.fixture.json and rollout.fixture.json by hand (no simulator) and
validates them against the schemas. The numbers are placeholders so the web app
can be built before the simulator exists; nothing here is a result.

    .venv/bin/python contracts/fixtures/make_fixture.py
"""
import json
import math
import random
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).parent
C = HERE.parent
ENUMS = yaml.safe_load((C / "enums.yaml").read_text())
ACTIONS = yaml.safe_load((C / "actions.yaml").read_text())["heads"]
METRICS = yaml.safe_load((C / "metrics.yaml").read_text())["metrics"]
E = {k: {n: i for i, n in enumerate(v)} for k, v in ENUMS.items() if isinstance(v, list)}


def room(id, type, label, x, z, w, d, cap, zone, prov="inferred", note=""):
    return dict(id=id, type=type, label=label, zone=zone, x=x, z=z, w=w, d=d, floor=0, capacity=cap,
                physical=True, catalog_ref=f"space/{type}", provenance=prov,
                source="fixture layout, hand-placed", note=note)


def make_layout():
    rooms = [
        room("entrance", "entrance", "Walk-in entrance", 10, 62, 6, 4, 0, "ED front"),
        room("waiting", "waiting_room", "Waiting room", 14, 50, 18, 14, 40, "ED front"),
        room("triage-1", "triage", "Triage 1", 28, 44, 4, 4, 1, "ED front"),
        room("triage-2", "triage", "Triage 2", 28, 49, 4, 4, 1, "ED front"),
        room("triage-3", "triage", "Triage 3", 28, 54, 4, 4, 1, "ED front"),
        room("results", "results_waiting", "Results waiting", 14, 36, 12, 6, 12, "ED front", "published"),
        room("station-a", "nurse_station", "Nurse station A", 46, 44, 8, 4, 0, "ED main"),
        room("amb-bay", "ambulance_bay", "Ambulance bay", 78, 62, 20, 6, 8, "Outside", "published"),
        room("pharmacy", "pharmacy", "Pharmacy", 84, 30, 8, 6, 0, "Support"),
        room("lab", "lab", "Lab", 84, 22, 8, 6, 0, "Support"),
        room("xray-1", "xray", "X-ray 1", 70, 22, 6, 6, 1, "Imaging", "published"),
        room("ct-1", "ct", "CT 1", 62, 22, 6, 6, 1, "Imaging", "published"),
        room("ward-a", "ward_unit", "Ward A", 30, 12, 40, 10, 24, "Inpatient"),
    ]
    for i in range(3):
        rooms.append(room(f"resus-{i+1}", "resus_bay", f"Resus {i+1}", 62 + i * 7, 54, 6, 6, 1, "Resus", "published"))
    n = 0
    for r in range(2):
        for c in range(8):
            n += 1
            rooms.append(room(f"bay-{n:03d}", "treatment_bay", f"Bay {n}", 36 + c * 4.2, 36 + r * 14, 3.6, 4, 1, "ED main"))
    for i in range(4):
        rooms.append(room(f"ft-{i+1}", "fast_track", f"Fast track {i+1}", 6 + i * 4.2, 28, 3.6, 4, 1, "Fast track", "published"))
    equipment = [
        dict(id="ct-1-scanner", type="ct", label="CT scanner 1", room="ct-1", catalog_ref="equipment/ct", provenance="inferred", source="fixture"),
        dict(id="xr-1-unit", type="xray", label="X-ray unit 1", room="xray-1", catalog_ref="equipment/xray", provenance="inferred", source="fixture"),
    ]
    return dict(
        schema_version=1, hospital_id="fixture", name="Fixture Hospital (hand-built, not a real plan)",
        disclaimer="Fixture layout for development. Not a real hospital. All flows simulated.",
        version=1,
        site=dict(w=100, d=70,
                  roads=[dict(id="road-s", label="Access road", width=7, points=[[0, 67], [100, 67]], provenance="inferred")],
                  buildings=[dict(id="tower", label="Tower", height=30, polygon=[[20, 2], [60, 2], [60, 6], [20, 6]], provenance="inferred", source="fixture")]),
        rooms=rooms, equipment=equipment, walk_speed_m_per_min=70,
        sources=[dict(title="hand-built fixture", url="contracts/fixtures/make_fixture.py", used_for="everything")],
    )


def make_rollout(layout, days=2, seed=1):
    rng = random.Random(seed)
    rooms = layout["rooms"]
    ridx = {r["id"]: i for i, r in enumerate(rooms)}
    bays = [r for r in rooms if r["type"] in ("treatment_bay", "resus_bay", "fast_track")]
    S = E["patient_state"]
    staff_ids = [f"MD-{i+1:02d}" for i in range(4)] + [f"RN-{i+1:02d}" for i in range(10)] + ["TECH-01", "REG-01"]
    staff_role = [E["staff_role"]["attending"]] * 4 + [E["staff_role"]["rn"]] * 10 + [E["staff_role"]["tech"], E["staff_role"]["registration"]]
    staff_home = [rng.choice(bays)["id"] for _ in range(14)] + ["ct-1", "entrance"]

    patients = {}  # id -> dict
    next_id = 0
    bay_of = {}
    snapshots, hourly = [], {k: [] for k in METRICS}
    decisions_all = []
    hour_acc = dict(arrivals=0, first_seen=0, wait_sum=0, lwbs=0, departures=0, los_sum=0)
    waits = []
    settings = {h["name"]: h["default"] for h in ACTIONS}

    def slot_pos(r, k):
        cols = max(1, int(r["w"] // 1.5))
        return (r["x"] - r["w"] / 2 + 0.75 + (k % cols) * 1.5, r["z"] - r["d"] / 2 + 0.75 + (k // cols) * 1.5)

    for t in range(days * 288):
        mod = (t * 5) % 1440
        hour = mod // 60
        rate = 3.0 + 7.0 * math.exp(-((hour - 13) / 5.0) ** 2)  # per hour, placeholder curve
        events, decisions = [], []
        if t % 12 == 0 and hour == 0 and t > 0:
            prev = settings["rn_night"]
            settings["rn_night"] = 1 if prev == 2 else 2
            d = dict(t=t, head="rn_night", value=settings["rn_night"], prev=prev, cadence="daily",
                     label=f"Nurses, night shift: level {prev} -> level {settings['rn_night']}")
            decisions.append(d)
            decisions_all.append(d)
        for _ in range(sum(1 for _ in range(4) if rng.random() < rate / 12 / 4)):
            patients[next_id] = dict(id=next_id, acuity=rng.choices([1, 2, 3, 4, 5], [1, 12, 50, 30, 7])[0],
                                     condition=rng.randrange(len(ENUMS["condition_group"])), state=S["waiting_triage"],
                                     exit=0, room="waiting", slot=rng.randrange(40), t0=t, ts=t,
                                     mode=rng.choices([0, 1], [80, 20])[0], band=rng.randrange(4), payer=rng.randrange(5),
                                     flags=0, next=t + rng.randint(1, 4))
            next_id += 1
            hour_acc["arrivals"] += 1
        gone = []
        for p in patients.values():
            if p["state"] == S["exited"]:
                gone.append(p["id"])
                continue
            if t < p["next"]:
                continue
            s = p["state"]
            if s == S["waiting_triage"]:
                p.update(state=S["in_triage"], room=f"triage-{rng.randint(1, 3)}", slot=0, ts=t, next=t + 2)
            elif s == S["in_triage"]:
                p.update(state=S["waiting_bay"], room="waiting", slot=rng.randrange(40), ts=t, next=t + 1)
            elif s == S["waiting_bay"]:
                free = [b for b in bays if b["id"] not in bay_of.values()]
                if free:
                    b = rng.choice(free)
                    bay_of[p["id"]] = b["id"]
                    p.update(state=S["waiting_provider"], room=b["id"], slot=0, ts=t, next=t + rng.randint(1, 6))
                elif (t - p["t0"]) > 36 and rng.random() < 0.03:
                    p.update(state=S["exited"], exit=E["patient_exit"]["lwbs"], ts=t)
                    hour_acc["lwbs"] += 1
                    events.append(dict(t=t, kind="lwbs", text=f"P-{p['id']:06d} left without being seen", entity=p["id"]))
            elif s == S["waiting_provider"]:
                w = (t - p["t0"]) * 5
                hour_acc["first_seen"] += 1
                hour_acc["wait_sum"] += w
                waits.append(w)
                p.update(state=S["with_provider"], ts=t, next=t + rng.randint(2, 5))
            elif s == S["with_provider"]:
                if rng.random() < 0.35:
                    p.update(state=S["in_test"], room=rng.choice(["ct-1", "xray-1"]), ts=t, next=t + rng.randint(2, 5))
                else:
                    p.update(state=S["waiting_results"], ts=t, next=t + rng.randint(4, 14))
            elif s == S["in_test"]:
                p.update(state=S["waiting_results"], room=bay_of[p["id"]], ts=t, next=t + rng.randint(4, 10))
            elif s == S["waiting_results"]:
                bay_of.pop(p["id"], None)
                hour_acc["departures"] += 1
                hour_acc["los_sum"] += (t - p["t0"]) * 5
                if rng.random() < 0.18:
                    p.update(state=S["in_ward"], room="ward-a", slot=rng.randrange(24), ts=t, flags=2, next=t + rng.randint(100, 250))
                else:
                    p.update(state=S["exited"], exit=E["patient_exit"]["discharged_ed"], ts=t)
            elif s == S["in_ward"]:
                p.update(state=S["exited"], exit=E["patient_exit"]["discharged_ward"], ts=t)
        cols = {k: [] for k in ["id", "acuity", "condition", "state", "exit", "room", "x", "z", "age_min", "state_min", "arrival_mode", "age_band", "payer", "flags", "staff"]}
        occ = [0] * len(rooms)
        for p in patients.values():
            r = rooms[ridx[p["room"]]]
            x, z = slot_pos(r, p["slot"])
            occ[ridx[p["room"]]] += 1
            for k, v in dict(id=p["id"], acuity=p["acuity"], condition=p["condition"], state=p["state"], exit=p["exit"],
                             room=ridx[p["room"]], x=round(x, 2), z=round(z, 2), age_min=(t - p["t0"]) * 5,
                             state_min=(t - p["ts"]) * 5, arrival_mode=p["mode"], age_band=p["band"], payer=p["payer"],
                             flags=p["flags"], staff=-1).items():
                cols[k].append(v)
        for pid in gone:
            patients.pop(pid)
        if t % 6 == 0:
            staff_home[:14] = [rng.choice(bays)["id"] if rng.random() < 0.3 else h for h in staff_home[:14]]
        sx, sz = [], []
        for h in staff_home:
            r = rooms[ridx[h]]
            sx.append(round(r["x"] + 0.9, 2))
            sz.append(round(r["z"] - 0.9, 2))
        status = []
        for i, r in enumerate(rooms):
            status.append(E["room_status"]["occupied"] if occ[i] else E["room_status"]["open_empty"])
        waiting = sum(1 for s in cols["state"] if s <= S["waiting_provider"])
        ed = sum(1 for s in cols["state"] if s < S["in_ward"])
        w_sorted = sorted(waits[-200:])
        p95 = w_sorted[int(0.95 * (len(w_sorted) - 1))] if w_sorted else 0
        snap = dict(
            t=t, clock=dict(day=t // 288, minute_of_day=mod, dow=(t // 288) % 7), layout_version=1,
            patients=cols,
            staff=dict(id=staff_ids, name=[None] * len(staff_ids), role=staff_role,
                       state=[E["staff_state"]["busy"] if i < 14 else E["staff_state"]["idle"] for i in range(len(staff_ids))],
                       room=[ridx[h] for h in staff_home], x=sx, z=sz, patient=[-1] * len(staff_ids),
                       fatigue=[round(0.2 + 0.02 * i, 2) for i in range(len(staff_ids))]),
            rooms=dict(status=status, occupancy=occ, queue=[0] * len(rooms)),
            equipment=dict(status=[E["equipment_status"]["in_use"] if occ[ridx["ct-1"]] else 0, E["equipment_status"]["in_use"] if occ[ridx["xray-1"]] else 0]),
            ambulances=[dict(id="AMB-1", x=70 + (t % 12), z=67, state="approaching")] if t % 24 < 12 else [],
            kpis=dict(settings=dict(settings), ed_census=ed, waiting_count=waiting, wait_p95_min=p95,
                      wait_mean_min=round(sum(w_sorted) / len(w_sorted), 1) if w_sorted else 0,
                      bay_occupancy=round(len(bay_of) / len(bays), 3), lwbs_rate=0.02, margin=0),
            events=events, decisions=decisions,
        )
        snapshots.append(snap)
        if t % 12 == 11:
            a = hour_acc
            vals = dict(arrivals=a["arrivals"], first_seen=a["first_seen"], door_to_provider_sum_min=a["wait_sum"],
                        wait_mean_min=a["wait_sum"] / a["first_seen"] if a["first_seen"] else 0, wait_p95_min=p95,
                        lwbs=a["lwbs"], lwbs_rate=a["lwbs"] / max(1, a["arrivals"]), ed_census=ed, waiting_count=waiting,
                        ed_departures=a["departures"], ed_los_sum_min=a["los_sum"],
                        ed_los_median_min=a["los_sum"] / a["departures"] if a["departures"] else 0,
                        bay_occupancy=len(bay_of) / len(bays), ward_occupancy=occ[ridx["ward-a"]] / 24,
                        treated=a["departures"], md_utilization=0.7, rn_utilization=0.65, staff_on_shift=len(staff_ids),
                        revenue=a["departures"] * 900.0, cost_labor=len(staff_ids) * 70.0, cost_fixed=1500.0,
                        cost_variable=a["departures"] * 60.0)
            vals["cost_total"] = vals["cost_labor"] + vals["cost_fixed"] + vals["cost_variable"]
            vals["margin"] = vals["revenue"] - vals["cost_total"]
            for k in METRICS:
                hourly[k].append(round(float(vals.get(k, 0.0)), 3))
            hour_acc = dict(arrivals=0, first_seen=0, wait_sum=0, lwbs=0, departures=0, los_sum=0)

    spec = [dict(h, values=list(range(len(h["options"])))) for h in ACTIONS]
    hrs = len(hourly["arrivals"])
    summary = dict(
        wait_mean_min=sum(hourly["door_to_provider_sum_min"]) / max(1, sum(hourly["first_seen"])),
        wait_p95_min=max(hourly["wait_p95_min"]), lwbs_rate=sum(hourly["lwbs"]) / max(1, sum(hourly["arrivals"])),
        cost_per_day=sum(hourly["cost_total"]) / (hrs / 24), margin_per_day=sum(hourly["margin"]) / (hrs / 24),
        ed_los_median_min=sum(hourly["ed_los_sum_min"]) / max(1, sum(hourly["ed_departures"])),
    )
    return dict(
        schema_version=1,
        header=dict(rollout_id="fixture", manager=dict(id="fixture_fixed", kind="fixed", label="Fixture (not a simulator run)", objective="none"),
                    scenario="fixture", hospital_id="fixture", seed=seed, tick_minutes=5, days=days, created="2026-10-10",
                    synthetic=True, enums=ENUMS, layout=layout, action_spec=spec, summary={k: round(v, 3) for k, v in summary.items()}),
        hourly=hourly, decisions=decisions_all, structural_changes=[],
        segments=[dict(label="Day 0 08:00-20:00", start_t=96, every_ticks=1, snapshots=snapshots[96:240])],
    )


def validator(name):
    store = {}
    for f in C.glob("*.schema.json"):
        s = json.loads(f.read_text())
        store[s["$id"]] = Resource.from_contents(s)
    reg = Registry().with_resources(store.items())
    return Draft202012Validator(json.loads((C / name).read_text()), registry=reg)


if __name__ == "__main__":
    layout = make_layout()
    validator("layout.schema.json").validate(layout)
    rollout = make_rollout(layout)
    validator("rollout.schema.json").validate(rollout)
    (HERE / "layout.fixture.json").write_text(json.dumps(layout, indent=1))
    (HERE / "rollout.fixture.json").write_text(json.dumps(rollout, separators=(",", ":")))
    (HERE / "snapshot.fixture.json").write_text(json.dumps(rollout["segments"][0]["snapshots"][60], indent=1))
    print("ok", len(layout["rooms"]), "rooms;", len(rollout["segments"][0]["snapshots"]), "snapshots;",
          (HERE / "rollout.fixture.json").stat().st_size // 1024, "KB")
