"""The headline number per hospital. All numbers SIMULATED.

    python -m rl.headline --hospital rwjuh_nb --gpu-workers 2 --cpu-workers 10

writes rl/hospitals/<id>/headline.json, HEADLINE.md and headline_raw.json.

Protocol
  1. Candidates per operator objective = every available manager built for it (tuned heuristic, PPO).
  2. SELECTION on validation seeds (900,000+; never the evaluation seeds): constrained score against the
     calibrated baseline over ensemble members; the best candidate that meets every constraint is selected.
  3. HELD-OUT evaluation: seeds 9,000,000+ x ensemble members x >= 30 days, every candidate and the baseline
     (`fixed` = the hospital's calibrated current practice) on the same seeds in the same member (paired).
  4. Intervals: 95% percentile bootstrap, resampling ensemble members and seeds (two-way).
  5. Feasibility is a hard check on the held-out numbers. A selected policy that turns out infeasible on
     held-out data is REPORTED as infeasible; it is not swapped for another (that would be selecting on
     evaluation seeds).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch

from .common import (SEED_EVAL, SEED_VAL, calibration_status, fingerprints, get_spec, hospital_id, is_stale, load_ensemble, load_scales,
                     now_iso, paths, write_json, write_text)
from .managers import PARAM_NAMES, _policy_files, list_managers
from .objectives import (EPISODE_METRICS, FLOW_INDEX, LOWER_IS_BETTER, OPERATOR_OBJECTIVES, OVERTIME_SHARE, feasibility, objective_value,
                         operator_score)
from .rollout import group_task, run_groups

SEED_SELECT = SEED_VAL + 50_000
UNCALIBRATED = ("[UNCALIBRATED PIPELINE SMOKE RUN - NOT A HEADLINE, DO NOT PUBLISH: this hospital has no calibration file yet, so the "
                "baseline is an uncalibrated first guess.]")
PRIMARY = "same_budget_better_flow"
# (metric, label, unit, scale, decimals)
REPORT = [("ed_los_median_min", "Median ED length of stay", "min", 1.0, 1), ("wait_mean_min", "Mean door-to-provider wait", "min", 1.0, 1),
          ("wait_p95_min", "95th-percentile door-to-provider wait", "min", 1.0, 1), ("lwbs_rate", "Left without being seen", "% of arrivals", 100.0, 2),
          ("boarding_hours_per_day", "Boarding", "patient-hours/day", 1.0, 1), ("labor_cost_per_day", "Labor cost", "$k/day", 1e-3, 2),
          ("operating_cost_per_day", "Labor + fixed staffed-space cost", "$k/day", 1e-3, 1), ("margin_per_day", "Margin", "$k/day", 1e-3, 1),
          ("deaths_per_10k", "Deaths", "per 10,000 arrivals", 1.0, 2), ("adverse_events_per_day", "Adverse events", "per day", 1.0, 3),
          ("hi_acuity_wait_hours_per_day", "ESI 1-2 patients waiting", "patient-hours/day", 1.0, 2),
          ("diversion_hours_per_day", "Ambulance diversion", "h/day", 1.0, 2), ("overtime_hours_per_day", "Overtime", "h/day", 1.0, 2),
          ("transfers_per_day", "Transfers out", "per day", 1.0, 2)]
SENTENCE_METRICS = [("wait_mean_min", "mean door-to-provider wait"), ("ed_los_median_min", "median ED length of stay"),
                    ("lwbs_rate", "walk-outs (left without being seen)"), ("boarding_hours_per_day", "boarding hours")]
CAVEATS = [
    "Everything here is SIMULATED. No number is a measurement of the real hospital and none is a forecast of what would happen there.",
    "The twin is calibrated to public aggregates only (CMS-reported and other published figures listed in the hospital's catalog file). "
    "Parameters those figures do not pin down (service-time shapes, patience, staffing rosters, ward capacity share, cost allocation) are assumed; "
    "the calibration ensemble spans the sets found consistent with the public figures, and the 'holds in k/N twins' line is the only robustness "
    "statement made about them.",
    "The baseline ('current practice') is the calibration's reconstruction of the hospital's staffing and operating rules from public data. "
    "The real roster, call-in practice, fast-track hours and bed management are not known to us; if the real baseline is better than the "
    "reconstructed one, the real improvement is smaller.",
    "Not validated on the hospital's operational data. To validate: (1) one year of de-identified ED timestamps (arrival, triage, first provider, "
    "disposition, departure), acuity and disposition; (2) the actual staffing roster by hour and role, call-in and overtime logs; (3) inpatient bed "
    "occupancy and boarding logs; (4) the ED cost center's labor ledger. With those, refit the twin, check it reproduces held-out weeks, and re-run "
    "this report before any operational change.",
    "Safety figures (deaths, adverse events) come from literature hazard rates applied to simulated waiting; they are rare events with wide "
    "intervals and are a guard-rail in the optimization, not a clinical prediction.",
    "Money: labor cost uses published wage levels with assumed benefit, overtime and agency multipliers; margin additionally depends on assumed "
    "payer revenue and is reported for completeness only.",
    "The policy acts hourly on the simulator's observation (queue lengths, occupancy, arrivals in the last day, a next-hour arrival forecast). "
    "Running it in a real ED needs those signals live, and staff rules (minimum ratios, contract terms, call-in willingness) that the twin does not model.",
]


# ---------------------------------------------------------------------------------------------- statistics
def pooled(x: torch.Tensor) -> torch.Tensor:
    """[M, S, K] -> [K] mean over members and seeds."""
    return x.mean((0, 1))


def bootstrap_weights(M: int, S: int, reps: int = 2000, seed: int = 0):
    """Two-way resampling weights: members (when there is more than one) and seeds, with replacement."""
    g = torch.Generator().manual_seed(seed)
    ws = torch.zeros((reps, S), dtype=torch.float64)
    ws.scatter_add_(1, torch.randint(0, S, (reps, S), generator=g), torch.ones((reps, S), dtype=torch.float64))
    wm = torch.ones((reps, M), dtype=torch.float64)
    if M > 1:
        wm.zero_()
        wm.scatter_add_(1, torch.randint(0, M, (reps, M), generator=g), torch.ones((reps, M), dtype=torch.float64))
    return wm / M, ws / S


def boot_means(x: torch.Tensor, wm, ws) -> torch.Tensor:
    """[M, S, K] -> [reps, K] bootstrap means."""
    return torch.einsum("rm,rs,msk->rk", wm, ws, x.double())


def ci(v: torch.Tensor) -> list[float]:
    q = torch.quantile(v.double(), torch.tensor([0.025, 0.975], dtype=torch.float64), dim=0)
    return [float(q[0]), float(q[1])]


def paired_table(cand: torch.Tensor, base: torch.Tensor, reps: int = 2000, seed: int = 0) -> dict:
    """cand, base: [M, S, K] on the same members and seeds. -> metric -> baseline, policy, absolute and %
    change with 95% bootstrap intervals (the % interval is of the ratio of means)."""
    M, S, K = cand.shape
    wm, ws = bootstrap_weights(M, S, reps, seed)
    cb, bb = boot_means(cand, wm, ws), boot_means(base, wm, ws)
    cm, bm = pooled(cand.double()), pooled(base.double())
    out = {}
    for j, k in enumerate(EPISODE_METRICS):
        d = cb[:, j] - bb[:, j]
        den = bb[:, j].abs().clamp(min=1e-12)
        b0 = float(bm[j])
        out[k] = dict(baseline=b0, policy=float(cm[j]), diff=float(cm[j] - bm[j]), diff_ci95=ci(d),
                      pct=(100.0 * float(cm[j] - bm[j]) / abs(b0) if abs(b0) > 1e-9 else None),
                      pct_ci95=([100.0 * x for x in ci(d / den)] if abs(b0) > 1e-9 else None))
    return out


def as_dict(v: torch.Tensor) -> dict:
    return {k: float(v[j]) for j, k in enumerate(EPISODE_METRICS)}


def objective_ci(objective, cand, base, reps=2000, seed=0) -> dict:
    """The minimised quantity as a ratio to baseline, with a bootstrap interval."""
    wm, ws = bootstrap_weights(cand.shape[0], cand.shape[1], reps, seed)
    cb, bb = boot_means(cand, wm, ws), boot_means(base, wm, ws)
    v = objective_value(objective, cb, bb)
    return dict(value=float(objective_value(objective, pooled(cand.double()), pooled(base.double()))), ci95=ci(v))


def score_diff_ci(objective, a, b, base, reps=2000, seed=0) -> dict:
    """Constrained score (no tuning margin) of a minus b, bootstrap interval; + = a better."""
    wm, ws = bootstrap_weights(a.shape[0], a.shape[1], reps, seed)
    ab, bbm, base_b = boot_means(a, wm, ws), boot_means(b, wm, ws), boot_means(base, wm, ws)
    d = operator_score(objective, ab, base_b, margin=False) - operator_score(objective, bbm, base_b, margin=False)
    pm = lambda x: pooled(x.double())                                                       # noqa: E731
    mean = float(operator_score(objective, pm(a), pm(base), margin=False) - operator_score(objective, pm(b), pm(base), margin=False))
    lo, hi = ci(d)
    return dict(mean=mean, ci95=[lo, hi], verdict="beats" if lo > 0 else ("loses to" if hi < 0 else "matches (difference not significant)"))


def ensemble_coverage(objective: str, cand: torch.Tensor, base: torch.Tensor, member_ids: list) -> dict:
    """Per ensemble member (means over seeds): does the objective improve with the hard constraints met?"""
    rows = []
    for i, mid in enumerate(member_ids):
        c, b = as_dict(cand[i].mean(0)), as_dict(base[i].mean(0))
        f = feasibility(objective, c, b)
        hard_ok = all(r["met"] for r in f["constraints"] if r["kind"] == "hard")
        ratio = float(objective_value(objective, c, b))
        rows.append(dict(member=mid, objective_ratio=ratio, improves=bool(ratio < 1.0), hard_constraints_met=bool(hard_ok),
                         all_constraints_met=bool(f["feasible"]), violated=f["violated"], holds=bool(ratio < 1.0 and hard_ok),
                         **{k: dict(baseline=b[k], policy=c[k]) for k in ("wait_mean_min", "ed_los_median_min", "lwbs_rate", "labor_cost_per_day")}))
    worst = max(rows, key=lambda r: r["objective_ratio"])
    return dict(n_members=len(rows), holds=sum(r["holds"] for r in rows), holds_with_safety=sum(r["holds"] and r["all_constraints_met"] for r in rows),
                share=sum(r["holds"] for r in rows) / len(rows), worst_member=worst, members=rows,
                definition="holds = the minimised quantity is below baseline AND every hard constraint (budget, diversion, overtime, transfers; "
                           "for the cost objective also every flow metric) is met on that member's mean over the held-out seeds; "
                           "holds_with_safety additionally requires the rare-event safety point estimates to be no worse")


# ---------------------------------------------------------------------------------------------- running
def evaluate(hospital, managers, scenarios, members, seeds, days, a, want_actions=False, log=print) -> dict:
    """-> scenario -> dict(values [n_managers, M, S, K], names, actions...)"""
    scales = load_scales(hospital=hospital)
    tasks = []
    for s in scenarios:
        for m in members:
            tasks.append(group_task(hospital, s, m, [{"id": x} for x in managers], seeds, days, device=a.device, stage="stage_3",
                                    scales=scales, want_actions=want_actions and s == scenarios[0], tag=f"{s}/m{m}"))
    t0 = time.time()
    res = run_groups(tasks, a.gpu_workers, a.cpu_workers, log=log)
    log(f"  {len(tasks)} groups ({len(managers)} managers x {len(seeds)} seeds x {days} d) in {time.time() - t0:.0f}s")
    out, i = {}, 0
    for s in scenarios:
        rs = res[i:i + len(members)]
        i += len(members)
        d = dict(values=torch.stack([r["episode"] for r in rs], 1), names=managers, invalid=torch.stack([r["invalid"] for r in rs], 1))
        if rs[0].get("actions"):
            d["actions"] = {k: torch.stack([r["actions"][k] for r in rs]).mean(0) for k in rs[0]["actions"]}
            d["actions_by_dow"] = {k: torch.stack([r["actions_by_dow"][k] for r in rs]).mean(0) for k in rs[0]["actions_by_dow"]}
            d["option_values"], d["option_labels"] = rs[0]["option_values"], rs[0]["option_labels"]
            d["defaults_by_member"] = [r["defaults"] for r in rs]
        out[s] = d
    return out


# ---------------------------------------------------------------------------------------------- what changes
def _mean_value(share: torch.Tensor, values) -> float | None:
    if not values or not all(isinstance(v, (int, float)) for v in values):
        return None
    return float((share * torch.tensor([float(v) for v in values])).sum())


def what_changes(ev: dict, cand: str, params: dict | None) -> list[str]:
    """Operational differences between the policy and the baseline, from the settings in force hour by hour
    on the held-out runs (shares over seeds, days and ensemble members) and from the tuned rule's parameters."""
    A, names, vals, labs = ev["actions"], ev["names"], ev["option_values"], ev["option_labels"]
    ib, ic = names.index("fixed"), names.index(cand)
    sh = lambda head, i: A[head][i].mean(0)                    # noqa: E731  [n_options] share of hours
    L = []
    for role, word in (("md", "Providers"), ("rn", "Nurses")):
        parts = []
        for s, hrs in (("day", "07-15"), ("evening", "15-23"), ("night", "23-07")):
            hd = f"{role}_{s}"
            b, c = _mean_value(sh(hd, ib), vals[hd]), _mean_value(sh(hd, ic), vals[hd])
            dw = ev["actions_by_dow"][hd][ic]
            by = [_mean_value(dw[d], vals[hd]) for d in range(7)]
            rng = f" (by weekday {min(by):.1f}-{max(by):.1f})" if max(by) - min(by) >= 0.3 else ""
            parts.append(f"{s} {hrs}: {b:.1f} -> {c:.1f}{rng}")
        tot = lambda i: sum(_mean_value(sh(f"{role}_{s}", i), vals[f"{role}_{s}"]) for s in ("day", "evening", "night")) * 8      # noqa: E731
        L.append(f"{word} scheduled per shift (mean people, baseline -> policy): " + "; ".join(parts)
                 + f". Scheduled {word.lower()[:-1]}-hours per day {tot(ib):.0f} -> {tot(ic):.0f}.")
    b, c = _mean_value(sh("triage_nurses", ib), vals["triage_nurses"]), _mean_value(sh("triage_nurses", ic), vals["triage_nurses"])
    if abs(b - c) >= 0.05:
        L.append(f"Triage stations staffed: {b:.1f} -> {c:.1f} on average.")

    def shares(head, i):
        return ", ".join(f"{labs[head][j].replace('_', ' ')} {100 * float(x):.0f}%" for j, x in enumerate(sh(head, i)) if float(x) >= 0.005)

    for head, word in (("priority_rule", "Queue priority rule"), ("provider_split", "Provider time between new patients and dispositions"),
                       ("fast_track", "Fast track (share of hours)"), ("overflow_bays", "Hallway overflow spaces (share of hours)"),
                       ("discharge_push", "Ward early discharge rounds (share of days)"), ("agency_contract", "Agency nurse contract"),
                       ("imaging_hours", "Second CT / MRI staffed hours")):
        if float((sh(head, ib) - sh(head, ic)).abs().max()) >= 0.01:
            L.append(f"{word}: baseline {shares(head, ib)} -> policy {shares(head, ic)}.")
    if "call_in" in A:
        ci_b, ci_c = A["call_in"][ib], A["call_in"][ic]               # [24, options] share of (seed, day) with that call at that hour
        per_day = lambda x: float(x[:, 1:].sum())                     # noqa: E731
        if abs(per_day(ci_b) - per_day(ci_c)) >= 0.02:
            hrs = torch.argsort(ci_c[:, 1:].sum(1), descending=True)[:3].tolist()
            kinds = ", ".join(f"{labs['call_in'][j].replace('_', ' ')} {float(ci_c[:, j].sum()):.2f}/day" for j in range(1, ci_c.shape[1])
                              if float(ci_c[:, j].sum()) >= 0.01)
            L.append(f"Overtime call-in requests: {per_day(ci_b):.2f} -> {per_day(ci_c):.2f} per day ({kinds}); most often at "
                     + ", ".join(f"{h:02d}:00" for h in sorted(hrs)) + ".")
    for head, word in (("divert", "Ambulance diversion"), ("admission_cap", "Admission cap")):
        same = float((sh(head, ib) - sh(head, ic)).abs().max()) < 1e-6
        L.append(f"{word}: {'unchanged from baseline (locked)' if same else 'DIFFERS from baseline: ' + shares(head, ic)}.")
    for head in ("bays_delta", "ward_beds_delta", "equipment_buy", "relocate", "headcount"):
        if float((sh(head, ib) - sh(head, ic)).abs().max()) >= 1e-6:
            L.append(f"Structural head `{head}` differs from baseline: {shares(head, ic)} (capital decision; outside the operator objectives).")
    if params:
        L += describe_rule(params)
    if len(ev.get("defaults_by_member") or []) > 1:
        L.append("People counts above use ensemble member 0's level-to-people ladder (the point calibration); the ladders differ between "
                 "ensemble members, the policy's staffing LEVELS are the same in all of them.")
    return L


def describe_rule(p: dict) -> list[str]:
    """The tuned rule's triggers in plain terms (thresholds are in the simulator's observation units)."""
    g = lambda k, d=0.0: float(p.get(k, d))                           # noqa: E731
    L = []
    if g("md_demand_gain") > 0.02 or g("rn_demand_gain") > 0.02:
        L.append(f"Staffing reacts to yesterday's volume: +{8 * g('md_demand_gain') * 0.1:.2f} provider levels and "
                 f"+{8 * g('rn_demand_gain') * 0.1:.2f} nurse levels per 10% of arrivals above a typical day.")
    if g("md_dow_gain") > 0.02 or g("rn_dow_gain") > 0.02:
        L.append(f"Staffing follows the published weekday arrival pattern: +{16 * g('md_dow_gain') * 0.05:.2f} provider levels and "
                 f"+{16 * g('rn_dow_gain') * 0.05:.2f} nurse levels per 5% that the weekday runs above average.")
    rn, md = 0.8 * g("callin_rn_thr", 1.0), 0.5 * g("callin_md_thr", 1.0)
    L.append(f"Call-in triggers: a nurse when patients waiting for a bay exceed {100 * rn:.0f}% of the ED's bay count, a provider when patients "
             f"waiting for a provider exceed {100 * md:.0f}% of it"
             + (f"; thresholds drop by up to {100 * (1 - 1 / (1 + 2 * g('callin_forecast_gain') * 0.5)):.0f}% when the next hour is forecast 50% busier than typical"
                if g("callin_forecast_gain") > 0.02 else "")
             + (f"; no call-in in the last {round(4 * g('callin_late_cut'))} h of a shift" if round(4 * g("callin_late_cut")) >= 1 else "")
             + (f"; also a nurse when bay occupancy exceeds {100 * (0.6 + 0.4 * g('callin_occ_thr', 1.0)):.0f}% with a typical-or-busier hour ahead"
                if g("callin_occ_thr", 1.0) < 0.99 else "") + ".")
    lo = 0.5 * g("overflow_low_thr", 1.0)
    L.append(f"Hallway overflow opens when patients waiting for a bay exceed {100 * lo:.0f}% of the bay count "
             f"(second tier at {100 * (lo + 0.5 * g('overflow_high_gap', 1.0)):.0f}%).")
    if g("discharge_push_occ", 1.0) <= 0.83 or g("push_boarding_thr", 1.0) < 0.99:
        L.append("Early ward discharge rounds are triggered when " + " or ".join(
            ([f"ward occupancy exceeds {100 * (0.5 + 0.6 * g('discharge_push_occ')):.0f}%"] if g("discharge_push_occ", 1.0) <= 0.83 else [])
            + ([f"boarders exceed {100 * 0.3 * g('push_boarding_thr'):.0f}% of the bay count"] if g("push_boarding_thr", 1.0) < 0.99 else []))
                 + " at midnight.")
    if g("split_dispo_thr", 1.0) < 0.99 or g("split_new_thr", 1.0) < 0.99:
        L.append("Provider time shifts " + "; ".join(
            ([f"to dispositions when more than {10 * g('split_dispo_thr'):.0f} patients are ready for disposition"] if g("split_dispo_thr", 1.0) < 0.99 else [])
            + ([f"to new patients when those waiting for a provider exceed {100 * 0.5 * g('split_new_thr'):.0f}% of the bay count"]
               if g("split_new_thr", 1.0) < 0.99 else [])) + ".")
    if g("ft_close_night") > 0.5:
        L.append("Fast track is closed 23:00-07:00.")
    return L


# ---------------------------------------------------------------------------------------------- report
def _fmt(x, sc=1.0, nd=1):
    return "n/a" if x is None else f"{x * sc:,.{nd}f}"


def _pct(row):
    if row["pct"] is None:
        return "n/a"
    lo, hi = row["pct_ci95"]
    return f"{row['pct']:+.1f}% ({lo:+.1f} to {hi:+.1f})"


def direction(row, metric) -> str:
    lo, hi = row["diff_ci95"]
    better = (hi < 0) if LOWER_IS_BETTER[metric] else (lo > 0)
    worse = (lo > 0) if LOWER_IS_BETTER[metric] else (hi < 0)
    return "better" if better else ("worse" if worse else "no significant change")


def sentence(hlabel: str, cal: dict, objective: str, pol: dict, block: dict | None) -> str:
    twin = (f"a simulated twin calibrated to {hlabel}'s publicly reported figures" if cal["calibration_file"]
            else f"a simulated twin of {hlabel} built from public data (no calibration file yet: hand-set baseline)")
    if block is None:
        return f"In {twin}, no manager is available for the objective '{OPERATOR_OBJECTIVES[objective]['label']}' yet. All numbers simulated."
    T, feas, cov = block["metrics"], block["feasibility"], block["ensemble"]
    name = f"{pol['label']} (`{pol['id']}`, {pol['kind'].replace('_', ' ')})"
    bits = []
    for k, word in SENTENCE_METRICS:
        r = T[k]
        if r["pct"] is None:
            continue
        d = direction(r, k)
        if d == "better":
            bits.append(f"cut {word} by {-r['pct']:.1f}% (95% CI {-r['pct_ci95'][1]:.1f} to {-r['pct_ci95'][0]:.1f})")
        elif d == "worse":
            bits.append(f"INCREASED {word} by {r['pct']:.1f}% (95% CI {r['pct_ci95'][0]:.1f} to {r['pct_ci95'][1]:.1f})")
        else:
            bits.append(f"did not significantly change {word} ({r['pct']:+.1f}%, 95% CI {r['pct_ci95'][0]:+.1f} to {r['pct_ci95'][1]:+.1f})")
    lab, dth, div = T["labor_cost_per_day"], T["deaths_per_10k"], T["diversion_hours_per_day"]
    lab_s = (f"labor cost {lab['pct']:+.1f}% vs baseline (95% CI {lab['pct_ci95'][0]:+.1f} to {lab['pct_ci95'][1]:+.1f}; "
             + ("within budget" if lab["policy"] <= lab["baseline"] + 1e-9 else "OVER budget") + ")")
    dth_s = f"deaths per 10,000 arrivals {dth['diff']:+.2f} (95% CI {dth['diff_ci95'][0]:+.2f} to {dth['diff_ci95'][1]:+.2f})"
    div_s = "no ambulance diversion beyond baseline" if div["policy"] <= div["baseline"] + 1e-9 else f"ambulance diversion UP {div['diff']:.2f} h/day"
    if cov["n_members"] > 1:
        cov_s = (f"The improvement with budget constraints met holds in {cov['holds']}/{cov['n_members']} plausible twins of the calibration "
                 f"ensemble (worst twin: objective at {100 * cov['worst_member']['objective_ratio']:.1f}% of its baseline)")
    else:
        cov_s = ("Only the point calibration was available (1/1 twin): robustness to the parameters public data cannot identify is NOT yet assessed")
    if feas["feasible"]:
        verdict = "Every constraint was met on held-out data"
    else:
        verdict = "NOT FEASIBLE on held-out data: violated " + ", ".join(feas["violated"])
    lead = "; ".join(bits) if objective == PRIMARY else f"cut labor cost by {-lab['pct']:.1f}% (95% CI {-lab['pct_ci95'][1]:.1f} to {-lab['pct_ci95'][0]:.1f}); it " + "; ".join(bits)
    tail = f"with {lab_s}, {div_s} and {dth_s}" if objective == PRIMARY else f"with {div_s} and {dth_s}"
    return (f"In {twin}, {name} {lead}, {tail}. {verdict}. {cov_s}. All figures are simulated and not validated on the hospital's operational data.")


def annualise(T: dict, visits: float | None, visits_src: str) -> dict:
    base_arr = T["arrivals_per_day"]["baseline"] + T["diverted_per_day"]["baseline"]
    f = (visits / (base_arr * 365.0)) if visits and base_arr > 0 else 1.0

    def row(k, sign, scale, label, unit):
        r = T[k]
        lo, hi = sorted([sign * r["diff_ci95"][0] * scale, sign * r["diff_ci95"][1] * scale])
        return dict(label=label, unit=unit, value=sign * r["diff"] * scale, ci95=[lo, hi])

    y = 365.0
    return dict(annual_ed_visits=visits, annual_ed_visits_source=visits_src, simulated_arrivals_per_day=base_arr, volume_factor=f,
                note="30 simulated days of the `normal_week` scenario scaled to a year (x365) and to the hospital's measured annual volume "
                     "(volume factor); seasonality and surge weeks are not in this figure. Simulated.",
                rows=[row("ed_patient_hours_per_day", -1, y * f, "Patient-hours in the ED saved", "patient-hours/yr"),
                      row("wait_patient_hours_per_day", -1, y * f, "Patient-hours waiting for a provider saved", "patient-hours/yr"),
                      row("lwbs_per_day", -1, y * f, "Fewer walk-outs (left without being seen)", "patients/yr"),
                      row("boarding_hours_per_day", -1, y * f, "Boarding patient-hours saved", "patient-hours/yr"),
                      row("labor_cost_per_day", 1, y, "Labor cost change", "$/yr"),
                      row("margin_per_day", 1, y, "Margin change (assumed payer revenue)", "$/yr")])


def table_md(T: dict) -> list[str]:
    L = ["| Metric | Baseline | Policy | Change (95% CI) | % change (95% CI) | Reading |", "|---|---|---|---|---|---|"]
    for k, label, unit, sc, nd in REPORT:
        r = T[k]
        lo, hi = r["diff_ci95"]
        L.append(f"| {label} ({unit}) | {_fmt(r['baseline'], sc, nd)} | {_fmt(r['policy'], sc, nd)} | {r['diff'] * sc:+,.{nd}f} "
                 f"({lo * sc:+,.{nd}f} to {hi * sc:+,.{nd}f}) | {_pct(r)} | {direction(r, k)} |")
    return L


def feas_md(f: dict) -> list[str]:
    L = ["| Constraint | Baseline | Limit | Policy | Met | Status |", "|---|---|---|---|---|---|"]
    for r in f["constraints"]:
        L.append(f"| {r['label']} | {r['baseline']:,.3f} | {r['limit']:,.3f} | {r['candidate']:,.3f} | {'yes' if r['met'] else '**NO**'} | {r['status']} |")
    return L


def write_markdown(H: dict, path: Path):
    cal, ens, pr = H["calibration"], H["ensemble"], H["protocol"]
    L = [f"# {H['hospital_label']} (`{H['hospital_id']}`): operating-policy headline — ALL NUMBERS SIMULATED", "",
         f"Generated {H['generated']}. Calibration: "
         + (f"`catalog/hospitals/{H['hospital_id']}.calibration.yaml` (modified {cal['calibration_mtime']})" if cal["calibration_file"]
            else "**no calibration file yet** (catalog defaults; the baseline is the contract's flat default staffing)")
         + f"; ensemble: " + (f"{ens['n_members']} members from `{ens['source']}`" if ens["exists"] else "**no ensemble file** (1 member = the point calibration)")
         + f"; calibration fingerprint `{H['calibration_fingerprint']}`, simulator behaviour `{H['sim_behaviour_fingerprint']}`.", "",
         "## Headline" if H.get("publishable") else "## NOT A HEADLINE: uncalibrated pipeline smoke run", "", H["sentence"], ""]
    for obj, O in H["objectives"].items():
        spec = OPERATOR_OBJECTIVES[obj]
        L += [f"## Objective: {spec['label']} (`{obj}`)", "", f"What it asks for: {spec['meaning']}.", ""]
        if not O.get("selected"):
            L += ["No manager is available for this objective.", ""]
            continue
        sel = O["selected"]
        blk = O["candidates"][sel]["normal_week"]
        L += [f"**Selected policy: `{sel}`** — {O['managers'][sel]['label']} ({O['managers'][sel]['kind'].replace('_', ' ')}). {O['selection']['reason']}", "",
              O["sentence"], ""]
        if O["managers"][sel].get("stale"):
            L += ["**STALE: this policy was tuned / trained against another calibration or simulator behaviour. Re-run `rl/scripts/run_hospital.sh`.**", ""]
        L += [f"### Held-out result, normal operations ({pr['n_members']} twin(s) x {pr['n_seeds']} seeds x {pr['days']} days, paired against the baseline)", ""]
        L += table_md(blk["metrics"])
        L += ["", f"Minimized quantity ({'flow index' if spec['minimise'] == 'flow_index' else 'labor cost'}) as a share of baseline: "
              f"**{100 * blk['objective_ratio']['value']:.1f}%** (95% CI {100 * blk['objective_ratio']['ci95'][0]:.1f} to {100 * blk['objective_ratio']['ci95'][1]:.1f}). "
              + ("Flow index = " + " + ".join(f"{w:g} x {k}" for k, w in FLOW_INDEX.items()) + ", each as policy / baseline." if spec["minimise"] == "flow_index" else ""), "",
              f"### Constraints (hard check on held-out data): **{'FEASIBLE' if blk['feasibility']['feasible'] else 'NOT FEASIBLE'}**", ""]
        L += feas_md(blk["feasibility"])
        cov = blk["ensemble"]
        L += ["", "### Robustness to what public data cannot identify", ""]
        if cov["n_members"] > 1:
            w = cov["worst_member"]
            L += [f"Improvement with the hard constraints met holds in **{cov['holds']}/{cov['n_members']}** ensemble members "
                  f"({cov['holds_with_safety']}/{cov['n_members']} when the rare-event safety point estimates must also be no worse). "
                  f"Worst member: #{w['member']}, minimised quantity at {100 * w['objective_ratio']:.1f}% of its own baseline "
                  f"(mean wait {w['wait_mean_min']['baseline']:.1f} -> {w['wait_mean_min']['policy']:.1f} min, median stay "
                  f"{w['ed_los_median_min']['baseline']:.0f} -> {w['ed_los_median_min']['policy']:.0f} min, labor "
                  f"{w['labor_cost_per_day']['baseline'] / 1e3:.1f} -> {w['labor_cost_per_day']['policy'] / 1e3:.1f} $k/day"
                  + (f"; violated: {', '.join(w['violated'])}" if w["violated"] else "") + f"). {cov['definition']}.", ""]
        else:
            L += ["**Not assessed.** There is no calibration ensemble for this hospital yet, so this result is for one parameter set only. "
                  "The report picks the ensemble up automatically when `catalog/hospitals/<id>.ensemble.json` exists.", ""]
        if "flu_surge" in O["candidates"][sel]:
            fb = O["candidates"][sel]["flu_surge"]
            L += [f"### Same policy under a flu surge (held-out; feasibility: **{'FEASIBLE' if fb['feasibility']['feasible'] else 'NOT FEASIBLE: ' + ', '.join(fb['feasibility']['violated'])}**; "
                  f"holds in {fb['ensemble']['holds']}/{fb['ensemble']['n_members']} twins)", ""]
            L += table_md(fb["metrics"]) + [""]
        for scen in pr.get("stress_scenarios", []):
            if scen in O["candidates"][sel]:
                sb = O["candidates"][sel][scen]
                T = sb["metrics"]
                L.append(f"- Stress scenario `{scen}` ({pr['stress_seeds']} seeds x {pr['stress_days']} d x {sb['ensemble']['n_members']} twin(s)): "
                         f"mean wait {_pct(T['wait_mean_min'])}, median stay {_pct(T['ed_los_median_min'])}, walk-outs {_pct(T['lwbs_rate'])}, "
                         f"labor {_pct(T['labor_cost_per_day'])}; "
                         + ("feasible" if sb["feasibility"]["feasible"] else "NOT feasible: " + ", ".join(sb["feasibility"]["violated"])) + ".")
        if pr.get("stress_scenarios"):
            L.append("")
        if O.get("annualised"):
            an = O["annualised"]
            L += ["### Annualized translation (simulated)", "",
                  f"Annual volume: {an['annual_ed_visits']:,.0f} ED visits ({an['annual_ed_visits_source']}); simulated baseline "
                  f"{an['simulated_arrivals_per_day']:.0f} arrivals/day; volume factor {an['volume_factor']:.3f}. {an['note']}", "",
                  "| Quantity | Per year | 95% CI |", "|---|---|---|"]
            for r in an["rows"]:
                L.append(f"| {r['label']} ({r['unit']}) | {r['value']:+,.0f} | {r['ci95'][0]:+,.0f} to {r['ci95'][1]:+,.0f} |")
            L.append("")
        if O.get("what_changes"):
            L += ["### What the hospital would do differently (from the settings in force on the held-out runs)", ""]
            L += [f"- {x}" for x in O["what_changes"]] + [""]
        L += ["### Every candidate for this objective (held-out, normal operations; losses and infeasible results included)", "",
              "| Manager | Kind | Selected on validation | Minimized quantity vs baseline (95% CI) | Mean wait | Median stay | LWBS | Labor cost | Feasible | Violated | Stale |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for mid, C in O["candidates"].items():
            b = C["normal_week"]
            T = b["metrics"]
            L.append(f"| `{mid}` | {O['managers'][mid]['kind']} | {'yes' if mid == sel else 'no'} | {100 * b['objective_ratio']['value']:.1f}% "
                     f"({100 * b['objective_ratio']['ci95'][0]:.1f} to {100 * b['objective_ratio']['ci95'][1]:.1f}) | {_pct(T['wait_mean_min'])} | "
                     f"{_pct(T['ed_los_median_min'])} | {_pct(T['lwbs_rate'])} | {_pct(T['labor_cost_per_day'])} | "
                     f"{'yes' if b['feasibility']['feasible'] else '**no**'} | {', '.join(b['feasibility']['violated']) or '-'} | "
                     f"{'yes' if O['managers'][mid].get('stale') else 'no'} |")
        L.append("")
        if O.get("learned_vs_tuned"):
            L += ["### Did the learned agent (PPO) beat the tuned heuristic?", ""]
            for v in O["learned_vs_tuned"]:
                L.append(f"- `{v['a']}` {v['verdict']} `{v['b']}` on the constrained score, {v['scenario']}: {v['mean']:+.4f} "
                         f"(95% CI {v['ci95'][0]:+.4f} to {v['ci95'][1]:+.4f}); `{v['a']}` feasible: {'yes' if v['a_feasible'] else 'no'}, "
                         f"`{v['b']}` feasible: {'yes' if v['b_feasible'] else 'no'}.")
            L.append("")
        else:
            L += ["No learned (PPO) agent was available for this objective; the result above is the tuned heuristic's.", ""]
        L += ["Selection on validation seeds (never the held-out seeds):", "",
              "| Manager | Validation score | Feasible on validation | Violated |", "|---|---|---|---|"]
        for r in O["selection"]["rows"]:
            L.append(f"| `{r['id']}` | {r['score']:+.4f} | {'yes' if r['feasible'] else 'no'} | {', '.join(r['violated']) or '-'} |")
        L.append("")
    L += ["## Context: unconstrained reference managers on the same held-out runs (not candidates)", "",
          "| Manager | Mean wait | Median stay | LWBS | Labor cost | Diversion h/day |", "|---|---|---|---|---|---|"]
    for mid, T in H.get("context", {}).items():
        L.append(f"| `{mid}` | {_pct(T['wait_mean_min'])} | {_pct(T['ed_los_median_min'])} | {_pct(T['lwbs_rate'])} | {_pct(T['labor_cost_per_day'])} | "
                 f"{T['diversion_hours_per_day']['policy']:.2f} |")
    L += ["", "## Protocol", "",
          f"- Baseline = `fixed`: {H['baseline_label']}. Baseline actions (point calibration): "
          + ", ".join(f"{k}={v}" for k, v in H["baseline_actions"].items()) + ".",
          f"- Held-out: seeds {pr['seeds'][0]}..{pr['seeds'][-1]} ({pr['n_seeds']}) x {pr['n_members']} ensemble member(s) x {pr['days']} days per scenario; "
          "every manager and the baseline run on the same seeds inside the same member (common random numbers, paired).",
          f"- Selection: seeds {pr['select_seeds'][0]}..{pr['select_seeds'][-1]} x {pr['select_members']} member(s) x {pr['select_days']} days "
          "(validation range; tuning uses 200,000+, training 400,000+).",
          f"- Intervals: 95% percentile bootstrap ({pr['bootstrap_reps']} resamples) over ensemble members and seeds; % change = ratio of means.",
          "- 'Median ED length of stay' is the mean over episodes of each 30-day episode's median (histogram estimate, 5-minute bins).",
          f"- Constraints use the point estimates; overtime may exceed baseline by at most {100 * OVERTIME_SHARE:.0f}% of baseline staff-hours per day; "
          "transfers out by at most 2%. `divert` and `admission_cap` are locked at the baseline for operator-objective managers.",
          "- Structural / capital heads (bays, beds, scanners, relocation, headcount) are outside these objectives and stay at baseline.", "",
          "## Caveats", ""]
    L += [f"- {c}" for c in H["caveats"]] + [""]
    write_text(path, "\n".join(L))


# ---------------------------------------------------------------------------------------------- main
def build(a, log=print) -> dict:
    h = hospital_id(a.hospital)
    sp = get_spec(hospital=h)
    cal, ens = calibration_status(h), load_ensemble(h)
    members = list(range(len(ens["members"]))) if ens["exists"] else [None]
    if a.max_members:
        members = members[:a.max_members]
    sel_members = members[:max(1, a.select_members)] if a.select_members else members
    stress_members = members[:max(1, a.stress_members)]
    man = {m["id"]: m for m in list_managers(h) if m["available"]}
    files = _policy_files(h)
    for mid in man:
        if mid in files:
            man[mid]["stale"] = is_stale(files[mid][1], h)
    cands = {obj: [mid for mid, m in man.items() if m.get("objective") == obj and m["kind"] in ("tuned_heuristic", "learned")]
             for obj in OPERATOR_OBJECTIVES}
    allc = sorted({c for v in cands.values() for c in v})
    context = [c for c in a.context if c in man and c not in allc]
    names = ["fixed"] + allc + context
    log(f"[{now_iso()}] headline {h}: members {len(members)}, candidates {cands}, context {context}")
    seeds = [SEED_EVAL + i for i in range(a.seeds)]
    sseeds = [SEED_SELECT + i for i in range(a.select_seeds)]
    scen = ["normal_week", "flu_surge"]
    sel_ev = evaluate(h, ["fixed"] + allc, scen, sel_members, sseeds, a.select_days, a, log=log) if allc else {}
    ev = evaluate(h, names, scen, members, seeds, a.days, a, want_actions=True, log=log)
    stress = [s for s in a.stress if s not in scen]
    st_ev = evaluate(h, ["fixed"] + allc, stress, stress_members, seeds[:a.stress_seeds], a.stress_days, a, log=log) if (stress and allc) else {}
    ev.update(st_ev)
    visits = sp.get("ed_visits_per_year_cms") or sp.get("ed_visits_per_year") or sp["arrivals_per_day"] * 365.0
    vsrc = ("CMS-reported `ed_visits_per_year_cms`, counted per CMS certification number, which can cover more than one campus"
            + (f" [{' '.join(str(sp['ed_visits_note']).split())}]" if sp.get("ed_visits_note") else "") if sp.get("ed_visits_per_year_cms") else
            "hospital-published `ed_visits_per_year`" if sp.get("ed_visits_per_year") else "catalog arrivals_per_day x 365")
    V = lambda e, mid: e["values"][e["names"].index(mid)]                 # noqa: E731  [M, S, K]
    H = dict(hospital_label=sp["hospital_label"], generated=now_iso(), synthetic=True, **fingerprints(h), calibration=cal,
             ensemble=dict(exists=ens["exists"], source=ens["source"], n_members=len(members)),
             baseline_label=man["fixed"]["label"], baseline_actions={x["name"]: x["options"][x["default"]] for x in sp["action_spec"]},
             protocol=dict(seeds=seeds, n_seeds=len(seeds), days=a.days, n_members=len(members), members=members, scenarios=scen,
                           select_seeds=sseeds, select_days=a.select_days, select_members=len(sel_members), bootstrap_reps=a.reps,
                           stress_scenarios=stress, stress_seeds=min(a.stress_seeds, len(seeds)), stress_days=a.stress_days,
                           stress_members=len(stress_members)),
             objectives={}, context={}, caveats=CAVEATS)
    raw = dict(hospital_id=h, generated=H["generated"], synthetic=True, metrics=EPISODE_METRICS, members=members, seeds=seeds,
               values={s: {mid: V(ev[s], mid).tolist() for mid in ev[s]["names"]} for s in ev})
    for obj, spec in OPERATOR_OBJECTIVES.items():
        O = dict(label=spec["label"], candidates={}, managers={c: {k: man[c].get(k) for k in ("id", "kind", "label", "note", "stale")} for c in cands[obj]})
        if not cands[obj]:
            O.update(selected=None, sentence=sentence(sp["hospital_label"], cal, obj, {}, None))
            H["objectives"][obj] = O
            continue
        # ---- selection on validation seeds: constrained score (mean over the two scenarios), feasibility on normal operations
        rows = []
        for c in cands[obj]:
            sc = 0.0
            for s in scen:
                cm, bm = pooled(V(sel_ev[s], c)), pooled(V(sel_ev[s], "fixed"))
                sc += float(operator_score(obj, cm, bm, margin=False)) / len(scen)
            f = feasibility(obj, as_dict(pooled(V(sel_ev["normal_week"], c))), as_dict(pooled(V(sel_ev["normal_week"], "fixed"))))
            rows.append(dict(id=c, score=sc, feasible=f["feasible"], violated=f["violated"]))
        feas_rows = [r for r in rows if r["feasible"]]
        pick = max(feas_rows or rows, key=lambda r: r["score"])
        reason = ("Best constrained score among the candidates that met every constraint on the validation seeds."
                  if feas_rows else "NO candidate met every constraint on the validation seeds; this is the least-bad one and is reported as such.")
        O["selection"] = dict(rows=rows, reason=reason, any_feasible=bool(feas_rows))
        O["selected"] = sel = pick["id"]
        # ---- held-out tables for every candidate and scenario
        for c in cands[obj]:
            O["candidates"][c] = {}
            for s in ev:
                if c not in ev[s]["names"]:
                    continue
                cv, bv = V(ev[s], c), V(ev[s], "fixed")
                T = paired_table(cv, bv, a.reps)
                f = feasibility(obj, as_dict(pooled(cv)), as_dict(pooled(bv)), {k: tuple(T[k]["diff_ci95"]) for k in T})
                mem_ids = (members if s in scen else stress_members)
                O["candidates"][c][s] = dict(metrics=T, feasibility=f, objective_ratio=objective_ci(obj, cv, bv, a.reps),
                                             ensemble=ensemble_coverage(obj, cv, bv, mem_ids),
                                             invalid_actions_per_episode=float(ev[s]["invalid"][ev[s]["names"].index(c)].mean()))
        blk = O["candidates"][sel]["normal_week"]
        O["sentence"] = sentence(sp["hospital_label"], cal, obj, man[sel], blk)
        O["annualised"] = annualise(blk["metrics"], float(visits), vsrc)
        params = files[sel][1].get("params") if sel in files and files[sel][1].get("type") == "rule_params" else None
        O["what_changes"] = what_changes(ev["normal_week"], sel, params)
        if params:
            O["selected_params"] = params
        # ---- learned vs tuned heuristic, held-out
        tuned = next((c for c in cands[obj] if man[c]["kind"] == "tuned_heuristic"), None)
        lv = []
        for c in cands[obj]:
            if man[c]["kind"] == "learned" and tuned:
                for s in scen:
                    d = score_diff_ci(obj, V(ev[s], c), V(ev[s], tuned), V(ev[s], "fixed"), a.reps)
                    lv.append(dict(a=c, b=tuned, scenario=s, **d, a_feasible=O["candidates"][c][s]["feasibility"]["feasible"],
                                   b_feasible=O["candidates"][tuned][s]["feasibility"]["feasible"]))
        O["learned_vs_tuned"] = lv
        H["objectives"][obj] = O
    for c in context:
        H["context"][c] = paired_table(V(ev["normal_week"], c), V(ev["normal_week"], "fixed"), a.reps)
    H["sentence"] = H["objectives"][PRIMARY]["sentence"]
    # Without a calibration file the baseline is an uncalibrated first guess: the run proves the pipeline, nothing more.
    H["publishable"] = bool(cal["calibration_file"])
    if not H["publishable"]:
        H["sentence"] = UNCALIBRATED + " " + H["sentence"]
        for O in H["objectives"].values():
            O["sentence"] = UNCALIBRATED + " " + O["sentence"]
    H["primary_objective"] = PRIMARY
    return H, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hospital", default=None)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--gpu-workers", type=int, default=0)
    ap.add_argument("--cpu-workers", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=32)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--max-members", type=int, default=0, help="cap on ensemble members (0 = all)")
    ap.add_argument("--select-seeds", type=int, default=12)
    ap.add_argument("--select-days", type=int, default=30)
    ap.add_argument("--select-members", type=int, default=8, help="ensemble members used for selection (0 = all)")
    ap.add_argument("--stress", nargs="*", default=["discharge_delays", "nursing_absences", "imaging_outage"])
    ap.add_argument("--stress-seeds", type=int, default=8)
    ap.add_argument("--stress-days", type=int, default=30)
    ap.add_argument("--stress-members", type=int, default=4)
    ap.add_argument("--context", nargs="*", default=["rule_based", "tuned_min_wait", "tuned_balanced"])
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    assert a.days >= 30 or a.out, "the headline protocol is >= 30 days (use --out for a scratch run)"
    h = hospital_id(a.hospital)
    out = Path(a.out or paths(h).home)
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "headline_log.txt", "a")

    def log(s):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    H, raw = build(a, log)
    write_json(out / "headline.json", H, indent=1)
    write_json(out / "headline_raw.json", raw)
    write_markdown(H, out / "HEADLINE.md")
    log(f"wrote {out / 'HEADLINE.md'}\n{H['sentence']}")


if __name__ == "__main__":
    main()
