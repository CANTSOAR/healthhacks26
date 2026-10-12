"""Tune the parameterised rule-based manager per objective and per hospital with the cross-entropy method.

    python -m rl.tune --objective same_budget_better_flow --hospital rwjuh_nb --gpu-workers 2 --cpu-workers 8
    python -m rl.tune --objective min_cost --device cuda            # the legacy weighted objectives work as before

Every candidate is run on every (ensemble member, scenario) GROUP with common random numbers: all
candidates and the hospital's calibrated baseline (`fixed`) face the same seeds inside a group. Groups
run in parallel worker processes (rl.rollout). Robust score = blend of the mean and the worst quartile
over ensemble members (rl.objectives.robust_aggregate); with no ensemble file there is one member.

Operator objectives (rl.objectives) are scored on group means against the baseline rows, with a penalty
for every constraint violated (plus a tuning margin), and with `divert` / `admission_cap` locked at the
baseline. The result is a TUNED HEURISTIC (kind `tuned_heuristic`), not a learned agent. Seeds come from
the tuning range (common.SEED_TUNE); nothing here touches validation or evaluation seeds.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from .common import (OBJECTIVES, SEED_TUNE, TERMS, calibration_status, hospital_id, load_ensemble, load_scales, now_iso, objective_score,
                     sim_fingerprint, weights_dict, write_json)
from .managers import PARAM_NAMES, RULE_DEFAULT, RulePolicy, all_objectives, policy_dir, save_heuristic, theta_from_dict
from .objectives import (EPISODE_METRICS, LOCKED_HEADS, OPERATOR_OBJECTIVES, OPERATOR_STAGE, feasibility, is_operator, operator_score,
                         robust_aggregate)
from .rollout import group_task, run_groups


def baseline_theta(hospital: str | None = None) -> torch.Tensor:
    """Rule parameters that reproduce the hospital's calibrated baseline actions as closely as the rule can:
    the starting point of the search for the operator objectives (feasible by construction)."""
    from .common import get_spec
    d = {h["name"]: int(h["default"]) for h in get_spec(hospital=hospital)["action_spec"]}
    p = dict(RULE_DEFAULT)
    for s in ("day", "evening", "night"):
        p[f"md_{s}"], p[f"rn_{s}"] = d[f"md_{s}"] / 4.0, d[f"rn_{s}"] / 4.0
    p.update(md_demand_gain=0.0, rn_demand_gain=0.0, triage_nurses=d["triage_nurses"] / 2.0, admission_cap=d["admission_cap"] / 2.0,
             discharge_push_occ=(1.0 if d["discharge_push"] == 0 else 0.0), priority_rule=(d["priority_rule"] + 0.5) / 4.0,
             provider_split=(d["provider_split"] + 0.5) / 3.0, fast_track_thr=(0.0 if d["fast_track"] == 1 else 1.0),
             overflow_low_thr=1.0, overflow_high_gap=1.0, callin_rn_thr=1.0, callin_md_thr=1.0, divert_thr=1.0,
             agency_contract=d["agency_contract"] / 2.0, imaging_hours=d["imaging_hours"] / 2.0)
    return theta_from_dict(p)


@torch.no_grad()
def evaluate_population(theta: torch.Tensor, objective: str, scenarios: list[str], n_seeds: int, seed0: int, days: int,
                        device, scales: dict, stage="stage_1", hospital: str | None = None, members=(None,), gpu_workers: int = 0,
                        cpu_workers: int = 0, quantile: float = 0.25, log=None, detail: bool = False, chunk: int = 0):
    """theta [N, P] -> score [N] (robust over ensemble members; mean over scenarios and seeds) and the mean of
    every episode metric per candidate. With detail=True also returns per-group candidate / baseline means."""
    N = theta.shape[0]
    op = is_operator(objective)
    locked = LOCKED_HEADS if op else ()
    seeds = [seed0 + i for i in range(n_seeds)]
    # `chunk` > 0 splits each group's population into pieces of that many candidates (one worker process each) so a
    # many-core CPU box is used fully; seeds are explicit, so the rows are the same as in one batch. The baseline
    # rides along in the first piece of each group.
    step = int(chunk) if chunk and chunk > 0 else N
    pieces = [(a_, min(N, a_ + step)) for a_ in range(0, N, step)]
    tasks = []
    for m in members:
        for s in scenarios:
            for j, (a_, b_) in enumerate(pieces):
                pol = ([{"id": "fixed"}] if j == 0 else []) + [{"theta": theta[a_:b_].tolist(), "stage": stage, "locked": list(locked)}]
                tasks.append(group_task(hospital_id(hospital), s, m, pol, seeds, days, device=str(device), stage=stage, locked=locked,
                                        scales=scales, tag=f"{s}/m{m}/{j}", threads=1 if len(pieces) > 1 else 2))
    raw = run_groups(tasks, gpu_workers, cpu_workers, log=log)
    res = []
    for g in range(0, len(raw), len(pieces)):                     # stitch the pieces of one group back together
        part = raw[g:g + len(pieces)]
        res.append({k: torch.cat([x[k] for x in part], 0) for k in ("episode", "terms")})
    thr = float(scales.get("p95_wait_threshold_min", 60.0))
    per_member, cand_all, groups = [], [], []
    i = 0
    for m in members:
        sc_m = []
        for s in scenarios:
            r = res[i]
            i += 1
            ep = r["episode"]                                     # [1 + N, n_seeds, K]; row 0 is the baseline
            base, cand = ep[0].mean(0), ep[1:].mean(1)            # [K], [N, K]
            if op:
                sc = operator_score(objective, cand, base.unsqueeze(0), margin=True)
            else:
                p95 = ep[1:, :, EPISODE_METRICS.index("wait_p95_min")]
                sc = objective_score(objective, r["terms"][1:], p95, thr).mean(1)
            sc_m.append(sc)
            cand_all.append(cand)
            groups.append(dict(member=m, scenario=s, base=base, cand=cand))
        per_member.append(torch.stack(sc_m).mean(0))
    score = robust_aggregate(torch.stack(per_member, -1), quantile)
    mean = torch.stack(cand_all).mean(0)
    summ = {k: mean[:, j] for j, k in enumerate(EPISODE_METRICS)}
    return (score, summ, groups) if detail else (score, summ)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objective", required=True, choices=list(OBJECTIVES) + list(OPERATOR_OBJECTIVES))
    ap.add_argument("--hospital", default=None)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--gpu-workers", type=int, default=0, help="worker processes on cuda (0 with no cpu workers: run inline on --device)")
    ap.add_argument("--cpu-workers", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=0, help="candidates per worker task (0 = a whole population per group)")
    ap.add_argument("--pop", type=int, default=48)
    ap.add_argument("--seeds", type=int, default=6, help="seeds per group (member x scenario) per candidate")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--gens", type=int, default=10)
    ap.add_argument("--elite", type=int, default=10)
    ap.add_argument("--std", type=float, default=0.22)
    ap.add_argument("--min-std", type=float, default=0.03)
    ap.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    ap.add_argument("--members-per-gen", type=int, default=4, help="ensemble members per generation: member 0 plus random others")
    ap.add_argument("--final-members", type=int, default=8)
    ap.add_argument("--final-seeds", type=int, default=12)
    ap.add_argument("--final-days", type=int, default=14)
    ap.add_argument("--quantile", type=float, default=0.25, help="robust score: blend of the mean and this worst share of members")
    ap.add_argument("--stage", default=None)
    ap.add_argument("--init", default=None, help="a saved tuned heuristic (JSON) to start the search from")
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    h = hospital_id(a.hospital)
    op = is_operator(a.objective)
    slug = all_objectives()[a.objective]
    stage = a.stage or (OPERATOR_STAGE if op else "stage_1")
    run = Path(a.run or f"runs/{h}/tune_{slug}")
    run.mkdir(parents=True, exist_ok=True)
    out = Path(a.out or policy_dir(h) / f"tuned_{slug}.json")
    scales = load_scales(hospital=h)
    ens = load_ensemble(h)
    n_mem = len(ens["members"])
    all_members = list(range(n_mem)) if ens["exists"] else [None]
    g = torch.Generator().manual_seed(a.seed)
    P = len(PARAM_NAMES)
    base_th, default_th = baseline_theta(h), theta_from_dict(RULE_DEFAULT)
    mean = base_th.clone() if op else default_th.clone()
    if a.init and Path(a.init).exists():
        mean = theta_from_dict(json.loads(Path(a.init).read_text())["params"])
    std = torch.full((P,), a.std)
    hist = []
    log = open(run / "log.txt", "a")

    def say(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    def members_for(gen):
        if all_members == [None]:
            return [None]
        k = min(a.members_per_gen, n_mem)
        others = [m for m in all_members if m != 0]
        pick = [others[i] for i in torch.randperm(len(others), generator=g)[:k - 1].tolist()]
        return [0] + pick

    kw = dict(hospital=h, gpu_workers=a.gpu_workers, cpu_workers=a.cpu_workers, quantile=a.quantile, chunk=a.chunk)
    say(f"[{now_iso()}] tune {a.objective} hospital={h} members={n_mem} ({ens['source'] or 'no ensemble file: point calibration only'}) "
        f"pop={a.pop} seeds={a.seeds} days={a.days} gens={a.gens} scen={a.scenarios} stage={stage} fp={sim_fingerprint()} "
        f"calibration={calibration_status(h)}")
    el = mean.unsqueeze(0)
    best_seen = mean.clone()
    for gen in range(a.gens):
        t0 = time.time()
        cand = (mean + std * torch.randn((a.pop, P), generator=g)).clamp(0, 1)
        cand[0] = mean
        if gen == 0:
            cand[1], cand[2] = default_th, base_th
        cand[3] = best_seen                               # the incumbent is re-scored on every generation's fresh seeds
        mem = members_for(gen)
        sc, summ = evaluate_population(cand, a.objective, a.scenarios, a.seeds, SEED_TUNE + gen * 1000, a.days, a.device, scales, stage,
                                       members=mem, **kw)
        order = torch.argsort(sc, descending=True)
        el = cand[order[:a.elite]]
        best_seen = cand[order[0]].clone()
        mean = 0.7 * el.mean(0) + 0.3 * mean
        std = (0.7 * el.std(0) + 0.3 * std).clamp(min=a.min_std)
        b = int(order[0])
        rec = dict(gen=gen, best=float(sc[b]), mean_cand=float(sc[0]), pop_mean=float(sc.mean()), seconds=time.time() - t0, members=mem,
                   best_summary={k: float(v[b]) for k, v in summ.items()})
        hist.append(rec)
        bs = rec["best_summary"]
        say(f"gen {gen} best {rec['best']:.4f} mean-cand {rec['mean_cand']:.4f} pop {rec['pop_mean']:.4f} members {mem} "
            f"labor/day {bs['labor_cost_per_day']:.0f} wait {bs['wait_mean_min']:.1f} p95 {bs['wait_p95_min']:.0f} "
            f"los {bs['ed_los_median_min']:.0f} lwbs {bs['lwbs_rate']:.4f} board {bs['boarding_hours_per_day']:.1f} ({rec['seconds']:.0f}s)")
        write_json(run / "state.json", dict(mean=mean.tolist(), std=std.tolist(), hist=hist, elite=el.tolist()))
    # final round on fresh tuning seeds and more members: distribution mean, last elites, the baseline-equivalent
    # rule and the hand-written default
    init_th = [theta_from_dict(json.loads(Path(a.init).read_text())["params"]).unsqueeze(0)] if a.init and Path(a.init).exists() else []
    fin = torch.cat([mean.unsqueeze(0), el[:5]] + init_th + [base_th.unsqueeze(0), default_th.unsqueeze(0)], 0)
    fm = all_members if all_members == [None] else all_members[:max(1, a.final_members)]
    sc, summ, groups = evaluate_population(fin, a.objective, a.scenarios, a.final_seeds, SEED_TUNE + 100_000, a.final_days, a.device, scales,
                                           stage, members=fm, detail=True, **kw)
    b = int(torch.argmax(sc))
    say(f"final round scores {['%.4f' % float(x) for x in sc]} -> pick {b} (last two entries = baseline-equivalent rule, hand-written default)")
    feas = None
    if op:
        feas = []
        for gr in groups:
            cd = {k: float(gr["cand"][b, j]) for j, k in enumerate(EPISODE_METRICS)}
            bd = {k: float(gr["base"][j]) for j, k in enumerate(EPISODE_METRICS)}
            f = feasibility(a.objective, cd, bd)
            feas.append(dict(member=gr["member"], scenario=gr["scenario"], feasible=f["feasible"], violated=f["violated"]))
        say("final-round feasibility on tuning seeds (no margin): " + json.dumps(feas))
    lab = OPERATOR_OBJECTIVES[a.objective]["label"] if op else a.objective
    pol = RulePolicy(fin[b], id=f"tuned_{slug}", kind="tuned_heuristic", label=f"Tuned heuristic: {lab}",
                     objective=a.objective, reward_weights=weights_dict(a.objective), stage=stage, hospital=h,
                     locked=LOCKED_HEADS if op else ())
    save_heuristic(out, pol, dict(
        tuning=dict(method=f"cross-entropy method over {P} rule parameters; groups = ensemble member x scenario, common random numbers, "
                           "baseline rows on the same seeds; robust score over members",
                    pop=a.pop, seeds_per_group=a.seeds, days=a.days, gens=a.gens, scenarios=a.scenarios, stage=stage,
                    ensemble=dict(n_members=n_mem, source=ens["source"], members_per_gen=a.members_per_gen, final_members=fm, quantile=a.quantile),
                    seed_range=[SEED_TUNE, SEED_TUNE + 100_000 + a.final_seeds], final_score=float(sc[b]),
                    default_rule_score=float(sc[-1]), baseline_rule_score=float(sc[-2]), picked=b,
                    final_summary={k: float(v[b]) for k, v in summ.items()}, final_feasibility=feas,
                    p95_wait_threshold_min=scales.get("p95_wait_threshold_min"), history=hist, finished=now_iso())))
    say(f"saved {out}")


if __name__ == "__main__":
    main()
