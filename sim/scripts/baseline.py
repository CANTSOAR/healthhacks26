"""Baseline / validation / stationarity run. Regenerates sim/BASELINE.md.

    .venv/bin/python -m sim.scripts.baseline --days 60                 # local, small batch (slow: ~8 ms per tick)
    .venv/bin/python -m sim.scripts.baseline --days 60 --batch 16      # deepstack CPU
    .venv/bin/python -m sim.scripts.baseline --from-json sim/scripts/baseline_60d.json --write   # re-render a saved run
    add --write to overwrite sim/BASELINE.md, --json PATH to keep the raw numbers.

One run with default actions (the fixed roster). Hourly metrics come from step(); the discharged-only
ED time and the wait percentiles are collected by reading the patient tensors after every tick.
All numbers are simulated. Validation targets are read from catalog/validation_targets.yaml and are
never simulator inputs.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim import HospitalSim, load_scenario  # noqa: E402

DAY_KEYS = ["arrivals", "first_seen", "door_to_provider_sum_min", "lwbs", "admissions", "boarding_hours", "deaths",
            "deteriorations", "adverse_events", "cost_total", "cost_labor", "cost_fixed", "cost_variable", "revenue"]
INST_KEYS = ["ward_occupancy", "bay_occupancy", "md_utilization", "rn_utilization", "fatigue_mean", "ed_census", "staff_on_shift"]


def run(scenario="normal_week", days=60, batch=4, warm=3, device="cpu", seed=100000, overrides=None, progress=True):
    sim = HospitalSim(load_scenario(scenario, overrides=overrides or {}), batch_size=batch, device=device, seed=seed)
    p = sim.p
    daily, los_dc, los_acu, waits, wait_acu = [], [], [], [], []
    t0 = time.time()
    for d in range(days):
        tot = {k: 0.0 for k in DAY_KEYS}
        inst = {k: 0.0 for k in INST_KEYS}
        for _ in range(24):
            acts = sim.default_actions()
            for i in range(sim.ticks_per_step):
                sim.tick(acts if i == 0 else None)
                if d >= warm:
                    t = sim._tick - 1
                    ex = p["active"] & (p["state"] == 11) & (p["exit"] == 1)
                    los_dc.append(((t - p["t_arr"])[ex] * sim.tick_minutes).float().cpu())
                    los_acu.append(p["acu_q"][ex].cpu())
                    sn = p["active"] & (p["t_seen"] == t)
                    waits.append(((t - p["t_arr"])[sn] * sim.tick_minutes).float().cpu())
                    wait_acu.append(p["acu_q"][sn].cpu())
            m = sim.metrics_last_hour()
            for k in DAY_KEYS:
                tot[k] += float(m[k].mean())
            for k in INST_KEYS:
                inst[k] += float(m[k].mean()) / 24
        row = dict(day=d, **{k: tot[k] for k in DAY_KEYS}, **inst,
                   wait_mean=tot["door_to_provider_sum_min"] / max(tot["first_seen"], 1e-9),
                   wait_p95_24h=float(m["wait_p95_min"].mean()), ed_los_median_24h=float(m["ed_los_median_min"].mean()),
                   lwbs_rate=tot["lwbs"] / max(tot["arrivals"], 1e-9))
        daily.append(row)
        if progress:
            print(f"day {d:3d} wait {row['wait_mean']:6.1f} lwbs {100 * row['lwbs_rate']:5.2f}% ward {row['ward_occupancy']:.3f} "
                  f"boarding {row['boarding_hours']:6.1f}  [{time.time() - t0:6.0f}s]", flush=True)
    los_dc, los_acu, waits, wait_acu = torch.cat(los_dc), torch.cat(los_acu), torch.cat(waits), torch.cat(wait_acu)
    post = daily[warm:]
    n = max(1, len(post))
    mean = lambda k: sum(r[k] for r in post) / n   # noqa: E731
    by = lambda vals, acu: [float(vals[acu == a].median()) if bool((acu == a).any()) else None for a in range(1, 6)]   # noqa: E731
    cons = sim.conservation()
    return dict(
        meta=dict(scenario=scenario, days=days, batch=batch, warm_days=warm, device=device, seed=seed, torch=torch.__version__,
                  machine=platform.machine(), wall_seconds=round(time.time() - t0, 1), layout=sim.scn.layout_source,
                  fallback_keys=sim.scn.fallback_keys),
        daily=daily,
        summary={k: float(v.mean()) for k, v in sim.episode_summary().items()},
        means={k: float(v.mean()) for k, v in sim.episode_means().items()},
        validation=dict(
            arrivals_per_day=mean("arrivals"), admit_rate=mean("admissions") / mean("arrivals"), lwbs_rate=mean("lwbs") / mean("arrivals"),
            wait_mean=sum(r["door_to_provider_sum_min"] for r in post) / max(1e-9, sum(r["first_seen"] for r in post)),
            wait_median=float(waits.median()), wait_p90=float(waits.quantile(0.9)), wait_p95=float(waits.quantile(0.95)),
            wait_p90_by_acuity=[float(waits[wait_acu == a].quantile(0.9)) if bool((wait_acu == a).any()) else None for a in range(1, 6)],
            wait_median_by_acuity=by(waits, wait_acu), los_discharged_median=float(los_dc.median()),
            los_discharged_p90=float(los_dc.quantile(0.9)), los_discharged_median_by_acuity=by(los_dc, los_acu),
            boarding_hours_per_day=mean("boarding_hours"), deaths_per_day=mean("deaths"), deteriorations_per_day=mean("deteriorations"),
            adverse_events_per_day=mean("adverse_events"),
            cost_per_day=mean("cost_total"), cost_labor=mean("cost_labor"), cost_fixed=mean("cost_fixed"), cost_variable=mean("cost_variable"),
            revenue_per_day=mean("revenue"), **{k: mean(k) for k in INST_KEYS}),
        conservation_residual=int(cons["residual"].abs().max()), pool_overflow=int(cons["pool_overflow"].max()),
        P=sim.cfg)


def _targets():
    d = yaml.safe_load((ROOT / "catalog" / "validation_targets.yaml").read_text())["variants"]
    g = lambda v, k: d.get(v, {}).get("attributes", {}).get(k, {})   # noqa: E731
    return g


def verdict(x, lo, hi):
    return "inside" if lo <= x <= hi else ("OUTSIDE (too low)" if x < lo else "OUTSIDE (too high)")


def markdown(r: dict) -> str:
    m, v, P = r["meta"], r["validation"], r["P"]
    g = _targets()
    f1 = lambda xs: ", ".join("-" if x is None else f"{x:.0f}" for x in xs)   # noqa: E731
    L = []
    A = L.append
    A("# Baseline sanity: default actions (fixed roster)\n")
    A("Generated by `python -m sim.scripts.baseline` - do not edit by hand. All numbers are SIMULATED.\n")
    A(f"Run: scenario `{m['scenario']}`, {m['batch']} hospitals (seeds {m['seed']}..{m['seed'] + m['batch'] - 1}), {m['days']} days, "
      f"default actions every hour, device {m['device']}, torch {m['torch']} ({m['machine']}), wall time {m['wall_seconds']:.0f} s. "
      f"Layout `{m['layout']}`. Catalog keys taken from the fallback file: {m['fallback_keys'] or 'none'}.\n")
    A(f"## Result vs validation targets (`catalog/validation_targets.yaml`; days {m['warm_days']}..{m['days'] - 1}, the first {m['warm_days']} discarded)\n")
    A("| Measure | Simulated | Target | Verdict |\n|---|---|---|---|")
    t = g("rwjuh_nb", "median_ed_time_discharged_min")
    if t:
        A(f"| Median ED time, discharged patients | {v['los_discharged_median']:.0f} min | RWJUH CMS OP-18b {t['value']} min; very-high-volume peers "
          f"10th-90th pct {t['range'][0]:.0f}-{t['range'][1]:.0f} | {verdict(v['los_discharged_median'], *t['range'])} the peer range; "
          f"{v['los_discharged_median'] - t['value']:+.0f} min vs the hospital's own value |")
    t = g("rwjuh_nb", "lwbs_rate")
    if t:
        A(f"| LWBS share of arrivals | {100 * v['lwbs_rate']:.2f} % | RWJUH {100 * t['value']:.0f} % (published as a whole percent); peers "
          f"{100 * t['range'][0]:.0f}-{100 * t['range'][1]:.0f} % | {verdict(v['lwbs_rate'], *t['range'])} |")
    nh = "nhamcs_metro_teaching"
    t = g(nh, "wait_to_provider_median_min")
    if t:
        ta = g(nh, "wait_to_provider_median_min_by_acuity").get("value") or []
        A(f"| Median arrival-to-provider wait | {v['wait_median']:.0f} min (ESI 1..5: {f1(v['wait_median_by_acuity'])}) | NHAMCS metro teaching "
          f"{t['value']:.0f} min (by ESI {f1(ta)}) | within one 5-minute tick: {'yes' if abs(v['wait_median'] - t['value']) <= 5 else 'NO'} |")
    ta = g(nh, "wait_to_provider_p90_min_by_acuity").get("value")
    if ta:
        ok = all(s is not None and s >= 0.75 * x for s, x in zip(v["wait_p90_by_acuity"], ta))
        A(f"| 90th percentile wait | {v['wait_p90']:.0f} min overall (ESI 1..5: {f1(v['wait_p90_by_acuity'])}) | NHAMCS metro teaching by ESI {f1(ta)} | "
          f"{'comparable' if ok else 'OUTSIDE (too short) - see below'} |")
    ta = g(nh, "length_of_visit_discharged_median_min_by_acuity").get("value")
    if ta:
        A(f"| Median ED time, discharged, by ESI 1..5 | {f1(v['los_discharged_median_by_acuity'])} min | NHAMCS metro teaching {f1(ta)} | "
          f"differences {f1([None if s is None else s - x for s, x in zip(v['los_discharged_median_by_acuity'], ta)])} min |")
    ta = g(nh, "length_of_visit_discharged_p90_min_by_acuity").get("value")
    if ta:
        A(f"| 90th percentile ED time, discharged | {v['los_discharged_p90']:.0f} min | NHAMCS metro teaching by ESI {f1(ta)} | "
          f"{verdict(v['los_discharged_p90'], min(ta), max(ta))} that span |")
    t = g(nh, "admission_rate")
    if t:
        A(f"| Admission decisions / arrivals | {100 * v['admit_rate']:.1f} % | NHAMCS metro teaching {100 * t['value']:.1f} % | "
          f"{'close' if abs(v['admit_rate'] - t['value']) < 0.02 else 'differs'} (follows from measured p_admit) |")
    t = g("rwjuh_nb", "ed_visits_per_year")
    if t:
        A(f"| Arrivals per day | {v['arrivals_per_day']:.1f} | {t['value'] / 365:.0f} ({t['value']} / 365) | "
          f"{'close' if abs(v['arrivals_per_day'] - t['value'] / 365) < 8 else 'differs'} |")
    A("")
    A(f"Other outputs over the same days: mean wait {v['wait_mean']:.1f} min, p95 wait {v['wait_p95']:.0f} min, boarding "
      f"{v['boarding_hours_per_day']:.1f} patient-hours/day, bay occupancy {v['bay_occupancy']:.2f} (of staffed bays), ward-pool occupancy "
      f"{v['ward_occupancy']:.2f}, provider utilisation {v['md_utilization']:.2f}, nurse utilisation {v['rn_utilization']:.2f}, mean fatigue "
      f"{v['fatigue_mean']:.2f}, ED census {v['ed_census']:.0f}, staff on shift {v['staff_on_shift']:.0f}, deaths {v['deaths_per_day']:.2f}/day, "
      f"deteriorations {v['deteriorations_per_day']:.2f}/day, adverse events {v['adverse_events_per_day']:.2f}/day.")
    A(f"Money per day: cost {v['cost_per_day'] / 1e3:.0f} k USD (labour {v['cost_labor'] / 1e3:.0f} k, fixed {v['cost_fixed'] / 1e3:.0f} k, variable "
      f"{v['cost_variable'] / 1e3:.0f} k), revenue {v['revenue_per_day'] / 1e3:.0f} k, margin {(v['revenue_per_day'] - v['cost_per_day']) / 1e3:.0f} k.\n")
    A("### The 90th-percentile wait is outside the survey range (too short)\n")
    A("Stated plainly: the simulated upper tail of arrival-to-provider waits is much thinner than the national survey's. Likely reasons, "
      "none of them tested tonight: (1) the default roster has the same number of providers on all three shifts and never has an unfilled "
      "shift, so there is no chronically thin night or handover gap; (2) apart from Poisson arrivals, call-outs at the literature rate and rare "
      "scanner failures, nothing produces ED-wide bad days (no mass-casualty days, no hospital-wide bed crises: the ward pool runs near "
      f"{100 * v['ward_occupancy']:.0f} % with little boarding); (3) the survey pools many hospitals and seasons, so its tail also contains "
      "between-hospital variation that one simulated hospital cannot have; (4) providers in the model are interchangeable and always take the "
      "next patient the moment they are free. A manager that staffs leaner (the RL agent does) produces longer tails; the fixed baseline does not.\n")
    blk = max(1, m["days"] // 10)
    A(f"## Stationarity over {m['days']} days ({blk}-day means across the batch, nothing discarded)\n")
    A("| Days | Arrivals/day | Mean wait (min) | p95 wait, trailing 24 h | Median ED time, all departures | LWBS % | Admissions/day | "
      "Boarding pt-h/day | Ward occupancy | Bay occupancy | Cost k$/day | Margin k$/day |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    D = r["daily"]
    for i in range(0, len(D), blk):
        w = D[i:i + blk]
        f = lambda k: sum(x[k] for x in w) / len(w)   # noqa: E731
        A(f"| {i}-{i + len(w) - 1} | {f('arrivals'):.0f} | {f('wait_mean'):.1f} | {f('wait_p95_24h'):.0f} | {f('ed_los_median_24h'):.0f} | "
          f"{100 * f('lwbs_rate'):.2f} | {f('admissions'):.1f} | {f('boarding_hours'):.1f} | {f('ward_occupancy'):.3f} | {f('bay_occupancy'):.3f} | "
          f"{f('cost_total') / 1e3:.0f} | {(f('revenue') - f('cost_total')) / 1e3:.0f} |")
    half = len(D) // 2
    h1 = lambda k, a, b: sum(x[k] for x in D[a:b]) / max(1, b - a)   # noqa: E731
    A("")
    A(f"First half vs second half: ward occupancy {h1('ward_occupancy', 0, half):.3f} vs {h1('ward_occupancy', half, len(D)):.3f}; mean wait "
      f"{h1('wait_mean', 0, half):.1f} vs {h1('wait_mean', half, len(D)):.1f} min; LWBS {100 * h1('lwbs_rate', 0, half):.2f} vs "
      f"{100 * h1('lwbs_rate', half, len(D)):.2f} %; boarding {h1('boarding_hours', 0, half):.1f} vs {h1('boarding_hours', half, len(D)):.1f} pt-h/day.")
    A(f"Worst single day (batch mean): ward occupancy {max(x['ward_occupancy'] for x in D):.3f}, mean wait {max(x['wait_mean'] for x in D):.0f} min, "
      f"LWBS {100 * max(x['lwbs_rate'] for x in D):.1f} %, boarding {max(x['boarding_hours'] for x in D):.1f} pt-h.")
    s = r["summary"]
    A(f"Episode summary (contract keys): mean wait {s['wait_mean_min']:.1f} min, p95 wait {s['wait_p95_min']:.0f} min, median ED time over all "
      f"departures {s['ed_los_median_min']:.0f} min, LWBS {100 * s['lwbs_rate']:.2f} %, cost {s['cost_per_day'] / 1e3:.0f} k/day, margin "
      f"{s['margin_per_day'] / 1e3:.0f} k/day, {s['deaths_per_10k']:.1f} deaths per 10,000 arrivals, boarding {s['boarding_hours_per_day']:.1f} pt-h/day. "
      f"Conservation residual {r['conservation_residual']}, pool overflow {r['pool_overflow']}.\n")
    A("## Calibration record (ASSUMED attributes only; measured and literature values untouched)\n")
    A("| Attribute | Was | Now | Reason |\n|---|---|---|---|")
    A(f"| `staff.shared.provider_levels` | 3/5/7/9/11 | {'/'.join(str(x) for x in P['provider_levels'])} | With 7 providers at the default level: median "
      "discharged ED time 250 min, LWBS 2.3 %, p90 wait 80 min (8 hospitals, 3 + 10 days). 8 gave 185 min / 1.4 %; 9 gave 165 min / 1.0 %. "
      "The hospital's own values are 206 min / 1 %. |")
    A(f"| `hospitals/rwjuh_nb.ward_pool_los_factor` (sim-owned) | - | {P['ward_pool_los_factor']} | Ward inflow is about 31 admissions/day (measured "
      f"p_admit) and measured LOS is 5.29 days: about 164 occupied beds against the layout's {P['ward_cap0']}-bed pool, i.e. ~98 %, which is not "
      "stationary (boarding grows without limit). The factor is the assumed share of the stay spent in the modelled pool. The layout's bed counts "
      "were left alone. |")
    A(f"| `patient.shared.wrong_disposition_max_prob` (sim-owned) | 0.25 | {P['wrong_disposition_max_prob']} | 0.25 inflated admissions by about a "
      "quarter over the measured rate. |")
    A(f"| `patient.shared.inpatient_variable_cost_per_day` (sim-owned) | 2300 | {P['inpatient_cost_per_day']:.0f} | The measured ward fixed cost is "
      "fully allocated (includes nursing); 2300 double-counted. |")
    A("| Ward warm start (derived from the LOS distribution) | remaining stay = LOS x U | LOS x U x (1 + cv^2) | Mean residual life of a stay in "
      "progress, so occupancy does not sag in week 1. |")
    A("| Treatment clock (model choice) | started when the encounter ended | starts at first provider contact | `treatment_min` is measured from "
      "first contact. |\n")
    A("These are assumed calibrations of a model, not statements about the real hospital.\n")
    A("## Known limits\n")
    A("- 90th-percentile wait too short (above).")
    A("- By acuity, low-acuity discharged visits run long and high-acuity ones short relative to the survey medians (table above).")
    A("- Cost is insensitive to staffing because measured overhead dominates. That is what the cost report says, but it leaves a "
      "cost-minimising manager little room.")
    A("- Long stays in a bay are real model output, not a reporting error: boarding patients are reported as `boarding`, never as "
      "`waiting_results`. `waiting_results` covers the whole in-bay treatment period after the clinician encounter, and the measured "
      "`treatment_min` distributions are heavy-tailed (lognormal, cv 0.87-1.23), so with a median discharged stay near 190 min the 90th "
      f"percentile is {v['los_discharged_p90']:.0f} min and a few patients sit in `waiting_results` for 5-9 hours "
      "(the survey's 90th percentiles by acuity are 292-721 min).")
    A("- The layout's results-waiting room is drawn but not used by the model (no vertical-flow step), so it always shows 0 occupants; its "
      "capacity is whatever the layout file says.")
    A("- `community_small` and `midsize` layouts run (arrivals and rosters scaled by bay count) but are not calibrated.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="normal_week")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--warm", type=int, default=3)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seed", type=int, default=100000)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--write", action="store_true", help="overwrite sim/BASELINE.md")
    ap.add_argument("--json", default="")
    ap.add_argument("--from-json", default="", help="render from a saved --json file instead of running")
    a = ap.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    if a.from_json:        # re-render the report from a saved run (e.g. one made on deepstack)
        r = json.loads(Path(a.from_json).read_text())
        r["P"] = load_scenario(r["meta"]["scenario"]).P
    else:
        r = run(a.scenario, a.days, a.batch, a.warm, a.device, a.seed)
    md = markdown(r)
    if a.json:
        Path(a.json).write_text(json.dumps({k: v for k, v in r.items() if k != "P"}, indent=1))
    if a.write:
        (ROOT / "sim" / "BASELINE.md").write_text(md)
        print("wrote sim/BASELINE.md")
    else:
        print(md)


if __name__ == "__main__":
    main()
