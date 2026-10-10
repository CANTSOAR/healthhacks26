"""Authoring script for catalog/conditions/<condition_group>.yaml
(run: .venv/bin/python -m encounter.tools.build_templates).

The YAML files are the data the simulator and the encounter engine read; this script is the compact
form they are authored in. Everything is synthetic, written for this project, and flagged
needs_faculty_review. Reference intervals are taken from the open-access pages listed under `sources`
(fetched 2026-10-10). The values chosen for abnormal bands, the history wording, the examination
findings and the decision aids are "authored, unsourced" plausibility choices.

Fact template kinds
  fixed    one statement / patient_answer
  choice   options keyed by severity band (mild | moderate | severe) or `any`; one is picked by the patient's seed.
           Facts sharing a `choice_group` pick the same option index (keeps history and medicines consistent).
  numeric  a value drawn uniformly from the band's [low, high]; `statement` uses {value}; ref_low/ref_high give the flag
`include` limits a fact to a severity range, a sex, or a seeded probability p.
"""
from __future__ import annotations

import yaml

from ..normals import TEMPLATE_WORKUP
from ..paths import TEMPLATES_DIR

M, MO, S = "mild", "moderate", "severe"
ENC = ["clinician_encounter"]
TRIAGE = ["triage", "clinician_encounter"]
NURSE = ["triage", "nursing_assessment", "clinician_encounter"]

SOURCES = {
    "medlineplus_vitals": ("Vital signs (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/002341.htm"),
    "medlineplus_cbc": ("CBC blood test (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003642.htm"),
    "medlineplus_bmp": ("Basic metabolic panel (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003462.htm"),
    "medlineplus_cmp": ("Comprehensive metabolic panel (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003468.htm"),
    "medlineplus_troponin": ("Troponin test (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/007452.htm"),
    "medlineplus_bnp": ("Brain natriuretic peptide test (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/007509.htm"),
    "medlineplus_ddimer": ("D-dimer test (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/007620.htm"),
    "medlineplus_lactate": ("Lactic acid test (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003507.htm"),
    "medlineplus_lipase": ("Lipase test (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003465.htm"),
    "medlineplus_crp": ("C-reactive protein (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003356.htm"),
    "medlineplus_bac": ("Blood Alcohol Level (MedlinePlus Medical Test)", "https://medlineplus.gov/lab-tests/blood-alcohol-level/"),
    "medlineplus_abg": ("Blood gases (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003855.htm"),
    "medlineplus_urinalysis": ("Urinalysis (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/003579.htm"),
    "medlineplus_cap": ("Community-acquired pneumonia in adults (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/000145.htm"),
    "medlineplus_appendicitis": ("Appendicitis (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/000256.htm"),
    "medlineplus_alcohol_withdrawal": ("Alcohol withdrawal (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/000764.htm"),
    "medlineplus_lbp": ("Low back pain - acute (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/007425.htm"),
    "medlineplus_dka": ("Diabetic ketoacidosis (MedlinePlus Medical Encyclopedia)", "https://medlineplus.gov/ency/article/000320.htm"),
    "nhlbi_heart_attack": ("Heart Attack - Symptoms (NHLBI)", "https://www.nhlbi.nih.gov/health/heart-attack/symptoms"),
    "cdc_stroke_signs": ("Signs and Symptoms of Stroke (CDC)", "https://www.cdc.gov/stroke/signs-symptoms/index.html"),
    "niaaa_drinking_patterns": ("Understanding Alcohol Drinking Patterns (NIAAA)", "https://www.niaaa.nih.gov/alcohol-health/overview-alcohol-consumption/moderate-binge-drinking"),
    "niaaa_standard_drink": ("What Is A Standard Drink? (NIAAA)", "https://www.niaaa.nih.gov/alcohols-effects-health/overview-alcohol-consumption/what-standard-drink"),
}


def src(*ids):
    out = [{"source_id": i, "title": SOURCES[i][0], "url": SOURCES[i][1], "date": "fetched 2026-10-10", "role": "evidence_for_fact",
            "license": "public information (US government health site)"} for i in ids]
    out.append({"source_id": "authored", "title": "Authored for HospitalGym, unsourced: history wording, examination findings, abnormal-band values, "
                "decision aids and artifacts are synthetic teaching content awaiting faculty review", "role": "template", "license": "project-authored"})
    return out


def fx(fid, statement, answer=None, topics=(), rule="if_asked", **kw):
    f = _base(fid, answer is not None, topics, rule, kw)
    f.update(kind="fixed", statement=statement)
    if answer is not None:
        f["patient_answer"] = answer
    f.update(kw)
    return f


def ch(fid, options, topics=(), rule="if_asked", knows=True, **kw):
    f = _base(fid, knows, topics, rule, kw)
    f.update(kind="choice", options=options)
    f.update(kw)
    return f


def num(fid, label, unit, ranges, statement, topics=(), rule="chart_initial", decimals=0, **kw):
    f = _base(fid, False, topics, rule, kw)
    f.update(kind="numeric", label=label, unit=unit, ranges={M: list(ranges[0]), MO: list(ranges[1]), S: list(ranges[2])},
             decimals=decimals, statement=statement)
    f.update(kw)
    return f


def _base(fid, knows, topics, rule, kw):
    disc = {"rule": rule}
    for k in ("rapport_needed", "confront_with", "request"):
        if k in kw:
            disc[k] = kw.pop(k)
    cat = fid.split(".")[1]
    default_disc = {"vitals": TRIAGE, "lab": ["lab_test", "clinician_encounter"], "imaging": ["imaging_test", "clinician_encounter"],
                    "exam": ["clinician_encounter", "nursing_assessment"]}.get(cat, ENC)
    return {"fact_id": fid, "category": cat, "topics": list(topics), "patient_knows": knows, "disclosure": disc,
            "critical": bool(kw.pop("critical", False)), "discoverable_by": kw.pop("discoverable_by", default_disc)}


def o(statement, answer=None, **kw):
    d = {"statement": statement}
    if answer is not None:
        d["patient_answer"] = answer
    d.update(kw)
    return d


def vitals(hr, sbp, rr, temp, spo2, dbp_offset=(-52, -38)):
    """Vital-sign fact templates. Each argument is (mild, moderate, severe) ranges."""
    return [
        num("f.vitals.heart_rate", "Heart rate", "beats/min", hr, "Heart rate {value} beats/min", ["heart rate", "pulse"], ref_low=60, ref_high=100, ref_range="60-100", source_ids=["medlineplus_vitals"], chart_section="vitals"),
        num("f.vitals.systolic_bp", "Systolic blood pressure", "mmHg", sbp, "Systolic blood pressure {value} mmHg", ["blood pressure"], ref_low=90, ref_high=120, ref_range="90-120", source_ids=["medlineplus_vitals"], chart_section="vitals"),
        num("f.vitals.respiratory_rate", "Respiratory rate", "breaths/min", rr, "Respiratory rate {value}/min", ["respiratory rate", "breathing rate"], ref_low=12, ref_high=18, ref_range="12-18", source_ids=["medlineplus_vitals"], chart_section="vitals"),
        num("f.vitals.temperature", "Temperature", "C", temp, "Temperature {value} C", ["temperature"], decimals=1, ref_low=36.5, ref_high=37.3, ref_range="36.5-37.3", source_ids=["medlineplus_vitals"], chart_section="vitals"),
        num("f.vitals.spo2", "Oxygen saturation", "%", spo2, "SpO2 {value}% on room air", ["oxygen", "saturation", "sats"], ref_low=94, ref_high=100, ref_range="94-100 (arterial saturation)", source_ids=["medlineplus_abg"], chart_section="vitals"),
    ]


GENERIC_PMH = [
    o("No chronic medical conditions; no previous surgery", "I'm generally healthy. No ongoing conditions and I've never had surgery.", polarity="negative"),
    o("Hypertension for about six years", "I've had high blood pressure for about six years.", polarity="positive"),
    o("Type 2 diabetes and hypertension", "I have type 2 diabetes and high blood pressure.", polarity="positive"),
    o("Mild asthma since childhood; no hospital admissions for it", "I've had mild asthma since I was a kid. It's never put me in hospital.", polarity="positive"),
]
GENERIC_MEDS = [
    o("No regular medicines", "I don't take anything regularly."),
    o("Amlodipine 5 mg once daily", "One blood pressure pill a day, amlodipine, five milligrams."),
    o("Metformin 500 mg twice daily and lisinopril 10 mg once daily", "Metformin twice a day for the sugar, and lisinopril for my blood pressure."),
    o("Salbutamol (albuterol) inhaler as needed, about once a week", "Just my blue inhaler when I need it. Maybe once a week."),
]


def background(pmh=None, meds=None, smoking_bias=None):
    """History shared by every template. `pmh` and `meds` are lists (any severity) or {band: list}; they share a
    choice_group and must be the same length per band, so option i of one always goes with option i of the other."""
    pmh = pmh or GENERIC_PMH
    meds = meds or GENERIC_MEDS
    pmh_opts = pmh if isinstance(pmh, dict) else {"any": pmh}
    med_opts = meds if isinstance(meds, dict) else {"any": meds}
    assert set(pmh_opts) == set(med_opts) and all(len(pmh_opts[k]) == len(med_opts[k]) for k in pmh_opts), "pmh and meds options must pair up"
    return [
        ch("f.pmh.conditions", pmh_opts, ["pmh", "psh", "hypertension", "diabetes", "lung_disease", "heart_disease"], choice_group="background", chart_section="pmh"),
        ch("f.medications.current", med_opts, ["medications", "blood thinners", "inhaler", "insulin"], choice_group="background", critical=True, chart_section="medications"),
        ch("f.allergies.drug", {"any": [
            o("No known drug allergies", "No allergies that I know of.", polarity="negative", value="NKDA"),
            o("No known drug allergies", "No, no allergies.", polarity="negative", value="NKDA"),
            o("Penicillin allergy: itchy rash as a teenager", "Penicillin. I got an itchy rash from it as a teenager.", polarity="positive", value="penicillin"),
            o("Sulfonamide antibiotic allergy: hives", "Sulfa antibiotics give me hives.", polarity="positive", value="sulfa"),
        ]}, ["allergies"], critical=True, chart_section="allergies"),
        ch("f.family.history", {"any": [
            o("No significant family history", "Nothing I know of runs in my family.", polarity="negative"),
            o("Father had a heart attack at 58; mother has type 2 diabetes", "My father had a heart attack at fifty-eight. My mother has diabetes.", polarity="positive"),
            o("Mother had a stroke at 70", "My mother had a stroke when she was seventy.", polarity="positive"),
        ]}, ["family_history"], chart_section="family"),
        ch("f.social.smoking", {"any": smoking_bias or [
            o("Never smoked", "No, I've never smoked.", polarity="negative"),
            o("Smokes about ten cigarettes a day for 15 years", "About ten a day. I've smoked for fifteen years or so.", polarity="positive"),
            o("Stopped smoking five years ago; previously a pack a day", "I quit five years ago. Before that, a pack a day.", polarity="positive"),
            o("Vapes nicotine daily; never smoked cigarettes", "I vape every day. Never smoked actual cigarettes.", polarity="positive"),
        ]}, ["smoking"], chart_section="social"),
        ch("f.social.alcohol", {"any": [
            o("Drinks alcohol rarely, a drink a month or less", "Hardly ever. A drink a month, if that.", polarity="negative"),
            o("Two or three drinks on weekend evenings", "A couple of drinks on the weekend. Two or three in an evening.", polarity="positive"),
            o("One or two beers most evenings", "A beer or two most evenings.", polarity="positive"),
        ]}, ["alcohol"], chart_section="social"),
        ch("f.social.occupation", {"any": [
            o("Works as a warehouse supervisor", "I'm a supervisor at a warehouse."),
            o("Works as a home health aide", "I'm a home health aide."),
            o("Retired school bus driver", "I'm retired. I drove a school bus."),
            o("Works in a restaurant kitchen", "I work in a restaurant kitchen."),
            o("Office administrator at an insurance firm", "I do office administration at an insurance firm."),
            o("Delivery driver", "I drive deliveries."),
        ]}, ["occupation"], chart_section="social"),
        ch("f.social.living", {"any": [
            o("Lives with a spouse", "I live with my spouse."),
            o("Lives alone; a sibling lives nearby", "I live on my own. My sister is ten minutes away."),
            o("Lives with two children and a parent", "I live with my two kids and my mother."),
            o("Shares an apartment with a roommate", "I share an apartment with a roommate."),
        ]}, ["living_situation"], chart_section="social"),
    ]


STD_SECTIONS = [
    ("triage", "Triage note", "initial"), ("vitals", "Vital signs", "initial"), ("hpi", "History of present illness", "on_fact"),
    ("ros", "Review of systems", "on_fact"), ("pmh", "Past medical history", "on_fact"), ("medications", "Medications", "on_fact"),
    ("allergies", "Allergies", "on_fact"), ("family", "Family history", "on_fact"), ("social", "Social history", "on_fact"),
    ("exam", "Physical examination", "on_request"), ("labs", "Laboratory results", "on_request"),
    ("imaging", "Imaging and ECG", "on_request"), ("records", "Previous records", "on_request"),
]

STD_OBJECTIVES = [
    {"objective_id": "obj.background", "criterion": "Checks medicines and allergies", "kind": "safety", "linked_fact_ids": ["f.medications.current", "f.allergies.drug"],
     "evidence_rule": "met when both are asked", "critical": True, "rubric_domain": "gathering", "feedback_missed": "Ask every patient what they take and what they are allergic to."},
    {"objective_id": "obj.rapport", "criterion": "Acknowledges the patient's feelings and uses non-judging language", "kind": "communication",
     "evidence_rule": "empathic or normalising statements in the transcript", "rubric_domain": "rapport"},
    {"objective_id": "obj.structure", "criterion": "Runs a structured interview: introduction, open question first, summary, clear close", "kind": "sequencing",
     "evidence_rule": "three of: introduction, early open question, summary, closing", "rubric_domain": "opening"},
]


def template(group, label, description, complaint, keywords, facts, artifacts, objectives, diagnoses, teaching, sources, concealments, extra_sections=()):
    return {
        "schema_version": 1, "entity_type": "condition", "id": group, "condition_group": group, "label": label,
        "description": description, "synthetic": True, "needs_faculty_review": True,
        "authoring_note": "Synthetic teaching template authored for HospitalGym. Reference intervals follow the listed open-access sources; "
                          "abnormal-band values, wording, findings and artifacts are authored, unsourced, and need faculty review before teaching use.",
        "variants": {
            M: {"label": "Mild (severity below 1/3)", "attributes": {"severity_range": {"value": [0.0, 0.333], "unit": "fraction", "source": "assumed", "citation": "Band boundaries chosen for this project"}}},
            MO: {"label": "Moderate (severity 1/3 to 2/3)", "attributes": {"severity_range": {"value": [0.333, 0.667], "unit": "fraction", "source": "assumed", "citation": "Band boundaries chosen for this project"}}},
            S: {"label": "Severe (severity above 2/3)", "attributes": {"severity_range": {"value": [0.667, 1.0], "unit": "fraction", "source": "assumed", "citation": "Band boundaries chosen for this project"}}},
        },
        "complaint_label": complaint, "match_keywords": keywords,
        "diagnoses": diagnoses, "teaching_points": teaching, "typical_concealments": concealments,
        "chart_sections": [{"section_id": a, "title": b, "release": c} for a, b, c in list(STD_SECTIONS) + list(extra_sections)],
        "facts": facts, "artifacts": artifacts, "objectives": objectives + STD_OBJECTIVES,
        "rubric_links": {"rubric_id": "default", "domains": ["opening", "rapport", "gathering", "listening", "explanation", "reasoning", "closure"]},
        "sources": sources,
    }


def dx(m, mo, s):
    """diagnoses per band: (diagnosis, disposition, expected_orders, differential)"""
    return [{"band": b, "diagnosis": d[0], "expected_disposition": d[1], "expected_orders": d[2], "differential": d[3]} for b, d in ((M, m), (MO, mo), (S, s))]


def lab_art(aid, title, request, rows, interp, delay=0):
    rel = {"rule": "on_request", "request": request}
    if delay:
        rel["delay_turns"] = delay
    return {"artifact_id": aid, "kind": "lab_report", "title": title, "section_id": "labs", "release": rel, "rows_from": rows,
            "interpretation": interp, "linked_fact_ids": rows, "synthetic": True}


def text_art(aid, kind, title, request, content, interp, section="imaging", linked=(), delay=0):
    rel = {"rule": "on_request", "request": request}
    if delay:
        rel["delay_turns"] = delay
    return {"artifact_id": aid, "kind": kind, "title": title, "section_id": section, "release": rel, "content": content,
            "interpretation": interp, "linked_fact_ids": list(linked), "synthetic": True}


# =========================================================================================== templates

def chest_pain():
    facts = [
        ch("f.chief_complaint.chest_pain", {
            M: [o("Sharp left-sided chest pain for a day, worse on deep breaths", "I've had a sharp pain on the left side of my chest since yesterday. It catches when I breathe in deep.")],
            MO: [o("Central chest tightness on and off for three days, brought on by exertion", "My chest has been getting tight, on and off for three days. Mostly when I'm rushing around.")],
            S: [o("Heavy central chest pressure for about an hour", "There's a heavy pressure in the middle of my chest. It's been about an hour and it's not going away.")]},
           ["chief_complaint", "pain_chest"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi"),
        ch("f.hpi.onset", {
            M: [o("Began yesterday after moving furniture", "It started yesterday, a few hours after I'd been moving furniture.")],
            MO: [o("First noticed three days ago climbing stairs; settles within ten minutes of rest", "I first noticed it three days ago going up stairs. It settles if I rest for ten minutes.")],
            S: [o("Came on at rest about an hour ago", "It came on about an hour ago. I was just sitting watching television.")]}, ["onset", "duration"], critical=True, chart_section="hpi"),
        ch("f.hpi.character", {
            M: [o("Sharp, well localised, reproduced by pressing on the chest wall, 4/10", "It's sharp, and I can point to it with one finger. It hurts when I press there. A four out of ten.")],
            MO: [o("Tight band across the chest, 5/10 at worst", "It's like a tight band across my chest. About a five at its worst.")],
            S: [o("Crushing pressure, 8/10", "It's crushing, like someone is sitting on me. An eight out of ten.")]}, ["character", "severity", "location"], chart_section="hpi"),
        ch("f.hpi.radiation", {
            M: [o("No radiation", "No, it stays in that one spot.", polarity="negative")],
            MO: [o("Sometimes spreads to the left arm", "Sometimes I feel it in my left arm.", polarity="positive")],
            S: [o("Radiates to the left arm and jaw", "It goes down my left arm, and my jaw aches.", polarity="positive")]}, ["radiation"], critical=True, chart_section="hpi"),
        ch("f.hpi.associated", {
            M: [o("No sweating, nausea or shortness of breath", "No sweating, I don't feel sick, and my breathing is fine apart from the catch.", polarity="negative")],
            MO: [o("Mild shortness of breath with the tightness; no sweating or nausea", "I get a bit short of breath with it. No sweating, no nausea.", polarity="positive")],
            S: [o("Sweating, nausea and shortness of breath", "I'm sweating, I feel sick, and I can't quite get my breath.", polarity="positive")]},
           ["associated_symptoms", "sweating", "nausea_vomiting", "sob", "palpitations"], critical=True, chart_section="hpi"),
        fx("f.ros.pe_negatives", "No calf pain or leg swelling, no recent long travel or surgery, no coughing of blood",
           "My legs are fine. I haven't travelled or had an operation, and I'm not coughing anything up.", ["swelling", "travel", "cough", "fever"], polarity="negative", chart_section="ros"),
        ch("f.concealed.stimulant_use", {"any": [
            o("Used cocaine the night before the pain began; uses it a few times a year at parties",
              "All right. I used some cocaine at a party the night before. A few times a year, that's all. I didn't want it written down.",
              cover_answer="No, nothing like that.", polarity="positive")]},
           ["drugs", "cocaine", "stimulants", "tox screen", "drug screen"], rule="denied_until_confronted", confront_with=["art.tox_screen"],
           critical=True, chart_section="social", include={"p": 0.6, "min_severity": 0.3}),
        *background(),
        *vitals(((66, 92), (78, 104), (92, 124)), ((112, 134), (128, 152), (96, 172)), ((14, 18), (16, 20), (18, 26)), ((36.5, 37.2), (36.5, 37.2), (36.4, 37.3)), ((97, 99), (96, 99), (91, 97))),
        ch("f.exam.chest", {
            M: [o("Chest wall tender at the left fourth rib margin; heart sounds normal; lungs clear")],
            MO: [o("Heart sounds normal, no murmur; lungs clear; chest wall not tender; no leg swelling")],
            S: [o("Clammy and pale; heart sounds normal; fine crackles at both lung bases; chest wall not tender")]}, ["heart sounds", "lung sounds"],
           rule="on_request", request="exam:cardiac", knows=False, chart_section="exam"),
        num("f.lab.troponin", "Troponin (high-sensitivity)", "ng/L", ((3, 9), (8, 22), (60, 900)), "High-sensitivity troponin {value} ng/L", ["troponin"], rule="on_request", request="order:troponin",
            critical=True, ref_high=14, ref_range="below 14 (assay-specific; authored for this synthetic lab)", source_ids=["medlineplus_troponin"], chart_section="labs"),
        ch("f.imaging.ecg", {
            M: [o("ECG: normal sinus rhythm, no ST or T wave changes")],
            MO: [o("ECG: sinus rhythm, T wave flattening in the lateral leads, no ST elevation")],
            S: [o("ECG: sinus tachycardia with ST depression in the lateral leads")]}, ["ecg"], rule="on_request", request="order:ecg", knows=False, critical=True, chart_section="imaging"),
        ch("f.lab.tox_screen", {"any": [o("Urine drug screen: cocaine metabolite detected", value="cocaine metabolite detected")]}, ["tox screen"], rule="on_request", request="order:tox_screen",
           knows=False, chart_section="labs", include={"requires": "f.concealed.stimulant_use"}),
    ]
    arts = [
        lab_art("art.cardiac_labs", "Cardiac blood tests", "order:troponin", ["f.lab.troponin"], "Compare with this laboratory's reference; a single value does not exclude a heart attack early after onset, so repeat testing follows local protocol."),
        text_art("art.ecg", "ecg", "12-lead ECG (text description)", "order:ecg", {"from_fact": "f.imaging.ecg"}, "Read together with the history and troponin.", linked=["f.imaging.ecg"]),
        {"artifact_id": "art.tox_screen", "kind": "lab_report", "title": "Urine drug screen", "section_id": "labs", "release": {"rule": "on_request", "request": "order:tox_screen"},
         "content": [{"test": "Cocaine metabolite", "value": "detected", "unit": "", "ref_range": "not detected", "flag": "A"}], "interpretation": "A screening result; it does not time the exposure.",
         "linked_fact_ids": ["f.lab.tox_screen"], "synthetic": True, "include": {"requires": "f.concealed.stimulant_use"}},
    ]
    objs = [
        {"objective_id": "obj.characterise", "criterion": "Characterises the chest pain: onset, character, radiation and associated symptoms", "kind": "elicit_fact",
         "linked_fact_ids": ["f.hpi.onset", "f.hpi.character", "f.hpi.radiation", "f.hpi.associated"], "evidence_rule": "met when all are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.risk", "criterion": "Elicits cardiac risk factors: smoking, medical history and family history", "kind": "elicit_fact",
         "linked_fact_ids": ["f.social.smoking", "f.pmh.conditions", "f.family.history"], "evidence_rule": "met when all are elicited", "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Uncovers stimulant use despite an initial denial", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.stimulant_use"],
         "evidence_rule": "met when disclosed; partly when asked but the denial is accepted", "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Requests an ECG and a troponin", "kind": "action", "linked_requests": ["order:ecg", "order:troponin"], "evidence_rule": "met when both are requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the findings", "kind": "reasoning", "linked_fact_ids": ["f.lab.troponin", "f.imaging.ecg"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("chest_pain", "Chest pain", "Adult presenting to the emergency department with chest pain, from chest-wall pain to acute coronary syndrome.",
                    "chest pain", ["chest pain", "chest pressure", "chest tightness", "heart attack", "angina", "acs", "palpitations", "cardiac"],
                    facts, arts, objs,
                    dx(("Musculoskeletal chest wall pain", "discharge", ["order:ecg", "exam:cardiac"], ["Chest wall strain", "Pleurisy", "Acute coronary syndrome"]),
                       ("Possible unstable angina", "admit", ["order:ecg", "order:troponin"], ["Unstable angina", "Stable angina", "Reflux"]),
                       ("Acute coronary syndrome (non-ST-elevation)", "admit", ["order:ecg", "order:troponin"], ["Non-ST-elevation myocardial infarction", "Aortic dissection", "Pulmonary embolism"])),
                    ["Chest pressure with sweating, nausea or spread to the arm or jaw needs an ECG and troponin without delay.",
                     "A normal first troponin early after onset does not exclude a heart attack.", "Ask about stimulants in every chest pain patient."],
                    src("medlineplus_vitals", "medlineplus_troponin", "nhlbi_heart_attack", "medlineplus_abg"), ["f.concealed.stimulant_use"])


def respiratory():
    facts = [
        ch("f.chief_complaint.breathlessness", {
            M: [o("Cough and wheeze for three days", "I've had a cough and a wheezy chest for three days.")],
            MO: [o("Cough, fever and shortness of breath for four days", "I've been coughing for four days, with a fever, and now I'm short of breath.")],
            S: [o("Severe shortness of breath since this morning after a week of cough", "I can hardly breathe since this morning. I've had a bad cough all week.")]},
           ["chief_complaint", "sob", "cough"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi"),
        ch("f.hpi.cough_sputum", {
            M: [o("Dry cough, worse at night", "It's a dry cough. Worse at night.")],
            MO: [o("Cough with yellow-green sputum; no blood", "I'm bringing up yellow-green stuff. No blood.")],
            S: [o("Cough with thick rust-coloured sputum", "It's thick and kind of rust-coloured.")]}, ["cough", "sputum colour"], critical=True, chart_section="hpi"),
        ch("f.hpi.fever", {
            M: [o("No fever or chills", "No fever, no chills.", polarity="negative")],
            MO: [o("Fever to 38.5 C at home with chills", "I had a fever of 38.5 at home, and chills.", polarity="positive")],
            S: [o("Shaking chills last night; felt very hot", "I had shaking chills last night. I was burning up.", polarity="positive")]}, ["fever"], critical=True, chart_section="hpi"),
        ch("f.hpi.breathlessness_pattern", {
            M: [o("Breathless only when hurrying; speaks in full sentences", "Only when I hurry. I'm all right sitting here.")],
            MO: [o("Breathless walking across a room", "Walking across the room does it.")],
            S: [o("Breathless at rest; cannot finish a sentence", "Even sitting still. I can't... get a whole sentence out.")]}, ["severity", "aggravating", "exercise", "onset", "duration"], chart_section="hpi"),
        ch("f.hpi.pleuritic_pain", {
            M: [o("No chest pain", "No pain in my chest.", polarity="negative")],
            MO: [o("Sharp right-sided chest pain on deep breaths and coughing", "A sharp pain on the right when I breathe deep or cough.", polarity="positive")],
            S: [o("Sharp right-sided chest pain on every breath", "It stabs on the right side every time I breathe.", polarity="positive")]}, ["pain_chest", "character"], chart_section="hpi"),
        fx("f.ros.exposures", "A child at home had a cold last week; no recent travel; no known tuberculosis contact", "My kid had a cold last week. I haven't travelled anywhere.",
           ["travel", "sick contacts", "exposure"], chart_section="ros"),
        ch("f.concealed.inhaler_and_smoking", {"any": [
            o("Stopped the preventer inhaler two months ago and has gone back to smoking about ten cigarettes a day",
              "Okay, honestly, I stopped the preventer inhaler a couple of months back. And I'm smoking again, about ten a day. I know. I didn't want the lecture.",
              cover_answer="I use my inhalers like I'm supposed to. And I gave up smoking.", polarity="positive")]},
           ["adherence", "smoking", "inhaler", "preventer", "are you using your inhalers"], rule="after_rapport", rapport_needed=4, critical=True, chart_section="social", include={"p": 0.65}, replaces="f.social.smoking"),
        *background(
            pmh=[o("Asthma since childhood; one emergency visit two years ago, never intubated", "I've had asthma since I was a kid. One ER visit two years ago. Never on a breathing machine.", polarity="positive"),
                 o("Chronic obstructive pulmonary disease diagnosed four years ago; hypertension", "They told me I have COPD, about four years ago. And high blood pressure.", polarity="positive")],
            meds=[o("Prescribed a budesonide-formoterol preventer inhaler twice daily and a salbutamol reliever as needed", "I'm prescribed a preventer inhaler, twice a day, and a blue reliever inhaler for when I need it."),
                  o("Prescribed a tiotropium inhaler once daily, a salbutamol reliever as needed, and amlodipine 5 mg daily", "A once-a-day inhaler, a blue reliever inhaler, and amlodipine for my blood pressure.")]),
        *vitals(((78, 98), (92, 112), (108, 132)), ((112, 136), (104, 132), (86, 118)), ((16, 20), (20, 26), (26, 34)), ((36.6, 37.4), (37.8, 38.8), (38.4, 39.6)), ((95, 98), (90, 94), (82, 89))),
        ch("f.exam.lungs", {
            M: [o("Scattered expiratory wheeze; no crackles; speaking in full sentences")],
            MO: [o("Crackles and bronchial breathing at the right base; mild wheeze")],
            S: [o("Using accessory muscles; crackles over the right lower zone; reduced air entry; speaks in short phrases")]}, ["lung sounds"], rule="on_request", request="exam:lungs", knows=False, critical=True, chart_section="exam", source_ids=["medlineplus_cap"]),
        num("f.lab.wbc", "WBC", "x10^3/mcL", ((5.5, 10.5), (11.5, 16.0), (15.0, 24.0)), "White blood cell count {value} x10^3/mcL", ["white count"], rule="on_request", request="order:cbc", decimals=1,
            ref_low=4.5, ref_high=11.0, ref_range="4.5-11.0", source_ids=["medlineplus_cbc"], chart_section="labs"),
        num("f.lab.lactate", "Lactate", "mmol/L", ((0.7, 1.6), (1.2, 2.4), (2.6, 5.0)), "Lactate {value} mmol/L", ["lactate"], rule="on_request", request="order:lactate", decimals=1,
            ref_low=0.5, ref_high=2.2, ref_range="0.5-2.2", source_ids=["medlineplus_lactate"], chart_section="labs"),
        ch("f.imaging.chest_xray", {
            M: [o("Chest X-ray: clear lungs, mild hyperinflation")],
            MO: [o("Chest X-ray: right lower lobe consolidation, no effusion")],
            S: [o("Chest X-ray: dense right lower lobe consolidation with a small pleural effusion")]}, ["chest x-ray"], rule="on_request", request="order:chest_xray", knows=False, critical=True, chart_section="imaging", source_ids=["medlineplus_cap"]),
    ]
    arts = [
        lab_art("art.bloods", "Blood results", "order:cbc", ["f.lab.wbc"], "A raised white cell count supports infection but is not specific."),
        text_art("art.chest_xray", "xray", "Chest X-ray (report)", "order:chest_xray", {"from_fact": "f.imaging.chest_xray"}, "Correlate with the examination and oxygen saturation.", linked=["f.imaging.chest_xray"]),
        text_art("art.prior_note", "prior_note", "Primary care note (3 months ago)", "order:prior_records",
                 "Routine review. Advised to continue the preventer inhaler twice daily and to keep off cigarettes. Peak flow at that visit was near personal best. Influenza vaccine declined.",
                 "Gives the baseline and what was prescribed.", section="records"),
    ]
    objs = [
        {"objective_id": "obj.characterise", "criterion": "Characterises the cough, fever and breathlessness", "kind": "elicit_fact",
         "linked_fact_ids": ["f.hpi.cough_sputum", "f.hpi.fever", "f.hpi.breathlessness_pattern"], "evidence_rule": "met when all are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Finds out about inhaler use and smoking beyond the first answer", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.inhaler_and_smoking"],
         "evidence_rule": "met when disclosed; partly when asked but the first answer is accepted", "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Examines the chest and requests a chest X-ray", "kind": "action", "linked_requests": ["exam:lungs", "order:chest_xray"], "evidence_rule": "met when both are requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the oxygen level and findings", "kind": "reasoning", "linked_fact_ids": ["f.exam.lungs", "f.imaging.chest_xray"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("respiratory", "Cough and shortness of breath", "Adult with cough, wheeze or shortness of breath, from a mild asthma flare to pneumonia with low oxygen.",
                    "shortness of breath", ["shortness of breath", "breathless", "cough", "coughing", "cough and fever", "wheeze", "asthma", "copd", "pneumonia", "breathing", "sob", "respiratory"],
                    facts, arts, objs,
                    dx(("Mild asthma exacerbation", "discharge", ["exam:lungs"], ["Asthma flare", "Viral bronchitis"]),
                       ("Community-acquired pneumonia", "discharge", ["exam:lungs", "order:chest_xray"], ["Pneumonia", "Asthma or COPD exacerbation", "Pulmonary embolism"]),
                       ("Severe community-acquired pneumonia with hypoxaemia", "admit", ["exam:lungs", "order:chest_xray", "order:cbc", "order:lactate"], ["Severe pneumonia", "Sepsis", "Pulmonary embolism", "Heart failure"])),
                    ["Cough, fever, chills and sharp chest pain on breathing suggest pneumonia; listen for crackles and get a chest X-ray.",
                     "Low oxygen saturation changes the disposition.", "Ask how inhalers are actually used, not whether they are prescribed."],
                    src("medlineplus_vitals", "medlineplus_cap", "medlineplus_cbc", "medlineplus_lactate", "medlineplus_abg"), ["f.concealed.inhaler_and_smoking"])


def abdominal_pain():
    facts = [
        ch("f.chief_complaint.abdominal_pain", {
            M: [o("Cramping upper abdominal pain and loose stools for two days", "I've had stomach cramps and loose stools for two days.")],
            MO: [o("Right lower abdominal pain since yesterday", "My stomach hurts, low down on the right. Since yesterday.")],
            S: [o("Severe upper abdominal pain going through to the back since last night", "The pain in my upper stomach is terrible. It goes right through to my back. Since last night.")]},
           ["chief_complaint", "pain_abdomen"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi"),
        ch("f.hpi.onset_location", {
            M: [o("Began two days ago after a takeaway meal; crampy, around the navel, comes in waves", "It started two days ago, after a takeout meal. Crampy, around my belly button, in waves.")],
            MO: [o("Began around the navel about 20 hours ago and moved to the right lower abdomen", "It started around my belly button yesterday and moved down to the right.")],
            S: [o("Began suddenly last night after a heavy meal; constant, upper central, boring through to the back", "It came on suddenly last night after a big meal. It's constant, in the upper middle, boring into my back.")]},
           ["onset", "location", "radiation", "character", "duration"], critical=True, chart_section="hpi", source_ids=["medlineplus_appendicitis"]),
        ch("f.hpi.severity_modifiers", {
            M: [o("3/10; eased by passing stool", "About a three. It eases after I go to the toilet.")],
            MO: [o("6/10; worse with walking and coughing", "A six. Walking and coughing make it worse.")],
            S: [o("9/10; slightly better leaning forward; worse lying flat", "Nine out of ten. Leaning forward helps a little. Lying flat is worse.")]}, ["severity", "aggravating", "relieving"], chart_section="hpi"),
        ch("f.hpi.gi_symptoms", {
            M: [o("Nausea, no vomiting; four loose stools a day, no blood", "I feel queasy but I haven't thrown up. Loose stools, about four a day. No blood.", polarity="positive")],
            MO: [o("No appetite; vomited once; bowels normal yesterday", "I can't face food. I threw up once. My bowels were normal yesterday.", polarity="positive")],
            S: [o("Repeated vomiting; no appetite; no diarrhoea", "I keep throwing up. I can't eat. No diarrhea.", polarity="positive")]},
           ["nausea_vomiting", "appetite", "bowel", "associated_symptoms"], critical=True, chart_section="hpi"),
        fx("f.ros.urinary_fever", "No urinary burning or blood; felt feverish but did not measure a temperature", "No burning when I pee, no blood. I've felt feverish but I didn't check.",
           ["urinary", "fever"], chart_section="ros"),
        fx("f.ros.gyn", "Last menstrual period two weeks ago, normal; no vaginal bleeding or discharge", "My last period was two weeks ago and normal. No bleeding or discharge.",
           ["pregnancy", "vaginal bleeding"], critical=True, chart_section="ros", include={"sex": "female", "max_age": 52}),
        fx("f.hpi.last_meal", "Last ate about ten hours ago; sips of water since", "I last ate about ten hours ago. Just sips of water since.", ["last_meal"], chart_section="hpi"),
        ch("f.concealed.alcohol_intake", {"any": [
            o("Drinks about six to eight beers most days and more at weekends; the pain began after a weekend of heavy drinking",
              "Fine. It's more like six to eight beers a day. More on weekends, and this started after a heavy weekend. I didn't want you thinking I'm a drunk.",
              cover_answer="I have a drink now and then. Nothing unusual.", polarity="positive")]},
           ["alcohol", "how much do you drink", "liver tests", "lipase"], rule="denied_until_confronted", confront_with=["art.bloods", "f.lab.lipase"],
           critical=True, chart_section="social", include={"min_severity": 0.67}, replaces="f.social.alcohol"),
        *background(),
        *vitals(((70, 92), (88, 108), (104, 128)), ((108, 132), (106, 130), (88, 118)), ((14, 18), (16, 20), (20, 26)), ((36.6, 37.5), (37.6, 38.4), (37.4, 38.6)), ((97, 99), (96, 99), (93, 97))),
        ch("f.exam.abdomen", {
            M: [o("Abdomen soft; mild diffuse tenderness; no guarding; active bowel sounds")],
            MO: [o("Tender in the right lower quadrant with guarding and rebound tenderness")],
            S: [o("Marked epigastric tenderness with guarding; abdomen distended; bowel sounds reduced")]}, ["abdominal exam"], rule="on_request", request="exam:abdomen", knows=False, critical=True, chart_section="exam", source_ids=["medlineplus_appendicitis"]),
        num("f.lab.wbc", "WBC", "x10^3/mcL", ((5.0, 10.5), (12.0, 17.0), (13.0, 21.0)), "White blood cell count {value} x10^3/mcL", ["white count"], rule="on_request", request="order:cbc", decimals=1,
            ref_low=4.5, ref_high=11.0, ref_range="4.5-11.0", source_ids=["medlineplus_cbc"], chart_section="labs"),
        num("f.lab.lipase", "Lipase", "U/L", ((20, 120), (25, 140), (620, 2400)), "Lipase {value} U/L", ["lipase"], rule="on_request", request="order:lipase",
            ref_low=0, ref_high=160, ref_range="0-160", source_ids=["medlineplus_lipase"], chart_section="labs", critical=True),
        num("f.lab.ast", "AST", "U/L", ((14, 32), (15, 33), (88, 240)), "AST {value} U/L", ["liver tests"], rule="on_request", request="order:lft",
            ref_low=8, ref_high=33, ref_range="8-33", source_ids=["medlineplus_cmp"], chart_section="labs"),
        ch("f.lab.pregnancy_test", {"any": [o("Urine pregnancy test negative", value="negative", polarity="negative")]}, ["pregnancy test"], rule="on_request", request="order:pregnancy_test", knows=False,
           critical=True, chart_section="labs", include={"sex": "female", "max_age": 52}),
        ch("f.imaging.ct_abdomen", {
            M: [o("CT abdomen and pelvis: no acute abnormality")],
            MO: [o("CT abdomen and pelvis: dilated appendix (10 mm) with surrounding fat stranding; no abscess")],
            S: [o("CT abdomen and pelvis: swollen pancreas with surrounding fluid and fat stranding; no gallstones seen")]}, ["ct"], rule="on_request", request="order:ct_abdomen", knows=False, chart_section="imaging"),
    ]
    arts = [
        lab_art("art.bloods", "Blood results", "order:lipase", ["f.lab.lipase"], "Compare with the reference intervals; correlate with the history."),
        lab_art("art.blood_count", "Blood count", "order:cbc", ["f.lab.wbc"], "A raised white cell count supports inflammation or infection but is not specific."),
        lab_art("art.liver_tests", "Liver tests", "order:lft", ["f.lab.ast"], "Compare with the reference interval."),
        text_art("art.ct_report", "ct", "CT abdomen and pelvis (report)", "order:ct_abdomen", {"from_fact": "f.imaging.ct_abdomen"}, "Correlate with the examination.", linked=["f.imaging.ct_abdomen"], delay=2),
    ]
    objs = [
        {"objective_id": "obj.characterise", "criterion": "Characterises the pain and the bowel and stomach symptoms", "kind": "elicit_fact",
         "linked_fact_ids": ["f.hpi.onset_location", "f.hpi.severity_modifiers", "f.hpi.gi_symptoms"], "evidence_rule": "met when all are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.gyn", "criterion": "Asks about the last period and requests a pregnancy test", "kind": "safety", "linked_fact_ids": ["f.ros.gyn"], "linked_requests": ["order:pregnancy_test"],
         "evidence_rule": "met when asked and tested", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Establishes the true alcohol intake", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.alcohol_intake"],
         "evidence_rule": "met when disclosed; partly when asked but the first answer is accepted", "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Examines the abdomen and requests blood tests", "kind": "action", "linked_requests": ["exam:abdomen", "order:cbc", "order:lipase"], "evidence_rule": "met when all are requested", "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the findings", "kind": "reasoning", "linked_fact_ids": ["f.exam.abdomen"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("abdominal_pain", "Abdominal pain", "Adult with abdominal pain, from gastroenteritis to appendicitis or acute pancreatitis.",
                    "abdominal pain", ["abdominal pain", "stomach pain", "belly pain", "appendicitis", "pancreatitis", "vomiting", "diarrhea", "gastroenteritis", "abdomen"],
                    facts, arts, objs,
                    dx(("Acute gastroenteritis", "discharge", ["exam:abdomen"], ["Gastroenteritis", "Food poisoning", "Early appendicitis"]),
                       ("Acute appendicitis", "admit", ["exam:abdomen", "order:cbc", "order:ct_abdomen"], ["Appendicitis", "Ovarian pathology", "Kidney stone", "Urinary infection"]),
                       ("Acute pancreatitis, alcohol-related", "admit", ["exam:abdomen", "order:lipase", "order:lft", "order:cbc"], ["Pancreatitis", "Perforated ulcer", "Gallstone disease", "Heart attack"])),
                    ["Pain that starts around the navel and moves to the right lower abdomen, with loss of appetite, suggests appendicitis.",
                     "Test for pregnancy in women of child-bearing age before imaging.", "When the blood tests do not fit the stated alcohol intake, raise it without judgement."],
                    src("medlineplus_vitals", "medlineplus_appendicitis", "medlineplus_cbc", "medlineplus_lipase", "medlineplus_cmp", "niaaa_drinking_patterns", "medlineplus_abg"),
                    ["f.concealed.alcohol_intake"])


def injury_trauma():
    facts = [
        ch("f.chief_complaint.injury", {
            M: [o("Twisted the right ankle stepping off a kerb two hours ago", "I rolled my right ankle stepping off a curb a couple of hours ago.")],
            MO: [o("Fell onto an outstretched left hand; wrist pain and swelling", "I fell and put my left hand out. Now my wrist is swollen and it really hurts.")],
            S: [o("Fell down a flight of stairs; head struck the floor; left hip pain, unable to stand", "I fell down the stairs and hit my head. My left hip is killing me and I can't stand on it.")]},
           ["chief_complaint", "injury_mechanism", "pain_joint"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi"),
        ch("f.hpi.mechanism", {
            M: [o("Foot turned inward; no fall; felt no crack", "My foot just rolled inward. I didn't fall, and I didn't hear a crack.")],
            MO: [o("Tripped over a rug at home and landed on the palm; heard a crack", "I tripped on a rug at home and landed on my palm. I heard a crack.")],
            S: [o("Missed a step in the dark and fell about ten steps; does not remember the fall itself", "I missed a step in the dark and went down about ten stairs. I don't actually remember falling.")]},
           ["injury_mechanism", "onset"], critical=True, chart_section="hpi"),
        ch("f.hpi.function", {
            M: [o("Able to take four steps with a limp immediately afterwards and now", "I could walk on it straight away, with a limp. I still can.", polarity="positive")],
            MO: [o("Cannot grip or turn a door handle; fingers move; no numbness", "I can't grip or turn a door handle. My fingers move and they're not numb.", polarity="positive")],
            S: [o("Cannot bear weight on the left leg", "I can't put any weight on my left leg at all.", polarity="positive")]}, ["pain_joint", "severity", "weakness_numbness"], critical=True, chart_section="hpi"),
        ch("f.hpi.head_injury", {
            M: [o("Did not hit the head; no loss of consciousness", "No, I didn't hit my head.", polarity="negative")],
            MO: [o("Did not hit the head; no loss of consciousness", "I didn't hit my head or black out.", polarity="negative")],
            S: [o("Struck the back of the head; gap in memory of about a minute; vomited once; headache", "I hit the back of my head. There's a gap, maybe a minute I can't remember. I threw up once and I've got a headache.", polarity="positive")]},
           ["hit your head", "syncope", "headache", "nausea_vomiting", "loss of consciousness"], critical=True, chart_section="hpi"),
        fx("f.ros.other_injuries", "No neck pain, no chest or abdominal pain, no other injuries noticed", "My neck's fine. Nothing hurts in my chest or stomach. I don't think I hurt anything else.",
           ["other injuries", "neck_stiffness", "pain_chest", "pain_abdomen"], polarity="negative", chart_section="ros"),
        ch("f.concealed.alcohol_before_fall", {"any": [
            o("Drank about five glasses of wine in the evening before the fall",
              "Yes, all right. I'd had about five glasses of wine that evening. I'm embarrassed, I don't usually.",
              cover_answer="No, I'd had nothing to drink. I just missed the step.", polarity="positive")]},
           ["alcohol", "had anything to drink", "drinking before", "alcohol level"], rule="denied_until_confronted", confront_with=["art.ethanol", "f.lab.ethanol"], critical=True,
           chart_section="social", include={"min_severity": 0.5, "p": 0.75}),
        *background(
            pmh={M: GENERIC_PMH, MO: GENERIC_PMH,
                 S: [o("Atrial fibrillation and hypertension", "An irregular heartbeat, atrial fibrillation, and high blood pressure.", polarity="positive"),
                     o("Atrial fibrillation and osteoporosis", "Atrial fibrillation, and they say my bones are thin.", polarity="positive")]},
            meds={M: GENERIC_MEDS, MO: GENERIC_MEDS,
                  S: [o("Apixaban 5 mg twice daily (blood thinner) and amlodipine 5 mg daily", "I take a blood thinner, apixaban, twice a day, and amlodipine."),
                      o("Apixaban 5 mg twice daily (blood thinner), calcium and vitamin D", "I take a blood thinner, apixaban, twice a day. And calcium with vitamin D.")]}),
        *vitals(((66, 90), (78, 102), (92, 122)), ((112, 138), (118, 146), (94, 150)), ((14, 18), (16, 20), (18, 24)), ((36.5, 37.2), (36.5, 37.2), (36.2, 37.2)), ((97, 99), (97, 99), (94, 98))),
        ch("f.exam.msk", {
            M: [o("Right ankle: swelling below the lateral malleolus; no bony tenderness at the malleoli or the base of the fifth metatarsal; walks four steps")],
            MO: [o("Left wrist: swelling and a dorsal deformity; tender over the distal radius; pulses and sensation intact")],
            S: [o("Left leg shortened and turned outward; pain on any hip movement; foot pulses present; 3 cm scalp bruise at the back of the head")]},
           ["joint exam"], rule="on_request", request="exam:msk", knows=False, critical=True, chart_section="exam"),
        ch("f.exam.neuro", {
            M: [o("Alert and oriented; sensation and movement in the foot normal")],
            MO: [o("Alert and oriented; median, ulnar and radial nerve function intact in the hand")],
            S: [o("Alert, oriented to person and place but not date; pupils equal and reactive; moves all four limbs; no neck tenderness")]},
           ["neuro exam"], rule="on_request", request="exam:neuro", knows=False, chart_section="exam"),
        ch("f.imaging.xray", {
            M: [o("Ankle X-ray: no fracture; soft tissue swelling laterally")],
            MO: [o("Wrist X-ray: distal radius fracture with dorsal angulation")],
            S: [o("Pelvis and hip X-ray: displaced fracture of the left femoral neck")]}, ["x-ray"], rule="on_request", request="order:xray", knows=False, critical=True, chart_section="imaging"),
        ch("f.imaging.ct_head", {"any": [o("CT head: no bleeding, no skull fracture")]}, ["ct head"], rule="on_request", request="order:ct_head", knows=False, critical=True, chart_section="imaging", include={"min_severity": 0.67}),
        num("f.lab.ethanol", "Blood alcohol", "%", ((0.0, 0.0), (0.09, 0.14), (0.10, 0.19)), "Blood alcohol level {value}%", ["alcohol level"], rule="on_request", request="order:ethanol", decimals=2,
            ref_high=0.0, ref_range="not detected (0.08% is the usual legal driving limit)", source_ids=["medlineplus_bac"], chart_section="labs", include={"requires": "f.concealed.alcohol_before_fall"}),
    ]
    arts = [
        text_art("art.xray", "xray", "X-ray (report)", "order:xray", {"from_fact": "f.imaging.xray"}, "Correlate with the examination and neurovascular status.", linked=["f.imaging.xray"]),
        text_art("art.ct_head", "ct", "CT head (report)", "order:ct_head", {"from_fact": "f.imaging.ct_head"}, "A normal scan does not remove the need for observation in a patient on a blood thinner.", linked=["f.imaging.ct_head"], delay=1),
        dict(lab_art("art.ethanol", "Blood alcohol level", "order:ethanol", ["f.lab.ethanol"], "A level above zero shows recent drinking; it does not by itself explain the fall."), include={"requires": "f.concealed.alcohol_before_fall"}),
    ]
    objs = [
        {"objective_id": "obj.mechanism", "criterion": "Establishes the mechanism, function since the injury, and whether the head was hit", "kind": "elicit_fact",
         "linked_fact_ids": ["f.hpi.mechanism", "f.hpi.function", "f.hpi.head_injury"], "evidence_rule": "met when all are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.anticoagulant", "criterion": "Asks specifically what medicines the patient takes, including blood thinners", "kind": "safety", "linked_fact_ids": ["f.medications.current"], "evidence_rule": "met when elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Establishes whether alcohol was involved", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.alcohol_before_fall"],
         "evidence_rule": "met when disclosed; partly when asked but the denial is accepted", "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Examines the injured part and requests appropriate imaging", "kind": "action", "linked_requests": ["exam:msk", "order:xray"], "evidence_rule": "met when both are requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the injury", "kind": "reasoning", "linked_fact_ids": ["f.imaging.xray"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("injury_trauma", "Injury after a fall or twist", "Adult with a limb or head injury, from an ankle sprain to a hip fracture with head injury on a blood thinner.",
                    "injury", ["fall", "fell", "injury", "trauma", "fracture", "sprain", "ankle", "wrist", "hip", "head injury", "accident", "wound", "gunshot", "laceration"],
                    facts, arts, objs,
                    dx(("Lateral ankle sprain", "discharge", ["exam:msk"], ["Ankle sprain", "Ankle fracture"]),
                       ("Distal radius fracture", "discharge", ["exam:msk", "order:xray"], ["Distal radius fracture", "Scaphoid fracture", "Wrist sprain"]),
                       ("Femoral neck fracture with minor head injury on anticoagulation", "admit", ["exam:msk", "exam:neuro", "order:xray", "order:ct_head"], ["Hip fracture", "Intracranial bleeding", "Syncope as the cause of the fall"])),
                    ["Ask why the patient fell, not only what hurts.", "A head injury in someone on a blood thinner needs imaging and observation.", "Decision rules can avoid X-rays in ankle injuries when the patient can walk and has no bony tenderness (authored, unsourced summary)."],
                    src("medlineplus_vitals", "medlineplus_bac", "medlineplus_abg"), ["f.concealed.alcohol_before_fall"])


def neuro():
    facts = [
        ch("f.chief_complaint.neuro", {
            M: [o("Throbbing one-sided headache with nausea since this morning", "I've had a pounding headache on one side since this morning, and I feel sick.")],
            MO: [o("Right arm weakness and slurred speech for 20 minutes this morning, now resolved", "My right arm went weak and my words came out slurred this morning. It lasted about twenty minutes. I feel normal now.")],
            S: [o("Sudden right-sided weakness and difficulty speaking", "My right side... won't work. The words... come out wrong.")]},
           ["chief_complaint", "headache", "weakness_numbness", "speech_vision"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi", source_ids=["cdc_stroke_signs"]),
        ch("f.hpi.onset_time", {
            M: [o("Built up over an hour from about 8 am", "It built up over about an hour, from eight this morning.")],
            MO: [o("Began suddenly at 9:10 am while making coffee; back to normal by 9:30 am", "It came on all at once at ten past nine, while I was making coffee. By half past it was gone.")],
            S: [o("Last known well at 7:40 am; found by a neighbour at 8:05 am with symptoms", "I was fine at twenty to eight. My neighbour found me like this just after eight.")]},
           ["onset", "duration", "last known well", "what time did it start", "when were you last normal"], critical=True, chart_section="hpi", source_ids=["cdc_stroke_signs"]),
        ch("f.hpi.deficits", {
            M: [o("No weakness, numbness, speech or vision loss; zig-zag lights for 20 minutes before the headache", "No weakness or numbness, and my speech is fine. I saw zig-zag lights for about twenty minutes before it started.", polarity="negative")],
            MO: [o("Right arm felt heavy and clumsy; speech slurred; face not noticed; no vision loss", "My right arm felt heavy and clumsy and my speech was slurred. I didn't notice my face. My vision was fine.", polarity="positive")],
            S: [o("Right arm and leg weak; right face drooping; cannot find words", "My right arm and leg. My face... feels droopy. I can't find... the words.", polarity="positive")]},
           ["weakness_numbness", "speech_vision", "associated_symptoms"], critical=True, chart_section="hpi", source_ids=["cdc_stroke_signs"]),
        ch("f.hpi.headache_features", {
            M: [o("7/10, throbbing, worse with light and noise; similar to previous migraines; not the worst ever", "It's a seven. Throbbing. Light and noise make it worse. It's like my usual migraines, not the worst I've had.", polarity="positive")],
            MO: [o("No headache", "No headache at all.", polarity="negative")],
            S: [o("Mild dull headache", "A dull headache. Not bad.", polarity="positive")]}, ["headache", "severity", "character", "neck_stiffness", "previous_episodes"], chart_section="hpi"),
        fx("f.ros.negatives", "No seizure, no head injury, no fever, no neck stiffness", "No fits, I didn't hit my head, no fever, and my neck isn't stiff.",
           ["seizure", "hit your head", "fever", "neck_stiffness", "syncope"], polarity="negative", chart_section="ros"),
        ch("f.concealed.missed_medicines", {"any": [
            o("Stopped taking blood pressure tablets and the blood thinner about a month ago after losing insurance cover",
              "I haven't taken my blood pressure pills or the blood thinner for about a month. I lost my insurance and couldn't pay for them. I didn't want to say.",
              cover_answer="Yes, I take everything I'm prescribed.", polarity="positive")]},
           ["adherence", "blood thinners", "are you taking your medicines", "insurance_access"], rule="after_rapport", rapport_needed=4, critical=True, chart_section="medications",
           include={"min_severity": 0.34, "p": 0.7}),
        *background(
            pmh={M: [o("Migraine with aura since the twenties; otherwise well", "I've had migraines with aura since my twenties. Otherwise I'm healthy.", polarity="positive"),
                     o("Migraine with aura for ten years; mild hypertension", "Migraines for about ten years, and slightly high blood pressure.", polarity="positive")],
                 MO: [o("Hypertension and atrial fibrillation", "High blood pressure, and an irregular heartbeat called atrial fibrillation.", polarity="positive"),
                      o("Hypertension, atrial fibrillation and type 2 diabetes", "High blood pressure, atrial fibrillation and diabetes.", polarity="positive")],
                 S: [o("Hypertension and atrial fibrillation", "High blood pressure... and an irregular heartbeat.", polarity="positive"),
                     o("Hypertension, atrial fibrillation and type 2 diabetes", "Blood pressure... irregular heart... diabetes.", polarity="positive")]},
            meds={M: [o("Sumatriptan 50 mg when a migraine starts; no regular medicines", "Sumatriptan when a migraine starts. Nothing regular."),
                      o("Sumatriptan as needed and amlodipine 5 mg daily", "Sumatriptan when I need it, and amlodipine every day.")],
                  MO: [o("Prescribed apixaban 5 mg twice daily and amlodipine 10 mg daily", "I'm prescribed apixaban, a blood thinner, twice a day, and amlodipine."),
                       o("Prescribed apixaban 5 mg twice daily, lisinopril 20 mg daily and metformin 1 g twice daily", "I'm prescribed apixaban, lisinopril and metformin.")],
                  S: [o("Prescribed apixaban 5 mg twice daily and amlodipine 10 mg daily", "Apixaban... the blood thinner. And amlodipine."),
                      o("Prescribed apixaban 5 mg twice daily, lisinopril 20 mg daily and metformin 1 g twice daily", "Apixaban... lisinopril... metformin.")]}),
        *vitals(((64, 88), (72, 98), (78, 118)), ((114, 138), (148, 178), (162, 206)), ((14, 18), (14, 18), (16, 22)), ((36.5, 37.2), (36.5, 37.2), (36.5, 37.3)), ((97, 99), (96, 99), (94, 98))),
        num("f.lab.glucose", "Fingerstick glucose", "mg/dL", ((84, 118), (96, 168), (104, 228)), "Fingerstick glucose {value} mg/dL", ["blood sugar", "glucose"], rule="on_request", request="order:glucose",
            critical=True, ref_low=64, ref_high=100, ref_range="64-100 fasting", source_ids=["medlineplus_bmp"], chart_section="labs"),
        ch("f.exam.neuro", {
            M: [o("Normal strength, sensation, speech and visual fields; no neck stiffness; dislikes the light")],
            MO: [o("Normal strength, sensation, speech and face now; no arm drift")],
            S: [o("Right facial droop; right arm drifts and cannot resist gravity; right leg weak; speech effortful with wrong words; left side normal")]},
           ["neuro exam"], rule="on_request", request="exam:neuro", knows=False, critical=True, chart_section="exam", source_ids=["cdc_stroke_signs"]),
        ch("f.imaging.ct_head", {
            M: [o("CT head: normal")],
            MO: [o("CT head: no bleeding, no established infarct")],
            S: [o("CT head: no bleeding; early loss of grey-white differentiation in the left middle cerebral artery territory")]}, ["ct head"], rule="on_request", request="order:ct_head", knows=False, critical=True, chart_section="imaging"),
        ch("f.imaging.ecg", {
            M: [o("ECG: normal sinus rhythm")],
            MO: [o("ECG: atrial fibrillation, rate 88/min")],
            S: [o("ECG: atrial fibrillation, rate 104/min")]}, ["ecg"], rule="on_request", request="order:ecg", knows=False, chart_section="imaging"),
    ]
    arts = [
        text_art("art.ct_head", "ct", "CT head without contrast (report)", "order:ct_head", {"from_fact": "f.imaging.ct_head"}, "Imaging is read together with the time of onset.", linked=["f.imaging.ct_head"], delay=1),
        text_art("art.ecg", "ecg", "12-lead ECG (text description)", "order:ecg", {"from_fact": "f.imaging.ecg"}, "An irregular rhythm is a source of clots.", linked=["f.imaging.ecg"]),
        lab_art("art.glucose", "Point-of-care glucose", "order:glucose", ["f.lab.glucose"], "Low blood sugar can mimic a stroke and is checked first."),
        text_art("art.pharmacy", "medication_list", "Pharmacy dispensing record", "order:medication_list",
                 "Blood pressure tablet and blood thinner: last 30-day supplies dispensed about 10 weeks ago. No collections since.", "A gap in collection; ask what got in the way.", section="records"),
    ]
    objs = [
        {"objective_id": "obj.onset_time", "criterion": "Pins down the exact time of onset or the time last known well", "kind": "elicit_fact", "linked_fact_ids": ["f.hpi.onset_time"],
         "evidence_rule": "met when elicited", "critical": True, "rubric_domain": "gathering", "feedback_missed": "Treatment decisions in a possible stroke depend on the clock: ask when the patient was last normal."},
        {"objective_id": "obj.deficits", "criterion": "Asks about weakness, speech, vision and headache features", "kind": "elicit_fact", "linked_fact_ids": ["f.hpi.deficits", "f.hpi.headache_features"],
         "evidence_rule": "met when both are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Finds out whether prescribed medicines are actually being taken", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.missed_medicines"],
         "evidence_rule": "met when disclosed; partly when asked but the first answer is accepted", "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Performs a neurological examination, checks glucose and requests a CT head", "kind": "action", "linked_requests": ["exam:neuro", "order:glucose", "order:ct_head"],
         "evidence_rule": "met when all are requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the findings", "kind": "reasoning", "linked_fact_ids": ["f.exam.neuro", "f.imaging.ct_head"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("neuro", "Headache, weakness or speech disturbance", "Adult with a neurological complaint, from migraine to transient ischaemic attack to acute stroke.",
                    "neurological symptoms", ["stroke", "weakness", "numbness", "speech", "slurred", "headache", "migraine", "tia", "seizure", "dizzy", "confusion", "facial droop", "multiple sclerosis", "ms"],
                    facts, arts, objs,
                    dx(("Migraine with aura", "discharge", ["exam:neuro"], ["Migraine", "Tension headache", "Subarachnoid haemorrhage"]),
                       ("Transient ischaemic attack", "admit", ["exam:neuro", "order:glucose", "order:ct_head", "order:ecg"], ["Transient ischaemic attack", "Low blood sugar", "Migraine aura", "Seizure"]),
                       ("Acute ischaemic stroke", "admit", ["exam:neuro", "order:glucose", "order:ct_head", "order:ecg"], ["Ischaemic stroke", "Intracranial bleeding", "Low blood sugar", "Seizure with weakness"])),
                    ["Note the time symptoms began: the most effective stroke treatments are time-limited.", "Sudden weakness of the face, arm or leg, or trouble speaking, is a stroke until shown otherwise.",
                     "Symptoms that have resolved still need urgent assessment."],
                    src("medlineplus_vitals", "cdc_stroke_signs", "medlineplus_bmp", "medlineplus_abg"), ["f.concealed.missed_medicines"])


def infection_fever():
    facts = [
        ch("f.chief_complaint.fever", {
            M: [o("Burning on urination and frequency for two days", "It burns when I pee, and I've been going constantly for two days.")],
            MO: [o("Fever, right flank pain and urinary burning for three days", "I've had a fever and a pain in my right side, round the back, for three days. And it burns when I pee.")],
            S: [o("High fever, shaking chills and confusion since last night after several days of urinary symptoms", "I've been shaking with chills since last night. I feel so weak, and I can't think straight.")]},
           ["chief_complaint", "fever", "urinary"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi"),
        ch("f.hpi.urinary", {
            M: [o("Burning, frequency and urgency; urine cloudy; no visible blood", "Burning, going all the time, and I can't hold it. It's cloudy. No blood.", polarity="positive")],
            MO: [o("Burning and frequency for five days; urine cloudy and strong-smelling", "It's burned for five days and I go all the time. It's cloudy and smells strong.", polarity="positive")],
            S: [o("Burning for a week; passing very little urine today", "It's burned for a week. Today I've hardly passed anything.", polarity="positive")]}, ["urinary", "duration", "onset"], critical=True, chart_section="hpi"),
        ch("f.hpi.fever_chills", {
            M: [o("No fever or chills", "No fever, no chills.", polarity="negative")],
            MO: [o("Fever to 38.8 C at home with chills", "My temperature was 38.8 at home, and I had the chills.", polarity="positive")],
            S: [o("Shaking chills; temperature 39.6 C at home", "I couldn't stop shaking. It was 39.6 at home.", polarity="positive")]}, ["fever"], critical=True, chart_section="hpi"),
        ch("f.hpi.flank_pain_vomiting", {
            M: [o("No flank pain; no vomiting", "No pain in my back or sides. No vomiting.", polarity="negative")],
            MO: [o("Constant right flank ache, 6/10; nausea, vomited twice", "A constant ache in my right side, about a six. I feel sick and I've thrown up twice.", polarity="positive")],
            S: [o("Right flank pain; vomiting everything; very little to drink for a day", "My right side hurts. I throw up everything. I've barely drunk anything since yesterday.", polarity="positive")]},
           ["pain_back", "nausea_vomiting", "flank", "severity", "appetite"], chart_section="hpi"),
        fx("f.ros.negatives", "No cough, no rash, no neck stiffness, no diarrhoea", "No cough, no rash, my neck's fine, no diarrhea.", ["cough", "rash", "neck_stiffness", "bowel"], polarity="negative", chart_section="ros"),
        fx("f.ros.gyn", "Last menstrual period three weeks ago; no vaginal discharge", "My last period was three weeks ago. No discharge.", ["pregnancy", "vaginal discharge", "sexual_history"], chart_section="ros", include={"sex": "female", "max_age": 52}),
        ch("f.concealed.antibiotic_course", {"any": [
            o("Was prescribed antibiotics at an urgent care clinic five days ago and stopped after two doses because of nausea",
              "I did go to urgent care five days ago and they gave me antibiotics. I stopped after two doses, they made me feel sick. I thought you'd be annoyed.",
              cover_answer="No, I haven't seen anyone or taken anything for it.", polarity="positive")]},
           ["adherence", "antibiotics", "seen anyone about this", "urgent care", "treated for this", "relieving"], rule="denied_until_confronted", confront_with=["art.urgent_care_note"],
           critical=True, chart_section="medications", include={"min_severity": 0.34, "p": 0.7}),
        *background(),
        *vitals(((68, 92), (96, 116), (112, 138)), ((108, 132), (100, 126), (76, 98)), ((14, 18), (18, 22), (22, 30)), ((36.6, 37.4), (38.2, 39.0), (38.8, 40.0)), ((97, 99), (95, 98), (91, 96))),
        ch("f.exam.abdomen", {
            M: [o("Mild suprapubic tenderness; no flank tenderness")],
            MO: [o("Marked tenderness on tapping over the right flank; mild suprapubic tenderness")],
            S: [o("Right flank tenderness; dry mouth; cool hands; drowsy but rousable; slow to answer")]}, ["abdominal exam", "flank"], rule="on_request", request="exam:abdomen", knows=False, critical=True, chart_section="exam"),
        ch("f.lab.urinalysis", {
            M: [o("Urinalysis: nitrites positive, white cells present, trace blood")],
            MO: [o("Urinalysis: nitrites positive, many white cells, blood present")],
            S: [o("Urinalysis: nitrites positive, many white cells, blood and protein present")]}, ["urinalysis"], rule="on_request", request="order:urinalysis", knows=False, critical=True, chart_section="labs", source_ids=["medlineplus_urinalysis"]),
        num("f.lab.wbc", "WBC", "x10^3/mcL", ((5.5, 10.8), (12.5, 17.5), (17.0, 28.0)), "White blood cell count {value} x10^3/mcL", ["white count"], rule="on_request", request="order:cbc", decimals=1,
            ref_low=4.5, ref_high=11.0, ref_range="4.5-11.0", source_ids=["medlineplus_cbc"], chart_section="labs"),
        num("f.lab.lactate", "Lactate", "mmol/L", ((0.6, 1.5), (1.0, 2.1), (3.0, 6.0)), "Lactate {value} mmol/L", ["lactate"], rule="on_request", request="order:lactate", decimals=1, critical=True,
            ref_low=0.5, ref_high=2.2, ref_range="0.5-2.2", source_ids=["medlineplus_lactate"], chart_section="labs"),
        num("f.lab.creatinine", "Creatinine", "mg/dL", ((0.7, 1.1), (0.8, 1.3), (1.6, 2.8)), "Creatinine {value} mg/dL", ["kidney function"], rule="on_request", request="order:bmp", decimals=1,
            ref_low=0.8, ref_high=1.2, ref_range="0.8-1.2", source_ids=["medlineplus_bmp"], chart_section="labs"),
    ]
    arts = [
        text_art("art.urinalysis", "lab_report", "Urinalysis", "order:urinalysis", {"from_fact": "f.lab.urinalysis"}, "Nitrites and white cells are not normally found in urine.", section="labs", linked=["f.lab.urinalysis"]),
        lab_art("art.bloods", "Blood results", "order:cbc", ["f.lab.wbc"], "Compare with the reference intervals."),
        lab_art("art.lactate", "Lactate", "order:lactate", ["f.lab.lactate"], "A raised lactate in an infected patient signals poor tissue perfusion."),
        dict(text_art("art.urgent_care_note", "prior_note", "Urgent care visit summary (5 days ago)", "order:prior_records",
                      "Seen for urinary burning and frequency. Urine dip positive. Prescribed a five-day course of an oral antibiotic and advised to return if fever or flank pain developed.",
                      "A course was prescribed five days ago; ask whether it was taken.", section="records"), include={"requires": "f.concealed.antibiotic_course"}),
    ]
    objs = [
        {"objective_id": "obj.characterise", "criterion": "Characterises the urinary symptoms, fever and flank pain", "kind": "elicit_fact",
         "linked_fact_ids": ["f.hpi.urinary", "f.hpi.fever_chills", "f.hpi.flank_pain_vomiting"], "evidence_rule": "met when all are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Discovers the earlier antibiotic course that was not completed", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.antibiotic_course"],
         "evidence_rule": "met when disclosed; partly when asked but the denial is accepted", "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Requests a urinalysis and, when unwell, blood tests including lactate", "kind": "action", "linked_requests": ["order:urinalysis", "order:cbc", "order:lactate"],
         "evidence_rule": "met when all are requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Recognises how unwell the patient is and chooses a fitting disposition", "kind": "reasoning", "linked_fact_ids": ["f.lab.lactate", "f.exam.abdomen"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("infection_fever", "Fever and infection", "Adult with a urinary source of infection, from simple cystitis to pyelonephritis to sepsis.",
                    "fever", ["fever", "infection", "sepsis", "uti", "urinary", "pyelonephritis", "chills", "flu", "cellulitis", "burning when urinating"],
                    facts, arts, objs,
                    dx(("Uncomplicated urinary tract infection", "discharge", ["order:urinalysis"], ["Cystitis", "Sexually transmitted infection", "Vaginitis"]),
                       ("Acute pyelonephritis", "discharge", ["order:urinalysis", "order:cbc", "exam:abdomen"], ["Pyelonephritis", "Kidney stone with infection", "Appendicitis"]),
                       ("Sepsis from a urinary source", "admit", ["order:urinalysis", "order:cbc", "order:lactate", "order:bmp", "order:blood_cultures"], ["Urosepsis", "Obstructed infected kidney", "Other source of sepsis"])),
                    ["Fever with a fast heart rate, fast breathing, low blood pressure or new confusion should prompt a search for sepsis.", "Ask what treatment has already been tried, and whether it was finished.",
                     "A raised lactate changes the urgency."],
                    src("medlineplus_vitals", "medlineplus_urinalysis", "medlineplus_cbc", "medlineplus_lactate", "medlineplus_bmp", "medlineplus_abg"), ["f.concealed.antibiotic_course"])


def mental_health_substance():
    facts = [
        ch("f.chief_complaint.presentation", {
            M: [o("Anxiety, poor sleep and a racing heart for two weeks", "I've been on edge for two weeks. I can't sleep and my heart races.")],
            MO: [o("Shakiness, sweating and nausea since yesterday", "I've been shaky and sweaty since yesterday, and I feel sick.")],
            S: [o("Severe tremor, sweating and seeing things since this morning", "I can't stop shaking. I'm drenched. And I keep seeing things moving on the walls.")]},
           ["chief_complaint", "withdrawal", "mood"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi"),
        ch("f.hpi.symptoms", {
            M: [o("Worry most of the day, restless, irritable; no tremor; no hallucinations", "I worry all day and I'm irritable. I'm not shaky and I'm not seeing things.", polarity="positive")],
            MO: [o("Hand tremor, sweating, nausea, poor sleep and anxiety; no hallucinations; no seizure", "My hands shake, I sweat, I feel sick, I can't sleep, and I'm anxious. I'm not seeing things. No fits.", polarity="positive")],
            S: [o("Marked tremor, drenching sweats, vomiting, visual hallucinations, agitation; one seizure-like episode witnessed by a neighbour this morning",
                  "Shaking, sweating through my clothes, throwing up. I see things on the walls. My neighbour says I had some kind of fit this morning.", polarity="positive")]},
           ["withdrawal", "associated_symptoms", "seizure", "nausea_vomiting", "sweating", "sleep", "hallucinations"], critical=True, chart_section="hpi", source_ids=["medlineplus_alcohol_withdrawal"]),
        ch("f.concealed.alcohol_quantity", {
            M: [o("Drinks three or four glasses of wine every night to get to sleep, up from one a few months ago",
                  "It's more like three or four glasses of wine a night now. It used to be one. It's the only way I sleep.", cover_answer="A glass of wine with dinner. That's normal, isn't it?", polarity="positive")],
            MO: [o("Drinks about a 750 mL bottle of vodka every two days for the past year",
                   "A bottle of vodka lasts me about two days. It's been like that for a year.", cover_answer="I drink socially. A few at the weekend.", polarity="positive")],
            S: [o("Drinks about a 750 mL bottle of vodka a day for two years",
                  "A bottle of vodka a day. For a couple of years now.", cover_answer="I drink socially. A few at the weekend.", polarity="positive")]},
           ["alcohol", "how much do you drink", "how many drinks"], rule="after_rapport", rapport_needed=3, critical=True, chart_section="social", replaces="f.social.alcohol", source_ids=["niaaa_drinking_patterns"]),
        ch("f.concealed.last_drink", {
            M: [o("Last drink last night", "Last night.", cover_answer="I couldn't say exactly.", polarity="positive")],
            MO: [o("Last drink about 30 hours ago; stopped abruptly after an argument with family", "About thirty hours ago. I stopped cold after a row with my family.", cover_answer="A few days ago, I think.", polarity="positive")],
            S: [o("Last drink about 48 hours ago; ran out of money", "Two days ago. I ran out of money.", cover_answer="A while ago. I don't remember.", polarity="positive")]},
           ["last drink", "when did you last drink", "when did you stop drinking"], rule="denied_until_confronted", confront_with=["f.concealed.alcohol_quantity", "art.prior_note"], critical=True,
           chart_section="social", source_ids=["medlineplus_alcohol_withdrawal"]),
        ch("f.hpi.previous_withdrawal", {
            M: [o("Has never tried to stop drinking", "I've never tried to stop.", polarity="negative")],
            MO: [o("Shaky for a few days after stopping once before; no seizures", "I got the shakes for a few days when I stopped once before. No fits.", polarity="positive")],
            S: [o("One previous withdrawal seizure two years ago requiring admission", "I had a seizure coming off it two years ago. They kept me in.", polarity="positive")]}, ["previous_episodes", "withdrawal", "seizure", "hospitalizations"], critical=True, chart_section="hpi"),
        ch("f.concealed.self_harm_thoughts", {
            M: [o("No thoughts of self-harm or suicide", "No. I've never thought about hurting myself.", polarity="negative", rule="if_asked")],
            MO: [o("Passive thoughts that family would be better off without them; no plan or intent", "Sometimes I think they'd be better off without me. I wouldn't do anything. I don't have a plan.",
                   cover_answer="I'm fine. I'm just tired.", polarity="positive")],
            S: [o("Thoughts of ending life over the past week; no specific plan; no previous attempts", "This past week I've thought about ending it. I haven't planned anything. I've never tried.",
                  cover_answer="I'm fine. I just need something to settle me.", polarity="positive")]},
           ["self_harm", "mood"], rule="after_rapport", rapport_needed=4, critical=True, chart_section="social"),
        fx("f.social.other_substances", "No other drug use; no benzodiazepines", "Nothing else. No pills, no drugs.", ["drugs"], polarity="negative", chart_section="social"),
        *background(),
        *vitals(((72, 96), (98, 118), (116, 142)), ((116, 138), (138, 162), (156, 188)), ((14, 18), (16, 22), (20, 26)), ((36.5, 37.3), (37.2, 37.9), (37.8, 38.8)), ((97, 99), (96, 99), (94, 98))),
        ch("f.exam.general", {
            M: [o("Tense and restless; no tremor; no sweating; oriented")],
            MO: [o("Fine tremor of outstretched hands; sweaty palms; anxious; oriented to person, place and date")],
            S: [o("Coarse tremor; drenched in sweat; agitated; oriented to person only; picks at the bedclothes; tongue bitten at the side")]},
           ["general appearance", "mental status"], rule="on_request", request="exam:general", knows=False, critical=True, chart_section="exam", source_ids=["medlineplus_alcohol_withdrawal"]),
        num("f.lab.ethanol", "Blood alcohol", "%", ((0.0, 0.03), (0.0, 0.0), (0.0, 0.0)), "Blood alcohol level {value}%", ["alcohol level"], rule="on_request", request="order:ethanol", decimals=2,
            ref_high=0.0, ref_range="not detected", source_ids=["medlineplus_bac"], chart_section="labs"),
        num("f.lab.ast", "AST", "U/L", ((28, 60), (70, 160), (120, 320)), "AST {value} U/L", ["liver tests"], rule="on_request", request="order:lft", ref_low=8, ref_high=33, ref_range="8-33", source_ids=["medlineplus_cmp"], chart_section="labs"),
        num("f.lab.mcv", "MCV", "fL", ((90, 99), (99, 106), (102, 112)), "Mean cell volume {value} fL", ["blood count"], rule="on_request", request="order:cbc", ref_low=80, ref_high=100, ref_range="80-100", source_ids=["medlineplus_cbc"], chart_section="labs"),
        num("f.lab.potassium", "Potassium", "mEq/L", ((3.8, 4.6), (3.3, 3.8), (2.8, 3.4)), "Potassium {value} mEq/L", ["electrolytes"], rule="on_request", request="order:bmp", decimals=1, ref_low=3.7, ref_high=5.2, ref_range="3.7-5.2", source_ids=["medlineplus_bmp"], chart_section="labs"),
    ]
    arts = [
        lab_art("art.liver_tests", "Liver tests", "order:lft", ["f.lab.ast"], "A raised AST has many causes; alcohol is one."),
        lab_art("art.blood_count", "Blood count", "order:cbc", ["f.lab.mcv"], "Large red cells have several causes, including regular heavy drinking."),
        lab_art("art.chemistry", "Chemistry", "order:bmp", ["f.lab.potassium"], "Low potassium is common with vomiting and poor intake."),
        lab_art("art.ethanol", "Blood alcohol level", "order:ethanol", ["f.lab.ethanol"], "A level of zero does not exclude dependence; withdrawal begins as the level falls."),
        text_art("art.prior_note", "prior_note", "Previous emergency visit (11 months ago)", "order:prior_records",
                 "Brought in after a fall at home. Smelled of alcohol. Told staff then that they drank 'most of a bottle of spirits' daily. Declined referral to alcohol services. Left before review by the liaison team.",
                 "An earlier record of heavy daily drinking that differs from today's first answer.", section="records"),
    ]
    objs = [
        {"objective_id": "obj.quantity", "criterion": "Establishes how much alcohol the patient really drinks", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.alcohol_quantity"],
         "evidence_rule": "met when disclosed; partly when asked but the first answer is accepted", "critical": True, "rubric_domain": "listening",
         "feedback_missed": "The first answer minimised. Normalise the question ('I ask everyone'), acknowledge how hard it is to talk about, and ask again for a typical day."},
        {"objective_id": "obj.last_drink", "criterion": "Establishes the time of the last drink and previous withdrawal problems", "kind": "elicit_fact",
         "linked_fact_ids": ["f.concealed.last_drink", "f.hpi.previous_withdrawal"], "evidence_rule": "met when both are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.risk", "criterion": "Asks directly about thoughts of self-harm", "kind": "safety", "linked_fact_ids": ["f.concealed.self_harm_thoughts"],
         "evidence_rule": "met when elicited; partly when asked but the patient does not open up", "critical": True, "rubric_domain": "rapport"},
        {"objective_id": "obj.tests", "criterion": "Examines for signs of withdrawal and requests blood tests", "kind": "action", "linked_requests": ["exam:general", "order:bmp", "order:lft"], "evidence_rule": "met when all are requested", "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the withdrawal risk", "kind": "reasoning", "linked_fact_ids": ["f.exam.general", "f.hpi.previous_withdrawal"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("mental_health_substance", "Alcohol, anxiety and withdrawal", "Adult with anxiety and under-reported alcohol use, from risky drinking to severe alcohol withdrawal.",
                    "anxiety and shakiness", ["alcohol", "drinking", "withdrawal", "anxiety", "depression", "suicidal", "overdose", "substance", "cocaine", "drug use", "mental health", "panic", "intoxicated", "addiction"],
                    facts, arts, objs,
                    dx(("Anxiety with risky alcohol use", "discharge", ["exam:general"], ["Generalised anxiety", "Alcohol use disorder", "Thyroid overactivity"]),
                       ("Alcohol withdrawal, moderate", "admit", ["exam:general", "order:bmp", "order:lft"], ["Alcohol withdrawal", "Anxiety disorder", "Infection", "Low blood sugar"]),
                       ("Severe alcohol withdrawal with seizure and hallucinations", "admit", ["exam:general", "order:bmp", "order:lft", "order:cbc", "order:glucose"], ["Delirium tremens", "Head injury", "Infection", "Other drug withdrawal"])),
                    ["Withdrawal usually begins within hours of the last drink and peaks at 24 to 72 hours: the time of the last drink matters.", "People under-report drinking when they expect judgement; normalise and ask for a typical day.",
                     "Ask every patient in this situation about thoughts of self-harm, directly."],
                    src("medlineplus_vitals", "medlineplus_alcohol_withdrawal", "niaaa_drinking_patterns", "niaaa_standard_drink", "medlineplus_bac", "medlineplus_cmp", "medlineplus_cbc", "medlineplus_bmp", "medlineplus_abg"),
                    ["f.concealed.alcohol_quantity", "f.concealed.last_drink", "f.concealed.self_harm_thoughts"])


def musculoskeletal():
    facts = [
        ch("f.chief_complaint.back_pain", {
            M: [o("Low back pain for three days after lifting a box", "My lower back has been hurting for three days, since I lifted a heavy box.")],
            MO: [o("Low back pain shooting down the left leg for a week", "My lower back hurts and it shoots down my left leg. It's been a week.")],
            S: [o("Severe low back pain with weakness in both legs and difficulty passing urine since yesterday", "My back pain is terrible, both my legs feel weak, and since yesterday I can't pee properly.")]},
           ["chief_complaint", "pain_back"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi", source_ids=["medlineplus_lbp"]),
        ch("f.hpi.onset_character", {
            M: [o("Began when lifting; dull ache across the lower back, 4/10; no leg pain", "It started when I lifted the box. A dull ache across my lower back. About a four. Nothing in my legs.")],
            MO: [o("Began gradually; sharp, burning pain from the left buttock to the outer calf, 7/10; worse sitting and coughing", "It came on gradually. A sharp burning pain from my left buttock down to the outside of my calf. A seven. Sitting and coughing make it worse.")],
            S: [o("Six weeks of worsening central back pain, now 8/10, worse at night and lying down", "It's been getting worse for six weeks. An eight now. It's worst at night when I lie down.")]},
           ["onset", "character", "severity", "radiation", "aggravating", "relieving", "duration"], critical=True, chart_section="hpi", source_ids=["medlineplus_lbp"]),
        ch("f.hpi.neuro_symptoms", {
            M: [o("No leg weakness, numbness or tingling", "No weakness, no numbness, no tingling.", polarity="negative")],
            MO: [o("Tingling on the outer left foot; no weakness noticed", "The outside of my left foot tingles. I haven't noticed any weakness.", polarity="positive")],
            S: [o("Both legs feel heavy; stumbled twice today; numbness around the inner thighs", "Both legs feel heavy and I stumbled twice today. The insides of my thighs are numb.", polarity="positive")]}, ["weakness_numbness"], critical=True, chart_section="hpi"),
        ch("f.concealed.bladder_bowel", {
            M: [o("Normal bladder and bowel control; no saddle numbness", "No trouble peeing or with my bowels. No numbness down there.", polarity="negative", rule="if_asked")],
            MO: [o("Normal bladder and bowel control; no saddle numbness", "No, all normal. No numbness between my legs.", polarity="negative", rule="if_asked")],
            S: [o("Has not been able to feel when the bladder is full since yesterday, leaked urine twice, and is numb when wiping",
                  "It's embarrassing. Since yesterday I can't tell when I need to go. I've leaked twice. And it's numb when I wipe.", cover_answer="That's all fine.", polarity="positive")]},
           ["red_flags_back", "urinary", "bowel", "saddle numbness", "bladder control"], rule="after_rapport", rapport_needed=3, critical=True, chart_section="hpi", source_ids=["medlineplus_lbp"]),
        ch("f.hpi.red_flags", {
            M: [o("No fever, weight loss, cancer history, injection drug use or steroid use; no significant trauma", "No fever, my weight's steady, I've never had cancer. No steroids, no injected drugs. I didn't fall.", polarity="negative")],
            MO: [o("No fever, weight loss, cancer history, injection drug use or steroid use; no significant trauma", "No fever, no weight loss, no cancer. No steroids. No fall.", polarity="negative")],
            S: [o("Lost about 6 kg in two months without trying; treated for cancer four years ago", "I've lost about six kilos in two months without trying. And I was treated for cancer four years ago.", polarity="positive")]},
           ["weight_change", "fever", "cancer", "history of cancer", "steroids", "night pain"], critical=True, chart_section="hpi", source_ids=["medlineplus_lbp"]),
        fx("f.hpi.self_treatment", "Has taken ibuprofen 400 mg three times a day with partial relief; using a heat pad", "Ibuprofen, 400, three times a day. It takes the edge off. And a heat pad.",
           ["relieving", "medications", "tried anything", "painkillers"], chart_section="hpi"),
        *background(
            pmh={M: GENERIC_PMH, MO: GENERIC_PMH,
                 S: [o("Cancer treated with surgery and radiotherapy four years ago, discharged from follow-up; hypertension", "I had cancer four years ago, surgery and radiation. They discharged me. And high blood pressure.", polarity="positive"),
                     o("Cancer treated four years ago, discharged from follow-up; no other conditions", "I had cancer four years ago. It was treated and they discharged me. Nothing else.", polarity="positive")]},
            meds={M: GENERIC_MEDS, MO: GENERIC_MEDS,
                  S: [o("Amlodipine 5 mg once daily", "Just amlodipine for my blood pressure."),
                      o("No regular prescription medicines", "Nothing on prescription.")]}),
        *vitals(((66, 88), (72, 96), (84, 108)), ((112, 136), (118, 142), (116, 148)), ((14, 18), (14, 18), (16, 20)), ((36.5, 37.2), (36.5, 37.2), (36.6, 37.6)), ((97, 99), (97, 99), (96, 99))),
        ch("f.exam.back", {
            M: [o("Tender paraspinal muscles on both sides; full leg strength; reflexes normal; straight leg raise negative")],
            MO: [o("Straight leg raise reproduces left leg pain at 40 degrees; reduced sensation over the outer left foot; ankle reflex reduced on the left; strength full")],
            S: [o("Midline tenderness over the lower lumbar spine; hip flexion and ankle dorsiflexion weak (4/5) in both legs; reduced sensation around the saddle area; ankle reflexes absent")]},
           ["back exam"], rule="on_request", request="exam:msk", knows=False, critical=True, chart_section="exam"),
        ch("f.exam.bladder_scan", {"any": [o("Bladder scan after voiding: 620 mL retained")]}, ["bladder scan"], rule="on_request", request="exam:abdomen", knows=False, critical=True, chart_section="exam", include={"min_severity": 0.67}),
        ch("f.imaging.mri", {
            M: [o("MRI not indicated at this visit: no warning signs present")],
            MO: [o("MRI lumbar spine: left-sided L5-S1 disc protrusion touching the S1 nerve root")],
            S: [o("MRI whole spine: destructive lesion in the L3 vertebral body with soft tissue compressing the cauda equina")]}, ["mri"], rule="on_request", request="order:mri", knows=False, critical=True, chart_section="imaging", source_ids=["medlineplus_lbp"]),
        num("f.lab.crp", "CRP", "mg/dL", ((0.05, 0.3), (0.1, 0.6), (2.5, 9.0)), "C-reactive protein {value} mg/dL", ["crp"], rule="on_request", request="order:crp", decimals=1,
            ref_high=0.3, ref_range="below 0.3 in most healthy adults", source_ids=["medlineplus_crp"], chart_section="labs"),
    ]
    arts = [
        text_art("art.mri", "document", "MRI spine (report)", "order:mri", {"from_fact": "f.imaging.mri"}, "Imaging is reserved for warning signs or pain that persists.", linked=["f.imaging.mri"], delay=2),
        lab_art("art.bloods", "Blood results", "order:crp", ["f.lab.crp"], "A raised CRP is not specific but supports looking for infection or cancer when warning signs are present."),
    ]
    objs = [
        {"objective_id": "obj.characterise", "criterion": "Characterises the pain and any leg symptoms", "kind": "elicit_fact", "linked_fact_ids": ["f.hpi.onset_character", "f.hpi.neuro_symptoms"],
         "evidence_rule": "met when both are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.red_flags", "criterion": "Screens for warning signs: bladder or bowel change, saddle numbness, weight loss, cancer, fever", "kind": "safety",
         "linked_fact_ids": ["f.concealed.bladder_bowel", "f.hpi.red_flags"], "evidence_rule": "met when both are elicited", "critical": True, "rubric_domain": "gathering",
         "feedback_missed": "Ask every back pain patient about bladder and bowel control and numbness between the legs. Patients are often embarrassed: explain why you ask."},
        {"objective_id": "obj.tests", "criterion": "Examines the back and legs", "kind": "action", "linked_requests": ["exam:msk"], "evidence_rule": "met when requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Images only when warning signs are present, and chooses a fitting disposition", "kind": "reasoning", "linked_fact_ids": ["f.exam.back"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("musculoskeletal", "Back pain", "Adult with low back pain, from a simple strain to sciatica to cauda equina compression.",
                    "back pain", ["back pain", "sciatica", "lower back", "joint pain", "knee pain", "shoulder pain", "neck pain", "musculoskeletal", "strain", "arthritis"],
                    facts, arts, objs,
                    dx(("Mechanical low back strain", "discharge", ["exam:msk"], ["Muscle strain", "Disc problem"]),
                       ("Sciatica from a lumbar disc protrusion", "discharge", ["exam:msk"], ["Lumbar radiculopathy", "Hip disease"]),
                       ("Cauda equina compression from a spinal lesion", "admit", ["exam:msk", "exam:abdomen", "order:mri", "order:crp"], ["Cauda equina syndrome", "Spinal metastasis", "Spinal infection"])),
                    ["Most acute low back pain needs no imaging at the first visit.", "Loss of bladder or bowel control, numbness around the saddle area, weight loss, a history of cancer or fever are warning signs that change everything.",
                     "Embarrassing symptoms come out when the clinician explains why the question matters."],
                    src("medlineplus_vitals", "medlineplus_lbp", "medlineplus_crp", "medlineplus_abg"), ["f.concealed.bladder_bowel"])


def other_medical():
    facts = [
        ch("f.chief_complaint.general", {
            M: [o("Tiredness and thirst for two weeks", "I've been really tired and thirsty for a couple of weeks.")],
            MO: [o("Thirst, frequent urination and blurred vision for a week", "I'm thirsty all the time, I pee constantly, and my vision has gone blurry. It's been a week.")],
            S: [o("Vomiting, abdominal pain and deep rapid breathing since yesterday after days of thirst", "I've been throwing up since yesterday and my stomach hurts. I can't stop breathing fast. I was thirsty for days before.")]},
           ["chief_complaint", "fatigue", "thirst"], rule="volunteered", critical=True, polarity="positive", chart_section="hpi", source_ids=["medlineplus_dka"]),
        ch("f.hpi.osmotic_symptoms", {
            M: [o("Drinking about three litres a day; up twice a night to urinate", "I'm drinking about three litres a day and I get up twice a night to pee.", polarity="positive")],
            MO: [o("Drinking four to five litres a day; urinating hourly, including at night", "Four or five litres a day. I pee every hour, even at night.", polarity="positive")],
            S: [o("Extreme thirst and constant urination for five days; today too nauseated to drink", "I couldn't drink enough for five days and I was peeing constantly. Today I'm too sick to drink.", polarity="positive")]},
           ["thirst", "urinary", "how much water", "duration", "onset"], critical=True, chart_section="hpi", source_ids=["medlineplus_dka"]),
        ch("f.hpi.weight_appetite", {
            M: [o("Weight steady; appetite normal", "My weight's the same. I'm eating normally.", polarity="negative")],
            MO: [o("Lost 4 kg in a month despite eating normally", "I've lost four kilos this month and I'm eating the same.", polarity="positive")],
            S: [o("Lost 6 kg in a month; no appetite for two days", "I've lost six kilos in a month. I haven't wanted food for two days.", polarity="positive")]}, ["weight_change", "appetite"], chart_section="hpi"),
        ch("f.hpi.gi_breathing", {
            M: [o("No vomiting, no abdominal pain, breathing normal", "No vomiting, no stomach pain, and my breathing's fine.", polarity="negative")],
            MO: [o("Mild nausea; no vomiting; breathing normal", "A bit of nausea. I haven't thrown up. Breathing's normal.", polarity="negative")],
            S: [o("Vomited six times; generalised abdominal pain; breathing fast and deep", "I've thrown up six times. My whole stomach hurts. I'm breathing hard and I can't slow it down.", polarity="positive")]},
           ["nausea_vomiting", "pain_abdomen", "sob", "associated_symptoms"], critical=True, chart_section="hpi", source_ids=["medlineplus_dka"]),
        fx("f.ros.infection_screen", "No cough, fever or urinary burning; no chest pain", "No cough, no fever, no burning when I pee. No chest pain.", ["fever", "cough", "pain_chest", "burning when you"], polarity="negative", chart_section="ros"),
        ch("f.concealed.insulin_rationing", {"any": [
            o("Has been taking half the prescribed insulin dose for three weeks, and none for the past two days, because of the cost",
              "I've been taking half my insulin for three weeks to make it last. The last two days I've had none. I can't afford the refill until payday.",
              cover_answer="I take my insulin like I'm told.", polarity="positive")]},
           ["adherence", "insulin", "are you taking your insulin", "insurance_access", "afford"], rule="after_rapport", rapport_needed=3, critical=True, chart_section="medications", include={"min_severity": 0.34}),
        *background(
            pmh={M: [o("No known medical conditions; last saw a doctor three years ago", "Nothing I know of. I haven't seen a doctor in three years.", polarity="negative"),
                     o("Hypertension; told two years ago that blood sugar was borderline", "High blood pressure. And two years ago they said my sugar was borderline.", polarity="positive")],
                 MO: [o("Type 1 diabetes since age 14", "Type 1 diabetes since I was fourteen.", polarity="positive"),
                      o("Type 2 diabetes for ten years, on insulin for two", "Type 2 diabetes for ten years. On insulin for the last two.", polarity="positive")],
                 S: [o("Type 1 diabetes since age 14", "Type 1 diabetes since I was fourteen.", polarity="positive"),
                     o("Type 2 diabetes for ten years, on insulin for two", "Type 2 diabetes for ten years. On insulin for the last two.", polarity="positive")]},
            meds={M: [o("No regular medicines", "I don't take anything."),
                      o("Amlodipine 5 mg once daily", "Just amlodipine for my blood pressure.")],
                  MO: [o("Prescribed insulin glargine 24 units at night and insulin lispro with meals", "I'm prescribed a long-acting insulin at night and a fast one with meals."),
                       o("Prescribed insulin glargine 30 units at night and metformin 1 g twice daily", "I'm prescribed insulin at night and metformin twice a day.")],
                  S: [o("Prescribed insulin glargine 24 units at night and insulin lispro with meals", "I'm prescribed a long-acting insulin at night and a fast one with meals."),
                      o("Prescribed insulin glargine 30 units at night and metformin 1 g twice daily", "I'm prescribed insulin at night and metformin twice a day.")]}),
        *vitals(((68, 90), (84, 104), (108, 134)), ((114, 138), (108, 132), (86, 110)), ((14, 18), (16, 20), (24, 34)), ((36.5, 37.2), (36.5, 37.3), (36.4, 37.6)), ((97, 99), (97, 99), (95, 99))),
        ch("f.exam.general", {
            M: [o("Looks well; moist mouth; normal breathing")],
            MO: [o("Dry mouth; skin slow to spring back; breathing normal; alert")],
            S: [o("Drowsy but answers questions; very dry mouth; deep rapid breathing; breath smells fruity; diffusely tender abdomen without guarding")]},
           ["general appearance", "hydration"], rule="on_request", request="exam:general", knows=False, critical=True, chart_section="exam", source_ids=["medlineplus_dka"]),
        num("f.lab.glucose", "Glucose", "mg/dL", ((142, 210), (290, 420), (440, 720)), "Blood glucose {value} mg/dL", ["blood sugar", "glucose"], rule="on_request", request="order:glucose", critical=True,
            ref_low=64, ref_high=100, ref_range="64-100 fasting", source_ids=["medlineplus_bmp"], chart_section="labs"),
        num("f.lab.bicarbonate", "Bicarbonate (CO2)", "mmol/L", ((23, 28), (20, 25), (6, 14)), "Bicarbonate {value} mmol/L", ["electrolytes", "bicarbonate"], rule="on_request", request="order:bmp", critical=True,
            ref_low=23, ref_high=29, ref_range="23-29", source_ids=["medlineplus_bmp"], chart_section="labs"),
        num("f.lab.potassium", "Potassium", "mEq/L", ((3.9, 4.8), (4.0, 5.0), (5.0, 6.2)), "Potassium {value} mEq/L", ["potassium"], rule="on_request", request="order:bmp", decimals=1,
            ref_low=3.7, ref_high=5.2, ref_range="3.7-5.2", source_ids=["medlineplus_bmp"], chart_section="labs"),
        num("f.lab.ph", "Venous pH", "", ((7.36, 7.42), (7.33, 7.40), (6.98, 7.24)), "Venous blood gas pH {value}", ["blood gas"], rule="on_request", request="order:abg", decimals=2,
            ref_low=7.38, ref_high=7.42, ref_range="7.38-7.42 (arterial, sea level)", source_ids=["medlineplus_abg"], chart_section="labs"),
        ch("f.lab.ketones", {
            M: [o("Urine ketones negative", value="negative", polarity="negative")],
            MO: [o("Urine ketones trace", value="trace")],
            S: [o("Urine ketones large", value="large", polarity="positive")]}, ["urinalysis", "ketones"], rule="on_request", request="order:urinalysis", knows=False, critical=True, chart_section="labs", source_ids=["medlineplus_urinalysis"]),
    ]
    arts = [
        lab_art("art.chemistry", "Chemistry", "order:bmp", ["f.lab.bicarbonate", "f.lab.potassium"], "Compare with the reference intervals; a low bicarbonate indicates acid in the blood."),
        lab_art("art.glucose", "Glucose", "order:glucose", ["f.lab.glucose"], "Compare with the fasting reference interval."),
        lab_art("art.gas", "Venous blood gas", "order:abg", ["f.lab.ph"], "A low pH with a low bicarbonate is a metabolic acidosis."),
        text_art("art.pharmacy", "medication_list", "Pharmacy dispensing record", "order:medication_list",
                 "Insulin: last supply dispensed about 9 weeks ago (intended to last 4 weeks). Other medicines collected on time.", "A gap in insulin collection; ask what got in the way.", section="records"),
    ]
    objs = [
        {"objective_id": "obj.characterise", "criterion": "Elicits thirst, urination, weight change and vomiting or breathing symptoms", "kind": "elicit_fact",
         "linked_fact_ids": ["f.hpi.osmotic_symptoms", "f.hpi.weight_appetite", "f.hpi.gi_breathing"], "evidence_rule": "met when all are elicited", "critical": True, "rubric_domain": "gathering"},
        {"objective_id": "obj.concealed", "criterion": "Finds out that insulin doses have been cut, and why", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.insulin_rationing"],
         "evidence_rule": "met when disclosed; partly when asked but the first answer is accepted", "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.tests", "criterion": "Checks glucose and requests chemistry and ketones", "kind": "action", "linked_requests": ["order:glucose", "order:bmp", "order:urinalysis"], "evidence_rule": "met when all are requested", "critical": True, "rubric_domain": "reasoning"},
        {"objective_id": "obj.disposition", "criterion": "Chooses a disposition that fits the metabolic picture", "kind": "reasoning", "linked_fact_ids": ["f.lab.glucose", "f.lab.bicarbonate"],
         "evidence_rule": "disposition matches the case's expected disposition, with a summary naming the key findings", "critical": True, "rubric_domain": "reasoning"},
    ]
    return template("other_medical", "General medical: high blood sugar", "Adult with a general medical complaint centred on high blood sugar, from new diabetes to diabetic ketoacidosis.",
                    "feeling unwell", ["diabetes", "blood sugar", "thirst", "tired", "fatigue", "weak", "dizzy", "hypertension", "blood pressure", "heart failure", "cholesterol", "dyslipidemia", "obesity", "general", "unwell", "medical"],
                    facts, arts, objs,
                    dx(("Newly recognised high blood sugar without acidosis", "discharge", ["order:glucose"], ["Type 2 diabetes", "Urinary infection", "Thyroid disease"]),
                       ("Marked hyperglycaemia without ketoacidosis", "admit", ["order:glucose", "order:bmp", "order:urinalysis"], ["Uncontrolled diabetes", "Early ketoacidosis", "Infection as a trigger"]),
                       ("Diabetic ketoacidosis", "admit", ["order:glucose", "order:bmp", "order:urinalysis", "order:abg"], ["Diabetic ketoacidosis", "Sepsis", "Acute abdomen"])),
                    ["Thirst, frequent urination, vomiting and deep rapid breathing in a person with diabetes suggest ketoacidosis.", "Missed insulin is a common trigger; cost is a common reason. Ask without blame.",
                     "Look for the trigger as well as treating the numbers."],
                    src("medlineplus_vitals", "medlineplus_dka", "medlineplus_bmp", "medlineplus_abg", "medlineplus_urinalysis"), ["f.concealed.insulin_rationing"])


BUILDERS = [chest_pain, respiratory, abdominal_pain, injury_trauma, neuro, infection_fever, mental_health_substance, musculoskeletal, other_medical]


def sim_keys(t: dict) -> dict:
    """Mirror each fact's value rule into the generic keys the simulator's latent-truth reader understands
    (`by_severity` with `range` / `options`, `values`, `p`), so the simulator and instantiate_case pick the same values.
    Facts in a choice_group are left to instantiate_case, which keeps the group consistent."""
    for f in t["facts"]:
        inc = f.get("include") or {}
        if "p" in inc:
            f["p"] = inc["p"]
        if f.get("choice_group"):
            continue
        if f["kind"] == "numeric":
            f["by_severity"] = {b: {"range": [float(x) if f.get("decimals") else int(x) for x in f["ranges"][b]]} for b in (M, MO, S)}
        elif f["kind"] == "choice":
            opts = f["options"]
            if "any" in opts:
                f["values"] = [x["statement"] for x in opts["any"]]
            else:
                f["by_severity"] = {b: {"options": [x["statement"] for x in opts[b]]} for b in (M, MO, S) if b in opts}
        else:
            f["value"] = f.get("value", f["statement"])
    t["standard_workup"] = list(TEMPLATE_WORKUP[t["id"]])
    also = {"chest_pain": {"f.exam.chest": ["exam:lungs", "exam:general"]}, "infection_fever": {"f.exam.abdomen": ["exam:general"]},
            "musculoskeletal": {"f.exam.back": ["exam:neuro"]}, "other_medical": {"f.exam.general": ["exam:abdomen", "exam:lungs"]},
            "mental_health_substance": {"f.exam.general": ["exam:neuro", "exam:mental_status"]}, "respiratory": {"f.exam.lungs": ["exam:general"]},
            "injury_trauma": {"f.exam.msk": ["exam:general"], "f.exam.neuro": ["exam:mental_status"]}, "neuro": {"f.exam.neuro": ["exam:mental_status", "exam:general"]},
            "abdominal_pain": {"f.exam.abdomen": ["exam:general"]}}.get(t["id"], {})
    for f in t["facts"]:
        if f["fact_id"] in also:
            f["disclosure"]["also_requests"] = also[f["fact_id"]]
    for d in t["diagnoses"]:
        d["label"] = d["diagnosis"]
    t["diagnoses_ordered_by_severity"] = True
    return t


def main() -> int:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    header = ("# Condition template (catalog/conditions). SYNTHETIC teaching content authored for HospitalGym; needs faculty review.\n"
              "# Generated by encounter/tools/build_templates.py - edit there or here; `facts` is read by the simulator (latent truth)\n"
              "# and by encounter.templates.instantiate_case. Reference intervals: see `sources`. Everything else: authored, unsourced.\n")
    for b in BUILDERS:
        t = sim_keys(b())
        path = TEMPLATES_DIR / f"{t['id']}.yaml"
        path.write_text(header + yaml.safe_dump(t, sort_keys=False, allow_unicode=True, width=160))
        print(f"{path.name}: {len(t['facts'])} fact templates, {len(t['artifacts'])} artifacts, {len(t['objectives'])} objectives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
