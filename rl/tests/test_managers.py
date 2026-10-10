import gzip
import json

import torch

import rl
from rl.common import CONSTRAINED, OBJ_SLUG, TERMS, get_spec, objective_score, sim_fingerprint
from rl.env import HospitalEnv
from rl.managers import PARAM_NAMES, RULE_DEFAULT, LearnedPolicy, MultiPolicy, RulePolicy, load_manager, save_heuristic
from rl.net import ActorCritic
from rl.ppo import export_policy
from rl.record import decision_label, record, validate_rollout, write_index
from rl.tune import evaluate_population

KINDS = {"learned", "tuned_heuristic", "rule_based", "fixed", "random", "human"}


def test_list_managers_contract():
    rows = rl.list_managers()
    ids = [r["id"] for r in rows]
    assert {"fixed", "rule_based", "random"} <= set(ids) and len(ids) == len(set(ids))
    for r in rows:
        assert set(r) >= {"id", "kind", "label", "objective", "reward_weights", "available"}
        assert r["kind"] in KINDS and isinstance(r["available"], bool)
        if r["available"]:
            p = rl.load_manager(r["id"], device="cpu")
            assert p.id == r["id"] and p.kind == r["kind"]
    for slug in OBJ_SLUG.values():
        assert f"tuned_{slug}" in ids and f"ppo_{slug}" in ids


def test_policies_act_in_range_with_and_without_weights():
    sp = get_spec()
    obs = torch.rand(5, sp["obs_dim"])
    mask = {h["name"]: torch.ones(5, dtype=torch.bool) for h in sp["action_spec"]}
    for mid in ("fixed", "rule_based", "random"):
        p = load_manager(mid)
        p.reset(5, "cpu")
        for o in (obs, torch.cat([obs, torch.zeros(5, len(TERMS))], 1)):
            a = p.act(o, mask)
            for h in sp["action_spec"]:
                v = a[h["name"]]
                assert v.shape == (5,) and v.dtype == torch.long and int(v.min()) >= 0 and int(v.max()) < len(h["options"])
    a = load_manager("fixed").act(obs, mask)
    assert all(int(a[h["name"]][0]) == h["default"] for h in sp["action_spec"])


def test_learned_policy_roundtrip_cpu(tmp_path):
    sp = get_spec()
    sizes = [len(h["options"]) for h in sp["action_spec"]]
    net = ActorCritic(sp["obs_dim"] + len(TERMS), sizes, 32, 2, [h["default"] for h in sp["action_spec"]])
    cfg = dict(id="ppo_test", kind="learned", label="t", objective="balanced", reward_weights={"cost": 1.0}, type="ppo",
               obs_dim=net.obs_dim, sim_obs_dim=sp["obs_dim"], head_names=sp["head_names"], head_sizes=sizes,
               enabled_heads=[h["name"] for h in sp["action_spec"] if h["cadence"] in ("hourly", "daily")], hidden=32, layers=2)
    export_policy(net, cfg, tmp_path / "ppo_test")
    d = json.loads((tmp_path / "ppo_test.json").read_text())
    sd = torch.load(tmp_path / d["checkpoint"], map_location="cpu")
    assert all(isinstance(v, torch.Tensor) for v in sd.values())          # plain state_dict, no pickled classes
    p = LearnedPolicy(d, sd)
    obs = torch.rand(3, sp["obs_dim"])
    mask = {n: torch.ones(3, dtype=torch.bool) for n in sp["head_names"]}
    a1, a2 = p.act(obs, mask), p.act(torch.cat([obs, p.w.expand(3, -1)], 1), mask)
    for h in sp["action_spec"]:
        assert torch.equal(a1[h["name"]], a2[h["name"]])
        if h["cadence"] in ("weekly", "monthly"):
            assert bool((a1[h["name"]] == h["default"]).all())


def test_heuristic_save_load_and_population_eval(tmp_path, scales, monkeypatch):
    import rl.managers as M
    monkeypatch.setattr(M, "POLICY_DIR", tmp_path)
    th = torch.rand(len(PARAM_NAMES))
    pol = RulePolicy(th, id="tuned_x", kind="tuned_heuristic", label="x", objective="min_cost", reward_weights={"cost": 1.0})
    save_heuristic(tmp_path / "tuned_x.json", pol)
    q = M.load_manager("tuned_x")
    assert q.kind == "tuned_heuristic" and torch.allclose(q.theta, th, atol=1e-3)
    assert any(r["id"] == "tuned_x" and r["available"] for r in M.list_managers())
    cand = torch.stack([torch.tensor([RULE_DEFAULT[k] for k in PARAM_NAMES]), th])
    sc, summ = evaluate_population(cand, CONSTRAINED, ["normal_week"], 2, 200_000, 1, "cpu", scales)
    assert sc.shape == (2,) and torch.isfinite(sc).all() and summ["cost_per_day"].shape == (2,)


def test_objective_score_constraint_penalty():
    tm = torch.zeros(2, len(TERMS))
    tm[:, 0] = 1.0
    s = objective_score(CONSTRAINED, tm, torch.tensor([100.0, 240.0]), 120.0)
    assert torch.allclose(s, torch.tensor([-1.0, -6.0]))


def test_rollouts_validate_and_share_patients(tmp_path, scales, monkeypatch):
    import rl.record as R
    monkeypatch.setattr(R, "load_scales", lambda: scales)
    rows = [record(m, "normal_week", days=2, busy_day=1, out_dir=tmp_path) for m in ("fixed", "random")]
    rolls = []
    for r in rows:
        with gzip.open(tmp_path / r["file"], "rt") as f:
            rolls.append(json.load(f))
    for roll in rolls:
        validate_rollout(roll)
        h = roll["header"]
        assert h["synthetic"] is True and h["sim_fingerprint"] == sim_fingerprint() and h["days"] == 2
        assert all(len(v) == 48 for v in roll["hourly"].values()) and set(roll["hourly"]) == set(get_spec()["metric_names"])
        assert roll["segments"] and len(roll["segments"][0]["snapshots"]) == 12 * 12 + 1
        assert roll["segments"][0]["snapshots"][0]["t"] == roll["segments"][0]["start_t"]
    # common random numbers: both managers face the same patients (arrivals excludes diverted ambulances, so add them back)
    exo = [[a + d for a, d in zip(r["hourly"]["arrivals"], r["hourly"]["diverted"])] for r in rolls]
    assert exo[0] == exo[1] and sum(exo[0]) > 0
    assert rolls[0]["decisions"] == [] and len(rolls[1]["decisions"]) > 10
    d = rolls[1]["decisions"][0]
    assert set(d) >= {"t", "head", "value", "label", "cadence"} and ":" in d["label"]
    idx = write_index(tmp_path)
    assert len(idx) == 2 and set(idx[0]) >= {"rollout_id", "manager", "scenario", "seed", "days", "summary", "has_segments"}
    spec = {h["name"]: h for h in get_spec()["action_spec"]}
    lab = decision_label(spec["rn_night"], 2, 1)
    assert lab.startswith("Nurses, night shift: ") and "->" in lab and str(spec["rn_night"]["values"][1]) in lab


def test_multipolicy_matches_single(scales):
    env = HospitalEnv("normal_week", 4, "cpu", torch.tensor([3, 4, 3, 4]), 6, weights="balanced", scales=scales, auto_reset=False)
    mp = MultiPolicy([load_manager("fixed"), load_manager("rule_based")], [2, 2])
    mp.reset(4, "cpu")
    obs = env.reset()
    for _ in range(6):
        obs, r, d, info = env.step(mp.act(obs, env.action_mask()))
    exo = info["metrics"]["arrivals"] + info["metrics"]["diverted"]
    assert torch.equal(exo[:2], exo[2:])


def test_behaviour_fingerprint_and_conditioned_presets(tmp_path, monkeypatch):
    from rl.common import behaviour_fingerprint, weights_dict
    import rl.managers as M
    fp = behaviour_fingerprint()
    assert len(fp) == 16 and fp == behaviour_fingerprint()
    sp = get_spec()
    sizes = [len(h["options"]) for h in sp["action_spec"]]
    net = ActorCritic(sp["obs_dim"] + len(TERMS), sizes, 16, 1)
    cfg = dict(id="ppo_cond", kind="learned", label="c", objective=None, reward_weights=weights_dict("balanced"), type="ppo",
               weight_conditioned=True, obs_dim=net.obs_dim, sim_obs_dim=sp["obs_dim"], head_names=sp["head_names"], head_sizes=sizes,
               hidden=16, layers=1, sim_behaviour_fingerprint=fp)
    export_policy(net, cfg, tmp_path / "ppo_cond")
    monkeypatch.setattr(M, "POLICY_DIR", tmp_path)
    rows = {r["id"]: r for r in M.list_managers()}
    assert rows["ppo_cond"]["available"] and rows["ppo_cond_min_wait"]["available"]
    p = M.load_manager("ppo_cond_min_wait")
    assert p.id == "ppo_cond_min_wait" and p.objective == "min_wait" and p.reward_weights == weights_dict("min_wait")
    assert p.behaviour_fingerprint == fp
    q = M.load_manager("ppo_cond")
    q.set_weights({"wait": 2.0})
    assert float(q.w[TERMS.index("wait")]) == 2.0
    # a conditioned agent uses its own weights even when the observation already carries (other) weights
    obs = torch.rand(2, sp["obs_dim"])
    mask = {n: torch.ones(2, dtype=torch.bool) for n in sp["head_names"]}
    a1 = p.act(obs, mask)
    a2 = p.act(torch.cat([obs, torch.full((2, len(TERMS)), 9.0)], 1), mask)
    assert all(torch.equal(a1[n], a2[n]) for n in sp["head_names"])
