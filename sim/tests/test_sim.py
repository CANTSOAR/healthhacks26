"""Simulator verification. Run: .venv/bin/python -m pytest sim/tests -q

Every test is parametrised over the device; CUDA cases are skipped when CUDA is unavailable.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator  # noqa: E402
from referencing import Registry, Resource  # noqa: E402

from sim import HospitalSim, list_scenarios, load_scenario  # noqa: E402

C = ROOT / "contracts"
DEVICES = ["cpu", pytest.param("cuda", marks=pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available"))]


def validator(name, ref=None):
    store = {}
    for f in C.glob("*.schema.json"):
        s = json.loads(f.read_text())
        store[s["$id"]] = Resource.from_contents(s)
    reg = Registry().with_resources(store.items())
    schema = json.loads((C / name).read_text())
    if ref:
        schema = {"$schema": schema["$schema"], "$ref": f"#/$defs/{ref}", "$defs": schema["$defs"]}
    return Draft202012Validator(schema, registry=reg)


def random_actions(sim, gen, cadences=("hourly", "daily", "weekly", "monthly")):
    return {h["name"]: torch.randint(0, len(h["options"]), (sim.B,), generator=gen).to(sim.device)
            for h in sim.action_spec() if h["cadence"] in cadences}


# ------------------------------------------------------------------------------------------
# 1. M/M/c
# ------------------------------------------------------------------------------------------
def erlang_c_wq(lam, mu, c):
    a = lam / mu
    rho = a / c
    s = sum(a ** k / math.factorial(k) for k in range(c))
    last = a ** c / math.factorial(c) / (1 - rho)
    return (last / (s + last)) / (c * mu - lam)


@pytest.mark.parametrize("device", DEVICES)
def test_mmc_matches_erlang_c(device):
    """Stripped to Poisson arrivals, c servers, exponential service, FCFS, no abandonment.

    Discretisation, stated honestly: the simulator advances in 5-minute ticks. Arrivals appear and
    services start and end on tick boundaries, so an Exp(mean m) service occupies its server for
    ceil(S/5) ticks, which is a geometric number of ticks with mean 5/(1-exp(-5/m)) minutes
    (42.55 for m = 40), still memoryless. The right analytic comparator is therefore Erlang-C with
    that effective service mean. Against the un-discretised m = 40 the analytic wait is ~40 percent
    lower (7.1 vs 11.9 min here); the test asserts the simulator is NOT compatible with that number,
    so the tolerance is tight enough to tell the two apart.
    Tolerance: |sim - analytic| <= 4 standard errors (across independent hospitals) + 4 percent.
    """
    lam_day, m, c, tick = 216.0, 40.0, 8, 5.0
    scn = load_scenario("mmc_validation", overrides={"patient.shared.arrivals_per_day": lam_day})
    assert scn.P["fixed_servers"] == c and scn.P["provider_initial_min"]["mean"][2] == m
    B = 32 if device == "cpu" else 256
    sim = HospitalSim(scn, batch_size=B, device=device, seed=11)
    for _ in range(24 * 2):       # warm-up
        sim.step()
    fs = torch.zeros(B, device=device)
    ws = torch.zeros(B, device=device)
    for _ in range(24 * 10):
        mt = sim.step()
        fs += mt["first_seen"]
        ws += mt["door_to_provider_sum_min"]
    w = ws / fs
    mean, se = float(w.mean()), float(w.std() / B ** 0.5)
    lam = lam_day / 1440.0
    m_eff = tick / (1.0 - math.exp(-tick / m))
    wq_eff = erlang_c_wq(lam, 1.0 / m_eff, c)
    wq_nominal = erlang_c_wq(lam, 1.0 / m, c)
    print(f"\nM/M/{c} [{device}] sim mean wait {mean:.2f} min (SE {se:.2f}, B={B}); Erlang-C with tick-rounded "
          f"service {wq_eff:.2f}; Erlang-C continuous {wq_nominal:.2f}")
    assert abs(mean - wq_eff) <= 4 * se + 0.04 * wq_eff
    assert abs(mean - wq_nominal) > 4 * se
    assert int(sim.conservation()["residual"].abs().max()) == 0
    assert float(sim.exits[:, 3].sum()) == 0      # no LWBS


# ------------------------------------------------------------------------------------------
# 2. determinism
# ------------------------------------------------------------------------------------------
def _trajectory(device, seed, hours=20, B=2, actions_seed=None):
    sim = HospitalSim(load_scenario("normal_week"), batch_size=B, device=device, seed=seed)
    gen = torch.Generator().manual_seed(actions_seed) if actions_seed is not None else None
    out = []
    for _ in range(hours):
        m = sim.step(random_actions(sim, gen, ("hourly", "daily")) if gen is not None else sim.default_actions())
        out.append(torch.stack([m[k] for k in m], 1).cpu())
    return torch.stack(out), sim


@pytest.mark.parametrize("device", DEVICES)
def test_same_seed_same_trajectory(device):
    a, sa = _trajectory(device, 5, actions_seed=1)
    b, sb = _trajectory(device, 5, actions_seed=1)
    assert torch.equal(a, b)
    for k in ("state", "timer", "bay", "acu"):
        assert torch.equal(sa.p[k], sb.p[k])
    c, _ = _trajectory(device, 6, actions_seed=1)
    assert not torch.equal(a, c)
    # reset() reproduces the run; hospital b under int seed s is hospital 0 under seed s + b
    sa.reset(5)
    again = torch.stack([torch.stack([m[k] for k in sa.metric_names()], 1).cpu()
                         for m in (sa.step(sa.default_actions()) for _ in range(6))])
    ref, _ = _trajectory(device, 5, hours=6)
    assert torch.equal(again, ref)
    one, _ = _trajectory(device, torch.tensor([6]), hours=6, B=1)
    assert torch.equal(one[:, 0], ref[:, 1])


# ------------------------------------------------------------------------------------------
# 3. common random numbers
# ------------------------------------------------------------------------------------------
def _arrival_record(sim, actions_fn, hours):
    counts, seen = [], {}
    for _ in range(hours):
        acts = actions_fn()
        for i in range(sim.ticks_per_step):
            sim.tick(acts if i == 0 else None)
            counts.append(sim.next_ord.clone().cpu())
            act = sim.p["active"][0].cpu()
            ints = sim.ps[0].cpu()[act]
            flts = sim.pd[0].cpu()[act]
            for r, f in zip(ints.tolist(), flts.tolist()):
                seen.setdefault(r[0], (tuple(r[:8]), tuple(f)))     # all static ints except `needs` (a decision may rewrite it)
    return torch.stack(counts), seen


@pytest.mark.parametrize("device", DEVICES)
def test_common_random_numbers(device):
    scn = load_scenario("normal_week")
    a = HospitalSim(scn, batch_size=2, device=device, seed=21)
    b = HospitalSim(scn, batch_size=2, device=device, seed=21)
    gen = torch.Generator().manual_seed(3)
    ca, pa = _arrival_record(a, a.default_actions, 36)
    cb, pb = _arrival_record(b, lambda: random_actions(b, gen), 36)
    assert torch.equal(ca, cb), "arrival counts per tick must not depend on actions"
    common = set(pa) & set(pb)
    assert len(common) > 200
    for k in common:
        assert pa[k] == pb[k], f"patient {k} differs between managers"
    # the two runs really were managed differently
    assert not torch.equal(a.exits, b.exits) or not torch.equal(a.p["state"], b.p["state"])
    assert int(b.exits[:, 6].sum()) > 0      # random policy diverted someone; they never entered
    assert int(a.conservation()["residual"].abs().max()) == 0 and int(b.conservation()["residual"].abs().max()) == 0


# ------------------------------------------------------------------------------------------
# 4. conservation
# ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("device", DEVICES)
def test_conservation_random_actions(device):
    """generated == in system + sum(exits) every hour under random actions on every head,
    including structural ones (short build delays so they complete inside the run)."""
    scn = load_scenario("flu_surge", overrides={"space.shared.build_delay_days": 2, "space.shared.ward_bed_open_delay_days": 1,
                                                "equipment.shared.install_delay_days": 1, "space.shared.relocate_delay_days": 2,
                                                "staff.shared.hire_delay_days": 1, "days_per_month": 2})
    sim = HospitalSim(scn, batch_size=4, device=device, seed=2)
    gen = torch.Generator().manual_seed(0)
    v0 = sim.layout_version.clone()
    for h in range(24 * 7):
        sim.step(random_actions(sim, gen))
        c = sim.conservation()
        assert int(c["residual"].abs().max()) == 0, f"conservation broken at hour {h}"
        assert int((sim.p["active"] & (sim.p["state"] != 11)).sum(1).max()) <= sim.P
    ex = sim.exits.sum(0).tolist()
    assert ex[1] > 0 and ex[2] > 0 and ex[3] > 0 and ex[6] > 0
    assert bool((sim.layout_version > v0).all())
    # bays never double-booked: every occupied bay index is held by exactly one patient
    for b in range(sim.B):
        bays = sim.p["bay"][b][sim.p["active"][b] & (sim.p["bay"][b] < sim.NB)].tolist()
        assert len(bays) == len(set(bays))
        assert int(sim.bay_busy[b, :sim.NB].sum()) == len(bays)


@pytest.mark.parametrize("device", DEVICES)
def test_pool_overflow_is_counted(device):
    scn = load_scenario("normal_week", overrides={"pool_size": 176, "arrival_scale": 3.0, "hospital.ward_initial_occupancy": 0.5})
    sim = HospitalSim(scn, batch_size=2, device=device, seed=0)
    for _ in range(40):
        sim.step()
        assert int(sim.conservation()["residual"].abs().max()) == 0
    assert int(sim.pool_overflow.min()) > 0
    assert torch.equal(sim.exits[:, 6], sim.pool_overflow)      # turned away, counted as diverted


# ------------------------------------------------------------------------------------------
# 5. invalid / masked actions
# ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("device", DEVICES)
def test_invalid_and_masked_actions_rejected(device):
    sim = HospitalSim(load_scenario("normal_week"), batch_size=3, device=device, seed=0)
    L = lambda *v: torch.tensor(v, device=device)   # noqa: E731
    mask = sim.action_mask()
    assert all(bool(m.all()) for m in mask.values())            # t = 0 is every boundary
    sim.step({"md_day": L(4, 99, -1), "priority_rule": L(0, 7, 2)})
    assert sim.invalid_actions.tolist() == [0, 2, 1]
    assert sim.settings["md_day"].tolist() == [4, 2, 2] and sim.settings["priority_rule"].tolist() == [0, 1, 2]
    mask = sim.action_mask()
    assert bool(mask["priority_rule"].all()) and not bool(mask["md_day"].any()) and not bool(mask["bays_delta"].any())
    before = sim.invalid_actions.clone()
    sim.step({"md_day": L(0, 2, 2), "bays_delta": L(1, 2, 1), "divert": L(1, 0, 0)})   # daily + monthly heads are masked now
    assert (sim.invalid_actions - before).tolist() == [1, 1, 0]
    assert sim.settings["md_day"].tolist() == [4, 2, 2] and sim.settings["divert"].tolist() == [1, 0, 0]
    assert int(sim.pend_bays_n.sum()) == 0
    # rule-based rejection: call-ins beyond the per-shift cap
    before = sim.invalid_actions.clone()
    for _ in range(5):
        sim.step({"call_in": L(2, 0, 0)})
    assert int((sim.invalid_actions - before)[0]) >= 1 and int(sim.called_rn[0]) <= sim.cfg["callin_max"]["rn"]
    with pytest.raises(KeyError):
        sim.step({"no_such_head": L(0, 0, 0)})


# ------------------------------------------------------------------------------------------
# 6. contracts
# ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("device", DEVICES)
def test_snapshot_layout_metrics_conform(device):
    snap_v, lay_v = validator("snapshot.schema.json"), validator("layout.schema.json")
    metric_keys = list(yaml.safe_load((C / "metrics.yaml").read_text())["metrics"].keys())
    heads = yaml.safe_load((C / "actions.yaml").read_text())["heads"]
    ids = [s["id"] for s in list_scenarios()]
    for want in ["normal_week", "flu_surge", "nursing_absences", "imaging_outage", "discharge_delays", "mmc_validation"]:
        assert want in ids
    for sid in ids:
        sim = HospitalSim(load_scenario(sid), batch_size=2, device=device, seed=1)
        assert sim.metric_names() == metric_keys
        spec = sim.action_spec()
        assert [h["name"] for h in spec] == [h["name"] for h in heads]
        for h, ref in zip(spec, heads):
            assert h["options"] == ref["options"] and h["default"] == ref["default"] and len(h["values"]) == len(h["options"])
        lay = sim.layout(0)
        lay_v.validate(lay)
        for hour in range(34 if sid == "imaging_outage" else 14):
            m = sim.step(sim.default_actions())
            assert list(m.keys())[:len(metric_keys)] == metric_keys and "waiting_patient_minutes" in m
            for k, v in m.items():
                assert v.shape == (2,) and bool(torch.isfinite(v).all()), k
        for _ in range(3):
            sim.tick()
            snap = sim.snapshot(1)
            snap_v.validate(snap)
            json.dumps(snap)
            n = len(snap["patients"]["id"])
            assert all(len(v) == n for v in snap["patients"].values())
            assert len(snap["rooms"]["status"]) == len(lay["rooms"]) and len(snap["equipment"]["status"]) == len(lay["equipment"])
            assert all(-1 <= r < len(lay["rooms"]) for r in snap["patients"]["room"])
            assert set(snap["kpis"]["settings"]) == {h["name"] for h in heads}
        obs = sim.observe()
        assert obs.shape == (2, sim.obs_dim) and len(sim.obs_names()) == sim.obs_dim and sim.obs_dim < 96
        assert bool(torch.isfinite(obs).all())
        summ = sim.episode_summary()
        assert list(summ.keys()) == list(yaml.safe_load((C / "metrics.yaml").read_text())["episode_summary"].keys())
    out = HospitalSim(load_scenario("imaging_outage"), batch_size=1, device=device, seed=0)
    for _ in range(33):
        out.step()
    assert int(out.eq_avail[0, 1]) < out.eq_units0[1]          # a CT is down on day 1 after 08:00


@pytest.mark.parametrize("device", DEVICES)
def test_structural_changes_reflected_in_layout(device):
    scn = load_scenario("normal_week", overrides={"space.shared.build_delay_days": 1, "space.shared.ward_bed_open_delay_days": 1,
                                                  "equipment.shared.install_delay_days": 1})
    sim = HospitalSim(scn, batch_size=2, device=device, seed=0)
    lay_v = validator("layout.schema.json")
    lay0 = sim.layout(0)
    L = lambda *v: torch.tensor(v, device=device)   # noqa: E731
    n_phys = lambda lay: sum(1 for r in lay["rooms"] if r["type"] == "treatment_bay" and r.get("physical", True))   # noqa: E731
    ward = lambda lay: sum(r["capacity"] for r in lay["rooms"] if r["type"] in ("ward_unit", "icu_bed", "stepdown_bed"))   # noqa: E731
    m = sim.step({"bays_delta": L(2, 1), "ward_beds_delta": L(2, 1), "equipment_buy": L(1, 0)})
    assert float(m["cost_structural"][0]) > 0 and float(m["cost_structural"][1]) == 0
    for _ in range(26):
        sim.step()
    lay1, lay_other = sim.layout(0), sim.layout(1)
    lay_v.validate(lay1)
    assert lay1["version"] > lay0["version"] and lay_other["version"] == lay0["version"]
    assert n_phys(lay1) == n_phys(lay0) + sim.cfg["bay_step"] and ward(lay1) == ward(lay0) + sim.cfg["ward_step"]
    assert len(lay1["equipment"]) == len(lay0["equipment"]) + 1 and len(lay1["rooms"]) == len(lay0["rooms"])
    snap = sim.snapshot(0)
    validator("snapshot.schema.json").validate(snap)
    assert snap["layout_version"] == lay1["version"] and len(snap["equipment"]["status"]) == len(lay1["equipment"])
    assert int(sim.ward_cap[0]) == int(sim.ward_cap[1]) + sim.cfg["ward_step"]


# ------------------------------------------------------------------------------------------
# 7. interaction contract and played write-back
# ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("device", DEVICES)
def test_played_write_back(device):
    E = yaml.safe_load((C / "enums.yaml").read_text())
    WP, PROV = E["patient_state"].index("waiting_provider"), E["patient_state"].index("with_provider")
    sim = HospitalSim(load_scenario("normal_week"), batch_size=2, device=device, seed=4)
    truth_v, known_v, res_v = (validator("interaction.schema.json", r) for r in ("latent_truth", "known_state", "result"))
    for _ in range(11):
        sim.step()
    pid = None
    for _ in range(60):
        sim.tick()
        snap = sim.snapshot(0)
        cand = [p for p, s in zip(snap["patients"]["id"], snap["patients"]["state"]) if s == WP]
        if cand:
            pid = cand[0]
            break
    assert pid is not None
    for q in snap["patients"]["id"][:40]:
        truth_v.validate(sim.latent_truth(0, q))
        known_v.validate(sim.known_state(0, q))
        json.dumps(sim.patient_detail(0, q))
    for r in sim.interaction_log(0):
        res_v.validate(r)
    truth = sim.latent_truth(0, pid)
    assert truth == sim.latent_truth(0, pid)
    pend = sim.pending_interaction(0, pid)
    assert pend["interaction_type"] == "clinician_encounter" and pend["status"] == "waiting"
    assert sim.hold_for_play(0, pid) is True
    for _ in range(400):
        sim.tick()
        if sim.patient_detail(0, pid)["state"] == "with_provider":
            break
    d = sim.patient_detail(0, pid)
    assert d["state"] == "with_provider" and d["held_for_play"]
    t_seen = d["first_seen_t"]
    for _ in range(40):                      # far beyond any sampled encounter: the hold keeps patient and provider
        sim.tick()
    assert sim.patient_detail(0, pid)["state"] == "with_provider"
    assert sim.pending_interaction(0, pid)["status"] == "in_progress"
    busy = [s for s, p in zip(sim.snapshot(0)["staff"]["id"], sim.snapshot(0)["staff"]["patient"]) if p == pid]
    assert busy, "a provider stays with the held patient"
    elapsed = (sim._tick - 1 - t_seen) * sim.tick_minutes
    played_dur = elapsed + 30.0              # the played session lasted 30 more simulated minutes
    played_disp = "discharge" if truth["true_disposition"] == "admit" else "admit"
    res = dict(interaction_type="clinician_encounter", patient_id=pid, resolver="played", duration_min=played_dur,
               information_gained=[truth["facts"][0]["fact_id"]],
               decision=dict(kind="disposition", orders=["CT abdomen", "basic labs"], disposition=played_disp), quality=0.33,
               session_ref="test-session", participants=[dict(entity_id=pid, role="patient", played_by="ai"),
                                                         dict(entity_id=busy[0], role="attending", played_by="human")])
    res_v.validate(res)
    sim.apply_interaction_result(0, res)
    left_after = None
    for i in range(1, 30):
        sim.tick()
        if sim.patient_detail(0, pid)["state"] != "with_provider":
            left_after = i
            break
    assert left_after == 6, "the encounter ends exactly when the played duration has elapsed"
    d = sim.patient_detail(0, pid)
    assert d["state"] in ("waiting_test", "walking", "in_test") and d["orders"] == ["ct", "lab"]            # played orders drive the pathway
    assert "played" in d["flag_names"] and abs(d["encounter_quality"] - 0.33) < 1e-6
    assert d["disposition"] == played_disp
    log = [r for r in sim.interaction_log(0, pid) if r["interaction_type"] == "clinician_encounter"]
    assert len(log) == 1 and log[0]["resolver"] == "played" and log[0]["duration_min"] == played_dur
    assert sim.known_state(0, pid)["known_fact_ids"].count(truth["facts"][0]["fact_id"]) == 1
    final = None
    for _ in range(12 * 60):                 # follow the patient to the played disposition
        sim.tick()
        try:
            d = sim.patient_detail(0, pid)
        except KeyError:
            break
        final = d
        if d["state"] in ("boarding", "in_ward", "exited"):
            break
    assert final is not None
    if played_disp == "admit":
        assert final["state"] in ("boarding", "in_ward") or final["exit"] in ("transferred", "died")
    else:
        assert final["exit"] in ("discharged_ed", "died")
    with pytest.raises(ValueError):
        sim.apply_interaction_result(0, res)       # no longer in the encounter
    assert sim.hold_for_play(0, 10 ** 9) is False
    assert int(sim.conservation()["residual"].abs().max()) == 0


# ------------------------------------------------------------------------------------------
# 8. the model responds to management in the expected direction
# ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("device", DEVICES)
def test_staffing_changes_waits(device):
    scn = load_scenario("normal_week")
    seeds = torch.tensor([7, 7, 7])
    sim = HospitalSim(scn, batch_size=3, device=device, seed=seeds)
    acts = sim.default_actions()
    for k in ("md_day", "md_evening", "md_night"):
        acts[k] = torch.tensor([0, 2, 4], device=device)
    for _ in range(24 * 3):
        sim.step(acts)
    s = sim.episode_summary()
    w = s["wait_mean_min"].tolist()
    assert w[0] > w[1] > w[2], w
    assert float(sim.ep["cost_labor"][0]) < float(sim.ep["cost_labor"][1]) < float(sim.ep["cost_labor"][2])
    assert torch.equal(sim.next_ord[0], sim.next_ord[1]) and torch.equal(sim.next_ord[1], sim.next_ord[2])


# ------------------------------------------------------------------------------------------
# 9. additive API used by the server (server/SIM_REQUESTS.md)
# ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("device", DEVICES)
def test_server_additions(device):
    scn = load_scenario("normal_week")
    sim = HospitalSim(scn, batch_size=1, device=device, seed=9)
    for _ in range(10):
        sim.step()
    ev = sim.inject_event(0, "ct_outage")
    assert ev["type"] == "equipment_outage" and scn.events == []          # the caller's config is not mutated
    sim.step()
    sim.step()
    assert int(sim.eq_avail[0, 1]) == sim.eq_units0[1] - 1
    with pytest.raises(KeyError):
        sim.inject_event(0, "no_such_event")
    s1 = sim.snapshot(0, consume=False)
    s2 = sim.snapshot(0)
    assert s1["events"] == s2["events"] and len(s1["events"]) > 0 and sim.snapshot(0)["events"] == []
    # a played result that arrives before the encounter starts is stored and used when it begins
    pid = None
    for _ in range(100):
        sim.tick()
        snap = sim.snapshot(0)
        cand = [p for p, s in zip(snap["patients"]["id"], snap["patients"]["state"]) if s in (2, 3)]
        if cand:
            pid = cand[-1]
            break
    assert pid is not None
    pub = sim.patient_detail(0, pid, public=True)
    assert "true_acuity" not in pub and "severity" not in pub and "true_acuity" in sim.patient_detail(0, pid)
    res = dict(interaction_type="clinician_encounter", patient_id=pid, resolver="played", duration_min=50.0,
               information_gained=[], decision=dict(kind="disposition", disposition="discharge", orders=[]), quality=0.95)
    sim.apply_interaction_result(0, res, defer=True)
    started = None
    for _ in range(600):
        sim.tick()
        try:
            d = sim.patient_detail(0, pid)
        except KeyError:
            break
        if started is None and d["first_seen_t"] is not None:
            started = d["first_seen_t"]
            assert "played" in d["flag_names"] and not d["held_for_play"]
        if started is not None and d["state"] != "with_provider":
            assert (sim._tick - 1 - started) * 5 == 50                      # occupied the provider for the played 50 minutes
            assert d["orders"] == [] and d["disposition"] == "discharge"
            break
    assert started is not None or pid not in sim._deferred[0]
