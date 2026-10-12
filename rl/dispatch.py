"""Entity-level learned dispatch: who is taken next for a bay, a provider, a scanner. All numbers SIMULATED.

    python -m rl.dispatch tune  --mode dispatch_only --variant linear  --workers 24      # dispatch alone, every lever at baseline
    python -m rl.dispatch tune  --mode joint         --variant context --workers 24      # + the rule manager's parameters
    python -m rl.dispatch eval  --workers 24                                             # held-out comparison -> dispatch.json + DISPATCH.md
    python -m rl.dispatch report                                                         # re-render DISPATCH.md from dispatch.json

The simulator's hook is `sim.set_dispatch_params` (sim/engine.py): every tick each queued patient gets a priority
index computed from what a triage desk / charge nurse can know, and the lowest index goes first. The index is

    linear   x_i . w                         50 weights (queue x triage level, time waited, arrival mode, age, ...)
    context  x_i . (w + W g)                 + tied interactions with the state of the department (11 groups x 10)
    mlp      ... + w2 . tanh(W1 [x_i, g])    + a small network on top (default 16 hidden units)

plus one switch, `unify`: one provider queue in which new patients and ready dispositions compete on the index
(instead of the provider_split lever). The four hard-coded rules are exact special cases (tests).

Search: cross-entropy method, the same shape as rl.tune: a population of candidates per (ensemble member, scenario)
group in one batch with common random numbers, the calibrated baseline on the same seeds, robust score over members.
Tuning seeds only (common.SEED_TUNE range); the held-out comparison uses seeds >= 9,000,000.

Modes
  dispatch_only  every action head at the hospital's baseline; only the dispatch index is searched. Objective
                 `patient_outcome`: mean wait, walk-outs, ESI 1-2 waiting hours and adverse events relative to the
                 baseline, with median ED length of stay and boarding not allowed to get worse. Isolates what
                 dispatch alone buys.
  dispatch_flow  as dispatch_only, but scored on the operator objective same_budget_better_flow (flow index: wait,
                 median length of stay, walk-outs, boarding; safety and cost constraints). Every lever at baseline.
  joint          dispatch index AND the rule manager's parameters, on the operator objective
                 same_budget_better_flow (rl.objectives), warm-started from the tuned rule manager.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import multiprocessing as mp
import time
from pathlib import Path

import torch

from .common import (SEED_EVAL, SEED_TUNE, calibration_status, fingerprints, get_spec, hospital_id, is_stale, load_ensemble, load_scales,
                     now_iso, paths, write_json, write_text)
from .env import HospitalEnv
from .managers import PARAM_NAMES, FixedPolicy, MultiPolicy, RulePolicy, load_manager, policy_dir, theta_from_dict
from .objectives import EPISODE_METRICS, FLOORS, LOCKED_HEADS, OPERATOR_STAGE, feasibility, operator_score, robust_aggregate

OPERATOR = "same_budget_better_flow"
SEED_DISPATCH = SEED_TUNE + 120_000              # 320,000 .. 399,999: inside the tuning range, clear of rl.tune's seeds
ACU_STATS = ["first_seen", "wait_sum_min", "seen_over_60", "lwbs", "unseen_min"]

# patient-outcome index for the dispatch-only search: weights on candidate / baseline (1.0 = the baseline)
PATIENT_INDEX = {"wait_mean_min": 0.3, "lwbs_rate": 0.2, "hi_acuity_wait_hours_per_day": 0.3, "adverse_events_per_day": 0.2}
PATIENT_GUARDS = {"ed_los_median_min": 0.0, "boarding_hours_per_day": 0.02}      # may not exceed baseline * (1 + tol)
PATIENT_PENALTY = 5.0


def _j(k):
    return EPISODE_METRICS.index(k)


def patient_index(cand: torch.Tensor, base: torch.Tensor) -> torch.Tensor:
    f = 0.0
    for k, w in PATIENT_INDEX.items():
        f = f + w * cand[..., _j(k)] / base[..., _j(k)].clamp(min=FLOORS[k])
    return f


def patient_score(cand: torch.Tensor, base: torch.Tensor) -> torch.Tensor:
    """Higher is better; 0 = the baseline. cand [..., K], base [..., K] group means."""
    pen = 0.0
    for k, tol in PATIENT_GUARDS.items():
        b = base[..., _j(k)]
        pen = pen + torch.relu(cand[..., _j(k)] - b * (1.0 + tol)) / b.clamp(min=FLOORS[k])
    return 1.0 - patient_index(cand, base) - PATIENT_PENALTY * pen


# ---------------------------------------------------------------------------------------------- the search space
@torch.no_grad()
def engine_spec(hidden: int = 0, hospital: str | None = None) -> dict:
    from sim import HospitalSim, load_scenario
    sim = HospitalSim(load_scenario("normal_week", {"hospital_id": hospital_id(hospital)}), batch_size=1, device="cpu", seed=0)
    sp = sim.dispatch_spec(hidden)
    sp["rule_theta"] = [sim.dispatch_rule_theta(r, hidden).tolist() for r in range(4)]
    sp["rules"] = list(sim.action_spec()[sim.head_names.index("priority_rule")]["options"])
    return sp


class DispatchSpace:
    """Search vector z (plain reals, one unit = "one acuity level of priority" for most entries) <-> engine parameters.

    z = [unify gene | 50 feature weights | (context) 11 groups x 10 context signals | (mlp) W1, b1, w2]
    """
    VARIANTS = ("linear", "context", "mlp")

    def __init__(self, variant: str = "linear", hidden: int = 16, hospital: str | None = None, base_rule: int | None = None, seed: int = 0):
        assert variant in self.VARIANTS
        self.variant = variant
        self.hidden = int(hidden) if variant == "mlp" else 0
        self.hospital = hospital_id(hospital)
        sp = engine_spec(self.hidden, self.hospital)
        self.spec = sp
        self.features, self.context = sp["features"], sp["context"]
        nf, ng = sp["n_features"], sp["n_context"]
        self.nf, self.ng, self.n_engine = nf, ng, sp["n_params"]
        # priority-minutes per unit of z: the three rule terms are in the rules' own units, everything else in acuity levels (60)
        self.unit = torch.tensor([1.0, 1.0, 1.0] + [60.0] * (nf - 3))
        f = self.features
        self.groups = [("queue:" + s, [i for i, n in enumerate(f) if n.startswith(s + ":")]) for s in ("bay_queue", "new_in_bay", "disposition", "scan_queue")] \
            + [("triage:" + e, [i for i, n in enumerate(f) if n.endswith(":" + e) and not n.startswith("wait_h")]) for e in ("esi1", "esi2", "esi3", "esi4", "esi5")] \
            + [("wait_min", [f.index("wait_min")]), ("lwbs_pressure", [f.index("lwbs_pressure")])]
        self.use_ctx = variant in ("context", "mlp")
        self.n_ctx = len(self.groups) * ng if self.use_ctx else 0
        self.n_mlp = (nf + ng) * self.hidden + 2 * self.hidden if self.hidden else 0
        self.nz = 1 + nf + self.n_ctx + self.n_mlp
        names = ["unify"] + list(f)
        if self.use_ctx:
            names += [f"{g}*{c}" for g, _ in self.groups for c in self.context]
        names += [f"mlp{i}" for i in range(self.n_mlp)]
        self.names = names
        if base_rule is None:
            base_rule = int({h["name"]: h["default"] for h in get_spec(hospital=self.hospital)["action_spec"]}["priority_rule"])
        self.base_rule = base_rule
        self.seed = seed

    # ---- starting point and step sizes
    def init(self, split_default: int | None = None):
        z, std = torch.zeros(self.nz), torch.zeros(self.nz)
        nf = self.nf
        z[0], std[0] = 0.5, 0.3
        rt = torch.tensor(engine_spec(0, self.hospital)["rule_theta"][self.base_rule])[:nf]
        z[1:1 + nf] = rt / self.unit
        s = torch.full((nf,), 0.3)
        s[self.features.index("cond0"):] = 0.1
        s[self.features.index("wait_min")] = 0.3
        s[self.features.index("exp_encounter_min")] = 0.3
        std[1:1 + nf] = s
        o = 1 + nf
        if self.use_ctx:
            std[o:o + self.n_ctx] = 0.3
            o += self.n_ctx
        if self.hidden:
            h, nin = self.hidden, self.nf + self.ng
            g = torch.Generator().manual_seed(1234 + self.seed)
            z[o:o + h * nin] = 0.5 * torch.randn(h * nin, generator=g)
            std[o:o + h * nin] = 0.1
            std[o + h * nin:o + h * nin + h] = 0.1
            std[o + h * nin + h:] = 0.15
        return z, std

    def extend(self, z_small: torch.Tensor, small: "DispatchSpace") -> torch.Tensor:
        """A z of a smaller variant placed into this space (same behaviour: the added terms start at zero)."""
        z, _ = self.init()
        z[:1 + self.nf] = z_small[:1 + self.nf]
        if small.use_ctx and self.use_ctx:
            z[1 + self.nf:1 + self.nf + self.n_ctx] = z_small[1 + small.nf:1 + small.nf + small.n_ctx]
        return z

    # ---- decoding
    def decode(self, z: torch.Tensor):
        """z [N, nz] -> (engine theta [N, n_engine], unify BoolTensor[N])."""
        z = z if z.dim() == 2 else z.unsqueeze(0)
        N, nf, ng = z.shape[0], self.nf, self.ng
        th = torch.zeros((N, self.n_engine))
        th[:, :nf] = z[:, 1:1 + nf] * self.unit
        o = 1 + nf
        if self.use_ctx:
            zc = z[:, o:o + self.n_ctx].reshape(N, len(self.groups), ng)
            W = torch.zeros((N, nf, ng))
            for gi, (_, idx) in enumerate(self.groups):
                for i in idx:
                    W[:, i, :] += zc[:, gi, :] * float(self.unit[i])
            th[:, nf:nf + nf * ng] = W.reshape(N, -1)
            o += self.n_ctx
        if self.hidden:
            h, nin = self.hidden, nf + ng
            e = nf + nf * ng
            th[:, e:e + h * nin + h] = z[:, o:o + h * nin + h]
            th[:, e + h * nin + h:] = z[:, o + h * nin + h:] * 60.0
        return th, z[:, 0] > 0.5


def pad_engine(theta: torch.Tensor, hidden_from: int, hidden_to: int, hospital=None) -> torch.Tensor:
    """Engine parameters of a smaller network padded with zeros (the extra network outputs nothing)."""
    n_to = engine_spec(hidden_to, hospital)["n_params"]
    out = torch.zeros((theta.shape[0], n_to))
    n_lin = engine_spec(0, hospital)["n_params"]
    out[:, :n_lin] = theta[:, :n_lin]
    if hidden_from and hidden_from == hidden_to:
        out[:, n_lin:] = theta[:, n_lin:]
    elif hidden_from:
        raise ValueError("cannot mix two different hidden sizes in one batch")
    return out


class DispatchPolicy:
    """A saved learned dispatch policy: a manager for the 22 levers (the baseline, or rule parameters) plus the
    dispatch index. `apply(sim, rows)` installs the index; `manager()` is the lever policy."""
    kind = "learned_dispatch"

    def __init__(self, d: dict):
        self.d = d
        self.id, self.label, self.hospital = d["id"], d["label"], d.get("hospital_id")
        self.hidden = int(d["dispatch"]["hidden"])
        self.theta = torch.tensor(d["dispatch"]["engine_theta"], dtype=torch.float32)
        self.unify = bool(d["dispatch"]["unify"])
        self.rule_params = d.get("rule_params")
        self.stale = is_stale(d, self.hospital)

    @classmethod
    def load(cls, path) -> "DispatchPolicy":
        return cls(json.loads(Path(path).read_text()))

    def manager(self):
        if self.rule_params:
            return RulePolicy(self.rule_params, id=self.id, kind=self.kind, label=self.label, stage=self.d.get("stage", OPERATOR_STAGE),
                              hospital=self.hospital, locked=self.d.get("locked_heads") or ())
        return FixedPolicy(hospital=self.hospital)

    def apply(self, sim, active=None):
        sim.set_dispatch_params(self.theta, hidden=self.hidden, active=active, unify=self.unify)

    def block(self) -> dict:
        b = dict(name=self.id, disp=[self.theta.tolist()], unify=[self.unify], hidden=self.hidden)
        if self.rule_params:
            b["rule"] = [theta_from_dict(self.rule_params).tolist()]
        return b


# ---------------------------------------------------------------------------------------------- batched rollouts
def make_task(hospital, scenario, member, blocks, seeds, days, stage=OPERATOR_STAGE, locked=LOCKED_HEADS, scales=None, tag=None, threads=1):
    """blocks: list of arm blocks, each a dict
         name       label (a population gets name#i)
         manager    manager id (default "fixed"), or
         rule       [[31 rule parameters] x N]            a population of rule managers
         disp       [[engine dispatch parameters] x N]    learned dispatch rows (absent: the priority_rule head decides)
         unify      [bool x N] or bool
         hidden     hidden units of `disp` rows (0 = linear / context)
         overrides  {head: option index}                  forced every hour (e.g. priority_rule, provider_split)"""
    return dict(hospital=hospital, scenario=scenario, member=member, blocks=blocks, seeds=[int(s) for s in seeds], days=int(days), stage=stage,
                locked=list(locked or ()), scales=scales, tag=tag, threads=int(threads))


def _block_n(b: dict) -> int:
    if b.get("rule") is not None:
        return len(b["rule"])
    if b.get("disp") is not None:
        return len(b["disp"])
    return 1


@torch.no_grad()
def run_task(task: dict) -> dict:
    """-> episode [M, n_seeds, K] (EPISODE_METRICS), acuity [M, n_seeds, len(ACU_STATS), 6], names [M]."""
    t0 = time.time()
    torch.set_num_threads(max(1, int(task.get("threads", 1))))
    h, seeds, n = task["hospital"], task["seeds"], len(task["seeds"])
    stage, locked = task.get("stage", OPERATOR_STAGE), task.get("locked") or ()
    pols, sizes, names = [], [], []
    hidden = max([int(b.get("hidden", 0)) for b in task["blocks"] if b.get("disp") is not None] or [0])
    for b in task["blocks"]:
        N = _block_n(b)
        if b.get("rule") is not None:
            th = torch.as_tensor(b["rule"], dtype=torch.float32)
            pols.append(RulePolicy(th.repeat_interleave(n, 0), stage=stage, hospital=h, locked=locked))
        else:
            pols.append(load_manager(b.get("manager", "fixed"), "cpu", hospital=h))
        sizes.append(N * n)
        names += [b.get("name", "arm")] if N == 1 else [f"{b.get('name', 'arm')}#{i}" for i in range(N)]
    M = len(names)
    scales = task.get("scales") or load_scales(hospital=h)
    env = HospitalEnv(task["scenario"], M * n, "cpu", torch.tensor(seeds).repeat(M), task["days"] * 24, stage=stage, weights={}, scales=scales,
                      auto_reset=False, hospital=h, member=task.get("member"), locked_heads=locked)
    sim = env.sim
    n_eng = sim.dispatch_spec(hidden)["n_params"]
    theta = torch.zeros((M * n, n_eng))
    active = torch.zeros((M * n,), dtype=torch.bool)
    unify = torch.zeros((M * n,), dtype=torch.bool)
    forced, o = [], 0
    for b, sz in zip(task["blocks"], sizes):
        sl = slice(o, o + sz)
        if b.get("disp") is not None:
            th = torch.as_tensor(b["disp"], dtype=torch.float32)
            if th.shape[1] != n_eng:
                th = pad_engine(th, int(b.get("hidden", 0)), hidden, h)
            theta[sl] = th.repeat_interleave(n, 0)
            active[sl] = True
            u = b.get("unify", False)
            u = torch.as_tensor(u).bool().reshape(-1)
            unify[sl] = (u if u.numel() > 1 else u.expand(th.shape[0])).repeat_interleave(n, 0)
        for head, v in (b.get("overrides") or {}).items():
            forced.append((sl, head, int(v)))
        o += sz
    if bool(active.any()):
        sim.set_dispatch_params(theta, hidden=hidden, active=active, unify=unify)
    sim.enable_acuity_stats(True)
    mp_ = MultiPolicy(pols, sizes)
    mp_.reset(env.B, env.device, env.default_actions())
    obs = env.reset()
    info = {}
    for _ in range(task["days"] * 24):
        acts = mp_.act(obs, env.action_mask())
        for sl, head, v in forced:
            acts[head][sl] = v
        obs, _, _, info = env.step(acts)
    acu = torch.stack([sim.acu_stats[k] for k in ACU_STATS], 1).to(torch.float32)
    return dict(tag=task.get("tag"), scenario=task["scenario"], member=task.get("member"), names=names, seconds=time.time() - t0,
                episode=info["episode"].reshape(M, n, len(EPISODE_METRICS)).cpu(), acuity=acu.reshape(M, n, len(ACU_STATS), 6).cpu(),
                invalid=info["invalid_actions"].float().reshape(M, n).cpu())


class Pool:
    """Persistent single-thread worker processes (the simulator is latency-bound: many small batches beat one big one)."""

    def __init__(self, workers: int = 0):
        self.workers = int(workers)
        self.ex = cf.ProcessPoolExecutor(self.workers, mp_context=mp.get_context("spawn")) if self.workers > 0 else None

    def map(self, tasks: list[dict]) -> list[dict]:
        if self.ex is None:
            return [run_task(t) for t in tasks]
        futs = [self.ex.submit(run_task, t) for t in tasks]
        return [f.result() for f in futs]

    def close(self):
        if self.ex is not None:
            self.ex.shutdown(wait=False, cancel_futures=True)


def split_blocks(pop: dict, N: int, chunk: int) -> list[dict]:
    """One population block cut into pieces of at most `chunk` candidates."""
    out = []
    for a in range(0, N, chunk):
        b = dict(pop)
        for k in ("rule", "disp", "unify"):
            if isinstance(pop.get(k), list):
                b[k] = pop[k][a:a + chunk]
        out.append(b)
    return out


def evaluate_population(pool: Pool, pop: dict, N: int, mode: str, hospital: str, scenarios, members, seeds, days, scales, chunk: int = 8,
                        quantile: float = 0.25, detail: bool = False):
    """Score N candidates (one arm block `pop`) against the baseline on the same seeds. -> score [N], mean metrics [N, K]."""
    pieces = split_blocks(pop, N, chunk)
    tasks = []
    for m in members:
        for s in scenarios:
            for j, pc in enumerate(pieces):
                blocks = ([dict(name="fixed", manager="fixed")] if j == 0 else []) + [pc]
                tasks.append(make_task(hospital, s, m, blocks, seeds, days, scales=scales, tag=f"{s}/m{m}/{j}"))
    raw = pool.map(tasks)
    per_member, cand_all, groups, i = [], [], [], 0
    for m in members:
        sc_m = []
        for s in scenarios:
            part = raw[i:i + len(pieces)]
            i += len(pieces)
            ep = torch.cat([x["episode"] for x in part], 0)               # [1 + N, n_seeds, K]
            base, cand = ep[0].mean(0), ep[1:].mean(1)
            sc = patient_score(cand, base.unsqueeze(0)) if mode == "dispatch_only" else operator_score(OPERATOR, cand, base.unsqueeze(0), margin=True)   # dispatch_flow, joint: the operator objective
            sc_m.append(sc)
            cand_all.append(cand)
            groups.append(dict(member=m, scenario=s, base=base, cand=cand))
        per_member.append(torch.stack(sc_m).mean(0))
    score = robust_aggregate(torch.stack(per_member, -1), quantile)
    mean = torch.stack(cand_all).mean(0)
    return (score, mean, groups) if detail else (score, mean)


# ---------------------------------------------------------------------------------------------- tuner
def tuned_rule_theta(hospital: str):
    """The tuned rule manager for the operator objective, when it exists for the current calibration."""
    f = policy_dir(hospital) / "tuned_same_budget.json"
    if not f.exists():
        return None, "missing"
    d = json.loads(f.read_text())
    return theta_from_dict(d["params"]), ("stale" if is_stale(d, hospital) else "current")


def tune(a) -> dict:
    h = hospital_id(a.hospital)
    run = Path(a.run or f"runs/{h}/dispatch_{a.mode}_{a.variant}")
    run.mkdir(parents=True, exist_ok=True)
    out = Path(a.out or policy_dir(h) / f"dispatch_{a.mode}_{a.variant}.json")
    scales = load_scales(hospital=h)
    ens = load_ensemble(h)
    n_mem = len(ens["members"])
    all_members = list(range(n_mem)) if ens["exists"] else [None]
    g = torch.Generator().manual_seed(a.seed)
    space = DispatchSpace(a.variant, a.hidden, h, seed=a.seed)
    z0, zstd = space.init()
    init_note = "the hospital's baseline priority rule"
    if a.init and Path(a.init).exists():
        d0 = json.loads(Path(a.init).read_text())
        small = DispatchSpace(d0["dispatch"]["variant"], d0["dispatch"]["hidden"], h)
        z_small = torch.tensor(d0["dispatch"]["z"])
        z0 = z_small.clone() if (small.variant == space.variant and small.hidden == space.hidden) else space.extend(z_small, small)
        zstd[:1 + space.nf] *= a.init_shrink
        zstd[0] = 0.15
        init_note = f"warm start from {a.init}"
    joint = a.mode == "joint"
    R = len(PARAM_NAMES) if joint else 0
    if joint:
        rt, status = tuned_rule_theta(h)
        if rt is None:
            from .tune import baseline_theta
            rt = baseline_theta(h)
        if a.init and Path(a.init).exists() and json.loads(Path(a.init).read_text()).get("rule_params"):
            rt = theta_from_dict(json.loads(Path(a.init).read_text())["rule_params"])
        init_note += f"; rule parameters from tuned_same_budget ({status})"
        mean = torch.cat([rt, z0])
        std = torch.cat([torch.full((R,), a.rule_std), zstd])
    else:
        mean, std = z0.clone(), zstd.clone()
    init_mean = mean.clone()
    D = mean.shape[0]
    lo = torch.cat([torch.zeros(R), torch.full((space.nz,), -1e9)])
    hi = torch.cat([torch.ones(R), torch.full((space.nz,), 1e9)])
    min_std = torch.cat([torch.full((R,), 0.01), torch.full((space.nz,), a.min_std)])
    log = open(run / "log.txt", "a")

    def say(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    def block(c: torch.Tensor) -> dict:
        th, un = space.decode(c[:, R:])
        b = dict(name="cand", disp=th.tolist(), unify=un.tolist(), hidden=space.hidden)
        if joint:
            b["rule"] = c[:, :R].tolist()
        return b

    def members_for():
        if all_members == [None]:
            return [None]
        others = [m for m in all_members if m != 0]
        return [0] + [others[i] for i in torch.randperm(len(others), generator=g)[:min(a.members_per_gen, n_mem) - 1].tolist()]

    pool = Pool(a.workers)
    kw = dict(mode=a.mode, hospital=h, scales=scales, chunk=a.chunk, quantile=a.quantile)
    say(f"[{now_iso()}] dispatch tune mode={a.mode} variant={a.variant} hidden={space.hidden} dims={D} (rule {R} + dispatch {space.nz}) pop={a.pop} "
        f"elite={a.elite} gens={a.gens} seeds={a.seeds} days={a.days} members/gen={a.members_per_gen} of {n_mem} scen={a.scenarios} init: {init_note} "
        f"calibration={calibration_status(h)['calibration_fingerprint']}")
    hist, el, best_seen = [], mean.unsqueeze(0), mean.clone()
    state_f = run / "state.json"
    gen0 = 0
    if a.resume and state_f.exists():
        st = json.loads(state_f.read_text())
        if len(st["mean"]) == D:
            mean, std, hist, el = torch.tensor(st["mean"]), torch.tensor(st["std"]), st["hist"], torch.tensor(st["elite"])
            best_seen, gen0 = torch.tensor(st["best_seen"]), len(hist)
            say(f"resumed at generation {gen0}")
    try:
        for gen in range(gen0, a.gens):
            t0 = time.time()
            cand = mean + std * torch.randn((a.pop, D), generator=g)
            cand = torch.minimum(torch.maximum(cand, lo), hi)
            cand[0], cand[1], cand[2] = mean, best_seen, init_mean            # distribution mean, incumbent and the start: re-scored on fresh seeds
            mem = members_for()
            seeds = [SEED_DISPATCH + a.seed_block * 10_000 + gen * 50 + i for i in range(a.seeds)]
            sc, mm = evaluate_population(pool, block(cand), a.pop, scenarios=a.scenarios, members=mem, seeds=seeds, days=a.days, **kw)
            order = torch.argsort(sc, descending=True)
            el = cand[order[:a.elite]]
            best_seen = cand[order[0]].clone()
            mean = a.smooth * el.mean(0) + (1 - a.smooth) * mean
            std = torch.maximum(a.smooth * el.std(0) + (1 - a.smooth) * std, min_std)
            b = int(order[0])
            rec = dict(gen=gen, best=float(sc[b]), mean_cand=float(sc[0]), incumbent=float(sc[1]), init=float(sc[2]), pop_mean=float(sc.mean()),
                       seconds=time.time() - t0, members=mem, best_summary={k: float(mm[b, j]) for j, k in enumerate(EPISODE_METRICS)})
            hist.append(rec)
            bs = rec["best_summary"]
            say(f"gen {gen} best {rec['best']:+.4f} mean {rec['mean_cand']:+.4f} incumbent {rec['incumbent']:+.4f} init {rec['init']:+.4f} "
                f"pop {rec['pop_mean']:+.4f} | wait {bs['wait_mean_min']:.1f} p95 {bs['wait_p95_min']:.0f} los {bs['ed_los_median_min']:.0f} "
                f"lwbs {bs['lwbs_rate']:.4f} hi {bs['hi_acuity_wait_hours_per_day']:.2f} adv {bs['adverse_events_per_day']:.2f} members {mem} "
                f"({rec['seconds']:.0f}s)")
            write_json(state_f, dict(mean=mean.tolist(), std=std.tolist(), hist=hist, elite=el.tolist(), best_seen=best_seen.tolist()))
        # final round: fresh tuning seeds, more members; the distribution mean, the last elites and the starting point
        fin = torch.cat([mean.unsqueeze(0), el[:a.final_elites], init_mean.unsqueeze(0)], 0)
        fm = all_members if all_members == [None] else all_members[:max(1, a.final_members)]
        seeds = [SEED_DISPATCH + 70_000 + a.seed_block * 100 + i for i in range(a.final_seeds)]
        sc, mm, groups = evaluate_population(pool, block(fin), fin.shape[0], scenarios=a.scenarios, members=fm, seeds=seeds, days=a.final_days,
                                             detail=True, **kw)
    finally:
        pool.close()
    b = int(torch.argmax(sc))
    say(f"final round scores {['%+.4f' % float(x) for x in sc]} -> pick {b} (last entry = the starting point)")
    th, un = space.decode(fin[b:b + 1, R:])
    feas = None
    if a.mode != "dispatch_only":
        feas = []
        for gr in groups:
            cd = {k: float(gr["cand"][b, j]) for j, k in enumerate(EPISODE_METRICS)}
            bd = {k: float(gr["base"][j]) for j, k in enumerate(EPISODE_METRICS)}
            f = feasibility(OPERATOR, cd, bd)
            feas.append(dict(member=gr["member"], scenario=gr["scenario"], feasible=f["feasible"], violated=f["violated"]))
    pid = f"dispatch_{a.mode}_{a.variant}"
    lab = {"dispatch_only": "Learned dispatch (who is seen next), every lever at current practice",
           "dispatch_flow": "Learned dispatch tuned on the flow objective, every lever at current practice",
           "joint": "Learned dispatch + tuned rule manager: same budget, better flow"}[a.mode]
    d = dict(id=pid, kind="learned_dispatch", type="dispatch", label=f"{lab} [{a.variant} index]", mode=a.mode,
             objective=("patient_outcome" if a.mode == "dispatch_only" else OPERATOR), stage=OPERATOR_STAGE, locked_heads=list(LOCKED_HEADS),
             rule_params=({k: round(float(v), 4) for k, v in zip(PARAM_NAMES, fin[b, :R])} if joint else None),
             dispatch=dict(variant=a.variant, hidden=space.hidden, unify=bool(un[0]), z=fin[b, R:].tolist(), z_names=space.names,
                           engine_theta=th[0].tolist(), features=space.features, context=space.context,
                           unit_priority_minutes=space.unit.tolist()),
             note="A per-patient priority index found by direct policy search (cross-entropy method). It uses only what a triage desk can know. "
                  "All numbers simulated.",
             **fingerprints(h), synthetic=True,
             tuning=dict(method="cross-entropy method, common random numbers per (ensemble member, scenario) group, baseline rows on the same seeds, "
                                "robust score over members", mode=a.mode, dims=D, pop=a.pop, elite=a.elite, gens=a.gens, seeds_per_group=a.seeds,
                         days=a.days, members_per_gen=a.members_per_gen, final_members=fm, final_seeds=a.final_seeds, final_days=a.final_days,
                         scenarios=a.scenarios, init=init_note, seed_range=[SEED_DISPATCH, SEED_DISPATCH + 79_999], final_scores=[float(x) for x in sc],
                         picked=b, start_score=float(sc[-1]), final_score=float(sc[b]), final_feasibility=feas,
                         final_summary={k: float(mm[b, j]) for j, k in enumerate(EPISODE_METRICS)},
                         start_summary={k: float(mm[-1, j]) for j, k in enumerate(EPISODE_METRICS)},
                         patient_index=PATIENT_INDEX, patient_guards=PATIENT_GUARDS, history=hist, finished=now_iso()))
    write_json(out, d, indent=1)
    say(f"saved {out}")
    return d


# ---------------------------------------------------------------------------------------------- held-out evaluation
REPORT = [("wait_mean_min", "Mean door-to-provider wait", "min", 1.0, 1), ("wait_p95_min", "95th-percentile wait", "min", 1.0, 0),
          ("ed_los_median_min", "Median ED length of stay", "min", 1.0, 0), ("ed_los_mean_min", "Mean ED length of stay", "min", 1.0, 0),
          ("ed_patient_hours_per_day", "ED census (patient-hours per day)", "patient-h/day", 1.0, 0), ("lwbs_rate", "Left without being seen", "% of arrivals", 100.0, 2),
          ("hi_acuity_wait_hours_per_day", "ESI 1-2 waiting (hourly census)", "patient-h/day", 1.0, 2),
          ("deaths_per_10k", "Deaths", "per 10,000 arrivals", 1.0, 2), ("adverse_events_per_day", "Adverse events", "per day", 1.0, 2),
          ("boarding_hours_per_day", "Boarding", "patient-h/day", 1.0, 1), ("labor_cost_per_day", "Labour cost", "$k/day", 1e-3, 2)]
ACU_REPORT = [(f"wait_esi{e}_min", f"Mean wait, triage ESI {e}", "min", 1.0, 1) for e in range(1, 6)] \
    + [("unseen_h_esi12", "ESI 1-2 waiting (per tick)", "patient-h/day", 1.0, 2), ("unseen_h_esi3", "ESI 3 waiting", "patient-h/day", 1.0, 1),
       ("unseen_h_esi45", "ESI 4-5 waiting", "patient-h/day", 1.0, 1)] \
    + [(f"lwbs_esi{e}_per_day", f"Walk-outs, triage ESI {e}", "per day", 1.0, 2) for e in (3, 4, 5)]
ALL_METRICS = [r[0] for r in REPORT] + [r[0] for r in ACU_REPORT] + ["patient_index", "flow_index"]


def acuity_metrics(acu: torch.Tensor, days: int) -> dict:
    """acu [..., len(ACU_STATS), 6] -> name -> [...]."""
    s = {k: acu[..., i, :] for i, k in enumerate(ACU_STATS)}
    out = {}
    for e in range(1, 6):
        out[f"wait_esi{e}_min"] = s["wait_sum_min"][..., e] / s["first_seen"][..., e].clamp(min=1.0)
        out[f"lwbs_esi{e}_per_day"] = s["lwbs"][..., e] / days
    out["unseen_h_esi12"] = s["unseen_min"][..., 1:3].sum(-1) / 60.0 / days
    out["unseen_h_esi3"] = s["unseen_min"][..., 3] / 60.0 / days
    out["unseen_h_esi45"] = s["unseen_min"][..., 4:6].sum(-1) / 60.0 / days
    return out


def arm_values(ep: torch.Tensor, acu: torch.Tensor, base_ep: torch.Tensor, days: int) -> dict:
    """Per-episode values of every reported metric for one arm. ep [Mm, S, K]; base_ep the baseline on the same episodes."""
    from .objectives import flow_index
    v = {k: ep[..., _j(k)] for k, *_ in REPORT}
    v.update(acuity_metrics(acu, days))
    # indices are ratios of GROUP means (member x scenario), repeated over seeds only for shape
    bm, cm = base_ep.mean(1, keepdim=True), ep.mean(1, keepdim=True)
    v["patient_index"] = patient_index(cm, bm).expand(ep.shape[:2])
    v["flow_index"] = flow_index(cm, bm).expand(ep.shape[:2])
    return v


def paired(a: torch.Tensor, b: torch.Tensor, reps: int = 2000, seed: int = 0) -> dict:
    """a, b [Mm, S] on the same episodes. Mean of each, paired difference a - b with a 95% interval: two-way bootstrap
    over ensemble members and seeds (the same scheme as rl.headline), and how many members agree in sign."""
    d = a - b
    Mm, S = d.shape
    g = torch.Generator().manual_seed(seed)
    mi = torch.randint(0, Mm, (reps, Mm), generator=g) if Mm > 1 else torch.zeros((reps, 1), dtype=torch.long)
    si = torch.randint(0, S, (reps, S), generator=g)
    bm = d[mi.unsqueeze(2), si.unsqueeze(1)].mean((1, 2))
    lo, hi = torch.quantile(bm, torch.tensor([0.025, 0.975])).tolist()
    pm = d.mean(1)
    return dict(a=float(a.mean()), b=float(b.mean()), diff=float(d.mean()), lo=lo, hi=hi, rel=(float(d.mean() / b.mean()) if float(b.mean()) else None),
                members_lower=int((pm < 0).sum()), members_higher=int((pm > 0).sum()), n_members=Mm, n_seeds=S,
                significant=bool(lo > 0 or hi < 0))


def default_arms(h: str, policy_files: list[Path]) -> tuple[list[dict], dict]:
    """Every arm of the held-out comparison, and notes about them."""
    sp = engine_spec(0, h)
    spec = get_spec(hospital=h)["action_spec"]
    splits = next(x for x in spec if x["name"] == "provider_split")["options"]
    arms = [dict(name="fixed", manager="fixed")]
    for r, rn in enumerate(sp["rules"]):
        for s, sn in enumerate(splits):
            arms.append(dict(name=f"rule:{rn}+{sn}", manager="fixed", overrides={"priority_rule": r, "provider_split": s}))
    notes = dict(rules=sp["rules"], splits=list(splits))
    rt, status = tuned_rule_theta(h)
    notes["tuned_same_budget"] = status
    if rt is not None:
        arms.append(dict(name="tuned_same_budget", manager="tuned_same_budget"))
    for f in policy_files:
        p = DispatchPolicy.load(f)
        arms.append(p.block())
        notes[p.id] = dict(file=str(f), stale=p.stale, mode=p.d.get("mode"), variant=p.d["dispatch"]["variant"], unify=p.unify)
        if p.rule_params:
            # ablations: the joint policy's levers with the hard-coded queue rule those levers ask for (no learned index), and the
            # learned index transplanted onto the tuned rule manager's levers
            arms.append(dict(name=f"ablate:{p.id}:levers_only", rule=[theta_from_dict(p.rule_params).tolist()]))
            if rt is not None:
                arms.append(dict(name=f"ablate:{p.id}:index_on_tuned", rule=[rt.tolist()], disp=[p.theta.tolist()], unify=[p.unify], hidden=p.hidden))
    return arms, notes


def evaluate(a) -> dict:
    h = hospital_id(a.hospital)
    home = paths(h).home
    files = [Path(f) for f in (a.policies or sorted(policy_dir(h).glob("dispatch_*.json")))]
    arms, notes = default_arms(h, files)
    scales = load_scales(hospital=h)
    ens = load_ensemble(h)
    members = list(range(len(ens["members"])))[:a.members] if ens["exists"] else [None]
    seeds = [SEED_EVAL + a.seed_offset + i for i in range(a.seeds)]
    names = [x["name"] for x in arms]
    print(f"[{now_iso()}] held-out evaluation: {len(arms)} arms x {len(seeds)} seeds x {a.days} days x {len(members)} members x {a.scenarios}", flush=True)
    tasks = []
    for s in a.scenarios:
        for m in members:
            for j in range(0, len(arms), a.chunk):
                tasks.append(make_task(h, s, m, arms[j:j + a.chunk], seeds, a.days, scales=scales, tag=f"{s}/m{m}/{j}"))
    pool = Pool(a.workers)
    t0 = time.time()
    try:
        raw = pool.map(tasks)
    finally:
        pool.close()
    print(f"  {len(tasks)} tasks in {time.time() - t0:.0f}s", flush=True)
    data, i, per = {}, 0, math.ceil(len(arms) / a.chunk)
    for s in a.scenarios:
        ep, ac = [], []
        for m in members:
            part = raw[i:i + per]
            i += per
            ep.append(torch.cat([x["episode"] for x in part], 0))
            ac.append(torch.cat([x["acuity"] for x in part], 0))
        data[s] = dict(episode=torch.stack(ep, 1), acuity=torch.stack(ac, 1))            # [arms, members, seeds, ...]
    write_json(home / "dispatch_raw.json", dict(names=names, members=members, seeds=seeds, days=a.days, scenarios=a.scenarios,
                                                 episode_metrics=EPISODE_METRICS, acu_stats=ACU_STATS,
                                                 data={s: {k: v.tolist() for k, v in d.items()} for s, d in data.items()}))
    R = summarise(h, names, notes, members, seeds, a.days, a.scenarios, data)
    if a.anatomy:
        R["queue_anatomy"] = {"fixed (baseline)": queue_anatomy(h, a.scenarios, members, 4, 14)}
        flow = [f for f in files if "dispatch_flow" in f.name]
        if flow:
            pol = DispatchPolicy.load(flow[0])
            R["queue_anatomy"][f"{pol.id} (baseline levers)"] = queue_anatomy(h, a.scenarios, members, 4, 14, policy=pol)
    write_json(home / "dispatch.json", R, indent=1)
    write_markdown(R, home / "DISPATCH.md")
    print(f"wrote {home / 'dispatch.json'} and {home / 'DISPATCH.md'}", flush=True)
    return R


def summarise(h, names, notes, members, seeds, days, scenarios, data) -> dict:
    ix = {n: i for i, n in enumerate(names)}
    rule_arms = [n for n in names if n.startswith("rule:")]
    learned = [n for n in names if n.startswith("dispatch_")]
    only = [n for n in learned if "dispatch_only" in n or "dispatch_flow" in n]
    joint = [n for n in learned if "joint" in n]
    out = dict(generated=now_iso(), synthetic=True, **fingerprints(h),
               protocol=dict(seeds=[seeds[0], seeds[-1]], n_seeds=len(seeds), days=days, members=members, scenarios=scenarios,
                             pairing="every arm runs the same seeds in the same ensemble member; differences are paired per episode",
                             interval="95% two-way bootstrap over ensemble members and seeds",
                             patient_index=PATIENT_INDEX, patient_guards=PATIENT_GUARDS),
               arms=names, notes=notes, scenarios={})
    vals = {}
    for s in scenarios:
        ep, ac = data[s]["episode"], data[s]["acuity"]
        vals[s] = {n: arm_values(ep[ix[n]], ac[ix[n]], ep[ix["fixed"]], days) for n in names}
    pooled = {n: {k: torch.cat([vals[s][n][k] for s in scenarios], 1) for k in ALL_METRICS} for n in names}

    # the best hard-coded rule: lowest patient index pooled over scenarios (chosen on these held-out episodes, which favours the rules)
    def pidx(n):
        return float(sum(vals[s][n]["patient_index"].mean() for s in scenarios) / len(scenarios))

    def fidx(n):
        return float(sum(vals[s][n]["flow_index"].mean() for s in scenarios) / len(scenarios))
    base_split = notes["splits"][int({x["name"]: x["default"] for x in get_spec(hospital=h)["action_spec"]}["provider_split"])]
    same_split = [n for n in rule_arms if n.endswith("+" + base_split)]
    best_rule_same = min(same_split, key=pidx)
    best_rule_any = min(rule_arms, key=pidx)

    def oscore(n, s_=None):          # operator score on held-out group means, no tuning margin: mean over members (and scenarios)
        ss = [s_] if s_ else scenarios
        return float(sum(operator_score(OPERATOR, data[s]["episode"][ix[n]].mean(1), data[s]["episode"][ix["fixed"]].mean(1), margin=False).mean()
                         for s in ss) / len(ss))
    best_rule_flow = max(rule_arms, key=oscore)
    out["best_rule"] = dict(same_split=best_rule_same, any_split=best_rule_any, any_split_by_flow_index=best_rule_flow,
                            baseline_split=base_split, patient_index={n: pidx(n) for n in rule_arms}, flow_index={n: fidx(n) for n in rule_arms},
                            operator_score={n: oscore(n) for n in rule_arms},
                            note="picked on the held-out episodes themselves, which favours the hard-coded rules")
    comps = []
    for n in learned:
        if "dispatch_only" in n:
            comps += [(n, "fixed"), (n, best_rule_same), (n, best_rule_any)]
        else:
            comps += [(n, "fixed"), (n, best_rule_flow)] + ([(n, "tuned_same_budget")] if "tuned_same_budget" in ix else [])
    for n in names:
        if n.startswith("ablate:") and n.endswith(":levers_only"):
            comps.append((n.split(":")[1], n))                      # joint policy minus its own levers without the learned index
        if n.startswith("ablate:") and n.endswith(":index_on_tuned"):
            comps.append((n, "tuned_same_budget"))                  # tuned levers with the learned index minus tuned levers
    if "tuned_same_budget" in ix:
        comps.append(("tuned_same_budget", "fixed"))
    comps += [(best_rule_same, "fixed"), (best_rule_any, "fixed"), (best_rule_flow, "fixed")]
    comps = list(dict.fromkeys(c for c in comps if c[0] != c[1]))
    for s in scenarios + ["pooled"]:
        V = pooled if s == "pooled" else vals[s]
        blk = dict(means={n: {k: float(V[n][k].mean()) for k in ALL_METRICS} for n in names}, comparisons=[])
        for a_, b_ in comps:
            blk["comparisons"].append(dict(a=a_, b=b_, metrics={k: paired(V[a_][k], V[b_][k]) for k in ALL_METRICS if k not in ("patient_index", "flow_index")},
                                           patient_index=dict(a=float(V[a_]["patient_index"].mean()), b=float(V[b_]["patient_index"].mean())),
                                           flow_index=dict(a=float(V[a_]["flow_index"].mean()), b=float(V[b_]["flow_index"].mean()))))
        if s != "pooled":
            ep = data[s]["episode"]
            feas = {}
            for n in learned + [x for x in names if x.startswith("ablate:")] + rule_arms + (["tuned_same_budget"] if "tuned_same_budget" in ix else []):
                cm, bm = ep[ix[n]].mean((0, 1)), ep[ix["fixed"]].mean((0, 1))
                f = feasibility(OPERATOR, {k: float(cm[j]) for j, k in enumerate(EPISODE_METRICS)}, {k: float(bm[j]) for j, k in enumerate(EPISODE_METRICS)})
                per_m = operator_score(OPERATOR, ep[ix[n]].mean(1), ep[ix["fixed"]].mean(1), margin=False)
                feas[n] = dict(feasible=f["feasible"], violated=f["violated"], score=float(operator_score(OPERATOR, cm, bm, margin=False)),
                               score_members_mean=float(per_m.mean()), score_per_member=[float(x) for x in per_m],
                               members_feasible=int(sum(feasibility(OPERATOR, {k: float(ep[ix[n]][mi].mean(0)[j]) for j, k in enumerate(EPISODE_METRICS)},
                                                                    {k: float(ep[ix["fixed"]][mi].mean(0)[j]) for j, k in enumerate(EPISODE_METRICS)})["feasible"]
                                                        for mi in range(ep.shape[1]))))
            blk["operator"] = feas
            # per-member patient index of each learned arm against the best rule
            show_m = list(dict.fromkeys(learned + [best_rule_same, best_rule_any, best_rule_flow] + (["tuned_same_budget"] if "tuned_same_budget" in ix else [])))
            blk["per_member_patient_index"] = {n: [float(x) for x in vals[s][n]["patient_index"][:, 0]] for n in show_m}
            blk["per_member_flow_index"] = {n: [float(x) for x in vals[s][n]["flow_index"][:, 0]] for n in show_m}
        out["scenarios"][s] = blk
    out["feature_tables"] = {}
    for n in learned:
        f = notes[n]["file"]
        out["feature_tables"][n] = feature_table(json.loads(Path(f).read_text()))
    out["verdict"] = verdict(out)
    out["would_need"] = WOULD_NEED
    return out


WOULD_NEED = [
    "Individual providers. Providers are a head-count per pool, identical and interchangeable; any free provider takes any patient and any "
    "disposition. Matching needs provider-level skill or speed differences (attending / resident / APP), specialty fit by condition group, and "
    "continuity (the provider who saw the patient does the re-evaluation faster than a colleague).",
    "Patient features that predict something. Condition group, age band and arrival mode change no service time, hazard or patience in the model; "
    "within a triage level every patient is statistically the same except for time already waited. An index over (queue, triage level, wait) is "
    "therefore already sufficient. Needed: service time, test need, admission probability and deterioration risk that depend on condition, age "
    "and vitals, so that two ESI-3 patients genuinely differ.",
    "Signals that arrive while waiting. The only thing that changes for a queued patient is the clock and a rare deterioration flag. Needed: "
    "repeat vitals, results coming back, a nurse's concern flag, detectable mis-triage.",
    "A binding bay decision. In the calibrated twin the bay queue is empty almost all the time, and bay eligibility is a fixed cascade (resus, "
    "peds, fast track, main, hallway). Needed: scarce bays with mismatch costs (monitored vs unmonitored, isolation, a resus bay held back for "
    "the next ambulance), so that giving a bay to one patient has an opportunity cost.",
    "Work that can be batched or sequenced. Imaging is one patient per scanner with independent durations; labs are independent draws. Needed: "
    "transport batching, scanner set-up times by study type, provider rounds (several dispositions in one pass), parallel work-ups.",
    "Consequences of waiting that depend on who waits. Walk-out patience in the calibration is very long (catalog means of many hours) and the "
    "hazards before first contact act over a wait of about a quarter of an hour, so re-ordering barely moves walk-outs or harm. Needed: "
    "calibrated patience and time-critical conditions (door-to-ECG, stroke and sepsis windows) with outcomes that depend on minutes.",
    "A contended front door. About 80% of the time before first provider contact is triage service and walking, which no ordering can change, "
    "and triage itself is first-come-first-served because acuity is not known before it. Needed: a twin whose provider queue is actually long "
    "at peak (or a triage-desk decision such as quick-look acuity or split-flow streaming).",
]


def verdict(R: dict) -> list[str]:
    """Plain statements read off the held-out comparisons (pooled over scenarios unless said)."""
    out = []
    key = [("wait_mean_min", "mean wait", "min", 1.0), ("wait_p95_min", "95th-percentile wait", "min", 1.0), ("ed_los_median_min", "median ED length of stay", "min", 1.0),
           ("ed_los_mean_min", "mean ED length of stay", "min", 1.0),
           ("lwbs_rate", "walk-outs", "% of arrivals", 100.0), ("unseen_h_esi12", "ESI 1-2 waiting", "patient-h/day", 1.0),
           ("adverse_events_per_day", "adverse events", "/day", 1.0), ("deaths_per_10k", "deaths", "/10k", 1.0)]

    def line(c):
        parts = []
        for k, lab, unit, sc in key:
            m = c["metrics"][k]
            parts.append(f"{lab} {m['diff'] * sc:+.2f} {unit} [{m['lo'] * sc:+.2f}, {m['hi'] * sc:+.2f}]" + ("" if m["significant"] else " (ns)"))
        return "; ".join(parts)
    br = R["best_rule"]
    for s in list(R["scenarios"]):
        blk = R["scenarios"][s]
        for c in blk["comparisons"]:
            if not (c["a"].startswith("dispatch_") or c["a"].startswith("ablate:")) or c["b"] == "fixed":
                continue
            tag = "the tuned rule manager" if c["b"] == "tuned_same_budget" else ("its own levers without the learned index" if c["b"].startswith("ablate:")
                                                                                 else "the best hard-coded rule")
            out.append(f"[{s}] `{c['a']}` minus {tag} `{c['b']}`: {line(c)}. Patient index {c['patient_index']['a']:.3f} vs {c['patient_index']['b']:.3f}, "
                       f"flow index {c['flow_index']['a']:.3f} vs {c['flow_index']['b']:.3f} (1 = baseline, lower is better).")
        for n, f in (blk.get("operator") or {}).items():
            if n.startswith("dispatch_") or n.startswith("ablate:") or n in ("tuned_same_budget", br["any_split_by_flow_index"]):
                out.append(f"[{s}] same_budget_better_flow, `{n}`: score {f['score']:+.4f} on pooled means, feasible = {f['feasible']}"
                           + (f" (violated: {', '.join(f['violated'])})" if f["violated"] else "") + f"; feasible in {f['members_feasible']} of "
                           f"{len(f['score_per_member'])} members; per-member mean score {f['score_members_mean']:+.4f}.")
    return out


# ---------------------------------------------------------------------------------------------- reading the policy
def feature_table(d: dict) -> dict:
    """What the index does, in acuity levels (60 priority-minutes = one triage level under acuity_first). Negative = sooner."""
    dp = d["dispatch"]
    f, ctx = dp["features"], dp["context"]
    nf, ng = len(f), len(ctx)
    th = torch.tensor(dp["engine_theta"])
    w, W = th[:nf], th[nf:nf + nf * ng].reshape(nf, ng)
    fi = {n: i for i, n in enumerate(f)}
    stages, esis = ["bay_queue", "new_in_bay", "disposition", "scan_queue"], ["esi1", "esi2", "esi3", "esi4", "esi5"]
    # effective standing of (queue, triage level) at zero wait, relative to (same queue, ESI 3)
    exp_enc = None
    try:
        from sim import HospitalSim, load_scenario
        sim = HospitalSim(load_scenario("normal_week", {"hospital_id": d.get("hospital_id")}), batch_size=1, device="cpu", seed=0)
        exp_enc = [float(sim.exp_service[e]) for e in range(1, 6)]
    except Exception:
        exp_enc = [40.0, 30.0, 20.0, 12.0, 8.0]
    stand = {}
    for s in stages:
        stand[s] = [float(w[fi["acuity_x60"]] * 60 * (e + 1) + w[fi["exp_encounter_min"]] * exp_enc[e] + w[fi[f"{s}:{esis[e]}"]]) / 60.0 for e in range(5)]
    aging = [float(w[fi["wait_min"]] * 60 + w[fi[f"wait_h:{e}"]]) / 60.0 for e in esis]             # levels per hour since arrival
    q_aging = {s: float(w[fi[f"queue_h:{s}"]]) / 60.0 for s in stages}
    other = {n: float(w[fi[n]]) / 60.0 for n in ["lwbs_pressure", "deteriorated", "walk_in", "ambulance", "transfer_in", "age_0_17", "age_18_44",
                                                  "age_45_64", "age_65_plus"] + [f"cond{i}" for i in range(9)]}
    ctx_eff = []
    if bool((W != 0).any()):
        for i, n in enumerate(f):
            for k, c in enumerate(ctx):
                if abs(float(W[i, k])) > 0:
                    ctx_eff.append((n, c, float(W[i, k]) / (60.0 if i != fi["wait_min"] else 1.0)))
    return dict(unit="acuity levels (1 level = 60 priority-minutes; negative = served sooner)", unify=dp["unify"], variant=dp["variant"],
                hidden=dp["hidden"], standing_by_queue_and_triage_level=stand, aging_levels_per_hour_since_arrival=dict(zip(esis, aging)),
                aging_levels_per_hour_in_queue=q_aging, other=other, has_network=bool(dp["hidden"]),
                context_terms=len(ctx_eff), exp_encounter_min=exp_enc)


@torch.no_grad()
def queue_anatomy(hospital: str, scenarios=("normal_week", "flu_surge"), members=(0,), n_seeds: int = 4, days: int = 14, policy: DispatchPolicy | None = None) -> dict:
    """Where the time before first provider contact goes, and how often there is a real choice to make, under the
    baseline (or under a learned dispatch policy with baseline levers). Tick-level census; descriptive only."""
    from sim import HospitalSim, load_scenario
    from sim.engine import EPS, S_PROV, S_TRI, S_WALK, S_WB, S_WP, S_WRES, S_WT
    from .common import member_overrides
    h = hospital_id(hospital)
    out = {}
    for s in scenarios:
        acc = None
        for m in members:
            sim = HospitalSim(load_scenario(s, overrides=member_overrides(h, m)), batch_size=n_seeds, device="cpu",
                              seed=torch.tensor([SEED_EVAL + 500_000 + i for i in range(n_seeds)]))
            if policy is not None:
                policy.apply(sim)
                sim.reset()
            a = {k: torch.zeros(n_seeds, dtype=torch.float64) for k in
                 ("triage_queue", "in_triage", "bay_queue", "walk_to_bay", "provider_queue_new", "dispo_ready", "ticks", "backlog_bay", "backlog_new",
                  "backlog_dispo", "backlog_both", "free_prov", "busy_prov", "choice_new", "choice_bay")}
            acts = sim.default_actions()
            for _ in range(days * 24 * sim.tph):
                sim.tick(acts)
                p = sim.p
                st = p["state"]
                act = p["active"]
                n = lambda mask: (mask & act).sum(1).double()      # noqa: E731
                ready = (st == S_WRES) & (p["treat_left"] <= EPS) & (p["res_left"] <= EPS)
                wb, wp, rd = n(st == S_WB), n(st == S_WP), n(ready)
                a["triage_queue"] += n(st == S_WT)
                a["in_triage"] += n(st == S_TRI)
                a["bay_queue"] += wb
                a["walk_to_bay"] += n((st == S_WALK) & (p["next_state"] == S_WP))
                a["provider_queue_new"] += wp
                a["dispo_ready"] += rd
                a["ticks"] += 1
                # after this tick's assignments: who is still queued = a choice was made (someone else went first, or nobody could)
                a["backlog_bay"] += (wb > 0).double()
                a["backlog_new"] += (wp > 0).double()
                a["backlog_dispo"] += (rd > 0).double()
                a["backlog_both"] += ((wp > 0) & (rd > 0)).double()
                a["choice_new"] += (wp > 1).double()                # at least two new patients left in the provider queue
                a["choice_bay"] += (wb > 1).double()
                a["busy_prov"] += n(st == S_PROV)
                a["free_prov"] += (sim.md_eff.double() - n(st == S_PROV)).clamp(min=0)
            acc = a if acc is None else {k: torch.cat([acc[k], v]) for k, v in a.items()}
        T = acc["ticks"]
        pre = sum(acc[k] for k in ("triage_queue", "in_triage", "bay_queue", "walk_to_bay", "provider_queue_new"))
        out[s] = dict(
            share_of_pre_provider_time={k: float((acc[k] / pre).mean()) for k in ("triage_queue", "in_triage", "bay_queue", "walk_to_bay", "provider_queue_new")},
            mean_patients={k: float((acc[k] / T).mean()) for k in ("triage_queue", "bay_queue", "provider_queue_new", "dispo_ready", "busy_prov", "free_prov")},
            share_of_ticks_with_backlog=dict(bay_queue=float((acc["backlog_bay"] / T).mean()), new_patients=float((acc["backlog_new"] / T).mean()),
                                             dispositions=float((acc["backlog_dispo"] / T).mean()), new_and_dispositions=float((acc["backlog_both"] / T).mean()),
                                             two_or_more_new=float((acc["choice_new"] / T).mean()), two_or_more_for_bay=float((acc["choice_bay"] / T).mean())),
            members=list(members), n_seeds=n_seeds, days=days)
    return out


def _f(x, sc=1.0, nd=1):
    return "n/a" if x is None else f"{x * sc:,.{nd}f}"


def _cmp_cell(c, sc, nd):
    star = "" if c["significant"] else " (ns)"
    return f"{_f(c['diff'], sc, nd)} [{_f(c['lo'], sc, nd)}, {_f(c['hi'], sc, nd)}]{star}"


def write_markdown(R: dict, path: Path):
    L = []
    P = R["protocol"]
    L += [f"# Learned per-patient dispatch: {R['hospital_id']} (SIMULATED)", "",
          "Every number below is simulated. Nothing here is a measurement of the real hospital.", "",
          f"Generated {R['generated']}. Held-out seeds {P['seeds'][0]:,}..{P['seeds'][1]:,} ({P['n_seeds']} seeds) x {P['days']} days x "
          f"{len(P['members'])} calibration-ensemble members x {P['scenarios']}. {P['pairing']}. Intervals: {P['interval']}; `(ns)` = the interval "
          "contains zero.", ""]
    br = R["best_rule"]
    L += ["## Arms", "",
          "- `fixed`: the calibrated baseline (current practice), every lever at its default.",
          f"- `rule:<priority>+<split>`: baseline levers with a hard-coded queue rule and provider split forced (4 x 3 = 12 arms). Best by patient "
          f"index at the baseline split (`{br['baseline_split']}`): `{br['same_split']}`; best over all 12: `{br['any_split']}`; best by flow index: "
          f"`{br['any_split_by_flow_index']}`. {br['note']}.",
          f"- `tuned_same_budget`: the tuned rule manager for same_budget_better_flow ({R['notes'].get('tuned_same_budget')} for this calibration).",
          "- `dispatch_dispatch_only_*`: learned per-patient index, every lever at the baseline (isolates dispatch), searched on the patient index.",
          "- `dispatch_dispatch_flow_*`: the same, searched on the operator objective same_budget_better_flow (flow index + constraints).",
          "- `dispatch_joint_*`: learned index plus re-tuned rule-manager parameters on same_budget_better_flow.",
          "- `ablate:<joint>:levers_only`: the joint policy's lever parameters with the hard-coded queue rule they select (no learned index); "
          "`ablate:<joint>:index_on_tuned`: the tuned rule manager's levers with the joint policy's learned index.", ""]
    for n, v in R["notes"].items():
        if isinstance(v, dict) and "variant" in v:
            L.append(f"  - `{n}`: {v['variant']} index, unified provider queue = {v['unify']}, stale = {v['stale']}")
    L.append("")
    names = R["arms"]
    show = ["fixed", br["same_split"], br["any_split"], br["any_split_by_flow_index"]] + [n for n in names if n == "tuned_same_budget" or n.startswith("dispatch_") or n.startswith("ablate:")]
    show = list(dict.fromkeys(show))
    for s, blk in R["scenarios"].items():
        L += [f"## {s}", "", "### Means", "", "| Metric | " + " | ".join(f"`{n}`" for n in show) + " |", "|---|" + "---:|" * len(show)]
        for k, lab, unit, sc, nd in REPORT + ACU_REPORT:
            L.append(f"| {lab} ({unit}) | " + " | ".join(_f(blk["means"][n][k], sc, nd) for n in show) + " |")
        L.append("| Patient index (1 = baseline) | " + " | ".join(_f(blk["means"][n]["patient_index"], 1, 3) for n in show) + " |")
        L.append("| Flow index (1 = baseline) | " + " | ".join(_f(blk["means"][n]["flow_index"], 1, 3) for n in show) + " |")
        L.append("")
        L += ["### Paired differences (a minus b; negative = a is lower)", ""]
        for c in blk["comparisons"]:
            L += [f"**`{c['a']}` minus `{c['b']}`** (patient index {c['patient_index']['a']:.3f} vs {c['patient_index']['b']:.3f}; "
                  f"flow index {c['flow_index']['a']:.3f} vs {c['flow_index']['b']:.3f})", "",
                  "| Metric | a | b | difference [95% CI] | members lower / higher |", "|---|---:|---:|---:|---:|"]
            for k, lab, unit, sc, nd in REPORT + ACU_REPORT[:8]:
                m = c["metrics"][k]
                L.append(f"| {lab} ({unit}) | {_f(m['a'], sc, nd)} | {_f(m['b'], sc, nd)} | {_cmp_cell(m, sc, nd + 1)} | "
                         f"{m['members_lower']} / {m['members_higher']} of {m['n_members']} |")
            L.append("")
        if "operator" in blk and blk["operator"]:
            L += ["### same_budget_better_flow on held-out episodes (no tuning margin)", "",
                  "| Arm | score on pooled means (higher is better) | feasible | members feasible | mean per-member score | violated |", "|---|---:|---|---:|---:|---|"]
            for n, f in blk["operator"].items():
                L.append(f"| `{n}` | {f['score']:+.4f} | {f['feasible']} | {f['members_feasible']} / {len(f['score_per_member'])} | "
                         f"{f['score_members_mean']:+.4f} | {', '.join(f['violated']) or '-'} |")
            L.append("")
        if "per_member_patient_index" in blk:
            L += ["### Patient index per ensemble member (1 = that member's baseline)", "",
                  "| Arm | " + " | ".join(f"m{m}" for m in P["members"]) + " |", "|---|" + "---:|" * len(P["members"])]
            for n, v in blk["per_member_patient_index"].items():
                L.append(f"| `{n}` | " + " | ".join(f"{x:.3f}" for x in v) + " |")
            L.append("")
            L += ["### Flow index per ensemble member (1 = that member's baseline)", "",
                  "| Arm | " + " | ".join(f"m{m}" for m in P["members"]) + " |", "|---|" + "---:|" * len(P["members"])]
            for n, v in blk["per_member_flow_index"].items():
                L.append(f"| `{n}` | " + " | ".join(f"{x:.3f}" for x in v) + " |")
            L.append("")
        L += ["### All hard-coded rule arms", "", "| Arm | wait | p95 | LOS median | LWBS % | ESI 1-2 waiting h/day | adverse/day | patient index | flow index |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for n in names:
            if n.startswith("rule:") or n == "fixed":
                m = blk["means"][n]
                L.append(f"| `{n}` | {m['wait_mean_min']:.1f} | {m['wait_p95_min']:.0f} | {m['ed_los_median_min']:.0f} | {100 * m['lwbs_rate']:.2f} | "
                         f"{m['hi_acuity_wait_hours_per_day']:.2f} | {m['adverse_events_per_day']:.2f} | {m['patient_index']:.3f} | {m['flow_index']:.3f} |")
        L.append("")
    if R.get("feature_tables"):
        L += ["## What the learned index does", "",
              "Unit: acuity levels (one level = the gap between two adjacent triage levels under `acuity_first`). Negative = served sooner.", ""]
        for n, T in R["feature_tables"].items():
            L += [f"### `{n}` ({T['variant']} index; unified provider queue: {T['unify']})", "",
                  "Standing at zero wait, by queue and triage level:", "", "| Queue | ESI 1 | ESI 2 | ESI 3 | ESI 4 | ESI 5 |", "|---|---:|---:|---:|---:|---:|"]
            for s, v in T["standing_by_queue_and_triage_level"].items():
                L.append(f"| {s} | " + " | ".join(f"{x:+.2f}" for x in v) + " |")
            L += ["", "Aging, levels per hour since arrival: " + ", ".join(f"{k} {v:+.2f}" for k, v in T["aging_levels_per_hour_since_arrival"].items()) + ".",
                  "Aging, levels per hour in the current queue: " + ", ".join(f"{k} {v:+.2f}" for k, v in T["aging_levels_per_hour_in_queue"].items()) + ".",
                  "Other weights: " + ", ".join(f"{k} {v:+.2f}" for k, v in T["other"].items()) + ".",
                  (f"Plus {T['context_terms']} context interaction weights" if T["context_terms"] else "No context interactions")
                  + (f" and a {T['hidden']}-unit network (not readable from this table)." if T["has_network"] else "."), ""]
    if R.get("queue_anatomy"):
        L += ["## Where the choices are (baseline, tick-level census)", "",
              "| Scenario | arm | share of pre-provider time: triage queue | in triage | bay queue | walking to bay | provider queue | mean new patients queued "
              "| mean ready dispositions queued | ticks with 2+ new queued | ticks with 2+ queued for a bay | ticks with a new patient AND a disposition waiting |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for arm, A in R["queue_anatomy"].items():
            for s, q in A.items():
                sh, mp_, bk = q["share_of_pre_provider_time"], q["mean_patients"], q["share_of_ticks_with_backlog"]
                L.append(f"| {s} | {arm} | {100 * sh['triage_queue']:.0f}% | {100 * sh['in_triage']:.0f}% | {100 * sh['bay_queue']:.0f}% | {100 * sh['walk_to_bay']:.0f}% | "
                         f"{100 * sh['provider_queue_new']:.0f}% | {mp_['provider_queue_new']:.2f} | {mp_['dispo_ready']:.2f} | {100 * bk['two_or_more_new']:.0f}% | "
                         f"{100 * bk['two_or_more_for_bay']:.0f}% | {100 * bk['new_and_dispositions']:.0f}% |")
        L.append("")
    titles = dict(verdict="Held-out comparisons in one line each", summary="Verdict", why="Why", would_need="What the simulator would need for dispatch to matter more",
                  training="How it was trained", gradient_rl="Decision-level gradient RL")
    for k in ("summary", "why", "verdict", "training", "gradient_rl", "would_need"):
        if R.get(k):
            L += [f"## {titles[k]}", ""] + ([R[k]] if isinstance(R[k], str) else [f"- {x}" for x in R[k]]) + [""]
    write_text(path, "\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tune")
    t.add_argument("--mode", default="dispatch_only", choices=["dispatch_only", "dispatch_flow", "joint"])
    t.add_argument("--variant", default="linear", choices=list(DispatchSpace.VARIANTS))
    t.add_argument("--hidden", type=int, default=16)
    t.add_argument("--hospital", default=None)
    t.add_argument("--workers", type=int, default=0)
    t.add_argument("--chunk", type=int, default=8, help="candidates per worker task")
    t.add_argument("--pop", type=int, default=64)
    t.add_argument("--elite", type=int, default=12)
    t.add_argument("--gens", type=int, default=30)
    t.add_argument("--seeds", type=int, default=4)
    t.add_argument("--days", type=int, default=10)
    t.add_argument("--members-per-gen", type=int, default=4)
    t.add_argument("--final-members", type=int, default=8)
    t.add_argument("--final-seeds", type=int, default=8)
    t.add_argument("--final-days", type=int, default=14)
    t.add_argument("--final-elites", type=int, default=5)
    t.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    t.add_argument("--quantile", type=float, default=0.25)
    t.add_argument("--smooth", type=float, default=0.7)
    t.add_argument("--min-std", type=float, default=0.02)
    t.add_argument("--rule-std", type=float, default=0.05)
    t.add_argument("--init", default=None, help="a saved dispatch policy (JSON) to start from (a smaller variant is extended)")
    t.add_argument("--init-shrink", type=float, default=0.5)
    t.add_argument("--resume", action="store_true")
    t.add_argument("--run", default=None)
    t.add_argument("--out", default=None)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--seed-block", type=int, default=0, help="0..6: separates the tuning seeds of different runs")
    e = sub.add_parser("eval")
    e.add_argument("--hospital", default=None)
    e.add_argument("--workers", type=int, default=0)
    e.add_argument("--chunk", type=int, default=4, help="arms per worker task")
    e.add_argument("--seeds", type=int, default=16)
    e.add_argument("--seed-offset", type=int, default=0)
    e.add_argument("--days", type=int, default=30)
    e.add_argument("--members", type=int, default=8)
    e.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    e.add_argument("--policies", nargs="*", default=None)
    e.add_argument("--anatomy", action="store_true", help="also tabulate where pre-provider time goes and how often there is a choice")
    r = sub.add_parser("report")
    r.add_argument("--hospital", default=None)
    r.add_argument("--rebuild", action="store_true", help="recompute dispatch.json from dispatch_raw.json before rendering")
    a = ap.parse_args()
    if a.cmd == "tune":
        tune(a)
    elif a.cmd == "eval":
        evaluate(a)
    else:
        h = hospital_id(a.hospital)
        home = paths(h).home
        R = json.loads((home / "dispatch.json").read_text())
        if a.rebuild:                                   # recompute every table from the saved per-episode numbers (no simulation)
            raw = json.loads((home / "dispatch_raw.json").read_text())
            files = [Path(v["file"]) for v in R["notes"].values() if isinstance(v, dict) and "file" in v]
            files = [f if f.exists() else policy_dir(h) / f.name for f in files]
            arms, notes = default_arms(h, files)
            assert [x["name"] for x in arms] == raw["names"], "arms on disk differ from the evaluated ones"
            data = {s: {k: torch.tensor(v) for k, v in d.items()} for s, d in raw["data"].items()}
            R2 = summarise(h, raw["names"], notes, raw["members"], raw["seeds"], raw["days"], raw["scenarios"], data)
            for k in ("queue_anatomy", "summary", "why", "training", "gradient_rl"):
                if k in R:
                    R2[k] = R[k]
            R2["generated"] = R.get("generated", R2["generated"])
            R = R2
            write_json(home / "dispatch.json", R, indent=1)
        write_markdown(R, home / "DISPATCH.md")
        print(f"wrote {home / 'DISPATCH.md'}")


if __name__ == "__main__":
    main()
