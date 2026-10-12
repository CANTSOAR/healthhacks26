"""Calibrate a hospital's digital twin so the DEFAULT policy reproduces the hospital's own published figures.

    python -m twin.calibrate --hospital rwjuh_nb --device cuda            # fit + held-out check + ensemble + report
    python -m twin.calibrate --hospital rwjuh_nb --stage fit              # stages: fit | check | ensemble | report | all
    python -m twin.calibrate --hospital rwjuh_nb --stage report           # re-render the report from the saved runs

What is fitted (and nothing else): attributes tagged `assumed` in the catalog, plus the baseline schedule
(the action heads' defaults for this hospital). Measured and literature values are never changed; the
writer refuses to emit an override for an attribute that is not tagged `assumed`.

    free parameter                         catalog attribute / head                         tag
    providers on day / evening / night     staff.shared.provider_levels + md_* defaults     assumed
    nurses on day / evening / night        staff.shared.rn_levels + rn_* defaults           assumed
    triage stations, provider split        triage_nurses, provider_split defaults           baseline policy
    first-encounter time scale             patient.esi*.provider_initial_min                assumed
    re-evaluation / disposition time scale patient.esi*.provider_reeval_min                 assumed
    share of the stay in the ward pool     hospital.ward_pool_los_factor                    assumed
    ward warm start                        hospital.ward_initial_occupancy                  assumed (set to the target)

The schedule follows the arrival curve: people on shift s = mean x (arrival share of s)^alpha, alpha in [0.3, 1]
fitted (0 would be flat, 1 = proportional to arrivals; the lower bound is a prior - no real ED staffs nights like days).

Search: cross-entropy method with common random numbers. Every generation is ONE simulator batch of
population x seeds hospitals (twin/harness.py), >= 30 simulated days after a 7-day warm-up. The best few
are re-scored on fresh seeds, the winner is written to `catalog/hospitals/<id>.calibration.yaml`, then
checked on held-out seeds for 60 days through the ordinary loader. All numbers are SIMULATED.
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
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from twin import harness as H  # noqa: E402
from twin import targets as TG  # noqa: E402

CATALOG = ROOT / "catalog"
FIT_SEED, REFINE_SEED, CHECK_SEED = 200000, 300000, 400000
CONT = ["md_hpv", "md_alpha", "rn_hpv", "rn_alpha", "enc_scale", "reeval_scale", "los_rel"]
CATS = ["triage", "split"]
RN_HPV_LIT = (1.16, 2.0)          # research/operations-parameter-ranges.yaml ed_nurse_hours_per_visit (one US ED)
ADMIT_UPLIFT = 1.065              # simulated admit decisions / (acuity mix x p_admit): disposition errors add a few admissions
ALPHA_MIN = 0.3                   # prior: no real ED staffs nights like days; 0.3 keeps nights at or below ~3/4 of days
PHYS_HOURS_PER_YEAR, APP_HOURS_PER_YEAR = 1500.0, 1800.0   # assumed clinical hours per rostered clinician


def report_dir(hid: str) -> Path:
    d = ROOT / "twin" / "reports" / hid
    d.mkdir(parents=True, exist_ok=True)
    return d


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def save_json(path: Path, obj) -> None:
    H.atomic_write(path, json.dumps(_jsonable(obj), indent=1))


# ------------------------------------------------------------------------------------------------
# search space
# ------------------------------------------------------------------------------------------------
def search_space(base: dict, T: dict, roster: dict) -> dict:
    A = base["arrivals_per_day"]
    occ = T["ward_occupancy"].value if "ward_occupancy" in T else None
    adm = A * base["admit_rate"] * ADMIT_UPLIFT
    f_star = occ * base["ward_cap"] / (adm * base["los_days"]) if occ else base["los_factor"]
    notes = []
    md_hi = 1.15
    if "em_physicians" in roster or "em_apps" in roster:
        hrs = roster.get("em_physicians", {}).get("value", 0.0) * PHYS_HOURS_PER_YEAR + roster.get("em_apps", {}).get("value", 0.0) * APP_HOURS_PER_YEAR
        # the public rosters list attendings and APPs; residents are not on them: model share of provider hours
        res_share = base["resident_share"]
        cap = hrs / 365.0 / max(1e-9, 1.0 - res_share) / A
        md_hi = max(0.5, min(1.6, cap))
        notes.append(f"Public roster: {roster.get('em_physicians', {}).get('value', 0):.0f} emergency physicians and "
                     f"{roster.get('em_apps', {}).get('value', 0):.0f} APPs. At {PHYS_HOURS_PER_YEAR:.0f} / {APP_HOURS_PER_YEAR:.0f} clinical "
                     f"hours a year (assumed) and residents covering {100 * res_share:.0f} % of provider hours (assumed role mix) that caps "
                     f"provider-hours at {cap * A:.0f} a day ({cap:.2f} per visit); the search upper bound is {md_hi:.2f} per visit. A roster "
                     "lists everyone affiliated, including part-time and multi-site clinicians, so it is an upper bound.")
    else:
        notes.append("No public clinician roster in the hospital file: provider-hours per visit searched over 0.45-1.15 "
                     "(the uncalibrated catalog has %.2f)." % (sum(base["base_theta"]["md"]) * 8.0 / A))
    if "ed_salaries_per_day" in T:
        rn_lo, rn_hi = RN_HPV_LIT[0], 6.0
        notes.append("Nurse hours: the hospital's own ED salary bill (HCRIS) is a target, so nurse-hours per visit are searched from the "
                     f"literature low ({RN_HPV_LIT[0]}) up to 6.0 and the salary target decides.")
    else:
        rn_lo, rn_hi = RN_HPV_LIT
        notes.append(f"No ED salary figure for this hospital: nurse-hours per visit kept inside the literature range {RN_HPV_LIT}.")
    if "rn_fte" in roster:
        notes.append(f"Hospital-wide RN FTE {roster['rn_fte']['value']:.0f} (all units) is reported but too coarse to bound the ED roster.")
    n_tri = max(1, min(len(base["triage_levels_cal"]), sum(1 for x in base["triage_levels_cal"] if x <= base["n_triage_rooms"])))
    if list(base["triage_levels_cal"]) != list(base["triage_levels"]):
        notes.append(f"Triage options resized for this hospital's volume: `staff.shared.triage_nurse_levels` {base['triage_levels']} -> "
                     f"{base['triage_levels_cal']} (assumed attribute; the top option keeps peak-hour triage load near 70 %).")
    return dict(
        lo=dict(md_hpv=0.45, md_alpha=ALPHA_MIN, rn_hpv=rn_lo, rn_alpha=ALPHA_MIN, enc_scale=0.7, reeval_scale=0.5,
                los_rel=(T["ward_occupancy"].lo / occ - 0.08) if occ else 0.9),
        hi=dict(md_hpv=md_hi, md_alpha=1.0, rn_hpv=rn_hi, rn_alpha=1.0, enc_scale=1.5, reeval_scale=3.0,
                los_rel=(T["ward_occupancy"].hi / occ + 0.08) if occ else 1.12),
        cats=dict(triage=n_tri, split=3), f_star=float(f_star), occ_target=float(occ if occ else base["ward_init"]), admit_uplift=ADMIT_UPLIFT, notes=notes)


def to_theta(x: dict, base: dict, space: dict) -> dict:
    """Search vector -> candidate theta (integer staffing that follows the arrival curve)."""
    A, sh = base["arrivals_per_day"], np.array(base["shift_share"])
    w = sh ** x["md_alpha"]
    md = np.maximum(2, np.round(A * x["md_hpv"] / 24.0 * w / w.mean())).astype(int).tolist()
    tri_n = min(base["triage_levels_cal"][int(x["triage"])], base["n_triage_rooms"])
    w = sh ** x["rn_alpha"]
    rn = np.maximum(3, np.round((A * x["rn_hpv"] / 24.0 - tri_n) * w / w.mean())).astype(int).tolist()
    th = dict(md=md, rn=rn, triage=int(x["triage"]), split=int(x["split"]), enc_scale=float(x["enc_scale"]),
              reeval_scale=float(x["reeval_scale"]), los_factor=float(space["f_star"] * x["los_rel"]),
              ward_init=float(np.clip(space["occ_target"] * x["los_rel"], 0.5, 0.97)))   # warm start at the expected long-run occupancy
    for k in ("lab_scale", "nurse_care_scale", "patience_scale", "absence_rate", "boarding_los_penalty"):
        if k in x:
            th[k] = float(x[k])
    return th


def sample_population(rs, n: int, space: dict, mean=None, std=None, cat_p=None) -> list[dict]:
    lo, hi = space["lo"], space["hi"]
    out = []
    if mean is None:                                # Latin hypercube over the box
        cols = {k: (rs.permutation(n) + rs.uniform(size=n)) / n for k in lo}
        for i in range(n):
            x = {k: lo[k] + (hi[k] - lo[k]) * cols[k][i] for k in lo}
            for c, m in space["cats"].items():
                x[c] = int(rs.randint(0, m))
            out.append(x)
        return out
    for i in range(n):
        x = {k: float(np.clip(rs.normal(mean[k], std[k]), lo[k], hi[k])) for k in lo}
        for c, m in space["cats"].items():
            x[c] = int(rs.choice(m, p=cat_p[c]))
        out.append(x)
    return out


def sim_row(metrics: dict, i: int) -> dict:
    return {k: float(v[i]) for k, v in metrics["pooled"].items()}


def penalised_loss(T: dict, row: dict) -> float:
    v = TG.loss(T, row)
    if any(math.isnan(row.get(k, 0.0)) for k in ("los_dc_median", "wait_median")):
        v += 1e6
    return v


# ------------------------------------------------------------------------------------------------
# stage 1: fit
# ------------------------------------------------------------------------------------------------
def fit(hid: str, device: str, pop: int, n_seeds: int, gens: int, days: int, warm: int, seed: int = 0) -> dict:
    t00 = time.time()
    base = H.base_values(hid)
    T = TG.collect_targets(hid)
    roster = TG.roster(hid)
    space = search_space(base, T, roster)
    rs = np.random.RandomState(seed)
    seeds = list(range(FIT_SEED, FIT_SEED + n_seeds))
    eq = H.equivalence_check(hid, dict(md=[max(2, m - 1) for m in base["base_theta"]["md"]], enc_scale=1.13, reeval_scale=1.4,
                                       los_factor=space["f_star"], ward_init=0.8, triage=0, split=0), days=2, device=device, base=base)
    print(f"[{hid}] harness vs ordinary loader identical: {eq['identical']} ({eq['patients']:.0f} patients)", flush=True)
    archive, history = [], []
    mean = std = cat_p = None
    for g in range(gens):
        xs = sample_population(rs, pop, space, mean, std, cat_p)
        if archive:                                  # carry the incumbents (same seeds, so they score the same)
            xs[:8] = [a["x"] for a in sorted(archive, key=lambda a: a["loss"])[:8]]
        thetas = [to_theta(x, base, space) for x in xs]
        r = H.evaluate(hid, thetas, seeds, days, warm, device, base, progress=f"[{hid}] fit gen {g + 1}/{gens}")
        for i, x in enumerate(xs):
            row = sim_row(r, i)
            archive.append(dict(x=x, theta=r["concs"][i]["theta"], sim=row, loss=penalised_loss(T, row), gen=g))
        archive.sort(key=lambda a: a["loss"])
        elite = archive[:max(12, pop // 10)]
        mean = {k: float(np.mean([e["x"][k] for e in elite])) for k in CONT}
        std = {k: float(max(1.25 * np.std([e["x"][k] for e in elite]), 0.03 * (space["hi"][k] - space["lo"][k]))) for k in CONT}
        cat_p = {}
        for c, m in space["cats"].items():
            cnt = np.array([sum(1 for e in elite if e["x"][c] == j) for j in range(m)], dtype=float) + 0.08 * len(elite)
            cat_p[c] = (cnt / cnt.sum()).tolist()
        b = archive[0]
        history.append(dict(gen=g, best_loss=b["loss"], elite_mean=mean, elite_std=std, cat_p=cat_p, wall=r["wall"],
                            n_inside=sum(1 for a in archive if a["gen"] == g and TG.accepted(T, a["sim"]))))
        print(f"[{hid}] gen {g + 1}: best loss {b['loss']:.2f}  md {b['theta']['md']} rn {b['theta']['rn']} tri {b['theta']['triage']} "
              f"split {b['theta']['split']}  ED time {b['sim']['los_dc_median']:.0f}  LWBS {100 * b['sim']['lwbs_rate']:.2f}%  occ "
              f"{b['sim']['ward_occupancy']:.3f}  p90 wait {b['sim']['wait_p90']:.0f}  inside this gen {history[-1]['n_inside']}/{pop}", flush=True)
    # ---- re-score the best distinct candidates on fresh seeds (guards against a lucky winner)
    top, seen = [], set()
    for a in archive:
        key = json.dumps(H.concrete(a["theta"], base), sort_keys=True)
        if key not in seen:
            seen.add(key)
            top.append(a)
        if len(top) >= 16:
            break
    rseeds = list(range(REFINE_SEED, REFINE_SEED + max(24, 3 * n_seeds)))
    r = H.evaluate(hid, [a["theta"] for a in top], rseeds, days + 10, warm, device, base, progress=f"[{hid}] re-score")
    for i, a in enumerate(top):
        a["sim_refine"] = sim_row(r, i)
        a["loss_refine"] = penalised_loss(T, a["sim_refine"])
    top.sort(key=lambda a: a["loss_refine"])
    best = top[0]
    print(f"[{hid}] winner on fresh seeds: loss {best['loss_refine']:.2f} (search-seed loss {best['loss']:.2f})", flush=True)
    out = dict(hospital_id=hid, generated=_dt.datetime.now().isoformat(timespec="seconds"), device=device,
               settings=dict(pop=pop, seeds=n_seeds, gens=gens, days=days, warm=warm, fit_seed=FIT_SEED, refine_seed=REFINE_SEED,
                             refine_seeds=len(rseeds), refine_days=days + 10),
               targets=TG.as_dicts(T), roster=roster, space=space, base=base, equivalence=eq, history=history,
               best=dict(x=best["x"], theta=best["theta"], conc=H.concrete(best["theta"], base), sim_search=best["sim"],
                         sim_refine=best["sim_refine"], loss_search=best["loss"], loss_refine=best["loss_refine"]),
               top=[dict(x=a["x"], theta=a["theta"], loss=a["loss"], loss_refine=a["loss_refine"], sim=a["sim_refine"]) for a in top],
               archive=[dict(x=a["x"], theta=a["theta"], loss=a["loss"], gen=a["gen"],
                             sim={k: a["sim"][k] for k in list(T) + ["wait_p90", "wait_mean", "md_utilization", "rn_utilization"] if k in a["sim"]})
                        for a in archive[:400]],
               n_evaluated=len(archive), wall_seconds=time.time() - t00)
    save_json(report_dir(hid) / "fit.json", out)
    write_calibration(hid, out)
    return out


# ------------------------------------------------------------------------------------------------
# calibration file
# ------------------------------------------------------------------------------------------------
_SCN_CACHE: dict = {}


def _attr_node(hid: str, path: str) -> dict:
    """The uncalibrated catalog node behind a dotted path (for its tag, unit and distribution)."""
    from sim import load_scenario
    if hid not in _SCN_CACHE:
        _SCN_CACHE[hid] = load_scenario(H.SCENARIO, overrides={"hospital_id": hid, "no_calibration": True})
    parts = path.split(".")
    if parts[0] == "hospital":
        return _SCN_CACHE[hid].attr("hospital", None, parts[1], required=False) or {}
    return _SCN_CACHE[hid].attr(parts[0], parts[1], parts[2], required=False) or {}


def write_calibration(hid: str, fitres: dict) -> Path:
    base, conc = fitres["base"], fitres["best"]["conc"]
    ov, acts = H.overrides_of(conc, base)
    cat = {}
    reasons = {
        "staff.shared.provider_levels": "Provider staffing ladder rebuilt around the fitted day / evening / night schedule.",
        "staff.shared.rn_levels": "Nurse staffing ladder rebuilt around the fitted day / evening / night schedule.",
        "staff.shared.triage_nurse_levels": "Triage staffing options resized to this hospital's arrival volume.",
        "hospital.ward_pool_los_factor": "Sets the ward pool's long-run occupancy to the hospital's published inpatient occupancy.",
        "hospital.ward_initial_occupancy": "Warm start at the pool's expected long-run occupancy so the first weeks are not a transient.",
        "provider_initial_min": "Assumed first-encounter time, scaled with the other free parameters to reproduce the hospital's ED time and LWBS.",
        "provider_reeval_min": "Assumed re-evaluation / disposition time, scaled to reproduce the hospital's median ED time of discharged patients."}
    for path, val in ov.items():
        node = _attr_node(hid, path)
        tag = node.get("source", "assumed" if not node else "?")
        if tag != "assumed":
            raise RuntimeError(f"refusing to calibrate {path}: tagged '{tag}', only 'assumed' attributes may be fitted")
        was = node.get("value")
        new = dict(value=val, source="assumed", calibrated=True, was=was,
                   citation=f"Fitted by twin/calibrate.py ({fitres['generated']}) so the default policy reproduces this hospital's published "
                            f"figures. {reasons.get(path, reasons.get(path.split('.')[-1], ''))} Was {was}. A model calibration, not a "
                            "statement about the real hospital.")
        if isinstance(node.get("dist"), dict):
            d = dict(node["dist"])
            if "mean" in d and isinstance(val, (int, float)):
                d["mean"] = val
            new["dist"] = d
        cat[path] = new
    doc = dict(
        hospital_id=hid, generated=fitres["generated"], generator="twin/calibrate.py",
        note="GENERATED - do not edit by hand. Loaded by sim/config.py::load_scenario after the hospital file. Only attributes tagged "
             "'assumed' are overridden; baseline_actions are this hospital's current-practice schedule (the action heads' defaults).",
        catalog_overrides=cat, baseline_actions={k: int(v) for k, v in acts.items()},
        schedule=dict(providers=dict(zip(["day", "evening", "night"], conc["md"])), nurses=dict(zip(["day", "evening", "night"], conc["rn"])),
                      triage_stations=int(min(conc["triage_levels"][conc["triage"]], base["n_triage_rooms"])),
                      provider_split=["favor_new", "balanced", "favor_dispositions"][conc["split"]]),
        theta=conc["theta"])
    path = CATALOG / "hospitals" / f"{hid}.calibration.yaml"
    H.atomic_write(path, "# GENERATED by `python -m twin.calibrate --hospital %s` - do not edit by hand.\n" % hid
                   + yaml.safe_dump(_jsonable(doc), sort_keys=False, width=140, default_flow_style=None))
    print(f"[{hid}] wrote {path.relative_to(ROOT)}", flush=True)
    return path


def repoint(hid: str, sets: dict, reason: str) -> dict:
    """Move the point calibration by setting theta entries by hand (documented in the report), e.g. after the held-out
    check shows the fitted point is not a steady state. Rewrites the calibration file and member 0 of the ensemble;
    run --stage check afterwards (it refreshes member 0's simulated fit)."""
    d = report_dir(hid)
    fitres = json.loads((d / "fit.json").read_text())
    base = fitres["base"]
    theta = dict(fitres["best"]["theta"])
    was = {k: theta.get(k) for k in sets}
    theta.update(sets)
    conc = H.concrete(theta, base)
    fitres["best"].update(theta=conc["theta"], conc=conc)
    fitres.setdefault("repoints", []).append(dict(when=_dt.datetime.now().isoformat(timespec="seconds"), set=sets, was=was, reason=reason))
    save_json(d / "fit.json", fitres)
    write_calibration(hid, fitres)
    efile = CATALOG / "hospitals" / f"{hid}.ensemble.json"
    if efile.exists():
        doc = json.loads(efile.read_text())
        ov, acts = H.overrides_of(conc, base, only_changed=False)
        doc["members"][0].update(overrides=ov, baseline_actions={k: int(v) for k, v in acts.items()}, theta=conc["theta"],
                                 search_round=-1, repointed=True)
        H.atomic_write(efile, json.dumps(_jsonable(doc), indent=1))
    return fitres


def _refresh_member0(hid: str, chk: dict) -> None:
    """Member 0 of the ensemble is the point calibration: keep its simulated fit equal to the held-out check."""
    efile = CATALOG / "hospitals" / f"{hid}.ensemble.json"
    if not efile.exists():
        return
    doc = json.loads(efile.read_text())
    T = TG.collect_targets(hid)
    a = chk["after"]["metrics"]
    m0 = doc["members"][0]
    m0["fit"] = {**m0.get("fit", {}), **{k: v["value"] for k, v in a.items()}}
    m0["inside"] = {k: bool(t.inside(a[k]["value"])) for k, t in T.items() if t.accept and k in a}
    m0["fit_source"] = "held-out check of the point calibration (twin/reports/%s/check.json)" % hid
    H.atomic_write(efile, json.dumps(_jsonable(doc), indent=1))


# ------------------------------------------------------------------------------------------------
# stage 2: held-out check, before / after, 60 days, through the ordinary loader
# ------------------------------------------------------------------------------------------------
def _summ(m: dict, T: dict) -> dict:
    """pooled value + 95 % interval of the mean over seeds for every simulated quantity."""
    out = {}
    n = m["n_seeds"]
    for k, v in m["pooled"].items():
        ps = np.asarray(m["per_seed"][k][0], dtype=float)
        ps = ps[~np.isnan(ps)]
        half = 1.96 * float(ps.std(ddof=1)) / math.sqrt(len(ps)) if len(ps) > 1 else float("nan")
        out[k] = dict(value=float(v[0]), ci=[float(v[0]) - half, float(v[0]) + half], seed_sd=float(ps.std(ddof=1)) if len(ps) > 1 else None,
                      seed_min=float(ps.min()) if len(ps) else None, seed_max=float(ps.max()) if len(ps) else None)
        if k in T:
            out[k]["share_of_seeds_inside"] = float(np.mean([T[k].inside(float(x)) for x in ps])) if len(ps) else None
    d = m["daily"]
    mean_b = lambda k: d[k][0].mean(1)   # noqa: E731  [days]
    days = len(mean_b("arrivals"))
    blk = max(1, days // 10)
    rows = []
    for i in range(0, days, blk):
        s = slice(i, min(days, i + blk))
        f = lambda k: float(mean_b(k)[s].mean())   # noqa: E731
        rows.append(dict(days=f"{i}-{min(days, i + blk) - 1}", arrivals=f("arrivals"),
                         wait_mean=float(mean_b("door_to_provider_sum_min")[s].sum() / max(1e-9, mean_b("first_seen")[s].sum())),
                         wait_p95_24h=f("wait_p95_min"), ed_los_median_24h=f("ed_los_median_min"),
                         lwbs=float(mean_b("lwbs")[s].sum() / max(1e-9, mean_b("arrivals")[s].sum())), admissions=f("admissions"),
                         boarding_hours=f("boarding_hours"), ward_occupancy=f("ward_occupancy"), bay_occupancy=f("bay_occupancy"),
                         cost=f("cost_total"), margin=f("revenue") - f("cost_total")))
    half = days // 2
    occ = d["ward_occupancy"][0]                                  # [days, seeds]
    stat = dict(rows=rows,
                halves=dict(ward_occupancy=[float(occ[:half].mean()), float(occ[half:].mean())],
                            boarding_hours=[float(d["boarding_hours"][0][:half].mean()), float(d["boarding_hours"][0][half:].mean())],
                            lwbs=[float(d["lwbs"][0][:half].sum() / d["arrivals"][0][:half].sum()), float(d["lwbs"][0][half:].sum() / d["arrivals"][0][half:].sum())],
                            wait_mean=[float(d["door_to_provider_sum_min"][0][:half].sum() / d["first_seen"][0][:half].sum()),
                                       float(d["door_to_provider_sum_min"][0][half:].sum() / d["first_seen"][0][half:].sum())]),
                last_10_days=dict(ward_occupancy=float(occ[-10:].mean()), boarding_hours=float(d["boarding_hours"][0][-10:].mean())),
                worst_day=dict(ward_occupancy=float(mean_b("ward_occupancy").max()), boarding_hours=float(mean_b("boarding_hours").max()),
                               lwbs=float((mean_b("lwbs") / np.maximum(mean_b("arrivals"), 1e-9)).max())),
                worst_single_hospital_day=dict(ward_occupancy=float(occ.max()), boarding_hours=float(d["boarding_hours"][0].max())),
                conservation_residual=m["conservation_residual"], pool_overflow=m["pool_overflow"])
    return dict(metrics=out, stationarity=stat, n_seeds=n, days=m["days"], warm=m["warm"], wall=m["wall"])


def check(hid: str, device: str, n_seeds: int, days: int, warm: int) -> dict:
    base = H.base_values(hid)
    T = TG.collect_targets(hid)
    seeds = list(range(CHECK_SEED, CHECK_SEED + n_seeds))
    cfile = CATALOG / "hospitals" / f"{hid}.calibration.yaml"
    if not cfile.exists():
        raise FileNotFoundError(f"{cfile} missing: run --stage fit first")
    cal = yaml.safe_load(cfile.read_text())
    before = H.evaluate_plain(hid, None, None, seeds, days, warm, device, base, no_calibration=True, progress=f"[{hid}] check: uncalibrated")
    after = H.evaluate_plain(hid, None, None, seeds, days, warm, device, base, no_calibration=False, progress=f"[{hid}] check: calibrated")
    eq = H.equivalence_check(hid, cal["theta"], days=3, device=device, base=base)
    out = dict(hospital_id=hid, generated=_dt.datetime.now().isoformat(timespec="seconds"), device=device,
               seeds=[seeds[0], seeds[-1]], days=days, warm=warm, before=_summ(before, T), after=_summ(after, T), equivalence=eq)
    save_json(report_dir(hid) / "check.json", out)
    _refresh_member0(hid, out)
    a = out["after"]["metrics"]
    for k, t in T.items():
        if k in a:
            print(f"[{hid}] held-out {t.label:50s} target {TG.fmt(t, t.value):>9s}  before {TG.fmt(t, out['before']['metrics'][k]['value']):>9s}"
                  f"  after {TG.fmt(t, a[k]['value']):>9s}  {t.verdict(a[k]['value'])}", flush=True)
    return out


# ------------------------------------------------------------------------------------------------
# stage 4: report
# ------------------------------------------------------------------------------------------------
def render_report(hid: str) -> str:
    d = report_dir(hid)
    fitres = json.loads((d / "fit.json").read_text())
    chk = json.loads((d / "check.json").read_text()) if (d / "check.json").exists() else None
    ens_f = CATALOG / "hospitals" / f"{hid}.ensemble.json"
    ens = json.loads(ens_f.read_text()) if ens_f.exists() else None
    T = TG.collect_targets(hid)
    base, best, sp, st = fitres["base"], fitres["best"], fitres["space"], fitres["settings"]
    conc = best["conc"]
    L = []
    A = L.append
    pct = lambda x: f"{100 * x:.1f} %"   # noqa: E731
    A(f"# Calibration report: {base['label']} (`{hid}`)\n")
    A("Generated by `python -m twin.calibrate` - do not edit by hand. **Every number in the \"simulated\" columns is SIMULATED**; the "
      "targets are the hospital's published figures or national survey tables. This is a model built from public data, not the "
      "hospital's operational data.\n")
    A("## What was done\n")
    A(f"The simulator's default policy (the fixed roster a manager would get if they changed nothing) was fitted so that it reproduces "
      f"this hospital's own published figures. Only catalog attributes tagged `assumed` and the baseline schedule were changed; measured "
      f"and literature values were left alone. Search: {st['gens']} generations x {st['pop']} candidates x {st['seeds']} seeds "
      f"({fitres['n_evaluated']} candidates, {st['days'] - st['warm']} simulated days each after a {st['warm']}-day warm-up, common random "
      f"numbers), best {len(fitres['top'])} re-scored on {st['refine_seeds']} fresh seeds, winner checked on held-out seeds below. "
      f"Wall time of the search {fitres['wall_seconds'] / 60:.0f} min on `{fitres['device']}`.\n")
    for rp in fitres.get("repoints", []):
        A(f"**Point moved after the search ({rp['when']}):** " + ", ".join(f"`{k}` {rp['was'][k]:.4g} -> {v:.4g}" for k, v in rp["set"].items())
          + f". {rp['reason']}\n")
    eq = (chk or fitres)["equivalence"]
    A(f"Search harness check: the same candidate run through the batched search harness and through the ordinary scenario loader gave "
      f"{'IDENTICAL' if eq['identical'] else 'DIFFERENT'} trajectories ({eq['patients']:.0f} patients, {eq['days']} days).\n")

    # ---- targets
    A("## Targets vs simulated, held-out seeds\n")
    if chk:
        b, a = chk["before"]["metrics"], chk["after"]["metrics"]
        A(f"{chk['after']['n_seeds']} hospitals (seeds {chk['seeds'][0]}..{chk['seeds'][1]}, never used in the search), {chk['days']} days, "
          f"first {chk['warm']} discarded, default actions, through `load_scenario` exactly as every other consumer loads the hospital. "
          "Brackets: 95 % interval of the mean over seeds. \"Before\" = the catalog without the calibration file.\n")
        for scope, title in (("hospital", "This hospital's own published figures"), ("stationarity", "Steady state (a model requirement)"),
                             ("input", "Inputs (checks, not tests)"),
                             ("national", "National survey shape (soft priors - they describe other hospitals)")):
            ts = [t for t in T.values() if t.scope == scope and t.key in a]
            if not ts:
                continue
            A(f"### {title}\n")
            A("| Measure | Published | Acceptance interval | Simulated before | Simulated after | After: verdict | Seeds inside |\n|---|---|---|---|---|---|---|")
            for t in ts:
                va, vb = a[t.key], b[t.key]
                ci = f" [{TG.fmt(t, va['ci'][0])} .. {TG.fmt(t, va['ci'][1])}]" if va["ci"][0] is not None else ""
                si = va.get("share_of_seeds_inside")
                A(f"| {t.label} | {TG.fmt(t, t.value)} | {TG.fmt(t, t.lo)} .. {TG.fmt(t, t.hi)} | {TG.fmt(t, vb['value'])} ({t.verdict(vb['value'])}) | "
                  f"{TG.fmt(t, va['value'])}{ci} | **{t.verdict(va['value'])}** | {'' if si is None else f'{100 * si:.0f} %'} |")
            A("")
        A("Where each target comes from and how its interval was set:\n")
        for t in T.values():
            A(f"- **{t.label}** ({t.scope}; fit weight {t.weight:g}): {t.source}. {t.note}")
        A("")
        g = lambda k, w=a: w[k]["value"]   # noqa: E731
        A("Other simulated outputs of the calibrated baseline (held-out seeds): "
          f"mean wait {g('wait_mean'):.1f} min (before {g('wait_mean', b):.1f}), 90th percentile wait {g('wait_p90'):.0f} min (before {g('wait_p90', b):.0f}), "
          f"95th {g('wait_p95'):.0f} min, 90th percentile ED time of discharged patients {g('los_dc_p90'):.0f} min, boarding "
          f"{g('boarding_hours_per_day'):.0f} patient-hours/day (before {g('boarding_hours_per_day', b):.0f}), provider utilisation "
          f"{g('md_utilization'):.2f} (before {g('md_utilization', b):.2f}), nurse utilisation {g('rn_utilization'):.2f} (before {g('rn_utilization', b):.2f}), "
          f"bay occupancy {g('bay_occupancy'):.2f}, ED census {g('ed_census'):.0f}, provider-hours {g('provider_hours_per_day'):.0f}/day "
          f"({g('provider_hours_per_visit'):.2f} per visit), nurse-hours {g('rn_hours_per_day'):.0f}/day ({g('rn_hours_per_visit'):.2f} per visit), "
          f"labour cost with benefits {g('cost_labor_per_day') / 1e3:.0f} k$/day (before {g('cost_labor_per_day', b) / 1e3:.0f}), all-staff wages "
          f"without benefits {g('ed_salaries_all_per_day') / 1e3:.0f} k$/day, total cost {g('cost_per_day') / 1e3:.0f} k$/day, margin "
          f"{g('margin_per_day') / 1e3:.0f} k$/day, deaths {g('deaths_per_day'):.2f}/day.\n")
    else:
        A("(held-out check not run yet)\n")

    # ---- parameters
    A("## Fitted parameters (assumed attributes only)\n")
    A("| Attribute | Tag | Was | Now | Why |\n|---|---|---|---|---|")
    bt, th = base["base_theta"], conc["theta"]
    f2 = lambda xs: "/".join(f"{x:g}" for x in xs)   # noqa: E731
    A(f"| `staff.shared.provider_levels` (ladder lvl0..lvl4) | {base['sources']['provider_levels']} | {f2(base['provider_levels'])} | "
      f"{f2(conc['provider_levels'])} | Rebuilt so the fitted day / evening / night head-counts are ladder levels with one step of room "
      "either side for a manager. |")
    A(f"| `staff.shared.rn_levels` (ladder lvl0..lvl4) | {base['sources']['rn_levels']} | {f2(base['rn_levels'])} | {f2(conc['rn_levels'])} | "
      "Same, for floor nurses. |")
    A(f"| `patient.esi1..5.provider_initial_min` | {base['sources']['enc']} | {f2(base['enc'])} | {f2(conc['enc'])} | First clinician "
      f"encounter, scale x{th['enc_scale']:.2f}. No public source for this hospital; trades off against the number of providers. |")
    A(f"| `patient.esi1..5.provider_reeval_min` | {base['sources']['reeval']} | {f2(base['reeval'])} | {f2(conc['reeval'])} | Re-evaluation "
      f"and disposition, scale x{th['reeval_scale']:.2f}. Moves the back end of the stay (ED time) without moving the front-door wait (LWBS). |")
    A(f"| `hospital.ward_pool_los_factor` | {base['sources']['los_factor']} | {bt['los_factor']:g} | {conc['los_factor']:g} | Share of an "
      f"admission's stay spent in the modelled bed pool. {base['arrivals_per_day'] * base['admit_rate']:.0f} admissions/day x "
      f"{base['los_days']} days (both measured{', plus about 6 % more admissions from disposition errors' if sp.get('admit_uplift', 1.0) > 1 else ''}) against {base['ward_cap']} pool beds: "
      f"{sp['f_star']:.3f} would give the published occupancy with no queueing; the fit adjusts for boarding. |")
    A(f"| `hospital.ward_initial_occupancy` | {base['sources'].get('ward_init', 'assumed')} | {base['ward_init']:g} | {conc['ward_init']:g} | Warm start at "
      "the pool's expected long-run occupancy. |")
    A("")
    A("Left at the catalog value in the point calibration (varied in the ensemble): lab turnaround, nurse care minutes per patient-hour, "
      "LWBS patience, absence rate, boarding length-of-stay penalty.\n")
    for n in sp["notes"]:
        A(f"- {n}")
    A("")

    # ---- schedule
    A("## Baseline schedule (\"current practice\" = the action heads' defaults for this hospital)\n")
    cal = yaml.safe_load((CATALOG / "hospitals" / f"{hid}.calibration.yaml").read_text())
    acts = cal["baseline_actions"]
    share = base["shift_share"]
    A("| Shift | Arrival share (x mean) | Providers was | Providers now | Nurses was | Nurses now |\n|---|---|---|---|---|---|")
    for j, nm in enumerate(["Day 07-15", "Evening 15-23", "Night 23-07"]):
        A(f"| {nm} | {share[j]:.2f} | {bt['md'][j]} | {conc['md'][j]} (lvl{acts[H.SHIFT_HEADS_MD[j]]}) | {bt['rn'][j]} | {conc['rn'][j]} (lvl{acts[H.SHIFT_HEADS_RN[j]]}) |")
    A("")
    x = best["x"]
    A(f"Triage stations staffed: {cal['schedule']['triage_stations']} (`triage_nurses` default {acts['triage_nurses']}, was "
      f"{base['defaults']['triage_nurses']}). Provider split: `{cal['schedule']['provider_split']}` (default {acts['provider_split']}, was "
      f"{base['defaults']['provider_split']}). Shape exponents fitted: providers {x['md_alpha']:.2f}, nurses {x['rn_alpha']:.2f} "
      f"(1 = proportional to arrivals, 0 would be the same on every shift; searched over {sp['lo']['md_alpha']:g}-1). All other heads keep the defaults of `contracts/actions.yaml`.\n")
    A("`sim.default_actions()` and the `fixed` manager now ARE this schedule for this hospital "
      "(`catalog/hospitals/%s.calibration.yaml: baseline_actions`).\n" % hid)

    # ---- stationarity
    if chk:
        s = chk["after"]["stationarity"]
        A(f"## Stationarity over {chk['days']} days (calibrated baseline, means across {chk['after']['n_seeds']} held-out hospitals, nothing discarded)\n")
        A("| Days | Arrivals/day | Mean wait (min) | p95 wait, trailing 24 h | Median ED time, all departures | LWBS % | Admissions/day | "
          "Boarding pt-h/day | Ward occupancy | Bay occupancy | Cost k$/day | Margin k$/day |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in s["rows"]:
            A(f"| {r['days']} | {r['arrivals']:.0f} | {r['wait_mean']:.1f} | {r['wait_p95_24h']:.0f} | {r['ed_los_median_24h']:.0f} | {100 * r['lwbs']:.2f} | "
              f"{r['admissions']:.1f} | {r['boarding_hours']:.1f} | {r['ward_occupancy']:.3f} | {r['bay_occupancy']:.3f} | {r['cost'] / 1e3:.0f} | {r['margin'] / 1e3:.0f} |")
        h = s["halves"]
        A("")
        A(f"First half vs second half: ward occupancy {h['ward_occupancy'][0]:.3f} vs {h['ward_occupancy'][1]:.3f}; boarding "
          f"{h['boarding_hours'][0]:.1f} vs {h['boarding_hours'][1]:.1f} patient-hours/day; mean wait {h['wait_mean'][0]:.1f} vs "
          f"{h['wait_mean'][1]:.1f} min; LWBS {100 * h['lwbs'][0]:.2f} vs {100 * h['lwbs'][1]:.2f} %. Last 10 days: occupancy "
          f"{s['last_10_days']['ward_occupancy']:.3f}, boarding {s['last_10_days']['boarding_hours']:.1f} pt-h/day. Worst day (mean across "
          f"hospitals): occupancy {s['worst_day']['ward_occupancy']:.3f}, boarding {s['worst_day']['boarding_hours']:.0f} pt-h, LWBS "
          f"{100 * s['worst_day']['lwbs']:.1f} %. Worst single hospital-day: occupancy {s['worst_single_hospital_day']['ward_occupancy']:.3f}, "
          f"boarding {s['worst_single_hospital_day']['boarding_hours']:.0f} pt-h. Conservation residual {s['conservation_residual']}, pool "
          f"overflow {s['pool_overflow']}.\n")
        drift = h["ward_occupancy"][1] - h["ward_occupancy"][0]
        # a baseline is steady only if the ED outcomes are too: occupancy can sit still while boarding snowballs
        grow = [k for k, lim in (("lwbs", 1.3), ("wait_mean", 1.3), ("boarding_hours", 2.0))
                if h[k][1] > lim * max(h[k][0], 1e-9) and (k != "boarding_hours" or h[k][1] > 30.0)]
        A(f"Reading: occupancy moves {100 * drift:+.1f} points between halves"
          + (" - no sustained fill. " if abs(drift) < 0.02 else " - CHECK: this is more than 2 points. ")
          + ("Walk-outs, waits and boarding are steady across the two halves: this baseline is a steady state.\n" if not grow else
             "**NOT A STEADY STATE: " + ", ".join(grow) + " grow from the first half to the second.** Boarding lengthens inpatient stays "
             "(literature penalty), which fills the pool further; at this occupancy the feedback runs away. A baseline that is still "
             "deteriorating cannot stand for a hospital's published annual figures - lower the pool's load (`--stage repoint`).\n"))

    # ---- ensemble
    A("## Ensemble: the twins consistent with the public record\n")
    if ens:
        mem = ens["members"]
        A(f"`catalog/hospitals/{hid}.ensemble.json` holds {len(mem)} parameter sets. Member 0 is the point calibration above. Each of the "
          f"others was drawn from the plausible ranges of the parameters public data does not pin down and KEPT ONLY IF the simulated "
          f"baseline stays inside every hospital-specific acceptance interval on the held-out seeds. {ens['search']['description']}\n")
        A("Spread of the hospital-specific targets and other outputs across members (held-out seeds):\n")
        A("| Simulated quantity | Member 0 | Min | Median | Max | Acceptance interval |\n|---|---|---|---|---|---|")
        keys = [k for k in T if k in mem[0]["fit"]] + [k for k in ["wait_mean", "wait_p90", "boarding_hours_per_day", "md_utilization", "rn_utilization",
                                                                 "cost_labor_per_day", "margin_per_day"] if k in mem[0]["fit"] and k not in T]
        for k in keys:
            v = np.array([m["fit"][k] for m in mem], dtype=float)
            t = T.get(k)
            f = (lambda z: TG.fmt(t, z)) if t else (lambda z: f"{z / 1e3:.0f} k$" if abs(z) > 5000 else (f"{z:.2f}" if abs(z) < 5 else f"{z:.0f}"))   # noqa: E731
            A(f"| {t.label if t else k} | {f(v[0])} | {f(np.nanmin(v))} | {f(np.nanmedian(v))} | {f(np.nanmax(v))} | "
              f"{(f(t.lo) + ' .. ' + f(t.hi)) if t else ''} |")
        A("")
        A("Spread of the parameters across members:\n")
        A("| Parameter | Tag | Member 0 | Min | Max | Range sampled | Where the range comes from |\n|---|---|---|---|---|---|---|")
        for pr in ens["parameters"]:
            v = np.array([m["theta"].get(pr["key"], m["derived"].get(pr["key"])) if not isinstance(m["theta"].get(pr["key"]), list)
                          else m["derived"][pr["key"]] for m in mem], dtype=float)
            A(f"| {pr['label']} | {pr['tag']} | {v[0]:.3g} | {v.min():.3g} | {v.max():.3g} | {pr['lo']:.3g} .. {pr['hi']:.3g} | {pr['why']} |")
        A("")
        A("How to read it: every member is a hospital that public data cannot tell apart from this one. A policy that improves a metric on "
          "member 0 only is fitted to one guess; a policy that improves it on all members is robust to what we do not know.\n")
    else:
        A("(ensemble not generated yet)\n")

    # ---- cannot tell
    A("## What public data cannot tell us\n")
    A("- **How many clinicians are actually on the floor, by shift.** No public source lists an ED's schedule. The schedule above is the one "
      "that, in this model, reproduces the published ED time and LWBS. Fewer providers who each work faster, or more who each work slower, "
      "fit the same figures (see the ensemble's spread of providers against encounter time).")
    A("- **How long a clinician spends per patient here.** The encounter and re-evaluation times are assumed everywhere and fitted here; "
      "they are identified only jointly with staffing.")
    if "ed_salaries_per_day" in T:
        A("- **Who is inside the ED salary line.** The cost report gives one number for the ED cost centre. Whether employed physicians, "
          "APPs, or agency staff are in it is not stated, and it counts paid hours, not worked hours. The nurse roster is set from that "
          "number, so it is uncertain by roughly the width of the salary interval; patient flow barely constrains it.")
    A("- **Nursing workload per patient.** Nurse minutes per patient-hour are assumed. With the roster implied by the salary bill, nurses "
      "are rarely the binding resource in the model; in the real department they may be.")
    A("- **Which beds ED admissions actually compete for.** The published occupancy is the annual average over all inpatient beds. The "
      "model has one pool; elective and transfer admissions, unit mismatch (ICU vs ward) and time-of-day discharge patterns are not in it. "
      "Boarding is therefore the least certain output of the baseline.")
    A("- **How patient this hospital's patients are.** LWBS is published as a whole percent. With the literature patience values, that "
      "figure by itself forces short front-door waits. If patients here tolerate longer waits than the literature study's, the same LWBS "
      "is consistent with a longer wait tail. The ensemble spans this; the point calibration uses the literature value.")
    A("- **The wait distribution itself.** No hospital-level wait percentiles are published. The 90th-percentile targets are a national "
      "survey that pools hospitals, so they also contain between-hospital spread.")
    A("- **ED admissions per day.** Derived from national admission probabilities by acuity, not from this hospital.")
    attrs, _ = TG.hospital_attrs(hid)
    for key, what in (("ed_visits_per_year_cms", "What the published visit count covers"), ("inpatient_occupancy", "What the published occupancy covers"),
                      ("ed_treatment_spaces", "How many treatment spaces the ED has"), ("em_apps", "How many advanced practice providers work in the ED")):
        note = str((attrs.get(key) or {}).get("note") or "").strip()
        if note:
            A(f"- **{what}** (`{key}`, from the data build): {' '.join(note.split())}"
              + (" The twin models the visits as ONE emergency department; if the count spans campuses, the real main-campus ED is smaller "
                 "than the twin and every per-day figure here is for the combined volume." if key == "ed_visits_per_year_cms" and "campus" in note else ""))
    A("- **Acuity and case mix of this hospital**, arrival pattern by hour (national survey shape scaled to the hospital's annual visits), "
      "and day-to-day surges beyond Poisson variation.")
    A("")
    A("## Residuals not closed\n")
    if chk:
        res = [t for t in T.values() if t.key in chk["after"]["metrics"] and not t.inside(chk["after"]["metrics"][t.key]["value"]) and t.scope != "input"]
        if not res:
            A("None: every target is inside its interval on held-out seeds.\n")
        for t in res:
            v = chk["after"]["metrics"][t.key]["value"]
            A(f"- **{t.label}** ({t.scope}): simulated {TG.fmt(t, v)}, published {TG.fmt(t, t.value)} (interval {TG.fmt(t, t.lo)} .. {TG.fmt(t, t.hi)}). "
              + ("The front-door wait tail stays thinner than the national survey's. With the literature patience values, a tail that long "
                 "would put LWBS well above this hospital's published figure, so the two cannot both be met without changing a literature "
                 "value; the hospital's own figure was given priority. " if t.key.startswith("wait_p90") else "")
              + ("Not fitted harder because it is a national prior, not this hospital's value." if t.scope == "national" else
                 "Hospital-specific and still outside: assumed parameters alone did not close it."))
        A("")
    A("## Files\n")
    A(f"- `catalog/hospitals/{hid}.calibration.yaml` - fitted assumed attributes + `baseline_actions` (loaded automatically by `load_scenario`; "
      "`overrides={'no_calibration': True}` skips it).")
    A(f"- `catalog/hospitals/{hid}.ensemble.json` - the ensemble (shape documented at the top of `twin/ensemble.py`).")
    A(f"- `twin/reports/{hid}/fit.json`, `check.json`, `ensemble_run.json` - raw numbers behind this report.")
    return "\n".join(L) + "\n"


def write_report(hid: str) -> Path:
    p = report_dir(hid) / "CALIBRATION.md"
    H.atomic_write(p, render_report(hid))
    print(f"[{hid}] wrote {p.relative_to(ROOT)}", flush=True)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hospital", default="rwjuh_nb")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--stage", default="all", choices=["all", "fit", "check", "ensemble", "report", "repoint"])
    ap.add_argument("--set", nargs="*", default=[], help="repoint: theta entries, e.g. los_factor=0.85 ward_init=0.85")
    ap.add_argument("--reason", default="", help="repoint: why (printed in the report)")
    ap.add_argument("--pop", type=int, default=192)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--gens", type=int, default=5)
    ap.add_argument("--days", type=int, default=44, help="simulated days per candidate (including warm-up)")
    ap.add_argument("--warm", type=int, default=7)
    ap.add_argument("--check-seeds", type=int, default=64)
    ap.add_argument("--check-days", type=int, default=60)
    ap.add_argument("--members", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0, help="seed of the search's own random numbers")
    a = ap.parse_args()
    if a.stage in ("all", "fit"):
        fit(a.hospital, a.device, a.pop, a.seeds, a.gens, a.days, a.warm, a.seed)
    if a.stage == "repoint":
        repoint(a.hospital, {k: float(v) for k, v in (x.split("=") for x in a.set)}, a.reason)
    if a.stage in ("all", "check", "repoint"):
        check(a.hospital, a.device, a.check_seeds, a.check_days, a.warm)
    if a.stage in ("all", "ensemble"):
        from twin import ensemble as EN
        EN.build(a.hospital, a.device, members=a.members, n_seeds=a.seeds, days=a.days, warm=a.warm, check_seeds=min(32, a.check_seeds), rounds=3)
    if a.stage in ("all", "report", "check", "ensemble", "repoint"):
        write_report(a.hospital)


if __name__ == "__main__":
    main()
