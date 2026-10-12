"""Ensemble of twins: every parameter set that reproduces the hospital's public record.

    python -m twin.ensemble --hospital rwjuh_nb --device cuda      # needs twin/reports/<id>/fit.json (twin.calibrate --stage fit)

Public data pins down a few aggregate figures (median ED time, LWBS, occupancy, salary bill) and leaves
the parameters behind them unidentified. Instead of one fitted hospital this writes N of them
(approximate Bayesian computation by rejection, with a few sequential rounds to find the region):

  1. draw candidates from the plausible range of every influential parameter that public data does not fix
     (assumed attributes: wide boxes; literature attributes: only inside the `range:` published in the catalog);
  2. simulate each with the baseline policy (candidates x seeds in one batch, common random numbers);
  3. keep a candidate only if EVERY hospital-specific target is inside its acceptance interval
     (twin/targets.py), later rounds perturb the kept ones;
  4. pick a spread-out subset (greedy max-min distance in parameter space), re-simulate it on held-out seeds
     and drop whatever no longer passes.

Member 0 is always the point calibration (`catalog/hospitals/<id>.calibration.yaml`).

OUTPUT  catalog/hospitals/<id>.ensemble.json

    {
      "hospital_id": "rwjuh_nb",
      "generated": "2026-10-10T12:00:00",
      "scenario": "normal_week",
      "usage": "...",
      "targets":   {<sim key>: {label, value, lo, hi, scope, unit, accept, ...}},      # twin/targets.py
      "parameters": [{key, label, tag, lo, hi, why}],                                  # what was varied and over what range
      "search":    {description, rounds: [{n, accepted}], n_candidates, n_accepted, acceptance_rate, n_verified, ...},
      "members": [
        {"id": 0,
         "overrides": {"staff.shared.provider_levels": [..5 ints..], "patient.esi3.provider_initial_min": 21.4,
                       "hospital.ward_pool_los_factor": 0.97, "patient.shared.lwbs_patience_min": [...], ...},
         "baseline_actions": {"md_day": 2, "md_evening": 3, "md_night": 1, "rn_day": 2, "rn_evening": 3, "rn_night": 1,
                              "triage_nurses": 1, "provider_split": 1},
         "theta":   {...the candidate in twin/harness.py terms (people per shift, scales)...},
         "derived": {provider_hours_per_visit, rn_hours_per_visit, providers_mean, nurses_mean, night_to_day_providers},
         "fit":     {<sim key>: simulated value on the held-out seeds, ...},
         "inside":  {<hospital target key>: true/false}}
        , ...]
    }

USE (rl/, server/): each member is a complete description, usable directly:

    m = json.load(open("catalog/hospitals/rwjuh_nb.ensemble.json"))["members"][i]
    scn = load_scenario("normal_week", overrides={**m["overrides"], "baseline_actions": m["baseline_actions"],
                                                  "hospital_id": "rwjuh_nb"})
    sim = HospitalSim(scn, ...)      # sim.default_actions() is that member's current-practice baseline

`overrides` lists every attribute the ensemble varies (not only those that differ from the calibration
file), so it gives the same hospital with or without `"no_calibration": True`. The staffing LADDER
(`staff.shared.provider_levels` / `rn_levels`) differs between members, so the same level index means a
different head-count in different members: compare a policy with that member's own baseline
(`default_actions()`), never across members by level index. All numbers are SIMULATED.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from twin import harness as H  # noqa: E402
from twin import targets as TG  # noqa: E402

CATALOG = ROOT / "catalog"
ENS_SEED, CHECK_SEED = 500000, 400000
EXTRA_FIT = ["wait_mean", "wait_median", "wait_p90", "wait_p95", "los_dc_p90", "boarding_hours_per_day", "admissions_per_day",
             "md_utilization", "rn_utilization", "bay_occupancy", "ed_census", "cost_labor_per_day", "cost_per_day", "revenue_per_day",
             "margin_per_day", "deaths_per_day", "adverse_events_per_day", "provider_hours_per_day", "rn_hours_per_day",
             "ed_salaries_all_per_day"]
NUISANCE = ["lab_scale", "nurse_care_scale", "patience_scale", "absence_rate", "boarding_los_penalty"]


def _range_of(hid: str, path: str):
    from twin.calibrate import _attr_node
    n = _attr_node(hid, path)
    return n.get("range"), n.get("value"), n.get("source", "?")


def parameter_space(hid: str, fitres: dict) -> tuple[dict, list[dict]]:
    """Box of the ensemble = the calibration's search box + the nuisance parameters."""
    sp = fitres["space"]
    base = fitres["base"]
    lo, hi = dict(sp["lo"]), dict(sp["hi"])
    lo.update(lab_scale=0.6, nurse_care_scale=0.6)
    hi.update(lab_scale=1.8, nurse_care_scale=2.0)
    notes = {}
    # literature attributes: only inside the published range
    rg, val, tag = _range_of(hid, "patient.shared.lwbs_patience_min")
    if rg and isinstance(rg[0], (list, tuple)):
        los = [r[0] / v for r, v in zip(rg[1:], val[1:]) if v]
        his = [r[1] / v for r, v in zip(rg[1:], val[1:]) if v]
        lo["patience_scale"], hi["patience_scale"] = float(max(los)), float(min(his))
        notes["patience_scale"] = (tag, "one scale on ESI 2-5 patience, limited so every acuity stays inside the catalog `range` "
                                        "(Batt & Terwiesch 2015, research/operations-parameter-ranges.yaml)")
    else:
        lo["patience_scale"] = hi["patience_scale"] = 1.0
        notes["patience_scale"] = (tag, "no range published in the catalog: not varied")
    for key, path, why in (("absence_rate", "staff.shared.absence_rate", "catalog `range` (BLS absence rates)"),
                           ("boarding_los_penalty", "patient.shared.boarding_los_penalty", "catalog `range` (boarding studies)")):
        rg, val, tag = _range_of(hid, path)
        if rg and not isinstance(rg[0], (list, tuple)):
            lo[key], hi[key] = float(rg[0]), float(rg[1])
            notes[key] = (tag, why)
        else:
            lo[key] = hi[key] = float(base["base_theta"][key])
            notes[key] = (tag, "no range published in the catalog: not varied")
    space = dict(lo=lo, hi=hi, cats=dict(sp["cats"]), f_star=sp["f_star"], occ_target=sp["occ_target"])
    src = base["sources"]
    params = [
        dict(key="provider_hours_per_visit", label="Provider-hours per visit (schedule)", tag=src["provider_levels"], lo=lo["md_hpv"], hi=hi["md_hpv"],
             why="no public schedule; roster bound if one is published"),
        dict(key="night_to_day_providers", label="Providers on nights / on days", tag="baseline policy", lo=0.2, hi=1.0,
             why="shape exponent 0.3..1 on the arrival curve"),
        dict(key="rn_hours_per_visit", label="Nurse-hours per visit (schedule, incl. triage)", tag=src["rn_levels"], lo=lo["rn_hpv"], hi=hi["rn_hpv"],
             why="literature low end up to what the salary bill allows"),
        dict(key="enc_scale", label="First-encounter time, x catalog", tag=src["enc"], lo=lo["enc_scale"], hi=hi["enc_scale"], why="assumed attribute, +/- about 50 %"),
        dict(key="reeval_scale", label="Re-evaluation time, x catalog", tag=src["reeval"], lo=lo["reeval_scale"], hi=hi["reeval_scale"], why="assumed attribute, x0.5 .. x3"),
        dict(key="los_factor", label="Share of inpatient stay in the ward pool", tag=src["los_factor"], lo=lo["los_rel"] * sp["f_star"],
             hi=hi["los_rel"] * sp["f_star"], why="around the value that gives the published occupancy"),
        dict(key="lab_scale", label="Lab turnaround, x catalog", tag=src["lab"], lo=lo["lab_scale"], hi=hi["lab_scale"], why="assumed attribute"),
        dict(key="nurse_care_scale", label="Nurse minutes per patient-hour, x catalog", tag=src["nurse_care"], lo=lo["nurse_care_scale"],
             hi=hi["nurse_care_scale"], why="assumed attribute"),
        dict(key="patience_scale", label="LWBS patience, x catalog", tag=notes["patience_scale"][0], lo=lo["patience_scale"], hi=hi["patience_scale"],
             why=notes["patience_scale"][1]),
        dict(key="absence_rate", label="Staff absence rate", tag=notes["absence_rate"][0], lo=lo["absence_rate"], hi=hi["absence_rate"], why=notes["absence_rate"][1]),
        dict(key="boarding_los_penalty", label="Inpatient stay penalty per boarding hour", tag=notes["boarding_los_penalty"][0],
             lo=lo["boarding_los_penalty"], hi=hi["boarding_los_penalty"], why=notes["boarding_los_penalty"][1]),
        dict(key="triage", label="Triage stations (option index)", tag="baseline policy", lo=0, hi=sp["cats"]["triage"] - 1, why="all options"),
        dict(key="split", label="Provider split (option index)", tag="baseline policy", lo=0, hi=2, why="all options")]
    return space, params


def distance(T: dict, row: dict) -> float:
    """Largest normalised miss over the hospital-specific acceptance targets (<= 1 means inside every interval)."""
    d = 0.0
    for k, t in T.items():
        if not t.accept or k not in row:
            continue
        v = float(row[k])
        if math.isnan(v):
            return 99.0
        mid, half = 0.5 * (t.lo + t.hi), 0.5 * (t.hi - t.lo)
        d = max(d, abs(v - mid) / max(half, 1e-12))
    return d


def _norm(x: dict, space: dict, keys: list[str]) -> np.ndarray:
    lo, hi = space["lo"], space["hi"]
    v = [(x[k] - lo[k]) / (hi[k] - lo[k]) if hi[k] > lo[k] else 0.5 for k in keys]
    v += [x[c] / max(1, m - 1) * 0.5 for c, m in space["cats"].items()]
    return np.array(v, dtype=float)


def _derived(theta: dict, base: dict) -> dict:
    A = base["arrivals_per_day"]
    tri = min(base["triage_levels_cal"][int(theta["triage"])], base["n_triage_rooms"])
    md, rn = theta["md"], theta["rn"]
    return dict(provider_hours_per_visit=8.0 * sum(md) / A, rn_hours_per_visit=(8.0 * sum(rn) + 24.0 * tri) / A,
                providers_mean=sum(md) / 3.0, nurses_mean=sum(rn) / 3.0, night_to_day_providers=md[2] / md[0],
                night_to_day_nurses=rn[2] / rn[0])


def build(hid: str, device: str = "cpu", members: int = 24, n_seeds: int = 6, days: int = 37, warm: int = 7, pop: int = 256,
          rounds: int = 4, check_seeds: int = 32, seed: int = 1) -> dict:
    from twin.calibrate import report_dir, save_json, to_theta, sample_population, sim_row
    t00 = time.time()
    fitres = json.loads((report_dir(hid) / "fit.json").read_text())
    base = H.base_values(hid)
    T = TG.collect_targets(hid)
    space, params = parameter_space(hid, fitres)
    keys = list(space["lo"])
    rs = np.random.RandomState(seed)
    x0 = dict(fitres["best"]["x"])
    for k in NUISANCE:
        x0.setdefault(k, 1.0 if k.endswith("_scale") else base["base_theta"][k])
    seeds = list(range(ENS_SEED, ENS_SEED + n_seeds))
    width = {k: space["hi"][k] - space["lo"][k] for k in keys}
    clip = lambda k, v: float(np.clip(v, space["lo"][k], space["hi"][k]))   # noqa: E731

    def child(parent: dict, sd: float) -> dict:
        x = {k: clip(k, rs.normal(parent[k], sd * width[k])) for k in keys}
        for k in NUISANCE:                         # keep the nuisance parameters spread over their whole range
            if rs.uniform() < 0.5:
                x[k] = float(rs.uniform(space["lo"][k], space["hi"][k]))
        for c, m in space["cats"].items():
            x[c] = int(parent[c]) if rs.uniform() < 0.7 else int(rs.randint(0, m))
        return x

    pool, stats = [], []
    for r in range(rounds):
        if r == 0:
            xs = sample_population(rs, pop // 2, space) + [child(x0, 0.25) for _ in range(pop - pop // 2)]
        else:
            ranked = sorted(pool, key=lambda a: a["d"])
            parents = [a for a in ranked if a["d"] <= 1.0] or ranked[:max(8, pop // 12)]
            if len(parents) < 8:
                parents = ranked[:8]
            xs = [child(parents[rs.randint(len(parents))]["x"], 0.10) for _ in range(pop)]
        xs[0] = dict(x0)
        thetas = [to_theta(x, base, space) for x in xs]
        res = H.evaluate(hid, thetas, seeds, days, warm, device, base, progress=f"[{hid}] ensemble round {r + 1}/{rounds}")
        n_acc = 0
        for i, x in enumerate(xs):
            row = sim_row(res, i)
            d = distance(T, row)
            n_acc += d <= 1.0
            pool.append(dict(x=x, theta=res["concs"][i]["theta"], sim=row, d=d, round=r))
        stats.append(dict(round=r, n=len(xs), accepted=int(n_acc)))
        print(f"[{hid}] ensemble round {r + 1}: {n_acc}/{len(xs)} inside every hospital-specific interval", flush=True)

    # ---- spread-out subset of the accepted candidates (a safety margin for the held-out re-check)
    acc = [a for a in pool if a["d"] <= 0.85]
    if len(acc) < members:
        acc = [a for a in pool if a["d"] <= 1.0]
    uniq, seen = [], set()
    for a in acc:
        k = json.dumps(H.concrete(a["theta"], base), sort_keys=True)
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    want = min(len(uniq), int(math.ceil(members * 1.7)))
    chosen = [dict(x=x0, theta=fitres["best"]["theta"], sim=fitres["best"]["sim_refine"], d=distance(T, fitres["best"]["sim_refine"]), round=-1)]
    vec = [_norm(a["x"], space, keys) for a in uniq]
    dmin = np.array([np.linalg.norm(v - _norm(x0, space, keys)) for v in vec]) if vec else np.array([])
    while len(chosen) < want + 1 and len(vec) and dmin.max() > 0:
        j = int(dmin.argmax())
        chosen.append(uniq[j])
        dmin = np.minimum(dmin, np.array([np.linalg.norm(v - vec[j]) for v in vec]))
    # ---- held-out verification (same seeds as the calibration's own held-out check)
    vseeds = list(range(CHECK_SEED, CHECK_SEED + check_seeds))
    res = H.evaluate(hid, [c["theta"] for c in chosen], vseeds, days + 8, warm, device, base, progress=f"[{hid}] ensemble held-out check")
    out_members, dropped = [], 0
    for i, c in enumerate(chosen):
        row = sim_row(res, i)
        inside = {k: bool(t.inside(row[k])) for k, t in T.items() if t.accept and k in row}
        if i > 0 and not all(inside.values()):
            dropped += 1
            continue
        if len(out_members) >= members:
            break
        conc = res["concs"][i]
        ov, acts = H.overrides_of(conc, base, only_changed=False)
        out_members.append(dict(
            id=len(out_members), overrides=ov, baseline_actions={k: int(v) for k, v in acts.items()}, theta=conc["theta"],
            derived=_derived(conc["theta"], base),
            fit={k: row[k] for k in list(T) + EXTRA_FIT if k in row}, inside=inside, search_round=c["round"]))
    n_cand = len(pool)
    n_acc = sum(1 for a in pool if a["d"] <= 1.0)
    doc = dict(
        hospital_id=hid, generated=_dt.datetime.now().isoformat(timespec="seconds"), scenario=H.SCENARIO, generator="twin/ensemble.py",
        usage="load_scenario(scenario, overrides={**member['overrides'], 'baseline_actions': member['baseline_actions'], 'hospital_id': '%s'}); "
              "member 0 = the point calibration; staffing ladders differ between members (see twin/ensemble.py)" % hid,
        targets=TG.as_dicts(T), parameters=params,
        search=dict(
            description=f"{rounds} rounds x {pop} candidates x {n_seeds} seeds, {days - warm} simulated days each after a {warm}-day warm-up: "
                        f"{n_acc} of {n_cand} candidates ({100.0 * n_acc / max(1, n_cand):.0f} %) were inside every hospital-specific interval "
                        f"(round 1, drawn half from the whole box and half around the point calibration: {stats[0]['accepted']} of {stats[0]['n']}). "
                        f"{len(chosen) - 1} spread-out candidates were re-simulated on {check_seeds} held-out seeds for {days + 8 - warm} days; "
                        f"{dropped} no longer passed and were dropped; {len(out_members)} members kept (including member 0).",
            rounds=stats, n_candidates=n_cand, n_accepted=n_acc, acceptance_rate=n_acc / max(1, n_cand), n_verified=len(chosen) - 1,
            n_dropped_on_held_out=dropped, search_seeds=[seeds[0], seeds[-1]], held_out_seeds=[vseeds[0], vseeds[-1]], days=days, warm=warm,
            held_out_days=days + 8, wall_seconds=time.time() - t00),
        members=out_members)
    for m in out_members[1:]:                       # literature values must stay inside their published range
        for pr in params:
            if pr["tag"] == "literature" and pr["key"] in m["theta"]:
                assert pr["lo"] - 1e-9 <= m["theta"][pr["key"]] <= pr["hi"] + 1e-9, (pr["key"], m["theta"][pr["key"]])
    from twin.calibrate import _jsonable
    H.atomic_write(CATALOG / "hospitals" / f"{hid}.ensemble.json", json.dumps(_jsonable(doc), indent=1))
    save_json(report_dir(hid) / "ensemble_run.json", dict(
        hospital_id=hid, generated=doc["generated"], space=space, stats=stats,
        pool=[dict(x=a["x"], d=a["d"], round=a["round"], sim={k: a["sim"][k] for k in list(T) + ["wait_p90", "wait_mean"] if k in a["sim"]}) for a in pool]))
    print(f"[{hid}] wrote catalog/hospitals/{hid}.ensemble.json: {len(out_members)} members "
          f"({n_acc}/{n_cand} candidates accepted, {dropped} dropped on held-out seeds)", flush=True)
    if not all(out_members[0]["inside"].values()):
        print(f"[{hid}] WARNING: member 0 (point calibration) is outside an interval on held-out seeds: {out_members[0]['inside']}", flush=True)
    return doc


def load_members(hospital_id: str) -> list[dict]:
    """Members as load_scenario override dicts (hospital_id and baseline_actions folded in)."""
    doc = json.loads((CATALOG / "hospitals" / f"{hospital_id}.ensemble.json").read_text())
    return [{**m["overrides"], "baseline_actions": m["baseline_actions"], "hospital_id": hospital_id} for m in doc["members"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hospital", default="rwjuh_nb")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--members", type=int, default=24)
    ap.add_argument("--pop", type=int, default=256)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--days", type=int, default=37)
    ap.add_argument("--warm", type=int, default=7)
    ap.add_argument("--check-seeds", type=int, default=32)
    a = ap.parse_args()
    build(a.hospital, a.device, a.members, a.seeds, a.days, a.warm, a.pop, a.rounds, a.check_seeds)
    from twin.calibrate import write_report
    write_report(a.hospital)


if __name__ == "__main__":
    main()
