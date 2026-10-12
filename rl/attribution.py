"""Marginal value of every resource unit of a hospital: point at a doctor, a room or a machine and read off
what it is worth. ALL NUMBERS ARE SIMULATED (a model fitted to public aggregates, not the hospital's data).

    python -m rl.attribution --hospital rwjuh_nb [--manager fixed|<policy id>] [--scenarios normal_week flu_surge]
                             [--seeds 32] [--days 30] [--workers 24]
    -> rl/hospitals/<id>/attribution.json + ATTRIBUTION.md   (attribution__<manager>.json for a named policy)

Method. Demand comes from a random stream that does not depend on actions or parameters, so two simulators
on the same seed face the same patients. For each resource unit the twin is run WITHOUT one unit and, where it
means something, WITH one more, on the same held-out seeds as the hospital's calibrated baseline ("current
practice"); every number is the mean over seeds of the PAIRED difference with a 95% Student-t interval.

How one unit is removed / added (each manipulation is asserted against the counts the simulator uses):
  * a provider / nurse on one shift: the 5-entry staffing ladder is rebuilt to contain the wanted head-count
    and the baseline action indices are re-pointed at it (`ladder_with`);
  * a triage station, fast track open/closed, hallway spaces, second-CT staffing hours: the baseline action;
  * a treatment bay of a class, ward beds, a CT scanner, an X-ray room: the `layout_edit` override of
    sim.load_scenario (capacity edits before the layout model is built).

Identifiability. Providers of a role are interchangeable in this model, so "Dr X on the evening shift" has the
value of "one evening provider"; bays of a class share the class-centroid walking distances, so every bay of a
class has the same simulated value (`location` lists the per-bay geometry the model does not use).

`minus_one` holds (without the unit) - (baseline): the effect of REMOVING it; `plus_one` holds
(with one more) - (baseline). The value of the existing unit is therefore -minus_one.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import math
import multiprocessing as mp
import os
import time
from pathlib import Path

import torch

from .common import (OBJECTIVES, ROOT, SCALE_FLOORS, SEED_EVAL, TERMS, calibration_fingerprint, hospital_id, now_iso, paths, weights_dict,
                     write_json, write_text)
from .objectives import EPISODE_METRICS, FLOORS, FLOW_INDEX, LOWER_IS_BETTER

SEED0 = SEED_EVAL + 100_000            # held-out; disjoint from tuning, training and in-training validation
DEFAULT_OBJECTIVE = "balanced"
SHIFTS = ("day", "evening", "night")
BAY_TYPES = dict(resus="resus_bay", main="treatment_bay", fast="fast_track", peds="peds_ed")
BAY_LABEL = dict(resus="resuscitation bay", main="main treatment bay", fast="fast-track space", peds="pediatric ED bay", hall="hallway stretcher space")
# hourly metrics kept as time profiles (per simulated day and by hour of day); all are per-hour sums
PROFILE = ["margin", "revenue", "cost_total", "waiting_patient_minutes", "lwbs", "boarding_hours", "ed_census", "adverse_events", "deaths"]
PROFILE_INFO = {
    "margin": ("Margin", "$"), "revenue": ("Revenue", "$"), "cost_total": ("Total cost", "$"),
    "waiting_patient_minutes": ("Patient-minutes waiting for a provider", "min"), "lwbs": ("Left without being seen", "patients"),
    "boarding_hours": ("Boarding", "patient-hours"), "ed_census": ("ED patient-hours", "patient-hours"),
    "adverse_events": ("Adverse events", "events"), "deaths": ("Deaths", "patients")}
METRIC_INFO = {
    "wait_mean_min": ("Mean door-to-provider wait", "min"), "wait_p95_min": ("95th-percentile door-to-provider wait", "min"),
    "ed_los_median_min": ("Median ED length of stay", "min"), "ed_los_mean_min": ("Mean ED length of stay", "min"),
    "lwbs_rate": ("Left-without-being-seen rate", "fraction"), "lwbs_per_day": ("Left without being seen", "patients/day"),
    "boarding_hours_per_day": ("Boarding", "patient-hours/day"), "deaths_per_day": ("Deaths", "per day"),
    "deaths_per_10k": ("Deaths", "per 10,000 arrivals"), "adverse_events_per_day": ("Adverse events", "per day"),
    "hi_acuity_wait_hours_per_day": ("ESI 1-2 patients waiting", "patient-hours/day"),
    "labor_cost_per_day": ("Labor cost", "$/day"), "fixed_cost_per_day": ("Fixed staffed-space cost", "$/day"),
    "operating_cost_per_day": ("Operating cost (labor + fixed)", "$/day"), "cost_per_day": ("Total cost", "$/day"),
    "revenue_per_day": ("Revenue", "$/day"), "margin_per_day": ("Margin", "$/day"), "treated_per_day": ("Patients treated", "per day"),
    "admissions_per_day": ("Admissions", "per day"), "transfers_per_day": ("Transfers out", "per day"),
    "wait_patient_hours_per_day": ("Waiting for a provider", "patient-hours/day"), "ed_patient_hours_per_day": ("ED patient-hours", "per day"),
    "staff_hours_per_day": ("Staff-hours", "per day"), "overtime_hours_per_day": ("Overtime", "hours/day"),
    "diversion_hours_per_day": ("Ambulance diversion", "hours/day"), "cost_per_treated": ("Cost per treated patient", "$"),
    "arrivals_per_day": ("Arrivals", "per day"), "diverted_per_day": ("Diverted ambulances", "per day")}
# the metrics the report leads with, and the ones a "no measurable harm" verdict is judged on
HEADLINE = ["wait_mean_min", "wait_p95_min", "ed_los_median_min", "lwbs_per_day", "boarding_hours_per_day", "deaths_per_day",
            "adverse_events_per_day", "labor_cost_per_day", "operating_cost_per_day", "revenue_per_day", "margin_per_day"]
EFFECTS = ["wait_mean_min", "wait_p95_min", "ed_los_median_min", "lwbs_per_day", "boarding_hours_per_day", "hi_acuity_wait_hours_per_day",
           "adverse_events_per_day", "deaths_per_day", "treated_per_day", "revenue_per_day"]
HARM = {"wait_mean_min": 0.02, "wait_p95_min": 0.02, "ed_los_median_min": 0.02, "lwbs_per_day": 0.02, "boarding_hours_per_day": 0.02,
        "hi_acuity_wait_hours_per_day": 0.05, "adverse_events_per_day": 0.05, "deaths_per_day": 0.05}
HARM_FLOORS = dict(FLOORS, lwbs_per_day=0.5, deaths_per_day=0.05)


# ------------------------------------------------------------------------------------------ small maths
def t975(df: int) -> float:
    """97.5% point of Student's t (Cornish-Fisher expansion; exact to 3 decimals for df >= 3)."""
    if df <= 0:
        return float("nan")
    if df == 1:
        return 12.706
    if df == 2:
        return 4.303
    z = 1.959964
    return (z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)
            + (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * df ** 3)
            + (79 * z ** 9 + 776 * z ** 7 + 1482 * z ** 5 - 1920 * z ** 3 - 945 * z) / (92160 * df ** 4))


def paired(delta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """delta: [n_seeds, ...] paired differences -> (mean, 95% half-width) over seeds (Student t)."""
    d = delta.double()
    n = d.shape[0]
    mean = d.mean(0)
    if n < 2:
        return mean, torch.full_like(mean, float("nan"))
    return mean, t975(n - 1) * d.std(0, unbiased=True) / math.sqrt(n)


def _r(x, sig: int = 5):
    """Round to `sig` significant digits (floats, tensors, nested lists)."""
    if isinstance(x, torch.Tensor):
        x = x.tolist()
    if isinstance(x, (list, tuple)):
        return [_r(v, sig) for v in x]
    x = float(x)
    if x == 0 or not math.isfinite(x):
        return 0.0 if x == 0 else None
    return round(x, sig - 1 - int(math.floor(math.log10(abs(x)))))


def stat(delta: torch.Tensor) -> dict:
    m, hw = paired(delta)
    m, hw = float(m), float(hw)
    return dict(mean=_r(m), lo=_r(m - hw), hi=_r(m + hw))


def reward_delta(terms_delta: torch.Tensor, scales: dict, weights) -> torch.Tensor:
    """[n_seeds, len(TERMS)] RAW per-hour term differences -> [n_seeds] difference in mean hourly reward,
    reward = -sum_k w_k * term_k / scale_k (the gym's definition; rl.env.reward_terms)."""
    w = weights_dict(weights)
    wv = torch.tensor([w[k] / float(scales[k]) for k in TERMS], dtype=torch.float64)
    return -(terms_delta.double() * wv).sum(-1)


def ladder_with(levels, needed) -> tuple[list[int], dict[int, int]]:
    """A staffing ladder of the same length that contains every head-count in `needed` (ascending, distinct),
    keeping the original entries that are farthest from the needed ones. -> (ladder, head-count -> index)."""
    levels = [int(x) for x in levels]
    need = sorted({int(x) for x in needed})
    if not need or need[0] < 1 or len(need) > len(levels):
        raise ValueError(f"cannot build a {len(levels)}-entry ladder containing {need}")
    out = list(need)
    spare = sorted((x for x in set(levels) if x not in need), key=lambda x: (-min(abs(x - n) for n in need), x))
    for x in spare:
        if len(out) < len(levels):
            out.append(x)
    v = max(out)
    while len(out) < len(levels):
        v += 1
        out.append(v)
    out.sort()
    return out, {n: out.index(n) for n in need}


# ------------------------------------------------------------------------------------------ resource units
def counts_of(scn) -> dict:
    """The resource counts the simulator will actually use under the scenario's baseline actions."""
    P, lm = scn.P, scn.layout
    d = {h["name"]: int(h["default"]) for h in scn.heads}
    c = {}
    for s in SHIFTS:
        c[f"providers_{s}"] = int(P["provider_levels"][d[f"md_{s}"]])
        c[f"nurses_{s}"] = int(P["rn_levels"][d[f"rn_{s}"]])
    c["triage_stations"] = int(min(P["triage_levels"][d["triage_nurses"]], lm.n_triage_rooms))
    from sim.layoutmodel import BAY_CLASSES
    for i, n in enumerate(BAY_CLASSES):
        if n != "hall":
            c[f"bays_{n}"] = sum(1 for b in lm.bays if b["cls"] == i and b["exists0"])
    c["hallway_open"] = int(P["hall_opts"][d["overflow_bays"]])
    c["ward_beds"] = int(P["ward_cap0"])
    c["ct_scanners"] = int(P["equip"]["ct"]["units"])
    c["xray_rooms"] = int(P["equip"]["xray"]["units"])
    c["fast_track_open"] = int(d["fast_track"])
    w = P["imaging_windows"][d["imaging_hours"]]
    c["second_ct_staffed_hours"] = int(w[1] - w[0])
    return c


def _shift_hours(starts, i):
    a, b = int(starts[i]), int(starts[(i + 1) % 3])
    return [h % 24 for h in range(a, b if b > a else b + 24)]


def build_units(hospital: str | None = None, scenario: str = "normal_week", with_all_shift: bool = False) -> list[dict]:
    """Every resource unit with the overrides that remove / add exactly one (and what the counts must become)."""
    from sim import load_scenario
    h = hospital_id(hospital)
    scn = load_scenario(scenario, {"hospital_id": h})
    P, lm = scn.P, scn.layout
    d = {x["name"]: int(x["default"]) for x in scn.heads}
    base = counts_of(scn)
    ben = float(P["benefits_load"])
    mix = P["role_mix"]
    wage_md = sum(P["wage"][r] * w for r, w in mix.items()) / (sum(mix.values()) or 1.0)
    wage_rn = float(P["wage"]["rn"])
    starts = [int(x) for x in scn.engine["shift_start_hours"]]
    units = []

    def U(id, label, cls, kind, unit_label, cost, basis, minus=None, plus=None, **kw):
        units.append(dict(id=id, label=label, resource_class=cls, kind=kind, unit_label=unit_label, unit_cost_per_day=float(cost), cost_basis=basis,
                          minus=minus, plus=plus, **kw))

    def V(overrides, expect, desc, n_units=1):
        return dict(overrides=overrides, expect=expect, desc=desc, n_units=int(n_units))

    # ---- staff: one provider / nurse on each shift
    for role, head, key, levels, wage, who in (("provider", "md", "provider_levels", P["provider_levels"], wage_md, "provider"),
                                               ("nurse", "rn", "rn_levels", P["rn_levels"], wage_rn, "nurse")):
        cur = {s: int(levels[d[f"{head}_{s}"]]) for s in SHIFTS}

        def staff_v(delta: dict, desc):
            want = {s: cur[s] + delta.get(s, 0) for s in SHIFTS}
            if min(want.values()) < 1:
                return None
            lad, idx = ladder_with(levels, want.values())
            return V({f"staff.shared.{key}": lad, "baseline_actions": {f"{head}_{s}": idx[want[s]] for s in SHIFTS}},
                     {f"{role}s_{s}": delta.get(s, 0) for s in SHIFTS if delta.get(s, 0)}, desc)

        for i, s in enumerate(SHIFTS):
            hrs = _shift_hours(starts, i)
            basis = (f"{'blended provider wage (attending/resident/APP mix)' if role == 'provider' else 'RN wage'} ${wage:.2f}/h x {len(hrs)} h "
                     f"x benefits load {ben:.3f}")
            U(f"{role}_{s}", f"One {who}, {s} shift", f"{role}_{s}", "staff", f"one {who} on the {s} shift ({hrs[0]:02d}:00-{(hrs[-1] + 1) % 24:02d}:00)",
              wage * len(hrs) * ben, basis,
              minus=staff_v({s: -1}, f"{cur[s]} -> {cur[s] - 1} {who}s on the {s} shift"),
              plus=staff_v({s: +1}, f"{cur[s]} -> {cur[s] + 1} {who}s on the {s} shift"),
              shift=s, hours=hrs, count=cur[s], role=role)
        if with_all_shift:
            # under a policy that picks its own levels only the whole ladder can be shifted: every level one lower / higher
            sh = lambda dv: V({f"staff.shared.{key}": [int(x) + dv for x in levels]}, {f"{role}s_{s}": dv for s in SHIFTS},   # noqa: E731
                              f"every staffing level {'one lower' if dv < 0 else 'one higher'} ({who}s), whatever level the policy picks")
            U(f"{role}_all_shifts", f"One {who} on every shift", f"{role}_all", "staff", f"one {who} on each of the three shifts",
              wage * 24 * ben, f"wage ${wage:.2f}/h x 24 h x benefits load {ben:.3f}",
              minus=sh(-1) if min(levels) > 1 else None, plus=sh(+1), shift=None, hours=list(range(24)), count=sum(cur.values()), role=role)

    # ---- triage station (a room plus the nurse who staffs it), round the clock
    tl, ti = [int(x) for x in P["triage_levels"]], d["triage_nurses"]
    n_tri = base["triage_stations"]
    tri_cost = (wage_rn * ben + float(P["triage_fixed"])) * 24
    minus = V({"baseline_actions": {"triage_nurses": tl.index(n_tri - 1)}}, {"triage_stations": -1}, f"{n_tri} -> {n_tri - 1} staffed triage stations") \
        if n_tri - 1 in tl else None
    new_tl = list(tl)
    new_tl[ti] = n_tri + 1                       # the baseline option now staffs one more station
    for j in range(ti + 1, len(new_tl)):
        new_tl[j] = max(new_tl[j], new_tl[j - 1] + 1)
    plus_ov = {"staff.shared.triage_nurse_levels": new_tl}
    if lm.n_triage_rooms < n_tri + 1:
        plus_ov["layout_edit"] = {"add": {"triage": n_tri + 1 - lm.n_triage_rooms}}
    U("triage_station", "One triage station (room + nurse)", "triage_station", "staff", "one staffed triage station, 24 h", tri_cost,
      f"(RN wage ${wage_rn:.2f}/h x benefits {ben:.3f} + room ${P['triage_fixed']:.2f}/h) x 24 h",
      minus=minus, plus=V(plus_ov, {"triage_stations": +1}, f"{n_tri} -> {n_tri + 1} staffed triage stations (a station is added to the layout)"),
      shift=None, hours=list(range(24)), count=n_tri, role="triage")

    # ---- treatment spaces by class
    from sim.layoutmodel import BAY_CLASSES
    bstep = int(P["bay_step"])
    for i, n in enumerate(BAY_CLASSES):
        if n == "hall" or base.get(f"bays_{n}", 0) <= 0:
            continue
        cnt, fx = base[f"bays_{n}"], float(P["bay_fixed"][i])
        U(f"bay_{n}", f"One {BAY_LABEL[n]}", f"bay_{n}", "space", f"one {BAY_LABEL[n]} (of {cnt})", fx * 24, f"staffed-space fixed cost ${fx:.2f}/h x 24 h",
          minus=V({"layout_edit": {"remove": {BAY_TYPES[n]: 1}}}, {f"bays_{n}": -1}, f"{cnt} -> {cnt - 1} {BAY_LABEL[n]}s") if cnt > 1 else None,
          plus=V({"layout_edit": {"add": {BAY_TYPES[n]: 1}}}, {f"bays_{n}": +1}, f"{cnt} -> {cnt + 1} {BAY_LABEL[n]}s"),
          shift=None, hours=list(range(24)), count=cnt, bay_class=n,
          capital_note=(f"building a bay costs ${P['bay_build_cost']:,.0f} in the model (not in the daily figures)" if n == "main" else None))
        if n == "main" and cnt > bstep:
            U("bay_main_block", f"A block of {bstep} main treatment bays", "bay_main", "space", f"{bstep} main treatment bays (the bays_delta step)", fx * 24 * bstep,
              f"staffed-space fixed cost ${fx:.2f}/h x 24 h x {bstep}",
              minus=V({"layout_edit": {"remove": {BAY_TYPES[n]: bstep}}}, {"bays_main": -bstep}, f"{cnt} -> {cnt - bstep} main treatment bays", bstep),
              plus=V({"layout_edit": {"add": {BAY_TYPES[n]: bstep}}}, {"bays_main": +bstep}, f"{cnt} -> {cnt + bstep} main treatment bays", bstep),
              shift=None, hours=list(range(24)), count=cnt, bay_class=n, block=bstep)
    # hallway overflow: closed at baseline, so only "open one" / "open the low block" exist
    ho, fx = [int(x) for x in P["hall_opts"]], float(P["bay_fixed"][BAY_CLASSES.index("hall")])
    if base["hallway_open"] == 0 and len(ho) > 1 and max(ho) >= 1:
        one = [1] + [x for x in ho[1:]]
        U("bay_hall", "One hallway stretcher space", "bay_hall", "space", "one hallway overflow space (none are open at baseline)", fx * 24,
          f"staffed-space fixed cost ${fx:.2f}/h x 24 h",
          plus=V({"hospital.hallway_overflow_spaces": one}, {"hallway_open": +1}, "0 -> 1 hallway spaces open round the clock"),
          shift=None, hours=list(range(24)), count=0, bay_class="hall")
        U("bay_hall_block", f"Hallway overflow, {ho[1]} spaces", "bay_hall", "space", f"{ho[1]} hallway overflow spaces (the overflow_bays 'low' option)", fx * 24 * ho[1],
          f"staffed-space fixed cost ${fx:.2f}/h x 24 h x {ho[1]}",
          plus=V({"baseline_actions": {"overflow_bays": 1}}, {"hallway_open": ho[1]}, f"0 -> {ho[1]} hallway spaces open round the clock", ho[1]),
          shift=None, hours=list(range(24)), count=0, bay_class="hall", block=ho[1])

    # ---- fast track as a whole
    if base.get("bays_fast", 0) > 0 and base["fast_track_open"] == 1:
        fx = float(P["bay_fixed"][BAY_CLASSES.index("fast")])
        U("fast_track", "Fast track (the whole stream)", "fast_track", "space", f"the fast-track stream: {base['bays_fast']} spaces with a dedicated provider",
          fx * 24 * base["bays_fast"], f"staffed-space fixed cost ${fx:.2f}/h x 24 h x {base['bays_fast']} spaces (its provider and nurse come from the shift roster)",
          minus=V({"baseline_actions": {"fast_track": 0}}, {"fast_track_open": -1}, "fast track closed: its spaces shut, its provider rejoins the main pool",
                  base["bays_fast"]),
          shift=None, hours=list(range(24)), count=1, block=base["bays_fast"])

    # ---- inpatient ward beds
    wb, wstep, cap = float(P["ward_bed_fixed"]), int(P["ward_step"]), base["ward_beds"]
    for uid, k, lab in (("ward_bed", 1, "One inpatient ward bed"), ("ward_bed_block", wstep, f"A block of {wstep} inpatient ward beds")):
        U(uid, lab, "ward_bed", "space", f"{k} inpatient bed{'s' if k > 1 else ''} of the pool the ED admits to (of {cap})", wb * 24 * k,
          f"ward fixed cost ${wb:.2f}/bed-hour x 24 h" + (f" x {k}" if k > 1 else ""),
          minus=V({"layout_edit": {"remove": {"ward_unit": k}}}, {"ward_beds": -k}, f"{cap} -> {cap - k} inpatient beds", k),
          plus=V({"layout_edit": {"add": {"ward_unit": k}}}, {"ward_beds": +k}, f"{cap} -> {cap + k} inpatient beds", k),
          shift=None, hours=list(range(24)), count=cap, **({"block": k} if k > 1 else {}))

    # ---- scanners
    tech = float(P["wage"]["imaging_tech"]) * ben * float(P["second_imaging_unit_tech"])
    win = P["imaging_windows"][d["imaging_hours"]]
    wh = int(win[1] - win[0])
    for t, lab, ckey in (("ct", "CT scanner", "ct_scanners"), ("xray", "X-ray room", "xray_rooms")):
        e, n = P["equip"][t], base[ckey]
        fixed = (e["maint_h"] + e["room_fixed"]) * 24
        cost = fixed + (tech * wh if t == "ct" else 0.0)
        basis = f"(maintenance ${e['maint_h']:.2f}/h + room ${e['room_fixed']:.2f}/h) x 24 h" + \
            (f" + technologist ${tech:.2f}/h x {wh} staffed hours (units beyond the first)" if t == "ct" else "")
        U(f"{t}_scanner" if t == "ct" else "xray_room", f"One {lab}", f"{t}_scanner" if t == "ct" else "xray_room", "equipment", f"one {lab} (of {n})", cost, basis,
          minus=V({"layout_edit": {"remove": {t: 1}}}, {ckey: -1}, f"{n} -> {n - 1} {lab}s") if n > 1 else None,
          plus=V({"layout_edit": {"add": {t: 1}}}, {ckey: +1}, f"{n} -> {n + 1} {lab}s"),
          shift=None, hours=list(range(24)), count=n, equipment_type=t,
          capital_note=f"purchase price ${e['purchase']:,.0f} in the catalog is not in the daily figures")
    # second-CT staffing hours (the imaging_hours action)
    wins, wi = P["imaging_windows"], d["imaging_hours"]
    n_extra = max(0, base["ct_scanners"] - int(P["units_always_staffed"]))
    if n_extra > 0:
        def win_v(j):
            w = wins[j]
            hrs = int(w[1] - w[0])
            return V({"baseline_actions": {"imaging_hours": j}}, {"second_ct_staffed_hours": hrs - wh},
                     f"second CT staffed {int(w[0]):02d}:00-{int(w[1]) % 24:02d}:00 instead of {int(win[0]):02d}:00-{int(win[1]) % 24:02d}:00", abs(hrs - wh))
        lo, hi = (win_v(wi - 1) if wi > 0 else None), (win_v(wi + 1) if wi + 1 < len(wins) else None)
        blk = abs(int(wins[wi][1] - wins[wi][0]) - int(wins[wi - 1][1] - wins[wi - 1][0])) if wi > 0 else abs(int(wins[wi + 1][1] - wins[wi + 1][0]) - wh)
        U("second_ct_hours", f"Second-CT staffing, an {blk}-hour block", "second_ct_hours", "equipment",
          f"{blk} more / fewer staffed hours a day on CT units beyond the first (now {wh} h: {int(win[0]):02d}:00-{int(win[1]) % 24:02d}:00)",
          tech * blk * n_extra, f"technologist ${tech:.2f}/h (wage x benefits) x {blk} h x {n_extra} extra unit(s)",
          minus=lo, plus=hi, shift=None, hours=list(range(int(win[0]), int(win[1]))), count=wh, block=blk, equipment_type="ct")
    for u in units:
        u["baseline_counts"] = base
    return units


def location_table(hospital: str | None = None, scenario: str = "normal_week") -> dict:
    """Per-bay geometry the simulator does NOT use (it walks patients between zone centroids): how much nearer
    or farther each bay is than its class centroid from the waiting room and from CT, in metres and seconds."""
    from sim import load_scenario
    from sim.layoutmodel import BAY_CLASSES
    scn = load_scenario(scenario, {"hospital_id": hospital_id(hospital)})
    lm, f, rooms = scn.layout, scn.layout.path_factor, scn.layout.rooms
    speed = float(scn.P["walk_speed_m_per_min"])
    man = lambda a, b: f * (abs(a[0] - b[0]) + abs(a[1] - b[1]))                  # noqa: E731
    xy = lambda i: (rooms[i]["x"], rooms[i]["z"])                                  # noqa: E731
    cen = lambda idx: (sum(rooms[i]["x"] for i in idx) / len(idx), sum(rooms[i]["z"] for i in idx) / len(idx)) if idx else None   # noqa: E731
    wait, ct = xy(lm.waiting), cen(lm.scan_rooms["ct"] or lm.scan_rooms["xray"])
    out, by_class = {}, {}
    for ci, cname in enumerate(BAY_CLASSES):
        idx = sorted({b["room"] for b in lm.bays if b["cls"] == ci and b["exists0"]})
        if not idx or cname == "hall":
            continue
        c = cen(idx)
        dw0, dc0 = man(wait, c), (man(c, ct) if ct else 0.0)
        ds = []
        for i in idx:
            dw, dc = man(wait, xy(i)), (man(xy(i), ct) if ct else 0.0)
            extra = (dw - dw0) + (dc - dc0)                                        # one walk in, one leg to CT (when imaged)
            out[rooms[i]["id"]] = dict(bay_class=cname, to_waiting_m=round(dw, 1), to_ct_m=round(dc, 1), vs_class_waiting_m=round(dw - dw0, 1),
                                       vs_class_ct_m=round(dc - dc0, 1), walk_seconds_vs_class=round(60.0 * extra / speed, 1))
            ds.append(60.0 * extra / speed)
        by_class[cname] = dict(n=len(idx), class_to_waiting_m=round(dw0, 1), class_to_ct_m=round(dc0, 1),
                               walk_seconds_vs_class_min=round(min(ds), 1), walk_seconds_vs_class_max=round(max(ds), 1))
    return dict(modelled=False, walk_speed_m_per_min=speed, by_class=by_class, rooms=out,
                note="The simulator walks every patient of a bay class over the same distance (class centroid to zone centroid), so all bays of a class "
                     "have the same simulated value. These are the geometric differences it ignores: seconds a single walk in plus one leg to CT would "
                     "gain or lose for this bay against its class centroid. Geometry only, not a simulated outcome.")


# ------------------------------------------------------------------------------------------ one simulator run
@torch.no_grad()
def run_variant(task: dict) -> dict:
    """One (scenario, variant) on all seeds in one batch -> per-seed tensors. task: hospital, scenario, key,
    overrides, expect, base_counts, seeds, days, manager."""
    t0 = time.time()
    torch.set_num_threads(int(task.get("threads", 1)))
    from sim.engine import S_EXIT, S_TEST, S_TRI
    from sim.layoutmodel import BAY_CLASSES

    from .env import HospitalEnv
    from .managers import MultiPolicy, load_manager
    h, seeds, days = task["hospital"], task["seeds"], int(task["days"])
    B, hours = len(seeds), days * 24
    unit = {"scales": {k: 1.0 for k in TERMS}}                       # raw terms; the report normalises by its own baseline
    env = HospitalEnv(task["scenario"], B, "cpu", torch.tensor(seeds), hours, stage="stage_3", weights={}, scales=unit, auto_reset=False,
                      hospital=h, member=None, overrides=dict(task.get("overrides") or {}))
    sim = env.sim
    counts = counts_of(sim.scn)
    # ---- the manipulation must be exactly what was asked for, in the counts the simulator uses
    if task.get("base_counts") is not None:
        want = dict(task["base_counts"])
        for k, dv in (task.get("expect") or {}).items():
            want[k] = want[k] + int(dv)
        if counts != want:
            diff = {k: (want.get(k), counts.get(k)) for k in set(want) | set(counts) if want.get(k) != counts.get(k)}
            raise AssertionError(f"variant {task['key']}: resource counts differ from the intended manipulation (want, got): {diff}")
        assert int(sim.eq_units0[1]) == counts["ct_scanners"] and int(sim.eq_units0[0]) == counts["xray_rooms"]
        assert int(sim.cfg["ward_cap0"]) == counts["ward_beds"]
    pol = MultiPolicy([load_manager(task.get("manager") or "fixed", "cpu", hospital=h)], [B])
    pol.reset(B, env.device, env.default_actions())
    obs = env.reset()
    NB = sim.NB
    prof_day = torch.zeros((B, days, len(PROFILE)), dtype=torch.float64)
    prof_hod = torch.zeros((B, 24, len(PROFILE)), dtype=torch.float64)
    term_day = torch.zeros((B, days, len(TERMS)), dtype=torch.float64)
    term_hod = torch.zeros((B, 24, len(TERMS)), dtype=torch.float64)
    ukeys = ["providers", "nurses", "triage"] + [f"bay_{n}" for n in BAY_CLASSES] + ["ward", "ct", "xray"]
    u_num, u_den, u_full = (torch.zeros((len(ukeys), 24), dtype=torch.float64) for _ in range(3))
    for hr in range(hours):
        obs, r, dn, info = env.step(pol.act(obs, env.action_mask()))
        m, day, hod = info["metrics"], hr // 24, hr % 24
        row = torch.stack([m[k].double() for k in PROFILE], 1)
        prof_day[:, day] += row
        prof_hod[:, hod] += row
        tr = info["terms"].double()
        term_day[:, day] += tr
        term_hod[:, hod] += tr
        # ---- utilisation, end-of-hour instants (hourly means for staff)
        p = sim.p
        act = p["active"] & (p["state"] != S_EXIT)
        busy, opn = sim.bay_busy[:, :NB], sim.bay_open[:, :NB]
        nums = [m["md_utilization"] * sim.md_eff.float(), m["rn_utilization"].clamp(max=1.0) * sim.rn_eff.float(), (act & (p["state"] == S_TRI)).sum(1).float()]
        dens = [sim.md_eff.float(), sim.rn_eff.float(), sim.tri_n.float()]
        for ci in range(len(BAY_CLASSES)):
            is_c = sim.bay_is[ci][:NB]
            nums.append((busy & is_c).sum(1).float())
            dens.append((opn & is_c).sum(1).float())
        nums.append(m["ward_occupancy"] * sim.ward_cap.float())
        dens.append(sim.ward_cap.float())
        for ti in (1, 0):
            nums.append((act & (p["state"] == S_TEST) & (p["eq"] == ti)).sum(1).float())
            dens.append(sim.eq_avail[:, ti].float())
        for j, (a, b_) in enumerate(zip(nums, dens)):
            u_num[j, hod] += float(a.sum())
            u_den[j, hod] += float(b_.sum())
            u_full[j, hod] += float(((a >= b_ - 1e-6) & (b_ > 0)).float().mean())
    assert bool(dn.all())
    util = {}
    for j, k in enumerate(ukeys):
        if float(u_den[j].sum()) <= 0:
            continue
        util[k] = dict(mean=float(u_num[j].sum() / u_den[j].sum()), full_share=float(u_full[j].sum() / hours),
                       by_hour=(u_num[j] / u_den[j].clamp(min=1e-9)).tolist(), full_by_hour=(u_full[j] / days).tolist())
    return dict(key=task["key"], scenario=task["scenario"], seeds=list(seeds), days=days, counts=counts, layout_edit=list(getattr(sim.scn, "layout_edit", []) or []),
                episode=info["episode"].double().cpu(), terms=(env.ep_terms / env.h).double().cpu(), prof_day=prof_day, prof_hod=prof_hod / days,
                term_day=term_day / 24.0, term_hod=term_hod / days, util=util, legs=[float(x) for x in sim.scn.layout.legs[0]],
                invalid=float(info["invalid_actions"].float().sum()), seconds=time.time() - t0)


def _worker(task):
    try:
        return run_variant(task)
    except Exception as e:  # noqa: BLE001 - one failed variant must not lose the others
        import traceback
        return dict(key=task["key"], scenario=task["scenario"], error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())


def run_tasks(tasks: list[dict], workers: int = 0, work_dir: Path | None = None, log=print) -> dict:
    """-> {(scenario, key): result}. Finished results are checkpointed in `work_dir` and reused."""
    out, todo = {}, []
    for t in tasks:
        f = (work_dir / f"{t['scenario']}__{t['key']}.pt") if work_dir else None
        if f is not None and f.exists():
            r = torch.load(f)
            if r.get("seeds") == list(t["seeds"]) and r.get("days") == t["days"]:
                out[(t["scenario"], t["key"])] = r
                continue
        todo.append(t)
    if work_dir:
        work_dir.mkdir(parents=True, exist_ok=True)

    def done(r):
        if "error" in r:
            log(f"  FAILED {r['scenario']} {r['key']}: {r['error']}")
        else:
            log(f"  {r['scenario']:<12} {r['key']:<28} {r['seconds']:.0f}s")
            if work_dir:
                f = work_dir / f"{r['scenario']}__{r['key']}.pt"
                tmp = f.with_suffix(f".{os.getpid()}.tmp")
                torch.save(r, tmp)
                os.replace(tmp, f)
        out[(r["scenario"], r["key"])] = r

    if workers <= 1:
        for t in todo:
            done(_worker(t))
    elif todo:
        with cf.ProcessPoolExecutor(min(workers, len(todo)), mp_context=mp.get_context("spawn")) as ex:
            for fut in cf.as_completed([ex.submit(_worker, t) for t in todo]):
                done(fut.result())
    return out


# ------------------------------------------------------------------------------------------ paired analysis
def _profile(delta_metric: torch.Tensor, delta_terms: torch.Tensor, scales: dict) -> dict:
    """delta_metric: [n, T, len(PROFILE)], delta_terms: [n, T, len(TERMS)] (raw per hour) -> per-T means and half-widths."""
    out = {}
    m, hw = paired(delta_metric)
    for j, k in enumerate(PROFILE):
        out[k] = dict(mean=_r(m[:, j], 4), hw=_r(hw[:, j], 3))
    n, T, _ = delta_terms.shape
    rw = reward_delta(delta_terms.reshape(n * T, -1), scales, DEFAULT_OBJECTIVE).reshape(n, T)
    m, hw = paired(rw)
    out["reward"] = dict(mean=_r(m, 4), hw=_r(hw, 3))
    sc = torch.tensor([float(scales[k]) for k in TERMS], dtype=torch.float64)
    out["terms"] = _r(delta_terms.double().mean(0) / sc, 4)                          # [T][len(TERMS)] normalised: re-weightable
    return out


def analyse(var: dict, base: dict, scales: dict, unit_cost: float, sign_units: int, base_mean: dict) -> dict:
    """Paired comparison of one variant against the baseline on the same seeds.
    sign_units: -n when n units were removed, +n when added."""
    assert var["seeds"] == base["seeds"], "variant and baseline must be on the same seeds"
    de = var["episode"] - base["episode"]
    dt = var["terms"] - base["terms"]
    delta = {k: stat(de[:, j]) for j, k in enumerate(EPISODE_METRICS)}
    reward = {o: stat(reward_delta(dt, scales, o)) for o in OBJECTIVES}
    # patient-flow index of rl.objectives (wait, median stay, walk-out rate, boarding; each as a share of its baseline):
    # change in percent of the baseline index, positive = flow got worse. No money in it.
    jx = {k: EPISODE_METRICS.index(k) for k in FLOW_INDEX}
    flow = stat(100.0 * sum(w * de[:, jx[k]] / max(abs(base_mean[k]), FLOORS[k]) for k, w in FLOW_INDEX.items()))
    effects = []
    for k in EFFECTS:
        s = delta[k]
        den = max(abs(base_mean[k]), HARM_FLOORS.get(k, 1e-9))
        sig = bool(s["lo"] is not None and (s["lo"] > 0 or s["hi"] < 0))
        worse = (s["mean"] > 0) == LOWER_IS_BETTER[k]
        effects.append(dict(metric=k, label=METRIC_INFO[k][0], unit=METRIC_INFO[k][1], delta=s["mean"], lo=s["lo"], hi=s["hi"], baseline=_r(base_mean[k]),
                            pct=_r(100.0 * s["mean"] / den, 3), significant=sig, direction=("none" if s["mean"] == 0 else ("worse" if worse else "better"))))
    effects.sort(key=lambda e: (not e["significant"], -abs(e["pct"] or 0.0)))
    mg = delta["margin_per_day"]
    n = abs(sign_units)
    # value of the unit(s): for a removal it is what was lost (-delta), for an addition what was gained (+delta)
    s = -1.0 if sign_units < 0 else 1.0
    net = dict(mean=_r(s * mg["mean"]), lo=_r(min(s * mg["lo"], s * mg["hi"])), hi=_r(max(s * mg["lo"], s * mg["hi"])))
    money = dict(margin_per_day=mg, margin_per_year={k: _r(v * 365.0) for k, v in mg.items()}, unit_cost_per_day=_r(unit_cost),
                 net_value_per_day=net, net_value_per_year={k: _r(v * 365.0) for k, v in net.items()},
                 gross_value_per_day={k: _r(v + unit_cost) for k, v in net.items()},
                 net_value_per_dollar=({k: _r(v / unit_cost, 4) for k, v in net.items()} if unit_cost > 0 else None),
                 observed_operating_cost_change_per_day=delta["operating_cost_per_day"], n_units=n)
    # the same thing through the objective: change in reward x the cost scale = dollars of cost the objective would trade for it.
    # It is net of the unit's own cost (cost is a reward term) and counts waiting, walk-outs, safety, boarding and staff strain.
    rv = stat(s * reward_delta(dt, scales, DEFAULT_OBJECTIVE) * float(scales["cost"]) * 24.0)
    money["reward_value_per_day"] = rv
    money["reward_value_per_dollar"] = {k: _r(v / unit_cost, 4) for k, v in rv.items()} if unit_cost > 0 else None
    # ---- verdict (harm = a flow or safety metric getting worse; `tol` is the equivalence margin, share of baseline)
    harm = []
    for k, tol in HARM.items():
        d_, den = delta[k], max(abs(base_mean[k]), HARM_FLOORS.get(k, 1e-9))
        # worse = measurably worse AND not shown to be negligible; within_margin = shown to be at most negligibly worse
        harm.append(dict(metric=k, worse=bool(d_["lo"] > 0 and d_["hi"] > tol * den), within_margin=bool(d_["hi"] <= tol * den), better=bool(d_["hi"] < 0),
                         margin=_r(tol * den)))
    rw = reward[DEFAULT_OBJECTIVE]
    if sign_units < 0:
        if any(x["worse"] for x in harm):
            verdict = "needed" if rw["hi"] < 0 else ("trade-off" if rw["lo"] <= 0 else "costs more than it returns")
        elif all(x["within_margin"] for x in harm):
            # no more than negligible harm on any single metric; still not slack if the objective as a whole measurably falls
            verdict = "trade-off" if rw["hi"] < 0 else ("slack" if mg["lo"] > 0 else "no measurable effect")
        else:
            verdict = "inconclusive"
    else:
        verdict = "worth adding" if rw["lo"] > 0 else ("not worth adding" if rw["hi"] < 0 else "not shown either way")
    return dict(delta=delta, terms=dict(mean=_r(dt.mean(0) / torch.tensor([float(scales[k]) for k in TERMS], dtype=torch.float64))),
                terms_seeds=_r(dt, 5), reward=reward, flow_index_pct=flow, top_effects=effects, money=money, harm=harm, verdict=verdict,
                by_day=_profile(var["prof_day"] - base["prof_day"], var["term_day"] - base["term_day"], scales),
                by_hour=_profile(var["prof_hod"] - base["prof_hod"], var["term_hod"] - base["term_hod"], scales),
                verified={k: [base["counts"][k], var["counts"][k]] for k in base["counts"] if base["counts"][k] != var["counts"][k]},
                layout_edit=var.get("layout_edit") or None,
                max_walking_leg_change_m=_r(max(abs(a - b) for a, b in zip(var["legs"], base["legs"])), 3))


UTIL_KEY = {"provider": "providers", "nurse": "nurses", "triage_station": "triage", "ward_bed": "ward", "ct_scanner": "ct", "xray_room": "xray",
            "second_ct_hours": "ct", "fast_track": "bay_fast"}


def _util_for(unit: dict, util: dict) -> dict | None:
    cls = unit["resource_class"]
    key = UTIL_KEY.get(cls) or UTIL_KEY.get(cls.rsplit("_", 1)[0]) or (cls if cls.startswith("bay_") else None)
    u = util.get(key)
    if not u:
        return None
    hrs = unit.get("hours") or list(range(24))
    return dict(source=key, mean=_r(sum(u["by_hour"][h] for h in hrs) / len(hrs), 4), full_share=_r(sum(u["full_by_hour"][h] for h in hrs) / len(hrs), 4),
                by_hour=_r(u["by_hour"], 4), full_by_hour=_r(u["full_by_hour"], 4),
                definition=dict(providers="share of provider time with a patient, hours of this shift", nurses="nursing care demanded / nursing time on shift (capped at 1), hours of this shift",
                                triage="triage stations occupied at the end of the hour", ward="inpatient beds occupied",
                                ct="CT units scanning at the end of the hour / units up and staffed", xray="X-ray units in use at the end of the hour / units up"
                                ).get(key, "spaces of this class occupied at the end of the hour / spaces open") + "; full_share = share of hours every unit was in use")


def build_report(hospital: str, manager: str, scenarios: list[str], seeds: list[int], days: int, units: list[dict], results: dict) -> dict:
    h = hospital
    base0 = results[(scenarios[0], "base")]
    raw = base0["terms"].mean(0)
    raw[TERMS.index("revenue")] = raw[TERMS.index("cost")]                 # revenue shares the cost scale (margin), as in measure_scales
    scales = {k: max(abs(float(raw[i])), SCALE_FLOORS[k]) for i, k in enumerate(TERMS)}
    from .managers import load_manager
    try:
        from .common import fingerprints
        fp = fingerprints(h)
    except Exception:  # noqa: BLE001
        fp = dict(hospital_id=h, calibration_fingerprint=calibration_fingerprint(h))
    pol = load_manager(manager, "cpu", hospital=h)
    baseline, out_units, failed = {}, [], []
    for sc in scenarios:
        b = results[(sc, "base")]
        em, ehw = paired(b["episode"])
        baseline[sc] = dict(episode={k: dict(mean=_r(em[j]), sd=_r(b["episode"][:, j].std()) if len(seeds) > 1 else None) for j, k in enumerate(EPISODE_METRICS)},
                            counts=b["counts"], reward_per_hour={o: _r(float(reward_delta(b["terms"], scales, o).mean())) for o in OBJECTIVES},
                            by_hour={k: _r(b["prof_hod"].mean(0)[:, j], 4) for j, k in enumerate(PROFILE)},
                            utilisation={k: dict(mean=_r(v["mean"], 4), full_share=_r(v["full_share"], 4), by_hour=_r(v["by_hour"], 4)) for k, v in b["util"].items()},
                            invalid_actions=b["invalid"])
    for u in units:
        o = {k: v for k, v in u.items() if k not in ("minus", "plus", "baseline_counts")}
        o["unit_cost_per_day"] = _r(u["unit_cost_per_day"])
        o["scenarios"], o["utilisation"] = {}, {}
        for sc in scenarios:
            b = results[(sc, "base")]
            bm = {k: float(b["episode"][:, j].mean()) for j, k in enumerate(EPISODE_METRICS)}
            row = {}
            for side, sg in (("minus", -1), ("plus", 1)):
                v = u.get(side)
                if v is None:
                    row[f"{side}_one"] = None
                    continue
                r = results.get((sc, f"{u['id']}__{side}"))
                if r is None or "error" in r:
                    row[f"{side}_one"] = None
                    failed.append(dict(unit=u["id"], side=side, scenario=sc, error=(r or {}).get("error", "not run")))
                    continue
                a = analyse(r, b, scales, u["unit_cost_per_day"], sg * v["n_units"] if u.get("block") else sg, bm)
                a["description"] = v["desc"]
                row[f"{side}_one"] = a
            o["scenarios"][sc] = row
            o["utilisation"][sc] = _util_for(u, b["util"])
        out_units.append(o)
    rep = dict(synthetic=True, simulated=True, generated=now_iso(), **dict(fp, hospital_id=h),
               disclaimer="Every number here is SIMULATED: a model fitted to the hospital's published aggregates, not its operational data. "
                          "Differences are paired on the same simulated patients; intervals are 95% Student-t over seeds.",
               manager=dict(id=manager, label=pol.label, kind=pol.kind),
               protocol=dict(seeds=[int(seeds[0]), int(seeds[-1])], n_seeds=len(seeds), days=int(days), scenarios=list(scenarios), paired=True,
                             ci="95% Student-t interval of the mean paired difference over seeds", calibration="point calibration (ensemble member 0)",
                             minus_one="(without the unit) - (baseline)", plus_one="(with one more) - (baseline)"),
               reward=dict(terms=TERMS, scales={k: _r(v, 6) for k, v in scales.items()}, objectives={k: weights_dict(k) for k in OBJECTIVES},
                           cost_scale_per_hour=_r(scales["cost"], 6),
                           value_definition="reward_value_per_day = change in reward per hour x cost scale x 24: the dollars of daily cost the objective "
                                            "would trade for the unit (its own cost already netted off). An exchange rate set by the chosen weights, not cash.",
                           default_objective=DEFAULT_OBJECTIVE,
                           definition="reward per hour = -sum_k w_k * term_k / scale_k; scale_k = this run's baseline mean per hour on "
                                      f"{scenarios[0]} (floored; revenue uses the cost scale). Re-score with any weights from `terms_seeds` (raw per-hour "
                                      "term differences per seed) without re-simulating.",
                           scale_source=f"baseline of this run, {scenarios[0]}, {len(seeds)} seeds x {days} days"),
               metrics={k: dict(label=METRIC_INFO[k][0], unit=METRIC_INFO[k][1], lower_is_better=bool(LOWER_IS_BETTER[k])) for k in EPISODE_METRICS},
               headline_metrics=HEADLINE, profile_metrics={k: dict(label=v[0], unit=v[1]) for k, v in PROFILE_INFO.items()},
               harm_margins=dict(HARM), flow_index=dict(weights=dict(FLOW_INDEX), definition="weighted sum of (metric / its baseline) over these metrics; "
                                                        "`flow_index_pct` is the change in percent of the baseline index, positive = worse flow"),
               baseline=baseline, units=out_units, failed=failed, location=location_table(h, scenarios[0]),
               identifiability=[
                   "Providers of a role are interchangeable in the model: a named provider has the value of one provider on that shift. The model has no "
                   "individual skill, speed or specialty, so no per-person differences are reported.",
                   "A 'provider' is costed at the blended wage of the attending / resident / APP mix; the model does not move patients differently by role "
                   "(except the fast-track provider's productivity).",
                   "Bays of a class differ only by position, and the simulator walks patients between zone centroids, so every bay of a class has the same "
                   "simulated value. `location` gives the per-bay distances it ignores.",
                   "A ward bed is one bed of the pooled inpatient capacity the ED admits to (ward, step-down and ICU rooms pooled); beds are not distinguished.",
                   "Removing a ward bed also changes the starting census (the pool starts at a fixed occupancy share), so its effect includes that.",
                   "Staff the model holds constant (technicians, registration, pharmacist, transport, EVS, charge nurse) cannot be removed in it and have no "
                   "marginal value here.",
                   "Scanner purchase price and bay construction cost are capital, outside the daily figures.",
                   "Nurses constrain the model only through a cap on staffed spaces per nurse and through care minutes; the nurse and provider head-counts "
                   "are calibration parameters fitted to public aggregates, not the hospital's roster. 'Slack' and 'needed' describe that fitted model.",
                   "The dollar 'value to the objective' is the reward change at the objective's own exchange rate between cost and waiting, walk-outs, "
                   "safety and boarding. It moves with the weights; it is not cash. Margin alone is the cash figure, and in this cost model slower care can "
                   "raise it (more admissions, each booked as revenue)."])
    rep["ranking"] = {sc: ranking(rep, sc) for sc in scenarios}
    rep["findings"] = {sc: findings(rep, sc) for sc in scenarios}
    return rep


def rescore(rep: dict, weights) -> dict:
    """Reward differences of every unit under another weight vector, from the stored per-seed term differences
    (no simulation). -> {unit id: {scenario: {minus_one|plus_one: {mean, lo, hi}}}}"""
    scales, out = rep["reward"]["scales"], {}
    for u in rep["units"]:
        out[u["id"]] = {}
        for sc, row in u["scenarios"].items():
            out[u["id"]][sc] = {side: (stat(reward_delta(torch.tensor(a["terms_seeds"], dtype=torch.float64), scales, weights)) if a else None)
                                for side, a in row.items()}
    return out


def ranking(rep: dict, sc: str) -> list[dict]:
    """Units ordered by net value per dollar of the EXISTING unit (what removing it loses, per dollar it costs), where value
    is the objective's (`reward_value_per_day`); `rank_by_margin` is the order on margin alone."""
    rows = []
    for u in rep["units"]:
        r = u["scenarios"][sc]
        mi, pl = r.get("minus_one"), r.get("plus_one")
        row = dict(unit=u["id"], label=u["label"], resource_class=u["resource_class"], kind=u["kind"], unit_cost_per_day=u["unit_cost_per_day"],
                   n_units=(mi or pl or {}).get("money", {}).get("n_units", 1))
        for name, a in (("existing", mi), ("next", pl)):
            if a is None:
                row[name] = None
                continue
            row[name] = dict(reward_value_per_day=a["money"]["reward_value_per_day"], reward_value_per_dollar=a["money"]["reward_value_per_dollar"],
                             net_value_per_day=a["money"]["net_value_per_day"], net_value_per_dollar=a["money"]["net_value_per_dollar"],
                             reward=a["reward"][DEFAULT_OBJECTIVE], flow_index_pct=a["flow_index_pct"], verdict=a["verdict"],
                             top_effects=[dict(metric=e["metric"], label=e["label"], unit=e["unit"], delta=e["delta"], lo=e["lo"], hi=e["hi"], pct=e["pct"],
                                               significant=e["significant"], direction=e["direction"]) for e in a["top_effects"][:3]])
        rows.append(row)
    key = lambda r, f: ((r["existing"] or r["next"])[f] or {}).get("mean") or 0.0      # noqa: E731
    rows.sort(key=lambda r: -key(r, "net_value_per_dollar"))
    for i, r in enumerate(rows):
        r["rank_by_margin"] = i + 1
    rows.sort(key=lambda r: -key(r, "reward_value_per_dollar"))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def findings(rep: dict, sc: str) -> dict:
    """The binding constraint (what to add first) and the slack (what could go), from the intervals only."""
    add, slack, needed, unclear = [], [], [], []
    for u in rep["units"]:
        r = u["scenarios"][sc]
        pl, mi = r.get("plus_one"), r.get("minus_one")
        if pl is not None and pl["verdict"] == "worth adding":
            add.append(dict(unit=u["id"], label=u["label"], reward=pl["reward"][DEFAULT_OBJECTIVE], net_value_per_day=pl["money"]["net_value_per_day"],
                            reward_value_per_day=pl["money"]["reward_value_per_day"],
                            n_units=pl["money"]["n_units"]))
        if mi is not None:
            e = dict(unit=u["id"], label=u["label"], reward=mi["reward"][DEFAULT_OBJECTIVE], margin_per_day=mi["delta"]["margin_per_day"], verdict=mi["verdict"])
            (slack if mi["verdict"] == "slack" else needed if mi["verdict"] == "needed" else unclear).append(e)
    add.sort(key=lambda x: -x["reward"]["mean"] / max(1, x["n_units"]))
    needed.sort(key=lambda x: x["reward"]["mean"])
    slack.sort(key=lambda x: -x["margin_per_day"]["mean"])
    # where the money figure and the flow figure disagree: removing the unit makes flow measurably worse, yet revenue RISES
    perverse = []
    for u in rep["units"]:
        mi = u["scenarios"][sc].get("minus_one")
        if mi and mi["delta"]["revenue_per_day"]["lo"] > 0 and mi["flow_index_pct"]["lo"] > 0:
            perverse.append(dict(unit=u["id"], label=u["label"], revenue_per_day=mi["delta"]["revenue_per_day"], admissions_per_day=mi["delta"]["admissions_per_day"],
                                 flow_index_pct=mi["flow_index_pct"]))
    # the money-free view: which single removal hurts patient flow most, which single addition helps it most
    flow_rm = sorted(((u["label"], u["scenarios"][sc]["minus_one"]["flow_index_pct"]) for u in rep["units"] if u["scenarios"][sc].get("minus_one")),
                     key=lambda x: -x[1]["mean"])
    flow_add = sorted(((u["label"], u["scenarios"][sc]["plus_one"]["flow_index_pct"]) for u in rep["units"] if u["scenarios"][sc].get("plus_one")),
                      key=lambda x: x[1]["mean"])
    return dict(binding=(add[0] if add else None), worth_adding=add, slack=slack, needed=needed, not_shown_either_way=unclear,
                revenue_rises_when_removed=perverse,
                flow_most_hurt_by_removing=[dict(label=a, flow_index_pct=b) for a, b in flow_rm if b["lo"] > 0][:6],
                flow_most_helped_by_adding=[dict(label=a, flow_index_pct=b) for a, b in flow_add if b["hi"] < 0][:6],
                rule="worth adding: the balanced reward rises with a 95% interval above zero. needed: removing it makes a flow or safety metric worse "
                     "(interval above zero and not inside the equivalence margin) and lowers the balanced reward (interval below zero). slack: removing it "
                     "saves money (interval above zero), every flow and safety metric's interval stays inside its equivalence margin, i.e. it is shown "
                     "to get at most negligibly worse (margin: 2% of baseline for waits, stay, walk-outs and boarding; 5% for rare safety events), "
                     "and the balanced reward does not measurably fall. "
                     "Anything else is not shown either way.")


# ------------------------------------------------------------------------------------------ markdown
def _ci(s, fmt="{:,.0f}", unit=""):
    if s is None or s.get("mean") is None:
        return "n/a"
    return f"{fmt.format(s['mean'])}{unit} [{fmt.format(s['lo'])}, {fmt.format(s['hi'])}]"


def _eff(e):
    f = "{:+,.2f}" if abs(e["delta"]) < 10 else "{:+,.1f}"
    return f"{e['label']} {f.format(e['delta'])} {e['unit']}" + ("" if e["significant"] else " (n.s.)")


def write_markdown(rep: dict, path: Path):
    P, L = rep["protocol"], []
    w = L.append
    w(f"# Marginal value of every resource: {rep['hospital_id']} (SIMULATED)")
    w("")
    w(f"> {rep['disclaimer']}")
    w("")
    w(f"Generated {rep['generated']} by `rl/attribution.py`. Policy: **{rep['manager']['label']}** (`{rep['manager']['id']}`). "
      f"{P['n_seeds']} held-out seeds ({P['seeds'][0]}..{P['seeds'][1]}) x {P['days']} simulated days per scenario, {P['calibration']}. "
      "Every row compares the twin with and without ONE unit on the same seeds (same patients), so the differences are paired; "
      "brackets are 95% intervals. Calibration fingerprint "
      f"`{rep.get('calibration_fingerprint')}`.")
    w("")
    w(f"**How to read it.** *Value to the objective* is the unit's net effect on the `{rep['reward']['default_objective']}` reward (cost, revenue, waiting, "
      "walk-outs, safety, boarding, staff strain; each term divided by its baseline level), expressed in dollars of daily cost at the objective's own exchange "
      f"rate (change in reward per hour x ${rep['reward']['cost_scale_per_hour']:,.0f}/h x 24). It is already net of what the unit costs, and it is an exchange rate "
      "set by the chosen weights, not cash; the per-seed term differences in the JSON re-score it under any other weights. *Per $* divides it by what the unit "
      "costs per day, and the table is ranked on that. *Margin alone* = the cash margin the hospital would lose per day without the unit (its cost netted off); "
      "it counts no harm. *Next unit* = the same two numbers for adding one more. *Patient-flow index* is the money-free view: door-to-provider "
      "wait, median ED stay, walk-out rate and boarding, each as a share of its baseline (weights 0.3 / 0.3 / 0.2 / 0.2); +1% means flow got 1% worse.")
    w("")
    for sc in P["scenarios"]:
        b = rep["baseline"][sc]["episode"]
        w(f"## {sc} (simulated)")
        w("")
        w(f"Baseline: mean door-to-provider wait {b['wait_mean_min']['mean']:.1f} min, p95 {b['wait_p95_min']['mean']:.0f} min, median ED stay "
          f"{b['ed_los_median_min']['mean']:.0f} min, {b['lwbs_per_day']['mean']:.1f} walk-outs/day, boarding {b['boarding_hours_per_day']['mean']:.0f} patient-hours/day, "
          f"labor ${b['labor_cost_per_day']['mean']:,.0f}/day, margin ${b['margin_per_day']['mean']:,.0f}/day.")
        w("")
        w("### Ranked by net value per dollar of the existing unit (simulated)")
        w("")
        w("| # | Resource | Costs $/day | Value to the objective, $-equivalent/day [95% CI] | per $ | Margin alone, net $/day [95% CI] | Patient-flow index if removed, % [95% CI] (+ = worse) | Removing it: biggest effects | Verdict if removed | Next unit: value to the objective, $-eq/day [95% CI] | Next unit: margin alone $/day | Flow index if added, % | Verdict if added |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rep["ranking"][sc]:
            ex, nx = r["existing"], r["next"]
            w("| {} | {} | {:,.0f} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                r["rank"], r["label"], r["unit_cost_per_day"],
                _ci(ex["reward_value_per_day"], "{:+,.0f}") if ex else "n/a (not in use at baseline)",
                "{:+.1f}".format(ex["reward_value_per_dollar"]["mean"]) if ex and ex["reward_value_per_dollar"] else "",
                _ci(ex["net_value_per_day"], "{:+,.0f}") if ex else "",
                _ci(ex["flow_index_pct"], "{:+.2f}") if ex else "",
                ("; ".join(_eff(e) for e in ex["top_effects"] if e["significant"]) or "none outside the intervals") if ex else "",
                ex["verdict"] if ex else "",
                _ci(nx["reward_value_per_day"], "{:+,.0f}") if nx else "n/a", _ci(nx["net_value_per_day"], "{:+,.0f}") if nx else "",
                _ci(nx["flow_index_pct"], "{:+.2f}") if nx else "", nx["verdict"] if nx else ""))
        w("")
        f = rep["findings"][sc]
        w("### Binding and slack (simulated)")
        w("")
        if f["binding"]:
            x = f["binding"]
            w(f"- **Add first: {x['label']}.** Value to the objective {_ci(x['reward_value_per_day'], '{:+,.0f}')} $-equivalent/day "
              f"(reward {_ci(x['reward'], '{:+.4f}')} per hour); margin alone {_ci(x['net_value_per_day'], '{:+,.0f}')} $/day.")
            if len(f["worth_adding"]) > 1:
                w("- Also worth adding (reward interval above zero): " + "; ".join(f"{x['label']} ({_ci(x['reward'], '{:+.4f}')})" for x in f["worth_adding"][1:]) + ".")
        else:
            w("- **No single added unit raises the balanced reward with a 95% interval above zero.** Nothing is flagged as the binding constraint.")
        if f["needed"]:
            w("- Needed (removing one measurably hurts flow or safety and lowers the reward): " +
              "; ".join(f"{x['label']} ({_ci(x['reward'], '{:+.4f}')})" for x in f["needed"]) + ".")
        if f["slack"]:
            w("- Slack (removing one saves money and no flow or safety metric leaves its equivalence margin): " +
              "; ".join(f"{x['label']} (margin {_ci(x['margin_per_day'], '{:+,.0f}')} $/day)" for x in f["slack"]) + ".")
        else:
            w("- Slack: none can be called slack at this sample size.")
        if f["not_shown_either_way"]:
            w("- Not shown either way: " + "; ".join(f"{x['label']} ({x['verdict']})" for x in f["not_shown_either_way"]) + ".")
        if f["flow_most_helped_by_adding"]:
            w("- Patient flow only (no money): the single additions that improve the flow index most are " +
              "; ".join(f"{x['label']} ({_ci(x['flow_index_pct'], '{:+.2f}')}%)" for x in f["flow_most_helped_by_adding"]) + ".")
        if f["flow_most_hurt_by_removing"]:
            w("- Patient flow only: the single removals that hurt it most are " +
              "; ".join(f"{x['label']} ({_ci(x['flow_index_pct'], '{:+.2f}')}%)" for x in f["flow_most_hurt_by_removing"]) + ".")
        if f["revenue_rises_when_removed"]:
            w("- **Read the money columns with care.** For " + "; ".join(
                f"{x['label']} (revenue {_ci(x['revenue_per_day'], '{:+,.0f}')} $/day, admissions {_ci(x['admissions_per_day'], '{:+.3f}')}/day)"
                for x in f["revenue_rises_when_removed"]) +
              " the model's revenue goes UP when the unit is removed although patient flow gets measurably worse: with slower care more patients end up admitted, "
              "and the model books inpatient revenue per admission with no penalty for avoidable admissions. That is a property of the cost model, not evidence "
              "that the unit loses money; the reward and flow columns are the ones to act on for these rows.")
        w("")
        w(f"Rule: {f['rule']}")
        w("")
        w("### Effect of removing one unit on each headline metric (simulated; paired difference, 95% CI)")
        w("")
        hm = rep["headline_metrics"]
        w("| Resource | " + " | ".join(f"{METRIC_INFO[k][0]} ({METRIC_INFO[k][1]})" for k in hm) + " |")
        w("|---|" + "---|" * len(hm))
        for side, title in (("minus_one", None), ("plus_one", "### Effect of adding one unit (simulated; paired difference, 95% CI)")):
            if title:
                w("")
                w(title)
                w("")
                w("| Resource | " + " | ".join(f"{METRIC_INFO[k][0]} ({METRIC_INFO[k][1]})" for k in hm) + " |")
                w("|---|" + "---|" * len(hm))
            for u in rep["units"]:
                a = u["scenarios"][sc].get(side)
                if a is None:
                    continue
                cells = []
                for k in hm:
                    s = a["delta"][k]
                    fmt = "{:+,.0f}" if METRIC_INFO[k][1].startswith("$") else ("{:+.3f}" if "Deaths" in METRIC_INFO[k][0] or "Adverse" in METRIC_INFO[k][0] else "{:+.2f}")
                    cells.append(_ci(s, fmt))
                w(f"| {u['label']} | " + " | ".join(cells) + " |")
        w("")
        w("### When each unit matters (simulated)")
        w("")
        w("Value of the unit to the objective ($-equivalent per hour, mean over seeds; for rows marked *adding*, the value of adding it) by block of the day, "
          "the same per day over the three thirds of the month, and how busy the resource is at baseline. Hour-by-hour and day-by-day series with intervals, "
          "for margin and every other profile metric too, are in the JSON (`by_hour`, `by_day`).")
        w("")
        w("| Resource | 07-15 $-eq/h | 15-23 | 23-07 | Days 1-10 $-eq/day | Days 11-20 | Days 21-30 | Utilisation | Share of hours every unit is in use |")
        w("|---|---|---|---|---|---|---|---|---|")
        cs = float(rep["reward"]["cost_scale_per_hour"])
        for u in rep["units"]:
            a = u["scenarios"][sc].get("minus_one") or u["scenarios"][sc].get("plus_one")
            if a is None:
                continue
            ex = u["scenarios"][sc].get("minus_one") is not None
            sg = -1.0 if ex else 1.0
            bh, bd = [sg * x * cs for x in a["by_hour"]["reward"]["mean"]], [sg * x * cs * 24.0 for x in a["by_day"]["reward"]["mean"]]
            blk = lambda hs: sum(bh[h] for h in hs) / len(hs)                               # noqa: E731
            n = len(bd)
            third = lambda i: sum(bd[i * n // 3:(i + 1) * n // 3]) / max(1, len(bd[i * n // 3:(i + 1) * n // 3]))   # noqa: E731
            ut = u["utilisation"].get(sc)
            w(f"| {u['label']}{'' if ex else ' (adding)'} | {blk(range(7, 15)):+,.0f} | {blk(range(15, 23)):+,.0f} | {blk([23, 0, 1, 2, 3, 4, 5, 6]):+,.0f} | "
              f"{third(0):+,.0f} | {third(1):+,.0f} | {third(2):+,.0f} | "
              f"{(format(ut['mean'], '.0%') if ut else 'n/a')} | {(format(ut['full_share'], '.0%') if ut else 'n/a')} |")
        w("")
    w("## What cannot be told apart (identifiability)")
    w("")
    for s in rep["identifiability"]:
        w(f"- {s}")
    loc = rep["location"]
    w("")
    w("Per-bay position, geometry only (not simulated): seconds one walk in plus one leg to CT would gain or lose against the class centroid.")
    w("")
    w("| Bay class | Bays | Class centroid to waiting room (m) | to CT (m) | Nearest bay (s) | Farthest bay (s) |")
    w("|---|---|---|---|---|---|")
    for k, v in loc["by_class"].items():
        w(f"| {BAY_LABEL[k]} | {v['n']} | {v['class_to_waiting_m']} | {v['class_to_ct_m']} | {v['walk_seconds_vs_class_min']:+.0f} | {v['walk_seconds_vs_class_max']:+.0f} |")
    w("")
    w("## Manipulations (each asserted against the counts the simulator used)")
    w("")
    w("| Resource | Removed | Added | Largest change in a zone walking distance (m) |")
    w("|---|---|---|---|")
    sc = P["scenarios"][0]
    for u in rep["units"]:
        mi, pl = u["scenarios"][sc].get("minus_one"), u["scenarios"][sc].get("plus_one")
        leg = max([a["max_walking_leg_change_m"] or 0.0 for a in (mi, pl) if a] or [0.0])
        w(f"| {u['label']} | {mi['description'] if mi else 'n/a'} | {pl['description'] if pl else 'n/a'} | {leg:.2f} |")
    w("")
    if rep["failed"]:
        w("Variants that did not run: " + "; ".join(f"{x['unit']} {x['side']} ({x['scenario']}): {x['error']}" for x in rep["failed"]))
        w("")
    w("Reward weights and scales, per-seed term differences (for re-scoring under any weights), per-day and per-hour profiles and utilisation by hour are in "
      "`attribution.json`. Served at `GET /api/attribution/{hospital_id}`.")
    w("")
    write_text(path, "\n".join(L))


# ------------------------------------------------------------------------------------------ driver
def make_tasks(hospital, manager, scenarios, seeds, days, units) -> list[dict]:
    tasks = []
    for sc in scenarios:
        base = dict(hospital=hospital, scenario=sc, seeds=list(seeds), days=days, manager=manager)
        tasks.append(dict(base, key="base", overrides={}, expect={}, base_counts=units[0]["baseline_counts"] if units else None))
        for u in units:
            for side in ("minus", "plus"):
                v = u.get(side)
                if v is not None:
                    tasks.append(dict(base, key=f"{u['id']}__{side}", overrides=v["overrides"], expect=v["expect"], base_counts=u["baseline_counts"]))
    return tasks


def run(hospital=None, manager="fixed", scenarios=("normal_week", "flu_surge"), n_seeds=32, days=30, workers=0, only=None, work_dir=None, out_dir=None,
        seed0=SEED0, log=print) -> dict:
    h = hospital_id(hospital)
    scenarios = list(scenarios)
    seeds = [int(seed0) + i for i in range(int(n_seeds))]
    units = build_units(h, scenarios[0], with_all_shift=(manager != "fixed"))
    if int(n_seeds) < 2:
        raise ValueError("paired intervals need at least 2 seeds")
    if manager != "fixed":
        # a policy chooses its own staffing levels and hourly settings: only capacity edits and whole-ladder shifts stay well defined
        ok = lambda v: v is None or set(v["overrides"]) <= {"layout_edit"}             # noqa: E731
        units = [u for u in units if (u["id"].endswith("_all_shifts") or (ok(u.get("minus")) and ok(u.get("plus"))))]
    if only:
        units = [u for u in units if u["id"] in set(only)]
    tasks = make_tasks(h, manager, scenarios, seeds, days, units)
    log(f"attribution {h} manager={manager}: {len(units)} units, {len(tasks)} runs of {len(seeds)} seeds x {days} days, {workers or 1} worker(s)")
    t0 = time.time()
    res = run_tasks(tasks, workers, Path(work_dir) if work_dir else None, log)
    missing = [k for k in ((sc, "base") for sc in scenarios) if k not in res or "error" in res[k]]
    if missing:
        raise RuntimeError(f"baseline runs failed: {[res.get(k, {}).get('error') for k in missing]}")
    rep = build_report(h, manager, scenarios, seeds, days, units, res)
    rep["compute_seconds"] = round(time.time() - t0, 1)
    out = Path(out_dir) if out_dir else paths(h).home
    stem = "attribution" if manager == "fixed" else f"attribution__{manager}"
    write_json(out / f"{stem}.json", rep, separators=(",", ":"))
    write_markdown(rep, out / f"{stem.upper() if manager == 'fixed' else stem}.md")
    log(f"wrote {out / (stem + '.json')} ({(out / (stem + '.json')).stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s; {len(rep['failed'])} variant(s) failed")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hospital", default=None)
    ap.add_argument("--manager", default="fixed", help="fixed (the calibrated baseline policy) or a policy id; under a policy only capacity units are run")
    ap.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    ap.add_argument("--seeds", type=int, default=32)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, min(24, (os.cpu_count() or 2) - 1)), help="single-thread processes")
    ap.add_argument("--units", nargs="*", default=None, help="only these unit ids")
    ap.add_argument("--work-dir", default=None, help="checkpoint directory (finished runs are reused)")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--seed0", type=int, default=SEED0)
    a = ap.parse_args()
    assert a.seed0 >= SEED_EVAL, "attribution runs on held-out seeds only"
    h = hospital_id(a.hospital)
    work = a.work_dir or str(ROOT / "runs" / "attribution" / h / f"{a.manager}_s{a.seeds}_d{a.days}")
    run(h, a.manager, a.scenarios, a.seeds, a.days, a.workers, a.units, work, a.out_dir, a.seed0)


if __name__ == "__main__":
    main()
