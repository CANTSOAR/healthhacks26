"""Run policies on one (hospital, ensemble member, scenario) group and fan groups out over processes.

One simulator holds one scenario configuration, and a simulator tick costs about the same wall time for
64 or 1,024 hospitals, so the unit of work is a GROUP: every policy x every seed of one ensemble member
and one scenario in a single batch (common random numbers: all policies face the same seeds). Groups are
independent and run in worker processes (some on the GPU, the rest on CPU cores).

Used by rl.tune (population + baseline rows), rl.headline (validation selection and held-out evaluation)
and the tests. All numbers simulated.
"""
from __future__ import annotations

import concurrent.futures as cf
import multiprocessing as mp
import time

import torch

from .common import TERMS, load_scales
from .env import HospitalEnv
from .managers import MultiPolicy, RulePolicy, load_manager
from .objectives import EPISODE_METRICS

DAILY_STAFF = ("md_day", "md_evening", "md_night", "rn_day", "rn_evening", "rn_night")


def group_task(hospital, scenario, member, policies, seeds, days, device="cpu", stage="stage_3", locked=(), scales=None,
               want_actions=False, threads=2, tag=None) -> dict:
    """policies: list of {"id": manager_id} | {"theta": [[...]] (N x P list), "stage": ..., "locked": [...]}.
    A theta entry is a whole population of rule managers (N policies)."""
    return dict(hospital=hospital, scenario=scenario, member=member, policies=policies, seeds=[int(s) for s in seeds], days=int(days),
                device=device, stage=stage, locked=list(locked), scales=scales, want_actions=bool(want_actions), threads=int(threads), tag=tag)


@torch.no_grad()
def run_group(task: dict) -> dict:
    """-> {"episode": [n_policies, n_seeds, K] (EPISODE_METRICS order), "terms": [n_policies, n_seeds, len(TERMS)],
    "p95": ..., "invalid": ..., "actions": {head: [n_policies, 24, n_options]} when asked, plus the task's keys}."""
    t0 = time.time()
    dev = task["device"]
    if str(dev) == "cpu":
        torch.set_num_threads(max(1, int(task.get("threads", 2))))
    h, seeds, n = task["hospital"], task["seeds"], len(task["seeds"])
    pols, names = [], []
    for spec in task["policies"]:
        if "theta" in spec:
            th = torch.as_tensor(spec["theta"], dtype=torch.float32)
            for i in range(th.shape[0]):
                names.append(f"theta{i}")
            pols.append((RulePolicy(th.repeat_interleave(n, 0), stage=spec.get("stage", "stage_1"), hospital=h, locked=spec.get("locked") or ()),
                         th.shape[0] * n))
        else:
            pols.append((load_manager(spec["id"], dev, hospital=h), n))
            names.append(spec["id"])
    M = len(names)
    scales = task.get("scales") or load_scales(hospital=h)
    env = HospitalEnv(task["scenario"], M * n, dev, torch.tensor(seeds).repeat(M), task["days"] * 24, stage=task.get("stage", "stage_3"),
                      weights={}, scales=scales, auto_reset=False, hospital=h, member=task.get("member"), locked_heads=task.get("locked") or ())
    mp_ = MultiPolicy([p for p, _ in pols], [k for _, k in pols])
    mp_.reset(env.B, env.device, env.default_actions())
    obs = env.reset()
    want = task.get("want_actions")
    counts = {nm: torch.zeros((M, 24, sz), device=env.device) for nm, sz in zip(env.head_names, env.head_sizes)} if want else None
    by_dow = {nm: torch.zeros((M, 7, env.head_sizes[env.head_names.index(nm)]), device=env.device) for nm in DAILY_STAFF} if want else None
    for hr in range(task["days"] * 24):
        obs, r, d, info = env.step(mp_.act(obs, env.action_mask()))
        if want:
            hod = hr % 24
            for nm, sz in zip(env.head_names, env.head_sizes):
                # impulse heads (call-in, structural): what was sent this hour; the others: the setting in force
                v = env.last_sent.get(nm) if nm == "call_in" else env.sim.settings[nm]
                if v is None:
                    continue
                counts[nm][:, hod] += torch.nn.functional.one_hot(v.long(), sz).float().reshape(M, n, sz).sum(1)
            if hod == 0:
                for nm in DAILY_STAFF:
                    sz = by_dow[nm].shape[-1]
                    by_dow[nm][:, (hr // 24) % 7] += torch.nn.functional.one_hot(env.sim.settings[nm].long(), sz).float().reshape(M, n, sz).sum(1)
    out = dict(task, policies=None, names=names, scales=None, seconds=time.time() - t0, device=str(dev),
               defaults={nm: int(v) for nm, v in zip(env.head_names, env.defaults)},
               episode=info["episode"].reshape(M, n, len(EPISODE_METRICS)).cpu(),
               terms=info["terms_mean"].reshape(M, n, len(TERMS)).cpu(),
               invalid=info["invalid_actions"].float().reshape(M, n).cpu())
    if want:
        out["actions"] = {k: (v / float(n * task["days"])).cpu() for k, v in counts.items()}      # share of (seed, day) per hour of day
        out["actions_by_dow"] = {k: (v / v.sum(-1, keepdim=True).clamp(min=1.0)).cpu() for k, v in by_dow.items()}
        out["option_values"] = {hd["name"]: hd.get("values") for hd in env.spec}
        out["option_labels"] = {hd["name"]: list(hd["options"]) for hd in env.spec}
    return out


def _worker(task):
    return run_group(task)


def run_groups(tasks: list[dict], gpu_workers: int = 0, cpu_workers: int = 0, log=None) -> list[dict]:
    """Run group tasks, in order of submission. With no workers everything runs inline on each task's device.
    Otherwise `gpu_workers` processes take tasks on cuda and `cpu_workers` on cpu, whichever is free first
    (the largest tasks are offered to the GPU first)."""
    if gpu_workers + cpu_workers <= 0 or len(tasks) == 1 and gpu_workers + cpu_workers <= 1:
        dev = "cuda" if gpu_workers > 0 else None
        return [run_group(dict(t, device=dev or t["device"])) for t in tasks]
    ctx = mp.get_context("spawn")
    pools = []
    if gpu_workers > 0:
        pools.append(("cuda", gpu_workers, cf.ProcessPoolExecutor(gpu_workers, mp_context=ctx)))
    if cpu_workers > 0:
        pools.append(("cpu", cpu_workers, cf.ProcessPoolExecutor(cpu_workers, mp_context=ctx)))
    size = lambda t: sum(len(p["theta"]) if "theta" in p else 1 for p in t["policies"]) * len(t["seeds"]) * t["days"]   # noqa: E731
    todo = sorted(range(len(tasks)), key=lambda i: -size(tasks[i]))
    free = {d: n for d, n, _ in pools}
    running, results = {}, [None] * len(tasks)
    try:
        while todo or running:
            for d, _, pool in pools:
                while todo and free[d] > 0:
                    i = todo.pop(0) if d == "cuda" else todo.pop(-1)       # big ones to the GPU, small ones to CPU
                    running[pool.submit(_worker, dict(tasks[i], device=d))] = (i, d)
                    free[d] -= 1
            done, _ = cf.wait(list(running), return_when=cf.FIRST_COMPLETED)
            for f in done:
                i, d = running.pop(f)
                results[i] = f.result()
                free[d] += 1
                if log:
                    r = results[i]
                    log(f"  group {r.get('tag') or i}: {r['scenario']} member {r['member']} on {r['device']} in {r['seconds']:.0f}s")
    finally:
        for _, _, pool in pools:
            pool.shutdown(wait=False, cancel_futures=True)
    return results
