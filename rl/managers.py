"""Managers behind the Policy interface of contracts/sim_api.md.

kinds: fixed, rule_based, random, tuned_heuristic (a rule-based manager whose parameters were
found by evolutionary search; NOT a learned agent), learned (PPO network).
"""
from __future__ import annotations

import json
from pathlib import Path

import torch

from .common import IMPULSE_HEADS, OBJECTIVES, POLICY_DIR, STAGES, TERMS, get_spec, weights_dict, weights_vec


class Policy:
    id: str = ""
    kind: str = ""
    label: str = ""
    objective: str | None = None
    reward_weights: dict | None = None

    def __init__(self):
        sp = get_spec()
        self.spec = sp["action_spec"]
        self.head_names = sp["head_names"]
        self.head_sizes = [len(h["options"]) for h in self.spec]
        self.defaults = {h["name"]: int(h["default"]) for h in self.spec}
        self.obs_names = sp["obs_names"]
        self.sim_obs_dim = sp["obs_dim"]
        self.oi = {n: i for i, n in enumerate(self.obs_names)}
        self.B, self.device = 1, torch.device("cpu")

    def reset(self, B: int, device) -> None:
        self.B, self.device = int(B), torch.device(device)

    def act(self, obs, mask, sim=None) -> dict:
        raise NotImplementedError

    note: str | None = None

    def info(self) -> dict:
        d = dict(id=self.id, kind=self.kind, label=self.label, objective=self.objective, reward_weights=self.reward_weights)
        if self.note:
            d["note"] = self.note
        return d

    def _full(self, v: int, B, device):
        return torch.full((B,), int(v), device=device, dtype=torch.long)

    def _finalize(self, actions: dict, mask: dict, sim=None) -> dict:
        """With a simulator handle, replace masked heads by the value the simulator accepts
        silently (current setting, or the default for impulse heads) so nothing is counted invalid."""
        if sim is None:
            return actions
        out = {}
        for n, v in actions.items():
            m = mask.get(n)
            if m is None:
                out[n] = v
                continue
            keep = self._full(self.defaults[n], v.shape[0], v.device) if n in IMPULSE_HEADS else sim.settings[n]
            out[n] = torch.where(m, v, keep)
        return out


class FixedPolicy(Policy):
    id, kind, label = "fixed", "fixed", "Fixed staffing (contract defaults)"

    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        return self._finalize({n: self._full(self.defaults[n], B, dev) for n in self.head_names}, mask, sim)


class RandomPolicy(Policy):
    id, kind, label = "random", "random", "Random (uniform over hourly and daily options)"

    def __init__(self, seed: int = 12345, stage: str = "stage_1"):
        super().__init__()
        self.seed, self.cad = seed, STAGES[stage]
        self.gen = torch.Generator().manual_seed(seed)

    def reset(self, B, device):
        super().reset(B, device)
        self.gen = torch.Generator().manual_seed(self.seed)

    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        out = {}
        for h, n in zip(self.spec, self.head_sizes):
            if h["cadence"] in self.cad:
                out[h["name"]] = torch.randint(0, n, (B,), generator=self.gen).to(dev)
            else:
                out[h["name"]] = self._full(h["default"], B, dev)
        return self._finalize(out, mask, sim)


# ------------------------------------------------------------------------------------------
# Parameterised rule-based manager. Every parameter is a number in [0, 1] (decoded below), so
# the evolutionary tuner searches a unit box. Thresholds are in the simulator's normalised
# observation units (queues as a share of the ED's treatment bays).
# ------------------------------------------------------------------------------------------
PARAM_NAMES = [
    "md_day", "md_evening", "md_night",          # base provider level per shift: 4*u in [0, 4]
    "rn_day", "rn_evening", "rn_night",          # base nurse level per shift: 4*u
    "md_demand_gain", "rn_demand_gain",          # extra levels per unit of (yesterday's arrivals / typical day - 1): 8*u
    "triage_nurses",                             # round(2*u)
    "admission_cap",                             # round(2*u)
    "discharge_push_occ",                        # early rounds when ward occupancy > 0.5 + 0.6*u (u > 0.83: never)
    "priority_rule",                             # floor(4*u)
    "provider_split",                            # floor(3*u)
    "fast_track_thr",                            # open when waiting ESI4-5 share >= 0.3*(u - 0.3) (u <= 0.3: always open)
    "overflow_low_thr",                          # hallway_low when waiting-for-bay share > 0.5*u
    "overflow_high_gap",                         # hallway_high when > low threshold + 0.5*u
    "callin_rn_thr",                             # call nurses when waiting-for-bay share > 0.8*u
    "callin_md_thr",                             # call a provider when waiting-for-provider share > 0.5*u
    "divert_thr",                                # divert when total not-yet-seen share > 0.2 + 2.5*u
    "agency_contract",                           # round(2*u)   (weekly; only acts from curriculum stage 2)
    "imaging_hours",                             # round(2*u)   (weekly)
]
# Hand-written default: staff up for the busy evening, down at night; react to yesterday's volume;
# two triage nurses; acuity with aging; fast track always open; overflow, call-in and diversion
# on rising queue thresholds (diversion only under extreme load).
RULE_DEFAULT = {
    "md_day": 0.5, "md_evening": 0.75, "md_night": 0.25, "rn_day": 0.5, "rn_evening": 0.75, "rn_night": 0.5,
    "md_demand_gain": 0.25, "rn_demand_gain": 0.25, "triage_nurses": 0.5, "admission_cap": 0.0,
    "discharge_push_occ": 0.65, "priority_rule": 0.6, "provider_split": 0.5, "fast_track_thr": 0.0,
    "overflow_low_thr": 0.2, "overflow_high_gap": 0.4, "callin_rn_thr": 0.3, "callin_md_thr": 0.3,
    "divert_thr": 0.5, "agency_contract": 0.0, "imaging_hours": 0.5,
}


def theta_from_dict(d: dict) -> torch.Tensor:
    return torch.tensor([float(d.get(k, RULE_DEFAULT[k])) for k in PARAM_NAMES], dtype=torch.float32)


class RulePolicy(Policy):
    """Rule-based manager. `theta` is [n_params] (one manager) or [B, n_params] (a population)."""

    def __init__(self, params: dict | torch.Tensor | None = None, id="rule_based", kind="rule_based",
                 label="Rule-based manager (hand-written thresholds)", objective=None, reward_weights=None,
                 stage="stage_1"):
        super().__init__()
        self.stage = stage
        self.active = {h["name"] for h in self.spec if h["cadence"] in STAGES[stage]}
        self.id, self.kind, self.label, self.objective, self.reward_weights = id, kind, label, objective, reward_weights
        if kind == "tuned_heuristic":
            self.note = ("Rule-based manager whose 21 parameters were tuned by evolutionary search (cross-entropy method) for this "
                         "objective. A tuned heuristic, not a learned agent. All numbers simulated.")
        if params is None:
            params = RULE_DEFAULT
        self.theta = params.clone().float() if isinstance(params, torch.Tensor) else theta_from_dict(params)

    def params_dict(self) -> dict:
        assert self.theta.dim() == 1
        return {k: round(float(v), 4) for k, v in zip(PARAM_NAMES, self.theta)}

    def reset(self, B, device):
        super().reset(B, device)
        self.theta = self.theta.to(device)

    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        th = self.theta.to(dev)
        th = th.unsqueeze(0).expand(B, -1) if th.dim() == 1 else th
        u = {k: th[:, i] for i, k in enumerate(PARAM_NAMES)}
        o = lambda name: obs[:, self.oi[name]]                                       # noqa: E731
        lvl = lambda x, n: torch.round(x).clamp(0, n - 1).long()                     # noqa: E731
        cat = lambda x, n: torch.floor(x * n).clamp(0, n - 1).long()                 # noqa: E731
        demand = o("arrivals_24h") - 1.0
        # yesterday's volume is unknown on the very first day (the trailing window is empty)
        demand = torch.where(o("arrivals_24h") < 0.3, torch.zeros_like(demand), demand)
        a = {}
        for s in ("day", "evening", "night"):
            a[f"md_{s}"] = lvl(4 * u[f"md_{s}"] + 8 * u["md_demand_gain"] * demand, 5)
            a[f"rn_{s}"] = lvl(4 * u[f"rn_{s}"] + 8 * u["rn_demand_gain"] * demand, 5)
        a["triage_nurses"] = lvl(2 * u["triage_nurses"], 3)
        a["admission_cap"] = lvl(2 * u["admission_cap"], 3)
        a["discharge_push"] = (o("ward_occupancy") > 0.5 + 0.6 * u["discharge_push_occ"]).long()
        a["priority_rule"] = cat(u["priority_rule"], 4)
        a["provider_split"] = cat(u["provider_split"], 3)
        a["fast_track"] = (o("waiting_esi45") >= 0.3 * (u["fast_track_thr"] - 0.3)).long()
        wb, wp = o("q_waiting_bay"), o("q_waiting_provider")
        lo = 0.5 * u["overflow_low_thr"]
        a["overflow_bays"] = (wb > lo).long() + (wb > lo + 0.5 * u["overflow_high_gap"]).long()
        rn_thr = 0.8 * u["callin_rn_thr"]
        need_rn, need_md = wb > rn_thr, wp > 0.5 * u["callin_md_thr"]
        rn_opt = torch.where(wb > 1.5 * rn_thr + 0.05, torch.full_like(a["fast_track"], 2), torch.ones_like(a["fast_track"]))
        a["call_in"] = torch.where(need_rn & need_md, torch.full_like(rn_opt, 4),
                                   torch.where(need_md, torch.full_like(rn_opt, 3),
                                               torch.where(need_rn, rn_opt, torch.zeros_like(rn_opt))))
        waiting = o("q_waiting_triage") + wb + wp
        a["divert"] = (waiting > 0.2 + 2.5 * u["divert_thr"]).long()
        a["agency_contract"] = lvl(2 * u["agency_contract"], 3)
        a["imaging_hours"] = lvl(2 * u["imaging_hours"], 3)
        for n in self.head_names:
            if n not in a or n not in self.active:        # heads outside this manager's curriculum stage stay at default
                a[n] = self._full(self.defaults[n], B, dev)
        return self._finalize(a, mask, sim)


class LearnedPolicy(Policy):
    """PPO network loaded from a JSON config + plain state_dict. Acts greedily (argmax per head)."""
    kind = "learned"

    def __init__(self, config: dict, state_dict: dict, device="cpu", deterministic=True):
        super().__init__()
        from .net import ActorCritic
        self.config = config
        self.id, self.label, self.objective = config["id"], config["label"], config.get("objective")
        self.note = config.get("note")
        self.reward_weights = config.get("reward_weights")
        self.net_heads = list(config["head_names"])
        self.enabled = set(config.get("enabled_heads", self.net_heads))
        self.net = ActorCritic(config["obs_dim"], config["head_sizes"], config.get("hidden", 256), config.get("layers", 2))
        self.net.load_state_dict(state_dict)
        self.net.to(device).eval()
        self.deterministic = deterministic
        self.set_weights(self.reward_weights or {})

    def set_weights(self, weights: dict):
        """Reward weights this agent is conditioned on (they are part of its observation). Only a
        weight-conditioned agent (config `weight_conditioned`) was trained to respond to changes."""
        self.reward_weights = {k: float(weights.get(k, 0.0)) for k in TERMS}
        self.w = torch.tensor([self.reward_weights[k] for k in TERMS], dtype=torch.float32)

    def reset(self, B, device):
        super().reset(B, device)
        self.net.to(device)

    @torch.no_grad()
    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        if next(self.net.parameters()).device != dev:
            self.net.to(dev)
        n_sim = self.config["sim_obs_dim"]
        if obs.shape[1] == n_sim:                     # raw sim.observe(): append this agent's own weights
            obs = torch.cat([obs, self.w.to(dev).unsqueeze(0).expand(B, -1)], 1)
        elif self.config.get("weight_conditioned") or obs.shape[1] != self.config["obs_dim"]:
            # conditioned agent: its own weights override whatever the env appended (also used when the caller's
            # weight vector has a different length than the one this network was trained with)
            obs = torch.cat([obs[:, :n_sim], self.w.to(dev).unsqueeze(0).expand(B, -1)], 1)
        if obs.shape[1] != self.config["obs_dim"]:    # network trained with a different number of weight entries
            nw = self.config["obs_dim"] - n_sim
            wpad = torch.zeros((B, nw), device=dev)
            wpad[:, :min(nw, obs.shape[1] - n_sim)] = obs[:, n_sim:n_sim + nw]
            obs = torch.cat([obs[:, :n_sim], wpad], 1)
        acts, _ = self.net.act(obs, deterministic=self.deterministic)
        out = {}
        for n in self.head_names:
            if n in self.net_heads and n in self.enabled:
                out[n] = acts[:, self.net_heads.index(n)].clamp(0, self.head_sizes[self.head_names.index(n)] - 1)
            else:
                out[n] = self._full(self.defaults[n], B, dev)
        return self._finalize(out, mask, sim)


class MultiPolicy:
    """Runs several policies on consecutive slices of one batch (evaluation and recording)."""

    def __init__(self, policies: list[Policy], sizes: list[int]):
        self.policies, self.slices, o = policies, [], 0
        for s in sizes:
            self.slices.append(slice(o, o + s))
            o += s
        self.B = o

    def reset(self, B, device):
        assert B == self.B
        for p, s in zip(self.policies, self.slices):
            p.reset(s.stop - s.start, device)

    def act(self, obs, mask, sim=None):
        outs = [p.act(obs[s], {k: v[s] for k, v in mask.items()}, None) for p, s in zip(self.policies, self.slices)]
        return {n: torch.cat([o[n] for o in outs], 0) for n in outs[0]}


# ------------------------------------------------------------------------------------------
# registry
# ------------------------------------------------------------------------------------------
def save_heuristic(path: Path, pol: RulePolicy, extra: dict | None = None):
    from .common import behaviour_fingerprint, sim_fingerprint, write_json
    d = dict(id=pol.id, kind=pol.kind, label=pol.label, objective=pol.objective, reward_weights=pol.reward_weights,
             type="rule_params", stage=pol.stage, params=pol.params_dict(), param_names=PARAM_NAMES, sim_fingerprint=sim_fingerprint(),
             sim_behaviour_fingerprint=behaviour_fingerprint(),
             synthetic=True)
    d.update(extra or {})
    write_json(path, d, indent=1)


def _policy_files() -> dict:
    out = {}
    if POLICY_DIR.exists():
        for f in sorted(POLICY_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue
            if isinstance(d, dict) and "id" in d and d.get("type") in ("rule_params", "ppo"):
                out[d["id"]] = (f, d)
    return out


def expected_managers() -> list[dict]:
    from .common import OBJ_SLUG, SCRATCH_OBJECTIVES
    rows = [dict(id="fixed", kind="fixed", label=FixedPolicy.label, objective=None, reward_weights=None),
            dict(id="rule_based", kind="rule_based", label="Rule-based manager (hand-written thresholds)", objective=None, reward_weights=None),
            dict(id="random", kind="random", label=RandomPolicy.label, objective=None, reward_weights=None)]
    for obj, slug in OBJ_SLUG.items():
        rows.append(dict(id=f"tuned_{slug}", kind="tuned_heuristic", label=f"Tuned heuristic: {obj}", objective=obj,
                         reward_weights=weights_dict(obj)))
    for obj, slug in OBJ_SLUG.items():
        rows.append(dict(id=f"ppo_{slug}", kind="learned", label=f"Learned (PPO, cloned from tuned heuristic then fine-tuned): {obj}",
                         objective=obj, reward_weights=weights_dict(obj)))
    for obj in SCRATCH_OBJECTIVES:
        rows.append(dict(id=f"ppo_scratch_{OBJ_SLUG[obj]}", kind="learned", label=f"Learned (PPO from scratch): {obj}", objective=obj,
                         reward_weights=weights_dict(obj)))
    return rows


def heldout_verdicts() -> dict:
    """manager id -> one line per scenario: held-out verdict against the tuned heuristic of its objective
    (from rl/results/results.json; empty when there is no evaluation yet)."""
    from .common import RESULTS_DIR
    out = {}
    try:
        res = json.loads((RESULTS_DIR / "results.json").read_text())
    except Exception:
        return out
    for c in res.get("comparisons", []):
        if c["b"].startswith("tuned_") and not c["a"].startswith("tuned_"):
            d = c["paired_diff"]
            out.setdefault(c["a"], []).append(f"{c['scenario']}: {c['verdict']} {c['b']} on {c['objective']} score "
                                              f"({d['mean']:+.4f} ± {d['ci95']:.4f}, paired, held-out seeds)")
    return {k: "; ".join(v) for k, v in out.items()}


def list_managers() -> list[dict]:
    files = _policy_files()
    rows, seen = [], set()
    for r in expected_managers():
        r = dict(r)
        if r["kind"] in ("fixed", "rule_based", "random"):
            r["available"] = True
        else:
            f = files.get(r["id"])
            ok = f is not None
            if ok and f[1]["type"] == "ppo":
                ok = (f[0].parent / f[1]["checkpoint"]).exists()
            if ok:
                for k in ("label", "objective", "reward_weights", "note"):
                    if f[1].get(k) is not None or k in r:
                        r[k] = f[1].get(k, r.get(k))
            r["available"] = bool(ok)
        seen.add(r["id"])
        rows.append(r)
    cond = files.get("ppo_cond")
    cond_ok = cond is not None and (cond[0].parent / cond[1]["checkpoint"]).exists()
    rows.append(dict(id="ppo_cond", kind="learned", label="Learned (PPO, weight-conditioned; balanced weights by default)",
                     objective=None, reward_weights=weights_dict("balanced"), available=bool(cond_ok), weight_conditioned=True))
    seen.add("ppo_cond")
    if cond_ok and cond[1].get("note"):
        rows[-1]["note"] = cond[1]["note"]
    for obj in OBJECTIVES:
        if obj == "cost_s.t._p95_wait":
            continue
        rows.append(dict(id=f"ppo_cond_{obj}", kind="learned", label=f"Learned (PPO, weight-conditioned) at {obj} weights",
                         objective=obj, reward_weights=weights_dict(obj), available=bool(cond_ok), weight_conditioned=True))
        if cond_ok and cond[1].get("note"):
            rows[-1]["note"] = cond[1]["note"]
        seen.add(f"ppo_cond_{obj}")
    for mid, (f, d) in files.items():                 # anything else saved under rl/policies/
        if mid in seen:
            continue
        ok = d["type"] != "ppo" or (f.parent / d["checkpoint"]).exists()
        rows.append(dict(id=mid, kind=d["kind"], label=d["label"], objective=d.get("objective"),
                         reward_weights=d.get("reward_weights"), available=bool(ok)))
    verdicts = heldout_verdicts()
    for r in rows:
        if r["kind"] == "tuned_heuristic" and "note" not in r:
            r["note"] = "Rule-based manager with parameters tuned by evolutionary search; a tuned heuristic, not a learned agent."
        if r["kind"] == "learned":
            r["heldout_verdict"] = verdicts.get(r["id"])
    return rows


def load_manager(id: str, device="cpu") -> Policy:
    if id == "fixed":
        p = FixedPolicy()
    elif id == "rule_based":
        p = RulePolicy()
    elif id == "random":
        p = RandomPolicy()
    else:
        files = _policy_files()
        preset = None
        if id.startswith("ppo_cond_") and id[len("ppo_cond_"):] in OBJECTIVES:
            preset, real_id, id = id[len("ppo_cond_"):], id, "ppo_cond"
        if id not in files:
            raise KeyError(f"manager '{id}' is not available (no file under rl/policies/)")
        f, d = files[id]
        if d["type"] == "rule_params":
            p = RulePolicy(d["params"], id=d["id"], kind=d["kind"], label=d["label"], objective=d.get("objective"),
                           reward_weights=d.get("reward_weights"), stage=d.get("stage", "stage_1"))
        else:
            sd = torch.load(f.parent / d["checkpoint"], map_location="cpu")
            p = LearnedPolicy(d, sd, device=device)
            if preset is not None:
                p.id, p.objective = real_id, preset
                p.label = f"Learned (PPO, weight-conditioned) at {preset} weights"
                p.set_weights(weights_dict(preset))
        p.file_fingerprint = d.get("sim_fingerprint")
        p.behaviour_fingerprint = d.get("sim_behaviour_fingerprint")
    p.reset(1, device)
    return p
