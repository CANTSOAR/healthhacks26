"""Per-hospital artefacts, ensemble environments, constrained operator objectives and the headline maths."""
import argparse
import json

import pytest
import torch

import rl.common as C
import rl.managers as M
from rl.env import ConcatEnv, HospitalEnv
from rl.headline import bootstrap_weights, build, ensemble_coverage, paired_table, write_markdown
from rl.managers import FixedPolicy, MultiPolicy, PARAM_NAMES, RULE_DEFAULT, RulePolicy, save_heuristic, theta_from_dict
from rl.objectives import (EPISODE_METRICS, LOCKED_HEADS, OPERATOR_OBJECTIVES, OPERATOR_STAGE, feasibility, flow_index, operator_score,
                           robust_aggregate, violations)
from rl.rollout import group_task, run_group
from rl.tune import baseline_theta, evaluate_population

K = len(EPISODE_METRICS)
J = {k: i for i, k in enumerate(EPISODE_METRICS)}


def base_vec():
    v = torch.zeros(K)
    for k, x in dict(wait_mean_min=20.0, wait_p95_min=60.0, ed_los_median_min=200.0, lwbs_rate=0.015, boarding_hours_per_day=6.0,
                     labor_cost_per_day=77000.0, operating_cost_per_day=470000.0, deaths_per_10k=5.0, adverse_events_per_day=0.4,
                     hi_acuity_wait_hours_per_day=3.0, diversion_hours_per_day=0.0, overtime_hours_per_day=0.0, transfers_per_day=3.0,
                     staff_hours_per_day=1200.0, arrivals_per_day=222.0, lwbs_per_day=3.3, margin_per_day=4.4e5,
                     ed_patient_hours_per_day=900.0, wait_patient_hours_per_day=80.0).items():
        v[J[k]] = x
    return v


@pytest.fixture
def ensemble(tmp_path, monkeypatch):
    """A two-member calibration ensemble for the default hospital, in a temp catalog directory (catalog/ is read-only)."""
    d = tmp_path / "cat"
    d.mkdir()
    (d / "rwjuh_nb.yaml").write_text("placeholder: 1\n")
    ens = dict(hospital_id="rwjuh_nb", members=[
        dict(id=0, overrides={}, baseline_actions={}, fit={"loss": 0.0}),
        dict(id=1, overrides={"arrival_scale": 1.3}, baseline_actions={"md_night": 0, "rn_evening": 3}, fit={"loss": 0.1})])
    (d / "rwjuh_nb.ensemble.json").write_text(json.dumps(ens))
    monkeypatch.setattr(C, "CATALOG_HOSPITALS", d)
    return d


# ---------------------------------------------------------------------------------- constraint scoring
def test_operator_score_rewards_flow_and_penalises_violations():
    b = base_vec()
    same = operator_score("same_budget_better_flow", b, b, margin=False)
    assert abs(float(same)) < 1e-6 and abs(float(flow_index(b, b)) - 1.0) < 1e-6
    better = b.clone()
    better[J["wait_mean_min"]] = 10.0                                  # half the wait, nothing else moves
    assert abs(float(operator_score("same_budget_better_flow", better, b, margin=False)) - 0.15) < 1e-5
    over = better.clone()
    over[J["labor_cost_per_day"]] = 77000.0 * 1.05                     # 5% over the labour budget: the gain is wiped out
    assert float(operator_score("same_budget_better_flow", over, b, margin=False)) < -0.3
    v = violations("same_budget_better_flow", over, b)
    assert abs(float(v["labor_cost_per_day"]) - 0.05) < 1e-5 and float(v["operating_cost_per_day"]) <= 0
    # the tuning margin asks for head-room: exactly-at-baseline is penalised with margin, not without
    assert float(operator_score("same_budget_better_flow", b, b, margin=True)) < 0
    # batched: [N, K] candidates against one baseline
    sc = operator_score("same_budget_better_flow", torch.stack([b, better, over]), b.unsqueeze(0), margin=False)
    assert sc.shape == (3,) and float(sc[1]) > float(sc[0]) > float(sc[2])


def test_cannot_buy_the_objective_with_diversion_walkouts_or_overtime():
    b = base_vec()
    as_d = lambda v: {k: float(v[J[k]]) for k in EPISODE_METRICS}       # noqa: E731
    for obj in OPERATOR_OBJECTIVES:
        cheat = b.clone()
        cheat[J["labor_cost_per_day"]] *= 0.8
        cheat[J["wait_mean_min"]] *= 0.5
        cheat[J["diversion_hours_per_day"]] = 6.0                      # diverting ambulances
        f = feasibility(obj, as_d(cheat), as_d(b))
        assert not f["feasible"] and "diversion_hours_per_day" in f["violated"]
        assert float(operator_score(obj, cheat, b, margin=False)) < 0
        ot = b.clone()
        ot[J["overtime_hours_per_day"]] = 0.01 * 1200.0 + 1.0          # above baseline + 1% of staff-hours
        assert "overtime_hours_per_day" in feasibility(obj, as_d(ot), as_d(b))["violated"]
        ot[J["overtime_hours_per_day"]] = 0.01 * 1200.0 - 1.0
        assert "overtime_hours_per_day" not in feasibility(obj, as_d(ot), as_d(b))["violated"]
    shed = b.clone()                                                   # cheaper by letting patients walk out
    shed[J["labor_cost_per_day"]] *= 0.8
    shed[J["lwbs_rate"]] = 0.05
    f = feasibility("same_service_lower_cost", as_d(shed), as_d(b))
    assert not f["feasible"] and f["violated"] == ["lwbs_rate"]
    assert float(operator_score("same_service_lower_cost", shed, b, margin=False)) < 0
    worse = b.clone()
    worse[J["deaths_per_10k"]] = 6.0
    f = feasibility("same_budget_better_flow", as_d(worse), as_d(b), {"deaths_per_10k": (-0.5, 2.5)})
    row = next(r for r in f["constraints"] if r["metric"] == "deaths_per_10k")
    assert not f["feasible"] and row["status"] == "worse (difference not significant)"
    assert float(robust_aggregate(torch.tensor([[0.2, 0.1, 0.0, -0.3]]))) == pytest.approx(0.5 * 0.0 + 0.5 * -0.3)


def test_locked_heads_cannot_be_moved_by_any_policy(scales):
    env = HospitalEnv("normal_week", 2, "cpu", 5, 30, stage=OPERATOR_STAGE, weights="same_budget_better_flow", scales=scales,
                      auto_reset=False, locked_heads=LOCKED_HEADS)
    assert not env.enabled["divert"] and not env.enabled["admission_cap"] and env.enabled["call_in"] and env.enabled["agency_contract"]
    assert not env.enabled["bays_delta"]                               # structural heads are outside the operator stage
    obs = env.reset()
    for _ in range(30):
        a = {n: torch.full((2,), s - 1, dtype=torch.long) for n, s in zip(env.head_names, env.head_sizes)}   # push every head to its last option
        obs, r, d, info = env.step(a)
        assert int(env.sim.settings["divert"].max()) == 0 and int(env.sim.settings["admission_cap"].max()) == 0
    ep = info["episode"]
    assert ep.shape == (2, K) and torch.isfinite(ep).all()
    assert float(ep[:, J["diversion_hours_per_day"]].max()) == 0.0
    assert torch.allclose(ep[:, J["operating_cost_per_day"]], ep[:, J["labor_cost_per_day"]] + ep[:, J["fixed_cost_per_day"]], rtol=1e-5)
    assert torch.allclose(ep[:, J["wait_mean_min"]], info["summary"]["wait_mean_min"])
    # a rule manager built for an operator objective does not touch the locked heads either
    th = theta_from_dict(dict(RULE_DEFAULT, divert_thr=0.0, admission_cap=1.0))
    pol = RulePolicy(th, stage=OPERATOR_STAGE, locked=LOCKED_HEADS)
    o = torch.rand(3, len(pol.obs_names)) * 3
    mask = {n: torch.ones(3, dtype=torch.bool) for n in pol.head_names}
    act = pol.act(o, mask)
    assert int(act["divert"].max()) == pol.defaults["divert"] and int(act["admission_cap"].max()) == pol.defaults["admission_cap"]
    assert int(RulePolicy(th, stage=OPERATOR_STAGE).act(o, mask)["divert"].max()) == 1


def test_new_rule_parameters_are_neutral_by_default(scales):
    """A 21-parameter (version 1) rule and the same rule padded with the new defaults act identically."""
    from rl.managers import N_PARAMS_V1
    assert len(PARAM_NAMES) > N_PARAMS_V1 and PARAM_NAMES[N_PARAMS_V1 - 1] == "imaging_hours"
    th = torch.rand(4, N_PARAMS_V1)
    old = RulePolicy(th, stage="stage_2")
    assert old.theta.shape == (4, len(PARAM_NAMES))
    env = HospitalEnv("normal_week", 4, "cpu", 3, 30, stage="stage_2", weights="balanced", scales=scales, auto_reset=False)
    obs = env.reset()
    v1 = {k: th[:, i] for i, k in enumerate(PARAM_NAMES[:N_PARAMS_V1])}
    for _ in range(30):
        act = old.act(obs, env.action_mask())
        o = lambda n: obs[:, old.oi[n]]                                                           # noqa: E731
        assert torch.equal(act["discharge_push"], (o("ward_occupancy") > 0.5 + 0.6 * v1["discharge_push_occ"]).long())
        assert torch.equal(act["provider_split"], torch.floor(v1["provider_split"] * 3).clamp(0, 2).long())
        assert torch.equal(act["fast_track"], (o("waiting_esi45") >= 0.3 * (v1["fast_track_thr"] - 0.3)).long())
        obs, *_ = env.step(act)
    # the new triggers do something when switched on
    on = RulePolicy(theta_from_dict(dict(RULE_DEFAULT, ft_close_night=1.0, split_new_thr=0.0, rn_dow_gain=1.0)), stage="stage_2")
    env.reset()
    a0 = on.act(env.observe(), env.action_mask())                      # hour 0 = night
    assert int(a0["fast_track"].max()) == 0
    o2 = env.observe().clone()
    o2[:, on.oi["q_waiting_provider"]] = 0.2
    assert int(on.act(o2, env.action_mask())["provider_split"].max()) == 0          # favour new patients when the provider queue is long


# ---------------------------------------------------------------------------------- hospital-keyed artefacts
def test_paths_and_hospital_keyed_loading(tmp_path, monkeypatch):
    monkeypatch.delenv("HOSPITAL_ID", raising=False)
    assert C.hospital_id() == "rwjuh_nb" and C.hospital_id("x") == "x"
    assert C.paths().policies == C.POLICY_DIR and C.paths().results == C.RESULTS_DIR and C.paths().scales == C.SCALES_PATH
    monkeypatch.setattr(C, "HOSPITALS_DIR", tmp_path / "hospitals")
    p = C.paths("other_hospital")
    assert p.policies == tmp_path / "hospitals" / "other_hospital" / "policies" and p.home == tmp_path / "hospitals" / "other_hospital"
    assert C.paths("rwjuh_nb").home == tmp_path / "hospitals" / "rwjuh_nb"       # headline of the default hospital
    monkeypatch.setenv("HOSPITAL_ID", "other_hospital")
    assert C.hospital_id() == "other_hospital" and C.paths().policies == p.policies
    monkeypatch.setattr(M, "POLICY_DIR", tmp_path / "default_policies")
    pol = RulePolicy(torch.rand(len(PARAM_NAMES)), id="tuned_same_budget", kind="tuned_heuristic", label="x",
                     objective="same_budget_better_flow", stage=OPERATOR_STAGE, hospital="other_hospital", locked=LOCKED_HEADS)
    save_heuristic(M.policy_dir("other_hospital") / "tuned_same_budget.json", pol)
    d = json.loads((p.policies / "tuned_same_budget.json").read_text())
    assert d["hospital_id"] == "other_hospital" and d["calibration_fingerprint"] == C.calibration_fingerprint("other_hospital")
    assert d["locked_heads"] == list(LOCKED_HEADS) and len(d["params"]) == len(PARAM_NAMES)
    rows = {r["id"]: r for r in M.list_managers()}                     # HOSPITAL_ID is honoured
    assert rows["tuned_same_budget"]["available"] and rows["tuned_same_budget"]["stale"] is False
    q = M.load_manager("tuned_same_budget")
    assert q.hospital == "other_hospital" and q.locked == LOCKED_HEADS and q.stage == OPERATOR_STAGE and q.stale is False
    rows = {r["id"]: r for r in M.list_managers("rwjuh_nb")}           # explicit id wins; the other hospital's file is not offered
    assert not rows["tuned_same_budget"]["available"] and {"tuned_same_service", "ppo_same_budget", "tuned_min_cost"} <= set(rows)
    with pytest.raises(KeyError):
        M.load_manager("tuned_same_budget", hospital="rwjuh_nb")
    assert M.load_manager("fixed", hospital="rwjuh_nb").hospital == "rwjuh_nb"


def test_staleness_follows_the_hospitals_calibration(ensemble):
    art = dict(id="x", **C.fingerprints("rwjuh_nb"))
    assert art["hospital_id"] == "rwjuh_nb" and not C.is_stale(art)
    st = C.calibration_status("rwjuh_nb")
    assert st["ensemble_file"] and st["n_members"] == 2 and not st["calibration_file"]
    (ensemble / "rwjuh_nb.ensemble.json").write_text(json.dumps(dict(hospital_id="rwjuh_nb", members=[dict(id=0, overrides={"arrival_scale": 0.9})])))
    assert C.is_stale(art) and C.calibration_fingerprint("rwjuh_nb") != art["calibration_fingerprint"]
    assert C.calibration_fingerprint("rwjuh_nb") != C.calibration_fingerprint("mount_sinai")
    assert not C.is_stale(dict(id="old artefact without the fields"))
    assert C.is_stale(dict(sim_behaviour_fingerprint="0000000000000000"), "rwjuh_nb")


# ---------------------------------------------------------------------------------- ensemble environments
def test_ensemble_members_and_domain_randomised_concat_env(ensemble, scales):
    ens = C.load_ensemble("rwjuh_nb")
    assert ens["exists"] and [m["id"] for m in ens["members"]] == [0, 1]
    assert C.load_ensemble("no_such_hospital")["members"] == [dict(id=0, overrides={}, baseline_actions={}, fit=None)]
    ov = C.member_overrides("rwjuh_nb", 1)
    assert ov == {"hospital_id": "rwjuh_nb", "arrival_scale": 1.3, "baseline_actions": {"md_night": 0, "rn_evening": 3}}
    mk = lambda m: HospitalEnv("normal_week", 2, "cpu", 7, 24, stage="stage_1", weights="balanced", scales=scales, auto_reset=False,   # noqa: E731
                               hospital="rwjuh_nb", member=m)
    e0, e1 = mk(0), mk(1)
    i = e0.head_names.index("md_night")
    assert e1.defaults[i] == 0 and e0.defaults[i] != 0 and e1.defaults[e1.head_names.index("rn_evening")] == 3
    env = ConcatEnv([e0, e1])
    da = env.default_actions()
    assert da["md_night"].tolist() == [e0.defaults[i]] * 2 + [0, 0]
    pol = MultiPolicy([FixedPolicy(), RulePolicy()], [2, 2])           # the baseline follows each row's own member
    fixed_all = FixedPolicy()
    fixed_all.reset(env.B, env.device, da)
    obs = env.reset()
    arr = torch.zeros(4)
    for _ in range(24):
        act = fixed_all.act(obs, env.action_mask())
        assert act["md_night"].tolist() == da["md_night"].tolist()
        obs, r, d, info = env.step(act)
        arr += info["metrics"]["arrivals"]
    assert info["episode"].shape == (4, K) and bool(d.all())
    assert float(arr[2:].sum()) > float(arr[:2].sum())                 # member 1 has 30% more arrivals
    assert int(e1.sim.settings["md_night"].max()) == 0 and int(e0.sim.settings["md_night"].min()) == e0.defaults[i]
    env.replace(1, mk(0))                                              # redraw the member in a slot
    assert env.default_actions()["md_night"].tolist() == [e0.defaults[i]] * 4
    pol.reset(4, "cpu", env.default_actions())
    assert set(pol.act(env.reset(), env.action_mask())) == set(env.head_names)


def test_group_rollout_and_robust_tuning_over_members(ensemble, scales):
    th = torch.stack([baseline_theta("rwjuh_nb"), theta_from_dict(RULE_DEFAULT)])
    t = group_task("rwjuh_nb", "normal_week", 1, [{"id": "fixed"}, {"theta": th.tolist(), "stage": OPERATOR_STAGE, "locked": list(LOCKED_HEADS)}],
                   [200_000, 200_001], 1, stage=OPERATOR_STAGE, locked=LOCKED_HEADS, scales=scales, want_actions=True)
    r = run_group(t)
    assert r["episode"].shape == (3, 2, K) and r["names"] == ["fixed", "theta0", "theta1"] and r["defaults"]["md_night"] == 0
    assert r["actions"]["md_night"].shape[0] == 3 and float(r["actions"]["md_night"][0, :, 0].min()) == 1.0     # baseline rows sit at the member's default
    assert torch.allclose(r["actions"]["fast_track"].sum(-1), torch.ones(3, 24))
    # the baseline-equivalent rule starts where the baseline is (same staffing; never diverts)
    assert float(r["episode"][1, :, J["diversion_hours_per_day"]].max()) == 0.0
    sc, summ, groups = evaluate_population(th, "same_budget_better_flow", ["normal_week"], 2, 200_000, 1, "cpu", scales, OPERATOR_STAGE,
                                           hospital="rwjuh_nb", members=[0, 1], detail=True)
    assert sc.shape == (2,) and torch.isfinite(sc).all() and len(groups) == 2 and set(summ) == set(EPISODE_METRICS)
    assert float(groups[1]["base"][J["arrivals_per_day"]]) > float(groups[0]["base"][J["arrivals_per_day"]])
    sc2, _ = evaluate_population(th, "min_wait", ["normal_week"], 2, 200_000, 1, "cpu", scales, hospital="rwjuh_nb", members=[1])
    assert sc2.shape == (2,) and torch.isfinite(sc2).all()


# ---------------------------------------------------------------------------------- headline maths
def test_paired_table_and_ensemble_coverage():
    g = torch.Generator().manual_seed(0)
    Mm, S = 4, 16
    base = base_vec().expand(Mm, S, K).clone() * (1 + 0.05 * torch.randn((Mm, S, 1), generator=g))
    cand = base.clone()
    cand[..., J["wait_mean_min"]] *= 0.8                               # exactly 20% lower on every paired episode
    cand[..., J["labor_cost_per_day"]] *= 0.99
    cand[..., J["margin_per_day"]] += 1000.0 * torch.randn((Mm, S), generator=g)
    cand[3, :, J["labor_cost_per_day"]] = base[3, :, J["labor_cost_per_day"]] * 1.02      # one twin goes over budget
    T = paired_table(cand, base, reps=500)
    w = T["wait_mean_min"]
    assert w["pct"] == pytest.approx(-20.0, abs=1e-3) and w["pct_ci95"][0] == pytest.approx(-20.0, abs=1e-3) and w["pct_ci95"][1] == pytest.approx(-20.0, abs=1e-3)
    assert w["diff"] == pytest.approx(w["policy"] - w["baseline"]) and w["diff_ci95"][0] <= w["diff"] <= w["diff_ci95"][1] < 0
    m = T["margin_per_day"]
    assert m["diff_ci95"][0] < 0 < m["diff_ci95"][1]                   # pure noise: the interval covers zero
    assert T["lwbs_rate"]["diff"] == 0.0 and T["diversion_hours_per_day"]["pct"] is None
    wm, ws = bootstrap_weights(Mm, S, 50)
    assert torch.allclose(wm.sum(1), torch.ones(50, dtype=torch.float64)) and torch.allclose(ws.sum(1), torch.ones(50, dtype=torch.float64))
    assert float(bootstrap_weights(1, S, 5)[0].min()) == 1.0           # a single member is never resampled away
    cov = ensemble_coverage("same_budget_better_flow", cand, base, [0, 1, 2, 3])
    assert cov["n_members"] == 4 and cov["holds"] == 3 and cov["share"] == 0.75
    assert [r["holds"] for r in cov["members"]] == [True, True, True, False] and cov["members"][3]["violated"] == ["labor_cost_per_day"]
    assert cov["worst_member"]["objective_ratio"] == pytest.approx(1 - 0.3 * 0.2, abs=1e-4)


def test_headline_end_to_end_tiny(ensemble, scales, tmp_path, monkeypatch):
    """Selection on validation seeds, held-out evaluation over two ensemble members, report written. One-day episodes."""
    import rl.common as CC
    monkeypatch.setattr(M, "POLICY_DIR", tmp_path / "policies")
    monkeypatch.setattr(CC, "SCALES_PATH", tmp_path / "reward_scales.json")
    CC.write_json(tmp_path / "reward_scales.json", scales)
    for slug, obj, th in (("same_budget", "same_budget_better_flow", baseline_theta("rwjuh_nb")),
                          ("same_service", "same_service_lower_cost", theta_from_dict(RULE_DEFAULT))):
        pol = RulePolicy(th, id=f"tuned_{slug}", kind="tuned_heuristic", label=f"Tuned heuristic: {slug}", objective=obj,
                         stage=OPERATOR_STAGE, hospital="rwjuh_nb", locked=LOCKED_HEADS)
        save_heuristic(tmp_path / "policies" / f"tuned_{slug}.json", pol)
    a = argparse.Namespace(hospital="rwjuh_nb", device="cpu", gpu_workers=0, cpu_workers=0, seeds=2, days=1, max_members=0, select_seeds=2,
                           select_days=1, select_members=1, stress=[], stress_seeds=1, stress_days=1, stress_members=1, context=["rule_based"],
                           reps=200)
    H, raw = build(a, log=lambda s: None)
    assert H["synthetic"] is True and H["hospital_id"] == "rwjuh_nb" and H["ensemble"]["n_members"] == 2
    assert H["calibration_fingerprint"] == C.calibration_fingerprint("rwjuh_nb")
    assert min(H["protocol"]["seeds"]) >= 9_000_000 and 900_000 <= min(H["protocol"]["select_seeds"]) < 1_000_000
    O = H["objectives"]["same_budget_better_flow"]
    assert O["selected"] == "tuned_same_budget" and set(O["candidates"]["tuned_same_budget"]) == {"normal_week", "flu_surge"}
    blk = O["candidates"]["tuned_same_budget"]["normal_week"]
    for k in ("ed_los_median_min", "wait_mean_min", "wait_p95_min", "lwbs_rate", "boarding_hours_per_day", "labor_cost_per_day",
              "margin_per_day", "deaths_per_10k", "diversion_hours_per_day", "overtime_hours_per_day"):
        r = blk["metrics"][k]
        assert set(r) == {"baseline", "policy", "diff", "diff_ci95", "pct", "pct_ci95"} and r["diff_ci95"][0] <= r["diff_ci95"][1]
    assert blk["metrics"]["diversion_hours_per_day"]["policy"] == 0.0
    assert blk["ensemble"]["n_members"] == 2 and isinstance(blk["feasibility"]["feasible"], bool) and len(blk["feasibility"]["constraints"]) == 8
    assert len(O["annualised"]["rows"]) == 6 and O["annualised"]["annual_ed_visits"] > 50_000
    assert any("Providers scheduled per shift" in x for x in O["what_changes"]) and any("locked" in x for x in O["what_changes"])
    assert "simulated" in H["sentence"].lower() and "plausible twins" in H["sentence"] and len(H["caveats"]) >= 5
    assert H["publishable"] is False and H["sentence"].startswith("[UNCALIBRATED PIPELINE SMOKE RUN")       # no calibration file
    assert "rule_based" in H["context"] and raw["metrics"] == EPISODE_METRICS
    assert torch.tensor(raw["values"]["normal_week"]["fixed"]).shape == (2, 2, K)
    write_markdown(H, tmp_path / "HEADLINE.md")
    md = (tmp_path / "HEADLINE.md").read_text()
    assert "ALL NUMBERS SIMULATED" in md and "## Caveats" in md and "Same service, lower cost" in md and "no calibration file yet" in md and "NOT A HEADLINE" in md
