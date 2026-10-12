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
# Artefacts of the DEFAULT hospital stay where the server and the web app read them; every other hospital
# lives under rl/hospitals/<id>/ (see `paths`). Headline reports live under rl/hospitals/<id>/ for all.
DEFAULT_HOSPITAL = "rwjuh_nb"
POLICY_DIR = RL_DIR / "policies"
RESULTS_DIR = RL_DIR / "results"
ROLLOUT_DIR = RL_DIR / "rollouts"
SCALES_PATH = RL_DIR / "reward_scales.json"
HOSPITALS_DIR = RL_DIR / "hospitals"
CATALOG_HOSPITALS = ROOT / "catalog" / "hospitals"


def hospital_id(hospital: str | None = None) -> str:
    """Explicit id > HOSPITAL_ID environment variable > the default hospital (same order as sim.load_scenario)."""
    return str(hospital or os.environ.get("HOSPITAL_ID") or DEFAULT_HOSPITAL)


class HospitalPaths:
    def __init__(self, hospital: str | None = None):
        self.hospital = h = hospital_id(hospital)
        self.home = HOSPITALS_DIR / h                      # headline.json, HEADLINE.md, selection.json
        legacy = h == DEFAULT_HOSPITAL
        self.policies = POLICY_DIR if legacy else self.home / "policies"
        self.results = RESULTS_DIR if legacy else self.home / "results"
        self.rollouts = ROLLOUT_DIR if legacy else self.home / "rollouts"
        self.scales = SCALES_PATH if legacy else self.home / "reward_scales.json"


def paths(hospital: str | None = None) -> HospitalPaths:
    return HospitalPaths(hospital)


def load_ensemble(hospital: str | None = None) -> dict:
    """catalog/hospitals/<id>.ensemble.json when the calibration has written one, else a single member
    with no overrides (the point calibration). Member 0 is always the point calibration."""
    h = hospital_id(hospital)
    f = CATALOG_HOSPITALS / f"{h}.ensemble.json"
    if f.exists():
        d = json.loads(f.read_text())
        mem = [dict(id=int(m.get("id", i)), overrides=dict(m.get("overrides") or {}), baseline_actions=dict(m.get("baseline_actions") or {}),
                    fit=m.get("fit")) for i, m in enumerate(d.get("members") or [])]
        if mem:
            return dict(hospital_id=h, members=mem, source=(str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f)), exists=True)
    return dict(hospital_id=h, members=[dict(id=0, overrides={}, baseline_actions={}, fit=None)], source=None, exists=False)


def member_overrides(hospital: str | None = None, member: int | dict | None = 0, extra: dict | None = None) -> dict:
    """The `overrides` dict for sim.load_scenario that builds one ensemble member of one hospital."""
    h = hospital_id(hospital)
    ov = {"hospital_id": h}
    if member is not None:
        m = member if isinstance(member, dict) else load_ensemble(h)["members"][int(member)]
        ov.update(m.get("overrides") or {})
        if m.get("baseline_actions"):
            ov["baseline_actions"] = dict(m["baseline_actions"])
    ov.update(extra or {})
    return ov


def calibration_fingerprint(hospital: str | None = None) -> str:
    """Hash of the hospital's calibration inputs (hospital file, calibration file, ensemble file). Artefacts
    carry it; a different value means they were built against another calibration and are stale."""
    h = hospital_id(hospital)
    hh = hashlib.sha256()
    for suffix in (".yaml", ".calibration.yaml", ".ensemble.json"):
        f = CATALOG_HOSPITALS / f"{h}{suffix}"
        hh.update(suffix.encode())
        hh.update(f.read_bytes() if f.exists() else b"<absent>")
    return hh.hexdigest()[:16]


def calibration_status(hospital: str | None = None) -> dict:
    h = hospital_id(hospital)
    ens = load_ensemble(h)
    cf = CATALOG_HOSPITALS / f"{h}.calibration.yaml"
    return dict(hospital_id=h, hospital_file=(CATALOG_HOSPITALS / f"{h}.yaml").exists(), calibration_file=cf.exists(),
                ensemble_file=bool(ens["exists"]), n_members=len(ens["members"]), calibration_fingerprint=calibration_fingerprint(h),
                calibration_mtime=(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(cf.stat().st_mtime)) if cf.exists() else None))

SEED_SCALES = 100_000
SEED_TUNE = 200_000
SEED_TRAIN = 400_000
SEED_VAL = 900_000
SEED_EVAL = 9_000_000
RECORD_SEED = 9_000_001

# the 7 reward_terms of contracts/metrics.yaml in order, plus one rl-side extension, `labor`
# (cost_labor: wages + overtime + agency, the part of cost a manager controls directly);
# see rl/CONTRACT_REQUESTS.md. The reward-weight vector appended to the observation has these 8 entries.
# `los` (ed_census: patient-hours in the ED this hour, the dense proxy of ED length of stay) and `opcost`
# (cost_labor + cost_fixed: staffing plus staffed-space cost, so opening hallway spaces is not free) were added
# for the operator objectives. Networks trained with 8 weight entries still load (LearnedPolicy pads/truncates).
TERMS = ["cost", "wait", "lwbs", "safety", "boarding", "staff", "revenue", "labor", "los", "opcost"]
FATIGUE_THRESHOLD = 0.5          # assumed: "fatigue above threshold" part of the staff term
SCALE_FLOORS = {"cost": 1.0, "wait": 60.0, "lwbs": 0.05, "safety": 0.02, "boarding": 0.1, "staff": 1.0, "revenue": 1.0, "labor": 1.0, "los": 1.0, "opcost": 1.0}

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
    if isinstance(objective_or_dict, str):
        from .objectives import OPERATOR_OBJECTIVES
        w = OBJECTIVES[objective_or_dict] if objective_or_dict in OBJECTIVES else OPERATOR_OBJECTIVES[objective_or_dict]["reward_weights"]
    else:
        w = dict(objective_or_dict)
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
def _behaviour_fingerprint(hospital: str) -> str:
    """Hash of what the simulator DOES: hourly patient counts (and labour cost rounded to $10) on a
    fixed seed under a fixed action script over the hourly and daily heads, for normal_week (48 h)
    and flu_surge (72 h), 2 hospitals on CPU. Unlike `sim_fingerprint` (a hash of files) it only
    changes when the dynamics change, so staleness of policies, results and rollouts is keyed on it.
    Run on the hospital's point calibration (no ensemble member), so it is per hospital.
    Cached per (file hash, hospital) in the system temp dir."""
    import tempfile
    cache = Path(tempfile.gettempdir()) / "hospitalgym_behaviour_fp.json"
    fh = sim_fingerprint() + ("" if hospital == DEFAULT_HOSPITAL else ":" + hospital)
    try:
        c = json.loads(cache.read_text())
        if fh in c:
            return c[fh]
    except Exception:
        c = {}
    from sim import HospitalSim, load_scenario
    h = hashlib.sha256()
    nt = torch.get_num_threads()
    torch.set_num_threads(1)
    for scen, hours in (("normal_week", 48), ("flu_surge", 72)):
        sim = HospitalSim(load_scenario(scen, {"hospital_id": hospital}), batch_size=2, device="cpu", seed=424242)
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
        tmp = cache.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(c))
        os.replace(tmp, cache)
    except Exception:
        pass
    return out


def behaviour_fingerprint(hospital: str | None = None) -> str:
    return _behaviour_fingerprint(hospital_id(hospital))


def fingerprints(hospital: str | None = None) -> dict:
    """Everything an artefact is stamped with. Staleness = `sim_behaviour_fingerprint` or
    `calibration_fingerprint` differs from the current one for that hospital (see `is_stale`)."""
    h = hospital_id(hospital)
    return dict(hospital_id=h, sim_fingerprint=sim_fingerprint(), sim_behaviour_fingerprint=behaviour_fingerprint(h),
                calibration_fingerprint=calibration_fingerprint(h))


def is_stale(artefact: dict, hospital: str | None = None) -> bool:
    """True when the artefact was built against other simulator dynamics or another calibration of this
    hospital. Artefacts that predate a field are not flagged on that field."""
    if not isinstance(artefact, dict):
        return False
    h = hospital_id(hospital or artefact.get("hospital_id"))
    b, c = artefact.get("sim_behaviour_fingerprint") or artefact.get("behaviour_fingerprint"), artefact.get("calibration_fingerprint")
    return bool((b and b != behaviour_fingerprint(h)) or (c and c != calibration_fingerprint(h)))


@functools.lru_cache(maxsize=None)
def _get_spec(scenario: str, hospital: str, cfp: str) -> dict:
    from sim import HospitalSim, load_scenario
    scn = load_scenario(scenario, {"hospital_id": hospital})
    sim = HospitalSim(scn, batch_size=1, device="cpu", seed=0)
    spec = sim.action_spec()
    hosp = scn.cat.get("hospital") or {}
    val = lambda k: (hosp.get(k) or {}).get("value") if isinstance(hosp.get(k), dict) else None      # noqa: E731
    return dict(action_spec=spec, obs_names=sim.obs_names(), obs_dim=int(sim.obs_dim),
                head_names=[h["name"] for h in spec], hospital_id=getattr(sim.scn, "hospital_id", None),
                hospital_label=getattr(scn, "hospital_label", hospital), metric_names=sim.metric_names(),
                dow_prof=[float(x) for x in scn.P["dow_prof"]], hour_prof=[float(x) for x in scn.P["hour_prof"]],
                shift_starts=[int(x) for x in getattr(sim, "shift_starts", (7, 15, 23))],
                arrivals_per_day=float(scn.P["arrivals_per_day"]),
                ed_visits_per_year_cms=val("ed_visits_per_year_cms"), ed_visits_per_year=val("ed_visits_per_year"),
                ed_visits_note=((hosp.get("ed_visits_per_year_cms") or {}).get("note") if isinstance(hosp.get("ed_visits_per_year_cms"), dict) else None))


def get_spec(scenario: str = "normal_week", hospital: str | None = None) -> dict:
    """Action spec (defaults = the hospital's calibrated baseline), observation names and the public arrival
    profiles, from a tiny CPU simulator instance of the hospital's point calibration."""
    h = hospital_id(hospital)
    return _get_spec(scenario, h, calibration_fingerprint(h))


def load_scales(path: Path | None = None, hospital: str | None = None) -> dict:
    path = Path(path or paths(hospital).scales)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m rl.scripts.measure_scales --hospital {hospital_id(hospital)}`")
    return json.loads(path.read_text())


def scales_vec(scales: dict, device="cpu") -> torch.Tensor:
    """Scales in TERMS order. Files measured before `los`/`opcost` existed fall back to labour-derived / floor values."""
    s = dict(scales["scales"])
    s.setdefault("los", SCALE_FLOORS["los"])
    s.setdefault("opcost", float(s.get("labor", SCALE_FLOORS["opcost"])))
    return torch.tensor([float(s[k]) for k in TERMS], dtype=torch.float32, device=device)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_text(path, text: str):
    """Atomic write (temp file in the same directory, then rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_json(path, obj, **kw):
    write_text(path, json.dumps(obj, **kw))


def objective_score(objective: str, terms_mean: torch.Tensor, p95: torch.Tensor, threshold: float) -> torch.Tensor:
    """Per-episode score (higher is better) for an objective.

    terms_mean: [..., len(TERMS)] episode means of the baseline-normalised reward terms.
    Weighted objectives: mean hourly reward. Constrained: -labor_term - PENALTY * relu(p95/threshold - 1).
    """
    w = weights_vec(objective, terms_mean.device)
    s = -(terms_mean * w).sum(-1)
    if objective == CONSTRAINED:
        s = s - CONSTRAINT_PENALTY * torch.relu(p95 / float(threshold) - 1.0)
    return s
