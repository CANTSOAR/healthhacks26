"""Run-time loader for the organizers' sample patients (never committed).

When `.private/` holds the organizers' faculty-provided sample patient CSV, each row is turned into a
published case in the gitignored data dir: background lines become askable social facts, measurements in the
notes become chart values, hidden habits become concealed facts (released only after rapport, with a
generic cover answer), "needs ..." lines become counselling objectives, and the photo is attached.

Nothing here contains the organizers' text: the code only knows generic patterns. The patient wording is
auto-drafted from third-person notes, so every case is flagged needs_faculty_review. When the CSV is
absent this module does nothing and the app still works with the tracked seed cases.
"""
from __future__ import annotations

import csv
import re

from rapidfuzz import fuzz

from .paths import sample_patient_images, sample_patients_csv
from .store import _VERB_3RD, CaseStore, default_store, slugify
from .validate import validate_case

# common occupation words (generic list; nothing here is taken from the organizers' profiles)
_JOB_WORDS = (r"student|employee|professional|associate|volunteer|retired|driver|nurse|teacher|worker|clerk|engineer|manager|mechanic|technician|"
              r"cleaner|janitor|cook|chef|farmer|officer|assistant|operator|producer|designer|accountant|electrician|plumber|carpenter|cashier|"
              r"waiter|waitress|builder|programmer|analyst|consultant|artist|musician|writer|lawyer|pilot|soldier|caregiver|homemaker|unemployed")

_HABITS = [
    # topic, pattern, rule, rapport_needed, generic cover answer (own wording)
    ("smoking", r"\bsmok|cigarette|\bvap|tobacco", "if_asked", 0, ""),
    ("alcohol", r"alcohol|\bdrinks?\b|hard drinks|\bbeer|\bwine\b|liquor", "after_rapport", 3, "I drink socially, like anyone."),
    ("drugs", r"cocaine|heroin|opioid|marijuana|cannabis|\bmeth\b|intranasal|recreational", "after_rapport", 4, "No, nothing like that."),
    ("sexual_history", r"sexual|condom|partners?\b", "after_rapport", 3, "I'd rather not get into that."),
    ("bowel", r"constipat|bowel|stool", "after_rapport", 3, "Everything's fine there."),
    ("diet", r"noncomplian|non-complian|dislikes? (?:fruits?|vegetables?)", "after_rapport", 2, "I eat okay, I guess."),
    ("adherence", r"discomfort with taking|doesn'?t take|skips?|misses doses", "after_rapport", 3, "I do what I'm told, more or less."),
    ("healthcare_trust", r"mistrust|distrust|skeptic|dislikes students", "after_rapport", 2, "It's fine. Let's just get on with it."),
    ("health_understanding", r"struggles to understand|confused about|didn'?t understand|uncertain(?:ty)? about|overwhelmed", "after_rapport", 2, "I think I've got it, mostly."),
]
_SOCIAL = [
    ("occupation", _JOB_WORDS + r"|works?\b|career|degree|college|school|university"),
    ("living_situation", r"\blives?\b|married|alone|siblings|family|support"),
    ("exercise", r"walks?\b|plays?\b|runs?\b|swims?\b|cycl|gym|exercise|sport|football|soccer|tennis|cricket|basketball|yoga"),
    ("diet", r"vegetarian|vegan|diet"),
]
_MEASURES = [
    ("bmi", "Body mass index", r"\bBMI\s*(?:of|is)?\s*(\d+(?:\.\d+)?)", "kg/m2", "vitals"),
    ("total_cholesterol", "Total cholesterol", r"Total Chol(?:esterol)?\s*(\d+)", "mg/dL", "lab"),
    ("ldl", "LDL cholesterol", r"\bLDL\s*(\d+)", "mg/dL", "lab"),
    ("hdl", "HDL cholesterol", r"\bHDL\s*(\d+)", "mg/dL", "lab"),
    ("blood_pressure", "Blood pressure", r"\bBP\s*(\d{2,3}/\d{2,3})", "mmHg", "vitals"),
    ("waist", "Waist circumference", r"\bWC\s*(?:of)?\s*(\d+(?:\.\d+)?)", "inches", "vitals"),
]
_NEEDS = re.compile(r"\bneeds?\b|key for\b", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("“", '"').replace("”", '"').replace("’", "'").strip().strip('"').strip())


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"])|;\s*", re.sub(r"\b(vs|e\.g|i\.e|approx|Dr|Mr|Mrs|Ms)\.", r"\1", _clean(text)))
    out = []
    for p in parts:
        p = p.strip().strip('"').strip()
        if len(p) > 2:
            out.append(p.rstrip("."))
    return out


def _split_habits(sentence: str) -> list[str]:
    """'X and uses Y' -> ['X', 'uses Y'] when both halves carry their own habit verb."""
    parts = re.split(r"\s+and\s+(?=(?:uses?|smokes?|drinks?|consumes?|takes?|vapes?|injects?)\b)", sentence)
    return [p.strip() for p in parts if p.strip()]


_JOB = re.compile(_JOB_WORDS, re.I)


def _lower_first(s: str) -> str:
    w = s.split(" ", 1)
    if w and not w[0].isupper():          # keep acronyms such as IT, TV, MS
        w[0] = w[0][0].lower() + w[0][1:]
    return " ".join(w)


def _base_verb(v: str) -> str:
    low = v.lower()
    if low in _VERB_3RD:
        return _VERB_3RD[low]
    if low.endswith(("ches", "shes", "sses", "xes")):
        return low[:-2]
    if low.endswith("ies"):
        return low[:-3] + "y"
    return low[:-1] if low.endswith("s") and not low.endswith("ss") else low


def _first_person(sentence: str, name: str) -> str:
    """Generic third-person note -> first-person draft. Wording is auto-drafted and flagged for review."""
    s = re.sub(r"\s*\([^)]*\)", "", sentence)                                   # patients do not recite bracketed values
    s = re.sub(r"\b(?:and\s+)?(?:a\s+)?(?:BMI|WC)\s+(?:of|is)\s+[\d.]+(?:\s+inches)?", "", s)
    s = re.sub(r",\s*,", ",", re.sub(r"\s+,", ",", re.sub(r"\s{2,}", " ", s))).strip().rstrip(".").strip(", ")
    if len(s) < 3:
        return ""
    first = name.split()[0] if name else ""
    subj = r"(?:He|She|They" + (("|" + re.escape(first)) if first else "") + r")"
    s = re.sub(rf"\b{subj}\s+(\w+)", lambda m: "I " + _base_verb(m.group(1)), s)
    s = re.sub(r"\b(his|her)\b(?=\s+[a-z])", "my", s, flags=re.I)
    s = re.sub(r"\bnon-?compliant with\b", "not great at sticking to my", s, flags=re.I)
    low = s.lower()
    if re.match(r"^i\b", low):
        pass
    elif re.match(r"^(college|university|school)\s+in\b", low):
        s = "I went to " + _lower_first(s)
    elif low.split(" ", 1)[0] in _VERB_3RD:
        w = s.split(" ", 1)
        s = "I " + _VERB_3RD[w[0].lower()] + (" " + w[1] if len(w) > 1 else "")
    elif re.match(r"^[a-z]+s\s+(\d|an? |the |one |two |about |some |my |up to )", low):
        w = s.split(" ", 1)                                    # an unlisted third-person verb followed by a quantity
        s = "I " + _base_verb(w[0]) + " " + w[1]
    elif re.match(r"^(recently\s+)?diagnosed\b", low):
        s = "I was " + _lower_first(s)
    elif re.match(r"^recent\s", low):
        s = "I'm a " + _lower_first(s)
    elif _JOB.search(s) and len(s.split()) <= 14:
        ls = _lower_first(s)
        s = "I'm " + ("an " if ls[0].lower() in "aeiou" or ls.split()[0] in ("IT", "MRI") else "a ") + ls
    elif re.match(r"^(\w+ly\s+\w+|living|recovering|not great|\w+ed)\b", low):
        s = "I'm " + _lower_first(s)
    else:
        s = "What I can say is: " + _lower_first(s)
    # verbs later in the sentence that still agree with he/she
    s = re.sub(r"(,|\band\b|\bbut\b)\s+(is)\b", r"\1 am", s)
    s = re.sub(r"(,|\band\b|\bbut\b)\s+(\w+s)\b", lambda m: f"{m.group(1)} {_base_verb(m.group(2))}" if m.group(2).lower() in _VERB_3RD else m.group(0), s)
    s = re.sub(r"\bI came in with\b", "I get", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[0].upper() + s[1:] + "."


def _image_for(name: str) -> str | None:
    best, score = None, 0
    for p in sample_patient_images():
        sc = fuzz.partial_ratio(name.lower(), p.stem.lower())
        if sc > score:
            best, score = p, sc
    return str(best) if best is not None and score >= 80 else None


def build_case_from_row(row: dict) -> dict:
    name = _clean(row.get("patient-name") or "Sample patient")
    try:
        age = int(float(_clean(row.get("age") or "40")))
    except ValueError:
        age = 40
    gender = _clean(row.get("gender") or "unspecified").lower()
    background = _clean(row.get("background") or "")
    notes = _clean(row.get("notes") or "")
    summary = _clean(row.get("summary") or "")
    facts: list[dict] = []
    objectives: list[dict] = []
    used: set[str] = set()

    def fid(cat: str, slug: str) -> str:
        base = f"f.{cat}.{slugify(slug, 'item').replace('-', '_')[:28]}"
        out, n = base, 2
        while out in used:
            out, n = f"{base}_{n}", n + 1
        used.add(out)
        return out

    # what the patient is here about: only the non-habit items of the summary are voiced
    items = [i.strip() for i in re.split(r",|\band\b", summary) if i.strip()]
    habit_pat = "|".join(p for _, p, *_ in _HABITS[:6]) + r"|user\b|abuse"
    medical = [i for i in items if not re.search(habit_pat, i, re.I) and not re.search(r"vegetarian|vegan|frequent flier", i, re.I)]
    def spoken(item: str) -> str:
        return " ".join(w if w.isupper() else w.lower() for w in item.split())

    first_item = spoken(medical[0]) if medical else ""
    if not first_item:
        reason_line = "I was told to come in for a health review."
    elif re.match(r"^\w+ing\b", first_item):
        reason_line = f"I'm here because I'm {first_item}."
    elif " with " in first_item:
        reason_line = f"I'm here about my {first_item.split(' with ', 1)[1]}."
    else:
        reason_line = f"I'm here about my {first_item}."
    facts.append({"fact_id": fid("chief_complaint", "visit_reason"), "category": "chief_complaint",
                  "statement": ("Attending about: " + ", ".join(medical)) if medical else "Attending for a health review",
                  "patient_knows": True, "patient_answer": reason_line,
                  "topics": ["chief_complaint", "pmh"] + [m.lower() for m in medical], "disclosure": {"rule": "volunteered"},
                  "critical": True, "chart_section": "hpi", "patient_answer_auto": True})

    for s in _sentences(background):
        topics = [k for k, pat in _SOCIAL if re.search(pat, s, re.I)] or ["social_history"]
        facts.append({"fact_id": fid("social", topics[0]), "category": "social", "statement": s, "patient_knows": True,
                      "patient_answer": _first_person(s, name), "topics": topics + ["social_history"], "disclosure": {"rule": "if_asked"},
                      "chart_section": "social", "patient_answer_auto": True})

    rows = []
    for key, label, pat, unit, cat in _MEASURES:
        m = re.search(pat, notes, re.I)
        if not m:
            continue
        raw = m.group(1)
        val = raw if "/" in raw else (float(raw) if "." in raw else int(raw))
        f_id = fid(cat, key)
        facts.append({"fact_id": f_id, "category": cat, "label": label, "statement": f"{label} {raw} {unit}", "value": val, "unit": unit,
                      "patient_knows": False, "topics": [label.lower()], "disclosure": {"rule": "chart_initial"},
                      "chart_section": "vitals" if cat == "vitals" else "labs"})
        rows.append({"test": label, "value": val, "unit": unit, "ref_range": "", "flag": "", "fact_id": f_id})

    teaching = []
    raw_notes = row.get("notes") or ""
    quoted_spans = [_clean(q) for q in re.findall(r"\u201c([^\u201d]*)(?:\u201d|$)", raw_notes) if len(q.split()) >= 5]
    for s in _sentences(notes):
        quoted = any(s.rstrip(".") in q for q in quoted_spans)
        if quoted and not _NEEDS.search(s):
            facts.append({"fact_id": fid("hpi", "own_words"), "category": "hpi", "statement": f'Patient says: "{s}"', "patient_knows": True,
                          "patient_answer": s + ".", "topics": ["health_understanding", "patient_concerns", "what did your doctor tell you"],
                          "disclosure": {"rule": "if_asked"}, "chart_section": "hpi"})
            continue
        if _NEEDS.search(s):
            teaching.append(s)
            objectives.append({"objective_id": "obj.counsel_" + str(len(objectives) + 1), "criterion": "Addresses what this patient needs: " + s[:160],
                               "kind": "communication", "evidence_rule": "explains in plain words, checks understanding, invites questions",
                               "rubric_domain": "explanation"})
            continue
        for part in _split_habits(s):
            hit = next(((t, rule, need, cover) for t, pat, rule, need, cover in _HABITS if re.search(pat, part, re.I)), None)
            only_measures = bool(rows) and not hit and re.fullmatch(r"[^a-z]*(?:[A-Z][\w ]*\s+has a\s+)?(?:BMI|WC|BP|Total|LDL|HDL|and|of|a|[\d\s.,()/:%]|mmHg|inches|dyslipidemia|Chol)+[^a-z]*", part)
            if only_measures:
                continue
            if hit:
                topic, rule, need, cover = hit
                concealed = rule != "if_asked"
                f = {"fact_id": fid("concealed" if concealed else "social", topic), "category": "concealed" if concealed else "social",
                     "statement": part, "patient_knows": True, "patient_answer": _first_person(part, name),
                     "topics": [topic], "disclosure": {"rule": rule}, "chart_section": "social", "patient_answer_auto": True,
                     "polarity": "positive"}
                if concealed:
                    f["disclosure"]["rapport_needed"] = need
                    f["cover_answer"] = cover
                    f["critical"] = True
                    f["patient_answer"] = "Okay, honestly. " + f["patient_answer"]
                    objectives.append({"objective_id": f"obj.uncover_{topic}_{len(objectives) + 1}", "criterion": f"Builds enough trust for the patient to talk openly about {topic.replace('_', ' ')}",
                                       "kind": "elicit_fact", "linked_fact_ids": [f["fact_id"]], "evidence_rule": "met when the patient discloses it",
                                       "critical": True, "rubric_domain": "listening"})
                facts.append(f)
            elif _first_person(part, name):
                facts.append({"fact_id": fid("hpi", "context"), "category": "hpi", "statement": part, "patient_knows": True,
                              "patient_answer": _first_person(part, name), "topics": ["patient_concerns", "mood", "social_history"],
                              "disclosure": {"rule": "if_asked"}, "chart_section": "hpi", "patient_answer_auto": True})

    askable_social = [f["fact_id"] for f in facts if f["category"] == "social"]
    if askable_social:
        objectives.append({"objective_id": "obj.social_context", "criterion": "Explores the patient's work, home and daily life", "kind": "elicit_fact",
                           "linked_fact_ids": askable_social[:3], "evidence_rule": "met when the linked background is elicited", "rubric_domain": "gathering"})
    objectives += [
        {"objective_id": "obj.rapport", "criterion": "Acknowledges the patient's feelings and uses non-judging language", "kind": "communication",
         "evidence_rule": "empathic or normalising statements in the transcript", "rubric_domain": "rapport"},
        {"objective_id": "obj.structure", "criterion": "Runs a structured interview: introduction, open question first, summary, clear close", "kind": "sequencing",
         "evidence_rule": "three of: introduction, early open question, summary, closing", "rubric_domain": "opening"},
    ]
    artifacts = [{"artifact_id": "art.referral", "kind": "document", "title": "Referral summary", "section_id": "triage", "release": {"rule": "initial"},
                  "content": f"{name}, {age}. " + (("Known: " + ", ".join(medical) + ".") if medical else "Referred for a health review."),
                  "synthetic": True, "linked_fact_ids": [], "source_ids": ["organizer_sample"]},
                 {"artifact_id": "art.prior_note", "kind": "prior_note", "title": "Previous clinic note", "section_id": "records",
                  "release": {"rule": "on_request", "request": "order:prior_records"},
                  "content": "Last clinic visit: " + (", ".join(medical) if medical else "routine review") + ". Lifestyle history was not completed at that visit.",
                  "synthetic": True, "linked_fact_ids": [], "source_ids": ["organizer_sample"]}]
    if rows:
        artifacts.append({"artifact_id": "art.measurements", "kind": "lab_report", "title": "Recent measurements and results", "section_id": "labs",
                          "release": {"rule": "initial"}, "content": rows, "synthetic": True, "linked_fact_ids": [r["fact_id"] for r in rows],
                          "source_ids": ["organizer_sample"]})
    image = _image_for(name)
    profile = {"name": name, "age": age, "gender": gender, "background": background, "personality": _clean(row.get("personality") or ""),
               "race_ethnicity": _clean(row.get("race/ethinicity") or row.get("race/ethnicity") or "")}
    if image:
        profile["image"] = image
    case = {
        "schema_version": 1, "case_id": "sample-" + slugify(name), "version": 1, "status": "published",
        "title": f"{name}, {age}", "origin": {"kind": "from_sample_patient", "sample_patient_uuid": _clean(row.get("patient-uuid") or "")},
        "review": {"author": "Built at run time from the organizers' sample patient profile", "needs_faculty_review": True, "synthetic": True},
        "intended_learner": "Health professions students", "learner_role": "Clinician in training", "setting": "Clinic or ward consultation",
        "prebrief": f"You are meeting {name}, {age}. Read the referral summary, take a history that includes daily life and habits, and respond to what this patient needs.",
        "profile": {k: v for k, v in profile.items() if v not in ("", None)},
        "faculty_truth": {"diagnosis": summary, "teaching_points": teaching},
        "facts": facts,
        "chart": {"sections": [{"section_id": "triage", "title": "Referral", "release": "initial"}, {"section_id": "vitals", "title": "Measurements", "release": "initial"},
                               {"section_id": "labs", "title": "Results", "release": "initial"}, {"section_id": "hpi", "title": "History", "release": "on_fact"},
                               {"section_id": "social", "title": "Social history", "release": "on_fact"}, {"section_id": "records", "title": "Previous records", "release": "on_request"}],
                  "artifacts": artifacts},
        "objectives": objectives, "rubric_id": "default",
        "sources": [{"source_id": "organizer_sample", "title": "Organizers' faculty-provided sample patient profile (private resource pack, read at run time)", "role": "organizer_sample"}],
        "unknown_response": "I'm not sure. I can't really tell you anything about that.",
    }
    return case


def load_sample_rows() -> list[dict]:
    path = sample_patients_csv()
    if not path:
        return []
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return [r for r in csv.DictReader(fh) if (r.get("patient-name") or "").strip()]
    except Exception:
        return []


def ensure_sample_cases(store: CaseStore | None = None) -> list[dict]:
    """Build (or refresh) the sample-patient cases in the data dir. Returns [{case_id, ok, errors}]."""
    store = store or default_store()
    out = []
    for row in load_sample_rows():
        try:
            case = build_case_from_row(row)
            rep = validate_case(case)
            if rep["ok"]:
                saved = store.save_published(case)
                out.append({"case_id": saved["case_id"], "version": saved["version"], "ok": True, "warnings": len(rep["warnings"])})
            else:
                case["status"] = "draft"
                out.append({"case_id": case["case_id"], "ok": False, "errors": rep["errors"][:5], "consistency": rep["consistency"][:5]})
        except Exception as e:  # noqa: BLE001 - a malformed row must never stop the app
            out.append({"case_id": None, "ok": False, "errors": [{"path": "", "message": f"{type(e).__name__}: {e}"}]})
    return out
