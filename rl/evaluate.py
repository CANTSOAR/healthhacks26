"""Held-out evaluation of every available manager. All numbers are simulated.

    python -m rl.evaluate --device cuda --seeds 32 --days 30 --scenarios normal_week flu_surge

Protocol: seeds SEED_EVAL .. SEED_EVAL+n-1 (9,000,000+; tuning and training only ever use seeds
below 1,000,000). Every manager runs on the same seeds, so with the simulator's common random
numbers they face the same patients and comparisons are paired. One simulator batch per
scenario holds managers x seeds hospitals. Writes rl/results/results.json (the /api/results
shape of contracts/api.md), eval_raw.json (per-seed values) and RESULTS.md.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import torch

from .common import (CONSTRAINED, OBJ_SLUG, OBJECTIVES, RESULTS_DIR, SEED_EVAL, TERMS, load_scales, now_iso,
                     objective_score, behaviour_fingerprint, sim_fingerprint, write_json)
from .env import HospitalEnv
from .managers import MultiPolicy, list_managers, load_manager


@torch.no_grad()
def run_scenario(scenario: str, manager_ids: list[str], n_seeds: int, days: int, device: str, seed0: int = SEED_EVAL) -> dict:
    scales = load_scales()
    pols = [load_manager(m, device) for m in manager_ids]
    M = len(pols)
    seeds = (seed0 + torch.arange(n_seeds)).repeat(M)
    w = torch.zeros((M * n_seeds, len(TERMS)))
    for i, p in enumerate(pols):
        if p.reward_weights:
            w[i * n_seeds:(i + 1) * n_seeds] = torch.tensor([float(p.reward_weights.get(k, 0.0)) for k in TERMS])
    stage = "stage_3"                               # the env lets every head through; each policy limits itself
    env = HospitalEnv(scenario, M * n_seeds, device, seeds, days * 24, stage=stage, weights=w, scales=scales, auto_reset=False)
    mp = MultiPolicy(pols, [n_seeds] * M)
    mp.reset(env.B, env.device)
    obs = env.reset()
    exo = []
    labor = torch.zeros(env.B, device=env.device)
    t0 = time.time()
    for h in range(days * 24):
        obs, r, d, info = env.step(mp.act(obs, env.action_mask()))
        m = info["metrics"]
        exo.append((m["arrivals"] + m["diverted"])[:n_seeds].cpu())
        labor += m["cost_labor"]
    per = lambda x: x.reshape(M, n_seeds).cpu()      # noqa: E731
    vals = {k: per(v) for k, v in info["summary"].items()}
    if hasattr(env.sim, "episode_means"):
        for k, v in env.sim.episode_means().items():
            vals[k + "_mean"] = per(v)
    vals["labor_cost_per_day"] = per(labor / days)       # the controllable part of cost (wages, overtime, agency)
    tm = info["terms_mean"]
    for i, k in enumerate(TERMS):
        vals["term_" + k] = per(tm[:, i])
    thr = scales["p95_wait_threshold_min"]
    for obj, slug in OBJ_SLUG.items():
        vals["score_" + slug] = per(objective_score(obj, tm, info["summary"]["wait_p95_min"], thr))
    vals["p95_within_threshold"] = (vals["wait_p95_min"] <= thr).float()
    vals["invalid_actions"] = per(info["invalid_actions"].float())
    exo = torch.stack(exo, 1)                        # [n_seeds, hours] exogenous arrivals (incl. diverted)
    return dict(scenario=scenario, managers=[p.info() | {"file_fingerprint": getattr(p, "file_fingerprint", None),
                                        "behaviour_fingerprint": getattr(p, "behaviour_fingerprint", None)} for p in pols],
                seeds=[seed0 + i for i in range(n_seeds)], days=days, seconds=time.time() - t0, device=str(device),
                values={k: v.tolist() for k, v in vals.items()},
                daily_exogenous_arrivals=exo.reshape(n_seeds, days, 24).sum(2).tolist(),
                sim_fingerprint=sim_fingerprint(), sim_behaviour_fingerprint=behaviour_fingerprint(),
                scales_behaviour_fingerprint=scales.get("sim_behaviour_fingerprint"))


def stat(x: list[float]) -> dict:
    n = len(x)
    mean = sum(x) / n
    var = sum((v - mean) ** 2 for v in x) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(var)
    return dict(mean=mean, std=std, ci95=1.96 * std / math.sqrt(n))


def verdict(diff: dict) -> str:
    if diff["mean"] - diff["ci95"] > 0:
        return "beats"
    if diff["mean"] + diff["ci95"] < 0:
        return "loses to"
    return "matches (difference not significant)"


def merge(parts: list[dict]) -> dict:
    scales = load_scales()
    rows, comps = [], []
    for part in parts:
        ids = [m["id"] for m in part["managers"]]
        for i, m in enumerate(part["managers"]):
            rows.append(dict(manager_id=m["id"], kind=m["kind"], label=m["label"], objective=m["objective"],
                             scenario=part["scenario"], n_seeds=len(part["seeds"]),
                             stale=bool(m.get("behaviour_fingerprint") and m["behaviour_fingerprint"] != part["sim_behaviour_fingerprint"]),
                             metrics={k: stat(v[i]) for k, v in part["values"].items()}))
        for obj, slug in OBJ_SLUG.items():
            key = "score_" + slug
            sc = part["values"][key]
            pairs = [(f"ppo_{slug}", f"tuned_{slug}"), (f"ppo_{slug}", "rule_based"), (f"ppo_{slug}", "fixed"),
                     (f"tuned_{slug}", "rule_based"), (f"tuned_{slug}", "fixed")]
            pairs += [(f"ppo_cond_{slug}", f"tuned_{slug}"), (f"ppo_cond_{slug}", "rule_based"), (f"ppo_cond_{slug}", f"ppo_{slug}")]
            for a, b in pairs:
                if a in ids and b in ids:
                    d = stat([x - y for x, y in zip(sc[ids.index(a)], sc[ids.index(b)])])
                    comps.append(dict(objective=obj, scenario=part["scenario"], a=a, b=b, score=key,
                                      a_mean=stat(sc[ids.index(a)])["mean"], b_mean=stat(sc[ids.index(b)])["mean"],
                                      paired_diff=d, verdict=verdict(d)))
    p0 = parts[0]
    return dict(generated=now_iso(), synthetic=True, sim_fingerprint=sim_fingerprint(),
                sim_behaviour_fingerprint=p0["sim_behaviour_fingerprint"],
                stale_scales=bool(p0.get("scales_behaviour_fingerprint") and p0["scales_behaviour_fingerprint"] != p0["sim_behaviour_fingerprint"]),
                protocol=dict(seeds=p0["seeds"], days=p0["days"], scenarios=[p["scenario"] for p in parts],
                              seed_note="held-out: evaluation seeds are 9,000,000+; tuning and training seeds are below 1,000,000",
                              paired="all managers run on the same seeds (common random numbers)",
                              ci95="half-width, 1.96*std/sqrt(n_seeds)",
                              scores="score_<objective> = mean hourly reward under that objective's weights on baseline-normalised "
                                     "terms (higher is better); constrained objective: -cost_term - 5*relu(p95_wait/threshold - 1)",
                              p95_wait_threshold_min=scales["p95_wait_threshold_min"], reward_scales=scales["scales"],
                              objectives={k: v for k, v in OBJECTIVES.items()},
                              learned_agents_act="greedy (argmax per head)"),
                rows=rows, comparisons=comps, human_runs=[])


def fmt(s: dict, nd=1) -> str:
    return f"{s['mean']:.{nd}f} ± {s['ci95']:.{nd}f}"


def write_markdown(res: dict, path: Path):
    L = ["# Held-out evaluation of hospital managers (all numbers SIMULATED)", "",
         f"Generated {res['generated']}; simulator behaviour fingerprint `{res['sim_behaviour_fingerprint']}` (hash of a fixed-seed "
         f"trajectory; staleness is keyed on it), file hash `{res['sim_fingerprint']}` (information only).", "",
         "Managers tuned or trained against a different simulator behaviour: "
         + (", ".join(sorted({'`' + r['manager_id'] + '`' for r in res['rows'] if r.get('stale')})) or "none") + ".", "",
         f"Protocol: {len(res['protocol']['seeds'])} held-out seeds ({res['protocol']['seeds'][0]}..{res['protocol']['seeds'][-1]}) x "
         f"{res['protocol']['days']} days per manager per scenario; every manager faces the same seeds (paired). "
         "Tuning and training never used seeds at or above 1,000,000. Values are mean ± 95% CI half-width over seeds.", "",
         "Kinds: `fixed`, `rule_based` and `random` are baselines; `tuned_heuristic` is the rule-based manager with parameters found by "
         "evolutionary search (NOT a learned agent); `learned` is a PPO network acting greedily.", "",
         f"Constrained objective: cheapest subject to episode p95 wait <= {res['protocol']['p95_wait_threshold_min']:.0f} min "
         "(a chosen service target; see rl/reward_scales.json). `labor cost/day` is the part of cost the manager controls directly "
         "(wages, overtime, agency); fixed and per-patient costs dominate `cost/day`.", ""]
    for scen in res["protocol"]["scenarios"]:
        L += [f"## Scenario `{scen}`", "",
              "| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in res["rows"]:
            if r["scenario"] != scen:
                continue
            m = r["metrics"]
            k = lambda s: dict(mean=s["mean"] / 1000, ci95=s["ci95"] / 1000)       # noqa: E731
            pc = lambda s: dict(mean=s["mean"] * 100, ci95=s["ci95"] * 100)        # noqa: E731
            L.append(f"| `{r['manager_id']}` | {r['kind']} | {fmt(m['wait_mean_min'])} | {fmt(m['wait_p95_min'])} | {fmt(pc(m['lwbs_rate']), 2)} | "
                     f"{fmt(k(m['cost_per_day']))} | {fmt(k(m['labor_cost_per_day']))} | {fmt(k(m['margin_per_day']))} | {fmt(m['deaths_per_10k'])} | {fmt(m['boarding_hours_per_day'])} | "
                     f"{fmt(m['overtime_hours_per_day'])} | {fmt(m['diversion_hours_per_day'], 2)} |")
        L += ["", "Objective scores (higher is better; each column is that objective's own score):", "",
              "| manager | kind | " + " | ".join(OBJ_SLUG) + " | p95 within threshold (share of seeds) |", "|---|---|" + "---|" * (len(OBJ_SLUG) + 1)]
        for r in res["rows"]:
            if r["scenario"] != scen:
                continue
            m = r["metrics"]
            L.append(f"| `{r['manager_id']}` | {r['kind']} | " + " | ".join(fmt(m['score_' + s], 3) for s in OBJ_SLUG.values())
                     + f" | {m['p95_within_threshold']['mean']:.2f} |")
        L.append("")
    L += ["## Verdicts (paired difference of the objective's own score, a minus b, on held-out seeds)", ""]
    if not any(c["a"].startswith("ppo") for c in res["comparisons"]):
        L += ["No learned (PPO) agent was available for this evaluation, so there is no learned-vs-heuristic verdict here.", ""]
    L += ["| objective | scenario | a | b | a score | b score | a - b (± CI95) | verdict |", "|---|---|---|---|---|---|---|---|"]
    for c in res["comparisons"]:
        L.append(f"| {c['objective']} | {c['scenario']} | `{c['a']}` | `{c['b']}` | {c['a_mean']:.4f} | {c['b_mean']:.4f} | "
                 f"{c['paired_diff']['mean']:+.4f} ± {c['paired_diff']['ci95']:.4f} | a {c['verdict']} b |")
    L += ["", "A verdict of 'beats' or 'loses to' means the 95% interval of the paired difference excludes zero; otherwise the two are "
          "reported as matching. The verdict is statistical, not practical: because seeds are paired, differences of a fraction of a "
          "percent of the score can be significant; read the size of the difference. The learned agents are warm-started by behaviour "
          "cloning from the tuned heuristic of the same objective and then fine-tuned with PPO, so a learned agent that 'matches' is "
          "largely reproducing that heuristic. Nothing outside this table should be read as a claim that a learned agent beats a baseline.", ""]
    path.write_text("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seeds", type=int, default=32)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    ap.add_argument("--managers", nargs="+", default=None)
    ap.add_argument("--out", default=str(RESULTS_DIR))
    ap.add_argument("--part", default=None, help="internal: evaluate one scenario and write its part file")
    ap.add_argument("--sequential", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    ids = a.managers or [m["id"] for m in list_managers() if m["available"]]
    if a.part:
        part = run_scenario(a.part, ids, a.seeds, a.days, a.device)
        write_json(out / "parts" / f"{a.part}.json", part)
        print(f"{a.part}: {len(ids)} managers x {a.seeds} seeds x {a.days} d in {part['seconds']:.0f}s")
        return
    if a.sequential:
        parts = []
        for s in a.scenarios:
            parts.append(run_scenario(s, ids, a.seeds, a.days, a.device))
            write_json(out / "parts" / f"{s}.json", parts[-1])
    else:
        procs = [subprocess.Popen([sys.executable, "-m", "rl.evaluate", "--device", a.device, "--seeds", str(a.seeds), "--days", str(a.days),
                                   "--out", str(out), "--part", s, "--managers", *ids]) for s in a.scenarios]
        if any(p.wait() != 0 for p in procs):
            raise SystemExit("an evaluation part failed")
        parts = [json.loads((out / "parts" / f"{s}.json").read_text()) for s in a.scenarios]
    res = merge(parts)
    write_json(out / "results.json", res, indent=1)
    write_json(out / "eval_raw.json", dict(generated=res["generated"], synthetic=True, sim_fingerprint=res["sim_fingerprint"], parts=parts))
    write_markdown(res, out / "RESULTS.md")
    print(f"wrote {out / 'results.json'} ({len(res['rows'])} rows, {len(res['comparisons'])} comparisons)")


if __name__ == "__main__":
    main()
