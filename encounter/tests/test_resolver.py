import json

import jsonschema
import pytest
from fastapi.testclient import TestClient

from encounter import api, templates as tpl
from encounter.app import app
from encounter.paths import CONTRACTS_DIR, REPO_ROOT
from encounter.resolver import ClinicianEncounterResolver, ResolverError

ISCHEMA = json.loads((CONTRACTS_DIR / "interaction.schema.json").read_text())


def _schema(name):
    return {"$schema": ISCHEMA["$schema"], "$defs": ISCHEMA["$defs"], "$ref": f"#/$defs/{name}"}


class FakeSim:
    """Minimal stand-in coded against contracts/sim_api.md."""

    def __init__(self, group="chest_pain", severity=0.8, seed=41, playable=True):
        self.t = 96
        self.playable = playable
        self.held, self.applied = [], []
        self.truth = {"patient_id": 123, "seed": seed, "condition_group": group, "condition_template": f"catalog/conditions/{group}.yaml",
                      "diagnosis": "Simulated diagnosis", "severity": severity, "acuity": 2, "age": 57, "sex": "male", "arrival_mode": "ambulance",
                      "payer": "medicare", "true_disposition": "admit", "needs": ["lab"],
                      "facts": tpl.sample_fact_values(group, severity, seed, 57, "male")}
        jsonschema.validate(self.truth, _schema("latent_truth"))

    def hold_for_play(self, b, patient_id):
        if self.playable:
            self.held.append((b, patient_id))
        return self.playable

    def latent_truth(self, b, patient_id):
        return self.truth

    def known_state(self, b, patient_id):
        ks = {"patient_id": patient_id, "known_fact_ids": ["f.vitals.heart_rate", "f.chief_complaint.chest_pain", "f.not.in.case"],
              "triage_note": "ESI 2; chest pain; arrived by ambulance; age 57", "orders": [], "results_ready": []}
        jsonschema.validate(ks, _schema("known_state"))
        return ks

    def apply_interaction_result(self, b, result):
        jsonschema.validate(result, _schema("result"))
        assert result["resolver"] == "played"
        self.applied.append((b, result))


SCRIPT = ["Hello, I'm Dr. Rao, the resident. What brings you in today?", "When did it start?", "What does the pain feel like?", "Does it spread anywhere?",
          "Any sweating or nausea?", "Do you smoke?", "What medications do you take?", "Any allergies?", "!order:ecg", "!order:troponin",
          "The plan is to keep you in for more tests. Any questions?"]


def test_resolver_hold_instantiate_play_writeback(store, manager):
    sim = FakeSim()
    r = ClinicianEncounterResolver(store, manager)
    started = r.start(sim, 0, 123, run_id="run-1")
    assert sim.held == [(0, 123)] and started["held"] is True
    assert started["sim"] == {"run_id": "run-1", "b": 0, "patient_id": 123, "held": True, "t_start": 96}
    assert started["case"]["case_id"] == "sim-chest_pain-p123-s41"
    assert started["patient"]["age"] == 57 and started["patient"]["gender"] == "male"
    chart = started["chart"]
    known = {f["fact_id"] for s in chart["sections"] for f in s["facts"]}
    assert "f.chief_complaint.chest_pain" in known and "f.vitals.heart_rate" in known and "f.not.in.case" not in known
    assert chart["sections"][0]["section_id"] == "triage" and [a["artifact_id"] for a in chart["artifacts"]] == ["art.triage_note"]
    assert "ESI 2; chest pain" in chart["artifacts"][0]["content"]
    eid = started["encounter_id"]
    for line in SCRIPT:
        manager.request(eid, line[1:]) if line.startswith("!") else manager.turn(eid, line)
    out = r.finish(eid, "admit", summary="Chest pressure with raised troponin and ECG changes: admit.")
    assert out["written_back"] is True and len(sim.applied) == 1
    b, res = sim.applied[0]
    assert b == 0 and res is not None and res["patient_id"] == 123 and res["session_ref"] == eid and res["t_start"] == 96
    assert res["decision"]["disposition"] == "admit" and res["decision"]["orders"] == ["ecg (bedside)", "troponin (lab)"]
    assert 0 < res["quality"] <= 1 and res["duration_min"] > 5
    truth_ids = {f["fact_id"] for f in sim.truth["facts"]}
    assert set(res["information_gained"]) <= truth_ids                     # everything learned is part of the patient's latent truth
    assert {"f.lab.troponin", "f.imaging.ecg", "f.medications.current"} <= set(res["information_gained"])
    assert [p["played_by"] for p in res["participants"]] == ["ai", "human"]
    assert r.finish(eid)["already_finished"] and len(sim.applied) == 1     # no double write-back


def test_same_patient_same_case(store, manager):
    r = ClinicianEncounterResolver(store, manager)
    a = r.start(FakeSim(), 0, 123)
    b = r.start(FakeSim(), 0, 123)
    assert a["case"]["case_id"] == b["case"]["case_id"] and a["case"]["version"] == b["case"]["version"] == 1
    assert a["patient"] == b["patient"] and a["chart"]["artifacts"] == b["chart"]["artifacts"]
    assert store.versions("sim-chest_pain-p123-s41") == [1]
    c = store.get("sim-chest_pain-p123-s41")
    assert c["status"] == "published" and c["origin"]["sim_patient_id"] == 123 and c["review"]["needs_faculty_review"]
    assert c["faculty_truth"]["diagnosis"] == "Simulated diagnosis" and c["faculty_truth"]["expected_disposition"] == "admit"
    sim_vals = {f["fact_id"]: f["value"] for f in FakeSim().truth["facts"]}
    assert all(sim_vals[f["fact_id"]] == f.get("value") for f in c["facts"])   # the interviewed patient is the simulated patient


def test_not_playable_patient_is_refused(store, manager):
    with pytest.raises(ResolverError):
        ClinicianEncounterResolver(store, manager).start(FakeSim(playable=False), 0, 123)


def test_writeback_failure_does_not_lose_feedback(store, manager):
    sim = FakeSim()
    sim.apply_interaction_result = lambda b, result: (_ for _ in ()).throw(ValueError("patient 123 is not in a clinician encounter"))
    r = ClinicianEncounterResolver(store, manager)
    eid = r.start(sim, 0, 123)["encounter_id"]
    manager.turn(eid, "What brings you in?")
    out = r.finish(eid, "admit")
    assert out["written_back"] is False and "not in a clinician encounter" in out["feedback"]["writeback_error"]
    assert out["interaction_result"]["quality"] >= 0


def test_scripted_resolve_and_unknown_template_falls_back(store, manager):
    sim = FakeSim()
    sim.truth = {**sim.truth, "condition_template": "generic (no condition template found)", "condition_group": "made_up_group", "facts": []}
    out = ClinicianEncounterResolver(store, manager).resolve(sim, 0, 123, ["What brings you in?", "!order:glucose"], "discharge")
    assert out["written_back"] and sim.applied[0][1]["decision"]["disposition"] == "discharge"
    assert store.get("sim-other_medical-p123-s41")["origin"]["condition_template"] == "other_medical"


def test_api_run_id_patient_id_path_uses_registered_sim():
    sim = FakeSim(group="abdominal_pain", severity=0.5)
    api.register_sim_lookup(lambda run_id: (sim, 0) if run_id == "live-1" else None)
    c = TestClient(app)
    assert c.post("/api/encounters", json={"run_id": "nope", "patient_id": 123}).status_code == 404
    r = c.post("/api/encounters", json={"run_id": "live-1", "patient_id": 123})
    assert r.status_code == 201 and r.json()["sim"]["run_id"] == "live-1" and sim.held == [(0, 123)]
    eid = r.json()["encounter_id"]
    c.post(f"/api/encounters/{eid}/turn", json={"text": "What brings you in today?"})
    fin = c.post(f"/api/encounters/{eid}/finish", json={"disposition": "admit", "orders": ["ct abdomen", "cbc"]}).json()
    assert fin["written_back"] is True and sim.applied[0][1]["decision"]["orders"] == ["ct abdomen (imaging)", "cbc (lab)"]
    sim.playable = False
    assert c.post("/api/encounters", json={"run_id": "live-1", "patient_id": 123}).status_code == 409


@pytest.mark.skipif(not (REPO_ROOT / "sim" / "M2_READY").exists(), reason="sim/M2_READY not present: the real simulator's interaction API is not ready")
def test_against_real_simulator(store, manager):
    from sim import HospitalSim, load_scenario
    sim = HospitalSim(load_scenario("normal_week"), batch_size=1, device="cpu", seed=3)
    sim.reset(seed=3)
    target = None
    for _ in range(12 * 30):                                      # up to 30 simulated hours, one tick at a time
        sim.tick()
        for pid in sim.snapshot(0)["patients"]["id"]:
            pi = sim.pending_interaction(0, int(pid))
            if pi and pi.get("status") == "in_progress":
                target = int(pid)
                break
        if target is not None:
            break
    assert target is not None, "no patient reached a clinician encounter"
    truth = sim.latent_truth(0, target)
    jsonschema.validate(truth, _schema("latent_truth"))
    jsonschema.validate(sim.known_state(0, target), _schema("known_state"))
    r = ClinicianEncounterResolver(store, manager)
    started = r.start(sim, 0, target, run_id="real")
    case = store.get(started["case"]["case_id"])
    assert case["origin"]["sim_patient_id"] == target and case["origin"]["condition_template"] == truth["condition_group"]
    eid = started["encounter_id"]
    for line in ["Hello, I'm the resident. What brings you in today?", "Do you take any medications?", "Any allergies?"]:
        manager.turn(eid, line)
    out = r.finish(eid, truth["true_disposition"], summary="Scripted test encounter.")
    assert out["written_back"] is True, out["feedback"].get("writeback_error")
    log = sim.interaction_log(0, target)
    assert any(x.get("resolver") == "played" and x.get("session_ref") == eid for x in log)
