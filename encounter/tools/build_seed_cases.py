"""Authoring script for the three seed cases in encounter/cases/ (run: .venv/bin/python -m encounter.tools.build_seed_cases).

The JSON files it writes are the shipped cases; this script only exists so the team can edit them in a
compact form. All content is original and synthetic, written for this project, and flagged
needs_faculty_review. Reference ranges come from the open-access pages listed in each case's `sources`
(fetched 2026-10-10); anything not on those pages is marked "authored, unsourced".
"""
from __future__ import annotations

import json

from ..paths import SEED_CASES_DIR
from ..validate import validate_case

SRC = {
    "medlineplus_cbc": {"source_id": "medlineplus_cbc", "title": "CBC blood test (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/003642.htm", "date": "fetched 2026-10-10", "role": "evidence_for_fact", "license": "US National Library of Medicine, public information"},
    "medlineplus_bmp": {"source_id": "medlineplus_bmp", "title": "Basic metabolic panel (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/003462.htm", "date": "fetched 2026-10-10", "role": "evidence_for_fact", "license": "US National Library of Medicine, public information"},
    "medlineplus_vitals": {"source_id": "medlineplus_vitals", "title": "Vital signs (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/002341.htm", "date": "fetched 2026-10-10", "role": "evidence_for_fact", "license": "US National Library of Medicine, public information"},
    "medlineplus_troponin": {"source_id": "medlineplus_troponin", "title": "Troponin test (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/007452.htm", "date": "fetched 2026-10-10", "role": "objective_rationale", "license": "US National Library of Medicine, public information"},
    "nhlbi_heart_attack": {"source_id": "nhlbi_heart_attack", "title": "Heart Attack - Symptoms (NHLBI)", "url": "https://www.nhlbi.nih.gov/health/heart-attack/symptoms", "date": "fetched 2026-10-10", "role": "objective_rationale", "license": "NIH, public information"},
    "medlineplus_appendicitis": {"source_id": "medlineplus_appendicitis", "title": "Appendicitis (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/000256.htm", "date": "fetched 2026-10-10", "role": "objective_rationale", "license": "US National Library of Medicine, public information"},
    "medlineplus_crp": {"source_id": "medlineplus_crp", "title": "C-reactive protein (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/003356.htm", "date": "fetched 2026-10-10", "role": "evidence_for_fact", "license": "US National Library of Medicine, public information"},
    "medlineplus_bnp": {"source_id": "medlineplus_bnp", "title": "Brain natriuretic peptide test (MedlinePlus Medical Encyclopedia)", "url": "https://medlineplus.gov/ency/article/007509.htm", "date": "fetched 2026-10-10", "role": "evidence_for_fact", "license": "US National Library of Medicine, public information"},
    "authored": {"source_id": "authored", "title": "Authored for HospitalGym, unsourced: synthetic teaching content awaiting faculty review", "role": "teaching_artifact", "license": "project-authored"},
}


def F(fid, statement, answer=None, topics=(), rule="if_asked", **kw):
    cat = fid.split(".")[1]
    disc = {"rule": rule}
    for k in ("rapport_needed", "confront_with", "request"):
        if k in kw:
            disc[k] = kw.pop(k)
    f = {"fact_id": fid, "category": cat, "statement": statement, "patient_knows": answer is not None, "disclosure": disc,
         "topics": list(topics)}
    if answer is not None:
        f["patient_answer"] = answer
    f.update(kw)
    return f


def lab(test, value, unit, ref, flag="", fact_id=None):
    row = {"test": test, "value": value, "unit": unit, "ref_range": ref, "flag": flag}
    if fact_id:
        row["fact_id"] = fact_id
    return row


def base(case_id, title, **kw):
    c = {"schema_version": 1, "case_id": case_id, "version": 1, "status": "published", "title": title,
         "origin": {"kind": "authored"},
         "review": {"author": "HospitalGym overnight build (AI-drafted)", "needs_faculty_review": True, "synthetic": True},
         "intended_learner": "Medical students and first-year emergency medicine residents",
         "learner_role": "Emergency medicine resident", "setting": "Emergency department treatment bay",
         "rubric_id": "default",
         "unknown_response": "I'm not sure. I can't really tell you anything about that."}
    c.update(kw)
    return c


# =====================================================================================================
# Case 1: chest pain, patient denies stimulant use until confronted with evidence
# =====================================================================================================
def case_chest_pain():
    facts = [
        F("f.chief_complaint.chest_pain", "Central chest pressure that began about two hours before arrival",
          "I've got this pressure in the middle of my chest. It started a couple of hours ago and it scared me enough to come in.",
          ["chief_complaint", "pain_chest"], rule="volunteered", critical=True, polarity="positive"),
        F("f.hpi.onset", "Onset at rest, around 6 am, while getting ready for a shift; woke feeling unwell",
          "It came on around six this morning. I wasn't doing anything, just getting ready for work.", ["onset"], critical=True),
        F("f.hpi.character", "Pressure-like, 'a weight on the chest', not sharp or tearing",
          "It's like a weight sitting on my chest. Pressure. It's not sharp.", ["character"]),
        F("f.hpi.severity", "Pain was 7/10 at its worst, 4/10 on arrival", "It was about a seven at its worst. Maybe a four right now.",
          ["severity"], value="7/10 peak, 4/10 now"),
        F("f.hpi.radiation", "Radiates to the left shoulder and left side of the jaw",
          "Yeah, it goes into my left shoulder, and my jaw aches on that side.", ["radiation"], critical=True, polarity="positive"),
        F("f.hpi.duration", "Constant for roughly two hours, easing slightly since arrival",
          "It's been there the whole time, about two hours. It's eased off a little since I got here.", ["duration"]),
        F("f.hpi.aggravating_relieving", "Not changed by breathing, position or pressing on the chest; nothing taken for it",
          "Nothing really changes it. Breathing, moving, pressing on it, it's all the same. I didn't take anything.",
          ["aggravating", "relieving"], polarity="negative"),
        F("f.hpi.associated", "Sweating, palpitations and nausea with the pain; no vomiting, no shortness of breath at rest",
          "I was sweating a lot, my heart was pounding, and I felt sick to my stomach. I didn't throw up. My breathing is okay.",
          ["associated_symptoms", "sweating", "palpitations", "nausea_vomiting", "sob"], polarity="positive"),
        F("f.hpi.previous_episodes", "One similar, milder episode about eight months ago that settled within an hour",
          "Something like this happened once before, maybe eight months back. It was milder and went away in an hour.",
          ["previous_episodes"]),
        F("f.ros.negatives", "Denies fever, cough, leg swelling, calf pain, recent travel or immobilisation, syncope",
          "No fever, no cough. My legs are fine, no swelling. I haven't travelled anywhere and I didn't pass out.",
          ["fever", "cough", "swelling", "travel", "syncope", "dizziness"], polarity="negative"),
        F("f.pmh.hypertension", "Told two years ago that his blood pressure was borderline high; never treated or followed up",
          "A doctor told me a couple of years ago my blood pressure was borderline. I never went back about it.",
          ["hypertension"], critical=True, polarity="positive"),
        F("f.pmh.other", "No known diabetes, high cholesterol (never tested), heart disease or prior surgery",
          "No diabetes that I know of. I've never had my cholesterol checked. No heart problems before, no surgeries.",
          ["diabetes", "cholesterol", "heart_disease", "psh"], polarity="negative"),
        F("f.medications.current", "No regular prescription medicines; occasional ibuprofen for back ache; energy drinks most shifts",
          "I'm not on any regular medicines. Ibuprofen now and then for my back. I do drink a couple of energy drinks most shifts.",
          ["medications", "energy drinks", "caffeine"]),
        F("f.allergies.nkda", "No known drug allergies", "No allergies that I know of.", ["allergies"], polarity="negative", value="NKDA"),
        F("f.family.father_mi", "Father had a heart attack at age 52 and died at 60; mother has type 2 diabetes",
          "My dad had a heart attack at fifty-two. He died at sixty. My mom has diabetes.", ["family_history", "heart attack in the family"],
          critical=True, polarity="positive"),
        F("f.social.smoking", "Smokes about half a pack of cigarettes a day for 20 years (about 10 pack-years)",
          "About half a pack a day. I started when I was around twenty.", ["smoking"], critical=True, polarity="positive",
          value=10, unit="pack-years"),
        F("f.social.alcohol", "Drinks three or four beers after a shift, three nights a week",
          "A few beers after a shift. Three, four, maybe three nights a week.", ["alcohol"], polarity="positive"),
        F("f.social.occupation", "Line cook working double shifts; behind on rent; sleeps about five hours a night",
          "I'm a line cook. I've been pulling doubles because I'm behind on rent, so I sleep maybe five hours.",
          ["occupation", "sleep", "stress"]),
        F("f.social.living", "Lives with his partner and their seven-year-old daughter",
          "I live with my partner and our daughter. She's seven.", ["living_situation"]),
        F("f.concealed.cocaine_use", "Used intranasal cocaine at about 1 am, roughly five hours before the pain began; uses it about twice a month to get through double shifts",
          "Okay. Yes. I did a couple of lines of coke around one this morning, to get through a double. I do it maybe twice a month. I didn't want it on my record, and I didn't want my partner finding out.",
          ["drugs", "cocaine", "stimulants", "uppers", "tox screen", "drug screen", "urine test", "what did you take", "take anything last night"],
          rule="denied_until_confronted", confront_with=["art.tox_screen", "art.prior_ed_note"], critical=True, polarity="positive",
          cover_answer="No. I don't do drugs. Just the energy drinks.", chart_section="social"),
        F("f.concealed.worry", "Afraid of losing his job and of his daughter seeing him ill; his father died of heart disease",
          "Honestly, I'm scared. My dad died of this. And if I can't work, we lose the apartment. I keep thinking about my daughter.",
          ["patient_concerns", "mood"], rule="after_rapport", rapport_needed=4,
          cover_answer="I'm fine. I just want to get this checked and get back to work.", chart_section="social"),
        F("f.vitals.heart_rate", "Heart rate 112 beats/min", None, ["heart rate", "pulse"], rule="chart_initial", value=112, unit="beats/min", label="Heart rate", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.vitals.blood_pressure", "Blood pressure 168/102 mmHg", None, ["blood pressure"], rule="chart_initial", value="168/102", unit="mmHg", label="Blood pressure", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.vitals.other", "Respiratory rate 20/min, SpO2 98% on room air, temperature 37.4 C", None, ["oxygen", "temperature", "respiratory rate"], rule="chart_initial", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.exam.general", "Anxious, diaphoretic, restless; pupils 6 mm and reactive", None, ["general appearance", "pupils"], rule="on_request", request="exam:general", chart_section="exam"),
        F("f.exam.cardiac", "Regular tachycardia, no murmur, rub or gallop; chest wall not tender", None, ["heart sounds"], rule="on_request", request="exam:cardiac", chart_section="exam"),
        F("f.exam.lungs", "Lungs clear bilaterally; no leg oedema, calves soft", None, ["lung sounds"], rule="on_request", request="exam:lungs", chart_section="exam"),
        F("f.imaging.ecg", "ECG: sinus tachycardia 110/min, 1 mm ST depression in V4-V6, no ST elevation", None, ["ecg"], rule="on_request", request="order:ecg", critical=True, chart_section="imaging"),
        F("f.lab.troponin", "High-sensitivity troponin 31 ng/L at presentation (this laboratory's reference: below 14 ng/L)", None, ["troponin"], rule="on_request", request="order:troponin", critical=True, value=31, unit="ng/L", label="Troponin", chart_section="labs"),
        F("f.lab.tox_cocaine", "Urine drug screen: cocaine metabolite detected", None, ["tox screen"], rule="on_request", request="order:tox_screen", value="detected", label="Cocaine metabolite", chart_section="labs"),
    ]
    artifacts = [
        {"artifact_id": "art.triage_note", "kind": "document", "title": "Triage note", "section_id": "triage", "release": {"rule": "initial"}, "synthetic": True,
         "content": "41-year-old man, walked in. Central chest pressure for about 2 hours, sweaty and restless at triage. Says he has 'no medical problems'. Pain 4/10 now. ESI 2. ECG requested per chest pain pathway (not yet reviewed)."},
        {"artifact_id": "art.ecg", "kind": "ecg", "title": "12-lead ECG (text description)", "section_id": "imaging", "release": {"rule": "on_request", "request": "order:ecg"}, "synthetic": True,
         "content": "Rate 110/min, sinus rhythm. Normal axis. PR 150 ms, QRS 90 ms, QTc 450 ms. ST depression of about 1 mm in V4, V5 and V6. No ST elevation. No pathological Q waves. No previous ECG on file for comparison.",
         "interpretation": "Sinus tachycardia with lateral ST depression: ischaemia cannot be excluded. Together with the raised troponin this needs serial ECGs and troponins.",
         "linked_fact_ids": ["f.imaging.ecg"], "source_ids": ["authored"]},
        {"artifact_id": "art.cardiac_labs", "kind": "lab_report", "title": "Blood results (first set)", "section_id": "labs", "release": {"rule": "on_request", "request": "order:troponin"}, "synthetic": True,
         "content": [lab("Troponin (high-sensitivity)", 31, "ng/L", "below 14 (this lab; assay-specific)", "H", "f.lab.troponin"),
                     lab("Hemoglobin", 15.1, "g/dL", "13-18"), lab("WBC", 9.8, "x10^3/mcL", "4.5-11.0"), lab("Platelets", 244, "x10^3/mcL", "150-400"),
                     lab("Sodium", 139, "mEq/L", "136-144"), lab("Potassium", 3.9, "mEq/L", "3.7-5.2"), lab("Creatinine", 1.0, "mg/dL", "0.8-1.2"),
                     lab("Glucose", 108, "mg/dL", "64-100 fasting", "H")],
         "interpretation": "Troponin above this laboratory's reference at presentation; the troponin reference is assay-specific and authored for this synthetic case. A repeat is needed to see the trend.",
         "linked_fact_ids": ["f.lab.troponin"], "source_ids": ["medlineplus_cbc", "medlineplus_bmp", "medlineplus_troponin"]},
        {"artifact_id": "art.tox_screen", "kind": "lab_report", "title": "Urine drug screen", "section_id": "labs", "release": {"rule": "on_request", "request": "order:tox_screen"}, "synthetic": True,
         "content": [lab("Cocaine metabolite", "detected", "", "not detected", "A", "f.lab.tox_cocaine"), lab("Amphetamines", "not detected", "", "not detected"),
                     lab("Opiates", "not detected", "", "not detected"), lab("Cannabinoids", "not detected", "", "not detected"), lab("Benzodiazepines", "not detected", "", "not detected")],
         "interpretation": "Screening immunoassay consistent with recent cocaine exposure. A screen does not time the exposure or prove the cause of the chest pain.",
         "linked_fact_ids": ["f.lab.tox_cocaine"], "source_ids": ["authored"]},
        {"artifact_id": "art.prior_ed_note", "kind": "prior_note", "title": "Previous emergency visit (8 months ago)", "section_id": "records", "release": {"rule": "on_request", "request": "order:prior_records"}, "synthetic": True,
         "content": "Seen 8 months ago with palpitations and chest tightness that settled within an hour. Heart rate 124 on arrival. ECG: sinus tachycardia only. Patient reported using 'something from a coworker to stay awake'. Left before a drug screen was collected. Advised to follow up for blood pressure 150/96; no follow-up recorded.",
         "interpretation": "A documented earlier stimulant-related episode and an untreated raised blood pressure.", "source_ids": ["authored"]},
    ]
    return base(
        "chest-pain-line-cook", "Chest pressure in a 41-year-old line cook",
        standard_workup=["order:ecg", "order:troponin", "order:tox_screen", "order:prior_records", "order:cbc", "order:bmp", "order:chest_xray", "order:d_dimer",
                         "order:medication_list", "exam:general", "exam:cardiac", "exam:lungs", "exam:vitals", "exam:abdomen"],
        prebrief="You are the emergency medicine resident. Rafael Quintero, 41, walked in with chest pressure that started about two hours ago. Triage has taken vital signs. Take a focused history, request the examination and tests you need, and decide on a disposition. You have about eight minutes.",
        profile={"name": "Rafael Quintero", "age": 41, "gender": "male", "race_ethnicity": "Hispanic/Latino",
                 "background": "Line cook at a busy restaurant, works double shifts, lives with his partner and young daughter.",
                 "personality": "Proud, guarded, minimises problems; warms up when treated with respect.",
                 "speech_style": "Short, plain sentences. Deflects with 'I'm fine'."},
        faculty_truth={"diagnosis": "Cocaine-associated chest pain with possible non-ST-elevation myocardial infarction",
                       "differential": ["Acute coronary syndrome", "Cocaine-induced coronary vasospasm", "Hypertensive urgency", "Aortic dissection (less likely)", "Anxiety or panic"],
                       "teaching_points": ["Ask every chest pain patient about stimulant use, and ask again when the evidence does not fit the answer.",
                                           "A guarded patient is more likely to disclose after a non-judging explanation of why the question matters for treatment.",
                                           "A first troponin above the reference needs a repeat and observation, not discharge."],
                       "expected_disposition": "admit", "expected_orders": ["order:ecg", "order:troponin", "order:tox_screen"], "severity": 0.7, "acuity": 2},
        facts=facts,
        chart={"sections": [
            {"section_id": "triage", "title": "Triage note", "release": "initial"},
            {"section_id": "vitals", "title": "Vital signs", "release": "initial"},
            {"section_id": "hpi", "title": "History of present illness", "release": "on_fact"},
            {"section_id": "pmh", "title": "Past medical history", "release": "on_fact"},
            {"section_id": "medications", "title": "Medications", "release": "on_fact"},
            {"section_id": "allergies", "title": "Allergies", "release": "on_fact"},
            {"section_id": "family", "title": "Family history", "release": "on_fact"},
            {"section_id": "social", "title": "Social history", "release": "on_fact"},
            {"section_id": "ros", "title": "Review of systems", "release": "on_fact"},
            {"section_id": "exam", "title": "Physical examination", "release": "on_request"},
            {"section_id": "imaging", "title": "ECG and imaging", "release": "on_request"},
            {"section_id": "labs", "title": "Laboratory results", "release": "on_request"},
            {"section_id": "records", "title": "Previous records", "release": "on_request"}],
            "artifacts": artifacts},
        objectives=[
            {"objective_id": "obj.characterise_pain", "criterion": "Characterises the chest pain: onset, character, radiation and associated symptoms", "kind": "elicit_fact",
             "linked_fact_ids": ["f.hpi.onset", "f.hpi.character", "f.hpi.radiation", "f.hpi.associated"], "evidence_rule": "met when all four are elicited; partly when some are",
             "critical": True, "rubric_domain": "gathering", "feedback_met": "You built a clear picture of the pain before moving on.",
             "feedback_missed": "Work through onset, character, radiation and associated symptoms for any chest pain."},
            {"objective_id": "obj.cardiac_risk", "criterion": "Elicits cardiac risk factors: smoking, blood pressure and family history", "kind": "elicit_fact",
             "linked_fact_ids": ["f.social.smoking", "f.pmh.hypertension", "f.family.father_mi"], "evidence_rule": "met when all three are elicited", "rubric_domain": "gathering",
             "feedback_missed": "Ask about smoking, blood pressure, diabetes, cholesterol and heart disease in close relatives."},
            {"objective_id": "obj.stimulant_use", "criterion": "Uncovers recent stimulant use despite the patient's initial denial", "kind": "elicit_fact",
             "linked_fact_ids": ["f.concealed.cocaine_use"], "evidence_rule": "met when the patient discloses cocaine use; partly when the learner asks about drugs but accepts the denial",
             "critical": True, "rubric_domain": "listening",
             "feedback_met": "You noticed that the story and the evidence did not match, and raised it in a way that let him answer honestly.",
             "feedback_missed": "He denied drug use, but the previous visit note and the urine screen say otherwise. Request them, then raise what you found without judgement and explain why it changes treatment."},
            {"objective_id": "obj.allergies_meds", "criterion": "Checks medicines and allergies", "kind": "safety",
             "linked_fact_ids": ["f.medications.current", "f.allergies.nkda"], "evidence_rule": "met when both are asked", "rubric_domain": "gathering"},
            {"objective_id": "obj.initial_tests", "criterion": "Requests an ECG and a troponin", "kind": "action", "linked_requests": ["order:ecg", "order:troponin"],
             "evidence_rule": "met when both are requested", "critical": True, "rubric_domain": "reasoning",
             "feedback_missed": "Chest pressure with sweating needs an ECG straight away and a troponin."},
            {"objective_id": "obj.nonjudgmental", "criterion": "Responds to the patient's fear and uses non-judging language on sensitive topics", "kind": "communication",
             "linked_fact_ids": ["f.concealed.worry"], "evidence_rule": "empathic or normalising statements; strongest evidence is the patient sharing what he is afraid of",
             "rubric_domain": "rapport", "feedback_missed": "He says 'I'm fine' but he is frightened. Name it, and tell him sensitive questions are routine and confidential."},
            {"objective_id": "obj.structure", "criterion": "Runs a structured interview: introduction, open question first, summary, clear close", "kind": "sequencing",
             "evidence_rule": "three of: introduction, early open question, summary, closing", "rubric_domain": "opening"},
            {"objective_id": "obj.disposition", "criterion": "Recognises that this patient needs observation and repeat testing rather than discharge", "kind": "reasoning",
             "linked_fact_ids": ["f.lab.troponin", "f.imaging.ecg"], "evidence_rule": "disposition is admit, with a summary that names the ECG change or the raised troponin",
             "critical": True, "rubric_domain": "reasoning", "feedback_missed": "ST depression and a raised first troponin mean he should stay for serial testing."},
        ],
        sources=[dict(SRC["medlineplus_vitals"], supports=["f.vitals.heart_rate", "f.vitals.blood_pressure", "f.vitals.other"]),
                 dict(SRC["medlineplus_cbc"], supports=["art.cardiac_labs"]), dict(SRC["medlineplus_bmp"], supports=["art.cardiac_labs"]),
                 dict(SRC["medlineplus_troponin"], supports=["obj.initial_tests", "obj.disposition"]),
                 dict(SRC["nhlbi_heart_attack"], supports=["obj.characterise_pain"]),
                 dict(SRC["authored"], supports=["art.ecg", "art.tox_screen", "art.prior_ed_note", "f.lab.troponin"])],
    )


# =====================================================================================================
# Case 2: right lower abdominal pain in a young woman; penicillin allergy; fear of surgery after rapport
# =====================================================================================================
def case_abdominal_pain():
    facts = [
        F("f.chief_complaint.abdominal_pain", "Lower right abdominal pain since yesterday evening, getting worse",
          "My stomach has been hurting since last night, down on the right side, and it keeps getting worse.",
          ["chief_complaint", "pain_abdomen"], rule="volunteered", critical=True, polarity="positive"),
        F("f.hpi.onset_migration", "Began about 18 hours ago as a dull ache around the navel, then moved to the right lower abdomen overnight",
          "It started yesterday evening as a dull ache around my belly button. Overnight it moved down to the right.",
          ["onset", "location", "did the pain move", "where did it start"], critical=True),
        F("f.hpi.character_severity", "Now sharp and constant, 7/10", "It's sharp now, and it doesn't let up. About a seven out of ten.", ["character", "severity", "duration"]),
        F("f.hpi.aggravating", "Worse with walking, coughing and bumps in the car; best lying still with knees bent",
          "Walking and coughing make it much worse. Every bump on the drive here hurt. Lying still with my knees up is the only thing that helps.",
          ["aggravating", "relieving", "radiation"], critical=True),
        F("f.hpi.appetite_nausea", "No appetite since yesterday; nauseated; vomited once this morning",
          "I haven't wanted to eat since yesterday. I feel sick, and I threw up once this morning.",
          ["appetite", "nausea_vomiting", "associated_symptoms"], critical=True, polarity="positive"),
        F("f.hpi.fever", "Felt hot and shivery overnight; did not take her temperature", "I felt hot and shivery last night. I didn't take my temperature.", ["fever"], polarity="positive"),
        F("f.ros.bowel", "Last bowel movement yesterday, normal; no diarrhoea, no blood", "I went yesterday and it was normal. No diarrhea, no blood.", ["bowel"], polarity="negative"),
        F("f.ros.urinary", "No burning, frequency or blood in urine", "No, peeing is normal. No burning, no blood.", ["urinary"], polarity="negative"),
        F("f.ros.gyn", "Last period three weeks ago and normal; no vaginal bleeding or discharge", "My last period was three weeks ago, right on time and normal. No bleeding or discharge since.",
          ["pregnancy", "vaginal bleeding", "discharge"], critical=True),
        F("f.social.sexual_history", "Sexually active with one male partner; uses a combined oral contraceptive pill, missed no pills this month",
          "I have one partner, my boyfriend. I'm on the pill and I haven't missed any this month.", ["sexual_history", "could you be pregnant"]),
        F("f.pmh.none", "No chronic medical conditions; no previous surgery; appendix in place", "I'm healthy. No medical problems, and I've never had an operation.",
          ["pmh", "psh"], polarity="negative"),
        F("f.medications.current", "Combined oral contraceptive daily; took ibuprofen 400 mg at 6 am with little relief",
          "Just my birth control pill. I took an ibuprofen, 400 milligrams, at six this morning. It barely touched it.", ["medications", "relieving"]),
        F("f.allergies.penicillin", "Penicillin allergy: widespread hives and lip swelling at age 12", "I'm allergic to penicillin. I got hives all over and my lips swelled when I was twelve.",
          ["allergies"], critical=True, polarity="positive", value="penicillin"),
        F("f.hpi.last_meal", "Last ate at about 7 pm yesterday; sips of water at 5 am", "I last ate around seven last night. I've only had sips of water since, at about five.", ["last_meal", "diet"]),
        F("f.family.history", "No family history of bowel disease; father has high blood pressure", "Nothing with the stomach or bowels in my family. My dad has high blood pressure.", ["family_history"]),
        F("f.social.habits", "Does not smoke; a glass of wine at weekends; no recreational drugs", "I don't smoke. A glass of wine on weekends. No drugs.", ["smoking", "alcohol", "drugs"], polarity="negative"),
        F("f.social.occupation", "Graduate student in chemistry; defends her thesis in two days", "I'm a grad student in chemistry. I defend my thesis in two days.", ["occupation"]),
        F("f.social.living", "Lives with a roommate; parents live four hours away", "I live with a roommate. My parents are about four hours away.", ["living_situation"]),
        F("f.concealed.fear_of_surgery", "Waited 18 hours before coming in and wants to leave quickly because she fears an operation: her mother was very unwell after a general anaesthetic, and the thesis defence is in two days",
          "The truth is I waited because I'm terrified you'll say I need surgery. My mom was really sick after an anesthetic, she took hours to wake up properly. And my defense is in two days. I can't miss it.",
          ["patient_concerns", "mood", "delay", "anesthesia", "anaesthetic", "surgery worries"], rule="after_rapport", rapport_needed=4, critical=True,
          cover_answer="I just need something for the pain so I can get back to my work.", chart_section="social"),
        F("f.vitals.temperature", "Temperature 38.1 C", None, ["temperature"], rule="chart_initial", value=38.1, unit="C", label="Temperature", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.vitals.heart_rate", "Heart rate 104 beats/min", None, ["heart rate", "pulse"], rule="chart_initial", value=104, unit="beats/min", label="Heart rate", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.vitals.other", "Blood pressure 118/72 mmHg, respiratory rate 18/min, SpO2 99% on room air", None, ["blood pressure", "oxygen"], rule="chart_initial", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.exam.abdomen", "Abdomen: tender in the right lower quadrant with guarding and rebound tenderness; pressing on the left lower abdomen causes pain on the right; bowel sounds reduced",
          None, ["abdominal exam"], rule="on_request", request="exam:abdomen", critical=True, chart_section="exam", source_ids=["medlineplus_appendicitis"]),
        F("f.lab.pregnancy_test", "Urine pregnancy test negative", None, ["pregnancy test"], rule="on_request", request="order:pregnancy_test", critical=True, value="negative", label="Urine hCG", chart_section="labs", polarity="negative"),
        F("f.lab.wbc", "White blood cell count 14.8 x10^3/mcL (reference 4.5-11.0)", None, ["white count"], rule="on_request", request="order:cbc", value=14.8, unit="x10^3/mcL", label="WBC", chart_section="labs", source_ids=["medlineplus_cbc"]),
        F("f.lab.crp", "C-reactive protein 6.2 mg/dL (healthy adults usually below 0.3)", None, ["crp"], rule="on_request", request="order:crp", value=6.2, unit="mg/dL", label="CRP", chart_section="labs", source_ids=["medlineplus_crp"]),
        F("f.lab.urinalysis", "Urinalysis: no nitrites, no white cells, no blood", None, ["urinalysis"], rule="on_request", request="order:urinalysis", chart_section="labs", polarity="negative"),
        F("f.imaging.ct_abdomen", "CT abdomen and pelvis: dilated appendix (11 mm) with wall thickening and surrounding fat stranding; no abscess, no free air", None, ["ct"], rule="on_request", request="order:ct_abdomen", critical=True, chart_section="imaging"),
    ]
    artifacts = [
        {"artifact_id": "art.triage_note", "kind": "document", "title": "Triage note", "section_id": "triage", "release": {"rule": "initial"}, "synthetic": True,
         "content": "26-year-old woman, walked in bent forward holding her right side. Lower abdominal pain since yesterday evening. Vomited once. Asked twice how long this will take. ESI 3."},
        {"artifact_id": "art.blood_results", "kind": "lab_report", "title": "Blood count", "section_id": "labs", "release": {"rule": "on_request", "request": "order:cbc"}, "synthetic": True,
         "content": [lab("WBC", 14.8, "x10^3/mcL", "4.5-11.0", "H", "f.lab.wbc"), lab("Hemoglobin", 13.4, "g/dL", "12-16"), lab("Platelets", 288, "x10^3/mcL", "150-400")],
         "interpretation": "Raised white cell count, in keeping with an inflammatory or infective process. Not specific.", "linked_fact_ids": ["f.lab.wbc"], "source_ids": ["medlineplus_cbc"]},
        {"artifact_id": "art.ct_report", "kind": "ct", "title": "CT abdomen and pelvis with contrast (report)", "section_id": "imaging", "release": {"rule": "on_request", "request": "order:ct_abdomen", "delay_turns": 2}, "synthetic": True,
         "content": "Technique: CT of the abdomen and pelvis with intravenous contrast. Findings: the appendix measures 11 mm in diameter with wall thickening and stranding of the surrounding fat. No appendicolith. No abscess or free intraperitoneal air. Ovaries and uterus unremarkable. No hydronephrosis.",
         "interpretation": "Findings consistent with acute uncomplicated appendicitis: surgical review. Note the penicillin allergy when antibiotics are chosen.",
         "linked_fact_ids": ["f.imaging.ct_abdomen"], "source_ids": ["authored"]},
        {"artifact_id": "art.clinic_note", "kind": "prior_note", "title": "Student health clinic note (4 months ago)", "section_id": "records", "release": {"rule": "on_request", "request": "order:prior_records"}, "synthetic": True,
         "content": "Routine visit for contraception review. Well. Blood pressure 112/70. Combined oral contraceptive continued. Allergy recorded: penicillin (hives, lip swelling, childhood). No other medicines.",
         "interpretation": "Confirms the penicillin allergy and the contraceptive pill.", "linked_fact_ids": [], "source_ids": ["authored"]},
    ]
    return base(
        "abdominal-pain-grad-student", "Lower abdominal pain in a 26-year-old graduate student",
        standard_workup=["exam:abdomen", "order:pregnancy_test", "order:cbc", "order:crp", "order:urinalysis", "order:ct_abdomen", "order:prior_records", "order:bmp",
                         "order:lft", "order:lipase", "order:ultrasound", "order:ecg", "order:medication_list", "exam:vitals", "exam:cardiac", "exam:lungs", "exam:general"],
        prebrief="You are the emergency medicine resident. Hannah Lindqvist, 26, has had worsening lower abdominal pain since yesterday evening. Take a history, request the examination and tests you need, and decide on a disposition. She seems in a hurry to leave.",
        profile={"name": "Hannah Lindqvist", "age": 26, "gender": "female", "race_ethnicity": "White",
                 "background": "Chemistry graduate student two days from her thesis defence; lives with a roommate.",
                 "personality": "Conscientious, anxious, tries to stay in control; honest when she feels heard.",
                 "speech_style": "Precise and quick, a little clipped when in pain."},
        faculty_truth={"diagnosis": "Acute uncomplicated appendicitis",
                       "differential": ["Acute appendicitis", "Ovarian torsion or ruptured ovarian cyst", "Ectopic pregnancy (excluded by a negative test)", "Urinary tract infection or kidney stone", "Gastroenteritis"],
                       "teaching_points": ["Pain that starts around the navel and moves to the right lower abdomen, with loss of appetite, is a classic story for appendicitis.",
                                           "Every woman of child-bearing age with abdominal pain needs a pregnancy test before imaging.",
                                           "Ask why a patient waited: fear of an operation can drive a request to leave, and it is addressable.",
                                           "Record the allergy before anyone prescribes an antibiotic."],
                       "expected_disposition": "admit", "expected_orders": ["exam:abdomen", "order:pregnancy_test", "order:cbc", "order:ct_abdomen"], "severity": 0.6, "acuity": 3},
        facts=facts,
        chart={"sections": [
            {"section_id": "triage", "title": "Triage note", "release": "initial"},
            {"section_id": "vitals", "title": "Vital signs", "release": "initial"},
            {"section_id": "hpi", "title": "History of present illness", "release": "on_fact"},
            {"section_id": "ros", "title": "Review of systems", "release": "on_fact"},
            {"section_id": "pmh", "title": "Past medical and surgical history", "release": "on_fact"},
            {"section_id": "medications", "title": "Medications", "release": "on_fact"},
            {"section_id": "allergies", "title": "Allergies", "release": "on_fact"},
            {"section_id": "family", "title": "Family history", "release": "on_fact"},
            {"section_id": "social", "title": "Social history", "release": "on_fact"},
            {"section_id": "exam", "title": "Physical examination", "release": "on_request"},
            {"section_id": "labs", "title": "Laboratory results", "release": "on_request"},
            {"section_id": "imaging", "title": "Imaging", "release": "on_request"},
            {"section_id": "records", "title": "Previous records", "release": "on_request"}],
            "artifacts": artifacts},
        objectives=[
            {"objective_id": "obj.pain_story", "criterion": "Elicits the migration of the pain, what worsens it, and the loss of appetite and nausea", "kind": "elicit_fact",
             "linked_fact_ids": ["f.hpi.onset_migration", "f.hpi.aggravating", "f.hpi.appetite_nausea"], "evidence_rule": "met when all three are elicited", "critical": True, "rubric_domain": "gathering",
             "feedback_missed": "Ask where the pain started and whether it moved, what makes it worse, and about appetite."},
            {"objective_id": "obj.gyn_history", "criterion": "Takes a menstrual and sexual history and requests a pregnancy test", "kind": "safety",
             "linked_fact_ids": ["f.ros.gyn", "f.social.sexual_history"], "linked_requests": ["order:pregnancy_test"], "evidence_rule": "met when the last period and sexual history are asked and a pregnancy test is requested",
             "critical": True, "rubric_domain": "gathering", "feedback_missed": "Lower abdominal pain in a 26-year-old woman: ask about her last period and contraception, and test for pregnancy before imaging."},
            {"objective_id": "obj.allergy", "criterion": "Identifies the penicillin allergy and the reaction", "kind": "safety", "linked_fact_ids": ["f.allergies.penicillin"],
             "evidence_rule": "met when the allergy is elicited", "critical": True, "rubric_domain": "gathering", "feedback_missed": "Always ask about allergies and what the reaction was."},
            {"objective_id": "obj.exam_and_tests", "criterion": "Examines the abdomen and requests a blood count and appropriate imaging", "kind": "action",
             "linked_requests": ["exam:abdomen", "order:cbc", "order:ct_abdomen"], "evidence_rule": "met when all three are requested", "rubric_domain": "reasoning"},
            {"objective_id": "obj.explore_fear", "criterion": "Finds out why she waited and why she wants to leave", "kind": "communication", "linked_fact_ids": ["f.concealed.fear_of_surgery"],
             "evidence_rule": "the patient shares her fear of surgery after the learner acknowledges her worry", "critical": True, "rubric_domain": "rapport",
             "feedback_met": "You slowed down, acknowledged the pressure she is under, and she told you what was really worrying her.",
             "feedback_missed": "She keeps asking to leave. Acknowledge the pressure of the thesis defence, then ask what worries her about being here."},
            {"objective_id": "obj.structure", "criterion": "Runs a structured interview: introduction, open question first, summary, clear close", "kind": "sequencing",
             "evidence_rule": "three of: introduction, early open question, summary, closing", "rubric_domain": "opening"},
            {"objective_id": "obj.disposition", "criterion": "Recognises probable appendicitis and arranges surgical review rather than discharge", "kind": "reasoning",
             "linked_fact_ids": ["f.exam.abdomen", "f.imaging.ct_abdomen"], "evidence_rule": "disposition is admit, with a summary naming the examination or CT findings", "critical": True, "rubric_domain": "reasoning"},
        ],
        sources=[dict(SRC["medlineplus_appendicitis"], supports=["obj.pain_story", "f.exam.abdomen"]), dict(SRC["medlineplus_cbc"], supports=["f.lab.wbc", "art.blood_results"]),
                 dict(SRC["medlineplus_crp"], supports=["f.lab.crp"]), dict(SRC["medlineplus_vitals"], supports=["f.vitals.temperature", "f.vitals.heart_rate", "f.vitals.other"]),
                 dict(SRC["authored"], supports=["art.ct_report", "art.clinic_note"])],
    )


# =====================================================================================================
# Case 3: breathlessness in a 68-year-old; stopped his water tablet, admits it only when shown the pharmacy record
# =====================================================================================================
def case_breathless():
    facts = [
        F("f.chief_complaint.breathlessness", "Worsening shortness of breath over two weeks, much worse for three days",
          "I can't get my breath. It's been building for a couple of weeks, and the last three days it's been bad.",
          ["chief_complaint", "sob"], rule="volunteered", critical=True, polarity="positive"),
        F("f.hpi.exertion", "Used to walk four blocks to the shop; now stops after half a block and after one flight of stairs",
          "I used to walk four blocks to the store without thinking. Now I stop after half a block. One flight of stairs and I'm done.",
          ["exercise", "aggravating", "how far can you walk", "severity", "onset", "duration"], critical=True),
        F("f.hpi.orthopnea", "Sleeps propped on three pillows; wakes at night gasping and has to sit on the edge of the bed",
          "I'm sleeping on three pillows now. A couple of nights I woke up gasping and had to sit on the edge of the bed.",
          ["orthopnea", "sleep"], critical=True, polarity="positive"),
        F("f.hpi.swelling_weight", "Both ankles swollen for a week, shoes tight; gained about 4 kg in two weeks",
          "Both ankles are swollen. My shoes are tight. The bathroom scale says I'm up about four kilos in two weeks.",
          ["swelling", "weight_change"], critical=True, polarity="positive"),
        F("f.hpi.cough", "Dry cough at night; no fever; no coloured sputum or blood", "A dry cough at night. No fever. Nothing coming up, no blood.", ["cough", "fever"]),
        F("f.ros.chest_pain", "No chest pain, palpitations or fainting", "No chest pain. No racing heart. I haven't passed out.", ["pain_chest", "palpitations", "syncope", "dizziness"], polarity="negative"),
        F("f.hpi.appetite", "Reduced appetite, feels full after a few bites", "I'm not eating much. A few bites and I feel full.", ["appetite", "nausea_vomiting"]),
        F("f.pmh.heart_failure", "Heart failure diagnosed three years ago after a heart attack; one admission for fluid overload last winter",
          "I had a heart attack three years ago and they told me my heart was weak after it. I was in hospital last winter with fluid on my lungs.",
          ["pmh", "heart_disease", "hospitalizations"], critical=True, polarity="positive"),
        F("f.pmh.other", "High blood pressure for 15 years; type 2 diabetes for 8 years; no lung disease", "High blood pressure for about fifteen years. Diabetes for eight. My lungs have always been fine.",
          ["hypertension", "diabetes", "lung_disease"], polarity="positive"),
        F("f.medications.list", "Prescribed furosemide 40 mg each morning, lisinopril 10 mg, metoprolol succinate 50 mg, metformin 500 mg twice daily, atorvastatin 40 mg",
          "I'm on a water pill, furosemide. Lisinopril, metoprolol, metformin twice a day, and a cholesterol pill, atorvastatin.", ["medications"], critical=True),
        F("f.medications.otc", "Has taken naproxen twice a day for two weeks for knee pain", "I've been taking naproxen for my knee. Twice a day, for a couple of weeks now.",
          ["over the counter", "painkillers", "pain relievers", "naproxen", "anything for pain", "pain_joint"], critical=True, polarity="positive"),
        F("f.allergies.nkda", "No known drug allergies", "No allergies.", ["allergies"], polarity="negative", value="NKDA"),
        F("f.concealed.stopped_diuretic", "Stopped furosemide about three weeks ago: it made him get up to urinate several times a night and he had an accident on the bus; he has not collected a refill",
          "All right. I stopped the water pill about three weeks ago. I was up all night to the bathroom, and I had an accident on the bus. I was too embarrassed to say. I haven't picked up the refill.",
          ["adherence", "water pill", "furosemide", "are you taking your medicines", "stopped any", "pharmacy", "refill"], rule="denied_until_confronted",
          confront_with=["art.pharmacy_record"], critical=True, polarity="positive", cover_answer="I take my pills every morning, same as always.", chart_section="medications"),
        F("f.social.diet", "Eats canned soup and deli meat most days since his wife died; does not limit salt or fluids",
          "Since my wife passed I mostly eat canned soup and sandwiches with deli meat. I don't watch the salt, no.", ["diet"], critical=True, polarity="positive"),
        F("f.social.living", "Widowed 14 months ago; lives alone in a second-floor apartment; daughter visits on Sundays",
          "My wife died fourteen months ago. I live on my own, second floor. My daughter comes by on Sundays.", ["living_situation"]),
        F("f.social.occupation", "Retired city bus driver", "I drove a city bus for thirty-one years. Retired now.", ["occupation"]),
        F("f.social.smoking_alcohol", "Stopped smoking 12 years ago (30 pack-years); one beer on Sundays", "I quit smoking twelve years ago. I smoked a pack a day for thirty years before that. One beer on a Sunday.",
          ["smoking", "alcohol", "drugs"]),
        F("f.concealed.low_mood", "Low mood and poor motivation since his wife's death; has stopped weighing himself and going to the seniors' club",
          "Since she died I don't see much point in the routines. I stopped weighing myself, stopped going to the club. Some days I don't get dressed.",
          ["mood", "patient_concerns", "how are you coping"], rule="after_rapport", rapport_needed=5, cover_answer="I get by.", chart_section="social"),
        F("f.family.history", "Father died of a heart attack at 70; brother has diabetes", "My father died of a heart attack at seventy. My brother has diabetes.", ["family_history"]),
        F("f.vitals.spo2", "SpO2 91% on room air", None, ["oxygen"], rule="chart_initial", value=91, unit="%", label="SpO2", chart_section="vitals"),
        F("f.vitals.blood_pressure", "Blood pressure 154/92 mmHg", None, ["blood pressure"], rule="chart_initial", value="154/92", unit="mmHg", label="Blood pressure", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.vitals.other", "Heart rate 96 beats/min, respiratory rate 24/min, temperature 36.8 C, weight 94 kg (90 kg at clinic two months ago)", None, ["heart rate", "weight"], rule="chart_initial", chart_section="vitals", source_ids=["medlineplus_vitals"]),
        F("f.exam.lungs", "Crackles at both lung bases to the mid zones; speaks in short sentences", None, ["lung sounds"], rule="on_request", request="exam:lungs", critical=True, chart_section="exam"),
        F("f.exam.cardiac", "Raised jugular venous pressure; third heart sound; no murmur", None, ["heart sounds"], rule="on_request", request="exam:cardiac", chart_section="exam"),
        F("f.exam.extremities", "Pitting oedema of both legs to the knees", None, ["leg swelling"], rule="on_request", request="exam:extremities", chart_section="exam"),
        F("f.lab.bnp", "BNP 1,240 pg/mL (below 100 makes heart failure unlikely)", None, ["bnp"], rule="on_request", request="order:bnp", critical=True, value=1240, unit="pg/mL", label="BNP", chart_section="labs", source_ids=["medlineplus_bnp"]),
        F("f.lab.creatinine", "Creatinine 1.6 mg/dL (reference 0.8-1.2; 1.1 two months ago)", None, ["kidney function"], rule="on_request", request="order:bmp", value=1.6, unit="mg/dL", label="Creatinine", chart_section="labs", source_ids=["medlineplus_bmp"]),
        F("f.imaging.chest_xray", "Chest X-ray: enlarged heart, upper-lobe vascular redistribution, small bilateral pleural effusions; no consolidation", None, ["chest x-ray"], rule="on_request", request="order:chest_xray", critical=True, chart_section="imaging"),
    ]
    artifacts = [
        {"artifact_id": "art.triage_note", "kind": "document", "title": "Triage note", "section_id": "triage", "release": {"rule": "initial"}, "synthetic": True,
         "content": "68-year-old man brought by his daughter. Short of breath, worse over three days. Speaking in short sentences. Known 'weak heart'. Says he takes all his medicines. Oxygen started at 2 L/min. ESI 2."},
        {"artifact_id": "art.pharmacy_record", "kind": "medication_list", "title": "Pharmacy dispensing record (last 3 months)", "section_id": "medications", "release": {"rule": "on_request", "request": "order:medication_list"}, "synthetic": True,
         "content": [{"medicine": "Furosemide 40 mg tablets", "last_dispensed": "9 weeks ago", "supply_days": 30, "note": "no refill collected since"},
                     {"medicine": "Lisinopril 10 mg tablets", "last_dispensed": "2 weeks ago", "supply_days": 30, "note": ""},
                     {"medicine": "Metoprolol succinate 50 mg tablets", "last_dispensed": "2 weeks ago", "supply_days": 30, "note": ""},
                     {"medicine": "Metformin 500 mg tablets", "last_dispensed": "2 weeks ago", "supply_days": 30, "note": ""},
                     {"medicine": "Atorvastatin 40 mg tablets", "last_dispensed": "2 weeks ago", "supply_days": 30, "note": ""}],
         "interpretation": "Every medicine except furosemide has been collected on time. A 30-day supply dispensed 9 weeks ago means at least 5 weeks without a refill. A dispensing gap does not by itself prove the medicine was not taken; ask.",
         "linked_fact_ids": ["f.medications.list"], "source_ids": ["authored"]},
        {"artifact_id": "art.blood_results", "kind": "lab_report", "title": "Blood results", "section_id": "labs", "release": {"rule": "on_request", "request": "order:bmp"}, "synthetic": True,
         "content": [lab("Sodium", 133, "mEq/L", "136-144", "L"), lab("Potassium", 4.8, "mEq/L", "3.7-5.2"), lab("BUN", 34, "mg/dL", "6-20", "H"),
                     lab("Creatinine", 1.6, "mg/dL", "0.8-1.2", "H", "f.lab.creatinine"), lab("Glucose", 162, "mg/dL", "64-100 fasting", "H")],
         "interpretation": "Kidney function is worse than two months ago and sodium is low. In this setting consider fluid overload and the recent anti-inflammatory painkiller.",
         "linked_fact_ids": ["f.lab.creatinine"], "source_ids": ["medlineplus_bmp"]},
        {"artifact_id": "art.chest_xray", "kind": "xray", "title": "Chest X-ray (report)", "section_id": "imaging", "release": {"rule": "on_request", "request": "order:chest_xray"}, "synthetic": True,
         "content": "PA and lateral chest. The heart is enlarged. Upper-lobe vascular redistribution with interstitial markings at both bases. Small bilateral pleural effusions. No focal consolidation. No pneumothorax.",
         "interpretation": "Appearances of pulmonary venous congestion with small effusions: fluid overload from heart failure rather than pneumonia.",
         "linked_fact_ids": ["f.imaging.chest_xray"], "source_ids": ["authored"]},
        {"artifact_id": "art.cardiology_letter", "kind": "prior_note", "title": "Cardiology clinic letter (2 months ago)", "section_id": "records", "release": {"rule": "on_request", "request": "order:prior_records"}, "synthetic": True,
         "content": "Stable heart failure with reduced ejection fraction (35% on last echocardiogram). Weight 90 kg, no oedema. Creatinine 1.1 mg/dL. Continue furosemide 40 mg daily, lisinopril, metoprolol. Advised daily weights, to limit salt, and to avoid anti-inflammatory painkillers.",
         "interpretation": "Baseline two months ago: 4 kg lighter, no oedema, normal creatinine, and explicit advice to avoid anti-inflammatory painkillers.", "source_ids": ["authored"]},
    ]
    return base(
        "breathless-retired-driver", "Breathlessness in a 68-year-old retired bus driver",
        standard_workup=["exam:lungs", "exam:cardiac", "exam:extremities", "order:bnp", "order:bmp", "order:chest_xray", "order:medication_list", "order:prior_records",
                         "order:ecg", "order:troponin", "order:cbc", "exam:vitals", "exam:abdomen", "exam:general"],
        prebrief="You are the emergency medicine resident. Leonard Asante, 68, has been brought in by his daughter with worsening breathlessness. Triage has started oxygen. Take a history, request the examination and tests you need, find out why he has got worse, and decide on a disposition.",
        profile={"name": "Leonard Asante", "age": 68, "gender": "male", "race_ethnicity": "Black",
                 "background": "Retired city bus driver, widowed 14 months ago, lives alone on the second floor.",
                 "personality": "Dignified, private, dry sense of humour; embarrassed by anything to do with the bathroom.",
                 "speech_style": "Unhurried, short of breath, pauses between phrases. Understates."},
        faculty_truth={"diagnosis": "Acute decompensated heart failure precipitated by stopping furosemide, anti-inflammatory painkiller use and high salt intake",
                       "differential": ["Decompensated heart failure", "Pneumonia", "Acute coronary syndrome", "Pulmonary embolism", "Worsening kidney function"],
                       "teaching_points": ["Finding the reason for a decompensation (medicines stopped, new medicines, diet) is as important as recognising it.",
                                           "A dispensing record can show a gap the patient is embarrassed to admit; raise it kindly and ask what got in the way.",
                                           "Over-the-counter anti-inflammatory painkillers are a common, easily missed precipitant.",
                                           "Bereavement and low mood undermine self-care routines such as daily weights."],
                       "expected_disposition": "admit", "expected_orders": ["exam:lungs", "order:bnp", "order:chest_xray", "order:bmp", "order:medication_list"], "severity": 0.75, "acuity": 2},
        facts=facts,
        chart={"sections": [
            {"section_id": "triage", "title": "Triage note", "release": "initial"},
            {"section_id": "vitals", "title": "Vital signs", "release": "initial"},
            {"section_id": "hpi", "title": "History of present illness", "release": "on_fact"},
            {"section_id": "ros", "title": "Review of systems", "release": "on_fact"},
            {"section_id": "pmh", "title": "Past medical history", "release": "on_fact"},
            {"section_id": "medications", "title": "Medications", "release": "on_fact"},
            {"section_id": "allergies", "title": "Allergies", "release": "on_fact"},
            {"section_id": "family", "title": "Family history", "release": "on_fact"},
            {"section_id": "social", "title": "Social history", "release": "on_fact"},
            {"section_id": "exam", "title": "Physical examination", "release": "on_request"},
            {"section_id": "labs", "title": "Laboratory results", "release": "on_request"},
            {"section_id": "imaging", "title": "Imaging", "release": "on_request"},
            {"section_id": "records", "title": "Previous records", "release": "on_request"}],
            "artifacts": artifacts},
        objectives=[
            {"objective_id": "obj.hf_symptoms", "criterion": "Elicits the pattern of fluid overload: exertional limit, breathlessness lying flat, swelling and weight gain", "kind": "elicit_fact",
             "linked_fact_ids": ["f.hpi.exertion", "f.hpi.orthopnea", "f.hpi.swelling_weight"], "evidence_rule": "met when all three are elicited", "critical": True, "rubric_domain": "gathering",
             "feedback_missed": "Ask how far he can walk, how he sleeps, and about swelling and weight."},
            {"objective_id": "obj.background", "criterion": "Establishes the cardiac history and the prescribed medicines", "kind": "elicit_fact",
             "linked_fact_ids": ["f.pmh.heart_failure", "f.medications.list"], "evidence_rule": "met when both are elicited", "rubric_domain": "gathering"},
            {"objective_id": "obj.adherence", "criterion": "Discovers that he stopped his diuretic, and why", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.stopped_diuretic"],
             "evidence_rule": "met when the patient discloses stopping furosemide; partly when the learner asks about adherence but accepts 'I take my pills'", "critical": True, "rubric_domain": "listening",
             "feedback_met": "You checked the dispensing record, raised the gap kindly, and learned the real barrier: night-time urination and embarrassment.",
             "feedback_missed": "He said he takes everything, yet he is 4 kg heavier. Request the pharmacy record, then say what you see and ask what got in the way."},
            {"objective_id": "obj.precipitants", "criterion": "Identifies other precipitants: anti-inflammatory painkillers and a high-salt diet", "kind": "elicit_fact",
             "linked_fact_ids": ["f.medications.otc", "f.social.diet"], "evidence_rule": "met when both are elicited", "critical": True, "rubric_domain": "gathering",
             "feedback_missed": "Ask specifically about over-the-counter painkillers and about what he eats."},
            {"objective_id": "obj.exam_and_tests", "criterion": "Examines the chest and requests BNP and a chest X-ray", "kind": "action", "linked_requests": ["exam:lungs", "order:bnp", "order:chest_xray"],
             "evidence_rule": "met when all three are requested", "rubric_domain": "reasoning"},
            {"objective_id": "obj.person", "criterion": "Explores how he has been coping since his wife's death", "kind": "communication", "linked_fact_ids": ["f.concealed.low_mood"],
             "evidence_rule": "the patient describes his low mood after sustained empathic engagement", "rubric_domain": "rapport",
             "feedback_missed": "He mentioned his wife's death in passing. Acknowledge it and ask how he has been managing; it explains the missed routines."},
            {"objective_id": "obj.structure", "criterion": "Runs a structured interview: introduction, open question first, summary, clear close", "kind": "sequencing",
             "evidence_rule": "three of: introduction, early open question, summary, closing", "rubric_domain": "opening"},
            {"objective_id": "obj.disposition", "criterion": "Recognises decompensated heart failure needing admission and names the reversible causes", "kind": "reasoning",
             "linked_fact_ids": ["f.lab.bnp", "f.imaging.chest_xray", "f.concealed.stopped_diuretic"], "evidence_rule": "disposition is admit, with a summary naming fluid overload and at least one precipitant", "critical": True, "rubric_domain": "reasoning"},
        ],
        sources=[dict(SRC["medlineplus_bnp"], supports=["f.lab.bnp"]), dict(SRC["medlineplus_bmp"], supports=["f.lab.creatinine", "art.blood_results"]),
                 dict(SRC["medlineplus_vitals"], supports=["f.vitals.blood_pressure", "f.vitals.other"]),
                 dict(SRC["authored"], supports=["art.pharmacy_record", "art.chest_xray", "art.cardiology_letter", "f.vitals.spo2"])],
    )


def main() -> int:
    SEED_CASES_DIR.mkdir(parents=True, exist_ok=True)
    bad = 0
    for build in (case_chest_pain, case_abdominal_pain, case_breathless):
        c = build()
        rep = validate_case(c)
        path = SEED_CASES_DIR / f"{c['case_id']}.v1.json"
        path.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
        print(f"{path.name}: facts={len(c['facts'])} objectives={len(c['objectives'])} ok={rep['ok']} "
              f"errors={len(rep['errors'])} warnings={len(rep['warnings'])} consistency={len(rep['consistency'])}")
        for e in rep["errors"] + rep["consistency"]:
            print("   !", e)
        for w in rep["warnings"]:
            print("   w", w)
        bad += 0 if rep["ok"] else 1
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
