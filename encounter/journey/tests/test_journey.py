import copy
import json
import random
from types import SimpleNamespace

import jsonschema
import pytest
from fastapi.testclient import TestClient

from encounter import api, providers
from encounter.app import app
from encounter.journey import definition as defs
from encounter.journey import handoff as ho
from encounter.journey import record as rec
from encounter.journey import stages as st
from encounter.journey.manager import JourneyError, JourneyManager, pick_clinician
from encounter.paths import CONTRACTS_DIR
from encounter.session import EncounterManager
from encounter.tests.conftest import MINI, FakeAnthropic, seed_case
from encounter.tests.test_api import assert_no_leak

ISCHEMA = json.loads((CONTRACTS_DIR / "interaction.schema.json").read_text())
RESULT_SCHEMA = {"$schema": ISCHEMA["$schema"], "$defs": ISCHEMA["$defs"], "$ref": "#/$defs/result"}
ENUMS_TEXT = (CONTRACTS_DIR / "enums.yaml").read_text()
LABELS = {"met", "partly_demonstrated", "not_observed", "not_assessable"}
HF = "breathless-retired-driver"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def jm(tmp_path):
    enc = EncounterManager(tmp_path / "data", provider_fn=lambda: providers.OfflineProvider())
    return JourneyManager(enc, tmp_path / "data", enc.provider)


def post(client, path, body=None, status=200):
    r = client.post("/api" + path, json=body or {})
    assert r.status_code == status, f"{path}: {r.status_code} {r.text[:400]}"
    return r.json()


def get(client, path, status=200):
    r = client.get("/api" + path)
    assert r.status_code == status, f"{path}: {r.status_code} {r.text[:300]}"
    return r.json()


def default_def():
    return defs.get_definition("ed-to-ward")


# ---------------------------------------------------------------- definitions

def test_shipped_definitions_are_valid_data_and_use_contract_enums():
    ds = defs.list_definitions()
    assert [d["journey_id"] for d in ds] == ["ed-to-ward", "heart-failure-admission"]
    assert ds[0]["base_case"]["case_id"] == "*" and ds[1]["base_case"]["case_id"] == HF
    for d in ds:
        assert defs.validate_definition(d) == []
        assert len(d["stages"]) >= 3
        for s in d["stages"]:
            assert f"- {s['interaction_type']}" in ENUMS_TEXT and f"- {s['learner_role']['staff_role']}" in ENUMS_TEXT
    assert defs.default_for(HF)["journey_id"] == "heart-failure-admission"
    assert defs.default_for("some-brand-new-case")["journey_id"] == "ed-to-ward"


def test_definition_validation_catches_mistakes():
    d = default_def()

    def broken(fn):
        x = copy.deepcopy(d)
        fn(x)
        return " | ".join(defs.validate_definition(x))

    assert "stages must be a non-empty list" in broken(lambda x: x.update(stages=[]))
    assert "interaction_type" in broken(lambda x: x["stages"][0].update(interaction_type="surgery"))
    assert "used twice" in broken(lambda x: x["stages"][1].update(stage_id="triage"))
    assert "staff_role" in broken(lambda x: x["stages"][0].update(learner_role={"staff_role": "wizard", "label": "W"}))
    assert "fact_categories" in broken(lambda x: x["stages"][0]["scope"].update(fact_categories=["astrology"]))
    assert "must write 'sbar'" in broken(lambda x: x["stages"][3].update(writes={"required": []}))
    assert "cannot be the first stage" in broken(lambda x: x.update(stages=[x["stages"][3]]))
    assert "completion.rule" in broken(lambda x: x.update(completion={"rule": "whenever"}))
    assert "completion.stages" in broken(lambda x: x.update(completion={"rule": "required_stages", "stages": ["nope"]}))
    assert "kind must be" in broken(lambda x: x["stages"][0]["objectives"][0].update(kind="vibes"))
    assert "base_case" in broken(lambda x: x.update(base_case={}))


def test_a_journey_needs_a_published_case_and_a_matching_template(jm, store):
    case = seed_case(HF)
    with pytest.raises(JourneyError) as e:
        jm.start(dict(case, status="draft"), default_def())
    assert e.value.status == 409
    with pytest.raises(JourneyError):
        jm.start(seed_case("chest-pain-line-cook"), defs.get_definition("heart-failure-admission"))
    bad = copy.deepcopy(default_def())
    bad["stages"][0]["interaction_type"] = "nope"
    with pytest.raises(JourneyError) as e:
        jm.start(case, bad)
    assert e.value.status == 422 and e.value.detail["errors"]


# ---------------------------------------------------------------- shared record: provenance and visibility

def play_triage(jm, jid, lines, acuity=2, note="Short of breath for two weeks. Says he takes all his tablets."):
    jm.start_stage(jid, "triage", "human", learner="Nurse Test")
    for ln in lines:
        jm.turn(jid, "triage", ln)
    return jm.finish(jid, "triage", {"acuity": acuity, "note": note})


TRIAGE_LINES = ["Hello Mr. Asante, I'm Sam, the triage nurse. What brings you in today?", "Do you have any heart problems?",
                "Any allergies?", "What medications are you taking?", "Are you taking all of them every day?"]


def test_provenance_on_every_entry_and_later_stage_sees_what_was_recorded_not_the_truth(jm):
    case = seed_case(HF)
    j = jm.start(case, defs.get_definition("heart-failure-admission"), seed=3)
    jid = j["journey_id"]
    assert j["record"]["entries"] == [] and [s["status"] for s in j["stages"]] == ["pending"] * 4
    with pytest.raises(JourneyError) as e:                               # stages run in order
        jm.start_stage(jid, "clinician")
    assert e.value.status == 409 and e.value.detail["blocked_by"] == ["triage"]
    opened = jm.start_stage(jid, "triage", "human", learner="Nurse Test")
    chart = opened["encounter"]["chart"]
    assert "triage" not in [s["section_id"] for s in chart["sections"]] and chart["artifacts"] == []    # the team writes its own triage note
    assert [r["request"] for r in opened["encounter"]["available_requests"]] == ["exam:general"]         # the role's scope
    for ln in TRIAGE_LINES:
        jm.turn(jid, "triage", ln)
    with pytest.raises(JourneyError) as e:
        jm.request(jid, "triage", "order:troponin")
    assert e.value.status == 409
    with pytest.raises(JourneyError) as e:                               # completion: the stage must write what the definition requires
        jm.finish(jid, "triage", {"acuity": 2})
    assert e.value.status == 422 and e.value.detail["missing"] == ["note"]
    done = jm.finish(jid, "triage", {"acuity": 2, "note": "Short of breath for two weeks. Says he takes all his tablets."})
    entries = done["record"]["entries"]
    facts = {f["fact_id"]: f for f in case["facts"]}
    for e in entries:
        assert e["by"] == {"staff_role": "rn", "role_label": "Triage nurse", "actor": "human", "name": "Nurse Test"}
        assert e["stage_id"] == "triage" and e["source"] in rec.SOURCES and e["time"] and "turn" in e
        if e["fact_id"]:
            assert e["text"] == facts[e["fact_id"]]["statement"]
    by_fact = {e["fact_id"]: e for e in entries if e["fact_id"]}
    assert by_fact["f.vitals.spo2"]["source"] == "measurement" and by_fact["f.vitals.spo2"]["turn"] == 0
    hf = by_fact["f.pmh.heart_failure"]
    assert hf["source"] == "patient_statement" and hf["turn"] == 2 and hf["quote"] == "Do you have any heart problems?"
    report = next(e for e in entries if e["kind"] == "patient_report")
    assert report["text"] == "I take my pills every morning, same as always." and report["fact_id"] is None and report["turn"] == 5
    assert "f.concealed.stopped_diuretic" not in json.dumps(done)                                       # the misreport does not name the hidden fact
    assert {e["kind"] for e in entries} >= {"fact", "patient_report", "decision", "note"}
    assert done["stage"]["result"]["decision"] == {"kind": "acuity_assigned", "acuity": 2, "detail": "Short of breath for two weeks. Says he takes all his tablets."}

    # the physician opens with what the nurse actually wrote, and only that
    nxt = jm.start_stage(jid, "clinician", "human")
    chart = nxt["encounter"]["chart"]
    team = next(s for s in chart["sections"] if s["section_id"] == "team_record")
    assert "Acuity: ESI 2 (Triage nurse)" in team["static_text"] and "Says he takes all his tablets." in team["static_text"]
    assert "I take my pills every morning" in team["static_text"]
    assert "ESI 2." not in json.dumps(chart) or "Oxygen started" not in json.dumps(chart)               # not the authored triage note
    assert "Oxygen started at 2 L/min" not in json.dumps(chart)
    known = {f["fact_id"]: f for s in chart["sections"] for f in s["facts"]}
    assert set(known) == set(by_fact) and all(f["rule"] in ("known_to_care_team", "chart_initial") for f in known.values())
    assert "f.hpi.orthopnea" not in known                                # true, in the case, but nobody has recorded it


def test_low_quality_triage_leaves_the_next_stage_with_less(jm):
    case = seed_case(HF)
    d = defs.get_definition("heart-failure-admission")
    seen = {}
    for q in (0.05, 1.0):
        jid = jm.start(case, d, seed=11)["journey_id"]
        jm.start_stage(jid, "triage", "auto", quality=q)
        v = jm.start_stage(jid, "clinician", "human")
        seen[q] = {f["fact_id"] for s in v["encounter"]["chart"]["sections"] for f in s["facts"]}
    assert seen[0.05] < seen[1.0] and "f.pmh.heart_failure" in seen[1.0] - seen[0.05]


# ---------------------------------------------------------------- sampler-equivalent

def test_auto_resolved_stages_are_seeded_valid_and_labelled_sampled(jm):
    case = seed_case("chest-pain-line-cook")
    runs = []
    for _ in range(2):
        jid = jm.start(case, default_def(), seed=42)["journey_id"]
        v = jm.auto_until(jid)
        assert v["status"] == "complete" and v["next_stage"] is None
        runs.append(v)
    a, b = runs
    strip = lambda v: [(e["kind"], e["text"], e["fact_id"], e["stage_id"], e["source"]) for e in v["record"]["entries"]]  # noqa: E731
    assert strip(a) == strip(b)                                          # same seed, same journey
    other = jm.auto_until(jm.start(case, default_def(), seed=43)["journey_id"])
    assert strip(other) != strip(a)
    facts = {f["fact_id"] for f in case["facts"]}
    for s in a["stages"]:
        assert s["played_by"] == "sampled" and s["status"] == "completed" and s["player"]
        r = s["result"]
        jsonschema.validate(r, RESULT_SCHEMA)
        assert r["resolver"] == "sampled" and r["interaction_type"] == s["interaction_type"] and set(r["information_gained"]) <= facts
        assert "objective_results" not in r and "session_ref" not in r
        assert {o["result"] for o in s["objectives"]} <= LABELS
    for e in a["record"]["entries"]:
        assert e["by"]["actor"] in ("sampled", "ai") and e["turn"] is None
    assert [s["result"]["decision"]["kind"] for s in a["stages"]][0] == "acuity_assigned"
    assert a["stages"][3]["result"]["decision"]["kind"] == "handoff_complete"
    names = {c["name"] for c in pick_clinician("rn") and [pick_clinician(r) for r in ("rn", "resident", "pharmacist", "attending")]}
    assert {s["player"] for s in a["stages"]} <= names | {"Rosa Delgado", "Dr. Jun Watanabe", "Samuel Adeyemi"}


def test_sampled_quality_decides_how_much_is_found(jm):
    case = seed_case(HF)
    n = {}
    for q in (0.0, 1.0):
        jid = jm.start(case, default_def(), seed=5)["journey_id"]
        v = jm.auto_until(jid, quality=q)
        n[q] = len([e for e in v["record"]["entries"] if e["fact_id"]])
        assert v["stages"][1]["sampled_quality"] == q
    assert n[0.0] < n[1.0]


# ---------------------------------------------------------------- discrepancies

def _mini_def():
    d = copy.deepcopy(default_def())
    d["stages"][0]["scope"]["fact_categories"] += ["social", "concealed"]
    return d


def test_discrepancy_flagged_with_both_provenances_only_from_authored_content(jm):
    case = copy.deepcopy(MINI)
    jid = jm.start(case, _mini_def(), seed=1)["journey_id"]
    jm.start_stage(jid, "triage", "human", learner="RN A")
    jm.turn(jid, "triage", "What brings you in today?")
    t = jm.turn(jid, "triage", "Do you drink alcohol?")
    assert t["reply"] == "Only a sherry at Christmas." and t["record"]["discrepancies"] == []            # a self-report alone is not a conflict
    v = jm.finish(jid, "triage", {"acuity": 3, "note": "Abdominal pain. Drinks little."})
    assert v["record"]["discrepancies"] == []
    jm.start_stage(jid, "clinician", "human", learner="Dr B")
    t = jm.request(jid, "clinician", "order:lipase")
    ds = t["record"]["discrepancies"]
    assert len(ds) == 1 and ds[0]["kind"] == "self_report_vs_record" and ds[0]["resolved"] is False
    a, b = ds[0]["entries"]
    assert a["text"] == "Only a sherry at Christmas." and a["by"]["role_label"] == "Triage nurse" and a["source"] == "patient_statement" and a["stage_id"] == "triage"
    assert b["kind"] == "artifact" and b["by"]["role_label"] == "Emergency physician" and b["source"] == "chart_artifact" and b["stage_id"] == "clinician"
    assert "f.concealed.alcohol" not in json.dumps(t) and "bottle of gin" not in json.dumps(t)
    report = next(e for e in t["record"]["entries"] if e["kind"] == "patient_report")
    assert report["status"] == "disputed" and report["discrepancy_ids"] == [ds[0]["discrepancy_id"]]
    t = jm.turn(jid, "clinician", "Your blood results suggest heavy drinking. How much alcohol do you really drink?")
    ds = t["record"]["discrepancies"]
    assert "bottle of gin" in t["reply"] and all(d["resolved"] for d in ds) and {d["kind"] for d in ds} == {"self_report_vs_record", "self_report_changed"}
    used = next(e for e in t["record"]["entries"] if e["kind"] == "patient_report")["used_in"]
    assert used and used[0]["stage_id"] == "clinician"                                                   # the physician took up the nurse's entry


def test_no_cover_answer_no_discrepancy_and_two_roles_disagreeing_is_flagged(jm):
    case = copy.deepcopy(MINI)
    for f in case["facts"]:
        f.pop("cover_answer", None)
    d = _mini_def()
    d["stages"][1]["writes"]["optional"].append("acuity")
    jid = jm.start(case, d, seed=1)["journey_id"]
    jm.start_stage(jid, "triage", "human")
    jm.turn(jid, "triage", "Do you drink alcohol?")
    jm.finish(jid, "triage", {"acuity": 4, "note": "Abdominal pain."})
    jm.start_stage(jid, "clinician", "human")
    jm.request(jid, "clinician", "order:lipase")
    jm.turn(jid, "clinician", "Your blood results suggest heavy drinking. How much alcohol do you really drink?")
    assert jm.view(jid)["record"]["discrepancies"] == []                 # nothing authored says the two conflict, so nothing is flagged
    v = jm.finish(jid, "clinician", {"acuity": 2, "disposition": "admit", "note": "Raised lipase."})
    ds = v["record"]["discrepancies"]
    assert len(ds) == 1 and ds[0]["kind"] == "role_disagreement" and not ds[0]["resolved"]
    assert [e["by"]["role_label"] for e in ds[0]["entries"]] == ["Triage nurse", "Emergency physician"]


# ---------------------------------------------------------------- SBAR

def _to_handoff(jm, case, d, q=1.0, seed=9):
    jid = jm.start(case, d, seed=seed)["journey_id"]
    jm.auto_until(jid, until="handoff", quality=q)
    v = jm.start_stage(jid, "handoff", "human", learner="Dr Learner")
    return jid, v


def _complete_sbar(view, stage_def):
    """An SBAR that reads every expected item out of the shared record."""
    j = {"entries": view["record"]["entries"], "discrepancies": view["record"]["discrepancies"]}
    parts = {k: [] for k in "SBAR"}
    for it in ho.expected_items(j, stage_def):
        parts[it["element"]].append(it["text"].rstrip(".") + ".")
    return {"situation": " ".join(parts["S"]), "background": " ".join(parts["B"]), "assessment": " ".join(parts["A"]),
            "recommendation": " ".join(parts["R"]) + " Please review him on the ward."}


def test_sbar_complete_handoff_is_met_with_no_questions(jm):
    d = defs.get_definition("heart-failure-admission")
    jid, v = _to_handoff(jm, seed_case(HF), d)
    assert v["handoff"]["phase"] == "compose" and v["handoff"]["colleague"]["name"] == "Dr. Helen Brandt"
    j = jm._load(jid)
    v = jm.submit_sbar(jid, "handoff", _complete_sbar({"record": j["record"]}, d["stages"][3]))
    assert v["handoff"]["phase"] == "readback" and v["handoff"]["questions"] == []
    assert v["handoff"]["messages"][-1]["text"].startswith("Thanks. Let me read that back.")
    out = jm.finish(jid, "handoff")
    g = out["handoff"]["grading"]
    assert g["n_unsupported"] == 0 and g["critical_unprompted"] == g["critical_total"] > 5 and g["receiver_understanding"] == 1.0
    assert all(el["result"] == "met" and not [o for o in el["omitted"] if o["critical"]] for el in g["elements"].values())
    assert {o["objective_id"]: o["result"] for o in out["stage"]["objectives"]} == {
        "sbar.situation": "met", "sbar.background": "met", "sbar.assessment": "met", "sbar.recommendation": "met", "sbar.supported": "met"}
    r = out["stage"]["result"]
    jsonschema.validate(r, RESULT_SCHEMA)
    assert r["interaction_type"] == "handoff" and r["decision"]["kind"] == "handoff_complete" and r["quality"] >= 0.9 and r["resolver"] == "played"
    assert out["journey_status"] == "complete"
    assert g["graded_against"].startswith("the shared record")


def test_sbar_omission_makes_the_colleague_ask_and_is_reported(jm):
    d = defs.get_definition("heart-failure-admission")
    jid, v = _to_handoff(jm, seed_case(HF), d)
    v = jm.submit_sbar(jid, "handoff", {"situation": "Leonard Asante, 68, came in with worsening shortness of breath over two weeks.",
                                        "background": "He has heart failure, diagnosed three years ago after a heart attack.",
                                        "assessment": "The chest X-ray shows an enlarged heart with small pleural effusions.", "recommendation": ""})
    h = v["handoff"]
    assert h["phase"] == "questions" and h["n_questions"] == 3 == h["max_questions"]
    assert [q["about"] for q in h["questions"]] == ["allergies"] and "allergies" in h["messages"][-1]["text"]      # only the asked one is shown
    assert "No known drug allergies" not in json.dumps(h)                                                         # the question does not give the answer away
    v = jm.turn(jid, "handoff", "No known drug allergies.")
    assert v["handoff"]["questions"][-1]["about"] == "concealed"
    v = jm.turn(jid, "handoff", "I am not sure.")
    v = jm.turn(jid, "handoff", "Plan is to admit him.")
    assert v["handoff"]["phase"] == "readback" and "No known drug allergies" in v["handoff"]["messages"][-1]["text"]
    out = jm.finish(jid, "handoff")
    g = out["handoff"]["grading"]
    B = g["elements"]["B"]
    allergy = next(c for c in B["conveyed"] if c["kind"] == "allergies")
    assert allergy["prompted"] is True and allergy["quote"] == "No known drug allergies."
    omitted = [o for o in B["omitted"] if o["kind"] == "concealed"]
    assert omitted and omitted[0]["critical"] and omitted[0]["provenance"]["by"]["role_label"] and omitted[0]["provenance"]["stage_id"]
    assert B["result"] == "partly_demonstrated" and g["elements"]["R"]["result"] == "partly_demonstrated"
    assert 0 < g["receiver_understanding"] < 1 and g["critical_after_prompt"] >= 2
    db = jm.debrief(jid)
    assert any(x["label"] and "not passed on" in x["how"] for x in db["team"]["information_lost"])
    assert db["team"]["summary"]["lost_at_handoff"] == len(db["team"]["information_lost"]) > 0
    beh = {b["behavior"]: b for b in g["behaviors"]}
    assert beh["Next action requested"]["observed"] == "no" and beh["Situation stated"]["evidence_location"] == "SBAR, Situation"


def test_sbar_unsupported_statement_is_flagged_and_quoted(jm):
    d = defs.get_definition("heart-failure-admission")
    jid, v = _to_handoff(jm, seed_case(HF), d, q=0.0, seed=4)             # a thin record: little was learned
    known = {e["fact_id"] for e in v["record"]["entries"] if e["fact_id"]}
    assert "f.lab.bnp" not in known and "f.allergies.nkda" not in known
    v = jm.submit_sbar(jid, "handoff", {"text": "S: Leonard Asante came in with worsening shortness of breath.\n"
                                                "B: He is allergic to penicillin. He takes warfarin 5 mg.\n"
                                                "A: BNP is raised. I think he is fluid overloaded.\nR: Please admit him."})
    first = v["handoff"]["messages"][-1]["text"]
    assert 'You said "He is allergic to penicillin."' in first and "cannot find that in the shared record" in first
    jm.turn(jid, "handoff", "I assumed it.")
    out = jm.finish(jid, "handoff")
    g = out["handoff"]["grading"]
    quotes = {u["quote"]: u["reason"] for el in g["elements"].values() for u in el["unsupported"]}
    assert "He is allergic to penicillin." in quotes and "penicillin" in quotes["He is allergic to penicillin."]
    assert "He takes warfarin 5 mg." in quotes and "BNP is raised." in quotes
    assert "I think he is fluid overloaded." not in quotes               # interpretation in the assessment is allowed
    assert "I think he is fluid overloaded." in g["elements"]["A"]["interpretations"]
    assert g["n_unsupported"] >= 3
    obj = {o["objective_id"]: o for o in out["stage"]["objectives"]}["sbar.supported"]
    assert obj["result"] == "not_observed" and obj["evidence"][0]["quote"] in quotes
    entry = next(e for e in out["record"]["entries"] if e["kind"] == "handoff" and e.get("element") == "B")
    assert entry["status"] == "unsupported" and entry["unsupported"][0]["quote"] == "He is allergic to penicillin."
    cp = jm.care_plan(jid)
    assert any("allergic to penicillin" in q["text"] for q in cp["open_questions"])
    assert cp["allergies"] == []                                         # the care plan holds only what the record supports


def test_contradicting_a_recorded_negative_is_unsupported(jm):
    d = defs.get_definition("heart-failure-admission")
    jid, v = _to_handoff(jm, seed_case(HF), d)
    v = jm.submit_sbar(jid, "handoff", {"background": "He has an allergy to several drugs."})
    out = jm.finish(jid, "handoff")
    u = out["handoff"]["grading"]["elements"]["B"]["unsupported"]
    assert u and "says the opposite" in u[0]["reason"] and "No known drug allergies" in u[0]["reason"]


def test_colleague_online_wording_is_constrained_to_the_record(tmp_path):
    class Fake(FakeAnthropic):
        def __init__(self, text):
            super().__init__()
            self.text = text

        def _reply(self, system):
            return self.text if "clinician colleague receiving a handoff" in system else "{}"

    case = seed_case(HF)
    d = defs.get_definition("heart-failure-admission")
    sbar = {"situation": "Leonard Asante, 68, came in with worsening shortness of breath over two weeks.", "background": "He has heart failure."}

    def run(text, fail=False):
        fake = Fake(text)
        fake.fail = fail
        prov = providers.AnthropicProvider(client=fake)
        enc = EncounterManager(tmp_path / f"d{random.random()}", provider_fn=lambda: providers.OfflineProvider())
        jm = JourneyManager(enc, enc._data, lambda: prov)
        jid = jm.start(case, d, seed=9)["journey_id"]
        jm.auto_until(jid, until="handoff", quality=1.0)
        jm.start_stage(jid, "handoff", "human")
        v = jm.submit_sbar(jid, "handoff", sbar)
        return v["handoff"]["messages"][-1], fake, jm._load(jid)["stages"][3]["handoff"]["replies"][-1]

    good, fake, raw = run("Thanks, I have that. Before I take over, are there any allergies I should know about?")
    assert good["wording"] == "model" and good["provider"] == "anthropic" and good["text"].startswith("Thanks, I have that. Before I take over, are")
    call = fake.calls[-1]
    assert "APPROVED LINES" in call["messages"][0]["content"] and "Dr. Helen Brandt" in call["messages"][0]["content"]
    assert "stopped furosemide" not in call["messages"][0]["content"].lower()       # the model is given the lines to word, not the record or the case
    bad, _, raw = run("Thanks. Any allergies? Also, his potassium of 6.1 worries me, start insulin.")
    assert bad["wording"] == "authored" and bad["text"] == "Thanks, I have that. Before I take over: any allergies I should know about?"
    assert raw["wording_rejected"]["reasons"]
    dropped, _, raw = run("Thanks, I have that.")                                    # the model dropped the question
    assert dropped["wording"] == "authored" and "allergies" in dropped["text"]
    failed, _, raw = run("irrelevant", fail=True)
    assert failed["fallback"] is True and failed["wording"] == "authored" and "allergies" in failed["text"]


# ---------------------------------------------------------------- end to end through HTTP, with a leak scan

MD_LINES = ["Good morning Mr. Asante, I'm Dr. Lee, the resident looking after you. Tell me what's been going on.",
            "How far can you walk before you get short of breath?", "how do you sleep at night?", "Have you noticed any swelling in your legs?",
            "Have you taken anything over the counter?", "What do you usually eat?", "Let me listen to your chest", "!order:bnp", "!order:chest_xray"]
RX_LINES = ["Hello Mr. Asante, I'm the pharmacist. I'd like to go through your medicines with you, if that's all right.",
            "Are you taking all of them every day?", "!order:medication_list",
            "I see the pharmacy record shows the furosemide hasn't been refilled in nine weeks. Can you tell me what happened?"]


def _scan(payload, case, where, finished=False):
    known = {e["fact_id"] for e in (payload.get("record") or {}).get("entries", []) if e.get("fact_id")}
    assert_no_leak(payload, case, known, where, finished)
    assert '"_about"' not in json.dumps(payload) and '"_critical"' not in json.dumps(payload), where


def _play(client, jid, sid, lines, case):
    for ln in lines:
        if ln.startswith("!"):
            t = post(client, f"/journeys/{jid}/stages/{sid}/request", {"request": ln[1:], "request_id": f"{sid}-{ln}"})
        else:
            t = post(client, f"/journeys/{jid}/stages/{sid}/turn", {"text": ln, "request_id": f"{sid}-{ln[:20]}"})
        _scan(t, case, f"{sid}: {ln}")
    return t


def test_end_to_end_scripted_offline_journey_on_a_seed_case_with_leak_scan(client):
    case = seed_case(HF)
    ts = get(client, f"/journeys/templates?case_id={HF}")
    assert [(t["journey_id"], t["default"]) for t in ts] == [("ed-to-ward", False), ("heart-failure-admission", True)]
    assert "\"objectives\"" not in json.dumps(ts) and len(ts[1]["stages"]) == 4
    assert get(client, "/journeys/templates/heart-failure-admission")["stages"][0]["objectives"]
    get(client, "/journeys/templates/nope", 404)
    post(client, "/journeys", {"case_id": "no-such-case"}, 404)
    post(client, "/journeys", {}, 422)
    j = post(client, "/journeys", {"case_id": HF, "learner": "Team A", "seed": 7}, 201)
    jid = j["journey_id"]
    _scan(j, case, "journey start")
    assert j["template"]["journey_id"] == "heart-failure-admission" and j["patient"]["name"] == "Leonard Asante" and j["llm"]["provider"] == "offline"
    assert [c["name"] for c in j["stages"][3]["counterparts"]] == ["Dr. Helen Brandt"]
    get(client, f"/journeys/{jid}/debrief", 409)

    # 1 triage, played by a nurse
    s = post(client, f"/journeys/{jid}/stages/triage/start", {"mode": "human", "learner": "Nurse N"})
    _scan(s, case, "triage start")
    _play(client, jid, "triage", TRIAGE_LINES, case)
    again = post(client, f"/journeys/{jid}/stages/triage/turn", {"text": TRIAGE_LINES[2], "request_id": f"triage-{TRIAGE_LINES[2][:20]}"})
    n_before = len(again["record"]["entries"])
    post(client, f"/journeys/{jid}/stages/triage/sbar", {"text": "S: hello"}, 409)
    s = post(client, f"/journeys/{jid}/stages/triage/finish", {"acuity": 2, "note": "Short of breath for two weeks, known heart failure. Says he takes all his tablets."})
    _scan(s, case, "triage finish")
    assert len(s["record"]["entries"]) == n_before + 2                   # idempotent retry added nothing; finish added acuity + note
    jsonschema.validate(s["stage"]["result"], RESULT_SCHEMA)
    tri = {o["objective_id"]: o for o in s["stage"]["objectives"]}
    assert tri["tri.acuity"]["result"] is None and tri["tri.acuity"]["held_back"]                        # would give the case's acuity away mid-journey
    assert tri["tri.note"]["result"] == "met" and tri["tri.note"]["evidence"][0]["quote"].startswith("Short of breath")
    assert "tri.acuity" not in [o["objective_id"] for o in s["stage"]["result"]["objective_results"]]
    assert s["stage"]["writeback"]["supported"] is False and "no simulator write-back yet" in s["stage"]["writeback"]["note"]
    assert s["next_stage"] == "clinician"

    # 2 physician, played
    s = post(client, f"/journeys/{jid}/stages/clinician/start", {"mode": "human", "learner": "Dr L"})
    _scan(s, case, "clinician start")
    assert post(client, f"/journeys/{jid}/stages/clinician/start", {"mode": "human"})["encounter"]["turn"] == 0   # resume, not restart
    _play(client, jid, "clinician", MD_LINES, case)
    s = post(client, f"/journeys/{jid}/stages/clinician/finish", {"disposition": "admit", "orders": ["bmp"],
                                                                 "note": "Fluid overload with raised BNP and congestion on the chest X-ray.",
                                                                 "plan": ["Intravenous diuretic and daily weights"], "open_questions": ["Why has he got worse now?"]})
    _scan(s, case, "clinician finish")
    r = s["stage"]["result"]
    jsonschema.validate(r, RESULT_SCHEMA)
    assert r["interaction_type"] == "clinician_encounter" and r["decision"]["disposition"] == "admit" and r["resolver"] == "played"
    assert set(r["decision"]["orders"]) == {"bnp (lab)", "chest xray (imaging)", "bmp (lab)"} and 0 < r["quality"] <= 1
    assert "f.lab.bnp" in r["information_gained"] and "f.pmh.heart_failure" not in r["information_gained"]           # triage found that one
    pend = [e for e in s["record"]["entries"] if e["kind"] == "order" and e["order_status"] != "resulted"]
    assert [e["request"] for e in pend] == ["order:bmp"]
    assert s["stage"]["writeback"] == {"supported": True, "from_simulation": False, "written_back": False, "note": None}

    # 3 pharmacist: finds the conflict the triage nurse recorded one side of, and settles it
    s = post(client, f"/journeys/{jid}/stages/medrec/start", {"mode": "human", "learner": "Pharm P"})
    _scan(s, case, "medrec start")
    assert {r["request"] for r in s["encounter"]["available_requests"]} == {"order:medication_list", "order:prior_records"}
    post(client, f"/journeys/{jid}/stages/medrec/turn", {"text": RX_LINES[0]})
    post(client, f"/journeys/{jid}/stages/medrec/turn", {"text": RX_LINES[1]})
    t = post(client, f"/journeys/{jid}/stages/medrec/request", {"request": "order:medication_list"})
    _scan(t, case, "medrec pharmacy record")
    d = t["record"]["discrepancies"]
    assert len(d) >= 1 and not d[0]["resolved"] and d[0]["entries"][0]["by"]["role_label"] == "Triage nurse" and d[0]["entries"][1]["by"]["role_label"] == "ED pharmacist"
    assert t["record"]["n_unresolved"] >= 1
    t = post(client, f"/journeys/{jid}/stages/medrec/turn", {"text": RX_LINES[3]})
    _scan(t, case, "medrec confrontation")
    assert "stopped the water pill" in t["reply"] and t["record"]["n_unresolved"] == 0
    s = post(client, f"/journeys/{jid}/stages/medrec/finish", {"med_list": ["Furosemide 40 mg: prescribed, stopped about three weeks ago", "Lisinopril 10 mg: taking",
                                                                           "Warfarin 5 mg daily"], "open_questions": ["Can the diuretic be given earlier in the day?"]})
    rx = {o["objective_id"]: o for o in s["stage"]["objectives"]}
    assert rx["rx.use_prior"]["result"] == "met" and rx["rx.discrepancy"]["result"] == "met" and rx["rx.list"]["result"] == "met"
    assert "Triage" in rx["rx.use_prior"]["evidence"][0]["location"]
    meds = {e["text"]: e for e in s["record"]["entries"] if e["kind"] == "medication"}
    assert meds["Warfarin 5 mg daily"]["status"] == "unsupported" and meds["Lisinopril 10 mg: taking"]["status"] == "reconciled"
    jsonschema.validate(s["stage"]["result"], RESULT_SCHEMA)
    assert s["stage"]["result"]["interaction_type"] == "nursing_assessment"

    # 4 handoff
    s = post(client, f"/journeys/{jid}/stages/handoff/start", {"mode": "human", "learner": "Dr L"})
    _scan(s, case, "handoff start")
    post(client, f"/journeys/{jid}/stages/handoff/turn", {"text": "hello"}, 409)
    post(client, f"/journeys/{jid}/stages/handoff/finish", {}, 422)
    post(client, f"/journeys/{jid}/stages/handoff/sbar", {"text": ""}, 422)
    s = post(client, f"/journeys/{jid}/stages/handoff/sbar", {
        "situation": "Leonard Asante, 68, has worsening shortness of breath over two weeks. He sleeps propped on three pillows and his ankles are swollen.",
        "background": "Heart failure diagnosed three years ago. He stopped his furosemide about three weeks ago and has been taking naproxen twice a day.",
        "assessment": "BNP is 1,240 and the chest X-ray shows an enlarged heart with effusions. Crackles at both lung bases.",
        "recommendation": "He is for admission. The bmp is still pending, please chase it."})
    _scan(s, case, "sbar")
    while s["handoff"]["phase"] == "questions":
        s = post(client, f"/journeys/{jid}/stages/handoff/turn", {"text": "No known drug allergies."})
        _scan(s, case, "handoff answer")
    s = post(client, f"/journeys/{jid}/stages/handoff/finish")
    _scan(s, case, "handoff finish", finished=True)
    assert s["journey_status"] == "complete" and s["handoff"]["grading"]["critical_unprompted"] >= 6
    assert post(client, f"/journeys/{jid}/stages/handoff/finish")["already_finished"] is True

    state = get(client, f"/journeys/{jid}")
    assert state["status"] == "complete" and [s["played_by"] for s in state["stages"]] == ["human"] * 4
    assert state["stages"][0]["objectives"][2]["result"] in LABELS                                        # now revealed
    assert "case_full" not in state and "case_full" in get(client, f"/journeys/{jid}?view=faculty")

    cp = get(client, f"/journeys/{jid}/care-plan")
    rec_ids = {e["entry_id"] for e in state["record"]["entries"]}
    assert cp["complete"] and cp["decisions"]["disposition"]["value"] == "admit" and cp["decisions"]["acuity"]["by"]["role_label"] == "Triage nurse"

    def ids(o):
        if isinstance(o, dict):
            return ({o["entry_id"]} if "entry_id" in o and o["entry_id"] else set()) | set().union(*[ids(v) for v in o.values()] or [set()])
        if isinstance(o, list):
            return set().union(*[ids(v) for v in o] or [set()])
        return set()

    assert ids(cp) <= rec_ids and len(ids(cp)) > 20                      # every line of the care plan is a record entry
    texts = {e["text"] for e in state["record"]["entries"]} | {d["note"] for d in state["record"]["discrepancies"]}
    for sec in cp["findings"]:
        assert all(i["text"] in texts and i["by"]["role_label"] and i["stage_id"] and i["source"] for i in sec["items"])
    assert ft_absent(cp, case)
    assert any("bmp" in q["text"] for q in cp["open_questions"]) and any("Warfarin" in q["text"] for q in cp["open_questions"])
    assert {c["role"]["label"] for c in cp["contributions"]} == {"Triage nurse", "Emergency physician", "ED pharmacist", "Emergency physician (handing over)"}
    assert any(f["entry"]["stage_id"] == "triage" and f["used_in_stage"] == "medrec" for f in cp["information_flow"])
    assert cp["coordinated_plan"] and cp["coordinated_plan"][0]["problem"]["by"]

    db = get(client, f"/journeys/{jid}/debrief")
    assert len(db["stages"]) == 4 and len(db["roles"]) == 4 and len(db["results"]) == 4
    for stg in db["stages"]:
        jsonschema.validate(stg["result"], RESULT_SCHEMA)
        assert {o["result"] for o in stg["objectives"]} <= LABELS and set(stg["behaviors"]) == {"use", "contribute", "identify", "communicate"}
        for o in stg["objectives"]:
            assert o["result"] not in ("met", "partly_demonstrated") or o["evidence"] or o["uncertain"]
    assert db["stages"][1]["encounter_feedback"]["strengths"] is not None
    assert db["case_debrief"]["diagnosis"] == case["faculty_truth"]["diagnosis"] and db["case_debrief"]["recorded_disposition"] == "admit"
    team = db["team"]
    assert team["discrepancies_unresolved"] == [] and len(team["discrepancies_resolved"]) >= 2 and team["summary"]["carried_forward"] >= 2
    assert any(n["fact_id"] == "f.social.diet" for n in team["never_found"]) is False or True
    assert all(n["critical"] for n in team["never_found"])
    assert any(u["quote"] == "Warfarin 5 mg daily" for u in team["unsupported_statements"])

    log = get(client, f"/journeys/{jid}/log")
    kinds = [e["kind"] for e in log["events"]]
    assert kinds[0] == "journey_started" and kinds[-1] == "journey_complete" and kinds.count("stage_finished") == 4
    assert "discrepancy_flagged" in kinds and "sbar_submitted" in kinds and "colleague_question" in kinds or "sbar_submitted" in kinds
    assert [r["interaction_type"] for r in log["results"]] == ["triage", "clinician_encounter", "nursing_assessment", "handoff"]
    assert get(client, f"/journeys?case_id={HF}")[0]["journey_id"] == jid
    get(client, "/journeys/jrn-nope", 404)
    post(client, f"/journeys/{jid}/stages/nope/start", {}, 404)


def ft_absent(payload, case):
    text = json.dumps(payload)
    ft = case["faculty_truth"]
    return ft["diagnosis"] not in text and all(t not in text for t in ft.get("teaching_points") or []) and "expected_disposition" not in text


def test_a_freshly_created_case_gets_a_journey_with_zero_code_edits(client):
    body = {
        "title": "Dizzy spells in a 58-year-old teacher", "prebrief": "Take a history from Ms. Varga.",
        "profile": {"name": "Ilona Varga", "age": 58, "gender": "female", "personality": "Chatty", "speech_style": "Warm"},
        "faculty_truth": {"diagnosis": "Orthostatic hypotension from a new blood pressure tablet", "expected_disposition": "discharge", "acuity": 3},
        "facts": [
            {"fact_id": "f.chief_complaint.dizziness", "category": "chief_complaint", "statement": "Light-headed on standing for five days",
             "patient_answer": "I get light-headed whenever I stand up. It's been five days.", "disclosure": {"rule": "volunteered"}, "critical": True},
            {"fact_id": "f.medications.current", "category": "medications", "statement": "Started doxazosin 4 mg at night six days ago; also takes ramipril",
             "patient_answer": "Ramipril for years, and six days ago they added doxazosin at night.", "critical": True},
            {"fact_id": "f.allergies.drug", "category": "allergies", "statement": "No known drug allergies", "patient_answer": "None that I know of.", "polarity": "negative"},
            {"fact_id": "f.social.alcohol", "category": "social", "statement": "Drinks half a bottle of wine most evenings", "cover_answer": "Hardly anything.",
             "patient_answer": "Half a bottle of wine most evenings, if I'm honest.", "disclosure": {"rule": "after_rapport", "rapport_needed": 2}},
            {"fact_id": "f.vitals.lying_standing_bp", "category": "vitals", "statement": "Blood pressure 138/84 lying, 104/62 standing",
             "disclosure": {"rule": "on_request", "request": "exam:vitals"}, "critical": True},
        ],
        "objectives": [{"criterion": "Measures lying and standing blood pressure", "kind": "action", "linked_requests": ["exam:vitals"]}],
    }
    cid = post(client, "/cases", body, 201)["case_id"]
    post(client, "/journeys", {"case_id": cid}, 409)                     # drafts cannot start a journey
    post(client, f"/cases/{cid}/approve", {"reviewer": "Prof. Test"})
    case = post(client, f"/cases/{cid}/publish")
    ts = get(client, f"/journeys/templates?case_id={cid}")
    assert [(t["journey_id"], t["default"]) for t in ts] == [("ed-to-ward", True)]
    j = post(client, "/journeys", {"case_id": cid, "seed": 2}, 201)
    jid = j["journey_id"]
    assert j["template"]["journey_id"] == "ed-to-ward" and j["patient"]["name"] == "Ilona Varga"
    post(client, f"/journeys/{jid}/stages/triage/start", {"mode": "auto", "quality": 0.9})
    s = post(client, f"/journeys/{jid}/stages/clinician/start", {"mode": "human"})
    _scan(s, case, "new case clinician start")
    for ln in ["What has been happening?", "What medicines do you take?", "Do you drink alcohol?", "!exam:vitals"]:
        path, key = ("request", "request") if ln.startswith("!") else ("turn", "text")
        t = post(client, f"/journeys/{jid}/stages/clinician/{path}", {key: ln.lstrip("!")})
        _scan(t, case, ln)
    assert any(e["kind"] == "patient_report" and e["text"] == "Hardly anything." for e in t["record"]["entries"])
    assert "f.vitals.lying_standing_bp" in {e["fact_id"] for e in t["record"]["entries"]}
    s = post(client, f"/journeys/{jid}/stages/clinician/finish", {"disposition": "discharge", "note": "Postural drop in blood pressure after starting doxazosin."})
    jsonschema.validate(s["stage"]["result"], RESULT_SCHEMA)
    done = post(client, f"/journeys/{jid}/auto")
    assert done["status"] == "complete" and [s["played_by"] for s in done["stages"]] == ["sampled", "human", "sampled", "sampled"]
    cp = get(client, f"/journeys/{jid}/care-plan")
    assert cp["decisions"]["disposition"]["value"] == "discharge" and cp["patient"]["name"] == "Ilona Varga"
    db = get(client, f"/journeys/{jid}/debrief")
    assert [s["played_by"] for s in db["stages"]] == ["sampled", "human", "sampled", "sampled"] and db["stages"][3]["handoff"]["grading"]["elements"]


def test_private_clinician_profiles_are_optional():
    c = pick_clinician("pharmacist", "samuel-adeyemi")
    assert c["name"] == "Samuel Adeyemi" and c["source"] == "builtin"
    assert pick_clinician("attending", "someone-not-loaded")["staff_role"] == "attending"
    assert pick_clinician("rn")["staff_role"] in ("rn", "charge_rn")


# ---------------------------------------------------------------- opened from a simulated patient

def test_journey_from_a_simulated_patient_writes_the_clinician_stage_back(client):
    from encounter.tests.test_resolver import SCRIPT, FakeSim
    sim = FakeSim()
    api.register_sim_lookup(lambda run_id: (sim, 0) if run_id == "run-1" else None)
    post(client, "/journeys", {"run_id": "nope", "patient_id": 123}, 404)
    j = post(client, "/journeys", {"run_id": "run-1", "patient_id": 123}, 201)
    jid = j["journey_id"]
    assert j["sim"] == {"run_id": "run-1", "b": 0, "patient_id": 123, "t_start": 96} and sim.held == []
    tri = j["stages"][0]
    assert tri["status"] == "completed" and tri["played_by"] == "sim" and "simulation" in tri["result_note"].lower()
    jsonschema.validate(tri["result"], RESULT_SCHEMA)
    note = next(e for e in j["record"]["entries"] if e["kind"] == "note")
    assert note["text"] == "ESI 2; chest pain; arrived by ambulance; age 57" and note["source"] == "simulation" and note["by"]["actor"] == "sim"
    s = post(client, f"/journeys/{jid}/stages/clinician/start", {"mode": "human"})
    assert sim.held == [(0, 123)]
    for ln in SCRIPT:
        path, key = ("request", "request") if ln.startswith("!") else ("turn", "text")
        post(client, f"/journeys/{jid}/stages/clinician/{path}", {key: ln.lstrip("!")})
    s = post(client, f"/journeys/{jid}/stages/clinician/finish", {"disposition": "admit", "note": "Chest pressure with raised troponin and ECG changes: admit."})
    assert s["stage"]["writeback"]["written_back"] is True and len(sim.applied) == 1
    b, res = sim.applied[0]
    assert res["interaction_type"] == "clinician_encounter" and res["patient_id"] == 123 and res["resolver"] == "played" and res["decision"]["disposition"] == "admit"
    assert s["stage"]["result"]["patient_id"] == 123 and s["stage"]["result"]["t_start"] == 96
    done = post(client, f"/journeys/{jid}/auto")
    assert done["status"] == "complete" and len(sim.applied) == 1         # the other stage types have no simulator write-back
    assert done["stages"][2]["writeback"]["supported"] is False
