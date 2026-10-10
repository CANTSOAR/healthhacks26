"""Shared constants and helpers for the RL workstream.

All numbers produced anywhere under rl/ are SIMULATED. Seed ranges (never overlap):

    reward-scale measurement   100_000 .. 199_999
    heuristic tuning (CEM)     200_000 .. 399_999
    PPO training               400_000 .. 899_999
    in-training validation     900_000 .. 999_999
    held-out evaluation        9_000_000 ..          (rl/evaluate.py, rl/record.py)
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
RL_DIR = Path(__file__).resolve().parent
POLICY_DIR = RL_DIR / "policies"
RESULTS_DIR = RL_DIR / "results"
ROLLOUT_DIR = RL_DIR / "rollouts"
SCALES_PATH = RL_DIR / "reward_scales.json"

SEED_SCALES = 100_000
SEED_TUNE = 200_000
SEED_TRAIN = 400_000
SEED_VAL = 900_000
SEED_EVAL = 9_000_000
RECORD_SEED = 9_000_001

# order of contracts/metrics.yaml reward_terms
TERMS = ["cost", "wait", "lwbs", "safety", "boarding", "staff", "revenue"]
FATIGUE_THRESHOLD = 0.5          # assumed: "fatigue above threshold" part of the staff term
SCALE_FLOORS = {"cost": 1.0, "wait": 60.0, "lwbs": 0.05, "safety": 0.02, "boarding": 0.1, "staff": 1.0, "revenue": 1.0}

# Objective presets. Weights multiply baseline-normalised terms (each term is ~1 at the
# fixed-default baseline when its scale is not floored), reward = -sum_k w_k * term_k.
OBJECTIVES = {
    "min_cost": {"cost": 1.0, "safety": 0.02},          # essentially pure cost: it does what it is asked
    "min_wait": {"wait": 1.0, "lwbs": 0.2, "safety": 0.2, "cost": 0.05},
    "balanced": {"cost": 1.0, "revenue": 1.0, "wait": 0.5, "lwbs": 0.25, "safety": 0.25, "boarding": 0.1, "staff": 0.1},
    # constrained: cost only, plus a penalty on the episode p95 wait above the threshold
    "cost_s.t._p95_wait": {"cost": 1.0},
}
CONSTRAINED = "cost_s.t._p95_wait"
CONSTRAINT_PENALTY = 5.0         # score = -cost_term - PENALTY * relu(p95 / threshold - 1)
OBJ_SLUG = {"min_cost": "min_cost", "min_wait": "min_wait", "balanced": "balanced", CONSTRAINED: "cost_p95"}
STAGES = {"stage_1": ("hourly", "daily"), "stage_2": ("hourly", "daily", "weekly"),
          "stage_3": ("hourly", "daily", "weekly", "monthly")}
IMPULSE_HEADS = ("bays_delta", "ward_beds_delta", "equipment_buy", "relocate", "headcount", "call_in")


def weights_dict(objective_or_dict) -> dict:
    w = OBJECTIVES[objective_or_dict] if isinstance(objective_or_dict, str) else dict(objective_or_dict)
    return {k: float(w.get(k, 0.0)) for k in TERMS}


def weights_vec(objective_or_dict, device="cpu") -> torch.Tensor:
    w = weights_dict(objective_or_dict)
    return torch.tensor([w[k] for k in TERMS], dtype=torch.float32, device=device)


def sim_fingerprint() -> str:
    """Hash of the simulator sources, scenario files and catalog values (git-independent)."""
    h = hashlib.sha256()
    files = sorted((ROOT / "sim").glob("*.py")) + sorted((ROOT / "sim" / "scenarios").glob("*.yaml")) \
        + sorted((ROOT / "catalog").rglob("*.yaml"))
    for f in files:
        h.update(str(f.relative_to(ROOT)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


@functools.lru_cache(maxsize=None)
def get_spec(scenario: str = "normal_week") -> dict:
    """Action spec and observation names taken from a tiny CPU simulator instance."""
    from sim import HospitalSim
    sim = HospitalSim(scenario, batch_size=1, device="cpu", seed=0)
    spec = sim.action_spec()
    return dict(action_spec=spec, obs_names=sim.obs_names(), obs_dim=int(sim.obs_dim),
                head_names=[h["name"] for h in spec], hospital_id=getattr(sim.scn, "hospital_id", None),
                metric_names=sim.metric_names())


def load_scales(path: Path | None = None) -> dict:
    path = Path(path or SCALES_PATH)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m rl.scripts.measure_scales`")
    return json.loads(path.read_text())


def scales_vec(scales: dict, device="cpu") -> torch.Tensor:
    return torch.tensor([float(scales["scales"][k]) for k in TERMS], dtype=torch.float32, device=device)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_json(path, obj, **kw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, **kw))
    os.replace(tmp, path)


def objective_score(objective: str, terms_mean: torch.Tensor, p95: torch.Tensor, threshold: float) -> torch.Tensor:
    """Per-episode score (higher is better) for an objective.

    terms_mean: [..., 7] episode means of the baseline-normalised reward terms.
    Weighted objectives: mean hourly reward. Constrained: -cost_term - PENALTY * relu(p95/threshold - 1).
    """
    w = weights_vec(objective, terms_mean.device)
    s = -(terms_mean * w).sum(-1)
    if objective == CONSTRAINED:
        s = s - CONSTRAINT_PENALTY * torch.relu(p95 / float(threshold) - 1.0)
    return s
