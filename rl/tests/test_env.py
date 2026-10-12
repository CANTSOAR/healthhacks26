import torch

from rl.common import IMPULSE_HEADS, OBJECTIVES, TERMS, weights_vec
from rl.env import ConcatEnv, HospitalEnv, reward_terms
from rl.managers import FixedPolicy, RandomPolicy, RulePolicy


def make(scales, B=3, hours=26, stage="stage_1", weights="balanced", seed=11, scenario="normal_week"):
    return HospitalEnv(scenario, B, "cpu", seed, hours, stage=stage, weights=weights, scales=scales, auto_reset=False)


def test_shapes_and_weights_in_observation(scales):
    env = make(scales)
    obs = env.reset()
    assert obs.shape == (3, env.sim.obs_dim + len(TERMS)) and env.obs_dim == obs.shape[1]
    assert torch.allclose(obs[:, -len(TERMS):], weights_vec("balanced").expand(3, -1))
    assert len(env.head_names) == len(env.head_sizes) == len(env.spec)
    pol = FixedPolicy()
    obs, r, done, info = env.step(pol.act(obs, env.action_mask()))
    assert r.shape == (3,) and done.shape == (3,) and done.dtype == torch.bool and torch.isfinite(obs).all()
    # tensor actions [B, H] are accepted too
    a = torch.tensor(env.defaults).unsqueeze(0).repeat(3, 1)
    obs, r, done, info = env.step(a)
    assert torch.isfinite(r).all()


def test_masks_follow_cadence_and_stage(scales):
    env = make(scales, stage="stage_1")
    env.reset()
    pol = FixedPolicy()
    for h in range(26):
        m = env.action_mask()
        for hd in env.spec:
            v = bool(m[hd["name"]].all())
            assert bool(m[hd["name"]].any()) == v
            if hd["cadence"] == "hourly":
                assert v
            elif hd["cadence"] == "daily":
                assert v == (h % 24 == 0)
            else:
                assert not v                       # weekly / monthly are disabled in stage_1
        env.step(pol.act(env.observe(), m))
    env3 = make(scales, stage="stage_3")
    env3.reset()
    assert all(bool(v.all()) for v in env3.action_mask().values())    # hour 0 of day 0 is every boundary


def test_masked_and_disabled_heads_keep_value(scales):
    env = make(scales, B=2, stage="stage_1")
    obs = env.reset()
    pol = RandomPolicy(seed=3, stage="stage_3")    # tries to move every head, including weekly/monthly
    obs, *_ = env.step(pol.act(obs, env.action_mask()))
    daily = {n: env.sim.settings[n].clone() for n in env.head_names if env.cadence[n] == "daily"}
    for _ in range(5):
        obs, *_ = env.step(pol.act(obs, env.action_mask()))
    for n, v in daily.items():                     # daily heads cannot change inside the day
        assert torch.equal(env.sim.settings[n], v)
    for hd in env.spec:                            # disabled cadences stay at default
        if hd["cadence"] in ("weekly", "monthly"):
            assert bool((env.sim.settings[hd["name"]] == hd["default"]).all())


def test_determinism_and_reward_recomputation(scales):
    outs = []
    for _ in range(2):
        env = make(scales, B=2, weights="min_wait", seed=5)
        pol = RulePolicy()
        pol.reset(2, "cpu")
        obs, rs = env.reset(), []
        for _ in range(26):
            obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
            m = info["metrics"]
            staff = m["overtime_hours"] + torch.relu(m["fatigue_mean"] - 0.5) * m["staff_on_shift"]
            raw = dict(cost=m["cost_total"], wait=m.get("waiting_patient_minutes", m["waiting_count"] * 60), lwbs=m["lwbs"], safety=m["adverse_events"],
                       boarding=m["boarding_hours"], staff=staff, revenue=-m["revenue"], labor=m["cost_labor"],
                       los=m["ed_census"], opcost=m["cost_labor"] + m["cost_fixed"])
            exp = -sum(OBJECTIVES["min_wait"].get(k, 0.0) * raw[k] / scales["scales"][k] for k in TERMS)
            assert torch.allclose(r, exp, rtol=1e-4, atol=1e-5)
            rs.append(r)
        assert bool(d.all()) and "summary" in info and torch.allclose(info["return_mean"], torch.stack(rs).mean(0), atol=1e-5)
        outs.append((torch.stack(rs), obs))
    assert torch.equal(outs[0][0], outs[1][0]) and torch.equal(outs[0][1], outs[1][1])


def test_auto_reset_moves_to_new_seeds(scales):
    env = HospitalEnv("normal_week", 2, "cpu", 7, 3, weights="balanced", scales=scales, auto_reset=True)
    obs = env.reset()
    pol = FixedPolicy()
    for _ in range(3):
        obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
    assert bool(d.all()) and "final_obs" in info and env.h == 0
    assert env.seeds.tolist() == [9, 10] and int(env.sim.t[0]) == 0


def test_concat_env_mixes_scenarios(scales):
    env = ConcatEnv([make(scales, B=2, hours=4), make(scales, B=2, hours=4, scenario="flu_surge")])
    obs = env.reset()
    assert obs.shape[0] == 4
    pol = FixedPolicy()
    for _ in range(4):
        obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
    assert r.shape == (4,) and info["summary"]["wait_mean_min"].shape == (4,) and info["terms_mean"].shape == (4, len(TERMS))
