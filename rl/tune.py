"""Tune the parameterised rule-based manager per objective with the cross-entropy method.

    python -m rl.tune --objective min_cost --device cuda --run runs/tune_min_cost

A whole population is evaluated as one simulator batch (population x seeds hospitals per
scenario) with common random numbers: every candidate faces the same seeds. The result is a
TUNED HEURISTIC (kind `tuned_heuristic`), not a learned agent. Seeds come from the tuning
range (common.SEED_TUNE); nothing here touches evaluation seeds.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from .common import (CONSTRAINED, OBJ_SLUG, OBJECTIVES, POLICY_DIR, SEED_TUNE, load_scales, now_iso, objective_score,
                     sim_fingerprint, weights_dict, write_json)
from .env import ConcatEnv, HospitalEnv
from .managers import PARAM_NAMES, RULE_DEFAULT, RulePolicy, save_heuristic, theta_from_dict


@torch.no_grad()
def evaluate_population(theta: torch.Tensor, objective: str, scenarios: list[str], n_seeds: int, seed0: int, days: int,
                        device, scales: dict, stage="stage_1") -> tuple[torch.Tensor, dict]:
    """theta [N, P] -> score [N] (mean over scenarios x seeds), and mean summary metrics per candidate."""
    N = theta.shape[0]
    B1 = N * n_seeds
    seeds = (seed0 + torch.arange(n_seeds)).repeat(N)                   # row = cand * n_seeds + seed
    envs = [HospitalEnv(s, B1, device, seeds, days * 24, stage=stage, weights=objective,
                        scales=scales, auto_reset=False) for s in scenarios]
    env = ConcatEnv(envs) if len(envs) > 1 else envs[0]
    th = theta.to(device).repeat_interleave(n_seeds, 0).repeat(len(scenarios), 1)
    pol = RulePolicy(th, stage=stage)
    pol.reset(env.B, device)
    obs = env.reset()
    for _ in range(days * 24):
        obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
    p95 = info["summary"]["wait_p95_min"]
    sc = objective_score(objective, info["terms_mean"], p95, scales["p95_wait_threshold_min"])
    per = lambda x: x.reshape(len(scenarios), N, n_seeds).mean((0, 2))   # noqa: E731
    summ = {k: per(v).cpu() for k, v in info["summary"].items()}
    return per(sc).cpu(), summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objective", required=True, choices=list(OBJECTIVES))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--pop", type=int, default=48)
    ap.add_argument("--seeds", type=int, default=6, help="seeds per scenario per candidate")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--gens", type=int, default=8)
    ap.add_argument("--elite", type=int, default=10)
    ap.add_argument("--std", type=float, default=0.25)
    ap.add_argument("--min-std", type=float, default=0.03)
    ap.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    ap.add_argument("--final-seeds", type=int, default=16)
    ap.add_argument("--stage", default="stage_1")
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    slug = OBJ_SLUG[a.objective]
    run = Path(a.run or f"runs/tune_{slug}")
    run.mkdir(parents=True, exist_ok=True)
    out = Path(a.out or POLICY_DIR / f"tuned_{slug}.json")
    scales = load_scales()
    g = torch.Generator().manual_seed(a.seed)
    P = len(PARAM_NAMES)
    mean = theta_from_dict(RULE_DEFAULT)
    std = torch.full((P,), a.std)
    best = (-1e30, mean.clone())
    hist = []
    log = open(run / "log.txt", "a")

    def say(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    say(f"[{now_iso()}] tune {a.objective} pop={a.pop} seeds={a.seeds} days={a.days} gens={a.gens} scen={a.scenarios} fp={sim_fingerprint()}")
    for gen in range(a.gens):
        t0 = time.time()
        cand = (mean + std * torch.randn((a.pop, P), generator=g)).clamp(0, 1)
        cand[0] = mean
        if gen == 0:
            cand[1] = theta_from_dict(RULE_DEFAULT)
        seed0 = SEED_TUNE + gen * 1000
        sc, summ = evaluate_population(cand, a.objective, a.scenarios, a.seeds, seed0, a.days, a.device, scales, a.stage)
        order = torch.argsort(sc, descending=True)
        el = cand[order[:a.elite]]
        mean = 0.7 * el.mean(0) + 0.3 * mean
        std = (0.7 * el.std(0) + 0.3 * std).clamp(min=a.min_std)
        b = int(order[0])
        rec = dict(gen=gen, best=float(sc[b]), mean_cand=float(sc[0]), pop_mean=float(sc.mean()), seconds=time.time() - t0,
                   best_summary={k: float(v[b]) for k, v in summ.items()})
        hist.append(rec)
        say(f"gen {gen} best {rec['best']:.4f} mean-cand {rec['mean_cand']:.4f} pop {rec['pop_mean']:.4f} "
            f"cost/day {rec['best_summary']['cost_per_day']:.0f} wait {rec['best_summary']['wait_mean_min']:.1f} "
            f"p95 {rec['best_summary']['wait_p95_min']:.0f} lwbs {rec['best_summary']['lwbs_rate']:.3f} ({rec['seconds']:.0f}s)")
        write_json(run / "state.json", dict(mean=mean.tolist(), std=std.tolist(), hist=hist, elite=el.tolist()))
    # final round on fresh tuning seeds: distribution mean, last elites, the hand-written default
    fin = torch.cat([mean.unsqueeze(0), el[:5], theta_from_dict(RULE_DEFAULT).unsqueeze(0)], 0)
    sc, summ = evaluate_population(fin, a.objective, a.scenarios, a.final_seeds, SEED_TUNE + 100_000, a.days, a.device, scales, a.stage)
    b = int(torch.argmax(sc))
    say(f"final round scores {['%.4f' % float(x) for x in sc]} -> pick {b} (last entry = hand-written default)")
    pol = RulePolicy(fin[b], id=f"tuned_{slug}", kind="tuned_heuristic", label=f"Tuned heuristic: {a.objective}",
                     objective=a.objective, reward_weights=weights_dict(a.objective), stage=a.stage)
    save_heuristic(out, pol, dict(
        tuning=dict(method="cross-entropy method over 21 rule parameters, batched with common random numbers",
                    pop=a.pop, seeds_per_scenario=a.seeds, days=a.days, gens=a.gens, scenarios=a.scenarios, stage=a.stage,
                    seed_range=[SEED_TUNE, SEED_TUNE + 100_000 + a.final_seeds], final_score=float(sc[b]),
                    default_rule_score=float(sc[-1]), final_summary={k: float(v[b]) for k, v in summ.items()},
                    p95_wait_threshold_min=scales["p95_wait_threshold_min"], history=hist, finished=now_iso())))
    say(f"saved {out}")


if __name__ == "__main__":
    main()
