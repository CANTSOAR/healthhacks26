"""Batched Gymnasium-style environment over the simulator. Everything stays on the sim device.

One step = one simulated hour. Observation = sim.observe() ++ reward-weight vector (len(common.TERMS)).
`hospital` picks the hospital (else HOSPITAL_ID, else the default); `member` picks one member of that
hospital's calibration ensemble (None = the point calibration). `locked_heads` are held at the hospital's
baseline whatever the policy sends (operator objectives lock ambulance diversion and the admission cap).
Actions: dict head -> LongTensor[B], or LongTensor[B, n_heads] in action_spec order.
The simulator keeps one clock for the whole batch, so resets are synchronous: every hospital
finishes its episode on the same step and the batch is re-seeded together.
"""
from __future__ import annotations

import torch

from sim import HospitalSim, load_scenario

from .common import (FATIGUE_THRESHOLD, IMPULSE_HEADS, STAGES, TERMS, hospital_id, load_scales, member_overrides, scales_vec, weights_vec)
from .objectives import EPISODE_METRICS

X_TRANSFER = 4                                  # sim.exits column (contracts/enums.yaml patient_exit: transferred)


def reward_terms(m: dict, scale: torch.Tensor) -> torch.Tensor:
    """[B, 8] baseline-normalised reward terms for one hour of metrics (order = common.TERMS).

    wait: patient-minutes accrued this hour by everyone not yet seen: the simulator's
    `waiting_patient_minutes` when it emits it, else waiting_count (end of hour) x 60.
    staff: overtime hours + staff-hours of fatigue above the threshold.
    revenue: negative (a reward), normalised by the COST scale so cost+revenue weights give margin.
    labor: cost_labor (wages, overtime, agency), the controllable part of cost.
    los: ed_census (patients in the ED at the end of the hour = patient-hours of ED stay this hour).
    opcost: cost_labor + cost_fixed (staffing plus the fixed cost of staffed spaces).
    """
    staff = m["overtime_hours"] + torch.relu(m["fatigue_mean"] - FATIGUE_THRESHOLD) * m["staff_on_shift"]
    wait = m["waiting_patient_minutes"] if "waiting_patient_minutes" in m else m["waiting_count"] * 60.0
    raw = torch.stack([m["cost_total"], wait, m["lwbs"], m["adverse_events"],
                       m["boarding_hours"], staff, -m["revenue"], m["cost_labor"], m["ed_census"],
                       m["cost_labor"] + m["cost_fixed"]], 1)
    return raw / scale


class HospitalEnv:
    def __init__(self, scenario="normal_week", batch_size=1, device="cpu", seed=0, episode_hours=720,
                 stage="stage_1", weights="balanced", scales: dict | None = None, overrides: dict | None = None,
                 auto_reset=True, hospital: str | None = None, member: int | dict | None = None, locked_heads=()):
        self.scenario = scenario
        self.hospital = hospital_id(hospital)
        self.member = member if not isinstance(member, dict) else member.get("id")
        self.locked_heads = tuple(locked_heads or ())
        scn = load_scenario(scenario, overrides=member_overrides(self.hospital, member, overrides))
        self.sim = HospitalSim(scn, batch_size=batch_size, device=device, seed=seed)
        self.B, self.device = self.sim.B, self.sim.device
        self.episode_hours = int(episode_hours)
        self.auto_reset = auto_reset
        self.spec = self.sim.action_spec()
        self.head_names = [h["name"] for h in self.spec]
        self.head_sizes = [len(h["options"]) for h in self.spec]
        self.defaults = [int(h["default"]) for h in self.spec]
        self.cadence = {h["name"]: h["cadence"] for h in self.spec}
        self.set_stage(stage)
        self.scales = scales if scales is not None else load_scales(hospital=self.hospital)
        self._i_hi = self.sim.obs_names().index("waiting_esi12")
        self.scale = scales_vec(self.scales, self.device)
        self.sim_obs_dim = int(self.sim.obs_dim)
        self.obs_dim = self.sim_obs_dim + len(TERMS)
        self.obs_weights = None
        self.set_weights(weights)
        self._seed_to(seed)
        self._zero_stats()

    # ---- configuration
    def set_stage(self, stage: str):
        self.stage = stage
        cad = STAGES[stage]
        self.enabled = {h["name"]: (h["cadence"] in cad and h.get("implemented", True) and h["name"] not in self.locked_heads)
                        for h in self.spec}

    def set_weights(self, weights):
        if isinstance(weights, torch.Tensor):
            w = weights.to(self.device, torch.float32)
            w = w.expand(self.B, len(TERMS)).clone() if w.dim() == 1 else w.clone()
        else:
            w = weights_vec(weights, self.device).unsqueeze(0).repeat(self.B, 1)
        self.weights = w

    def set_obs_weights(self, weights):
        """Pin the weight vector shown in the observation (reward still uses `set_weights`). Lagrangian training
        changes the reward weights every rollout; the policy must not see them move, and at deployment it is given
        the objective's own constant weights."""
        w = weights.to(self.device, torch.float32) if isinstance(weights, torch.Tensor) else weights_vec(weights, self.device)
        self.obs_weights = w.expand(self.B, len(TERMS)).clone() if w.dim() == 1 else w.clone()

    def _seed_to(self, seed):
        if isinstance(seed, torch.Tensor):
            self.seeds = seed.to(self.device, torch.long).reshape(-1).expand(self.B).clone()
        else:
            self.seeds = int(seed) + torch.arange(self.B, device=self.device, dtype=torch.long)
        self.seed_stride = int(self.seeds.max() - self.seeds.min()) + 1

    def _zero_stats(self):
        self.h = 0
        self.ep_terms = torch.zeros((self.B, len(TERMS)), device=self.device)
        self.ep_return = torch.zeros((self.B,), device=self.device)
        self.ep_hi = torch.zeros((self.B,), device=self.device)       # sum over hours of ESI 1-2 patients still waiting
        self.ep_wait_min = torch.zeros((self.B,), device=self.device)
        self.last_sent = {}

    def default_actions(self) -> dict:
        """head -> LongTensor[B]: this environment's baseline ("current practice") actions."""
        return {n: torch.full((self.B,), d, device=self.device, dtype=torch.long) for n, d in zip(self.head_names, self.defaults)}

    def episode_metrics(self) -> torch.Tensor:
        """[B, len(EPISODE_METRICS)] for the episode so far (rl.objectives.EPISODE_METRICS order)."""
        sim, days = self.sim, max(self.h, 1) / 24.0
        ep, s, em = sim.ep, sim.episode_summary(), sim.episode_means()
        f = lambda k: ep[k].to(torch.float32)                                        # noqa: E731
        d = dict(s)
        d.update(labor_cost_per_day=f("cost_labor") / days, fixed_cost_per_day=f("cost_fixed") / days,
                 operating_cost_per_day=(f("cost_labor") + f("cost_fixed")) / days, adverse_events_per_day=f("adverse_events") / days,
                 deaths_per_day=f("deaths") / days, lwbs_per_day=f("lwbs") / days, arrivals_per_day=f("arrivals") / days,
                 diverted_per_day=f("diverted") / days, treated_per_day=f("treated") / days, admissions_per_day=f("admissions") / days,
                 transfers_per_day=sim.exits[:, X_TRANSFER].to(torch.float32) / days,
                 ed_los_mean_min=f("ed_los_sum_min") / f("ed_departures").clamp(min=1.0),
                 wait_patient_hours_per_day=self.ep_wait_min / 60.0 / days, ed_patient_hours_per_day=em["ed_census"] * 24.0,
                 hi_acuity_wait_hours_per_day=self.ep_hi / days, staff_hours_per_day=em["staff_on_shift"] * 24.0,
                 revenue_per_day=f("revenue") / days)
        return torch.stack([d[k].to(torch.float32) for k in EPISODE_METRICS], 1)

    # ---- gym API
    def reset(self, seed=None) -> torch.Tensor:
        if seed is not None:
            self._seed_to(seed)
        self.sim.reset(self.seeds)
        self._zero_stats()
        return self.observe()

    def observe(self) -> torch.Tensor:
        return torch.cat([self.sim.observe(), self.weights if self.obs_weights is None else self.obs_weights], 1)

    def action_mask(self) -> dict:
        """True where the head can be changed now (cadence boundary AND enabled by the curriculum)."""
        m = self.sim.action_mask()
        return {n: (m[n] & self.enabled[n]) for n in self.head_names}

    def mask_vector(self) -> torch.Tensor:
        """BoolTensor[n_heads]; masks are uniform over the batch because the clock is shared."""
        m = self.action_mask()
        return torch.stack([m[n][0] for n in self.head_names])

    def _to_dict(self, actions) -> dict:
        if isinstance(actions, dict):
            return actions
        return {n: actions[:, i] for i, n in enumerate(self.head_names)}

    def step(self, actions):
        actions = self._to_dict(actions)
        sm = self.sim.action_mask()
        send = {}
        for i, n in enumerate(self.head_names):
            if not bool(sm[n][0]):
                continue                                  # masked: previous setting persists
            if self.enabled[n] and n in actions:
                send[n] = actions[n].to(self.device, torch.long).clamp(0, self.head_sizes[i] - 1)
            elif not self.enabled[n]:
                send[n] = torch.full((self.B,), self.defaults[i], device=self.device, dtype=torch.long)
        self.last_sent = send
        m = self.sim.step(send)
        terms = reward_terms(m, self.scale)
        reward = -(terms * self.weights).sum(1)
        self.ep_terms += terms
        self.ep_return += reward
        self.ep_wait_min += m["waiting_patient_minutes"] if "waiting_patient_minutes" in m else m["waiting_count"] * 60.0
        self.h += 1
        obs = self.observe()
        self.ep_hi += obs[:, self._i_hi] * 10.0          # observation entry = (ESI 1-2 waiting) / 10, end-of-hour census
        done = self.h >= self.episode_hours
        info = {"metrics": m, "terms": terms}
        if done:
            info["summary"] = self.sim.episode_summary()
            info["episode"] = self.episode_metrics()
            info["terms_mean"] = self.ep_terms / self.h
            info["return_mean"] = self.ep_return / self.h
            info["seeds"] = self.seeds.clone()
            info["invalid_actions"] = self.sim.invalid_actions.clone()
            if self.auto_reset:
                info["final_obs"] = obs
                obs = self.reset(self.seeds + self.seed_stride)
        return obs, reward, torch.full((self.B,), done, device=self.device, dtype=torch.bool), info

    def current_settings(self) -> torch.Tensor:
        return torch.stack([self.sim.settings[n] for n in self.head_names], 1)


class ConcatEnv:
    """Several HospitalEnvs (e.g. normal + surge scenarios) stepped as one batch.

    All parts share episode length and stage, so their clocks and masks agree.
    """

    def __init__(self, envs: list[HospitalEnv]):
        self.envs = envs
        e = envs[0]
        self.B = sum(x.B for x in envs)
        self.device, self.spec, self.head_names, self.head_sizes = e.device, e.spec, e.head_names, e.head_sizes
        self.defaults, self.enabled, self.obs_dim, self.sim_obs_dim = e.defaults, e.enabled, e.obs_dim, e.sim_obs_dim
        self.episode_hours = e.episode_hours
        self.slices, o = [], 0
        for x in envs:
            self.slices.append(slice(o, o + x.B))
            o += x.B

    def default_actions(self) -> dict:
        ds = [x.default_actions() for x in self.envs]
        return {n: torch.cat([d[n] for d in ds], 0) for n in self.head_names}

    def replace(self, i: int, env: HospitalEnv):
        """Swap one part for another of the same size (domain randomisation: a new ensemble member)."""
        assert env.B == self.envs[i].B and env.episode_hours == self.episode_hours
        self.envs[i] = env

    def set_weights(self, w: torch.Tensor):
        for x, s in zip(self.envs, self.slices):
            x.set_weights(w[s] if (isinstance(w, torch.Tensor) and w.dim() == 2) else w)

    def reset(self, seed=None):
        return torch.cat([x.reset(seed) for x in self.envs], 0)

    def observe(self):
        return torch.cat([x.observe() for x in self.envs], 0)

    def action_mask(self):
        ms = [x.action_mask() for x in self.envs]
        return {n: torch.cat([m[n] for m in ms], 0) for n in self.head_names}

    def mask_vector(self):
        return self.envs[0].mask_vector()

    def step(self, actions):
        outs = []
        for x, s in zip(self.envs, self.slices):
            a = {n: v[s] for n, v in actions.items()} if isinstance(actions, dict) else actions[s]
            outs.append(x.step(a))
        obs = torch.cat([o[0] for o in outs], 0)
        rew = torch.cat([o[1] for o in outs], 0)
        done = torch.cat([o[2] for o in outs], 0)
        info = {}
        for k in outs[0][3]:
            v0 = outs[0][3][k]
            if isinstance(v0, dict):
                info[k] = {kk: torch.cat([o[3][k][kk] for o in outs], 0) for kk in v0}
            else:
                info[k] = torch.cat([o[3][k] for o in outs], 0)
        return obs, rew, done, info

    def current_settings(self):
        return torch.cat([x.current_settings() for x in self.envs], 0)
