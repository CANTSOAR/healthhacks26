"""Scenario loading: catalog/*.yaml + sim/scenarios/<id>.yaml + layout -> ScenarioConfig.

Every simulator parameter is read here by key from the catalog (or, if the key is missing there,
from sim/scenarios/_defaults.yaml:catalog_fallback, and recorded). The engine only sees the
resolved numbers in `ScenarioConfig.P`.
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path

import yaml

from .layoutmodel import BAY_CLASSES, LayoutModel

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
CONTRACTS = ROOT / "contracts"
SCENARIOS = Path(__file__).resolve().parent / "scenarios"
CAT_FILES = ["patient", "staff", "space", "equipment", "event"]


_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_YAML_CACHE: dict = {}


def _yaml(path: Path):
    """Parsed YAML, cached by (path, mtime); callers get their own deep copy."""
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns)
    hit = _YAML_CACHE.get(str(path))
    if hit is None or hit[0] != key:
        with open(path) as f:
            hit = (key, yaml.load(f, Loader=_LOADER))
        _YAML_CACHE[str(path)] = hit
    return copy.deepcopy(hit[1])


class ScenarioConfig:
    def __init__(self):
        self.id = ""
        self.label = ""
        self.description = ""
        self.hospital_id = ""
        self.days_default = 7
        self.cat: dict = {}
        self.P: dict = {}
        self.engine: dict = {}
        self.flags: dict = {}
        self.events: list = []
        self.enums: dict = {}
        self.metric_defs: dict = {}
        self.summary_defs: dict = {}
        self.heads: list = []
        self.layout: LayoutModel | None = None
        self.layout_source = ""
        self.fallback_keys: list[str] = []
        self.overrides: dict = {}

    # ---- catalog access ------------------------------------------------------------------
    def attr(self, file: str, variant: str, key: str, required: bool = True):
        d = self.cat.get(file) or {}
        if file == "hospital":
            node = d.get(key)
        elif variant in (None, "shared"):
            node = (d.get("shared") or {}).get(key)
        else:
            node = (((d.get("variants") or {}).get(variant) or {}).get("attributes") or {}).get(key)
        if node is None or node.get("value") is None and "dist" not in node:
            fb = self._fallback.get(file) or {}
            fnode = fb.get(key) if file == "hospital" else (fb.get(variant or "shared") or {}).get(key)
            if fnode is not None:
                tag = f"{file}.{variant or 'shared'}.{key}"
                if tag not in self.fallback_keys:
                    self.fallback_keys.append(tag)
                return fnode
            if node is None and required:
                raise KeyError(f"catalog attribute missing: {file}.{variant or 'shared'}.{key}")
        return node

    def val(self, file, variant, key, default=None):
        a = self.attr(file, variant, key, required=default is None)
        if a is None or a.get("value") is None:
            return default
        return a["value"]

    def dist(self, file, variant, key):
        """(kind, mean, cv) with kind in fixed|lognormal|exponential."""
        a = self.attr(file, variant, key)
        d = a.get("dist") or {}
        kind = d.get("kind", "fixed")
        mean = d.get("mean", a.get("value"))
        if isinstance(mean, (list, dict)):
            mean = a.get("value")
        cv = d.get("cv", 1.0 if kind == "exponential" else 0.0)
        if kind in ("gamma", "normal", "uniform"):
            kind = "lognormal" if cv else "fixed"      # approximated by a lognormal with the same mean and cv
        if kind not in ("lognormal", "exponential"):
            kind = "fixed"
        return kind, mean, float(cv or 0.0)


def list_scenarios() -> list[dict]:
    out = []
    for f in sorted(SCENARIOS.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        d = _yaml(f)
        out.append(dict(id=d.get("id", f.stem), label=d.get("label", f.stem), description=d.get("description", ""),
                        hospital_id=d.get("hospital_id", "rwjuh_nb"), days_default=int(d.get("days_default", 7))))
    order = ["normal_week", "flu_surge", "nursing_absences", "imaging_outage", "discharge_delays", "mmc_validation"]
    out.sort(key=lambda s: (order.index(s["id"]) if s["id"] in order else 99, s["id"]))
    return out


def _set_path(cat: dict, path: str, value):
    parts = path.split(".")
    file = parts[0]
    if file == "hospital":
        node = cat["hospital"].setdefault(parts[1], dict(unit="", source="assumed", citation="scenario override"))
    else:
        variant, key = parts[1], parts[2]
        if variant == "shared":
            holder = cat[file].setdefault("shared", {})
        else:
            holder = cat[file].setdefault("variants", {}).setdefault(variant, dict(label=variant, attributes={}))["attributes"]
        node = holder.setdefault(key, dict(unit="", source="assumed", citation="scenario override"))
    if isinstance(value, dict) and ("value" in value or "dist" in value):
        node.update(value)
    else:
        node["value"] = value
        if isinstance(node.get("dist"), dict) and "mean" in node["dist"] and isinstance(value, (int, float)):
            node["dist"]["mean"] = value


def apply_layout_edit(layout: dict, edit: dict, bay_types: dict | None = None) -> list[dict]:
    """Counterfactual capacity edit of a layout dict, IN PLACE, before the LayoutModel is built.

        edit = {"remove": {"<type>": n, ...}, "add": {"<type>": n, ...}}

    `<type>` is a layout room type (`treatment_bay`, `resus_bay`, `fast_track`, `peds_ed`, `ward_unit`, `triage`, ...)
    or a scanner type present in the layout's equipment list (`ct`, `xray`). Rooms: n units of CAPACITY are taken
    from / added to the rooms of that type nearest the type's centroid (one unit per room, round robin), so the
    walking distances between zone centroids barely move; an ED bay room left with capacity 0 stays in the file as an
    empty room, any other room left with capacity 0 is marked not physical (closed). Hallway stretcher spaces are never touched (they belong to the `overflow_bays` action). Scanners: units are
    removed from / appended to the equipment list and the scanner rooms stay where they are.
    Returns the list of changes made; raises ValueError when there is nothing left to remove."""
    rooms, equipment = layout["rooms"], layout.setdefault("equipment", [])
    eq_types = {e["type"] for e in equipment}
    multi_ok = set(bay_types or {})          # ED bay rooms hold one patient space per unit of capacity
    done = []
    for sign, part in ((-1, "remove"), (1, "add")):
        for typ, n in ((edit or {}).get(part) or {}).items():
            n = int(n)
            if n <= 0:
                continue
            if typ in eq_types and typ in ("ct", "xray"):
                for k in range(n):
                    units = [e for e in equipment if e["type"] == typ]
                    if sign < 0:
                        if not units:
                            raise ValueError(f"layout_edit: no {typ} unit left to remove")
                        equipment.remove(units[-1])
                        done.append(dict(op="remove", type=typ, id=units[-1]["id"]))
                    else:
                        src = units[-1]
                        new = dict(src, id=f"{src['id']}-plus{k + 1}", label=f"{src.get('label', typ)} (added {k + 1})",
                                   provenance="inferred", source="counterfactual layout_edit")
                        equipment.append(new)
                        done.append(dict(op="add", type=typ, id=new["id"]))
                continue
            idx = [i for i, r in enumerate(rooms) if r["type"] == typ and r.get("physical", True) is not False
                   and "hallway" not in (r.get("catalog_ref") or "")]
            if not idx:
                raise ValueError(f"layout_edit: no physical room of type '{typ}' in the layout")
            cx = sum(rooms[i]["x"] for i in idx) / len(idx)
            cz = sum(rooms[i]["z"] for i in idx) / len(idx)
            order = sorted(idx, key=lambda i: (abs(rooms[i]["x"] - cx) + abs(rooms[i]["z"] - cz), i))
            left, k = n, 0
            while left > 0:
                if sign < 0:
                    order = [i for i in order if int(rooms[i].get("capacity") or 0) > 0]
                    if not order:
                        raise ValueError(f"layout_edit: no '{typ}' capacity left to remove")
                r = rooms[order[k % len(order)]]
                r["capacity"] = int(r.get("capacity") or 0) + sign
                if sign < 0 and r["capacity"] <= 0 and typ not in multi_ok:
                    r["physical"] = False                      # a non-bay room with nothing left in it is closed
                done.append(dict(op=part, type=typ, id=r["id"], capacity=r["capacity"]))
                left, k = left - 1, k + 1
    return done


def load_scenario(scenario_id: str = "normal_week", overrides: dict | None = None) -> ScenarioConfig:
    overrides = dict(overrides or {})
    path = SCENARIOS / f"{scenario_id}.yaml"
    if not path.exists():
        raise KeyError(f"unknown scenario '{scenario_id}'; have {[s['id'] for s in list_scenarios()]}")
    sd = _yaml(path) or {}
    defaults = _yaml(SCENARIOS / "_defaults.yaml")
    c = ScenarioConfig()
    c._fallback = defaults.get("catalog_fallback") or {}
    c.id = sd.get("id", scenario_id)
    c.label = sd.get("label", scenario_id)
    c.description = sd.get("description", "")
    # hospital: explicit override > HOSPITAL_ID environment variable > the scenario file's default
    c.hospital_id = overrides.pop("hospital_id", None) or os.environ.get("HOSPITAL_ID") or sd.get("hospital_id", "rwjuh_nb")
    c.days_default = int(overrides.pop("days", sd.get("days_default", 7)))
    base_act_override = dict(overrides.pop("baseline_actions", None) or {})
    no_calibration = bool(overrides.pop("no_calibration", False))
    layout_edit = overrides.pop("layout_edit", None)
    c.engine = copy.deepcopy(defaults["engine"])
    for k, v in (sd.get("engine") or {}).items():
        if k == "flags":
            c.engine["flags"].update(v)
        else:
            c.engine[k] = v
    c.flags = c.engine["flags"]
    c.events = copy.deepcopy(sd.get("events") or [])
    c.overrides = dict(overrides, **({"layout_edit": layout_edit} if layout_edit else {}))

    # ---- catalog
    for f in CAT_FILES:
        c.cat[f] = _yaml(CATALOG / f"{f}.yaml") or {}
    hfile = CATALOG / "hospitals" / f"{c.hospital_id}.yaml"
    own_hospital = hfile.exists()
    if not own_hospital:
        hfile = CATALOG / "hospitals" / "rwjuh_nb.yaml"
    hd = _yaml(hfile)
    variants = hd.get("variants") or {}
    hv = variants.get(c.hospital_id) or next(iter(variants.values()))
    c.cat["hospital"] = copy.deepcopy(hv.get("attributes") or {})
    c.hospital_label = hv.get("label", c.hospital_id)
    # hospital-specific values of attributes that live in the shared catalog files (arrivals, wages, rosters,
    # calibrated parameters): `catalog_overrides: {"<file>.<variant|shared>.<key>": value | attribute node}`
    c.hospital_overrides = dict(hd.get("catalog_overrides") or {}) if own_hospital else {}
    for pth, v in c.hospital_overrides.items():
        _set_path(c.cat, pth, v)
    # calibration (written by twin/calibrate.py, never by hand): fitted values of ASSUMED attributes so the
    # baseline reproduces the hospital's published figures, and the baseline ("current practice") action defaults
    cfile = CATALOG / "hospitals" / f"{c.hospital_id}.calibration.yaml"
    c.calibration = (_yaml(cfile) or {}) if cfile.exists() and not no_calibration else {}
    for pth, v in (c.calibration.get("catalog_overrides") or {}).items():
        _set_path(c.cat, pth, v)
    for pth, v in (sd.get("catalog_overrides") or {}).items():
        _set_path(c.cat, pth, v)
    arrival_scale = float(sd.get("arrival_scale", 1.0))
    for k in list(overrides):
        if k == "arrival_scale":
            arrival_scale = float(overrides[k])
        elif k == "events":
            c.events = copy.deepcopy(overrides[k])
        elif k == "flags":
            c.flags.update(overrides[k])
        elif k in c.engine:
            c.engine[k] = overrides[k]
        elif "." in k:
            _set_path(c.cat, k, overrides[k])
        else:
            raise KeyError(f"unknown scenario override '{k}'")

    # ---- contracts
    c.enums = _yaml(CONTRACTS / "enums.yaml")
    m = _yaml(CONTRACTS / "metrics.yaml")
    c.metric_defs = m["metrics"]
    c.summary_defs = m["episode_summary"]
    c.heads = _yaml(CONTRACTS / "actions.yaml")["heads"]
    base_act = dict(c.calibration.get("baseline_actions") or {})
    base_act.update(base_act_override)
    for h in c.heads:                                # per-hospital baseline policy = the heads' defaults
        if h["name"] in base_act:
            h["default"] = max(0, min(len(h["options"]) - 1, int(base_act[h["name"]])))

    # ---- layout
    lfile = None
    cand = [CATALOG / "hospitals" / f"{c.hospital_id}.layout.json"]
    if own_hospital and hd.get("layout_file"):
        cand.insert(0, ROOT / hd["layout_file"])
    if sd.get("layout_file"):
        cand.insert(0, ROOT / sd["layout_file"])
    for p in cand:
        if p.exists():
            lfile = p
            break
    if lfile is None:
        lfile = CONTRACTS / "fixtures" / "layout.fixture.json"
    with open(lfile) as f:
        layout = json.load(f)
    c.layout_source = str(lfile.relative_to(ROOT))
    H = lambda k, d=None: c.val("hospital", None, k, d)   # noqa: E731
    # counterfactual capacity edit (rl/attribution.py): default None = the file as it is
    c.layout_edit = apply_layout_edit(layout, layout_edit, H("ed_bay_room_types")) if layout_edit else []
    eng = c.engine
    hall_opts = [int(x) for x in H("hallway_overflow_spaces")]
    bay_step = int(H("bays_delta_step"))
    ward_step = int(H("ward_beds_delta_step"))
    nominal_bays = float(H("ed_treatment_spaces"))
    probe = LayoutModel(layout, H("ed_bay_room_types"), H("ward_pool_room_types"), 0, 0)
    exact = own_hospital and lfile.name.startswith(c.hospital_id)
    size_ratio = 1.0 if exact else max(0.02, probe.n_ed_bays0 / nominal_bays)
    hall_opts = [int(round(x * size_ratio)) for x in hall_opts] if not exact else hall_opts
    lm = LayoutModel(layout, H("ed_bay_room_types"), H("ward_pool_room_types"), max(hall_opts),
                     bay_step * int(eng["structural_max_steps"]), float(c.val("space", None, "walk_path_factor")))
    c.layout = lm
    c.size_ratio = size_ratio

    P = c.P
    S = lambda f, k, d=None: c.val(f, None, k, d)   # noqa: E731
    acu = ["esi1", "esi2", "esi3", "esi4", "esi5"]
    P["size_ratio"] = size_ratio
    P["arrival_scale"] = arrival_scale
    P["arrivals_per_day"] = float(S("patient", "arrivals_per_day")) * arrival_scale * size_ratio
    P["hour_prof"] = [float(x) for x in S("patient", "arrival_hour_profile")]
    P["dow_prof"] = [float(x) for x in S("patient", "arrival_dow_profile")]
    P["month_prof"] = [float(x) for x in S("patient", "arrival_month_profile")]
    if not c.flags["diurnal"]:
        P["hour_prof"], P["dow_prof"], P["month_prof"] = [1.0] * 24, [1.0] * 7, [1.0] * 12
    P["acuity_mix"] = [float(x) for x in S("patient", "acuity_mix")]

    def mix(key, names):
        d = S("patient", key)
        v = [float(d.get(n, 0.0)) for n in names]
        s = sum(v) or 1.0
        return [x / s for x in v]

    E = c.enums
    P["cond_mix"] = mix("condition_mix", E["condition_group"])
    P["age_mix"] = mix("age_band_mix", E["age_band"])
    P["payer_mix"] = mix("payer_mix", E["payer"])
    pm = S("patient", "payer_revenue_multiplier")
    P["payer_mult"] = [float(pm.get(n, 1.0)) for n in E["payer"]]
    P["amb_share"] = [float(x) for x in S("patient", "ambulance_share_by_acuity")]
    P["p_transfer_in"] = float(S("patient", "p_transfer_in"))
    P["p_transfer_out"] = float(S("patient", "p_transfer_out"))
    P["p_mistriage"] = float(S("patient", "p_mistriage"))
    P["det_haz"] = [float(x) for x in S("patient", "deterioration_hazard_per_hour_waiting")]
    P["death_haz"] = [float(x) for x in S("patient", "death_hazard_per_hour_untreated")]
    P["death_post_mult"] = float(S("patient", "death_hazard_post_contact_multiplier"))
    k, mean, cv = c.dist("patient", None, "lwbs_patience_min")
    P["patience"] = dict(kind=k, mean=[float(x) for x in S("patient", "lwbs_patience_min")], cv=[cv] * 5)
    k, mean, cv = c.dist("patient", None, "inpatient_los_days")
    P["ward_pool_los_factor"] = float(c.val("hospital", None, "ward_pool_los_factor"))
    P["los"] = dict(kind=k, mean=float(mean) * 1440.0 * P["ward_pool_los_factor"], cv=cv)
    k, mean, cv = c.dist("patient", None, "lab_turnaround_min")
    P["lab"] = dict(kind=k, mean=float(mean), cv=cv)
    P["inpatient_revenue"] = float(S("patient", "inpatient_revenue"))
    P["inpatient_cost_per_day"] = float(S("patient", "inpatient_variable_cost_per_day"))
    P["boarding_los_penalty"] = float(S("patient", "boarding_los_penalty"))
    for k2 in ["wrong_disposition_max_prob", "wrong_discharge_adverse_prob", "low_quality_treatment_stretch",
               "transfer_wait_min", "acuity_aging_levels_per_hour", "discharge_push_los_factor",
               "discharge_push_cost_per_hour", "transfer_out_cost", "baseline_error_events_per_patient_hour"]:
        P[k2] = float(S("patient", k2))
    P["admission_cap_thr"] = [float(x) for x in S("patient", "admission_cap_thresholds")]

    def by_acu_dist(key):
        ks, ms, cvs = [], [], []
        for a in acu:
            k_, m_, cv_ = c.dist("patient", a, key)
            ks.append(k_), ms.append(float(m_)), cvs.append(cv_)
        return dict(kind=ks, mean=ms, cv=cvs)

    for key in ["triage_min", "provider_initial_min", "provider_reeval_min", "treatment_min"]:
        P[key] = by_acu_dist(key)
    so = sd.get("service_override")
    if so:      # M/M/c validation: one service distribution for the clinician encounter
        P["provider_initial_min"] = dict(kind=[so["kind"]] * 5, mean=[float(so["mean"])] * 5, cv=[float(so.get("cv", 1.0))] * 5)
    for key in ["p_imaging", "p_ct_given_imaging", "p_lab", "p_admit", "revenue_ed_visit", "supply_cost",
                "nurse_care_min_per_hour"]:
        P[key] = [float(c.val("patient", a, key)) for a in acu]

    # ---- staff
    for k2 in ["overtime_multiplier", "agency_premium_multiplier", "benefits_load", "absence_rate",
               "fatigue_gain_per_busy_hour", "fatigue_recovery_per_idle_hour", "fatigue_speed_penalty",
               "fatigue_error_multiplier", "callin_delay_min", "rn_patients_per_nurse_max", "fatigue_shift_carryover",
               "hire_delay_days", "hire_cost_per_head", "encounter_quality_base", "encounter_quality_sd",
               "fatigue_quality_penalty", "second_imaging_unit_tech", "headcount_max_steps"]:
        P[k2] = float(S("staff", k2))
    P["headcount_max_steps"] = int(P["headcount_max_steps"])
    scale_people = lambda xs: [max(1, int(round(float(x) * size_ratio))) for x in xs]   # noqa: E731
    P["provider_levels"] = scale_people(S("staff", "provider_levels"))
    P["rn_levels"] = scale_people(S("staff", "rn_levels"))
    P["triage_levels"] = [int(x) for x in S("staff", "triage_nurse_levels")]
    P["agency_levels"] = [int(round(float(x) * size_ratio)) if x else 0 for x in S("staff", "agency_nurses_per_shift")]
    P["callin_max"] = {k_: int(v) for k_, v in S("staff", "callin_max_per_shift").items()}
    P["ft_dedicated"] = {k_: int(v) for k_, v in S("staff", "fast_track_dedicated").items()}
    P["headcount_step"] = {k_: int(v) for k_, v in S("staff", "headcount_step").items()}
    P["role_mix"] = {k_: float(v) for k_, v in S("staff", "provider_role_mix").items()}
    P["support"] = {k_: max(1, int(round(float(v) * size_ratio))) for k_, v in S("staff", "support_staff_per_shift").items()}
    P["wage"] = {r: float(c.val("staff", r, "wage_per_hour")) for r in E["staff_role"]}
    P["productivity"] = {r: float(c.val("staff", r, "productivity", 1.0)) for r in E["staff_role"]}

    # ---- space
    for k2 in ["walk_speed_m_per_min", "patient_transport_speed_m_per_min", "hallway_quality_penalty",
               "build_delay_days", "relocate_delay_days", "relocate_cost", "ward_bed_open_delay_days",
               "ward_bed_open_cost", "bay_close_cost", "relocate_reduced_triage_stations"]:
        P[k2] = float(S("space", k2))
    if layout.get("walk_speed_m_per_min"):
        P["walk_speed_m_per_min"] = float(layout["walk_speed_m_per_min"])
    cls_space = dict(resus="resus_bay", main="treatment_bay", fast="fast_track", peds="peds_ed", hall="hallway_overflow")
    P["turnaround"] = [float(c.val("space", cls_space[n], "turnaround_min")) for n in BAY_CLASSES]
    P["bay_fixed"] = [float(c.val("space", cls_space[n], "fixed_cost_per_hour")) for n in BAY_CLASSES]
    P["bay_build_cost"] = float(c.val("space", "treatment_bay", "build_cost"))
    P["triage_fixed"] = float(c.val("space", "triage", "fixed_cost_per_hour"))
    wu_cap = max(1.0, float(c.val("space", "ward_unit", "capacity")))
    P["ward_bed_fixed"] = float(c.val("space", "ward_unit", "fixed_cost_per_hour")) / wu_cap
    P["other_fixed"] = sum(float(c.val("space", t, "fixed_cost_per_hour", 0.0)) * len(lm.by_type.get(t, []))
                           for t in ["waiting_room", "results_waiting", "lab", "pharmacy"])

    # ---- equipment (xray = 0, ct = 1)
    P["equip"] = {}
    vc = S("equipment", "variable_cost_per_use")
    for t in ("xray", "ct"):
        k, mean, cv = c.dist("equipment", t, "procedure_min")
        P["equip"][t] = dict(
            proc=dict(kind=k, mean=float(mean), cv=cv), units=int(lm.scan_units[t]),
            fail=float(c.val("equipment", t, "failure_prob_per_hour")),
            repair=float(c.dist("equipment", t, "repair_min")[1]),
            purchase=float(c.val("equipment", t, "purchase_cost")),
            maint_h=float(c.val("equipment", t, "maintenance_cost_per_year")) / 8760.0,
            revenue=float(c.val("equipment", t, "revenue_per_use")),
            result_delay=float(c.val("equipment", t, "result_delay_min")),
            var_cost=float(vc.get(t, 0.0)),
            room_fixed=float(c.val("space", t, "fixed_cost_per_hour", 0.0)))
    P["imaging_windows"] = [[int(a), int(b)] for a, b in S("equipment", "imaging_hours_windows")]
    P["install_delay_days"] = float(S("equipment", "install_delay_days"))
    P["units_always_staffed"] = int(S("equipment", "units_always_staffed"))

    # ---- hospital
    P["hall_opts"] = hall_opts
    P["bay_step"], P["ward_step"] = bay_step, ward_step
    P["ward_initial_occupancy"] = float(H("ward_initial_occupancy"))
    P["min_main_bays"] = max(1, int(round(float(H("min_main_bays")) * size_ratio)))
    P["min_ward_beds"] = max(1, int(round(float(H("min_ward_beds")) * size_ratio)))
    P["ward_cap0"] = lm.ward_cap
    P["ward_cap_max"] = lm.ward_cap + ward_step * int(eng["structural_max_steps"])
    fixed_c = sd.get("fixed_servers")
    P["fixed_servers"] = int(fixed_c) if fixed_c else 0
    pool = overrides.get("pool_size") or sd.get("pool_size") or eng.get("pool_size")
    if not pool:
        r = int(eng["pool_round_to"])
        ward_part = P["ward_cap_max"] if c.flags["ward"] else 0
        pool = int(math.ceil((ward_part + lm.n_bays + int(eng["pool_waiting_slack"])) / r) * r)
    P["pool_size"] = int(pool)

    # ---- events -> resolved list (parameters from catalog/event.yaml, scenario may override)
    ev_out = []
    for ev in c.events:
        base = {}
        for k_, a in ((((c.cat["event"].get("variants") or {}).get(ev["type"]) or {}).get("attributes")) or {}).items():
            base[k_] = a.get("value")
        base.update({k_: v for k_, v in ev.items()})
        ev_out.append(base)
    c.events = ev_out
    return c
