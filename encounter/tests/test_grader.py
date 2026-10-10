import json

import jsonschema
import pytest

from encounter import grader
from encounter.paths import CONTRACTS_DIR
from encounter.rubric import get_rubric

from .conftest import SEED_IDS, seed_case
from .scripts import SCRIPTS

ISCHEMA = json.loads((CONTRACTS_DIR / "interaction.schema.json").read_text())
RESULT_SCHEMA = {"$schema": ISCHEMA["$schema"], "$defs": ISCHEMA["$defs"], "$ref": "#/$defs/result"}


def run(manager, cid, lines=None, finish=None):
    sc = SCRIPTS[cid]
    eid = manager.start(seed_case(cid))["encounter_id"]
    for line in (sc["lines"] if lines is None else lines):
        manager.request(eid, line[1:]) if line.startswith("!") else manager.turn(eid, line)
    return eid, manager.finish(eid, **(sc["finish"] if finish is None else finish))


@pytest.mark.parametrize("cid", SEED_IDS)
def test_full_script_feedback_and_writeback_shape(manager, cid):
    eid, out = run(manager, cid)
    fb, res = out["feedback"], out["interaction_result"]
    jsonschema.validate(res, RESULT_SCHEMA)
    assert res["resolver"] == "played" and res["interaction_type"] == "clinician_encounter" and res["session_ref"] == eid
    assert 0.0 <= res["quality"] <= 1.0 and res["quality"] >= 0.8
    assert res["decision"]["disposition"] == "admit" and res["decision"]["kind"] == "disposition" and res["decision"]["orders"]
    assert set(SCRIPTS[cid]["expect"]) <= set(res["information_gained"])
    assert {o["objective_id"] for o in res["objective_results"]} == {o["objective_id"] for o in seed_case(cid)["objectives"]}
    assert fb["grader"] == "offline" and "not a validated" in fb["formative_note"].lower()
    transcript = {(t["turn"], t["text"]) for t in manager.get(eid)["transcript"]}
    n_ev = 0
    for o in fb["objectives"]:
        assert o["result"] in grader.RESULTS and isinstance(o["uncertain"], bool) and o["suggestion"]
        if o["result"] in ("met", "partly_demonstrated"):
            assert o["evidence"], o
        for e in o["evidence"]:
            n_ev += 1
            if not e["quote"].startswith("["):
                assert any(t == e["turn"] and (e["quote"].rstrip("…") in text) for t, text in transcript), e      # a real quote from that turn
    assert n_ev >= 8
    met = [o for o in fb["objectives"] if o["result"] == "met"]
    assert len(met) >= len(fb["objectives"]) - 2
    rub = fb["rubric"]
    assert len(rub["domains"]) == len(get_rubric()["domains"]) and rub["max_total"] <= 28
    for d in rub["domains"]:
        assert d["score"] in (1, 2, 3, 4, "N/A") and d["rationale"]
    assert fb["elicited"] and fb["strengths"] and isinstance(fb["next_time"], list)
    assert fb["structure"]["opening"]["observed"] and fb["structure"]["closing"]["observed"]
    assert fb["communication"]["empathy_statements"]


def test_poor_interview_is_graded_lower_with_missed_findings(manager):
    cid = "chest-pain-line-cook"
    eid, out = run(manager, cid, lines=["chest pain?", "do you smoke?", "Do you use drugs?", "any allergies?"],
                   finish={"disposition": "discharge", "summary": ""})
    fb, res = out["feedback"], out["interaction_result"]
    by = {o["objective_id"]: o for o in fb["objectives"]}
    assert by["obj.stimulant_use"]["result"] == "partly_demonstrated" and by["obj.stimulant_use"]["uncertain"]      # asked, accepted the denial
    assert by["obj.stimulant_use"]["evidence"][0]["quote"] == "Do you use drugs?"
    assert by["obj.initial_tests"]["result"] == "not_observed" and by["obj.initial_tests"]["evidence"] == []
    assert by["obj.nonjudgmental"]["result"] == "not_observed"
    assert by["obj.structure"]["result"] == "not_observed"
    assert by["obj.cardiac_risk"]["result"] == "partly_demonstrated"
    assert "f.concealed.cocaine_use" in {m["fact_id"] for m in fb["missed"]}
    assert next(m for m in fb["missed"] if m["fact_id"] == "f.concealed.cocaine_use")["asked"] is True
    assert res["quality"] < 0.45
    assert fb["quality_parts"]["decision_score"] == 0.0
    reasoning = next(d for d in fb["rubric"]["domains"] if "reason" in d["key"])
    assert reasoning["score"] in (1, 2)
    assert any("Start with your name" in s for s in fb["next_time"])
    assert fb["communication"]["missed_cues"]


def test_no_turns_everything_not_assessable(manager):
    eid = manager.start(seed_case("chest-pain-line-cook"))["encounter_id"]
    out = manager.finish(eid)
    assert {o["result"] for o in out["feedback"]["objectives"]} == {"not_assessable"}
    assert all(d["score"] == "N/A" for d in out["feedback"]["rubric"]["domains"])
    jsonschema.validate(out["interaction_result"], RESULT_SCHEMA)
    assert out["interaction_result"]["decision"] == {"kind": "none", "orders": [], "disposition": "undecided", "detail": ""}
    assert out["written_back"] is False and out["interaction_result"]["duration_min"] == 5.0


def test_quality_formula(manager):
    eid, out = run(manager, "abdominal-pain-grad-student")
    p = out["feedback"]["quality_parts"]
    assert out["feedback"]["quality"] == pytest.approx(0.5 * p["critical_fraction"] + 0.3 * p["objective_score"] + 0.2 * p["decision_score"], abs=2e-3)


def test_duration_formula(manager):
    eid, out = run(manager, "chest-pain-line-cook")
    st = manager.get(eid, "faculty")["ledger_full"]
    turns = sum(1 for e in st if e["kind"] == "turn")
    reqs = sum(1 for e in st if e["kind"] == "request")
    assert out["interaction_result"]["duration_min"] == pytest.approx(4 + 0.75 * turns + 1.5 * reqs, abs=0.06)


def test_verify_quotes_keeps_only_real_quotes():
    tr = [{"turn": 1, "speaker": "student", "text": "I'm so sorry to hear that. Take your time."}, {"turn": 2, "speaker": "patient", "text": "Thank you."}]
    ev = [{"turn": 1, "quote": "sorry to hear that"}, {"turn": 7, "quote": "Take your time."}, {"turn": 1, "quote": "I completely understand your pain"}, {"turn": 2, "quote": "ok"}]
    assert grader.verify_quotes(ev, tr) == [{"turn": 1, "quote": "sorry to hear that"}, {"turn": 1, "quote": "Take your time."}]


def test_rubric_default_is_builtin_when_private_absent():
    r = get_rubric("default")
    assert r["rubric_id"] == "builtin_encounter_v1" and r["source"] == "builtin" and len(r["domains"]) == 7
    assert r["allowed_scores"] == [4, 3, 2, 1, "N/A"] and len(r["rating_scale"]) == 4


def test_organizer_rubric_used_when_present(tmp_path, monkeypatch):
    d = tmp_path / "private" / "shp" / "pack" / "evaluation rubrics"
    d.mkdir(parents=True)
    (d / "encounter_evaluation_rubric.json").write_text(json.dumps({"title": "Stub", "rating_scale": [], "allowed_scores": [4, 3, 2, 1, "N/A"],
                                                                     "domains": [{"id": 1, "key": "information_gathering", "name": "Information gathering", "descriptors": {"4": "a", "1": "d"}}]}))
    r = get_rubric("default")
    assert r["rubric_id"] == "organizer_encounter" and r["source"] == "organizer_private" and r["is_default"]
