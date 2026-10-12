"""Marginal-value attribution: ladder rebuild, verified manipulations, paired statistics, re-scoring, a tiny end-to-end run."""
import json
import math

import pytest
import torch

import rl.attribution as A
from rl.common import OBJECTIVES, TERMS
from rl.objectives import EPISODE_METRICS

J = {k: i for i, k in enumerate(EPISODE_METRICS)}
H = "rwjuh_nb"


def test_t_quantile():
    for df, want in ((1, 12.706), (2, 4.303), (5, 2.5706), (10, 2.2281), (31, 2.0395), (1000, 1.9623)):
        assert A.t975(df) == pytest.approx(want, abs=2e-3)


def test_paired_interval_matches_the_textbook():
    d = torch.tensor([1.0, 2.0, 3.0, 4.0, 6.0])
    m, hw = A.paired(d)
    assert float(m) == pytest.approx(3.2) and float(hw) == pytest.approx(2.7764 * d.std().item() / math.sqrt(5), rel=2e-3)
    s = A.stat(d - 3.2)
    assert s["mean"] == pytest.approx(0.0, abs=1e-6) and s["lo"] < 0 < s["hi"]
    # a constant difference has a zero-width interval; common random numbers make that the usual case for costs
    assert A.stat(torch.full((8,), -925.0)) == dict(mean=-925.0, lo=-925.0, hi=-925.0)


def test_ladder_rebuild():
    lad, idx = A.ladder_with([5, 7, 15, 16, 18], [14, 16, 7])              # day 15 -> 14
    assert len(lad) == 5 and lad == sorted(set(lad)) and {7, 14, 16} <= set(lad) and [lad[idx[n]] for n in (14, 16, 7)] == [14, 16, 7]
    lad, idx = A.ladder_with([5, 7, 15, 16, 18], [15, 17, 7])              # evening 16 -> 17
    assert lad[idx[17]] == 17 and lad[idx[15]] == 15 and lad[idx[7]] == 7 and len(lad) == 5
    lad, idx = A.ladder_with([1, 2, 3], [4, 5, 6])
    assert lad == [4, 5, 6]
    lad, idx = A.ladder_with([3, 3, 3], [2])                                # degenerate ladders are padded upward
    assert len(lad) == 3 and lad == sorted(set(lad)) and lad[idx[2]] == 2
    for bad in ([0, 3], [], [1, 2, 3, 4]):
        with pytest.raises(ValueError):
            A.ladder_with([2, 4, 6], bad)


def test_every_unit_changes_exactly_the_count_it_claims():
    """Each manipulation is checked against the counts the simulator will use (scn.P / scn.layout / head defaults)."""
    from sim import load_scenario
    units = A.build_units(H)
    base = units[0]["baseline_counts"]
    ids = {u["id"] for u in units}
    assert {"provider_day", "provider_evening", "provider_night", "nurse_day", "nurse_evening", "nurse_night", "triage_station", "bay_resus", "bay_main",
            "bay_fast", "bay_hall", "fast_track", "ward_bed", "ward_bed_block", "ct_scanner", "xray_room", "second_ct_hours"} <= ids
    n = 0
    for u in units:
        assert u["unit_cost_per_day"] > 0 and u["cost_basis"]
        for side, sg in (("minus", -1), ("plus", 1)):
            v = u[side]
            if v is None:
                continue
            got = A.counts_of(load_scenario("normal_week", dict(v["overrides"], hospital_id=H)))
            want = dict(base)
            for k, dv in v["expect"].items():
                want[k] += dv
                assert dv != 0 and (dv < 0) == (sg < 0)
            assert got == want, (u["id"], side)
            n += 1
    assert n >= 30
    u = next(x for x in units if x["id"] == "provider_day")
    assert u["minus"]["expect"] == {"providers_day": -1} and u["hours"] == list(range(7, 15)) and u["count"] == base["providers_day"]


@pytest.fixture(scope="module")
def tiny():
    seeds = [A.SEED0, A.SEED0 + 1, A.SEED0 + 2]
    units = [u for u in A.build_units(H) if u["id"] in ("provider_day", "bay_hall")]
    tasks = A.make_tasks(H, "fixed", ["normal_week"], seeds, 1, units)
    res = A.run_tasks(tasks, workers=0, log=lambda *_: None)
    return seeds, units, res


def test_paired_run_removes_exactly_one_providers_pay(tiny):
    seeds, units, res = tiny
    assert not any("error" in r for r in res.values()), [r.get("error") for r in res.values()]
    base, minus, plus = res[("normal_week", "base")], res[("normal_week", "provider_day__minus")], res[("normal_week", "provider_day__plus")]
    assert base["seeds"] == minus["seeds"] == seeds
    cost = units[0]["unit_cost_per_day"]
    # same seeds, same patients: arrivals are identical with and without the unit
    assert torch.equal(base["episode"][:, J["arrivals_per_day"]], minus["episode"][:, J["arrivals_per_day"]])
    dl = (minus["episode"] - base["episode"])[:, J["labor_cost_per_day"]]
    # one provider x 8 h x wage x benefits less, unless that provider had called out that day (then nothing was paid anyway)
    assert all(abs(float(x) + cost) < 1.0 or abs(float(x)) < 1.0 for x in dl) and float(dl.mean()) < 0
    dp = (plus["episode"] - base["episode"])[:, J["labor_cost_per_day"]]
    assert all(abs(float(x) - cost) < 1.0 or abs(float(x)) < 1.0 for x in dp)
    assert minus["counts"]["providers_day"] == base["counts"]["providers_day"] - 1
    # the hourly profile sums to the episode: margin by day equals the episode margin
    assert torch.allclose(base["prof_day"][:, :, A.PROFILE.index("margin")].sum(1), base["episode"][:, J["margin_per_day"]], rtol=1e-4)
    assert torch.allclose(base["prof_hod"][:, :, A.PROFILE.index("margin")].sum(1), base["episode"][:, J["margin_per_day"]], rtol=1e-4)
    assert 0 < base["util"]["providers"]["mean"] <= 1 and len(base["util"]["bay_main"]["by_hour"]) == 24


def test_a_wrong_manipulation_is_caught():
    u = next(x for x in A.build_units(H) if x["id"] == "ct_scanner")
    t = dict(hospital=H, scenario="normal_week", key="bad", seeds=[A.SEED0, A.SEED0 + 1], days=1, manager="fixed", overrides=u["minus"]["overrides"],
             expect={"ct_scanners": -2}, base_counts=u["baseline_counts"])
    with pytest.raises(AssertionError, match="ct_scanners"):
        A.run_variant(t)


def test_report_rescore_and_markdown(tiny, tmp_path):
    seeds, units, res = tiny
    rep = A.build_report(H, "fixed", ["normal_week"], seeds, 1, units, res)
    assert rep["simulated"] and rep["synthetic"] and not rep["failed"] and "SIMULATED" in rep["disclaimer"]
    json.dumps(rep, allow_nan=False)
    u = rep["units"][0]
    a = u["scenarios"]["normal_week"]["minus_one"]
    assert a["verified"] == {"providers_day": [units[0]["baseline_counts"]["providers_day"], units[0]["baseline_counts"]["providers_day"] - 1]}
    assert set(a["delta"]) == set(EPISODE_METRICS) and len(a["by_hour"]["margin"]["mean"]) == 24 and len(a["by_day"]["margin"]["mean"]) == 1
    assert len(a["terms_seeds"]) == len(seeds) and len(a["terms_seeds"][0]) == len(TERMS)
    # value of the unit = -(effect of removing it); gross = net + what it costs
    m = a["money"]
    assert m["net_value_per_day"]["mean"] == pytest.approx(-a["delta"]["margin_per_day"]["mean"], rel=1e-4)
    assert m["net_value_per_day"]["lo"] == pytest.approx(-a["delta"]["margin_per_day"]["hi"], rel=1e-4)
    assert m["gross_value_per_day"]["mean"] == pytest.approx(m["net_value_per_day"]["mean"] + m["unit_cost_per_day"], rel=1e-4, abs=1e-2)
    # stored per-seed term differences reproduce the stored reward for every preset, and re-score under new weights
    rs = A.rescore(rep, "balanced")[u["id"]]["normal_week"]["minus_one"]
    assert rs["mean"] == pytest.approx(a["reward"]["balanced"]["mean"], rel=1e-3, abs=1e-6)
    only_cost = A.rescore(rep, {"labor": 1.0})[u["id"]]["normal_week"]["minus_one"]
    assert only_cost["mean"] > 0                                           # one provider fewer is cheaper: the labour-only reward rises
    assert set(a["reward"]) == set(OBJECTIVES)
    # the hallway space has no "minus" side (none is open at baseline)
    hall = next(x for x in rep["units"] if x["id"] == "bay_hall")["scenarios"]["normal_week"]
    assert hall["minus_one"] is None and hall["plus_one"]["verified"] == {"hallway_open": [0, 1]}
    row = next(r for r in rep["ranking"]["normal_week"] if r["unit"] == "bay_hall")
    assert row["existing"] is None and row["next"]["verdict"] in ("worth adding", "not worth adding", "not shown either way")
    # the server's pure-python re-scoring agrees with the torch one
    from server import attribution as S
    w = {"wait": 1.0, "lwbs": 0.25}
    got = S.reward_stat(a["terms_seeds"], rep["reward"]["terms"], rep["reward"]["scales"], w)
    want = A.rescore(rep, w)[u["id"]]["normal_week"]["minus_one"]
    assert got["mean"] == pytest.approx(want["mean"], rel=1e-4, abs=1e-7) and got["lo"] == pytest.approx(want["lo"], rel=1e-3, abs=1e-6)
    A.write_markdown(rep, tmp_path / "ATTRIBUTION.md")
    md = (tmp_path / "ATTRIBUTION.md").read_text()
    assert "SIMULATED" in md and "One provider, day shift" in md and md.count("(simulated") >= 4 and "identifiability" in md.lower()


def test_verdicts_follow_the_intervals():
    """Synthetic paired data: slack needs tight intervals, a wide interval is never called slack."""
    n, K = 16, len(EPISODE_METRICS)
    g = torch.Generator().manual_seed(0)
    base_ep = torch.zeros(n, K, dtype=torch.float64)
    for k, v in dict(wait_mean_min=20.0, wait_p95_min=60.0, ed_los_median_min=200.0, lwbs_per_day=3.0, boarding_hours_per_day=50.0, margin_per_day=4e5,
                     hi_acuity_wait_hours_per_day=4.0, adverse_events_per_day=1.0, deaths_per_day=0.2, operating_cost_per_day=5e5).items():
        base_ep[:, J[k]] = v
    scales = {k: 1.0 for k in TERMS}

    def res(ep, terms):
        z = torch.zeros(n, 1, len(A.PROFILE), dtype=torch.float64)
        zt = torch.zeros(n, 1, len(TERMS), dtype=torch.float64)
        return dict(seeds=list(range(n)), episode=ep, terms=terms, prof_day=z, prof_hod=z.repeat(1, 24, 1), term_day=zt, term_hod=zt.repeat(1, 24, 1),
                    counts={"x": 1}, legs=[0.0])

    bm = {k: float(base_ep[:, j].mean()) for k, j in J.items()}
    t0 = torch.zeros(n, len(TERMS), dtype=torch.float64)
    base = res(base_ep, t0)
    # (1) cheaper, nothing else moves -> slack
    ep = base_ep.clone()
    ep[:, J["margin_per_day"]] += 900.0
    tm = t0.clone()
    tm[:, TERMS.index("cost")] -= 900.0 / 24
    assert A.analyse(res(ep, tm), base, scales, 900.0, -1, bm)["verdict"] == "slack"
    # (2) cheaper but the wait difference is noisy around zero with a wide interval -> not called slack
    ep2 = ep.clone()
    ep2[:, J["wait_mean_min"]] += torch.randn(n, generator=g, dtype=torch.float64) * 5.0
    assert A.analyse(res(ep2, tm), base, scales, 900.0, -1, bm)["verdict"] == "inconclusive"
    # (3) waits clearly longer and the reward clearly lower -> needed
    ep3 = base_ep.clone()
    ep3[:, J["wait_mean_min"]] += 5.0 + torch.randn(n, generator=g, dtype=torch.float64) * 0.5
    tm3 = t0.clone()
    tm3[:, TERMS.index("wait")] += 3.0 + torch.randn(n, generator=g, dtype=torch.float64) * 0.1
    a = A.analyse(res(ep3, tm3), base, scales, 900.0, -1, bm)
    assert a["verdict"] == "needed" and a["top_effects"][0]["metric"] == "wait_mean_min" and a["top_effects"][0]["direction"] == "worse"
    # (4) adding: reward interval above zero -> worth adding; straddling zero -> not shown either way
    tm4 = t0.clone()
    tm4[:, TERMS.index("wait")] -= 2.0 + torch.randn(n, generator=g, dtype=torch.float64) * 0.1
    assert A.analyse(res(base_ep, tm4), base, scales, 900.0, +1, bm)["verdict"] == "worth adding"
    tm5 = t0.clone()
    tm5[:, TERMS.index("wait")] += torch.randn(n, generator=g, dtype=torch.float64)
    assert A.analyse(res(base_ep, tm5), base, scales, 900.0, +1, bm)["verdict"] == "not shown either way"


def test_location_table_is_geometry_only():
    loc = A.location_table(H)
    assert loc["modelled"] is False and set(loc["by_class"]) >= {"resus", "main", "fast"}
    v = loc["by_class"]["main"]
    assert v["walk_seconds_vs_class_min"] < 0 < v["walk_seconds_vs_class_max"] and len(loc["rooms"]) >= v["n"]
