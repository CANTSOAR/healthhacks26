import json

import jsonschema
import pytest
from fastapi.testclient import TestClient

from encounter import api
from encounter.app import app
from encounter.paths import CONTRACTS_DIR

from .conftest import SEED_IDS, seed_case
from .scripts import SCRIPTS

ISCHEMA = json.loads((CONTRACTS_DIR / "interaction.schema.json").read_text())
RESULT_SCHEMA = {"$schema": ISCHEMA["$schema"], "$defs": ISCHEMA["$defs"], "$ref": "#/$defs/result"}
CASE_SCHEMA = json.loads((CONTRACTS_DIR / "case.schema.json").read_text())


@pytest.fixture
def client():
    return TestClient(app)


def hidden_strings(case: dict, disclosed: set[str], finished: bool = False) -> list[str]:
    """Everything a student response must not contain at this point of the encounter."""
    out = []
    for f in case["facts"]:
        if f["fact_id"] in disclosed:
            continue
        out.append(f["fact_id"])
        for k in ("statement", "patient_answer"):
            if isinstance(f.get(k), str) and len(f[k]) > 12:
                out.append(f[k])
    if not finished:
        ft = case.get("faculty_truth") or {}
        out += [x for x in [ft.get("diagnosis")] + list(ft.get("differential") or []) + list(ft.get("teaching_points") or []) if isinstance(x, str) and len(x) > 12]
        for o in case.get("objectives") or []:
            out += [o["objective_id"]] + [o[k] for k in ("criterion", "feedback_met", "feedback_missed", "evidence_rule") if isinstance(o.get(k), str) and len(o[k]) > 12]
        for a in (case.get("chart") or {}).get("artifacts") or []:
            if isinstance(a.get("interpretation"), str):
                out.append(a["interpretation"])
    return out


def assert_no_leak(payload, case, disclosed, where, finished=False):
    text = json.dumps(payload, ensure_ascii=False)
    assert "faculty_truth" not in text and "cover_answer" not in text and "expected_disposition" not in text or finished, where
    for s in hidden_strings(case, disclosed, finished):
        assert json.dumps(s, ensure_ascii=False)[1:-1] not in text, f"LEAK at {where}: {s!r}"


@pytest.mark.parametrize("cid", SEED_IDS)
def test_end_to_end_scripted_offline_encounter_with_leak_scan(client, cid):
    case, sc = seed_case(cid), SCRIPTS[cid]
    r = client.post("/api/encounters", json={"case_id": cid})
    assert r.status_code == 201
    start = r.json()
    eid = start["encounter_id"]
    assert set(start) >= {"encounter_id", "case", "chart", "patient", "llm"} and start["llm"] == {"provider": "offline", "live": False, "model": None}
    assert start["patient"]["name"] == case["profile"]["name"] and start["case"]["version"] == 1
    disclosed = {f["fact_id"] for s in start["chart"]["sections"] for f in s["facts"]}
    assert disclosed == {f["fact_id"] for f in case["facts"] if f["disclosure"]["rule"] == "chart_initial"}
    assert [a["artifact_id"] for a in start["chart"]["artifacts"]] == ["art.triage_note"]         # triage note visible at once
    assert_no_leak(start, case, disclosed, "start")
    for i, line in enumerate(sc["lines"], start=1):
        if line.startswith("!"):
            resp = client.post(f"/api/encounters/{eid}/request", json={"request": line[1:], "request_id": f"r{i}"})
        else:
            resp = client.post(f"/api/encounters/{eid}/turn", json={"text": line, "request_id": f"r{i}"})
        assert resp.status_code == 200, resp.text
        t = resp.json()
        assert set(t) >= {"reply", "disclosed", "chart", "ledger_tail", "rapport", "provider"} and t["provider"] == "offline" and t["fallback"] is False
        for d in t["disclosed"]:
            assert set(d) >= {"fact_id", "chart_section", "text"}
            disclosed.add(d["fact_id"])
        assert {f["fact_id"] for s in t["chart"]["sections"] for f in s["facts"]} == disclosed          # chart == ledger, nothing more
        for fid, turn in sc["hidden_until"].items():
            assert (fid in disclosed) == (i >= turn), (fid, i)                                          # never released early
        assert_no_leak(t, case, disclosed, f"turn {i}: {line}")
    state = client.get(f"/api/encounters/{eid}").json()
    assert_no_leak(state, case, disclosed, "state")
    assert len([x for x in state["transcript"] if x["speaker"] == "student"]) == len(sc["lines"])
    assert set(sc["expect"]) <= disclosed, sorted(set(sc["expect"]) - disclosed)
    fin = client.post(f"/api/encounters/{eid}/finish", json=sc["finish"]).json()
    assert set(fin) >= {"feedback", "interaction_result", "written_back"} and fin["written_back"] is False
    jsonschema.validate(fin["interaction_result"], RESULT_SCHEMA)
    fb = fin["feedback"]
    assert set(fb) >= {"objectives", "rubric", "elicited", "missed", "strengths", "next_time", "grader"} and fb["grader"] == "offline"
    assert {o["result"] for o in fb["objectives"]} <= {"met", "partly_demonstrated", "not_observed", "not_assessable"}
    assert sum(o["result"] == "met" for o in fb["objectives"]) >= len(fb["objectives"]) - 2
    assert client.post(f"/api/encounters/{eid}/turn", json={"text": "hello"}).status_code == 409
    log = client.get("/api/encounters", params={"case_id": cid}).json()
    assert [x["encounter_id"] for x in log] == [eid] and log[0]["status"] == "finished" and log[0]["quality"] == fin["interaction_result"]["quality"]
    assert (api.manager().dir / f"{eid}.json").is_file()                                              # session logged to disk


def test_faculty_view_has_everything_student_view_does_not(client):
    full = client.get("/api/cases/chest-pain-line-cook").json()
    jsonschema.validate({k: v for k, v in full.items() if k not in ("versions", "seed", "updated")}, CASE_SCHEMA)
    assert full["faculty_truth"]["diagnosis"] and full["versions"] == [1]
    student = client.get("/api/cases/chest-pain-line-cook", params={"view": "student"}).json()
    assert "faculty_truth" not in json.dumps(student) and "facts" not in student["case"] and "objectives" not in student["case"]
    eid = client.post("/api/encounters", json={"case_id": "chest-pain-line-cook"}).json()["encounter_id"]
    assert "ledger_full" not in client.get(f"/api/encounters/{eid}").json()
    assert "ledger_full" in client.get(f"/api/encounters/{eid}", params={"view": "faculty"}).json()


def test_key_demonstration_new_faculty_case_works_immediately(client):
    """A faculty member authors a brand-new patient through the API and interviews her at once: zero code edits."""
    body = {
        "title": "Dizzy spells in a 58-year-old teacher",
        "prebrief": "Take a history from Ms. Varga.",
        "profile": {"name": "Ilona Varga", "age": 58, "gender": "female", "personality": "Chatty", "speech_style": "Warm"},
        "faculty_truth": {"diagnosis": "Orthostatic hypotension from a new blood pressure tablet", "expected_disposition": "discharge"},
        "facts": [
            {"fact_id": "f.chief_complaint.dizziness", "category": "chief_complaint", "statement": "Light-headed on standing for five days",
             "patient_answer": "I get light-headed whenever I stand up. It's been five days.", "disclosure": {"rule": "volunteered"}, "critical": True},
            {"fact_id": "f.hpi.onset", "category": "hpi", "statement": "Started the day after a new tablet was added", "patient_answer": "It began the day after my doctor added a new tablet."},
            {"fact_id": "f.medications.current", "category": "medications", "statement": "Started doxazosin 4 mg at night six days ago; also takes ramipril",
             "patient_answer": "Ramipril for years, and six days ago they added doxazosin at night.", "critical": True},
            {"fact_id": "f.allergies.drug", "category": "allergies", "statement": "No known drug allergies", "patient_answer": "None that I know of.", "polarity": "negative"},
            {"fact_id": "f.social.alcohol", "category": "social", "statement": "Drinks half a bottle of wine most evenings", "cover_answer": "Hardly anything.",
             "patient_answer": "Half a bottle of wine most evenings, if I'm honest.", "disclosure": {"rule": "after_rapport", "rapport_needed": 2}},
            {"fact_id": "f.social.falls", "category": "social", "statement": "Fell in the kitchen two days ago, no injury", "topics": ["fall", "fallen", "falls"],
             "patient_answer": "I went down in the kitchen two days ago. Nothing broken."},
            {"fact_id": "f.vitals.lying_standing_bp", "category": "vitals", "statement": "Blood pressure 138/84 lying, 104/62 standing",
             "disclosure": {"rule": "on_request", "request": "exam:vitals"}, "critical": True},
        ],
        "objectives": [
            {"criterion": "Links the dizziness to the new medicine", "kind": "elicit_fact", "linked_fact_ids": ["f.hpi.onset", "f.medications.current"], "critical": True},
            {"criterion": "Measures lying and standing blood pressure", "kind": "action", "linked_requests": ["exam:vitals"]},
        ],
    }
    r = client.post("/api/cases", json=body)
    assert r.status_code == 201, r.text
    draft = r.json()
    cid = draft["case_id"]
    assert draft["status"] == "draft" and draft["version"] == 1 and draft["validation"]["ok"], draft["validation"]
    assert client.post("/api/encounters", json={"case_id": cid}).status_code == 409                    # a draft cannot be started by students
    assert client.post("/api/encounters", json={"case_id": cid, "preview": True}).status_code == 201   # faculty preview can
    assert client.post(f"/api/cases/{cid}/validate").json()["ok"]
    assert client.post(f"/api/cases/{cid}/publish").status_code == 409                                 # must be approved first
    assert client.post(f"/api/cases/{cid}/approve", json={"reviewer": "Prof. Test"}).json()["status"] == "approved"
    assert client.post(f"/api/cases/{cid}/publish").json()["status"] == "published"
    assert cid in [c["case_id"] for c in client.get("/api/cases", params={"status": "published"}).json()]

    eid = client.post("/api/encounters", json={"case_id": cid}).json()["encounter_id"]

    def say(text):
        return client.post(f"/api/encounters/{eid}/turn", json={"text": text}).json()

    assert "light-headed" in say("Hello, I'm Dr. Ito. What brings you in today?")["reply"]
    assert "doxazosin" in say("What medications are you taking?")["reply"]
    assert say("When did it start?")["reply"] == "It began the day after my doctor added a new tablet."
    assert say("Any allergies?")["reply"] == "None that I know of."
    assert say("Have you had any falls?")["reply"].startswith("I went down in the kitchen")
    assert say("Do you have any pets?")["result"] == "deflected_off_topic"
    assert say("Do you smoke?")["result"] == "answered_negative_by_default"            # the case defines nothing on smoking
    a = say("Do you drink alcohol?")                                # rapport is 2 after an introduction and an open question
    assert "Half a bottle" in a["reply"]
    v = client.post(f"/api/encounters/{eid}/request", json={"request": "exam:vitals"}).json()
    assert v["disclosed"][0]["fact_id"] == "f.vitals.lying_standing_bp"
    fin = client.post(f"/api/encounters/{eid}/finish", json={"disposition": "discharge", "summary": "Dizziness since doxazosin was started; postural drop."}).json()
    assert [o["result"] for o in fin["feedback"]["objectives"]] == ["met", "met"]
    assert fin["interaction_result"]["quality"] > 0.9
    # editing the published case makes v2 (draft); students keep getting v1 until v2 is published
    v2 = client.put(f"/api/cases/{cid}", json={"title": "Dizzy spells (revised)"}).json()
    assert v2["version"] == 2 and v2["status"] == "draft" and v2["new_version_created"] is True
    assert client.post("/api/encounters", json={"case_id": cid}).json()["case"]["version"] == 1


def test_validate_endpoint_reports_errors_for_bad_draft(client, mini_case):
    mini_case["facts"][3]["disclosure"] = {"rule": "after_rapport"}
    mini_case["objectives"][0]["linked_fact_ids"] = ["f.ghost"]
    cid = client.post("/api/cases", json=mini_case).json()["case_id"]
    rep = client.post(f"/api/cases/{cid}/validate").json()
    assert set(rep) == {"ok", "errors", "warnings", "consistency", "needs_acknowledgement"} and not rep["ok"]
    assert all(set(e) == {"path", "message"} for e in rep["errors"])
    r = client.post(f"/api/cases/{cid}/approve")
    assert r.status_code == 422 and r.json()["detail"]["errors"]
    # validating unsaved edits sent in the body
    fixed = client.post(f"/api/cases/{cid}/validate", json={"facts": [f for f in mini_case["facts"] if f["fact_id"] != "f.concealed.mood"],
                                                              "objectives": mini_case["objectives"][1:]}).json()
    assert fixed["ok"]


def test_create_from_template_and_from_description(client):
    r = client.post("/api/cases", json={"from_template": "neuro", "overrides": {"severity": "severe", "seed": 4, "sex": "female", "age": 71}})
    assert r.status_code == 201
    c = r.json()
    assert c["status"] == "draft" and c["origin"] == {"kind": "from_template", "condition_template": "neuro", "sim_seed": 4}
    assert c["profile"]["age"] == 71 and c["validation"]["ok"] and c["review"]["needs_faculty_review"]
    assert client.post("/api/cases", json={"from_template": "nope"}).status_code == 404
    r = client.post("/api/cases", json={"from_description": "Mr. Dale Horn, a 47-year-old man who works as a long-haul trucker, has had a fever and a bad cough for four days. He hides that he smokes two packs a day."})
    d = r.json()
    assert r.status_code == 201 and d["status"] == "draft" and d["created_from"]["method"] == "offline" and d["created_from"]["template_id"] == "respiratory"
    assert d["profile"]["name"] == "Dale Horn" and d["profile"]["age"] == 47 and d["profile"]["gender"] == "male"
    assert d["validation"]["ok"], d["validation"]["errors"]
    assert d["validation"]["needs_acknowledgement"]                       # a sparse draft is flagged, not silently "valid"
    hidden = [f for f in d["facts"] if f["category"] == "concealed"]
    assert len(hidden) == 1 and hidden[0]["patient_answer"] == "All right. I smoke two packs a day." and hidden[0]["cover_answer"]
    assert any(n.startswith("Taken from your text") for n in d["notes"]) and any(n.startswith("Missing") for n in d["notes"])
    assert any("draft" in n.lower() or "review" in n.lower() for n in d["notes"])


def test_reference_routes(client):
    t = client.get("/api/templates").json()
    assert len(t) == 9 and all(x["synthetic"] and x["needs_faculty_review"] for x in t)
    full = client.get("/api/templates/chest_pain").json()
    assert full["facts"] and all("fact_id" in f and "category" in f for f in full["facts"])
    assert client.get("/api/templates/zzz").status_code == 404
    rub = client.get("/api/rubrics").json()
    assert [r["rubric_id"] for r in rub] == ["builtin_encounter_v1"] and rub[0]["is_default"]
    assert client.get("/api/rubrics/default").json()["rubric_id"] == "builtin_encounter_v1"
    assert client.get("/api/rubrics/zzz").status_code == 404
    cl = client.get("/api/clinicians").json()
    assert cl["source"] == "builtin" and len(cl["clinicians"]) == 5 and cl["fictional"] is True
    assert client.get("/api/cases/nope").status_code == 404 and client.get("/api/encounters/enc-nope").status_code == 404
    assert client.post("/api/encounters", json={}).status_code == 422
    assert client.post("/api/encounters", json={"run_id": "live", "patient_id": 1}).status_code == 503
    st = client.get("/api/status").json()["services"]
    assert st["llm"] == {"live": False, "provider": "offline", "model": None} and st["voice"] == {"live": False, "provider": "browser"}


def test_tts_204_without_key_and_audio_with_key(client, monkeypatch):
    assert client.post("/api/tts", json={"text": "Hello"}).status_code == 204
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    import httpx

    class R:
        status_code, content = 200, b"ID3fakeaudio"
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, key=headers["xi-api-key"], text=json["text"])
        return R()
    monkeypatch.setattr(httpx, "post", fake_post)
    r = client.post("/api/tts", json={"text": "Hello", "voice": "v1"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fakeaudio"
    assert seen == {"url": "https://api.elevenlabs.io/v1/text-to-speech/v1", "key": "k", "text": "Hello"}

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(httpx, "post", boom)
    assert client.post("/api/tts", json={"text": "Hello"}).status_code == 204       # failure never becomes an error


def test_image_route_placeholder_and_private_file(client, tmp_path):
    r = client.get("/api/cases/chest-pain-line-cook/image")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg") and "RQ" in r.text
    assert client.get("/api/cases/nope/image").status_code == 404
    img = tmp_path / "private" / "photos" / "p.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    c = seed_case("chest-pain-line-cook")
    c["profile"]["image"] = str(img)
    del c["case_id"]
    cid = client.post("/api/cases", json=c).json()["case_id"]
    r = client.get(f"/api/cases/{cid}/image")
    assert r.headers["content-type"] == "image/png" and r.content.startswith(b"\x89PNG")
    # a path outside the private dir is never served
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"\x89PNG")
    client.put(f"/api/cases/{cid}", json={"profile": {**c["profile"], "image": str(outside)}})
    assert client.get(f"/api/cases/{cid}/image").headers["content-type"].startswith("image/svg")


def test_routes_match_contract():
    paths = {(m, r.path) for r in api.router.routes if hasattr(r, "methods") for m in r.methods if m in ("GET", "POST", "PUT")}  # the journey sub-router is checked in encounter/journey/tests
    expected = {("GET", "/cases"), ("GET", "/cases/{case_id}"), ("POST", "/cases"), ("PUT", "/cases/{case_id}"), ("POST", "/cases/{case_id}/validate"),
                ("POST", "/cases/{case_id}/approve"), ("POST", "/cases/{case_id}/publish"), ("GET", "/templates"), ("GET", "/templates/{template_id}"),
                ("GET", "/rubrics"), ("GET", "/rubrics/{rubric_id}"), ("GET", "/clinicians"), ("POST", "/encounters"), ("POST", "/encounters/{encounter_id}/turn"),
                ("POST", "/encounters/{encounter_id}/request"), ("GET", "/encounters/{encounter_id}"), ("POST", "/encounters/{encounter_id}/finish"),
                ("GET", "/encounters"), ("POST", "/tts")}
    assert expected <= paths, expected - paths
    assert paths - expected == {("GET", "/cases/{case_id}/image"), ("GET", "/encounter/status")}
