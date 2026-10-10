"""Case validation: JSON schema plus reference, disclosure, reachability and consistency checks.

Returns {ok, errors: [{path, message}], warnings: [{path, message}], consistency: [{level, kind, message, paths}]}.
Validation finds structural problems and explicit contradictions. It cannot establish medical
correctness: faculty review is still required.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from jsonschema import Draft202012Validator

from . import taxonomy as tx
from .paths import CONTRACTS_DIR

PATIENT_VOICED = ("volunteered", "if_asked", "after_rapport", "denied_until_confronted")

DRUG_CLASSES = {
    "penicillin": ["penicillin", "amoxicillin", "ampicillin", "augmentin", "amoxicillin-clavulanate", "piperacillin",
                   "flucloxacillin", "dicloxacillin", "co-amoxiclav"],
    "sulfa": ["sulfa", "sulfamethoxazole", "bactrim", "co-trimoxazole", "septra", "sulfasalazine"],
    "nsaid": ["nsaid", "nsaids", "ibuprofen", "naproxen", "ketorolac", "diclofenac", "advil", "motrin", "aleve",
              "aspirin", "indomethacin", "celecoxib"],
    "aspirin": ["aspirin", "asa"],
    "cephalosporin": ["cephalosporin", "cephalexin", "ceftriaxone", "cefazolin", "cefuroxime", "keflex"],
    "opioid": ["opioid", "opioids", "codeine", "morphine", "oxycodone", "hydrocodone", "tramadol", "fentanyl"],
    "statin": ["statin", "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
    "ace inhibitor": ["ace inhibitor", "lisinopril", "enalapril", "ramipril", "captopril"],
    "macrolide": ["macrolide", "azithromycin", "erythromycin", "clarithromycin"],
    "fluoroquinolone": ["fluoroquinolone", "ciprofloxacin", "levofloxacin", "moxifloxacin"],
    "contrast": ["contrast", "iodinated contrast", "iodine"],
    "latex": ["latex"],
}
_ALLERGY_NOISE = set("allergy allergic allergies reaction reactions rash hives anaphylaxis swelling to with and causes "
                     "caused developed known drug drugs medication medications childhood as a child severe mild".split())


MIN_HISTORY_FACTS = 5
_QUALITATIVE = {"negative", "positive", "detected", "not detected", "trace", "small", "moderate", "large", "normal", "abnormal", "pending", "nil", "none",
                "present", "absent", "reactive", "non-reactive", "clear", "cloudy"}
_STOPPED_MED = re.compile(r"\b(?:stopped|quit|no longer|not been|hasnt been|has not been|skips|skipping|ran out of|run out of)\s+(?:taking\s+|using\s+)?(?:(?:her|his|their|the|my)\s+)?"
                          r"((?:[a-z\-]+\s+){0,3}?(?:pills?|tablets?|medication|medicine|meds|inhalers?|insulin|injections?|thinners?|drops|statins?|antibiotics?|"
                          r"[a-z]+(?:pril|olol|statin|sartan|formin|dipine|xaban|semide|azide)))\b")
_MED_SYNONYMS = {
    "blood pressure": ["amlodipine", "lisinopril", "ramipril", "losartan", "metoprolol", "atenolol", "hydrochlorothiazide", "enalapril", "pressure", "antihypertensive", "doxazosin"],
    "thinner": ["apixaban", "warfarin", "rivaroxaban", "dabigatran", "anticoagulant", "thinner", "heparin"],
    "water": ["furosemide", "diuretic", "bumetanide", "water"],
    "insulin": ["insulin", "glargine", "lispro"],
    "inhaler": ["inhaler", "salbutamol", "albuterol", "budesonide", "tiotropium"],
    "diabetes": ["metformin", "insulin", "gliclazide"],
    "sugar": ["metformin", "insulin"],
    "cholesterol": ["statin", "atorvastatin", "simvastatin", "rosuvastatin"],
    "statin": ["statin", "atorvastatin", "simvastatin", "rosuvastatin"],
    "antibiotic": ["antibiotic", "amoxicillin", "nitrofurantoin", "ciprofloxacin", "trimethoprim"],
    "heart": ["metoprolol", "bisoprolol", "furosemide", "lisinopril", "heart"],
}


def _measure_ok(v: str) -> bool:
    t = v.strip().lower()
    return bool(re.fullmatch(r"[<>]?\s*-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?\s*%?", t)) or t in _QUALITATIVE or any(t.startswith(q) for q in _QUALITATIVE)


@lru_cache(maxsize=1)
def case_schema() -> dict:
    return json.loads((CONTRACTS_DIR / "case.schema.json").read_text())


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(case_schema())


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*", v)
        if m:
            return float(m.group(1))
    return None


def _words(text: str) -> set[str]:
    return set(tx.normalize(text or "").replace("-", " ").split())


def validate_case(case: dict, rubric: dict | None = None) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    consistency: list[dict] = []

    def err(path, msg):
        errors.append({"path": path, "message": msg})

    def warn(path, msg, level="info"):
        w = {"path": path, "message": msg}
        if level != "info":
            w["level"] = level          # "attention": a thin or incomplete case; approval asks for acknowledgement
        warnings.append(w)

    def contra(kind, msg, paths, level="contradiction"):
        consistency.append({"level": level, "kind": kind, "message": msg, "paths": paths})

    if not isinstance(case, dict):
        return {"ok": False, "errors": [{"path": "", "message": "case must be an object"}], "warnings": [], "consistency": []}

    for e in sorted(_validator().iter_errors(case), key=lambda e: list(e.absolute_path)):
        err("/" + "/".join(str(p) for p in e.absolute_path), e.message[:300])

    facts = [f for f in (case.get("facts") or []) if isinstance(f, dict)]
    chart = case.get("chart") if isinstance(case.get("chart"), dict) else {}
    sections = [s for s in (chart.get("sections") or []) if isinstance(s, dict)]
    artifacts = [a for a in (chart.get("artifacts") or []) if isinstance(a, dict)]
    objectives = [o for o in (case.get("objectives") or []) if isinstance(o, dict)]
    sources = [s for s in (case.get("sources") or []) if isinstance(s, dict)]

    def dupes(items, key, base):
        seen = {}
        for i, it in enumerate(items):
            k = it.get(key)
            if k is None:
                continue
            if k in seen:
                err(f"/{base}/{i}/{key}", f"duplicate {key} '{k}' (also at /{base}/{seen[k]})")
            else:
                seen[k] = i
        return seen

    fact_idx = dupes(facts, "fact_id", "facts")
    sec_idx = dupes(sections, "section_id", "chart/sections")
    art_idx = dupes(artifacts, "artifact_id", "chart/artifacts")
    obj_idx = dupes(objectives, "objective_id", "objectives")
    src_idx = dupes(sources, "source_id", "sources")
    default_sections = {sid for sid, _ in tx.CATEGORY_SECTION.values()}
    by_id = {f.get("fact_id"): f for f in facts}
    art_by_id = {a.get("artifact_id"): a for a in artifacts}

    # every request string that yields something
    requests: set[str] = set()
    for f in facts:
        d = f.get("disclosure") or {}
        if d.get("rule") == "on_request" and d.get("request"):
            requests.add(str(d["request"]).lower())
    for a in artifacts:
        r = a.get("release") or {}
        if r.get("rule") == "on_request":
            requests.add(str(r.get("request") or f"artifact:{a.get('artifact_id')}").lower())
        requests.add(f"artifact:{a.get('artifact_id')}")

    # ---- facts
    for i, f in enumerate(facts):
        p = f"/facts/{i}"
        d = f.get("disclosure") if isinstance(f.get("disclosure"), dict) else {}
        rule = d.get("rule")
        sec = f.get("chart_section")
        if sec and sec not in sec_idx and sec not in default_sections:
            err(p + "/chart_section", f"chart section '{sec}' is not defined in chart.sections")
        for sid in f.get("source_ids") or []:
            if sid not in src_idx:
                err(p + "/source_ids", f"source '{sid}' is not defined in sources")
        if rule == "after_rapport":
            rn = d.get("rapport_needed")
            if not isinstance(rn, int) or isinstance(rn, bool) or rn < 1:
                err(p + "/disclosure/rapport_needed", "after_rapport needs rapport_needed (integer >= 1)")
        if rule == "denied_until_confronted":
            cw = d.get("confront_with") or []
            if not cw:
                err(p + "/disclosure/confront_with", "denied_until_confronted needs confront_with (fact or artifact IDs the learner must have seen)")
            for c in cw:
                if c not in by_id and c not in art_by_id:
                    err(p + "/disclosure/confront_with", f"confront_with '{c}' is neither a fact nor an artifact in this case")
                if c == f.get("fact_id"):
                    err(p + "/disclosure/confront_with", "a fact cannot be its own confrontation evidence")
            if not f.get("cover_answer"):
                err(p + "/cover_answer", "denied_until_confronted needs an authored cover_answer (what the patient says while denying)")
        if rule == "on_request":
            req = d.get("request")
            if not req:
                err(p + "/disclosure/request", "on_request needs request (e.g. 'order:troponin', 'exam:abdomen')")
            elif not re.match(r"^(order|exam|artifact):[a-z0-9_\-]+$", str(req).lower()):
                warn(p + "/disclosure/request", f"request '{req}' is not of the form order:<name> / exam:<name> / artifact:<id>")
        if rule in PATIENT_VOICED:
            if f.get("patient_knows") is False:
                err(p + "/patient_knows", f"rule '{rule}' is voiced by the patient, but patient_knows is false (use chart_initial or on_request)")
            elif not (f.get("patient_answer") or "").strip():
                err(p + "/patient_answer", "the patient knows this fact but has no patient_answer wording to voice it")
            elif f.get("patient_answer_auto"):
                warn(p + "/patient_answer", "patient_answer was auto-drafted from the statement; review the wording")
            if not f.get("topics") and len(str(f.get("fact_id", "")).split(".")[-1]) < 4:
                warn(p + "/topics", "no topics: the offline matcher can only use the fact ID slug and category")
        if rule == "after_rapport" and not f.get("cover_answer"):
            warn(p + "/cover_answer", "no cover_answer: the patient gives a neutral deflection until rapport is reached")
        pa, pol = tx.normalize(f.get("patient_answer") or ""), f.get("polarity")
        if pa and pol == "negative" and re.match(r"^(yes|yeah|yep)\b", pa):
            contra("polarity_vs_answer", f"{f.get('fact_id')}: polarity is negative but the patient answer begins with yes", [p], "warning")
        if pa and pol == "positive" and re.match(r"^(no|nope|never)\b", pa) and rule != "denied_until_confronted":
            contra("polarity_vs_answer", f"{f.get('fact_id')}: polarity is positive but the patient answer begins with no", [p], "warning")

    # ---- artifacts
    for i, a in enumerate(artifacts):
        p = f"/chart/artifacts/{i}"
        if a.get("section_id") and a["section_id"] not in sec_idx and a["section_id"] not in default_sections:
            err(p + "/section_id", f"chart section '{a['section_id']}' is not defined")
        for fid in a.get("linked_fact_ids") or []:
            if fid not in by_id:
                err(p + "/linked_fact_ids", f"linked fact '{fid}' does not exist")
        for sid in a.get("source_ids") or []:
            if sid not in src_idx:
                err(p + "/source_ids", f"source '{sid}' is not defined in sources")
        r = a.get("release") if isinstance(a.get("release"), dict) else {}
        if r.get("rule") == "on_fact":
            if not r.get("fact_id"):
                err(p + "/release/fact_id", "release rule on_fact needs fact_id")
            elif r["fact_id"] not in by_id:
                err(p + "/release/fact_id", f"release fact '{r['fact_id']}' does not exist")
        if a.get("content") in (None, "", []) and not a.get("asset"):
            warn(p, "artifact has neither content nor an asset")

    # ---- objectives
    domain_keys = None
    if rubric:
        from .rubric import canonical_domain
        domain_keys = {d.get("key") for d in rubric.get("domains", [])} | {canonical_domain(d) for d in rubric.get("domains", [])}
    for i, o in enumerate(objectives):
        p = f"/objectives/{i}"
        lf, lr = o.get("linked_fact_ids") or [], [str(r).lower() for r in (o.get("linked_requests") or [])]
        for fid in lf:
            if fid not in by_id:
                err(p + "/linked_fact_ids", f"linked fact '{fid}' does not exist")
        for r in lr:
            if r not in requests:
                warn(p + "/linked_requests", f"request '{r}' releases nothing in this case (no fact or artifact uses it)")
        kind = o.get("kind")
        if kind == "elicit_fact" and not lf:
            err(p + "/linked_fact_ids", "elicit_fact objective has no linked facts: there is no evidence path to assess it")
        elif kind == "action" and not lr and not lf:
            err(p + "/linked_requests", "action objective has no linked requests or facts: there is no evidence path to assess it")
        elif kind in ("communication", "sequencing", "reasoning", "safety") and not (lf or lr or o.get("evidence_rule") or o.get("rubric_domain")):
            err(p, f"{kind} objective has no evidence path (add evidence_rule, rubric_domain, linked facts or requests)")
        if domain_keys is not None and o.get("rubric_domain"):
            from .rubric import canonical_key
            if o["rubric_domain"] not in domain_keys and canonical_key(o["rubric_domain"]) not in domain_keys:
                warn(p + "/rubric_domain", f"rubric domain '{o['rubric_domain']}' is not in rubric '{rubric.get('rubric_id', '')}'")
    for i, s in enumerate(sources):
        for sup in s.get("supports") or []:
            if sup not in by_id and sup not in obj_idx and sup not in art_idx:
                err(f"/sources/{i}/supports", f"'{sup}' is not a fact, objective or artifact in this case")

    # ---- reachability of critical facts
    def reachable(f, seen=()):
        d = f.get("disclosure") or {}
        rule = d.get("rule")
        if rule in ("chart_initial", "volunteered", "if_asked", "after_rapport"):
            return rule == "chart_initial" or f.get("patient_knows") is not False
        if rule == "on_request":
            return bool(d.get("request"))
        if rule == "denied_until_confronted":
            if f.get("patient_knows") is False:
                return False
            for c in d.get("confront_with") or []:
                if c in art_by_id:
                    return True
                g = by_id.get(c)
                if g and c not in seen and reachable(g, seen + (f.get("fact_id"),)):
                    return True
            return False
        return False

    for i, f in enumerate(facts):
        if not reachable(f):
            msg = f"{f.get('fact_id')} can never be released by any rule (check patient_knows, request, or confrontation evidence)"
            if f.get("critical"):
                err(f"/facts/{i}/disclosure", "critical fact " + msg)
            else:
                warn(f"/facts/{i}/disclosure", msg)
    linked_by_obj = {fid for o in objectives for fid in (o.get("linked_fact_ids") or [])}
    for i, f in enumerate(facts):
        if f.get("critical") and f.get("fact_id") not in linked_by_obj:
            warn(f"/facts/{i}", f"critical fact {f.get('fact_id')} is not linked to any objective")
    ft = case.get("faculty_truth") or {}
    for o in ft.get("expected_orders") or []:
        if str(o).lower() not in requests:
            warn("/faculty_truth/expected_orders", f"expected order '{o}' releases nothing in this case")

    # ---- consistency
    # (a) the same thing stated twice with different value / polarity
    groups: dict[str, list[int]] = {}
    for i, f in enumerate(facts):
        slug = str(f.get("fact_id", "")).split(".")[-1]
        if slug:
            groups.setdefault(slug, []).append(i)
    for slug, idxs in groups.items():
        for a_i in range(len(idxs)):
            for b_i in range(a_i + 1, len(idxs)):
                fa, fb = facts[idxs[a_i]], facts[idxs[b_i]]
                pa_, pb_ = fa.get("polarity"), fb.get("polarity")
                va, vb = fa.get("value"), fb.get("value")
                paths = [f"/facts/{idxs[a_i]}", f"/facts/{idxs[b_i]}"]
                if pa_ and pb_ and pa_ != pb_ and "unknown" not in (pa_, pb_):
                    contra("fact_polarity", f"{fa['fact_id']} and {fb['fact_id']} describe '{slug}' with opposite polarity", paths)
                elif va is not None and vb is not None and va != vb and (
                        (_num(va) is not None and _num(vb) is not None)
                        or (fa.get("category") == fb.get("category") and isinstance(va, str) and isinstance(vb, str)
                            and len(va.split()) <= 4 and len(vb.split()) <= 4)):
                    contra("fact_value", f"{fa['fact_id']} ({va}) and {fb['fact_id']} ({vb}) give different values for '{slug}'", paths)
    # (b) artifact rows against linked facts
    for i, a in enumerate(artifacts):
        rows = a.get("content") if isinstance(a.get("content"), list) else []
        for fid in a.get("linked_fact_ids") or []:
            f = by_id.get(fid)
            if not f:
                continue
            fv = _num(f.get("value"))
            if fv is None:
                continue
            slug_words = set(fid.split(".")[-1].split("_")) | _words(f.get("label") or "")
            for r_i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                if row.get("fact_id") == fid or (not row.get("fact_id") and slug_words & _words(str(row.get("test", "")).replace("_", " "))):
                    rv = _num(row.get("value"))
                    paths = [f"/chart/artifacts/{i}/content/{r_i}", f"/facts/{fact_idx.get(fid)}"]
                    if rv is not None and abs(rv - fv) > 1e-9:
                        contra("artifact_value", f"artifact {a.get('artifact_id')} reports {row.get('test')} = {row.get('value')} but fact {fid} says {f.get('value')}", paths)
                    elif rv is not None and row.get("unit") and f.get("unit") and str(row["unit"]).lower() != str(f["unit"]).lower():
                        contra("artifact_unit", f"artifact {a.get('artifact_id')} reports {row.get('test')} in {row.get('unit')} but fact {fid} uses {f.get('unit')}", paths, "warning")
    # (c) allergies against medications
    meds = [(i, f) for i, f in enumerate(facts) if f.get("category") == "medications"]
    allergies = [(i, f) for i, f in enumerate(facts) if f.get("category") == "allergies"]
    pos_all = [(i, f) for i, f in allergies if f.get("polarity", "positive") != "negative"
               and not re.search(r"\b(no known|nkda|none|no allergies|denies)\b", tx.normalize(f"{f.get('statement', '')} {f.get('value', '')}"))]
    neg_all = [(i, f) for i, f in allergies if (i, f) not in pos_all]
    if pos_all and neg_all:
        contra("allergy_polarity", "the case states both 'no known allergies' and a specific allergy",
               [f"/facts/{neg_all[0][0]}", f"/facts/{pos_all[0][0]}"])
    for ai, af in pos_all:
        atext = f"{af.get('statement', '')} {af.get('value', '') if isinstance(af.get('value'), str) else ''}"
        awords = _words(atext) - _ALLERGY_NOISE - tx.STOPWORDS
        aclasses = {c for c, members in DRUG_CLASSES.items() if awords & set(members) or c in tx.normalize(atext)}
        for mi, mf in meds:
            if mf.get("polarity") == "negative":
                continue
            mtext = f"{mf.get('statement', '')} {mf.get('value', '') if isinstance(mf.get('value'), str) else ''}"
            mwords = _words(mtext)
            hit = None
            for c in aclasses:
                inter = mwords & set(DRUG_CLASSES[c])
                if inter:
                    hit = f"{sorted(inter)[0]} (allergy class: {c})"
            direct = {w for w in awords & mwords if len(w) > 4}
            if not hit and direct:
                hit = sorted(direct)[0]
            if hit:
                contra("allergy_vs_medication", f"allergy {af.get('fact_id')} conflicts with medication {mf.get('fact_id')}: {hit}",
                       [f"/facts/{ai}", f"/facts/{mi}"])
    # (d) ages
    age = (case.get("profile") or {}).get("age")
    if isinstance(age, int) and not isinstance(age, bool):
        texts = [("/title", case.get("title")), ("/prebrief", case.get("prebrief")), ("/profile/background", (case.get("profile") or {}).get("background"))]
        texts += [(f"/chart/sections/{i}/static_text", s.get("static_text")) for i, s in enumerate(sections)]
        texts += [(f"/facts/{i}/statement", f.get("statement")) for i, f in enumerate(facts)]
        texts += [(f"/facts/{i}/patient_answer", f.get("patient_answer")) for i, f in enumerate(facts)]
        texts += [(f"/chart/artifacts/{i}/content", a.get("content")) for i, a in enumerate(artifacts) if isinstance(a.get("content"), str)]
        for path, t in texts:
            if not isinstance(t, str):
                continue
            for m in re.finditer(r"\b(\d{1,3})[- ]year[- ]old\b", t.lower()):
                n = int(m.group(1))
                # "my 12-year-old son" is not the patient: only flag statements about the patient
                before = t.lower()[max(0, m.start() - 12): m.start()]
                if n != age and not re.search(r"\b(my|his|her|their)\s*$", before):
                    contra("age", f"text says {n}-year-old but profile.age is {age}", [path, "/profile/age"])
            if not re.search(r"\b(father|mother|dad|mom|brother|sister|parent|grand|uncle|aunt|wife|husband|son|daughter)", t.lower()):
                for m in re.finditer(r"\b(?:for|over|past|last)\s+(?:about\s+|the\s+(?:last|past)\s+)?(\d{1,3})\s+years\b", t.lower()):
                    if int(m.group(1)) > age:
                        contra("age", f"a duration of {m.group(1)} years exceeds the patient's age ({age})", [path, "/profile/age"])
        for i, f in enumerate(facts):
            if str(f.get("fact_id", "")).split(".")[-1] == "age" and _num(f.get("value")) is not None and int(_num(f.get("value"))) != age:
                contra("age", f"{f['fact_id']} says {f.get('value')} but profile.age is {age}", [f"/facts/{i}", "/profile/age"])
        if age < 0 or age > 120:
            err("/profile/age", "age must be between 0 and 120")

    # ---- thin or malformed cases (D18): never silent
    voiced = [f for f in facts if (f.get("disclosure") or {}).get("rule") in PATIENT_VOICED and f.get("patient_knows") is not False]
    if not any(f.get("category") == "chief_complaint" for f in facts):
        err("/facts", "no chief complaint: add a fact with category chief_complaint so the patient can say why they came. "
                      "A case without one cannot be approved or published")
    src = (case.get("review") or {}).get("source_description") if isinstance(case.get("review"), dict) else None
    if isinstance(src, str) and src.strip():
        from .coverage import coverage_report
        cov = coverage_report(case)
        if cov["uncovered"]:
            shown = "; ".join(f"\"{u['text'][:90]}\" (not found: {', '.join(u['missing_words'][:5])})" for u in cov["uncovered"][:3])
            warn("/review/source_description", f"description coverage incomplete: {len(cov['uncovered'])} of {cov['sentences']} sentence(s) of the source description "
                                               f"are not fully reflected in any fact or artifact: {shown}", "attention")
    history = [f for f in voiced if f.get("category") not in ("chief_complaint",)]
    if len(history) < MIN_HISTORY_FACTS:
        warn("/facts", f"only {len(history)} history fact(s) the patient can talk about (fewer than {MIN_HISTORY_FACTS}): most questions will get "
                       "a default answer. Add history, medicines, allergies and social facts", "attention")
    if not str(ft.get("diagnosis") or "").strip():
        warn("/faculty_truth/diagnosis", "no diagnosis in the faculty truth: the debrief cannot say what the case was", "attention")
    if ft.get("expected_disposition") not in ("discharge", "admit", "transfer"):
        warn("/faculty_truth/expected_disposition", "no expected disposition: the learner's decision cannot be judged", "attention")
    if not objectives:
        warn("/objectives", "no learning objectives: feedback cannot be tied to what you want taught", "attention")
    has_initial = any((f.get("disclosure") or {}).get("rule") == "chart_initial" for f in facts) or \
        any((a.get("release") or {}).get("rule") == "initial" for a in artifacts) or any(s_.get("release") == "initial" and s_.get("static_text") for s_ in sections)
    if not has_initial:
        warn("/chart", "nothing is in the chart at the start (no chart_initial fact, initial artifact or section text): add a triage note or vital signs", "attention")
    for i, f in enumerate(facts):
        d = f.get("disclosure") or {}
        if f.get("category") == "concealed" and d.get("rule") == "after_rapport":
            warn(f"/facts/{i}/disclosure", f"{f.get('fact_id')} is concealed with no evidence path: it opens up through rapport only. "
                                           "Add an artifact and use denied_until_confronted if the learner should be able to confront it")
        if f.get("category") in ("lab", "vitals") and f.get("unit") and isinstance(f.get("value"), str) and not _measure_ok(f["value"]):
            err(f"/facts/{i}/value", f"{f.get('fact_id')} has unit '{f['unit']}' but its value '{f['value']}' is not a number")
    for i, a in enumerate(artifacts):
        rows = a.get("content") if isinstance(a.get("content"), list) and a.get("kind") == "lab_report" else []
        for r_i, row in enumerate(rows):
            if isinstance(row, dict) and "value" in row and isinstance(row["value"], str) and not _measure_ok(row["value"]) and \
                    (row.get("unit") or re.search(r"\d", str(row.get("ref_range") or ""))):
                err(f"/chart/artifacts/{i}/content/{r_i}/value", f"lab row '{row.get('test')}' has a numeric unit or reference range but its value '{row['value']}' is not a number")
    # a medicine the story says was stopped must be on the medication list
    med_text = " ".join(tx.normalize(f"{f.get('statement', '')} {f.get('patient_answer', '')}") for f in facts if f.get("category") == "medications").replace("-", " ")
    for i, f in enumerate(facts):
        if f.get("category") == "medications":
            continue
        m = _STOPPED_MED.search(tx.normalize(f.get("statement") or "").replace("-", " "))
        if not m:
            continue
        drug = m.group(1).strip()
        words = {w for w in drug.split() if len(w) > 3 and w not in ("pill", "pills", "tablet", "tablets", "medication", "medicine", "meds", "taking", "blood")}
        alts = set(words)
        for key, members in _MED_SYNONYMS.items():
            if key in drug:
                alts |= set(members)
        if not med_text.strip():
            contra("stopped_medication_not_listed", f"{f.get('fact_id')} says the patient stopped '{drug}', but the case has no medication list", [f"/facts/{i}"])
        elif not any(w in med_text for w in alts):
            contra("stopped_medication_not_listed", f"{f.get('fact_id')} says the patient stopped '{drug}', but no medication fact mentions it", [f"/facts/{i}"])

    blocking = [c for c in consistency if c["level"] == "contradiction"]
    return {"ok": not errors and not blocking, "errors": errors, "warnings": warnings, "consistency": consistency,
            "needs_acknowledgement": any(w.get("level") == "attention" for w in warnings)}
