"""Measure the reward-term scales from the hospital's baseline policy and write its reward_scales.json
(rl/reward_scales.json for the default hospital, rl/hospitals/<id>/reward_scales.json otherwise).

    python -m rl.scripts.measure_scales --hospital rwjuh_nb --device cuda --seeds 64 --days 30

Scale k = mean per-hour value of term k under the fixed policy on normal_week (floored for
terms that are ~0 at baseline). Also records the baseline p95 wait next to the chosen threshold of
the constrained objective (a service target, default 60 min). All numbers simulated.
"""
import argparse

import torch

from rl.common import SCALE_FLOORS, SEED_SCALES, TERMS, calibration_status, fingerprints, hospital_id, now_iso, paths, write_json
from rl.env import HospitalEnv
from rl.managers import FixedPolicy
from rl.objectives import EPISODE_METRICS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seeds", type=int, default=64)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--hospital", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--p95-threshold", type=float, default=60.0,
                    help="constrained objective: episode p95 door-to-provider wait must stay under this many minutes")
    a = ap.parse_args()
    h = hospital_id(a.hospital)
    a.out = a.out or str(paths(h).scales)
    unit = {"scales": {k: 1.0 for k in TERMS}}
    env = HospitalEnv("normal_week", a.seeds, a.device, SEED_SCALES, a.days * 24, weights={"cost": 1.0}, scales=unit, auto_reset=False,
                      hospital=h)
    pol = FixedPolicy(hospital=h)
    pol.reset(env.B, env.device, env.default_actions())
    obs = env.reset()
    for _ in range(a.days * 24):
        obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
    raw = info["terms_mean"].mean(0)
    raw[TERMS.index("revenue")] = raw[TERMS.index("cost")]          # revenue shares the cost scale (margin)
    scales = {k: max(abs(float(raw[i])), SCALE_FLOORS[k]) for i, k in enumerate(TERMS)}
    summ = {k: float(v.mean()) for k, v in info["summary"].items()}
    p95 = summ["wait_p95_min"]
    thr = float(a.p95_threshold)
    epm = info["episode"].mean(0)
    out = dict(generated=now_iso(), synthetic=True, **fingerprints(h), calibration=calibration_status(h), policy="fixed", scenario="normal_week",
               baseline_actions={n: int(d) for n, d in zip(env.head_names, env.defaults)},
               baseline_episode={k: float(epm[i]) for i, k in enumerate(EPISODE_METRICS)},
               seeds=[SEED_SCALES, SEED_SCALES + a.seeds - 1], days=a.days, terms=TERMS,
               raw_per_hour={k: float(info["terms_mean"].mean(0)[i]) for i, k in enumerate(TERMS)},
               floors=SCALE_FLOORS, scales=scales, baseline_summary=summ, p95_wait_threshold_min=thr,
               note="scale = baseline-policy (`fixed` = the hospital's calibrated current practice) mean per hour on the point calibration (floored); "
                    "wait = patient-minutes waited; revenue uses the cost scale; los = ED census (patient-hours per hour); opcost = labour + fixed cost; "
                    "p95 threshold is a chosen service target (default 60 min door-to-provider at the 95th percentile), "
                    f"fixed baseline p95 here = {p95:.0f} min")
    write_json(a.out, out, indent=1)
    print(out)


if __name__ == "__main__":
    main()
