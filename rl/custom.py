"""Optimise the hospital for a reward the user picks. All numbers SIMULATED.

    python -m rl.custom --spec spec.json --out runs/custom/<job> --hospital rwjuh_nb --cpu-workers 92

spec.json:
    {"goals": [{"metric": "profit", "direction": "max", "rank": 1},
               {"metric": "wait", "direction": "min", "rank": 2}],
     "guardrails": true}

Each goal is one entry of METRIC_MENU with a direction (max | min) and a rank (1 = most important; ties
allowed). Ranks become weights: every rank is worth half the rank above it, weights sum to 1. The reward
is the weighted index of the chosen metrics as ratios to the hospital's calibrated baseline (1.0 = current
practice, lower is better); a "max" goal enters mirrored, so pushing it up lowers the index. Nothing stops
a user from asking for something that makes no sense (maximise waiting): the optimiser follows the reward.

Guardrails (on by default): deaths, adverse events and high-acuity waiting no worse than baseline, no extra
diversion, bounded overtime, no extra transfers out. Ambulance diversion and the admission cap stay locked
at the baseline either way.

The search is the cross-entropy method over the rule manager's parameters (rl/tune.py), started from the
hospital's baseline AND every policy already tuned for this hospital, so a few generations are enough. The
baseline is always one of the candidates in the final round, so the result is never worse than current
practice on the chosen index on the tuning seeds. The comparison that is reported is on HELD-OUT seeds.
Writes <out>/status.json while it runs (a UI can poll it) and <out>/result.json at the end.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from . import objectives as O
from .common import (SEED_EVAL, SEED_TUNE, calibration_status, fingerprints, hospital_id, load_ensemble, load_scales, now_iso, write_json)
from .managers import PARAM_NAMES, RULE_DEFAULT, RulePolicy, policy_dir, save_heuristic, theta_from_dict
from .objectives import EPISODE_METRICS, LOCKED_HEADS, LOWER_IS_BETTER, OPERATOR_STAGE
from .rollout import group_task, run_groups

# what a user can pick -> the episode metrics behind it (weights within one entry sum to 1)
METRIC_MENU = {
    "profit": dict(label="Profit (operating margin)", unit="$/day", parts={"margin_per_day": 1.0}, natural="max"),
    "revenue": dict(label="Revenue", unit="$/day", parts={"revenue_per_day": 1.0}, natural="max"),
    "total_cost": dict(label="Total cost", unit="$/day", parts={"cost_per_day": 1.0}, natural="min"),
    "labor_cost": dict(label="Labor cost", unit="$/day", parts={"labor_cost_per_day": 1.0}, natural="min"),
    "wait": dict(label="Door-to-provider wait (mean)", unit="min", parts={"wait_mean_min": 1.0}, natural="min"),
    "wait_p95": dict(label="Worst-case wait (95th percentile)", unit="min", parts={"wait_p95_min": 1.0}, natural="min"),
    "length_of_stay": dict(label="ED length of stay (median)", unit="min", parts={"ed_los_median_min": 1.0}, natural="min"),
    "walkouts": dict(label="Patients who leave without being seen", unit="share", parts={"lwbs_rate": 1.0}, natural="min"),
    "boarding": dict(label="Boarding (admitted patients held in the ED)", unit="patient-hours/day", parts={"boarding_hours_per_day": 1.0}, natural="min"),
    "deaths": dict(label="Deaths", unit="per 10,000 arrivals", parts={"deaths_per_10k": 1.0}, natural="min"),
    "adverse_events": dict(label="Adverse events", unit="per day", parts={"adverse_events_per_day": 1.0}, natural="min"),
    "high_acuity_wait": dict(label="Sickest patients (ESI 1-2) waiting", unit="patient-hours/day", parts={"hi_acuity_wait_hours_per_day": 1.0}, natural="min"),
    "patients_treated": dict(label="Patients treated", unit="per day", parts={"treated_per_day": 1.0}, natural="max"),
    "overtime": dict(label="Staff overtime", unit="hours/day", parts={"overtime_hours_per_day": 1.0}, natural="min"),
    "staff_hours": dict(label="Staff hours scheduled", unit="hours/day", parts={"staff_hours_per_day": 1.0}, natural="min"),
    # no satisfaction survey is simulated: a stated proxy built from what patients experience at the front door.
    # `invert`: higher experience = LOWER wait, stay and walk-outs, so "maximise" pushes the parts down.
    "patient_experience": dict(label="Patient experience (proxy: shorter wait and stay, fewer walk-outs)", unit="index",
                               parts={"wait_mean_min": 0.4, "ed_los_median_min": 0.3, "lwbs_rate": 0.3}, natural="max", proxy=True, invert=True),
}
GUARDRAILS = O._SAFETY + O._NO_DUMPING
NEUTRAL = {"staff_hours_per_day", "arrivals_per_day", "admissions_per_day", "diverted_per_day", "cost_per_treated", "fixed_cost_per_day"}
KEY = "custom"


def goal_weights(goals: list[dict]) -> tuple[dict, list[dict]]:
    """goals -> (episode metric -> signed weight, the goals with their weights). Positive = minimise."""
    rows = []
    for g in goals:
        if g.get("direction") not in ("max", "min"):
            continue                                        # "ignore"
        if g["metric"] not in METRIC_MENU:
            raise ValueError(f"unknown metric '{g['metric']}'; have {sorted(METRIC_MENU)}")
        rows.append(dict(metric=g["metric"], direction=g["direction"], rank=max(1, int(g.get("rank") or 1))))
    if not rows:
        raise ValueError("pick at least one metric to maximise or minimise")
    ranks = sorted({r["rank"] for r in rows})
    for r in rows:
        r["raw"] = 0.5 ** ranks.index(r["rank"])            # dense ranks: 1, 1/2, 1/4, ...
    tot = sum(r["raw"] for r in rows)
    signed: dict = {}
    for r in rows:
        r["weight"] = r.pop("raw") / tot
        sign = 1.0 if r["direction"] == "min" else -1.0
        if METRIC_MENU[r["metric"]].get("invert"):
            sign = -sign
        for k, share in METRIC_MENU[r["metric"]]["parts"].items():
            # a proxy built from lower-is-better parts flips as a whole when the user maximises it
            signed[k] = signed.get(k, 0.0) + sign * r["weight"] * share
        r["label"] = METRIC_MENU[r["metric"]]["label"]
        r["against_the_grain"] = r["direction"] != METRIC_MENU[r["metric"]]["natural"]
    norm = sum(abs(v) for v in signed.values()) or 1.0      # opposite asks on one metric can cancel
    return {k: v / norm for k, v in signed.items() if abs(v) > 1e-12}, rows


def register(spec: dict) -> dict:
    """Install the user's objective under OPERATOR_OBJECTIVES['custom'] (this process only)."""
    signed, rows = goal_weights(spec.get("goals") or [])
    O.OPERATOR_OBJECTIVES[KEY] = dict(
        slug="custom", minimise=signed, label="Custom reward",
        meaning="; ".join(f"{'maximize' if r['direction'] == 'max' else 'minimize'} {r['label']} (rank {r['rank']}, weight {r['weight']:.2f})" for r in rows),
        constraints=list(GUARDRAILS) if spec.get("guardrails", True) else [], reward_weights={}, lagrange={})
    return dict(signed_weights=signed, goals=rows, guardrails=bool(spec.get("guardrails", True)))


def score_groups(groups: list[dict], signed: dict, scales: dict | None, n_scen: int) -> torch.Tensor:
    """Candidate scores [N] from per-group means (rl.tune.evaluate_population(detail=True)): 1 - goal index -
    guardrail penalty, averaged over scenarios, robust over ensemble members."""
    per_group = []
    for gr in groups:
        base, cand = gr["base"].unsqueeze(0), gr["cand"]
        sc = 1.0 - O.goal_index(signed, cand, base, scales)
        v = O.violations(KEY, cand, base, margin=True)
        for con in O.OPERATOR_OBJECTIVES[KEY]["constraints"]:
            sc = sc - O.PENALTY * con["weight"] * torch.relu(v[con["metric"]])
        per_group.append(sc)
    per_member = torch.stack(per_group).reshape(len(groups) // n_scen, n_scen, -1).mean(1)       # groups are member-major
    return O.robust_aggregate(per_member.T)


def measure_scales(groups: list[dict], signed: dict) -> dict:
    """How far each chosen metric moves between candidate policies (std over the first generation's candidates
    of the mean over groups), floored at 1% of the baseline: the unit the ranks are traded in."""
    cand = torch.stack([gr["cand"] for gr in groups]).mean(0)                                    # [N, K]
    base = torch.stack([gr["base"] for gr in groups]).mean(0)
    out = {}
    for k in signed:
        j = EPISODE_METRICS.index(k)
        lo, hi = torch.quantile(cand[:, j], torch.tensor([0.1, 0.9]))                             # robust to the few wild candidates
        out[k] = float(max(float(hi - lo) / 2.56, 0.01 * abs(float(base[j])), 1e-9))
    return out


def warm_starts(h: str) -> list[tuple[str, torch.Tensor]]:
    """Rule parameters of every heuristic already tuned for this hospital (any objective)."""
    out = []
    for f in sorted(policy_dir(h).glob("tuned_*.json")):
        try:
            d = json.loads(f.read_text())
            if d.get("type") == "rule_params" and d.get("stage", OPERATOR_STAGE) == OPERATOR_STAGE:
                out.append((d["id"], theta_from_dict(d["params"])))
        except Exception:
            pass
    return out


def run(spec: dict, out: Path, hospital: str | None = None, cpu_workers: int = 8, gpu_workers: int = 0, device: str = "cpu", pop: int = 46,
        chunk: int = 2, gens: int = 4, seeds: int = 4, days: int = 10, members_per_gen: int = 2, eval_members: int = 6, eval_seeds: int = 16,
        eval_days: int = 30, scenarios=("normal_week", "flu_surge"), eval_scenarios=("normal_week", "flu_surge", "nursing_absences"),
        seed: int = 0) -> dict:
    from .headline import paired_table, what_changes
    from .tune import baseline_theta, evaluate_population
    t00 = time.time()
    h = hospital_id(hospital)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    reg = register(spec)
    scales = load_scales(hospital=h)
    ens = load_ensemble(h)
    all_members = list(range(len(ens["members"]))) if ens["exists"] else [None]
    g = torch.Generator().manual_seed(seed)
    P = len(PARAM_NAMES)
    base_th, default_th = baseline_theta(h), theta_from_dict(RULE_DEFAULT)
    starts = warm_starts(h)
    hist: list = []
    signed, goal_scales = reg["signed_weights"], None

    def status(phase, **kw):
        write_json(out / "status.json", dict(phase=phase, hospital_id=h, started=started, updated=now_iso(), elapsed_s=time.time() - t00,
                                             gens=gens, pop=pop, history=hist, objective=reg, **kw), indent=1)

    started = now_iso()
    status("starting")
    kw = dict(hospital=h, gpu_workers=gpu_workers, cpu_workers=cpu_workers, chunk=chunk)

    def members_for():
        if all_members == [None]:
            return [None]
        others = [m for m in all_members if m != 0]
        return [0] + [others[i] for i in torch.randperm(len(others), generator=g)[:max(0, members_per_gen - 1)].tolist()]

    # generation 0 is seeded with the baseline, the hand-written rule and everything already tuned for this hospital
    mean, std = base_th.clone(), torch.full((P,), 0.18)
    best_seen = base_th.clone()
    for gen in range(gens):
        t0 = time.time()
        cand = (mean + std * torch.randn((pop, P), generator=g)).clamp(0, 1)
        cand[0], cand[1] = mean, best_seen
        if gen == 0:
            fixed_c = [base_th, default_th] + [t for _, t in starts]
            for i, t in enumerate(fixed_c[:pop - 2]):
                cand[2 + i] = t
            for i in range(2 + len(fixed_c), pop):               # the rest: jitter around a known policy, not only the baseline
                src = fixed_c[int(torch.randint(0, len(fixed_c), (1,), generator=g))]
                cand[i] = (src + 0.12 * torch.randn((P,), generator=g)).clamp(0, 1)
        _, summ, groups = evaluate_population(cand, KEY, list(scenarios), seeds, SEED_TUNE + 500_000 + gen * 1000, days, device, scales,
                                              OPERATOR_STAGE, members=members_for(), detail=True, **kw)
        if goal_scales is None:
            goal_scales = measure_scales(groups, signed)
        sc = score_groups(groups, signed, goal_scales, len(scenarios))
        order = torch.argsort(sc, descending=True)
        el = cand[order[:8]]
        best_seen = cand[order[0]].clone()
        mean = 0.7 * el.mean(0) + 0.3 * mean
        std = (0.7 * el.std(0) + 0.3 * std).clamp(min=0.03)
        b = int(order[0])
        hist.append(dict(gen=gen, best_score=float(sc[b]), baseline_score=float(sc[2]) if gen == 0 else None, seconds=time.time() - t0,
                         best={k: float(v[b]) for k, v in summ.items()}))
        status("searching", gen=gen + 1)
    # final round on fresh tuning seeds: the search's answer, the elites, every warm start and the baseline itself
    fin = torch.cat([mean.unsqueeze(0), el[:5], base_th.unsqueeze(0)] + [t.unsqueeze(0) for _, t in starts], 0)
    status("selecting", gen=gens)
    fm = all_members if all_members == [None] else all_members[:4]
    _, _, groups = evaluate_population(fin, KEY, list(scenarios), 8, SEED_TUNE + 700_000, 14, device, scales, OPERATOR_STAGE, members=fm,
                                       detail=True, **kw)
    sc = score_groups(groups, signed, goal_scales, len(scenarios))
    sc[len(fin) - 1 - len(starts)] += 1e-6                    # ties go to the baseline
    b = int(torch.argmax(sc))
    names = ["search mean"] + [f"elite {i}" for i in range(5)] + ["baseline (current practice)"] + [n for n, _ in starts]
    theta = fin[b]
    picked_baseline = names[b].startswith("baseline")
    pol = RulePolicy(theta, id="custom", kind="tuned_heuristic", label="Optimized for your reward", objective=KEY, reward_weights={},
                     stage=OPERATOR_STAGE, hospital=h, locked=LOCKED_HEADS)
    save_heuristic(out / "policy.json", pol, dict(custom=reg, picked=names[b]))

    # held-out comparison against the calibrated baseline, same seeds, several twins, several scenarios
    status("evaluating", gen=gens, picked=names[b])
    em = all_members if all_members == [None] else all_members[:eval_members]
    ev_seeds = [SEED_EVAL + 50_000 + i for i in range(eval_seeds)]
    tasks = []
    for s in eval_scenarios:
        for m in em:
            tasks.append(group_task(h, s, m, [{"id": "fixed"}, {"theta": [theta.tolist()], "stage": OPERATOR_STAGE, "locked": list(LOCKED_HEADS)}],
                                    ev_seeds, eval_days, device=device, stage="stage_3", scales=scales, want_actions=(s == eval_scenarios[0]),
                                    tag=f"{s}/m{m}", threads=1))
    res = run_groups(tasks, gpu_workers, cpu_workers)
    by_scen, changes = {}, []
    for i, s in enumerate(eval_scenarios):
        rs = res[i * len(em):(i + 1) * len(em)]
        vals = torch.stack([r["episode"] for r in rs], 1)                       # [2, M, S, K]; 0 = baseline, 1 = policy
        tab = paired_table(vals[1], vals[0])
        basem, candm = vals[0].mean((0, 1)), vals[1].mean((0, 1))
        idx = float(O.goal_index(signed, candm, basem, goal_scales))
        for k, row in tab.items():
            lo, hi = row["diff_ci95"]
            better = (hi < 0) if LOWER_IS_BETTER[k] else (lo > 0)
            worse = (lo > 0) if LOWER_IS_BETTER[k] else (hi < 0)
            row["reading"] = "better" if better else ("worse" if worse else "no significant change")
            if k in NEUTRAL and row["reading"] != "no significant change":
                row["reading"] = "changed"                    # neither good nor bad in itself
            row["chosen_weight"] = signed.get(k, 0.0)
        per_member = [float(O.goal_index(signed, vals[1, j].mean(0), vals[0, j].mean(0), goal_scales)) for j in range(len(em))]
        cd, bd = {k: float(candm[j]) for j, k in enumerate(EPISODE_METRICS)}, {k: float(basem[j]) for j, k in enumerate(EPISODE_METRICS)}
        guard = None
        if O.OPERATOR_OBJECTIVES[KEY]["constraints"]:
            f = O.feasibility(KEY, cd, bd, {k: tab[k]["diff_ci95"] for k in tab})
            guard = dict(all_met=f["feasible"], rows=f["constraints"])
        by_scen[s] = dict(index=idx, index_change_pct=100.0 * (idx - 1.0), index_by_twin=per_member,
                          twins_improved=sum(1 for x in per_member if x < 1.0), n_twins=len(em), metrics=tab, guardrails=guard)
        if i == 0 and rs[0].get("actions"):
            ev = dict(names=["fixed", "theta0"], actions={k: torch.stack([r["actions"][k] for r in rs]).mean(0) for k in rs[0]["actions"]},
                      actions_by_dow={k: torch.stack([r["actions_by_dow"][k] for r in rs]).mean(0) for k in rs[0]["actions_by_dow"]},
                      option_values=rs[0]["option_values"], option_labels=rs[0]["option_labels"], defaults_by_member=[r["defaults"] for r in rs])
            changes = what_changes(ev, "theta0", pol.params_dict())
            staffing = {hd: dict(values=ev["option_values"][hd], baseline=ev["actions"][hd][0].mean(0).tolist(), policy=ev["actions"][hd][1].mean(0).tolist())
                        for hd in ("md_day", "md_evening", "md_night", "rn_day", "rn_evening", "rn_night")}
    n0 = by_scen[eval_scenarios[0]]
    parts = []
    for r in sorted(reg["goals"], key=lambda r: r["rank"]):
        for k in METRIC_MENU[r["metric"]]["parts"]:
            m = n0["metrics"][k]
            want_down = (r["direction"] == "min") != bool(METRIC_MENU[r["metric"]].get("invert"))
            got = (m["diff_ci95"][1] < 0) if want_down else (m["diff_ci95"][0] > 0)
            lost = (m["diff_ci95"][0] > 0) if want_down else (m["diff_ci95"][1] < 0)
            r.setdefault("outcome", []).append(dict(metric=k, pct=m["pct"], diff=m["diff"], achieved=bool(got), went_against=bool(lost)))
        o = r["outcome"]
        pct = sum((x["pct"] or 0.0) * w for x, w in zip(o, METRIC_MENU[r["metric"]]["parts"].values()))
        if METRIC_MENU[r["metric"]].get("invert"):
            pct = -pct                                        # the proxy improves when its parts fall
        parts.append(f"{r['label']} {pct:+.1f}% (rank {r['rank']}, asked to {'maximize' if r['direction'] == 'max' else 'minimize'}"
                     + (": moved the way you asked" if all(x["achieved"] for x in o) else
                        (": moved AGAINST what you asked" if any(x["went_against"] for x in o) else ": no significant change")) + ")")
    headline = ("Nothing the search found beats current practice on the reward you chose; the plan shown is current practice."
                if picked_baseline else
                "Against current practice in the simulated twin, the plan optimized for your reward gives: " + "; ".join(parts)
                + f". Better on your reward in {n0['twins_improved']} of {n0['n_twins']} twins consistent with the public record.")
    result = dict(
        **{**fingerprints(h), "hospital_id": h}, synthetic=True, generated=now_iso(), seconds=time.time() - t00, objective=reg,
        calibration=calibration_status(h), picked=names[b], picked_baseline=picked_baseline,
        headline=headline, goal_scales=goal_scales,
        scenarios=by_scen, what_changes=changes, staffing=staffing if changes else None, params=pol.params_dict(), search=hist,
        protocol=dict(held_out_seeds=[ev_seeds[0], ev_seeds[-1]], days=eval_days, twins=len(em), scenarios=list(eval_scenarios),
                      search=dict(pop=pop, gens=gens, seeds=seeds, days=days, warm_starts=[n for n, _ in starts]),
                      note="Simulated. Calibrated to public aggregates; not validated on the hospital's operational data. Intervals are 95% "
                           "bootstrap over twins and seeds, paired with the baseline on the same patients."),
        menu={k: dict(label=v["label"], unit=v["unit"], natural=v["natural"], proxy=bool(v.get("proxy"))) for k, v in METRIC_MENU.items()})
    write_json(out / "result.json", result, indent=1)
    status("done", gen=gens, picked=names[b], headline=result["headline"])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hospital", default=None)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--cpu-workers", type=int, default=8)
    ap.add_argument("--gpu-workers", type=int, default=0)
    ap.add_argument("--pop", type=int, default=46)
    ap.add_argument("--chunk", type=int, default=2)
    ap.add_argument("--gens", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--eval-members", type=int, default=6)
    ap.add_argument("--eval-seeds", type=int, default=16)
    ap.add_argument("--eval-days", type=int, default=30)
    a = ap.parse_args()
    try:
        r = run(json.loads(Path(a.spec).read_text()), Path(a.out), a.hospital, a.cpu_workers, a.gpu_workers, a.device, a.pop, a.chunk, a.gens,
                a.seeds, a.days, eval_members=a.eval_members, eval_seeds=a.eval_seeds, eval_days=a.eval_days)
        print(r["headline"])
    except Exception as e:                                   # the UI polls status.json: make failures visible there
        write_json(Path(a.out) / "status.json", dict(phase="failed", error=f"{type(e).__name__}: {e}", updated=now_iso()), indent=1)
        raise


if __name__ == "__main__":
    main()
