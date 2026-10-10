"""HospitalSim: batched, tensorised, time-stepped ED + ward simulation (contracts/sim_api.md).

One tick = 5 simulated minutes. All per-patient state lives in tensors of shape [B, P]
(B hospitals, P patient slots). The tick path contains no Python loop over patients or
hospitals; the only loops are over a handful of bay classes, provider pools and scanner types.
"""
from __future__ import annotations

import copy
import math

import torch

from . import rng
from .config import ScenarioConfig, load_scenario
from .layoutmodel import BAY_CLASSES, C_FAST, C_HALL, C_MAIN, C_PEDS, C_RESUS, RELOCATE_VARIANTS
from .viewer import ViewerMixin
from .interact import InteractMixin

# patient_state (contracts/enums.yaml)
S_WT, S_TRI, S_WB, S_WP, S_PROV, S_WTEST, S_TEST, S_WRES, S_BOARD, S_WARD, S_WALK, S_EXIT = range(12)
# patient_exit
X_NONE, X_DISCH, X_WARD, X_LWBS, X_TRANSFER, X_DIED, X_DIVERTED = range(7)
D_DISCHARGE, D_ADMIT, D_TRANSFER = 0, 1, 2
F_DET, F_ADMIT, F_FAST, F_PLAYED = 1, 2, 4, 8
N_XRAY, N_CT, N_LAB = 1, 2, 4

# random streams / per-patient columns
ST_ARR, ST_PAT, ST_ABS, ST_EQ, ST_TICK, ST_INIT = 1, 2, 3, 4, 5, 6
(C_ACU, C_COND, C_RESP, C_TRIN, C_AMB, C_AGE, C_PAYER, C_SEV, C_PAT, C_MIS, C_IMG, C_CT, C_LAB, C_TROUT, C_MCI,
 C_MISDIR) = range(16)
C_TRI_D, C_ENC_D, C_TREAT_D, C_LAB_D, C_PROC_D, C_REEVAL_D, C_LOS_D, C_QUAL, C_DERR, C_WADV, C_INITLOS = range(16, 27)
C_HAZ = 27
N_COLS = 29
INT_COLS = dict(pid=0, pseed=1, cond=2, mode=3, age=4, payer=5, tdisp=6, t_arr=7, needs=8)
I_PID, I_PSEED, I_COND, I_MODE, I_AGE, I_PAYER, I_TDISP, I_TARR, I_NEEDS = range(9)
N_INT = 9
FLT_COLS = dict(sev=0, patience=1, tri_dur=2, test_dur=6, dis_dur=7)
(F_SEV, F_PATIENCE, F_TRI, F_ENC, F_TREAT, F_LAB, F_PROC, F_REEVAL, F_LOS, F_QZ, F_DERR, F_WADV, F_THR_DET,
 F_THR_DIE) = range(14)
N_FLT = 14
EPS = 1e-3
LEG_TRI, LEG_WAIT, LEG_AMB, LEG_SCAN, LEG_WARD = 0, 1, 6, 11, 21
SCAN_TYPES = ["xray", "ct"]
IMPULSE_HEADS = ("bays_delta", "ward_beds_delta", "equipment_buy", "relocate", "headcount", "call_in")

SUM_METRICS = ["arrivals", "first_seen", "door_to_provider_sum_min", "lwbs", "diverted", "diversion_hours",
               "ed_departures", "ed_los_sum_min", "boarding_hours", "admissions", "treated", "deteriorations",
               "deaths", "adverse_events", "overtime_hours", "revenue", "cost_labor", "cost_fixed", "cost_variable",
               "cost_structural"]


# returned by step() after the contract metrics (additive; not in contracts/metrics.yaml):
#   waiting_patient_minutes = patient-minutes accrued this hour by patients not yet seen by a provider
EXTRA_METRICS = ["waiting_patient_minutes"]


class DistTable:
    """Inverse-CDF sampler for fixed / lognormal / exponential durations indexed by a small table."""

    def __init__(self, kinds, means, cvs, device):
        if not isinstance(kinds, (list, tuple)):
            kinds, means, cvs = [kinds], [means], [cvs]
        mu, sg = [], []
        for k, m, cv in zip(kinds, means, cvs):
            s2 = math.log(1.0 + cv * cv) if (k == "lognormal" and cv > 0) else 0.0
            sg.append(math.sqrt(s2))
            mu.append(math.log(max(m, 1e-9)) - 0.5 * s2)
        f = dict(device=device, dtype=torch.float32)
        self.mean = torch.tensor(means, **f)
        self.mu = torch.tensor(mu, **f)
        self.sig = torch.tensor(sg, **f)
        self.is_ln = torch.tensor([k == "lognormal" for k in kinds], device=device)
        self.is_exp = torch.tensor([k == "exponential" for k in kinds], device=device)
        self.any_ln = any(k == "lognormal" for k in kinds)
        self.any_exp = any(k == "exponential" for k in kinds)
        self.all_ln = all(k == "lognormal" for k in kinds)
        self.all_exp = all(k == "exponential" for k in kinds)

    def sample(self, u, idx=None):
        """u: uniform tensor; idx: long tensor of table rows (same shape) or None for row 0."""
        if idx is None:
            m, mu, sg = self.mean[0], self.mu[0], self.sig[0]
            if self.all_ln:
                return torch.exp(mu + sg * rng.normal_from_unit(u))
            if self.all_exp:
                return -m * torch.log1p(-u)
            return torch.zeros_like(u) + m
        m = self.mean[idx]
        if self.all_ln:
            return torch.exp(self.mu[idx] + self.sig[idx] * rng.normal_from_unit(u))
        if self.all_exp:
            return -m * torch.log1p(-u)
        out = m
        if self.any_ln:
            out = torch.where(self.is_ln[idx], torch.exp(self.mu[idx] + self.sig[idx] * rng.normal_from_unit(u)), out)
        if self.any_exp:
            out = torch.where(self.is_exp[idx], -m * torch.log1p(-u), out)
        return out


class HospitalSim(ViewerMixin, InteractMixin):
    def __init__(self, scenario: ScenarioConfig | str = "normal_week", batch_size: int = 1, device="cpu", seed: int = 0):
        if isinstance(scenario, str):
            scenario = load_scenario(scenario)
        self.scn = copy.copy(scenario)
        self.scn.events = [dict(e) for e in scenario.events]      # per-simulator schedule (inject_event appends here)
        self.cfg = scenario.P
        self.flags = scenario.flags
        self.B = int(batch_size)
        self.device = torch.device(device)
        self.enums = scenario.enums
        eng = scenario.engine
        self.tick_minutes = int(eng["tick_minutes"])
        self.ticks_per_step = int(eng["ticks_per_step"])
        self.P = int(self.cfg["pool_size"])
        self.K = int(eng["max_arrivals_per_tick"])
        self.record = self.B <= int(eng["event_log_max_batch"])
        self._seed_arg = seed
        self.start_day = int(eng.get("start_day", 0))
        self._build_static()
        self.reset(seed)

    # ======================================================================================
    # static tables
    # ======================================================================================
    def _build_static(self):
        c, dev, lm = self.cfg, self.device, self.scn.layout
        f32 = dict(device=dev, dtype=torch.float32)
        i64 = dict(device=dev, dtype=torch.long)
        self.dt = float(self.tick_minutes)
        self.tph = 60 // self.tick_minutes            # ticks per hour
        self.tpd = 24 * self.tph
        pad = lambda xs: torch.tensor([xs[0]] + list(xs), **f32)   # noqa: E731  index by acuity 1..5

        def cdf(pr):
            t = torch.tensor(pr, dtype=torch.float64).cumsum(0)
            return (t / t[-1])[:-1].to(dev, torch.float32).contiguous()

        self.acu_cdf = cdf(c["acuity_mix"])
        self.cond_cdf = cdf(c["cond_mix"])
        self.age_cdf = cdf(c["age_mix"])
        self.payer_cdf = cdf(c["payer_mix"])
        self.resp_idx = self.enums["condition_group"].index("respiratory")
        self.amb_share = pad(c["amb_share"])
        self.payer_mult = torch.tensor(c["payer_mult"], **f32)
        self.det_haz = pad(c["det_haz"]) / self.tph
        self.death_haz = pad(c["death_haz"]) / self.tph
        self.p_img, self.p_ct, self.p_lab = pad(c["p_imaging"]), pad(c["p_ct_given_imaging"]), pad(c["p_lab"])
        self.p_admit = pad(c["p_admit"])
        self.rev_ed, self.supply = pad(c["revenue_ed_visit"]), pad(c["supply_cost"])
        self.nurse_care = pad(c["nurse_care_min_per_hour"])
        dpad = lambda d: DistTable([d["kind"][0]] + d["kind"], [d["mean"][0]] + d["mean"], [d["cv"][0]] + d["cv"], dev)  # noqa: E731
        self.d_triage = dpad(c["triage_min"])
        self.d_enc = dpad(c["provider_initial_min"])
        self.d_reeval = dpad(c["provider_reeval_min"])
        self.d_treat = dpad(c["treatment_min"])
        pt = c["patience"]
        self.d_patience = DistTable([pt["kind"]] * 6, [pt["mean"][0]] + pt["mean"], [pt["cv"][0]] + pt["cv"], dev)
        self.d_los = DistTable(c["los"]["kind"], c["los"]["mean"], c["los"]["cv"], dev)
        self.d_lab = DistTable(c["lab"]["kind"], c["lab"]["mean"], c["lab"]["cv"], dev)
        eq = [c["equip"][t] for t in SCAN_TYPES]
        self.d_proc = DistTable([e["proc"]["kind"] for e in eq], [e["proc"]["mean"] for e in eq], [e["proc"]["cv"] for e in eq], dev)
        self.eq_result_delay = torch.tensor([e["result_delay"] for e in eq], **f32)
        self.eq_revenue = torch.tensor([e["revenue"] for e in eq], **f32)
        self.eq_var_cost = torch.tensor([e["var_cost"] for e in eq], **f32)
        self.eq_fail = torch.tensor([e["fail"] / self.tph for e in eq], **f32)
        self.eq_repair = torch.tensor([e["repair"] for e in eq], **f32)
        self.eq_units0 = [int(e["units"]) for e in eq]
        self.E = max(self.eq_units0) + int(self.scn.engine["structural_max_steps"])
        self.exp_service = pad(c["provider_initial_min"]["mean"])

        # ---- bays (index NB is a trash column)
        self.NB = lm.n_bays
        cls = list(lm.bay_cls) + [C_MAIN]
        self.bay_cls = torch.tensor(cls, **i64)
        self.bay_exists0 = torch.tensor([b["exists0"] for b in lm.bays] + [False], device=dev)
        self.bay_is = [(self.bay_cls == k) & (torch.arange(self.NB + 1, device=dev) < self.NB) for k in range(len(BAY_CLASSES))]
        self.cls_present = [bool(m.any()) for m in self.bay_is]
        hall_rank = torch.cumsum(self.bay_is[C_HALL].long(), 0) - 1
        self.hall_rank = torch.where(self.bay_is[C_HALL], hall_rank, torch.full_like(hall_rank, 1 << 30))
        self.bay_turn = torch.tensor(c["turnaround"], **f32)[self.bay_cls]
        self.bay_fixed = torch.tensor(c["bay_fixed"], **f32)[self.bay_cls]
        self.bay_fixed[self.NB] = 0.0
        self.hall_opts = torch.tensor(c["hall_opts"], **i64)
        self.n_main_slots = int(self.bay_is[C_MAIN].sum())
        self.legs_var = torch.tensor(lm.legs, **f32)                # [variants, 26] metres
        self.class_order = [k for k in (C_RESUS, C_PEDS, C_FAST, C_MAIN, C_HALL) if self.cls_present[k]]

        # ---- state lookup tables
        tab = lambda idx: torch.tensor([i in idx for i in range(12)], device=dev)   # noqa: E731
        self.tab_pre = tab((S_WT, S_TRI, S_WB, S_WP))
        self.tab_leave = tab((S_WT, S_WB, S_WP))
        self.tab_rule = tab((S_WB, S_WP, S_WRES, S_WTEST))
        self.tab_ed = tab(range(0, 9))
        dm = [1.0, 1.0, 1.0, 1.0] + [c["death_post_mult"]] * 5 + [0.0, c["death_post_mult"], 0.0]
        self.tab_death = torch.tensor(dm, **f32)
        self.arK = torch.arange(self.K, **i64)
        self.arP = torch.arange(self.P, **i64)
        self.arNB = torch.arange(self.NB + 1, **i64)
        self.arE = torch.arange(self.E, **i64)
        self.kdesc = (self.K - self.arK)
        self.pdesc = (self.P - self.arP).to(torch.float32)

        # ---- staffing tables
        self.prov_levels = torch.tensor(c["provider_levels"], **i64)
        self.rn_levels = torch.tensor(c["rn_levels"], **i64)
        self.tri_levels = torch.tensor(c["triage_levels"], **i64)
        self.agency_levels = torch.tensor(c["agency_levels"], **i64)
        self.max_md = int(max(c["provider_levels"])) + c["headcount_max_steps"] * abs(c["headcount_step"]["provider"]) + c["callin_max"]["provider"]
        self.max_rn = int(max(c["rn_levels"])) + c["headcount_max_steps"] * abs(c["headcount_step"]["rn"]) + c["callin_max"]["rn"] + max(c["agency_levels"])
        mixw = c["role_mix"]
        tot = sum(mixw.values()) or 1.0
        self.wage_md = sum(c["wage"][r] * w for r, w in mixw.items()) / tot
        self.wage_rn = c["wage"]["rn"]
        self.support_n = sum(c["support"].values())
        self.support_cost_h = sum(c["wage"][r] * n for r, n in c["support"].items()) * c["benefits_load"]
        self.ft_speed = 1.0 / max(0.1, c["productivity"].get("app", 1.0))
        self.callin_delay = max(1, int(math.ceil(c["callin_delay_min"] / self.dt)))
        self.callin_tab = torch.tensor([[0, 0], [1, 0], [2, 0], [0, 1], [1, 1]], **i64)   # [option] -> (rn, provider)
        self.adm_thr = torch.tensor(c["admission_cap_thr"], **f32)
        self.img_windows = c["imaging_windows"]
        self.shift_starts = [int(x) for x in self.scn.engine["shift_start_hours"]]

        # ---- priority rule coefficients: fcfs, acuity_first, acuity_with_aging, shortest_first
        self.rule_ac = torch.tensor([0.0, 1.0, 1.0, 0.0], **f32)
        self.rule_age = torch.tensor([0.0, 0.0, c["acuity_aging_levels_per_hour"], 0.0], **f32)
        self.rule_sh = torch.tensor([0.0, 0.0, 0.0, 1.0], **f32)

        # ---- action heads
        self.heads = self.scn.heads
        self.head_names = [h["name"] for h in self.heads]
        self.head_n = {h["name"]: len(h["options"]) for h in self.heads}
        self.head_default = {h["name"]: int(h["default"]) for h in self.heads}
        self.head_cadence = {h["name"]: h["cadence"] for h in self.heads}
        self._metric_names = list(self.scn.metric_defs.keys())
        self.wait_bins = int(self.scn.engine["wait_hist_bins"])
        self.los_bins = int(self.scn.engine["los_hist_bins"])
        self.dpm = int(self.scn.engine["days_per_month"])
        # structural delays in days
        self.delay_days = dict(bays=int(c["build_delay_days"]), ward=int(c["ward_bed_open_delay_days"]),
                               equip=int(c["install_delay_days"]), reloc=int(c["relocate_delay_days"]),
                               head=int(c["hire_delay_days"]))
        self.pend_slots = {k: int(v // self.dpm) + 2 for k, v in self.delay_days.items()}
        # reference scale for money features in the observation: default-roster labour per hour
        d = self.head_default
        self.cost_scale = float(
            (c["provider_levels"][d["md_day"]] * self.wage_md + c["rn_levels"][d["rn_day"]] * self.wage_rn) * c["benefits_load"]
            + self.support_cost_h) or 1.0
        # ---- constant tensors reused by the tick path
        B, P, NB = self.B, self.P, self.NB
        cst = lambda v, shape=(B, P), dt=torch.long: torch.full(shape, v, device=dev, dtype=dt)   # noqa: E731
        self._c_wb, self._c_wp = cst(S_WB, (B, self.K)), cst(S_WP, (B, self.K))
        self._c_walkin_state = cst(S_WT if self.flags["triage"] else S_WB, (B, self.K))
        self._c_wtest, self._c_wres, self._c_nb, self._c_inf = cst(S_WTEST), cst(S_WRES), cst(NB), cst(1 << 62)
        self._zf = torch.zeros((B, P), **f32)
        self._false_bp = torch.zeros((B, P), device=dev, dtype=torch.bool)
        self._true_bp = torch.ones((B, P), device=dev, dtype=torch.bool)
        self._c_nb_row = cst(NB, (B, NB + 1))
        self._arNB_row = self.arNB.unsqueeze(0).expand(B, -1).contiguous()
        self._eq_ctr = (torch.arange(2, device=dev).view(1, 2, 1) * 64 + self.arE.view(1, 1, -1))
        self._two_pools = bool(self.cls_present[C_FAST] and self.flags["bays"])
        self._has_type = [int(self.eq_units0[i] > 0) for i in range(2)]
        self._has_outage = any(e["type"] == "equipment_outage" for e in self.scn.events)
        self._inv_walk = 1.0 / c["walk_speed_m_per_min"]
        self._inv_transport = 1.0 / c["patient_transport_speed_m_per_min"]
        st_i = torch.arange(72, device=dev) // 6
        ac_i = (torch.arange(72, device=dev) % 6).clamp(min=1)
        self.haz_det = self.det_haz[ac_i] * self.tab_pre[st_i].float()
        self.haz_die = self.death_haz[ac_i] * self.tab_death[st_i]
        self._fat_g = c["fatigue_gain_per_busy_hour"] / self.tph
        self._fat_r = c["fatigue_recovery_per_idle_hour"] / self.tph
        self._err_base = c["baseline_error_events_per_patient_hour"] / self.tph
        self._obs_names = None
        self.obs_dim = len(self.obs_names())

    # ======================================================================================
    # reset
    # ======================================================================================
    def reset(self, seed=None, start_day: int | None = None) -> None:
        """start_day (additive): calendar day of tick 0 (0 = a Monday at the scenario's start month); shifts the
        weekday and seasonal arrival profiles only. Default: engine setting `start_day` (0)."""
        B, P, dev = self.B, self.P, self.device
        if start_day is not None:
            self.start_day = int(start_day)
        if seed is None:
            seed = self._seed_arg
        self._seed_arg = seed
        self._reset_count = getattr(self, "_reset_count", 0) + 1
        if isinstance(seed, torch.Tensor):
            seeds = seed.to(dev, torch.long).reshape(-1).expand(B).clone()
        else:
            seeds = int(seed) + torch.arange(B, device=dev, dtype=torch.long)
        self.seeds = seeds
        self.seedkey = rng.mix(seeds * rng.GOLD + 0x5851F42D)
        self._tick = 0
        z = lambda dt=torch.long, fill=0: torch.full((B, P), fill, device=dev, dtype=dt)   # noqa: E731
        zf = lambda: torch.zeros((B, P), device=dev, dtype=torch.float32)                  # noqa: E731
        p = {}
        p["active"] = torch.zeros((B, P), device=dev, dtype=torch.bool)
        self.ps = torch.zeros((B, P, N_INT), device=dev, dtype=torch.long)       # static ints, written at arrival
        self.pd = torch.zeros((B, P, N_FLT), device=dev, dtype=torch.float32)    # static draws, written at arrival
        for n, i in INT_COLS.items():
            p[n] = self.ps[:, :, i]
        for n, i in FLT_COLS.items():
            p[n] = self.pd[:, :, i]
        for n in ["phase", "next_state", "flags", "exit", "t_state"]:
            p[n] = z()
        p["acu"], p["acu_q"] = z(fill=3), z(fill=3)
        p["state"] = z(fill=S_EXIT)
        p["disp"], p["t_seen"], p["eq"], p["t_board"] = z(fill=-1), z(fill=-1), z(fill=-1), z(fill=-1)
        p["bay"] = z(fill=self.NB)
        for n in ["timer", "timer2", "walk_total", "treat_left", "res_left", "enc_dur", "enc_q", "h_det", "h_die"]:
            p[n] = zf()
        p["hold"] = torch.zeros((B, P), device=dev, dtype=torch.bool)
        self.p = p
        zb = lambda dt=torch.long, fill=0: torch.full((B,), fill, device=dev, dtype=dt)    # noqa: E731
        self.next_ord = zb()
        self.exits = torch.zeros((B, 7), device=dev, dtype=torch.long)
        self.entered = zb()
        self.pool_overflow = zb()
        self.invalid_actions = zb()
        # resources
        self.bay_busy = torch.zeros((B, self.NB + 1), device=dev, dtype=torch.bool)
        self.bay_clean = torch.zeros((B, self.NB + 1), device=dev, dtype=torch.float32)
        self.bay_exists = self.bay_exists0.unsqueeze(0).repeat(B, 1)
        self.bay_open = self.bay_exists.clone()
        self.ward_cap = zb(fill=int(self.cfg["ward_cap0"]))
        self.eq_units = torch.tensor(self.eq_units0, device=dev, dtype=torch.long).unsqueeze(0).repeat(B, 1)
        self.eq_down = torch.zeros((B, 2, self.E), device=dev, dtype=torch.float32)
        self.eq_avail = self.eq_units.clone()
        self.headcount_off = zb()
        self.reloc = zb()
        self.reloc_moving = zb()
        self.layout_version = zb(fill=int(self.scn.layout.base.get("version", 1) or 1))
        self.legs = self.legs_var[self.reloc]
        self.pend = {k: dict(due=torch.full((B, s), -1, device=dev, dtype=torch.long),
                             val=torch.zeros((B, s), device=dev, dtype=torch.long)) for k, s in self.pend_slots.items()}
        self.pend_bays_n = zb()
        self.pend_eq_n = torch.zeros((B, 2), device=dev, dtype=torch.long)
        self.pend_ward_n = zb()
        # staff
        zfb = lambda: torch.zeros((B,), device=dev, dtype=torch.float32)                   # noqa: E731
        self.md_sched, self.rn_sched, self.md_abs, self.rn_abs = zb(), zb(), zb(), zb()
        self.md_eff, self.rn_eff, self.tri_n, self.agency_n = zb(fill=1), zb(fill=1), zb(fill=1), zb()
        self.extra_md, self.extra_rn, self.called_md, self.called_rn = zb(), zb(), zb(), zb()
        self.callin_ring = torch.zeros((B, 2, self.callin_delay + 1), device=dev, dtype=torch.long)
        self.fat_md, self.fat_rn = zfb(), zfb()
        self.speed_md = torch.ones((B,), device=dev)
        self.speed_rn = torch.ones((B,), device=dev)
        self.ward_speed = torch.ones((B,), device=dev)
        self.rn_load = zfb()
        self.md_cap = [zb(fill=1), zb()]
        self._shift_idx = -1
        # settings
        self.settings = {n: zb(fill=self.head_default[n]) for n in self.head_names}
        # metrics
        self.acc = {k: zfb() for k in SUM_METRICS}
        self.acc["md_busy"], self.acc["md_on"], self.acc["rn_load"] = zfb(), zfb(), zfb()
        self.acc["waiting_patient_minutes"] = zfb()
        zdb = lambda: torch.zeros((B,), device=dev, dtype=torch.float64)                   # noqa: E731  (long episodes)
        self.ep = {k: zdb() for k in SUM_METRICS + EXTRA_METRICS}
        for k in ["ed_census", "waiting_count", "boarding_count", "bay_occupancy", "ward_occupancy", "md_utilization",
                  "rn_utilization", "staff_on_shift", "fatigue_mean"]:
            self.ep[k] = zdb()
        self.ep_hours = 0
        i32 = torch.int32
        self.wait_hist_cur = torch.zeros((B, self.wait_bins), device=dev, dtype=i32)
        self.wait_hist_24 = torch.zeros((B, self.wait_bins), device=dev, dtype=i32)
        self.wait_hist_ep = torch.zeros((B, self.wait_bins), device=dev, dtype=i32)
        self.wait_ring = torch.zeros((B, 24, self.wait_bins), device=dev, dtype=torch.int16)
        self.los_hist_cur = torch.zeros((B, self.los_bins), device=dev, dtype=i32)
        self.los_hist_24 = torch.zeros((B, self.los_bins), device=dev, dtype=i32)
        self.los_hist_ep = torch.zeros((B, self.los_bins), device=dev, dtype=i32)
        self.los_ring = torch.zeros((B, 24, self.los_bins), device=dev, dtype=torch.int16)
        self.ring_arr = torch.zeros((B, 24), device=dev, dtype=torch.float32)
        self.ring_lwbs = torch.zeros((B, 24), device=dev, dtype=torch.float32)
        self.ring_margin = torch.zeros((B, 24), device=dev, dtype=torch.float32)
        self._last = {k: zfb() for k in self._metric_names + EXTRA_METRICS}
        self._arr_cdf = torch.zeros((self.K,), device=dev, dtype=torch.float32)
        self._ev = dict(arr=1.0, resp=0.0, abs_rn=1.0, abs_md=1.0, los=1.0, mci_share=0.0)
        self._mci_cdf = None
        self.los_mult = 1.0
        # python-side logs (only meaningful for small batches)
        self._events = [[] for _ in range(B)] if self.record else None
        self._decisions = [[] for _ in range(B)] if self.record else None
        self._played = [dict() for _ in range(B)]
        self._viz_staff = [dict() for _ in range(min(B, 64))]
        self._viz_ward = [dict() for _ in range(min(B, 64))]
        self._viz_scan = [dict() for _ in range(min(B, 64))]
        self._ev_started = set()
        self._rate = torch.full((B, 12), self.dt, device=dev)
        self._treat_dec = self.dt
        self._q_base = torch.full((B,), float(self.cfg["encounter_quality_base"]), device=dev)
        self._any_played = False
        self._deferred = [dict() for _ in range(B)]
        self._gone = [dict() for _ in range(B)] if self.record else []
        self._deferred_n = 0
        self._callin_pending, self._callin_active = 0, False
        self.ft_open = torch.ones((B,), device=dev, dtype=torch.bool)
        self.ct_extra_staffed = torch.ones((B,), device=dev, dtype=torch.bool)
        if self.flags["ward"] and self.cfg["ward_initial_occupancy"] > 0:
            self._init_ward()
        self.initial_census = self.entered.clone()
        self._hour_start()

    @property
    def t(self):
        return torch.full((self.B,), self._tick, device=self.device, dtype=torch.long)

    def _init_ward(self):
        """Warm start: fill the ward pool to the catalog's initial occupancy with patients whose
        remaining stay is a uniform fraction of a fresh length-of-stay draw (assumed)."""
        p, B, dev = self.p, self.B, self.device
        n = int(round(self.cfg["ward_initial_occupancy"] * self.cfg["ward_cap0"]))
        n = max(0, min(n, self.P))
        if n == 0:
            return
        ords = torch.arange(n, device=dev, dtype=torch.long).unsqueeze(0).expand(B, n)
        pk = rng.key(self.seedkey.unsqueeze(1), ST_INIT, ords)
        a_int, a_flt, _, _ = self._attrs(pk, ords, 0)
        # ward patients skew to higher acuity: acuity weighted by admission probability
        w = torch.tensor(self.cfg["acuity_mix"], device=dev) * self.p_admit[1:]
        cdf = (w.cumsum(0) / w.sum())[:-1].contiguous()
        acu = torch.bucketize(rng.unit(pk, C_ACU), cdf) + 1
        a_int[:, :, I_MODE] = 0
        a_int[:, :, I_TDISP] = D_ADMIT
        sl = slice(0, n)
        self.ps[:, sl] = a_int
        self.pd[:, sl] = a_flt
        p["active"][:, sl] = True
        p["acu"][:, sl] = acu
        p["acu_q"][:, sl] = acu
        p["state"][:, sl] = S_WARD
        p["disp"][:, sl] = D_ADMIT
        p["flags"][:, sl] = F_ADMIT
        p["t_seen"][:, sl] = 0
        # mean residual life of a stay in progress is mean * (1 + cv^2) / 2
        p["timer"][:, sl] = a_flt[:, :, F_LOS] * rng.unit(pk, C_INITLOS) * (1.0 + self.cfg["los"]["cv"] ** 2)
        self.next_ord += n
        self.entered += n

    # ======================================================================================
    # specs
    # ======================================================================================
    def metric_names(self) -> list[str]:
        return list(self._metric_names)

    def action_spec(self) -> list[dict]:
        c = self.cfg
        vals = dict(
            priority_rule=[0, 1, 2, 3], overflow_bays=list(c["hall_opts"]), divert=[0, 1],
            call_in=[dict(rn=int(a), provider=int(b)) for a, b in self.callin_tab.tolist()],
            fast_track=[0, 1], provider_split=["favor_new", "balanced", "favor_dispositions"],
            md_day=c["provider_levels"], md_evening=c["provider_levels"], md_night=c["provider_levels"],
            rn_day=c["rn_levels"], rn_evening=c["rn_levels"], rn_night=c["rn_levels"],
            triage_nurses=[min(x, self.scn.layout.n_triage_rooms) for x in c["triage_levels"]],
            admission_cap=c["admission_cap_thr"], discharge_push=[1.0, c["discharge_push_los_factor"]],
            agency_contract=c["agency_levels"], imaging_hours=c["imaging_windows"],
            bays_delta=[-c["bay_step"], 0, c["bay_step"]], ward_beds_delta=[-c["ward_step"], 0, c["ward_step"]],
            equipment_buy=[None, "ct", "xray"], relocate=list(RELOCATE_VARIANTS),
            headcount=[dict(provider=-c["headcount_step"]["provider"], rn=-c["headcount_step"]["rn"]), dict(provider=0, rn=0),
                       dict(provider=c["headcount_step"]["provider"], rn=c["headcount_step"]["rn"])])
        notes = dict(
            relocate="Implemented as geometry: the zone's rooms move, walking distances are recomputed, the zone runs "
                     "reduced/closed during the move. No triage-initiated imaging protocol is modelled, so "
                     "triage_next_to_imaging only changes the waiting-room-to-triage walk.",
            bays_delta=f"add: built after {self.delay_days['bays']} days; remove: immediate",
            ward_beds_delta=f"add: opens after {self.delay_days['ward']} days; remove: immediate",
            equipment_buy=f"installed after {self.delay_days['equip']} days",
            headcount=f"grow: after {self.delay_days['head']} days; reduce: immediate")
        out = []
        for h in self.heads:
            d = dict(name=h["name"], cadence=h["cadence"], options=list(h["options"]), default=int(h["default"]),
                     desc=h["desc"], values=list(vals[h["name"]]), implemented=True)
            if h["name"] in notes:
                d["note"] = notes[h["name"]]
            out.append(d)
        return out

    def default_actions(self) -> dict:
        return {n: torch.full((self.B,), self.head_default[n], device=self.device, dtype=torch.long) for n in self.head_names}

    def _boundary(self, cadence: str, hour: int) -> bool:
        if cadence == "hourly":
            return True
        if cadence == "daily":
            return hour % 24 == 0
        if cadence == "weekly":
            return hour % 168 == 0
        return hour % 24 == 0 and (hour // 24) % self.dpm == 0

    def action_mask(self) -> dict:
        hour = self._tick // self.tph
        on_hour = self._tick % self.tph == 0
        return {n: torch.full((self.B,), bool(on_hour and self._boundary(self.head_cadence[n], hour)), device=self.device,
                              dtype=torch.bool) for n in self.head_names}

    # ======================================================================================
    # actions
    # ======================================================================================
    def _apply_actions(self, actions: dict):
        hour = self._tick // self.tph
        day = hour // 24
        dev = self.device
        c = self.cfg
        struct_cost = torch.zeros((self.B,), device=dev)
        changed_struct = torch.zeros((self.B,), device=dev, dtype=torch.bool)
        for name, val in actions.items():
            if name not in self.head_n:
                raise KeyError(f"unknown action head '{name}'")
            if not isinstance(val, torch.Tensor):
                val = torch.as_tensor(val)
            val = val.to(dev, torch.long).reshape(-1).expand(self.B)
            cur = self.settings[name]
            in_range = (val >= 0) & (val < self.head_n[name])
            at_boundary = self._boundary(self.head_cadence[name], hour)
            if not at_boundary:
                self.invalid_actions += (~in_range | (val != cur)).long() if name not in IMPULSE_HEADS else \
                    (~in_range | (val != self.head_default[name])).long()
                continue
            ok = in_range
            v = torch.where(ok, val, cur)
            # ---- rule checks for impulse heads
            if name == "call_in":
                req = self.callin_tab[v.clamp(0, 4)]
                over = ((self.called_rn + req[:, 0]) > c["callin_max"]["rn"]) | ((self.called_md + req[:, 1]) > c["callin_max"]["provider"])
                ok = ok & ~over
                req = torch.where(ok.unsqueeze(1), req, torch.zeros_like(req))
                slot = (self._tick + self.callin_delay) % (self.callin_delay + 1)
                self.callin_ring[:, 0, slot] += req[:, 0]
                self.callin_ring[:, 1, slot] += req[:, 1]
                self.called_rn += req[:, 0]
                self.called_md += req[:, 1]
                if bool((req.sum(1) > 0).any()):
                    self._callin_pending, self._callin_active = self.callin_delay + 1, True
                v = torch.where(ok, v, torch.zeros_like(v))
            elif name == "bays_delta":
                n_main = (self.bay_exists & self.bay_is[C_MAIN]).sum(1)
                rem, add = ok & (v == 0), ok & (v == 2)
                bad = (rem & (n_main - c["bay_step"] < c["min_main_bays"])) | \
                      (add & (n_main + self.pend_bays_n + c["bay_step"] > self.n_main_slots))
                ok = ok & ~bad
                rem, add = rem & ~bad, add & ~bad
                em = self.bay_exists & self.bay_is[C_MAIN]
                r_end = torch.flip(torch.cumsum(torch.flip(em.long(), [1]), 1), [1]) - 1
                self.bay_exists = self.bay_exists & ~(em & (r_end < c["bay_step"]) & rem.unsqueeze(1))
                self._schedule("bays", add, torch.ones_like(v), day)
                self.pend_bays_n += add.long() * c["bay_step"]
                struct_cost += rem.float() * c["bay_step"] * c["bay_close_cost"] + add.float() * c["bay_step"] * c["bay_build_cost"]
                changed_struct |= rem
                v = torch.where(ok, v, torch.ones_like(v))
            elif name == "ward_beds_delta":
                rem, add = ok & (v == 0), ok & (v == 2)
                bad = (rem & (self.ward_cap - c["ward_step"] < c["min_ward_beds"])) | \
                      (add & (self.ward_cap + self.pend_ward_n + c["ward_step"] > c["ward_cap_max"]))
                ok = ok & ~bad
                rem, add = rem & ~bad, add & ~bad
                self.ward_cap = self.ward_cap - rem.long() * c["ward_step"]
                self._schedule("ward", add, torch.ones_like(v), day)
                self.pend_ward_n += add.long() * c["ward_step"]
                struct_cost += add.float() * c["ward_step"] * c["ward_bed_open_cost"]
                changed_struct |= rem
                v = torch.where(ok, v, torch.ones_like(v))
            elif name == "equipment_buy":
                ti = (v == 1).long()          # option 1 = ct (scanner type 1), option 2 = xray (type 0)
                buy = ok & (v > 0)
                tot = (self.eq_units + self.pend_eq_n).gather(1, ti.unsqueeze(1)).squeeze(1)
                bad = buy & (tot + 1 > self.E)
                ok = ok & ~bad
                buy = buy & ~bad
                self._schedule("equip", buy, ti, day)
                self.pend_eq_n.scatter_add_(1, ti.unsqueeze(1), buy.long().unsqueeze(1))
                cost = torch.tensor([c["equip"]["xray"]["purchase"], c["equip"]["ct"]["purchase"]], device=dev)[ti]
                struct_cost += buy.float() * cost
                v = torch.where(ok, v, torch.zeros_like(v))
            elif name == "relocate":
                mv = ok & (v > 0)
                bad = mv & ((self.reloc_moving > 0) | (self.reloc == v))
                ok = ok & ~bad
                mv = mv & ~bad
                self._schedule("reloc", mv, v, day)
                self.reloc_moving = torch.where(mv, v, self.reloc_moving)
                struct_cost += mv.float() * c["relocate_cost"]
                v = torch.where(ok, v, torch.zeros_like(v))
            elif name == "headcount":
                red, grow = ok & (v == 0), ok & (v == 2)
                pend_h = (self.pend["head"]["due"] >= 0).sum(1)
                hmax = c["headcount_max_steps"]
                bad = (red & (self.headcount_off <= -hmax)) | (grow & (self.headcount_off + pend_h >= hmax))
                ok = ok & ~bad
                red, grow = red & ~bad, grow & ~bad
                self.headcount_off = self.headcount_off - red.long()
                self._schedule("head", grow, torch.ones_like(v), day)
                n_people = 3 * (c["headcount_step"]["provider"] + c["headcount_step"]["rn"])
                struct_cost += (red | grow).float() * n_people * c["hire_cost_per_head"]
                v = torch.where(ok, v, torch.ones_like(v))
            self.invalid_actions += (~ok).long()
            if self.record:
                ch = (v != cur) if name not in IMPULSE_HEADS else (ok & (v != self.head_default[name]))
                if bool(ch.any()):
                    self._log_decisions(name, cur, v, ch)
            self.settings[name] = v
        self.acc["cost_structural"] += struct_cost
        if bool(changed_struct.any()):
            self.layout_version += changed_struct.long()

    def _schedule(self, kind, mask, val, day):
        pd = self.pend[kind]
        slot = (day // self.dpm) % pd["due"].shape[1]
        pd["due"][:, slot] = torch.where(mask, torch.full_like(val, day + self.delay_days[kind]), pd["due"][:, slot])
        pd["val"][:, slot] = torch.where(mask, val, pd["val"][:, slot])

    def _complete_structural(self, day):
        c = self.cfg
        any_change = torch.zeros((self.B,), device=self.device, dtype=torch.bool)
        for kind, pd in self.pend.items():
            if not bool((pd["due"] >= 0).any()):
                continue
            for s in range(pd["due"].shape[1]):
                m = (pd["due"][:, s] >= 0) & (pd["due"][:, s] <= day)
                if not bool(m.any()):
                    continue
                val = pd["val"][:, s]
                if kind == "bays":
                    freem = (~self.bay_exists) & self.bay_is[C_MAIN]
                    r = torch.cumsum(freem.long(), 1) - 1
                    self.bay_exists = self.bay_exists | (freem & (r < c["bay_step"]) & m.unsqueeze(1))
                    self.pend_bays_n -= m.long() * c["bay_step"]
                elif kind == "ward":
                    self.ward_cap = self.ward_cap + m.long() * c["ward_step"]
                    self.pend_ward_n -= m.long() * c["ward_step"]
                elif kind == "equip":
                    self.eq_units.scatter_add_(1, val.unsqueeze(1), m.long().unsqueeze(1))
                    self.pend_eq_n.scatter_add_(1, val.unsqueeze(1), -m.long().unsqueeze(1))
                elif kind == "reloc":
                    self.reloc = torch.where(m, val, self.reloc)
                    self.reloc_moving = torch.where(m, torch.zeros_like(val), self.reloc_moving)
                    self.legs = self.legs_var[self.reloc]
                elif kind == "head":
                    self.headcount_off = self.headcount_off + m.long()
                pd["due"][:, s] = torch.where(m, torch.full_like(val, -1), pd["due"][:, s])
                any_change |= m
                if self.record:
                    for b in torch.nonzero(m).flatten().tolist():
                        self._events[b].append(dict(t=self._tick, kind="structural_done", text=f"Structural change completed: {kind}", entity=None))
        self.layout_version += any_change.long()

    # ======================================================================================
    # hour boundary
    # ======================================================================================
    def _scenario_state(self, hour):
        """Exogenous scenario events active at this hour (python, once per simulated hour)."""
        ev = dict(arr=1.0, resp=0.0, abs_rn=1.0, abs_md=1.0, los=1.0, mci_rate=0.0)
        mci_mix = None
        for i, e in enumerate(self.scn.events):
            start = int(e.get("start_day", 0)) * 24 + int(e.get("start_hour", 0))
            ty = e["type"]
            if ty == "mass_casualty":
                dur_h = max(1.0, float(e["window_min"]) / 60.0)
            elif ty == "equipment_outage":
                dur_h = float(e["duration_hours"])
            else:
                dur_h = float(e["duration_days"]) * 24.0
            rep = e.get("repeat_every_days")
            h = hour
            if rep and hour >= start:
                h = start + (hour - start) % int(float(rep) * 24)
            on = start <= h < start + dur_h
            if on and h == start and (i, hour) not in self._ev_started:
                self._ev_started.add((i, hour))
                if self.record:
                    for b in range(self.B):
                        self._events[b].append(dict(t=self._tick, kind="scenario", text=f"Scenario event started: {ty}", entity=None))
                if ty == "equipment_outage":
                    ti = SCAN_TYPES.index(e["equipment"]) if e["equipment"] in SCAN_TYPES else None
                    if ti is not None:
                        k = max(0, min(int(e["units_down"]), self.E))
                        self.eq_down[:, ti, :k] = torch.clamp(self.eq_down[:, ti, :k], min=dur_h * 60.0)
            if not on:
                continue
            if ty == "flu_wave":
                ev["arr"] *= float(e["arrival_multiplier"])
                ev["resp"] += float(e["respiratory_share_uplift"])
                ev["abs_rn"] *= float(e["staff_absence_multiplier"])
                ev["abs_md"] *= float(e["staff_absence_multiplier"])
            elif ty == "staff_callouts":
                roles = e.get("roles") or ["rn", "provider"]
                if "rn" in roles:
                    ev["abs_rn"] *= float(e["absence_multiplier"])
                if "provider" in roles:
                    ev["abs_md"] *= float(e["absence_multiplier"])
            elif ty == "discharge_delay":
                ev["los"] *= float(e["inpatient_los_multiplier"])
            elif ty == "mass_casualty":
                ev["mci_rate"] += float(e["extra_patients"]) * self.cfg["size_ratio"] / (dur_h * self.tph)
                mci_mix = e["acuity_mix"]
        return ev, mci_mix

    def _hour_start(self):
        """Runs at the first tick of every simulated hour, after actions were applied."""
        c, dev = self.cfg, self.device
        hour = self._tick // self.tph
        hod, day = hour % 24, hour // 24
        if hod == 0 and self._tick > 0:
            self._complete_structural(day)
        ev, mci_mix = self._scenario_state(hour)
        # ---- arrival rate for this hour (same for the whole batch: exogenous, scenario-level)
        cal = day + self.start_day
        month = (int(self.scn.engine["start_month"]) + int(cal // 30.4375)) % 12
        lam = c["arrivals_per_day"] / self.tpd * c["hour_prof"][hod] * c["dow_prof"][cal % 7] * c["month_prof"][month] * ev["arr"]
        lam_tot = lam + ev["mci_rate"]
        ev["mci_share"] = ev["mci_rate"] / lam_tot if lam_tot > 0 else 0.0
        ks = torch.arange(self.K, dtype=torch.float64)
        logp = -lam_tot + ks * math.log(max(lam_tot, 1e-12)) - torch.lgamma(ks + 1.0)
        self._arr_cdf = torch.exp(logp).cumsum(0).to(dev, torch.float32)
        self._lam = lam_tot
        if mci_mix is not None:
            t = torch.tensor(mci_mix, dtype=torch.float64).cumsum(0)
            self._mci_cdf = (t / t[-1])[:-1].to(dev, torch.float32).contiguous()
        self._ev = ev
        self.los_mult = ev["los"]
        s = self.settings
        # ---- shift
        st = self.shift_starts
        shift = 0 if st[0] <= hod < st[1] else (1 if st[1] <= hod < st[2] else 2)
        shift_ord = (hour + (24 - st[0])) // 8
        new_shift = shift_ord != self._shift_idx
        if new_shift:
            self._shift_idx = shift_ord
            self.extra_md.zero_(), self.extra_rn.zero_(), self.called_md.zero_(), self.called_rn.zero_()
            self.callin_ring.zero_()
            self._callin_pending, self._callin_active = 0, False
            self.fat_md = self.fat_md * c["fatigue_shift_carryover"]
            self.fat_rn = self.fat_rn * c["fatigue_shift_carryover"]
        md_lvl = s[("md_day", "md_evening", "md_night")[shift]]
        rn_lvl = s[("rn_day", "rn_evening", "rn_night")[shift]]
        if c["fixed_servers"]:
            self.md_sched = torch.full_like(self.md_sched, c["fixed_servers"])
            self.rn_sched = self.rn_levels[rn_lvl]
        else:
            self.md_sched = (self.prov_levels[md_lvl] + self.headcount_off * c["headcount_step"]["provider"]).clamp(min=1)
            self.rn_sched = (self.rn_levels[rn_lvl] + self.headcount_off * c["headcount_step"]["rn"]).clamp(min=1)
        if self.flags["absences"]:
            sk = rng.key(self.seedkey, ST_ABS, shift_ord)
            u_md = rng.unit(rng.key(sk.unsqueeze(1), 11, torch.arange(self.max_md, device=dev)), 0)
            u_rn = rng.unit(rng.key(sk.unsqueeze(1), 12, torch.arange(self.max_rn, device=dev)), 0)
            am = torch.arange(self.max_md, device=dev).unsqueeze(0) < self.md_sched.unsqueeze(1)
            ar = torch.arange(self.max_rn, device=dev).unsqueeze(0) < self.rn_sched.unsqueeze(1)
            md_abs = ((u_md < c["absence_rate"] * ev["abs_md"]) & am).sum(1)
            rn_abs = ((u_rn < c["absence_rate"] * ev["abs_rn"]) & ar).sum(1)
            if self.record and new_shift:
                for b in torch.nonzero((md_abs + rn_abs) > 0).flatten().tolist():
                    self._events[b].append(dict(t=self._tick, kind="callout", entity=None,
                                                text=f"Call-outs this shift: {int(rn_abs[b])} nurses, {int(md_abs[b])} providers"))
            self.md_abs, self.rn_abs = md_abs, rn_abs
        self.agency_n = self.agency_levels[s["agency_contract"]]
        self.tri_n = torch.clamp(self.tri_levels[s["triage_nurses"]], max=self.scn.layout.n_triage_rooms)
        if c["relocate_reduced_triage_stations"] >= 0:
            self.tri_n = torch.where(self.reloc_moving == 1, torch.clamp(self.tri_n, max=int(c["relocate_reduced_triage_stations"])), self.tri_n)
        ft_open = (s["fast_track"] == 1) & (self.reloc_moving != 2)
        self.ft_open = ft_open
        self._staff_update()
        # ---- bay availability
        hall_n = self.hall_opts[s["overflow_bays"]]
        op = self.bay_exists.clone()
        if self.cls_present[C_HALL]:
            op = op & ~(self.bay_is[C_HALL] & (self.hall_rank.unsqueeze(0) >= hall_n.unsqueeze(1)))
        if self.cls_present[C_FAST]:
            op = op & ~(self.bay_is[C_FAST] & ~ft_open.unsqueeze(1))
        self.bay_open = op
        # ---- scanner staffing window (CT units beyond the always-staffed ones)
        w0, w1 = zip(*self.img_windows)
        w0 = torch.tensor(w0, device=dev)[s["imaging_hours"]]
        w1 = torch.tensor(w1, device=dev)[s["imaging_hours"]]
        self.ct_extra_staffed = (w0 <= hod) & (hod < w1)
        self._eq_update()
        self.ward_speed = 1.0 + (s["discharge_push"] == 1).float() * (1.0 / c["discharge_push_los_factor"] - 1.0)
        self.cap_thr = self.adm_thr[s["admission_cap"]]
        self.divert_on = s["divert"] == 1
        self._divert_h = self.divert_on.float() / self.tph
        self._rate[:, S_WARD] = self.dt * self.ward_speed
        self._fatigue_rates()
        self._pregen_arrivals()
        rule = s["priority_rule"]
        self.k_ac, self.k_age, self.k_sh = self.rule_ac[rule].unsqueeze(1), self.rule_age[rule].unsqueeze(1), self.rule_sh[rule].unsqueeze(1)
        # ---- hourly costs known at the start of the hour
        ben, ot, ag = c["benefits_load"], c["overtime_multiplier"], c["agency_premium_multiplier"]
        md_paid = (self.md_sched - self.md_abs).clamp(min=0).float()
        rn_paid = (self.rn_sched - self.rn_abs).clamp(min=0).float() + self.tri_n.float()
        extra_ct = torch.where(self.ct_extra_staffed, (self.eq_units[:, 1] - c["units_always_staffed"]).clamp(min=0), torch.zeros_like(self.tri_n)).float()
        labor = md_paid * self.wage_md * ben + rn_paid * self.wage_rn * ben + self.support_cost_h \
            + self.agency_n.float() * self.wage_rn * ag \
            + extra_ct * c["second_imaging_unit_tech"] * c["wage"]["imaging_tech"] * ben \
            + (s["discharge_push"] == 1).float() * c["discharge_push_cost_per_hour"]
        self.acc["cost_labor"] += labor
        self._ot_rate_md, self._ot_rate_rn = self.wage_md * ot, self.wage_rn * ot
        eqc = c["equip"]
        fixed = (self.bay_open.float() * self.bay_fixed.unsqueeze(0)).sum(1) + self.tri_n.float() * c["triage_fixed"] \
            + self.ward_cap.float() * c["ward_bed_fixed"] + c["other_fixed"] \
            + self.eq_units[:, 0].float() * (eqc["xray"]["maint_h"] + eqc["xray"]["room_fixed"]) \
            + self.eq_units[:, 1].float() * (eqc["ct"]["maint_h"] + eqc["ct"]["room_fixed"])
        self.acc["cost_fixed"] += fixed

    def _staff_update(self):
        c = self.cfg
        self.md_eff = (self.md_sched - self.md_abs).clamp(min=0) + self.extra_md
        self.rn_eff = (self.rn_sched - self.rn_abs).clamp(min=0) + self.extra_rn + self.agency_n
        if self.cls_present[C_FAST] and self.flags["bays"]:
            ft = torch.minimum(torch.full_like(self.md_eff, c["ft_dedicated"]["provider"]), (self.md_eff - 1).clamp(min=0))
            ft = torch.where(self.ft_open, ft, torch.zeros_like(ft))
        else:
            ft = torch.zeros_like(self.md_eff)
        self.md_cap = [self.md_eff - ft, ft]
        self.bay_budget_cap = torch.floor(self.rn_eff.float() * c["rn_patients_per_nurse_max"]).long()

    def _eq_update(self):
        up = (self.eq_down <= 0) & (self.arE.view(1, 1, -1) < self.eq_units.unsqueeze(2))
        staffed_ct = torch.where(self.ct_extra_staffed, torch.full_like(self.eq_units[:, 1], self.E),
                                 torch.full_like(self.eq_units[:, 1], self.cfg["units_always_staffed"]))
        n_up = up.sum(2)
        self.eq_avail = torch.stack([n_up[:, 0], torch.minimum(n_up[:, 1], staffed_ct)], 1)

    # ======================================================================================
    # helpers
    # ======================================================================================
    def _attrs(self, pk, ords, t):
        """Patient attributes and service-time draws from the per-patient key (exogenous; never
        depends on actions). Returns stacked static ints, stacked static floats, acuity, triage acuity."""
        c, ev = self.cfg, self._ev
        U = rng.units(pk, N_COLS)
        u = lambda col: U[..., col]   # noqa: E731
        acu = torch.bucketize(u(C_ACU).contiguous(), self.acu_cdf) + 1
        if ev["mci_share"] > 0 and self._mci_cdf is not None:
            acu = torch.where(u(C_MCI) < ev["mci_share"], torch.bucketize(u(C_ACU).contiguous(), self._mci_cdf) + 1, acu)
        cond = torch.bucketize(u(C_COND).contiguous(), self.cond_cdf)
        if ev["resp"] > 0:
            cond = cond.masked_fill(u(C_RESP) < ev["resp"], self.resp_idx)
        mode = (u(C_AMB) < self.amb_share[acu]).long().masked_fill(u(C_TRIN) < c["p_transfer_in"], 2)
        us = u(C_SEV)
        sev = ((5 - acu).float() + us) / 5.0
        tdisp = (u(C_TROUT) < c["p_transfer_out"]).long() * D_TRANSFER
        tdisp = tdisp.masked_fill(us > 1.0 - self.p_admit[acu], D_ADMIT)
        img = u(C_IMG) < self.p_img[acu]
        ct = u(C_CT) < self.p_ct[acu]
        needs = (img & ~ct).long() * N_XRAY * self._has_type[0] + (img & ct).long() * N_CT * self._has_type[1] \
            + (u(C_LAB) < self.p_lab[acu]).long() * N_LAB
        mis = (u(C_MIS) < c["p_mistriage"]) & (mode == 0)
        acu_q = torch.where(mis, torch.where(u(C_MISDIR) < 0.5, acu - 1, acu + 1).clamp(1, 5), acu)
        a_int = torch.stack([ords.expand_as(acu), pk, cond, mode, torch.bucketize(u(C_AGE).contiguous(), self.age_cdf),
                             torch.bucketize(u(C_PAYER).contiguous(), self.payer_cdf), tdisp,
                             (t.expand_as(acu) if isinstance(t, torch.Tensor) else torch.full_like(acu, t)), needs], -1)
        a_flt = torch.stack([
            sev, self.d_patience.sample(u(C_PAT), acu), self.d_triage.sample(u(C_TRI_D), acu_q),
            self.d_enc.sample(u(C_ENC_D), acu), self.d_treat.sample(u(C_TREAT_D), acu), self.d_lab.sample(u(C_LAB_D)),
            self.d_proc.sample(u(C_PROC_D), (needs & N_CT > 0).long()), self.d_reeval.sample(u(C_REEVAL_D), acu),
            self.d_los.sample(u(C_LOS_D)), c["encounter_quality_sd"] * rng.normal_from_unit(u(C_QUAL)),
            u(C_DERR), u(C_WADV), -torch.log1p(-u(C_HAZ)), -torch.log1p(-u(C_HAZ + 1))], -1)
        return a_int, a_flt, acu, acu_q

    def _pregen_arrivals(self):
        """Draw this hour's arrivals (counts per tick and every arriving patient's attributes) in one
        pass. They depend only on (seed, tick, arrival ordinal), so drawing them ahead changes nothing."""
        t0, n = self._tick, self.tph
        ticks = t0 + torch.arange(n, device=self.device)
        tk = rng.key(self.seedkey.unsqueeze(1), ST_ARR, ticks.unsqueeze(0))
        n_arr = (rng.unit(tk, 0).unsqueeze(2) > self._arr_cdf.view(1, 1, -1)).sum(2)
        start = self.next_ord.unsqueeze(1) + torch.cumsum(n_arr, 1) - n_arr
        ords = start.unsqueeze(2) + self.arK
        a_int, a_flt, acu, acu_q = self._attrs(rng.key(self.seedkey.view(-1, 1, 1), ST_PAT, ords), ords, ticks.view(1, n, 1))
        self._pre = dict(t0=t0, tk=tk, n=n_arr, a_int=a_int, a_flt=a_flt, acu=acu, acu_q=acu_q)

    def _select(self, cand, n):
        """Top-n candidates per hospital in the current priority order. Returns (mask, rank)."""
        cs = cand.gather(1, self._order)
        r = torch.cumsum(cs, 1) - 1
        ss = cs & (r < n.unsqueeze(1))
        sel = torch.zeros_like(cand).scatter_(1, self._order, ss)
        rank = torch.zeros_like(r).scatter_(1, self._order, r)
        return sel, rank

    def _free_bays(self, mask):
        p = self.p
        idx = torch.where(mask, p["bay"], torch.full_like(p["bay"], self.NB))
        self.bay_busy.scatter_(1, idx, torch.zeros_like(mask))
        self.bay_clean.scatter_(1, idx, self.bay_turn[idx])
        p["bay"] = torch.where(mask, torch.full_like(idx, self.NB), p["bay"])

    def _hist_add(self, hist, mask, ticks):
        bins = ticks.clamp(0, hist.shape[1] - 1)
        hist.scatter_add_(1, bins, mask.to(hist.dtype))

    @staticmethod
    def _hist_q(hist, q):
        cs = torch.cumsum(hist.to(torch.float32), 1)
        tot = cs[:, -1:]
        idx = (cs < q * tot).sum(1).clamp(max=hist.shape[1] - 1)
        return torch.where(tot.squeeze(1) > 0, idx.float(), torch.zeros_like(idx, dtype=torch.float32))

    # ======================================================================================
    # tick
    # ======================================================================================
    def tick(self, actions: dict | None = None) -> None:
        if self._tick % self.tph == 0:
            if actions:
                self._apply_actions(actions)
            if self._tick > 0:
                self._hour_start()
            elif actions:
                self._hour_start_redo()
        self._tick_core()
        if self.record:
            self._capture_exits()
        if self._deferred_n:
            self._apply_deferred()
        if self._tick % self.tph == 0:
            self._hour_end()

    # ---- scenario events injected at run time (additive API, used by the server) ----------
    EVENT_ALIASES = dict(flu_surge="flu_wave", ct_outage="equipment_outage", rn_callouts="staff_callouts",
                         nursing_absences="staff_callouts", imaging_outage="equipment_outage", discharge_delays="discharge_delay")

    def inject_event(self, b: int = 0, type: str = "flu_wave", **params) -> dict:
        """Start a catalog event (catalog/event.yaml) at the next simulated hour. Parameters default
        to the catalog values and can be overridden by keyword. The schedule is exogenous and shared
        by every hospital of the batch (`b` is accepted for symmetry; events are scenario-level)."""
        ty = self.EVENT_ALIASES.get(type, type)
        variants = (self.scn.cat.get("event") or {}).get("variants") or {}
        if ty not in variants:
            raise KeyError(f"unknown event type '{type}'; have {sorted(variants)}")
        ev = {k: a.get("value") for k, a in (variants[ty].get("attributes") or {}).items()}
        if type == "rn_callouts" or type == "nursing_absences":
            ev["roles"] = ["rn"]
        ev.update(params)
        hour = self._tick // self.tph + 1
        ev.update(type=ty, start_day=hour // 24, start_hour=hour % 24)
        self.scn.events.append(ev)
        if ty == "equipment_outage":
            self._has_outage = True
        return dict(ev)

    def _hour_start_redo(self):
        # reset() already ran _hour_start for hour 0 with default settings; redo it with the
        # manager's first actions (undo the hourly costs that were booked).
        self.acc["cost_labor"].zero_()
        self.acc["cost_fixed"].zero_()
        self._shift_idx = -1
        self._hour_start()

    def step(self, actions: dict | None = None) -> dict:
        for i in range(self.ticks_per_step):
            self.tick(actions if i == 0 else None)
        return self.metrics_last_hour()

    def metrics_last_hour(self) -> dict:
        return dict(self._last)

    def _tick_core(self):
        p, c, fl, dev, B = self.p, self.cfg, self.flags, self.device, self.B
        t, dt, NB = self._tick, self.dt, self.NB
        acc = self.acc
        rec = self.record
        ps, pd = self.ps, self.pd
        zf = self._zf
        # ---------------- 1. free the slots of patients who exited last tick
        state = p["state"]
        active = p["active"] & (state != S_EXIT)

        # ---------------- 2. arrivals (exogenous stream)
        pre = self._pre                       # this hour's arrivals were drawn at the hour start (exogenous)
        hi = t - pre["t0"]
        tk = pre["tk"][:, hi]
        n_arr = pre["n"][:, hi]
        valid = self.arK.unsqueeze(0) < n_arr.unsqueeze(1)
        a_int, a_flt, a_acu, a_acuq = pre["a_int"][:, hi], pre["a_flt"][:, hi], pre["acu"][:, hi], pre["acu_q"][:, hi]
        a_mode = a_int[:, :, I_MODE]
        divert = valid & self.divert_on.unsqueeze(1) & (a_mode == 1) & (a_acu >= 3)
        enter = valid & ~divert
        free = ~active
        n_free = free.sum(1)
        e_rank = torch.cumsum(enter, 1) - 1
        over = enter & (e_rank >= n_free.unsqueeze(1))
        enter = enter & ~over
        n_enter = enter.sum(1)
        n_over = over.sum(1)
        n_div = divert.sum(1) + n_over
        self.next_ord = self.next_ord + n_arr
        self.entered = self.entered + n_enter
        self.pool_overflow = self.pool_overflow + n_over
        self.exits[:, X_DIVERTED] += n_div
        acc["arrivals"] += n_enter
        acc["diverted"] += n_div
        # k-th entering arrival goes to the k-th free slot
        src = torch.topk(enter.long() * self.kdesc, self.K, dim=1).indices
        slot = torch.topk(free.float() * self.pdesc, self.K, dim=1).indices
        putm = self.arK.unsqueeze(0) < n_enter.unsqueeze(1)
        slot3, putm3 = slot.unsqueeze(2), putm.unsqueeze(2)
        ords = a_int[:, :, I_PID]
        s_i = slot3.expand(-1, -1, ps.shape[2])
        ps.scatter_(1, s_i, torch.where(putm3, a_int.gather(1, src.unsqueeze(2).expand(-1, -1, ps.shape[2])), ps.gather(1, s_i)))
        s_f = slot3.expand(-1, -1, pd.shape[2])
        pd.scatter_(1, s_f, torch.where(putm3, a_flt.gather(1, src.unsqueeze(2).expand(-1, -1, pd.shape[2])), pd.gather(1, s_f)))
        if fl["bays"]:
            st_new = torch.where(a_mode == 0, self._c_walkin_state, self._c_wb)
        else:
            st_new = self._c_wp.expand(B, self.K)
        acu, aq = p["acu"], p["acu_q"]
        state = state.scatter(1, slot, torch.where(putm, st_new.gather(1, src), state.gather(1, slot)))
        acu = acu.scatter(1, slot, torch.where(putm, a_acu.gather(1, src), acu.gather(1, slot)))
        aq = aq.scatter(1, slot, torch.where(putm, a_acuq.gather(1, src), aq.gather(1, slot)))
        new = torch.zeros_like(active).scatter_(1, slot, putm)
        active = active | new
        p["active"] = active
        flags = p["flags"].masked_fill(new, 0)
        pexit = p["exit"].masked_fill(new, 0)
        hold = p["hold"] & ~new
        disp = p["disp"].masked_fill(new, -1)
        t_seen = p["t_seen"].masked_fill(new, -1)
        t_state = p["t_state"].masked_fill(new, t)
        h_det = p["h_det"].masked_fill(new, 0.0)
        h_die = p["h_die"].masked_fill(new, 0.0)
        pid, mode, needs, tdisp, t_arr = ps[:, :, I_PID], ps[:, :, I_MODE], ps[:, :, I_NEEDS], ps[:, :, I_TDISP], ps[:, :, I_TARR]
        bay, phase, nxt, eq = p["bay"], p["phase"], p["next_state"], p["eq"].masked_fill(new, -1)
        timer2, walk_total, treat_left, res_left = p["timer2"], p["walk_total"], p["treat_left"], p["res_left"]
        enc_q = p["enc_q"]

        # ---------------- 3. equipment failures and repairs (exogenous stream), call-ins arriving
        if fl["equipment_failures"]:
            eq_down = (self.eq_down - dt).clamp(min=0)
            uf, ur = rng.unit2(rng.key(tk.view(B, 1, 1), ST_EQ, self._eq_ctr), 0)
            fail = (uf < self.eq_fail.view(1, 2, 1)) & (eq_down <= 0) & (self.arE.view(1, 1, -1) < self.eq_units.unsqueeze(2))
            self.eq_down = torch.where(fail, -self.eq_repair.view(1, 2, 1) * torch.log1p(-ur), eq_down)
            if rec and bool(fail.any()):
                for b, ti, e in torch.nonzero(fail).tolist():
                    self._events[b].append(dict(t=t, kind="equipment_down", text=f"{SCAN_TYPES[ti].upper()} unit {e + 1} is down", entity=f"{SCAN_TYPES[ti]}-{e + 1}"))
            self._eq_update()
        elif self._has_outage:
            self.eq_down = (self.eq_down - dt).clamp(min=0)
            self._eq_update()
        if self._callin_pending > 0:
            cslot = t % (self.callin_delay + 1)
            arr_staff = self.callin_ring[:, :, cslot]
            self.extra_rn = self.extra_rn + arr_staff[:, 0]
            self.extra_md = self.extra_md + arr_staff[:, 1]
            self.callin_ring[:, :, cslot] = 0
            self._callin_pending -= 1
            self._staff_update()

        # ---------------- 4. timers and completions
        dec = self._rate.gather(1, state)
        bcls = self.bay_cls[bay]
        is_prov = state == S_PROV
        if self._two_pools:
            in_ft = (bcls == C_FAST) & self.ft_open.unsqueeze(1)
            dec = torch.where(in_ft & is_prov, dec * self.ft_speed, dec)
        if self._any_played:      # a played encounter lasts exactly its played duration (no fatigue scaling)
            dec.masked_fill_(is_prov & (phase == 1) & ((flags & F_PLAYED) > 0), dt)
        dec.masked_fill_(hold & is_prov, 0.0)
        timer = p["timer"] - dec
        treat_left = treat_left - self._treat_dec
        res_left = res_left - dt
        self.bay_clean = (self.bay_clean - dt).clamp(min=0)
        done = active & (timer <= EPS)
        m_tri = done & (state == S_TRI)
        m_enc = done & is_prov & (phase == 1) & ~hold
        m_dis = done & is_prov & (phase == 2)
        m_walk = done & (state == S_WALK)
        m_test = done & (state == S_TEST)
        m_trn = done & (state == S_BOARD) & (disp == D_TRANSFER)
        m_wdone = done & (state == S_WARD)
        ex = torch.zeros_like(state)                 # exit code to apply this tick (0 = none)
        paym = self.payer_mult[ps[:, :, I_PAYER]]

        # triage finished
        state.masked_fill_(m_tri, S_WB if fl["bays"] else S_WP)
        # clinician encounter finished
        if fl["post_encounter"]:
            # the treatment clock started at first provider contact; low encounter quality stretches it
            treat_left = torch.where(m_enc, treat_left + pd[:, :, F_TREAT] * ((1.0 - enc_q) * c["low_quality_treatment_stretch"]), treat_left)
            has_img = (needs & 3) > 0
            res_left = torch.where(m_enc, torch.where((needs & N_LAB) > 0, pd[:, :, F_LAB], self._zf), res_left)
            state = torch.where(m_enc, torch.where(has_img, self._c_wtest, self._c_wres), state)
        else:
            ex.masked_fill_(m_enc, X_DISCH)
        # walking finished
        state = torch.where(m_walk, nxt, state)
        timer = torch.where(m_walk, timer2 + timer, timer)
        # imaging finished
        if fl["post_encounter"]:
            eqi = eq.clamp(min=0)
            res_left = torch.where(m_test, torch.maximum(res_left, self.eq_result_delay[eqi]), res_left)
            acc["revenue"] += torch.where(m_test, self.eq_revenue[eqi] * paym, zf).sum(1)
            acc["cost_variable"] += torch.where(m_test, self.eq_var_cost[eqi], zf).sum(1)
            if fl["walking"]:
                back = self.legs.gather(1, LEG_SCAN + bcls * 2 + eqi) * self._inv_transport
                state.masked_fill_(m_test, S_WALK)
                nxt.masked_fill_(m_test, S_WRES)
                walk_total = torch.where(m_test, back, walk_total)
                timer2.masked_fill_(m_test, 0.0)
                timer = torch.where(m_test, back + timer, timer)
            else:
                state.masked_fill_(m_test, S_WRES)
            # disposition finished
            derr = pd[:, :, F_DERR] < (1.0 - enc_q) * c["wrong_disposition_max_prob"]
            samp = torch.where(derr & (tdisp != D_TRANSFER), 1 - tdisp, tdisp)
            d = torch.where(disp >= 0, disp, samp)
            if fl["ward"]:
                n_ward = ((state == S_WARD) | ((state == S_WALK) & (nxt == S_WARD))).sum(1)
                n_board = ((state == S_BOARD) & (disp == D_ADMIT)).sum(1)
                capped = (n_ward + n_board).float() >= self.cap_thr * self.ward_cap.float()
                d.masked_fill_((d == D_ADMIT) & capped.unsqueeze(1), D_TRANSFER)
            else:
                d.masked_fill_(d == D_ADMIT, D_DISCHARGE)
            disp = torch.where(m_dis, d, disp)
            m_adm = m_dis & (d == D_ADMIT)
            m_tro = m_dis & (d == D_TRANSFER)
            m_dc = m_dis & (d == D_DISCHARGE)
            ex.masked_fill_(m_dc, X_DISCH)
            m_brd = m_adm | m_tro
            state.masked_fill_(m_brd, S_BOARD)
            timer.masked_fill_(m_tro, c["transfer_wait_min"])
            flags = torch.where(m_adm, flags | F_ADMIT, flags)
            p["t_board"] = p["t_board"].masked_fill(m_brd, t)
            acc["admissions"] += m_adm.sum(1)
            wrong_dc = m_dc & (tdisp == D_ADMIT) & (pd[:, :, F_WADV] < c["wrong_discharge_adverse_prob"])
            acc["adverse_events"] += wrong_dc.sum(1)
            acc["cost_variable"] += m_tro.sum(1).float() * c["transfer_out_cost"]
            # transfer leaves / ward stay finished
            ex.masked_fill_(m_trn, X_TRANSFER)
            ex.masked_fill_(m_wdone, X_WARD)
            acc["revenue"] += torch.where(m_wdone, paym, zf).sum(1) * c["inpatient_revenue"]
            t_state.masked_fill_(m_tri | m_enc | m_walk | m_test | m_dis, t)
        else:
            t_state.masked_fill_(m_tri | m_walk, t)

        # ---------------- 5. hazards for patients still here
        wait_ticks = t - t_arr
        wait_min = wait_ticks.float() * dt
        live = active & (ex == 0)
        if fl["abandonment"]:
            m_lwbs = live & self.tab_leave[state] & (mode == 0) & (wait_min >= pd[:, :, F_PATIENCE])
            ex.masked_fill_(m_lwbs, X_LWBS)
            acc["lwbs"] += m_lwbs.sum(1)
            if rec and bool(m_lwbs.any()):
                self._log_patient_events(m_lwbs, "lwbs", "Patient {} left without being seen")
        if fl["hazards"]:
            hz = state * 6 + acu
            h_det = h_det + self.haz_det[hz]
            h_die = h_die + self.haz_die[hz]
            m_det = live & (h_det >= pd[:, :, F_THR_DET]) & (acu > 1)
            m_die = live & (h_die >= pd[:, :, F_THR_DIE])
            h_det.masked_fill_(m_det, 0.0)
            dl = m_det.long()
            acu = acu - dl
            aq = (aq - dl).clamp(min=1)
            flags = torch.where(m_det, flags | F_DET, flags)
            ex.masked_fill_(m_die, X_DIED)
            nd, ndie = m_det.sum(1), m_die.sum(1)
            acc["deteriorations"] += nd
            acc["deaths"] += ndie
            acc["adverse_events"] += nd + ndie
            if rec and bool((m_det | m_die).any()):
                self._log_patient_events(m_det, "deterioration", "Patient {} deteriorated while waiting")
                self._log_patient_events(m_die, "death", "Patient {} died")
        # ---- apply exits
        m_ex = ex > 0
        was_ed = self.tab_ed[state] | ((state == S_WALK) & (nxt != S_WARD))
        m_dep = m_ex & was_ed & (ex != X_LWBS)                # ED departures this tick (ward moves added below)
        m_rev = m_dep & (ex != X_DIED)
        fidx = torch.where(m_ex, bay, self._c_nb)
        self.bay_busy.scatter_(1, fidx, self._false_bp)
        self.bay_clean.scatter_(1, fidx, self.bay_turn[fidx])
        bay.masked_fill_(m_ex, NB)
        state.masked_fill_(m_ex, S_EXIT)
        pexit = torch.where(m_ex, ex, pexit)
        t_state.masked_fill_(m_ex, t)
        hold = hold & ~m_ex
        self.exits.scatter_add_(1, ex, m_ex.long())
        acc["treated"] += (m_ex & ((ex == X_DISCH) | (ex == X_WARD) | (ex == X_TRANSFER))).sum(1)

        # ---------------- 6. assignments
        prio = self.k_ac * (aq * 60).float() - self.k_age * wait_min + self.k_sh * self.exp_service[aq]
        prio = torch.where(self.tab_rule[state], prio, self._zf)
        key = (prio.long() << 32) + pid
        key = torch.where(active & ~m_ex, key, self._c_inf)
        order = torch.argsort(key, dim=1)
        self._order = order
        moved = torch.zeros_like(active)              # patients whose state changes in this phase
        # ---- triage
        if fl["triage"] and fl["bays"]:
            n = (self.tri_n - (state == S_TRI).sum(1)).clamp(min=0)
            sel, _ = self._select(state == S_WT, n)
            dur = pd[:, :, F_TRI]
            if fl["walking"]:
                dur = dur + self.legs[:, LEG_TRI:LEG_TRI + 1] * self._inv_walk
            state.masked_fill_(sel, S_TRI)
            timer = torch.where(sel, dur, timer)
            moved = moved | sel
        # ---- bays
        if fl["bays"]:
            budget = (self.bay_budget_cap - (bay < NB).sum(1)).clamp(min=0)
            freeb_all = self.bay_open & ~self.bay_busy & (self.bay_clean <= 0)
            child = ps[:, :, I_AGE] == 0
            wb = state == S_WB
            got = torch.zeros_like(wb)
            for k in self.class_order:
                if k == C_RESUS:
                    cand = wb & (aq == 1)
                elif k == C_PEDS:
                    cand = wb & child & (aq >= 2) & ~got
                elif k == C_FAST:
                    cand = wb & (aq >= 4) & ~child & ~got
                elif k == C_HALL:
                    cand = wb & (aq >= 3) & ~got
                else:
                    cand = wb & ~got
                freeb = freeb_all & self.bay_is[k]
                n = torch.minimum(freeb.sum(1), budget)
                sel, rank = self._select(cand, n)
                br = torch.cumsum(freeb, 1) - 1
                by_rank = self._c_nb_row.scatter(1, torch.where(freeb, br, self._c_nb_row), self._arNB_row)
                pb = by_rank.gather(1, rank.clamp(0, NB - 1))
                bay = torch.where(sel, pb, bay)
                self.bay_busy.scatter_(1, torch.where(sel, pb, self._c_nb), self._true_bp)
                budget = budget - sel.sum(1)
                got = got | sel
                if k == C_FAST:
                    flags = torch.where(sel, flags | F_FAST, flags)
            self.bay_busy[:, NB] = False
            bcls = self.bay_cls[bay]
            if fl["walking"]:
                wt = self.legs.gather(1, torch.where(mode == 0, LEG_WAIT + bcls, LEG_AMB + bcls)) * self._inv_walk
                state.masked_fill_(got, S_WALK)
                nxt.masked_fill_(got, S_WP)
                timer = torch.where(got, wt, timer)
                walk_total = torch.where(got, wt, walk_total)
                timer2.masked_fill_(got, 0.0)
            else:
                state.masked_fill_(got, S_WP)
            moved = moved | got
        # ---- providers (pool 0 = main, pool 1 = fast track)
        post = fl["post_encounter"]
        ready = (state == S_WRES) & (treat_left <= EPS) & (res_left <= EPS) if post else None
        split = self.settings["provider_split"]
        is_prov = state == S_PROV
        is_wp = state == S_WP
        seen_new = None
        seen_dis = None
        if self._two_pools:
            in_ft = (bcls == C_FAST) & self.ft_open.unsqueeze(1)
        for pool in ((0, 1) if self._two_pools else (0,)):
            if not self._two_pools:
                busy = is_prov.sum(1)
                newc, disc = is_wp, ready
            else:
                pm = in_ft if pool == 1 else ~in_ft
                busy = (is_prov & pm).sum(1)
                newc = is_wp & pm
                disc = ready & pm if post else None
            freep = (self.md_cap[pool] - busy).clamp(min=0)
            n_new = newc.sum(1)
            if post:
                n_dis = disc.sum(1)
                q_new = torch.where(split == 0, freep, torch.where(split == 1, (freep + 1) // 2, torch.zeros_like(freep)))
                a_new0 = torch.minimum(n_new, q_new)
                a_dis = torch.minimum(n_dis, freep - a_new0)
                a_new = a_new0 + torch.minimum(n_new - a_new0, freep - a_new0 - a_dis)
                sd_, _ = self._select(disc, a_dis)
                seen_dis = sd_ if seen_dis is None else seen_dis | sd_
            else:
                a_new = torch.minimum(n_new, freep)
            sn_, _ = self._select(newc, a_new)
            seen_new = sn_ if seen_new is None else seen_new | sn_
        # start clinician encounters
        dur = pd[:, :, F_ENC]
        qual = pd[:, :, F_QZ] + self._q_base.unsqueeze(1)
        if self.cls_present[C_HALL] and fl["bays"]:
            qual = qual - c["hallway_quality_penalty"] * (bcls == C_HALL).float()
        qual = qual.clamp(0.05, 1.0)
        timer = torch.where(seen_new, dur, timer)
        treat_left = torch.where(seen_new, pd[:, :, F_TREAT], treat_left)
        p["enc_dur"] = torch.where(seen_new, dur, p["enc_dur"])
        enc_q = torch.where(seen_new, qual, enc_q)
        t_seen.masked_fill_(seen_new, t)
        phase.masked_fill_(seen_new, 1)
        acc["first_seen"] += seen_new.sum(1)
        acc["door_to_provider_sum_min"] += torch.where(seen_new, wait_min, zf).sum(1)
        acc["cost_variable"] += torch.where(seen_new, self.supply[acu], zf).sum(1)
        self.wait_hist_cur.scatter_add_(1, wait_ticks.clamp(0, self.wait_bins - 1), seen_new.to(torch.int32))
        if post:
            timer = torch.where(seen_dis, pd[:, :, F_REEVAL], timer)
            phase.masked_fill_(seen_dis, 2)
            seen_any = seen_new | seen_dis
        else:
            seen_any = seen_new
        state.masked_fill_(seen_any, S_PROV)
        moved = moved | seen_any
        n_ward = None
        if post:
            # ---- scanners
            wtest = state == S_WTEST
            scanning = (state == S_TEST) | ((state == S_WALK) & (nxt == S_TEST))
            proc = pd[:, :, F_PROC]
            for ti in range(2):
                n = (self.eq_avail[:, ti] - (scanning & (eq == ti)).sum(1)).clamp(min=0)
                sel, _ = self._select(wtest & ((needs & (1 << ti)) > 0), n)
                eq.masked_fill_(sel, ti)
                if fl["walking"]:
                    go = self.legs.gather(1, LEG_SCAN + bcls * 2 + ti) * self._inv_transport
                    state.masked_fill_(sel, S_WALK)
                    nxt.masked_fill_(sel, S_TEST)
                    timer = torch.where(sel, go, timer)
                    walk_total = torch.where(sel, go, walk_total)
                    timer2 = torch.where(sel, proc, timer2)
                else:
                    state.masked_fill_(sel, S_TEST)
                    timer = torch.where(sel, proc, timer)
                moved = moved | sel
            # ---- ward beds
            n_ward = ((state == S_WARD) | ((state == S_WALK) & (nxt == S_WARD))).sum(1)
            if fl["ward"]:
                n = (self.ward_cap - n_ward).clamp(min=0)
                sel, _ = self._select((state == S_BOARD) & (disp == D_ADMIT), n)
                board_h = (t - p["t_board"]).float() * (dt / 60.0)
                los = pd[:, :, F_LOS] * self.los_mult * (1.0 + c["boarding_los_penalty"] * board_h)
                fidx = torch.where(sel, bay, self._c_nb)
                self.bay_busy.scatter_(1, fidx, self._false_bp)
                self.bay_clean.scatter_(1, fidx, self.bay_turn[fidx])
                bay.masked_fill_(sel, NB)
                if fl["walking"]:
                    go = self.legs.gather(1, LEG_WARD + bcls) * self._inv_transport
                    state.masked_fill_(sel, S_WALK)
                    nxt.masked_fill_(sel, S_WARD)
                    timer = torch.where(sel, go, timer)
                    walk_total = torch.where(sel, go, walk_total)
                    timer2 = torch.where(sel, los, timer2)
                else:
                    state.masked_fill_(sel, S_WARD)
                    timer = torch.where(sel, los, timer)
                moved = moved | sel
                m_dep = m_dep | sel
                m_rev = m_rev | sel
                n_ward = n_ward + sel.sum(1)
        t_state.masked_fill_(moved, t)
        p["state"], p["timer"], p["acu"], p["acu_q"], p["flags"], p["exit"], p["hold"] = state, timer, acu, aq, flags, pexit, hold
        p["disp"], p["t_seen"], p["t_state"], p["h_det"], p["h_die"], p["bay"], p["phase"] = disp, t_seen, t_state, h_det, h_die, bay, phase
        p["next_state"], p["eq"], p["timer2"], p["walk_total"], p["treat_left"], p["res_left"], p["enc_q"] = nxt, eq, timer2, walk_total, treat_left, res_left, enc_q

        # ---------------- 7. accounting
        acc["ed_departures"] += m_dep.sum(1)
        acc["ed_los_sum_min"] += torch.where(m_dep, wait_min, zf).sum(1)
        self.los_hist_cur.scatter_add_(1, wait_ticks.clamp(0, self.los_bins - 1), m_dep.to(torch.int32))
        acc["revenue"] += torch.where(m_rev, self.rev_ed[acu] * paym, zf).sum(1)
        n_prov = (state == S_PROV).sum(1).float()
        acc["md_busy"] += n_prov
        acc["md_on"] += self.md_eff
        acc["diversion_hours"] += self._divert_h
        acc["waiting_patient_minutes"] += self.tab_pre[state].sum(1) * dt
        if post:
            acc["boarding_hours"] += (state == S_BOARD).sum(1).float() / self.tph
            acc["cost_variable"] += n_ward.float() * (c["inpatient_cost_per_day"] / self.tpd)
        if self._callin_active:
            acc["overtime_hours"] += (self.extra_md + self.extra_rn).float() / self.tph
            acc["cost_labor"] += (self.extra_md.float() * self._ot_rate_md + self.extra_rn.float() * self._ot_rate_rn) / self.tph
        if fl["bays"]:
            in_bay = bay < NB
            care = torch.where(in_bay, self.nurse_care[acu], zf).sum(1)
            self.rn_load = care / (60.0 * self.rn_eff.float().clamp(min=1.0))
            acc["rn_load"] += self.rn_load.clamp(max=1.0)
        if fl["fatigue"]:
            um = (n_prov / self.md_eff.float().clamp(min=1.0)).clamp(max=1.0)
            ur = self.rn_load.clamp(max=1.0)
            self.fat_md = (self.fat_md + self._fat_g * um - self._fat_r * (1.0 - um)).clamp(0.0, 1.0)
            self.fat_rn = (self.fat_rn + self._fat_g * ur - self._fat_r * (1.0 - ur)).clamp(0.0, 1.0)
            excess = (c["fatigue_error_multiplier"] - 1.0) * 0.5 * (self.fat_md + self.fat_rn) + (self.rn_load - 1.0).clamp(min=0)
            p_err = self._err_base * in_bay.sum(1).float() * excess
            acc["adverse_events"] += (rng.unit(tk, 7) < p_err).float()
            self._fatigue_rates()
        self._tick = t + 1

    def _fatigue_rates(self):
        """Per-state timer decrement for the next tick (fatigue slows providers and nurses)."""
        c, dt = self.cfg, self.dt
        if self.flags["fatigue"]:
            self._rate[:, S_PROV] = dt / (1.0 + c["fatigue_speed_penalty"] * self.fat_md)
            self._rate[:, S_TRI] = dt / (1.0 + c["fatigue_speed_penalty"] * self.fat_rn)
            self._treat_dec = (dt / self.rn_load.clamp(min=1.0)).unsqueeze(1)
        self._q_base = c["encounter_quality_base"] - c["fatigue_quality_penalty"] * self.fat_md

    # ======================================================================================
    # metrics
    # ======================================================================================
    def _instant(self):
        p = self.p
        st = p["state"]
        act = p["active"] & (st != S_EXIT)
        cnt = torch.zeros((self.B, 12), device=self.device).scatter_add_(1, st, act.float())
        walking_ward = (act & (st == S_WALK) & (p["next_state"] == S_WARD)).sum(1).float()
        ed = cnt[:, :9].sum(1) + cnt[:, S_WALK] - walking_ward
        waiting = cnt[:, :4].sum(1) + (act & (st == S_WALK) & (p["next_state"] == S_WP)).sum(1).float()
        occ = (p["bay"] < self.NB).sum(1).float()
        phys = self.bay_open[:, :self.NB].sum(1)
        staffed = torch.minimum(phys, self.bay_budget_cap).float().clamp(min=1.0)
        ward = cnt[:, S_WARD] + walking_ward
        return dict(cnt=cnt, ed_census=ed, waiting_count=waiting, boarding_count=cnt[:, S_BOARD],
                    bay_occupancy=occ / staffed, ward_occupancy=ward / self.ward_cap.float().clamp(min=1.0),
                    occ=occ, staffed=staffed, phys=phys.float(), ward=ward)

    def _hour_end(self):
        acc, tph = self.acc, self.tph
        h = (self._tick // tph - 1) % 24
        inst = self._instant()
        m = {k: acc[k].clone() for k in SUM_METRICS}
        m["cost_total"] = m["cost_labor"] + m["cost_fixed"] + m["cost_variable"] + m["cost_structural"]
        m["margin"] = m["revenue"] - m["cost_total"]
        m["wait_mean_min"] = m["door_to_provider_sum_min"] / m["first_seen"].clamp(min=1.0)
        # trailing 24 h windows
        self.wait_hist_24 += self.wait_hist_cur - self.wait_ring[:, h].to(torch.int32)
        self.wait_ring[:, h] = self.wait_hist_cur.to(torch.int16)
        self.los_hist_24 += self.los_hist_cur - self.los_ring[:, h].to(torch.int32)
        self.los_ring[:, h] = self.los_hist_cur.to(torch.int16)
        self.wait_hist_ep += self.wait_hist_cur
        self.los_hist_ep += self.los_hist_cur
        self.wait_hist_cur.zero_()
        self.los_hist_cur.zero_()
        self.ring_arr[:, h] = m["arrivals"]
        self.ring_lwbs[:, h] = m["lwbs"]
        self.ring_margin[:, h] = m["margin"]
        m["wait_p95_min"] = self._hist_q(self.wait_hist_24, 0.95) * self.dt
        m["ed_los_median_min"] = self._hist_q(self.los_hist_24, 0.5) * self.dt
        m["lwbs_rate"] = self.ring_lwbs.sum(1) / self.ring_arr.sum(1).clamp(min=1.0)
        for k in ["ed_census", "waiting_count", "boarding_count", "bay_occupancy", "ward_occupancy"]:
            m[k] = inst[k]
        m["md_utilization"] = (acc["md_busy"] / acc["md_on"].clamp(min=1.0)).clamp(max=1.0)
        m["rn_utilization"] = acc["rn_load"] / tph
        n_staff = (self.md_eff + self.rn_eff + self.tri_n).float() + self.support_n
        m["staff_on_shift"] = n_staff
        m["fatigue_mean"] = (self.fat_md * self.md_eff.float() + self.fat_rn * self.rn_eff.float()) / (self.md_eff + self.rn_eff).float().clamp(min=1.0)
        m["waiting_patient_minutes"] = acc["waiting_patient_minutes"].clone()
        self._last = {k: m[k] for k in self._metric_names + EXTRA_METRICS}
        for k, v in self.ep.items():
            v += m[k]
        self.ep_hours += 1
        for v in acc.values():
            v.zero_()

    def episode_summary(self) -> dict:
        ep = self.ep
        days = max(self.ep_hours, 1) / 24.0
        arr = ep["arrivals"].clamp(min=1.0)
        out = dict(
            wait_mean_min=ep["door_to_provider_sum_min"] / ep["first_seen"].clamp(min=1.0),
            wait_p95_min=self._hist_q(self.wait_hist_ep + self.wait_hist_cur, 0.95) * self.dt,
            ed_los_median_min=self._hist_q(self.los_hist_ep + self.los_hist_cur, 0.5) * self.dt,
            lwbs_rate=ep["lwbs"] / arr,
            cost_per_day=(ep["cost_labor"] + ep["cost_fixed"] + ep["cost_variable"] + ep["cost_structural"]) / days,
            margin_per_day=(ep["revenue"] - ep["cost_labor"] - ep["cost_fixed"] - ep["cost_variable"] - ep["cost_structural"]) / days,
            cost_per_treated=(ep["cost_labor"] + ep["cost_fixed"] + ep["cost_variable"] + ep["cost_structural"]) / ep["treated"].clamp(min=1.0),
            deaths_per_10k=1e4 * ep["deaths"] / arr,
            boarding_hours_per_day=ep["boarding_hours"] / days,
            diversion_hours_per_day=ep["diversion_hours"] / days,
            overtime_hours_per_day=ep["overtime_hours"] / days)
        return {k: out[k].to(torch.float32) for k in self.scn.summary_defs}

    def episode_means(self) -> dict:
        """Episode means of the instant / utilisation metrics (not part of the contract summary)."""
        h = max(self.ep_hours, 1)
        return {k: (self.ep[k] / h).to(torch.float32) for k in ["ed_census", "waiting_count", "boarding_count", "bay_occupancy", "ward_occupancy",
                                             "md_utilization", "rn_utilization", "staff_on_shift", "fatigue_mean"]}

    def conservation(self) -> dict:
        """Counts for the conservation law: generated == in_system + sum(exits)."""
        p = self.p
        in_sys = (p["active"] & (p["state"] != S_EXIT)).sum(1)
        return dict(generated=self.next_ord.clone(), in_system=in_sys, exits=self.exits.clone(),
                    initial_census=self.initial_census.clone(), pool_overflow=self.pool_overflow.clone(),
                    residual=self.next_ord - in_sys - self.exits.sum(1))

    # ======================================================================================
    # observation
    # ======================================================================================
    def obs_names(self) -> list[str]:
        if self._obs_names is None:
            n = ["q_waiting_triage", "q_in_triage", "q_waiting_bay", "q_waiting_provider", "q_with_provider", "q_imaging",
                 "q_waiting_results", "q_ready_disposition", "q_boarding", "ward_occupancy",
                 "wait_longest", "wait_mean_waiting", "waiting_esi12", "waiting_esi3", "waiting_esi45",
                 "bay_occupancy", "staffed_bay_share", "fast_track_occupancy", "resus_occupancy",
                 "md_on", "rn_on", "fatigue_md", "fatigue_rn", "md_util_last", "rn_util_last", "md_absent", "rn_absent",
                 "md_called_in", "rn_called_in",
                 "hour_sin", "hour_cos", "dow_sin", "dow_cos", "dom_sin", "dom_cos", "day_frac_1000",
                 "arrivals_last_hour", "arrivals_24h", "lwbs_rate_24h", "arrival_forecast_next_hour",
                 "xray_available", "ct_available", "wait_p95_24h", "ed_los_median_24h", "divert_on",
                 "margin_last_hour", "margin_24h", "cost_last_hour",
                 "main_bays", "ward_beds", "xray_units", "ct_units", "pending_bays", "pending_ward", "pending_equipment",
                 "reloc_triage", "reloc_fast_track", "headcount_offset"]
            n += [f"set_{h}" for h in self.head_names]
            self._obs_names = n
        return list(self._obs_names)

    def observe(self) -> torch.Tensor:
        p, c = self.p, self.cfg
        inst = self._instant()
        cnt = inst["cnt"]
        st = p["state"]
        act = p["active"] & (st != S_EXIT)
        nb = float(max(1, self.scn.layout.n_ed_bays0))
        t = self._tick
        hour = t / self.tph
        wait = (t - p["t_arr"]).float() * self.dt
        waiting = act & self.tab_pre[st]
        wf = waiting.float()
        nwait = wf.sum(1).clamp(min=1.0)
        ready = act & (st == S_WRES) & (p["treat_left"] <= EPS) & (p["res_left"] <= EPS)
        aq = p["acu_q"]
        bc = self.bay_cls[p["bay"]]
        inb = p["bay"] < self.NB
        n_ft = float(max(1, int(self.bay_is[C_FAST].sum())))
        n_rs = float(max(1, int(self.bay_is[C_RESUS].sum())))
        last = self._last
        two_pi = 2 * math.pi
        hod, day = hour % 24, int(hour // 24) + self.start_day
        eday = int(hour // 24)                # episode day (cadence boundaries); `day` is the calendar day
        nxt = int(hour + 1)
        fc = c["hour_prof"][nxt % 24] * c["dow_prof"][(nxt // 24 + self.start_day) % 7]
        mean_h = max(1e-6, c["arrivals_per_day"] / 24.0)
        const = lambda v: torch.full((self.B,), float(v), device=self.device)   # noqa: E731
        n_main = (self.bay_exists & self.bay_is[C_MAIN]).sum(1).float()
        n_main0 = float(max(1, int((self.bay_exists0 & self.bay_is[C_MAIN]).sum())))
        f = [cnt[:, S_WT] / nb, cnt[:, S_TRI] / 3.0, cnt[:, S_WB] / nb, cnt[:, S_WP] / nb, cnt[:, S_PROV] / max(1.0, float(self.max_md)),
             (cnt[:, S_WTEST] + cnt[:, S_TEST]) / 10.0, cnt[:, S_WRES] / nb, ready.float().sum(1) / 10.0, cnt[:, S_BOARD] / nb,
             inst["ward_occupancy"],
             (wait * wf).max(1).values / 240.0, (wait * wf).sum(1) / nwait / 120.0,
             (wf * (aq <= 2)).sum(1) / 10.0, (wf * (aq == 3)).sum(1) / nb, (wf * (aq >= 4)).sum(1) / nb,
             inst["bay_occupancy"], inst["staffed"] / inst["phys"].clamp(min=1.0),
             (inb & (bc == C_FAST)).sum(1).float() / n_ft, (inb & (bc == C_RESUS)).sum(1).float() / n_rs,
             self.md_eff.float() / self.max_md, self.rn_eff.float() / self.max_rn, self.fat_md, self.fat_rn,
             last["md_utilization"], last["rn_utilization"], self.md_abs.float() / 3.0, self.rn_abs.float() / 5.0,
             self.extra_md.float() / 2.0, self.extra_rn.float() / 4.0,
             const(math.sin(two_pi * hod / 24)), const(math.cos(two_pi * hod / 24)),
             const(math.sin(two_pi * (day % 7) / 7)), const(math.cos(two_pi * (day % 7) / 7)),
             const(math.sin(two_pi * (eday % self.dpm) / self.dpm)), const(math.cos(two_pi * (eday % self.dpm) / self.dpm)),
             const(min(eday / 1000.0, 2.0)),
             last["arrivals"] / mean_h, self.ring_arr.sum(1) / (24.0 * mean_h), last["lwbs_rate"] * 10.0, const(fc * self._ev["arr"]),
             self.eq_avail[:, 0].float() / max(1, self.eq_units0[0]), self.eq_avail[:, 1].float() / max(1, self.eq_units0[1]),
             last["wait_p95_min"] / 240.0, last["ed_los_median_min"] / 600.0, self.divert_on.float(),
             last["margin"] / (4.0 * self.cost_scale), self.ring_margin.sum(1) / (96.0 * self.cost_scale), last["cost_total"] / (4.0 * self.cost_scale),
             n_main / n_main0, self.ward_cap.float() / max(1.0, float(c["ward_cap0"])),
             self.eq_units[:, 0].float() / max(1, self.eq_units0[0]), self.eq_units[:, 1].float() / max(1, self.eq_units0[1]),
             self.pend_bays_n.float() / max(1, c["bay_step"]), self.pend_ward_n.float() / max(1, c["ward_step"]),
             self.pend_eq_n.sum(1).float(), (self.reloc == 1).float(), (self.reloc == 2).float(), self.headcount_off.float() / 2.0]
        f += [self.settings[h].float() / max(1, self.head_n[h] - 1) for h in self.head_names]
        clip = float(self.scn.engine["obs_clip"])
        return torch.stack(f, 1).clamp(-clip, clip)

    # ======================================================================================
    # logs (small batches only)
    # ======================================================================================
    def _log_patient_events(self, mask, kind, text):
        for b, s in torch.nonzero(mask).tolist():
            pid = int(self.p["pid"][b, s])
            self._events[b].append(dict(t=self._tick, kind=kind, text=text.format(f"P-{pid:06d}"), entity=pid))

    def _log_decisions(self, name, prev, new, changed):
        spec = {h["name"]: h for h in self.heads}[name]
        for b in torch.nonzero(changed).flatten().tolist():
            a, n = int(prev[b]), int(new[b])
            self._decisions[b].append(dict(t=self._tick, head=name, value=n, prev=a, cadence=spec["cadence"],
                                           label=f"{name}: {spec['options'][a]} -> {spec['options'][n]}"))
            if name == "divert":
                self._events[b].append(dict(t=self._tick, kind="diversion_on" if n == 1 else "diversion_off",
                                            text="Ambulance diversion " + ("started" if n == 1 else "ended"), entity=None))
            if name in ("bays_delta", "ward_beds_delta", "equipment_buy", "relocate", "headcount"):
                self._events[b].append(dict(t=self._tick, kind="structural_started", entity=None,
                                            text=f"Structural decision: {name} = {spec['options'][n]}"))
