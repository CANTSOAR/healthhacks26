"""Custom (user-picked) reward: ranks -> weights, the goal index, and the scale that keeps rank order honest."""
import pytest
import torch

from rl import objectives as O
from rl.custom import METRIC_MENU, goal_weights, measure_scales, register, score_groups
from rl.objectives import EPISODE_METRICS


@pytest.fixture(autouse=True)
def _unregister_custom_objective():
    """register() installs the user's objective process-wide; other tests iterate over OPERATOR_OBJECTIVES."""
    yield
    O.OPERATOR_OBJECTIVES.pop("custom", None)


def _vec(**kw):
    v = torch.ones(len(EPISODE_METRICS))
    for k, x in kw.items():
        v[EPISODE_METRICS.index(k)] = x
    return v


def test_ranks_halve_and_sum_to_one():
    signed, rows = goal_weights([dict(metric="profit", direction="max", rank=1), dict(metric="wait", direction="min", rank=2),
                                 dict(metric="walkouts", direction="min", rank=5), dict(metric="deaths", direction="ignore")])
    w = {r["metric"]: r["weight"] for r in rows}
    assert w["profit"] == pytest.approx(4 / 7) and w["wait"] == pytest.approx(2 / 7) and w["walkouts"] == pytest.approx(1 / 7)
    assert signed["margin_per_day"] < 0 < signed["wait_mean_min"] and "deaths_per_10k" not in signed
    assert sum(abs(v) for v in signed.values()) == pytest.approx(1.0)
    assert not rows[0]["against_the_grain"]
    assert goal_weights([dict(metric="wait", direction="max", rank=1)])[1][0]["against_the_grain"]


def test_empty_and_unknown_goals_are_rejected():
    with pytest.raises(ValueError):
        goal_weights([dict(metric="wait", direction="ignore")])
    with pytest.raises(ValueError):
        goal_weights([dict(metric="nope", direction="min", rank=1)])
    for v in METRIC_MENU.values():
        assert sum(v["parts"].values()) == pytest.approx(1.0) and all(k in EPISODE_METRICS for k in v["parts"])


def test_index_is_one_at_baseline_and_follows_direction():
    signed, _ = goal_weights([dict(metric="profit", direction="max", rank=1), dict(metric="wait", direction="min", rank=2)])
    base = _vec(margin_per_day=400_000.0, wait_mean_min=20.0)
    assert float(O.goal_index(signed, base, base)) == pytest.approx(1.0)
    assert float(O.goal_index(signed, _vec(margin_per_day=420_000.0, wait_mean_min=20.0), base)) < 1.0
    assert float(O.goal_index(signed, _vec(margin_per_day=400_000.0, wait_mean_min=25.0), base)) > 1.0


def test_scales_stop_a_swingy_low_rank_metric_outvoting_rank_one():
    """Profit rank 1 moves a few percent at most, wait rank 2 can halve: on raw ratios the wait gain buys a profit
    loss; on achievable-movement scales it does not."""
    signed, _ = goal_weights([dict(metric="profit", direction="max", rank=1), dict(metric="wait", direction="min", rank=2)])
    base = _vec(margin_per_day=400_000.0, wait_mean_min=20.0)
    g = torch.Generator().manual_seed(0)
    cand = base.repeat(40, 1)
    cand[:, EPISODE_METRICS.index("margin_per_day")] += 8_000.0 * torch.randn(40, generator=g)
    cand[:, EPISODE_METRICS.index("wait_mean_min")] += 5.0 * torch.randn(40, generator=g)
    scales = measure_scales([dict(base=base, cand=cand)], signed)
    assert 4_000 < scales["margin_per_day"] < 16_000 and 2.0 < scales["wait_mean_min"] < 10.0
    trade = _vec(margin_per_day=390_000.0, wait_mean_min=14.0)          # profit -2.5%, wait -30%
    assert float(O.goal_index(signed, trade, base)) < 1.0               # raw ratios: looks like a win
    assert float(O.goal_index(signed, trade, base, scales)) > 1.0       # scaled: rank 1 was sold, a loss


def test_score_groups_ranks_candidates_and_applies_guardrails():
    reg = register(dict(goals=[dict(metric="wait", direction="min", rank=1)], guardrails=True))
    base = _vec(wait_mean_min=20.0, deaths_per_10k=5.0, adverse_events_per_day=0.5, hi_acuity_wait_hours_per_day=6.0, staff_hours_per_day=1000.0)
    good, bad, unsafe = base.clone(), base.clone(), base.clone()
    good[EPISODE_METRICS.index("wait_mean_min")] = 15.0
    bad[EPISODE_METRICS.index("wait_mean_min")] = 25.0
    unsafe[EPISODE_METRICS.index("wait_mean_min")] = 10.0
    unsafe[EPISODE_METRICS.index("hi_acuity_wait_hours_per_day")] = 12.0
    groups = [dict(base=base, cand=torch.stack([base, good, bad, unsafe])) for _ in range(2)]      # 1 member x 2 scenarios
    sc = score_groups(groups, reg["signed_weights"], None, 2)
    assert sc[1] > sc[0] > sc[2] and sc[3] < sc[1]
    reg = register(dict(goals=[dict(metric="wait", direction="min", rank=1)], guardrails=False))
    assert score_groups(groups, reg["signed_weights"], None, 2)[3] > sc[1]


def test_patient_experience_proxy_is_inverted():
    signed, rows = goal_weights([dict(metric="patient_experience", direction="max", rank=1)])
    assert all(v > 0 for v in signed.values()) and not rows[0]["against_the_grain"]        # maximise experience = minimise its parts
    assert all(v < 0 for v in goal_weights([dict(metric="patient_experience", direction="min", rank=1)])[0].values())
