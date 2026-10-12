"""Managers behind the Policy interface of contracts/sim_api.md.

kinds: fixed, rule_based, random, tuned_heuristic (a rule-based manager whose parameters were
found by evolutionary search; NOT a learned agent), learned (PPO network).
"""
from __future__ import annotations

import json
from pathlib import Path

import torch

import math

from .common import (DEFAULT_HOSPITAL, IMPULSE_HEADS, OBJECTIVES, POLICY_DIR, STAGES, TERMS, calibration_status, get_spec, hospital_id,
                     is_stale, paths, weights_dict, weights_vec)
from .objectives import LOCKED_HEADS, OPERATOR_OBJECTIVES, OPERATOR_SLUG, OPERATOR_STAGE


class Policy:
    id: str = ""
    kind: str = ""
    label: str = ""
    objective: str | None = None
    reward_weights: dict | None = None

    def __init__(self, hospital: str | None = None):
        self.hospital = hospital_id(hospital)
        sp = get_spec(hospital=self.hospital)
        self.row_defaults = None
        self.dow_prof, self.shift_starts = sp["dow_prof"], sp["shift_starts"]
        self.spec = sp["action_spec"]
        self.head_names = sp["head_names"]
        self.head_sizes = [len(h["options"]) for h in self.spec]
        self.defaults = {h["name"]: int(h["default"]) for h in self.spec}
        self.obs_names = sp["obs_names"]
        self.sim_obs_dim = sp["obs_dim"]
        self.oi = {n: i for i, n in enumerate(self.obs_names)}
        self.B, self.device = 1, torch.device("cpu")

    def reset(self, B: int, device, defaults: dict | None = None) -> None:
        """`defaults` (optional): head -> LongTensor[B], the baseline actions of the environment rows this policy
        drives (they differ between ensemble members). Without it the hospital's point-calibration defaults apply."""
        self.B, self.device = int(B), torch.device(device)
        self.row_defaults = defaults

    def _default(self, n: str, B: int, device):
        rd = self.row_defaults
        if rd is not None and n in rd and rd[n].shape[0] == B:
            return rd[n].to(device)
        return self._full(self.defaults[n], B, device)

    def act(self, obs, mask, sim=None) -> dict:
        raise NotImplementedError

    note: str | None = None

    def info(self) -> dict:
        d = dict(id=self.id, kind=self.kind, label=self.label, objective=self.objective, reward_weights=self.reward_weights)
        d["hospital_id"] = self.hospital
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
            keep = self._default(n, v.shape[0], v.device) if n in IMPULSE_HEADS else sim.settings[n]
            out[n] = torch.where(m, v, keep)
        return out


FIXED_LABEL = "Fixed staffing (contract defaults)"
FIXED_LABEL_CALIBRATED = "Current practice (calibrated baseline actions)"


class FixedPolicy(Policy):
    """The baseline: every head at its default. With a calibration file for the hospital the defaults are the
    calibration's `baseline_actions`, i.e. the hospital's current practice as far as public data pins it down."""
    id, kind, label = "fixed", "fixed", FIXED_LABEL

    def __init__(self, hospital: str | None = None):
        super().__init__(hospital)
        if calibration_status(self.hospital)["calibration_file"]:
            self.label = FIXED_LABEL_CALIBRATED

    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        return self._finalize({n: self._default(n, B, dev) for n in self.head_names}, mask, sim)


class RandomPolicy(Policy):
    id, kind, label = "random", "random", "Random (uniform over hourly and daily options)"

    def __init__(self, seed: int = 12345, stage: str = "stage_1", hospital: str | None = None):
        super().__init__(hospital)
        self.seed, self.cad = seed, STAGES[stage]
        self.gen = torch.Generator().manual_seed(seed)

    def reset(self, B, device, defaults=None):
        super().reset(B, device, defaults)
        self.gen = torch.Generator().manual_seed(self.seed)

    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        out = {}
        for h, n in zip(self.spec, self.head_sizes):
            if h["cadence"] in self.cad:
                out[h["name"]] = torch.randint(0, n, (B,), generator=self.gen).to(dev)
            else:
                out[h["name"]] = self._default(h["name"], B, dev)
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
    # ---- added for the operator objectives; every default below is a no-op, so 21-parameter files load unchanged
    "md_dow_gain", "rn_dow_gain",                # extra levels per unit of (published day-of-week arrival factor - 1): 16*u
    "triage_demand_gain",                        # extra triage stations per unit of (yesterday's arrivals / typical day - 1): 4*u
    "callin_forecast_gain",                      # anticipatory call-in: thresholds divided by 1 + 2*u*relu(next-hour arrival forecast - 1)
    "callin_late_cut",                           # no call-in when <= round(4*u) hours of the shift remain (called staff leave at shift end)
    "callin_occ_thr",                            # also call a nurse when bay occupancy > 0.6 + 0.4*u and the forecast is >= typical (u >= 0.99: never)
    "push_boarding_thr",                         # early discharge rounds also when boarding share of bays > 0.3*u (u >= 0.99: never)
    "split_dispo_thr",                           # favour dispositions when > 10*u patients are ready for disposition (u >= 0.99: never)
    "split_new_thr",                             # favour new patients when waiting-for-provider share > 0.5*u (u >= 0.99: never)
    "ft_close_night",                            # u > 0.5: fast track closed 23:00-07:00
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
    "md_dow_gain": 0.0, "rn_dow_gain": 0.0, "triage_demand_gain": 0.0, "callin_forecast_gain": 0.0, "callin_late_cut": 0.0,
    "callin_occ_thr": 1.0, "push_boarding_thr": 1.0, "split_dispo_thr": 1.0, "split_new_thr": 1.0, "ft_close_night": 0.0,
}
N_PARAMS_V1 = 21


def theta_from_dict(d: dict) -> torch.Tensor:
    return torch.tensor([float(d.get(k, RULE_DEFAULT[k])) for k in PARAM_NAMES], dtype=torch.float32)


class RulePolicy(Policy):
    """Rule-based manager. `theta` is [n_params] (one manager) or [B, n_params] (a population)."""

    def __init__(self, params: dict | torch.Tensor | None = None, id="rule_based", kind="rule_based",
                 label="Rule-based manager (hand-written thresholds)", objective=None, reward_weights=None,
                 stage="stage_1", hospital: str | None = None, locked=()):
        super().__init__(hospital)
        self.stage = stage
        self.locked = tuple(locked or ())
        self.active = {h["name"] for h in self.spec if h["cadence"] in STAGES[stage] and h["name"] not in self.locked}
        self.id, self.kind, self.label, self.objective, self.reward_weights = id, kind, label, objective, reward_weights
        if kind == "tuned_heuristic":
            self.note = (f"Rule-based manager whose {len(PARAM_NAMES)} parameters were tuned by evolutionary search (cross-entropy method) "
                         "for this objective. A tuned heuristic, not a learned agent. All numbers simulated.")
        if params is None:
            params = RULE_DEFAULT
        self.theta = params.clone().float() if isinstance(params, torch.Tensor) else theta_from_dict(params)
        if self.theta.shape[-1] < len(PARAM_NAMES):               # a population / vector from the 21-parameter version
            pad = theta_from_dict(RULE_DEFAULT)[self.theta.shape[-1]:]
            self.theta = torch.cat([self.theta, pad.expand(*self.theta.shape[:-1], -1)], -1)

    def params_dict(self) -> dict:
        assert self.theta.dim() == 1
        return {k: round(float(v), 4) for k, v in zip(PARAM_NAMES, self.theta)}

    def reset(self, B, device, defaults=None):
        super().reset(B, device, defaults)
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
        # calendar features decoded from the observation (the same for the whole batch; kept per row for safety)
        two_pi = 2 * math.pi
        hod = torch.round(torch.atan2(o("hour_sin"), o("hour_cos")) / two_pi * 24).long() % 24
        dow = torch.round(torch.atan2(o("dow_sin"), o("dow_cos")) / two_pi * 7).long() % 7
        dowf = torch.tensor(self.dow_prof, device=dev, dtype=torch.float32)[dow] - 1.0     # published weekday factor of the day starting
        s0 = int(self.shift_starts[0])
        shift_left = 8 - ((hod - s0) % 8)                                                  # hours left in the running shift (8..1)
        fc = o("arrival_forecast_next_hour")
        a = {}
        for s in ("day", "evening", "night"):
            a[f"md_{s}"] = lvl(4 * u[f"md_{s}"] + 8 * u["md_demand_gain"] * demand + 16 * u["md_dow_gain"] * dowf, 5)
            a[f"rn_{s}"] = lvl(4 * u[f"rn_{s}"] + 8 * u["rn_demand_gain"] * demand + 16 * u["rn_dow_gain"] * dowf, 5)
        a["triage_nurses"] = lvl(2 * u["triage_nurses"] + 4 * u["triage_demand_gain"] * demand, 3)
        a["admission_cap"] = lvl(2 * u["admission_cap"], 3)
        a["discharge_push"] = ((o("ward_occupancy") > 0.5 + 0.6 * u["discharge_push_occ"])
                               | ((o("q_boarding") > 0.3 * u["push_boarding_thr"]) & (u["push_boarding_thr"] < 0.99))).long()
        a["priority_rule"] = cat(u["priority_rule"], 4)
        wb, wp = o("q_waiting_bay"), o("q_waiting_provider")
        split = cat(u["provider_split"], 3)
        split = torch.where((o("q_ready_disposition") > u["split_dispo_thr"]) & (u["split_dispo_thr"] < 0.99), torch.full_like(split, 2), split)
        split = torch.where((wp > 0.5 * u["split_new_thr"]) & (u["split_new_thr"] < 0.99), torch.zeros_like(split), split)
        a["provider_split"] = split
        night = (hod >= 23) | (hod < 7)
        a["fast_track"] = ((o("waiting_esi45") >= 0.3 * (u["fast_track_thr"] - 0.3)) & ~(night & (u["ft_close_night"] > 0.5))).long()
        lo = 0.5 * u["overflow_low_thr"]
        a["overflow_bays"] = (wb > lo).long() + (wb > lo + 0.5 * u["overflow_high_gap"]).long()
        antic = 1.0 + 2.0 * u["callin_forecast_gain"] * torch.relu(fc - 1.0)               # busy hour ahead: act on a shorter queue
        rn_thr = 0.8 * u["callin_rn_thr"] / antic
        allowed = shift_left > torch.round(4 * u["callin_late_cut"])
        need_rn = (wb > rn_thr) | ((o("bay_occupancy") > 0.6 + 0.4 * u["callin_occ_thr"]) & (fc >= 1.0) & (u["callin_occ_thr"] < 0.99))
        need_rn, need_md = need_rn & allowed, (wp > 0.5 * u["callin_md_thr"] / antic) & allowed
        rn_opt = torch.where(wb > 1.5 * rn_thr + 0.05, torch.full_like(a["fast_track"], 2), torch.ones_like(a["fast_track"]))
        a["call_in"] = torch.where(need_rn & need_md, torch.full_like(rn_opt, 4),
                                   torch.where(need_md, torch.full_like(rn_opt, 3),
                                               torch.where(need_rn, rn_opt, torch.zeros_like(rn_opt))))
        waiting = o("q_waiting_triage") + wb + wp
        a["divert"] = (waiting > 0.2 + 2.5 * u["divert_thr"]).long()
        a["agency_contract"] = lvl(2 * u["agency_contract"], 3)
        a["imaging_hours"] = lvl(2 * u["imaging_hours"], 3)
        for n in self.head_names:
            if n not in a or n not in self.active:        # heads outside this manager's stage, or locked: the baseline
                a[n] = self._default(n, B, dev)
        return self._finalize(a, mask, sim)


class LearnedPolicy(Policy):
    """PPO network loaded from a JSON config + plain state_dict. Acts greedily (argmax per head)."""
    kind = "learned"

    def __init__(self, config: dict, state_dict: dict, device="cpu", deterministic=True, hospital: str | None = None):
        super().__init__(hospital or config.get("hospital_id"))
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

    def reset(self, B, device, defaults=None):
        super().reset(B, device, defaults)
        self.net.to(device)

    @torch.no_grad()
    def act(self, obs, mask, sim=None):
        B, dev = obs.shape[0], obs.device
        if next(self.net.parameters()).device != dev:
            self.net.to(dev)
        n_sim = self.config["sim_obs_dim"]
        # The agent always sees ITS OWN reward weights (the ones it was trained or conditioned with, incl. the Lagrange
        # multipliers at export), whatever weight vector the caller's environment appended: an evaluation environment
        # shared by many managers cannot carry each one's weights. Networks trained with fewer weight entries get the
        # leading ones (the term order only ever grew at the end).
        nw = self.config["obs_dim"] - n_sim
        w = torch.zeros((B, nw), device=dev)
        k = min(nw, self.w.shape[0])
        w[:, :k] = self.w.to(dev)[:k]
        obs = torch.cat([obs[:, :n_sim], w], 1)
        acts, _ = self.net.act(obs, deterministic=self.deterministic)
        out = {}
        for n in self.head_names:
            if n in self.net_heads and n in self.enabled:
                out[n] = acts[:, self.net_heads.index(n)].clamp(0, self.head_sizes[self.head_names.index(n)] - 1)
            else:
                out[n] = self._default(n, B, dev)
        return self._finalize(out, mask, sim)


class MultiPolicy:
    """Runs several policies on consecutive slices of one batch (evaluation and recording)."""

    def __init__(self, policies: list[Policy], sizes: list[int]):
        self.policies, self.slices, o = policies, [], 0
        for s in sizes:
            self.slices.append(slice(o, o + s))
            o += s
        self.B = o

    def reset(self, B, device, defaults=None):
        assert B == self.B
        for p, s in zip(self.policies, self.slices):
            p.reset(s.stop - s.start, device, None if defaults is None else {n: v[s] for n, v in defaults.items()})

    def act(self, obs, mask, sim=None):
        outs = [p.act(obs[s], {k: v[s] for k, v in mask.items()}, None) for p, s in zip(self.policies, self.slices)]
        return {n: torch.cat([o[n] for o in outs], 0) for n in outs[0]}


# ------------------------------------------------------------------------------------------
# registry (per hospital; the default hospital's files stay in rl/policies/)
# ------------------------------------------------------------------------------------------
def policy_dir(hospital: str | None = None) -> Path:
    h = hospital_id(hospital)
    return POLICY_DIR if h == DEFAULT_HOSPITAL else paths(h).policies


def save_heuristic(path: Path, pol: RulePolicy, extra: dict | None = None):
    from .common import fingerprints, write_json
    d = dict(id=pol.id, kind=pol.kind, label=pol.label, objective=pol.objective, reward_weights=pol.reward_weights,
             type="rule_params", stage=pol.stage, locked_heads=list(pol.locked), params=pol.params_dict(), param_names=PARAM_NAMES,
             **fingerprints(pol.hospital), synthetic=True)
    d.update(extra or {})
    write_json(path, d, indent=1)


def _policy_files(hospital: str | None = None) -> dict:
    out, h, pdir = {}, hospital_id(hospital), policy_dir(hospital)
    if pdir.exists():
        for f in sorted(pdir.glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue
            if isinstance(d, dict) and "id" in d and d.get("type") in ("rule_params", "ppo"):
                if d.get("hospital_id") not in (None, h):          # a file of another hospital: never offered here
                    continue
                out[d["id"]] = (f, d)
    return out


def all_objectives() -> dict:
    """objective name -> file slug, legacy weighted objectives then operator objectives."""
    from .common import OBJ_SLUG
    return {**OBJ_SLUG, **OPERATOR_SLUG}


def expected_managers(hospital: str | None = None) -> list[dict]:
    from .common import OBJ_SLUG, SCRATCH_OBJECTIVES
    cal = calibration_status(hospital)["calibration_file"]
    rows = [dict(id="fixed", kind="fixed", label=FIXED_LABEL_CALIBRATED if cal else FIXED_LABEL, objective=None, reward_weights=None),
            dict(id="rule_based", kind="rule_based", label="Rule-based manager (hand-written thresholds)", objective=None, reward_weights=None),
            dict(id="random", kind="random", label=RandomPolicy.label, objective=None, reward_weights=None)]
    for obj, slug in all_objectives().items():
        rows.append(dict(id=f"tuned_{slug}", kind="tuned_heuristic", label=f"Tuned heuristic: {obj}", objective=obj,
                         reward_weights=weights_dict(obj)))
    for obj, slug in all_objectives().items():
        rows.append(dict(id=f"ppo_{slug}", kind="learned", label=f"Learned (PPO, cloned from tuned heuristic then fine-tuned): {obj}",
                         objective=obj, reward_weights=weights_dict(obj)))
    for obj in SCRATCH_OBJECTIVES:
        rows.append(dict(id=f"ppo_scratch_{OBJ_SLUG[obj]}", kind="learned", label=f"Learned (PPO from scratch): {obj}", objective=obj,
                         reward_weights=weights_dict(obj)))
    return rows


def heldout_verdicts(hospital: str | None = None) -> dict:
    """manager id -> one line per scenario: held-out verdict against the tuned heuristic of its objective
    (from the hospital's results.json; empty when there is no evaluation yet)."""
    out = {}
    try:
        res = json.loads((paths(hospital).results / "results.json").read_text())
    except Exception:
        return out
    for c in res.get("comparisons", []):
        if c["b"].startswith("tuned_") and not c["a"].startswith("tuned_"):
            d = c["paired_diff"]
            out.setdefault(c["a"], []).append(f"{c['scenario']}: {c['verdict']} {c['b']} on {c['objective']} score "
                                              f"({d['mean']:+.4f} ± {d['ci95']:.4f}, paired, held-out seeds)")
    return {k: "; ".join(v) for k, v in out.items()}


def list_managers(hospital: str | None = None) -> list[dict]:
    files = _policy_files(hospital)
    rows, seen = [], set()
    for r in expected_managers(hospital):
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
    for mid, (f, d) in files.items():                 # anything else saved in the hospital's policy directory
        if mid in seen:
            continue
        ok = d["type"] != "ppo" or (f.parent / d["checkpoint"]).exists()
        rows.append(dict(id=mid, kind=d["kind"], label=d["label"], objective=d.get("objective"),
                         reward_weights=d.get("reward_weights"), available=bool(ok)))
    verdicts = heldout_verdicts(hospital)
    h = hospital_id(hospital)
    for r in rows:
        if r["kind"] == "tuned_heuristic" and "note" not in r:
            r["note"] = "Rule-based manager with parameters tuned by evolutionary search; a tuned heuristic, not a learned agent."
        if r["kind"] == "learned":
            r["heldout_verdict"] = verdicts.get(r["id"])
        f = files.get("ppo_cond" if r["id"].startswith("ppo_cond") else r["id"])
        if f is not None and r["available"]:
            r["stale"] = is_stale(f[1], h)            # built against other dynamics or another calibration of this hospital
    return rows


def load_manager(id: str, device="cpu", hospital: str | None = None) -> Policy:
    h = hospital_id(hospital)
    if id == "fixed":
        p = FixedPolicy(hospital=h)
    elif id == "rule_based":
        p = RulePolicy(hospital=h)
    elif id == "random":
        p = RandomPolicy(hospital=h)
    else:
        files = _policy_files(h)
        preset = None
        if id.startswith("ppo_cond_") and id[len("ppo_cond_"):] in OBJECTIVES:
            preset, real_id, id = id[len("ppo_cond_"):], id, "ppo_cond"
        if id not in files:
            raise KeyError(f"manager '{id}' is not available for hospital '{h}' (no file under {policy_dir(h)})")
        f, d = files[id]
        if d["type"] == "rule_params":
            p = RulePolicy(d["params"], id=d["id"], kind=d["kind"], label=d["label"], objective=d.get("objective"),
                           reward_weights=d.get("reward_weights"), stage=d.get("stage", "stage_1"), hospital=h,
                           locked=d.get("locked_heads") or ())
        else:
            sd = torch.load(f.parent / d["checkpoint"], map_location="cpu")
            p = LearnedPolicy(d, sd, device=device, hospital=h)
            if preset is not None:
                p.id, p.objective = real_id, preset
                p.label = f"Learned (PPO, weight-conditioned) at {preset} weights"
                p.set_weights(weights_dict(preset))
        p.file_fingerprint = d.get("sim_fingerprint")
        p.behaviour_fingerprint = d.get("sim_behaviour_fingerprint")
        p.calibration_fingerprint = d.get("calibration_fingerprint")
        p.stale = is_stale(d, h)
    p.reset(1, device)
    return p
