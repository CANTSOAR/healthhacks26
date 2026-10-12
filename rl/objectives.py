"""Operator objectives: what a hospital would sign off on. All numbers SIMULATED.

Each objective minimises one quantity SUBJECT TO constraints, and everything is measured against the
hospital's own calibrated baseline (`fixed` = the calibration's "current practice" actions) on the SAME
seeds and the SAME ensemble member (paired). Nothing here is a free weighting of costs against harm.

    same_budget_better_flow   minimise a patient-flow index (door-to-provider wait, median ED length of
                              stay, walk-outs, boarding) with labour cost and operating cost <= baseline,
                              safety <= baseline, no extra ambulance diversion, bounded overtime, no extra
                              transfers out.
    same_service_lower_cost   minimise labour cost with every flow and safety metric <= baseline.

Closing the known ways to game them:
  * `divert` and `admission_cap` are LOCKED at the baseline value (the environment overrides whatever a
    policy sends), and diversion hours / transfers out are constrained on top of that;
  * walk-outs (LWBS) are in the flow index and are a constraint of the cost objective, so shedding patients
    never pays;
  * the budget is labour cost AND labour + fixed staffed-space cost, so hallway spaces are not free;
  * overtime is paid inside labour cost and separately capped;
  * safety is deaths, adverse events and the hours high-acuity (ESI 1-2) patients spend waiting;
  * monthly (structural / capital) heads are outside these objectives (curriculum stage 2).

Scoring is on GROUP MEANS (one group = one ensemble member x one scenario, candidate and baseline on the
same seeds): deaths are far too rare for a per-episode constraint to mean anything.
"""
from __future__ import annotations

import math

import torch

OPERATOR_STAGE = "stage_2"                       # hourly + daily + weekly; no structural / capital heads
LOCKED_HEADS = ("divert", "admission_cap")       # held at the hospital's baseline for operator objectives
PENALTY = 10.0                                   # score = -objective - PENALTY * sum of weighted relative violations
OVERTIME_SHARE = 0.01                            # overtime may exceed baseline by at most 1% of baseline staff-hours/day

# flow index: weights on (candidate / baseline) of each metric; 1.0 at the baseline
FLOW_INDEX = {"wait_mean_min": 0.3, "ed_los_median_min": 0.3, "lwbs_rate": 0.2, "boarding_hours_per_day": 0.2}
# denominators never fall below these (keeps the ratio sane where the baseline is ~0)
FLOORS = {"wait_mean_min": 5.0, "wait_p95_min": 15.0, "ed_los_median_min": 60.0, "lwbs_rate": 0.002, "boarding_hours_per_day": 2.0,
          "labor_cost_per_day": 1.0, "operating_cost_per_day": 1.0, "deaths_per_10k": 5.0, "adverse_events_per_day": 0.2,
          "hi_acuity_wait_hours_per_day": 0.5, "diversion_hours_per_day": 1.0, "overtime_hours_per_day": 1.0, "transfers_per_day": 1.0}


def _c(metric, kind="hard", tol=0.0, weight=1.0, label=None, margin=0.0):
    """constraint: candidate <= baseline * (1 + tol) [+ absolute allowance]. `margin` is the extra relative
    head-room demanded while TUNING/TRAINING only (so held-out evaluation stays feasible); `weight` scales the
    tuning penalty (rare-event metrics get less, they are mostly noise at tuning sample sizes)."""
    return dict(metric=metric, kind=kind, tol=float(tol), weight=float(weight), margin=float(margin), label=label or metric)


# Deaths and adverse events are rare: at tuning sample sizes their paired difference is mostly noise, so the tuner
# gives them slack (negative margin) and a small weight and leans on the dense proxy (hours high-acuity patients
# wait). The held-out feasibility check has no slack: point estimate <= baseline.
_SAFETY = [_c("deaths_per_10k", "safety", weight=0.1, margin=-0.15, label="deaths per 10,000 arrivals"),
           _c("adverse_events_per_day", "safety", weight=0.3, margin=-0.08, label="adverse events per day"),
           _c("hi_acuity_wait_hours_per_day", "safety", margin=0.02, label="hours ESI 1-2 patients spend waiting, per day")]
_NO_DUMPING = [_c("diversion_hours_per_day", "hard", label="ambulance diversion hours per day"),
               _c("overtime_hours_per_day", "hard", label="overtime hours per day (cap: baseline + 1% of staff-hours)"),
               _c("transfers_per_day", "hard", tol=0.02, label="transfers out per day")]

OPERATOR_OBJECTIVES = {
    "same_budget_better_flow": dict(
        slug="same_budget", minimise="flow_index",
        label="Same budget, better flow",
        meaning="shortest waits and stays, fewest walk-outs and least boarding without spending more on labour or staffed space, "
                "with safety no worse than current practice, no extra diversion, bounded overtime and no extra transfers out",
        constraints=[_c("labor_cost_per_day", margin=0.005, label="labour cost per day"),
                     _c("operating_cost_per_day", margin=0.002, label="labour + fixed staffed-space cost per day")] + _SAFETY + _NO_DUMPING,
        # dense reward for PPO: weights on baseline-normalised hourly terms; `lagrange` terms get a multiplier
        reward_weights={"wait": 0.3, "los": 0.3, "lwbs": 0.2, "boarding": 0.2},
        lagrange={"labor": "labor_cost_per_day", "opcost": "operating_cost_per_day", "safety": "adverse_events_per_day",
                  "staff": "overtime_hours_per_day"}),
    "same_service_lower_cost": dict(
        slug="same_service", minimise="labor_cost_per_day",
        label="Same service, lower cost",
        meaning="lowest labour cost with door-to-provider wait (mean and 95th percentile), median ED length of stay, walk-outs, "
                "boarding and safety all no worse than current practice, no extra diversion, bounded overtime, no extra transfers out",
        constraints=[_c("wait_mean_min", margin=0.03, label="mean door-to-provider wait"),
                     _c("wait_p95_min", weight=0.5, margin=0.03, label="95th-percentile door-to-provider wait"),
                     _c("ed_los_median_min", margin=0.01, label="median ED length of stay"),
                     _c("lwbs_rate", margin=0.03, label="left-without-being-seen rate"),
                     _c("boarding_hours_per_day", weight=0.3, margin=0.0, label="boarding patient-hours per day"),
                     _c("operating_cost_per_day", label="labour + fixed staffed-space cost per day")] + _SAFETY + _NO_DUMPING,
        reward_weights={"labor": 1.0},
        lagrange={"wait": "wait_mean_min", "los": "ed_los_median_min", "lwbs": "lwbs_rate", "boarding": "boarding_hours_per_day",
                  "safety": "adverse_events_per_day", "staff": "overtime_hours_per_day", "opcost": "operating_cost_per_day"}),
}
OPERATOR_SLUG = {k: v["slug"] for k, v in OPERATOR_OBJECTIVES.items()}

# every per-episode number the gym reports (order fixed: rollout workers return a [rows, K] tensor in it)
EPISODE_METRICS = [
    "wait_mean_min", "wait_p95_min", "ed_los_median_min", "lwbs_rate", "cost_per_day", "margin_per_day", "cost_per_treated",
    "deaths_per_10k", "boarding_hours_per_day", "diversion_hours_per_day", "overtime_hours_per_day",          # contract summary
    "labor_cost_per_day", "fixed_cost_per_day", "operating_cost_per_day", "adverse_events_per_day", "deaths_per_day",
    "lwbs_per_day", "arrivals_per_day", "diverted_per_day", "treated_per_day", "admissions_per_day", "transfers_per_day",
    "ed_los_mean_min", "wait_patient_hours_per_day", "ed_patient_hours_per_day", "hi_acuity_wait_hours_per_day",
    "staff_hours_per_day", "revenue_per_day"]
LOWER_IS_BETTER = {k: True for k in EPISODE_METRICS}
for _k in ("margin_per_day", "treated_per_day", "revenue_per_day", "arrivals_per_day", "admissions_per_day", "staff_hours_per_day"):
    LOWER_IS_BETTER[_k] = False


def is_operator(objective) -> bool:
    return objective in OPERATOR_OBJECTIVES


def _get(x, k):
    return x[k] if isinstance(x, dict) else x[..., EPISODE_METRICS.index(k)]


def limit(con: dict, base, margin: bool = False):
    """The largest allowed value of the constraint's metric given the baseline mean."""
    k = con["metric"]
    b = _get(base, k)
    rel = con["tol"] - (con["margin"] if margin else 0.0)
    lim = b * (1.0 + rel)
    if k == "overtime_hours_per_day":
        lim = lim + OVERTIME_SHARE * _get(base, "staff_hours_per_day")
    return lim


def violations(objective: str, cand, base, margin: bool = False) -> dict:
    """metric -> relative excess over the limit (<= 0 means satisfied). cand / base: dict metric -> value
    (floats or tensors of GROUP MEANS), or tensors [..., K] in EPISODE_METRICS order."""
    out = {}
    for con in OPERATOR_OBJECTIVES[objective]["constraints"]:
        k = con["metric"]
        b = _get(base, k)
        den = b.clamp(min=FLOORS[k]) if isinstance(b, torch.Tensor) else max(float(b), FLOORS[k])
        out[k] = (_get(cand, k) - limit(con, base, margin)) / den
    return out


def flow_index(cand, base):
    """Weighted mean of candidate / baseline over the flow metrics (1.0 = the baseline; lower is better)."""
    f = 0.0
    for k, w in FLOW_INDEX.items():
        b = _get(base, k)
        den = b.clamp(min=FLOORS[k]) if isinstance(b, torch.Tensor) else max(float(b), FLOORS[k])
        f = f + w * _get(cand, k) / den
    return f


def goal_index(goals: dict, cand, base, scales: dict | None = None):
    """A user-chosen index: goals = metric -> signed weight (positive: minimise, negative: maximise), |weights|
    summing to 1. 1.0 at the baseline, lower is better. Each term is the candidate's distance from the baseline
    in units of `scales[metric]` - how far that metric can realistically be moved (rl/custom.py measures it as the
    spread between candidate policies) - so a rank-1 goal is not outvoted by a lower-ranked metric that merely
    happens to swing more in percentage terms. Without scales the unit is the baseline value itself."""
    f = 0.0
    for k, w in goals.items():
        b = _get(base, k)
        if scales and k in scales:
            den = float(scales[k])
        else:
            den = b.abs().clamp(min=FLOORS.get(k, 1e-6)) if isinstance(b, torch.Tensor) else max(abs(float(b)), FLOORS.get(k, 1e-6))
        r = 1.0 + (_get(cand, k) - b) / den
        f = f + (w * r if w >= 0 else -w * (2.0 - r))
    return f


def objective_value(objective: str, cand, base):
    """The minimised quantity as a ratio to baseline (1.0 = the baseline; lower is better)."""
    if OPERATOR_OBJECTIVES[objective]["minimise"] == "flow_index":
        return flow_index(cand, base)
    if isinstance(OPERATOR_OBJECTIVES[objective]["minimise"], dict):
        return goal_index(OPERATOR_OBJECTIVES[objective]["minimise"], cand, base)
    k = OPERATOR_OBJECTIVES[objective]["minimise"]
    b = _get(base, k)
    den = b.clamp(min=FLOORS[k]) if isinstance(b, torch.Tensor) else max(float(b), FLOORS[k])
    return _get(cand, k) / den


def operator_score(objective: str, cand, base, margin: bool = True, penalty: float = PENALTY):
    """Higher is better; 0 = exactly the baseline with every constraint met with its margin... more precisely
    score = (1 - objective ratio) - penalty * sum_k weight_k * relu(violation_k). Group means in, score out."""
    v = violations(objective, cand, base, margin)
    pen = 0.0
    for con in OPERATOR_OBJECTIVES[objective]["constraints"]:
        x = v[con["metric"]]
        pen = pen + con["weight"] * (torch.relu(x) if isinstance(x, torch.Tensor) else max(0.0, float(x)))
    return 1.0 - objective_value(objective, cand, base) - penalty * pen


def feasibility(objective: str, cand: dict, base: dict, diff_ci: dict | None = None) -> dict:
    """Hard check on evaluation numbers (no tuning margin). cand / base: metric -> mean over the evaluated
    episodes; diff_ci: optional metric -> (lo, hi) 95% interval of the paired difference candidate - baseline.

    A constraint is `met` when the point estimate is within its limit. For the rare-event safety metrics the
    interval is reported too: `status` is one of better / no worse / worse (not significant) / worse.
    `feasible` = every constraint met on the point estimate."""
    rows, ok = [], True
    v = violations(objective, cand, base, margin=False)
    for con in OPERATOR_OBJECTIVES[objective]["constraints"]:
        k = con["metric"]
        c, b, lim = float(cand[k]), float(base[k]), float(limit(con, base))
        met = bool(c <= lim + 1e-9)
        ci = (diff_ci or {}).get(k)
        if ci is not None and ci[1] < 0:
            status = "better"
        elif met:
            status = "no worse"
        elif ci is not None and ci[0] <= 0:
            status = "worse (difference not significant)"
        else:
            status = "worse"
        rows.append(dict(metric=k, label=con["label"], kind=con["kind"], candidate=c, baseline=b, limit=lim, met=met, status=status,
                         relative_excess=float(v[k]), diff_ci95=(list(ci) if ci is not None else None)))
        ok = ok and met
    return dict(feasible=bool(ok), constraints=rows, violated=[r["metric"] for r in rows if not r["met"]])


def robust_aggregate(member_scores: torch.Tensor, quantile: float = 0.25, blend: float = 0.5) -> torch.Tensor:
    """[..., n_members] -> [...]: (1 - blend) * mean + blend * mean of the worst `quantile` share of members.
    With one member this is that member's score."""
    n = member_scores.shape[-1]
    k = max(1, int(math.ceil(quantile * n)))
    worst = torch.sort(member_scores, dim=-1).values[..., :k].mean(-1)
    return (1.0 - blend) * member_scores.mean(-1) + blend * worst
