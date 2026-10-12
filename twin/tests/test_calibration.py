"""Offline checks of the calibration layer (no long simulation):

    .venv/bin/python -m pytest twin/tests/test_calibration.py -q

For every hospital that has `catalog/hospitals/<id>.calibration.yaml`: the file loads, only `assumed`
attributes are overridden, `baseline_actions` become the action heads' defaults, and every member of
`<id>.ensemble.json` builds a ScenarioConfig (member 0 = the point calibration).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim import HospitalSim, load_scenario  # noqa: E402
from twin import harness as H  # noqa: E402
from twin import targets as TG  # noqa: E402

HOSP = ROOT / "catalog" / "hospitals"
CALIBRATED = sorted(p.name[:-len(".calibration.yaml")] for p in HOSP.glob("*.calibration.yaml"))
ENSEMBLES = sorted(p.name[:-len(".ensemble.json")] for p in HOSP.glob("*.ensemble.json"))
CONTRACT_DEFAULTS = {h["name"]: int(h["default"]) for h in yaml.safe_load((ROOT / "contracts" / "actions.yaml").read_text())["heads"]}
P_KEYS = ["provider_levels", "rn_levels", "provider_initial_min", "provider_reeval_min", "nurse_care_min_per_hour", "patience", "los",
          "lab", "ward_pool_los_factor", "ward_initial_occupancy", "absence_rate", "boarding_los_penalty", "arrivals_per_day", "pool_size"]


def _node(scn, path):
    parts = path.split(".")
    return scn.attr("hospital", None, parts[1], required=False) if parts[0] == "hospital" else scn.attr(parts[0], parts[1], parts[2], required=False)


def test_rwjuh_is_calibrated():
    assert "rwjuh_nb" in CALIBRATED and "rwjuh_nb" in ENSEMBLES


@pytest.mark.parametrize("hid", CALIBRATED)
def test_calibration_file_loads_and_sets_baseline(hid):
    cal = yaml.safe_load((HOSP / f"{hid}.calibration.yaml").read_text())
    assert cal["hospital_id"] == hid and cal["catalog_overrides"] and cal["baseline_actions"]
    raw = load_scenario("normal_week", overrides={"hospital_id": hid, "no_calibration": True})
    scn = load_scenario("normal_week", overrides={"hospital_id": hid})
    assert scn.calibration and not raw.calibration
    # only assumed attributes are fitted, and the fitted value is what the scenario uses
    for path, node in cal["catalog_overrides"].items():
        assert (_node(raw, path) or {}).get("source", "assumed") == "assumed", f"{path} is not tagged assumed"
        assert _node(scn, path)["value"] == node["value"], path
    # baseline_actions ARE the defaults; without the calibration the contract defaults apply
    spec = {h["name"]: h for h in scn.heads}
    assert {h["name"]: int(h["default"]) for h in raw.heads} == CONTRACT_DEFAULTS
    for name, idx in cal["baseline_actions"].items():
        assert spec[name]["default"] == idx and 0 <= idx < len(spec[name]["options"])
    assert any(spec[n]["default"] != CONTRACT_DEFAULTS[n] for n in cal["baseline_actions"]) or scn.P["provider_levels"] != raw.P["provider_levels"]
    sim = HospitalSim(scn, batch_size=2, device="cpu", seed=5)
    acts = sim.default_actions()
    for name, idx in cal["baseline_actions"].items():
        assert acts[name].tolist() == [idx, idx]
    # the schedule the report prints is what the simulator staffs
    lv = scn.P["provider_levels"]
    assert [lv[cal["baseline_actions"][h]] for h in H.SHIFT_HEADS_MD] == list(cal["schedule"]["providers"].values())
    lv = scn.P["rn_levels"]
    assert [lv[cal["baseline_actions"][h]] for h in H.SHIFT_HEADS_RN] == list(cal["schedule"]["nurses"].values())
    assert lv == sorted(lv) and len(set(lv)) == 5
    for _ in range(2):
        m = sim.step(sim.default_actions())
    assert int(sim.invalid_actions.sum()) == 0 and float(m["staff_on_shift"].min()) > 0
    # an explicit override still wins over the file
    other = load_scenario("normal_week", overrides={"hospital_id": hid, "baseline_actions": {"md_day": 0}})
    assert {h["name"]: h["default"] for h in other.heads}["md_day"] == 0


@pytest.mark.parametrize("hid", CALIBRATED)
def test_targets_collect(hid):
    T = TG.collect_targets(hid)
    assert T and all(t.lo <= t.value <= t.hi for t in T.values())
    assert any(t.scope == "hospital" and t.accept for t in T.values())


@pytest.mark.parametrize("hid", ENSEMBLES)
def test_ensemble_members_build(hid):
    doc = json.loads((HOSP / f"{hid}.ensemble.json").read_text())
    assert doc["hospital_id"] == hid and doc["targets"] and doc["parameters"]
    mem = doc["members"]
    assert 8 <= len(mem) <= 40 and [m["id"] for m in mem] == list(range(len(mem)))
    cal = load_scenario("normal_week", overrides={"hospital_id": hid})
    raw = load_scenario("normal_week", overrides={"hospital_id": hid, "no_calibration": True})
    lit = {p["key"]: p for p in doc["parameters"] if p["tag"] == "literature"}
    for m in mem:
        ov = {**m["overrides"], "baseline_actions": m["baseline_actions"], "hospital_id": hid}
        scn = load_scenario("normal_week", overrides=ov)
        alone = load_scenario("normal_week", overrides={**ov, "no_calibration": True})
        for k in P_KEYS:                            # a member is a complete description: the calibration file does not leak into it
            assert scn.P[k] == alone.P[k], (m["id"], k)
        d = {h["name"]: h["default"] for h in scn.heads}
        assert {k: d[k] for k in m["baseline_actions"]} == m["baseline_actions"]
        assert [scn.P["provider_levels"][m["baseline_actions"][h]] for h in H.SHIFT_HEADS_MD] == m["theta"]["md"]
        assert [scn.P["rn_levels"][m["baseline_actions"][h]] for h in H.SHIFT_HEADS_RN] == m["theta"]["rn"]
        for path in m["overrides"]:                 # nothing measured is ever overridden
            assert (_node(raw, path) or {}).get("source", "assumed") in ("assumed", "literature"), path
        for key, p in lit.items():
            assert p["lo"] - 1e-9 <= m["theta"][key] <= p["hi"] + 1e-9, (m["id"], key)
        if m["id"] > 0:
            assert all(m["inside"].values()), m["id"]
        assert set(doc["targets"]) <= set(m["fit"])
    # member 0 is the point calibration
    m0 = load_scenario("normal_week", overrides={**mem[0]["overrides"], "baseline_actions": mem[0]["baseline_actions"], "hospital_id": hid})
    for k in P_KEYS:
        assert m0.P[k] == cal.P[k], k
    assert {h["name"]: h["default"] for h in m0.heads} == {h["name"]: h["default"] for h in cal.heads}
    sim = HospitalSim(load_scenario("normal_week", overrides={**mem[-1]["overrides"], "baseline_actions": mem[-1]["baseline_actions"],
                                                              "hospital_id": hid}), batch_size=1, device="cpu", seed=3)
    sim.step(sim.default_actions())
    assert int(sim.invalid_actions.sum()) == 0


def test_harness_matches_ordinary_loader():
    base = H.base_values("rwjuh_nb")
    th = dict(md=[9, 10, 5], rn=[16, 18, 11], triage=2, split=0, enc_scale=1.2, reeval_scale=1.5, lab_scale=1.3, nurse_care_scale=1.2,
              los_factor=0.93, patience_scale=1.3, absence_rate=0.03, boarding_los_penalty=0.02)
    r = H.equivalence_check("rwjuh_nb", th, seeds=(11, 12), days=1, base=base)
    assert r["identical"], r
