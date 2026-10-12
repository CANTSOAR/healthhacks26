"""Batched evaluation of calibration candidates: many parameter sets x seeds in ONE HospitalSim batch.

The simulator takes one ScenarioConfig per batch, so every hospital of a batch normally shares its
parameters. For a search that is far too slow (one 30-day run costs minutes whatever the batch size).
This module builds one simulator and then swaps the handful of per-scenario tables the search varies
for per-hospital tables (duck-typed stand-ins for `DistTable` and a few 1-D lookup tensors). Nothing in
`sim/` is edited. `equivalence_check()` proves the trick: a candidate run through this harness and the
same candidate run the ordinary way (`load_scenario(overrides=...)` + default actions) give the same
trajectory.

A candidate ("theta") is a plain dict:

    md, rn             [day, evening, night] people on shift (providers; floor nurses)
    triage, split      option index of the `triage_nurses` and `provider_split` heads
    enc_scale          x catalog provider_initial_min          (assumed)
    reeval_scale       x catalog provider_reeval_min           (assumed)
    lab_scale          x catalog lab_turnaround_min            (assumed)
    nurse_care_scale   x catalog nurse_care_min_per_hour       (assumed)
    los_factor         hospital.ward_pool_los_factor           (assumed)
    patience_scale     x catalog lwbs_patience_min             (literature; ensemble only, inside its range)
    absence_rate       staff.shared.absence_rate               (literature; ensemble only, inside its range)
    boarding_los_penalty patient.shared.boarding_los_penalty   (literature; ensemble only, inside its range)

`concrete()` turns a theta into the exact numbers both paths use; `overrides_of()` turns those into
`load_scenario` overrides + `baseline_actions`.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from sim import HospitalSim, load_scenario  # noqa: E402
from sim import rng  # noqa: E402

ACU = ["esi1", "esi2", "esi3", "esi4", "esi5"]
SHIFT_HEADS_MD = ("md_day", "md_evening", "md_night")
SHIFT_HEADS_RN = ("rn_day", "rn_evening", "rn_night")
SCENARIO = "normal_week"
SUM_KEYS = ["arrivals", "first_seen", "door_to_provider_sum_min", "lwbs", "admissions", "boarding_hours", "deaths",
            "deteriorations", "adverse_events", "cost_total", "cost_labor", "cost_fixed", "cost_variable", "revenue",
            "ed_departures", "ed_los_sum_min", "treated"]
INST_KEYS = ["ward_occupancy", "bay_occupancy", "md_utilization", "rn_utilization", "fatigue_mean", "ed_census",
             "staff_on_shift", "boarding_count", "waiting_count"]
DEFAULT_THETA = dict(triage=1, split=1, enc_scale=1.0, reeval_scale=1.0, lab_scale=1.0, nurse_care_scale=1.0,
                     patience_scale=1.0)


# ------------------------------------------------------------------------------------------------
# catalog base values (the hospital WITHOUT its calibration file)
# ------------------------------------------------------------------------------------------------
def base_values(hospital_id: str) -> dict:
    scn = load_scenario(SCENARIO, overrides={"hospital_id": hospital_id, "no_calibration": True})
    P = scn.P
    src = lambda f, v, k: (scn.attr(f, v, k, required=False) or {}).get("source", "?")   # noqa: E731
    heads = {h["name"]: h for h in scn.heads}
    adm = sum(m * p for m, p in zip(P["acuity_mix"], P["p_admit"])) / sum(P["acuity_mix"])
    hp = P["hour_prof"]
    sh = [sum(hp[7:15]), sum(hp[15:23]), sum(hp[23:]) + sum(hp[:7])]
    mixw = P["role_mix"]
    tot = sum(mixw.values()) or 1.0
    return dict(
        hospital_id=scn.hospital_id, label=getattr(scn, "hospital_label", hospital_id), layout=scn.layout_source,
        enc=[float(x) for x in P["provider_initial_min"]["mean"]],
        reeval=[float(x) for x in P["provider_reeval_min"]["mean"]],
        lab=float(P["lab"]["mean"]),
        nurse_care=[float(x) for x in P["nurse_care_min_per_hour"]],
        patience=[float(x) for x in P["patience"]["mean"]],
        los_days=float(scn.dist("patient", None, "inpatient_los_days")[1]),
        los_factor=float(P["ward_pool_los_factor"]), ward_init=float(P["ward_initial_occupancy"]),
        absence_rate=float(P["absence_rate"]), boarding_los_penalty=float(P["boarding_los_penalty"]),
        provider_levels=list(P["provider_levels"]), rn_levels=list(P["rn_levels"]), triage_levels=list(P["triage_levels"]),
        n_triage_rooms=int(scn.layout.n_triage_rooms), triage_levels_cal=_triage_ladder(P, int(scn.layout.n_triage_rooms)),
        triage_source=src("staff", None, "triage_nurse_levels"),
        defaults={n: int(h["default"]) for n, h in heads.items()},
        arrivals_per_day=float(P["arrivals_per_day"]), admit_rate=float(adm), ward_cap=int(P["ward_cap0"]),
        n_bays=int(scn.layout.n_ed_bays0), shift_share=[x / (sum(sh) / 3.0) for x in sh],
        wage_md=sum(P["wage"][r] * w for r, w in mixw.items()) / tot,
        wage_phys=sum(P["wage"][r] * w for r, w in mixw.items() if r in ("attending", "resident")) / tot,
        resident_share=float(mixw.get("resident", 0.0)) / tot, app_share=float(mixw.get("app", 0.0)) / tot,
        wage_rn=float(P["wage"]["rn"]), benefits=float(P["benefits_load"]),
        support=dict(P["support"]), support_wages={r: float(P["wage"][r]) for r in P["support"]},
        support_raw=dict(scn.val("staff", None, "support_staff_per_shift")),
        rn_per_bay=float(P["rn_patients_per_nurse_max"]), size_ratio=float(P["size_ratio"]),
        sources=dict(
            enc=src("patient", "esi3", "provider_initial_min"), reeval=src("patient", "esi3", "provider_reeval_min"),
            lab=src("patient", None, "lab_turnaround_min"), nurse_care=src("patient", "esi3", "nurse_care_min_per_hour"),
            patience=src("patient", None, "lwbs_patience_min"), los_factor=src("hospital", None, "ward_pool_los_factor"),
            ward_init=src("hospital", None, "ward_initial_occupancy"), absence_rate=src("staff", None, "absence_rate"), boarding_los_penalty=src("patient", None, "boarding_los_penalty"),
            provider_levels=src("staff", None, "provider_levels"), rn_levels=src("staff", None, "rn_levels"),
            support=src("staff", None, "support_staff_per_shift")),
        base_theta=dict(DEFAULT_THETA, md=[P["provider_levels"][heads[h]["default"]] for h in SHIFT_HEADS_MD],
                        rn=[P["rn_levels"][heads[h]["default"]] for h in SHIFT_HEADS_RN],
                        triage=heads["triage_nurses"]["default"], split=heads["provider_split"]["default"],
                        los_factor=float(P["ward_pool_los_factor"]), absence_rate=float(P["absence_rate"]),
                        boarding_los_penalty=float(P["boarding_los_penalty"])))


def _triage_ladder(P: dict, rooms: int) -> list[int]:
    """Triage staffing options sized to the hospital's volume: the top option keeps peak-hour triage load near 70 %."""
    tri = sum(m * t for m, t in zip(P["acuity_mix"], P["triage_min"]["mean"])) / sum(P["acuity_mix"]) + 1.0   # + a short walk
    need = P["arrivals_per_day"] / 24.0 * max(P["hour_prof"]) * (1.0 - sum(m * a for m, a in zip(P["acuity_mix"], P["amb_share"]))) * tri / 60.0
    top = max(3, min(max(1, rooms), int(math.ceil(need / 0.7))))
    cur = [int(x) for x in P["triage_levels"]]
    return cur if top <= max(cur) else [max(1, top - 2), max(1, top - 1), top]


def ladder(vals, step: int, lo: int) -> list[int]:
    """Five increasing staffing levels that contain the shift values, with room above and below them."""
    u = sorted(set(int(v) for v in vals))
    hi_v, lo_v = max(u), min(u)
    while len(u) < 5:
        n_above = sum(1 for x in u if x > hi_v)
        n_below = sum(1 for x in u if x < lo_v)
        if n_above <= n_below or u[0] - step < lo:
            u.append(u[-1] + step)
        else:
            u.insert(0, u[0] - step)
    return u


def concrete(theta: dict, base: dict) -> dict:
    """Exact numbers for a theta (rounded once here so that the batched and the ordinary path agree)."""
    th = dict(base["base_theta"])
    th.update(theta)
    md = [max(2, int(x)) for x in th["md"]]
    rn = [max(2, int(x)) for x in th["rn"]]
    r = lambda x, n=4: float(round(float(x), n))   # noqa: E731
    pat = base["patience"]
    return dict(
        md=md, rn=rn, triage=int(th["triage"]), split=int(th["split"]),
        triage_levels=list(base["triage_levels_cal"]), provider_levels=ladder(md, 2, 2), rn_levels=ladder(rn, max(2, int(round(0.2 * max(rn)))), 3),
        enc=[r(b * th["enc_scale"]) for b in base["enc"]],
        reeval=[r(b * th["reeval_scale"]) for b in base["reeval"]],
        lab=r(base["lab"] * th["lab_scale"]),
        nurse_care=[r(b * th["nurse_care_scale"]) for b in base["nurse_care"]],
        patience=[pat[0]] + [r(b * th["patience_scale"], 1) for b in pat[1:]],
        los_factor=r(th["los_factor"]), ward_init=r(th.get("ward_init", base["ward_init"]), 3), absence_rate=r(th["absence_rate"], 5),
        boarding_los_penalty=r(th["boarding_los_penalty"], 5),
        theta={k: (list(v) if isinstance(v, (list, tuple)) else v) for k, v in th.items()})


def overrides_of(conc: dict, base: dict, only_changed: bool = True) -> tuple[dict, dict]:
    """(load_scenario dotted-path overrides, baseline_actions) for a concrete candidate."""
    th = conc["theta"]
    bt = base["base_theta"]
    ov, acts = {}, {}
    ch = lambda k: (not only_changed) or abs(float(th[k]) - float(bt[k])) > 1e-12   # noqa: E731
    if ch("enc_scale"):
        for a, v in zip(ACU, conc["enc"]):
            ov[f"patient.{a}.provider_initial_min"] = v
    if ch("reeval_scale"):
        for a, v in zip(ACU, conc["reeval"]):
            ov[f"patient.{a}.provider_reeval_min"] = v
    if ch("nurse_care_scale"):
        for a, v in zip(ACU, conc["nurse_care"]):
            ov[f"patient.{a}.nurse_care_min_per_hour"] = v
    if ch("lab_scale"):
        ov["patient.shared.lab_turnaround_min"] = conc["lab"]
    if ch("patience_scale"):
        ov["patient.shared.lwbs_patience_min"] = list(conc["patience"])
    if ch("los_factor"):
        ov["hospital.ward_pool_los_factor"] = conc["los_factor"]
    if (not only_changed) or abs(conc["ward_init"] - base["ward_init"]) > 1e-9:
        ov["hospital.ward_initial_occupancy"] = conc["ward_init"]
    if ch("absence_rate"):
        ov["staff.shared.absence_rate"] = conc["absence_rate"]
    if ch("boarding_los_penalty"):
        ov["patient.shared.boarding_los_penalty"] = conc["boarding_los_penalty"]
    sr = base["size_ratio"]
    unscale = (lambda xs: [int(round(x / sr)) for x in xs]) if abs(sr - 1.0) > 1e-9 else list   # noqa: E731
    if (not only_changed) or list(conc["triage_levels"]) != list(base["triage_levels"]):
        ov["staff.shared.triage_nurse_levels"] = list(conc["triage_levels"])
    ov["staff.shared.provider_levels"] = unscale(conc["provider_levels"])
    ov["staff.shared.rn_levels"] = unscale(conc["rn_levels"])
    for h, v in zip(SHIFT_HEADS_MD, conc["md"]):
        acts[h] = conc["provider_levels"].index(v)
    for h, v in zip(SHIFT_HEADS_RN, conc["rn"]):
        acts[h] = conc["rn_levels"].index(v)
    acts["triage_nurses"] = conc["triage"]
    acts["provider_split"] = conc["split"]
    return ov, acts


# ------------------------------------------------------------------------------------------------
# per-hospital stand-ins for the simulator's per-scenario tables
# ------------------------------------------------------------------------------------------------
class BDist:
    """DistTable with one row set per hospital: mean/mu are [B, R]; kinds and cv are shared."""

    def __init__(self, kinds, means_b, cvs, device):
        if not isinstance(kinds, (list, tuple)):
            kinds, cvs, means_b = [kinds], [cvs], [[m] for m in means_b]
        mu = []
        sg = []
        for k, cv in zip(kinds, cvs):
            s2 = math.log(1.0 + cv * cv) if (k == "lognormal" and cv > 0) else 0.0
            sg.append(math.sqrt(s2))
        for row in means_b:
            mu.append([math.log(max(m, 1e-9)) - 0.5 * (math.log(1.0 + cv * cv) if (k == "lognormal" and cv > 0) else 0.0)
                       for k, m, cv in zip(kinds, row, cvs)])
        f = dict(device=device, dtype=torch.float32)
        self.mean = torch.tensor(means_b, **f)
        self.mu = torch.tensor(mu, **f)
        self.sig = torch.tensor(sg, **f)
        self.is_ln = torch.tensor([k == "lognormal" for k in kinds], device=device)
        self.is_exp = torch.tensor([k == "exponential" for k in kinds], device=device)
        self.any_ln, self.any_exp = bool(self.is_ln.any()), bool(self.is_exp.any())
        self.all_ln, self.all_exp = bool(self.is_ln.all()), bool(self.is_exp.all())
        self.B = self.mean.shape[0]

    def _b(self, t, like):                       # [B] -> [B, 1, 1, ...] matching `like`
        return t.view(self.B, *([1] * (like.dim() - 1)))

    def sample(self, u, idx=None):
        if idx is None:
            m, mu, sg = self._b(self.mean[:, 0], u), self._b(self.mu[:, 0], u), self.sig[0]
            if self.all_ln:
                return torch.exp(mu + sg * rng.normal_from_unit(u))
            if self.all_exp:
                return -m * torch.log1p(-u)
            return torch.zeros_like(u) + m
        bi = self._b(torch.arange(self.B, device=u.device), idx)
        m = self.mean[bi, idx]
        if self.all_ln:
            return torch.exp(self.mu[bi, idx] + self.sig[idx] * rng.normal_from_unit(u))
        if self.all_exp:
            return -m * torch.log1p(-u)
        out = m
        if self.any_ln:
            out = torch.where(self.is_ln[idx], torch.exp(self.mu[bi, idx] + self.sig[idx] * rng.normal_from_unit(u)), out)
        if self.any_exp:
            out = torch.where(self.is_exp[idx], -m * torch.log1p(-u), out)
        return out


class BTable:
    """1-D lookup table with one row per hospital: `table[idx]` with idx of shape [B, ...]."""

    def __init__(self, rows_b: torch.Tensor):
        self.t = rows_b
        self.B = rows_b.shape[0]

    def __getitem__(self, idx):
        bi = torch.arange(self.B, device=self.t.device).view(self.B, *([1] * (idx.dim() - 1)))
        return self.t[bi, idx]


def build_batched(hospital_id: str, concs: list[dict], seeds: list[int], device="cpu") -> HospitalSim:
    """One simulator with len(concs) x len(seeds) hospitals; hospital b = candidate b // n_seeds, seed b % n_seeds."""
    n_s = len(seeds)
    B = len(concs) * n_s
    cap_md = max(max(c["md"]) for c in concs) + 1
    cap_rn = max(max(c["rn"]) for c in concs) + 1
    scn = load_scenario(SCENARIO, overrides={"hospital_id": hospital_id, "no_calibration": True})
    # placeholder ladders: they only size max_md / max_rn (absence draws are keyed by person index, so the size is neutral)
    scn.P["provider_levels"] = [1, 2, 3, 4, max(cap_md, 5)]
    scn.P["rn_levels"] = [1, 2, 3, 4, max(cap_rn, 5)]
    scn.P["triage_levels"] = list(concs[0]["triage_levels"])
    scn.P["ward_initial_occupancy"] = max(c["ward_init"] for c in concs)      # trimmed per hospital after reset (below)
    seed_t = torch.tensor(list(seeds), dtype=torch.long).repeat(len(concs))
    sim = HospitalSim(scn, batch_size=B, device=device, seed=seed_t)
    dev = sim.device
    P = scn.P
    rep = lambda rows, dt=torch.float32: torch.tensor(rows, dtype=dt).repeat_interleave(n_s, 0).to(dev)   # noqa: E731
    padk = lambda d: ([d["kind"][0]] + list(d["kind"]), [d["cv"][0]] + list(d["cv"]))   # noqa: E731
    padm = lambda xs: [xs[0]] + list(xs)   # noqa: E731
    rows = lambda key: [padm(c[key]) for c in concs for _ in range(n_s)]   # noqa: E731
    k, cv = padk(P["provider_initial_min"])
    sim.d_enc = BDist(k, rows("enc"), cv, dev)
    k, cv = padk(P["provider_reeval_min"])
    sim.d_reeval = BDist(k, rows("reeval"), cv, dev)
    pt = P["patience"]
    sim.d_patience = BDist([pt["kind"]] * 6, rows("patience"), [pt["cv"][0]] + list(pt["cv"]), dev)
    los_days = float(scn.dist("patient", None, "inpatient_los_days")[1])
    sim.d_los = BDist(P["los"]["kind"], [los_days * 1440.0 * c["los_factor"] for c in concs for _ in range(n_s)], P["los"]["cv"], dev)
    sim.d_lab = BDist(P["lab"]["kind"], [c["lab"] for c in concs for _ in range(n_s)], P["lab"]["cv"], dev)
    sim.nurse_care = BTable(rep([padm(c["nurse_care"]) for c in concs]))
    P["absence_rate"] = rep([[c["absence_rate"]] for c in concs])
    P["boarding_los_penalty"] = rep([[c["boarding_los_penalty"]] for c in concs])
    sim.prov_levels = torch.arange(int(sim.max_md) + 1, device=dev)
    sim.rn_levels = torch.arange(int(sim.max_rn) + 1, device=dev)
    sim.reset(seed_t)
    # per-hospital warm start: the engine filled slots [0, n_max) of every hospital; keep the first n_b (same patients, same
    # ordinals as a scenario with that hospital's own ward_initial_occupancy) and rewind the ordinal counter
    if sim.flags["ward"] and scn.P["ward_initial_occupancy"] > 0:
        n_b = rep([max(0, min(int(round(c["ward_init"] * P["ward_cap0"])), sim.P)) for c in concs], torch.long)
        drop = sim.arP.unsqueeze(0) >= n_b.unsqueeze(1)
        sim.p["active"] = sim.p["active"] & ~drop
        sim.p["state"] = sim.p["state"].masked_fill(drop, 11)
        for nm, fill in (("flags", 0), ("disp", -1), ("t_seen", -1)):
            sim.p[nm] = sim.p[nm].masked_fill(drop, fill)
        sim.p["timer"] = sim.p["timer"].masked_fill(drop, 0.0)
        sim.p["acu"] = sim.p["acu"].masked_fill(drop, 3)
        sim.p["acu_q"] = sim.p["acu_q"].masked_fill(drop, 3)
        sim.next_ord = n_b.clone()
        sim.entered = n_b.clone()
        sim.initial_census = n_b.clone()
    for j, h in enumerate(SHIFT_HEADS_MD):
        sim.settings[h] = rep([c["md"][j] for c in concs], torch.long)
    for j, h in enumerate(SHIFT_HEADS_RN):
        sim.settings[h] = rep([c["rn"][j] for c in concs], torch.long)
    sim.settings["triage_nurses"] = rep([c["triage"] for c in concs], torch.long)
    sim.settings["provider_split"] = rep([c["split"] for c in concs], torch.long)
    sim._hour_start_redo()            # what tick() does when the first actions differ from the reset defaults
    sim._twin_batched = True
    return sim


def build_plain(hospital_id: str, overrides: dict | None, baseline_actions: dict | None, seeds: list[int], device="cpu",
                no_calibration: bool = True) -> HospitalSim:
    """The ordinary path: one parameter set, hospitals differ by seed only."""
    ov = dict(overrides or {})
    ov["hospital_id"] = hospital_id
    if no_calibration:
        ov["no_calibration"] = True
    if baseline_actions:
        ov["baseline_actions"] = dict(baseline_actions)
    sim = HospitalSim(load_scenario(SCENARIO, overrides=ov), batch_size=len(seeds), device=device,
                      seed=torch.tensor(list(seeds), dtype=torch.long))
    sim._twin_batched = False
    return sim


# ------------------------------------------------------------------------------------------------
# run + collect
# ------------------------------------------------------------------------------------------------
def simulate(sim: HospitalSim, days: int, warm: int, progress: str = "") -> dict:
    """Run `days` with the baseline policy. Returns per-hospital numpy arrays (post warm-up unless noted)."""
    B, dev, p_get = sim.B, sim.device, (lambda: sim.p)
    wb, lb = sim.wait_bins, sim.los_bins
    wait_h = torch.zeros((B, 5 * wb), device=dev, dtype=torch.int32)
    los_h = torch.zeros((B, 5 * lb), device=dev, dtype=torch.int32)
    sums = {k: torch.zeros((B,), device=dev, dtype=torch.float64) for k in SUM_KEYS}
    inst = {k: torch.zeros((B,), device=dev, dtype=torch.float64) for k in INST_KEYS}
    md_paid = torch.zeros((B,), device=dev, dtype=torch.float64)
    rn_paid = torch.zeros((B,), device=dev, dtype=torch.float64)
    daily = {k: [] for k in ["arrivals", "lwbs", "admissions", "boarding_hours", "ward_occupancy", "bay_occupancy",
                             "door_to_provider_sum_min", "first_seen", "cost_total", "revenue", "wait_p95_min", "ed_los_median_min"]}
    batched = bool(getattr(sim, "_twin_batched", False))
    t0 = time.time()
    for d in range(days):
        day = {k: torch.zeros((B,), device=dev, dtype=torch.float64) for k in daily}
        for _ in range(24):
            acts = None if batched else sim.default_actions()
            for i in range(sim.ticks_per_step):
                sim.tick(acts if i == 0 else None)
                if d >= warm:
                    p = p_get()
                    t = sim._tick - 1
                    st = p["state"]
                    aq = (p["acu_q"] - 1).clamp(0, 4)
                    age = t - p["t_arr"]
                    ex = p["active"] & (st == 11) & (p["exit"] == 1)
                    los_h.scatter_add_(1, aq * lb + age.clamp(0, lb - 1), ex.to(torch.int32))
                    sn = p["active"] & (p["t_seen"] == t)
                    wait_h.scatter_add_(1, aq * wb + age.clamp(0, wb - 1), sn.to(torch.int32))
                    if i == 0:
                        md_paid += (sim.md_sched - sim.md_abs).clamp(min=0)
                        rn_paid += (sim.rn_sched - sim.rn_abs).clamp(min=0) + sim.tri_n
            m = sim.metrics_last_hour()
            for k in day:
                if k in ("ward_occupancy", "bay_occupancy"):
                    day[k] += m[k].double() / 24.0
                elif k in ("wait_p95_min", "ed_los_median_min"):
                    day[k] = m[k].double()
                else:
                    day[k] += m[k].double()
            if d >= warm:
                for k in SUM_KEYS:
                    sums[k] += m[k].double()
                for k in INST_KEYS:
                    inst[k] += m[k].double()
        for k in daily:
            daily[k].append(day[k].cpu().numpy())
        if progress and (d % 5 == 4 or d == days - 1):
            print(f"  {progress} day {d + 1}/{days}  [{time.time() - t0:5.0f}s]", flush=True)
    nd = max(1, days - warm)
    cons = sim.conservation()
    out = dict(
        days=days, warm=warm, n_days=nd, wall=time.time() - t0,
        wait_hist=wait_h.view(B, 5, wb).cpu().numpy().astype(np.int64),
        los_hist=los_h.view(B, 5, lb).cpu().numpy().astype(np.int64),
        sums={k: v.cpu().numpy() for k, v in sums.items()},
        inst={k: (v / (nd * 24.0)).cpu().numpy() for k, v in inst.items()},
        md_paid_hours=md_paid.cpu().numpy(), rn_paid_hours=rn_paid.cpu().numpy(),
        daily={k: np.stack(v) for k, v in daily.items()},                       # [days, B]
        conservation_residual=int(cons["residual"].abs().max()), pool_overflow=int(cons["pool_overflow"].max()),
        tick_minutes=float(sim.tick_minutes))
    return out


def hist_q(h: np.ndarray, q: float, dt: float = 5.0) -> np.ndarray:
    """Quantile of a 5-minute histogram over the last axis; mass of bin k spread over [5k - 2.5, 5k + 2.5]."""
    h = np.asarray(h, dtype=np.float64)
    cs = np.cumsum(h, -1)
    tot = cs[..., -1:]
    k = np.minimum((cs < q * tot).sum(-1), h.shape[-1] - 1)
    prev = np.take_along_axis(cs, np.maximum(k - 1, 0)[..., None], -1)[..., 0] * (k > 0)
    cnt = np.take_along_axis(h, k[..., None], -1)[..., 0]
    frac = np.where(cnt > 0, (q * tot[..., 0] - prev) / np.maximum(cnt, 1e-9), 0.5)
    val = np.maximum(dt * (k - 0.5 + frac), 0.0)
    return np.where(tot[..., 0] > 0, val, np.nan)


def metrics_of(raw: dict, base: dict, n_cand: int, n_seeds: int) -> dict:
    """Named simulated quantities: `pooled[key]` = [n_cand] (all seeds pooled), `per_seed[key]` = [n_cand, n_seeds]."""
    nd, dt = raw["n_days"], raw["tick_minutes"]
    ben, wphys = base["benefits"], base["wage_phys"]

    def calc(wait_h, los_h, s, inst, mdh, n):           # n = number of hospital-runs pooled into each entry
        days = nd * n
        arr = np.maximum(s["arrivals"], 1e-9)
        o = dict(
            arrivals_per_day=s["arrivals"] / days, admissions_per_day=s["admissions"] / days,
            admit_rate=s["admissions"] / arr, lwbs_rate=s["lwbs"] / arr,
            wait_mean=s["door_to_provider_sum_min"] / np.maximum(s["first_seen"], 1e-9),
            wait_median=hist_q(wait_h.sum(-2), 0.5, dt), wait_p90=hist_q(wait_h.sum(-2), 0.9, dt),
            wait_p95=hist_q(wait_h.sum(-2), 0.95, dt),
            los_dc_median=hist_q(los_h.sum(-2), 0.5, dt), los_dc_p90=hist_q(los_h.sum(-2), 0.9, dt),
            boarding_hours_per_day=s["boarding_hours"] / days,
            boarding_min_per_admission=60.0 * s["boarding_hours"] / np.maximum(s["admissions"], 1e-9),
            cost_labor_per_day=s["cost_labor"] / days, cost_per_day=s["cost_total"] / days,
            revenue_per_day=s["revenue"] / days, margin_per_day=(s["revenue"] - s["cost_total"]) / days,
            deaths_per_day=s["deaths"] / days, adverse_events_per_day=s["adverse_events"] / days,
            ed_salaries_all_per_day=s["cost_labor"] / ben / days,
            ed_salaries_per_day=(s["cost_labor"] / ben - mdh["md"] * wphys) / days,
            provider_hours_per_day=mdh["md"] / days, rn_hours_per_day=mdh["rn"] / days,
            provider_hours_per_visit=mdh["md"] / arr, rn_hours_per_visit=mdh["rn"] / arr)
        for a in range(5):
            o[f"wait_median_esi{a + 1}"] = hist_q(wait_h[..., a, :], 0.5, dt)
            o[f"wait_p90_esi{a + 1}"] = hist_q(wait_h[..., a, :], 0.9, dt)
            o[f"los_dc_median_esi{a + 1}"] = hist_q(los_h[..., a, :], 0.5, dt)
            o[f"los_dc_p90_esi{a + 1}"] = hist_q(los_h[..., a, :], 0.9, dt)
        for k in INST_KEYS:
            o[k] = inst[k] / n
        return o

    sh = lambda x: x.reshape(n_cand, n_seeds, *x.shape[1:])   # noqa: E731
    per = calc(sh(raw["wait_hist"]), sh(raw["los_hist"]), {k: sh(v) for k, v in raw["sums"].items()},
               {k: sh(v) for k, v in raw["inst"].items()}, dict(md=sh(raw["md_paid_hours"]), rn=sh(raw["rn_paid_hours"])), 1)
    pooled = calc(sh(raw["wait_hist"]).sum(1), sh(raw["los_hist"]).sum(1), {k: sh(v).sum(1) for k, v in raw["sums"].items()},
                  {k: sh(v).sum(1) for k, v in raw["inst"].items()},
                  dict(md=sh(raw["md_paid_hours"]).sum(1), rn=sh(raw["rn_paid_hours"]).sum(1)), n_seeds)
    daily = {k: sh(v.T).transpose(0, 2, 1) for k, v in raw["daily"].items()}     # [n_cand, days, n_seeds]
    # stationarity: ward occupancy over the last 10 days minus the first 10 measured days (0 = no fill, no drain)
    occ = daily["ward_occupancy"]
    w, n10 = raw["warm"], max(1, min(10, (raw["days"] - raw["warm"]) // 2))
    per["ward_occupancy_drift"] = occ[:, -n10:, :].mean(1) - occ[:, w:w + n10, :].mean(1)
    pooled["ward_occupancy_drift"] = per["ward_occupancy_drift"].mean(1)
    return dict(pooled=pooled, per_seed=per, daily=daily, n_cand=n_cand, n_seeds=n_seeds, days=raw["days"], warm=raw["warm"],
                wall=raw["wall"], conservation_residual=raw["conservation_residual"], pool_overflow=raw["pool_overflow"])


def evaluate(hospital_id: str, thetas: list[dict], seeds: list[int], days: int, warm: int, device="cpu", base=None,
             progress: str = "") -> dict:
    """Batched evaluation of candidate thetas with common random numbers. Returns metrics_of(...) + `concs`."""
    base = base or base_values(hospital_id)
    concs = [concrete(t, base) for t in thetas]
    sim = build_batched(hospital_id, concs, seeds, device)
    out = metrics_of(simulate(sim, days, warm, progress), base, len(concs), len(seeds))
    out["concs"] = concs
    del sim
    if str(device).startswith("cuda"):
        torch.cuda.empty_cache()
    return out


def evaluate_plain(hospital_id: str, overrides: dict | None, baseline_actions: dict | None, seeds: list[int], days: int,
                   warm: int, device="cpu", base=None, no_calibration: bool = True, progress: str = "") -> dict:
    """The ordinary path (load_scenario + default actions) for one parameter set."""
    base = base or base_values(hospital_id)
    sim = build_plain(hospital_id, overrides, baseline_actions, seeds, device, no_calibration)
    out = metrics_of(simulate(sim, days, warm, progress), base, 1, len(seeds))
    del sim
    if str(device).startswith("cuda"):
        torch.cuda.empty_cache()
    return out


def equivalence_check(hospital_id: str, theta: dict, seeds=(900001, 900002), days: int = 3, device="cpu", base=None) -> dict:
    """Same candidate through the batched harness and through load_scenario(overrides): identical counts?"""
    base = base or base_values(hospital_id)
    conc = concrete(theta, base)
    ov, acts = overrides_of(conc, base)
    a = simulate(build_batched(hospital_id, [conc], list(seeds), device), days, 0)
    b = simulate(build_plain(hospital_id, ov, acts, list(seeds), device), days, 0)
    keys = ["arrivals", "first_seen", "door_to_provider_sum_min", "lwbs", "admissions", "ed_departures", "ed_los_sum_min", "deaths"]
    diff = {k: float(np.abs(a["sums"][k] - b["sums"][k]).max()) for k in keys}
    diff["cost_labor_rel"] = float(np.abs(a["sums"]["cost_labor"] / b["sums"]["cost_labor"] - 1).max())
    diff["wait_hist"] = int(np.abs(a["wait_hist"] - b["wait_hist"]).sum())
    diff["los_hist"] = int(np.abs(a["los_hist"] - b["los_hist"]).sum())
    same = all(diff[k] == 0 for k in keys) and diff["wait_hist"] == 0 and diff["los_hist"] == 0 and diff["cost_labor_rel"] < 1e-5
    return dict(identical=bool(same), max_abs_difference=diff, days=days, seeds=list(seeds),
                patients=float(a["sums"]["arrivals"].sum()))


def atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{int(time.time() * 1e6) % 10 ** 9}")
    tmp.write_text(text)
    tmp.replace(path)
