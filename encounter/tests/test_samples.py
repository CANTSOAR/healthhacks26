import csv

from fastapi.testclient import TestClient

from encounter import samples
from encounter.app import app
from encounter.clinicians import list_clinicians
from encounter.validate import validate_case

ROWS = [{"patient-uuid": "00000000-aaaa-bbbb-cccc-000000000001", "patient-name": "Testa Fixture", "age": "44", "background": "Bakery owner. Lives with two cats.",
         "gender": "female", "notes": "Smokes ten cigarettes per day; consumes 3-4 glasses of wine on most nights and uses cannabis weekly. Fixture has a BMI of 31 and dyslipidemia (Total Chol 250, LDL 170). She needs plain-language counseling about cholesterol.",
         "patient-img": "s3://bucket/x.png", "personality": "Dry, sceptical", "race/ethinicity": "Fictional", "summary": "Dyslipidemia, smoker"}]


def _write_pack(tmp_path):
    d = tmp_path / "private" / "shp" / "pack" / "Challenge 1"
    (d / "patient images").mkdir(parents=True)
    with open(d / "faculty-provided-sample-patient-details.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ROWS[0]))
        w.writeheader()
        w.writerows(ROWS)
    (d / "patient images" / "Testa Fixture, Patient.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")


def test_absent_private_dir_means_no_sample_cases(store):
    assert samples.load_sample_rows() == [] and samples.ensure_sample_cases(store) == []
    assert not [c for c in store.list() if c["case_id"].startswith("sample-")]
    assert list_clinicians()["source"] == "builtin"


def test_sample_patients_become_cases_at_run_time(tmp_path, store):
    _write_pack(tmp_path)
    res = samples.ensure_sample_cases(store)
    assert res == [{"case_id": "sample-testa-fixture", "version": 1, "ok": True, "warnings": res[0]["warnings"]}]
    assert samples.ensure_sample_cases(store)[0]["version"] == 1                        # idempotent
    c = store.get("sample-testa-fixture")
    assert validate_case(c)["ok"] and c["status"] == "published" and c["review"]["needs_faculty_review"]
    assert c["origin"] == {"kind": "from_sample_patient", "sample_patient_uuid": ROWS[0]["patient-uuid"]}
    assert c["profile"]["image"].endswith("Testa Fixture, Patient.png") and c["profile"]["personality"] == "Dry, sceptical"
    f = {x["fact_id"]: x for x in c["facts"]}
    assert f["f.social.smoking"]["disclosure"]["rule"] == "if_asked" and f["f.social.smoking"]["patient_answer"] == "I smoke ten cigarettes per day."
    assert f["f.concealed.alcohol"]["disclosure"] == {"rule": "after_rapport", "rapport_needed": 3} and f["f.concealed.alcohol"]["cover_answer"]
    assert "3-4 glasses of wine" in f["f.concealed.alcohol"]["patient_answer"] and f["f.concealed.drugs"]["disclosure"]["rapport_needed"] == 4
    assert f["f.vitals.bmi"]["value"] == 31 and f["f.lab.ldl"]["value"] == 170 and f["f.lab.ldl"]["disclosure"]["rule"] == "chart_initial"
    assert f["f.chief_complaint.visit_reason"]["patient_answer"] == "I'm here about my dyslipidemia."     # habits are not volunteered
    assert any(o["objective_id"].startswith("obj.uncover_alcohol") for o in c["objectives"])
    assert any(o["objective_id"].startswith("obj.counsel_") and "counseling" in o["criterion"] for o in c["objectives"])
    # it lives in the data dir only
    assert (store.cases_dir / "sample-testa-fixture.v1.json").is_file()


def test_sample_case_plays_through_the_api_with_photo(tmp_path):
    _write_pack(tmp_path)
    c = TestClient(app)
    assert "sample-testa-fixture" in [x["case_id"] for x in c.get("/api/cases", params={"status": "published"}).json()]
    img = c.get("/api/cases/sample-testa-fixture/image")
    assert img.headers["content-type"] == "image/png"
    eid = c.post("/api/encounters", json={"case_id": "sample-testa-fixture"}).json()["encounter_id"]
    say = lambda t: c.post(f"/api/encounters/{eid}/turn", json={"text": t}).json()
    assert say("What brings you in today?")["reply"] == "I'm here about my dyslipidemia."
    assert say("Do you drink alcohol?")["reply"] == "I drink socially, like anyone."
    r = say("I ask everyone these questions and it stays confidential.")                    # rapport 2 of 3: still guarded
    assert r["disclosed"] == []
    r = say("That sounds stressful. Take your time.")                                       # rapport 3: comes back to it unprompted
    assert "glasses of wine" in r["reply"] and [d["fact_id"] for d in r["disclosed"]] == ["f.concealed.alcohol"]
    assert "ldl" in str(c.get(f"/api/encounters/{eid}").json()["chart"]).lower()
