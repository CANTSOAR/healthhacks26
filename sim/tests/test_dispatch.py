"""Learned dispatch hook (sim.set_dispatch_params): additive, behaviour-neutral when off, the four hard-coded rules are
exact special cases, parameters are per hospital of the batch."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import HospitalSim, load_scenario  # noqa: E402
from sim.engine import ACU_STATS, DISPATCH_CONTEXT, DISPATCH_FEATURES, DISPATCH_SCALE  # noqa: E402
from sim.tests.golden import action_sequence  # noqa: E402

HOURS = 36
SEEDS = torch.tensor([11, 12, 13, 14])


def make(scn="flu_surge", B=4):
    return HospitalSim(load_scenario(scn, overrides={"no_calibration": True}), batch_size=B, device="cpu", seed=SEEDS[:B])


def run(sim, rule=None, split=None, hours=HOURS, uniform=False):
    """Fixed pseudo-random hourly + daily actions; `rule` / `split` (LongTensor[B]) override those heads.
    uniform: every hospital of the batch gets the same actions (else two alternating action streams)."""
    seq = action_sequence(sim.action_spec(), hours)
    rows = []
    for h in range(hours):
        a = {k: (v[:1].repeat(sim.B) if uniform else v.repeat(sim.B // 2)) for k, v in seq[h].items()}
        if rule is not None:
            a["priority_rule"] = rule
        if split is not None:
            a["provider_split"] = split
        m = sim.step(a)
        rows.append(torch.stack([m[k] for k in sim.metric_names()], 1))
    return torch.stack(rows)


def test_spec_layout():
    sim = make(B=2)
    nf, ng = len(DISPATCH_FEATURES), len(DISPATCH_CONTEXT)
    assert len(DISPATCH_SCALE) == nf and len(set(DISPATCH_FEATURES)) == nf
    assert sim.dispatch_spec(0)["n_params"] == nf + nf * ng
    assert sim.dispatch_spec(16)["n_params"] == nf + nf * ng + (nf + ng) * 16 + 32
    # nothing a triage desk cannot know is a feature
    for bad in ("true", "latent", "patience_draw", "sev", "needs", "tdisp"):
        assert not any(bad in f for f in DISPATCH_FEATURES)


def test_off_is_neutral_and_inactive_rows_are_untouched():
    rule = torch.tensor([0, 1, 2, 3])
    ref = run(make(), rule)
    sim = make()
    assert sim._disp is None
    th = torch.randn((4, sim.dispatch_spec(8)["n_params"]), generator=torch.Generator().manual_seed(0)) * 50
    sim.set_dispatch_params(th, hidden=8, active=torch.zeros(4, dtype=torch.bool), unify=True)     # set, but no row uses it
    sim.enable_acuity_stats(True)
    sim.reset(SEEDS)
    assert torch.equal(run(sim, rule), ref)
    sim.set_dispatch_params(None)
    sim.reset(SEEDS)
    assert sim._disp is None and torch.equal(run(sim, rule), ref)


@pytest.mark.parametrize("scn", ["normal_week", "flu_surge"])
@pytest.mark.parametrize("hidden", [0, 8])
def test_hard_coded_rules_are_exact_special_cases(scn, hidden):
    rule = torch.tensor([0, 1, 2, 3])
    ref = run(make(scn), rule)
    sim = make(scn)
    th = torch.stack([sim.dispatch_rule_theta(r, hidden) for r in range(4)])
    if hidden:      # a network with random first layer and zero output weights adds exactly nothing
        sp = sim.dispatch_spec(hidden)
        n1 = (sp["n_features"] + sp["n_context"]) * hidden + hidden
        th[:, sp["n_linear"]:sp["n_linear"] + n1] = torch.randn((4, n1), generator=torch.Generator().manual_seed(1))
    sim.set_dispatch_params(th, hidden=hidden)
    sim.reset(SEEDS)
    got = run(sim, torch.full((4,), 3 if scn == "flu_surge" else 0))       # the head no longer matters on active rows
    assert torch.equal(got, ref)
    assert sim.dispatch_rule_theta("acuity_first").tolist() == sim.dispatch_rule_theta(1).tolist()


def test_batch_parameter_shapes_and_per_row_effect():
    sim = make()
    n = sim.dispatch_spec(0)["n_params"]
    with pytest.raises(ValueError):
        sim.set_dispatch_params(torch.zeros((3, n)))
    with pytest.raises(ValueError):
        sim.set_dispatch_params(torch.zeros((4, n + 1)))
    with pytest.raises(ValueError):
        sim.set_dispatch_params(torch.zeros((4, n)), hidden=4)
    sim.set_dispatch_params(sim.dispatch_rule_theta(1))                    # a single row broadcasts to the batch
    assert tuple(sim._disp["theta"].shape) == (4, n) and bool(sim._disp["active"].all())
    # two hospitals with the SAME seed and different parameters diverge; identical parameters do not
    sim = HospitalSim(load_scenario("flu_surge", overrides={"no_calibration": True}), batch_size=4, device="cpu", seed=torch.tensor([7, 7, 7, 7]))
    th = torch.stack([sim.dispatch_rule_theta(1), sim.dispatch_rule_theta(1), -sim.dispatch_rule_theta(1), sim.dispatch_rule_theta(3)])
    sim.set_dispatch_params(th)
    sim.reset(torch.tensor([7, 7, 7, 7]))
    out = run(sim, uniform=True)
    assert torch.equal(out[:, 0], out[:, 1])
    assert not torch.equal(out[:, 0], out[:, 2]) and not torch.equal(out[:, 0], out[:, 3])
    assert bool((sim.conservation()["residual"] == 0).all())


def test_context_and_network_terms_change_the_order_and_stay_finite():
    sim = HospitalSim(load_scenario("flu_surge", overrides={"no_calibration": True}), batch_size=4, device="cpu", seed=torch.tensor([7, 7, 7, 7]))
    sp = sim.dispatch_spec(8)
    nf, ng = sp["n_features"], sp["n_context"]
    g = torch.Generator().manual_seed(3)
    th = torch.stack([sim.dispatch_rule_theta(1, 8)] * 4)
    th[1, nf:nf + nf * ng] = 200 * torch.randn(nf * ng, generator=g)       # context interactions only
    th[2, sp["n_linear"]:] = 30 * torch.randn(sp["n_params"] - sp["n_linear"], generator=g)   # network only
    th[3] = float("nan")                                                   # garbage must not crash the sort
    sim.set_dispatch_params(th, hidden=8, unify=torch.tensor([False, False, True, False]))
    sim.reset(torch.tensor([7, 7, 7, 7]))
    out = run(sim, uniform=True)
    assert bool(torch.isfinite(out).all())
    assert not torch.equal(out[:, 0], out[:, 1]) and not torch.equal(out[:, 0], out[:, 2])


def test_unified_provider_queue_ignores_the_split_head():
    seeds = torch.tensor([7, 7, 7, 7])
    sim = HospitalSim(load_scenario("flu_surge", overrides={"no_calibration": True}), batch_size=4, device="cpu", seed=seeds)
    sim.set_dispatch_params(sim.dispatch_rule_theta(1), unify=torch.tensor([True, True, False, False]))
    sim.reset(seeds)
    out = run(sim, split=torch.tensor([0, 2, 0, 2]), uniform=True)
    assert torch.equal(out[:, 0], out[:, 1])               # unified: favor_new and favor_dispositions give the same trajectory
    assert not torch.equal(out[:, 2], out[:, 3])           # split kept: the head matters


def test_acuity_stats_add_up_and_do_not_touch_dynamics():
    ref = run(make())
    sim = make()
    sim.enable_acuity_stats(True)
    sim.reset(SEEDS)
    assert torch.equal(run(sim), ref)
    a = sim.acu_stats
    assert set(a) == set(ACU_STATS) and tuple(a["first_seen"].shape) == (4, 6)
    assert torch.allclose(a["first_seen"].sum(1), sim.ep["first_seen"])
    assert torch.allclose(a["wait_sum_min"].sum(1), sim.ep["door_to_provider_sum_min"], rtol=1e-5)
    assert torch.allclose(a["lwbs"].sum(1), sim.ep["lwbs"])
    assert bool((a["first_seen"][:, 0] == 0).all()) and bool((a["unseen_min"] >= 0).all())
