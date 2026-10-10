"""Self-check for the description reader (orchestrator's follow-up to QA round 2): 25 descriptions in varied sentence shapes
(encounter/tests/descriptions_batch.py) plus the Elena Park description that exposed the bugs. Every drafted title, statement,
patient answer, cover answer and fact id must be free of cut marks; the six reported behaviours are pinned below."""
import re

import pytest

from encounter import templates as tpl
from encounter.describe import text_problems, wording_problems
from encounter.disclosure import Engine, new_state
from encounter.patient import respond
from encounter.providers import OfflineProvider
from encounter.validate import validate_case

from .descriptions_batch import BATCH
from .test_round3 import ALL

PARK = BATCH["embedded_fever"]
_DANGLING = re.compile(r"\b(?:a|an|and|of|with|the|or|but)\s*[.,;!?]|\b(?:a|an|and|of|the|or|but)$|,\s*,|\b(?:and|or|but)\s+(?:and|or|but)\b|\bmy a\b|\s{2,}", re.I)
_THIRD = re.compile(r"\b(?:she|he|her|his|him|hers|herself|himself)\b", re.I)
_RELATIVES = re.compile(r"\b(?:mother|father|mom|mum|dad|parents?|wife|husband|partner|daughter|son|sister|brother|aunt|uncle|neighbour|neighbor|friend|housemates?)\b", re.I)


def play(case):
    eng, st = Engine(case), new_state()
    eng.start(st)
    return eng, st, (lambda t: respond(case, eng, st, t, OfflineProvider()))


def of(case, category):
    return [f for f in case["facts"] if f["category"] == category]


@pytest.mark.parametrize("key", sorted(BATCH) + ["r3_" + k for k in sorted(ALL)])
def test_generated_wording_has_no_cut_marks(key):
    text = BATCH[key] if key in BATCH else ALL[key[3:]]
    c = tpl.from_description(text)["case"]
    assert wording_problems(c) == []                                    # the reader's own check
    # ... and an independent, simpler check written from the bug list
    title = c["title"]
    assert not _DANGLING.search(title) and not re.search(r"\b(?:a|an|and|of|with|the|in)$", title.split(" in a")[0].split(" in an")[0].strip(), re.I), title
    assert len(title) <= 110, title
    parent_voice = bool(c.get("answers_by"))
    assert of(c, "chief_complaint"), "every one of these has a clinical clause"
    for f in c["facts"]:
        fid = f["fact_id"]
        assert not re.search(r"(?:^|[._])(?:a|an|and|of|the|or|with)$", fid.split(".")[-1]), fid          # symptom_a, *_and
        st = f["statement"].strip()
        assert len(st) >= 3 and re.search(r"[A-Za-z]{3}", st) and not re.search(r"\b(?:a|an|and|of|with|the|or)$", st, re.I), (fid, st)
        for k in ("patient_answer", "cover_answer"):
            a = f.get(k)
            if not a:
                continue
            assert not _DANGLING.search(a.replace("...", "")), (fid, a)
            assert a[0].isupper() and a.rstrip()[-1] in ".!?", (fid, a)
            assert not re.search(r"\bI (?:is|has|does|takes|drinks|smokes)\b|\bI've had (?:the|this|he|she|was|is|has)\b|\bI have was\b|\bI'm an? (?:was|is|presents|and)\b", a), (fid, a)
            if k == "patient_answer" and not parent_voice and f["category"] != "family" and not _RELATIVES.search(a):
                assert not _THIRD.search(a), (fid, a)                   # she/he/her/his/him where I/me/my is meant
    rep = validate_case(c)
    assert rep["ok"], rep["errors"] + [x for x in rep["consistency"] if x["level"] == "contradiction"]


def test_the_check_itself_catches_the_reported_bugs():
    for bad in ("I've had confusion and a for two days.", "Yes, I've had a.", "I have type 2 diabetes and.", "I'm allergic to sulfa drugs, and which give my a rash."):
        assert text_problems(bad), bad
    assert text_problems("Confusion and a in a 67-year-old woman", "title")
    for good in ("I've had confusion and a fever for two days.", "My daughter is here with me.", "No... not really. Nothing worth mentioning.", "I take what I'm supposed to."):
        assert not text_problems(good), good


def test_park_fever_is_a_symptom_and_a_vital_and_nothing_dangles():
    c = tpl.from_description(PARK)["case"]
    by = {f["fact_id"]: f for f in c["facts"]}
    assert c["title"] == "Confusion and a fever in a 67-year-old woman"
    assert of(c, "chief_complaint")[0]["patient_answer"] == "I've had confusion and a fever for two days."
    assert by["f.hpi.symptom_a_fever"]["patient_answer"] == "Yes, I've had a fever." and "f.hpi.symptom_a" not in by
    assert by["f.vitals.temperature"]["value"] == 38.9 and by["f.vitals.heart_rate"]["value"] == 108 and by["f.vitals.blood_pressure"]["value"] == "104/62"
    assert [f["patient_answer"] for f in of(c, "pmh")] == ["I have type 2 diabetes."]
    assert of(c, "allergies")[0]["patient_answer"] == "I'm allergic to sulfa drugs. They give me a rash."
    assert "metformin 500 mg twice daily" in of(c, "medications")[0]["patient_answer"] and "lisinopril 10 mg every morning" in of(c, "medications")[0]["patient_answer"]
    assert not c["review"]["coverage"]["uncovered"] and c["default_negatives"] is True


def test_park_interview_defaults_cover_answers_and_threshold():
    c = tpl.from_description(PARK)["case"]
    hidden = of(c, "concealed")[0]
    eng, st, say = play(c)
    r = say("Hello, my name is Dr. Lee. Is it okay if I ask you some questions?")
    assert r["event"]["result"] == "no_fact_requested" and "what's wrong with me" not in r["reply"]
    say("What brings you in today?")
    assert st["rapport"] >= 3                                             # introduction + agenda + open question: no empathy yet
    r = say("Do you smoke?")
    assert r["reply"].startswith("No") and r["event"]["result"] == "answered_negative_by_default"          # a person knows whether they smoke
    r = say("Do you have chest pain?")
    assert r["reply"].startswith("No") and r["event"]["result"] == "answered_negative_by_default"
    r = say("Any burning when you pee?")
    assert r["reply"] == hidden["cover_answer"] and r["event"]["result"] == "withheld"                     # direct ask before real rapport: cover answer
    r = say("Do you have any pain anywhere?")
    assert r["reply"] == hidden["cover_answer"] and "not sure" not in r["reply"]                           # the only pain is the hidden one: cover, not "not sure"
    r = say("Nothing you say will be judged. Is there anything you haven't mentioned?")
    assert r["event"]["disclosed_fact_ids"] == [hidden["fact_id"]] and "burning when I urinate for a week" in r["reply"]
    for q in ("Have you had a fever?", "Are you confused?", "Do you take metformin?", "Do you drink alcohol?", "Do you have diabetes?"):
        assert not say(q)["reply"].startswith("No"), q                    # the default "no" never contradicts the text


def test_incomplete_coverage_gives_a_soft_negative_not_a_flat_no_or_not_sure():
    c = tpl.from_description(BATCH["passive"])["case"]
    assert c["review"]["coverage"]["unplaced"] and c["default_negatives"] is False and c["soft_negatives"] is True
    eng, st, say = play(c)
    r = say("Do you smoke?")
    assert r["event"]["result"] == "answered_soft_negative_by_default" and r["reply"] in ("Not that I've noticed.", "Not that I know of.", "I don't think so.")
    assert not r["event"]["disclosed_fact_ids"]
    r = say("Were you brought in by ambulance?")                          # in the text, not in a fact: non-committal, not a negative of any kind
    assert r["event"]["result"] in ("answered_noncommittal", "disclosed", "repeat") and not r["reply"].startswith(("No", "Not"))


def test_values_embedded_mid_clause_and_relative_clauses():
    c = tpl.from_description(BATCH["pain_score"])["case"]
    by = {f["fact_id"]: f for f in c["facts"]}
    assert by["f.hpi.severity"]["patient_answer"] == "It's about an 8 out of 10." and by["f.vitals.blood_pressure"]["value"] == "150/90" and by["f.vitals.heart_rate"]["value"] == 112
    assert by["f.medications.none"]["patient_answer"] == "No, I don't take any regular medicines."
    c = tpl.from_description(BATCH["which_clause"])["case"]
    assert c["title"] == "Cut on her left hand in a 38-year-old woman"
    said = [f["patient_answer"] for f in of(c, "hpi")]
    assert "I got it from a knife two hours ago." in said and "It is still bleeding." in said
    assert of(c, "allergies")[0]["patient_answer"] == "I'm allergic to latex. It gives me hives."
    c = tpl.from_description(BATCH["relative_who"])["case"]
    assert c["profile"]["age"] == 72 and "It gets worse when I climb stairs." in [f["patient_answer"] for f in of(c, "hpi")]
    assert "GTN spray" in of(c, "medications")[0]["statement"]
    c = tpl.from_description(BATCH["and_list"])["case"]
    assert [f["statement"] for f in of(c, "pmh")] == ["Diabetes", "High blood pressure", "Arthritis"]
    assert "Yes, I've had left arm." not in [f.get("patient_answer") for f in c["facts"]]


def test_infant_and_toddler_are_answered_by_the_adult_with_them():
    c = tpl.from_description(BATCH["infant"])["case"]
    assert c["title"] == "Fever and poor feeding in an 8-month-old girl" and c["answers_by"] == "accompanying adult"
    assert of(c, "chief_complaint")[0]["patient_answer"] == "She's had a fever and poor feeding for a day."
    assert {f["fact_id"]: f for f in c["facts"]}["f.social.accompanied_by"]["patient_answer"] == "We're her parents."
    t = tpl.from_description(BATCH["toddler_parent"])["case"]
    assert t["profile"]["name"] == "Leo" and t["profile"]["age"] == 2 and t["title"].endswith("in a 2-year-old boy")
    assert of(t, "chief_complaint")[0]["patient_answer"].startswith("He's had diarrhoea and vomiting since yesterday.")
    assert all(not re.search(r"\b(?:I|my|me)\b", f["patient_answer"]) for f in t["facts"] if f.get("patient_answer_auto") and f["fact_id"] != "f.social.accompanied_by")


# ------------------------------------------------------------------ second blind description (orchestrator): concealment phrasings, mechanism, location

JAMES = ("James Whitfield, 34, a bike courier, came in after falling off his bicycle an hour ago. He has pain in his right wrist rated 7/10 and a graze on his knee. "
         "No medical problems and no regular medications. He is allergic to penicillin (hives). He hit his head and briefly blacked out but is not mentioning it because "
         "he wants to get back to work. BP 128/78, pulse 92. He smokes about five cigarettes a day and does not drink.")
_BASE = "Tom Reed is a 40-year-old builder who presents with a sore shoulder for two days. {} He lives alone."
CONCEALMENT_PHRASINGS = [
    "He hit his head and blacked out but is not mentioning it because he wants to get back to work.",
    "He hit his head and blacked out but hasn't mentioned it.",
    "He hit his head and blacked out but won't mention it because he is embarrassed.",
    "He hit his head and blacked out but hasn't told anyone.",
    "He hit his head and blacked out but has not told staff because he fears losing his job.",
    "He hit his head and blacked out but doesn't want to say because he is embarrassed.",
    "He hit his head and blacked out but does not want to admit it.",
    "He is hiding that he hit his head and blacked out.",
    "He conceals that he hit his head and blacked out.",
    "He hit his head and blacked out but keeps quiet about it.",
    "He hit his head and blacked out but keeps it to himself.",
    "He hit his head and blacked out but is embarrassed to say.",
    "He hit his head and blacked out but is ashamed to admit it.",
    "He hit his head and blacked out but is afraid to say because he wants to keep working.",
    "He denies any head injury but in fact he hit his head and blacked out.",
    "He hit his head and blacked out but will not volunteer it.",
    "He only admits that he hit his head and blacked out if pressed.",
    "He hit his head and blacked out but plays it down.",
    "He hit his head and blacked out but minimises it.",
    "He secretly hit his head and blacked out.",
    "He has not told us that he hit his head and blacked out.",
]
_META = re.compile(r"mention|hiding|conceal|keeps? (?:quiet|it to)|embarrassed to|ashamed to|afraid to say|volunteer|if pressed|plays? (?:it )?down|minimi[sz]|secretly|told (?:anyone|staff|us)|denies", re.I)


@pytest.mark.parametrize("sentence", CONCEALMENT_PHRASINGS)
def test_every_way_of_saying_it_is_concealed(sentence):
    c = tpl.from_description(_BASE.format(sentence))["case"]
    hidden = of(c, "concealed")
    assert len(hidden) == 1, [f["statement"] for f in c["facts"]]
    h = hidden[0]
    assert "hit his head" in h["statement"].lower() and h["disclosure"]["rule"] == "after_rapport" and h["cover_answer"]
    assert "I hit my head and blacked out" in h["patient_answer"]
    for f in c["facts"]:                                  # the author's note about the concealment never reaches the patient's mouth
        assert not _META.search((f.get("patient_answer") or "").replace("I didn't say because", "")), (f["fact_id"], f.get("patient_answer"))
    assert not _META.search(h["cover_answer"]) and not re.match(r"^No,? I didn'?t", h["cover_answer"])        # a deflection, not an invented flat lie
    assert wording_problems(c) == [] and of(c, "chief_complaint")[0]["patient_answer"] == "I've had a sore shoulder for two days."
    eng, st, say = play(c)
    r = say("Did you hit your head?")
    assert r["reply"] == h["cover_answer"] and r["event"]["result"] == "withheld"


def test_james_mechanism_location_severity_concealment_and_off_topic():
    c = tpl.from_description(JAMES)["case"]
    assert c["title"] == "Fall from a bicycle in a 34-year-old man" and wording_problems(c) == [] and not c["review"]["coverage"]["uncovered"]
    assert of(c, "chief_complaint")[0]["patient_answer"] == "I fell off my bicycle about an hour ago and my right wrist hurts."
    said = {f["statement"]: f.get("patient_answer") for f in c["facts"]}
    assert said["A graze on his knee"] == "I've got a graze on my knee." and said["He has pain in his right wrist"] == "I have pain in my right wrist."
    h = of(c, "concealed")[0]
    assert h["patient_answer"] == "All right. I hit my head and briefly blacked out. I didn't say because I want to get back to work."
    assert h["cover_answer"] == "I'm fine. It's just my wrist."
    eng, st, say = play(c)
    say("What brings you in?")
    r = say("Did you hit your head?")
    assert r["reply"] == h["cover_answer"] and "Like I said" not in r["reply"]
    assert say("Did you black out at all?")["reply"] == h["cover_answer"]
    assert say("Where does it hurt?")["reply"] == "I have pain in my right wrist."            # location, not the severity score
    assert say("How bad is the pain?")["reply"] == "It's about a 7 out of 10."
    assert say("Which part hurts?")["reply"] == "I have pain in my right wrist."               # same fact, different question: said plainly
    r = say("Who's the president?")
    assert r["event"]["result"] == "deflected_off_topic" and "not sure" not in r["reply"]
    say("That sounds painful, I'm sorry. Take your time.")
    assert h["fact_id"] in eng.disclosed(st)
    assert say("Do you smoke?")["reply"] == "I smoke about five cigarettes a day."
    assert say("Do you smoke?")["reply"].startswith("Like I said")                              # the same question again


def test_like_i_said_needs_the_same_question_topic():
    from .conftest import seed_case
    eng, st, say = play(seed_case("chest-pain-line-cook"))
    first = say("What brings you in today?")["reply"]
    assert say("Do you have any chest pain?")["reply"] == first                                 # a different question reaching the same fact: no "Like I said"
    assert say("What brings you in today?")["reply"].startswith("Like I said")
