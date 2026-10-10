"""Regression tests for the second independent QA pass (overnight/QA_REPORT_2.md: N1, N2, N7, N10, N11, D18 and D19 leftovers).
The questions are QA's own, word for word; the expected behaviour is what the report asked for."""
import json
import re

import pytest

from encounter import grader
from encounter import templates as tpl
from encounter import taxonomy as tx
from encounter.coverage import coverage_report
from encounter.describe import first_person
from encounter.disclosure import Engine, new_state
from encounter.matcher import correct_typos, match_facts
from encounter.patient import respond
from encounter.providers import OfflineProvider
from encounter.rubric import get_rubric
from encounter.store import CaseError
from encounter.validate import validate_case

from .conftest import SEED_IDS, seed_case
from .test_api import client  # noqa: F401  (the API test client fixture)

CHEST = "45M, crushing chest pain 1 hour, smoker."
MATEO = ("Mateo Alvarez is a 6 year old boy brought in by his mother with a barking cough and noisy breathing since last night. He had a runny nose for two days. "
         "Temperature 38.4, heart rate 128, oxygen saturation 95%. His immunisations are up to date. His mother is anxious because his older sister was hospitalised "
         "with asthma. He does not want to tell anyone that he swallowed a small toy piece yesterday.")
GLORIA = ("Gloria Petrakis, 74, retired teacher, presents with two days of black tarry stools and feeling lightheaded when she stands. She takes warfarin 5 mg daily for "
          "atrial fibrillation, metoprolol 25 mg twice a day, omeprazole 20 mg, and atorvastatin 40 mg. She is allergic to sulfa drugs (rash) and codeine (vomiting). "
          "She has been taking ibuprofen for a week for hip pain but has not told her doctor. Heart rate 108, blood pressure 96/58, respiratory rate 20, SpO2 97%. "
          "Hemoglobin 8.1, INR 4.6. She drinks two glasses of wine most evenings.")
SAMUEL = ("Samuel Okafor is a 52-year-old long-haul truck driver with sudden pain and swelling in his right calf since this morning after a 14 hour drive. He is allergic "
          "to penicillin. He takes lisinopril 10 mg daily and metformin 1000 mg twice daily. He is hiding that he has been coughing up blood since yesterday because he is "
          "afraid of losing his commercial licence. Heart rate 104, blood pressure 138/84, SpO2 93%.")
RUTH = ("Ruth Calloway is a 58-year-old bookkeeper who comes in with three days of dizziness and a pounding headache. She is hiding that she stopped "
        "taking her blood-pressure pills a month ago because they made her cough. She lives alone and is worried about missing work. Her blood pressure is 192/110.")
TERSE = "74 y/o F, SOB x 3 days, hx of COPD and CHF, on furosemide 40 mg daily, salbutamol inhaler, NKDA, ex-smoker, sats 88% on room air, RR 28"
PEDS = ("Aisha is a 4-year-old girl brought in by her father with a fever and pulling at her left ear for two days. She is allergic to amoxicillin (hives). "
        "Temp 39.1, HR 140. No vomiting or rash. She attends daycare.")
MULTI = ("Mr. Harold Finch, a 68-year-old retired plumber, presents with three hours of palpitations and shortness of breath. History of hypertension, type 2 diabetes "
         "and a heart attack in 2019. Medications: aspirin 81 mg daily, bisoprolol 5 mg daily, ramipril 10 mg daily, metformin 500 mg twice daily, atorvastatin 80 mg at night. "
         "Allergic to penicillin (anaphylaxis) and shellfish. BP 148/92, HR 142, SpO2 94%, potassium 3.1, troponin 22 ng/L, creatinine 1.4 mg/dL. "
         "He drinks a bottle of wine most nights but minimises it. Lives with his wife. Non-smoker.")
NARRATIVE = ("Elena Markovic is a 34-year-old nurse who comes in with a severe headache that started suddenly this morning while she was lifting a patient. She describes it "
             "as the worst headache of her life. She has vomited twice and the light hurts her eyes. She has a history of migraines but says this feels different. She takes "
             "the oral contraceptive pill and occasionally sumatriptan. She has no known drug allergies. Her mother died of a brain aneurysm at 52. She smokes ten cigarettes "
             "a day and does not drink alcohol. She is worried about who will pick up her children from school. Blood pressure 168/98, heart rate 88, temperature 37.1.")
FIRST = ("I am a 29 year old teacher. I have had a sore throat and a fever for three days. I take the pill. I am allergic to penicillin. I smoke about five cigarettes a day. "
         "I haven't told anyone that I have been vomiting blood since last night.")
ALL = {"chest": CHEST, "mateo": MATEO, "gloria": GLORIA, "samuel": SAMUEL, "ruth": RUTH, "terse": TERSE, "peds": PEDS, "multi": MULTI, "narrative": NARRATIVE, "first": FIRST}
_THIRD = re.compile(r"\b(she|he|his|him|himself|herself)\b", re.I)


def draft(text):
    out = tpl.from_description(text)
    return out["case"], out


def play(case, known=None):
    eng, st = Engine(case), new_state()
    eng.start(st, known_fact_ids=known)
    return eng, st, (lambda t: respond(case, eng, st, t, OfflineProvider()))


def by_id(case):
    return {f["fact_id"]: f for f in case["facts"]}


def of(case, category):
    return [f for f in case["facts"] if f["category"] == category]


# ------------------------------------------------------------------ N1 + N11: the description path

@pytest.mark.parametrize("key", sorted(ALL))
def test_every_description_gives_a_first_person_patient_with_a_complaint(key):
    c, out = draft(ALL[key])
    cc = of(c, "chief_complaint")
    assert len(cc) == 1 and cc[0]["disclosure"]["rule"] == "volunteered", "always a chief-complaint fact"
    assert re.match(r"^(I|I'm|I've|My)\b", cc[0]["patient_answer"]), cc[0]["patient_answer"]
    assert c["review"]["source_description"] == ALL[key]
    assert c["default_negatives"] is False                       # what the text did not say is unknown, never "no"
    for f in c["facts"]:
        a = f.get("patient_answer") or ""
        if f["disclosure"]["rule"] in ("volunteered", "if_asked", "after_rapport", "denied_until_confronted"):
            assert a.strip(), f["fact_id"]
            assert not a.startswith("It's the "), a              # never "It's the smoker."
            if f["category"] != "family":
                assert not _THIRD.search(a), (f["fact_id"], a)   # no author's third person in the patient's mouth
    rep = validate_case(c)
    assert rep["ok"], rep["errors"] + rep["consistency"]
    # completeness guarantee: every sentence is in the case or named under "missing"
    cov = coverage_report(c)
    listed = " ".join(out["missing"])
    for u in cov["uncovered"]:
        assert u["text"] in listed.replace('\\"', '"') or json.dumps(u["text"]) in listed, u
    assert c["review"]["coverage"]["sentences"] == cov["sentences"]


def test_shorthand_age_sex_and_smoker():
    c, out = draft(CHEST)
    assert (c["profile"]["age"], c["profile"]["gender"]) == (45, "male") and c["title"] == "Crushing chest pain in a 45-year-old man"
    f = by_id(c)
    assert f["f.chief_complaint.crushing_chest_pain"]["patient_answer"] == "I've had crushing chest pain for an hour."
    assert f["f.social.smoking"]["patient_answer"] == "Yes, I smoke." and f["f.social.smoking"]["topics"] == ["smoking"]
    eng, st, say = play(c)
    assert say("What brings you in?")["reply"] == "I've had crushing chest pain for an hour."
    r = say("Do you have chest pain?")
    assert not r["reply"].startswith("No") and "chest pain" in r["reply"]
    assert say("Do you smoke?")["reply"] == "Yes, I smoke."
    c2, _ = draft(TERSE)
    assert (c2["profile"]["age"], c2["profile"]["gender"]) == (74, "female")
    assert of(c2, "chief_complaint")[0]["patient_answer"] == "I've had shortness of breath for 3 days."      # shorthand never reaches the patient's mouth
    assert {f["statement"] for f in of(c2, "pmh")} == {"COPD", "CHF"} and by_id(c2)["f.pmh.chf"]["patient_answer"] == "I have heart failure."
    assert "furosemide 40 mg daily" in of(c2, "medications")[0]["statement"] and "salbutamol inhaler" in of(c2, "medications")[0]["statement"]
    assert by_id(c2)["f.allergies.nkda"]["polarity"] == "negative" and by_id(c2)["f.social.smoking"]["patient_answer"].startswith("I used to smoke")
    assert by_id(c2)["f.vitals.spo2"]["value"] == 88 and by_id(c2)["f.vitals.respiratory_rate"]["value"] == 28


def test_child_title_voice_companion_and_concealed_toy():
    c, out = draft(MATEO)
    assert c["title"] == "Barking cough and noisy breathing in a 6-year-old boy" and "man" not in c["title"] and "Shortness of breath" not in c["title"]
    assert c["profile"]["gender"] == "male" and c["profile"]["age"] == 6
    f = by_id(c)
    assert f["f.social.accompanied_by"]["patient_answer"] == "My mom is here with me."
    said = {x["statement"]: x.get("patient_answer") for x in c["facts"]}
    assert said["His immunisations are up to date"] == "My mom says my immunisations are up to date."      # parent-reported
    assert said["He had a runny nose for two days"] == "I had a runny nose for two days."
    assert "my older sister was hospitalised with asthma" in of(c, "family")[0]["patient_answer"]
    assert {v["label"] for v in of(c, "vitals")} == {"Temperature", "Heart rate", "Oxygen saturation"}
    toy = of(c, "concealed")[0]
    assert {"swallow", "toy", "ate", "put in your mouth"} <= set(toy["topics"]) and toy["cover_answer"] and toy["patient_answer"].endswith("I swallowed a small toy piece yesterday.")
    eng, st, say = play(c)
    r = say("Do you have a cough?")
    assert not r["reply"].startswith("No") and "barking cough" in r["reply"]
    r = say("Did you swallow anything?")
    assert r["reply"] == toy["cover_answer"] and r["event"]["result"] == "withheld"
    assert say("Is your mum here with you?")["reply"] == "My mom is here with me."
    for line in ("That sounds scary. I'm not here to judge.", "Many kids do this, it is very common.", "I understand, take your time."):
        last = say(line)
    assert "f.concealed.swallowed" in eng.disclosed(st)           # opens up once rapport is there (he was asked before)
    assert "swallowed a small toy piece" in say("Did you swallow anything?")["reply"]


def test_every_medicine_allergy_vital_and_lab_is_kept():
    c, out = draft(GLORIA)
    meds = of(c, "medications")[0]
    for item in ("warfarin 5 mg daily for atrial fibrillation", "metoprolol 25 mg twice a day", "omeprazole 20 mg", "atorvastatin 40 mg"):
        assert item in meds["statement"] and item in meds["patient_answer"]
    al = of(c, "allergies")[0]
    assert "sulfa drugs (rash)" in al["statement"] and "codeine (vomiting)" in al["statement"] and al["patient_answer"].startswith("I'm allergic to sulfa drugs")
    labs = {f["label"]: f for f in of(c, "lab")}
    assert labs["Hemoglobin"]["value"] == 8.1 and labs["INR"]["value"] == 4.6
    assert labs["Hemoglobin"]["disclosure"] == {"rule": "on_request", "request": "order:cbc"} and labs["INR"]["disclosure"]["request"] == "order:coags"
    arts = {a["artifact_id"]: a for a in c["chart"]["artifacts"]}
    assert arts["art.lab_cbc"]["content"][0]["value"] == 8.1 and arts["art.lab_coags"]["linked_fact_ids"] == [labs["INR"]["fact_id"]]
    assert {f["label"]: f["value"] for f in of(c, "vitals")} == {"Heart rate": 108, "Blood pressure": "96/58", "Respiratory rate": 20, "Oxygen saturation": 97}
    assert by_id(c)["f.social.alcohol"]["patient_answer"] == "I drink two glasses of wine most evenings."
    assert by_id(c)["f.pmh.atrial_fibrillation"]["patient_answer"] == "I have atrial fibrillation."
    hidden = of(c, "concealed")[0]
    assert "ibuprofen" in hidden["statement"].lower() and "ibuprofen" in hidden["topics"] and "painkillers" in hidden["topics"]
    assert not [m for m in out["missing"] if m.startswith("not ")], out["missing"]          # nothing dropped, nothing left to list
    eng, st, say = play(c)
    assert say("What brings you in?")["reply"] == "I've had black tarry stools for two days. I feel lightheaded when I stand."
    r = say("Do you take omeprazole or atorvastatin?")
    assert "omeprazole 20 mg" in r["reply"] and "atorvastatin 40 mg" in r["reply"] and not r["reply"].startswith("No")
    r = say("Have you been taking any painkillers like ibuprofen?")
    assert r["event"]["result"] == "withheld" and r["reply"] == hidden["cover_answer"]      # the concealed fact answers, per its rule
    r = eng.process_request(st, "order:cbc")
    assert labs["Hemoglobin"]["fact_id"] in r["released"]


def test_first_person_conversion_examples():
    assert first_person("feeling lightheaded when she stands") == "I feel lightheaded when I stand."
    assert first_person("she stopped taking her blood-pressure pills a month ago because they made her cough") == \
        "I stopped taking my blood-pressure pills a month ago because they made me cough."
    assert first_person("he has been coughing up blood since yesterday") == "I've been coughing up blood since yesterday."
    assert first_person("black tarry stools") == "I've had black tarry stools."
    assert first_person("sudden pain and swelling in his right calf") == "I've had sudden pain and swelling in my right calf."
    assert first_person("She takes warfarin and drinks wine") == "I take warfarin and drink wine."
    assert first_person("Ruth lives alone", "Ruth Calloway") == "I live alone."


def test_longer_descriptions_keep_history_social_and_family():
    c, out = draft(MULTI)
    assert c["profile"]["name"] == "Harold Finch" and by_id(c)["f.social.smoking"]["patient_answer"] == "No, I don't smoke."
    assert [f["statement"] for f in of(c, "pmh")] == ["Hypertension", "Type 2 diabetes", "A heart attack in 2019"]
    assert of(c, "medications")[0]["statement"].count(";") == 4 and len({f["label"] for f in of(c, "lab")}) == 3
    assert "penicillin (anaphylaxis)" in of(c, "allergies")[0]["statement"] and "shellfish" in of(c, "allergies")[0]["statement"]
    assert of(c, "concealed")[0]["patient_answer"] == "All right. I drink a bottle of wine most nights."           # "... but minimises it"
    n, _ = draft(NARRATIVE)
    f = by_id(n)
    assert f["f.social.smoking"]["patient_answer"] == "I smoke ten cigarettes a day." and f["f.social.alcohol"]["patient_answer"] == "No, I don't drink."
    assert of(n, "family")[0]["patient_answer"] == "My mother died of a brain aneurysm at 52."
    assert "sumatriptan" in of(n, "medications")[0]["statement"] and f["f.hpi.onset"]["patient_answer"].startswith("It started suddenly this morning while I was lifting")
    p, _ = draft(PEDS)
    assert p["title"].endswith("in a 4-year-old girl") and p["profile"]["name"] == "Aisha"
    assert of(p, "allergies")[0]["patient_answer"] == "My dad says I'm allergic to amoxicillin, it gives me hives."
    assert of(p, "ros")[0]["patient_answer"] == "No, no vomiting or rash." and of(p, "ros")[0]["polarity"] == "negative"
    fp, _ = draft(FIRST)
    assert of(fp, "chief_complaint")[0]["patient_answer"] == "I've had a sore throat and a fever for three days."
    assert of(fp, "concealed")[0]["patient_answer"] == "All right. I've been vomiting blood since last night."


def test_coverage_check_names_what_was_dropped():
    text = "Lena Brandt, 50, presents with wrist pain for two days. She keeps bees and was stung on the forearm at the weekend, zxqv 77 units."
    c, out = draft(text)
    assert not coverage_report(c)["uncovered"] or any("zxqv" in m or "stung" in m for m in out["missing"])
    c["facts"] = [f for f in c["facts"] if f["category"] == "chief_complaint"]         # an author (or a bug) drops everything else
    cov = coverage_report(c)
    assert cov["uncovered"] and any("bees" in u["missing_words"] or "stung" in u["missing_words"] for u in cov["uncovered"])
    w = [x for x in validate_case(c)["warnings"] if "description coverage incomplete" in x["message"]]
    assert w and w[0]["level"] == "attention"
    for cid in SEED_IDS:                                                                # seed cases have no source description: no such warning
        assert not any("coverage" in x["message"] for x in validate_case(seed_case(cid))["warnings"])


# ------------------------------------------------------------------ N1 safety net: the default "no"

def test_default_no_never_contradicts_the_case_or_its_source_text(mini_case):
    for cid in SEED_IDS:                                   # QA: "Do you have pain anywhere?" -> "No, nothing like that." in all three
        eng, st, say = play(seed_case(cid))
        r = say("Do you have pain anywhere?")
        assert r["event"]["result"] == "disclosed" and not r["reply"].startswith("No, nothing"), (cid, r["reply"])
    # a fact that carries no topic at all is still found through its own wording, whatever its category
    mini_case["facts"].append({"fact_id": "f.hpi.x1", "category": "hpi", "statement": "Was stung by a wasp on the forearm yesterday", "patient_knows": True,
                               "patient_answer": "A wasp got me on the arm yesterday.", "disclosure": {"rule": "if_asked"}})
    eng, st, say = play(mini_case)
    r = say("Were you stung by anything?")
    assert r["reply"] == "A wasp got me on the arm yesterday." and r["event"]["matched_intents"][0]["via"] == "the case's own wording"
    # the description mentions it but no fact holds it: non-committal, never "no"
    c, _ = draft(SAMUEL)
    c["default_negatives"] = True
    c["facts"] = [f for f in c["facts"] if f["category"] != "allergies"]
    eng, st, say = play(c)
    r = say("Are you allergic to penicillin?")
    assert r["event"]["result"] == "answered_noncommittal" and not r["reply"].startswith("No")
    r = say("Have you ever had kidney stones?")
    assert r["event"]["result"] == "answered_negative_by_default"                      # nothing in the case or its text: the plain "no" still works


def test_what_brings_you_in_is_always_answerable(mini_case):
    c, _ = draft(CHEST)
    c["facts"] = [f for f in c["facts"] if f["category"] != "chief_complaint"]
    eng, st, say = play(c)
    r = say("What brings you in?")
    assert r["reply"] == "I came in because of crushing chest pain." and r["event"]["result"] == "answered_from_case_summary"
    bare = {**mini_case, "title": "Untitled case", "prebrief": "", "facts": [f for f in mini_case["facts"] if f["category"] != "chief_complaint"]}
    eng, st, say = play(bare)
    r = say("What brings you in today?")
    assert "not sure" not in r["reply"].lower() and r["reply"].startswith("I ")
    assert seed_case(SEED_IDS[0]).get("default_negatives", True) is True                # seed cases keep the default "no"


# ------------------------------------------------------------------ N2: concealed items from descriptions

def test_concealed_haemoptysis_cover_then_disclosure_and_feedback(manager):
    c, out = draft(SAMUEL)
    h = of(c, "concealed")[0]
    assert {"blood", "coughing up blood", "cough", "spit", "sputum"} <= set(h["topics"])
    assert h["cover_answer"] and h["disclosure"] == {"rule": "after_rapport", "rapport_needed": 3}
    assert h["patient_answer"] == "All right. I've been coughing up blood since yesterday. I didn't say because I'm afraid of losing my commercial licence."
    eid = manager.start(c, preview=True)["encounter_id"]
    say = lambda t: manager.turn(eid, t)        # noqa: E731
    assert say("What brings you in?")["reply"].startswith("I've had sudden pain and swelling in my right calf")
    r = say("Have you been coughing up any blood?")
    assert r["reply"] == h["cover_answer"] and "not coughing" not in r["reply"]                        # QA saw "No, I'm not coughing."
    assert say("Any blood when you cough?")["reply"] == h["cover_answer"]
    fb = manager.finish(eid, "admit", [], "calf pain")["feedback"]
    missed = next(m for m in fb["missed"] if m["fact_id"] == h["fact_id"])
    assert missed["asked"] is True and missed["status"] == "asked_not_disclosed" and "you asked" in missed["how_to_reach"]
    # a second learner builds rapport first
    eid = manager.start(c, preview=True)["encounter_id"]
    say = lambda t: manager.turn(eid, t)        # noqa: E731
    r = say("Is there something you are afraid to tell me?")
    assert r["reply"] == "I'd rather not get into that right now."                                    # QA saw "Sorry, I don't follow."
    for line in ("I can see this is worrying you. That sounds frightening. Whatever you tell me is only used to look after you.",
                 "Thank you for telling me. I understand how hard this is.", "That sounds frightening, I'm sorry."):
        r = say(line)
    for q in ("Have you been coughing up blood?", "Have you coughed up any blood since yesterday?", "Any blood when you cough?"):
        assert "coughing up blood since yesterday" in say(q)["reply"], q
    assert h["fact_id"] in [f["fact_id"] for f in manager.finish(eid, "admit", [], "")["feedback"]["elicited"]]


def test_general_probe_counts_as_asking_once_rapport_is_there():
    c, _ = draft(SAMUEL)
    eng, st, say = play(c)
    for line in ("Hello, my name is Dr. Lee, I'm one of the doctors.", "That sounds frightening, I'm sorry.", "I understand how hard this is."):
        say(line)
    assert st["rapport"] >= 3
    r = say("Is there anything worrying you that you haven't mentioned?")
    assert r["event"]["disclosed_fact_ids"] == [of(c, "concealed")[0]["fact_id"]] and "coughing up blood" in r["reply"]
    # a case with nothing held back treats the same question as a question about worries, never as off-topic
    c2, _ = draft(CHEST)
    eng, st, say = play(c2)
    assert say("Is there anything worrying you that you haven't mentioned?")["event"]["result"] == "answered_from_persona"


def test_concealed_fact_wins_over_a_neighbouring_symptom_fact():
    c, _ = draft(SAMUEL)
    c["facts"].append({"fact_id": "f.ros.cough", "category": "ros", "statement": "No cough", "patient_knows": True, "patient_answer": "No, I'm not coughing.",
                       "topics": ["cough"], "polarity": "negative", "disclosure": {"rule": "if_asked"}})
    eng, st, say = play(c)
    r = say("Have you been coughing up any blood?")
    assert r["reply"] == of(c, "concealed")[0]["cover_answer"] and "f.ros.cough" not in r["event"]["disclosed_fact_ids"]


# ------------------------------------------------------------------ D18 leftovers: lifecycle

def test_no_chief_complaint_cannot_be_approved_or_published(store):
    c, out = draft("An anxious 30 year old man.")
    saved = store.create(c)
    rep = store.validate(saved["case_id"])
    assert not rep["ok"] and any("no chief complaint" in e["message"] for e in rep["errors"])
    with pytest.raises(CaseError) as e:
        store.approve(saved["case_id"], acknowledge_warnings=True)
    assert e.value.status == 422


def test_approve_refuses_without_explicit_acknowledgement(client):
    r = client.post("/api/cases", json={"from_description": SAMUEL})
    cid = r.json()["case_id"]
    assert r.status_code == 201 and r.json()["validation"]["ok"] and r.json()["validation"]["needs_acknowledgement"]
    for body in (None, {}, {"reviewer": "Prof. X"}, {"acknowledge_warnings": False}, {"acknowledge_warnings": "yes"}):
        r = client.post(f"/api/cases/{cid}/approve", json=body) if body is not None else client.post(f"/api/cases/{cid}/approve")
        assert r.status_code == 409, body
        d = r.json()["detail"]
        assert d["needs_acknowledgement"] is True and len(d["warnings"]) >= 2 and all(w["level"] == "attention" for w in d["warnings"])
    assert client.get(f"/api/cases/{cid}").json()["status"] == "draft"
    assert client.post(f"/api/cases/{cid}/publish").status_code == 409
    r = client.post(f"/api/cases/{cid}/approve", json={"acknowledge_warnings": True, "reviewer": "Prof. X"})
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["review"]["warnings_acknowledged"] is True
    assert client.post(f"/api/cases/{cid}/publish").json()["status"] == "published"
    e = client.post("/api/encounters", json={"case_id": cid}).json()
    t = client.post(f"/api/encounters/{e['encounter_id']}/turn", json={"text": "What brings you in?"}).json()
    assert "my right calf" in t["reply"]


# ------------------------------------------------------------------ N7: matcher precision

@pytest.mark.parametrize("cid", SEED_IDS)
def test_off_topic_questions_match_and_disclose_nothing(cid):
    case = seed_case(cid)
    for q in ("Who do you think will win the election?", "Who will win the world cup?", "What do you think about politics?", "Did you watch the game last night?",
              "What is the capital of France?"):
        assert match_facts(q, case["facts"]).fact_ids == [], q
        eng, st, say = play(case)
        r = say(q)
        assert not r["event"]["disclosed_fact_ids"] and r["event"]["result"] == "deflected_off_topic", (q, r["reply"])
    eng, st, say = play(case)
    say("Who do you think will win the election?")
    assert not say("Do you drink alcohol?")["reply"].startswith("Like I said")           # first ask: never "Like I said"
    assert say("Do you drink alcohol?")["reply"].startswith("Like I said")               # second ask in the same encounter: fine


def test_win_is_not_wine_and_common_words_trigger_no_topic():
    assert tx.stem("wine") == "wine" and tx.stem("wines") == "wine" and tx.stem("win") == "win" and tx.stem("note") != tx.stem("not")
    alcohol = [{"fact_id": "f.social.alcohol", "category": "social", "topics": ["alcohol"]}]
    for q in ("Who will win?", "Who do you think will win?", "What will you think?"):
        assert match_facts(q, alcohol).fact_ids == []
    assert match_facts("Do you drink wine?", alcohol).fact_ids == ["f.social.alcohol"]


def test_pills_medications_progression_thread_and_typos():
    case = seed_case("abdominal-pain-grad-student")
    eng, st, say = play(case)
    r = say("Which pills are you on regularly?")
    assert r["event"]["disclosed_fact_ids"] == ["f.medications.current"] and "Like I said" not in r["reply"]      # QA: the bowel answer was glued on
    r = say("Has it been getting worse since it began?")
    assert "f.hpi.aggravating" not in r["event"]["disclosed_fact_ids"] and r["event"]["result"] in ("disclosed", "repeat", "answered_noncommittal")
    assert correct_typos("wat abuot ur brething") == "what about your breathing"
    c, _ = draft(SAMUEL)
    eng, st, say = play(c)
    say("What brings you in?")
    r = say("Tell me more about the leg.")
    assert r["event"]["result"] == "disclosed" and r["reply"] != "I think that's all, really."
    r = say("wat abuot ur brething")
    assert r["reply"] != "Mm-hm." and r["event"]["result"] in ("answered_noncommittal", "not_specified")
    eng, st, say = play(seed_case("breathless-retired-driver"))
    assert "breath" in say("wat abuot ur brething")["reply"]


def test_like_i_said_only_for_what_this_listener_was_told():
    case = seed_case("chest-pain-line-cook")
    eng, st, say = play(case, known=["f.social.smoking", "f.chief_complaint.chest_pain"])      # known from an earlier stage of a journey
    r = say("Do you smoke?")
    assert not r["reply"].startswith("Like I said") and r["reply"] == by_id(case)["f.social.smoking"]["patient_answer"]
    assert say("Do you smoke?")["reply"].startswith("Like I said")


# ------------------------------------------------------------------ N10 + D19: grader

def test_confidentiality_reassurance_is_rapport_not_judgment(manager):
    eid = manager.start(seed_case("chest-pain-line-cook"))["encounter_id"]
    t = manager.turn(eid, "I can see this is worrying you. That sounds frightening. Whatever you tell me is only used to look after you.")
    assert t["rapport"] >= 2
    fb = manager.finish(eid, "undecided", [], "")["feedback"]
    rap = next(d for d in fb["rubric"]["domains"] if "rapport" in (d["key"] + d["name"]).lower())
    assert rap["score"] >= 3 and "judgmental" not in rap["rationale"]
    assert fb["communication"]["judgmental_language"] == [] and fb["communication"]["normalising_statements"]
    assert all("judgmental" not in d["rationale"] for d in fb["rubric"]["domains"])
    for phrase in ("Whatever you tell me is only used to look after you", "I'm not here to judge", "Anything you tell me stays confidential"):
        from encounter.matcher import detect_cues
        cues = detect_cues(phrase)
        assert "judgmental" not in cues and "normalising" in cues, phrase
    assert "judgmental" in detect_cues("Whatever you say. Just answer the question.")


def test_a_turn_is_never_both_a_strength_and_a_score_of_one(manager):
    eid = manager.start(seed_case("chest-pain-line-cook"))["encounter_id"]
    manager.turn(eid, "Why didn't you come in sooner? That's irresponsible.")
    manager.turn(eid, "You should have known better. Stop lying to me.")
    fb = manager.finish(eid, "undecided", [], "")["feedback"]
    rap = next(d for d in fb["rubric"]["domains"] if "rapport" in (d["key"] + d["name"]).lower())
    assert rap["score"] == 1 and not any("Acknowledged the patient's feelings" in s for s in fb["strengths"])


def test_acceptable_disposition_is_not_reported_as_differing(mini_case):
    mini_case["faculty_truth"] = {**mini_case.get("faculty_truth", {}), "expected_disposition": "discharge", "acceptable_dispositions": ["admit", "discharge"]}
    eng, st, say = play(mini_case)
    say("What brings you in?")
    fb = grader.grade(mini_case, st, get_rubric("default"), {"disposition": "admit", "orders": [], "summary": "admit for observation"})
    text = json.dumps(fb)
    assert "differs from the case's expected disposition" not in text and "is one of the dispositions this case accepts" in text
    assert fb["quality_parts"]["decision_score"] == 1.0
    mini_case["faculty_truth"]["acceptable_dispositions"] = ["discharge"]
    fb = grader.grade(mini_case, st, get_rubric("default"), {"disposition": "admit", "orders": [], "summary": "admit"})
    assert "differs from the case's expected disposition" in json.dumps(fb)
