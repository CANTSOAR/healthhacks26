"""Long-horizon run with structural actions at every monthly boundary; checks conservation daily.

    .venv/bin/python -m sim.scripts.long_run --days 1000 --batch 64 --device cpu --out sim/LONG_RUN.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim import HospitalSim, load_scenario  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--scenario", default="normal_week")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--start-day", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    sim = HospitalSim(load_scenario(a.scenario), batch_size=a.batch, device=a.device, seed=a.seed)
    if a.start_day:
        sim.reset(a.seed, start_day=a.start_day)
    g = torch.Generator().manual_seed(1)
    monthly = [h for h in sim.action_spec() if h["cadence"] == "monthly"]
    v0 = sim.layout_version.clone()
    t0 = time.time()
    worst, struct_cost, log = 0, 0.0, []
    for d in range(a.days):
        for h in range(24):
            acts = sim.default_actions()
            if h == 0 and d % sim.dpm == 0:      # a random structural decision per hospital on every head
                for hd in monthly:
                    acts[hd["name"]] = torch.randint(0, len(hd["options"]), (a.batch,), generator=g).to(a.device)
            m = sim.step(acts)
            struct_cost += float(m["cost_structural"].sum())
        worst = max(worst, int(sim.conservation()["residual"].abs().max()))
        assert worst == 0, f"conservation broken on day {d}"
        if d % 50 == 49 or d == a.days - 1:
            el = time.time() - t0
            n_main = (sim.bay_exists & sim.bay_is[1]).sum(1).float()
            row = dict(day=d + 1, wall_s=round(el, 1), hospital_days_per_s=round(a.batch * (d + 1) / el, 2),
                       main_bays=[float(n_main.min()), float(n_main.mean()), float(n_main.max())],
                       ward_beds=[int(sim.ward_cap.min()), float(sim.ward_cap.float().mean()), int(sim.ward_cap.max())],
                       ct_units=float(sim.eq_units[:, 1].float().mean()), xray_units=float(sim.eq_units[:, 0].float().mean()),
                       layout_version_mean=float(sim.layout_version.float().mean()),
                       lwbs_rate_24h=float(m["lwbs_rate"].mean()), ward_occupancy=float(m["ward_occupancy"].mean()),
                       wait_p95_24h=float(m["wait_p95_min"].mean()), generated=int(sim.next_ord.sum()),
                       in_system=int(sim.conservation()["in_system"].sum()), pool_overflow=int(sim.pool_overflow.sum()),
                       invalid_actions=int(sim.invalid_actions.sum()), conservation_residual_max=worst)
            log.append(row)
            print(json.dumps(row), flush=True)
            if a.out:
                Path(a.out).write_text(json.dumps(dict(args=vars(a), torch=torch.__version__, progress=log,
                                                       structural_cost_total=struct_cost, finished=d == a.days - 1,
                                                       summary={k: float(v.mean()) for k, v in sim.episode_summary().items()}), indent=1))
    print("hospitals whose layout version changed:", int((sim.layout_version > v0).sum()), "of", a.batch)
    print("DONE", a.days, "days x", a.batch, "hospitals in", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
