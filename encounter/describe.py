"""Studio "from a description" path: free text -> an honest, sparse DRAFT case.

Rule: the draft contains what the text states and nothing else. The closest condition template is used
only as scaffolding (chart sections, generic objectives, rubric link, and the standard-workup defaults the
encounter can fall back to); none of its symptoms, history, medicines or results are copied in. Whatever
the text does not say is reported as missing so the author can fill it in.

Returns {"case", "notes", "method", "fallback", "template_id", "taken", "scaffolded", "missing"}.
"""
from __future__ import annotations

import hashlib
import re

from . import taxonomy as tx
from .providers import Provider, ProviderError
from .store import _VERB_3RD, fill_defaults, slugify

NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "twelve": 12, "several": "several", "few": "a few", "couple": "a couple of"}
_UNIT = r"(?:minutes?|hours?|days?|weeks?|months?|years?)"
_N = r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|several|a few|a couple of)"

_AGE = re.compile(r"\b(\d{1,3})\s*[- ]?\s*(?:year[- ]old|years? old|yo|y/o|y\.o\.)\b", re.I)
_AGE2 = re.compile(r"\b(?:age|aged)\s*(\d{1,3})\b|^[^,.]{2,40},\s*(\d{1,3})\s*,", re.I)
_OCC3 = re.compile(r",\s*\d{1,3},\s+(?:an?\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|and|presenting|presents|comes|came)\b|[,.;])", re.I)
_NAME_LEAD = re.compile(r"^\s*(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?([A-Z][a-z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2})(?=\s*(?:,|\(|:|\bis\b|\bhas\b|\bcomes\b|\bpresents\b|\bwas\b|\barrives\b|\bcame\b))")
_NAME_ANY = re.compile(r"\b(?:[Nn]amed|[Nn]ame is|[Cc]alled|[Pp]atient:?|Mrs?\.?|Ms\.?|Miss)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)")
_OCC1 = re.compile(r"(?:year[- ]old|years old|yo|y/o),?\s+(?:(?:fe)?male\s+|man\s+|woman\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|presenting|presents|comes|came|complaining|brought|arrives|has|had|in)\b|[,.;])", re.I)
_OCC2 = re.compile(r"\b(?:works? as|working as|employed as|job as|is)\s+(?:an?\s+)(?:retired\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|and|presenting|presents|comes|came)\b|[,.;]|$)", re.I)
_NOT_JOB = re.compile(r"^(man|woman|male|female|patient|lady|gentleman|boy|girl|person|adult|child|smoker|diabetic|\d)", re.I)
_PRESENT = re.compile(r"\b(?:comes? in with|came in with|presents? with|presenting with|presented with|complains? of|complaining of|brought in (?:with|for|after)|"
                      r"arrives? with|has had|has been having|is having|(?:year[- ]old|years old|yo|y/o)(?:\s+[a-z\-]+){0,4}?\s+with|has)\s+(.+?)(?=[.;]|$)", re.I | re.S)
_DUR_OF = re.compile(rf"^({_N})\s+({_UNIT})\s+of\s+(.+)$", re.I)
_DUR_FOR = re.compile(rf"^(.+?)\s+(?:for|over|during)\s+(?:the\s+(?:last|past)\s+)?({_N})\s+({_UNIT})\b(.*)$", re.I)
_DUR_SINCE = re.compile(r"^(.+?)\s+(since\s+(?:yesterday|this morning|last night|last week|\w+day|\w+ \w+))\b(.*)$", re.I)
_HIDE = re.compile(r"\b(?:is hiding|hides|hiding|conceals|concealing|is concealing|denies|will deny|won'?t (?:admit|mention|say|tell (?:you|anyone))|"
                   r"doesn'?t (?:admit|mention|want to (?:say|admit|talk about))|does not (?:admit|mention|want to (?:say|admit|talk about))|"
                   r"is reluctant to (?:admit|discuss|talk about|mention)|reluctant to (?:admit|discuss|talk about|mention)|"
                   r"is embarrassed (?:about|to admit|by)|embarrassed (?:about|to admit|by)|ashamed (?:of|to admit)|secretly|"
                   r"avoids? (?:talking about|mentioning|discussing)|minimi[sz]es|downplays|under-?reports|not forthcoming about|"
                   r"has not told anyone|hasn'?t told anyone|keeps quiet about)\b\s*(?:that\s+|to\s+|about\s+|the fact that\s+)?(.+?)(?=\.(?:\s|$)|;|$)", re.I | re.S)
_STOPPED = re.compile(r"\b(?:stopped|quit|not|isn'?t|hasn'?t been|skips?|skipping|misses|missing)\s+(?:taking\s+|been taking\s+)?(?:(?:her|his|their|the|my)\s+)?"
                      r"([a-z][a-z\- ]{2,40}?(?:pills?|tablets?|medication|medicine|meds|inhalers?|insulin|injections?|thinners?|drops|patch(?:es)?|statins?|antibiotics?))\b", re.I)
_VITALS = [
    ("blood_pressure", "Blood pressure", "mmHg", re.compile(r"\b(?:bp|blood[- ]pressure)\s*(?:is|was|of|:|=)?\s*(\d{2,3}\s*/\s*\d{2,3})", re.I)),
    ("heart_rate", "Heart rate", "beats/min", re.compile(r"\b(?:hr|heart[- ]rate|pulse)\s*(?:is|was|of|:|=)?\s*(\d{2,3})\b", re.I)),
    ("temperature", "Temperature", "", re.compile(r"\b(?:temp(?:erature)?|fever)\s*(?:is|was|of|:|=)?\s*(\d{2,3}(?:\.\d)?)\s*(?:°|degrees)?\s*([CF])?\b", re.I)),
    ("spo2", "Oxygen saturation", "%", re.compile(r"\b(?:spo2|sp02|o2 sats?|sats?|oxygen saturation|saturations?)\s*(?:is|are|was|of|:|=)?\s*(\d{2,3})\s*%?", re.I)),
    ("respiratory_rate", "Respiratory rate", "breaths/min", re.compile(r"\b(?:rr|resp(?:iratory)? rate)\s*(?:is|was|of|:|=)?\s*(\d{1,2})\b", re.I)),
    ("glucose", "Blood glucose", "mg/dL", re.compile(r"\b(?:glucose|blood sugar|sugar)\s*(?:is|was|of|:|=)?\s*(\d{2,3})\b", re.I)),
]
_PMH = re.compile(r"\b(?:history of|known|long-?standing|has had|diagnosed with|suffers from|lives with|past medical history(?: of|:)?)\s+([a-z0-9][^.;]{2,80}?)(?=,?\s+(?:takes|taking|on|and takes|who|brought|presents|comes)\b|[.;]|$)", re.I)
_PMH_HAS = re.compile(r"\bhas\s+((?:type [12] )?(?:diabetes|hypertension|high blood pressure|asthma|copd|heart failure|atrial fibrillation|epilepsy|"
                      r"depression|anxiety|high cholesterol|kidney disease|migraines?|arthritis|cancer|hiv|angina)[^.;]{0,50})", re.I)
_MEDS = re.compile(r"\b(?:takes|taking|is on|on|prescribed|uses)\s+((?:[a-z]+(?:pril|olol|statin|sartan|formin|dipine|parin|xaban|cillin|mycin|azole|prazole|ine|ide|one|pam|in)\b|"
                   r"insulin|aspirin|warfarin|an? [a-z\- ]{0,20}inhaler|blood[- ]pressure (?:pills?|tablets?|medication)|blood thinners?|the pill|birth control)[^.;]{0,60})", re.I)
_ALLERGY = re.compile(r"\ballerg(?:ic|y) to\s+([a-z][^.;,]{2,40})", re.I)
_NO_ALLERGY = re.compile(r"\bno (?:known )?(?:drug )?allergies\b|\bnkda\b", re.I)
_LIVES = re.compile(r"\b(lives (?:alone|with [^.;,]{2,40}|in [^.;,]{2,40})|is (?:married|widowed|divorced|single|homeless)[^.;,]{0,30})", re.I)
_WORRY = re.compile(r"\b(?:is |feels |feeling )?(worried|anxious|afraid|scared|frightened|concerned|terrified|stressed|embarrassed)\s+(about|that|of|by)\s+([^.;]{3,90})", re.I)
_SMOKES = re.compile(r"\b((?:smokes?|vapes?)\s+[^.;]{0,50}|(?:non-?smoker|never smoked|ex-?smoker[^.;]{0,30}|smoker))", re.I)
_DRINKS = re.compile(r"\b(drinks\s+[^.;]{2,60}|does not drink(?: alcohol)?|doesn'?t drink(?: alcohol)?|teetotal)", re.I)
_SEVERITY_HI = re.compile(r"\b(severe|critical|unstable|crushing|worst|collapsed|septic|unresponsive)\b", re.I)
_SEVERITY_LO = re.compile(r"\b(mild|minor|slight|stable)\b", re.I)

_TOPIC_HINTS = [("alcohol", r"alcohol|drink|beer|wine|vodka|whisk|liquor|gin\b"), ("drugs", r"cocaine|heroin|opioid|drug|marijuana|cannabis|meth|stimulant|oxycodone"),
                ("smoking", r"smok|cigarette|vap|tobacco|nicotine"), ("adherence", r"medic|pill|insulin|inhaler|tablet|dose|adheren|complian|prescri|stopped taking|thinner"),
                ("sexual_history", r"\bsex|condom|partner|\bsti\b|\bstd\b"), ("mood", r"depress|mood|sad|anxi|suicid|grief|lonely"),
                ("diet", r"diet|eat|food|salt|sugar|fruit|vegetable"), ("bowel", r"constipat|bowel|stool|diarrh"), ("safety_at_home", r"abuse|violence|unsafe|hit by|hurt by"),
                ("pregnancy", r"pregnan"), ("injury_mechanism", r"\bfell\b|fall|accident")]
COVERS = {"alcohol": "I drink socially, like anyone.", "drugs": "No, nothing like that.", "smoking": "Not really, no.",
          "adherence": "I take what I'm supposed to.", "sexual_history": "I'd rather not get into that.", "mood": "I'm fine. Just tired.",
          "diet": "I eat okay, I guess.", "bowel": "Everything's fine there.", "safety_at_home": "Everything is fine at home.",
          "pregnancy": "No, I don't think so.", "injury_mechanism": "I just slipped. It was nothing."}
_OBJECT_VERBS = r"(made|makes|make|gave|gives|give|told|tells|tell|helped|helps|help|let|lets|kept|keeps|keep|left|leaves|leave|caused|causes|hit|hits|scared|scares|worried|worries|bothers?|woke|wakes)"


def first_person(clause: str, name: str = "") -> str:
    """Third-person clause from a description -> what the patient would say. Conservative, flagged for review."""
    s = re.sub(r"\s+", " ", clause.strip().rstrip("."))
    first = name.split()[0] if name else ""
    subj = r"(?:she|he" + (("|" + re.escape(first)) if first else "") + r")"
    s = re.sub(rf"\b{_OBJECT_VERBS}\s+(?:her|him|them)\b", r"\1 me", s, flags=re.I)
    s = re.sub(rf"\b{subj}\s+(?:is|was)\s+not\b", "I am not", s, flags=re.I)
    s = re.sub(rf"\b{subj}\s+is\b", "I am", s, flags=re.I)
    s = re.sub(rf"\b{subj}\s+was\b", "I was", s, flags=re.I)
    s = re.sub(rf"\b{subj}\s+has\b", "I have", s, flags=re.I)
    s = re.sub(rf"\b{subj}\s+(?:does not|doesn'?t)\b", "I don't", s, flags=re.I)

    def verb(m):
        v = m.group(1)
        low = v.lower()
        if low in _VERB_3RD:
            return "I " + _VERB_3RD[low]
        if low.endswith(("ches", "shes", "sses", "xes")):
            return "I " + low[:-2]
        if low.endswith("ies"):
            return "I " + low[:-3] + "y"
        if low.endswith("s") and not low.endswith(("ss", "us", "is")):
            return "I " + low[:-1]
        return "I " + v
    s = re.sub(rf"\b{subj}\s+([a-z']+)", verb, s, flags=re.I)
    s = re.sub(r"\b(?:her|his|their)\b(?=\s+[a-z])", "my", s, flags=re.I)
    s = re.sub(r"\b(?:her|him|them)\b", "me", s, flags=re.I)
    s = re.sub(r"\b(?:herself|himself|themselves)\b", "myself", s, flags=re.I)
    low = s.lower()
    if not re.match(r"^(i|my|no|yes)\b", low):
        w = s.split(" ", 1)
        if w[0].lower() in _VERB_3RD:
            s = "I " + _VERB_3RD[w[0].lower()] + (" " + w[1] if len(w) > 1 else "")
        elif re.match(r"^[a-z]+(ed|ing)\b", low):
            s = ("I " if re.match(r"^[a-z]+ed\b", low) else "I was ") + s[0].lower() + s[1:]
        else:
            s = "It's the " + s[0].lower() + s[1:] if len(s.split()) <= 4 else s
    s = re.sub(r"\bI am\b", "I'm", s)
    return s[0].upper() + s[1:] + "."


def _topic_keys(text: str, limit: int = 4) -> list[str]:
    toks = tx.tokens(text)
    hits = []
    for key, phrases in tx.TOPICS.items():
        if key in ("chief_complaint", "duration", "onset", "character", "location", "severity", "identity", "associated_symptoms", "patient_concerns"):
            continue
        best = max((len(tx.tokens(p)) for p in phrases if tx.contains_phrase(toks, tx.tokens(p))), default=0)
        if best:
            hits.append((best, key))
    hits.sort(reverse=True)
    return [k for _, k in hits[:limit]]


def _dur_words(n: str, unit: str) -> str:
    n = n.lower()
    val = NUM_WORDS.get(n, n)
    if val in (1, "1"):
        return f"a{'n' if unit[0] in 'aeiou' or unit.startswith('hour') else ''} {unit.rstrip('s')}"
    return f"{n} {unit if unit.endswith('s') else unit + 's'}"


def extract(text: str) -> dict:
    """Pull out only what the description states."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    out: dict = {"vitals": [], "concealed": [], "pmh": [], "meds": [], "social": [], "concerns": [], "symptoms": []}
    m = _AGE.search(t) or _AGE2.search(t)
    if m:
        n = int(next(g for g in m.groups() if g))
        if 0 < n < 121:
            out["age"] = n
    low = t.lower()
    if re.search(r"\b(woman|female|she|her|mrs|ms|girl|lady)\b", low):
        out["gender"] = "female"
    elif re.search(r"\b(man|male|he|his|him|mr|boy|gentleman)\b", low):
        out["gender"] = "male"
    m = _NAME_LEAD.search(t) or _NAME_ANY.search(t)
    if m and m.group(1).split()[0] not in ("A", "An", "The", "This", "Patient", "She", "He"):
        out["name"] = m.group(1).strip()
    for rx in (_OCC1, _OCC3, _OCC2):
        m = rx.search(t)
        if m:
            job = m.group(1).strip()
            if 1 <= len(job.split()) <= 4 and not _NOT_JOB.match(job) and not re.search(r"\b(old|year|with|pain|history)\b", job):
                out["occupation"] = job
                break
    # the concealed element(s) first, so their text is not re-read as ordinary history
    hidden_spans = []
    for m in _HIDE.finditer(t):
        phrase = m.group(1).strip().rstrip(".")
        if len(phrase) >= 4:
            out["concealed"].append(phrase)
            hidden_spans.append((m.start(), m.end()))
    visible = t
    for a, b in reversed(hidden_spans):
        visible = visible[:a] + " " + visible[b:]
    # presenting complaint and duration
    m = _PRESENT.search(visible)
    if m:
        comp = m.group(1).strip()
        after = bool(re.search(r"after\s*$", m.group(0)[: m.start(1) - m.start(0)], re.I))
        comp = re.sub(r",?\s*\b(?:critical|critically ill|unstable|stable)\s*$", "", comp, flags=re.I).strip()
        out["complaint_lead"] = "after" if after else ("article" if re.match(r"^(?:a|an)\s", comp, re.I) else "")
        out["complaint_raw"] = comp
        comp = re.sub(r"^(?:a|an|the)\s+", "", comp)
        dur = None
        d = _DUR_OF.match(comp)
        if d:
            dur, comp = _dur_words(d.group(1), d.group(2)), d.group(3)
        else:
            d = _DUR_FOR.match(comp)
            if d:
                dur, comp = _dur_words(d.group(2), d.group(3)), (d.group(1) + d.group(4)).strip()
            else:
                d = _DUR_SINCE.match(comp)
                if d:
                    dur, comp = d.group(2), (d.group(1) + d.group(3)).strip()
        comp = re.sub(r"\s+(?:that|which)\s+(?:started|began).*$", "", comp).strip(" ,")
        if comp and len(comp) < 160 and not re.match(r"^(history|type [12]|diabetes|hypertension|asthma|copd)\b", comp, re.I):
            out["complaint"] = comp
            out["symptoms"] = [re.sub(r"^(?:a|an|the|some)\s+", "", p.strip()) for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", comp) if p.strip()]
            if dur:
                out["duration"] = dur
    for key, label, unit, rx in _VITALS:
        m = rx.search(t)
        if m:
            val = m.group(1).replace(" ", "")
            u = unit
            if key == "temperature":
                u = (m.group(2) or ("F" if float(val) > 45 else "C")).upper()
            out["vitals"].append({"key": key, "label": label, "value": val, "unit": u})
    for rx in (_PMH, _PMH_HAS):
        for m in rx.finditer(visible):
            item = m.group(1).strip().rstrip(".")
            if _PRESENT.search(m.group(0)) and out.get("complaint") and item.lower().startswith(out["complaint"].lower()[:12]):
                continue
            if rx is _PMH and m.group(0).lower().startswith("has had") and out.get("complaint"):
                continue
            if item and all(item.lower() not in x.lower() for x in out["pmh"]):
                out["pmh"].append(item)
    for m in _MEDS.finditer(visible):
        item = m.group(1).strip().rstrip(".")
        if item and item not in out["meds"]:
            out["meds"].append(item)
    m = _ALLERGY.search(visible)
    if m:
        out["allergy"] = m.group(1).strip()
    elif _NO_ALLERGY.search(visible):
        out["allergy"] = None
    for m in _LIVES.finditer(visible):
        out["social"].append(("living_situation", m.group(1).strip()))
    m = _SMOKES.search(visible)
    if m:
        out["social"].append(("smoking", m.group(1).strip()))
    m = _DRINKS.search(visible)
    if m:
        out["social"].append(("alcohol", m.group(1).strip()))
    for m in _WORRY.finditer(visible):
        out["concerns"].append(f"{m.group(1).lower()} {m.group(2).lower()} {m.group(3).strip()}")
    out["severity"] = "severe" if _SEVERITY_HI.search(low) else ("mild" if _SEVERITY_LO.search(low) else "moderate")
    return out


def build_case(text: str, ex: dict, template: dict, model_extra: list[dict] | None = None, profile_extra: dict | None = None) -> tuple[dict, list[str], list[str], list[str]]:
    """Assemble the sparse draft. Returns (case, taken, scaffolded, missing)."""
    taken, scaffolded, missing = [], [], []
    name = ex.get("name")
    age = ex.get("age")
    gender = ex.get("gender")
    facts: list[dict] = []
    used: set[str] = set()

    def fid(cat: str, slug: str) -> str:
        base = f"f.{cat}.{slugify(slug, 'item').replace('-', '_')[:30]}"
        out, n = base, 2
        while out in used:
            out, n = f"{base}_{n}", n + 1
        used.add(out)
        return out

    if name:
        taken.append(f"name: {name}")
    else:
        missing.append("patient name (a placeholder is used)")
    if age:
        taken.append(f"age: {age}")
    else:
        missing.append("age (a placeholder of 40 is used)")
    if gender:
        taken.append(f"sex: {gender}")
    else:
        missing.append("sex")

    comp = ex.get("complaint")
    if comp:
        dur = ex.get("duration")
        stmt = comp[0].upper() + comp[1:] + (f" for {dur}" if dur and not dur.startswith("since") else (f" {dur}" if dur else ""))
        lead = ex.get("complaint_lead")
        opener = f"I had {ex.get('complaint_raw', comp)}" if lead == "after" else (f"I've got {ex.get('complaint_raw', comp)}" if lead == "article" and not dur else f"I've had {comp}")
        if dur and lead in ("after", "article") and ex.get("complaint_raw", "").endswith(comp) is False:
            opener = f"I've had {comp}"
        ans = opener + (f" for {dur}." if dur and not dur.startswith("since") else (f" {dur}." if dur else "."))
        keys = _topic_keys(comp)
        facts.append({"fact_id": fid("chief_complaint", ex["symptoms"][0] if ex.get("symptoms") else "presenting"), "category": "chief_complaint", "statement": stmt,
                      "patient_knows": True, "patient_answer": ans, "topics": ["chief_complaint"] + keys + ex.get("symptoms", []),
                      "disclosure": {"rule": "volunteered"}, "critical": True, "chart_section": "hpi", "polarity": "positive", "patient_answer_auto": True})
        taken.append(f"presenting complaint: {stmt}")
        if dur:
            facts.append({"fact_id": fid("hpi", "duration"), "category": "hpi", "statement": f"Symptoms present {('for ' + dur) if not dur.startswith('since') else dur}",
                          "patient_knows": True, "patient_answer": f"It's been {dur}." if not dur.startswith("since") else f"It started {dur[6:]}.",
                          "topics": ["onset", "duration"], "disclosure": {"rule": "if_asked"}, "chart_section": "hpi", "patient_answer_auto": True})
            taken.append(f"duration: {dur}")
        else:
            missing.append("how long the complaint has been present")
    else:
        missing.append("presenting complaint (none could be read from the text: add a chief_complaint fact)")

    if ex.get("occupation"):
        job = ex["occupation"]
        art = "an" if job[0].lower() in "aeiou" else "a"
        facts.append({"fact_id": fid("social", "occupation"), "category": "social", "statement": f"Occupation: {job}", "patient_knows": True,
                      "patient_answer": f"I'm {art} {job}.", "topics": ["occupation"], "disclosure": {"rule": "if_asked"}, "chart_section": "social"})
        taken.append(f"occupation: {job}")
    for topic, phrase in ex.get("social", []):
        facts.append({"fact_id": fid("social", topic), "category": "social", "statement": phrase[0].upper() + phrase[1:], "patient_knows": True,
                      "patient_answer": first_person(phrase, name or ""), "topics": [topic], "disclosure": {"rule": "if_asked"}, "chart_section": "social",
                      "patient_answer_auto": True})
        taken.append(f"{topic.replace('_', ' ')}: {phrase}")
    for c in ex.get("concerns", []):
        mine = re.sub(r"\b(?:her|his|their)\b(?=\s+[a-z])", "my", re.sub(r"\b(?:she|he|they)\b", "I", c, flags=re.I), flags=re.I)
        facts.append({"fact_id": fid("hpi", "concern"), "category": "hpi", "statement": "Patient is " + c, "patient_knows": True,
                      "patient_answer": f"Honestly, I'm {mine}.", "topics": ["patient_concerns", "mood"], "disclosure": {"rule": "if_asked"},
                      "chart_section": "hpi", "patient_answer_auto": True})
        taken.append(f"concern: {c}")
    for p in ex.get("pmh", []):
        facts.append({"fact_id": fid("pmh", p), "category": "pmh", "statement": p[0].upper() + p[1:], "patient_knows": True,
                      "patient_answer": f"I have {p}." if not re.match(r"^(a|an)\b", p) else f"I've had {p}.", "topics": ["pmh"] + _topic_keys(p, 2),
                      "disclosure": {"rule": "if_asked"}, "chart_section": "pmh", "polarity": "positive", "patient_answer_auto": True})
        taken.append(f"history: {p}")
    med_items = list(ex.get("meds", []))

    # concealed elements
    artifacts = []
    vital_ids = []
    for v in ex.get("vitals", []):
        f_id = fid("vitals", v["key"])
        vital_ids.append(f_id)
        num = v["value"] if "/" in v["value"] else (float(v["value"]) if "." in v["value"] else int(v["value"]))
        facts.append({"fact_id": f_id, "category": "vitals", "label": v["label"], "statement": f"{v['label']} {v['value']}{(' ' + v['unit']) if v['unit'] else ''}".strip(),
                      "value": num, "unit": v["unit"], "patient_knows": False, "topics": [v["label"].lower()], "disclosure": {"rule": "chart_initial"},
                      "chart_section": "vitals"})
        taken.append(f"vital sign: {v['label']} {v['value']} {v['unit']}".strip())
    if not ex.get("vitals"):
        missing.append("vital signs (none in the text)")

    concealed_ids = []
    for i, phrase in enumerate(ex.get("concealed", [])):
        topics = [k for k, pat in _TOPIC_HINTS if re.search(pat, phrase.lower())]
        stopped = _STOPPED.search(phrase)
        ans = first_person(phrase, name or "")
        f_id = fid("concealed", (topics[0] if topics else "hidden") + ("_stopped" if stopped else ""))
        f = {"fact_id": f_id, "category": "concealed", "statement": re.sub(r"^(she|he|they)\s+", "", phrase, flags=re.I).strip().capitalize(), "patient_knows": True,
             "patient_answer": "All right. " + ans, "topics": topics + ([stopped.group(1)] if stopped else []) + [phrase[:60]],
             "critical": True, "chart_section": "medications" if stopped else "social", "polarity": "positive", "patient_answer_auto": True, "needs_review": True}
        if stopped:
            drug = re.sub(r"\s+", " ", stopped.group(1).strip())
            if not any(drug.lower() in m.lower() for m in med_items):
                med_items.append(drug)
                scaffolded.append(f"medication list: '{drug}' added because the concealed item says the patient stopped it")
            aid = "art.pharmacy_record" if not artifacts else f"art.pharmacy_record_{i + 1}"
            artifacts.append({"artifact_id": aid, "kind": "medication_list", "title": "Pharmacy dispensing record", "section_id": "medications",
                              "release": {"rule": "on_request", "request": "order:medication_list"}, "synthetic": True, "needs_review": True,
                              "content": [{"medicine": drug[0].upper() + drug[1:], "last_dispensed": "EDIT: date of last supply", "note": "no refill collected since (placeholder: edit to match your case)"}],
                              "interpretation": f"A gap in collecting {drug}; a gap does not prove the medicine was not taken, so ask.", "linked_fact_ids": []})
            f["cover_answer"] = "I take my pills like I'm supposed to." if re.search(r"pill|tablet|med", drug) else COVERS["adherence"]
            f["disclosure"] = {"rule": "denied_until_confronted", "confront_with": [aid]}
            f["topics"] += ["adherence", "are you taking your medicines", "stopped taking", "did you stop", "stop taking", "still taking", "taking your " + drug.split()[-1]]
            scaffolded.append(f"evidence path for the concealed item: a pharmacy dispensing record ({aid}, released by 'order:medication_list') with placeholder content to edit")
        else:
            f["cover_answer"] = COVERS.get(topics[0], "I'd rather not get into that.") if topics else "I'd rather not get into that."
            f["disclosure"] = {"rule": "after_rapport", "rapport_needed": 3}
            missing.append(f"evidence in the chart for the concealed item '{phrase[:50]}' (it opens up after rapport only; add an artifact and switch the rule to denied_until_confronted if you want a confrontation)")
        scaffolded.append(f"cover answer for the concealed item: \"{f['cover_answer']}\" (generic wording: edit)")
        facts.append(f)
        concealed_ids.append(f_id)
        taken.append(f"concealed: {phrase}")
    for mi in med_items:
        facts.append({"fact_id": fid("medications", mi), "category": "medications", "statement": f"Prescribed {mi}", "patient_knows": True,
                      "patient_answer": f"I'm prescribed {'a ' if re.search(r'(pill|tablet|inhaler|thinner|patch|statin|antibiotic)$', mi) else ''}{mi}.", "topics": ["medications"] + _topic_keys(mi, 1), "disclosure": {"rule": "if_asked"},
                      "chart_section": "medications", "critical": True, "patient_answer_auto": True})
        if mi in ex.get("meds", []):
            taken.append(f"medication: {mi}")
    if not med_items:
        missing.append("medications (none stated: the offline patient will say they take nothing regular unless you add them)")
    if "allergy" in ex:
        a = ex["allergy"]
        facts.append({"fact_id": fid("allergies", a or "nkda"), "category": "allergies", "statement": f"Allergy: {a}" if a else "No known drug allergies",
                      "patient_knows": True, "patient_answer": f"I'm allergic to {a}." if a else "No allergies that I know of.", "topics": ["allergies"],
                      "disclosure": {"rule": "if_asked"}, "chart_section": "allergies", "polarity": "positive" if a else "negative", "critical": True})
        taken.append(f"allergy: {a or 'none known'}")
    else:
        missing.append("allergies")
    if not ex.get("pmh"):
        missing.append("past medical history")
    missing.append("diagnosis, differential and expected disposition in the faculty truth")
    missing.append("examination findings and test results (none are invented; undefined standard tests fall back to the template's normal result during the encounter)")

    for i, ef in enumerate(model_extra or []):
        if any(tx.normalize(ef["statement"]) == tx.normalize(f["statement"]) for f in facts):
            continue
        ef = dict(ef)
        while ef["fact_id"] in used:
            ef["fact_id"] += "_x"
        used.add(ef["fact_id"])
        facts.append(ef)
        if ef.get("cover_answer"):
            concealed_ids.append(ef["fact_id"])

    noun = {"female": "woman", "male": "man"}.get(gender or "", "patient")
    triage = f"{age or '?'}-year-old {noun}." if age else f"Adult {noun}."
    if comp:
        triage += f" {facts[0]['statement']}."
    for v in ex.get("vitals", []):
        triage += f" {v['label']} {v['value']}{(' ' + v['unit']) if v['unit'] else ''}."
    artifacts.insert(0, {"artifact_id": "art.triage_note", "kind": "document", "title": "Triage note", "section_id": "triage", "release": {"rule": "initial"},
                         "content": triage, "synthetic": True, "linked_fact_ids": []})
    scaffolded.append("triage note assembled from the stated age, sex, complaint and vital signs")

    objectives = []
    cc_ids = [f["fact_id"] for f in facts if f["category"] in ("chief_complaint", "hpi") and f["disclosure"]["rule"] != "chart_initial"][:4]
    if cc_ids:
        objectives.append({"objective_id": "obj.complaint", "criterion": "Establishes the presenting complaint and how long it has been going on", "kind": "elicit_fact",
                           "linked_fact_ids": cc_ids, "evidence_rule": "met when the linked facts are elicited", "critical": True, "rubric_domain": "gathering"})
    meds_ids = [f["fact_id"] for f in facts if f["category"] in ("medications", "allergies")]
    if meds_ids:
        objectives.append({"objective_id": "obj.medicines", "criterion": "Asks what medicines the patient takes and about allergies", "kind": "safety",
                           "linked_fact_ids": meds_ids, "evidence_rule": "met when asked", "rubric_domain": "gathering"})
    for k, cid in enumerate(concealed_ids):
        f = next(x for x in facts if x["fact_id"] == cid)
        objectives.append({"objective_id": f"obj.uncovers_{k + 1}", "criterion": "Uncovers what the patient holds back: " + f["statement"][:90], "kind": "elicit_fact",
                           "linked_fact_ids": [cid], "evidence_rule": "met when the patient discloses it", "critical": True, "rubric_domain": "listening"})
    objectives += [o for o in (template.get("objectives") or []) if o.get("objective_id") in ("obj.rapport", "obj.structure")]
    scaffolded.append(f"chart sections, the rapport and structure objectives and the rubric link from the '{template['id']}' template (no symptoms, history, medicines or results were copied from it)")

    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    sev = {"mild": 0.2, "moderate": 0.5, "severe": 0.85}[ex.get("severity", "moderate")]
    title_c = (comp or template.get("complaint_label", "presentation"))
    prof = {"name": name or "Unnamed patient", "age": age or 40, "gender": gender or "unspecified"}
    bg = []
    if ex.get("occupation"):
        bg.append(f"Occupation: {ex['occupation']}.")
    bg += [p[0].upper() + p[1:] + "." for _, p in ex.get("social", []) if _ == "living_situation"]
    if bg:
        prof["background"] = " ".join(bg)
    prof.update({k: v for k, v in (profile_extra or {}).items() if isinstance(v, str) and v.strip()})
    sections = [dict(s) for s in (template.get("chart_sections") or [])]
    case = {
        "schema_version": 1, "case_id": "draft-" + slugify(name or template["id"]) + "-" + format(seed % 0xFFFFFF, "06x"), "version": 1, "status": "draft",
        "title": f"{title_c[0].upper() + title_c[1:]} in a {age}-year-old {noun}" if age else f"{title_c[0].upper() + title_c[1:]}",
        "origin": {"kind": "from_template", "condition_template": template["id"], "sim_seed": seed},
        "review": {"author": "Drafted from a free-text description (offline pattern extraction)", "needs_faculty_review": True, "synthetic": True,
                   "source_description": text[:2000], "taken_from_text": taken, "scaffolded": scaffolded, "missing": missing},
        "intended_learner": "Medical students and first-year emergency medicine residents",
        "learner_role": "Emergency medicine resident", "setting": "Emergency department treatment bay",
        "prebrief": f"You are the emergency medicine resident. {prof['name']}, {prof['age']}, has come in" + (f" with {comp}." if comp else ".") +
                    " Take a focused history, request what you need, and decide on a disposition.",
        "profile": prof,
        "faculty_truth": {"severity": sev, "teaching_points": []},
        "facts": facts,
        "chart": {"sections": sections, "artifacts": artifacts},
        "objectives": objectives,
        "rubric_id": (template.get("rubric_links") or {}).get("rubric_id", "default"),
        "sources": [{"source_id": "description", "title": "Faculty free-text description (see review.source_description)", "role": "teaching_artifact"},
                    {"source_id": "template", "title": f"Condition template catalog/conditions/{template['id']}.yaml, used for structure only", "role": "template"}],
        "unknown_response": "I'm not sure. I can't really tell you anything about that.",
    }
    return fill_defaults(case), taken, scaffolded, missing
