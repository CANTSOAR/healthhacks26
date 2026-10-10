"""Throughput benchmark: hospital-days per second for several batch sizes.

    .venv/bin/python -m sim.bench --device cpu --batch 1 16 64 --days 2
    .venv/bin/python -m sim.bench --device cuda --batch 256 1024 4096 --days 2
"""
from __future__ import annotations

import argparse
import time

import torch

from . import HospitalSim, load_scenario


def bench(device: str, B: int, days: float, scenario: str = "normal_week", random_actions: bool = False, warm_days: float = 1.0):
    sim = HospitalSim(load_scenario(scenario), batch_size=B, device=device, seed=0)
    spec = sim.action_spec()
    g = torch.Generator().manual_seed(0)

    def acts():
        if not random_actions:
            return sim.default_actions()
        return {h["name"]: torch.randint(0, len(h["options"]), (B,), generator=g).to(device) for h in spec
                if h["cadence"] in ("hourly", "daily")}

    for _ in range(int(warm_days * 24)):
        sim.step(acts())
    if device.startswith("cuda"):
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    steps = int(days * 24)
    for _ in range(steps):
        sim.step(acts())
        sim.observe()
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    mem = torch.cuda.max_memory_allocated() / 2 ** 20 if device.startswith("cuda") else float("nan")
    return dict(device=device, B=B, days=steps / 24, seconds=dt, hospital_days_per_s=B * steps / 24 / dt,
                ms_per_tick=1000 * dt / (steps * 12), peak_mem_mb=mem, pool=sim.P)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--batch", type=int, nargs="+", default=[1, 16, 64])
    ap.add_argument("--days", type=float, default=2.0)
    ap.add_argument("--scenario", default="normal_week")
    ap.add_argument("--random-actions", action="store_true")
    ap.add_argument("--threads", type=int, default=0)
    a = ap.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    print(f"torch {torch.__version__}  device {a.device}  threads {torch.get_num_threads()}  scenario {a.scenario}"
          f"  actions {'random hourly+daily' if a.random_actions else 'default'}  (step + observe per hour)")
    print(f"{'B':>6} {'pool':>5} {'sim days':>8} {'seconds':>8} {'ms/tick':>8} {'hospital-days/s':>16} {'peak MB':>8}")
    for B in a.batch:
        r = bench(a.device, B, a.days, a.scenario, a.random_actions)
        print(f"{r['B']:>6} {r['pool']:>5} {r['days']:>8.1f} {r['seconds']:>8.2f} {r['ms_per_tick']:>8.2f} {r['hospital_days_per_s']:>16.1f} {r['peak_mem_mb']:>8.0f}")


if __name__ == "__main__":
    main()
