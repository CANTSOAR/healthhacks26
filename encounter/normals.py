"""Standard workup and default normal results.

When a learner requests a standard test or examination that the case does not define, the encounter returns the
unremarkable result below instead of "not available" (ledger rule `template_default_normal`). These results are
SYNTHETIC defaults authored for this project, shown with a "default normal" marker, never added to the case's facts,
and not evidence for any objective. Reference intervals follow the MedlinePlus pages cited in the condition templates;
the troponin and D-dimer wording is authored, unsourced.

Which requests are offered: the case's own requests, plus `case["standard_workup"]` if present, else the
`standard_workup` of the case's condition template, else GENERIC_WORKUP. A request outside that list returns
"not available in this scenario" and is not written back as an order.
"""
from __future__ import annotations


def _rows(*r):
    return [{"test": t, "value": v, "unit": u, "ref_range": ref, "flag": ""} for t, v, u, ref in r]


NORMALS: dict[str, dict] = {
    "order:cbc": {"kind": "lab_report", "title": "Blood count", "content": _rows(("WBC", 7.2, "x10^3/mcL", "4.5-11.0"), ("Hemoglobin", 14.1, "g/dL", "12-18"), ("Platelets", 250, "x10^3/mcL", "150-400"), ("MCV", 90, "fL", "80-100"))},
    "order:bmp": {"kind": "lab_report", "title": "Basic metabolic panel", "content": _rows(("Sodium", 140, "mEq/L", "136-144"), ("Potassium", 4.2, "mEq/L", "3.7-5.2"), ("Bicarbonate (CO2)", 25, "mmol/L", "23-29"), ("BUN", 14, "mg/dL", "6-20"), ("Creatinine", 0.9, "mg/dL", "0.8-1.2"), ("Glucose", 92, "mg/dL", "64-100"))},
    "order:lft": {"kind": "lab_report", "title": "Liver tests", "content": _rows(("ALT", 22, "U/L", "4-36"), ("AST", 20, "U/L", "8-33"), ("ALP", 70, "U/L", "20-130"), ("Total bilirubin", 0.6, "mg/dL", "0.1-1.2"))},
    "order:lipase": {"kind": "lab_report", "title": "Lipase", "content": _rows(("Lipase", 40, "U/L", "0-160"))},
    "order:lactate": {"kind": "lab_report", "title": "Lactate", "content": _rows(("Lactate", 1.1, "mmol/L", "0.5-2.2"))},
    "order:glucose": {"kind": "lab_report", "title": "Point-of-care glucose", "content": _rows(("Glucose", 96, "mg/dL", "64-100 fasting"))},
    "order:crp": {"kind": "lab_report", "title": "C-reactive protein", "content": _rows(("CRP", 0.2, "mg/dL", "below 0.3"))},
    "order:troponin": {"kind": "lab_report", "title": "Troponin", "content": _rows(("Troponin (high-sensitivity)", 5, "ng/L", "below 14 (assay-specific; authored)"))},
    "order:bnp": {"kind": "lab_report", "title": "BNP", "content": _rows(("BNP", 40, "pg/mL", "below 100"))},
    "order:d_dimer": {"kind": "lab_report", "title": "D-dimer", "content": _rows(("D-dimer", "negative", "", "negative"))},
    "order:coags": {"kind": "lab_report", "title": "Coagulation", "content": _rows(("INR", 1.0, "", "0.8-1.2 (authored)"))},
    "order:abg": {"kind": "lab_report", "title": "Blood gas", "content": _rows(("pH", 7.40, "", "7.38-7.42"), ("PaCO2", 40, "mmHg", "38-42"), ("PaO2", 90, "mmHg", "75-100"), ("Bicarbonate", 24, "mmol/L", "22-28"))},
    "order:urinalysis": {"kind": "lab_report", "title": "Urinalysis", "content": _rows(("Nitrites", "negative", "", "negative"), ("White cells", "none", "", "none"), ("Blood", "none", "", "none"), ("Glucose", "none", "", "none"), ("Ketones", "none", "", "none"))},
    "order:urine_culture": {"kind": "lab_report", "title": "Urine culture", "content": "No growth (preliminary)."},
    "order:blood_cultures": {"kind": "lab_report", "title": "Blood cultures", "content": "No growth to date (preliminary)."},
    "order:pregnancy_test": {"kind": "lab_report", "title": "Urine pregnancy test", "content": _rows(("Urine hCG", "negative", "", "negative")), "only": "female_under_55"},
    "order:tox_screen": {"kind": "lab_report", "title": "Urine drug screen", "content": _rows(("Cocaine metabolite", "not detected", "", "not detected"), ("Amphetamines", "not detected", "", "not detected"), ("Opiates", "not detected", "", "not detected"), ("Cannabinoids", "not detected", "", "not detected"), ("Benzodiazepines", "not detected", "", "not detected"))},
    "order:ethanol": {"kind": "lab_report", "title": "Blood alcohol level", "content": _rows(("Ethanol", "not detected", "", "not detected"))},
    "order:covid_flu_swab": {"kind": "lab_report", "title": "Respiratory viral swab", "content": _rows(("Influenza A/B", "not detected", "", "not detected"), ("SARS-CoV-2", "not detected", "", "not detected"))},
    "order:ecg": {"kind": "ecg", "title": "12-lead ECG (text description)", "content": "Sinus rhythm. Normal axis and intervals. No ST segment or T wave changes."},
    "order:chest_xray": {"kind": "xray", "title": "Chest X-ray (report)", "content": "Clear lungs. Normal heart size. No effusion or pneumothorax."},
    "order:xray": {"kind": "xray", "title": "X-ray (report)", "content": "No fracture or dislocation seen."},
    "order:ct_head": {"kind": "ct", "title": "CT head (report)", "content": "No bleeding, mass or established infarct."},
    "order:ct_abdomen": {"kind": "ct", "title": "CT abdomen and pelvis (report)", "content": "No acute abnormality."},
    "order:ct_chest": {"kind": "ct", "title": "CT chest (report)", "content": "No pulmonary embolus. Lungs clear."},
    "order:ultrasound": {"kind": "document", "title": "Ultrasound (report)", "content": "No abnormality seen."},
    "order:mri": {"kind": "document", "title": "MRI (report)", "content": "No abnormality seen."},
    "order:prior_records": {"kind": "prior_note", "title": "Previous records", "content": "No previous records on file at this hospital."},
    "order:medication_list": {"kind": "medication_list", "title": "Pharmacy dispensing record", "content": "No dispensing record found."},
    "exam:general": {"kind": "document", "title": "General examination", "content": "Nothing further of note on general inspection beyond the triage observations."},
    "exam:vitals": {"kind": "document", "title": "Repeat vital signs", "content": "Repeat vital signs are unchanged from triage."},
    "exam:cardiac": {"kind": "document", "title": "Cardiac examination", "content": "Regular rhythm, normal heart sounds, no murmur."},
    "exam:lungs": {"kind": "document", "title": "Chest examination", "content": "Clear to auscultation with equal air entry."},
    "exam:abdomen": {"kind": "document", "title": "Abdominal examination", "content": "Soft, not tender, no masses, normal bowel sounds."},
    "exam:neuro": {"kind": "document", "title": "Neurological examination", "content": "Alert and oriented. Cranial nerves, strength, sensation and coordination normal."},
    "exam:msk": {"kind": "document", "title": "Musculoskeletal examination", "content": "No deformity, swelling or bony tenderness; full range of movement."},
    "exam:skin": {"kind": "document", "title": "Skin examination", "content": "No rash or wounds."},
    "exam:heent": {"kind": "document", "title": "Head and neck examination", "content": "Throat, ears and neck unremarkable."},
    "exam:extremities": {"kind": "document", "title": "Limb examination", "content": "No swelling; calves soft; pulses present."},
    "exam:mental_status": {"kind": "document", "title": "Mental status", "content": "Oriented to person, place and time."},
}

_COMMON = ["exam:general", "exam:vitals", "order:prior_records", "order:medication_list"]
GENERIC_WORKUP = ["order:cbc", "order:bmp", "order:ecg", "order:urinalysis", "order:glucose", "exam:cardiac", "exam:lungs", "exam:abdomen"] + _COMMON
TEMPLATE_WORKUP = {
    "chest_pain": ["order:ecg", "order:troponin", "order:cbc", "order:bmp", "order:chest_xray", "order:d_dimer", "order:tox_screen", "exam:cardiac", "exam:lungs"] + _COMMON,
    "respiratory": ["order:chest_xray", "order:cbc", "order:bmp", "order:lactate", "order:abg", "order:covid_flu_swab", "order:ecg", "order:blood_cultures", "exam:lungs", "exam:cardiac"] + _COMMON,
    "abdominal_pain": ["order:cbc", "order:bmp", "order:lft", "order:lipase", "order:urinalysis", "order:pregnancy_test", "order:ct_abdomen", "order:ultrasound", "order:lactate", "order:ecg", "exam:abdomen"] + _COMMON,
    "injury_trauma": ["order:xray", "order:ct_head", "order:cbc", "order:bmp", "order:coags", "order:ethanol", "order:ecg", "exam:msk", "exam:neuro", "exam:skin"] + _COMMON,
    "neuro": ["order:glucose", "order:ct_head", "order:ecg", "order:cbc", "order:bmp", "order:coags", "exam:neuro", "exam:cardiac", "exam:mental_status"] + _COMMON,
    "infection_fever": ["order:urinalysis", "order:urine_culture", "order:cbc", "order:bmp", "order:lactate", "order:blood_cultures", "order:crp", "order:chest_xray", "order:pregnancy_test", "exam:abdomen", "exam:lungs", "exam:skin"] + _COMMON,
    "mental_health_substance": ["order:bmp", "order:lft", "order:cbc", "order:glucose", "order:ethanol", "order:tox_screen", "order:ecg", "exam:neuro", "exam:mental_status"] + _COMMON,
    "musculoskeletal": ["order:xray", "order:mri", "order:crp", "order:cbc", "order:urinalysis", "exam:msk", "exam:neuro", "exam:abdomen"] + _COMMON,
    "other_medical": ["order:glucose", "order:bmp", "order:urinalysis", "order:abg", "order:cbc", "order:ecg", "order:lactate", "exam:abdomen", "exam:cardiac", "exam:lungs"] + _COMMON,
}


def workup_for(case: dict) -> list[str]:
    if isinstance(case.get("standard_workup"), list):
        return [str(r).lower() for r in case["standard_workup"]]
    tid = str((case.get("origin") or {}).get("condition_template") or "")
    if tid in TEMPLATE_WORKUP:
        try:
            from .templates import get_template
            w = get_template(tid).get("standard_workup")
            if isinstance(w, list) and w:
                return [str(r).lower() for r in w]
        except Exception:
            pass
        return list(TEMPLATE_WORKUP[tid])
    return list(GENERIC_WORKUP)


def default_result(case: dict, request: str) -> dict | None:
    n = NORMALS.get(request)
    if not n:
        return None
    if n.get("only") == "female_under_55":
        p = case.get("profile") or {}
        if str(p.get("gender", "")).lower() not in ("female", "f", "woman") or int(p.get("age") or 0) >= 55:
            return {"request": request, "kind": "document", "title": n["title"], "content": "Not applicable for this patient.", "synthetic": True,
                    "default_normal": True, "note": "Not applicable."}
    return {"request": request, "kind": n["kind"], "title": n["title"], "content": n["content"], "synthetic": True, "default_normal": True,
            "note": "Default normal result (synthetic): this scenario does not define this test, so an unremarkable result is shown."}
