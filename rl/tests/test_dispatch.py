"""Learned dispatch: search space, batched runner, scoring, report."""
import argparse
import json

import torch

import rl.dispatch as D
from rl.dispatch import (ACU_STATS, DispatchPolicy, DispatchSpace, Pool, acuity_metrics, engine_spec, evaluate_population, feature_table, make_task,
                         paired, patient_score, run_task, summarise, write_markdown)
from rl.objectives import EPISODE_METRICS

H = "rwjuh_nb"
K = len(EPISODE_METRICS)


def test_space_starts_at_the_baseline_rule_and_variants_nest():
    sp = engine_spec(0, H)
    lin, ctx, mlp = DispatchSpace("linear", hospital=H), DispatchSpace("context", hospital=H), DispatchSpace("mlp", 8, hospital=H)
    assert lin.nz == 1 + lin.nf and ctx.nz == lin.nz + 11 * lin.ng and len(ctx.names) == ctx.nz and len(mlp.names) == mlp.nz
    z, std = lin.init()
    th, un = lin.decode(z)
    assert th.shape == (1, sp["n_params"]) and not bool(un[0])
    assert th[0].tolist() == sp["rule_theta"][lin.base_rule]            # exactly the hospital's baseline priority rule
    assert bool((std[1:] > 0).all())
    for r in range(4):                                                  # every hard-coded rule is a point of the space
        zr = DispatchSpace("linear", hospital=H, base_rule=r).init()[0]
        assert lin.decode(zr)[0][0].tolist() == sp["rule_theta"][r]
    g = torch.Generator().manual_seed(0)
    zl = z + std * torch.randn(lin.nz, generator=g)
    zc = ctx.extend(zl, lin)
    assert torch.equal(ctx.decode(zc)[0], lin.decode(zl)[0])            # the added context terms start at zero
    zm = mlp.extend(zc, ctx)
    tm = mlp.decode(zm)[0]
    n_lin = sp["n_params"]
    assert torch.equal(tm[:, :n_lin], lin.decode(zl)[0]) and bool((tm[:, -8:] == 0).all())     # output weights zero: the network adds nothing
    # a context gene moves every feature of its group
    zc2 = zc.clone()
    zc2[1 + ctx.nf] = 1.0                                              # queue:bay_queue x q_bay
    W = ctx.decode(zc2)[0][0, ctx.nf:].reshape(ctx.nf, ctx.ng)
    idx = [i for i, n in enumerate(ctx.features) if n.startswith("bay_queue:")]
    assert W[idx, 0].tolist() == [60.0] * 5 and float(W.abs().sum()) == 300.0


def test_patient_score_zero_at_baseline_and_guards():
    base = torch.rand(K) + 100.0
    assert abs(float(patient_score(base, base))) < 1e-6
    better = base.clone()
    better[EPISODE_METRICS.index("wait_mean_min")] *= 0.5
    assert float(patient_score(better, base)) > 0.1
    worse_los = better.clone()
    worse_los[EPISODE_METRICS.index("ed_los_median_min")] = base[EPISODE_METRICS.index("ed_los_median_min")] + 100.0
    assert float(patient_score(worse_los, base)) < float(patient_score(better, base))


def test_runner_rule_rows_match_the_hard_coded_rules(scales):
    """In one batch on the same seeds: the dispatch row that encodes rule r equals the arm with the head forced to r,
    and the baseline arm equals the row that encodes the baseline rule."""
    sp = engine_spec(0, H)
    lin = DispatchSpace("linear", hospital=H)
    blocks = [dict(name="fixed", manager="fixed")]
    blocks += [dict(name=f"rule{r}", manager="fixed", overrides={"priority_rule": r}) for r in range(4)]
    blocks += [dict(name="learned", disp=sp["rule_theta"], unify=False, hidden=0)]
    r = run_task(make_task(H, "flu_surge", 0, blocks, [9_500_000, 9_500_001], 1, scales=scales))
    ep, ac = r["episode"], r["acuity"]
    assert ep.shape == (9, 2, K) and ac.shape == (9, 2, len(ACU_STATS), 6) and len(r["names"]) == 9
    for k in range(4):
        assert torch.equal(ep[1 + k], ep[5 + k]) and torch.equal(ac[1 + k], ac[5 + k])
    assert torch.equal(ep[0], ep[1 + lin.base_rule])
    assert float(r["invalid"].sum()) == 0.0
    m = acuity_metrics(ac, 1)
    assert m["wait_esi3_min"].shape == (9, 2) and bool((m["unseen_h_esi12"] >= 0).all())


def test_population_scoring_inline(scales):
    lin = DispatchSpace("linear", hospital=H)
    z, std = lin.init()
    cand = z + std * torch.randn((3, lin.nz), generator=torch.Generator().manual_seed(1))
    cand[0] = z
    th, un = lin.decode(cand)
    pop = dict(name="cand", disp=th.tolist(), unify=un.tolist(), hidden=0)
    pool = Pool(0)
    for mode in ("dispatch_only", "joint"):
        p = dict(pop, rule=[D.theta_from_dict(D.RulePolicy(hospital=H).params_dict()).tolist()] * 3) if mode == "joint" else pop
        sc, mean = evaluate_population(pool, p, 3, mode, H, ["normal_week"], [0], [330_000], 1, scales, chunk=2)
        assert sc.shape == (3,) and mean.shape == (3, K) and bool(torch.isfinite(sc).all())
        if mode == "dispatch_only":
            assert abs(float(sc[0])) < 1e-6                 # the starting point is the baseline: index exactly 1


def test_paired_interval_and_member_counts():
    g = torch.Generator().manual_seed(0)
    b = torch.randn((4, 8), generator=g)
    p = paired(b - 1.0, b)
    assert abs(p["diff"] + 1.0) < 1e-6 and p["lo"] <= p["diff"] <= p["hi"] and p["significant"] and p["members_lower"] == 4
    q = paired(b + 0.01 * torch.randn((4, 8), generator=g), b)
    assert q["lo"] < q["hi"]


def test_policy_file_report_and_markdown(tmp_path, scales, monkeypatch):
    lin = DispatchSpace("linear", hospital=H)
    z, _ = lin.init()
    z[0] = 1.0
    z[1 + lin.features.index("disposition:esi4")] = -1.5
    th, un = lin.decode(z)
    d = dict(id="dispatch_dispatch_only_linear", kind="learned_dispatch", type="dispatch", label="test", mode="dispatch_only", hospital_id=H,
             rule_params=None, dispatch=dict(variant="linear", hidden=0, unify=bool(un[0]), z=z.tolist(), z_names=lin.names,
                                             engine_theta=th[0].tolist(), features=lin.features, context=lin.context))
    f = tmp_path / "dispatch_dispatch_only_linear.json"
    f.write_text(json.dumps(d))
    pol = DispatchPolicy.load(f)
    assert pol.kind == "learned_dispatch" and pol.unify and pol.block()["disp"][0] == th[0].tolist()
    T = feature_table(d)
    st = T["standing_by_queue_and_triage_level"]
    assert abs(st["disposition"]["esi4"] if isinstance(st["disposition"], dict) else st["disposition"][3] - (st["bay_queue"][3] - 1.5)) < 1e-4
    arms, notes = D.default_arms(H, [f])
    names = [a["name"] for a in arms]
    assert names[0] == "fixed" and sum(n.startswith("rule:") for n in names) == 12 and names[-1] == pol.id
    arms = [a for a in arms if a["name"] != "tuned_same_budget"]         # the installed tuned policy may be stale; not needed here
    names = [a["name"] for a in arms]
    data = {}
    for s in ("normal_week",):
        parts = [run_task(make_task(H, s, m, arms, [9_600_000, 9_600_001], 1, scales=scales)) for m in (0, 1)]
        data[s] = dict(episode=torch.stack([p["episode"] for p in parts], 1), acuity=torch.stack([p["acuity"] for p in parts], 1))
    R = summarise(H, names, notes, [0, 1], [9_600_000, 9_600_001], 1, ["normal_week"], data)
    assert R["synthetic"] and "pooled" in R["scenarios"] and R["best_rule"]["same_split"].startswith("rule:")
    c = R["scenarios"]["normal_week"]["comparisons"][0]
    assert c["a"] == pol.id and c["b"] == "fixed" and "wait_mean_min" in c["metrics"] and "lo" in c["metrics"]["wait_esi3_min"]
    json.dumps(R)
    write_markdown(R, tmp_path / "DISPATCH.md")
    txt = (tmp_path / "DISPATCH.md").read_text()
    assert "SIMULATED" in txt and "What the learned index does" in txt and "Paired differences" in txt
