"""Measure the reward-term scales from the fixed-default policy and write rl/reward_scales.json.

    python -m rl.scripts.measure_scales --device cuda --seeds 64 --days 30

Scale k = mean per-hour value of term k under the fixed policy on normal_week (floored for
terms that are ~0 at baseline). Also records the baseline p95 wait and derives the threshold of
the constrained objective from it. All numbers simulated.
"""
import argparse

import torch

from rl.common import SCALE_FLOORS, SCALES_PATH, SEED_SCALES, TERMS, now_iso, sim_fingerprint, write_json
from rl.env import HospitalEnv
from rl.managers import FixedPolicy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seeds", type=int, default=64)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default=str(SCALES_PATH))
    a = ap.parse_args()
    unit = {"scales": {k: 1.0 for k in TERMS}}
    env = HospitalEnv("normal_week", a.seeds, a.device, SEED_SCALES, a.days * 24, weights={"cost": 1.0}, scales=unit, auto_reset=False)
    pol = FixedPolicy()
    pol.reset(env.B, env.device)
    obs = env.reset()
    for _ in range(a.days * 24):
        obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
    raw = info["terms_mean"].mean(0)
    raw[TERMS.index("revenue")] = raw[TERMS.index("cost")]          # revenue shares the cost scale (margin)
    scales = {k: max(abs(float(raw[i])), SCALE_FLOORS[k]) for i, k in enumerate(TERMS)}
    summ = {k: float(v.mean()) for k, v in info["summary"].items()}
    p95 = summ["wait_p95_min"]
    thr = max(15.0, round(0.75 * p95 / 15.0) * 15.0)
    out = dict(generated=now_iso(), synthetic=True, sim_fingerprint=sim_fingerprint(), policy="fixed", scenario="normal_week",
               seeds=[SEED_SCALES, SEED_SCALES + a.seeds - 1], days=a.days, terms=TERMS,
               raw_per_hour={k: float(info["terms_mean"].mean(0)[i]) for i, k in enumerate(TERMS)},
               floors=SCALE_FLOORS, scales=scales, baseline_summary=summ, p95_wait_threshold_min=thr,
               note="scale = fixed-policy mean per hour (floored); wait = waiting_count*60 patient-minutes; revenue uses the cost scale; "
                    "p95 threshold = 0.75 x baseline episode p95 wait rounded to 15 min")
    write_json(a.out, out, indent=1)
    print(out)


if __name__ == "__main__":
    main()
