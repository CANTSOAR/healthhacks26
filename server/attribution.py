"""Marginal value of a resource unit, read from rl/hospitals/<id>/attribution.json (written by rl/attribution.py).

Everything here is a lookup or plain arithmetic on the stored numbers: no simulation, no torch. ALL VALUES ARE
SIMULATED. `minus_one` in the file is (without the unit) - (baseline), so the value of the unit is its negative.
"""
from __future__ import annotations

import math

from . import cache
from .paths import rl_dir

SHIFTS = ("day", "evening", "night")
ROOM_UNIT = {"resus_bay": "bay_resus", "fast_track": "bay_fast", "peds_ed": "bay_peds", "triage": "triage_station", "ward_unit": "ward_bed",
             "icu_bed": "ward_bed", "stepdown_bed": "ward_bed", "ct": "ct_scanner", "xray": "xray_room"}
EQUIPMENT_UNIT = {"ct": "ct_scanner", "xray": "xray_room"}
HELD_CONSTANT = ("Held constant in the model: this role is not a decision the simulator can change, so it has no simulated marginal value.")


def path(hospital_id: str):
    return rl_dir() / "hospitals" / hospital_id / "attribution.json"


def load(hospital_id: str) -> dict | None:
    if not hospital_id or not str(hospital_id).replace("_", "").isalnum():
        return None
    d = cache.load(path(hospital_id))
    return d if isinstance(d, dict) and isinstance(d.get("units"), list) else None


# ---------------------------------------------------------------- re-scoring under other weights
def _t975(df: int) -> float:
    if df <= 0:
        return float("nan")
    if df <= 2:
        return (12.706, 4.303)[df - 1]
    z = 1.959964
    return (z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)
            + (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * df ** 3)
            + (79 * z ** 9 + 776 * z ** 7 + 1482 * z ** 5 - 1920 * z ** 3 - 945 * z) / (92160 * df ** 4))


def reward_stat(terms_seeds: list, terms: list, scales: dict, weights: dict) -> dict:
    """Mean and 95% interval of the change in reward per hour under `weights`, from the stored per-seed RAW
    term differences: reward = -sum_k w_k * term_k / scale_k."""
    wv = [float(weights.get(k, 0.0)) / float(scales[k]) for k in terms]
    xs = [-sum(w * float(v) for w, v in zip(wv, row)) for row in terms_seeds]
    n = len(xs)
    m = sum(xs) / max(1, n)
    if n < 2:
        return dict(mean=m, lo=None, hi=None)
    hw = _t975(n - 1) * math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) / math.sqrt(n)
    return dict(mean=m, lo=m - hw, hi=m + hw)


def weights_for(rep: dict, objective: str | None = None, weights: dict | None = None) -> dict | None:
    if weights:
        return {k: float(v) for k, v in weights.items() if k in rep["reward"]["terms"] and isinstance(v, (int, float))}
    if objective:
        return (rep["reward"].get("objectives") or {}).get(objective)
    return None


def rescored(rep: dict, weights: dict) -> dict:
    """A copy of the report (shallow per unit) where every direction carries `reward.custom` under `weights`."""
    terms, scales = rep["reward"]["terms"], rep["reward"]["scales"]
    out = dict(rep, reward=dict(rep["reward"], custom_weights=weights), units=[])
    for u in rep["units"]:
        sc_out = {}
        for sc, row in u["scenarios"].items():
            sc_out[sc] = {side: (dict(a, reward=dict(a["reward"], custom=reward_stat(a["terms_seeds"], terms, scales, weights))) if a else None)
                          for side, a in row.items()}
        out["units"].append(dict(u, scenarios=sc_out))
    return out


def summary(rep: dict) -> dict:
    """The report without the bulky per-seed and per-day arrays (ranking, findings, per-unit money and hourly profile stay)."""
    drop = ("terms_seeds", "by_day")
    units = []
    for u in rep["units"]:
        units.append(dict(u, scenarios={sc: {side: ({k: v for k, v in a.items() if k not in drop} if a else None) for side, a in row.items()}
                                        for sc, row in u["scenarios"].items()}))
    return dict(rep, units=units, location=dict(rep.get("location") or {}, rooms=None), view="summary")


# ---------------------------------------------------------------- entity -> resource unit
def shift_of(hour: int, starts=(7, 15, 23)) -> str:
    a, b, c = starts
    return "day" if a <= hour < b else ("evening" if b <= hour < c else "night")


def unit_id(kind: str, live: dict, hour: int) -> tuple[str | None, str | None]:
    """(unit id, reason when there is none) for an inspected entity."""
    if kind == "staff":
        role, sid = str(live.get("role") or ""), str(live.get("staff_id") or "")
        shift = live.get("shift") if live.get("shift") in SHIFTS else shift_of(hour)
        if live.get("group") == "triage":
            return "triage_station", None
        if role in ("attending", "resident", "app"):
            return f"provider_{shift}", None
        if role == "rn":
            return f"nurse_{shift}", None
        return None, HELD_CONSTANT if sid else None
    if kind == "room":
        t = str(live.get("type") or "")
        if t == "treatment_bay":
            return ("bay_hall" if "hallway" in str(live.get("catalog_ref") or "") else "bay_main"), None
        return ROOM_UNIT.get(t), None
    if kind == "equipment":
        return EQUIPMENT_UNIT.get(str(live.get("type") or "")), None
    return None, None


def _neg(s):
    return None if not s or s.get("mean") is None else dict(mean=-s["mean"], lo=-s["hi"], hi=-s["lo"])


def entity_value(hospital_id: str, kind: str, live: dict, scenario: str | None, hour: int, utilisation_now: dict | None = None) -> dict | None:
    """The compact block the inspector shows for one entity, or None when there is no report / no unit."""
    rep = load(hospital_id)
    uid, reason = unit_id(kind, live, hour)
    if rep is None or (uid is None and reason is None):
        return None
    if uid is None:
        return dict(available=False, simulated=True, reason=reason)
    u = next((x for x in rep["units"] if x["id"] == uid), None)
    scs = rep["protocol"]["scenarios"]
    sc = scenario if scenario in scs else scs[0]
    if u is None or sc not in u["scenarios"]:
        return None
    row = u["scenarios"][sc]
    mi, pl = row.get("minus_one"), row.get("plus_one")
    a, existing = (mi, True) if mi else (pl, False)
    if a is None:
        return None
    obj = rep["reward"]["default_objective"]
    sgn = -1.0 if existing else 1.0                      # value of the unit = -(effect of removing it)
    bh = a["by_hour"]
    cs = float(rep["reward"].get("cost_scale_per_hour") or rep["reward"]["scales"]["cost"])   # reward -> dollars of cost per hour
    h = int(hour) % 24
    val = lambda k: [sgn * x for x in bh[k]["mean"]]     # noqa: E731
    out = dict(
        available=True, simulated=True, unit=uid, label=u["label"], unit_label=u["unit_label"], resource_class=u["resource_class"], kind=u["kind"],
        shift=u.get("shift"), scenario=sc, manager=rep["manager"]["id"], objective=obj, existing=existing, n_units=a["money"]["n_units"],
        basis=("value of the existing unit: what the hospital loses without it" if existing else "value of adding it: none are in use at baseline"),
        reward_value_per_day=a["money"].get("reward_value_per_day"), reward_value_per_dollar=a["money"].get("reward_value_per_dollar"),
        net_value_per_day=a["money"]["net_value_per_day"], net_value_per_year=a["money"]["net_value_per_year"],
        unit_cost_per_day=a["money"]["unit_cost_per_day"], net_value_per_dollar=a["money"]["net_value_per_dollar"], cost_basis=u.get("cost_basis"),
        reward=(_neg(a["reward"][obj]) if existing else a["reward"][obj]), flow_index_pct=a.get("flow_index_pct"), verdict=a["verdict"],
        top_effects=[{k: e[k] for k in ("metric", "label", "unit", "delta", "lo", "hi", "pct", "significant", "direction")} for e in a["top_effects"][:3]],
        effects_of="removing it" if existing else "adding it",
        now=dict(hour=h, margin_per_hour=dict(mean=sgn * bh["margin"]["mean"][h], hw=bh["margin"]["hw"][h]),
                 reward_per_hour=dict(mean=sgn * bh["reward"]["mean"][h], hw=bh["reward"]["hw"][h]),
                 reward_value_per_hour=dict(mean=sgn * bh["reward"]["mean"][h] * cs, hw=bh["reward"]["hw"][h] * cs)),
        by_hour=dict(margin=val("margin"), margin_hw=bh["margin"]["hw"], reward=val("reward"), reward_hw=bh["reward"]["hw"],
                     reward_value=[x * cs for x in val("reward")], reward_value_hw=[x * cs for x in bh["reward"]["hw"]]),
        utilisation_typical=(lambda t: dict(mean=t["mean"], at_hour=t["by_hour"][h], full_share=t["full_share"], definition=t["definition"]) if t else None)(
            (u.get("utilisation") or {}).get(sc)),
        utilisation_now=utilisation_now,
        next_unit=(dict(net_value_per_day=pl["money"]["net_value_per_day"], reward_value_per_day=pl["money"].get("reward_value_per_day"),
                        reward=pl["reward"][obj], verdict=pl["verdict"]) if (pl and existing) else None),
        protocol=dict(n_seeds=rep["protocol"]["n_seeds"], days=rep["protocol"]["days"], ci=rep["protocol"]["ci"]),
        note=_note(u), generated=rep.get("generated"))
    if kind == "room":
        loc = ((rep.get("location") or {}).get("rooms") or {}).get(str(live.get("id")))
        if loc:
            out["location"] = dict(loc, modelled=False)
    return out


def _note(u: dict) -> str:
    cls = u["resource_class"]
    if cls.startswith(("provider", "nurse")):
        return ("Staff of a role are interchangeable in the model: this is the value of one " + u["unit_label"].replace("one ", "", 1)
                + ", not of this person.")
    if cls.startswith("bay_"):
        return "Every space of this class has the same simulated value: the model walks patients between zone centres, not to individual bays."
    if cls == "ward_bed":
        return "One bed of the pooled inpatient capacity the ED admits to; beds are not told apart in the model."
    if cls == "triage_station":
        return "A triage station is a room plus the nurse who staffs it, round the clock."
    return "Units of this type are interchangeable in the model."
