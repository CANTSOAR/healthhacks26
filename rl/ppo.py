"""PPO for the factored, masked hospital-manager action space. Written here; no RL library.

    python -m rl.ppo --objective min_cost --device cuda --run runs/ppo_min_cost --ref tuned_min_cost --bc

Batch layout per scenario sub-environment (all in one GPU batch):
    [0, nv)        greedy validation rows: the network acting by argmax; never trained on
    [nv, 2nv)      reference rows: the --ref manager (the tuned heuristic) on the SAME seeds; never trained on
    [2nv, ...)     training rows: sampled actions, PPO data
so every finished episode gives a paired, same-seed comparison of the learned agent against the
heuristic it has to beat, for free. Validation seeds are 900,000+, training seeds 400,000+;
held-out evaluation (rl/evaluate.py) uses 9,000,000+.

Masked heads (not at their cadence boundary, or disabled by the curriculum stage) contribute
zero log-prob and zero entropy. Episode ends are time limits, so the value of the final
observation is bootstrapped. `--bc` behaviour-clones the reference manager before PPO starts.
The constrained objective uses a Lagrangian-style weight on the wait term that rises while the
p95-wait constraint is violated on the training rows; the weight is part of the observation.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from .common import (CONSTRAINED, OBJ_SLUG, OBJECTIVES, POLICY_DIR, SEED_TRAIN, SEED_VAL, STAGES, TERMS, load_scales, now_iso,
                     objective_score, sim_fingerprint, weights_dict, weights_vec, write_json)
from .env import ConcatEnv, HospitalEnv
from .managers import load_manager
from .net import ActorCritic


def export_policy(net: ActorCritic, cfg: dict, stem: Path):
    """Plain state_dict (.pt) + JSON config; loads on torch 2.2 CPU via rl.load_manager."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    tmp = stem.with_suffix(".pt.tmp")
    torch.save({k: v.detach().cpu() for k, v in net.state_dict().items()}, tmp)
    tmp.replace(stem.with_suffix(".pt"))
    cfg = dict(cfg, checkpoint=stem.with_suffix(".pt").name)
    write_json(stem.with_suffix(".json"), cfg, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objective", default="balanced", choices=list(OBJECTIVES))
    ap.add_argument("--id", default=None)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--run", default=None)
    ap.add_argument("--scenarios", nargs="+", default=["normal_week", "flu_surge"])
    ap.add_argument("--envs", type=int, default=1024, help="total hospitals across scenarios")
    ap.add_argument("--nv", type=int, default=32, help="validation rows per scenario (and reference rows)")
    ap.add_argument("--episode-hours", type=int, default=336)
    ap.add_argument("--T", type=int, default=48, help="rollout length in hours; must divide episode-hours")
    ap.add_argument("--stage", default="stage_1")
    ap.add_argument("--hours", type=float, default=2.0, help="wall-clock budget")
    ap.add_argument("--max-iters", type=int, default=10 ** 9)
    ap.add_argument("--ref", default=None, help="manager id for the reference rows and for --bc")
    ap.add_argument("--bc", action="store_true")
    ap.add_argument("--bc-hours", type=int, default=336)
    ap.add_argument("--bc-epochs", type=int, default=30)
    ap.add_argument("--bc-smooth", type=float, default=0.03)
    ap.add_argument("--critic-warmup", type=int, default=3, help="iterations with the actor frozen")
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--lam", type=float, default=0.97)
    ap.add_argument("--clip", type=float, default=0.15)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatches", type=int, default=4)
    ap.add_argument("--ent", type=float, default=0.005)
    ap.add_argument("--ent-final", type=float, default=0.0005)
    ap.add_argument("--vf", type=float, default=0.5)
    ap.add_argument("--max-grad", type=float, default=0.5)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--lag-lr", type=float, default=0.25)
    ap.add_argument("--lag-init", type=float, default=0.2)
    ap.add_argument("--export", default=None, help="export stem (default <run>/best; install with rl.scripts.install_policies)")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    assert a.episode_hours % a.T == 0
    torch.manual_seed(a.seed)
    dev = torch.device(a.device)
    slug = OBJ_SLUG[a.objective]
    pid = a.id or f"ppo_{slug}"
    run = Path(a.run or f"runs/{pid}")
    run.mkdir(parents=True, exist_ok=True)
    log = open(run / "log.txt", "a")

    def say(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    scales = load_scales()
    thr = float(scales["p95_wait_threshold_min"])
    constrained = a.objective == CONSTRAINED
    w = weights_vec(a.objective, dev)
    lag = a.lag_init if constrained else 0.0
    if constrained:
        w[TERMS.index("wait")] = lag
    nS = len(a.scenarios)
    per = a.envs // nS
    ref = load_manager(a.ref, dev) if a.ref else None
    nv = a.nv
    n_fix = nv * (2 if ref is not None else 1)
    envs = [HospitalEnv(s, per, dev, 0, a.episode_hours, stage=a.stage, weights=w, scales=scales, auto_reset=False) for s in a.scenarios]
    env = ConcatEnv(envs)
    B, H = env.B, len(env.head_names)
    row = torch.arange(B, device=dev) % per
    is_val, is_ref = row < nv, (row >= nv) & (row < n_fix) if ref is not None else torch.zeros(B, dtype=torch.bool, device=dev)
    is_train = row >= n_fix
    n_train = int(is_train.sum())
    enabled = torch.tensor([env.enabled[n] for n in env.head_names], device=dev)
    net = ActorCritic(env.obs_dim, env.head_sizes, a.hidden, a.layers, env.defaults).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr, eps=1e-5)
    fp = sim_fingerprint()
    say(f"[{now_iso()}] ppo {pid} objective={a.objective} B={B} (train rows {n_train}, val {int(is_val.sum())}, ref {int(is_ref.sum())}) "
        f"T={a.T} ep={a.episode_hours}h scen={a.scenarios} stage={a.stage} ref={a.ref} bc={a.bc} fp={fp} args={vars(a)}")

    def seeds_for(ep):
        out = []
        for si in range(nS):
            val = SEED_VAL + (ep * nv + torch.arange(nv)) % 100_000
            tr = SEED_TRAIN + (ep * per * nS + si * per + torch.arange(per - n_fix)) % 500_000
            out.append(torch.cat([val, val, tr]) if ref is not None else torch.cat([val, tr]))
        return out

    def reset(ep):
        for e in env.envs:
            e.set_weights(w)
        return torch.cat([e.reset(s) for e, s in zip(env.envs, seeds_for(ep))], 0)

    def ref_actions(obs, rows):
        acts = ref.act(obs[rows], {n: m[rows] for n, m in env.action_mask().items()})
        return torch.stack([acts[n] for n in env.head_names], 1)

    def config(extra):
        rw = {k: float(w[i]) for i, k in enumerate(TERMS)}
        return dict(id=pid, kind="learned", label=f"Learned (PPO): {a.objective}", objective=a.objective, reward_weights=rw, type="ppo",
                    obs_dim=env.obs_dim, sim_obs_dim=env.sim_obs_dim, head_names=env.head_names, head_sizes=env.head_sizes,
                    enabled_heads=[n for n in env.head_names if env.enabled[n]], hidden=a.hidden, layers=a.layers, stage=a.stage,
                    obs_names=env.envs[0].sim.obs_names() + ["w_" + k for k in TERMS], sim_fingerprint=fp, synthetic=True,
                    training=dict(algorithm="PPO (rl/ppo.py)", args=vars(a), **extra))

    ep, t_start = 0, time.time()
    obs = reset(ep)
    hist, best = [], None
    total_steps = 0

    # ------------------------------------------------------------------ behaviour cloning
    if a.bc and ref is not None:
        t0 = time.time()
        O, A, M, R = [], [], [], []
        for t in range(a.bc_hours):
            mv = env.mask_vector() & enabled
            act = ref_actions(obs, torch.ones(B, dtype=torch.bool, device=dev))
            O.append(obs), A.append(act), M.append(mv)
            obs, r, done, info = env.step(act)
            R.append(r)
            if bool(done[0]):
                ep += 1
                obs = reset(ep)
        O, A, M, R = torch.stack(O), torch.stack(A), torch.stack(M), torch.stack(R)
        net.update_obs_stats(O)
        G = torch.zeros_like(R)
        g = torch.zeros(B, device=dev)
        for t in reversed(range(a.bc_hours)):
            g = R[t] + a.gamma * g
            G[t] = g
        keep = max(1, a.bc_hours - 96)                       # the last days have truncated returns: not used for the critic
        net.update_ret_stats(G[:keep])
        Of, Af, Gf = O.reshape(-1, O.shape[-1]), A.reshape(-1, H), ((G - net.ret_mean) / torch.sqrt(net.ret_var + 1e-8)).reshape(-1)
        Mf = M.unsqueeze(1).expand(-1, B, -1).reshape(-1, H)
        vmask = (torch.arange(a.bc_hours, device=dev) < keep).unsqueeze(1).expand(-1, B).reshape(-1)
        bopt = torch.optim.Adam(net.parameters(), lr=1e-3)
        N = Of.shape[0]
        for epch in range(a.bc_epochs):
            perm = torch.randperm(N, device=dev)
            tot, acc_n, acc_d = 0.0, torch.zeros(H, device=dev), torch.zeros(H, device=dev)
            for idx in perm.split(8192):
                lg = net.logits(Of[idx])
                loss = 0.0
                for hI in range(H):
                    m = Mf[idx, hI]
                    if not bool(m.any()):
                        continue
                    ce = F.cross_entropy(lg[hI][m], Af[idx, hI][m], label_smoothing=a.bc_smooth)
                    loss = loss + ce
                    acc_n[hI] += (lg[hI][m].argmax(-1) == Af[idx, hI][m]).float().sum()
                    acc_d[hI] += m.float().sum()
                vl = ((net.value_norm(Of[idx]) - Gf[idx]) ** 2 * vmask[idx]).sum() / vmask[idx].sum().clamp(min=1)
                bopt.zero_grad()
                (loss + 0.5 * vl).backward()
                bopt.step()
                tot += float(loss)
            if epch % 5 == 0 or epch == a.bc_epochs - 1:
                acc = (acc_n / acc_d.clamp(min=1))[enabled]
                say(f"bc epoch {epch} loss {tot:.3f} acc mean {float(acc.mean()):.3f} min {float(acc.min()):.3f}")
        del O, A, M, R, G, Of, Af, Gf, Mf
        say(f"bc done in {time.time() - t0:.0f}s ({a.bc_hours} h x {B} hospitals of {a.ref})")
        ep += 1
        obs = reset(ep)

    # ------------------------------------------------------------------ PPO
    T = a.T
    obs_buf = torch.zeros((T, B, env.obs_dim), device=dev)
    act_buf = torch.zeros((T, B, H), device=dev, dtype=torch.long)
    lp_buf, val_buf, rew_buf = (torch.zeros((T, B), device=dev) for _ in range(3))
    mask_buf = torch.zeros((T, H), device=dev, dtype=torch.bool)
    done_buf = torch.zeros((T,), device=dev)
    p95_acc, p95_n = 0.0, 0
    it = 0
    budget = a.hours * 3600
    while it < a.max_iters and time.time() - t_start < budget:
        t_it = time.time()
        frac = min(1.0, (time.time() - t_start) / budget)
        ent_coef = a.ent + (a.ent_final - a.ent) * frac
        for g_ in opt.param_groups:
            g_["lr"] = a.lr * (1.0 - 0.7 * frac)
        net.update_obs_stats(obs[is_train])
        for t in range(T):
            with torch.no_grad():
                mv = env.mask_vector() & enabled
                lgs = net.logits(obs)
                acts, lps = [], []
                for lg in lgs:
                    lp = torch.log_softmax(lg, -1)
                    s = torch.multinomial(lp.exp(), 1).squeeze(-1)
                    s = torch.where(is_val, lp.argmax(-1), s)
                    acts.append(s)
                    lps.append(lp.gather(-1, s.unsqueeze(-1)).squeeze(-1))
                act = torch.stack(acts, 1)
                lp = (torch.stack(lps, 1) * mv).sum(1)
                if ref is not None:
                    act[is_ref] = ref_actions(obs, is_ref)
                v = net.value(obs)
            obs_buf[t], act_buf[t], lp_buf[t], val_buf[t], mask_buf[t] = obs, act, lp, v, mv
            obs, r, done, info = env.step(act)
            if constrained:
                p95_acc += float(info["metrics"]["wait_p95_min"][is_train].mean())
                p95_n += 1
            done_buf[t] = 0.0
            if bool(done[0]):
                with torch.no_grad():
                    r = r + a.gamma * net.value(obs)           # time-limit bootstrap from the final observation
                done_buf[t] = 1.0
                p95 = info["summary"]["wait_p95_min"]
                sc = objective_score(a.objective, info["terms_mean"], p95, thr)
                rec = dict(ep=ep, it=it, steps=total_steps, minutes=(time.time() - t_start) / 60, val=float(sc[is_val].mean()),
                           train=float(sc[is_train].mean()), val_wait=float(info["summary"]["wait_mean_min"][is_val].mean()),
                           val_p95=float(p95[is_val].mean()), val_cost=float(info["summary"]["cost_per_day"][is_val].mean()),
                           val_lwbs=float(info["summary"]["lwbs_rate"][is_val].mean()), lag=float(lag))
                if ref is not None:
                    d = sc[is_val] - sc[is_ref]
                    rec.update(ref=float(sc[is_ref].mean()), diff=float(d.mean()), diff_ci95=float(1.96 * d.std() / math.sqrt(d.numel())),
                               ref_wait=float(info["summary"]["wait_mean_min"][is_ref].mean()), ref_cost=float(info["summary"]["cost_per_day"][is_ref].mean()))
                hist.append(rec)
                say("EP " + json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}))
                # selection: paired margin over the reference when there is one, else the raw validation score
                sel = rec.get("diff", rec["val"])
                if it >= a.critic_warmup and (best is None or sel > best["sel"]):
                    best = dict(sel=sel, **rec)
                    if not a.no_export:
                        export_policy(net, config(dict(selected=rec, history=hist[-200:], finished=None, steps=total_steps,
                                                       reference=a.ref, p95_wait_threshold_min=thr, lagrange_weight=float(lag))),
                                      Path(a.export) if a.export else run / "best")
                        say(f"exported best (selection {sel:.4f})")
                if constrained:
                    viol = (p95_acc / max(p95_n, 1)) / thr - 1.0
                    lag = float(min(5.0, max(0.0, lag + a.lag_lr * viol)))
                    w[TERMS.index("wait")] = lag
                    p95_acc, p95_n = 0.0, 0
                ep += 1
                obs = reset(ep)
            rew_buf[t] = r
            total_steps += n_train
        # ---- GAE on raw rewards with de-normalised values
        with torch.no_grad():
            last_v = net.value(obs)
            adv = torch.zeros((T, B), device=dev)
            gae = torch.zeros(B, device=dev)
            for t in reversed(range(T)):
                nd = 1.0 - done_buf[t]
                nv_ = last_v if t == T - 1 else val_buf[t + 1]
                delta = rew_buf[t] + a.gamma * nv_ * nd - val_buf[t]
                gae = delta + a.gamma * a.lam * nd * gae
                adv[t] = gae
            ret = adv + val_buf
            net.update_ret_stats(ret[:, is_train])
            rstd, rmean = torch.sqrt(net.ret_var + 1e-8), net.ret_mean.clone()
        o = obs_buf[:, is_train].reshape(-1, env.obs_dim)
        ac = act_buf[:, is_train].reshape(-1, H)
        olp = lp_buf[:, is_train].reshape(-1)
        ad = adv[:, is_train].reshape(-1)
        rt = ((ret[:, is_train] - rmean) / rstd).reshape(-1)
        mk = mask_buf.unsqueeze(1).expand(-1, n_train, -1).reshape(-1, H).float()
        N = o.shape[0]
        actor_on = it >= a.critic_warmup
        stats = dict(pl=0.0, vl=0.0, ent=0.0, kl=0.0, clipfrac=0.0)
        nb = 0
        for epch in range(a.epochs):
            perm = torch.randperm(N, device=dev)
            for idx in perm.split(N // a.minibatches + 1):
                lps, ents = net.evaluate(o[idx], ac[idx])
                nlp = (lps * mk[idx]).sum(1)
                ent = (ents * mk[idx]).sum(1).mean()
                adv_b = ad[idx]
                adv_b = (adv_b - adv_b.mean()) / (adv_b.std() + 1e-8)
                ratio = torch.exp(nlp - olp[idx])
                pl = -torch.min(ratio * adv_b, ratio.clamp(1 - a.clip, 1 + a.clip) * adv_b).mean()
                vl = F.smooth_l1_loss(net.value_norm(o[idx]), rt[idx])
                loss = a.vf * vl + ((pl - ent_coef * ent) if actor_on else 0.0)
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), a.max_grad)
                opt.step()
                with torch.no_grad():
                    stats["pl"] += float(pl); stats["vl"] += float(vl); stats["ent"] += float(ent)
                    stats["kl"] += float((olp[idx] - nlp).mean()); stats["clipfrac"] += float(((ratio - 1).abs() > a.clip).float().mean())
                nb += 1
        it += 1
        dt = time.time() - t_it
        say(f"it {it} steps {total_steps} sps {T * B / dt:.0f} rew {float(rew_buf[:, is_train].mean()):.4f} "
            + " ".join(f"{k} {v / nb:.4f}" for k, v in stats.items()) + f" ent_coef {ent_coef:.4f} lag {lag:.3f} ({dt:.0f}s)")
        export_policy(net, config(dict(selected=None, history=hist[-200:], steps=total_steps, reference=a.ref, lagrange_weight=float(lag))),
                      run / "latest")
        write_json(run / "progress.json", dict(id=pid, it=it, steps=total_steps, minutes=(time.time() - t_start) / 60, best=best, hist=hist,
                                               sim_fingerprint=fp, updated=now_iso()))
    say(f"[{now_iso()}] finished: {it} iterations, {total_steps} training steps, best {best}")


if __name__ == "__main__":
    main()
