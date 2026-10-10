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

# the 7 reward_terms of contracts/metrics.yaml in order, plus one rl-side extension, `labor`
# (cost_labor: wages + overtime + agency, the part of cost a manager controls directly);
# see rl/CONTRACT_REQUESTS.md. The reward-weight vector appended to the observation has these 8 entries.
TERMS = ["cost", "wait", "lwbs", "safety", "boarding", "staff", "revenue", "labor"]
FATIGUE_THRESHOLD = 0.5          # assumed: "fatigue above threshold" part of the staff term
SCALE_FLOORS = {"cost": 1.0, "wait": 60.0, "lwbs": 0.05, "safety": 0.02, "boarding": 0.1, "staff": 1.0, "revenue": 1.0, "labor": 1.0}

# Objective presets. Weights multiply baseline-normalised terms (each term is ~1 at the
# fixed-default baseline when its scale is not floored), reward = -sum_k w_k * term_k.
# The presets are deliberately blunt: each manager does exactly what it is asked.
OBJECTIVES = {
    "min_cost": {"labor": 1.0},                          # controllable (labour) cost only; no wait, LWBS or safety term
    "min_wait": {"wait": 1.0, "lwbs": 0.25},             # waiting and walk-outs only; no cost term
    "max_margin": {"cost": 1.0, "revenue": 1.0},         # revenue minus total cost (both on the cost scale)
    "balanced": {"cost": 1.0, "revenue": 1.0, "wait": 0.5, "lwbs": 0.25, "safety": 0.25, "boarding": 0.1, "staff": 0.1},
    # constrained: labour cost only, plus a penalty on the episode p95 wait above the threshold
    "cost_s.t._p95_wait": {"labor": 1.0},
}
CONSTRAINED = "cost_s.t._p95_wait"
CONSTRAINT_PENALTY = 5.0         # score = -labor_term - PENALTY * relu(p95 / threshold - 1)
OBJ_SLUG = {"min_cost": "min_cost", "min_wait": "min_wait", "max_margin": "max_margin", "balanced": "balanced", CONSTRAINED: "cost_p95"}
SCRATCH_OBJECTIVES = ("min_cost", "min_wait")       # also trained from scratch (no behaviour cloning) for an honest comparison
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


_BEHAVIOUR_METRICS = ["arrivals", "diverted", "first_seen", "lwbs", "ed_departures", "admissions", "treated", "deaths"]


@functools.lru_cache(maxsize=None)
def behaviour_fingerprint() -> str:
    """Hash of what the simulator DOES: hourly patient counts (and labour cost rounded to $10) on a
    fixed seed under a fixed action script over the hourly and daily heads, for normal_week (48 h)
    and flu_surge (72 h), 2 hospitals on CPU. Unlike `sim_fingerprint` (a hash of files) it only
    changes when the dynamics change, so staleness of policies, results and rollouts is keyed on it.
    Cached per file hash in the system temp dir."""
    import tempfile
    cache = Path(tempfile.gettempdir()) / "hospitalgym_behaviour_fp.json"
    fh = sim_fingerprint()
    try:
        c = json.loads(cache.read_text())
        if fh in c:
            return c[fh]
    except Exception:
        c = {}
    from sim import HospitalSim
    h = hashlib.sha256()
    nt = torch.get_num_threads()
    torch.set_num_threads(1)
    for scen, hours in (("normal_week", 48), ("flu_surge", 72)):
        sim = HospitalSim(scen, batch_size=2, device="cpu", seed=424242)
        spec = [x for x in sim.action_spec() if x["cadence"] in ("hourly", "daily")]
        for t in range(hours):
            acts = {}
            for i, x in enumerate(spec):
                n = len(x["options"])
                v0 = (t // 6 + i) % n if x["name"] != "divert" else int(t % 24 == 13)
                acts[x["name"]] = torch.tensor([v0, (v0 + 1) % n if x["name"] != "divert" else 0])
            m = sim.step(acts)
            row = [int(round(float(v))) for k in _BEHAVIOUR_METRICS for v in m[k]] + [int(round(float(v) / 10.0)) for v in m["cost_labor"]]
            h.update(json.dumps(row).encode())
    torch.set_num_threads(nt)
    out = h.hexdigest()[:16]
    try:
        c[fh] = out
        cache.write_text(json.dumps(c))
    except Exception:
        pass
    return out


def fingerprints() -> dict:
    """Both fingerprints, for stamping artefacts."""
    return dict(sim_fingerprint=sim_fingerprint(), sim_behaviour_fingerprint=behaviour_fingerprint())


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
    Weighted objectives: mean hourly reward. Constrained: -labor_term - PENALTY * relu(p95/threshold - 1).
    """
    w = weights_vec(objective, terms_mean.device)
    s = -(terms_mean * w).sum(-1)
    if objective == CONSTRAINED:
        s = s - CONSTRAINT_PENALTY * torch.relu(p95 / float(threshold) - 1.0)
    return s
